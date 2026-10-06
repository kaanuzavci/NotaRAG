"""Zorluk katmanı testleri (internetsiz, gerçek kayıtlara dokunmaz). Çalıştırma: python -m tests.test_difficulty"""

import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from src import difficulty as D
from src.simulate import correct

COPY_Q = {"type": "multiple_choice", "question": "Organik tarımda sentetik gübre kullanılmaması hangi sonucu doğurur?",
          "options": ["Verim düşer", "Toprak tuzlanır", "Erozyon artar", "Su kirlenir"], "answer_index": 0,
          "answer": "Verim düşer", "evidence_quote": "Organik tarımda sentetik gübre kullanılmadığı için verim düşer",
          "bloom_level": "remember", "difficulty": "hard"}
APPLY_Q = {"type": "short_answer", "question": "x² - 6x + 4 = 0 denkleminin kökleri için x₁² + x₂² kaçtır?",
           "answer": "28", "compute": "6**2 - 2*4", "solution": ["x₁+x₂=6, x₁x₂=4", "36-8=28"],
           "evidence_quote": "x1 + x2 = -b/a", "bloom_level": "apply", "difficulty": "hard"}
ONE_OP = {**APPLY_Q, "question": "8 kişiden 3 kişilik ekip kaç farklı şekilde seçilir?", "answer": "56",
          "compute": "binomial(8, 3)", "solution": ["C(8,3)=56"]}


def test_structure() -> None:
    f = D.features(COPY_Q)
    assert f["answer_in_source"] and f["overlap"] >= 0.5
    assert D.cap(COPY_Q) == ("easy", "cevap kaynak cümlede aynen yazılı ve soru o cümleyi büyük ölçüde tekrar ediyor")
    assert D.cap({**COPY_Q, "evidence_quote": "Ürün rotasyonu toprağı korur"})[0] == "medium"  # hatırlama tavanı
    assert D.cap(APPLY_Q)[0] == "medium"  # tek kural (Vieta), iki adım: zor olamaz
    multi = {**APPLY_Q, "solution": ["genel terim", "üs koşulu r=4", "C(6,4)·16=240"], "compute": "binomial(6, 4) * (-2)**4"}
    assert D.cap(multi)[0] == "hard"  # üç adım, üç+ işlem: tavan yok
    assert D.cap(ONE_OP)[0] == "easy"  # tek formül
    assert D.features({**APPLY_Q, "compute": "Integer(26)"})["ops"] is None  # düz sayı: işlem sayısı bilinmiyor
    # "Zor" için yapısal koşul: en az iki ayrı bilgi/kural (notta bulunan ayrı alıntı) ya da çok adımlı hesap
    text_q = {**COPY_Q, "evidence_quote": "Ürün rotasyonu toprağı korur", "bloom_level": "understand"}
    assert D.cap(text_q, D.features(text_q, {"facts": 1}))[0] == "medium"
    assert D.cap(text_q, D.features(text_q, {"facts": 2}))[0] == "hard"
    assert D.features(text_q)["facts"] == 1  # eski soru: tek kanıt alıntısı
    padded = {**APPLY_Q, "compute": "Integer(26)", "solution": ["a", "b", "c", "d"]}  # şişirilmiş adım, düz sayı
    assert D.cap(padded, D.features(padded, {"facts": 1}))[0] == "medium"


def test_fact_count() -> None:
    from src.verification.checks import count_facts
    chunks = [{"page": 3, "text": "Mutasyon çeşitliliği artırır. Seçim uygun bireyleri korur."},
              {"page": 5, "text": "Çaprazlama iki ebeveynin genlerini birleştirir."}]
    # iki ayrı bilgi (iki sayfa); aynı bilgiyi tekrar eden alıntı bir kez sayılır; notta olmayan sayılmaz
    assert count_facts(["Mutasyon çeşitliliği artırır", "Çaprazlama iki ebeveynin genlerini birleştirir",
                        "mutasyon çeşitliliği artırır.", "Elitizm en iyiyi korur"], chunks) == (2, [3, 5])


def test_levels() -> None:
    # Benzetim alt sınırdır: sınıfın hepsi doğruysa (tavan) bilgi yok; çaba düzeye katılmaz (pilotta soru tipini ölçtü)
    assert D.sim_level(1.0, 80) is None and D.sim_level(1.0, 1500) is None
    assert D.sim_level(0.75) == "medium" and D.sim_level(0.5, 100) == "medium" and D.sim_level(0.25, 100) == "hard"
    # Etkin düzey: ölçüm > iddia; yapı tavanı ölçümü de kısar; gerçek öğrenci verisi kısılmaz
    it = {"id": "x", "q": dict(COPY_Q)}
    assert D.effective(it)["level"] == "easy" and D.effective(it)["capped_from"] == "hard"
    sim = {"p": 0.25, "think": 1200, "level": "hard"}
    text_q = {**COPY_Q, "evidence_quote": "Ürün rotasyonu toprağı korur", "bloom_level": "understand", "difficulty": "easy"}
    e = D.effective({"id": "y", "q": text_q, "check": {"facts": 2}}, sim=sim)
    assert e["source"] == "benzetim" and e["level"] == "hard"
    # Tavan: hepsi doğru → iddia geçerli (ölçüm düşürmez); bir yanılma kolay iddiayı ortaya çıkarır, zoru düşürmez
    ceil = {"p": 1.0, "think": 400, "level": None}
    e = D.effective({"id": "y", "q": text_q, "check": {"facts": 2}}, sim=ceil)
    assert e["source"] == "üretici" and e["level"] == "easy" and e["sim_ceiling"]
    one_miss = {"p": 0.75, "think": 400, "level": "medium"}
    assert D.effective({"id": "y", "q": text_q, "check": {"facts": 2}}, sim=one_miss)["level"] == "medium"
    hard_claim = {**text_q, "difficulty": "hard"}
    assert D.effective({"id": "y", "q": hard_claim, "check": {"facts": 2}}, sim=one_miss)["level"] == "hard"
    assert D.effective({"id": "y", "q": dict(APPLY_Q)}, sim=sim)["source"] == "üretici"  # hesap sorusu benzetilmez
    # Sözel kısa cevap da benzetilmez: metin eşleşmesi doğru ama farklı sözcüklü cevabı yanlış sayıyor (sahte p=0)
    sa_text = {**text_q, "type": "short_answer", "options": None, "answer_index": None, "answer": "Verim kaybı riski"}
    assert not D.measurable(sa_text) and D.measurable(text_q) and D.measurable({**text_q, "type": "true_false"})
    assert D.effective({"id": "y", "q": sa_text, "check": {"facts": 2}}, sim=sim)["source"] == "üretici"
    real = {"n": 6, "p": 0.2, "level": "hard"}
    assert D.effective(it, sim=sim, real=real)["level"] == "hard"
    assert D.effective(it, real={"n": 2, "p": 0.2, "level": "hard"})["level"] == "easy"  # az veri → tavan geçerli


def test_claims_and_elo() -> None:
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "llm.sqlite"
        with closing(sqlite3.connect(db)) as c:
            c.execute("CREATE TABLE cache (key TEXT, model TEXT, response TEXT, created REAL)")
            c.execute("INSERT INTO cache VALUES ('k','m',?,0)", (json.dumps({"units": [{"unit": "U1", "questions": [
                {"question": "AB - BA = 54 ise kaç AB vardır?", "difficulty": "medium"}]}]}),))
            c.commit()
        claims = D.claims_from_cache(db)
        assert claims[D.norm("AB - BA = 54 ise kaç AB vardır?")] == "medium"
        it = {"id": "z", "q": {**APPLY_Q, "question": "AB - BA = 54 ise kaç AB vardır?", "difficulty": "hard"}}
        assert D.effective(it, claims=claims)["claim"] == "medium"  # zorla yazılmış 'hard' yerine üretecin iddiası
    att = [{"id": "zor", "correct": False}] * 6 + [{"id": "kolay", "correct": True}] * 6
    r = D.elo(att)
    assert r["zor"]["d"] > 0 > r["kolay"]["d"] and r["zor"]["n"] == 6
    assert D.elo([{"id": "q", "correct": False, "retry": True}]) == {}  # ikinci denemeler sayılmaz


def test_simulated_answer_check() -> None:
    mc = {"q": {"type": "multiple_choice", "options": ["a", "b", "c", "d"], "answer_index": 2}}
    assert correct(mc, "B", [3, 2, 0, 1]) and not correct(mc, "A", [3, 2, 0, 1]) and correct(mc, "Cevap: B", [3, 2, 0, 1])
    tf = {"q": {"type": "true_false", "answer": "false"}}
    assert correct(tf, "Yanlış", None) and not correct(tf, "Doğru.", None)
    sa = {"q": {**APPLY_Q}, "check": {"computed": {"value": "28"}}}
    assert correct(sa, "28", None) and not correct(sa, "30", None)


def test_evolve_offline() -> None:
    """Zorlaştırma (PROMPTS §2d) LLM'siz: istem A ve B parçalarını taşır; iki parçadan alıntılı yeni soru 2 bilgi sayılır."""
    from src import request as R
    from src import review_store as rs
    from src.generation import generate as G
    from src.llm.router import Result
    chunks = rs.load_chunks()
    text_items = [it for it in R.all_items().values() if R.usable(it) and not it["q"].get("compute")]
    a_it, b_it = text_items[0], next(x for x in text_items if x["doc"] != text_items[0]["doc"])
    part_b = {"chunks": [chunks[c] for c in b_it["chunk_ids"]]}
    words = lambda c: " ".join(chunks[c]["text"].split()[:7])
    qa, qb = words(a_it["chunk_ids"][0]), words(b_it["chunk_ids"][0])
    seen = {}

    def fake(role, prompt, **kw):
        seen["prompt"] = prompt
        q = {"question": "İki bilgiyi birleştiren yeni soru nedir?", "type": "short_answer", "answer": "x",
             "evidence_quote": qa, "evidence_quotes": [qa, qb], "bloom_level": "apply", "difficulty": "hard"}
        return Result(json.dumps({"units": [{"unit": "U1", "questions": [q]}]}), "test-model", False)

    orig, G.call = G.call, fake
    try:
        out = G.evolve_request([(a_it, part_b)], "tr", "hard")
    finally:
        G.call = orig
    assert "EVOLVE TASK" in seen["prompt"] and "Part A:" in seen["prompt"] and "Part B:" in seen["prompt"]
    assert out and out[0]["check"]["facts"] == 2 and out[0]["requested_difficulty"] == "hard"


if __name__ == "__main__":
    test_structure()
    test_fact_count()
    test_levels()
    test_claims_and_elo()
    test_simulated_answer_check()
    test_evolve_offline()
    print("difficulty: tüm testler geçti")

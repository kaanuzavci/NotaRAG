"""Zorluk: üretecin iddiası değil, ölçüm (LITERATURE §8, ROADMAP 8).

Etiketi eldeki en güvenilir katman verir, kaynağı yanında saklanır (arayüz "ölçüldü / tahmin" diye gösterebilir):
  1. Gerçek öğrenci — çözüm kayıtlarından (attempts.jsonl, ilk denemeler) Elo; yeterli kayıt varsa (MIN_REAL).
  2. Benzetilmiş öğrenci — src/simulate.py: bir model sınıfının hızlı-cevap doğru oranı (p). Yalnızca sınıf
     yanıldığında söz sahibi (alt sınır); hepsi doğruysa (tavan) bilgi vermez. Dikkatli çözümün düşünme token'ı
     (çaba) kaydedilir ama düzeye katılmaz (sim_level).
  3. Üretecin kendi etiketi — önbellekteki ham yanıttan (sınav isteğinde kod eskiden etiketi zorla yazıyordu).
Bunlara her soruda kodla (kota yok) açıklanabilir bir **tavan** uygulanır: ör. cevabı kaynak cümlede aynen yazılı ve
o cümleyi tekrar eden soru "kolay"dan zor olamaz; hatırlama düzeyindeki soru "zor" olamaz. Gerçek öğrenci verisi
tavanla kısılmaz (ölçümün kendisi).

Ölçümler data/review/difficulty.jsonl'de (soru kimliğine bağlı, yalnızca eklenir); soru dosyalarına yazılmaz —
yüklenirken bindirilir (apply). Alan tek tip (her PDF): özellikler dil ve konudan bağımsız (örtüşme, Bloom,
işlem sayısı, çeldirici yakınlığı), ölçüm de öğrenci benzetimi.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from rapidfuzz import fuzz

from src import config
from src.textnorm import normalize_for_match as norm

LOG = config.DATA_DIR / "review" / "difficulty.jsonl"
ATTEMPTS = config.DATA_DIR / "review" / "attempts.jsonl"
LEVELS = ("easy", "medium", "hard")
RANK = {lvl: i for i, lvl in enumerate(LEVELS)}
MIN_REAL = 5            # gerçek öğrenci etiketi için en az ilk-deneme sayısı
# Doğru oranı eşikleri: gerçek öğrencide p ≥ 0,75 kolay, < 0,40 zor; benzetimde p < 0,40 zor (sim_level).
P_EASY, P_HARD = 0.75, 0.40

_STOP = set("ve veya ile bir bu şu da de mi mu mü için gibi göre olan olarak ise ki en daha çok ne nedir hangi hangisi "
            "hangisidir kaç kaçtir aşağıdakilerden the a an of to in is are and or for which what how".split())
_NEG = re.compile(r"değildir|yanlıştır|olmayan|olamaz|hariç|\bnot\b|\bexcept\b", re.I)
_OPS = re.compile(r"\*\*|binomial|factorial|sqrt|log|sin|cos|tan|Abs|[+\-*/]")
_LITERAL = re.compile(r"\s*(?:Integer|Rational|Float)?\(?\s*-?[\d.\s/,]+\)?\s*")


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"\w+", norm(str(s or ""))) if len(w) >= 3 and w not in _STOP}


def answer_text(q: dict) -> str:
    """Doğru cevabın metni (çoktan seçmelide doğru şık; kısa cevapta cevap; D/Y'de boş — ifade sorunun kendisi)."""
    if q.get("type") == "multiple_choice" and q.get("options") and q.get("answer_index") is not None:
        return str(q["options"][q["answer_index"]])
    return str(q.get("answer", "")) if q.get("type") == "short_answer" else ""


def features(q: dict, check: dict | None = None) -> dict:
    """Kodla ölçülen yapısal zorluk özellikleri (kota yok; dil ve konudan bağımsız). check: kod kontrolünün sonucu —
    'facts' = notta bulunan ayrı kanıt alıntısı sayısı (sorunun birleştirdiği bilgi/kural sayısı; eski sorularda 1)."""
    src = str(q.get("evidence_quote") or "")
    tq = _tokens(q.get("question", ""))
    na, ns = norm(answer_text(q)), norm(src)
    compute = str(q.get("compute") or "")
    facts = (check or {}).get("facts")
    f = {"facts": facts if facts is not None else (1 if src else 0),
         "overlap": round(len(tq & _tokens(src)) / max(1, len(tq)), 2),  # sorunun kaynak cümleden gelen payı
         "answer_in_source": bool(len(na) >= 3 and ns and fuzz.partial_ratio(na, ns) >= 90),
         "bloom": q.get("bloom_level") or "remember",
         "steps": len(q.get("solution") or []),
         "ops": len(_OPS.findall(compute)) if compute and not _LITERAL.fullmatch(compute) else None,
         "negation": bool(_NEG.search(str(q.get("question", "")))),
         "compute": bool(compute)}
    if q.get("type") == "multiple_choice" and q.get("options") and q.get("answer_index") is not None:
        key = norm(q["options"][q["answer_index"]])
        others = [norm(o) for i, o in enumerate(q["options"]) if i != q["answer_index"]]
        f["distractor_sim"] = round(max(fuzz.token_set_ratio(key, o) for o in others) / 100, 2)  # en yakın çeldirici
    return f


def cap(q: dict, f: dict | None = None) -> tuple[str, str]:
    """Yapının izin verdiği en yüksek düzey ve nedeni (kural tabanlı, açıklanabilir). "Zor"un yapısal koşulu
    (otomatik madde üretimindeki zorluğu değiştiren değişken, LITERATURE §8): en az iki ayrı bilgi/kural ya da çok
    adımlı hesap."""
    f = f or features(q)
    if not f["compute"] and q.get("type") != "true_false" and f["answer_in_source"] and f["overlap"] >= 0.5:
        return "easy", "cevap kaynak cümlede aynen yazılı ve soru o cümleyi büyük ölçüde tekrar ediyor"
    if q.get("type") == "true_false" and f["overlap"] >= 0.75:
        return "easy", "ifade kaynak cümlenin neredeyse aynısı"
    if f["compute"] and f["ops"] is not None and f["ops"] <= 1:
        return "easy", "tek formül / tek işlem"
    multi_step = f["compute"] and f["steps"] >= 3 and (f["ops"] or 0) >= 3
    if f["facts"] <= 1 and not multi_step:
        return "medium", "tek bilgi ya da kurala dayanıyor: zor için en az iki ayrı bilgi ya da çok adımlı hesap gerekir"
    if f["bloom"] == "remember" and not f["compute"]:
        return "medium", "hatırlama düzeyi: bilgiyi birleştirme ya da uygulama yok"
    return "hard", ""


def measurable(q: dict) -> bool:
    """Benzetilmiş öğrenci bu soruda ölçüm verebilir mi? Yalnızca sözel ve nesnel puanlanan sorular (çoktan seçmeli,
    doğru/yanlış). Hesap sorusu: Gemma 4 lise matematiğinde doyuyor. Sözel kısa cevap: puanlama metin eşleşmesi,
    anlamı yakalamıyor (pilotta doğru cevap "verimlerinin önemli bir kısmını kaybetme" yanlış sayıldı → sahte p=0)."""
    return not q.get("compute") and q.get("type") in ("multiple_choice", "true_false")


def sim_level(p: float, think: float | None = None) -> str | None:
    """Benzetim → düzeyin alt sınırı. Sınıfın hepsi doğruysa (tavan) None: ölçüm bilgi vermez, iddia + yapı tavanı
    geçerli. 2026-10-06 pilotu: ölçülebilir 14 sözel sorunun 14'ünde p = 1 (Gemma 4 açık kitapta öğrenciden çok
    güçlü). Çaba (think) düzeye katılmaz: aynı pilotta soru tipini ölçtü (D/Y 221-269, ÇS 365-545 token; ÇS içinde
    üretecin iddiasıyla ilişkisiz) → gerçek öğrenci verisiyle ayarlanana kadar yalnızca kaydedilir."""
    if p >= 1.0:
        return None
    return "hard" if p < P_HARD else "medium"


# ---------------------------------------------------------------- kayıtlar

def record(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**entry, "t": time.time()}, ensure_ascii=False) + "\n")


def measurements(path: Path | None = None) -> dict[str, dict]:
    """Soru kimliği → son benzetim ölçümü {p, think, k, level}."""
    path = path or LOG
    out: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                if e.get("kind") == "sim":
                    out[e["id"]] = {**e, "level": sim_level(e["p"], e.get("think"))}
    return out


_claims_memo: dict = {"key": None, "map": {}}


def claims_from_cache(db: Path | None = None) -> dict[str, str]:
    """Üretecin ham yanıtlarındaki kendi zorluk etiketi: normalize soru metni → etiket. Sınav isteğinde kod etiketi
    eskiden zorla yazıyordu (TYT 'zor' isteği: Gemini 17 sorudan 14'üne 'orta' demişti); gerçek iddia önbellekte."""
    db = db or config.DATA_DIR / "llm.sqlite"
    if not db.exists():
        return {}
    key = (str(db), db.stat().st_mtime)
    if _claims_memo["key"] == key:
        return _claims_memo["map"]
    out: dict[str, str] = {}
    with closing(sqlite3.connect(db)) as c:  # 'with connect()' bağlantıyı kapatmaz (Windows'ta dosya kilitli kalır)
        rows = c.execute("SELECT response FROM cache WHERE response LIKE '%\"difficulty\"%'").fetchall()
    for (resp,) in rows:
        try:
            d = json.loads(resp)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        for g in [d] if "questions" in d else d.get("units", []):
            for q in g.get("questions", []) if isinstance(g, dict) else []:
                if isinstance(q, dict) and q.get("question") and q.get("difficulty") in RANK:
                    out[norm(q["question"])] = q["difficulty"]
    _claims_memo.update(key=key, map=out)
    return out


def elo(attempts: list[dict], prior: dict[str, float] | None = None) -> dict[str, dict]:
    """Gerçek öğrenci ilk denemelerinden Elo (Pelánek 2016): madde zorluğu d ve öğrenci yeteneği θ birlikte güncellenir;
    adım küçülür (K = 1 / (1 + 0.05·n)). prior: benzetimden başlangıç zorluğu (logit). Kayıtlarda öğrenci kimliği
    yok → tek öğrenci varsayılır (çok kullanıcılı kurulumda öğrenci başına θ)."""
    prior = prior or {}
    d: dict[str, float] = {}
    n: dict[str, int] = {}
    theta, n_student = 0.0, 0
    for a in attempts:
        if a.get("retry"):
            continue
        qid = a["id"]
        d.setdefault(qid, prior.get(qid, 0.0))
        p = 1 / (1 + math.exp(-(theta - d[qid])))
        y = 1.0 if a.get("correct") else 0.0
        d[qid] -= (y - p) / (1 + 0.05 * n.get(qid, 0))
        theta += (y - p) / (1 + 0.05 * n_student)
        n[qid] = n.get(qid, 0) + 1
        n_student += 1
    return {q: {"d": round(d[q], 3), "n": n[q], "p": round(1 / (1 + math.exp(d[q])), 2)} for q in d}


def _real() -> dict[str, dict]:
    if not ATTEMPTS.exists():
        return {}
    rows = [json.loads(x) for x in ATTEMPTS.read_text(encoding="utf-8").splitlines() if x.strip()]
    out = elo(rows)
    for r in out.values():
        r["level"] = "easy" if r["p"] >= P_EASY else ("medium" if r["p"] >= P_HARD else "hard")
    return out


# ---------------------------------------------------------------- bindirme

def effective(it: dict, sim: dict | None = None, real: dict | None = None, claims: dict | None = None) -> dict:
    q = it["q"]
    claim = (claims or {}).get(norm(q.get("question", ""))) or q.get("difficulty_claim") or q.get("difficulty") or "medium"
    f = features(q, it.get("check"))
    top, why = cap(q, f)
    if real and real["n"] >= MIN_REAL:
        return {"level": real["level"], "source": "öğrenci", "claim": claim, "n": real["n"], "p": real["p"]}
    if not measurable(q):
        sim = None  # hesap ve sözel kısa cevap benzetilmez (measurable): yapı + iddia
    level, source = claim, "üretici"
    if sim and sim.get("level"):  # sınıf yanıldı: düzey en az ölçülen kadar (alt sınır)
        level, source = max(claim, sim["level"], key=RANK.get), "benzetim"
    out = {"level": level, "source": source, "claim": claim}
    if sim:
        out.update(p=sim["p"], think=sim.get("think"), sim_ceiling=not sim.get("level"))
    if RANK[level] > RANK[top]:
        out.update(level=top, capped_from=level, cap_why=why)
    return out


def apply(items: list[dict]) -> list[dict]:
    """Yüklenen sorulara etkin zorluğu bindir: q["difficulty"] = etkin düzey, q["difficulty_claim"] = üretecin
    etiketi, it["difficulty"] = {level, source, ...}. Bütün arayüz ve sınav kodu q["difficulty"]'yi okur."""
    sims, real, claims = measurements(), _real(), claims_from_cache()
    for it in items:
        qid = it.get("id")
        d = effective(it, sims.get(qid), real.get(qid), claims)
        it["difficulty"] = d
        it["q"]["difficulty_claim"] = d["claim"]
        it["q"]["difficulty"] = d["level"]
    return items

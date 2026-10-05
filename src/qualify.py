"""Model yeterlilik testi (kalite kapısı): aday bir modeli doğrulayıcı olarak onaylamadan önce tek komutla sınar.

  1. Metin doğrulama (verify): kasıtlı bozulmuş sorular (yanlış anahtar, iki doğru şık, D/Y ters, kısa cevap yanlış,
     metinde olmayan ama gerçekte doğru ifade) yakalanıyor mu? Sağlam sorular doğrulanıyor mu (yanlış alarm)?
  2. Hesap (verify_math): SymPy'nin doğruladığı TYT hesap sorularını körlemesine aynı sonuçla çözüyor mu? Anahtarı
     kaydırılmış soruyu fark ediyor mu? qwen'in yanıldığı iki zor problemi (yuvarlak masa, ANANAS) çözüyor mu?
  Sonuç: eval/yeterlilik/<model>.json + .md ve onay önerisi (models.py APPROVED'a eklenecek satır). Onayı insan verir.

Kullanım: python -m src.qualify <model> [--kisa]
  --kisa: günlük istek sınırı düşük sağlayıcılar için (~30 çağrı; OpenRouter ücretsiz: günde 50). Sınırı 50 olan
          modellerde kendiliğinden açılır. Her yanıt önbellekte: yarıda kalan test yeniden çalıştırılınca kaldığı yerden sürer.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from src import config
from src import review_store as rs
from src.llm.models import MODELS, ROLES
from src.verification.sensitivity import NOT_IN_CONTEXT, corruptions
from src.verification.verify import family, verify_item

OUT = config.ROOT / "eval" / "yeterlilik"
TEXT_SETS = ["toplu_gemini-3.8-flash_english_tr_dogrulama.jsonl", "qwen_qwen3.8-27b_english_tr_dogrulama.jsonl"]
PASS = {"text_catch": 0.95, "text_clean": 0.80, "math_clean": 0.90, "math_catch": 0.95}


def _load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _text_items(model: str) -> list[dict]:
    """Doğrulanmış GA soruları; üreticisi adayla aynı aileden olmayan set seçilir (aile kuralı)."""
    for name in TEXT_SETS:
        items = [i for i in _load(config.DATA_DIR / "pilot" / name) if i["verification"]["label"] == "verified"]
        if items and family(items[0]["model"]) != family(model):
            return items
    return []


def _math_items(model: str) -> tuple[list[dict], list[dict]]:
    """(SymPy'den geçmiş TYT hesap soruları, zor problemler). Üreticisi Gemini; aday Gemini ise boş."""
    tyt = [i for i in _load(config.DATA_DIR / "questions" / "tyt-matematik_tr.jsonl")
           if i["q"].get("compute") and i["check"].get("computed", {}).get("key_ok")
           and i["verification"]["label"] == "verified"]
    req = config.DATA_DIR / "questions" / "istek_tr.jsonl"
    hard = [i for i in (_load(req) if req.exists() else []) if i["q"].get("compute")
            and i["check"].get("computed", {}).get("key_ok") and i["q"].get("difficulty") == "hard"]
    if tyt and family(tyt[0]["model"]) == family(model):
        return [], []
    return tyt, hard


def run(model: str, short: bool) -> dict:
    if model not in MODELS:
        raise SystemExit(f"Bilinmeyen model: {model} (src/llm/models.py MODELS'e ekleyin)")
    ROLES["verify"] = [model]          # yalnızca aday sınanır; onaylılar devreye girmez
    ROLES["verify_math"] = [model]
    chunks = rs.load_chunks()
    res: dict = {"model": model, "short": short, "text": {}, "math": {}, "misses": []}

    # 1. Metin doğrulama
    items = _text_items(model)
    if short:
        items = items[:6]
    caught = total = clean_ok = 0
    for it in items:
        v = verify_item(it, chunks, light=True)
        clean_ok += v["label"] == "verified"
        if v["label"] != "verified":
            res["misses"].append(("sağlam soru reddedildi", it["q"]["question"][:90], v["why"]))
        for kind, bad, expect in corruptions(it):
            v = verify_item(bad, chunks, light=True)
            ok = v["label"] != "verified" if expect == "not_verified" else v["label"] == "rejected"
            caught, total = caught + ok, total + 1
            if not ok:
                res["misses"].append((kind, it["q"]["question"][:90], v["why"]))
    if items:
        base = next(i for i in items if i["q"]["type"] != "true_false")
        for s in NOT_IN_CONTEXT[: 2 if short else 3]:
            it = copy.deepcopy(base)
            it["q"] = {"question": s, "type": "true_false", "answer": "true", "evidence_quote": "-"}
            ok = verify_item(it, chunks, light=True)["label"] == "rejected"
            caught, total = caught + ok, total + 1
            if not ok:
                res["misses"].append(("not_in_context", s[:90], "metinde olmayan ifade kabul edildi"))
        res["text"] = {"catch": [caught, total], "clean": [clean_ok, len(items)]}

    # 2. Hesap
    tyt, hard = _math_items(model)
    if tyt:
        tyt = tyt[:10] if short else tyt[:20]
        agree = 0
        for it in tyt + hard:
            v = verify_item(it, chunks, light=True)
            agree += v["label"] == "verified"
            if v["label"] != "verified":
                res["misses"].append(("hesap: kod ile uyuşmadı", it["q"]["question"][:90],
                                      f"kör: {v.get('blind_answer')} · kod: {it['check']['computed'].get('value')}"))
        mcq = [i for i in tyt if i["q"]["type"] == "multiple_choice"][: 5 if short else 10]
        mcaught = 0
        for it in mcq:
            bad = copy.deepcopy(it)
            bad["q"]["answer_index"] = (it["q"]["answer_index"] + 1) % 4
            v = verify_item(bad, chunks, light=True)
            mcaught += v["label"] != "verified"
            if v["label"] == "verified":
                res["misses"].append(("hesap: kaydırılmış anahtar kabul edildi", it["q"]["question"][:90], v["why"]))
        res["math"] = {"clean": [agree, len(tyt) + len(hard)], "hard": [sum(1 for _ in hard), len(hard)],
                       "catch": [mcaught, len(mcq)]}

    # Öneri
    t, m = res["text"], res["math"]
    rate = lambda pair: pair[0] / pair[1] if pair and pair[1] else 0.0
    res["recommend"] = {
        "verify": bool(t) and rate(t["catch"]) >= PASS["text_catch"] and rate(t["clean"]) >= PASS["text_clean"],
        "verify_math": bool(m) and rate(m["clean"]) >= PASS["math_clean"] and rate(m["catch"]) >= PASS["math_catch"],
    }
    return res


def report(res: dict) -> str:
    t, m = res["text"], res["math"]
    lines = [f"# Yeterlilik testi: `{res['model']}`" + (" (kısa)" if res["short"] else ""), "",
             "| Sınav | Sonuç | Eşik |", "|---|---|---|"]
    if t:
        lines += [f"| Kasıtlı hataları yakalama | {t['catch'][0]}/{t['catch'][1]} | ≥ %{int(PASS['text_catch'] * 100)} |",
                  f"| Sağlam soruyu doğrulama | {t['clean'][0]}/{t['clean'][1]} | ≥ %{int(PASS['text_clean'] * 100)} |"]
    if m:
        lines += [f"| Hesap: kod ile aynı sonuç | {m['clean'][0]}/{m['clean'][1]} | ≥ %{int(PASS['math_clean'] * 100)} |",
                  f"| Hesap: kaydırılmış anahtarı yakalama | {m['catch'][0]}/{m['catch'][1]} | ≥ %{int(PASS['math_catch'] * 100)} |"]
    rec = res["recommend"]
    lines += ["", "**Öneri:** " + (", ".join(k for k, v in rec.items() if v) + " rolü için onaylanabilir"
                                   if any(rec.values()) else "onaylanmamalı")]
    if res["misses"]:
        lines += ["", "**Kaçırılanlar / uyuşmazlıklar:**"] + [f"- [{k}] {q} → {w}" for k, q, w in res["misses"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    model = sys.argv[1]
    from src.llm.router import has_key
    if model in MODELS and not has_key(model):
        env = {"openrouter": "OPENROUTER_API_KEY", "cerebras": "CEREBRAS_API_KEY",
               "mistral": "MISTRAL_API_KEY"}.get(MODELS[model].provider, "?")
        raise SystemExit(f"{model} için API anahtarı yok: .env dosyasına {env}=... satırını ekleyip yeniden çalıştırın.")
    short = "--kisa" in sys.argv or (MODELS.get(model) and (MODELS[model].rpd or 10 ** 6) <= 50)
    res = run(model, bool(short))
    OUT.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", model)
    (OUT / f"{safe}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = report(res)
    (OUT / f"{safe}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

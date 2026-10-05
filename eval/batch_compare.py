"""Toplu üretim (§2b, tek istek) kalite karşılaştırması — kalite kapısı testi.

Aynı birimler (EN slaytın ilk 12 birimi, Türkçe soru):
  taban : qwen3.8-27b, birim başına bir istek (data/pilot/qwen_qwen3.8-27b_english_tr.jsonl, mevcut)
  aday  : Gemini modelleri, TÜM birimler tek istekte
Hepsi aynı kod kontrolleri + aynı kör doğrulayıcı (gpt-oss-120b, hafif mod).
Kabul ölçütü: aday, tabana göre doğrulanma oranında ve 'dayanaksız' oranında daha kötü olmamalı.

Çalıştırma: python -m eval.batch_compare [model ...]  → eval/sonuclar_toplu_uretim.md
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from src import config
from src.generation.generate import build_units, generate_batched
from src.llm import ledger
from src.llm.models import ROLES
from src.verification.verify import verify_item

DOC, LIMIT, LANG = "english", 12, "tr"
OUT = config.DATA_DIR / "pilot"


def chunks() -> dict:
    return {json.loads(x)["id"]: json.loads(x)
            for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}


def stats(name: str, items: list[dict], requests: int, tokens: int, secs: float) -> dict:
    n = len(items)
    lab = Counter(i["verification"]["label"] for i in items)
    flags = Counter(f for i in items if i["check"]["status"] != "rejected" for f in i["check"]["flags"])
    unsupported = sum("evidence_not_found" in i["check"]["rejected"]
                      or (i["check"]["status"] != "rejected" and i["verification"]["label"] != "verified") for i in items)
    return {"yöntem": name, "soru": n, "kod red": dict(Counter(r for i in items for r in i["check"]["rejected"])),
            "verified": lab["verified"], "needs_review": lab["needs_review"],
            "verified oranı": lab["verified"] / n if n else 0, "dayanaksız": unsupported,
            "uyarılar": dict(flags), "tipler": dict(Counter(i["q"].get("type", "?") for i in items)),
            "bloom": dict(Counter(i["q"].get("bloom_level", "?") for i in items if i["verification"]["label"] == "verified")),
            "istek": requests, "token": tokens, "süre_sn": round(secs)}


def main() -> None:
    ch = chunks()
    rows = []
    base = [json.loads(x) for x in (OUT / "qwen_qwen3.8-27b_english_tr.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for it in base:
        it["verification"] = verify_item(it, ch, light=True)
    rows.append(stats("qwen, birim başına istek (taban)", base, requests=12, tokens=12 * 2700, secs=0))

    units = build_units(DOC)[:LIMIT]
    for model in sys.argv[1:] or ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.8-flash"]:
        ROLES["_batch"] = [model]
        before = ledger.usage(model)
        t = time.time()
        for attempt in range(4):  # 503 "yoğun" geçicidir
            try:
                items = generate_batched(units, LANG, "_batch")
                break
            except Exception as e:
                print(f"   {model}: {str(e)[:80]} → 45 sn sonra tekrar", flush=True)
                time.sleep(45)
        else:
            print(f"   {model}: atlandı", flush=True)
            continue
        secs = time.time() - t
        after = ledger.usage(model)
        for it in items:
            it["verification"] = verify_item(it, ch, light=True)
        (OUT / f"toplu_{model}_{DOC}_{LANG}_dogrulama.jsonl").write_text(
            "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        rows.append(stats(f"{model}, TEK istek", items, after[0] - before[0], after[1] - before[1], secs))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    md = ["# Toplu Üretim Kalite Karşılaştırması\n",
          f"Aynı {LIMIT} birim (EN slayt → Türkçe soru), aynı kontroller, aynı doğrulayıcı (gpt-oss-120b).\n",
          "| Yöntem | İstek | Token | Soru | Verified | Verified oranı | Dayanaksız | Kod red | Uyarılar |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['yöntem']} | {r['istek']} | {r['token']:,} | {r['soru']} | {r['verified']} | {r['verified oranı']:.0%} | "
                  f"{r['dayanaksız']} | {r['kod red'] or '-'} | {r['uyarılar'] or '-'} |")
    md.append("\nTipler / bloom (doğrulananlar): " + "; ".join(f"{r['yöntem']}: {r['tipler']} / {r['bloom']}" for r in rows))
    (Path(__file__).parent / "sonuclar_toplu_uretim.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (Path(__file__).parent / "sonuclar_toplu_uretim.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                                                     encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

"""Sadakat ↔ bilişsel düzey deneyi (README §7.4).

Hipotez: dokümana sadakat zorlandığında üretici "hatırlama" düzeyine kayar; "uygulama" düzeyi istendiğinde
dokümanda dayanağı olmayan (halüsinasyonlu) soru oranı artar.
Tasarım: aynı üretim birimleri, iki koşul — A: yalnızca 'remember', B: yalnızca 'apply'. Üretici YALNIZCA
gemini-2.5-flash, toplu üretim (yedeğe geçmez; ilk sürüm qwen ile Groq token kotasına takılıp saatlerce bekledi), aynı kod kontrolleri, aynı kör doğrulayıcı (gpt-oss, hafif mod).
Groq'un token/gün sınırına (kayan 24 saat, model başına 200k) takılınca bekleyip kaldığı yerden devam eder;
önceden alınmış yanıtlar önbellekten gelir.

Çalıştırma: python -m eval.bloom_experiment  → data/pilot/bloom_<koşul>_dogrulama.jsonl, eval/sonuclar_bloom.md
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from src import config
from src.generation.generate import build_units, generate_batched
from src.llm import ledger
from src.llm.models import ROLES
from src.llm.router import AllModelsExhausted
from src.verification.checks import mark_duplicates
from src.verification.verify import verify_item

DOCS = [("7.Hafta Sunu Dosyası", None), ("4_ENERJİ, TARIM, BESLENME", None), ("english", 6)]
CONDITIONS = ["remember", "apply"]
GENERATOR = "gemini-2.5-flash"  # toplu üretim (§2b): belge başına 1 istek
OUT = config.DATA_DIR / "pilot"


def patient(fn, *args, **kwargs):
    """Kota/bekleme yüzünden tüm modeller kapalıysa en kısa bekleme kadar uyu ve tekrar dene."""
    for _ in range(40):
        try:
            return fn(*args, **kwargs)
        except AllModelsExhausted as e:
            waits = [ledger.cooldown_left(m) for m in list(ledger.MODELS)]
            wait = min([w for w in waits if w > 0] or [600])
            print(f"   ⏳ kota bekleniyor ({e}); {wait / 60:.1f} dk", flush=True)
            time.sleep(wait + 5)
    raise RuntimeError("çok uzun süre kota beklendi")


def run(cond: str, chunks: dict) -> list[dict]:
    ROLES["_bloom_gen"] = [GENERATOR]
    items = []
    for doc, limit in DOCS:
        units = build_units(doc)[:limit]
        got = patient(generate_batched, units, "tr", "_bloom_gen", bloom_target=cond)
        items += got
        print(f"   {cond} | {doc[:10]}: {len(units)} birim → {len(got)} soru", flush=True)
    mark_duplicates(items)
    for n, it in enumerate(items, 1):
        it["verification"] = patient(verify_item, it, chunks, light=True)
    (OUT / f"bloom_{cond}_dogrulama.jsonl").write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    return items


def summarize(cond: str, items: list[dict], n_units: int) -> dict:
    n = len(items)
    lab = Counter(i["verification"]["label"] for i in items)
    unsupported = sum("evidence_not_found" in i["check"]["rejected"]
                      or (i["check"]["status"] != "rejected" and i["verification"]["label"] != "verified")
                      for i in items)
    return {"koşul": cond, "birim": n_units, "soru": n,
            "soru üretmeyen birim": n_units - len({i["unit"] + str(i["pages"]) for i in items}),
            "verified": lab["verified"], "needs_review": lab["needs_review"], "rejected": lab["rejected"],
            "kod red nedenleri": dict(Counter(r for i in items for r in i["check"]["rejected"])),
            "dayanaksız": unsupported, "dayanaksız oranı": unsupported / n if n else 0,
            "modelin kendi bloom etiketi": dict(Counter(i["q"].get("bloom_level", "?") for i in items))}


def main() -> None:
    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    n_units = sum(len(build_units(d)[:l]) for d, l in DOCS)
    rows = []
    for cond in CONDITIONS:
        print(f"→ koşul: {cond} ({n_units} birim)", flush=True)
        rows.append(summarize(cond, run(cond, chunks), n_units))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    md = ["# Sadakat ↔ Bilişsel Düzey Deneyi\n",
          f"Aynı {n_units} üretim birimi; üretici {GENERATOR} (toplu, yedeksiz), doğrulayıcı gpt-oss-120b (hafif mod).\n",
          "**Dayanaksız** = kanıtı metinde bulunamayan + kod kontrolünü geçip doğrulayıcının onaylamadığı sorular.\n",
          "| Koşul | Soru | Soru üretmeyen birim | Verified | Needs review | Rejected | Dayanaksız oranı |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['koşul']} | {r['soru']} | {r['soru üretmeyen birim']} | {r['verified']} | {r['needs_review']} | "
                  f"{r['rejected']} | {r['dayanaksız oranı']:.0%} |")
    md.append("\nKod red nedenleri: " + "; ".join(f"{r['koşul']}: {r['kod red nedenleri']}" for r in rows))
    md.append("\nModelin kendi bloom etiketi: " + "; ".join(f"{r['koşul']}: {r['modelin kendi bloom etiketi']}" for r in rows))
    (Path(__file__).parent / "sonuclar_bloom.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (Path(__file__).parent / "sonuclar_bloom.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
    print("\n".join(md), flush=True)
    print("DENEY BİTTİ", flush=True)


if __name__ == "__main__":
    main()

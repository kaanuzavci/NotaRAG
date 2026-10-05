"""Kullanım: python -m src.verification data/pilot/<model>.jsonl [...]

Her dosyadaki soruları kör doğrulamadan geçirir → <dosya>_dogrulama.jsonl ve data/pilot/dogrulama.md
"""

import json
import sys
from collections import Counter
from pathlib import Path

from src import config
from src.verification.verify import verify_item

LETTERS = "ABCD"
ICON = {"verified": "✅", "needs_review": "🟡", "rejected": "❌"}


def main() -> None:
    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    md = ["# Doğrulama Sonuçları\n"]
    for path in map(Path, sys.argv[1:]):
        items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        print(f"→ {path.name}: {len(items)} soru", flush=True)
        for it in items:
            it["verification"] = verify_item(it, chunks, allow_candidates=True)  # pilot: model karşılaştırma
        out = path.with_name(path.stem + "_dogrulama.jsonl")
        out.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        labels = Counter(i["verification"]["label"] for i in items)
        mcq = [i for i in items if "closed_book_correct" in i["verification"]]
        cb = sum(i["verification"]["closed_book_correct"] for i in mcq)
        print(f"   {dict(labels)} | bağlamsız da doğru bilinen ÇS: {cb}/{len(mcq)}")
        md.append(f"\n## {items[0]['model'] if items else path.stem}\n")
        md.append(f"- **Sonuç:** {dict(labels)}")
        md.append(f"- **Dokümansız da doğru cevaplanan çoktan seçmeli:** {cb}/{len(mcq)}\n")
        for n, it in enumerate(items, 1):
            v, q = it["verification"], it["q"]
            cbt = " · 📖✗ dokümansız da bilindi" if v.get("closed_book_correct") else ""
            md.append(f"{n}. {ICON[v['label']]} **{q.get('question', '?')}**  ")
            ans = (f"{LETTERS[q['answer_index']]}) {q['options'][q['answer_index']]}" if q.get("type") == "multiple_choice"
                   else q.get("answer"))
            md.append(f"   <sub>Anahtar: {ans} · {v['why']}{cbt}"
                      f"{' · doğrulayıcı: ' + v['verifier'] if v.get('verifier') else ''}</sub>")
            if v.get("verifier_reason"):
                md.append(f"   <sub>Gerekçe: {v['verifier_reason']}</sub>")
            if v.get("blind_answer"):
                md.append(f"   <sub>Kör cevap: {v['blind_answer'][:150]}</sub>")
            md.append("")
    (config.DATA_DIR / "pilot" / "dogrulama.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Rapor: {config.DATA_DIR / 'pilot' / 'dogrulama.md'}")


if __name__ == "__main__":
    main()

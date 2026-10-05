"""Kullanım: python -m src.chunking   (internet kullanmaz)

data/parsed/*.json → data/chunks/chunks.jsonl, sections.jsonl, skipped.jsonl
"""

import json
from collections import Counter

from src import config
from src.chunking.chunker import chunk_document


def _write_jsonl(path, rows) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> None:
    out = config.DATA_DIR / "chunks"
    out.mkdir(parents=True, exist_ok=True)
    all_c, all_s, all_k = [], [], []
    for jp in sorted(config.PARSED_DIR.glob("*.json")):
        c, s, k = chunk_document(json.loads(jp.read_text(encoding="utf-8")))
        all_c += c; all_s += s; all_k += k
        lens = sorted(len(x["text"]) for x in c)
        print(f"■ {jp.stem}: {len(c)} parça, {len(s)} bölüm, {len(k)} sayfa dışarıda "
              f"{dict(Counter(x['reason'] for x in k))} | parça uzunluğu medyan {lens[len(lens)//2]}, max {lens[-1]}"
              f" | görselden gelen parça: {sum(x['source'] == 'vision' for x in c)}")
    _write_jsonl(out / "chunks.jsonl", all_c)
    _write_jsonl(out / "sections.jsonl", all_s)
    _write_jsonl(out / "skipped.jsonl", all_k)
    print(f"\nToplam: {len(all_c)} parça, {len(all_s)} bölüm → {out}")
    print(f"Embedding'e gidecek metin: {sum(len(x['embed_text'].encode('utf-8')) for x in all_c) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()

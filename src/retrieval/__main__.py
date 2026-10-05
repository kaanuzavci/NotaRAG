"""Kullanım:
    python -m src.retrieval build                    # eksik embedding'leri al (İNTERNET, yalnızca yeni/değişen parçalar) + dizini kur
    python -m src.retrieval search "sorgu" [mod]     # mod: dense (varsayılan) | hybrid | bm25 | bm25_plain
"""

import sys

from src.retrieval.index import Index


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    idx = Index()
    if cmd == "build":
        texts = [c["embed_text"] for c in idx.chunks]
        todo = idx.embedder.missing(texts)
        print(f"{len(idx.chunks)} parça; embedding'i eksik: {len(todo)} "
              f"(~{sum(len(t.encode('utf-8')) for t in todo) / 1e3:.0f} KB gönderim, ~{len(todo) * 10.6 / 1e3:.1f} MB indirme)")
        print(idx.build())
    elif cmd == "search":
        query, mode = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "dense")
        for i, c in enumerate(idx.search(query, k=5, mode=mode), 1):
            print(f"{i}. [{c['doc'][:12]} s.{c['page']}] {c['heading']!s:.40} | {c['text'][:90]!r}")


if __name__ == "__main__":
    main()

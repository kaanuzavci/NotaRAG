"""Arama değerlendirmesi (ROADMAP Adım 9, README §7.1).

İki sorgu kümesi:
  elle   : eval/retrieval_queries.json — 35 konu sorgusu, doğru sayfalar elle etiketli
  üretim : doğrulanmış üretilmiş sorular (data/pilot/*_dogrulama.jsonl); doğru sayfa = kanıtın sayfası
Yöntemler: dense | bm25_plain | bm25 (F5) | hybrid | hybrid_nolang (dil kuralı kapalı)
Ölçüler: isabet@1/3/5 (ilk k sonuçta doğru sayfa var mı), MRR@10. Tüm belgeler üzerinde arama yapılır.

Çalıştırma: python -m eval.evaluate_retrieval  → eval/sonuclar_retrieval.md
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from src import config
from src.retrieval.index import Index

ROOT = Path(__file__).resolve().parent
MODES = {"dense": dict(mode="dense"), "bm25_plain": dict(mode="bm25_plain"), "bm25": dict(mode="bm25"),
         "hybrid": dict(mode="hybrid"), "hybrid_nolang": dict(mode="hybrid", lang_rule=False)}
MODE_TR = {"dense": "Yalnızca vektör (dense)", "bm25_plain": "BM25, köklemesiz", "bm25": "BM25, ilk 5 harf (F5)",
           "hybrid": "Hibrit (RRF + dil kuralı)", "hybrid_nolang": "Hibrit, dil kuralı kapalı"}


def hand_queries() -> list[dict]:
    spec = json.loads((ROOT / "retrieval_queries.json").read_text(encoding="utf-8"))
    out = []
    for q in spec["queries"]:
        rel = {(spec["docs"][d], p) for d, pages in q["rel"].items() for p in pages}
        out.append({"q": q["q"], "kind": "elle: " + q["kind"], "rel": rel})
    return out


def generated_queries() -> list[dict]:
    out, seen = [], set()
    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    for path in sorted((config.DATA_DIR / "pilot").glob("*_dogrulama.jsonl")):
        if path.name.startswith("v1_"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            it = json.loads(line)
            page = it.get("check", {}).get("evidence_page")
            if it.get("verification", {}).get("label") != "verified" or not page or it["q"]["question"] in seen:
                continue
            seen.add(it["q"]["question"])
            doc = chunks[it["chunk_ids"][0]]["doc"]
            cross = "_english_tr" in path.name
            out.append({"q": it["q"]["question"], "kind": "üretim: " + ("tr→en" if cross else "tr→tr"), "rel": {(doc, page)}})
    return out


def evaluate(idx: Index, queries: list[dict]) -> dict:
    res: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for q in queries:
        for name, kw in MODES.items():
            hits = idx.search(q["q"], k=10, **kw)
            rank = next((i + 1 for i, c in enumerate(hits) if (c["doc"], c["page"]) in q["rel"]), None)
            for group in ("TÜMÜ", q["kind"]):
                r = res[group][name]
                r["n"] += 1
                for k in (1, 3, 5):
                    r[f"@{k}"] += bool(rank and rank <= k)
                r["mrr"] += 1 / rank if rank else 0
    return res


def to_markdown(res: dict) -> str:
    lines = ["# Arama Değerlendirmesi\n",
             "İsabet@k: ilk k sonuçta doğru sayfa var mı. MRR@10: doğru sayfanın sırasının tersinin ortalaması.\n"]
    for group in sorted(res, key=lambda g: (g != "TÜMÜ", g)):
        n = int(next(iter(res[group].values()))["n"])
        lines += [f"\n## {group} (n={n})\n", "| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |", "|---|---|---|---|---|"]
        best = max(res[group].values(), key=lambda r: r["@5"])["@5"]
        for name, r in res[group].items():
            mark = " **★**" if r["@5"] == best else ""
            lines.append(f"| {MODE_TR[name]}{mark} | {r['@1'] / n:.0%} | {r['@3'] / n:.0%} | {r['@5'] / n:.0%} | "
                         f"{r['mrr'] / n:.2f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    idx = Index()
    queries = hand_queries() + generated_queries()
    print(f"{len(queries)} sorgu ({sum(q['kind'].startswith('elle') for q in queries)} elle)")
    res = evaluate(idx, queries)
    md = to_markdown(res)
    (ROOT / "sonuclar_retrieval.md").write_text(md, encoding="utf-8")
    import json as _json
    (ROOT / "sonuclar_retrieval.json").write_text(_json.dumps(
        {"modes": MODE_TR, "groups": {g: {m: dict(v) for m, v in r.items()} for g, r in res.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(md)
    print(f"Embedding gönderilen yeni sorgu: {idx.embedder.sent_texts}")


if __name__ == "__main__":
    main()

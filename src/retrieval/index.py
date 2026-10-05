"""Hibrit arama: ChromaDB (dense) + BM25 (F5 kökleme), Reciprocal Rank Fusion ile birleştirme.

Diller arası kural: sorgu dili belli ve bir parçanın dilinden farklıysa (Türkçe konu araması,
İngilizce slayt), BM25 o parça için anlamsızdır; füzyona yalnızca dense sırası girer.
"""

from __future__ import annotations

import json
from functools import cached_property

import chromadb
from rank_bm25 import BM25Okapi

from src import config
from src.retrieval.embedder import Embedder
from src.textnorm import detect_language, f5_tokens

COLLECTION = "chunks"
RRF_K = 60          # Cormack vd. (2009) önerisi
CANDIDATES = 20     # her yöntemden füzyona giren aday sayısı


def load_chunks() -> list[dict]:
    path = config.DATA_DIR / "chunks" / "chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Index:
    def __init__(self) -> None:
        self.chunks = load_chunks()
        self.by_id = {c["id"]: c for c in self.chunks}
        self.embedder = Embedder()
        self.client = chromadb.PersistentClient(
            path=str(config.DATA_DIR / "chroma"), settings=chromadb.Settings(anonymized_telemetry=False))

    # --- kurulum -------------------------------------------------------------
    def build(self) -> dict:
        """Eksik embedding'leri alır (internet) ve Chroma koleksiyonunu baştan yazar (yerel)."""
        texts = [c["embed_text"] for c in self.chunks]
        missing = len(self.embedder.missing(texts))
        vecs = self.embedder.embed(texts)
        try:
            self.client.delete_collection(COLLECTION)
        except Exception:
            pass
        col = self.client.create_collection(COLLECTION, embedding_function=None,
                                            metadata={"hnsw:space": "cosine"})
        col.add(ids=[c["id"] for c in self.chunks], embeddings=vecs.tolist(),
                documents=[c["text"] for c in self.chunks],
                metadatas=[{"doc": c["doc"], "page": c["page"], "section_id": c["section_id"],
                            "language": c["language"], "source": c["source"]} for c in self.chunks])
        return {"chunks": len(self.chunks), "embedded_now": missing, "sent_texts": self.embedder.sent_texts}

    @cached_property
    def _bm25_f5(self) -> BM25Okapi:
        return BM25Okapi([f5_tokens(c["embed_text"]) or ["_"] for c in self.chunks])

    @cached_property
    def _bm25_plain(self) -> BM25Okapi:  # ablasyon için: köklemesiz tam kelime
        return BM25Okapi([f5_tokens(c["embed_text"], prefix=100) or ["_"] for c in self.chunks])

    # --- arama ---------------------------------------------------------------
    def dense(self, query: str, n: int = CANDIDATES, where: dict | None = None) -> list[str]:
        col = self.client.get_collection(COLLECTION, embedding_function=None)
        r = col.query(query_embeddings=[self.embedder.embed_query(query).tolist()], n_results=n, where=where)
        return r["ids"][0]

    def bm25(self, query: str, n: int = CANDIDATES, f5: bool = True, docs: set[str] | None = None) -> list[str]:
        model = self._bm25_f5 if f5 else self._bm25_plain
        q = f5_tokens(query, prefix=5 if f5 else 100)
        if not q:
            return []
        scores = model.get_scores(q)
        order = sorted(range(len(self.chunks)), key=lambda i: -scores[i])
        out = [self.chunks[i]["id"] for i in order if scores[i] > 0
               and (docs is None or self.chunks[i]["doc"] in docs)]
        return out[:n]

    def search(self, query: str, k: int = 5, mode: str = "dense", doc: str | None = None,
               lang_rule: bool = True) -> list[dict]:
        """mode: dense (varsayılan) | hybrid | bm25 | bm25_plain. lang_rule=False: ablasyon.

        Varsayılan 'dense': eval/sonuclar_retrieval.md (68 sorgu, 2026-10-03) — dense isabet@5 %100, MRR 0.90;
        hibrit %85 / 0.70. TR sorgu → EN slaytta BM25, TR slayttaki benzer kelimeleri öne çıkarıp doğru sayfayı itiyor.
        """
        where = {"doc": doc} if doc else None
        docs = {doc} if doc else None
        if mode == "dense":
            ranked = self.dense(query, where=where)
        elif mode in ("bm25", "bm25_plain"):
            ranked = self.bm25(query, f5=(mode == "bm25"), docs=docs)
        else:
            q_lang = detect_language(query)
            dense = self.dense(query, where=where)
            sparse = [cid for cid in self.bm25(query, docs=docs)
                      if not lang_rule or q_lang == "unknown" or self.by_id[cid]["language"] == q_lang]
            score: dict[str, float] = {}
            for lst in (dense, sparse):
                for rank, cid in enumerate(lst):
                    score[cid] = score.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
            ranked = sorted(score, key=lambda c: -score[c])
        return [self.by_id[cid] for cid in ranked[:k]]

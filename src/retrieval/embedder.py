"""Gemini embedding + disk önbelleği (ROADMAP Adım 4).

Neden gemini-embedding-001 (README'deki 'Gemini Embedding 2' yerine):
  gemini-embedding-2 metin listesini tek girdi sayıp TEK vektör döndürüyor → her parça ayrı
  istek (ücretsiz kotada riskli). 001 tek istekte 100 metin alıyor, RETRIEVAL_DOCUMENT/QUERY
  ayrımını destekliyor ve TR↔EN testinde ayrıştırması en az onun kadar iyi.
Neden 768 boyut: 3072 boyutlu vektör JSON olarak ~35 KB iner; 768 ile ~10 KB (Matryoshka,
  kalite kaybı küçük). Mobil internet için 4 kat tasarruf.
Önbellek: vektörler metnin sha1 özetiyle data/embeddings/ altında saklanır; aynı metin bir daha
  gönderilmez. Sayfalar yeniden ayrıştırılınca yalnızca DEĞİŞEN parçalar gönderilir.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

import numpy as np

from src import config

MODEL = "gemini-embedding-001"
DIM = 768
BATCH = 100


def _key(text: str, task: str) -> str:
    return hashlib.sha1(f"{MODEL}|{DIM}|{task}|{text}".encode("utf-8")).hexdigest()


class Embedder:
    def __init__(self) -> None:
        self.dir = config.DATA_DIR / "embeddings"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"cache_{MODEL}_{DIM}.npz"
        self.cache: dict[str, np.ndarray] = {}
        if self.path.exists():
            data = np.load(self.path)
            self.cache = dict(zip(json.loads(str(data["keys"])), data["vecs"]))
        self._client = None
        self.sent_texts = 0

    def _save(self) -> None:
        keys = list(self.cache)
        vecs = np.stack([self.cache[k] for k in keys]) if keys else np.zeros((0, DIM), np.float32)
        np.savez_compressed(self.path, keys=json.dumps(keys), vecs=vecs)

    def _call(self, texts: list[str], task: str) -> list[np.ndarray]:
        from google import genai
        from google.genai import types

        if self._client is None:
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        # Ücretsiz katman: dakikada 100 METİN (toplu istekteki her metin ayrı sayılır). Dakikalık
        # sınıra takılınca hata mesajındaki süre kadar beklenir; günlük kotada beklemenin anlamı yok.
        for attempt in range(3):
            try:
                r = self._client.models.embed_content(
                    model=MODEL, contents=texts,
                    config=types.EmbedContentConfig(output_dimensionality=DIM, task_type=task))
                break
            except Exception as e:
                msg = str(e)
                if "PerMinute" not in msg or attempt == 2:
                    raise
                m = re.search(r"retry in ([\d.]+)s", msg)
                time.sleep((float(m.group(1)) if m else 60) + 2)
        if len(r.embeddings) != len(texts):
            raise RuntimeError(f"{len(texts)} metin gönderildi, {len(r.embeddings)} vektör geldi")
        self.sent_texts += len(texts)
        out = []
        for e in r.embeddings:
            v = np.asarray(e.values, dtype=np.float32)
            out.append(v / np.linalg.norm(v))  # boyut küçültülünce vektörler normalize gelmiyor
        return out

    def missing(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[str]:
        return [t for t in dict.fromkeys(texts) if _key(t, task) not in self.cache]

    def embed(self, texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        todo = self.missing(texts, task)
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            for t, v in zip(batch, self._call(batch, task)):
                self.cache[_key(t, task)] = v
            self._save()
        return np.stack([self.cache[_key(t, task)] for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text], task="RETRIEVAL_QUERY")[0]

"""Sona eklenen kayıt dosyaları (JSONL: her satır bir JSON nesnesi): çözümler, kartlar, bildirimler, kararlar.

Streamlit bütün oturumları tek süreçte, ayrı iş parçacıklarında çalıştırır. İki kullanıcı aynı anda yazarsa satırlar
birbirine karışmasın diye ekleme bir kilitle yapılır (birden çok satır tek seferde yazılır).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

_LOCK = threading.Lock()


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def append(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    with _LOCK, path.open("a", encoding="utf-8") as f:
        f.write(text)

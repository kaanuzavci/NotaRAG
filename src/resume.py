"""Kaldığın yerden devam et: kişinin en son yarım bıraktığı kart oturumu ve sınav (data/app.sqlite, progress).

Kişi ve tür ('cards' | 'exam') başına tek satır: ekrandaki durumun (st.session_state.cards / .exam) kopyası. Her
değişiklikte üzerine yazılır, oturum bitince silinir. Böylece sekme kapansa, çıkış yapılsa ya da başka bir cihazdan
girilse de ana sayfa yarım kalanı gösterir. Sınavın süresi beklenen arada işlemez: kayıt anı saklanır, devam
edilirken başlangıç o kadar ileri alınır.
"""

from __future__ import annotations

import json
import time

from src import appdb

KINDS = ("cards", "exam")


def save(user_id: str | None, kind: str, state: dict) -> None:
    if not user_id:
        return
    assert kind in KINDS
    with appdb.connect() as con:
        con.execute("INSERT INTO progress (user_id, kind, data, updated) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (user_id, kind) DO UPDATE SET data = excluded.data, updated = excluded.updated",
                    (user_id, kind, json.dumps(state, ensure_ascii=False), time.time()))


def load(user_id: str | None, kind: str) -> dict | None:
    """Kayıtlı durum + 'updated' (son değişiklik zamanı); yoksa None."""
    if not user_id:
        return None
    with appdb.connect() as con:
        row = con.execute("SELECT data, updated FROM progress WHERE user_id = ? AND kind = ?", (user_id, kind)).fetchone()
    if not row:
        return None
    state = json.loads(row["data"])
    state["updated"] = row["updated"]
    return state


def restore_exam(state: dict) -> dict:
    """Sınava dönüş: beklenen süre sayaca eklenmesin (başlangıç, ara kadar ileri alınır)."""
    s = {k: v for k, v in state.items() if k != "updated"}
    if s.get("started") and state.get("updated"):
        s["started"] += max(0.0, time.time() - state["updated"])
    s["phase"] = "solve" if s.get("started") else "start"
    return s


def clear(user_id: str | None, kind: str) -> None:
    if not user_id:
        return
    with appdb.connect() as con:
        con.execute("DELETE FROM progress WHERE user_id = ? AND kind = ?", (user_id, kind))

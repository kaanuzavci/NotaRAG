"""Kota defteri + yanıt önbelleği (yerel SQLite, data/llm.sqlite).

- usage: model başına, o modelin kota günü için istek/token sayısı ve "dolu" işareti.
- cache: aynı (model, istem, görüntü, parametre) için yanıt bir kez alınır; tekrar çalıştırma kota harcamaz.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from src import config
from src.llm.models import MODELS

_DB = config.DATA_DIR / "llm.sqlite"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.execute("""CREATE TABLE IF NOT EXISTS usage (model TEXT, day TEXT, requests INT DEFAULT 0,
                 tokens INT DEFAULT 0, exhausted INT DEFAULT 0, PRIMARY KEY (model, day))""")
    c.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, model TEXT, response TEXT, created REAL)")
    # Groq'un token/gün sınırı kayan 24 saatlik pencere: her çağrının zamanı ve token'ı tutulur
    c.execute("CREATE TABLE IF NOT EXISTS calls (model TEXT, ts REAL, tokens INT)")
    # Sağlayıcı "X dakika sonra dene" dediğinde o saate kadar model kullanılmaz (gün boyu değil)
    c.execute("CREATE TABLE IF NOT EXISTS cooldown (model TEXT PRIMARY KEY, until REAL)")
    # İstem önbelleği (Groq gpt-oss): sağlayıcının önbellekten okuduğu giriş token'ları. calls.tokens bunları da
    # içerir; Groq bunları token/gün sınırından düşüyor mu, ölçülene kadar yalnızca ayrıca kaydedilir (calls'a
    # sütun eklenmedi: çalışan eski süreçlerin 'INSERT INTO calls VALUES (?, ?, ?)' satırı bozulurdu)
    c.execute("CREATE TABLE IF NOT EXISTS prompt_cache (model TEXT, ts REAL, tokens INT)")
    # Ölçüm: TPD hatasında sağlayıcının bildirdiği kullanım ile bizim kaydımız ve önbellekli kısım yan yana.
    # used ≈ ours - cached çıkarsa önbellekli token kotadan düşmüyor demektir → kayıtta düşülebilir
    c.execute("CREATE TABLE IF NOT EXISTS quota_sync (model TEXT, ts REAL, used INT, ours INT, cached INT)")
    return c


def quota_day(model: str) -> str:
    tz = MODELS[model].tz if model in MODELS else "UTC"
    return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")


def usage(model: str) -> tuple[int, int, bool]:
    with _conn() as c:
        row = c.execute("SELECT requests, tokens, exhausted FROM usage WHERE model=? AND day=?",
                        (model, quota_day(model))).fetchone()
    return (row[0], row[1], bool(row[2])) if row else (0, 0, False)


def tokens_24h(model: str, table: str = "calls") -> int:
    with _conn() as c:
        row = c.execute(f"SELECT COALESCE(SUM(tokens), 0) FROM {table} WHERE model=? AND ts > ?",
                        (model, time.time() - 86400)).fetchone()
    return int(row[0])


def cached_24h(model: str) -> int:
    """Son 24 saatte istem önbelleğinden okunan giriş token'ları (tokens_24h'nin içinde)."""
    return tokens_24h(model, "prompt_cache")


def cooldown_left(model: str) -> float:
    with _conn() as c:
        row = c.execute("SELECT until FROM cooldown WHERE model=?", (model,)).fetchone()
    return max(0.0, row[0] - time.time()) if row else 0.0


def set_cooldown(model: str, seconds: float) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO cooldown VALUES (?, ?)", (model, time.time() + seconds))


def available(model: str, need_tokens: int = 0) -> bool:
    """Günlük istek kotası, bekleme süresi ve kayan 24 saatlik token sınırı (tpd) birlikte kontrol edilir."""
    req, _, exhausted = usage(model)
    spec = MODELS.get(model)
    if exhausted or cooldown_left(model) > 0:
        return False
    if spec and spec.rpd is not None and req >= spec.rpd:
        return False
    # Tahminimiz (karakter/3) gerçek token sayısının biraz altında kalıyor → %5 pay
    return not (spec and spec.tpd is not None and tokens_24h(model) * 1.05 + need_tokens > spec.tpd)


def time_until_available(model: str, need_tokens: int = 0) -> float:
    """Model bu işi yapabilecek hale ne zaman gelir (sn)? Groq: kayan 24 saatte eski çağrılar düştükçe yer açılır;
    Gemini: takvim günü (sağlayıcının saat diliminde gece yarısı). Kullanılabilirse 0."""
    spec = MODELS.get(model)
    wait = cooldown_left(model)
    if spec is None:
        return wait
    req, _, exhausted = usage(model)
    if exhausted or (spec.rpd is not None and req >= spec.rpd):
        now = datetime.now(ZoneInfo(spec.tz))
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return max(wait, 86400 - (now - midnight).total_seconds() + 60)
    if spec.tpd is None:
        return wait
    with _conn() as c:
        rows = c.execute("SELECT ts, tokens FROM calls WHERE model=? AND ts > ? ORDER BY ts",
                         (model, time.time() - 86400)).fetchall()
    excess = sum(t for _, t in rows) * 1.05 + need_tokens - spec.tpd
    freed = 0.0
    for ts, tok in rows:
        if freed >= excess:
            break
        freed += tok * 1.05
        wait = max(wait, ts + 86400 - time.time() + 30)
    return max(0.0, wait)


def record(model: str, tokens: int = 0, cached: int = 0) -> None:
    with _conn() as c:
        c.execute("INSERT INTO calls VALUES (?, ?, ?)", (model, time.time(), tokens))
        if cached:
            c.execute("INSERT INTO prompt_cache VALUES (?, ?, ?)", (model, time.time(), cached))
        c.execute("""INSERT INTO usage (model, day, requests, tokens) VALUES (?, ?, 1, ?)
                     ON CONFLICT(model, day) DO UPDATE SET requests=requests+1, tokens=tokens+excluded.tokens""",
                  (model, quota_day(model), tokens))


def record_correction(model: str, tokens: int) -> None:
    """Sağlayıcının bildirdiği gerçek kullanım ile kaydımız arasındaki fark: yalnızca kayan pencereye eklenir
    (günlük istek sayısını değiştirmez)."""
    with _conn() as c:
        c.execute("INSERT INTO calls VALUES (?, ?, ?)", (model, time.time(), tokens))


def record_sync(model: str, used: int) -> None:
    """Sağlayıcının TPD hatasında bildirdiği kullanımı, o anki kaydımızla birlikte sakla (istem önbelleği ölçümü)."""
    with _conn() as c:
        c.execute("INSERT INTO quota_sync VALUES (?, ?, ?, ?, ?)",
                  (model, time.time(), used, tokens_24h(model), cached_24h(model)))


def last_sync(model: str) -> tuple[float, int, int, int] | None:
    """(zaman, sağlayıcının bildirdiği, bizim kaydımız, önbellekli kısım) — en son TPD hatasından."""
    with _conn() as c:
        return c.execute("SELECT ts, used, ours, cached FROM quota_sync WHERE model=? ORDER BY ts DESC LIMIT 1",
                         (model,)).fetchone()


def mark_exhausted(model: str) -> None:
    with _conn() as c:
        c.execute("""INSERT INTO usage (model, day, exhausted) VALUES (?, ?, 1)
                     ON CONFLICT(model, day) DO UPDATE SET exhausted=1""", (model, quota_day(model)))


def cache_key(model: str, prompt: str, image: bytes | None, params: dict) -> str:
    img = hashlib.sha1(image).hexdigest() if image else ""
    return hashlib.sha1(json.dumps([model, prompt, img, params], sort_keys=True).encode("utf-8")).hexdigest()


def cache_get(key: str) -> str | None:
    with _conn() as c:
        row = c.execute("SELECT response FROM cache WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def cache_put(key: str, model: str, response: str) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)", (key, model, response, time.time()))


def report() -> list[dict]:
    """Bugünkü kullanım: her model için harcanan / limit."""
    rows = []
    for name, spec in MODELS.items():
        req, tok, ex = usage(name)
        rows.append({"model": name, "day": quota_day(name), "requests": req, "rpd": spec.rpd,
                     "tokens": tok, "tokens_24h": tokens_24h(name), "cached_24h": cached_24h(name),
                     "tpd": spec.tpd, "exhausted": ex,
                     "cooldown_s": round(cooldown_left(name))})
    return rows


class Throttle:
    """Dakikalık istek/token sınırına çarpmadan önce bekler (süreç içi kayan pencere)."""

    def __init__(self) -> None:
        self.events: dict[str, deque] = {}

    def wait(self, model: str, tokens: int) -> None:
        spec = MODELS.get(model)
        if not spec or (spec.rpm is None and spec.tpm is None):
            return
        q = self.events.setdefault(model, deque())
        while True:
            now = time.time()
            while q and now - q[0][0] > 60:
                q.popleft()
            ok_rpm = spec.rpm is None or len(q) < spec.rpm
            ok_tpm = spec.tpm is None or sum(t for _, t in q) + tokens <= spec.tpm
            if ok_rpm and ok_tpm:
                q.append((now, tokens))
                return
            time.sleep(max(1.0, 60 - (now - q[0][0]) + 0.5))

    def can(self, model: str, tokens: int) -> bool:
        """Beklemeden şimdi çağrılabilir mi? (wait() ile aynı kural, ama bloklamaz)"""
        spec = MODELS.get(model)
        if not spec or (spec.rpm is None and spec.tpm is None):
            return True
        q = self.events.get(model, deque())
        now = time.time()
        recent = [(t, n) for t, n in q if now - t <= 60]
        return ((spec.rpm is None or len(recent) < spec.rpm)
                and (spec.tpm is None or sum(n for _, n in recent) + tokens <= spec.tpm))

    def settle(self, model: str, actual_tokens: int) -> None:
        """Çağrı bitince en kötü durum rezervasyonunu gerçek kullanımla değiştir.

        Pilotta rezervasyon çağrı başına ~4500 token (max_tokens dahil), gerçek kullanım ~1800'dü;
        düzeltme olmadan Groq'ta dakikada yalnızca 1 çağrı yapılabiliyordu.
        """
        q = self.events.get(model)
        if q:
            ts, _ = q.pop()
            q.append((ts, actual_tokens))

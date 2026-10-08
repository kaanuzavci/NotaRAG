"""Uygulama veritabanı (data/app.sqlite): hesaplar, oturumlar, belge kaydı.

Değişebilen ve tekil olması gereken kayıtlar burada (aynı kullanıcı adı iki kez alınamaz, belgenin görünürlüğü
değişir). Sona eklenen geçmiş (çözümler, kartlar, bildirimler, kararlar) JSONL dosyalarında kalır.
LLM önbelleğinden (llm.sqlite) ayrı tutulur: önbellek silinirse kotayla yeniden üretilir, hesaplar üretilemez.

Şema değişikliği: MIGRATIONS listesinin SONUNA yeni bir adım eklenir, eskileri asla değiştirilmez. Dosyanın hangi
adıma kadar geldiği PRAGMA user_version'da durur; açılışta eksik adımlar sırayla uygulanır. Böylece yeni bir tablo
ya da alan (ör. telefon doğrulaması) var olan veriyi bozmadan eklenir.
WAL kipi: arayüz ve arka plan süreçleri (belge işleme) aynı anda okuyup yazabilir.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src import config

PATH: Path = config.APP_DB  # testler ve önizleme geçici dosyaya yönlendirir

MIGRATIONS: list[list[str]] = [
    # 1 (2026-10-07): hesaplar, giriş yolları, oturumlar, ayarlar, belge kaydı ve erişim
    [
        # Hesabın değişmeyen kimliği giriş yönteminden bağımsız: kayıtlara (çözüm, kart, bildirim) bu kimlik yazılır
        """CREATE TABLE users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created REAL NOT NULL)""",
        # Giriş yolları: bugün 'password' (subject = kullanıcı adı, secret = parola özeti); ileride 'google'
        # (subject = OIDC 'sub') ya da 'phone' (subject = +90...) aynı hesaba yeni satır olarak bağlanır
        """CREATE TABLE identities (
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            secret TEXT,
            created REAL NOT NULL,
            PRIMARY KEY (provider, subject))""",
        "CREATE INDEX identities_user ON identities(user_id)",
        # "Beni hatırla": belirtecin kendisi değil özeti saklanır (dosya ele geçse de oturum çalınamaz)
        """CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created REAL NOT NULL,
            expires REAL NOT NULL)""",
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)",
        # doc = belgenin veri dosyalarındaki anahtarı (sample_docs/<doc>.pdf, parsed/<doc>.json, parça kimlikleri);
        # bir kez verilir, değişmez. public_since dolu = herkese açık (geri alınamaz)
        """CREATE TABLE documents (
            doc TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            text_sig TEXT,
            pages INTEGER,
            owner TEXT REFERENCES users(id),
            public_since REAL,
            created REAL NOT NULL)""",
        "CREATE INDEX documents_sig ON documents(text_sig)",
        """CREATE TABLE doc_access (
            doc TEXT NOT NULL REFERENCES documents(doc) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            since REAL NOT NULL,
            PRIMARY KEY (doc, user_id))""",
        "CREATE INDEX doc_access_user ON doc_access(user_id)",
    ],
    # 2 (2026-10-08): profil (resim, kısa tanıtım) ve "kaldığın yerden devam et" (yarım kalan kart oturumu, sınav)
    [
        "ALTER TABLE users ADD COLUMN avatar BLOB",   # 256×256 JPEG; yoksa baş harfler gösterilir
        "ALTER TABLE users ADD COLUMN about TEXT",    # ör. "Bilgisayar Mühendisliği 3. sınıf"
        # Kişi ve tür başına (cards / exam) tek satır: en son yarım kalan oturumun durumu (JSON)
        """CREATE TABLE progress (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            data TEXT NOT NULL,
            updated REAL NOT NULL,
            PRIMARY KEY (user_id, kind))""",
    ],
]

_ready: set[str] = set()  # bu süreçte şeması güncellenmiş dosyalar


def _migrate(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA journal_mode = WAL")  # dosyaya kalıcı yazılır; işlem (transaction) içinde değiştirilemez
    con.execute("BEGIN IMMEDIATE")  # iki süreç aynı anda açarsa ikincisi bekler, sonra sürümü güncel okur
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for n, steps in enumerate(MIGRATIONS[version:], version + 1):
        for sql in steps:
            con.execute(sql)
        con.execute(f"PRAGMA user_version = {n}")
    con.commit()


@contextmanager
def connect():
    """with connect() as con: ... → çıkışta kaydeder (hata olursa geri alır) ve kapatır."""
    PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        if str(PATH) not in _ready:
            _migrate(con)
            _ready.add(str(PATH))
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def version() -> int:
    with connect() as con:
        return con.execute("PRAGMA user_version").fetchone()[0]

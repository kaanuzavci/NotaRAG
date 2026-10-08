"""Hesaplar ve giriş (data/app.sqlite; şema src/appdb.py).

Rol yok: her hesap aynı şeyleri yapar (belge yükler, sınav çözer, inceler); farkı yalnızca kendi verisidir.
Hesabın değişmeyen kimliği (users.id) giriş yönteminden bağımsızdır; çözüm, kart, bildirim ve karar kayıtlarına bu
kimlik yazılır. Giriş yolları ayrı tabloda (identities: sağlayıcı + o sağlayıcıdaki kimlik). Bugün yalnızca
'password' (kullanıcı adı + parola); ileride Google ('google', OIDC 'sub') ya da telefon ('phone') aynı hesaba yeni
bir satır olarak bağlanır, şema ve kayıtlar değişmez.

Parola: scrypt (Python'un hashlib'i, ek paket yok). Tuz ve parametreler özetin içinde saklanır: parametreler ileride
güçlendirilirse eski parolalar yine doğrulanır. Parola hiçbir yere düz yazılmaz.
Eski kayıtlar (girişten önceki dönemin çözümleri, kartları; kullanıcı alanı yok): ilk açılan hesaba aittir (legacy_owner).

Komut satırı: python -m src.accounts                        (hesapları listele)
              python -m src.accounts sifirla <kullanıcı_adı>  (parolayı sıfırla; unutulursa)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sys
import time

from src import appdb

USERNAME = re.compile(r"[a-z0-9._-]{3,32}")
MIN_PASSWORD = 8
SESSION_DAYS = 30
_N_LOG2, _R, _P = 15, 8, 1  # scrypt: 2^15 × 8 × 128 bayt = 32 MB bellek, ~0,1 sn (kaba kuvvete karşı yavaş)
_legacy: dict[str, str | None] = {}  # veritabanı yolu → eski kayıtların sahibi (bir kez okunur)


class AccountError(ValueError):
    """Kullanıcıya gösterilecek (Türkçe) hata."""


# ---------------------------------------------------------------- parola

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** _N_LOG2, r=_R, p=_P, maxmem=64 * 2 ** 20)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return f"scrypt${_N_LOG2}${_R}${_P}${b64(salt)}${b64(key)}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, n_log2, r, p, salt, key = stored.split("$")
        if algo != "scrypt":
            return False
        got = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt), n=2 ** int(n_log2), r=int(r),
                             p=int(p), maxmem=128 * 2 ** 20)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, base64.b64decode(key))  # sabit süreli karşılaştırma


# ---------------------------------------------------------------- hesaplar

def _user(con, user_id: str) -> dict | None:
    row = con.execute("SELECT id, name FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    login = con.execute("SELECT subject FROM identities WHERE user_id = ? AND provider = 'password'",
                        (user_id,)).fetchone()
    return {"id": row["id"], "name": row["name"], "username": login["subject"] if login else None}


def profile(user_id: str) -> dict | None:
    """Profil sayfası için: ad, kullanıcı adı, tanıtım, katılım zamanı, resmi var mı."""
    with appdb.connect() as con:
        u = _user(con, user_id)
        if not u:
            return None
        row = con.execute("SELECT about, created, avatar IS NOT NULL AS has_avatar FROM users WHERE id = ?",
                          (user_id,)).fetchone()
    return {**u, "about": row["about"] or "", "created": row["created"], "has_avatar": bool(row["has_avatar"])}


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def create(username: str, password: str, name: str = "") -> dict:
    """Yeni hesap. İlk hesap eski kayıtların sahibi olur (dönüşte "legacy": True)."""
    username, name = normalize_username(username), " ".join((name or "").split()) or username
    if not USERNAME.fullmatch(username):
        raise AccountError("Kullanıcı adı 3-32 karakter olmalı; yalnızca küçük harf (a-z), rakam, nokta, alt çizgi "
                           "ve tire.")
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(f"Parola en az {MIN_PASSWORD} karakter olmalı.")
    if len(name) > 60:
        raise AccountError("Görünen ad en çok 60 karakter olabilir.")
    secret = hash_password(password)  # yavaş adım işlem dışında (veritabanı kilitli kalmasın)
    with appdb.connect() as con:
        if con.execute("SELECT 1 FROM identities WHERE provider = 'password' AND subject = ?", (username,)).fetchone():
            raise AccountError("Bu kullanıcı adı alınmış.")
        uid, now = secrets.token_hex(6), time.time()
        con.execute("INSERT INTO users (id, name, created) VALUES (?, ?, ?)", (uid, name, now))
        link(con, uid, "password", username, secret)
        first = con.execute("SELECT value FROM settings WHERE key = 'legacy_owner'").fetchone() is None
        if first:
            con.execute("INSERT INTO settings (key, value) VALUES ('legacy_owner', ?)", (uid,))
    _legacy.pop(str(appdb.PATH), None)
    return {"id": uid, "name": name, "username": username, "legacy": first}


def link(con, user_id: str, provider: str, subject: str, secret: str | None = None) -> None:
    """Hesaba bir giriş yolu bağlar. Yeni yöntem (Google, telefon) eklemek = bu fonksiyonu o sağlayıcıyla çağırmak."""
    con.execute("INSERT INTO identities (provider, subject, user_id, secret, created) VALUES (?, ?, ?, ?, ?)",
                (provider, subject, user_id, secret, time.time()))


def by_identity(provider: str, subject: str) -> tuple[dict, str | None] | None:
    """(hesap, saklı sır) ya da None."""
    with appdb.connect() as con:
        row = con.execute("SELECT user_id, secret FROM identities WHERE provider = ? AND subject = ?",
                          (provider, subject)).fetchone()
        return (_user(con, row["user_id"]), row["secret"]) if row else None


def authenticate(username: str, password: str) -> dict | None:
    found = by_identity("password", normalize_username(username))
    if not found:
        hash_password(password or "")  # olmayan hesapta da aynı süre: süreden kullanıcı adının varlığı anlaşılmasın
        return None
    user, secret = found
    return user if secret and check_password(password or "", secret) else None


def get(user_id: str) -> dict | None:
    with appdb.connect() as con:
        return _user(con, user_id)


def all_users() -> list[dict]:
    with appdb.connect() as con:
        return [_user(con, r["id"]) for r in con.execute("SELECT id FROM users ORDER BY created")]


def count() -> int:
    with appdb.connect() as con:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def set_password(username: str, password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(f"Parola en az {MIN_PASSWORD} karakter olmalı.")
    secret = hash_password(password)
    with appdb.connect() as con:
        row = con.execute("SELECT user_id FROM identities WHERE provider = 'password' AND subject = ?",
                          (normalize_username(username),)).fetchone()
        if not row:
            raise AccountError("Böyle bir kullanıcı yok.")
        con.execute("UPDATE identities SET secret = ? WHERE provider = 'password' AND subject = ?",
                    (secret, normalize_username(username)))
        con.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))  # açık oturumlar kapanır


def change_password(user_id: str, old: str, new: str) -> None:
    """Kişinin kendi parolasını değiştirmesi (profil sayfası): önce eski parola doğrulanır."""
    with appdb.connect() as con:
        row = con.execute("SELECT subject, secret FROM identities WHERE user_id = ? AND provider = 'password'",
                          (user_id,)).fetchone()
    if not row or not check_password(old or "", row["secret"] or ""):
        raise AccountError("Şu anki parola yanlış.")
    set_password(row["subject"], new)


# ---------------------------------------------------------------- profil

AVATAR_SIZE = 256
MAX_AVATAR_BYTES = 8 * 2 ** 20


def update_profile(user_id: str, name: str, about: str = "") -> None:
    name, about = " ".join((name or "").split()), " ".join((about or "").split())
    if not 1 <= len(name) <= 60:
        raise AccountError("Görünen ad 1-60 karakter olmalı.")
    if len(about) > 120:
        raise AccountError("Tanıtım en çok 120 karakter olabilir.")
    with appdb.connect() as con:
        con.execute("UPDATE users SET name = ?, about = ? WHERE id = ?", (name, about or None, user_id))


def set_avatar(user_id: str, data: bytes) -> None:
    """Yüklenen resim ortadan kare kırpılır, 256×256 JPEG'e küçültülür (veritabanında ~15-30 KB). Resim dosyası
    olduğu gibi saklanmaz: kamera fotoğraflarındaki konum gibi üst veriler de böylece atılır."""
    from io import BytesIO

    from PIL import Image, ImageOps, UnidentifiedImageError

    if len(data) > MAX_AVATAR_BYTES:
        raise AccountError("Resim en çok 8 MB olabilir.")
    try:
        img = ImageOps.exif_transpose(Image.open(BytesIO(data)))  # telefon fotoğrafı yan dönmesin
    except (UnidentifiedImageError, OSError):
        raise AccountError("Bu dosya bir resim olarak açılamadı (JPG, PNG ya da WEBP yükle).")
    img = ImageOps.fit(img.convert("RGB"), (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    out = BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)
    with appdb.connect() as con:
        con.execute("UPDATE users SET avatar = ? WHERE id = ?", (out.getvalue(), user_id))


def avatar(user_id: str) -> bytes | None:
    with appdb.connect() as con:
        row = con.execute("SELECT avatar FROM users WHERE id = ?", (user_id,)).fetchone()
    return bytes(row["avatar"]) if row and row["avatar"] else None


def remove_avatar(user_id: str) -> None:
    with appdb.connect() as con:
        con.execute("UPDATE users SET avatar = NULL WHERE id = ?", (user_id,))


def legacy_owner() -> str | None:
    """Kullanıcı alanı olmayan eski kayıtların sahibi (ilk hesap); hesap yoksa None."""
    key = str(appdb.PATH)
    if key not in _legacy:
        if not appdb.PATH.exists():  # okumak veritabanı oluşturmasın (ör. testler, komut satırı ölçümleri)
            return None
        with appdb.connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key = 'legacy_owner'").fetchone()
        if not row:
            return None  # henüz hesap yok: sonuç saklanmaz, ilk hesap açılınca okunur
        _legacy[key] = row["value"]
    return _legacy[key]


# ---------------------------------------------------------------- oturumlar ("beni hatırla")

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(user_id: str, days: int = SESSION_DAYS) -> str:
    token, now = secrets.token_urlsafe(32), time.time()
    with appdb.connect() as con:
        con.execute("DELETE FROM sessions WHERE expires < ?", (now,))  # süresi geçenleri temizle
        con.execute("INSERT INTO sessions (token_hash, user_id, created, expires) VALUES (?, ?, ?, ?)",
                    (_token_hash(token), user_id, now, now + days * 86400))
    return token


def session_user(token: str) -> dict | None:
    if not isinstance(token, str) or not token:  # çerez tarayıcıdan gelir: her türlü değer olabilir
        return None
    with appdb.connect() as con:
        row = con.execute("SELECT user_id FROM sessions WHERE token_hash = ? AND expires > ?",
                          (_token_hash(token), time.time())).fetchone()
        return _user(con, row["user_id"]) if row else None


def end_session(token: str) -> None:
    with appdb.connect() as con:
        con.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "sifirla":
        import getpass
        pw = getpass.getpass("Yeni parola: ")
        if pw != getpass.getpass("Yeni parola (tekrar): "):
            sys.exit("Parolalar aynı değil.")
        try:
            set_password(sys.argv[2], pw)
        except AccountError as e:
            sys.exit(str(e))
        print("Parola değişti; açık oturumlar kapatıldı.")
    else:
        legacy = legacy_owner()
        for u in all_users():
            print(f"{u['username']:<20} {u['name']:<30} {u['id']}" + ("  (eski kayıtların sahibi)" if u["id"] == legacy else ""))

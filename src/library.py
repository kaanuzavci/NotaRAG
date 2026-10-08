"""Belge kütüphanesi: her belgenin kaydı, kimliği, sahibi ve görünürlüğü (data/app.sqlite; şema src/appdb.py).

Kimlik (doc): belgenin veri dosyalarındaki anahtarı — data/sample_docs/<doc>.pdf, parsed/<doc>.json, parça
kimliklerinin başı (<doc>:p003:1), questions/<doc>_tr.jsonl. Bir kez verilir, değişmez; görünen ad ayrıdır ve
değiştirilebilir. Yeni belgede dosya adının kökü; o ad alınmışsa sonuna içerik özetinin ilk 6 hanesi eklenir.
Hiçbir yükleme var olan bir belgenin üzerine yazmaz (eskiden aynı adlı farklı PDF eskisinin yerine geçiyor, eski
sorular ve sayfa metinleri yeni dosyayla karışıyordu).

Aynı belgeyi tanıma (yeniden işleme yok, kota harcanmaz), ad ya da sayfa sayısına değil içeriğe bakılır:
  1. Dosya özeti (SHA-256): birebir aynı dosya, adı ne olursa olsun.
  2. Sayfa sayısı + her sayfanın metninin özeti: dosyası farklı (yeniden kaydedilmiş, üst verisi değişmiş) ama
     içeriği aynı belge. Metni az olan (taranmış) belgede bu kademe atlanır: boş sayfalar her belgede eşleşirdi.
Kısmen aynı belge (notun yeni sürümü) ayrı belgedir: değişen sayfalarda eski soruların kanıtı tutmaz.
Eşleşen belge yükleyene açılır; hazır sorular, konu haritası ve dizin olduğu gibi kullanılır.

Görünürlük: belge, erişimi olanlara (yükleyenler) görünür. Erişimi olan biri belgeyi herkese açabilir; açılan belge
arayüzden yeniden gizlenemez (başkalarının ondan hazırladığı sınavlar ve kayıtlar boşa düşmesin). Acil durumda
(ör. telif) yalnızca bu bilgisayarda: python -m src.library gizle <belge>.

Komut satırı: python -m src.library   (kayıtlı belgeler)
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
import time
from pathlib import Path

from src import appdb, config

DOCS: Path = config.DATA_DIR / "sample_docs"
MIN_PAGE_CHARS = 30      # bu kadar metni olan sayfa "metinli" sayılır
MIN_TEXT_SHARE = 0.8     # sayfaların en az bu kadarı metinliyse içerik özeti çıkarılır
_names: tuple[float, dict] = (0.0, {})
_skipped: set[str] = set()  # kaydedilemeyen dosyalar (aynı içerik başka adla kayıtlı): her eşitlemede yeniden okunmasın


class LibraryError(ValueError):
    """Kullanıcıya gösterilecek (Türkçe) hata."""


# ---------------------------------------------------------------- içerik özeti

def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_signature(data: bytes) -> tuple[int, str | None]:
    """(sayfa sayısı, sayfa metinlerinin özeti). Metin boşluk ve büyük/küçük harf farkından arındırılır.
    PDF değilse ValueError (PyMuPDF HTML ve düz metni de açıyor; pdf_parser'daki gibi biçime bakılır)."""
    import pymupdf
    with pymupdf.open(stream=data) as doc:
        if not doc.is_pdf or doc.page_count == 0:
            raise ValueError("PDF değil")
        texts = [" ".join(page.get_text().split()).lower() for page in doc]
    if not texts or sum(len(t) >= MIN_PAGE_CHARS for t in texts) < MIN_TEXT_SHARE * len(texts):
        return len(texts), None
    pages = "\n".join(hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts)
    return len(texts), hashlib.sha256(pages.encode("ascii")).hexdigest()


# ---------------------------------------------------------------- kayıt

def _row(r: sqlite3.Row) -> dict:
    d = {"doc": r["doc"], "name": r["name"], "file": r["file"], "pages": r["pages"], "owner": r["owner"],
         "public": r["public_since"] is not None, "public_since": r["public_since"], "created": r["created"]}
    if "rowid" in r.keys():
        d["order"] = r["rowid"]  # kayda giriş sırası (değişmez): ana sayfada notun rengi
    return d


def _taken(con, key: str) -> bool:
    """Bu anahtar kullanılmış mı? Kayıt, PDF ya da ondan türemiş veri (silinmiş bir belgenin artığı) varsa evet;
    yoksa yeni belge eski soruları ve sayfa metinlerini devralırdı. Windows'ta dosya adları büyük/küçük harf duyarsız."""
    if con.execute("SELECT 1 FROM documents WHERE lower(doc) = lower(?)", (key,)).fetchone():
        return True
    d = config.DATA_DIR
    return ((DOCS / f"{key}.pdf").exists() or (config.PARSED_DIR / f"{key}.json").exists()
            or (d / "topics" / f"{key}.json").exists() or any((d / "questions").glob(f"{key}_*.jsonl")))


def _free_key(con, stem: str, sha: str) -> str:
    base = re.sub(r"[:\\/]", "_", stem).strip(" .") or "belge"  # ':' parça kimliğinde ayırıcı
    for key in (base, f"{base}-{sha[:6]}", f"{base}-{sha[:12]}"):
        if not _taken(con, key):
            return key
    raise LibraryError("Bu belge için boş bir ad bulunamadı; dosyanın adını değiştirip yeniden dene.")


def _grant(con, doc: str, user_id: str) -> bool:
    """Erişim verir; zaten varsa False."""
    cur = con.execute("INSERT OR IGNORE INTO doc_access (doc, user_id, since) VALUES (?, ?, ?)",
                      (doc, user_id, time.time()))
    return cur.rowcount == 1


def register(data: bytes, filename: str, user_id: str) -> tuple[dict, str]:
    """Yüklenen PDF'i kaydeder. → (belge, durum). Durum:
    'new' (yeni belge, işlenmeyi bekliyor) · 'same_file' / 'same_content' (sistemde vardı, yükleyene açıldı) ·
    'already_yours' (zaten listesinde)."""
    sha = file_hash(data)
    try:
        pages, sig = text_signature(data)
    except Exception:
        raise LibraryError("Bu dosya PDF olarak açılamadı.")
    with appdb.connect() as con:
        row, status = con.execute("SELECT * FROM documents WHERE sha256 = ?", (sha,)).fetchone(), "same_file"
        if row is None and sig:
            row = con.execute("SELECT * FROM documents WHERE text_sig = ? AND pages = ?", (sig, pages)).fetchone()
            status = "same_content"
        if row is not None:
            return _row(row), (status if _grant(con, row["doc"], user_id) else "already_yours")
        key = _free_key(con, Path(filename).stem, sha)
        (DOCS / f"{key}.pdf").parent.mkdir(parents=True, exist_ok=True)
        (DOCS / f"{key}.pdf").write_bytes(data)
        con.execute("INSERT INTO documents (doc, name, file, sha256, text_sig, pages, owner, public_since, created) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                    (key, config.doc_name(Path(filename).stem), f"{key}.pdf", sha, sig, pages, user_id, time.time()))
        _grant(con, key, user_id)
        row = con.execute("SELECT * FROM documents WHERE doc = ?", (key,)).fetchone()
    _forget_names()
    return _row(row), "new"


def sync() -> int:
    """data/sample_docs'ta olup kayıtta olmayan PDF'leri kaydeder (girişten önceki belgeler, elle konanlar; sahibi
    ilk hesap) ve sahipsiz kayıtları ilk hesaba bağlar. → yeni kaydedilen belge sayısı."""
    from src.accounts import legacy_owner
    owner = legacy_owner()
    with appdb.connect() as con:
        known = {r["file"].lower() for r in con.execute("SELECT file FROM documents")}
    new = 0
    for pdf in sorted(DOCS.glob("*.pdf")):
        if pdf.name.lower() in known or str(pdf) in _skipped:
            continue
        data = pdf.read_bytes()
        try:
            pages, sig = text_signature(data)
        except Exception:
            pages, sig = None, None
        try:
            with appdb.connect() as con:
                con.execute("INSERT INTO documents (doc, name, file, sha256, text_sig, pages, owner, public_since, "
                            "created) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                            (pdf.stem, config.doc_name(pdf.stem), pdf.name, file_hash(data), sig, pages, owner,
                             pdf.stat().st_mtime))
                if owner:
                    _grant(con, pdf.stem, owner)
            new += 1
        except sqlite3.IntegrityError:  # aynı içerik başka adla kayıtlı (ya da başka iş parçacığı az önce kaydetti)
            _skipped.add(str(pdf))
    if owner:
        with appdb.connect() as con:
            for r in con.execute("SELECT doc FROM documents WHERE owner IS NULL").fetchall():
                con.execute("UPDATE documents SET owner = ? WHERE doc = ?", (owner, r["doc"]))
                _grant(con, r["doc"], owner)
    if new:
        _forget_names()
    return new


# ---------------------------------------------------------------- görünürlük ve ad

def visible(user_id: str | None) -> set[str]:
    """Kişinin görebildiği belgeler: herkese açık olanlar + erişimi olanlar."""
    with appdb.connect() as con:
        rows = con.execute("SELECT doc FROM documents WHERE public_since IS NOT NULL "
                           "UNION SELECT doc FROM doc_access WHERE user_id = ?", (user_id,)).fetchall()
    return {r["doc"] for r in rows}


def get(doc: str) -> dict | None:
    with appdb.connect() as con:
        row = con.execute("SELECT * FROM documents WHERE doc = ?", (doc,)).fetchone()
    return _row(row) if row else None


def all_docs() -> dict[str, dict]:
    with appdb.connect() as con:
        return {r["doc"]: _row(r) for r in con.execute("SELECT rowid, * FROM documents ORDER BY created")}


def has_access(doc: str, user_id: str) -> bool:
    with appdb.connect() as con:
        return con.execute("SELECT 1 FROM doc_access WHERE doc = ? AND user_id = ?", (doc, user_id)).fetchone() is not None


def publish(doc: str, user_id: str) -> bool:
    """Belgeyi herkese açar (geri alınamaz). Yalnızca erişimi olan açabilir. → yeni açıldıysa True."""
    if not has_access(doc, user_id):
        raise LibraryError("Bu belgeyi yalnızca onu yükleyenler herkese açabilir.")
    with appdb.connect() as con:
        cur = con.execute("UPDATE documents SET public_since = ? WHERE doc = ? AND public_since IS NULL",
                          (time.time(), doc))
    return cur.rowcount == 1


def add_to_library(doc: str, user_id: str) -> bool:
    """Herkese açık bir notu kişinin kendi notları arasına ekler (ana sayfada "Notlarıma ekle"). → yeni eklendiyse True."""
    d = get(doc)
    if not d or not d["public"]:
        raise LibraryError("Yalnızca herkese açık notlar eklenebilir.")
    with appdb.connect() as con:
        return _grant(con, doc, user_id)


def mine(user_id: str) -> set[str]:
    """Kişinin kendi listesindeki notlar (yükledikleri ve eklediği herkese açık notlar)."""
    with appdb.connect() as con:
        return {r["doc"] for r in con.execute("SELECT doc FROM doc_access WHERE user_id = ?", (user_id,))}


def rename(doc: str, user_id: str, name: str) -> None:
    name = " ".join((name or "").split())
    if not 1 <= len(name) <= 80:
        raise LibraryError("Ad 1-80 karakter olmalı.")
    d = get(doc)
    if not d or d["owner"] != user_id:
        raise LibraryError("Belgenin adını yalnızca sahibi değiştirebilir.")
    with appdb.connect() as con:
        con.execute("UPDATE documents SET name = ? WHERE doc = ?", (name, doc))
    _forget_names()


def _forget_names() -> None:
    global _names
    _names = (0.0, {})


def display_name(doc: str) -> str:
    """Belgenin görünen adı (kayıttaki ad; kayıtta yoksa dosya adından). 10 sn bellekte tutulur: dışa aktarma ve
    soru kartları her soru için çağırır."""
    global _names
    if time.time() - _names[0] > 10:
        try:
            with appdb.connect() as con:
                _names = (time.time(), {r["doc"]: r["name"] for r in con.execute("SELECT doc, name FROM documents")})
        except sqlite3.Error:
            _names = (time.time(), {})
    return _names[1].get(doc) or config.doc_name(doc)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "gizle":  # acil durum (telif): herkese açıklığı kaldırır
        with appdb.connect() as con:
            n = con.execute("UPDATE documents SET public_since = NULL WHERE doc = ?", (sys.argv[2],)).rowcount
        print("Belge yeniden gizli." if n else "Böyle bir belge yok.")
    else:
        from src import accounts
        users = {u["id"]: u["username"] for u in accounts.all_users()}
        with appdb.connect() as con:
            access = {r["doc"]: r["n"] for r in con.execute("SELECT doc, COUNT(*) AS n FROM doc_access GROUP BY doc")}
        for d in all_docs().values():
            print(f"{d['doc'][:44]:<45} {d['name'][:28]:<29} {users.get(d['owner'], '-'):<14} "
                  f"{'herkese açık' if d['public'] else 'gizli':<13} erişim {access.get(d['doc'], 0)}")

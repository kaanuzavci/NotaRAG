"""Hesaplar, oturumlar ve belge kütüphanesi testleri (internetsiz; geçici veritabanı, gerçek kayda dokunmaz).
Çalıştırma: python -m tests.test_accounts"""

import tempfile
import time
from pathlib import Path

import pymupdf

from src import accounts, appdb, config, library


def _fresh(d: str) -> None:
    """Her test kendi boş veritabanı ve belge klasörüyle."""
    appdb.PATH = Path(d) / "app.sqlite"
    library.DOCS = Path(d) / "docs"
    library.DOCS.mkdir()
    library._forget_names()


def _pdf(lines: list[str], title: str = "") -> bytes:
    doc = pymupdf.open()
    for text in lines:
        doc.new_page().insert_text((72, 72), text)
    if title:
        doc.set_metadata({"title": title})  # üst veri farklı → dosya baytları farklı, metin aynı
    return doc.tobytes()


def test_passwords() -> None:
    h = accounts.hash_password("gizli-parola")
    assert h.startswith("scrypt$") and "gizli-parola" not in h
    assert accounts.check_password("gizli-parola", h) and not accounts.check_password("yanlış-parola", h)
    assert accounts.hash_password("gizli-parola") != h  # her seferinde yeni tuz
    assert not accounts.check_password("x", "bozuk") and not accounts.check_password("x", "md5$abc")


def test_accounts_and_sessions() -> None:
    with tempfile.TemporaryDirectory() as d:
        _fresh(d)
        assert appdb.version() == len(appdb.MIGRATIONS) and accounts.legacy_owner() is None
        for bad in (("ka", "parola123"), ("Kaan Uz", "parola123"), ("kaan", "kısa")):
            try:
                accounts.create(*bad)
                raise AssertionError(f"kabul edilmemeliydi: {bad}")
            except accounts.AccountError:
                pass
        a = accounts.create("Kaan", "parola123", "Kaan")  # kullanıcı adı küçük harfe çevrilir
        b = accounts.create("demo", "parola456")
        assert a["username"] == "kaan" and a["legacy"] and not b["legacy"] and b["name"] == "demo"
        assert accounts.legacy_owner() == a["id"] and accounts.count() == 2
        try:
            accounts.create("kaan", "baska-parola")
            raise AssertionError("aynı kullanıcı adı ikinci kez alınmamalı")
        except accounts.AccountError:
            pass
        assert accounts.authenticate("KAAN", "parola123")["id"] == a["id"]
        assert accounts.authenticate("kaan", "parola456") is None and accounts.authenticate("yok", "parola123") is None
        # Oturum: belirteç → hesap; çıkışta ve süresi geçince geçersiz
        tok = accounts.new_session(a["id"])
        assert accounts.session_user(tok)["id"] == a["id"] and accounts.session_user("uydurma") is None
        accounts.end_session(tok)
        assert accounts.session_user(tok) is None
        assert accounts.session_user(accounts.new_session(a["id"], days=-1)) is None
        # Parola sıfırlama: eski parola ve açık oturumlar geçersiz
        tok = accounts.new_session(b["id"])
        accounts.set_password("demo", "yeni-parola")
        assert accounts.authenticate("demo", "parola456") is None and accounts.authenticate("demo", "yeni-parola")
        assert accounts.session_user(tok) is None
        # Yeni giriş yolu (ileride Google / telefon) aynı hesaba bağlanır; şema değişmez
        with appdb.connect() as con:
            accounts.link(con, a["id"], "google", "1234567890")
        assert accounts.by_identity("google", "1234567890")[0]["id"] == a["id"]
        # Şema adımları bir kez uygulanır: yeniden açmak bir şey bozmaz
        appdb._ready.clear()
        assert appdb.version() == len(appdb.MIGRATIONS) and accounts.count() == 2


def test_library() -> None:
    with tempfile.TemporaryDirectory() as d:
        _fresh(d)
        # Girişten önce elle konmuş belge: sahipsiz kaydedilir, ilk hesap açılınca ona bağlanır
        (library.DOCS / "eski_not.pdf").write_bytes(_pdf(["Eski not: mutasyon çeşitliliği artırır."] * 2))
        assert library.sync() == 1 and library.get("eski_not")["owner"] is None
        a = accounts.create("kaan", "parola123")["id"]
        b = accounts.create("demo", "parola123")["id"]
        library.sync()
        assert library.get("eski_not")["owner"] == a and library.visible(a) == {"eski_not"} and not library.visible(b)
        assert library.display_name("eski_not") == "eski not"

        notes = _pdf(["Çaprazlama iki ebeveynin genlerini birleştirir.", "Seçim, uygun bireyleri bir sonraki kuşağa taşır."])
        doc, status = library.register(notes, "Hafta 3.pdf", a)
        assert status == "new" and doc["doc"] == "Hafta 3" and (library.DOCS / "Hafta 3.pdf").read_bytes() == notes
        # Aynı dosya başka adla: yeniden işlenmez, yükleyene açılır; aynı kişi yeniden yüklerse "zaten listende"
        doc2, status = library.register(notes, "kopya.pdf", b)
        assert (status, doc2["doc"]) == ("same_file", "Hafta 3") and not (library.DOCS / "kopya.pdf").exists()
        assert library.register(notes, "Hafta 3.pdf", a)[1] == "already_yours"
        # Dosyası farklı (üst veri), içeriği aynı: yine eşleşir
        same = _pdf(["Çaprazlama iki ebeveynin genlerini birleştirir.", "Seçim, uygun bireyleri bir sonraki kuşağa taşır."], title="v2")
        assert same != notes and library.register(same, "baska_ad.pdf", b)[1] == "already_yours"
        c = accounts.create("ucuncu", "parola123")["id"]
        assert library.register(same, "baska_ad.pdf", c)[1] == "same_content"
        # Aynı ad, farklı içerik: eskisinin üzerine yazılmaz, yeni anahtar alır (eskiden yerine geçiyordu)
        other = _pdf(["Elitizm en iyi bireyi bir sonraki kuşağa aynen taşır.", "Bambaşka bir not."])
        doc3, status = library.register(other, "Hafta 3.pdf", a)
        assert status == "new" and doc3["doc"].startswith("Hafta 3-") and (library.DOCS / "Hafta 3.pdf").read_bytes() == notes
        # Kısmen aynı (yeni sürüm): ayrı belge
        v2 = _pdf(["Çaprazlama iki ebeveynin genlerini birleştirir.", "Seçim, uygun bireyleri bir sonraki kuşağa taşır.", "Yeni sayfa."])
        assert library.register(v2, "Hafta 3 yeni.pdf", a)[1] == "new"
        # Metinsiz (taranmış) iki farklı belge: boş sayfalar eşleşmesin
        scan1, scan2 = _pdf(["", ""]), _pdf(["", "", ""])
        assert library.register(scan1, "tarama1.pdf", a)[1] == "new" and library.register(scan2, "tarama2.pdf", a)[1] == "new"
        try:
            library.register(b"<html>error page</html>", "x.pdf", a)
            raise AssertionError("PDF olmayan dosya kabul edilmemeli")
        except library.LibraryError:
            pass
        # Görünürlük: gizli belge yalnızca erişimi olanlara; herkese açmak tek yönlü
        assert doc3["doc"] not in library.visible(b)
        try:
            library.publish(doc3["doc"], b)  # erişimi yok
            raise AssertionError("erişimi olmayan herkese açamamalı")
        except library.LibraryError:
            pass
        assert library.publish(doc3["doc"], a) and not library.publish(doc3["doc"], a)
        assert doc3["doc"] in library.visible(b) and library.get(doc3["doc"])["public"]
        assert not hasattr(library, "unpublish")  # arayüzde geri alma yok
        # Ad: yalnızca sahibi değiştirir
        try:
            library.rename("Hafta 3", b, "Başkasının adı")
            raise AssertionError("sahibi olmayan adı değiştirmemeli")
        except library.LibraryError:
            pass
        library.rename("Hafta 3", a, "Genetik Algoritmalar 3")
        assert library.display_name("Hafta 3") == "Genetik Algoritmalar 3"


def test_profile_and_resume() -> None:
    """Profil (ad, tanıtım, resim), kendi parolanı değiştirme, herkese açık notu listeye ekleme, kaldığın yerden devam."""
    from io import BytesIO

    from PIL import Image

    from src import resume
    with tempfile.TemporaryDirectory() as d:
        _fresh(d)
        a = accounts.create("kaan", "parola123", "Kaan")["id"]
        b = accounts.create("demo", "parola123")["id"]
        accounts.update_profile(a, "  Kaan   Uzavcı ", "Bilgisayar Mühendisliği")
        p = accounts.profile(a)
        assert p["name"] == "Kaan Uzavcı" and p["about"] == "Bilgisayar Mühendisliği" and not p["has_avatar"]
        for bad in (("", ""), ("x" * 61, ""), ("Kaan", "y" * 121)):
            try:
                accounts.update_profile(a, *bad)
                raise AssertionError(f"kabul edilmemeliydi: {bad}")
            except accounts.AccountError:
                pass
        # Resim: ortadan kare kırpılır, 256×256 JPEG; resim olmayan dosya reddedilir
        buf = BytesIO()
        Image.new("RGB", (800, 400), (200, 30, 30)).save(buf, "PNG")
        accounts.set_avatar(a, buf.getvalue())
        img = Image.open(BytesIO(accounts.avatar(a)))
        assert img.format == "JPEG" and img.size == (256, 256) and accounts.profile(a)["has_avatar"]
        try:
            accounts.set_avatar(a, b"resim degil")
            raise AssertionError("resim olmayan dosya kabul edilmemeli")
        except accounts.AccountError:
            pass
        accounts.remove_avatar(a)
        assert accounts.avatar(a) is None
        # Kendi parolanı değiştirme: önce eski parola
        try:
            accounts.change_password(a, "yanlis-parola", "yeni-parola1")
            raise AssertionError("eski parola yanlışken değişmemeli")
        except accounts.AccountError:
            pass
        accounts.change_password(a, "parola123", "yeni-parola1")
        assert accounts.authenticate("kaan", "yeni-parola1") and not accounts.authenticate("kaan", "parola123")
        # Herkese açık notu listeye ekleme; gizli not eklenemez
        doc = library.register(_pdf(["Seçilim baskısı, uygun bireylerin üreme şansını artırır."]), "not.pdf", a)[0]["doc"]
        try:
            library.add_to_library(doc, b)
            raise AssertionError("gizli not eklenmemeli")
        except library.LibraryError:
            pass
        library.publish(doc, a)
        assert doc not in library.mine(b) and library.add_to_library(doc, b) and doc in library.mine(b)
        assert not library.add_to_library(doc, b)  # ikinci kez: değişiklik yok
        # Kaldığın yerden devam: kişi ve tür başına tek satır, üzerine yazılır, silinir
        resume.save(a, "cards", {"queue": ["q1", "q2"], "pos": 1})
        resume.save(a, "cards", {"queue": ["q1", "q2"], "pos": 2})
        assert resume.load(a, "cards")["pos"] == 2 and resume.load(b, "cards") is None
        saved = {"id": "r1", "answers": {"q1": 0}, "started": time.time() - 600, "phase": "solve"}
        resume.save(a, "exam", saved)
        row = resume.load(a, "exam")
        row["updated"] -= 3600  # bir saat önce bırakılmış gibi: o an sınavın 10. dakikasıydı
        row["started"] -= 3600
        back = resume.restore_exam(row)
        assert back["phase"] == "solve" and "updated" not in back
        assert abs((time.time() - back["started"]) - 600) < 5  # beklenen bir saat süreye eklenmez
        resume.clear(a, "exam")
        assert resume.load(a, "exam") is None and appdb.version() == len(appdb.MIGRATIONS) == 2


def test_free_key_avoids_leftovers() -> None:
    """Silinmiş bir belgenin artığı (soru dosyası) varsa o ad yeni belgeye verilmez: eski soruları devralırdı."""
    with tempfile.TemporaryDirectory() as d:
        _fresh(d)
        real_data, real_parsed = config.DATA_DIR, config.PARSED_DIR
        config.DATA_DIR, config.PARSED_DIR = Path(d), Path(d) / "parsed"
        try:
            (Path(d) / "questions").mkdir()
            (Path(d) / "questions" / "artik_tr.jsonl").write_text("{}\n", encoding="utf-8")
            a = accounts.create("kaan", "parola123")["id"]
            doc, status = library.register(_pdf(["Yeni bir not, eski adla."]), "artik.pdf", a)
            assert status == "new" and doc["doc"] != "artik" and doc["doc"].startswith("artik-")
        finally:
            config.DATA_DIR, config.PARSED_DIR = real_data, real_parsed


if __name__ == "__main__":
    t0 = time.time()
    test_passwords()
    test_accounts_and_sessions()
    test_library()
    test_profile_and_resume()
    test_free_key_avoids_leftovers()
    print(f"accounts: tüm testler geçti ({time.time() - t0:.1f} sn)")

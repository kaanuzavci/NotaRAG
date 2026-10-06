"""Ayrıştırıcı regresyon testleri: örnek PDF'lerde bulunan her zor durum burada sabitlenir.

Çalıştırma: python -m tests.test_parser   (internet kullanmaz; data/sample_docs/ gerekir)
Her test, bir hatanın tekrar ortaya çıkmasını önlemek için yazıldı; yorumda hangi hata olduğu yazıyor.
"""

from src import config
from src.ingestion.pdf_parser import parse_pdf

DOCS = config.DATA_DIR / "sample_docs"
_cache: dict[str, dict] = {}


def doc(name: str) -> dict:
    if name not in _cache:
        _cache[name] = parse_pdf(DOCS / name)
    return _cache[name]


def page(name: str, n: int) -> dict:
    return doc(name)["pages"][n - 1]


EN, YZ, EK = "english.pdf", "7.Hafta Sunu Dosyası.pdf", "4_ENERJİ, TARIM, BESLENME.pdf"


def test_language() -> None:
    assert doc(EN)["language"] == "en" and doc(YZ)["language"] == "tr" and doc(EK)["language"] == "tr"


def test_rotated_pages_and_header_footer() -> None:
    # EN sayfaları 90° döndürülmüş; üst bilgi sayfanın %22'sinde, sabit şeritte değil.
    assert "r.k. bhattacharjya/ce/iitg" in doc(EN)["header_footer_patterns"]
    assert all("R.K. Bhattacharjya/CE/IITG" not in p["text"] for p in doc(EN)["pages"])
    assert all("November 2013" not in p["text"] for p in doc(EN)["pages"])
    assert page(EN, 5)["text"].startswith("Genetic Algorithms are the heuristic search")


def test_page_number_rule_keeps_content_numbers() -> None:
    # Eski '±2' kuralı s20 diyagramındaki dört '22' değerini sayfa numarası sanıp siliyordu.
    p = page(EN, 20)
    assert (p["text"] + p["figure_text"]).count("22") >= 4


def test_repeated_slide_titles_are_kept() -> None:
    # Tekrar eden başlık üst bilgi sanılmamalı (en büyük yazı kuralı).
    assert page(EK, 12)["heading"] == "Organik Tarım" and page(EK, 16)["heading"] == "Organik Tarım"
    assert page(YZ, 16)["heading"] == "Proportional Selection ≡ Orantılı Seçim (Rulet Tekerleği)"
    assert page(YZ, 12)["heading"] == "KAPSAMLI BİR GA ÖRNEĞİ"


def test_figure_labels_separated_from_body() -> None:
    # Diyagram etiketleri ('Amaç Fonksiyonu', 'Giriş veya') gövdeye karışmamalı.
    assert page(YZ, 2)["text"].startswith("Optimizasyon, bir problemin çözümünde")
    assert "disiplinlerdir." in page(YZ, 2)["text"]  # paragrafın son satırı gövdede kalmalı


def test_plain_text_slide_exact() -> None:
    t = page(EK, 13)["text"]
    assert "Tutarsız getiriler: Organik tarım ürün rotasyonuna dayandığından" in t
    assert "• Büyük kayıplara karşı savunmasızlık" in t


def test_special_pages_flagged() -> None:
    assert "title_page" in page(EK, 1)["flags"] and "title_page" in page(EN, 1)["flags"]
    assert "toc_like" in page(EK, 2)["flags"]
    assert "toc_like" not in page(EN, 39)["flags"]  # numaralı algoritma adımları içindekiler değil


def test_image_pages_need_vision() -> None:
    for n in (8, 17, 18, 19, 20, 21):
        assert page(EK, n)["quality"] == "needs_vision", n
    assert page(YZ, 11)["quality"] == "needs_vision"


def test_tables_extracted_on_cpu() -> None:
    p33 = page(EN, 33)
    assert p33["quality"] == "ok" and "tables_extracted" in p33["flags"]
    assert "| Population | Set of solutions |" in p33["text"]
    assert "| Gene | Part of the encoding solution |" in p33["text"]
    p22 = page(EN, 22)["text"]
    assert "| 2 | 0.286 | 0 |" in p22 and "Novem" not in p22  # bölünmüş alt bilgi temizlendi
    assert "Chrom # Fitness Chrom # Rank" not in p22           # konteyner sahte tablo atlandı
    assert "| 1 | 100101 | 37 | 0.587 | 0.96 |" in page(EN, 35)["text"]


def test_garbled_formulas_go_to_vision() -> None:
    for name, n in ((YZ, 4), (YZ, 6), (EN, 41), (EN, 43), (EN, 89)):
        assert "noisy_text" in page(name, n)["flags"], (name, n)
    assert not any("noisy_text" in p["flags"] for p in doc(EK)["pages"])  # düz metinde yanlış alarm yok


def test_turkish_characters_intact() -> None:
    assert "Yılda 1.3 milyar ton yemek çöpe gidiyor" == page(EK, 21)["heading"]
    assert "Öküzden traktöre" == page(EK, 10)["heading"]


def test_scanned_pages_need_vision() -> None:
    # Taranmış PDF (sayfa = tek tam sayfa görüntü, metin yok) 'ok' sanılıp bölümleyicide 'boş' diye atlanıyordu:
    # 192 sayfalık taranmış ders kitabından hiç soru çıkmazdı. Tarayıcının sayfa başına yer imleri
    # ('…_Sayfa_001') de başlık sanılıyordu. Dil bozuk/boş katmandan değil, sonradan belirlenmeli (2026-10-06).
    import tempfile
    from pathlib import Path

    import pymupdf
    src = pymupdf.open(DOCS / YZ)
    out = pymupdf.open()
    for i in range(4):
        pix = src[i + 2].get_pixmap(dpi=60)
        pg = out.new_page(width=src[i + 2].rect.width, height=src[i + 2].rect.height)
        pg.insert_image(pg.rect, pixmap=pix)
    out.set_toc([[1, f"Ders Notu 22.07.2015_Sayfa_{i + 1:03d}", i + 1] for i in range(4)])
    path = Path(tempfile.gettempdir()) / "nr_taranmis_test.pdf"
    out.save(path)
    d = parse_pdf(path)
    assert all(p["quality"] == "needs_vision" and "scanned" in p["flags"] for p in d["pages"]), \
        [(p["quality"], p["flags"]) for p in d["pages"]]
    assert all(p["heading"] is None for p in d["pages"])  # yer imi başlık değil
    assert d["language"] == "unknown" and d["title"] == "nr_taranmis_test"


TESTS = [v for k, v in dict(globals()).items() if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ✗ {t.__name__} {e or ''}")
    print(f"{len(TESTS) - failed}/{len(TESTS)} test geçti")
    raise SystemExit(1 if failed else 0)

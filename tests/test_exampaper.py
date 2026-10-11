"""Sınav kâğıdı PDF'i (src/exampaper.py): her şablonda sayfa üretir, soru sayısı ve cevap anahtarı doğru. API çağırmaz.
Çalıştırma: python -m tests.test_exampaper"""

import pymupdf

from src import exampaper as X
from src import request as R


def main() -> None:
    items = [it for it in R.all_items().values() if R.usable(it) and it["q"]["type"] in
             ("multiple_choice", "true_false", "short_answer")][:26]
    assert len(items) >= 10, "test için yeterli soru yok"
    meta = X.Meta(title="Deneme ığşçöü", course="Ders", date="01.01.2027", minutes=60)
    for key, t in X.TEMPLATES.items():
        pdf, info = X.build_exam(items, key, meta)
        with pymupdf.open(stream=pdf) as d:
            text = "".join(p.get_text() for p in d)
            assert d.page_count == info["pages"] >= 1, key
            assert f"{len(items)}." in text and "Deneme" in text, key
            assert info["font"] >= t.font_min, key
        print(f"{key}: {info['pages']} sayfa, {info['font']} punto")
    # A / B kitapçığı: tür yuvaları aynı (tek optik form), doğru şıkkın metni korunur, sıra gerçekten değişir
    A = X.prepare(items, meta)
    B = X.booklet_b(A)
    assert [X._kind(i) for i in A] == [X._kind(i) for i in B] and sorted(i["id"] for i in A) == sorted(i["id"] for i in B)
    assert any(a["id"] != b["id"] for a, b in zip(A, B))
    bq = {it["id"]: it["q"] for it in B}
    for it in A:
        q = it["q"]
        if q["type"] == "multiple_choice":
            assert bq[it["id"]]["options"][bq[it["id"]]["answer_index"]] == q["options"][q["answer_index"]]
    pdf_b, _ = X.build_exam(B, "a4_2", meta, booklet="B")
    with pymupdf.open(stream=pdf_b) as d:
        assert "B kitapçığı" in d[0].get_text()
    # Optik form ve belirtke tablosu
    with pymupdf.open(stream=X.build_sheet(A, meta, ("A", "B"))) as d:
        text = d[0].get_text()
        assert d.page_count == 1 and "Optik cevap" in text and f"{len(A)}." in text and "Kitapçık türü" in text
    bp = X.blueprint(A)
    assert bp["total"]["n"] == len(A) == sum(r["n"] for r in bp["rows"])
    assert abs(sum(r["points"] for r in bp["rows"]) - 100) < 1
    with pymupdf.open(stream=X.build_key({"A": A, "B": B}, meta)) as d:
        text = "".join(p.get_text() for p in d)
        assert "A kitapçığı" in text and "B kitapçığı" in text and "Belirtke tablosu" in text
    key_pdf = X.build_key(items, meta)
    with pymupdf.open(stream=key_pdf) as d:
        assert "Cevap anahtarı" in d[0].get_text()
    print("tamam")


if __name__ == "__main__":
    main()

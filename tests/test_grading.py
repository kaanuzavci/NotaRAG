"""Kısa cevap puanlaması testleri (internetsiz). Çalıştırma: python -m tests.test_grading"""

from src.grading import grade_short

# (öğrencinin cevabı, beklenen cevap, kodun hesapladığı değer ya da None, doğru mu?)
CASES = [
    # Kullanıcının bulduğu iki hata (2026-10-05)
    ("2", "(n choose 2) * 2", None, False),            # eski yöntem bunu DOĞRU sayıyordu (kelime kümesi içerme)
    ("3", "9! / (3! ⋅ 2!)", None, False),
    ("30240", "9! / (3! ⋅ 2!)", None, True),            # eski yöntem bunu YANLIŞ sayardı (formül ↔ sayı)
    # Matematiksel denklik: değer karşılaştırması
    ("9!/(3!·2!)", "9! / (3! ⋅ 2!)", None, True),
    ("362880/12", "9! / (3! ⋅ 2!)", None, True),
    ("30240 farklı kelime", "9! / (3! ⋅ 2!)", None, True),
    ("n(n-1)", "(n choose 2) * 2", None, True),
    ("n²-n", "(n choose 2) * 2", None, True),
    ("2C(n,2)", "(n choose 2) * 2", None, True),
    ("2^n", "2^n", None, True), ("2ⁿ", "2^n", None, True), ("n^2", "2^n", None, False),
    ("300", "300", "300", True), ("300 tane", "300", "300", True), ("301", "300", "300", False),
    ("2,5", "5/2", "5/2", True),
    # Metin cevaplar: eşitlik ya da uzunluğu da yakın eşleşme; bir parçası olmak yetmez
    ("Tanımsız", "Tanımsız", None, True), ("tanımsızdır", "Tanımsız", None, True),
    ("Parazitoid", "Parazitoid", None, True), ("Gen", "Gen", None, True), ("Kromozom", "Gen", None, False),
    ("böcek", "Faydalı böcekler (parazitoid)", None, False),
    ("Uygunluk fonksiyonu", "Uygunluk (fitness) fonksiyonu", None, True),
    ("dirençli", "direnç", None, False), ("", "Gen", None, False),
    # Güvenlik: öğrencinin girdisi hesaplanmadan önce sınırlanır (sistemi kilitlememeli, kod çalıştırmamalı)
    ("9^9^9", "9! / (3! ⋅ 2!)", None, False), ("170!", "9!", None, False),
    ("__import__('os')", "9!", None, False), ("(2**10)**(2**10)", "9!", None, False),
]


def test_all() -> None:
    bad = [(a, e, w) for a, e, c, w in CASES if grade_short(a, e, c) != w]
    assert not bad, bad


if __name__ == "__main__":
    test_all()
    print(f"test_grading: {len(CASES)} durumun hepsi doğru")

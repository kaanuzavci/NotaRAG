"""Çalıştırma: python -m tests.test_textnorm"""

from src.textnorm import (LINEBREAK_HYPHEN, clean_line, detect_language, join_lines, normalize_for_match as n,
                          pretty_math, resolve_hyphens, to_script, tr_lower)


def test_all() -> None:
    assert tr_lower("IŞIK İzmir") == "ışık izmir"
    assert n("İSTANBUL") == n("Istanbul")
    assert n("bilgisa-\nyar ağı") == n("bilgisayar ağı")          # satır sonu tirelemesi
    assert n("meta- sezgisel") == n("meta-sezgisel")              # bileşik kelime
    assert n("“Select The Best”") == n('"select the best"')        # tırnak türleri, büyük/küçük
    assert clean_line("Hem ülkemizde") == "• Hem ülkemizde"   # Wingdings madde işareti
    assert clean_line("\x01 D. E. Goldberg") == "• D. E. Goldberg"  # kontrol karakteri madde işareti
    assert clean_line("ﬁnal 𝑓𝑥") == "final fx"                      # bitişik harf, matematik italik
    assert join_lines(["Başlık", "• madde 1", "devamı"]) == "Başlık\n• madde 1 devamı"
    assert detect_language("Bu bir deneme metnidir ve Türkçe yazılmıştır, için") == "tr"
    assert detect_language("This is a test of the language detector and it is English") == "en"

    # Satır sonu tiresi: join_lines işaretler, resolve_hyphens belgenin geri kalanına bakarak çözer
    # (TYT'de 'bü-tün' alıntısı ekranda tireli görünüyordu; 'meta-sezgisel' ise gerçek bileşik kelime)
    joined = join_lines(["ise bü-", "tün çarpanlar"])
    assert joined == f"ise bü{LINEBREAK_HYPHEN}tün çarpanlar"
    assert resolve_hyphens([joined, "bütün sayılar"])[0] == "ise bütün çarpanlar"
    assert resolve_hyphens([join_lines(["optimizasyon meta-", "sezgisel"]), "meta-sezgisel"])[0] == "optimizasyon meta-sezgisel"
    assert resolve_hyphens([join_lines(["real-", "coded GA"])], "en")[0] == "real-coded GA"  # bilinmiyorsa EN: tire kalır
    assert n(f"bü{LINEBREAK_HYPHEN}tün") == n("bütün")

    # Üst/alt simgeler: temizlikte korunur (NFKC 'x²'yi 'x2' yapıyordu), karşılaştırmada düzleşir
    assert to_script("n") == "ⁿ" and to_script("12") == "¹²" and to_script("1", sup=False) == "₁"
    assert to_script("w") == "^w" and to_script("ab+c") == "^(ab+c)"
    assert clean_line("x² + 2ⁿ ﬁ") == "x² + 2ⁿ fi"
    assert n("alt küme sayısı 2ⁿ") == n("alt küme sayısı 2n")

    # Ekranda gösterim: görsel okumanın LaTeX'i ve ^ gösterimi okunur Unicode
    assert pretty_math(r"A maddesinin ağırlık yüzdesi = $\frac{100 \cdot a}{a + b}$") == \
        "A maddesinin ağırlık yüzdesi = (100 · a)/(a + b)"
    assert pretty_math("alt küme sayısı 2^n") == "alt küme sayısı 2ⁿ"
    assert pretty_math("2^10 = 1024") == "2¹⁰ = 1024"
    assert pretty_math(r"x_1 + x_{n} \leq 5") == "x₁ + xₙ ≤ 5"
    assert pretty_math("Düz metin, değişmez.") == "Düz metin, değişmez."


if __name__ == "__main__":
    test_all()
    print("textnorm: tüm testler geçti")

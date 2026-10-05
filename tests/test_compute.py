"""Hesap sorusu kontrolü testleri (internetsiz, SymPy). Çalıştırma: python -m tests.test_compute"""

from fractions import Fraction

from src.generation.compute import judge, numbers_in, reasons, validate
from src.generation.generate import _shuffle


def mcq(compute, options, values, key=0):
    return {"type": "multiple_choice", "question": "q", "compute": compute, "options": options,
            "option_values": values, "answer_index": key, "answer": options[key]}


def verdict(q):
    res = judge(q)
    return reasons(res), res


def test_all() -> None:
    # Güvenlik: modelin yazdığı ifade kod olarak çalıştırılmadan önce AST beyaz listesinden geçer
    for bad in ("__import__('os').system('dir')", "x.__class__", "open('a.txt')", "'metin'", "lambda: 1",
                "2**100000", "solve(x, dict=True)", "[c for c in (1, 2)]", "getattr(x, 'a')", "x if 1 else 2"):
        assert validate(bad) is not None, bad
    for ok in ("solve(Eq(2*x + 3, 11), x)[0]", "binomial(5, 2)", "ff(5, 2)", "Rational(3, 4) * 20", "sqrt(2)/2",
               "x1 + x2"):
        assert validate(ok) is None, ok

    assert validate("solve([Eq(3*x + y, 11), Eq(x - y, 1)], (x, y))[x]") is None
    assert validate("solve(x, x)[open]") is not None
    # Denklem sistemi: çözüm sözlüğünden x
    (rej, _), res = verdict(mcq("solve([Eq(3*x + y, 11), Eq(x - y, 1)], (x, y))[x]", ["3", "2", "4", "5"],
                                ["3", "2", "4", "5"]))
    assert rej == [] and res["value"] == "3", (rej, res)

    # Doğru soru: hiçbir red yok
    (rej, flags), res = verdict(mcq("solve(Eq(2*x + 3, 11), x)[0]", ["4", "5", "3", "7"], ["4", "5", "3", "7"]))
    assert res["ok"] and res["key_ok"] and rej == [] and flags == [], (rej, res)
    # Permütasyon / kombinasyon
    (rej, _), _ = verdict(mcq("ff(5, 2)", ["20", "10", "25", "60"], ["20", "10", "25", "60"]))
    assert rej == []
    (rej, _), _ = verdict(mcq("binomial(6, 2)", ["30", "15", "12", "36"], ["30", "15", "12", "36"], key=1))
    assert rej == []

    # Yanlış anahtar → yakalanmalı
    (rej, _), _ = verdict(mcq("solve(Eq(2*x + 3, 11), x)[0]", ["4", "5", "3", "7"], ["4", "5", "3", "7"], key=1))
    assert "compute_mismatch" in rej
    # İki doğru şık (8/2 = 4)
    (rej, _), _ = verdict(mcq("2 + 2", ["4", "8/2", "3", "7"], ["4", "8/2", "3", "7"]))
    assert "compute_two_correct" in rej
    # Şık metni değeriyle çelişiyor: öğrenci '12' görür, kod 4 sanır
    (rej, _), _ = verdict(mcq("2 + 2", ["12", "5", "3", "7"], ["4", "5", "3", "7"]))
    assert "compute_text_mismatch" in rej
    # Çeldiricinin metni doğru sonucu gösteriyor ama değeri farklı yazılmış
    (rej, _), _ = verdict(mcq("2 + 2", ["4", "x = 4", "3", "7"], ["4", "5", "3", "7"]))
    assert "compute_two_correct" in rej and "compute_text_mismatch" in rej

    # Yüzde ve Türkçe ondalık virgül
    (rej, _), _ = verdict(mcq("Rational(1, 4)", ["%25", "%40", "%50", "%75"],
                              ["Rational(1,4)", "Rational(2,5)", "Rational(1,2)", "Rational(3,4)"]))
    assert rej == [], rej
    (rej, _), _ = verdict(mcq("Rational(5, 2)", ["2,5", "3,5", "1,5", "4"], ["5/2", "7/2", "3/2", "4"]))
    assert rej == [], rej
    assert Fraction(5, 2) in numbers_in("x = 2,5 cm") and Fraction(3, 4) in numbers_in("3/4 oranında")
    assert Fraction(-3) in numbers_in("x = –3")  # tipografik eksi

    # İrrasyonel sonuç: metin denetlenemez → yalnızca uyarı
    (rej, flags), _ = verdict(mcq("sqrt(8)", ["2√2", "4", "√6", "3√2"], ["2*sqrt(2)", "4", "sqrt(6)", "3*sqrt(2)"]))
    assert "compute_mismatch" not in rej and "compute_two_correct" not in rej

    # Kısa cevap
    sa = {"type": "short_answer", "question": "q", "compute": "factorial(4)", "answer": "24 farklı şekilde",
          "answer_value": "24"}
    (rej, _), _ = verdict(sa)
    assert rej == [], rej
    (rej, _), _ = verdict({**sa, "answer_value": "12", "answer": "12"})
    assert "compute_mismatch" in rej

    # Hesaplanamayan ifade
    (rej, _), res = verdict(mcq("1/0 + y", ["1", "2", "3", "4"], ["1", "2", "3", "4"]))
    assert rej == ["compute_error"] or "compute_mismatch" in rej, res

    # Şık karıştırma değerleri de taşımalı (yoksa anahtar başka şıkkın değerine bakar)
    q = mcq("2 + 2", ["4", "5", "3", "7"], ["4", "5", "3", "7"])
    for seed in ("a", "b", "c", "d"):
        s = _shuffle(q, seed)
        assert s["options"] == s["option_values"] and s["options"][s["answer_index"]] == "4"
        (rej, _), _ = verdict(s)
        assert rej == [], (seed, rej)


if __name__ == "__main__":
    test_all()
    print("test_compute: tamam")

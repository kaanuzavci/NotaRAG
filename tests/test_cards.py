"""Bilgi kartı (Leitner) testleri (internetsiz, gerçek kayda dokunmaz). Çalıştırma: python -m tests.test_cards"""

import tempfile
from pathlib import Path

from src.cards import card_ok, history, is_due, next_gap, pick, record, step, summary

DAY = 86400


def test_all() -> None:
    s = step(None, "good", 100)
    assert s["box"] == 2 and s["seen"] == 1 and s["last"] == 100
    s = step(step(step(step(s, "good", 0), "good", 0), "good", 0), "good", 0)
    assert s["box"] == 5  # tavan
    assert step(s, "bad", 5)["box"] == 1  # bilemedim → başa
    assert step(s, "skip", 999) == s  # atla → değişmez (zaman da)
    # Aralık: 2. kutu 1 gün sonra gelir
    s2 = step(None, "good", 0)
    assert not is_due(s2, DAY - 1) and is_due(s2, DAY)
    assert is_due(None, 0) and is_due(step(None, "bad", 0), 0)  # yeni ve 1. kutu hemen
    assert next_gap(None, "good") == 1 and next_gap(s2, "good") == 3 and next_gap(s2, "bad") == 0
    # Deste: önce zamanı gelen tekrarlar (düşük kutu önce), sonra yeniler; zamanı gelmeyen dışarıda
    items = [{"id": x} for x in "abcd"]
    hist = {"a": step(None, "bad", 0), "b": {**step(step(None, "good", 0), "good", 0), "last": 0},
            "c": step(None, "good", 10 * DAY)}
    order = pick(items, hist, 10, now=10 * DAY + 5, seed=1)
    assert order[:2] == ["a", "b"] and order[2] == "d" and "c" not in order
    assert len(pick(items, hist, 10, now=0, only_due=False)) == 4
    assert summary(items, hist, 10 * DAY + 5) == {"total": 4, "new": 1, "due": 2, "mastered": 0}
    # Kart = soru → cevap: şıklara dayanan kökler ve doğru/yanlış karta dönüşmez (kullanıcı: "kartta şık olmaz")
    mc = lambda s: {"type": "multiple_choice", "question": s}
    assert card_ok({"type": "short_answer", "question": "C(5,2) kaçtır?"})
    assert card_ok(mc("ALU'nun temel görevi nedir?")) and card_ok(mc("Verileri taşıyan işlev hangisidir?"))
    assert card_ok(mc("Karışan yaklaşık oran yüzde kaçtır?"))  # 'yaklaşık' içindeki 'şık' şık sayılmaz
    assert not card_ok(mc("Aşağıdakilerden hangisi bir seçim yöntemidir?"))
    assert not card_ok(mc("Hangisi kodlama mekanizmalarından biri değildir?"))
    assert not card_ok({"type": "true_false", "question": "Mutasyon çeşitliliği artırır."})
    # Kayıt baştan oynatılınca aynı durum
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "cards.jsonl"
        for r in ("good", "skip", "good", "bad", "good"):
            record("q1", r, p)
        h = history(p)
        assert h["q1"]["box"] == 2 and h["q1"]["seen"] == 4 and h["q1"]["good"] == 3


if __name__ == "__main__":
    test_all()
    print("cards: tüm testler geçti")

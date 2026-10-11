"""Bilgi kartı (FSRS-5 aralıklı tekrar) testleri (internetsiz, gerçek kayda dokunmaz). Çalıştırma: python -m tests.test_cards"""

import tempfile
from pathlib import Path

from src.cards import card_ok, first_seen, gap_days, history, is_due, next_gap, pick, record, step, summary

DAY = 86400


def test_all() -> None:
    s = step(None, "good", 100)
    assert s["seen"] == 1 and s["last"] == 100 and gap_days(s) == 3 and s["box"] == 3  # ilk Bildim: 3 gün
    # Bildikçe aralık büyür (FSRS-5 varsayılanlarıyla 3 → 11 → 35 gün), kararlılık zamanında tekrarla artar
    t, gaps = 100, []
    for _ in range(3):
        t += gap_days(s) * DAY
        s = step(s, "good", t)
        gaps.append(gap_days(s))
    assert gaps == [11, 35, 101] and s["box"] == 5
    bad = step(s, "bad", t + 101 * DAY)
    assert bad["lapsed"] and gap_days(bad) == 0 and bad["box"] == 1 and bad["s"] < s["s"]  # bilemedim → bugün yine
    assert bad["d"] > s["d"]  # bilinmeyen kart zorlaşır
    assert step(s, "skip", 999) == s  # atla → değişmez (zaman da)
    # Geç tekrar edilip yine bilinen kart, zamanında tekrar edilenden daha çok büyür (unutmaya yakındı)
    s2 = step(None, "good", 0)
    assert step(s2, "good", 10 * DAY)["s"] > step(s2, "good", 3 * DAY)["s"]
    assert not is_due(s2, 3 * DAY - 1) and is_due(s2, 3 * DAY)
    assert is_due(None, 0) and is_due(step(None, "bad", 0), 0)  # yeni ve bilinemeyen kart hemen
    assert next_gap(None, "good", 0) == 3 and next_gap(s2, "bad", 3 * DAY) == 0
    # Deste: önce zamanı gelen tekrarlar (unutulmaya en yakın önce), sonra yeniler; zamanı gelmeyen dışarıda
    items = [{"id": x} for x in "abcde"]
    hist = {"a": step(None, "bad", 0),                      # bilinemedi: hatırlama olasılığı 0 sayılır
            "b": step(None, "good", 0),                     # 3 günlük kart, 10 gün geçti
            "e": step(step(None, "good", 0), "good", 3 * DAY),  # 11 günlük kart, 7 gün geçti: henüz değil
            "c": step(None, "good", 10 * DAY)}              # yeni değerlendirildi
    order = pick(items, hist, 10, now=10 * DAY + 5, seed=1)
    assert order == ["a", "b", "d"]
    assert len(pick(items, hist, 10, now=0, only_due=False)) == 5
    assert summary(items, hist, 10 * DAY + 5) == {"total": 5, "new": 1, "due": 2, "mastered": 0}
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
        assert h["q1"]["seen"] == 4 and h["q1"]["good"] == 3 and h["q1"]["bad"] == 1 and not h["q1"]["lapsed"]


def test_per_user() -> None:
    """Kartlar kişiye özel: aynı kural, herkesin kendi değerlendirmeleri. Kişi alanı olmayan eski satırlar ilk hesabın."""
    from src import accounts, appdb
    with tempfile.TemporaryDirectory() as d:
        appdb.PATH = Path(d) / "app.sqlite"
        p = Path(d) / "cards.jsonl"
        record("q1", "good", p)  # girişten önceki dönem (kişi alanı yok)
        kaan = accounts.create("kaan", "parola123")["id"]  # ilk hesap: eski satırların sahibi
        demo = accounts.create("demo", "parola123")["id"]
        record("q1", "good", p, user=kaan)
        record("q1", "bad", p, user=demo)
        record("q2", "skip", p, user=demo)
        assert history(p, user=kaan)["q1"]["good"] == 2  # eski + yeni: iki kez bildi
        assert history(p, user=demo)["q1"]["box"] == 1 and "q1" not in history(p, user="baskasi")
        assert history(p)["q1"]["seen"] == 3  # kişi verilmezse bütün satırlar
        seen = first_seen(p)
        assert set(seen) == {(kaan, "q1"), (demo, "q1")}  # atla sayılmaz: cevap görülmemiş olabilir


if __name__ == "__main__":
    test_all()
    test_per_user()
    print("cards: tüm testler geçti")

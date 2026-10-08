"""Beyin analizi (src/mastery.py) testleri: LLM yok, gerçek kayda dokunmaz. Çalıştırma: python -m tests.test_mastery"""

import time

from src import mastery as M

DAY = 86400


def test_topic_and_states() -> None:
    topics = [{"title": "Seçilim", "pages": [3, 4]}, {"title": "Çaprazlama", "pages": [5]}]
    assert M.topic_of(4, topics) == "Seçilim" and M.topic_of(5, topics) == "Çaprazlama" and M.topic_of(9, topics) == "Diğer"
    # En son kanıt kazanır: sınavda yanlış, sonra kartta bildi → biliyor; kartta 4. kutu → uzun süreli
    attempts = [{"id": "a", "correct": False, "t": 100}, {"id": "b", "correct": True, "t": 100},
                {"id": "c", "correct": True, "t": 500}]
    cards = {"a": {"box": 2, "last": 200, "seen": 1}, "c": {"box": 1, "last": 300, "seen": 2},
             "d": {"box": 5, "last": 50, "seen": 4}, "e": {"box": 1, "last": 0, "seen": 0}}
    s = M.question_states(attempts, cards)
    assert s["a"]["state"] == "known" and s["b"]["state"] == "known"
    assert s["c"]["state"] == "known"  # kart (t=300) sınavdan (t=500) eski: son kanıt sınav
    assert s["d"]["state"] == "strong" and "e" not in s  # hiç değerlendirilmemiş kart sayılmaz


def test_topic_status() -> None:
    assert M.topic_status(5, 0, 0) == "başlanmadı"
    assert M.topic_status(5, 1, 0) == "çalışılıyor"  # tek yanlış: zayıf demek için az
    assert M.topic_status(5, 3, 1) == "zayıf"
    assert M.topic_status(10, 4, 4) == "öğrenildi" and M.topic_status(10, 3, 3) == "çalışılıyor"  # en az 4 soru
    assert M.topic_status(2, 2, 2) == "öğrenildi"  # konuda 2 soru varsa ikisi yeter


def test_analyze_memory_activity() -> None:
    items = [{"id": f"q{i}", "doc": "ga", "check": {"evidence_page": p}} for i, p in enumerate([3, 3, 4, 5, 9])]
    maps = {"ga": [{"title": "Seçilim", "pages": [3, 4]}, {"title": "Çaprazlama", "pages": [5]}]}
    states = {"q0": {"state": "weak", "t": 1}, "q1": {"state": "weak", "t": 1}, "q2": {"state": "known", "t": 1}}
    r = M.analyze(items, maps, states)
    doc = r["docs"][0]
    assert [t["title"] for t in doc["topics"]] == ["Seçilim", "Çaprazlama", "Diğer"]  # haritadaki sıra
    sec = doc["topics"][0]
    assert (sec["n"], sec["seen"], sec["known"], sec["status"]) == (3, 3, 1, "zayıf")
    assert doc["topics"][1]["status"] == "başlanmadı" and r["weak"][0]["title"] == "Seçilim"
    assert (doc["n"], doc["seen"], doc["known"]) == (5, 3, 1)
    mem = M.memory({"a": {"box": 1, "seen": 1}, "b": {"box": 3, "seen": 2}, "c": {"box": 5, "seen": 5},
                    "d": {"box": 4, "seen": 4}, "x": {"box": 5, "seen": 5}}, alive={"a", "b", "c", "d"})
    assert mem == {"kısa": 1, "pekişiyor": 1, "uzun": 2}  # havuzdan çıkmış soru (x) sayılmaz
    now = time.mktime((2026, 10, 8, 15, 0, 0, 0, 0, -1))
    act = M.activity([{"t": now - 60}, {"t": now - 2 * DAY}], [{"t": now - 120, "result": "good"},
                                                                {"t": now - 30, "result": "skip"}], now=now)
    assert len(act) == 14 and act[-1] == 2 and act[-3] == 1 and sum(act) == 3  # "Atla" çalışma sayılmaz


if __name__ == "__main__":
    test_topic_and_states()
    test_topic_status()
    test_analyze_memory_activity()
    print("mastery: tüm testler geçti")

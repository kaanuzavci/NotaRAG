"""Bilgi kartları: havuzdaki DOĞRULANMIŞ sorulardan deste + aralıklı tekrar (Leitner kutuları).

LLM çağrısı yok: soru → ön yüz; cevap, kanıt alıntısı ve (varsa) çözüm → arka yüz. NotebookLM'deki gibi şık yok:
yalnızca şıksız da anlaşılan sorular kart olur (card_ok) — kısa cevap ve kökü kendi başına soru olan çoktan seçmeli
(cevabı doğru şıkkın metni). Doğru/yanlış ifadeleri ve "aşağıdakilerden hangisi", olumsuz kök gibi şıklara dayanan
sorular sınavda kalır. Kartın sonucu öğrencinin kendi
değerlendirmesidir (Bildim / Bilemedim / Atla); sınavın madde istatistiğine (attempts.jsonl) karışmaz, ayrı kaydedilir:
data/review/cards.jsonl (soru kimliğine bağlı, yalnızca eklenir — kutular kayıt baştan oynatılarak bulunur).

Leitner: her kart bir kutudadır (1-5). Bildim → bir üst kutu, Bilemedim → 1. kutu, Atla → değişmez.
Kutu yükseldikçe kart seyrekleşir: 1. kutu her oturumda, sonra 1, 3, 7, 14 gün.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from src import config

LOG = config.DATA_DIR / "review" / "cards.jsonl"
INTERVAL_DAYS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}
RESULTS = ("good", "bad", "skip")
# Kökü şıklara dayanan soru: "Aşağıdakilerden hangisi…", olumsuz kök, şık/seçenek anılıyor ("yaklaşık" değil: \b)
_OPTION_BOUND = re.compile(r"aşağıdaki|\bseçenek|\bşıklar|\bşık\b|değildir|yanlıştır|which of|the following", re.I)


def card_ok(q: dict) -> bool:
    """Soru şıksız bir karta dönüşebilir mi?"""
    if q.get("type") == "short_answer":
        return True
    if q.get("type") == "multiple_choice":
        return not _OPTION_BOUND.search(str(q.get("question", "")))
    return False  # doğru / yanlış: ifadenin kendisi bir seçim


def step(state: dict | None, result: str, t: float) -> dict:
    """Bir değerlendirmeden sonra kartın yeni durumu (saf fonksiyon)."""
    s = dict(state or {"box": 1, "last": 0.0, "seen": 0, "good": 0, "bad": 0})
    if result == "skip":
        return s
    s["seen"] += 1
    s["last"] = t
    if result == "good":
        s["box"] = min(5, s["box"] + 1)
        s["good"] += 1
    else:
        s["box"] = 1
        s["bad"] += 1
    return s


def history(path: Path | None = None) -> dict[str, dict]:
    """Kart kimliği → {box, last, seen, good, bad}."""
    out: dict[str, dict] = {}
    path = path or LOG
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["id"]] = step(out.get(e["id"]), e["result"], e["t"])
    return out


def record(qid: str, result: str, path: Path | None = None) -> None:
    assert result in RESULTS
    path = path or LOG  # çağrı anında okunur (testler geçici dosyaya yönlendirebilsin)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": qid, "result": result, "t": time.time()}) + "\n")


def is_due(state: dict | None, now: float) -> bool:
    """Hiç görülmemiş kart ya da kutusunun aralığı dolmuş kart."""
    return state is None or now - state["last"] >= INTERVAL_DAYS[state["box"]] * 86400


def next_gap(state: dict | None, result: str) -> int:
    """Bu sonuçtan sonra kart kaç gün sonra yeniden gelir (arayüzdeki ipucu için)."""
    return INTERVAL_DAYS[step(state, result, 0)["box"]]


def pick(items: list[dict], hist: dict[str, dict], n: int, now: float, only_due: bool = True,
         seed: int | None = None) -> list[str]:
    """Deste: önce zamanı gelmiş tekrar kartları (düşük kutu önce), sonra hiç görülmemişler; eşitlerde karışık."""
    pool = [it for it in items if not only_due or is_due(hist.get(it["id"]), now)]
    random.Random(seed).shuffle(pool)
    pool.sort(key=lambda it: (it["id"] not in hist, hist.get(it["id"], {}).get("box", 0)))
    return [it["id"] for it in pool[:n]]


def pool(docs: list[str]) -> list[dict]:
    """Seçili belgelerdeki kart olabilen sorular (sınavla aynı kural: doğrulanmış, reddedilmemiş, bildirilmemiş)."""
    from src import request as R
    blocked = R.blocked_ids()
    return [it for it in R.all_items().values()
            if R.usable(it) and it["id"] not in blocked and it["doc"] in docs and card_ok(it["q"])]


def summary(items: list[dict], hist: dict[str, dict], now: float) -> dict:
    seen = [hist[it["id"]] for it in items if it["id"] in hist]
    return {"total": len(items), "new": len(items) - len(seen),
            "due": sum(is_due(s, now) for s in seen), "mastered": sum(s["box"] >= 4 for s in seen)}

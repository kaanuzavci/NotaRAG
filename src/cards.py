"""Bilgi kartları: havuzdaki DOĞRULANMIŞ sorulardan deste + aralıklı tekrar (Leitner kutuları).

LLM çağrısı yok: soru → ön yüz; cevap, kanıt alıntısı ve (varsa) çözüm → arka yüz. NotebookLM'deki gibi şık yok:
yalnızca şıksız da anlaşılan sorular kart olur (card_ok) — kısa cevap ve kökü kendi başına soru olan çoktan seçmeli
(cevabı doğru şıkkın metni). Doğru/yanlış ifadeleri ve "aşağıdakilerden hangisi", olumsuz kök gibi şıklara dayanan
sorular sınavda kalır. Kartın sonucu öğrencinin kendi
değerlendirmesidir (Bildim / Bilemedim / Atla); sınavın madde istatistiğine (attempts.jsonl) karışmaz, ayrı kaydedilir:
data/review/cards.jsonl (soru ve kişi kimliğine bağlı, yalnızca eklenir — kutular kayıt baştan oynatılarak bulunur).
Kutular kişiye özeldir: herkes aynı kuralla, kendi değerlendirmeleriyle ilerler. Kişi alanı olmayan eski satırlar
ilk hesabındır (accounts.legacy_owner).

Leitner: her kart bir kutudadır (1-5). Bildim → bir üst kutu, Bilemedim → 1. kutu, Atla → değişmez.
Kutu yükseldikçe kart seyrekleşir: 1. kutu her oturumda, sonra 1, 3, 7, 14 gün.
"""

from __future__ import annotations

import random
import re
import time
from pathlib import Path

from src import config, jsonl

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


def _mine(rows: list[dict], user: str | None) -> list[dict]:
    """user verilirse yalnızca o kişinin satırları (kişi alanı olmayan eski satırlar ilk hesabın)."""
    if user is None:
        return rows
    from src.accounts import legacy_owner
    legacy = legacy_owner()
    return [e for e in rows if (e.get("user") or legacy) == user]


def history(path: Path | None = None, user: str | None = None) -> dict[str, dict]:
    """Kart kimliği → {box, last, seen, good, bad}. user: kişinin kendi kutuları (None: bütün satırlar)."""
    out: dict[str, dict] = {}
    for e in _mine(jsonl.read(path or LOG), user):
        out[e["id"]] = step(out.get(e["id"]), e["result"], e["t"])
    return out


def first_seen(path: Path | None = None) -> dict[tuple[str | None, str], float]:
    """(kişi, soru) → kartta ilk değerlendirildiği an. Kartta cevabı görülmüş soru, sonra sınavda çıkarsa o deneme
    taze değildir (zorluk ölçümüne girmez: difficulty.fresh_attempts). Atla sayılmaz (cevap görülmemiş olabilir)."""
    from src.accounts import legacy_owner
    legacy, out = legacy_owner(), {}
    for e in jsonl.read(path or LOG):
        if e["result"] != "skip":
            out.setdefault((e.get("user") or legacy, e["id"]), e["t"])
    return out


def record(qid: str, result: str, path: Path | None = None, user: str | None = None) -> None:
    assert result in RESULTS
    rec = {"id": qid, "result": result, "t": time.time()}
    if user:
        rec["user"] = user
    jsonl.append(path or LOG, [rec])  # yol çağrı anında okunur (testler geçici dosyaya yönlendirebilsin)


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

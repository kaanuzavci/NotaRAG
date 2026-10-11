"""Bilgi kartları: havuzdaki DOĞRULANMIŞ sorulardan deste + aralıklı tekrar (FSRS-5).

LLM çağrısı yok: soru → ön yüz; cevap, kanıt alıntısı ve (varsa) çözüm → arka yüz. NotebookLM'deki gibi şık yok:
yalnızca şıksız da anlaşılan sorular kart olur (card_ok) — kısa cevap ve kökü kendi başına soru olan çoktan seçmeli
(cevabı doğru şıkkın metni). Doğru/yanlış ifadeleri ve "aşağıdakilerden hangisi", olumsuz kök gibi şıklara dayanan
sorular sınavda kalır. Kartın sonucu öğrencinin kendi
değerlendirmesidir (Bildim / Bilemedim / Atla); sınavın madde istatistiğine (attempts.jsonl) karışmaz, ayrı kaydedilir:
data/review/cards.jsonl (soru ve kişi kimliğine bağlı, yalnızca eklenir — kutular kayıt baştan oynatılarak bulunur).
Kutular kişiye özeldir: herkes aynı kuralla, kendi değerlendirmeleriyle ilerler. Kişi alanı olmayan eski satırlar
ilk hesabındır (accounts.legacy_owner).

Zamanlama: FSRS-5 (Free Spaced Repetition Scheduler; Ye ve ark. 2022-2024, Anki 23.10'dan beri varsayılan). Her kartın
iki sayısı var: kararlılık S (gün; hatırlama olasılığının %90'a düşmesine kadar geçen süre) ve zorluk D (1-10). Bildim →
S kartın zorluğuna, mevcut kararlılığına ve "unutmaya ne kadar yakındı"ya göre büyür (geç tekrar edilen ama bilinen kart
daha çok büyür); Bilemedim → S küçülür, kart bugün yine gelir, D artar. Atla → değişmez. Sonraki tekrar: hatırlama
olasılığı %90'a indiğinde (I = S gün). Parametreler FSRS-5'in milyonlarca Anki tekrarından öğrenilmiş varsayılanları;
kişiye göre eğitilmedi (bunun için yüzlerce tekrar gerekir). Önceki Leitner kutuları (1-5) geriye uyum için S'den
türetilir ("box": profilin bellek özeti ve ustalık durumu bunu kullanır).
Kayıt biçimi değişmedi (her değerlendirme bir satır): geçmiş baştan oynatılınca eski kayıtlar da FSRS'le yeniden hesaplanır.
"""

from __future__ import annotations

import math
import random
import re
import time
from pathlib import Path

from src import config, jsonl

LOG = config.DATA_DIR / "review" / "cards.jsonl"
RETENTION = 0.9      # hedef hatırlama olasılığı (FSRS varsayılanı)
MAX_DAYS = 365
# FSRS-5 varsayılan parametreleri (w0-w18). w0-w3: ilk değerlendirmede S (Tekrar / Zor / İyi / Kolay)
W = (0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11,
     0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621)
DECAY, FACTOR = -0.5, 19 / 81  # R(t, S) = (1 + FACTOR·t/S)^DECAY → R(S, S) = 0,9
GRADE = {"bad": 1, "good": 3}  # Bilemedim = Tekrar, Bildim = İyi (FSRS'in Zor / Kolay notları kullanılmıyor)
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


def _retrievability(elapsed_days: float, stability: float) -> float:
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def _d0(g: int) -> float:
    return W[4] - math.exp(W[5] * (g - 1)) + 1


def _clamp_d(d: float) -> float:
    return min(10.0, max(1.0, d))


def interval_days(s: float) -> int:
    """Hatırlama olasılığı RETENTION'a inene kadar geçen gün (RETENTION = 0,9'da I = S)."""
    return int(min(MAX_DAYS, max(1, round(s / FACTOR * (RETENTION ** (1 / DECAY) - 1)))))


def _box(state: dict) -> int:
    """Geriye uyum: eski Leitner kutusu (1-5) kararlılıktan. Son değerlendirme Bilemedim ise 1."""
    if state["lapsed"]:
        return 1
    return 1 + sum(state["s"] >= x for x in (1, 3, 7, 21))


_EMPTY = {"s": 0.0, "d": 0.0, "last": 0.0, "seen": 0, "good": 0, "bad": 0, "lapsed": False, "box": 1}


def step(state: dict | None, result: str, t: float) -> dict:
    """Bir değerlendirmeden sonra kartın yeni durumu (saf fonksiyon, FSRS-5)."""
    if result == "skip":
        return dict(state or _EMPTY)
    g = GRADE[result]
    if not state or not state.get("seen"):  # ilk değerlendirme
        st, s, d = dict(_EMPTY), W[g - 1], _clamp_d(_d0(g))
    else:
        st, s, d = dict(state), state["s"], state["d"]
        elapsed = max(0.0, (t - st["last"]) / 86400)
        if elapsed < 1:  # aynı gün yeniden (kısa vadeli): FSRS-5'in gün içi formülü
            s = s * math.exp(W[17] * (g - 3 + W[18]))
        else:
            r = _retrievability(elapsed, s)
            if g == 1:
                s = min(s, W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r)))
            else:
                s = s * (math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) + 1)
        delta = -W[6] * (g - 3)
        d = _clamp_d(W[7] * _d0(4) + (1 - W[7]) * (d + delta * (10 - d) / 9))  # zorluk: değişim + ortalamaya dönüş
    st.update(s=max(0.01, s), d=d, last=t, seen=st["seen"] + 1, lapsed=g == 1)
    st["good" if g > 1 else "bad"] += 1
    st["box"] = _box(st)
    return st


def _mine(rows: list[dict], user: str | None) -> list[dict]:
    """user verilirse yalnızca o kişinin satırları (kişi alanı olmayan eski satırlar ilk hesabın)."""
    if user is None:
        return rows
    from src.accounts import legacy_owner
    legacy = legacy_owner()
    return [e for e in rows if (e.get("user") or legacy) == user]


def history(path: Path | None = None, user: str | None = None) -> dict[str, dict]:
    """Kart kimliği → {s, d, box, last, seen, good, bad, lapsed}. user: kişinin kendi kutuları (None: bütün satırlar)."""
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


def gap_days(state: dict) -> int:
    """Değerlendirilmiş kartın bir sonraki tekrarına kaç gün var (Bilemedim: 0 → bugün yine)."""
    return 0 if state["lapsed"] else interval_days(state["s"])


def is_due(state: dict | None, now: float) -> bool:
    """Hiç görülmemiş kart ya da tekrar zamanı gelmiş kart."""
    return state is None or not state.get("seen") or now - state["last"] >= gap_days(state) * 86400


def next_gap(state: dict | None, result: str, now: float | None = None) -> int:
    """Bu sonuçtan sonra kart kaç gün sonra yeniden gelir (arayüzdeki ipucu için)."""
    return gap_days(step(state, result, time.time() if now is None else now))


def pick(items: list[dict], hist: dict[str, dict], n: int, now: float, only_due: bool = True,
         seed: int | None = None) -> list[str]:
    """Deste: önce zamanı gelmiş tekrar kartları (unutulmaya en yakın önce: hatırlama olasılığı en düşük), sonra hiç
    görülmemişler; eşitlerde karışık."""
    pool = [it for it in items if not only_due or is_due(hist.get(it["id"]), now)]
    random.Random(seed).shuffle(pool)

    def urgency(it: dict) -> tuple[int, float]:
        h = hist.get(it["id"])
        if not h or not h.get("seen"):
            return (1, 0.0)
        return (0, 0.0 if h["lapsed"] else _retrievability(max(0.0, (now - h["last"]) / 86400), h["s"]))
    pool.sort(key=urgency)
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
            "due": sum(is_due(s, now) for s in seen), "mastered": sum(s.get("seen", 0) > 0 and s["s"] >= 21 for s in seen)}

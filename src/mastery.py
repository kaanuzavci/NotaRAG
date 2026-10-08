"""Beyin analizi: kişinin notlarındaki konulara ne kadar hâkim olduğu (LLM yok; yalnızca kendi kayıtları).

Soru → konu bağı kalıcıdır: sorunun kanıt sayfası, belgenin konu haritasında hangi konunun sayfalarındaysa o konu
(haritası olmayan belgede bölüm başlıkları; hiçbirine düşmeyen soru "Diğer"). Sınav ekranındaki konu ise o sınavın
arama sonucuna göre değişebiliyordu; ustalık için sabit bir bağ gerekir.

Bir sorunun kişi için durumu, o soruya dair EN SON kanıttan gelir:
  - sınavdaki son cevabı (doğru / yanlış; ikinci denemeler dahil — öğrenmeyi gösterir),
  - kartın kutusu (Leitner: 2-3. kutu bildi, 1. kutu bilemedi, 4-5. kutu uzun süreli bellekte).
Konu durumu (başlanmadı / zayıf / çalışılıyor / öğrenildi) bu soruların sayılarıyla, açıklanabilir kurallarla verilir.
Küçük sayılarda yüzde yanıltır; arayüz "5 sorudan 4" diye gösterir.

Bellek özeti (kart kutuları): 1-2. kutu kısa süreli, 3. kutu pekişiyor, 4-5. kutu uzun süreli bellek.
Ölçüm (madde güçlüğü, Elo) bundan ayrıdır: orada yalnızca kişinin soruyu ilk görüşü sayılır (difficulty.py).
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict

STATUS = ("başlanmadı", "zayıf", "çalışılıyor", "öğrenildi")
MIN_LEARNED = 4         # "öğrenildi" için en az bu kadar farklı soru (konuda daha az soru varsa hepsi)
LEARNED_SHARE = 0.8
WEAK_SHARE = 0.5
OTHER = "Diğer"


def topic_of(page: int | None, topics: list[dict]) -> str:
    for t in topics:
        if page in t["pages"]:
            return t["title"]
    return OTHER


def question_states(attempts: list[dict], card_hist: dict[str, dict]) -> dict[str, dict]:
    """soru → {state: 'known' | 'strong' | 'weak', t}. attempts: kişinin sınav satırları (sırayla);
    card_hist: cards.history(user=…)."""
    out: dict[str, dict] = {}
    for a in attempts:
        t = a.get("t") or 0.0
        out[a["id"]] = {"state": "known" if a.get("correct") else "weak", "t": t}
    for qid, s in card_hist.items():
        if not s.get("seen"):
            continue
        state = "strong" if s["box"] >= 4 else ("known" if s["box"] >= 2 else "weak")
        prev = out.get(qid)
        if prev is None or s["last"] >= prev["t"]:
            out[qid] = {"state": state, "t": s["last"]}
    return out


def topic_status(n: int, seen: int, known: int) -> str:
    if seen == 0:
        return "başlanmadı"
    share = known / seen
    if seen >= 2 and share < WEAK_SHARE:
        return "zayıf"
    if share >= LEARNED_SHARE and seen >= min(MIN_LEARNED, n):
        return "öğrenildi"
    return "çalışılıyor"


def analyze(items: list[dict], topic_maps: dict[str, list[dict]], states: dict[str, dict]) -> dict:
    """items: kişinin görebildiği belgelerin kullanılabilir soruları; topic_maps: belge → konu haritası.
    → {docs: [{doc, n, seen, known, topics: [{title, n, seen, known, weak, strong, status}]}], weak: [...]}"""
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for it in items:
        page = it.get("check", {}).get("evidence_page")
        groups[it["doc"]][topic_of(page, topic_maps.get(it["doc"], []))].append(it["id"])
    docs, weak = [], []
    for doc, by_topic in groups.items():
        order = [t["title"] for t in topic_maps.get(doc, [])] + [OTHER]  # haritadaki sırayla
        rows = []
        for title in sorted(by_topic, key=lambda x: order.index(x) if x in order else len(order)):
            ids = by_topic[title]
            c = Counter(states[q]["state"] for q in ids if q in states)
            seen, known = sum(c.values()), c["known"] + c["strong"]
            row = {"title": title, "n": len(ids), "seen": seen, "known": known, "weak": c["weak"],
                   "strong": c["strong"], "status": topic_status(len(ids), seen, known)}
            rows.append(row)
            if row["status"] == "zayıf":
                weak.append({"doc": doc, **row})
        docs.append({"doc": doc, "n": sum(r["n"] for r in rows), "seen": sum(r["seen"] for r in rows),
                     "known": sum(r["known"] for r in rows), "topics": rows,
                     "status": Counter(r["status"] for r in rows)})
    weak.sort(key=lambda r: (r["known"] / r["seen"], -r["seen"]))
    return {"docs": docs, "weak": weak}


def memory(card_hist: dict[str, dict], alive: set[str] | None = None) -> dict[str, int]:
    """Kart kutularından bellek özeti (havuzdan çıkmış sorular sayılmaz)."""
    out = {"kısa": 0, "pekişiyor": 0, "uzun": 0}
    for qid, s in card_hist.items():
        if not s.get("seen") or (alive is not None and qid not in alive):
            continue
        out["kısa" if s["box"] <= 2 else ("pekişiyor" if s["box"] == 3 else "uzun")] += 1
    return out


def activity(attempts: list[dict], card_rows: list[dict], days: int = 14, now: float | None = None) -> list[int]:
    """Son `days` günün her biri için çalışma sayısı (sınav cevabı + kart değerlendirmesi), eskiden yeniye."""
    now = now or time.time()
    today = time.localtime(now)
    start = time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, -1)) - (days - 1) * 86400
    out = [0] * days
    for t in [a.get("t") for a in attempts] + [c.get("t") for c in card_rows if c.get("result") != "skip"]:
        if t and t >= start:
            out[min(days - 1, int((t - start) // 86400))] += 1
    return out


def for_user(user_id: str, visible: set[str]) -> dict:
    """Profil sayfasının bütün verisi (kayıtlar diskte; LLM yok)."""
    from src import cards, jsonl
    from src import request as R
    from src.accounts import legacy_owner
    from src.difficulty import ATTEMPTS
    from src.topics import topic_map

    legacy = legacy_owner()
    rows = [a for a in jsonl.read(ATTEMPTS) if (a.get("user") or legacy) == user_id]
    for a in rows:
        if not a.get("t"):  # eski satırlar: zaman yalnızca metin olarak
            try:
                a["t"] = time.mktime(time.strptime(a["time"], "%Y-%m-%d %H:%M:%S"))
            except (KeyError, ValueError):
                a["t"] = 0.0
    hist = cards.history(user=user_id)
    blocked = R.blocked_ids()
    items = [it for it in R.all_items().values() if it["doc"] in visible and R.usable(it) and it["id"] not in blocked]
    maps = {d: topic_map(d, build_missing=False) for d in {it["doc"] for it in items}}
    result = analyze(items, maps, question_states(rows, hist))
    card_rows = [c for c in jsonl.read(cards.LOG) if (c.get("user") or legacy) == user_id]
    result.update(memory=memory(hist, {it["id"] for it in items}), activity=activity(rows, card_rows),
                  answered=len(rows), reviewed=sum(c["result"] != "skip" for c in card_rows),
                  correct=sum(bool(a.get("correct")) for a in rows))
    return result

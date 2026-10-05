"""Sınav isteği — sistemin RAG akışı: seçilen konular → ARAMA → hazır havuz → eksikse hedefli üretim + doğrulama.

1. Arama: kullanıcı konuları hazır listeden SEÇER (src/topics.py); her konunun adı sorgudur. Seçili belgelerde
   dense arama (eval: isabet@5 %98,6; Türkçe konu İngilizce slaytta da bulunur) → en ilgili parçalar.
2. Havuz: o sayfalara bağlı, istenen tip ve zorlukta, DOĞRULANMIŞ ve insan/öğrenci tarafından reddedilmemiş ya
   da hatalı bildirilmemiş sorular → anında verilir, token harcanmaz.
3. Eksik: yalnızca bulunan parçalardan, seçilen zorlukta ve tiplerde üretim (§2 + §2b; hesap §2c) → kod
   kontrolleri → kör doğrulama → havuza eklenir (data/questions/istek_<dil>.jsonl). Bir dahaki istekte hazırdır.

Arka plan işi: python -m src.request <istek_id>   (arayüz başlatır; ilerleme data/requests/<id>.json'da)
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
import uuid
from functools import lru_cache
from pathlib import Path

from src import config
from src import review_store as rs

REQ_DIR = config.DATA_DIR / "requests"
QDIR = config.DATA_DIR / "questions"
ATTEMPTS = config.DATA_DIR / "review" / "attempts.jsonl"
REPORTS = config.DATA_DIR / "review" / "reports.jsonl"
KINDS = {"multiple_choice": "Çoktan seçmeli", "true_false": "Doğru / Yanlış", "short_answer": "Kısa cevap",
         "computed": "Hesap sorusu"}
DIFFS = {"easy": "Kolay", "medium": "Orta", "hard": "Zor"}
MAX_CONTEXT = 4000
TOPIC_K = 4          # konu başına en çok parça
SLACK = 0.08         # en iyi eşleşmeden bu kadar uzak (kosinüs) parçalar da alınır


def kind(q: dict) -> str:
    return "computed" if q.get("compute") else q.get("type", "?")


# ---------------------------------------------------------------- 1. arama

@lru_cache(maxsize=1)
def _index():
    from src.retrieval.index import Index
    return Index()


def retrieve(topic: str, docs: list[str]) -> list[dict]:
    """Konu adı → seçili belgelerde en ilgili parçalar (dense; görsel okuma bekleyenler hariç)."""
    idx = _index()
    col = idx.client.get_collection("chunks", embedding_function=None)
    where = {"doc": docs[0]} if len(docs) == 1 else {"doc": {"$in": docs}}
    r = col.query(query_embeddings=[idx.embedder.embed_query(topic).tolist()], n_results=12, where=where,
                  include=["distances"])
    ids, dist = r["ids"][0], r["distances"][0]
    if not ids:
        return []
    keep = [i for i, d in zip(ids, dist) if d <= dist[0] + SLACK and not idx.by_id[i].get("pending_vision")]
    return [{**idx.by_id[i], "distance": round(d, 3)} for i, d in zip(ids, dist) if i in keep[:TOPIC_K]]


# ---------------------------------------------------------------- 2. havuz

def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def all_items() -> dict[str, dict]:
    """Tam akış ve istek setlerindeki tüm sorular (pilot/deney setleri havuza girmez: farklı istem ve modeller)."""
    out = {}
    for p in sorted(QDIR.glob("*.jsonl")):
        for it in _jsonl(p):
            it["id"] = rs.question_id(it)
            it["doc"] = next(iter(it.get("chunk_ids") or []), "?").split(":")[0]
            out.setdefault(it["id"], it)
    return out


def reported() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in _jsonl(REPORTS):
        out.setdefault(r["id"], []).append(r)
    return out


def blocked_ids() -> set[str]:
    """Havuzdan çıkarılan sorular: insanın reddettiği ya da öğrencinin hatalı bildirdiği (insan onaylamadıysa)."""
    decs = rs.decisions()
    out = {qid for qid, d in decs.items() if d["decision"] == "reject"}
    for qid, reps in reported().items():
        d = decs.get(qid)
        if not d or d["time"] < max(r["time"] for r in reps):  # bildirimden sonra onaylanmadıysa
            out.add(qid)
    return out


def usable(it: dict) -> bool:
    return it.get("verification", {}).get("label") == "verified" and it["check"]["status"] != "rejected"


# ---------------------------------------------------------------- istek

def _split(n: int, k: int) -> list[int]:
    return [n // k + (1 if i < n % k else 0) for i in range(k)]


def prepare(docs: list[str], topics: list[str], difficulty: str | None, kinds: list[str], n: int,
            language: str = "tr") -> dict:
    """Aramayı ve havuz eşleştirmesini yapar (anında); eksik kalan soru sayısını hesaplar. İstek dosyasını yazar."""
    from src.topics import topic_map

    if not topics:  # konu seçilmediyse: seçili belgelerin bütün konuları
        topics = [t["title"] for d in docs for t in topic_map(d)]
    sources = {t: retrieve(t, docs) for t in topics}
    sources = {t: s for t, s in sources.items() if s}
    items, blocked = all_items(), blocked_ids()
    quota = dict(zip(sources, _split(n, max(1, len(sources)))))
    chosen, missing = [], {}
    for t, chunks in sources.items():
        pages = {(c["doc"], c["page"]) for c in chunks}
        cands = [it for it in items.values() if usable(it) and it["id"] not in blocked and it["id"] not in chosen
                 and (it["doc"], it["check"].get("evidence_page")) in pages and kind(it["q"]) in kinds
                 and (not difficulty or it["q"].get("difficulty") == difficulty)]
        random.shuffle(cands)  # her istekte farklı sorular
        take = [c["id"] for c in cands[:quota[t]]]
        chosen += take
        if len(take) < quota[t]:
            missing[t] = quota[t] - len(take)
    req = {"id": time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4], "created": time.time(),
           "params": {"docs": docs, "topics": topics, "difficulty": difficulty, "kinds": kinds, "n": n,
                      "language": language},
           "sources": {t: [{"doc": c["doc"], "page": c["page"], "chunk": c["id"], "distance": c["distance"]}
                           for c in s] for t, s in sources.items()},
           "pool_ids": chosen, "missing": missing, "new_ids": [], "status": "ready" if not missing else "partial",
           "progress": ""}
    save(req)
    return req


def save(req: dict) -> None:
    REQ_DIR.mkdir(parents=True, exist_ok=True)
    tmp = REQ_DIR / f"{req['id']}.tmp"
    tmp.write_text(json.dumps(req, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(REQ_DIR / f"{req['id']}.json")


def load(req_id: str) -> dict | None:
    p = REQ_DIR / f"{req_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def items_of(req: dict) -> list[dict]:
    items = all_items()
    ids = list(dict.fromkeys(req["pool_ids"] + req["new_ids"]))[: req["params"]["n"]]
    return [items[i] for i in ids if i in items]


def start(req: dict) -> None:
    """Eksikleri arka planda üret (arayüz kapansa da sürer)."""
    import subprocess

    req["status"], req["progress"] = "generating", "Başlıyor"
    save(req)
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if sys.platform == "win32" else 0
    log = (REQ_DIR / f"{req['id']}.log").open("w", encoding="utf-8")
    subprocess.Popen([sys.executable, "-m", "src.request", req["id"]], cwd=config.ROOT, stdout=log,
                     stderr=subprocess.STDOUT, creationflags=flags,
                     env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})


# ---------------------------------------------------------------- 3. eksikleri üret + doğrula (arka plan)

def _unit(topic: str, refs: list[dict], chunks: dict[str, dict], wide: bool = False) -> dict:
    """Konunun üretim bağlamı: aramanın bulduğu parçalar. wide=True (bir konudan çok soru istendiğinde): aynı
    sayfalardaki diğer parçalar da eklenir — konunun dışına çıkmadan daha çok malzeme (sınır 6.000 karakter)."""
    from src.generation.generate import _render
    ids = [r["chunk"] for r in refs]
    if wide:
        pages = {(r["doc"], r["page"]) for r in refs}
        ids += [cid for cid, c in chunks.items() if (c["doc"], c["page"]) in pages and cid not in ids
                and not c.get("pending_vision")]
    limit = 6000 if wide else MAX_CONTEXT
    picked, size = [], 0
    for cid in ids:
        c = chunks[cid]
        if picked and size + len(c["text"]) > limit:
            break
        picked.append(c)
        size += len(c["text"])
    picked.sort(key=lambda c: (c["doc"], c["page"]))
    return {"title": topic, "chunks": picked, "text": _render(picked), "pages": sorted({c["page"] for c in picked})}


def _dur(seconds: float) -> str:
    m = max(1, round(seconds / 60))
    return f"{m // 60} sa {m % 60} dk" if m >= 60 else f"{m} dk"


def _progress(req: dict, text: str) -> None:
    req["progress"] = text
    save(req)
    print(text, flush=True)


def run(req_id: str) -> None:
    from src.generation.generate import generate_request, generate_unit
    from src.llm.router import AllModelsExhausted
    from src.pipeline import patient
    from src.verification.checks import mark_duplicates
    from src.verification.verify import verify_item

    req = load(req_id)
    p = req["params"]
    chunks = rs.load_chunks()
    # Elenecekleri telafi etmek için biraz fazla iste (fazlası havuza kalır, boşa gitmez)
    plain_kinds = [k for k in p["kinds"] if k != "computed"]
    spec_plain, spec_worked = [], []
    for t, m in req["missing"].items():
        u = _unit(t, req["sources"][t], chunks, wide=m > 4)
        # Eksik + %40 pay (elenenleri telafi; fazlası havuza). Üst sınır 12: ilk sürümde 6'ydı ve tek konudan 7 soru
        # eksik olunca istenen bile eksiğin altında kalıyordu (2026-10-04).
        ask = min(12, m + max(1, math.ceil(m * 0.4)))
        if "computed" in p["kinds"]:
            share = ask if not plain_kinds else math.ceil(ask / len(p["kinds"]))
            spec_worked.append((u, share, ["multiple_choice", "short_answer"][: max(1, min(2, share))]))
            ask -= share
        if ask > 0 and plain_kinds:
            spec_plain.append((u, ask, [plain_kinds[i % len(plain_kinds)] for i in range(ask)]))

    new = []
    for worked, spec in ((False, spec_plain), (True, spec_worked)):
        if not spec:
            continue
        what = "hesap soruları" if worked else "sorular"
        _progress(req, f"Yeni {what} üretiliyor ({sum(n for _, n, _ in spec)} soru, {len(spec)} konu)")
        try:
            new += generate_request(spec, p["language"], p["difficulty"], worked=worked)
        except AllModelsExhausted as e:
            if worked:  # §2c için yedek yol yok (kalite kapısı)
                _progress(req, f"Hesap soruları şu an üretilemiyor ({'yoğunluk' if e.transient else 'kota'})")
                continue
            for u, n, types in spec:  # §2 yedek: onaylı birim başına üretici (qwen), kota dolarsa bekler
                new += patient(generate_unit, u, "", p["language"], "generate", n=n, types=types,
                               difficulty=p["difficulty"], what="üretim")
    mark_duplicates(new, keep=list(all_items().values()))  # havuzdakinin tekrarı doğrulamaya gitmez (kota)
    for it in new:
        it["request"] = req_id
    ok = [it for it in new if it["check"]["status"] != "rejected"]
    for i, it in enumerate(ok, 1):
        _progress(req, f"Doğrulanıyor {i}/{len(ok)}")
        wait_note = lambda why, s, i=i: _progress(req, f"Doğrulama {i}/{len(ok)}: {why}; ~{_dur(s)} sonra kendiliğinden devam edecek")
        it["verification"] = patient(verify_item, it, chunks, light=True, what=f"doğrulama {i}/{len(ok)}",
                                     on_wait=wait_note)
    for it in new:
        it.setdefault("verification", {"label": "rejected", "why": "kod kontrolü: " + ", ".join(it["check"]["rejected"])})

    QDIR.mkdir(parents=True, exist_ok=True)
    with (QDIR / f"istek_{p['language']}.jsonl").open("a", encoding="utf-8") as f:
        for it in new:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    good = [rs.question_id(it) for it in new if usable(it) and kind(it["q"]) in p["kinds"]]
    req = load(req_id)
    req["new_ids"] = good
    req["status"] = "done"
    have = len(set(req["pool_ids"] + good))
    req["progress"] = (f"{len(good)} yeni soru doğrulandı" +
                       (f"; istenen {p['n']} sorunun {have}'i hazır" if have < p["n"] else ""))
    save(req)
    print(req["progress"], flush=True)


# ---------------------------------------------------------------- öğrenci denemeleri ve bildirimler

def record_attempt(req_id: str, results: dict[str, bool], retry: bool = False, answers: dict | None = None,
                   hints: dict | None = None) -> None:
    """retry=True: yanlışların ikinci denemesi — madde istatistiğine girmez (güçlük ilk denemeden ölçülür).
    answers: öğrencinin verdiği cevap da saklanır → puanlama düzelirse eski denemeler yeniden puanlanabilir
    (2026-10-05'te puanlama hatası yalnızca doğru/yanlış saklandığı için ekran görüntüsünden düzeltilebildi) ve
    hangi çeldiricinin seçildiği görülür (hiç seçilmeyen çeldirici = işe yaramayan çeldirici)."""
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPTS.open("a", encoding="utf-8") as f:
        for qid, correct in results.items():
            rec = {"id": qid, "correct": bool(correct), "request": req_id, "retry": retry,
                   "time": time.strftime("%Y-%m-%d %H:%M:%S")}
            if answers is not None and answers.get(qid) is not None:
                rec["answer"] = answers[qid]
            if hints and hints.get(qid):
                rec["hints"] = hints[qid]  # kullanılan ipucu sayısı (ipucuyla doğru ≠ ipucusuz doğru)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def item_stats() -> dict[str, dict]:
    """Soru başına öğrenci istatistiği (madde analizi): çözülme sayısı ve doğru oranı (yalnızca ilk denemeler)."""
    out: dict[str, dict] = {}
    for a in (x for x in _jsonl(ATTEMPTS) if not x.get("retry")):
        s = out.setdefault(a["id"], {"n": 0, "correct": 0})
        s["n"] += 1
        s["correct"] += int(a["correct"])
    for s in out.values():
        s["rate"] = s["correct"] / s["n"]
    return out


def report(qid: str, note: str, req_id: str | None = None) -> None:
    REPORTS.parent.mkdir(parents=True, exist_ok=True)
    with REPORTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": qid, "note": note.strip(), "request": req_id,
                            "time": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    run(sys.argv[1])

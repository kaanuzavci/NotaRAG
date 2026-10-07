"""Uzman zorluk adımları ↔ sistemin zorluk sinyalleri (MEB 3 Adım Soru Bankası) → eval/sonuclar_uc_adim.md

3 Adım Soru Bankası'nda (MEB OGM, 2024) her konunun soruları uzmanlarca üç adımda zorlaşır: 1. adım temel, 2. adım
orta, 3. adım ileri. TurkishMMLU deneyiyle (eval/turkishmmlu_zorluk.py, gerçek öğrenci doğru oranı) aynı sinyaller
burada uzman sıralamasına karşı ölçülür: benzetilmiş öğrenci p (kapalı kitap), dikkatli çözümün çabası, LLM'in
zorluk etiketi ve difficulty.sim_level kuralı. Soru başına 6 Gemma çağrısı (turkishmmlu_zorluk.measure).

Soru çıkarma (kota yok): sayfa başlığından adım ve konu, satır başındaki 'N.' ile soru sınırı, 'A)…E)' ile şıklar,
kitabın sonundaki konu / adım cevap anahtarı (sayfa düzeninden, konuma göre: _page_keys). Görsele dayanan sorular
(harita, grafik, tablo, şekil, şerit, koordinat sistemi) metinle cevaplanamayacağı için atlanır. Raporda adım başına
dikkatli çözücünün doğruluğu anahtar sağlamasıdır. Veri: data/kaynak_veri/ogm/3adim (depoda değil).

Kullanım: python -m eval.uc_adim [--cikar] [--n 10] [--parca k/m] [--rapor]
          --cikar: yalnızca soruları çıkarıp sayıları yazar (kota yok)
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
import time
from collections import defaultdict

from src import config
from src.llm.router import AllModelsExhausted

SRC = config.DATA_DIR / "kaynak_veri" / "ogm" / "3adim"
DIR = config.DATA_DIR / "uc_adim"
LOG = DIR / "olcumler.jsonl"
OUT = config.ROOT / "eval" / "sonuclar_uc_adim.md"
BOOKS = {"TYT_Tarih_074.pdf": "Tarih", "TYT_Cografya_069.pdf": "Coğrafya", "TYT_Felsefe_070.pdf": "Felsefe",
         "TYT_Biyoloji_068.pdf": "Biyoloji"}
_Q = re.compile(r"(?m)^\s*(\d{1,2})\.(?!\s*ADIM)\s")
_STEP = re.compile(r"([123])\.\s*ADIM")
_KEY = re.compile(r"(\d{1,2})-([A-E])")
_KEY_WORD = re.compile(r"^(\d{1,2})-([A-E])$")
_STEP_LINE = re.compile(r"^([123])\.\s*ADIM$")
# "Yukarıdaki koordinat sisteminde taralı bölgeler…" gibi şekle dayanan Coğrafya soruları da metinle cevaplanamaz
_VISUAL = re.compile(r"(harita|grafik|tablo|şekil|görsel|şeri[dt]|diyagram|fotoğraf|resim|koordinat sistemi|taralı"
                     r"|işaretli)", re.I)


def _page_keys(page) -> list[dict]:
    """Anahtar sayfası → [{name, steps: {1: [harf…], 2: …, 3: …}}]. Sayfa düzeni: her konu bir tablo; adı tablonun
    üstünde, satırların solunda '1. ADIM' / '2. ADIM' / '3. ADIM', harfler satırda ('11-A' satırın alt yarısında).
    Konuma bakılır, metin sırasına değil: metin sırasında ilk konunun adı sayfanın sonunda çıkıyor, başlıkları
    ayrı satırda duran tablolar da öncekine karışıyordu (2026-10-07 hatası: 1. adımda anahtar başka konudandı)."""
    lines = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = " ".join(s["text"] for s in ln["spans"]).strip()
            if t:
                lines.append((t, *ln["bbox"]))
    labels = [(int(_STEP_LINE.match(t).group(1)), x0, (y0 + y1) / 2, y0) for t, x0, y0, x1, y1 in lines
              if _STEP_LINE.match(t)]
    names = [(t, x0, y1) for t, x0, y0, x1, y1 in lines
             if not _STEP_LINE.match(t) and not _KEY_WORD.match(t.split()[0]) and not t.isdigit()
             and "CEVAP ANAHTARI" not in t.upper() and len(t) > 3]
    rows: dict[int, dict[int, str]] = defaultdict(dict)
    for w in page.get_text("words"):
        m = _KEY_WORD.match(w[4])
        yc = (w[1] + w[3]) / 2
        near = [(abs(yc - ly), i) for i, (_, lx, ly, _) in enumerate(labels) if lx < w[0] and abs(yc - ly) < 14]
        if m and near:  # harf, dikeyde en yakın adım satırına (solunda etiketi olan sütunda)
            rows[min(near)[1]][int(m.group(1))] = m.group(2)
    topics = []
    for i, (step, lx, _, top) in enumerate(labels):
        if step == 1:  # yeni tablo: adı hemen üstündeki, aynı sütundaki satır
            above = [(ny, t) for t, nx, ny in names if ny <= top + 1 and abs(nx - lx) < 40]
            topics.append({"name": max(above)[1] if above else None, "steps": {}})
        if topics:
            topics[-1]["steps"][step] = [rows[i][k] for k in sorted(rows[i])]
    return topics


def _keys(doc) -> list[dict]:
    """Kitabın sonundaki anahtar sayfaları → konu listesi (adı aynı iki konu olabilir: liste, sözlük değil).
    İlk anahtar sayfası bazı kitaplarda görüntü: o konular bulunmaz, testleri atlanır."""
    out = []
    for page in list(doc)[-16:]:
        text = page.get_text()
        if "ADIM" in text and _KEY.search(text):
            out += _page_keys(page)
    return out


def _norm(s: str | None) -> str:
    """Konu adı karşılaştırması: Türkçe küçük harf, boşluk ve noktalama yok ('Felsefeyle Düşünme-1' = '… - 1')."""
    s = (s or "").replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^\wçğıöşü]", "", s)


def _match_keys(triples: list[dict], keys: list[dict]) -> dict[int, dict]:
    """Test üçlüsü (aynı konunun 1-2-3. adım testleri) → anahtar konusu. Sırayla:
    1) ad aynı; 2) ad kesik ya da yazım farklı ('Ahlak Felsefenin Konusu ve') → benzer adlılar arasında adım soru
    sayıları en çok tutan (en az 2 adım); 3) başlık yerine soru cümlesi okunmuşsa: üç adımın soru sayısı, boşta
    kalan tek bir konununkiyle birebir aynıysa. Her anahtar konusu bir kez kullanılır."""
    from rapidfuzz import fuzz

    def agree(tr: dict, k: dict) -> int:
        return sum(len(k["steps"].get(s) or []) == n for s, n in tr["n"].items())

    used, out = set(), {}
    for rule in (1, 2, 3):
        for ti, tr in enumerate(triples):
            if ti in out:
                continue
            tn = _norm(tr["topic"])
            free = [(ki, k) for ki, k in enumerate(keys) if ki not in used and k["name"]]
            if rule == 1:
                cand = [(ki, k) for ki, k in free if _norm(k["name"]) == tn and agree(tr, k)]
            elif rule == 2:
                cand = [(ki, k) for ki, k in free if len(tn) >= 8 and fuzz.partial_ratio(tn, _norm(k["name"])) >= 90
                        and agree(tr, k) >= 2]
                best = max((agree(tr, k) for _, k in cand), default=0)
                cand = [(ki, k) for ki, k in cand if agree(tr, k) == best]
                # eşitlikte adı test adıyla başlayan: 'Devletleşme Sürecinde' → '…Savaşçılar', '(Yerleşme ve) …' değil
                cand = [(ki, k) for ki, k in cand if _norm(k["name"]).startswith(tn)] or cand
            else:
                cand = [(ki, k) for ki, k in free if len(tr["n"]) == 3 and agree(tr, k) == 3]
            if len(cand) == 1:
                out[ti] = cand[0][1]
                used.add(cand[0][0])
    return out


def _tests(doc) -> list[dict]:
    """Soru sayfaları → testler: [{step, topic, questions: [(no, metin)]}] (sayfa sırasıyla)."""
    tests, topic = [], None
    for page in doc:
        text = page.get_text()
        m = _STEP.search(text[:120])
        if not m or not _Q.search(text):
            continue
        step = int(m.group(1))
        head = [ln.strip() for ln in text[:200].split("\n") if ln.strip()]
        for ln in head:  # tek sayfalarda başlıkta konu adı var
            if len(ln) > 6 and not re.match(r"^(\d+\.?|ADIM|TYT|AYT|\d+\.\s*ADIM)$", ln) and not ln.isupper():
                topic = ln
                break
        parts = _Q.split(text)
        for i in range(1, len(parts) - 1, 2):
            no, body = int(parts[i]), parts[i + 1]
            if not tests or tests[-1]["step"] != step or (no == 1 and tests[-1]["questions"]):
                tests.append({"step": step, "topic": topic, "questions": []})
            tests[-1]["questions"].append((no, body))
    return tests


def _split_options(body: str) -> tuple[str, list[str]] | None:
    body = re.sub(r"­\s*", "", body)  # satır sonu tiresi (yumuşak tire) kalıntısı: "bırakıl- mıştır"
    parts = re.split(r"(?:^|\s)([A-E])\)\s*", body)
    if len(parts) < 11:
        return None
    stem = re.sub(r"\s+", " ", parts[0]).strip()
    opts = {parts[i]: re.sub(r"\s+", " ", parts[i + 1]).strip() for i in range(1, len(parts) - 1, 2)}
    if sorted(opts) != list("ABCDE") or not all(opts.values()):
        return None
    return stem, [opts[c] for c in "ABCDE"]


def extract() -> tuple[list[dict], dict]:
    import pymupdf
    items, stats = [], {}
    for fname, subject in BOOKS.items():
        doc = pymupdf.open(SRC / fname)
        keys, tests = _keys(doc), _tests(doc)
        triples, of_test = [], {}  # aynı konunun ardışık 1-2-3. adım testleri
        for t_i, test in enumerate(tests):
            if test["step"] == 1 or not triples or test["step"] in triples[-1]["n"]:
                triples.append({"topic": test["topic"], "n": {}})
            triples[-1]["n"][test["step"]] = len(test["questions"])
            of_test[t_i] = len(triples) - 1
        matched = _match_keys(triples, keys)
        ok = skipped_visual = bad = unmatched = 0
        for t_i, test in enumerate(tests):
            k = matched.get(of_test[t_i])
            key = k["steps"].get(test["step"]) if k else None
            if not key or len(key) != len(test["questions"]):  # soru sayısı tutmayan adım alınmaz
                unmatched += len(test["questions"])
                continue
            for (no, body), letter in zip(test["questions"], key):
                so = _split_options(body)
                if not so or len(so[0]) < 25:
                    bad += 1
                    continue
                stem, options = so
                if _VISUAL.search(stem):
                    skipped_visual += 1
                    continue
                items.append({"id": f"ua_{subject[:3].lower()}_{t_i:02d}_{no:02d}", "subject": subject, "step": test["step"],
                              "topic": k["name"], "question": stem, "choices": options, "answer": "ABCDE".index(letter),
                              "metadata": {"grade": "lise (TYT)"}})
                ok += 1
        stats[subject] = {"test": len(tests), "anahtardaki konu": len(keys), "eşleşen konu": len(matched), "soru": ok,
                          "görselli (atlandı)": skipped_visual, "ayrıştırılamadı": bad,
                          "anahtarla eşleşmedi": unmatched}
    return items, stats


def sample(items: list[dict], n: int, seed: int = 23) -> list[dict]:
    rnd, by = random.Random(seed), defaultdict(list)
    for it in items:
        by[(it["subject"], it["step"])].append(it)
    out = []
    for k in sorted(by):
        out += rnd.sample(by[k], min(n, len(by[k])))
    return out


def done() -> dict[str, dict]:
    out = {}
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["id"]] = e
    return out


def run(todo: list[dict]) -> None:
    from eval.turkishmmlu_zorluk import measure
    have = done()
    todo = [x for x in todo if x["id"] not in have]
    DIR.mkdir(parents=True, exist_ok=True)
    for i, x in enumerate(todo, 1):
        for attempt in range(16):
            try:
                e = measure(x)
                break
            except AllModelsExhausted as ex:
                if not ex.transient or attempt == 15:
                    print(f"durdu ({ex}); {len(todo) - i + 1} soru ölçülmedi", flush=True)
                    return
                print("⏳ Gemma şu an yoğun (geçici) → 2 dk bekleniyor", flush=True)
                time.sleep(120)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"ölçüldü {i}/{len(todo)} · {x['id']} · {x['subject']} {x['step']}. adım · p={e['p']} çaba={e['think']} "
              f"etiket={e['label']}", flush=True)


def report(picked: list[dict], stats: dict) -> None:
    from eval.turkishmmlu_zorluk import _fmt, _sim_level, spearman_ci
    meas = done()
    got = [x for x in picked if x["id"] in meas]
    lines = ["# Uzman zorluk adımları ↔ sistemin zorluk sinyalleri (3 Adım Soru Bankası)", "",
             "MEB 3 Adım Soru Bankası'nda (TYT) her konunun soruları uzmanlarca üç adımda zorlaşır. Aynı sinyaller "
             "(eval/turkishmmlu_zorluk.py) bu uzman sıralamasına karşı: ρ = adım (1, 2, 3) ile Spearman sıra korelasyonu. "
             "Zorluğu izleyen bir sinyalde beklenen: p için −, çaba ve LLM etiketi için +.", "",
             "Soru çıkarma: " + "; ".join(f"{s}: {v['soru']} soru ({v['görselli (atlandı)']} görselli atlandı, "
                                           f"{v['ayrıştırılamadı']} ayrıştırılamadı)" for s, v in stats.items()), ""]
    if len(got) >= 10:
        m = [meas[x["id"]] for x in got]
        step = [float(x["step"]) for x in got]
        lab = {"easy": 0, "medium": 1, "hard": 2}

        def row(name: str, a: list, b: list, sign: str) -> str:
            rho, lo, hi = spearman_ci(a, b, n_boot=500)
            return f"| {name} | {_fmt(rho)} | {_fmt(lo)} … {_fmt(hi)} | {sign} |"
        th = [(e["think"], s) for e, s in zip(m, step) if e["think"]]
        lb = [(lab[e["label"]], s) for e, s in zip(m, step) if e["label"]]
        lines += [f"## Sinyaller ({len(got)} soru)", "", "| Sinyal | ρ (adımla) | %95 aralık | Beklenen |", "|---|---|---|---|",
                  row("Benzetilmiş öğrenci p", [e["p"] for e in m], step, "−"),
                  row("Çaba (düşünme token'ı)", [a for a, _ in th], [b for _, b in th], "+"),
                  row("LLM zorluk etiketi", [a for a, _ in lb], [b for _, b in lb], "+"), "",
                  "| Adım | n | ort. p | ort. çaba | LLM etiketi kolay / orta / zor | sim_level: bilgi yok / orta / zor "
                  "| dikkatli çözücü doğru¹ |",
                  "|---|---|---|---|---|---|---|"]
        for s in (1, 2, 3):
            g = [e for e, x in zip(m, got) if x["step"] == s]
            if not g:
                continue
            labs = [e["label"] for e in g]
            sims = [_sim_level(e["p"], e["think"]) for e in g]
            lines.append(f"| {s}. adım | {len(g)} | {statistics.mean(e['p'] for e in g):.2f} | "
                         f"{statistics.median(e['think'] or 0 for e in g):.0f} (medyan) | "
                         + " / ".join(str(labs.count(v)) for v in ("easy", "medium", "hard")) + " | "
                         + " / ".join(str(sims.count(v)) for v in ("tavan", "medium", "hard")) + " | "
                         + f"{sum(bool(e['careful_ok']) for e in g)}/{len(g)} |")
        by = defaultdict(list)
        for e, x in zip(m, got):
            by[x["subject"]].append((e, x["step"]))
        lines += ["", "¹ Anahtar sağlaması: dikkatli çözücü (Gemma, uzun düşünme) bir adımda belirgin biçimde düşükse o adımın "
                  "anahtarı şüphelidir (ilk çalıştırmada 1. adımın anahtarı başka konudandı: 1. adımda 17/30, 2. adımda 30/30).",
                  "", "Ders bazında ρ (adımla): " + ", ".join(
            f"{s} çaba {_fmt(spearman_ci([e['think'] or 0 for e, _ in v], [float(t) for _, t in v], n_boot=200)[0])} · "
            f"etiket {_fmt(spearman_ci([lab.get(e['label'], 1) for e, _ in v], [float(t) for _, t in v], n_boot=200)[0])}"
            for s, v in sorted(by.items())), ""]
    else:
        lines += ["Henüz yeterli ölçüm yok.", ""]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazıldı:", OUT)


def main() -> None:
    args = sys.argv[1:]
    items, stats = extract()
    if "--cikar" in args:
        print(json.dumps(stats, ensure_ascii=False, indent=1))
        by = defaultdict(int)
        for it in items:
            by[(it["subject"], it["step"])] += 1
        print(dict(by))
        return
    n = int(args[args.index("--n") + 1]) if "--n" in args else 10
    picked = sample(items, n)
    if "--rapor" not in args:
        k, m = map(int, args[args.index("--parca") + 1].split("/")) if "--parca" in args else (0, 1)
        mine = [x for i, x in enumerate(picked) if i % m == k]
        print(f"örneklem: {len(picked)} soru; bu süreç: {len(mine)} (parça {k}/{m})", flush=True)
        run(mine)
    report(picked, stats)


if __name__ == "__main__":
    main()

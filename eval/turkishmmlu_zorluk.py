"""Zorluk sinyallerinin GERÇEK öğrenci verisine karşı sınanması (TurkishMMLU) → eval/sonuclar_turkishmmlu.md

Veri: TurkishMMLU (Yüksel ve ark. 2024) alt kümesi — 900 lise sorusu (9 ders × 100, 5 şık); her birinde çevrim içi
platformdaki öğrencilerin doğru oranı (correctness_ratio, %) ve ondan türetilen etiket (kolay ≥ 42, orta 28-41,
zor ≤ 27). Lisans belirtilmemiş → veri depoya girmez (data/turkishmmlu/), yalnızca toplu sonuçlar yazılır.

Soru: elimizdeki ücretsiz zorluk sinyallerinden hangisi gerçek öğrenci zorluğunu izliyor?
  1. Metin özellikleri (kota yok, 900 soru): uzunluk, öncül sayısı (I. II. III.), olumsuz kök, formül/sayı, şık
     uzunluğu, doğru şıkla en yakın çeldiricinin benzerliği
  2. Benzetilmiş öğrenci, kapalı kitap (Gemma 4 sınıfı, düşünmeden 4 örneklem → p; PROMPTS §8b)
  3. Çaba: dikkatli çözümün düşünme token'ı (hepsi 5 şıklı ÇS → soru tipi karışmaz; sözel pilotta tipi ölçmüştü)
  4. LLM'in zorluk etiketi (Gemma 4 31B; PROMPTS §8c) — An ve Wang (2026) bulgusunun Türkçe tekrarı
Ölçüt: öğrenci doğru oranıyla Spearman ρ (zorluk sinyalinde beklenen işaret: p +, çaba ve etiket −) ve 3 düzeyde
tutma. Örneklem: ders × zorluk tabakalı (ders başına --n, varsayılan 20 → 180 soru). Ölçümler
data/turkishmmlu/olcumler.jsonl'de; kaldığı yerden devam eder. Maliyet: soru başına 6 Gemma çağrısı (ayrı ücretsiz
kota; Gemini ve Groq harcanmaz). Gemma kotası dolarsa durur ve eldekiyle rapor yazar.

Kullanım: python -m eval.turkishmmlu_zorluk [--n 20] [--parca k/m] [--rapor]
          --parca 0/4 … 3/4: örneklemi 4 sürece böl (paralel); --rapor: yeni çağrı yapmadan rapor
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
import time
import urllib.request
from collections import defaultdict

from rapidfuzz import fuzz

from src import config
from src.llm.router import AllModelsExhausted, call
from src.prompts import load_prompt
from src.simulate import CAREFUL, CLASS, _role

URL = "https://huggingface.co/datasets/AYueksel/TurkishMMLU/resolve/main/turkishmmlu_sub.json"
DIR = config.DATA_DIR / "turkishmmlu"
DATA, LOG = DIR / "turkishmmlu_sub.json", DIR / "olcumler.jsonl"
OUT = config.ROOT / "eval" / "sonuclar_turkishmmlu.md"
LETTERS = "ABCDE"
LEVELS = ("easy", "medium", "hard")
TR = {"easy": "kolay", "medium": "orta", "hard": "zor"}
LABELER = "gemma-4-31b-it"
_PREMISE = re.compile(r"(?<![A-Za-z])(I{1,3}|IV|V)\.\s")
_NEG = re.compile(r"değildir|yanlıştır|olmayan|olamaz|hariç|yoktur|bulunmaz|söylenemez|ulaşılamaz", re.I)
_MATH = re.compile(r"\$|\\\(|\d")


def load() -> list[dict]:
    if not DATA.exists():
        DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, DATA)
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    for i, x in enumerate(rows):
        x["id"] = f"tm{i:03d}"
        x["ratio"] = float(x["metadata"]["correctness_ratio"])
        x["level"] = x["metadata"]["difficulty"]
    return rows


def sample(rows: list[dict], n: int, seed: int = 11) -> list[dict]:
    """Ders başına n soru, zorluk düzeyleri sırayla (dengeli)."""
    rnd, out = random.Random(seed), []
    by = defaultdict(lambda: defaultdict(list))
    for x in rows:
        by[x["subject"]][x["level"]].append(x)
    for subj in sorted(by):
        pools = {lvl: rnd.sample(v, len(v)) for lvl, v in by[subj].items()}
        got = []
        while len(got) < n and any(pools.values()):
            for lvl in LEVELS:
                if pools.get(lvl) and len(got) < n:
                    got.append(pools[lvl].pop())
        out += got
    return out


# ---------------------------------------------------------------- 1. metin özellikleri (kota yok)

def features(x: dict) -> dict:
    q, ch = x["question"], [str(c) for c in x["choices"]]
    key = ch[x["answer"]]
    return {"uzunluk": len(q),
            "öncül sayısı": len(set(_PREMISE.findall(q))),
            "olumsuz kök": int(bool(_NEG.search(q))),
            "formül/sayı": int(bool(_MATH.search(q))),
            "şık uzunluğu": statistics.mean(len(c) for c in ch),
            "çeldirici benzerliği": max(fuzz.token_set_ratio(key, c) for i, c in enumerate(ch) if i != x["answer"])}


def _ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1  # eşitlere ortalama sıra
        i = j + 1
    return r


def spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(set(a)) < 2 or len(set(b)) < 2:
        return None
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / ((sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5)


def spearman_ci(a: list[float], b: list[float], n_boot: int = 1000, seed: int = 3) -> tuple[float | None, float, float]:
    """ρ ve önyükleme (bootstrap) %95 aralığı: 180 soruda ρ'nun belirsizliği ±0,15 civarı; tek sayı kesin sanılmasın."""
    rho = spearman(a, b)
    if rho is None:
        return None, 0.0, 0.0
    rnd, idx, boots = random.Random(seed), range(len(a)), []
    for _ in range(n_boot):
        s = [rnd.choice(idx) for _ in idx]
        r = spearman([a[i] for i in s], [b[i] for i in s])
        if r is not None:
            boots.append(r)
    boots.sort()
    return rho, boots[int(0.025 * len(boots))], boots[int(0.975 * len(boots)) - 1]


# ---------------------------------------------------------------- 2-4. Gemma ölçümleri

def _options(x: dict, perm: list[int]) -> str:
    return "\n".join(f"{LETTERS[i]}) {x['choices'][j]}" for i, j in enumerate(perm))


def _picked(x: dict, reply: str, perm: list[int]) -> bool:
    m = re.search(r"\b([A-E])\b", (reply or "").upper())
    return bool(m and perm[LETTERS.index(m.group(1))] == x["answer"])


def _student_prompt(x: dict, student: int) -> tuple[str, list[int]]:
    perm = list(range(len(x["choices"])))
    if student:  # 0 = dikkatli öğrenci: özgün sıra
        random.Random(f"{x['id']}|{student}").shuffle(perm)
    p = (load_prompt("8b").replace("{student}", str(student)).replace("{question}", x["question"])
         .replace("{options}", _options(x, perm)))
    return p, perm


def measure(x: dict) -> dict:
    ok, student = [], 0
    for model, k in CLASS:
        for _ in range(k):
            student += 1
            prompt, perm = _student_prompt(x, student)
            ok.append(_picked(x, call(_role(model), prompt, max_tokens=60, temperature=0.8, think="minimal").text, perm))
    prompt, perm = _student_prompt(x, 0)
    # Önbellek yok: önbellekten gelen yanıt düşünme token'ını taşımaz (simulate.measure ile aynı)
    careful = call(_role(CAREFUL), prompt, max_tokens=6000, temperature=0.0, think="high", use_cache=False)
    lp = (load_prompt("8c").replace("{grade}", str(x["metadata"].get("grade", ""))).replace("{question}", x["question"])
          .replace("{options}", _options(x, list(range(len(x["choices"]))))))
    lab = call(_role(LABELER), lp, max_tokens=20, temperature=0.0, think="minimal").text.strip().lower()
    label = next((lvl for lvl in LEVELS if lvl in lab), None)
    return {"id": x["id"], "p": round(sum(ok) / len(ok), 2), "k": len(ok), "think": careful.thoughts or None,
            "careful_ok": _picked(x, careful.text, perm), "label": label, "t": time.time()}


def done() -> dict[str, dict]:
    out = {}
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["id"]] = e
    return out


def run(todo: list[dict]) -> None:
    have = done()
    todo = [x for x in todo if x["id"] not in have]
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
        print(f"ölçüldü {i}/{len(todo)} · {x['id']} · {x['subject']} · öğrenci %{x['ratio']:.0f} ({TR[x['level']]}) · "
              f"p={e['p']} çaba={e['think']} etiket={e['label']}", flush=True)


# ---------------------------------------------------------------- rapor

def _fmt(r: float | None) -> str:
    return "–" if r is None else f"{r:+.2f}"


def _sim_level(p: float) -> str:
    """src/difficulty.sim_level ile aynı kural; tavan = 'bilgi yok'."""
    return "tavan" if p >= 1 else ("hard" if p < 0.40 else "medium")


def report(rows: list[dict], picked: list[dict]) -> None:
    meas = done()
    lines = ["# Zorluk sinyalleri ↔ gerçek öğrenci (TurkishMMLU)", "",
             "Veri: TurkishMMLU (Yüksel ve ark. 2024) alt kümesi, 900 lise sorusu (9 ders × 100, 5 şık); her sorunun "
             "çevrim içi platformdaki **öğrenci doğru oranı** ve ondan türetilen etiketi (kolay ≥ %42, orta %28-41, "
             "zor ≤ %27). ρ = öğrenci doğru oranıyla Spearman sıra korelasyonu: **+** sinyal yükseldikçe öğrenci daha "
             "çok bildi, **−** daha az. Zorluğu izleyen bir sinyalde beklenen: model doğru oranı p için +, çaba ve "
             "zorluk etiketi için −. |ρ| < 0,1 ≈ ilişki yok; 0,3 civarı orta; 0,5+ güçlü.", ""]
    ratio = [x["ratio"] for x in rows]
    f = [features(x) for x in rows]
    lines += [f"## 1. Metin özellikleri (kota yok, {len(rows)} soru)", "", "| Özellik | ρ | Ortalama (kolay / orta / zor) |",
              "|---|---|---|"]
    for name in f[0]:
        vals = [g[name] for g in f]
        means = " / ".join(f"{statistics.mean(v for v, x in zip(vals, rows) if x['level'] == lvl):.1f}" for lvl in LEVELS)
        lines.append(f"| {name} | {_fmt(spearman(vals, ratio))} | {means} |")
    by_subj = defaultdict(list)
    for x, g in zip(rows, f):
        by_subj[x["subject"]].append((g["uzunluk"], x["ratio"]))
    lines += ["", "Uzunluğun ders içi ρ'su (ders karışımının etkisi olmadan): "
              + ", ".join(f"{s} {_fmt(spearman([a for a, _ in v], [b for _, b in v]))}" for s, v in sorted(by_subj.items())), ""]

    got = [x for x in picked if x["id"] in meas]
    lines += [f"## 2-4. Gemma ölçümleri ({len(got)} / {len(picked)} soru ölçüldü)", ""]
    if len(got) >= 10:
        m = [meas[x["id"]] for x in got]
        r = [x["ratio"] for x in got]
        p = [e["p"] for e in m]
        th = [(e["think"], x["ratio"]) for e, x in zip(m, got) if e["think"]]
        lab = [({"easy": 0, "medium": 1, "hard": 2}[e["label"]], x["ratio"]) for e, x in zip(m, got) if e["label"]]
        # Birleşik: etiket ve çabanın sıraları toplanır (ikisi de 'zorluk arttıkça büyür'); ölçek gerektirmez
        both = [(e, x) for e, x in zip(m, got) if e["label"] and e["think"]]
        rl = _ranks([{"easy": 0, "medium": 1, "hard": 2}[e["label"]] for e, _ in both])
        rt = _ranks([e["think"] for e, _ in both])
        combo = [(a + b, x["ratio"]) for a, b, (_, x) in zip(rl, rt, both)]

        def row(name: str, pairs: list[tuple[float, float]], sign: str) -> str:
            rho, lo, hi = spearman_ci([a for a, _ in pairs], [b for _, b in pairs])
            return f"| {name} | {_fmt(rho)} | {_fmt(lo)} … {_fmt(hi)} | {sign} |"
        lines += ["| Sinyal | ρ (öğrenci doğru oranıyla) | %95 aralık | Beklenen işaret |", "|---|---|---|---|",
                  row("Benzetilmiş öğrenci p (kapalı kitap, düşünmeden, 4 örneklem)", list(zip(p, r)), "+"),
                  row("Dikkatli çözüm doğru mu (0/1)", [(float(e["careful_ok"]), x["ratio"]) for e, x in zip(m, got)], "+"),
                  row("Çaba (dikkatli çözümün düşünme token'ı)", th, "−"),
                  row("LLM zorluk etiketi (kolay 0 · orta 1 · zor 2)", lab, "−"),
                  row("Birleşik: etiket + çaba (sıra toplamı)", combo, "−"),
                  "", "Aralık sıfırı kesiyorsa ilişki bu örneklemde kanıtlanmış sayılmaz.", ""]
        lines += [f"Tavan (4 örneklemin 4'ü doğru): {sum(v >= 1 for v in p)}/{len(p)} · dikkatli çözüm doğru: "
                  f"{sum(e['careful_ok'] for e in m)}/{len(m)} · ortalama p: {statistics.mean(p):.2f}", ""]
        # Gerçek düzeye göre ortalamalar
        lines += ["| Gerçek düzey (öğrenci) | n | ort. p | tavan oranı | ort. çaba | LLM etiketi kolay / orta / zor |",
                  "|---|---|---|---|---|---|"]
        for lvl in LEVELS:
            g = [(e, x) for e, x in zip(m, got) if x["level"] == lvl]
            if not g:
                continue
            ths = [e["think"] for e, _ in g if e["think"]]
            labs = [e["label"] for e, _ in g]
            lines.append(f"| {TR[lvl]} | {len(g)} | {statistics.mean(e['p'] for e, _ in g):.2f} | "
                         f"%{100 * sum(e['p'] >= 1 for e, _ in g) / len(g):.0f} | {statistics.mean(ths) if ths else 0:.0f} | "
                         + " / ".join(str(labs.count(v)) for v in LEVELS) + " |")
        # Sistemin kuralı (difficulty.sim_level: alt sınır) ile gerçek düzey
        lines += ["", "Sistemin benzetim kuralı (yanılma varsa alt sınır, hepsi doğruysa bilgi yok) → gerçek düzey dağılımı:", "",
                  "| Benzetim sonucu | n | gerçek kolay / orta / zor | ort. öğrenci doğru oranı |", "|---|---|---|---|"]
        for s in ("tavan", "medium", "hard"):
            g = [x for e, x in zip(m, got) if _sim_level(e["p"]) == s]
            if g:
                lines.append(f"| {s if s == 'tavan' else TR[s]} | {len(g)} | "
                             + " / ".join(str(sum(x['level'] == lvl for x in g)) for lvl in LEVELS)
                             + f" | %{statistics.mean(x['ratio'] for x in g):.0f} |")
        hit = sum(1 for e, x in zip(m, got) if e["label"] == x["level"])
        lines += ["", f"LLM etiketinin gerçek düzeyi tutturma oranı: {hit}/{len(got)} (şans ≈ 1/3).", ""]
        subj = defaultdict(list)
        for e, x in zip(m, got):
            subj[x["subject"]].append((e["p"], x["ratio"]))
        lines += ["Ders bazında benzetim p'si ↔ öğrenci: "
                  + ", ".join(f"{s} {_fmt(spearman([a for a, _ in v], [b for _, b in v]))} (ort. p {statistics.mean(a for a, _ in v):.2f})"
                              for s, v in sorted(subj.items())), ""]
    else:
        lines += ["Henüz yeterli ölçüm yok.", ""]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazıldı:", OUT)


def main() -> None:
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 20
    rows = load()
    picked = sample(rows, n)
    if "--rapor" not in args:
        # --parca k/m: örneklemin k. dilimi (ayrı süreçler paralel çalışsın; darboğaz Gemma'nın yanıt süresi)
        k, m = map(int, args[args.index("--parca") + 1].split("/")) if "--parca" in args else (0, 1)
        mine = [x for i, x in enumerate(picked) if i % m == k]
        print(f"örneklem: {len(picked)} soru (ders başına {n}); bu süreç: {len(mine)} (parça {k}/{m})", flush=True)
        run(mine)
    report(rows, picked)


if __name__ == "__main__":
    main()

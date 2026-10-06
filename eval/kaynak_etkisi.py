"""Kaynak desteğinin cevap doğruluğuna etkisi (ödev gereksinimi, ROADMAP 4-B) → eval/sonuclar_kaynak_etkisi.md

Aynı soru üç koşulda cevaplatılır (Gemma 4 26B-A4B, düşünmeden, sıcaklık 0; PROMPTS §6 ve §6c):
  kaynaksız   yalnızca soru ve şıklar
  doğru       sorunun dayandığı kaynakla (Belebele: paragraf; havuz: sorunun üretildiği not sayfaları)
  yanlış      başka bir sorunun kaynağıyla (arama yanlış sayfa getirirse ne olur?)
Veri:
  Belebele-TR (Bandarkar ve ark. 2024): insan yazımı okuduğunu anlama soruları, 900'den 300 (sabit tohum)
  Havuz: doğrulanmış, kullanılabilir çoktan seçmeli sorularımız (sözel ve hesap ayrı raporlanır)
Ölçüt: doğruluk (%95 Wilson aralığı) ve eşli geçişler — kaynakla doğru ama kaynaksız yanlış ("kaynağa muhtaç"),
kaynaksız doğru ama yanlış kaynakla yanlış ("yanlış kaynağın zararı"). Ölçümler data/kaynak_etkisi/olcumler.jsonl'de;
kaldığı yerden devam eder. Maliyet: soru başına 3 Gemma çağrısı (Gemini/Groq harcanmaz).

Kullanım: python -m eval.kaynak_etkisi [--parca k/m] [--rapor]
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
import time
from collections import defaultdict

from src import config
from src.llm.router import AllModelsExhausted, call
from src.prompts import load_prompt
from src.simulate import _role

DIR = config.DATA_DIR / "kaynak_etkisi"
LOG = DIR / "olcumler.jsonl"
OUT = config.ROOT / "eval" / "sonuclar_kaynak_etkisi.md"
BELEBELE = config.DATA_DIR / "kaynak_veri" / "hf" / "facebook__belebele" / "tur_Latn" / "test_0000.parquet"
MODEL = "gemma-4-26b-a4b-it"  # 31B gece aşırı yüklüydü (basit çağrı 26-40 sn); 26B-A4B 0,7 sn
CONDITIONS = ("kaynaksiz", "dogru", "yanlis")
TR = {"kaynaksiz": "Kaynaksız", "dogru": "Doğru kaynakla", "yanlis": "Yanlış kaynakla"}
LETTERS = "ABCD"
N_BELEBELE = 300


def belebele() -> list[dict]:
    import pyarrow.parquet as pq
    rows = pq.read_table(BELEBELE).to_pylist()
    items = [{"id": f"bb{i:03d}", "set": "Belebele-TR", "group": "okuma", "question": r["question"],
              "options": [r[f"mc_answer{k}"] for k in range(1, 5)], "answer": int(r["correct_answer_num"]) - 1,
              "context": r["flores_passage"], "link": r["link"]} for i, r in enumerate(rows)]
    picked = random.Random(17).sample(items, N_BELEBELE)
    rnd = random.Random(18)
    for it in picked:  # yanlış kaynak: başka bir metinden (farklı bağlantı)
        it["wrong"] = rnd.choice([x for x in items if x["link"] != it["link"]])["context"]
    return picked


def pool() -> list[dict]:
    from src import request as R
    from src import review_store as rs
    from src.simulate import context_of
    chunks = rs.load_chunks()
    items = []
    for it in R.all_items().values():
        q = it["q"]
        if not R.usable(it) or q["type"] != "multiple_choice" or len(q.get("options") or []) != 4:
            continue
        ctx = context_of(it, chunks)
        if ctx:
            items.append({"id": it["id"], "set": "Havuz", "group": "hesap" if q.get("compute") else "sözel",
                          "doc": it["doc"], "question": q["question"], "options": q["options"],
                          "answer": q["answer_index"], "context": ctx, "level": it["difficulty"]["level"]})
    rnd = random.Random(19)
    for it in items:  # yanlış kaynak: başka bir belgeden
        it["wrong"] = rnd.choice([x for x in items if x["doc"] != it["doc"]])["context"]
    return sorted(items, key=lambda x: x["id"])


def _prompt(it: dict, cond: str) -> str:
    opts = {f"{{option_{c.lower()}}}": o for c, o in zip("abcd", it["options"])}
    p = load_prompt("6") if cond == "kaynaksiz" else load_prompt("6c").replace(
        "{context}", it["context"] if cond == "dogru" else it["wrong"])
    p = p.replace("{question}", it["question"])
    for k, v in opts.items():
        p = p.replace(k, str(v))
    return p


def _choice(text: str) -> int | None:
    m = re.search(r'"choice"\s*:\s*"?([A-D])', text or "") or re.search(r"\b([A-D])\b", (text or "").upper())
    return LETTERS.index(m.group(1)) if m else None


def done() -> dict[str, dict]:
    out = {}
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["id"]] = e
    return out


def measure(it: dict) -> dict:
    res, models = {}, []
    for cond in CONDITIONS:
        r = call(_role(MODEL), _prompt(it, cond), json_mode=True, max_tokens=60, temperature=0.0, think="minimal")
        res[cond] = _choice(r.text) == it["answer"]
        models.append(r.model)
    return {"id": it["id"], "set": it["set"], "group": it["group"], **res, "models": models, "t": time.time()}


def run(todo: list[dict]) -> None:
    have = done()
    todo = [x for x in todo if x["id"] not in have]
    DIR.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(todo, 1):
        for attempt in range(16):
            try:
                e = measure(it)
                break
            except AllModelsExhausted as ex:
                if not ex.transient or attempt == 15:
                    print(f"durdu ({ex}); {len(todo) - i + 1} soru ölçülmedi", flush=True)
                    return
                print("⏳ Gemma şu an yoğun (geçici) → 2 dk bekleniyor", flush=True)
                time.sleep(120)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"ölçüldü {i}/{len(todo)} · {it['id']} · {it['set']} {it['group']} · "
              + " ".join(f"{c}={'✓' if e[c] else '✗'}" for c in CONDITIONS), flush=True)


# ---------------------------------------------------------------- rapor

def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def report(items: list[dict]) -> None:
    meas = done()
    meta = {it["id"]: it for it in items}
    groups = defaultdict(list)
    for e in meas.values():
        if e["id"] in meta:
            groups[(e["set"], e["group"])].append(e)
    lines = ["# Kaynak desteğinin cevap doğruluğuna etkisi", "",
             "Aynı soru Gemma 4 26B-A4B'ye (düşünmeden, sıcaklık 0) üç koşulda soruldu: **kaynaksız** (PROMPTS §6), **doğru "
             "kaynakla** ve **yanlış kaynakla** (başka bir sorunun kaynağı; §6c). Belebele-TR: insan yazımı okuduğunu anlama "
             "soruları (300). Havuz: sistemin doğrulanmış çoktan seçmeli soruları; kaynak = sorunun üretildiği not sayfaları. "
             "Doğruluğun yanında %95 Wilson aralığı.", "",
             "| Veri | n | Kaynaksız | Doğru kaynakla | Yanlış kaynakla | Kaynağa muhtaç¹ | Yanlış kaynağın zararı² |",
             "|---|---|---|---|---|---|---|"]
    for (s, g), es in sorted(groups.items()):
        n = len(es)
        cells = []
        for c in CONDITIONS:
            k = sum(e[c] for e in es)
            lo, hi = wilson(k, n)
            cells.append(f"%{100 * k / n:.0f} ({100 * lo:.0f}–{100 * hi:.0f})")
        need = sum(e["dogru"] and not e["kaynaksiz"] for e in es)
        harm = sum(e["kaynaksiz"] and not e["yanlis"] for e in es)
        lines.append(f"| {s} · {g} | {n} | " + " | ".join(cells) + f" | %{100 * need / n:.0f} | %{100 * harm / n:.0f} |")
    lines += ["", "¹ Doğru kaynakla doğru, kaynaksız yanlış cevaplanan soruların oranı: cevabı gerçekten kaynağa bağlı sorular. "
              "Havuzda düşükse sorular genel bilgiyle cevaplanabiliyor (ders notuna özgü değil).",
              "² Kaynaksız doğru cevaplanıp yanlış kaynakla yanlışa dönen soruların oranı: arama yanlış sayfa getirirse doğruluk "
              "ne kadar düşer.", ""]
    pool_es = [e for e in meas.values() if e["set"] == "Havuz" and e["id"] in meta]
    if pool_es:
        by_doc, by_lvl = defaultdict(list), defaultdict(list)
        for e in pool_es:
            by_doc[meta[e["id"]]["doc"]].append(e)
            by_lvl[meta[e["id"]]["level"]].append(e)
        lines += ["## Havuz: belgeye ve etkin zorluğa göre", "", "| Grup | n | Kaynaksız | Doğru kaynakla | Kaynağa muhtaç |",
                  "|---|---|---|---|---|"]
        for name, d in [(f"belge: {k}", v) for k, v in sorted(by_doc.items())] + \
                       [(f"zorluk: {k}", v) for k, v in sorted(by_lvl.items())]:
            n = len(d)
            lines.append(f"| {name} | {n} | %{100 * sum(e['kaynaksiz'] for e in d) / n:.0f} | "
                         f"%{100 * sum(e['dogru'] for e in d) / n:.0f} | "
                         f"%{100 * sum(e['dogru'] and not e['kaynaksiz'] for e in d) / n:.0f} |")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazıldı:", OUT)


def main() -> None:
    args = sys.argv[1:]
    items = belebele() + pool()
    if "--rapor" not in args:
        k, m = map(int, args[args.index("--parca") + 1].split("/")) if "--parca" in args else (0, 1)
        mine = [x for i, x in enumerate(items) if i % m == k]
        print(f"{len(items)} soru (Belebele {sum(x['set'] == 'Belebele-TR' for x in items)}, havuz "
              f"{sum(x['set'] == 'Havuz' for x in items)}); bu süreç: {len(mine)} (parça {k}/{m})", flush=True)
        run(mine)
    report(items)


if __name__ == "__main__":
    main()

"""Zorluk ölçümü pilotu (ROADMAP 8, LITERATURE §8) → eval/sonuclar_zorluk.md

Soru: zorluk etiketi iddia değil ölçüm olabilir mi, ve yeni tanımlarla üretim istenen düzeyi tutuyor mu?
  A. Kullanıcının TYT "zor" isteği (10 hesap sorusu): üretecin iddiası ve yapı (ayrı kural sayısı, adım, işlem);
     Claude'un elle değerlendirmesiyle karşılaştırma (gerçek öğrenci verisi DEĞİL)
  C. Sözel belgelerden havuz örneklemi: benzetilmiş öğrenci (src/simulate.py) + yapı
  D1. Sözel merdiven: aynı birimlerden yeni tanımlarla kolay / orta / zor üretim → ölçer sırayı görüyor mu?
  D2. Hesap merdiveni: aynı TYT birimlerinden kolay / orta / zor → ayrı kural ve adım sayısı artıyor mu?
  E. Zorlaştırma (PROMPTS §2d): orta ölçülen sözel sorular → zor; önce/sonra
Merdiven ve zorlaştırma soruları yalnızca kod kontrolünden geçer (LLM doğrulaması yok: burada ölçülen zorluk).
Maliyet: ~7 Gemini (generate_batch), sözel soru başına 5 Gemma çağrısı. Yanıtlar önbellekte, ölçümler
data/review/difficulty.jsonl'de; yeniden çalıştırma kota harcamaz.

Kullanım: python -m eval.zorluk_olcumu [--uretimsiz]   (--uretimsiz: yalnızca A ve C; Gemini yoğunken, kota yok)
"""

from __future__ import annotations

import random
import statistics
import sys

from src import config
from src import difficulty as D
from src import request as R
from src import review_store as rs
from src import simulate as S
from src.generation.generate import build_units, evolve_request, generate_request, math_units
from src.pipeline import patient

OUT = config.ROOT / "eval" / "sonuclar_zorluk.md"
TYT_REQ = "20261005-225845-db0c"
# Claude'un elle değerlendirmesi (2026-10-05 sohbeti; gerçek öğrenci verisi DEĞİL)
MANUAL = {"8885b8611136": "easy", "55719017d153": "easy", "1946f56876f3": "easy", "a58127538c75": "easy",
          "ad7769c69170": "medium", "f127a4a4f7b9": "medium", "5a13ca7f9726": "medium", "8f963875cfac": "medium",
          "762c095dc33f": "medium", "ce1147580173": "hard"}
TR = {"easy": "kolay", "medium": "orta", "hard": "zor", None: "–"}
TEXT_DOCS = ["4_ENERJİ, TARIM, BESLENME", "7.Hafta Sunu Dosyası", "Hafta_02_Bilgisayar_Performansina_Giris"]


def _pick(items: list[dict], n: int, seed: int = 7) -> list[dict]:
    """İddiaya göre dengeli örneklem (her düzeyden sırayla)."""
    rnd = random.Random(seed)
    by = {lvl: [it for it in items if it["difficulty"]["claim"] == lvl] for lvl in D.LEVELS}
    for v in by.values():
        rnd.shuffle(v)
    out = []
    while len(out) < n and any(by.values()):
        for lvl in ("hard", "medium", "easy"):
            if by[lvl] and len(out) < n:
                out.append(by[lvl].pop())
    return out


def _ladder(units: list[dict], worked: bool) -> list[dict]:
    out = []
    for lvl in D.LEVELS:
        spec = [(u, 1, ["short_answer"] if worked else ["multiple_choice"]) for u in units]
        # Gemini yoğunsa (503) bekleyip yeniden dener; daha zayıf modele geçilmez (pipeline.patient)
        for it in patient(generate_request, spec, "tr", lvl, worked=worked, what=f"merdiven {lvl}"):
            if it["check"]["status"] != "rejected":
                it["id"] = rs.question_id(it)
                out.append(it)
    return D.apply(out)


def _units_text() -> list[dict]:
    out = []
    for doc in TEXT_DOCS:
        us = [u for u in build_units(doc) if len(u["text"]) > 900]
        out.append(random.Random(doc).choice(us))
    return out


def _cell(it: dict, sims: dict) -> str:
    d, f = it["difficulty"], D.features(it["q"], it.get("check"))
    m = sims.get(it["id"]) if S.simulable(it) else None
    q = it["q"]["question"].replace("|", "/").replace("\n", " ")
    sim = f"{m['p']:.2f} / {m.get('think') or '–'}" if m else "–"
    req = TR[it.get("requested_difficulty")] if it.get("requested_difficulty") else "–"
    man = TR[MANUAL[it["id"]]] if it["id"] in MANUAL else "–"
    return (f"| {q[:64]}{'…' if len(q) > 64 else ''} | {req} | {TR[d['claim']]} | {f['facts']} / {f['steps']} / {f['ops'] if f['ops'] is not None else '–'} "
            f"| {sim} | **{TR[d['level']]}** {('(tavan: ' + d['cap_why'] + ')') if d.get('cap_why') else ''} | {man} |")


def _table(title: str, items: list[dict], sims: dict, note: str = "") -> list[str]:
    lines = [f"## {title} ({len(items)} soru)", ""] + ([note, ""] if note else [])
    lines += ["| Soru | İstenen | Üretecin iddiası | Bilgi / adım / işlem | p / çaba | Etkin düzey | Elle |",
              "|---|---|---|---|---|---|---|"] + [_cell(it, sims) for it in items]
    req = [it for it in items if it.get("requested_difficulty")]
    if req:
        by = {lvl: [it for it in req if it["requested_difficulty"] == lvl] for lvl in D.LEVELS}
        parts = []
        for lvl, g in by.items():
            if not g:
                continue
            ps = [sims[it["id"]]["p"] for it in g if it["id"] in sims and S.simulable(it)]
            hit = sum(it["difficulty"]["level"] == lvl for it in g)
            parts.append(f"{TR[lvl]}: tutan {hit}/{len(g)}, bilgi ort. {statistics.mean(D.features(it['q'], it.get('check'))['facts'] for it in g):.1f}"
                         + (f", p ort. {statistics.mean(ps):.2f}" if ps else ""))
        lines += ["", "İstenen düzeye göre: " + " · ".join(parts)]
    return lines + [""]


def main() -> None:
    chunks = rs.load_chunks()
    pool = [it for it in R.all_items().values() if R.usable(it)]
    A = [it for it in pool if it.get("request") == TYT_REQ or it["id"] in MANUAL]
    C = _pick([it for it in pool if it["doc"] in TEXT_DOCS and S.simulable(it)], 12)
    print("C · sözel havuz:", len(C), flush=True)
    S.run(C, chunks, log=lambda s: print("  " + s, flush=True), waits=15)
    gen = "--uretimsiz" not in sys.argv
    D1, D2 = [], []
    if gen:
        D1 = _ladder(_units_text(), worked=False)
        print("D1 · sözel merdiven:", len(D1), flush=True)
        S.run(D1, chunks, log=lambda s: print("  " + s, flush=True), waits=15)
        rnd = random.Random(5)
        mu = math_units(build_units("tyt-matematik"))
        D2 = _ladder(rnd.sample(mu, min(3, len(mu))), worked=True)
        print("D2 · hesap merdiveni:", len(D2), flush=True)
    sims = D.measurements()
    D.apply(C)
    mid = [it for it in C if it["q"]["difficulty"] == "medium"][:3]
    E = []
    if mid and gen:
        by_doc = {it["doc"]: it for it in pool if it["doc"] in TEXT_DOCS}
        pairs = []
        for it in mid:
            other = next((x for d, x in by_doc.items() if d != it["doc"]), it)
            pairs.append((it, {"chunks": [chunks[c] for c in other["chunk_ids"] if c in chunks]}))
        E = [x for x in patient(evolve_request, pairs, "tr", "hard", what="zorlaştırma")
             if x["check"]["status"] != "rejected"]
        for x in E:
            x["id"] = rs.question_id(x)
        S.run(E, chunks, log=lambda s: print("  " + s, flush=True), waits=15)
        D.apply(E)
    sims = D.measurements()
    for g in (A, C, D1, D2, E):
        D.apply(g)

    lines = ["# Zorluk ölçümü pilotu", "",
             "Etkin düzey = ölçüm (sözel ÇS ve D/Y'de benzetilmiş öğrenci: Gemma 4 sınıfı, kaynak açık, çalışma yazmadan; "
             "p = doğru oranı; hepsi doğruysa tavan, bilgi yok; çaba = dikkatli çözümün düşünme token'ı, yalnızca kayıt) ya da üretecin iddiası; ikisine de yapı tavanı "
             "(src/difficulty.py): **zor için en az iki ayrı bilgi/kural ya da çok adımlı hesap**. Hesap ve sözel "
             "kısa cevap benzetilmez (Gemma 4 lise matematiğinde doyuyor; kısa cevap metin eşleşmesiyle puanlanıyor, PROMPTS §8). \"Bilgi\" = notta bulunan ayrı kanıt alıntısı.",
             ""]
    lines += _table("A · TYT 'zor' isteği (hesap)", A, sims, "Elle sütunu: Claude'un değerlendirmesi, öğrenci verisi değil.")
    lines += _table("C · Sözel havuz örneklemi", C, sims)
    if gen:
        lines += _table("D1 · Sözel merdiven (yeni tanımlarla üretim)", D1, sims)
        lines += _table("D2 · Hesap merdiveni (yeni tanımlarla üretim)", D2, sims)
    else:
        lines += ["_D1, D2, E (üretim gerektiren gruplar) bu çalıştırmada yok: `--uretimsiz`._", ""]
    if E:
        lines += _table("E · Zorlaştırma (orta → zor, PROMPTS §2d)", E, sims,
                        "Kaynak: C'de orta ölçülen sorular, başka bir belgenin notuyla birleştirildi.")
    man = [it for it in A if it["id"] in MANUAL]
    agree = sum(it["difficulty"]["level"] == MANUAL[it["id"]] for it in man)
    claim_agree = sum(it["difficulty"]["claim"] == MANUAL[it["id"]] for it in man)
    lines += [f"A'da elle değerlendirmeyle uyum: etkin düzey {agree}/{len(man)}, üretecin iddiası {claim_agree}/{len(man)}, "
              f"eski zorla yazılmış etiket ('zor') {sum(MANUAL[it['id']] == 'hard' for it in man)}/{len(man)}.", ""]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("yazıldı:", OUT)


if __name__ == "__main__":
    main()

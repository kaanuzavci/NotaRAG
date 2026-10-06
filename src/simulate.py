"""Benzetilmiş öğrenci: sözel soruların zorluğunu ölçmek (PROMPTS.md §8, LITERATURE §8).

Zayıf/orta modellerden bir "sınıf" (Gemma 4) her soruyu kaynak sayfası önündeyken (açık kitap: ezber değil, sorunun
istediği düşünme ölçülür) ve çalışma yazmadan (thinking_level="minimal") cevaplar → doğru oranı p. Ayrıca bir
"dikkatli öğrenci" (thinking_level="high") soruyu çözerken kaç düşünme token'ı harcadığını söyler → çaba.
Literatür: güçlü modeller zorlanan öğrenciyi taklit edemiyor, zayıf modeller daha iyi (Acquaye ve ark. 2026);
belirsizlik/tutarlılık zorluğun güçlü sinyali (Zotos ve ark. 2025). Etiket: src/difficulty.sim_level.

Hesap soruları benzetilmez: Gemma 4 lise matematiğinde ya kafadan aritmetiğe takılıyor ya da (karalama kâğıdıyla)
her şeyi çözüyor (2026-10-05 denemesi, PROMPTS.md §8) → onların zorluğu yapıdan gelir (ayrı kural sayısı, adım).
Sözel kısa cevap da benzetilmez: puanlama metin eşleşmesi, doğru ama farklı sözcüklü cevabı yanlış sayıyor
(2026-10-06 pilotu). Kural tek yerde: difficulty.measurable.

Her örneklem şıkları karıştırır ve öğrenci numarası taşır → örneklemler bağımsız, yanıtlar önbellekte (yeniden
çalıştırma kota harcamaz). Sonuç data/review/difficulty.jsonl'e yazılır (soru kimliğine bağlı, yalnızca eklenir).

Kullanım: python -m src.simulate --ids a1b2c3,d4e5f6   |   python -m src.simulate --doc 7.Hafta --limit 20
"""

from __future__ import annotations

import random
import re
import statistics
import sys

from src import difficulty as D
from src.llm.models import ROLES
from src.llm.router import call
from src.prompts import load_prompt

# (model, örneklem sayısı) — hızlı cevap; ve çaba ölçümü için dikkatli öğrenci
CLASS = [("gemma-4-26b-a4b-it", 2), ("gemma-4-31b-it", 2)]
CAREFUL = "gemma-4-26b-a4b-it"
LETTERS = "ABCD"
FORMAT = {"multiple_choice": "Reply with only the letter of your choice (A, B, C or D).",
          "true_false": "Reply with only one word: Doğru or Yanlış.",
          "short_answer": "Reply with only your final answer (a number, an expression or a few words)."}


def _role(model: str) -> str:
    """Ölçüm rolü (içerik üretmez, doğrulamaz): model meşgulse (503) örneklem sınıftaki öbür modele geçer."""
    ROLES[f"_sim_{model}"] = [model] + [m for m, _ in CLASS if m != model]
    return f"_sim_{model}"


def simulable(it: dict) -> bool:
    return D.measurable(it["q"])


def _prompt(it: dict, context: str, student: int) -> tuple[str, list[int] | None]:
    q = it["q"]
    perm = None
    options = ""
    if q["type"] == "multiple_choice":
        perm = list(range(len(q["options"])))
        random.Random(f"{it.get('id')}|{student}").shuffle(perm)
        options = "\n".join(f"{LETTERS[i]}) {q['options'][j]}" for i, j in enumerate(perm))
    p = (load_prompt("8").replace("{student}", str(student)).replace("{context}", context)
         .replace("{question}", q["question"]).replace("{options}", options).replace("{answer_format}", FORMAT[q["type"]]))
    return p, perm


def correct(it: dict, reply: str, perm: list[int] | None) -> bool:
    """Öğrencinin cevabı doğru mu? Çoktan seçmelide ilk şık harfi; D/Y'de doğru/yanlış; kısa cevapta puanlama kuralı."""
    q, text = it["q"], (reply or "").strip()
    if q["type"] == "multiple_choice":
        m = re.search(r"\b([A-D])\b", text.upper())
        return bool(m and perm and perm[LETTERS.index(m.group(1))] == q["answer_index"])
    if q["type"] == "true_false":
        t = text.replace("İ", "i").lower()
        said = "true" if re.search(r"doğru|dogru|true", t) else ("false" if re.search(r"yanlış|yanlis|false", t) else "")
        return said == q["answer"]
    from src.grading import grade_short
    computed = it.get("check", {}).get("computed", {}).get("value") if q.get("compute") else None
    return grade_short(text, q["answer"], computed)


def context_of(it: dict, chunks: dict[str, dict]) -> str:
    return "\n\n".join(f"[s.{chunks[c]['page']}] {chunks[c]['text']}" for c in it.get("chunk_ids", []) if c in chunks)


def measure(it: dict, chunks: dict[str, dict]) -> dict:
    """Bir sorunun benzetim ölçümü: {id, kind: 'sim', p, k, think, careful_ok, answers, models}."""
    ctx = context_of(it, chunks)
    answers, ok, used, student = [], [], [], 0
    for model, k in CLASS:
        for _ in range(k):
            student += 1
            prompt, perm = _prompt(it, ctx, student)
            r = call(_role(model), prompt, max_tokens=60, temperature=0.8, think="minimal")
            answers.append(r.text[:40])
            used.append(r.model)
            ok.append(correct(it, r.text, perm))
    prompt, perm = _prompt(it, ctx, 0)
    careful = call(_role(CAREFUL), prompt, max_tokens=6000, temperature=0.0, think="high")
    entry = {"id": it["id"], "kind": "sim", "p": round(sum(ok) / len(ok), 2), "k": len(ok),
             "think": careful.thoughts or None, "careful_ok": correct(it, careful.text, perm), "answers": answers,
             "models": used, "mode": "open_book_minimal"}
    D.record(entry)
    return entry


def run(items: list[dict], chunks: dict[str, dict], skip_measured: bool = True, log=print) -> list[dict]:
    """Ölçülmemiş ölçülebilir soruları ölç (hesap ve sözel kısa cevap atlanır: difficulty.measurable)."""
    done = D.measurements() if skip_measured else {}
    todo = [it for it in items if simulable(it) and it["id"] not in done]
    out = []
    for i, it in enumerate(todo, 1):
        e = measure(it, chunks)
        out.append(e)
        log(f"ölçüldü {i}/{len(todo)} · {it['id']} · p={e['p']} çaba={e['think']} → {D.sim_level(e['p'], e['think'])}")
    return out


def main() -> None:
    from src import request as R
    from src import review_store as rs
    args = sys.argv[1:]
    items = [it for it in R.all_items().values() if R.usable(it)]
    if "--ids" in args:
        want = set(args[args.index("--ids") + 1].split(","))
        items = [it for it in items if it["id"] in want]
    if "--doc" in args:
        items = [it for it in items if it["doc"] == args[args.index("--doc") + 1]]
    if "--limit" in args:
        items = items[: int(args[args.index("--limit") + 1])]
    res = run(items, rs.load_chunks())
    if res:
        print(f"{len(res)} soru ölçüldü; ortalama p={statistics.mean(e['p'] for e in res):.2f}")


if __name__ == "__main__":
    main()

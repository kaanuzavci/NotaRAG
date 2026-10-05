"""Hesap sorusu kod kontrolünün duyarlılığı (API yok, SymPy): kontrolden geçmiş hesap sorularına kasıtlı hata
eklenir, kontrolün her birini yakalayıp yakalamadığı ölçülür.

Bozulmalar (yalnızca çoktan seçmeli hesap soruları):
  wrong_key      anahtar başka bir şıkka kaydırılır                      → compute_mismatch beklenir
  two_correct    bir çeldiricinin metni ve değeri doğru sonuçla değiştirilir → compute_two_correct
  text_mismatch  doğru şıkkın METNİ yanlış bir sayıya değiştirilir (değer aynı kalır) → compute_text_mismatch
Ayrıca bozulmamış soruların yeniden kontrolü: hiçbiri reddedilmemeli (yanlış alarm).

Kullanım: python -m eval.compute_check [data/questions/tyt-matematik_tr.jsonl]
Çıktı:    eval/sonuclar_hesap_kontrol.md + .json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.generation.compute import judge, reasons

EXPECT = {"wrong_key": "compute_mismatch", "two_correct": "compute_two_correct", "text_mismatch": "compute_text_mismatch"}


def corrupt(q: dict, kind: str) -> dict:
    q = json.loads(json.dumps(q))
    k = q["answer_index"]
    d = (k + 1) % 4
    if kind == "wrong_key":
        q["answer_index"] = d
        q["answer"] = q["options"][d]
    elif kind == "two_correct":
        q["options"][d], q["option_values"][d] = q["options"][k] + " ", q["option_values"][k]
    elif kind == "text_mismatch":
        # Doğru şıkkın metnini bir çeldiricinin metniyle değiştir (değeri doğru kalır): öğrenci yanlış sayıyı görür
        q["options"][k] = q["options"][d] + " "
    return q


def main(path: str) -> None:
    items = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    base = [i["q"] for i in items if i["q"].get("compute") and i["q"]["type"] == "multiple_choice"
            and i["check"]["status"] != "rejected"]
    clean_fp = sum(bool(reasons(judge(q))[0]) for q in base)
    rows = {}
    for kind, want in EXPECT.items():
        caught = sum(want in reasons(judge(corrupt(q, kind)))[0] for q in base)
        rows[kind] = {"caught": caught, "total": len(base), "expected_reason": want}
    out = {"source": path, "n_clean": len(base), "false_alarms_on_clean": clean_fp, "corruptions": rows}
    Path("eval/sonuclar_hesap_kontrol.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Hesap sorusu kod kontrolü — duyarlılık ({Path(path).name})", "",
          f"Kontrolden geçmiş {len(base)} çoktan seçmeli hesap sorusu; her birine ayrı ayrı kasıtlı hata eklendi.", "",
          "| Bozulma | Yakalanan | Beklenen red nedeni |", "|---|---|---|"]
    md += [f"| {k} | {v['caught']}/{v['total']} | `{v['expected_reason']}` |" for k, v in rows.items()]
    md += ["", f"Bozulmamış sorularda yanlış alarm: **{clean_fp}/{len(base)}**"]
    Path("eval/sonuclar_hesap_kontrol.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/questions/tyt-matematik_tr.jsonl")

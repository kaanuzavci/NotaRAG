"""Soru üretim pilotu: aynı belgeden birden çok modelle soru üretip karşılaştırır.

Kullanım: python -m src.generation.pilot "<belge>" model1,model2 [çıktı_dili] [birim_sınırı]
   ör.: python -m src.generation.pilot english qwen/qwen3.8-27b tr 12   (İngilizce slayt → Türkçe soru)
Çıktı: data/pilot/<model>.jsonl ve data/pilot/rapor.md (VS Code'da okunabilir)
"""

import json
import sys
from collections import Counter

from src import config
from src.generation.generate import generate_doc
from src.llm.models import ROLES

TYPE_TR = {"multiple_choice": "Çoktan seçmeli", "short_answer": "Kısa cevap", "true_false": "Doğru/Yanlış"}
LETTERS = "ABCD"


def _stats(items: list[dict]) -> dict:
    ok = [i for i in items if i["check"]["status"] != "rejected"]
    mcq = [i for i in items if i["q"].get("type") == "multiple_choice" and "generated_answer_index" in i["check"]]
    return {
        "üretilen": len(items),
        "kontrolden geçen": len(ok),
        "red nedenleri": dict(Counter(r for i in items for r in i["check"]["rejected"])),
        "uyarılar (geçenlerde)": dict(Counter(f for i in ok for f in i["check"]["flags"])),
        "tipler": dict(Counter(TYPE_TR.get(i["q"].get("type"), "?") for i in items)),
        "bloom": dict(Counter(i["q"].get("bloom_level", "?") for i in ok)),
        "LLM'in doğru şık konumu (karıştırmadan önce)": dict(Counter(LETTERS[i["check"]["generated_answer_index"]] for i in mcq)),
    }


def _md_question(n: int, it: dict) -> str:
    q, c = it["q"], it["check"]
    status = "❌ RED: " + ", ".join(c["rejected"]) if c["status"] == "rejected" else "✅ kontrollerden geçti"
    flags = f" · ⚠️ {', '.join(c['flags'])}" if c["flags"] else ""
    lines = [f"**{n}. {q.get('question', '(şema dışı)')}**  ",
             f"<sub>{TYPE_TR.get(q.get('type'), '?')} · {q.get('bloom_level', '?')} · {q.get('difficulty', '?')} · "
             f"{it['unit'][:50]} · {status}{flags}</sub>", ""]
    if q.get("type") == "multiple_choice" and q.get("options"):
        for i, o in enumerate(q["options"]):
            mark = " ✔" if i == q.get("answer_index") else ""
            lines.append(f"- {LETTERS[i]}) {o}{mark}")
    else:
        ans = {"true": "Doğru", "false": "Yanlış"}.get(str(q.get("answer", "")).lower(), q.get("answer"))
        lines.append(f"- Cevap: {ans}")
    page = f" (s.{c['evidence_page']})" if c.get("evidence_page") else ""
    lines.append(f"- Kanıt{page}: _\"{q.get('evidence_quote', '')}\"_")
    return "\n".join(lines) + "\n"


def main() -> None:
    doc = sys.argv[1] if len(sys.argv) > 1 else "7.Hafta Sunu Dosyası"
    models = (sys.argv[2] if len(sys.argv) > 2 else "openai/gpt-oss-120b,qwen/qwen3.8-27b").split(",")
    lang = sys.argv[3] if len(sys.argv) > 3 else None
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
    out = config.DATA_DIR / "pilot"
    out.mkdir(parents=True, exist_ok=True)
    report = [f"# Soru Üretim Pilotu — {doc}\n"]
    summary = []
    for model in models:
        ROLES["_pilot"] = [model]  # pilot: her model tek başına, yedeğe düşmeden
        print(f"→ {model} …", flush=True)
        items = generate_doc(doc, role="_pilot", limit_units=limit, output_language=lang)
        slug = model.replace("/", "_") + (f"_{doc}_{lang}" if lang else "")
        (out / f"{slug}.jsonl").write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
        st = _stats(items)
        summary.append((model, st))
        print(json.dumps(st, ensure_ascii=False, indent=1))
        report.append(f"\n## {model}\n")
        report += [f"- **{k}:** {v}" for k, v in st.items()]
        report.append("")
        report += [_md_question(n, it) for n, it in enumerate(items, 1)]
    name = f"rapor_{doc}_{lang}.md" if lang else "rapor.md"
    (out / name).write_text("\n".join(report), encoding="utf-8")
    print(f"\nRapor: {out / name}")


if __name__ == "__main__":
    main()

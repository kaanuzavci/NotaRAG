"""Doğrulayıcı duyarlılık testi: doğrulayıcı, KASITLI olarak bozulmuş soruları yakalıyor mu?

"Doğrulanmış soruların hepsi geçti" sonucu, doğrulayıcı her şeye 'doğru' diyorsa anlamsızdır.
Bu yüzden doğrulanmış sorulardan, cevabı bilinen bozuk kopyalar üretilir:
  wrong_key      : çoktan seçmelide anahtar bir çeldiriciye kaydırılır        → verified OLMAMALI
  two_correct    : bir çeldirici doğru şıkkın eş anlamlısıyla değiştirilir     → verified OLMAMALI
  tf_flip        : doğru/yanlış cevabı ters çevrilir                           → verified OLMAMALI
  not_in_context : gerçekte doğru ama slaytta OLMAYAN ifade (dış bilgi)        → rejected OLMALI
  short_wrong    : kısa cevap yanlış bir değerle değiştirilir                  → verified OLMAMALI
Ayrıca 'yalnızca şıklar' testi (PROMPTS.md §6b) tüm çoktan seçmeli sorulara uygulanır.

Kullanım: python -m src.verification.sensitivity data/pilot/<model>_dogrulama.jsonl [doğrulayıcı_model]
  doğrulayıcı_model verilirse YALNIZCA o model doğrulayıcı olarak test edilir (aday modeli kalite kapısından geçirmek için).
"""

from __future__ import annotations

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

from src import config
from src.llm.router import call
from src.verification.verify import LETTERS, _fill, _json, verifier_role, verify_item

# Slaytlarda (YZ, 7. hafta) geçmeyen ama gerçekte doğru ifadeler: dış bilgiyle "doğru" denirse doğrulayıcı hatalı.
NOT_IN_CONTEXT = [
    "Genetik algoritmalar ilk olarak John Holland tarafından önerilmiştir.",
    "Rulet tekerleği seçimi, uygunluk değeri negatif olan bireyler için de doğrudan kullanılabilir.",
    "Genetik algoritmalarda mutasyon oranı genellikle çaprazlama oranından çok daha küçük seçilir.",
]


def corruptions(item: dict) -> list[tuple[str, dict, str]]:
    """(tür, bozuk_öğe, beklenen) listesi; beklenen: 'not_verified' | 'rejected'"""
    q, out = item["q"], []
    if q["type"] == "multiple_choice":
        a = copy.deepcopy(item)
        a["q"]["answer_index"] = (q["answer_index"] + 1) % 4
        a["q"]["answer"] = q["options"][a["q"]["answer_index"]]
        out.append(("wrong_key", a, "not_verified"))
        b = copy.deepcopy(item)
        j = (q["answer_index"] + 2) % 4
        b["q"]["options"][j] = "Başka bir deyişle: " + q["options"][q["answer_index"]]
        out.append(("two_correct", b, "not_verified"))
    elif q["type"] == "true_false":
        c = copy.deepcopy(item)
        c["q"]["answer"] = "false" if q["answer"] == "true" else "true"
        out.append(("tf_flip", c, "not_verified"))
    elif q["type"] == "short_answer":
        d = copy.deepcopy(item)
        d["q"]["answer"] = "Tek-kriterli ve doğrusal olarak formülize edilir."
        out.append(("short_wrong", d, "not_verified"))
    return out


def choices_only(item: dict) -> bool:
    q = item["q"]
    opts = {f"option_{c.lower()}": o for c, o in zip(LETTERS, q["options"])}
    r = call(verifier_role(item["model"]), _fill("6b", **opts), json_mode=True, max_tokens=300)
    return str(_json(r.text).get("choice", "")).strip().upper()[:1] == LETTERS[q["answer_index"]]


LIGHT = False


def main() -> None:
    global LIGHT
    if len(sys.argv) > 2:
        LIGHT = True  # aday test edilirken yalnızca karar veren ana doğrulama (§4) ölçülür  # aday doğrulayıcıyı tek başına test et
        from src.llm.models import ROLES
        ROLES["verify"] = [sys.argv[2]]
        print(f"Test edilen doğrulayıcı: {sys.argv[2]}")
    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    items = [json.loads(x) for x in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if x.strip()]
    good = [i for i in items if i["verification"]["label"] == "verified"]
    caught, total, rows = defaultdict(int), defaultdict(int), []

    for it in good:
        for kind, bad, expect in corruptions(it):
            v = verify_item(bad, chunks, light=LIGHT)
            ok = v["label"] != "verified" if expect == "not_verified" else v["label"] == "rejected"
            total[kind] += 1
            caught[kind] += ok
            rows.append((kind, ok, it["q"]["question"][:70], v["label"], v["why"]))

    # Dışarıdan doğru ama slaytta olmayan D/Y ifadeleri (ilk doğrulanmış sorunun bağlamıyla)
    base = next(i for i in good if i["q"]["type"] != "true_false")
    for s in NOT_IN_CONTEXT:
        it = copy.deepcopy(base)
        it["q"] = {"question": s, "type": "true_false", "answer": "true", "evidence_quote": "-"}
        v = verify_item(it, chunks, light=LIGHT)
        ok = v["label"] == "rejected"
        total["not_in_context"] += 1
        caught["not_in_context"] += ok
        rows.append(("not_in_context", ok, s[:70], v["label"], v["why"]))

    mcq = [i for i in good if i["q"]["type"] == "multiple_choice"]
    cue = [] if LIGHT else [i for i in mcq if choices_only(i)]

    from src import config as _cfg
    verifier = sys.argv[2] if len(sys.argv) > 2 else "openai/gpt-oss-120b"
    out = _cfg.ROOT / "eval" / "sonuclar_duyarlilik.json"
    allres = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    allres[verifier] = {"kinds": {k: [caught[k], total[k]] for k in total}, "light": LIGHT}
    out.write_text(json.dumps(allres, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nBozulma türü        yakalanan / toplam")
    for k in total:
        print(f"  {k:16} {caught[k]:3} / {total[k]}")
    print(f"  {'TOPLAM':16} {sum(caught.values()):3} / {sum(total.values())}")
    print(f"\nYalnızca şıklar testi: {len(cue)}/{len(mcq)} soruda soru görülmeden doğru şık bulundu")
    for i in cue:
        print("   •", i["q"]["question"][:90])
    print("\nKaçırılanlar:")
    for kind, ok, text, label, why in rows:
        if not ok:
            print(f"   [{kind}] {text} → {label} ({why})")


if __name__ == "__main__":
    main()

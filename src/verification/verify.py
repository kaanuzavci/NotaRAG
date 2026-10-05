"""Kör doğrulama (ROADMAP Adım 7, PROMPTS.md §4a-4d ve §6).

Doğrulayıcı, soruyu ÜRETEN modelden farklı bir model ailesidir ve cevap anahtarını görmez:
  çoktan seçmeli → şıklardan birini seçer (+ başka şık da destekleniyor mu?)
  doğru/yanlış    → SUPPORTED / CONTRADICTED / NOT_IN_CONTEXT
  kısa cevap      → kendi cevabını yazar; kodla ya da hakemle (§4d) karşılaştırılır
Ek olarak çoktan seçmeli sorular bağlamsız da sorulur (§6): doğru bilinirse 'low_source_dependence'.

Sonuç etiketleri: verified | needs_review | rejected  (+ gerekçe)
"""

from __future__ import annotations

import json
import re

from rapidfuzz import fuzz

from src.llm.models import ROLES
from src.llm.router import call
from src.prompts import load_prompt
from src.textnorm import normalize_for_match as norm

LETTERS = "ABCD"
CHECK_TR = {  # hesap sorusu red nedenleri (src/generation/compute.py) arayüzde okunur olsun
    "compute_error": "SymPy ifadesi hesaplanamadı",
    "compute_mismatch": "anahtar, kodun hesapladığı sonuç değil",
    "compute_two_correct": "başka bir şık da doğru sonuca eşit",
    "compute_text_mismatch": "şık metnindeki sayı şıkkın değeriyle çelişiyor",
    "all_none_option": "'hepsi / hiçbiri' şıkkı (soru yazım hatası)",
}


# Aynı şirketin farklı adlı modelleri aynı aile (Gemma = Google = Gemini; *stral = Mistral). Ad önekine bakan
# kural bunları ayrı aile sanıp aile kuralını sessizce çiğnerdi (Gemma 4 aday olmadan önce, 2026-10-05).
_FAMILY_ALIASES = {"gemma": "gemini", "magistral": "mistral", "ministral": "mistral", "pixtral": "mistral",
                   "codestral": "mistral", "devstral": "mistral"}


def family(model: str) -> str:
    """'openai/gpt-oss-120b' → 'gpt-oss', 'qwen/qwen3.8-27b' → 'qwen', 'gemma-4-31b-it' → 'gemini'"""
    name = model.split("/")[-1]
    fam = re.split(r"[\d.-]", name, maxsplit=1)[0] if not name.startswith("gpt-oss") else "gpt-oss"
    return _FAMILY_ALIASES.get(fam, fam)


def verifier_role(generator: str, allow_candidates: bool = False, task: str = "verify") -> str:
    """Üreticiyle aynı aileden olmayan ONAYLI doğrulayıcılardan geçici bir rol zinciri kurar.

    Onaylı doğrulayıcı yoksa hata verir; kalite testinden geçmemiş bir modele sessizce düşmez.
    allow_candidates=True yalnızca model karşılaştırma pilotları içindir (ör. gpt-oss'un ürettiği soruları qwen doğrular).
    task="verify_math": hesap sorusunun kör çözümü (§4e) için ayrıca onaylanmış modeller.
    """
    from src.llm.models import CANDIDATES

    pool = list(ROLES[task])
    if allow_candidates:
        pool += list(CANDIDATES.get(task, {})) + list(ROLES["generate"])
    chain = list(dict.fromkeys(m for m in pool if family(m) != family(generator)))
    if not chain:
        raise RuntimeError(f"{generator} için farklı aileden ONAYLI doğrulayıcı yok (kalite kapısı)")
    role = f"_{task}_not_{family(generator)}{'_cand' if allow_candidates else ''}"
    ROLES[role] = chain
    return role


_PAIR = re.compile(r'"(\w+)"\s*:\s*("(?:[^"\\]|\\.)*"|true|false|null|-?\d+(?:\.\d+)?)')


def _json(text: str) -> dict:
    """Doğrulayıcı yanıtı. Bozuk JSON'da (ör. Nemotron'un 'reason' içinde kaçışsız tırnağı) basit alanlar tek tek
    çıkarılır ('A': 'correct', 'equivalent': true); hiçbiri yoksa {} → karar temkinli tarafta (incelenmeli) kalır."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    out = {}
    for k, v in _PAIR.findall(text or ""):
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v.strip('"')
    return out


def _fill(section: str, **kw: str) -> str:
    p = load_prompt(section)
    for k, v in kw.items():
        p = p.replace("{" + k + "}", v)
    return p


def _option_label(verdict: dict, key: str) -> tuple[str, str]:
    """Şık bazlı kararlar (§4a, §4e) → (etiket, gerekçe). Yalnızca anahtar 'correct' ise doğrulanır."""
    correct_opts = [c for c in LETTERS if verdict[c] == "correct"]
    if correct_opts == [key]:
        return "verified", "doğrulayıcı yalnızca anahtar şıkkı doğru buldu"
    if key in correct_opts:
        others = ",".join(c for c in correct_opts if c != key)
        return "needs_review", f"anahtar doğru ama {others} de doğru bulundu (birden çok doğru şık?)"
    if not correct_opts:
        return "needs_review", f"doğrulayıcı hiçbir şıkkı kesin doğru bulmadı (anahtar {key}: {verdict[key] or '?'})"
    return "needs_review", f"doğrulayıcı {','.join(correct_opts)} dedi, anahtar {key}"


def verify_mcq(q: dict, context: str, role: str, light: bool = False) -> dict:
    opts = {f"option_{c.lower()}": o for c, o in zip(LETTERS, q["options"])}
    r = call(role, _fill("4a", context=context, question=q["question"], **opts), json_mode=True, max_tokens=800)
    out = _json(r.text)
    verdict = {c: str(out.get(c, "")).strip().lower() for c in LETTERS}
    key = LETTERS[q["answer_index"]]
    label, why = _option_label(verdict, key)
    if light:  # yalnızca ana doğrulama; bilgi amaçlı §6/§6b atlanır (token bütçesi kısıtlı deneyler için)
        return {"label": label, "why": why, "verifier": r.model, "verifier_reason": out.get("reason", ""),
                "option_verdicts": verdict}
    # Bağlamsız tahmin testi (§6) ve yalnızca-şıklar testi (§6b)
    cb = call(role, _fill("6", question=q["question"], **opts), json_mode=True, max_tokens=300)
    co = call(role, _fill("6b", **opts), json_mode=True, max_tokens=300)
    pick = lambda res: str(_json(res.text).get("choice", "")).strip().upper()[:1]
    return {"label": label, "why": why, "verifier": r.model, "verifier_reason": out.get("reason", ""),
            "option_verdicts": verdict, "closed_book_correct": pick(cb) == key, "choices_cue": pick(co) == key}


def verify_computed(q: dict, computed: dict, context: str, role: str) -> dict:
    """Hesap sorusu (§4e): doğrulayıcı soruyu yalnızca metinden kör çözer; ifade, çözüm ve anahtar gösterilmez.
    Kod (SymPy) modelin kendi ifadesini doğruladı; burada sorulan şeyin o ifade olduğu doğrulanır."""
    from src.generation.compute import numbers_in

    mcq = q["type"] == "multiple_choice"
    options = ("Options:\n" + "\n".join(f"{c}) {o}" for c, o in zip(LETTERS, q["options"]))) if mcq else ""
    r = call(role, _fill("4e", context=context, question=q["question"], options=options), json_mode=True,
             max_tokens=2000)
    out = _json(r.text)
    result = str(out.get("result", "")).strip()
    base = {"verifier": r.model, "verifier_reason": out.get("reason", ""), "blind_answer": result,
            "computed_value": computed.get("value")}
    if mcq:
        verdict = {c: str(out.get(c, "")).strip().lower() for c in LETTERS}
        label, why = _option_label(verdict, LETTERS[q["answer_index"]])
        if label == "verified":
            why = "kod hesabı ve kör çözüm aynı şıkkı buldu"
        return {"label": label, "why": why, "option_verdicts": verdict, **base}
    target = numbers_in(computed.get("value", ""))
    if len(target) == 1 and target[0] in numbers_in(result):
        return {"label": "verified", "why": "kod hesabı ve kör çözüm aynı sonucu buldu", **base}
    j = call(role, _fill("4d", question=q["question"], answer_1=q["answer"], answer_2=result or "(boş)"),
             json_mode=True, max_tokens=300)
    eq = _json(j.text)
    label = "verified" if eq.get("equivalent") is True else "needs_review"
    return {"label": label, "why": ("hakem: kör çözüm eşdeğer" if label == "verified" else
                                    f"kör çözüm farklı: {result or '?'} (kod: {computed.get('value')})"), **base}


def verify_tf(q: dict, context: str, role: str) -> dict:
    r = call(role, _fill("4b", context=context, question=q["question"]), json_mode=True, max_tokens=600)
    out = _json(r.text)
    lab = str(out.get("label", "")).upper()
    want = "SUPPORTED" if q["answer"] == "true" else "CONTRADICTED"
    if lab == want:
        label, why = "verified", f"metin ifadeyi {'destekliyor' if want == 'SUPPORTED' else 'çürütüyor'}"
    elif lab == "NOT_IN_CONTEXT":
        label, why = "rejected", "ifade metinde yok: doğru ya da yanlış olduğu dokümandan anlaşılamaz"
    else:
        label, why = "needs_review", f"doğrulayıcı {lab or '?'} dedi, beklenen {want}"
    return {"label": label, "why": why, "verifier": r.model, "verifier_reason": out.get("reason", "")}


def verify_short(q: dict, context: str, role: str) -> dict:
    r = call(role, _fill("4c", context=context, question=q["question"]), max_tokens=400)
    blind = r.text.strip()
    if "INSUFFICIENT_CONTEXT" in blind:
        return {"label": "needs_review", "why": "doğrulayıcı bağlamda cevap bulamadı", "verifier": r.model,
                "blind_answer": blind}
    a, b = norm(blind), norm(q["answer"])
    if a == b or fuzz.token_set_ratio(a, b) >= 90:
        return {"label": "verified", "why": "kör cevap aynı (kodla eşleşti)", "verifier": r.model, "blind_answer": blind}
    j = call(role, _fill("4d", question=q["question"], answer_1=q["answer"], answer_2=blind), json_mode=True,
             max_tokens=300)
    eq = _json(j.text)
    label = "verified" if eq.get("equivalent") is True else "needs_review"
    return {"label": label, "why": ("hakem: eşdeğer" if label == "verified" else "hakem: farklı cevap"),
            "verifier": r.model, "blind_answer": blind, "verifier_reason": eq.get("reason", "")}


def verify_item(item: dict, chunks_by_id: dict[str, dict], light: bool = False,
                allow_candidates: bool = False) -> dict:
    """Kod kontrolünden geçmiş bir soruyu doğrular; reddedilmişlere dokunmaz."""
    if item["check"]["status"] == "rejected":
        return {"label": "rejected", "why": "kod kontrolü: " + ", ".join(CHECK_TR.get(r, r) for r in item["check"]["rejected"])}
    context = "\n\n".join(f"[s.{chunks_by_id[c]['page']}] {chunks_by_id[c]['text']}" for c in item["chunk_ids"])
    q = item["q"]
    if q.get("compute"):
        role = verifier_role(item["model"], allow_candidates=allow_candidates, task="verify_math")
        return verify_computed(q, item["check"].get("computed", {}), context, role)
    role = verifier_role(item["model"], allow_candidates=allow_candidates)
    if q["type"] == "multiple_choice":
        return verify_mcq(q, context, role, light=light)
    fn = {"true_false": verify_tf, "short_answer": verify_short}[q["type"]]
    return fn(q, context, role)

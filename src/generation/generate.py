"""Soru üretimi (ROADMAP Adım 6): bölüm → bağlam → LLM (PROMPTS.md §2) → şema → kod kontrolleri → şık karıştırma.

Üretim birimi: bir bölüm. Çok kısa bölümler (<MIN_CONTEXT karakter; EN'de tek slaytlık başlıklar) sonraki
bölümlerle birleştirilir; çok uzunlar parçalara bölünür. Görsel okuma bekleyen parçalar kullanılmaz.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from pydantic import ValidationError

from src import config
from src.generation.schema import Question
from src.llm.router import call
from src.prompts import load_prompt
from src.verification.checks import check, mark_duplicates

MIN_CONTEXT = 400
MAX_CONTEXT = 4000
RELATED_CHARS = 600
LANG_NAMES = {"tr": "Turkish", "en": "English"}


def _load(name: str) -> list[dict]:
    path = config.DATA_DIR / "chunks" / name
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _render(chunks: list[dict]) -> str:
    return "\n\n".join(f"[s.{c['page']}] {c['text']}" for c in chunks)


def build_units(doc: str) -> list[dict]:
    """Bir belgenin üretim birimleri: [{title, chunks, text}]"""
    chunks = {c["id"]: c for c in _load("chunks.jsonl")}
    units, cur = [], None
    for sec in (s for s in _load("sections.jsonl") if s["doc"] == doc):
        usable = [chunks[i] for i in sec["chunk_ids"] if not chunks[i]["pending_vision"]]
        if not usable:
            continue
        if cur and len(_render(cur["chunks"])) < MIN_CONTEXT:
            cur["titles"].append(sec["title"])
            cur["chunks"] += usable
            continue
        cur = {"titles": [sec["title"]], "chunks": usable}
        units.append(cur)
    out = []
    for u in units:  # uzun birimleri parçala
        part: list[dict] = []
        for c in u["chunks"]:
            if part and len(_render(part + [c])) > MAX_CONTEXT:
                out.append({"titles": u["titles"], "chunks": part})
                part = []
            part.append(c)
        if part:
            out.append({"titles": u["titles"], "chunks": part})
    for u in out:
        u["text"] = _render(u["chunks"])
        u["title"] = " / ".join(dict.fromkeys(t for t in u["titles"] if t)) or "(başlıksız)"
        u["pages"] = sorted({c["page"] for c in u["chunks"]})
    return out


def _n_questions(text: str) -> int:
    return max(1, min(4, len(text) // 500))


_TYPE_CYCLE = ["multiple_choice", "true_false", "short_answer", "multiple_choice"]


def _type_plan(n: int, unit_index: int) -> str:
    """Tip dağılımını kod belirler (model 'çeşitlendir' talimatına uymuyordu: EN→TR pilotunda 12/12 ÇS).

    Döngü birim sırasına göre kaydırılır; böylece tek soruluk birimler de belge genelinde farklı tipler alır.
    """
    types = [_TYPE_CYCLE[(unit_index + i) % len(_TYPE_CYCLE)] for i in range(n)]
    return ", ".join(f"{i + 1}) {t}" for i, t in enumerate(types))


def _shuffle(q: dict, seed: str) -> dict:
    """Şıkları deterministik karıştır (aynı soru her çalıştırmada aynı sırada); LLM'in A-şıkkı yanlılığını kaldırır."""
    if q["type"] != "multiple_choice":
        return q
    rng = random.Random(seed)
    order = list(range(4))
    rng.shuffle(order)
    q = dict(q)
    q["options"] = [q["options"][i] for i in order]
    for k in ("option_values", "option_notes"):  # şık değerleri ve notları şıklarla birlikte taşınır
        if q.get(k):
            q[k] = [q[k][i] for i in order]
    q["answer_index"] = order.index(q["answer_index"])
    return q


BLOOM_TARGET = {
    "remember": "Every question must target the \"remember\" level: recall of a fact, term or definition stated in the Context.",
    "apply": ("Every question must target the \"apply\" level: the student must use a rule, formula or procedure stated "
              "in the Context on a concrete case (e.g. compute a value, trace a step, choose the outcome of an operator). "
              "The case and its answer must follow entirely from the Context; if the Context has no rule that can be "
              "applied, return an empty \"questions\" array."),
}


# Sınav isteğinde kullanıcının seçtiği zorluk (src/request.py). Modelin kendi etiketine bırakılmaz: hesap
# sorularında kendi seçimiyle 33 problemin yalnızca 1'i "zor" çıktı. Tanım işlemseldir ve istemde kural olarak verilir.
DIFFICULTY_TARGET = {
    "easy": ("Every question must be EASY: recall of one fact, term or definition stated in the Context, "
             "or a single direct step."),
    "medium": ("Every question must be MEDIUM: the student must understand, compare or classify ideas stated in "
               "the Context, or carry out two steps; not the recall of a single sentence."),
    "hard": ("Every question must be HARD: the student must combine two ideas or rules stated in the Context, or "
             "apply a rule in several steps or with a case analysis. It must still be fully answerable from the "
             "Context alone."),
}


def _target_rules(prompt: str, bloom_target: str | None = None, difficulty: str | None = None) -> str:
    extra = [BLOOM_TARGET[bloom_target]] if bloom_target else []
    extra += [DIFFICULTY_TARGET[difficulty]] if difficulty in DIFFICULTY_TARGET else []
    for rule in reversed(extra):
        prompt = prompt.replace("Rules:\n", f"Rules:\n- {rule}\n", 1)
    return prompt


def generate_unit(unit: dict, related: str, language: str, role: str = "generate", unit_index: int = 0,
                  bloom_target: str | None = None, n: int | None = None, types: list[str] | None = None,
                  difficulty: str | None = None) -> list[dict]:
    """bloom_target: None (model seçer) | 'remember' | 'apply' — bilişsel düzey deneyi için (eval/bloom_experiment.py).
    n / types / difficulty: sınav isteğinden (verilmezse bölüm uzunluğuna göre sayı ve döngüsel tip planı)."""
    n = n or _n_questions(unit["text"])
    plan = ", ".join(f"{i + 1}) {t}" for i, t in enumerate(types)) if types else _type_plan(n, unit_index)
    prompt = (load_prompt("2").replace("{n_questions}", str(n)).replace("{type_plan}", plan)
              .replace("{context}", unit["text"])
              .replace("{related}", related or "(none)").replace("{output_language}", LANG_NAMES.get(language, language)))
    prompt = _target_rules(prompt, bloom_target, difficulty)
    r = call(role, prompt, json_mode=True, max_tokens=3000, temperature=0.3)
    try:
        raw = json.loads(r.text).get("questions", [])
    except (json.JSONDecodeError, AttributeError):
        return [{"unit": unit["title"], "pages": unit["pages"], "model": r.model, "q": {"raw": r.text[:500]},
                 "check": {"status": "rejected", "rejected": ["invalid_json"], "flags": []}}]
    if difficulty:
        raw = [{**q, "difficulty": difficulty} if isinstance(q, dict) else q for q in raw]
    return _postprocess(raw, unit, r.model)


def _postprocess(raw: list, unit: dict, model: str) -> list[dict]:
    """LLM'in bir birim için döndürdüğü sorular → şema → kod kontrolleri → şık karıştırma."""
    items = []
    for item in raw:
        base = {"unit": unit["title"], "pages": unit["pages"], "model": model,
                "chunk_ids": [c["id"] for c in unit["chunks"]]}  # doğrulayıcı aynı bağlamı görsün
        try:
            q = Question(**item)
        except (ValidationError, TypeError) as e:
            items.append({**base, "q": item, "check": {"status": "rejected", "rejected": ["schema"],
                                                       "flags": [], "detail": str(e)[:200]}})
            continue
        res = check(q, unit["chunks"])
        qd = q.model_dump()
        res["generated_answer_index"] = qd.get("answer_index")  # karıştırmadan önce (konum yanlılığı ölçümü)
        seed = hashlib.sha1(f"{model}|{qd['question']}".encode("utf-8")).hexdigest()
        items.append({**base, "q": _shuffle(qd, seed), "check": res})
    return items


MAX_BATCH_UNITS = 12
MAX_BATCH_CHARS = 40_000


def _batch_prompt(units: list[dict], start_index: int, language: str, bloom_target: str | None = None) -> str:
    """§2'nin kural kısmı (değişmeden) + §2b toplu blok."""
    rules = load_prompt("2")
    rules = rules[:rules.index("Context:\n{context}")]
    if bloom_target:
        rules = rules.replace("Rules:\n", f"Rules:\n- {BLOOM_TARGET[bloom_target]}\n", 1)
    rules = (rules.replace("{n_questions}", "N (the number given for each unit)")
             .replace("{type_plan}", "the type plan given for each unit")
             .replace("{output_language}", LANG_NAMES.get(language, language)))
    blocks = []
    for k, u in enumerate(units):
        n = _n_questions(u["text"])
        blocks.append(f"### U{k + 1} — pages {u['pages']} — at most {n} question(s); "
                      f"types: {_type_plan(n, start_index + k)}\nContext:\n{u['text']}\n")
    return rules + load_prompt("2b").replace("{units}", "\n".join(blocks))


def generate_batched(units: list[dict], language: str, role: str, bloom_target: str | None = None) -> list[dict]:
    """Birden çok birim tek istekte (istek sınırlı sağlayıcılar için, PROMPTS.md §2b). Her birimin soruları
    o birimin kendi parçalarıyla kontrol edilir; tek birimlik üretimle aynı kontrol/doğrulama zincirinden geçer."""
    out, start = [], 0
    for g in batch_groups(units):
        out += generate_group(g, start, language, role, bloom_target)
        start += len(g)
    mark_duplicates(out)
    return out


def batch_groups(units: list[dict]) -> list[list[dict]]:
    """Birimleri tek isteğe sığacak gruplara böler (en çok MAX_BATCH_UNITS birim / MAX_BATCH_CHARS karakter)."""
    groups, cur = [], []
    for u in units:
        if cur and (len(cur) >= MAX_BATCH_UNITS or sum(len(x["text"]) for x in cur) + len(u["text"]) > MAX_BATCH_CHARS):
            groups.append(cur)
            cur = []
        cur.append(u)
    if cur:
        groups.append(cur)
    return groups


def generate_group(g: list[dict], start: int, language: str, role: str, bloom_target: str | None = None) -> list[dict]:
    """Tek grup = tek istek. Gruplar ayrı çağrıldığında biri başarısız olsa da diğerlerinin soruları korunur."""
    n_total = sum(_n_questions(u["text"]) for u in g)
    # Gemini 3.x önce "düşünür" ve düşünme token'ları çıktı sınırından düşer: sınır geniş tutulur
    # (istek sınırlı sağlayıcıda bu kotaya mal olmaz; 8k sınırda JSON 852 karakterde kesilmişti).
    r = call(role, _batch_prompt(g, start, language, bloom_target), json_mode=True, max_tokens=max(32000, 450 * n_total + 8000),
             temperature=0.3)
    return _split_units(r, g)


def _split_units(r, g: list[dict], force: dict | None = None) -> list[dict]:
    """Toplu yanıtı ({"units": [{"unit": "U1", "questions": [...]}]}) birimlere dağıtıp her soruyu işler."""
    try:
        by_unit = {str(x.get("unit")): x.get("questions", []) for x in json.loads(r.text).get("units", [])}
    except (json.JSONDecodeError, AttributeError):
        by_unit = None
    out = []
    for k, u in enumerate(g):
        if by_unit is None:
            out.append({"unit": u["title"], "pages": u["pages"], "model": r.model, "q": {"raw": r.text[:300]},
                        "check": {"status": "rejected", "rejected": ["invalid_json"], "flags": []}})
        else:
            qs = by_unit.get(f"U{k + 1}", [])
            if force:
                qs = [{**q, **force} if isinstance(q, dict) else q for q in qs]
            out += _postprocess(qs, u, r.model)
    return out


# ---------------------------------------------------------------- hesap soruları (PROMPTS.md §2c)

_MATH = re.compile(r"[=≤≥⇒⇔√²³^!∑π]|\d\s*[+\-*/·]\s*\d")
_WORKED_CYCLE = ["multiple_choice", "short_answer", "multiple_choice"]


def math_units(units: list[dict]) -> list[dict]:
    """Formül/kural içeren birimler (eşitlik, kök, üs, faktöriyel, işlem): hesap sorusu yalnızca bunlardan istenir."""
    return [u for u in units if len(_MATH.findall(u["text"])) >= 4]


def _worked_prompt(units: list[dict], start_index: int, language: str) -> str:
    blocks = []
    for k, u in enumerate(units):
        n = 1 if len(u["text"]) < 1500 else 2
        types = ", ".join(f"{i + 1}) {_WORKED_CYCLE[(start_index + k + i) % len(_WORKED_CYCLE)]}" for i in range(n))
        blocks.append(f"### U{k + 1} — pages {u['pages']} — at most {n} problem(s); types: {types}\n"
                      f"Context:\n{u['text']}\n")
    return (load_prompt("2c").replace("{output_language}", LANG_NAMES.get(language, language))
            .replace("{units}", "\n".join(blocks)))


def _spec_blocks(spec: list[tuple[dict, int, list[str]]], noun: str) -> str:
    return "\n".join(f"### U{k + 1} — pages {u['pages']} — at most {n} {noun}(s); types: "
                     f"{', '.join(f'{i + 1}) {t}' for i, t in enumerate(types))}\nContext:\n{u['text']}\n"
                     for k, (u, n, types) in enumerate(spec))


def generate_request(spec: list[tuple[dict, int, list[str]]], language: str, difficulty: str | None,
                     role: str = "generate_batch", worked: bool = False) -> list[dict]:
    """Sınav isteği (src/request.py): her birim = bir konunun ARAMAYLA bulunan parçaları; sayı ve tipler istekten.
    worked=False → §2 kuralları + §2b toplu blok; worked=True → §2c hesap problemleri. Tek istek."""
    lang = LANG_NAMES.get(language, language)
    if worked:
        prompt = _target_rules(load_prompt("2c"), difficulty=difficulty)
        prompt = prompt.replace("{output_language}", lang).replace("{units}", _spec_blocks(spec, "problem"))
    else:
        rules = load_prompt("2")
        rules = _target_rules(rules[:rules.index("Context:\n{context}")], difficulty=difficulty)
        rules = (rules.replace("{n_questions}", "N (the number given for each unit)")
                 .replace("{type_plan}", "the type plan given for each unit").replace("{output_language}", lang))
        prompt = rules + load_prompt("2b").replace("{units}", _spec_blocks(spec, "question"))
    n_total = sum(n for _, n, _ in spec)
    r = call(role, prompt, json_mode=True, max_tokens=max(32000, 1400 * n_total + 8000), temperature=0.4)
    force = {"bloom_level": "apply"} if worked else {}
    if difficulty:
        force["difficulty"] = difficulty
    return _split_units(r, [u for u, _, _ in spec], force=force or None)


def generate_worked_group(g: list[dict], start: int, language: str, role: str) -> list[dict]:
    """Bir grup birim için hesap soruları (tek istek). Cevaplar kod kontrolünde SymPy ile yeniden hesaplanır."""
    r = call(role, _worked_prompt(g, start, language), json_mode=True, max_tokens=max(32000, 1400 * len(g) + 8000),
             temperature=0.3)
    return _split_units(r, g, force={"bloom_level": "apply"})


def generate_doc(doc: str, role: str = "generate", limit_units: int | None = None,
                 output_language: str | None = None, bloom_target: str | None = None) -> list[dict]:
    """output_language verilmezse belgenin kendi dili kullanılır (ör. İngilizce slayt → 'tr' ile Türkçe soru)."""
    units = build_units(doc)[:limit_units]
    language = output_language or next((c["language"] for c in _load("chunks.jsonl") if c["doc"] == doc), "en")
    out = []
    for i, u in enumerate(units):
        neighbours = [units[j]["text"][:RELATED_CHARS] for j in (i - 1, i + 1) if 0 <= j < len(units)]
        out += generate_unit(u, "\n\n".join(neighbours), language, role, unit_index=i, bloom_target=bloom_target)
    mark_duplicates(out)
    return out

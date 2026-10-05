"""Hesap sorularının kodla doğrulanması (SymPy). LLM çağrısı yok, deterministik.

Hesap sorusunda model, cevabı hesaplayan bir SymPy ifadesi ("compute") ve her şıkkın değerini ("option_values")
da yazar. Burada:
  1. ifade güvenlik için AST üzerinden beyaz listeyle denetlenir (öznitelik erişimi, dunder, string, import yok);
  2. ayrı bir süreçte, süre sınırıyla hesaplanır (SymPy bazı ifadelerde çok uzun sürebilir);
  3. anahtar = hesaplanan değer mi, başka bir şık da aynı değere eşit mi (iki doğru şık), şık METNİNDEKİ sayı
     şıkkın değeriyle tutarlı mı (öğrenci metni görür, değeri değil) kontrol edilir.

Kanıt artık yalnızca "notta geçiyor" değil, "hesap doğru": kural notta (evidence_quote), sonuç kodda.
"""

from __future__ import annotations

import ast
import atexit
import multiprocessing as mp
import re
from fractions import Fraction

FUNCS = {
    "Rational", "Integer", "sqrt", "root", "cbrt", "Abs", "factorial", "binomial", "ff", "solve", "Eq", "log",
    "exp", "pi", "E", "I", "oo", "floor", "ceiling", "Min", "Max", "gcd", "lcm", "Mod", "re", "im",
    "conjugate", "simplify", "expand", "factor", "nsimplify", "degree", "Poly", "diff", "summation",
    "sin", "cos", "tan", "rad", "deg",
}
_SYMBOL = re.compile(r"^[a-z]\d?$")  # tek harf (x, n, k) ya da harf+rakam (x1, x2)
_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Tuple,
          ast.List, ast.Subscript, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
          ast.USub, ast.UAdd)
MAX_LEN = 300
TIMEOUT = 10


def validate(expr: str) -> str | None:
    """İfade güvenli ve izinli mi? Sorun varsa açıklama, yoksa None."""
    if not isinstance(expr, str) or not expr.strip():
        return "boş ifade"
    if len(expr) > MAX_LEN:
        return "ifade çok uzun"
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return "sözdizimi hatası"
    for node in ast.walk(tree):
        if not isinstance(node, _NODES):
            return f"izinsiz yapı: {type(node).__name__}"
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            return "yalnızca sayı sabitleri"
        if isinstance(node, ast.Name) and node.id not in FUNCS and not _SYMBOL.match(node.id):
            return f"izinsiz ad: {node.id}"
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
                return "izinsiz fonksiyon çağrısı"
            if node.keywords:
                return "anahtar kelimeli argüman yok"
        # [0] (köklerden ilki) ya da [x] (denklem sisteminin çözüm sözlüğünden x; 2026-10-04 TYT'de gerekti)
        if isinstance(node, ast.Subscript) and not (
                (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int))
                or (isinstance(node.slice, ast.Name) and _SYMBOL.match(node.slice.id))):
            return "yalnızca sabit ya da sembol indeksi ([0], [x])"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and isinstance(node.right, ast.Constant) \
                and abs(node.right.value) > 1000:
            return "üs çok büyük"
    return None


# ---------------------------------------------------------------- işçi süreç (SymPy yalnızca orada yüklenir)

def _ns():
    import sympy as sp
    ns = {name: getattr(sp, name) for name in FUNCS if hasattr(sp, name)}
    ns["rad"] = lambda d: d * sp.pi / 180
    ns["deg"] = lambda r: r * 180 / sp.pi
    for ch in "abcdfghjklmnopqrstuvwxyz":  # e ve i değil (E, I sabitleriyle karışmasın)
        ns[ch] = sp.Symbol(ch)
        for d in range(10):
            ns[f"{ch}{d}"] = sp.Symbol(f"{ch}{d}")
    return ns


def _eval(expr: str, ns: dict):
    import sympy as sp
    val = eval(compile(ast.parse(expr.strip(), mode="eval"), "<compute>", "eval"), {"__builtins__": {}}, dict(ns))
    if isinstance(val, (list, tuple, set)):
        vals = [sp.simplify(sp.sympify(v)) for v in val]
        return vals[0] if len(vals) == 1 else sp.FiniteSet(*vals)
    if isinstance(val, dict):
        raise ValueError("sözlük sonucu")
    val = sp.sympify(val)
    if isinstance(val, sp.Equality) or getattr(val, "is_Relational", False):
        raise ValueError("sonuç bir eşitlik/eşitsizlik; sayı bekleniyordu")
    return sp.simplify(val)


def _equal(a, b) -> bool:
    import sympy as sp
    if isinstance(a, sp.FiniteSet) or isinstance(b, sp.FiniteSet):
        sa = list(a) if isinstance(a, sp.FiniteSet) else [a]
        sb = list(b) if isinstance(b, sp.FiniteSet) else [b]
        return len(sa) == len(sb) and all(any(_equal(x, y) for y in sb) for x in sa)
    try:
        if sp.simplify(a - b) == 0:
            return True
        na, nb = complex(sp.N(a, 30)), complex(sp.N(b, 30))
        return abs(na - nb) <= 1e-9 * max(1.0, abs(na))
    except (TypeError, ValueError, AttributeError):
        return False


_NUM = re.compile(r"(?<![\w.,])[-–−]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?")


def numbers_in(text: str) -> list[Fraction]:
    """Metindeki sayılar (Türkçe ondalık virgül, kesir, eksi işaretleri): '%25' için hem 25 hem 1/4."""
    out = []
    for m in _NUM.finditer(text or ""):
        s = m.group(0).replace("–", "-").replace("−", "-").replace(" ", "")
        try:
            if "/" in s:
                p, q = s.split("/")
                f = Fraction(p.replace(",", ".")) / Fraction(q)
            else:
                f = Fraction(s.replace(",", "."))
        except (ValueError, ZeroDivisionError):
            continue
        out.append(f)
        if text[m.end():m.end() + 1] == "%" or text[max(0, m.start() - 1):m.start()] == "%":
            out.append(f / 100)
    return out


def _text_consistent(text: str, value) -> bool | None:
    """Şık metnindeki sayı, şıkkın değeriyle tutarlı mı? Değer rasyonel değilse ya da metinde sayı yoksa None."""
    import sympy as sp
    if not (getattr(value, "is_Rational", False) and value.is_finite):
        return None
    nums = numbers_in(text)
    if not nums:
        return None
    target = Fraction(int(value.p), int(value.q))
    return any(n == target for n in nums)


def _judge_worker(payload: dict) -> dict:
    """İşçi süreçte çalışır: hesapla ve karşılaştır. Dönen sözlük düz veri (süreçler arası taşınır)."""
    ns = _ns()
    try:
        value = _eval(payload["compute"], ns)
    except Exception as e:  # noqa: BLE001 — modelin ifadesi her türlü hatayı verebilir
        return {"ok": False, "error": f"hesaplanamadı: {type(e).__name__}: {str(e)[:120]}"}
    out = {"ok": True, "value": str(value)}
    if payload["type"] == "multiple_choice":
        vals = []
        for v in payload["option_values"]:
            try:
                vals.append(_eval(v, ns))
            except Exception as e:  # noqa: BLE001
                return {**out, "ok": False, "error": f"şık değeri hesaplanamadı ({v}): {type(e).__name__}"}
        matches = [_equal(value, v) for v in vals]
        out["matches"] = matches
        out["key_ok"] = matches[payload["answer_index"]]
        out["others_equal"] = sum(matches) - int(matches[payload["answer_index"]])
        texts = payload["options"]
        out["text_ok"] = [_text_consistent(t, v) for t, v in zip(texts, vals)]
        # Bir çeldiricinin METNİ doğru sonucu gösteriyorsa (değeri başka yazılmış olsa bile) öğrenci için iki doğru şık var
        out["distractor_text_shows_answer"] = any(
            i != payload["answer_index"] and _text_consistent(t, value) for i, t in enumerate(texts))
    else:
        av = payload.get("answer_value")
        if av:
            try:
                out["key_ok"] = _equal(value, _eval(av, ns))
            except Exception as e:  # noqa: BLE001
                return {**out, "ok": False, "error": f"cevap değeri hesaplanamadı: {type(e).__name__}"}
        else:
            out["key_ok"] = bool(_text_consistent(payload.get("answer", ""), value))
        out["text_ok"] = [_text_consistent(payload.get("answer", ""), value)]
        out["others_equal"] = 0
        out["distractor_text_shows_answer"] = False
    return out


_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = mp.get_context("spawn").Pool(1)  # tek işçi; SymPy bir kez yüklenir, sonraki sorular hızlı
    return _pool


@atexit.register
def _close() -> None:
    if _pool is not None:
        _pool.terminate()


def judge(q: dict) -> dict:
    """Bir hesap sorusunu kontrol eder → {"ok", "value", "key_ok", "others_equal", "text_ok", ...} ya da hata."""
    global _pool
    exprs = [q.get("compute")] + (q.get("option_values") or []) + ([q["answer_value"]] if q.get("answer_value") else [])
    for e in exprs:
        problem = validate(e)
        if problem:
            return {"ok": False, "error": f"ifade reddedildi ({problem}): {str(e)[:80]}"}
    payload = {k: q.get(k) for k in ("compute", "option_values", "answer_index", "answer_value", "answer", "options", "type")}
    try:
        return _get_pool().apply_async(_judge_worker, (payload,)).get(TIMEOUT)
    except mp.TimeoutError:
        _pool.terminate()
        _pool = None
        return {"ok": False, "error": f"hesap {TIMEOUT} sn içinde bitmedi"}


def reasons(res: dict) -> tuple[list[str], list[str]]:
    """judge() sonucu → (red nedenleri, uyarı bayrakları)"""
    if not res.get("ok"):
        return ["compute_error"], []
    rejected, flags = [], []
    if not res.get("key_ok"):
        rejected.append("compute_mismatch")          # anahtar, kodun hesapladığı sonuç değil
    if res.get("others_equal") or res.get("distractor_text_shows_answer"):
        rejected.append("compute_two_correct")       # başka bir şık da doğru sonuca eşit
    text_ok = res.get("text_ok") or []
    if any(t is False for t in text_ok):
        rejected.append("compute_text_mismatch")     # şık metni değeriyle çelişiyor: öğrenci yanlış sayıyı görür
    elif text_ok and all(t is None for t in text_ok):
        flags.append("compute_text_unchecked")       # metinde sayı yok (ör. √2, kelimeyle yazılmış)
    return rejected, flags

"""Kısa cevap puanlaması (sınav ekranı). LLM yok.

Matematiksel cevap: beklenen cevap ve öğrencinin cevabı SymPy ile hesaplanıp DEĞERLERİ karşılaştırılır
('30240' = '9!/(3!·2!)' = '362880/12'; 'n(n-1)' = '2·C(n, 2)'). Metin cevap: normalize edilmiş eşitlik ya da
uzunluğu da yakın bulanık eşleşme.

Neden (2026-10-05, kullanıcı ekran görüntüsü): eski karşılaştırma token_set_ratio idi; bir kümenin diğerini
içermesi 100 puan veriyordu → beklenen '(n choose 2) * 2' iken öğrencinin '2' cevabı DOĞRU sayıldı. Ayrıca
beklenen cevap hesaplanmamış bir formül olunca ('9! / (3! · 2!)') doğru sonucu (30240) yazan öğrenci yanlış sayılırdı.

Öğrencinin yazdığı ifade güvenilmez girdidir: AST beyaz listesinden (src/generation/compute.validate) ve ek büyüklük
sınırlarından geçmeden hesaplanmaz (iç içe üs, büyük faktöriyel, uzun ifade reddedilir).
"""

from __future__ import annotations

import ast
import re

from rapidfuzz import fuzz

from src.generation.compute import validate
from src.textnorm import SUB, SUP
from src.textnorm import normalize_for_match as norm

_SUP_REV = {v: k for k, v in SUP.items() if k not in "ı'′"}
_SUB_REV = {v: k for k, v in SUB.items()}
_WORDS_OK = {"tane", "adet", "nokta", "farklı", "şekilde", "kelime", "sayı", "olur", "eder", "dir", "dır", "tir", "tır"}
# Türkçe ek-fiil ('tanımsızdır' = 'tanımsız'): yalnızca kelime SONUNDAKİ -dır/-tir (normalize_for_match ı→i yapar)
_COPULA = re.compile(r"(?<=\w{3})[dt][iuü]r\b")


def to_sympy(text: str) -> str | None:
    """Okul gösterimini SymPy ifadesine çevirir: 9!/(3!·2!), C(n, 2), (n choose 2), 2ⁿ, 2^n, √x, n(n-1), 2,5.
    Çevrilemezse (kelimeler, bilinmeyen gösterim) None."""
    s = str(text or "").strip().rstrip(".")
    if not s or len(s) > 60:
        return None
    s = s.replace("⋅", "*").replace("·", "*").replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    s = s.replace("^", "**")
    # Üst / alt simgeler kelime kontrolünden önce ('n²' bir kelime sanılmasın)
    s = re.sub("[" + "".join(_SUP_REV) + "]+", lambda m: "**(" + "".join(_SUP_REV[c] for c in m.group(0)) + ")", s)
    s = "".join(_SUB_REV.get(c, c) for c in s)
    # Sondaki birim / açıklama kelimeleri ('30240 tane', '12 farklı şekilde') atılır; başka kelime varsa metin cevaptır
    words = re.findall(r"[^\W\d_]{2,}", s)
    if any(w.lower() not in _WORDS_OK | {"choose", "sqrt"} for w in words):
        return None
    s = re.sub(r"\b(" + "|".join(_WORDS_OK) + r")\b", " ", s, flags=re.I).strip()
    # Fonksiyon gösterimleri (virgüllü argümanlar ondalık virgülden önce)
    s = re.sub(r"(?<![A-Za-z])C\(\s*(\w+)\s*,\s*(\w+)\s*\)", r"binomial(\1;\2)", s)  # '2C(n,2)' de
    s = re.sub(r"(?<![A-Za-z])P\(\s*(\w+)\s*,\s*(\w+)\s*\)", r"ff(\1;\2)", s)
    s = re.sub(r"\(?\s*(\w+)\s+choose\s+(\w+)\s*\)?", r"binomial(\1;\2)", s)
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)  # Türkçe ondalık virgül
    if "," in s:
        return None
    s = s.replace(";", ",")
    s = re.sub(r"√\s*\(", "sqrt(", s)
    s = re.sub(r"√\s*(\w+)", r"sqrt(\1)", s)
    s = re.sub(r"(\d+|\b[a-z]\b)\s*!", r"factorial(\1)", s)
    # Örtük çarpma: 2n, 2(n+1), n(n-1), (a)(b)
    s = re.sub(r"(\d)\s*(?=[a-z(])", r"\1*", s)
    s = re.sub(r"(?<![A-Za-z_])([a-z])\s*(?=\()", r"\1*", s)
    s = re.sub(r"\)\s*(?=[\w(])", ")*", s)
    return s


def _bounded(expr: str) -> bool:
    """Güvenilmez girdide ek sınırlar: üs küçük sabit ya da tek sembol, faktöriyel ≤ 170, sayılar ≤ 10⁷, iç içe üs yok."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and abs(node.value) > 10 ** 7:
            return False
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            r = node.right
            small = isinstance(r, ast.Constant) and abs(r.value) <= 100
            sym = isinstance(r, ast.Name) and len(r.id) <= 2
            if not (small or sym or (isinstance(r, ast.UnaryOp) and isinstance(r.operand, ast.Constant))):
                return False
            if any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow) for n in ast.walk(node.left)):
                return False
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("factorial", "binomial", "ff"):
            for a in node.args:
                if isinstance(a, ast.Constant) and abs(a.value) > 170:
                    return False
    return True


def safe_value(text: str):
    """Okul gösterimindeki ifadenin SymPy değeri; çevrilemez, güvensiz ya da hesaplanamazsa None."""
    expr = to_sympy(text)
    if not expr or validate(expr) or not _bounded(expr):
        return None
    from src.generation.compute import _eval, _ns
    try:
        return _eval(expr, _ns())
    except Exception:  # noqa: BLE001 — öğrencinin girdisi her türlü hata verebilir
        return None


def same_value(a, b) -> bool:
    import sympy as sp
    try:
        if sp.simplify(sp.expand_func(a - b)) == 0:
            return True
        return abs(complex(sp.N(a)) - complex(sp.N(b))) <= 1e-9 * max(1.0, abs(complex(sp.N(a))))
    except (TypeError, ValueError, AttributeError):
        return False


def grade_short(answer: str, expected: str, computed_value: str | None = None) -> bool:
    """Kısa cevap doğru mu? Beklenen matematiksel ise değer karşılaştırması, değilse sıkı metin karşılaştırması."""
    if not str(answer or "").strip():
        return False
    target = safe_value(computed_value) if computed_value else safe_value(expected)
    if target is not None:
        got = safe_value(answer)
        if got is None:  # '30240 farklı kelime' gibi: içindeki tek sayı
            nums = re.findall(r"-?\d+(?:[.,]\d+)?", str(answer))
            got = safe_value(nums[0]) if len(nums) == 1 else None
        return got is not None and same_value(target, got)
    a, b = _COPULA.sub("", norm(answer)), _COPULA.sub("", norm(expected))
    if not a:
        return False
    if a == b or fuzz.ratio(a, b) >= 90:  # küçük yazım hatası ('parazitoit') evet; başka kelime ('dirençli') hayır
        return True
    # Kelime kümesi eşleşmesi yalnızca uzunluklar yakınsa (bir cevabın diğerinin parçası olması yetmez)
    return fuzz.token_set_ratio(a, b) >= 90 and min(len(a), len(b)) / max(len(a), len(b)) >= 0.6

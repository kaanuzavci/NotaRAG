"""Metin normalizasyonu: ayrıştırma, BM25 ve kanıt kontrolünün ortak kullandığı fonksiyonlar.

Aynı normalizasyonun her yerde kullanılması kritik: kanıt alıntısı ayrıştırılmış metinle
karşılaştırılırken iki taraf da aynı dönüşümlerden geçmeli.
"""

import re
import unicodedata

# Sembol fontlarından (Wingdings, Symbol) gelen madde işaretleri Unicode'un özel kullanım
# alanına (PUA) düşer; bazı PDF'lerde ise \x01 gibi kontrol karakterleri olarak gelir.
_PUA = re.compile(r"[-]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BULLET_CHARS = "•◦▪▫■□●○►▶➢➤✓✔-–—*"
_QUOTES = {"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"', "«": '"', "»": '"'}
_WS = re.compile(r"[ \t ]+")


# Üst / alt simgeler. PDF'in metin katmanında üs bilgisi kayboluyordu ("2ⁿ" → "2n", YZ'de "1·2⁴ + 1·2³" →
# "1.24 + 1.23"): metin matematiksel olarak yanlışlaşıyor ve sorular bu metinden üretiliyor. Ayrıştırıcı küçük
# ve yükseltilmiş yazıyı Unicode üst simgeye, alçaltılmışı alt simgeye çevirir; karşılığı yoksa ^(…) / _(…).
SUP = dict(zip("0123456789+-−–=()niı'′xakmrtyhpj", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻⁼⁽⁾ⁿⁱ′′′ˣᵃᵏᵐʳᵗʸʰᵖʲ"))
SUB = dict(zip("0123456789+-−–=()aeoxijkmnrt", "₀₁₂₃₄₅₆₇₈₉₊₋₋₋₌₍₎ₐₑₒₓᵢⱼₖₘₙᵣₜ"))
SCRIPT_CHARS = set(SUP.values()) | set(SUB.values())
LINEBREAK_HYPHEN = "‐"  # join_lines satır sonu tiresini bununla işaretler; resolve_hyphens belge düzeyinde çözer


def to_script(text: str, sup: bool = True) -> str:
    """'n' → 'ⁿ', '12' → '¹²'; karşılığı olmayan karakter varsa '^(…)' / '_(…)'."""
    t = text.strip()
    table = SUP if sup else SUB
    if not t:
        return text
    if all(ch in table for ch in t):
        return "".join(table[ch] for ch in t)
    return ("^" if sup else "_") + (t if len(t) == 1 else f"({t})")


_SCRIPT_RUN = re.compile("([" + re.escape("".join(sorted(SCRIPT_CHARS))) + "]+)")


def nfkc_keep_scripts(s: str) -> str:
    """NFKC (ﬁ→fi, 𝑓→f) ama üst/alt simgeler korunur (NFKC '²'yi '2' yapıyordu: 'x²' → 'x2')."""
    parts = _SCRIPT_RUN.split(s)
    return "".join(p if i % 2 else unicodedata.normalize("NFKC", p) for i, p in enumerate(parts))


def clean_line(line: str) -> str:
    """Tek bir PDF satırını temizler; satır başındaki sembol/kontrol madde işaretini '• ' yapar."""
    s = nfkc_keep_scripts(line)  # ﬁ→fi, 𝑓→f, tam genişlikli karakterler; üst/alt simgeler korunur
    s = s.replace("­", "")  # yumuşak tire
    lead = re.match(r"^\s*([-\x00-\x08\x0b\x0c\x0e-\x1f]+)\s*", s)
    if lead:
        s = "• " + s[lead.end():]
    s = _PUA.sub("", s)
    s = _CONTROL.sub("", s)
    for k, v in _QUOTES.items():
        s = s.replace(k, v)
    return _WS.sub(" ", s).strip()


def is_bullet(line: str) -> bool:
    return bool(line) and line[0] in _BULLET_CHARS and (len(line) == 1 or line[1] == " ")


def join_lines(lines: list[str]) -> str:
    """Aynı bloktaki satırları paragrafa çevirir. Madde işaretli satırlar yeni satırda başlar.

    Satır sonu tirelemesi: '...bilgisa-' + 'yar' → 'bilgisa‐yar' (özel tire işareti). Hece mi bölünmüş
    ('bü-tün' → 'bütün') yoksa gerçek bileşik kelime mi ('meta-sezgisel'), tek satıra bakarak anlaşılamaz;
    resolve_hyphens() belgenin geri kalanındaki yazımlara bakarak karar verir.
    """
    out = ""
    for ln in lines:
        if not ln:
            continue
        if not out:
            out = ln
        elif is_bullet(ln):
            out += "\n" + ln
        elif re.search(r"\w-$", out) and ln[:1].islower():
            out = out[:-1] + LINEBREAK_HYPHEN + ln
        else:
            out += " " + ln
    return out


_WORD = re.compile(r"\w+(?:-\w+)*")


def resolve_hyphens(texts: list[str], language: str = "tr") -> list[str]:
    """Satır sonu tirelerini (LINEBREAK_HYPHEN) belge düzeyinde çöz: birleşik yazım ('bütün') belgede başka yerde
    geçiyorsa birleştir; tireli yazım ('meta-sezgisel') geçiyorsa tireyi koru; ikisi de yoksa Türkçe'de birleştir
    (satır sonu bölmesi hecedir), İngilizce'de tireyi koru ('real-coded')."""
    vocab = {tr_lower(w) for t in texts for w in _WORD.findall(t.replace(LINEBREAK_HYPHEN, " "))}

    def fix(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        if tr_lower(a + b) in vocab:
            return a + b
        if tr_lower(f"{a}-{b}") in vocab:
            return f"{a}-{b}"
        return a + b if language == "tr" else f"{a}-{b}"

    pat = re.compile(rf"(\w+){LINEBREAK_HYPHEN}(\w+)")
    return [pat.sub(fix, t) if t else t for t in texts]


_LATEX_SYMBOLS = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥",
    r"\neq": "≠", r"\ne": "≠", r"\pm": "±", r"\mp": "∓", r"\infty": "∞", r"\in": "∈", r"\notin": "∉",
    r"\subseteq": "⊆", r"\subset": "⊂", r"\supset": "⊃", r"\cup": "∪", r"\cap": "∩", r"\emptyset": "∅",
    r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔", r"\iff": "⇔", r"\rightarrow": "→", r"\to": "→",
    r"\leftarrow": "←", r"\approx": "≈", r"\equiv": "≡", r"\sum": "∑", r"\prod": "∏", r"\forall": "∀",
    r"\exists": "∃", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\Delta": "Δ",
    r"\epsilon": "ε", r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\pi": "π", r"\rho": "ρ",
    r"\sigma": "σ", r"\Sigma": "Σ", r"\phi": "φ", r"\omega": "ω", r"\ldots": "…", r"\dots": "…",
    r"\cdots": "⋯", r"\%": "%", r"\,": " ", r"\;": " ", r"\ ": " ", r"\quad": " ", r"\mathbb{N}": "ℕ",
    r"\mathbb{Z}": "ℤ", r"\mathbb{Q}": "ℚ", r"\mathbb{R}": "ℝ", r"\mathbb{C}": "ℂ",
}


def _simple(x: str) -> str:
    x = x.strip()
    return x if re.fullmatch(r"[\w.·′]+", x) else f"({x})"


def pretty_math(s: str) -> str:
    """Ekranda gösterim için: görsel okumanın LaTeX'i ve '^' gösterimi okunur Unicode'a çevrilir
    ('$\\frac{100 \\cdot a}{a + b}$' → '100·a/(a + b)', '2^n' → '2ⁿ'). Saklanan metin değişmez."""
    if not s or not (any(c in s for c in "\\^_$*") or " choose " in s):
        return s
    # Görsel okumanın kombinasyon yazımı '(n choose 2)' → 'C(n, 2)'; programlama çarpımı '*' → '·'
    s = re.sub(r"\(\s*(\w+)\s+choose\s+(\w+)\s*\)|(\w+)\s+choose\s+(\w+)",
               lambda m: f"C({m.group(1) or m.group(3)}, {m.group(2) or m.group(4)})", s)
    s = re.sub(r"\s*\*\s*(?!\*)", " · ", s) if "**" not in s else s.replace("**", "^")
    s = s.replace("$", "")
    s = re.sub(r"\\(?:text|mathrm|mathbf|operatorname)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\left|\\right", "", s)
    for _ in range(3):  # iç içe kesirler
        s = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", lambda m: f"{_simple(m.group(1))}/{_simple(m.group(2))}", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", lambda m: "√" + _simple(m.group(1)), s)
    s = re.sub(r"\\binom\{([^{}]*)\}\{([^{}]*)\}", r"C(\1, \2)", s)
    for k in sorted(_LATEX_SYMBOLS, key=len, reverse=True):
        s = s.replace(k, _LATEX_SYMBOLS[k])
    s = re.sub(r"\^\{([^{}]*)\}", lambda m: to_script(m.group(1)) if len(m.group(1)) <= 6 else f"^({m.group(1)})", s)
    s = re.sub(r"\^\(([^()]{1,6})\)", lambda m: to_script(m.group(1)), s)
    s = re.sub(r"(?<=[\w)\]])\^(\d+|[a-zA-Z](?![a-zA-Z])|[′+-])", lambda m: to_script(m.group(1)), s)
    s = re.sub(r"_\{([^{}]*)\}", lambda m: to_script(m.group(1), sup=False) if len(m.group(1)) <= 4 else f"_({m.group(1)})", s)
    s = re.sub(r"(?<=[A-Za-z])_(\w)", lambda m: to_script(m.group(1), sup=False), s)
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)  # tanınmayan komut: adını bırak
    return re.sub(r"[{}]", "", s)


def tr_lower(s: str) -> str:
    """Türkçe'ye duyarlı küçük harf: Python'un lower()'ı 'I'yı 'i' yapar, doğrusu 'ı'."""
    return s.replace("I", "ı").replace("İ", "i").lower().replace("i̇", "i")


def normalize_for_match(s: str) -> str:
    """Kanıt alıntısı karşılaştırması için agresif normalizasyon (yalnızca karşılaştırmada kullanılır).

    ı/i ayrımı da katlanır: İngilizce metinde 'IITG' Türkçe kurala göre 'ııtg' olur, LLM ise
    'İstanbul'u 'Istanbul' yazabilir. Karşılaştırmada iki taraf da aynı biçime indirgenir.
    """
    s = clean_line(s.replace("\n", " ").replace(LINEBREAK_HYPHEN, ""))
    s = unicodedata.normalize("NFKC", s)  # karşılaştırmada üst simgeler düz: '2ⁿ' = '2n' = '2^n' (^ noktalama)
    # Görsel okuma formülleri LaTeX yazar ('$x \in [0, 30]$'), LLM alıntısı ise 'x ∈ [0, 30]'.
    # LaTeX komutları ve $ işaretleri atılır; sembollerin kendisi zaten noktalama olarak siliniyor.
    s = re.sub(r"\\[a-zA-Z]+", " ", s).replace("$", " ")
    s = tr_lower(s).replace("ı", "i")
    s = re.sub(r"(?<=\w)-\s*(?=\w)", "", s)  # kelime içi / satır sonu tireleri
    s = re.sub(r"[^\w\s]", " ", s)  # noktalama
    return re.sub(r"\s+", " ", s).strip()


_STOP_ALL = {
    # Türkçe
    "ve", "bir", "bu", "şu", "için", "ile", "da", "de", "ki", "mi", "mı", "mu", "mü", "olarak", "olan",
    "gibi", "daha", "çok", "veya", "ya", "ise", "her", "en", "ne", "o", "ama", "fakat", "kadar", "sonra",
    "önce", "göre", "değil", "var", "yok", "olur", "eder", "nedir", "nasıl", "hangi",
    # İngilizce
    "the", "and", "of", "to", "is", "in", "a", "an", "for", "are", "that", "with", "by", "as", "be",
    "this", "it", "on", "or", "from", "at", "which", "what", "how", "can", "will", "its", "their",
}


def f5_tokens(text: str, prefix: int = 5) -> list[str]:
    """BM25 için token'lar: normalize, stopword'süz, her kelimenin ilk 5 harfi (Can vd., 2008).

    Eklemeli Türkçe'de 'algoritmalarda', 'algoritmanın', 'algoritma' → hepsi 'algor'.
    """
    words = normalize_for_match(text).split()
    return [w[:prefix] for w in words if w not in _STOP_ALL and (len(w) > 1 or w.isdigit())]


_TR_STOP = {"ve", "bir", "bu", "için", "ile", "da", "de", "olarak", "olan", "gibi", "daha", "çok", "veya", "ise", "her"}
_EN_STOP = {"the", "and", "of", "to", "is", "in", "a", "for", "are", "that", "with", "by", "as", "be", "this"}


def detect_language(text: str) -> str:
    """Basit sezgisel dil tespiti ('tr', 'en' veya 'unknown'); ek paket gerektirmez."""
    words = re.findall(r"\w+", tr_lower(text))
    if len(words) < 5:
        return "unknown"
    tr_chars = len(re.findall(r"[çğıöşü]", tr_lower(text)))
    tr_score = sum(w in _TR_STOP for w in words) + tr_chars * 0.5
    en_score = sum(w in _EN_STOP for w in words)
    if tr_score == en_score:
        return "unknown"
    return "tr" if tr_score > en_score else "en"

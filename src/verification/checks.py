"""Kod kontrolleri (PROMPTS.md 'Programmatic Checks'): LLM çağrısı yok, ücretsiz ve deterministik.

Her soru için: red nedenleri (rejected) ve uyarı bayrakları (flags) üretir. Reddedilen soru
doğrulama LLM'ine hiç gönderilmez.
"""

from __future__ import annotations

import re
import statistics

from rapidfuzz import fuzz

from src.generation.schema import Question
from src.textnorm import normalize_for_match as norm

NEAR_VERBATIM = 90          # rapidfuzz partial_ratio: kanıt "neredeyse birebir"
ANSWER_OPTION_MATCH = 85    # cevap metni ile options[answer_index] benzerliği
LENGTH_CUE = 1.5            # doğru şık, çeldiricilerin ortalamasından bu kat uzunsa ipucu
VERBATIM_CUE = 0.8          # doğru şık token'larının bu oranı bir bağlam cümlesinden geliyorsa ipucu
DUPLICATE = 85              # soru metinleri bu kadar benzerse tekrar

_CONTEXT_REF = re.compile(
    r"\b(metinde|metne göre|bağlamda|bağlama göre|yukarıda(ki)?|(yukarıda |metinde )?bahsedilen|"
    r"sözü edilen|slaytta|according to the (text|passage|context)|in the (text|passage|context)|"
    r"mentioned above|the above|"
    # Pilotta kaçanlar: 'Bu seçim stratejisinin…', 'Verilen … örneğinde…' (öğrenci örneği/slaytı görmüyor)
    r"verilen ([\w()'’-]+ ){0,3}(örne(k|ğ)\w*|tablo\w*|şekil\w*|grafi\w*|değer\w*|veri\w*|bilgi\w*|şema\w*)|"
    r"örnekte(ki)?|tablodaki|şekildeki|"
    r"the given ([\w()'’-]+ ){0,3}(example|table|figure|values?|data)|this (method|strategy|technique|algorithm|approach))\b", re.I)
_ABSOLUTE = re.compile(
    r"\b(yalnızca|sadece|her zaman|asla|hiçbir zaman|tamamen|kesinlikle|zorunlu\w*|mutlaka|daima|"
    r"only|always|never|all|none|must|completely)\b", re.I)
_DEMONSTRATIVE_START = re.compile(
    r"^\s*(bu|şu|söz konusu)\s+(?!nedenle|yüzden|sayede|durumda|amaçla|şekilde)(\w+\s+){0,2}(yöntem|strateji|teknik|algoritma|yaklaşım|model|işlem|operatör|"
    r"fonksiyon|sistem|kavram)", re.I)


def _tokens(s: str) -> set[str]:
    return {t for t in norm(s).split() if len(t) > 2}


def _overlap_with_context(option: str, sentences: list[set[str]]) -> float:
    tok = _tokens(option)
    if not tok:
        return 0.0
    return max((len(tok & s) / len(tok) for s in sentences), default=0.0)


def _option_support(option: str, answer: str) -> float:
    """Şıkkın içerik kelimelerinin (sayılar dahil) cevap metninde geçme oranı; tam eşleşmede 1."""
    o, a = norm(option), norm(answer)
    if not o:
        return 0.0
    if o == a or o in a:
        return 1.0
    toks = [t for t in o.split() if len(t) > 2 or t.isdigit()]
    if not toks:
        return fuzz.ratio(o, a) / 100
    found = sum(t in a.split() or (len(t) >= 5 and t[:5] in a) for t in toks)
    return found / len(toks)


def locate_evidence(quote: str, chunks: list[dict]) -> tuple[str | None, dict | None]:
    """('exact' | 'near' | None, kanıtın bulunduğu parça)"""
    q = norm(quote)
    for c in chunks:
        if q and q in norm(c["text"]):
            return "exact", c
    best = max(chunks, key=lambda c: fuzz.partial_ratio(q, norm(c["text"])), default=None)
    if best and fuzz.partial_ratio(q, norm(best["text"])) >= NEAR_VERBATIM:
        return "near", best
    return None, None


# Soru yazım hataları (Item-Writing Flaws; SAQUET'in 19 kurallık listesinden, kodla güvenilir yakalanabilenler)
_ALL_NONE = re.compile(
    r"^\s*(hepsi|hiçbiri|tümü|yukarıdakilerin\s+(hepsi|tümü|hiçbiri)|hiçbiri\s+doğru\s+değildir|her\s+ikisi(\s+de)?|"
    r"[a-d]\s+ve\s+[a-d](\s+şıkları)?|all\s+of\s+the\s+above|none\s+of\s+the\s+above|both\s+[a-d]\s+and\s+[a-d])\s*\.?\s*$",
    re.I)
_NEGATIVE = re.compile(r"\b(değildir|değil midir|yoktur|olamaz|yanlıştır|hangisi\s+\w*\s*değil|not|except|false)\b", re.I)
_NEGATIVE_EMPHASIS = re.compile(r"\b(DEĞİLDİR|YOKTUR|OLAMAZ|YANLIŞTIR|NOT|EXCEPT)\b|\*\*|__")
_CLANG_STOP = {"aşağıdakilerden", "hangisi", "hangisidir", "olarak", "olduğu", "olduğuna", "göre", "nedir", "kaçtır",
               "which", "following", "what", "whose"}


def iwf_checks(q: Question) -> tuple[list[str], list[str]]:
    """(red, uyarı) — yalnızca çoktan seçmeli sorular."""
    if q.type != "multiple_choice":
        return [], []
    rejected, flags = [], []
    if any(_ALL_NONE.match(o) for o in q.options):
        rejected.append("all_none_option")       # "hepsi / hiçbiri" şıkkı: kısmi bilgiyle bulunur (istem de yasaklıyor)
    if _NEGATIVE.search(q.question) and not _NEGATIVE_EMPHASIS.search(q.question):
        flags.append("negative_stem")            # olumsuz kök vurgulanmamış: öğrenci "değildir"i kaçırabilir
    # 5 harflik kökler (Türkçe ekler: 'eşitsizliğin' = 'eşitsizlik'); arama katmanındaki F5 ile aynı yaklaşım
    f5 = lambda text: {t[:5] for t in _tokens(text) if len(t) >= 5 and t not in _CLANG_STOP}
    stem = f5(q.question)
    correct = f5(q.options[q.answer_index])
    others = set().union(*(f5(o) for i, o in enumerate(q.options) if i != q.answer_index))
    if (stem & correct) - others:
        flags.append("clang_cue")                # doğru şık kökteki kelimeyi tekrar ediyor, çeldiriciler etmiyor
    return rejected, flags


def check(q: Question, chunks: list[dict]) -> dict:
    rejected, flags = [], []

    if _CONTEXT_REF.search(q.question) or _DEMONSTRATIVE_START.search(q.question):
        rejected.append("context_reference")
    if q.type == "true_false" and q.question.rstrip().endswith("?"):
        flags.append("tf_not_statement")  # D/Y bir ifade olmalı, soru değil

    kind, chunk = locate_evidence(q.evidence_quote, chunks)
    page = chunk["page"] if chunk else None
    if kind is None:
        rejected.append("evidence_not_found")
    elif kind == "near":
        flags.append("near_verbatim")
    if chunk and chunk.get("source") == "vision":
        # Kanıt slaytın kendi metni değil, görsel okuma modelinin yazdığı metin (ör. akış şeması açıklaması):
        # görsel okuma hatası soruya taşınabilir → arayüzde daha düşük güvenle gösterilir.
        flags.append("vision_evidence")

    if q.type == "multiple_choice":
        correct = q.options[q.answer_index]
        # Doğru şıkkı answer_index belirler; 'answer' alanı açıklamalı bir cümle olabilir
        # ("%0.1-%6'sı" ↔ "Kullanılan pestisitlerin sadece %0.1 ile %6'sı…"; Gemini böyle yazıyor ve
        # bilişsel düzey deneyinde 12 geçerli soru bu yüzden boşuna reddedilmişti).
        # Gerçek hata yalnızca şu: cevap metni anahtardan çok BAŞKA bir şıkkı anlatıyorsa.
        support = [_option_support(opt, q.answer) for opt in q.options]
        best = max(range(4), key=lambda i: support[i])
        if best != q.answer_index and support[best] >= 0.6 and support[best] > support[q.answer_index] + 0.2:
            rejected.append("answer_option_mismatch")
        distractors = [o for i, o in enumerate(q.options) if i != q.answer_index]
        # Birbirine çok benzeyen şıklar → iki doğru şık riski (duyarlılık testinde doğrulayıcı 2/7 kaçırdı)
        # Tekrar = bir şıkkın kelimeleri diğerininkini tamamen kapsıyor ("Başka bir deyişle: Üç" ⊇ "Üç").
        # Metin benzerliği oranı kullanılmaz: "0.25'ten büyük" / "0.75'ten büyük" / "0.25'ten küçük"
        # %97 benzer çıkıyordu ama anlamları farklı (pilotun en iyi uygulama sorusu yanlışlıkla reddedildi).
        # Yalnızca ÖZ alt küme: aynı kelimelerin farklı sırası tekrar değildir — sıra soran sorular
        # ("Seçim, Mutasyon, Çaprazlama" / "Seçim, Çaprazlama, Mutasyon") ve yer değiştirince anlamı
        # ters dönen şıklar ("baskıyı azaltır, şansı artırır" / "baskıyı artırır, şansı azaltır").
        toks = [set(norm(o).split()) for o in q.options]
        if any(toks[i] and toks[j] and (toks[i] < toks[j] or toks[j] < toks[i])
               for i in range(4) for j in range(i + 1, 4)):
            rejected.append("near_duplicate_options")
        # Kesin ifadeli çeldiriciler ("yalnızca", "her zaman") tek makul şıkkı ele verir (yalnızca-şıklar testi)
        if sum(bool(_ABSOLUTE.search(d)) for d in distractors) >= 2 and not _ABSOLUTE.search(correct):
            flags.append("absolute_distractors")
        if len(correct) > LENGTH_CUE * statistics.mean(len(d) for d in distractors):
            flags.append("length_cue")
        sentences = [_tokens(s) for s in re.split(r"(?<=[.!?:;])\s+|\n", " ".join(c["text"] for c in chunks))]
        if (_overlap_with_context(correct, sentences) >= VERBATIM_CUE
                and max(_overlap_with_context(d, sentences) for d in distractors) < 0.5):
            flags.append("verbatim_cue")

    r, f = iwf_checks(q)
    rejected += r
    flags += f

    computed = None
    if q.compute is not None:  # hesap sorusu: cevap kodla yeniden hesaplanır (SymPy, ayrı süreçte)
        from src.generation.compute import judge, reasons
        computed = judge(q.model_dump())
        r, f = reasons(computed)
        rejected += r
        flags += f

    out = {"status": "rejected" if rejected else "passed_checks", "rejected": rejected,
           "flags": flags, "evidence_match": kind, "evidence_page": page}
    if computed is not None:
        out["computed"] = computed
    return out


def mark_duplicates(items: list[dict], keep: list[dict] = ()) -> None:
    """Aynı partide neredeyse aynı soru metinleri: ilki kalır, sonrakiler reddedilir. keep: zaten havuzda olan
    sorular (değiştirilmez); yeni bir soru bunlardan birinin tekrarıysa o da reddedilir."""
    seen: list[str] = [norm(k["q"]["question"]) for k in keep if k["check"]["status"] != "rejected"]
    for it in items:
        if it["check"]["status"] == "rejected":
            continue
        q = norm(it["q"]["question"])
        if any(fuzz.token_set_ratio(q, s) >= DUPLICATE for s in seen):
            it["check"]["status"] = "rejected"
            it["check"]["rejected"].append("duplicate")
        else:
            seen.append(q)

"""Ortak arayüz parçaları: sınav kâğıdı görünümünde soru kartı (İnceleme ve Sınav Hazırla sayfaları)."""

from __future__ import annotations

import base64
import re

from src.textnorm import pretty_math
from src.ui import data, style

LETTERS = "ABCD"
TYPE_TR = {"multiple_choice": "Çoktan seçmeli", "short_answer": "Kısa cevap", "true_false": "Doğru / Yanlış"}
DIFF_TR = {"easy": "Kolay", "medium": "Orta", "hard": "Zor"}


def t(x) -> str:
    """Ekranda gösterilecek metin: LaTeX ve ^ gösterimi okunur Unicode (2^n → 2ⁿ, kesirler, x₁), HTML'e kaçışlı.
    Saklanan veri değişmez; yalnızca gösterim."""
    return style.esc(pretty_math(str(x)))


def expected(q: dict) -> str:
    """Beklenen cevap; hesaplanmamış bir formülse değeri de: '9!/(3!·2!) = 30240' (öğrenci sayıyı yazabilsin)."""
    ans = str(q.get("answer", ""))
    if q.get("type") == "short_answer" and re.search(r"\d", ans) and re.search(r"[!/*·⋅^]|choose|C\(", ans):
        from src.grading import safe_value
        v = safe_value(ans)
        if v is not None and getattr(v, "is_number", False) and str(v) != ans.strip():
            return f"{t(ans)} = {t(v)}"
        if v is not None and getattr(v, "free_symbols", None):  # sembolik: sadeleşmiş hali (C(n, 2)·2 = n·(n − 1))
            import sympy as sp
            simple = str(sp.factor(sp.expand_func(v))).replace("**", "^").replace("*", "·")
            if simple.replace(" ", "") != ans.replace(" ", ""):
                return f"{t(ans)} = {t(simple)}"
    return t(ans)


def type_label(q: dict) -> str:
    return "Hesap sorusu" if q.get("compute") else TYPE_TR.get(q.get("type"), "?")


def _options(q: dict, reveal: bool, chosen=None) -> str:
    """Şıklar: yuvarlak harf + metin. reveal: doğru şık yeşil; chosen (öğrencinin cevabı) yanlışsa kırmızı."""
    if q.get("type") == "multiple_choice" and q.get("options"):
        opts = [(LETTERS[i], o, i == q.get("answer_index"), chosen == i) for i, o in enumerate(q["options"])]
    elif q.get("type") == "true_false":
        opts = [("D", "Doğru", q.get("answer") == "true", chosen == "true"),
                ("Y", "Yanlış", q.get("answer") == "false", chosen == "false")]
    else:
        if chosen is not None:
            mine = f'<span class="k">Senin cevabın</span>{t(chosen or "(boş)")}'
            body = mine + (f'<span class="k" style="margin-top:.5rem">Beklenen cevap</span>{expected(q)}'
                           if reveal else "")
        elif reveal:
            body = f'<span class="k">Beklenen cevap</span>{expected(q)}'
        else:
            body = '<span class="k">Cevap</span><span style="color:#9A9283">Kısa bir cevap yazılır.</span>'
        return f'<div class="nr-answer">{body}</div>'
    rows = []
    for letter, text, correct, picked in opts:
        cls = " ok" if reveal and correct else (" bad" if reveal and picked else "")
        tag = ("✓ Doğru cevap" if reveal and correct else ("Senin cevabın" if picked else ""))
        rows.append(f'<div class="nr-opt{cls}"><span class="l">{letter}</span><span>{t(text)}</span>'
                    f'{f"<span class=ck>{tag}</span>" if tag else ""}</div>')
    # Seçilen yanlış şıkkın temsil ettiği hata (yeni sorularda option_notes; PROMPTS §2): "neden yanlış?"
    notes = q.get("option_notes") or []
    if reveal and isinstance(chosen, int) and chosen != q.get("answer_index") and chosen < len(notes) and notes[chosen]:
        rows.append(f'<div class="nr-why"><b>Bu şıkkı seçtiysen:</b> {t(notes[chosen])}</div>')
    return '<div class="nr-opts">' + "".join(rows) + "</div>"


def question_card(item: dict, number: int, reveal: bool = True, chosen=None, verdict: bool = True,
                  options: bool = True) -> str:
    """Soru kartı HTML'i. reveal=False: cevap/kanıt gizli. options=False: yalnızca soru (sınavda şıklar ayrı seçilir)."""
    q, chk, ver = item["q"], item.get("check", {}), item.get("verification", {})
    chips = [type_label(q), DIFF_TR.get(q.get("difficulty"), "")]
    chips_html = "".join(f'<span class="nr-chip">{style.esc(c)}</span>' for c in chips if c)
    page = chk.get("evidence_page")
    tail = ""
    if reveal:
        if q.get("solution"):
            steps = "".join(f"<li>{t(s)}</li>" for s in q["solution"])
            tail += f'<div class="nr-label">Çözüm</div><ol class="nr-solution">{steps}</ol>'
        doc = data.short(item.get("doc", ""))
        where = " · ".join(x for x in (doc, f"sayfa {page}" if page else "") if x)
        label = "Uygulanan kural" if q.get("compute") else "Kaynak"
        tail += (f'<div class="nr-label">{label}{f" · {style.esc(where)}" if where else ""}</div>'
                 f'<div class="nr-evidence"><span class="nr-hl">{t(q.get("evidence_quote", ""))}</span></div>')
        if verdict:
            tail += (f'<div class="nr-grow"></div><div class="nr-verdict">{style.pill(ver.get("label", "?"))}'
                     f'<span>{style.esc(ver.get("why", ""))}</span></div>')
    body = _options(q, reveal, chosen) if options else ""
    return (f'<div class="nr-exam"><div class="nr-qhead"><span class="nr-qnum">SORU {number}</span>{chips_html}</div>'
            f'<div class="nr-q">{t(q.get("question", "(şema dışı)"))}</div>{body}{tail}</div>')


# Bitiş özeti (kart oturumu ve sınav sonucu). Grafik ilkeleri (dataviz yönergesi): hikâye "nerede zorlandım?" →
# grup başına tek oran (isabet) ölçer çubuğuyla, tek seri → tek renk ve lejant yok; her değer yazılı (renk tek başına
# anlam taşımaz); büyük sayılar düz yazı tipiyle. Durum renkleri yalnızca etiketli kutucuklarda (doğru / yanlış / boş).
STATUS_DOT = {"Doğru": "#3B8D66", "Bildim": "#3B8D66", "Yanlış": "#C6503A", "Bilemedim": "#C6503A",
              "Boş": "#B9AF98", "Atladım": "#B9AF98"}
DIFF_ORDER = ["Kolay", "Orta", "Zor"]


def _rate(counts: list[int], skip_neutral: bool) -> tuple[int, int]:
    """(bilinen, payda). Kartta atlananlar paydaya girmez (değerlendirilmedi); sınavda boş yanlış sayılır."""
    return counts[0], counts[0] + counts[1] + (0 if skip_neutral else counts[2])


def _group(records: list[dict], key: str, labels: tuple[str, ...]) -> dict[str, list[int]]:
    agg: dict[str, list[int]] = {}
    for r in records:
        agg.setdefault(r[key] or "Belirsiz", [0] * len(labels))[labels.index(r["status"])] += 1
    return agg


def _detail(name: str, counts: list[int], labels: tuple[str, ...]) -> str:
    return style.esc(f"{name} — " + " · ".join(f"{lab}: {c}" for lab, c in zip(labels, counts)))


def _meter(name: str, counts: list[int] | None, labels: tuple[str, ...], skip_neutral: bool) -> str:
    if not counts or not sum(counts):
        return (f'<div class="nr-m none"><div class="t"><span class="nm">{style.esc(name)}</span><span class="v">–</span>'
                f'</div><div class="nr-track"></div><div class="c">bu turda yok</div></div>')
    good, total = _rate(counts, skip_neutral)
    pct = round(100 * good / total) if total else None
    extra = f" · {counts[2]} {labels[2].lower()}" if skip_neutral and counts[2] else ""
    return (f'<div class="nr-m" title="{_detail(name, counts, labels)}"><div class="t"><span class="nm">{style.esc(name)}</span>'
            f'<span class="v">{"–" if pct is None else f"%{pct}"}</span></div>'
            f'<div class="nr-track"><i style="width:{pct or 0}%"></i></div><div class="c">{good} / {total}{extra}</div></div>')


def _topic_row(name: str, counts: list[int], labels: tuple[str, ...], skip_neutral: bool) -> str:
    good, total = _rate(counts, skip_neutral)
    pct = round(100 * good / total) if total else None
    weak = '<b class="nr-weak">↻ tekrar et</b>' if pct is not None and pct < 50 else ""
    return (f'<div class="nr-tr" title="{_detail(name, counts, labels)}"><div class="nm"><span>{style.esc(name)}</span>{weak}</div>'
            f'<div class="nr-track"><i style="width:{pct or 0}%"></i></div>'
            f'<div class="v">{"–" if pct is None else f"%{pct}"}</div><div class="c">{good}/{total}</div></div>')


def summary_html(records: list[dict], labels: tuple[str, ...], *, title: str, note: str, hero_label: str,
                 hero_sub: str, extra_tile: tuple[str, str] | None = None, by_type: bool = False,
                 skip_neutral: bool = False, topics_shown: int = 6) -> str:
    """records: [{"status": labels[i], "diff": "Kolay"…, "type", "topic"}] → tek özet kartı (HTML)."""
    counts = [sum(r["status"] == lab for r in records) for lab in labels]
    good, total = _rate(counts, skip_neutral)
    tiles = "".join(f'<div class="tile"><div class="k"><i style="background:{STATUS_DOT[lab]}"></i>{lab}</div>'
                    f'<div class="v">{c}</div></div>' for lab, c in zip(labels, counts))
    if extra_tile:
        tiles += f'<div class="tile"><div class="k">{style.esc(extra_tile[0])}</div><div class="v">{style.esc(extra_tile[1])}</div></div>'
    out = (f'<div class="nr-sum"><div class="title">{style.esc(title)}</div><div class="note">{style.esc(note)}</div>'
           f'<div class="head"><div class="hero"><div class="k">{style.esc(hero_label)}</div>'
           f'<div class="v">%{round(100 * good / total) if total else 0}</div><div class="d">{style.esc(hero_sub)}</div></div>'
           f'<div class="tiles">{tiles}</div></div>')
    diff = _group(records, "diff", labels)
    out += ('<div class="sec"><div class="h">Zorluğa göre</div><div class="meters">'
            + "".join(_meter(d, diff.get(d), labels, skip_neutral) for d in DIFF_ORDER) + "</div></div>")
    if by_type:
        types = sorted(_group(records, "type", labels).items(), key=lambda kv: -sum(kv[1]))
        out += (f'<div class="sec"><div class="h">Soru tipine göre</div><div class="meters" style="--n:{max(2, min(4, len(types)))}">'
                + "".join(_meter(t, c, labels, skip_neutral) for t, c in types) + "</div></div>")

    def weakness(kv: tuple[str, list[int]]) -> tuple[float, int]:
        g, t = _rate(kv[1], skip_neutral)
        return (g / t if t else 2.0, -sum(kv[1]))  # değerlendirilmemiş konu en sona
    rows = [_topic_row(n, c, labels, skip_neutral) for n, c in sorted(_group(records, "topic", labels).items(), key=weakness)]
    more = (f'<details><summary>+ {len(rows) - topics_shown} konu daha</summary>{"".join(rows[topics_shown:])}</details>'
            if len(rows) > topics_shown else "")
    out += (f'<div class="sec"><div class="h">Konulara göre<small>en çok zorlandığın önce</small></div>{"".join(rows[:topics_shown])}'
            f'{more}</div>')
    return out + "</div>"


def page_card(item: dict, png: bytes | None, note: str, reveal: bool = True) -> str:
    """Kaynak sayfa kartı (kanıt sarıyla işaretli sayfa görüntüsü)."""
    page = item.get("check", {}).get("evidence_page")
    head = (f'<div class="nr-page-head"><span class="nr-qnum">KAYNAK{f" · S.{page}" if page else ""}</span>'
            f'<span class="doc">{style.esc(data.short(item.get("doc", "")))}</span></div>')
    if not reveal:
        frame = '<div class="hidden">Kaynak sayfa gizli.<br>Soruyu çözdükten sonra göster.</div>'
        note = "Cevap ve kanıt gizli."
    else:
        frame = (f'<img alt="Kaynak sayfa" src="data:image/png;base64,{base64.b64encode(png).decode()}">' if png
                 else f'<div class="hidden">{style.esc(note)}</div>')
    return (f'<div class="nr-page">{head}<div class="nr-page-frame">{frame}</div>'
            f'<div class="nr-page-note">{style.esc(note)}</div></div>')

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


# Bitiş istatistikleri: durum → renk (renk hep etiketle birlikte gösterilir; açık gri "boş" için nötr)
STAT_COLORS = {"Doğru": "#10B981", "Bildim": "#10B981", "Yanlış": "#F43F5E", "Bilemedim": "#F43F5E",
               "Boş": "#CBD5E1", "Atladım": "#F59E0B"}
DIFF_ORDER = ["Kolay", "Orta", "Zor"]


def breakdown(title: str, rows: list[tuple[str, list[int]]], labels: tuple[str, ...], wide: bool = False,
              note: str = "") -> str:
    """Kırılım kartı: her satır bir grup (ör. 'Kolay'); çubuk durumlara göre yığılı, sağda 'ilk durum / toplam'."""
    body = "" if rows else '<div class="none">Bu gruplamada veri yok.</div>'
    for i, (name, counts) in enumerate(rows):
        total = max(1, sum(counts))
        detail = " · ".join(f"{lab}: {c}" for lab, c in zip(labels, counts))
        segs = "".join(f'<i style="width:{100 * c / total:.1f}%;background:{STAT_COLORS[lab]};'
                       f'animation-delay:{.15 + i * .06:.2f}s"></i>' for lab, c in zip(labels, counts) if c)
        body += (f'<div class="r" title="{style.esc(detail)}"><div class="nm">{style.esc(name)}</div>'
                 f'<div class="bar">{segs}</div><div class="ct"><b>{counts[0]}</b> / {sum(counts)}</div></div>')
    legend = "".join(f'<span><i style="background:{STAT_COLORS[lab]}"></i>{lab}</span>' for lab in labels)
    return (f'<div class="nr-bd{" wide" if wide else ""}"><div class="h">{style.esc(title)}<small>{style.esc(note)}</small>'
            f'</div>{body}<div class="nr-lg">{legend}</div></div>')


def breakdowns(records: list[dict], labels: tuple[str, ...]) -> str:
    """records: [{"diff", "type", "topic", "status"}] → zorluk ve soru tipi yan yana, konu altta geniş."""
    def group(key: str, order: list[str] | None = None, limit: int | None = None) -> list[tuple[str, list[int]]]:
        agg: dict[str, list[int]] = {}
        for r in records:
            agg.setdefault(r[key] or "Belirsiz", [0] * len(labels))[labels.index(r["status"])] += 1
        keys = [k for k in (order or []) if k in agg] + sorted((k for k in agg if k not in (order or [])),
                                                               key=lambda k: -sum(agg[k]))
        return [(k, agg[k]) for k in keys[:limit]]
    topics = group("topic", limit=8)
    note = f"en çok soru olan {len(topics)} konu" if len({r['topic'] for r in records}) > len(topics) else ""
    return ('<div class="nr-bdgrid">' + breakdown("Zorluğa göre", group("diff", DIFF_ORDER), labels)
            + breakdown("Soru tipine göre", group("type"), labels)
            + breakdown("Konuya göre", topics, labels, wide=True, note=note) + "</div>")


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

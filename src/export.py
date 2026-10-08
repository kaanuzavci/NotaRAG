"""Soru dışa aktarma: Moodle GIFT, yazdırılabilir sınav (HTML), CSV, JSON. Arayüzden bağımsız."""

from __future__ import annotations

import csv
import html
import io
import json
import time

LETTERS = "ABCD"
TYPE_TR = {"multiple_choice": "Çoktan seçmeli", "short_answer": "Kısa cevap", "true_false": "Doğru / Yanlış"}


TRANSPARENCY = ("Bu soru NotaRAG ile yapay zekâ kullanılarak üretildi; cevabı kaynaktaki cümleye bağlandı ve farklı "
                "bir model tarafından cevap anahtarı görülmeden yeniden çözülerek doğrulandı.")
DIFF_TR = {"easy": "Kolay", "medium": "Orta", "hard": "Zor"}


def _pretty(x) -> str:
    from src.textnorm import pretty_math
    return pretty_math(str(x))


def _doc(it: dict) -> str:
    return it.get("doc") or next(iter(it.get("chunk_ids") or []), "?").split(":")[0]


def _topic(it: dict) -> str:
    """Sorunun konusu: kanıt sayfası konu haritasında hangi konunun sayfalarındaysa (yoksa bölüm başlığı)."""
    from src.topics import topic_map
    page = it.get("check", {}).get("evidence_page")
    try:
        for t in topic_map(_doc(it), build_missing=False):
            if page in t["pages"]:
                return t["title"]
    except Exception:
        pass
    return it.get("unit") or "Genel"


def _doc_name(it: dict) -> str:
    from src.library import display_name  # kütüphanedeki görünen ad (değiştirilebilir); kayıtta yoksa dosya adından
    return display_name(_doc(it))


def _source(it: dict) -> str:
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    return f"{_doc_name(it)}{f', s.{page}' if page else ''}: “{_pretty(q.get('evidence_quote', ''))}”"


def _general_feedback(it: dict) -> list[str]:
    """Genel geri bildirim satırları: çözüm (varsa), kaynak, şeffaflık notu."""
    q = it["q"]
    lines = ["Çözüm: " + " → ".join(_pretty(x) for x in q["solution"])] if q.get("solution") else []
    return lines + ["Kaynak: " + _source(it), TRANSPARENCY]


def _option_feedback(q: dict, i: int) -> str:
    """Şık geri bildirimi; yeni sorularda çeldiricinin temsil ettiği hata da yazılır (option_notes, PROMPTS §2)."""
    if i == q["answer_index"]:
        return "Doğru."
    notes = q.get("option_notes") or []
    note = notes[i].strip() if i < len(notes) and notes[i] else ""
    right = f"Doğru cevap: {LETTERS[q['answer_index']]}) {_pretty(q['options'][q['answer_index']]).rstrip('.')}."
    return f"Yanlış. {_pretty(note)} {right}" if note else f"Yanlış. {right}"


def _numeric(it: dict) -> tuple[str, str] | None:
    """Kısa cevaplı hesap sorusunun sayısal cevabı (değer, tolerans): Moodle sayısal sorusu olur ('300' ve '300,0' doğru)."""
    from fractions import Fraction
    q = it["q"]
    if not q.get("compute") or q["type"] != "short_answer":
        return None
    try:
        f = Fraction(str(it.get("check", {}).get("computed", {}).get("value", "")).replace(" ", ""))
    except (ValueError, ZeroDivisionError):
        return None
    return (str(f.numerator), "0") if f.denominator == 1 else (f"{float(f):.6g}", "0.001")


def _ordered(items: list[dict]) -> list[tuple[int, dict, str]]:
    """(numara, soru, kategori yolu) — belge ve konuya göre gruplanmış."""
    rows = [(n, it, f"$course$/NotaRAG/{_doc_name(it)}/{_topic(it)}") for n, it in enumerate(items, 1)]
    return sorted(rows, key=lambda r: (r[2], r[0]))


def _gift_escape(s: str) -> str:
    # GIFT'te özel karakterler: ~ = # { } : ve \
    s = _pretty(s)
    for ch in "\\~=#{}:":
        s = s.replace(ch, "\\" + ch)
    return " ".join(str(s).split())


def to_gift(items: list[dict]) -> str:
    """Moodle 'GIFT' biçimi (Soru bankası → İçe aktar): konuya göre kategori, her şık için geri bildirim, genel geri
    bildirimde çözüm + kaynak + şeffaflık notu; kısa cevaplı hesap sorusu Moodle sayısal sorusu olarak."""
    out, last_cat = [], None
    for n, it, cat in _ordered(items):
        q = it["q"]
        if cat != last_cat:
            out.append("$CATEGORY: " + cat.replace(":", " -"))
            last_cat = cat
        diff = DIFF_TR.get(q.get("difficulty"), "")
        title = f"::NotaRAG-{n:03d}{' · ' + diff if diff else ''}::"
        stem = _gift_escape(q["question"])
        gen = _gift_escape(" · ".join(_general_feedback(it)))
        if q["type"] == "multiple_choice":
            opts = " ".join(("=" if i == q["answer_index"] else "~") + _gift_escape(o) + "#" +
                            _gift_escape(_option_feedback(q, i)) for i, o in enumerate(q["options"]))
            out.append(f"{title}{stem} {{{opts} ####{gen}}}")
        elif q["type"] == "true_false":
            key = "T" if q["answer"] == "true" else "F"
            out.append(f"{title}{stem} {{{key}#Yanlış.#Doğru. ####{gen}}}")  # ilk geri bildirim yanlış cevapta
        elif (num := _numeric(it)):
            out.append(f"{title}{stem} {{#={num[0]}:{num[1]}#Doğru. ####{gen}}}")
        else:
            out.append(f"{title}{stem} {{={_gift_escape(q['answer'])}#Doğru. ####{gen}}}")
    return "\n\n".join(out) + "\n"


def _cdata_html(lines) -> str:
    """Satırları <p> paragraflarına çevirip CDATA içine koyar (Moodle XML metin alanı)."""
    if isinstance(lines, str):
        lines = [lines]
    body = "".join(f"<p>{html.escape(_pretty(x))}</p>" for x in lines)
    return "<![CDATA[" + body.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def to_moodle_xml(items: list[dict]) -> str:
    """Moodle XML (Soru bankası → İçe aktar → Moodle XML): GIFT'in taşıyamadığı etiketleri de taşır
    (zorluk, tip, doğrulandı); şık başına geri bildirim; kısa cevaplı hesap sorusu sayısal soru tipi."""
    type_tag = {"multiple_choice": "coktan-secmeli", "true_false": "dogru-yanlis", "short_answer": "kisa-cevap"}
    out, last_cat = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"], None
    for n, it, cat in _ordered(items):
        q = it["q"]
        if cat != last_cat:
            out.append(f'  <question type="category"><category><text>{html.escape(cat)}</text></category></question>')
            last_cat = cat
        num = _numeric(it)
        qtype = {"multiple_choice": "multichoice", "true_false": "truefalse"}.get(
            q["type"], "numerical" if num else "shortanswer")
        tags = ["notarag", "zorluk-" + DIFF_TR.get(q.get("difficulty"), "belirsiz").lower(),
                "hesap" if q.get("compute") else type_tag.get(q["type"], q["type"])]
        if it.get("verification", {}).get("label") == "verified":
            tags.append("dogrulandi")
        x = [f'  <question type="{qtype}">',
             f"    <name><text>{html.escape(f'NotaRAG-{n:03d} · {_topic(it)}')}</text></name>",
             f'    <questiontext format="html"><text>{_cdata_html(q["question"])}</text></questiontext>',
             f'    <generalfeedback format="html"><text>{_cdata_html(_general_feedback(it))}</text></generalfeedback>',
             "    <defaultgrade>1</defaultgrade><penalty>0.3333333</penalty><hidden>0</hidden>"]
        if qtype == "multichoice":
            x.append("    <single>true</single><shuffleanswers>true</shuffleanswers><answernumbering>ABCD</answernumbering>")
            for i, o in enumerate(q["options"]):
                x.append(f'    <answer fraction="{100 if i == q["answer_index"] else 0}" format="html">'
                         f'<text>{_cdata_html(o)}</text><feedback format="html"><text>{_cdata_html(_option_feedback(q, i))}'
                         f"</text></feedback></answer>")
        elif qtype == "truefalse":
            for val in ("true", "false"):
                ok = q["answer"] == val
                x.append(f'    <answer fraction="{100 if ok else 0}" format="moodle_auto_format"><text>{val}</text>'
                         f'<feedback format="html"><text>{_cdata_html("Doğru." if ok else "Yanlış.")}</text></feedback></answer>')
        elif qtype == "numerical":
            x.append(f'    <answer fraction="100" format="moodle_auto_format"><text>{num[0]}</text>'
                     f'<feedback format="html"><text>{_cdata_html("Doğru.")}</text></feedback>'
                     f"<tolerance>{num[1]}</tolerance></answer>")
        else:
            x.append("    <usecase>0</usecase>")
            x.append(f'    <answer fraction="100" format="moodle_auto_format"><text>{html.escape(_pretty(q["answer"]))}</text>'
                     f'<feedback format="html"><text>{_cdata_html("Doğru.")}</text></feedback></answer>')
        x.append("    <tags>" + "".join(f"<tag><text>{t}</text></tag>" for t in tags) + "</tags>")
        x.append("  </question>")
        out += x
    out.append("</quiz>")
    return "\n".join(out) + "\n"


def to_csv(items: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["no", "belge", "tip", "soru", "A", "B", "C", "D", "cevap", "kanıt", "sayfa", "bloom", "sistem_kararı"])
    for n, it in enumerate(items, 1):
        q = it["q"]
        opts = (q.get("options") or [""] * 4) + [""] * 4
        ans = (LETTERS[q["answer_index"]] if q["type"] == "multiple_choice" else
               {"true": "Doğru", "false": "Yanlış"}.get(q["answer"], q["answer"]))
        w.writerow([n, it.get("doc", ""), TYPE_TR.get(q["type"], q["type"]), q["question"], *opts[:4], ans,
                    q.get("evidence_quote", ""), it.get("check", {}).get("evidence_page", ""), q.get("bloom_level", ""),
                    it.get("verification", {}).get("label", "")])
    return "﻿" + buf.getvalue()  # BOM: Excel Türkçe karakterleri doğru açsın


def to_json(items: list[dict]) -> str:
    keep = ("doc", "unit", "pages", "model", "q", "check", "verification")
    return json.dumps([{k: it.get(k) for k in keep} for it in items], ensure_ascii=False, indent=2)


def to_exam_html(items: list[dict], title: str, with_key: bool = True) -> str:
    """Yazdırılabilir sınav kâğıdı (tarayıcıda Yazdır → PDF). Cevap anahtarı ayrı sayfada."""
    from src.textnorm import pretty_math
    e = lambda x: html.escape(pretty_math(str(x)))  # LaTeX / ^ → okunur; sayılar da gelebilir
    qs = []
    for n, it in enumerate(items, 1):
        q = it["q"]
        body = f'<div class="q"><div class="n">{n}.</div><div><p>{e(q["question"])}</p>'
        if q["type"] == "multiple_choice":
            body += "<ol type='A'>" + "".join(f"<li>{e(o)}</li>" for o in q["options"]) + "</ol>"
        elif q["type"] == "true_false":
            body += "<p class='tf'>( ) Doğru &nbsp;&nbsp; ( ) Yanlış</p>"
        else:
            body += "<div class='line'></div>"
        qs.append(body + "</div></div>")
    key = ""
    if with_key:
        rows = "".join(
            f"<tr><td>{n}</td><td>{e(LETTERS[it['q']['answer_index']] if it['q']['type'] == 'multiple_choice' else {'true': 'Doğru', 'false': 'Yanlış'}.get(it['q']['answer'], it['q']['answer']))}</td>"
            f"<td>{e(it.get('doc', ''))} · s.{e(it.get('check', {}).get('evidence_page', '?'))}</td>"
            f"<td><mark>{e(it['q'].get('evidence_quote', ''))}</mark>"
            + (f"<div class='sol'>Çözüm: {' → '.join(e(s) for s in it['q']['solution'])}</div>"
               if it["q"].get("solution") else "") + "</td></tr>"
            for n, it in enumerate(items, 1))
        key = (f"<section class='key'><h2>Cevap anahtarı ve kaynaklar</h2><table><tr><th>No</th><th>Cevap</th>"
               f"<th>Kaynak</th><th>Kanıt</th></tr>{rows}</table></section>")
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{e(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Instrument+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
 body {{ font-family: 'Instrument Sans', sans-serif; color: #1E2433; max-width: 780px; margin: 2.5rem auto; padding: 0 1.2rem; }}
 h1 {{ font-family: 'Fraunces', serif; font-weight: 600; margin: 0; }}
 .sub {{ color: #6B6F7B; margin: .3rem 0 1.4rem; font-size: .92rem; }}
 .note {{ margin-top: 2rem; padding-top: .8rem; border-top: 1px solid #DDD; color: #6B6F7B; font-size: .8rem; }}
 hr {{ border: 0; border-top: 3px double #CFC5AF; margin: 1rem 0 1.6rem; }}
 .q {{ display: grid; grid-template-columns: 2rem 1fr; gap: .2rem; margin-bottom: 1.25rem; break-inside: avoid; }}
 .n {{ font-weight: 600; }} .q p {{ margin: 0 0 .4rem; }} ol {{ margin: .2rem 0 0 1.1rem; }} li {{ margin: .15rem 0; }}
 .line {{ border-bottom: 1px solid #999; height: 1.6rem; width: 70%; }} .tf {{ color: #333; }}
 .key {{ break-before: page; }} h2 {{ font-family: 'Fraunces', serif; font-weight: 600; }}
 table {{ border-collapse: collapse; width: 100%; font-size: .88rem; }} td, th {{ border-bottom: 1px solid #DDD; padding: .35rem .4rem; text-align: left; vertical-align: top; }}
 mark {{ background: #F7E58A; }} .sol {{ margin-top: .3rem; color: #2F6B4F; font-size: .84rem; }}
 @media print {{ body {{ margin: 0 auto; }} }}
</style></head><body><h1>{e(title)}</h1>
<div class="sub">{len(items)} soru · Yapay zekâ ile üretildi, kaynağa bağlandı ve doğrulandı (NotaRAG) · {time.strftime('%d.%m.%Y')}</div><hr>
{''.join(qs)}{key}<p class="note">{e(TRANSPARENCY)} Hesap sorularının sonucu ayrıca kodla (SymPy) yeniden hesaplandı.
Sorular öğretmen tarafından gözden geçirilmeden sınavda not vermek için kullanılmamalıdır.</p></body></html>"""

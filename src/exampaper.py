"""Basılı sınav kâğıdı (PDF): soru bankasından seçilen soruları A4 / A3 kâğıda şablonla yerleştirir. Arayüzden bağımsız.

Neden PDF (HTML değil)? Kâğıdın boyu, sütunları ve sayfa sonları kesin olsun: aynı dosya her yazıcıda aynı çıkar. PyMuPDF
yeterli: HTML + CSS'i doğrudan sayfaya yazar (Page.insert_htmlbox), yeni bağımlılık yok, Türkçe harfler ve matematik
simgeleri (√ ≤ ² ₁ …) PyMuPDF'in gömülü Nimbus / Noto yazı tiplerinde var.

Yerleşim (layout): sorular sırayla sütunlara dizilir; bir soru iki sütuna / sayfaya bölünmez (sığmazsa sonraki sütunun
başına geçer). Yazı boyu şablonun doğal boyundan başlayıp yarım punto adımlarla küçülür; en az sayfaya sığdıran en büyük boy seçilir
(alt sınırda durur: okunmayacak kadar küçük kâğıt çıkmasın; sığmazsa sayfa eklenir). İlk sayfanın üstünde başlık
bandı (ortalı: isteğe bağlı üst yazı — kurum, bölüm, dönem —, başlık, ders · tarih · süre, ad-soyad / numara / puan satırı,
açıklama), son sorunun ardından isteğe bağlı sınav sonu yazısı, her sayfanın altında sayfa numarası var.
Cevap anahtarı ayrı PDF'tir: sınav kâğıdı öğrenciye verilirken anahtarı yanlışlıkla çıktıya girmesin.

Ek çıktılar (kullanıcı isteği 2026-10-09):
  A / B kitapçığı  booklet_b(): sorular kendi türü içinde yer değiştirir (çoktan seçmeli yine çoktan seçmeli yuvasına),
                   çoktan seçmeli şıklar karışır. Tür yuvaları aynı kaldığı için tek optik form iki kitapçıkta da geçer.
                   Cevap anahtarında iki kitapçığın cevapları ayrı tablolarda, ayrıntılarda "B'de kaçıncı soru".
  Optik form       build_sheet(): ad-soyad, 10 haneli öğrenci numarası ızgarası, kitapçık türü, her soru için A-D
                   (doğru/yanlışta D-Y) yuvarlakları; kısa cevaplı sorular için "yazılı" kutusu.
  Belirtke tablosu blueprint(): konu × bilişsel düzey (Bloom) ve zorluk dağılımı, soru sayısı ve puan; cevap anahtarının
                   ilk sayfasında, arayüzde tablo olarak.
"""

from __future__ import annotations

import html
import random
import time
from dataclasses import dataclass

from src.textnorm import pretty_math

LETTERS = "ABCDE"
BLOOM_TR = {"remember": "Hatırlama", "understand": "Anlama", "apply": "Uygulama", "analyze": "Analiz",
            "evaluate": "Değerlendirme", "create": "Yaratma"}
DIFF_TR = {"easy": "Kolay", "medium": "Orta", "hard": "Zor"}
INK = "#14181F"


@dataclass(frozen=True)
class Template:
    key: str
    label: str
    note: str
    paper: str          # pymupdf.paper_size adı
    landscape: bool
    cols: int
    font_max: float     # başlangıç (en büyük) yazı boyu, punto
    font_min: float
    pages: int          # şablonun hedef sayfa sayısı (açıklamada; sığmazsa sayfa eklenir)
    advice: tuple[int, int]  # önerilen soru sayısı aralığı


TEMPLATES: dict[str, Template] = {t.key: t for t in (
    Template("a4_1", "A4 · tek sütun", "Klasik sınav kâğıdı: geniş, rahat okunur.", "a4", False, 1, 11, 10, 3, (10, 20)),
    Template("a4_2", "A4 · iki sütun", "Yoğun düzen: 20–30 soru, ön-arka iki yüze sığar.", "a4", False, 2, 10, 8.5, 2, (20, 30)),
    Template("a3_2", "A3 yatay · iki sütun", "Büyük kâğıt, iki geniş sütun: katlanınca A4 gibi.", "a3", True, 2, 11.5, 9.5, 1, (16, 28)),
    Template("a3_3", "A3 yatay · üç sütun", "Tek yüz: dergi düzeni, A3'ün tamamı dolar.", "a3", True, 3, 10.5, 8.5, 1, (24, 30)),
)}


@dataclass
class Meta:
    title: str = "Deneme Sınavı"
    course: str = ""
    date: str = ""
    minutes: int = 0
    note: str = ""            # başlığın altındaki açıklama (yönerge); birden çok satır olabilir
    top: str = ""             # en üstte ortalı serbest yazı (kurum, bölüm, dönem…); her satır ayrı
    end: str = ""             # son sorunun ardından ortalı serbest yazı (ör. "Başarılar dilerim. — Dr. …")
    points: bool = True       # her sorunun puanı (100 / soru sayısı) yazılsın
    name_box: bool = True     # ad-soyad / numara / puan kutusu
    by_type: bool = False     # türe göre sırala (çoktan seçmeli → doğru-yanlış → kısa cevap)


def _e(x) -> str:
    return html.escape(pretty_math(str(x)))


def _lines(text: str) -> str:
    """Kullanıcının yazdığı çok satırlı metin → kaçışlı, satırları <br> ile (boş satırlar atılır)."""
    return "<br>".join(_e(x.strip()) for x in str(text).splitlines() if x.strip())


# ---------------------------------------------------------------- soru bloğu

def _points(n: int) -> str:
    p = 100 / max(1, n)
    return f"{p:g}" if p == int(p) else f"{p:.1f}".replace(".", ",")


def _question_html(n: int, it: dict, meta: Meta, total: int) -> str:
    q = it["q"]
    pts = f' <span class="pt">({_points(total)}&nbsp;p)</span>' if meta.points else ""
    out = [f'<div class="q"><p class="qt"><b>{n}.</b> {_e(q["question"])}{pts}</p>']
    if q["type"] == "multiple_choice":
        out += [f'<p class="o"><b>{LETTERS[i]})</b> {_e(o)}</p>' for i, o in enumerate(q["options"])]
    elif q["type"] == "true_false":
        out.append('<p class="o">(&nbsp;&nbsp;&nbsp;) Doğru &nbsp;&nbsp;&nbsp;&nbsp; (&nbsp;&nbsp;&nbsp;) Yanlış</p>')
    elif q.get("compute"):
        out.append('<p class="o">Cevap: ' + "_" * 26 + "</p>")
    else:
        out.append('<p class="ln2">&nbsp;</p><p class="ln2">&nbsp;</p>')
    return "".join(out) + "</div>"


def _css(font: float) -> str:
    return (f"body {{ font-family: sans-serif; font-size: {font}pt; color: {INK}; line-height: 1.22; }}"
            f".q {{ margin: 0; }} .qt {{ margin: 0 0 {font * .28:.1f}pt 0; }}"
            f".o {{ margin: 0 0 {font * .16:.1f}pt {font * 1.5:.1f}pt; text-indent: -{font * 1.05:.1f}pt; }}"
            ".pt { color: #6B6F7B; font-size: 85%; }"
            f".ln {{ border-bottom: .6pt solid #888; }}"
            f".ln2 {{ margin: 0 0 {font * .3:.1f}pt {font * 1.5:.1f}pt; border-bottom: .6pt solid #999; line-height: {font * 1.7:.1f}pt; }}"
            f".end {{ text-align: center; border-top: .6pt solid #BBB; padding-top: {font * .7:.1f}pt; margin-top: {font * .4:.1f}pt; }}"
            ".end p { margin: 0; }")


# ---------------------------------------------------------------- yerleşim

def _measure(html_: str, width: float, css: str) -> float:
    """Bloğun gerçek yüksekliği. Story.place() ölçümü insert_htmlbox'ın çizdiğinden ~%40 büyüktü (gövde kenar boşlukları):
    ölçüm de çizimle aynı yoldan yapılır, boş bir sayfaya çizilip artan yükseklik çıkarılır."""
    import pymupdf
    page = _scratch().new_page(width=width, height=3000)
    spare, _ = page.insert_htmlbox(pymupdf.Rect(0, 0, width, 3000), html_, css=css)
    return 3000 - spare


_scratch_doc = None


def _scratch():
    global _scratch_doc
    import pymupdf
    if _scratch_doc is None or _scratch_doc.page_count > 400:  # ölçüm sayfaları birikmesin
        _scratch_doc = pymupdf.open()
    return _scratch_doc


def _geometry(t: Template) -> dict:
    import pymupdf
    w, h = pymupdf.paper_size(t.paper)
    if t.landscape:
        w, h = h, w
    m = 36 if t.paper == "a4" else 42
    gap = 18 if t.cols > 1 else 0
    colw = (w - 2 * m - gap * (t.cols - 1)) / t.cols
    # head: ilk sayfada başlık bandının yüksekliği; build_exam başlığın kendisini ölçüp yerine koyar
    return {"w": w, "h": h, "m": m, "gap": gap, "colw": colw, "head": 92, "foot": 26}


def _layout(blocks: list[str], font: float, t: Template, g: dict) -> tuple[list[tuple], int]:
    """Soruları (sayfa, sütun, y, yükseklik) olarak yerleştirir → (yerleşim, sayfa sayısı)."""
    css, space = _css(font), font * 1.1
    page = col = 0
    y = g["m"] + g["head"]
    bottom = g["h"] - g["m"] - g["foot"]
    placed = []
    for b in blocks:
        hgt = _measure(b, g["colw"], css) + 1
        if y + hgt > bottom and y > (g["m"] + (g["head"] if page == 0 else 0)):  # sütun doluysa sonrakine
            col += 1
            if col == t.cols:
                page, col = page + 1, 0
            y = g["m"] + (g["head"] if page == 0 else 0)
        placed.append((page, col, y, hgt))
        y += hgt + space
    return placed, page + 1


def _fit(blocks: list[str], t: Template, g: dict) -> tuple[float, list[tuple], int]:
    """En az sayfaya sığdıran en büyük yazı boyu (alt sınır font_min): 15 soru 3. sayfaya iki soru taşıyorsa yazı bir
    kademe küçülür ve kâğıt iki sayfa olur; ama okunmayacak kadar küçülmez."""
    font, best = t.font_max, None
    while True:
        placed, pages = _layout(blocks, font, t, g)
        if best is None or pages < best[2]:
            best = (font, placed, pages)
        if pages == 1 or font <= t.font_min:
            return best
        font = round(font - .5, 1)


def _head_html(meta: Meta, n: int, booklet: str = "") -> str:
    """İlk sayfanın başlığı, sınav kâğıtlarındaki gibi ortalı: üst yazı (kurum, bölüm, dönem), başlık, ders · tarih ·
    süre · soru sayısı, ad-soyad / numara / puan satırı, açıklama."""
    bits = [b for b in (meta.course, meta.date, f"Süre: {meta.minutes} dk" if meta.minutes else "", f"{n} soru",
                        f"{booklet} kitapçığı" if booklet else "") if b]
    out = [f'<p class="top">{_lines(meta.top)}</p>' if meta.top.strip() else "",
           f'<h1>{_e(meta.title)}</h1><p class="sub">{" &nbsp;·&nbsp; ".join(_e(b) for b in bits)}</p>']
    if meta.name_box:
        out.append('<table class="nb"><tr><td width="50%">Ad Soyad: ______________________________</td>'
                   '<td width="28%">Numara: ________________</td><td width="22%">Puan: __________</td></tr></table>')
    if meta.note.strip():
        out.append(f'<p class="nt">{_lines(meta.note)}</p>')
    return "".join(out)


_HEAD_CSS = (f"body {{ font-family: sans-serif; color: {INK}; text-align: center; }}"
             ".top { font-size: 10pt; font-weight: bold; line-height: 1.35; margin: 0 0 5pt 0; }"
             "h1 { font-size: 18pt; margin: 0 0 3pt 0; text-align: center; }"
             ".sub { font-size: 9.5pt; color: #4A5163; margin: 0 0 8pt 0; }"
             ".nb { width: 100%; margin: 0 0 5pt 0; } .nb td { font-size: 9.5pt; text-align: left; padding: 2pt 0; }"
             ".nt { font-size: 9pt; color: #2A3040; margin: 0; text-align: left; line-height: 1.35; }")


def _order(items: list[dict], by_type: bool) -> list[dict]:
    if not by_type:
        return list(items)
    rank = {"multiple_choice": 0, "true_false": 1, "short_answer": 2}
    return sorted(items, key=lambda it: rank.get(it["q"]["type"], 3))  # sıralama kararlı: tür içinde seçim sırası


def prepare(items: list[dict], meta: Meta) -> list[dict]:
    """A kitapçığının (tek kitapçıkta kâğıdın) soru sırası."""
    return _order(items, meta.by_type)


def build_exam(items: list[dict], template: str, meta: Meta, booklet: str = "") -> tuple[bytes, dict]:
    """Sınav kâğıdı PDF'i → (pdf, bilgi). bilgi: sayfa sayısı, yazı boyu, kâğıt. booklet ('A' / 'B'): sıra zaten
    hazırlanmış (prepare / booklet_b), başlıkta kitapçık yazar."""
    import pymupdf
    t = TEMPLATES[template]
    items = list(items) if booklet else _order(items, meta.by_type)
    if not items:
        raise ValueError("Kâğıda konacak soru yok.")
    g = _geometry(t)
    head_html = _head_html(meta, len(items), booklet)
    g["head"] = _measure(head_html, g["w"] - 2 * g["m"], _HEAD_CSS) + 16  # başlık + alt çizgi payı
    blocks = [_question_html(i, it, meta, len(items)) for i, it in enumerate(items, 1)]
    if meta.end.strip():  # sınav sonu yazısı: son sorunun ardından (aynı sütunda), ortalı
        blocks.append(f'<div class="end"><p>{_lines(meta.end)}</p></div>')
    font, placed, pages = _fit(blocks, t, g)
    css = _css(font)
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page(width=g["w"], height=g["h"])
    for b, (pg, col, y, hgt) in zip(blocks, placed):
        x = g["m"] + col * (g["colw"] + g["gap"])
        doc[pg].insert_htmlbox(pymupdf.Rect(x, y, x + g["colw"], y + hgt + 6), b, css=css)
    first = doc[0]
    first.insert_htmlbox(pymupdf.Rect(g["m"], g["m"], g["w"] - g["m"], g["m"] + g["head"]), head_html, css=_HEAD_CSS)
    ruler = g["m"] + g["head"] - 9  # başlık bandının altındaki çizgi
    first.draw_line((g["m"], ruler), (g["w"] - g["m"], ruler), color=(.2, .22, .3), width=1.2)
    for p_no, page in enumerate(doc):
        top = g["m"] + (g["head"] - 4 if p_no == 0 else 0)
        for c in range(1, t.cols):  # sütun ayıracı
            x = g["m"] + c * (g["colw"] + g["gap"]) - g["gap"] / 2
            page.draw_line((x, top), (x, g["h"] - g["m"] - g["foot"] + 4), color=(.8, .78, .72), width=.6)
        foot_y = g["h"] - g["m"] - g["foot"] + 10
        page.draw_line((g["m"], foot_y), (g["w"] - g["m"], foot_y), color=(.8, .78, .72), width=.6)
        page.insert_htmlbox(pymupdf.Rect(g["m"], foot_y + 3, g["w"] - g["m"], foot_y + 20),
                            f'<p style="font-size:8pt;color:#6B6F7B;margin:0">{_e(meta.title)}'
                            f' &nbsp;·&nbsp; Sayfa {p_no + 1} / {pages} &nbsp;·&nbsp; NotaRAG</p>')
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out, {"pages": pages, "font": font, "paper": t.paper.upper(), "questions": len(items)}


# ---------------------------------------------------------------- cevap anahtarı

def _answer_text(q: dict) -> str:
    if q["type"] == "multiple_choice":
        return f"{LETTERS[q['answer_index']]}) {q['options'][q['answer_index']]}"
    if q["type"] == "true_false":
        return {"true": "Doğru", "false": "Yanlış"}.get(q["answer"], str(q["answer"]))
    return str(q.get("answer", ""))


def _short(q: dict) -> str:
    """Özet tablosundaki kısa cevap: şık harfi, Doğru / Yanlış ya da cevabın başı."""
    return LETTERS[q["answer_index"]] if q["type"] == "multiple_choice" else _answer_text(q)[:14]


def _kind(it: dict) -> str:
    """Optik formdaki yuva türü: çoktan seçmeli, doğru-yanlış ya da yazılı (kısa cevap ve hesap)."""
    return {"multiple_choice": "mc", "true_false": "tf"}.get(it["q"]["type"], "sa")


def _shuffle_options(it: dict, rnd: random.Random) -> dict:
    """Çoktan seçmeli sorunun şıklarını karıştırır (doğru cevabın yeri değişir); şıkla aynı uzunluktaki listeler
    (şık notları, şık değerleri) aynı sırayla taşınır. Öbür türler olduğu gibi."""
    q = it["q"]
    if q["type"] != "multiple_choice" or len(q.get("options") or []) < 2:
        return it
    n = len(q["options"])
    perm = list(range(n))
    while perm == list(range(n)):
        rnd.shuffle(perm)
    nq = dict(q)
    for key in ("options", "option_notes", "option_values"):
        if isinstance(q.get(key), list) and len(q[key]) == n:
            nq[key] = [q[key][k] for k in perm]
    nq["answer_index"] = perm.index(q["answer_index"])
    return {**it, "q": nq}


def booklet_b(items: list[dict], seed: int = 7) -> list[dict]:
    """A kitapçığından B: sorular kendi türü içinde yer değiştirir (tür yuvaları aynı → tek optik form), şıklar karışır."""
    rnd, out = random.Random(seed), list(items)
    for kind in ("mc", "tf", "sa"):
        slots = [i for i, it in enumerate(items) if _kind(it) == kind]
        perm = slots[:]
        if len(slots) > 1:
            while perm == slots:
                rnd.shuffle(perm)
        for slot, src in zip(slots, perm):
            out[slot] = items[src]
    return [_shuffle_options(it, rnd) for it in out]


def blueprint(items: list[dict]) -> dict:
    """Belirtke tablosu: konu × bilişsel düzey ve zorluk. → {"levels": [...], "diffs": [...], "rows": [{topic, n,
    points, levels: {düzey: sayı}, diffs: {zorluk: sayı}}], "total": {...}}. Puan: her soru eşit (100 / n)."""
    from src.export import _topic
    n = max(1, len(items))
    levels = [k for k in BLOOM_TR if any(it["q"].get("bloom_level") == k for it in items)]
    diffs = [k for k in DIFF_TR if any(it["q"].get("difficulty") == k for it in items)]
    rows: dict[str, dict] = {}
    for it in items:
        t = _topic(it)
        r = rows.setdefault(t, {"topic": t, "n": 0, "levels": dict.fromkeys(levels, 0), "diffs": dict.fromkeys(diffs, 0)})
        r["n"] += 1
        if (lv := it["q"].get("bloom_level")) in r["levels"]:
            r["levels"][lv] += 1
        if (df := it["q"].get("difficulty")) in r["diffs"]:
            r["diffs"][df] += 1
    out = sorted(rows.values(), key=lambda r: -r["n"])
    for r in out:
        r["points"] = round(100 * r["n"] / n, 1)
    total = {"topic": "Toplam", "n": len(items), "points": 100.0,
             "levels": {k: sum(r["levels"][k] for r in out) for k in levels},
             "diffs": {k: sum(r["diffs"][k] for r in out) for k in diffs}}
    return {"levels": levels, "diffs": diffs, "rows": out, "total": total}


def _blueprint_html(bp: dict) -> str:
    head = ("<tr><th>Konu</th>" + "".join(f"<th>{BLOOM_TR[k]}</th>" for k in bp["levels"])
            + "".join(f"<th>{DIFF_TR[k]}</th>" for k in bp["diffs"]) + "<th>Soru</th><th>Puan</th></tr>")
    def row(r: dict, cls: str = "") -> str:
        return (f'<tr class="{cls}"><td>{_e(r["topic"])}</td>' + "".join(f'<td class="c">{r["levels"][k] or ""}</td>' for k in bp["levels"])
                + "".join(f'<td class="c">{r["diffs"][k] or ""}</td>' for k in bp["diffs"])
                + f'<td class="c"><b>{r["n"]}</b></td><td class="c">{r["points"]:g}</td></tr>')
    return ('<h2>Belirtke tablosu</h2><p class="sub">Soruların konulara, bilişsel düzeye (Bloom) ve zorluğa dağılımı. '
            'Zorluk: üretecin iddiası + yapı kuralı (gerçek öğrenci verisiyle güncellenir).</p>'
            f'<table class="bp">{head}{"".join(row(r) for r in bp["rows"])}{row(bp["total"], "t")}</table>')


def build_key(items: list[dict] | dict[str, list[dict]], meta: Meta) -> bytes:
    """Cevap anahtarı PDF'i (A4): belirtke tablosu, özet tablo(lar), her sorunun cevabı, çözümü ve kaynak cümlesi.
    items: tek kâğıt için soru listesi ya da kitapçıklar {"A": [...], "B": [...]} (sıralar hazırlanmış)."""
    import pymupdf
    books = items if isinstance(items, dict) else {"": _order(items, meta.by_type)}
    first = next(iter(books.values()))
    per = 6

    def grid(lst: list[dict]) -> str:
        return "".join("<tr>" + "".join(f'<td><b>{i}</b> &nbsp;{_e(_short(it["q"]))}</td>'
                                        for i, it in list(enumerate(lst, 1))[k:k + per]) + "</tr>"
                       for k in range(0, len(lst), per))
    tables = "".join((f"<h3>{b} kitapçığı</h3>" if b else "") + f'<table class="g">{grid(lst)}</table>' for b, lst in books.items())
    where_b = {it["id"]: (i, it) for i, it in enumerate(books.get("B", []), 1)}
    detail = []
    for i, it in enumerate(first, 1):
        q, ev = it["q"], it.get("check", {}).get("evidence_page")
        sol = ("<p class='s'>Çözüm: " + " → ".join(_e(s) for s in q["solution"]) + "</p>") if q.get("solution") else ""
        b = where_b.get(it["id"])
        other = f' &nbsp;·&nbsp; B kitapçığında {b[0]}. soru, cevap <b>{_e(_short(b[1]["q"]))}</b>' if b else ""
        detail.append(f'<div class="d"><p class="h"><b>{i}.</b> {_e(str(q["question"])[:240])}</p>'
                      f'<p class="a">Cevap: <b>{_e(_answer_text(q))}</b>{other}</p>{sol}'
                      f'<p class="k">Kaynak{f" (s.{ev})" if ev else ""}: “{_e(q.get("evidence_quote", ""))}”</p></div>')
    label = " · ".join(f"{b} kitapçığı" for b in books if b)
    body = (f'<h1>Cevap anahtarı</h1><p class="sub">{_e(meta.title)} · {len(first)} soru{f" · {label}" if label else ""} · '
            f'{time.strftime("%d.%m.%Y")}</p>{tables}{_blueprint_html(blueprint(first))}<h2>Ayrıntılar</h2>{"".join(detail)}'
            '<p class="sub">Bu anahtar öğrenciye verilen kâğıttan ayrıdır. Sorular yapay zekâ ile üretildi, kaynağa bağlandı '
            've doğrulandı; yine de sınavda kullanmadan önce öğretmen gözden geçirmelidir.</p>')
    css = (f"body {{ font-family: sans-serif; font-size: 9.5pt; color: {INK}; line-height: 1.3; }} h1 {{ font-size: 18pt; margin: 0 0 2pt 0; }}"
           "h2 { font-size: 12pt; margin: 14pt 0 4pt 0; } h3 { font-size: 10pt; margin: 8pt 0 3pt 0; }"
           ".sub { color: #4A5163; font-size: 9pt; margin: 0 0 8pt 0; }"
           "table.g { width: 100%; } .g td { border: .6pt solid #BBB; padding: 3pt 5pt; font-size: 10pt; }"
           "table.bp { width: 100%; } .bp th { font-size: 8pt; text-align: left; border-bottom: .8pt solid #555; padding: 2pt 3pt; }"
           ".bp td { font-size: 8.5pt; border-bottom: .4pt solid #CCC; padding: 2pt 3pt; } .bp td.c { text-align: center; }"
           ".bp tr.t td { font-weight: bold; border-top: .8pt solid #555; }"
           ".d { margin: 0 0 7pt 0; } .d p { margin: 0 0 1.5pt 0; } .a { color: #1F5A3E; } .s { color: #4A5163; }"
           ".k { color: #6B6F7B; font-size: 8.5pt; }")
    story = pymupdf.Story(html=body, user_css=css)
    import io
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    media, where = pymupdf.paper_rect("a4"), pymupdf.paper_rect("a4") + (40, 40, -40, -44)
    more = 1
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()


# ---------------------------------------------------------------- optik cevap kâğıdı

def build_sheet(items: list[dict], meta: Meta, booklets: tuple[str, ...] = ()) -> bytes:
    """Optik cevap kâğıdı (A4). items: A kitapçığının sırası (B'de tür yuvaları aynı, bu yüzden tek form yeter)."""
    import pymupdf
    ink, soft, mute = (.12, .14, .2), (.55, .52, .46), (.42, .44, .5)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    m, w = 36, 595
    page.insert_htmlbox(pymupdf.Rect(m, m, w - m, m + 44),
                        f'<p style="font-size:15pt;font-weight:bold;margin:0">Optik cevap kâğıdı</p>'
                        f'<p style="font-size:9pt;color:#4A5163;margin:2pt 0 0 0">{_e(meta.title)}'
                        + "".join(f" &nbsp;·&nbsp; {_e(x)}" for x in (meta.course, meta.date) if x) + '</p>')
    page.draw_line((m, m + 48), (w - m, m + 48), color=ink, width=1.1)

    # Sol üst: ad-soyad, imza, kitapçık türü, yönerge
    y0 = m + 62
    for k, lab in enumerate(("Ad Soyad", "İmza")):
        yy = y0 + k * 34
        page.insert_htmlbox(pymupdf.Rect(m, yy, m + 70, yy + 14), f'<p style="font-size:8.5pt;color:#4A5163;margin:0">{lab}</p>')
        page.draw_line((m + 62, yy + 12), (m + 300, yy + 12), color=soft, width=.6)

    def bubble(cx: float, cy: float, label: str, r: float = 5.6) -> None:
        page.draw_circle((cx, cy), r, color=ink, width=.7)
        page.insert_text((cx - (1.9 if len(label) == 1 else 3.6), cy + 2.3), label, fontsize=6.2, fontname="helv", color=soft)

    yb = y0 + 78
    if booklets:
        page.insert_htmlbox(pymupdf.Rect(m, yb - 6, m + 90, yb + 10), '<p style="font-size:8.5pt;color:#4A5163;margin:0">Kitapçık türü</p>')
        for k, b in enumerate(booklets):
            bubble(m + 100 + k * 26, yb, b)
    page.insert_htmlbox(pymupdf.Rect(m, yb + 18, m + 300, yb + 60),
                        '<p style="font-size:7.5pt;color:#6B6F7B;margin:0;line-height:1.35">Yuvarlakları koyu kalemle tam '
                        'doldurun; değiştirmek isterseniz tamamen silin. Her soru için tek yuvarlak. Kısa cevaplı sorular '
                        '“yazılı” kutusuna yazılır.</p>')

    # Sağ üst: 10 haneli öğrenci numarası (üstte yazma kutuları, altında 0-9 yuvarlakları)
    nx, ny, cw, rh = w - m - 10 * 15.5, y0 + 4, 15.5, 13.2
    page.insert_htmlbox(pymupdf.Rect(nx, ny - 15, w - m, ny), '<p style="font-size:8.5pt;color:#4A5163;margin:0">Öğrenci numarası</p>')
    for c in range(10):
        x = nx + c * cw
        page.draw_rect(pymupdf.Rect(x + 1, ny + 2, x + cw - 1, ny + 16), color=soft, width=.6)
        for d in range(10):
            bubble(x + cw / 2, ny + 26 + d * rh, str(d), r=5.2)

    # Cevaplar: en çok 4 sütun, sütun başına ~12 soru; satır yüksekliği kalan yere göre (işaretlemesi rahat olsun)
    top = ny + 26 + 10 * rh + 22
    page.draw_line((m, top - 14), (w - m, top - 14), color=soft, width=.6)
    ncols = min(4, max(1, -(-len(items) // 12)))
    per_col = -(-len(items) // ncols)
    rowh = min(26.0, (842 - m - 30 - top) / max(1, per_col))
    colw = (w - 2 * m) / 4
    for i, it in enumerate(items):
        c, r = divmod(i, per_col)
        x, y = m + c * colw, top + r * rowh
        page.insert_text((x + 2, y + 3), f"{i + 1:>2}.", fontsize=8.5, fontname="hebo", color=ink)
        kind = _kind(it)
        if kind == "mc":
            for k in range(min(5, len(it["q"].get("options") or []))):
                bubble(x + 32 + k * 17, y, LETTERS[k])
        elif kind == "tf":
            bubble(x + 32, y, "D")
            bubble(x + 49, y, "Y")
        else:
            page.draw_rect(pymupdf.Rect(x + 26, y - 7, x + colw - 10, y + 7), color=soft, width=.6)
            page.insert_htmlbox(pymupdf.Rect(x + 29, y - 5, x + 70, y + 6),  # Türkçe harf: yerleşik helv'de "ı" yok
                                '<p style="font-size:6pt;color:#6B6F7B;margin:0">yazılı</p>')
    foot = 842 - m
    page.draw_line((m, foot - 14), (w - m, foot - 14), color=soft, width=.6)
    page.insert_htmlbox(pymupdf.Rect(m, foot - 11, w - m, foot + 4),
                        f'<p style="font-size:7.5pt;color:#6B6F7B;margin:0">{_e(meta.title)} &nbsp;·&nbsp; {len(items)} soru'
                        f'{" &nbsp;·&nbsp; A ve B kitapçıklarında aynı form" if len(booklets) > 1 else ""} &nbsp;·&nbsp; NotaRAG</p>')
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out


def previews(pdf: bytes, dpi: int = 72) -> list[bytes]:
    """Her sayfanın PNG önizlemesi (arayüzde kâğıdı indirmeden görmek için)."""
    import pymupdf
    with pymupdf.open(stream=pdf) as doc:
        return [p.get_pixmap(dpi=dpi).tobytes("png") for p in doc]

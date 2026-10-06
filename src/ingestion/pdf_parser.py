"""PDF → sayfa sayfa yapılandırılmış metin (ROADMAP Adım 3).

Her sayfa için: başlık, gövde metni, şekil üzerindeki metin, kalite etiketi ve dil.
Görsel fallback (Gemini) burada çağrılmaz; yalnızca 'needs_vision' etiketiyle işaretlenir.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pymupdf

from src.textnorm import clean_line, detect_language, join_lines, resolve_hyphens, to_script

REPEAT_MIN_RATIO = 0.4          # satır sayfaların en az %40'ında tekrar ediyorsa üst/alt bilgi adayı
BACKGROUND_COVER = 0.9          # sayfanın %90'ından büyük görsel = slayt arka planı
BACKGROUND_REPEAT = 0.4         # sayfaların %40'ında tekrar eden görsel = şablon/logo
FIGURE_MIN_COVER = 0.08         # bundan büyük içerik görseli/diyagramı "anlamlı görsel" sayılır
MIN_TEXT_CHARS = 80             # gövde metni bundan kısaysa sayfa "az metinli"
HEADING_SIZE_RATIO = 1.2        # başlık, sayfadaki gövde yazısından en az bu kadar büyük olmalı
SINGLE_LINE_HEADING_SIZE = 24   # tek satırlık slaytta bu puntodan büyük satır başlık sayılır
FIGURE_LABEL_MAX_WORDS = 4
TITLE_PAGE_MAX_CHARS = 300      # ilk sayfa bundan kısaysa kapak sayılır
NOISY_RATIO = 0.4               # satırların bu oranı "parça" ise metin katmanı bozuk sayılır
NOISY_MIN_LINES = 4
TABLE_MIN_FILL = 0.5            # hücrelerin en az yarısı dolu değilse "tablo" sayılmaz
TABLE_MAX_SINGLE_ROWS = 0.4     # satırların %40'ından fazlası tek hücreliyse "tablo" sayılmaz
TABLE_MAX_CELL_LINES = 8        # bundan uzun hücre konteyner sayılır (gerçek çok satırlı hücreler ≤ 6)
LABEL_SIZE_ON_FIGURE = 0.85     # şekil üzerindeki kısa satır, gövde yazısının %85'inden küçükse etiket
LABEL_SIZE_ANYWHERE = 0.7       # konumdan bağımsız: gövdenin %70'inden küçük kısa satır etiket/dipnot
TOP_BAND = 0.12                 # boyutla başlık bulunamazsa en üst şerit başlık sayılır


@dataclass
class Line:
    text: str
    size: float
    bbox: pymupdf.Rect  # görsel (döndürülmüş) koordinatlarda
    block: int


@dataclass
class PageResult:
    page: int
    heading: str | None
    heading_source: str | None  # toc | visual | inherited
    text: str
    figure_text: str
    quality: str  # ok | needs_vision | empty
    char_count: int
    language: str
    flags: list[str] = field(default_factory=list)
    removed_lines: int = 0
    source: str = "text"  # text | vision


_SCRIPTABLE = re.compile(r"^[\w+\-−–=()′']{1,6}$")


def _line_text(l: dict) -> str:
    """Satırın span'larını birleştirir; küçük ve satır tabanından yükseltilmiş span → üst simge ('2ⁿ', 'x²'),
    alçaltılmış → alt simge ('x₁'). Yön, satırın yazı yönüne diktir (döndürülmüş slaytlarda da doğru).
    Düz birleştirme üssü kaybediyordu: TYT '2ⁿ' → '2n', YZ '1·2⁴ + 1·2³' → '1.24 + 1.23'."""
    spans = [s for s in l["spans"] if s["text"]]
    plain = "".join(s["text"] for s in spans)
    # Denklem editörü satırları (matematik italik harfler: 𝑥, 𝑓): kesir pay/paydası ve indisler dağınık konumlu,
    # konumdan simge çıkarmak yanlış sonuç veriyordu (YZ s12: x₁ → 'x¹'). Bu sayfalar zaten görsel okumaya gider.
    if len(spans) < 2 or any("\U0001D400" <= ch <= "\U0001D7FF" for ch in plain):
        return plain
    big = max(s["size"] for s in spans)
    base = next(s for s in spans if s["size"] >= big * 0.95)["origin"]
    cos, sin = l.get("dir", (1.0, 0.0))
    out = []
    for s in spans:
        t = s["text"]
        if s["size"] < big * 0.85 and _SCRIPTABLE.match(t.strip() or "."):
            dx, dy = s["origin"][0] - base[0], s["origin"][1] - base[1]
            up = dx * sin - dy * cos  # yazı yönüne dik, 'yukarı' pozitif (PDF'te y aşağı doğru artar)
            if up > big * 0.18:
                t = to_script(t, sup=True)
            elif up < -big * 0.12:
                t = to_script(t, sup=False)
        out.append(t)
    return "".join(out)


def _visual_lines(page: pymupdf.Page) -> list[Line]:
    rot = page.rotation_matrix
    out = []
    for bi, b in enumerate(page.get_text("dict")["blocks"]):
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            text = clean_line(_line_text(l))
            if not text or text == "•":
                continue
            # Madde işareti genelde ayrı ve küçük bir span; boyutu gerçek metinden al
            sizes = [s["size"] for s in l["spans"] if clean_line(s["text"]).strip("• ")]
            size = max(sizes) if sizes else l["spans"][0]["size"]
            out.append(Line(text, round(size, 1), pymupdf.Rect(l["bbox"]) * rot, bi))
    # Bloklar görsel konuma göre sıralanır; blok içindeki satırlar PDF'teki doğal sırada kalır
    # (satır bazında sıralama, liste numaralarını metnin sonuna kaydırıyordu).
    top: dict[int, list[float]] = {}
    for ln in out:
        r = top.setdefault(ln.block, [ln.bbox.y0, ln.bbox.x0])
        r[0], r[1] = min(r[0], ln.bbox.y0), min(r[1], ln.bbox.x0)
    out.sort(key=lambda ln: (round(top[ln.block][0] / 4), top[ln.block][1]))
    return out


def _template_xrefs(doc: pymupdf.Document) -> set[int]:
    """Sayfaların çoğunda tekrar eden görseller (slayt şablonu, logo)."""
    c = Counter(xref for p in doc for xref in {img[0] for img in p.get_images(full=True)})
    if doc.page_count < 3:
        return set()
    return {x for x, n in c.items() if n >= BACKGROUND_REPEAT * doc.page_count}


def _content_images(page: pymupdf.Page, template: set[int]) -> list[pymupdf.Rect]:
    """Arka plan/şablon olmayan görsellerin konumları (görsel koordinatlarda)."""
    rot, area = page.rotation_matrix, page.rect.get_area()
    rects = []
    for xref in {img[0] for img in page.get_images(full=True)} - template:
        for r in page.get_image_rects(xref):
            r = (r * rot) & page.rect
            if 0 < r.get_area() < BACKGROUND_COVER * area:
                rects.append(r)
    return rects


def _full_page_image(page: pymupdf.Page, template: set[int]) -> bool:
    """Sayfayı kaplayan, şablon olmayan görsel: taranmış sayfa ya da tam sayfa fotoğraf. _content_images bunları
    slayt arka planı sayıp atıyor; metni de yoksa sayfa 'ok' sanılıyor, bölümleyici 'boş' diye atlıyordu → taranmış
    PDF sessizce hiç soru üretmiyordu (taranmış ders kitabı, 192 sayfanın 192'si, 2026-10-06)."""
    rot, area = page.rotation_matrix, page.rect.get_area()
    for xref in {img[0] for img in page.get_images(full=True)} - template:
        for r in page.get_image_rects(xref):
            if ((r * rot) & page.rect).get_area() >= BACKGROUND_COVER * area:
                return True
    return False


def _figure_regions(page: pymupdf.Page, images: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """İçerik görselleri + vektör çizim kümeleri (diyagramlar)."""
    rot, area = page.rotation_matrix, page.rect.get_area()
    rects = list(images)
    try:
        for c in page.cluster_drawings():
            r = pymupdf.Rect(c) * rot
            if r.width > 20 and r.height > 20 and r.get_area() < BACKGROUND_COVER * area:
                rects.append(r)
    except Exception:
        pass
    return rects


def _cover(rects: list[pymupdf.Rect], page: pymupdf.Page) -> float:
    return min(1.0, sum(r.get_area() for r in rects) / page.rect.get_area())


def _hf_key(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower())


def _find_header_footer(pages_lines: list[list[Line]]) -> set[str]:
    """Belgenin çoğunda tekrar eden ve bulunduğu sayfalarda en büyük yazı OLMAYAN satırlar.

    Konum şeridi kullanılmaz (döndürülmüş slaytlarda üst bilgi sayfanın %22'sinde olabiliyor).
    'En büyük yazı değil' koşulu, ardışık slaytlarda tekrar eden başlıkları korur.
    """
    n = len(pages_lines)
    if n < 3:
        return set()
    seen: Counter[str] = Counter()
    largest: Counter[str] = Counter()
    for lines in pages_lines:
        if not lines:
            continue
        max_size = max(ln.size for ln in lines)
        seen.update({_hf_key(ln.text) for ln in lines})
        largest.update({_hf_key(ln.text) for ln in lines if ln.size >= max_size - 0.5})
    return {k for k, c in seen.items()
            if c >= max(3, REPEAT_MIN_RATIO * n) and largest[k] < c / 2 and k.strip("# ")}


def _paragraphs(lines: list[Line]) -> str:
    """Aynı bloktaki satırları paragraf yapar; bloklar ayrı satırlarda."""
    paras, cur_block, buf = [], None, []
    for ln in lines:
        if ln.block != cur_block and buf:
            paras.append(join_lines(buf))
            buf = []
        cur_block = ln.block
        buf.append(ln.text)
    if buf:
        paras.append(join_lines(buf))
    # PowerPoint bazen madde işaretinin devam satırını ayrı bloğa koyar ('...rotasyonuna' |
    # 'dayandığından, ...'): küçük harfle başlayan blok, noktalamasız biten önceki bloğun devamıdır.
    merged: list[str] = []
    for p in (p for p in paras if p):
        prev_is_prose = bool(merged) and len(re.findall(r"[^\W\d_]{3,}", merged[-1])) >= 3 \
            and not _garbled_formula(merged[-1])  # formül parçası cümleyle birleşip dedektörden kaçmasın
        if prev_is_prose and p[:1].islower() and not re.search(r"[.:;!?)\]]$", merged[-1]):
            merged[-1] += " " + p
        else:
            merged.append(p)
    return "\n".join(merged)


def _table_md(rows: list[list[str]]) -> str:
    """Tabloyu Markdown'a çevirir. Bir satırdaki hücrelerin hepsi aynı sayıda alt satır içeriyorsa
    (EN s33: 'Population\\nIndividual…' | 'Set of solutions\\nSolution to…') satır satır açılır;
    böylece eşleşmeler ayrı satırlarda korunur."""
    out = []
    for row in rows:
        cells = [clean_line(c or "") if "\n" not in (c or "") else c for c in row]
        parts = [[clean_line(x) for x in c.split("\n") if x.strip()] if c else [] for c in cells]
        sizes = {len(p) for p in parts if p}
        if len(sizes) == 1 and (k := sizes.pop()) > 1 and all(len(p) in (0, k) for p in parts):
            for i in range(k):
                out.append([p[i] if p else "" for p in parts])
        else:
            out.append([" ".join(p) for p in parts])
    out = [r for r in out if any(c.strip() for c in r)]
    if not out:
        return ""
    width = max(len(r) for r in out)
    out = [r + [""] * (width - len(r)) for r in out]
    lines = ["| " + " | ".join(c.replace("|", "/") for c in out[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in out[1:]]
    return "\n".join(lines)


def _clean_cell(cell: str | None, hf: set[str], pno: int) -> str:
    """Hücreye sızan üst/alt bilgi ve sayfa numarası satırlarını çıkarır ('7 November 2013')."""
    keep = [x for x in (cell or "").split("\n")
            if x.strip() and _hf_key(clean_line(x)) not in hf and x.strip() != str(pno)]
    # Çok uzun hücre gerçek hücre değil, başka tabloları da içine alan "konteyner"dır (EN s22).
    return "" if len(keep) > TABLE_MAX_CELL_LINES else "\n".join(keep)


def _tables(page: pymupdf.Page, hf: set[str] = frozenset(), pno: int = 0,
            hf_texts: list[str] = ()) -> list[tuple[pymupdf.Rect, str]]:
    """PyMuPDF tablo bulucu (işlemci, ~ms).

    Atlananlar: 2x2'den küçük 'tablolar' (hizalı formül parçaları) ve hücrelerinin yarısından azı dolu
    olanlar (EN s22'de sayfa düzeninin tamamı tek sütunlu sahte tablo olarak algılanmıştı).
    Not: t.bbox zaten görsel (döndürülmüş) koordinatlarda gelir; satırlar gibi dönüştürülmez.
    """
    out = []
    try:
        found = page.find_tables().tables
    except Exception:
        return []
    for t in found:
        rows = [[_clean_cell(c, hf, pno) for c in r] for r in t.extract()]
        rows = [_strip_split_footer(r, list(hf_texts)) for r in rows]
        rows = [r for r in rows if any(c.strip() for c in r)]
        if len(rows) < 2 or max(len(r) for r in rows) < 2:
            continue
        cells = [c for r in rows for c in r]
        if sum(bool(c.strip()) for c in cells) < TABLE_MIN_FILL * len(cells):
            continue
        # Satırların çoğunda tek hücre doluysa bu tablo değil, sayfa düzeninin yanlış okunmasıdır
        # (EN s22/s35'teki sahte tablolar).
        single = sum(sum(bool(c.strip()) for c in r) <= 1 for r in rows)
        if single > TABLE_MAX_SINGLE_ROWS * len(rows):
            continue
        md = _table_md(rows)
        if md:
            out.append((pymupdf.Rect(t.bbox), md))
    return out


def _is_noisy(text: str) -> bool:
    """Satırların ≥%40'ı (en az 4 satır) 'parça' mı: içinde 3+ harfli en az 2 kelime olmayan satır.

    Elle kontrol (2026-10-02): işaretlenen sayfalardan incelenen 5'in 5'i gerçekten bozuktu
    (düzleşmiş tablo, iki sütunlu eşleme, formül parçaları, özel font kodlaması); düz metinli
    Ekoloji slaytlarında hiçbir sayfa işaretlenmedi.
    """
    rows = [x for x in text.split("\n") if x.strip()]
    frag = sum(len(re.findall(r"[^\W\d_]{3,}", x)) < 2 for x in rows)
    return (frag >= NOISY_MIN_LINES and frag >= NOISY_RATIO * len(rows)) or any(map(_garbled_formula, rows))


def _garbled_formula(line: str) -> bool:
    """Metin katmanında dağılmış formül: token'ların yarısından fazlası tek karakter.

    '( ) nx x x ,... , 2 1' (YZ s6), ') ) 1( n y ..., ,1 ) ... α α α α' (EN s43) → True;
    'f(x) = -x^2 + 30x' ya da '0.5 0.7 0.7 0.5' (tablo satırı) → False.
    """
    toks = line.split()
    if all(re.fullmatch(r"[\d.,%]+", t) for t in toks):  # sayı satırı formül değil (parça oranı yakalar)
        return False
    return len(toks) >= 6 and sum(len(t) == 1 for t in toks) > 0.5 * len(toks)


def _strip_split_footer(row: list[str], hf_texts: list[str]) -> list[str]:
    """Alt bilgi tablo satırına hücrelere bölünerek sızabilir: '2 7 Novem' | '0.286 ber 2013'.

    Satırda alt bilgi kelimesinin bir parçası (≥3 harf, başı/sonu) varsa, alt bilgideki tam
    token'lar ve kelime parçaları o satırdan çıkarılır. Parça yoksa satıra dokunulmaz.
    """
    hf_tokens = {t for h in hf_texts for t in h.split()}
    words = [t for t in hf_tokens if len(t) >= 4 and t.isalpha()]

    def fragment(tok: str) -> bool:
        return tok.isalpha() and len(tok) >= 3 and tok not in hf_tokens and any(
            w.startswith(tok) or w.endswith(tok) for w in words)

    if not any(fragment(t) for c in row for t in c.split()):
        return row
    return [" ".join(t for t in c.split() if t not in hf_tokens and not fragment(t)) for c in row]


def _page_number_offset(pages_lines: list[list[Line]]) -> int | None:
    """Basılı sayfa numarası ile PDF sayfa sırası arasındaki sabit fark (çoğu belgede 0).

    Eskiden her sayfada 'sayfa_no ± 2' olan tüm sayı satırları siliniyordu; bu, EN s20'deki
    diyagramdaki dört '22' değerini de siliyordu. Artık fark belge genelinde bir kez belirlenir.
    """
    votes: Counter[int] = Counter()
    for pno, lines in enumerate(pages_lines, start=1):
        # isdecimal, isdigit değil: '²' isdigit() ama int('²') hata verir (fizik notu çöktü, 2026-10-06)
        votes.update({int(ln.text) - pno for ln in lines if ln.text.isdecimal() and abs(int(ln.text) - pno) <= 2})
    if not votes:
        return None
    off, n = votes.most_common(1)[0]
    return off if n >= max(2, 0.4 * len(pages_lines)) else None


def _page_number_line(lines: list[Line], number: int, rect: pymupdf.Rect) -> Line | None:
    """Sayfa numarasını taşıyan tek satır: değeri tutan adaylardan sayfa kenarına en yakını."""
    cands = [ln for ln in lines if ln.text == str(number)]
    edge = lambda ln: min(ln.bbox.y0, rect.height - ln.bbox.y1, ln.bbox.x0, rect.width - ln.bbox.x1)
    return min(cands, key=edge) if cands else None


def _toc_titles(doc: pymupdf.Document) -> dict[int, str]:
    """İçindekiler listesinden sayfa → başlık. 'Slayt 11' gibi içeriksiz girişler atlanır.
    Tarayıcı yer imleri ('B1 Ders Kitabı 22.07.2015_Sayfa_001', …: hemen her sayfada bir giriş, yalnızca numara
    değişiyor) başlık değildir → hiç kullanılmaz (taranmış ders kitabı, 2026-10-06)."""
    titles = {}
    for _lvl, title, pno in doc.get_toc():
        t = clean_line(re.sub(r"^\s*(Slayt|Slide)\s*\d+\s*:?", "", title, flags=re.I))
        if len(t) >= 3 and pno not in titles:
            titles[pno] = t
    if doc.page_count >= 3 and len(titles) >= 0.8 * doc.page_count:
        keys = Counter(re.sub(r"\d+", "#", t) for t in titles.values())
        if keys.most_common(1)[0][1] >= 0.8 * len(titles):
            return {}
    return titles


def _body_size(pages_lines: list[list[Line]]) -> float:
    """Belgenin baskın gövde yazı boyutu (karakter sayısıyla ağırlıklı medyan)."""
    sizes = sorted((ln.size, len(ln.text)) for lines in pages_lines for ln in lines)
    total, acc = sum(n for _, n in sizes), 0
    for size, n in sizes:
        acc += n
        if acc >= total / 2:
            return size
    return 12.0


def _top_band_heading(lines: list[Line], page_h: float) -> tuple[str | None, set[int]]:
    """Slayt başlığı gövdeyle aynı puntoda ama en üst şeritte olabilir ('KAPSAMLI BİR GA ÖRNEĞİ')."""
    idx = [i for i, ln in enumerate(lines) if ln.bbox.y1 < page_h * TOP_BAND]
    if not idx or len(idx) == len(lines):
        return None, set()
    text = " ".join(lines[i].text for i in sorted(idx, key=lambda i: lines[i].bbox.x0))
    return (text, set(idx)) if 3 <= len(text) <= 120 else (None, set())


def _visual_heading(lines: list[Line], page_h: float) -> tuple[str | None, set[int]]:
    """Sayfanın üst kısmındaki, gövdeden belirgin büyük yazılı satır(lar)."""
    if not lines:
        return None, set()
    if len(lines) == 1:  # tek satırlık slayt: "Yılda 1.3 milyar ton yemek çöpe gidiyor"
        ln = lines[0]
        ok = ln.size >= SINGLE_LINE_HEADING_SIZE and len(ln.text) <= 120
        return (ln.text, {0}) if ok else (None, set())
    body_size = statistics.median(ln.size for ln in lines)
    top = [i for i, ln in enumerate(lines)
           if ln.bbox.y0 < page_h * 0.35 and ln.size >= body_size * HEADING_SIZE_RATIO]
    if not top:
        return _top_band_heading(lines, page_h)
    best = max(lines[i].size for i in top)
    idx = [i for i in top if abs(lines[i].size - best) < 1.0]
    text = " ".join(lines[i].text for i in idx)
    if len(text) > 120:
        return None, set()
    return text, set(idx)


def parse_pdf(path: str | Path) -> dict:
    path = Path(path)
    doc = pymupdf.open(path)
    if not doc.is_pdf:  # PyMuPDF HTML/metin de açıyor: '.pdf' adlı bir hata sayfası '1 sayfalık belge' sanılıyordu
        raise ValueError(f"{path.name} bir PDF değil (biçim: {doc.metadata.get('format') or 'bilinmiyor'})")
    pages_lines = [_visual_lines(p) for p in doc]
    hf = _find_header_footer(pages_lines)
    toc = _toc_titles(doc)
    template = _template_xrefs(doc)
    body = _body_size([[ln for ln in lines if _hf_key(ln.text) not in hf] for lines in pages_lines])

    offset = _page_number_offset(pages_lines)

    results: list[PageResult] = []
    prev_heading = None
    for pno, (page, lines) in enumerate(zip(doc, pages_lines), start=1):
        area = page.rect.get_area()
        pnum = _page_number_line(lines, pno + offset, page.rect) if offset is not None else None
        kept = [ln for ln in lines if ln is not pnum and _hf_key(ln.text) not in hf]
        removed = len(lines) - len(kept)

        if pno in toc:
            heading, source = toc[pno], "toc"
            heading_idx = {i for i, ln in enumerate(kept) if ln.text.lower() in heading.lower()}
        else:
            heading, heading_idx = _visual_heading(kept, page.rect.height)
            source = "visual" if heading else None

        images = _content_images(page, template)
        figs = _figure_regions(page, images)
        body_lines, fig_lines = [], []
        for i, ln in enumerate(kept):
            if i in heading_idx:
                continue
            short = len(ln.text.split()) <= FIGURE_LABEL_MAX_WORDS
            on_figure = any(r.contains(ln.bbox.tl) and r.contains(ln.bbox.br) for r in figs)
            is_label = short and ((on_figure and ln.size < body * LABEL_SIZE_ON_FIGURE)
                                  or ln.size < body * LABEL_SIZE_ANYWHERE)
            (fig_lines if is_label else body_lines).append(ln)

        prose = _paragraphs(body_lines)
        tables_md: list[str] = []
        if len(prose) >= MIN_TEXT_CHARS and _is_noisy(prose):
            # Bozuk metin çoğu zaman düzleşmiş bir tablodur: tabloyu işlemcide yapısıyla çıkar,
            # tablo alanındaki dağınık satırları metinden düş (GPU/internet gerektirmez).
            tables = _tables(page, hf, pno + (offset or 0), [ln.text for ln in lines if _hf_key(ln.text) in hf])
            if tables:
                def inside(ln: Line) -> bool:
                    c = pymupdf.Point((ln.bbox.x0 + ln.bbox.x1) / 2, (ln.bbox.y0 + ln.bbox.y1) / 2)
                    return any(r.contains(c) for r, _ in tables)
                body_lines = [ln for ln in body_lines if not inside(ln)]
                fig_lines = [ln for ln in fig_lines if not inside(ln)]
                prose = _paragraphs(body_lines)
                tables_md = [md for _, md in tables]
        text = "\n\n".join([prose] + tables_md).strip() if tables_md else prose
        figure_text = " | ".join(ln.text for ln in fig_lines)

        if source in ("toc", "visual"):
            prev_heading = heading
        elif prev_heading:
            heading, source = prev_heading, "inherited"

        own_heading = len(heading) if heading and source != "inherited" else 0
        n_chars = len(text) + own_heading
        big_figure = _cover(images, page) >= FIGURE_MIN_COVER or any(
            r.get_area() >= FIGURE_MIN_COVER * area for r in figs)

        flags = []
        scanned = len(text) < MIN_TEXT_CHARS and _full_page_image(page, template)
        if scanned:
            # Taranmış sayfa: kapak olsa bile içeriği görselden okunmadan bilinmez (taranmış notun 1. sayfası çoğu
            # zaman içerik) → görsel okuma
            quality, flags = "needs_vision", ["scanned"]
        elif pno == 1 and 0 < n_chars < TITLE_PAGE_MAX_CHARS:
            # kapak: ders adı, hoca, üniversite, e-posta → soru malzemesi değil, görsel okumaya da gerek yok
            quality, flags = "ok", ["title_page"]
        elif len(text) >= MIN_TEXT_CHARS and _is_noisy(prose):
            # Metin var ama (tablolar çıkarıldıktan sonra bile) formül/diyagram parçalarından oluşuyor
            # (EN s41/s89, YZ s4): "ok" sayılırsa bu parçalardan anlamsız soru üretilir → görsel okuma.
            quality, flags = "needs_vision", ["noisy_text"]
        elif len(text) >= MIN_TEXT_CHARS:
            quality = "ok"
            if tables_md:
                flags = ["tables_extracted"]
        elif big_figure:
            quality = "needs_vision"
        elif n_chars == 0:
            quality = "empty"
        else:
            quality = "ok"

        # İçindekiler/ünite listesi: satırların neredeyse tamamı kısa numaralı başlık.
        # (Numaralı algoritma adımları da kısa olabilir; onları ayırmak için oran yüksek tutuldu.)
        rows = [x for x in text.split("\n") if x.strip()]
        numbered = sum(bool(re.match(r"^\d+\.\s|.*\s\d+\.$", x)) and len(x) < 60 for x in rows)
        if numbered >= 6 and numbered >= 0.8 * len(rows):
            flags.append("toc_like")
        if quality == "ok" and big_figure and _cover(images, page) >= 0.3:
            flags.append("image_heavy")

        results.append(PageResult(
            page=pno, heading=heading, heading_source=source, text=text, figure_text=figure_text,
            quality=quality, char_count=n_chars, language=detect_language(text or (heading or "")),
            flags=flags, removed_lines=removed,
        ))

    # Dil ve başlık yalnızca sağlam sayfalardan: taranmış notun bozuk OCR katmanı ('rmuuumvmuuıuuuuuııui') Türkçe el
    # yazısını 'en' gösteriyordu → sorular İngilizce üretilirdi (2026-10-06). Görsel okumadan sonra dil yeniden
    # belirlenir (vision.apply_cached_vision).
    clean = " ".join(r.text for r in results if r.quality == "ok")
    # Satır sonu tireleri belge düzeyinde: 'bü‐tün' → 'bütün' (belgede birleşik yazımı varsa), 'meta-sezgisel' kalır
    lang = detect_language(clean)
    fields = [(r, f) for r in results for f in ("text", "heading", "figure_text")]
    for (r, f), v in zip(fields, resolve_hyphens([getattr(r, f) or "" for r, f in fields], lang)):
        if getattr(r, f):
            setattr(r, f, v)
    clean = " ".join(r.text for r in results if r.quality == "ok")
    first = [ln for ln in pages_lines[0] if _hf_key(ln.text) not in hf] if pages_lines else []
    if results and results[0].quality == "needs_vision":
        first = []  # kapak taranmış ya da metni bozuk: başlık dosya adından
    title = max(first, key=lambda ln: ln.size).text if first else path.stem
    return {
        "file": path.name,
        "title": title,
        "language": detect_language(clean),
        "n_pages": doc.page_count,
        "header_footer_patterns": sorted(hf),
        "pages": [asdict(r) for r in results],
    }

"""İnceleme verisi: soru setleri, kanıtın sayfada işaretlenmesi, insan kararlarının kaydı.

Arayüzden (src/app.py) bağımsız tutuldu; böylece testlerle ve değerlendirmede (Adım 9) de kullanılabilir.
Kararlar data/reviews.jsonl'a eklenir (yalnızca ekleme; aynı soru için son karar geçerlidir).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pymupdf

from src import config
from src.textnorm import normalize_for_match as norm

REVIEWS = config.DATA_DIR / "reviews.jsonl"
DOCS = config.DATA_DIR / "sample_docs"

FLAG_TR = {
    "length_cue": "Doğru şık diğerlerinden belirgin uzun (cevabı ele verebilir)",
    "verbatim_cue": "Doğru şık slayttaki cümlenin neredeyse aynısı",
    "absolute_distractors": "Çeldiricilerde 'yalnızca / her zaman' gibi kesin ifadeler",
    "near_verbatim": "Kanıt alıntısı birebir değil, çok yakın eşleşti",
    "vision_evidence": "Kanıt, görsel okuma modelinin yazdığı metinden (slaytın kendi metni değil)",
    "tf_not_statement": "Doğru/Yanlış sorusu ifade değil, soru biçiminde",
    "compute_text_unchecked": "Şıklarda düz sayı yok (ör. √2): şık metni ile değeri kodla karşılaştırılamadı",
    "negative_stem": "Olumsuz soru kökü ('…değildir') vurgulanmamış; öğrenci gözden kaçırabilir",
    "clang_cue": "Doğru şık, sorudaki bir kelimeyi tekrar ediyor (çeldiriciler etmiyor): cevabı ele verebilir",
}
LABEL_TR = {"verified": "✅ Doğrulandı", "needs_review": "🟡 İncelenmeli", "rejected": "❌ Reddedildi"}


def question_id(item: dict) -> str:
    return hashlib.sha1(f"{item.get('model')}|{item['q'].get('question', '')}".encode("utf-8")).hexdigest()[:12]


def question_sets() -> list[Path]:
    """Önce tam akıştan çıkan setler (data/questions, python -m src.pipeline), sonra pilot/deney setleri."""
    return (sorted((config.DATA_DIR / "questions").glob("*.jsonl"))
            + sorted((config.DATA_DIR / "pilot").glob("*_dogrulama.jsonl")))


def load_set(path: Path) -> list[dict]:
    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    for it in items:
        it["id"] = question_id(it)
    return items


def load_chunks() -> dict[str, dict]:
    path = config.DATA_DIR / "chunks" / "chunks.jsonl"
    return {json.loads(x)["id"]: json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}


def decisions() -> dict[str, dict]:
    """soru id → son karar"""
    out: dict[str, dict] = {}
    if REVIEWS.exists():
        for line in REVIEWS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r
    return out


REJECT_REASONS = ["Yanlış cevap", "Birden çok doğru şık", "Metinde yok / uydurma", "Çok kolay / ipucu veriyor",
                  "Belirsiz soru", "Anlatım / dil hatası", "Önemsiz ayrıntı"]


def save_decision(item: dict, decision: str, note: str, source: str, reasons: list[str] | None = None) -> None:
    rec = {"id": item["id"], "decision": decision, "note": note.strip(), "reasons": reasons or [],
           "time": time.strftime("%Y-%m-%d %H:%M:%S"),
           "set": source, "model": item.get("model"), "question": item["q"].get("question"),
           "system_label": item.get("verification", {}).get("label"),
           "flags": item.get("check", {}).get("flags", [])}
    REVIEWS.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _pdf_for(doc_stem: str) -> Path | None:
    hits = [p for p in DOCS.glob("*.pdf") if p.stem == doc_stem]
    return hits[0] if hits else None


def _page_tokens(page: pymupdf.Page) -> tuple[list, list[tuple[str, tuple[int, ...]]]]:
    """Sayfanın kelimeleri ve normalize edilmiş belirteçleri; her belirteç hangi kelime(ler)den geldiğini bilir.
    Satır sonunda bölünmüş kelime ('bü-' + 'tün') tek belirteç olur ve iki kelimeyi birden işaretler."""
    words = page.get_text("words")  # (x0, y0, x1, y1, metin, blok, satır, sıra)
    toks, i = [], 0
    while i < len(words):
        w = words[i][4]
        if w.endswith("-") and i + 1 < len(words) and words[i + 1][4][:1].islower():
            toks += [(t, (i, i + 1)) for t in norm(w[:-1] + words[i + 1][4]).split()]
            i += 2
            continue
        toks += [(t, (i,)) for t in norm(w).split()]
        i += 1
    return words, toks


def _same(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 4 and long_.startswith(short) and len(short) >= 0.7 * len(long_)  # Türkçe ek farkı


def _align(q: list[str], toks: list[tuple[str, tuple[int, ...]]]) -> list[int]:
    """Yerel hizalama (Smith-Waterman, kelime düzeyinde): alıntının kelimelerini sayfanın kelime dizisinde, araya
    giren birkaç kelimeye (kesir çizgisi, '=' işareti, satır sonu) izin vererek bulur. Eşleşen belirteç konumları."""
    m, n = len(q), len(toks)
    H = [[0] * (n + 1) for _ in range(m + 1)]
    best, bi, bj = 0, 0, 0
    for i in range(1, m + 1):
        qi, row, prev = q[i - 1], H[i], H[i - 1]
        for j in range(1, n + 1):
            v = max(0, prev[j - 1] + (2 if _same(qi, toks[j - 1][0]) else -1), prev[j] - 1, row[j - 1] - 1)
            row[j] = v
            if v > best:
                best, bi, bj = v, i, j
    out, i, j = [], bi, bj
    while i > 0 and j > 0 and H[i][j] > 0:
        if _same(q[i - 1], toks[j - 1][0]) and H[i][j] == H[i - 1][j - 1] + 2:
            out.append(j - 1)
            i, j = i - 1, j - 1
        elif H[i][j] == H[i - 1][j] - 1:
            i -= 1
        else:
            j -= 1
    return out[::-1]


def _highlight_rects(page: pymupdf.Page, quote: str) -> list[pymupdf.Rect]:
    """Kanıtı sayfada bul ve satır satır işaretlenecek dikdörtgenleri döndür.

    1. Alıntı sayfada birebir geçiyorsa harf düzeyinde kesin konum.
    2. Geçmiyorsa kelime düzeyinde hizalama: satır sonu tireleri, kesir gibi iki boyutlu formüller, görsel okumanın
       LaTeX'i ('\frac{100 \cdot a}{a+b}'), üst simgeler ('2ⁿ' ↔ '2n') ve noktalama farkları eşleşmeyi bozmaz.
       Önceki yöntem birebir parça arıyordu; formüllü alıntılarda yalnızca bir iki kelime işaretleniyordu.
    """
    quote = " ".join(quote.replace("|", " ").split())  # tablo alıntısı: Markdown çizgileri PDF'te yok
    if not quote:
        return []
    hits = page.search_for(quote)
    if hits:
        return hits
    q = norm(quote).split()
    words, toks = _page_tokens(page)
    if not q or not toks:
        return []
    matched = _align(q, toks)
    if len(matched) < max(2, 0.6 * len(q)):
        return []
    # Uçlarda başka satıra taşan tek harflik eşleşmeleri at ('… a+b' alıntısının 'b'si alt satırdaki 'B maddesinin'e
    # yapışıyordu): kısa belirteç, komşu eşleşmeyle aynı satırda değilse alıntının parçası sayılmaz.
    line_of = lambda j: words[toks[j][1][0]][5:7]
    while len(matched) > 2 and len(toks[matched[-1]][0]) <= 2 and line_of(matched[-1]) != line_of(matched[-2]):
        matched.pop()
    while len(matched) > 2 and len(toks[matched[0]][0]) <= 2 and line_of(matched[0]) != line_of(matched[1]):
        matched.pop(0)
    idx = sorted({w for j in matched for w in toks[j][1]})
    # Eşleşen kelimelerin arasındaki en çok 3 kelimelik boşluğu da işaretle ('=' işareti, kesrin paydası)
    fill = [w for a, b in zip(idx, idx[1:]) if 1 < b - a <= 4 for w in range(a + 1, b)]
    lines: dict[tuple[int, int], pymupdf.Rect] = {}
    for w in sorted(set(idx) | set(fill)):
        x0, y0, x1, y1, _, blk, ln, _ = words[w]
        r = pymupdf.Rect(x0, y0, x1, y1)
        lines[(blk, ln)] = lines[(blk, ln)] | r if (blk, ln) in lines else r
    return list(lines.values())


def _evidence_clip(page: pymupdf.Page, rects: list[pymupdf.Rect]) -> pymupdf.Rect | None:
    """Kanıtın çevresi: en az sayfanın %32 genişliği ve %28 yüksekliği (bağlam görünsün diye kenar payıyla);
    kanıt sayfanın büyük kısmını kaplıyorsa None."""
    if not rects:
        return None
    pr = page.rect
    box = pymupdf.Rect(rects[0])
    for r in rects[1:]:
        box |= r
    if box.width > pr.width * 0.7 and box.height > pr.height * 0.6:
        return None
    w, h = max(box.width + pr.width * 0.12, pr.width * 0.32), max(box.height + pr.height * 0.15, pr.height * 0.28)
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    x0 = min(max(pr.x0, cx - w / 2), pr.x1 - w)
    y0 = min(max(pr.y0, cy - h / 2), pr.y1 - h)
    return pymupdf.Rect(x0, y0, x0 + w, y0 + h) & pr


def render_evidence(item: dict, chunks: dict[str, dict], dpi: int = 110) -> tuple[bytes | None, str]:
    """(png, açıklama). Kanıt sayfası, kanıt sarıyla işaretlenmiş olarak; orijinal PDF değiştirilmez."""
    page_no = item.get("check", {}).get("evidence_page") or (item.get("pages") or [None])[0]
    cid = next(iter(item.get("chunk_ids") or []), None)
    if not page_no or not cid or cid not in chunks:
        return None, "Kanıt sayfası bulunamadı."
    pdf = _pdf_for(chunks[cid]["doc"])
    if pdf is None:
        return None, "PDF dosyası bulunamadı."
    doc = pymupdf.open(pdf)  # bellekte açılır; işaretleme diske yazılmaz
    page = doc[page_no - 1]
    rects = _highlight_rects(page, item["q"].get("evidence_quote", ""))
    for r in rects:
        page.add_highlight_annot(r)
    clip = _evidence_clip(page, rects)
    # Yoğun sayfada (ör. TYT formül posteri) tam sayfa küçülünce işaretli kanıt okunmuyordu: kanıtın çevresi,
    # bağlam görünecek genişlikte kırpılıp daha yüksek çözünürlükte çizilir.
    png = page.get_pixmap(dpi=dpi if clip is None else int(dpi * 1.4), annots=True, clip=clip).tobytes("png")
    src = next((c for c in chunks.values() if c["doc"] == chunks[cid]["doc"] and c["page"] == page_no), {})
    if rects:
        note = (f"Sayfa {page_no} — kanıtın geçtiği bölüm yakınlaştırıldı, kanıt sarıyla işaretli." if clip is not None
                else f"Sayfa {page_no} — kanıt sarıyla işaretli.")
    elif src.get("source") == "vision":
        note = f"Sayfa {page_no} — bu sayfanın metni görselden okundu; kanıt PDF'te metin olarak bulunmadığı için işaretlenemiyor."
    else:
        note = f"Sayfa {page_no} — kanıt sayfada otomatik işaretlenemedi (alıntı satırlara bölünmüş olabilir)."
    return png, note


def agreement(items_by_id: dict[str, dict], decs: dict[str, dict]) -> dict:
    """Sistem etiketi × insan kararı: Adım 9'daki 'insan kabul oranı' ve 'doğrulayıcı isabeti'nin verisi."""
    table: dict[str, dict[str, int]] = {}
    for qid, d in decs.items():
        if qid not in items_by_id:
            continue
        lab = items_by_id[qid].get("verification", {}).get("label", "?")
        table.setdefault(lab, {"approve": 0, "reject": 0})
        table[lab][d["decision"]] = table[lab].get(d["decision"], 0) + 1
    return table

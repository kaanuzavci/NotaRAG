"""Ayrıştırılmış sayfalar → parçalar (chunk) ve bölümler (section). ROADMAP Adım 4.

- Parça: bir sayfa (slayt); uzun sayfalar paragraf sınırlarından bölünür. Arama birimi.
- Bölüm: aynı/benzer başlıklı ardışık sayfalar. Soru üretiminde LLM'e verilen bağlam.
- Kapak, içindekiler benzeri sayfalar ve kaynakça dizine alınmaz (gerekçesiyle kaydedilir).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from rapidfuzz import fuzz

from src.textnorm import normalize_for_match

MAX_CHUNK_CHARS = 1500      # bundan uzun sayfa bölünür
TARGET_CHUNK_CHARS = 1000   # bölünen parçaların hedef boyutu
MAX_SECTION_CHARS = 4000    # soru üretimine verilecek bölüm bağlamının üst sınırı
HEADING_MERGE_RATIO = 90    # başlık benzerliği (rapidfuzz) bu değerin üstündeyse aynı bölüm
_REFERENCES = re.compile(r"^(references?|bibliography|kaynak(ça|lar)|yararlanılan kaynaklar)\b", re.I)


def _same_section(a: str | None, b: str | None) -> bool:
    """'Simple Genetic Algorithms' ≈ 'Simple Genetic Algorithm'; 'Organik Tarım' ⊂ 'Organik Tarım suyu korur'."""
    if a is None or b is None:
        return a is b
    na, nb = normalize_for_match(a), normalize_for_match(b)
    return na == nb or nb.startswith(na + " ") or na.startswith(nb + " ") or fuzz.ratio(na, nb) >= HEADING_MERGE_RATIO


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n|\n(?=#)", text):  # boş satır ya da Markdown başlığı sınırı
        if cur and len(cur) + len(para) > TARGET_CHUNK_CHARS:
            parts.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _skip_reason(page: dict, section_title: str | None) -> str | None:
    if "title_page" in page["flags"]:
        return "kapak"
    if "toc_like" in page["flags"]:
        return "içindekiler"
    if section_title and _REFERENCES.match(section_title.strip()):
        return "kaynakça"
    if not page["text"].strip():
        return "boş"
    return None


def chunk_document(parsed: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """(chunks, sections, skipped) döndürür."""
    doc_id = Path(parsed["file"]).stem
    chunks, sections, skipped = [], [], []
    section = None
    for page in parsed["pages"]:
        heading = page["heading"]
        if section is None or not _same_section(section["title"], heading):
            section = {"id": f"{doc_id}:sec{len(sections) + 1:02d}", "doc": doc_id, "doc_title": parsed["title"],
                       "title": heading, "pages": [], "chunk_ids": []}
            sections.append(section)
        reason = _skip_reason(page, section["title"])
        if reason:
            skipped.append({"doc": doc_id, "page": page["page"], "reason": reason})
            continue
        for k, piece in enumerate(_split_long(page["text"]), start=1):
            embed_text = f"{heading}\n{piece}" if heading and heading not in piece[:200] else piece
            chunk = {
                "id": f"{doc_id}:p{page['page']:03d}:{k}",
                "doc": doc_id,
                "doc_title": parsed["title"],
                "page": page["page"],
                "section_id": section["id"],
                "heading": heading,
                "text": piece,
                "embed_text": embed_text,
                "language": parsed["language"],
                "source": page.get("source", "text"),
                # Görsel okuma bekleyen sayfa (resimli ya da metin katmanı bozuk): aramada bulunur,
                # ama soru üretiminde görsel okuma tamamlanana kadar kullanılmaz.
                "pending_vision": page["quality"] == "needs_vision",
                "vision_model": page.get("vision_model"),
                "hash": hashlib.sha1(embed_text.encode("utf-8")).hexdigest()[:16],
            }
            chunks.append(chunk)
            section["chunk_ids"].append(chunk["id"])
        if page["page"] not in section["pages"]:
            section["pages"].append(page["page"])

    sections = [s for s in sections if s["chunk_ids"]]
    by_id = {c["id"]: c for c in chunks}
    for s in sections:
        body = "\n\n".join(f"[s.{by_id[cid]['page']}] {by_id[cid]['text']}" for cid in s["chunk_ids"])
        s["text"] = body
        s["char_count"] = len(body)
        s["too_long"] = len(body) > MAX_SECTION_CHARS  # üretimde parça parça verilecek
    return chunks, sections, skipped

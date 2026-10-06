"""Görsel fallback: 'needs_vision' sayfalarını Gemini ile okur (PROMPTS.md §1).

İnternet kullanır. Her sayfa yalnızca bir kez gönderilir; sonuç data/vision_cache/ altında
saklanır ve sonraki çalıştırmalarda oradan okunur. Model zinciri: src/llm/models.py ROLES["vision"].
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

from src import config
from src.prompts import load_prompt


def _cache_path(pdf: Path, page: int) -> Path:
    return config.VISION_CACHE_DIR / f"{pdf.stem}_p{page:03d}.md"


_MODELS_FILE = "_models.json"
_FIRST_RUN_MODEL = "gemini-2.5-flash"  # kayıt tutulmadan önce okunan sayfaların modeli


def _models() -> dict:
    f = config.VISION_CACHE_DIR / _MODELS_FILE
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def _record_model(cache: Path, model: str) -> None:
    m = _models()
    m[cache.name] = model
    (config.VISION_CACHE_DIR / _MODELS_FILE).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


def _render(pdf: Path, page: int) -> bytes:
    with pymupdf.open(pdf) as doc:
        return doc[page - 1].get_pixmap(dpi=config.VISION_DPI).tobytes("jpeg", jpg_quality=80)


def pending_pages(parsed: dict, pdf: Path) -> list[int]:
    """Görsel okuma gereken ve henüz önbellekte olmayan sayfalar."""
    return [p["page"] for p in parsed["pages"]
            if p["quality"] == "needs_vision" and not _cache_path(pdf, p["page"]).exists()]


def estimate_upload_bytes(pdf: Path, pages: list[int]) -> int:
    return sum(len(_render(pdf, p)) for p in pages)


def _text_layer(page: dict) -> str:
    """Ayrıştırıcının bu sayfadan çıkardığı kesin metin; modele yazım ipucu olarak verilir. Taranıp OCR'lanmış
    sayfada (ocr_layer) katman tahmindir, el yazısında çöp ('rmuuumvmuuıuuuuuııui') → ipucu verilmez."""
    if "ocr_layer" in page.get("flags", []):
        return "(empty)"
    parts = [page.get("heading") if page.get("heading_source") != "inherited" else None,
             page.get("text"), page.get("figure_text")]
    return "\n".join(p for p in parts if p) or "(empty)"


def run_vision(parsed_path: Path, pdf: Path) -> bool:
    """Eksik sayfaları okuyup önbelleğe yazar, sonra JSON'a uygular. Tüm görsel modellerin
    kotası dolduysa False döndürür. Model seçimi, kota ve hata politikası src/llm/router.py'de."""
    from src.llm.router import AllModelsExhausted, call

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    todo = pending_pages(parsed, pdf)
    if todo:
        config.VISION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        by_no = {p["page"]: p for p in parsed["pages"]}
        for page in todo:
            prompt = load_prompt("1").replace("{text_layer}", _text_layer(by_no[page]))
            try:
                r = call("vision", prompt, image=_render(pdf, page))
            except AllModelsExhausted as e:
                print(f"    s{page}: TÜM GÖRSEL MODELLERİN KOTASI DOLU — durduruldu ({e}).")
                apply_cached_vision(parsed_path, pdf)
                return False
            _cache_path(pdf, page).write_text(r.text, encoding="utf-8")
            _record_model(_cache_path(pdf, page), r.model)
            print(f"    s{page}: {len(r.text)} karakter ({r.model}{', önbellek' if r.cached else ''})")
    apply_cached_vision(parsed_path, pdf)
    return True


def snap_to_text_layer(md: str, layer: str, threshold: float = 88) -> tuple[str, int]:
    """Görsel okumada metin katmanına çok benzeyen ama birebir aynı olmayan satırları düzeltir.

    Metin katmanı PDF'ten birebir geldiği için yazımda otoritedir; görsel model ise
    'çöpe gidiyor' → 'çöp gidiyor' gibi hatalar yapabilir. Düzeltilen satır sayısını da döndürür.
    """
    from rapidfuzz import fuzz

    ref = [ln.strip() for ln in layer.split("\n") if len(ln.strip()) >= 8]
    out, fixed = [], 0
    for line in md.split("\n"):
        m = re.match(r"^(\s*(?:#+|[-*•]|\d+\.)?\s*)(.*)$", line)
        prefix, body = m.group(1), m.group(2)
        best = max(ref, key=lambda r: fuzz.ratio(body, r), default=None) if len(body) >= 8 else None
        if best and body != best and fuzz.ratio(body, best) >= threshold:
            line, fixed = prefix + best, fixed + 1
        out.append(line)
    return "\n".join(out), fixed


def repair_from_layer(md: str, layer: str) -> str:
    """Görsel okuma, istem kuralı 6 gereği metin katmanının yazımını kopyalar. Metin katmanı eskiden üst simgeleri
    ve satır sonu tirelerini bozuyordu ('2ⁿ' → '2n', 'bütün' → 'bü-tün'); önbellekteki okumalar bu bozuk yazımı
    taşıyor. Düzeltilmiş metin katmanındaki kelimelerin eski düz yazımı, bir önceki kelimeyle birlikte (bağlam)
    bulunup düzeltilir. Görsel okumayı yeniden yaptırmaz (kota harcamaz)."""
    import unicodedata

    from src.textnorm import SCRIPT_CHARS, tr_lower

    toks = layer.split()
    for prev, tok in zip([""] + toks, toks):
        if not any(ch in SCRIPT_CHARS for ch in tok):
            continue
        plain = unicodedata.normalize("NFKC", tok)
        if plain != tok and prev:
            md = md.replace(f"{prev} {plain}", f"{prev} {tok}")
    vocab = {tr_lower(w) for w in re.findall(r"\w+(?:-\w+)*", layer)}

    def join(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        whole = tr_lower(f"{a}-{b}")
        return a + b if tr_lower(a + b) in vocab and whole not in vocab else m.group(0)

    return re.sub(r"(\w+)-(\w+)", join, md)


def apply_cached_vision(parsed_path: Path, pdf: Path) -> None:
    """Önbellekteki görsel okuma sonuçlarını ayrıştırılmış JSON'a yazar (internet kullanmaz)."""
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    for p in parsed["pages"]:
        cache = _cache_path(pdf, p["page"])
        if p["quality"] == "needs_vision" and cache.exists():
            # _text_layer OCR katmanında '(empty)' döner → yazım düzeltmesi yapılmaz (görsel okuma olduğu gibi kalır)
            text, fixed = snap_to_text_layer(cache.read_text(encoding="utf-8"), _text_layer(p))
            text = repair_from_layer(text, _text_layer(p))
            p["text_layer"] = p["text"]
            p["text"] = text
            p["vision_spelling_fixes"] = fixed
            p["source"] = "vision"
            p["vision_model"] = _models().get(cache.name, _FIRST_RUN_MODEL)
            p["quality"] = "ok"
    # Dil görsel okunan sayfalar dahil yeniden: taranmış belgede okuma öncesi metin yok ya da bozuk ('unknown' / yanlış)
    from src.textnorm import detect_language
    lang = detect_language(" ".join(p["text"] for p in parsed["pages"] if p["quality"] == "ok"))
    if lang != "unknown":
        parsed["language"] = lang
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

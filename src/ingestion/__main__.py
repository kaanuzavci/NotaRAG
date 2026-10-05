"""Kullanım:
    python -m src.ingestion                 # PDF'leri ayrıştır (internet kullanmaz)
    python -m src.ingestion --vision        # görsel okuma için gönderilecek sayfa/MB tahmini (internet kullanmaz)
    python -m src.ingestion --vision --yes  # görsel sayfaları Gemini ile oku (İNTERNET KULLANIR)

PDF'ler data/sample_docs/ altından okunur, sonuçlar data/parsed/<dosya>.json olarak yazılır.
Daha önce okunmuş görsel sayfalar önbellekten uygulanır, tekrar gönderilmez.
"""

import json
import sys
from pathlib import Path

from src import config
from src.ingestion.pdf_parser import parse_pdf
from src.ingestion.vision import apply_cached_vision, estimate_upload_bytes, pending_pages, run_vision

SRC = config.DATA_DIR / "sample_docs"


def _summary(doc: dict) -> None:
    pages = doc["pages"]
    vision = [p["page"] for p in pages if p["quality"] == "needs_vision"]
    done = [p["page"] for p in pages if p.get("source") == "vision"]
    print(f"\n■ {doc['file']}  ({doc['n_pages']} sayfa, dil: {doc['language']})")
    print(f"  Başlık: {doc['title']}")
    print(f"  Üst/alt bilgi kalıpları: {doc['header_footer_patterns'] or '-'}")
    print(f"  Silinen satır: {sum(p['removed_lines'] for p in pages)}")
    src_count = {s: sum(p['heading_source'] == s for p in pages) for s in ('toc', 'visual', 'inherited')}
    print(f"  Başlık kaynağı: {src_count}, başlıksız: {sum(p['heading'] is None for p in pages)}")
    print(f"  Görsel okuma bekleyen: {vision or '-'}   Görsel okunmuş: {done or '-'}")
    flagged = {f: [p['page'] for p in pages if f in p['flags']] for f in ('title_page', 'toc_like', 'image_heavy')}
    print(f"  Bayraklar: {flagged}")


def main() -> None:
    args = set(sys.argv[1:])
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SRC.glob("*.pdf"))
    for pdf in pdfs:
        out = config.PARSED_DIR / f"{pdf.stem}.json"
        out.write_text(json.dumps(parse_pdf(pdf), ensure_ascii=False, indent=2), encoding="utf-8")
        apply_cached_vision(out, pdf)

    if "--vision" in args:
        plan = []
        for pdf in pdfs:
            out = config.PARSED_DIR / f"{pdf.stem}.json"
            todo = pending_pages(json.loads(out.read_text(encoding="utf-8")), pdf)
            if todo:
                plan.append((pdf, out, todo, estimate_upload_bytes(pdf, todo)))
        n, mb = sum(len(t) for _, _, t, _ in plan), sum(b for *_, b in plan) / 1e6
        from src.llm import ledger
        from src.llm.models import MODELS, ROLES
        left = {m: (MODELS[m].rpd or 0) - ledger.usage(m)[0] for m in ROLES["vision"] if ledger.available(m)}
        print(f"\nGörsel okuma planı ({config.VISION_DPI} dpi): {n} sayfa, ~{mb:.1f} MB yükleme")
        print(f"  Bugün kullanılabilir görsel modeller (kalan istek): {left or 'YOK — kota sıfırlanınca tekrar deneyin'}")
        for pdf, _, todo, b in plan:
            print(f"  {pdf.name}: {len(todo)} sayfa, {b / 1e6:.1f} MB")
        if "--yes" not in args:
            print("Hiçbir şey gönderilmedi. Göndermek için: python -m src.ingestion --vision --yes")
        else:
            for pdf, out, todo, _ in plan:
                print(f"  → {pdf.name}")
                if not run_vision(out, pdf):
                    break  # kota doldu: diğer dosyalar için de istek atmanın anlamı yok

    for pdf in pdfs:
        _summary(json.loads((config.PARSED_DIR / f"{pdf.stem}.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()

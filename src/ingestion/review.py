"""Ayrıştırma kontrol sayfası: her PDF sayfasının görüntüsü ile sistemin çıkardığı metni yan yana gösterir.

Kullanım: python -m src.ingestion.review   → data/review/index.html (tarayıcıda açılır, internet kullanmaz)
"""

import html
import json

import pymupdf

from src import config

DPI = 70

CSS = """
:root { --bg:#fafaf7; --card:#fff; --ink:#1d1d1b; --mute:#6b6b66; --line:#e3e2dc;
        --ok:#2f7d4f; --vis:#2a62a8; --warn:#a8622a; --skip:#8a8a84; }
@media (prefers-color-scheme: dark) { :root { --bg:#161615; --card:#1f1f1d; --ink:#ecebe6; --mute:#a3a29b;
        --line:#34332f; --ok:#6cc08f; --vis:#7fb0ef; --warn:#e3a46c; --skip:#8a8a84; } }
* { box-sizing:border-box } body { margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { padding:20px 16px; max-width:1300px; margin:auto } h1 { margin:0 0 6px; font-size:22px }
nav a { margin-right:14px; color:var(--vis) } .doc { max-width:1300px; margin:auto; padding:0 16px 40px }
h2 { border-bottom:1px solid var(--line); padding-bottom:6px; margin-top:36px }
.page { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:16px; background:var(--card);
  border:1px solid var(--line); border-radius:8px; padding:12px; margin:14px 0 }
.page img { width:100%; border:1px solid var(--line); border-radius:4px }
.meta { font-size:13px; color:var(--mute); margin-bottom:6px }
.tag { display:inline-block; padding:1px 7px; border-radius:10px; font-size:12px; margin-right:4px; border:1px solid currentColor }
.ok { color:var(--ok) } .vision { color:var(--vis) } .needs_vision { color:var(--warn) } .skip { color:var(--skip) }
.head { font-weight:600; margin:4px 0 } pre { white-space:pre-wrap; word-break:break-word; margin:0;
  font:13px/1.45 ui-monospace, Consolas, monospace }
.fig { margin-top:8px; font-size:12px; color:var(--mute) }
@media (max-width:760px) { .page { grid-template-columns:1fr } }
"""


def main() -> None:
    out = config.DATA_DIR / "review"
    (out / "img").mkdir(parents=True, exist_ok=True)
    skipped = {}
    sk = config.DATA_DIR / "chunks" / "skipped.jsonl"
    if sk.exists():
        for line in sk.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            skipped[(r["doc"], r["page"])] = r["reason"]

    docs, nav = [], []
    for jp in sorted(config.PARSED_DIR.glob("*.json")):
        parsed = json.loads(jp.read_text(encoding="utf-8"))
        pdf = pymupdf.open(config.DATA_DIR / "sample_docs" / parsed["file"])
        anchor = f"d{len(docs)}"
        nav.append(f'<a href="#{anchor}">{html.escape(parsed["file"])}</a>')
        parts = [f'<h2 id="{anchor}">{html.escape(parsed["file"])} — {parsed["n_pages"]} sayfa, dil: {parsed["language"]}</h2>']
        for p in parsed["pages"]:
            img = f"img/{jp.stem}_{p['page']:03d}.jpg"
            pdf[p["page"] - 1].get_pixmap(dpi=DPI).save(str(out / img), jpg_quality=70)
            tags = []
            if p.get("source") == "vision":
                tags.append(f'<span class="tag vision">görselden okundu ({html.escape(p.get("vision_model") or "")})</span>')
            tags.append(f'<span class="tag {p["quality"]}">{p["quality"]}</span>')
            for f in p["flags"]:
                tags.append(f'<span class="tag skip">{f}</span>')
            reason = skipped.get((jp.stem, p["page"]))
            if reason:
                tags.append(f'<span class="tag skip">dizin dışı: {reason}</span>')
            head = html.escape(p["heading"] or "—")
            fig = f'<div class="fig">Şekil üzerindeki metin: {html.escape(p["figure_text"])}</div>' if p["figure_text"] else ""
            parts.append(
                f'<div class="page"><div><img loading="lazy" src="{img}" alt="Sayfa {p["page"]}"></div><div>'
                f'<div class="meta">Sayfa {p["page"]} {"".join(tags)}</div>'
                f'<div class="head">Başlık ({p["heading_source"] or "yok"}): {head}</div>'
                f'<pre>{html.escape(p["text"]) or "(metin yok)"}</pre>{fig}</div></div>')
        docs.append("\n".join(parts))

    page = (f'<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ayrıştırma Kontrolü</title>'
            f'<style>{CSS}</style></head><body><header><h1>Ayrıştırma Kontrolü</h1>'
            f'<p>Solda PDF sayfasının kendisi, sağda sistemin o sayfadan çıkardığı metin. '
            f'Mavi etiketli sayfalar görselden (Gemini) okundu; turuncu olanlar görsel okuma bekliyor.</p>'
            f'<nav>{"".join(nav)}</nav></header><div class="doc">{"".join(docs)}</div></body></html>')
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"Hazır: {out / 'index.html'}")


if __name__ == "__main__":
    main()

"""Belgeler: ders notu ekle (arka planda okunur, konu haritası çıkarılır, soru havuzu hazırlanır) ve her notun
konularını, sayfalarını, okuma kalitesini gör."""

import time

import pymupdf
import streamlit as st

from src import request as R
from src.ui import data, style

STEPS = ["PDF okuma", "Görsel okuma", "Bölümleme", "Dizin", "Soru havuzu", "Doğrulama"]
LANGS = {"Belgenin dili": None, "Türkçe": "tr", "İngilizce": "en"}
SOURCE_TR = {"text": "Metin katmanı", "vision": "Görselden okundu"}
FLAG_TR = {"title_page": "Kapak", "toc_like": "İçindekiler", "image_heavy": "Görsel ağırlıklı",
           "noisy_text": "Bozuk metin", "tables_extracted": "Tablo çıkarıldı"}


# ---------------------------------------------------------------- ekleme ve işler

def _add() -> None:
    with st.expander("Yeni ders notu ekle", icon=":material/upload_file:", expanded=not data.documents()):
        up = st.file_uploader("PDF dosyası", type=["pdf"], label_visibility="collapsed")
        lang = st.segmented_control("Soruların dili", list(LANGS), default="Belgenin dili",
                                    help="İngilizce bir slayttan Türkçe soru üretilebilir; kanıt alıntısı kaynak dilde kalır.")
        if up is not None:
            dest = data.DOCS_DIR / up.name
            if not dest.exists() or dest.stat().st_size != up.size:
                dest.write_bytes(up.getvalue())
                st.cache_data.clear()
            if st.button(f"“{up.name}” notunu işle", type="primary", icon=":material/play_arrow:"):
                data.start_job(up.name, LANGS[lang or "Belgenin dili"])
                st.toast("İşleme başladı; ilerleme aşağıda.", icon=":material/rocket_launch:")
                time.sleep(1)
                st.rerun()
        st.caption("Not okunur (gerekirse görsel okuma), konu haritası çıkarılır ve her konudan doğrulanmış sorularla "
                   "bir başlangıç havuzu hazırlanır. Arka planda yürür; sayfayı kapatsan da devam eder.")


@st.fragment(run_every=4)
def _jobs() -> None:
    running = [(s, j) for s, j in data.jobs() if not j["done"] and not j["failed"]
               and time.time() - j["started"] < 6 * 3600]
    for stem, j in running[:3]:
        with st.container(border=True):
            st.markdown(f"**{data.short(stem)}** işleniyor — {STEPS[max(0, j['step'] - 1)] if j['step'] else 'başlıyor'}")
            st.progress(j["step"] / 6)
            if j["waiting"]:
                st.caption(f"Kota bekleniyor; iş duraklamadı, kaldığı yerden devam edecek. {j['waiting'].lstrip('⏳ ')}")
            elif detail := _detail(j["tail"]):
                st.caption(detail)


def _detail(tail: list[str]) -> str | None:
    """Adımın içindeki son ilerleme satırı (ör. 'üretim 9/15', 'doğrulama 10/30'); adım başlığı ise gösterme."""
    last = tail[-1] if tail else ""
    if not last.startswith("   "):
        return None
    if "yapılamadı" in last and "qwen" in last:
        return "Gemini'nin günlük kotası dolu; sorular yedek modelle (qwen) tek tek üretiliyor, bu yüzden biraz daha yavaş."
    return last.strip()


# ---------------------------------------------------------------- belge ayrıntısı

@st.cache_data(max_entries=48)
def _page_png(file: str, page: int) -> bytes:
    with pymupdf.open(data.DOCS_DIR / file) as doc:
        return doc[page - 1].get_pixmap(dpi=85).tobytes("png")


def _topics_tab(d: dict) -> None:
    ts = data.topics(d["stem"])
    if not ts:
        st.info("Bu belge için konu bulunamadı.")
        return
    if ts[0].get("source") == "sections":
        st.caption("Konu haritası henüz çıkarılmadı; şimdilik PDF'teki bölüm başlıkları gösteriliyor.")
    pool = [it for it in R.all_items().values() if it["doc"] == d["stem"] and R.usable(it)]
    rows = []
    for t in ts:
        pages = set(t["pages"])
        rows.append({"Konu": t["title"], "Sayfalar": ", ".join(map(str, t["pages"])),
                     "Hazır soru": sum(it["check"].get("evidence_page") in pages for it in pool)})
    st.dataframe(rows, hide_index=True, width="stretch",
                 column_config={"Hazır soru": st.column_config.NumberColumn(
                     help="Bu konunun sayfalarına bağlı, doğrulanmış soru sayısı (sınavlarda anında kullanılır)")})


def _pages_tab(d: dict) -> None:
    p = data.parsed(d["stem"])
    if not p:
        st.info("Bu belge henüz okunmadı.")
        return
    pages = p["pages"]
    n = st.select_slider("Sayfa", options=[x["page"] for x in pages], key=f"s_{d['stem']}")
    pg = pages[n - 1]
    img, txt = st.columns([1, 1], gap="large")
    with img:
        st.image(_page_png(d["file"], n), width="stretch")
    with txt:
        b = st.container(horizontal=True)
        b.badge(SOURCE_TR.get(pg.get("source", "text"), "?"), color="violet" if pg.get("source") == "vision" else "gray")
        if pg.get("quality") == "needs_vision":
            b.badge("Görsel okuma bekliyor", color="orange")
        for f in pg.get("flags", []):
            b.badge(FLAG_TR.get(f, f), color="blue")
        style.html(f"<div class='nr-card' style='white-space:pre-wrap;font-size:.92rem;max-height:520px;overflow:auto'>"
                   f"{style.esc(pg['text']) or '(metin yok)'}</div>")
        st.caption("Sistemin bu sayfadan çıkardığı metin" + (f" · görsel okuma: `{pg['vision_model']}`"
                                                             if pg.get("vision_model") else ""))


def _quality_tab(d: dict) -> None:
    p = data.parsed(d["stem"]) or {}
    c = st.columns(3, gap="medium")
    c[0].metric("Görselden okunan sayfa", d["vision_pages"], border=True)
    c[1].metric("Tablosu çıkarılan sayfa", d["table_pages"], border=True)
    c[2].metric("Silinen üst/alt bilgi satırı", sum(x.get("removed_lines", 0) for x in p.get("pages", [])), border=True)
    skipped = [x for x in p.get("pages", []) if {"title_page", "toc_like"} & set(x.get("flags", []))]
    if skipped:
        st.caption("Soru üretiminden çıkarılan sayfalar: "
                   + ", ".join(f"s.{x['page']} ({', '.join(FLAG_TR.get(f, f) for f in x['flags'])})" for x in skipped))
    if d["pending_vision"]:
        st.caption(f"{d['pending_vision']} sayfa görsel okuma bekliyor (kota açılınca okunur).")


def render() -> None:
    style.header("İçerik", "Belgeler", "Ders notlarını ekle ve sistemin her notu nasıl okuduğunu, hangi konulara "
                 "ayırdığını gör.")
    _add()
    _jobs()
    docs = data.documents()
    if not docs:
        return
    st.space("small")
    stem = st.segmented_control("Belge", [d["stem"] for d in docs], format_func=data.short,
                                default=docs[0]["stem"], label_visibility="collapsed") or docs[0]["stem"]
    d = next(x for x in docs if x["stem"] == stem)
    pool = sum(it["doc"] == stem and R.usable(it) for it in R.all_items().values())
    st.caption(f"{d['title']} · {d['pages']} sayfa · dil {d['language'].upper()} · "
               f"{len(data.topics(stem))} konu · havuzda {pool} doğrulanmış soru")
    t1, t2, t3 = st.tabs(["Konular", "Sayfalar", "Okuma kalitesi"])
    with t1:
        _topics_tab(d)
    with t2:
        _pages_tab(d)
    with t3:
        _quality_tab(d)


render()

"""Belgeler: ders notu ekle (arka planda okunur, konu haritası çıkarılır, soru havuzu hazırlanır) ve her notun
konularını, sayfalarını, okuma kalitesini gör.

Belge kütüphanesi (src/library.py): yüklenen not yalnızca yükleyene görünür; istenirse herkese açılır (geri
alınamaz). Sistemde zaten olan bir not (aynı dosya ya da aynı içerik, adı farklı olsa da) yeniden işlenmez,
yükleyenin listesine eklenir."""

import time

import pymupdf
import streamlit as st

from src import library
from src import request as R
from src.ui import data, style, upload

STEPS = ["PDF okuma", "Görsel okuma", "Bölümleme", "Dizin", "Soru havuzu", "Doğrulama"]
SOURCE_TR = {"text": "Metin katmanı", "vision": "Görselden okundu"}
FLAG_TR = {"title_page": "Kapak", "toc_like": "İçindekiler", "image_heavy": "Görsel ağırlıklı",
           "noisy_text": "Bozuk metin", "tables_extracted": "Tablo çıkarıldı"}


# ---------------------------------------------------------------- ekleme ve işler

def _add() -> None:
    """Yükleme akışı src/ui/upload.py'de (ana sayfadaki "+ Yeni not ekle" penceresi de onu kullanır)."""
    with st.expander("Yeni ders notu ekle", icon=":material/upload_file:", expanded=not data.my_documents()):
        if upload.uploader("docs_up"):
            st.rerun()


def _start(file: str, lang: str | None) -> None:
    upload.start(file, lang)
    st.rerun()


@st.dialog("Notu herkese aç")
def _publish(d: dict) -> None:
    st.markdown(f"**{data.short(d['stem'])}** bütün hesaplara açılacak: sayfaları, sistemin çıkardığı metin, "
                "soruları ve kanıt alıntıları herkes görebilecek, bu nottan sınav hazırlayıp kart çalışabilecek.")
    st.warning("Bu işlem geri alınamaz: herkese açılan not yeniden gizlenemez.", icon=":material/warning:")
    c = st.columns(2)
    if c[0].button("Herkese aç", type="primary", width="stretch", key="pub_yes"):
        library.publish(d["stem"], data.uid())
        st.cache_data.clear()
        st.rerun()
    if c[1].button("Vazgeç", width="stretch", key="pub_no"):
        st.rerun()


def _actions(d: dict) -> None:
    """Görünürlük, ad ve (işlenmemişse) işle düğmesi."""
    meta = data.doc_meta().get(d["stem"], {})
    mine = meta.get("owner") == data.uid()
    row = st.container(horizontal=True, vertical_alignment="center", gap="small")
    if meta.get("public"):
        row.badge("Herkese açık", icon=":material/public:", color="green")
    else:
        row.badge("Gizli", icon=":material/lock:", color="gray",
                  help="Yalnızca bu notu yükleyenler görüyor.")
        if library.has_access(d["stem"], data.uid()) and row.button("Herkese aç", key=f"pub_{d['stem']}",
                                                                     icon=":material/public:", type="tertiary"):
            _publish(d)
    if mine:
        with row.popover("Adını değiştir", icon=":material/edit:", type="tertiary"):
            new = st.text_input("Görünen ad", value=data.short(d["stem"]), key=f"ren_{d['stem']}", max_chars=80)
            if st.button("Kaydet", key=f"renb_{d['stem']}", type="primary"):
                try:
                    library.rename(d["stem"], data.uid(), new)
                    st.cache_data.clear()
                    st.rerun()
                except library.LibraryError as e:
                    st.error(str(e))
    job = data.job_status(d["stem"])
    if not d["parsed"] and not (job and not job["done"] and not job["failed"]):
        st.info("Bu not henüz işlenmedi.", icon=":material/hourglass_empty:")
        if st.button("Notu işle", type="primary", icon=":material/play_arrow:", key=f"run_{d['stem']}"):
            _start(d["file"], None)


@st.fragment(run_every=4)
def _jobs() -> None:
    mine = data.visible()
    running = [(s, j) for s, j in data.jobs() if not j["done"] and not j["failed"] and s in mine
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
    docs = data.my_documents()
    if not docs:
        return
    st.space("small")
    names = [d["stem"] for d in docs]
    if (want := st.session_state.pop("doc_open", None)) in names:  # ana sayfada karta tıklandı
        st.session_state.doc_sel = want
    if st.session_state.get("doc_sel") not in names:
        st.session_state.doc_sel = names[0]
    stem = st.segmented_control("Belge", names, format_func=data.short, key="doc_sel",
                                label_visibility="collapsed") or names[0]
    d = next(x for x in docs if x["stem"] == stem)
    pool = sum(it["doc"] == stem and R.usable(it) for it in R.all_items().values())
    st.caption(f"{d['title']} · {d['pages']} sayfa · dil {d['language'].upper()} · "
               f"{len(data.topics(stem))} konu · havuzda {pool} doğrulanmış soru")
    _actions(d)
    t1, t2, t3 = st.tabs(["Konular", "Sayfalar", "Okuma kalitesi"])
    with t1:
        _topics_tab(d)
    with t2:
        _pages_tab(d)
    with t3:
        _quality_tab(d)


render()

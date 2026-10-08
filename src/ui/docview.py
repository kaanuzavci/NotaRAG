"""Not penceresi ve not kartı (ana sayfa ve Belgeler ortak).

Bir nota tıklayınca sayfanın üstünde geniş bir pencere açılır (st.dialog; arkadaki sayfa hafifçe bulanıklaşır,
style.py): üstte notun kimliği (renkli kapak, sayfa / dil / konu / hazır soru sayıları, gizli ya da herkese açık,
bildiğin soru), sağda Sınav hazırla, Kartları çalış, Adını değiştir, Herkese aç; altında üç sekme:
  Konular        konu haritası, her konunun sayfaları, hazır soru sayısı ve senin ustalık durumun; konuya tıklayınca
                 o konunun ilk sayfası tam ekran okuyucuda açılır. Liste kendi içinde kayar.
  Sayfalar       sayfa görüntüsü + sistemin o sayfadan çıkardığı metin; "Tam ekran çalış" (src/ui/reader.py)
  Okuma kalitesi görselden okunan, tablosu çıkarılan, üretimden çıkarılan sayfalar
(Hazır sorular sekmesi kaldırıldı, kullanıcı kararı 2026-10-08: sorular sınavın işi.)

Pencere ekrandan taşmaz: içerik pencerenin içinde kayar (konu listesi, sayfa metni); bulanık örtünün kendisi kaymaz.
Açık not session_state.doc_open'da durur: uygulama baştan çalışınca (ör. ad değişince) pencere yeniden açılır; kişi
kapatınca (X, Esc, dışarı tıklama) on_dismiss temizler. Tam ekran okuyucu açıkken sayfa kendini çizmez; okuyucu
kapanınca pencere geldiği sekmede, okunan sayfada geri açılır.
"""

from __future__ import annotations

import time
from collections import Counter

import streamlit as st

from src import library
from src.ui import data, reader, style, upload
from src.ui.shelf import Component, palette

STEPS = ["okunuyor", "görselden okunuyor", "bölümleniyor", "dizine ekleniyor", "sorular üretiliyor", "doğrulanıyor"]
TABS = ["Konular", "Sayfalar", "Okuma kalitesi"]
SOURCE_TR = {"text": "Metin katmanı", "vision": "Görselden okundu"}
FLAG_TR = {"title_page": "Kapak", "toc_like": "İçindekiler", "image_heavy": "Görsel ağırlıklı",
           "noisy_text": "Bozuk metin", "tables_extracted": "Tablo çıkarıldı"}
_LOCK = ('<svg viewBox="0 0 24 24"><path d="M6 22q-.8 0-1.4-.6T4 20V10q0-.8.6-1.4T6 8h1V6q0-2.1 1.5-3.5T12 1q2.1 0 '
         '3.5 1.5T17 6v2h1q.8 0 1.4.6T20 10v10q0 .8-.6 1.4T18 22Zm3-14h6V6q0-1.3-.9-2.1T12 3q-1.3 0-2.1.9T9 6Z"/></svg>')
_GLOBE = ('<svg viewBox="0 0 24 24"><path d="M12 22q-2.1 0-3.9-.8t-3.2-2.1q-1.4-1.4-2.1-3.2T2 12q0-2.1.8-3.9t2.1-3.2Q6.3 '
          '3.5 8.1 2.8T12 2q2.1 0 3.9.8t3.2 2.1q1.4 1.4 2.1 3.2T22 12q0 2.1-.8 3.9t-2.1 3.2q-1.4 1.4-3.2 2.1T12 22Zm-1-2.1V18q'
          '-.8 0-1.4-.6T9 16v-1l-4.8-4.8q-.1.5-.1.9V12q0 3 2 5.3t4.9 2.6Zm6.9-2.5q1-1.1 1.6-2.5T20 12q0-2.5-1.4-4.5T15 4.6V5q'
          '0 .8-.6 1.4T13 7h-2v2q0 .4-.3.7T10 10H8v2h6q.4 0 .7.3t.3.7v3h1q.7 0 1.2.4t.7 1Z"/></svg>')

_CSS = """<style>
/* Not penceresi (src/ui/docview.py) — sınıflar dv- önekli */
.dv-hero { display: flex; gap: 22px; align-items: center; padding: 2px 0 4px; }
.dv-cover { position: relative; flex: none; width: 92px; height: 120px; margin: 4px 10px 10px 2px; border-radius: 14px;
  background: var(--c1); overflow: hidden; border: 1px solid rgba(30, 36, 51, .08);
  box-shadow: 7px 7px 0 -1px var(--c2), 7px 7px 0 0 rgba(30, 36, 51, .08), 0 16px 28px -20px rgba(30, 36, 51, .7); }
.dv-cover::after { content: ""; position: absolute; inset: 0;
  background-image: repeating-linear-gradient(135deg, transparent 0 10px, rgba(255, 255, 255, .34) 10px 11px); }
.dv-cover span { position: absolute; left: 12px; bottom: 7px; z-index: 1; font: 600 60px/.8 'Fraunces', serif; color: var(--a); }
.dv-info { min-width: 0; display: flex; flex-direction: column; gap: 9px; }
.dv-orig { font-size: .86rem; color: #6B6F7B; line-height: 1.35; }
.dv-facts { display: flex; flex-wrap: wrap; gap: 6px; }
.dv-facts span { font-size: .8rem; color: #4A5163; background: #FFFDF8; border: 1px solid #E8E0CE; border-radius: 999px;
  padding: .12rem .62rem; white-space: nowrap; }
.dv-facts b { color: #1E2433; font-weight: 600; }
.dv-vis { display: flex; align-items: center; gap: 7px; font-size: .84rem; color: #5B5F6B; }
.dv-vis svg { width: 15px; height: 15px; fill: currentColor; flex: none; }
.dv-vis b { color: #1E2433; font-weight: 600; }
.dv-prog { display: flex; align-items: center; gap: 10px; font-size: .82rem; color: #5B5F6B; max-width: 380px; }
.dv-prog .bar { flex: 1; height: 6px; border-radius: 6px; background: #EFE8D8; overflow: hidden; }
.dv-prog .bar i { display: block; height: 100%; border-radius: 6px; background: var(--a); }
.dv-prog b { color: #1E2433; font-weight: 600; white-space: nowrap; }
.dv-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; font-size: .82rem; color: #4A5163; margin: .1rem 0 .1rem; }
.dv-legend span { display: inline-flex; align-items: center; gap: 6px; }
.dv-legend i { width: 18px; height: 18px; border-radius: 6px; display: inline-grid; place-items: center; font-style: normal;
  font-size: .68rem; font-weight: 700; color: #FFFFFF; }
.dv-legend em { font-style: normal; color: #7A6F57; margin-left: auto; font-size: .8rem; }
/* Sayfalar sekmesi: görüntü ve metin pencereye sığar (pencere ekranın altına taşmasın), metin kendi içinde kayar */
.dv-sheet { background: #EFE9DC; border-radius: 16px; padding: 14px; display: flex; justify-content: center; align-items: center;
  height: max(220px, calc(100vh - 510px)); }
.dv-sheet img { display: block; max-width: 100%; max-height: 100%; border-radius: 3px; background: #FFFFFF;
  box-shadow: 0 2px 4px rgba(30, 36, 51, .12), 0 10px 22px -14px rgba(30, 36, 51, .4); }
.dv-ptopic { font-size: .84rem; color: #5B5F6B; margin-bottom: .45rem; }
.dv-ptopic b { color: #1E2433; font-weight: 600; }
.dv-text { white-space: pre-wrap; font-size: .9rem; line-height: 1.62; color: #2A3040; overflow: auto; overscroll-behavior: contain;
  max-height: max(140px, calc(100vh - 614px)); background: #FFFDF8; border: 1px solid #E4DCC9; border-radius: 14px;
  padding: 14px 16px; }
</style>"""

# Konu listesi: her satır tıklanabilir (CCv2; düz HTML tıklamayı Python'a iletemez) → o konunun ilk sayfası okuyucuda.
# Liste kendi içinde kayar; yüksekliği JS'te pencerenin altına kadar kalan yerden hesaplanır (pencere ekrandan taşmasın).
# Satırlarda gölge ve kalkma yok, yalnızca renk değişir: kaydırırken her satırın yeniden boyanması takılma yapıyordu.
_TOPICS_CSS = """
:host { display: block; }
.list { font-family: 'Instrument Sans', sans-serif; color: #1E2433; display: flex; flex-direction: column; gap: 6px;
  padding: 2px 8px 6px 2px; overflow-y: auto; overscroll-behavior: contain; contain: content;
  scrollbar-width: thin; scrollbar-color: #CFC4AC transparent; }
.row { flex: none; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto 126px 70px 22px; gap: 12px; align-items: center;
  padding: 11px 14px; border-radius: 13px; background: #FFFDF8; border: 1px solid #E8E0CE; cursor: pointer; outline: none;
  transition: border-color .12s, background-color .12s; }
.row:hover, .row:focus-visible { border-color: #CFC4AC; background: #FFFFFF; }
.row:focus-visible { outline: 2px solid #1F3A5F; outline-offset: -2px; }
.n { font: 500 .72rem 'JetBrains Mono', monospace; color: #8A7E63; }
.t { font-size: .94rem; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pl { font-size: .78rem; color: #6B6F7B; white-space: nowrap; }
.st { display: inline-flex; align-items: center; gap: 7px; font-size: .8rem; color: #4A5163; white-space: nowrap; }
.st i { width: 18px; height: 18px; border-radius: 6px; display: inline-grid; place-items: center; font-style: normal; font-size: .66rem;
  font-weight: 700; color: #FFFFFF; background: var(--sc); }
.q { font-size: .8rem; color: #4A5163; text-align: right; white-space: nowrap; }
.q b { color: #1E2433; font-weight: 600; }
.q.none { color: #A39B88; }
.go { width: 22px; height: 22px; color: #B6A98C; transition: transform .2s, color .2s; }
.go svg { width: 22px; height: 22px; fill: currentColor; }
.row:hover .go, .row:focus-visible .go { color: #1F3A5F; transform: translateX(3px); }
@media (max-width: 760px) { .row { grid-template-columns: 26px minmax(0, 1fr) 70px; } .pl, .st, .go { display: none; } }
@media (prefers-reduced-motion: reduce) { .row, .go { transition: none; } }
"""

_TOPICS_JS = """
const ARROW = '<svg viewBox="0 0 24 24"><path d="M16.2 13H4v-2h12.2l-5.6-5.6L12 4l8 8-8 8-1.4-1.4Z"/></svg>'
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]))
}
export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root = parentElement.querySelector(".list")
  if (!root) return
  const sig = JSON.stringify(data)
  if (root.dataset.sig !== sig) {
    root.dataset.sig = sig
    root.innerHTML = (data.rows || []).map((r, k) => `
      <div class="row" role="button" tabindex="0" data-k="${k}" title="${esc(r.t)} · sayfaları tam ekranda aç">
        <span class="n">${String(r.i).padStart(2, "0")}</span><span class="t">${esc(r.t)}</span>
        <span class="pl">${esc(r.pl)}</span>
        <span class="st" style="--sc:${r.sc}"><i>${esc(r.si)}</i>${esc(r.sl)}</span>
        <span class="q${r.q ? "" : " none"}">${r.q ? `<b>${r.q}</b> soru` : "soru yok"}</span>
        <span class="go">${ARROW}</span></div>`).join("")
  }
  const fire = (el) => { const row = el.closest("[data-k]"); if (row) setTriggerValue("open", Number(row.dataset.k)) }
  root.onclick = (e) => fire(e.target)
  root.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fire(e.target) } }
  // Liste pencerenin altına kadar uzar, fazlası kendi içinde kayar: yükseklik = ekran − listenin üstü − pencerenin alt payı
  const fit = () => {
    const top = root.getBoundingClientRect().top
    if (top > 0) root.style.maxHeight = Math.max(180, Math.floor(innerHeight - top - 92)) + "px"
  }
  fit()
  requestAnimationFrame(fit)
  setTimeout(fit, 450)  // pencerenin açılış animasyonu bitince yeniden ölç
  if (root._fit) removeEventListener("resize", root._fit)
  root._fit = fit
  addEventListener("resize", fit)
  return () => removeEventListener("resize", fit)
}
"""

_TOPICS = Component("nr_topics", html='<div class="list"></div>', css=_TOPICS_CSS, js=_TOPICS_JS)


# ---------------------------------------------------------------- not kartı (raf ve ızgara)

def running(stem: str, jobs: dict) -> dict | None:
    """Notun süren işi (son 6 saatte başlamış, bitmemiş, çökmemiş) ya da None."""
    job = jobs.get(stem)
    return job if job and not job["done"] and not job["failed"] and time.time() - job["started"] < 6 * 3600 else None


def card(d: dict, meta: dict, jobs: dict, prog: dict, public_view: bool = False) -> dict:
    """Notun deste kartı (src/ui/shelf.py). public_view: kişinin listesinde olmayan herkese açık not."""
    stem, job = d["stem"], running(d["stem"], jobs)
    n_topics = len(data.topics(stem)) if d["chunks"] else 0
    n_ready = data.ready().get(stem, 0)
    c = {"id": stem, "kind": "doc", "title": data.short(stem), "palette": palette(stem, meta.get("order")),
         "sheets": 2 if n_ready >= 20 else (1 if n_ready else 0)}
    if job:
        step = max(1, job["step"])
        c.update(meta=f"{d['pages']} sayfa" if d["pages"] else "yeni not", badge="İşleniyor", badge_icon="sync",
                 progress=step / 6, live=True, plabel=STEPS[step - 1].capitalize(), pvalue=f"{step}/6",
                 actions=[{"id": "open", "label": "Ayrıntı"}])
        return c
    c["meta"] = f"{d['pages']} sayfa · {n_topics} konu" if d["parsed"] else "işlenmeyi bekliyor"
    if n_topics:  # fişin çizgili satırlarında notun ilk konuları (başlık iki satırsa iki konu: yer kalsın)
        c["lines"] = [t["title"] for t in data.topics(stem)[:2 if len(c["title"]) > 22 else 3]]
    if public_view:
        c.update(badge="Herkese açık", badge_icon="globe", plabel=f"{n_ready} hazır soru",
                 actions=[{"id": "add", "label": "Notlarıma ekle"}, {"id": "open", "label": "Göz at"}])
        return c
    c.update(badge="Herkese açık" if meta.get("public") else "Gizli", badge_icon="globe" if meta.get("public") else "lock")
    p = prog.get(stem)
    if n_ready and p and p["n"] and p["seen"]:
        c.update(progress=p["known"] / p["n"], plabel="Bildiğin", pvalue=f"{p['known']} / {p['n']} soru")
    elif n_ready:
        c.update(progress=0, plabel="Henüz çalışmadın", pvalue=f"{n_ready} soru")
    elif not d["parsed"]:
        c.update(plabel="Ayrıntıdan işlemeyi başlat")
    else:
        c.update(plabel="Henüz hazır soru yok")
    c["actions"] = ([{"id": "exam", "label": "Sınav"}, {"id": "cards", "label": "Kartlar"}] if n_ready
                    else [{"id": "open", "label": "Ayrıntı"}])
    return c


def act(ident: str, action: str, in_fragment: bool = False) -> None:
    """Not kartındaki tıklama: kartın kendisi pencereyi açar; Sınav / Kartlar o notla ilgili sayfaya geçer.
    Pencere sayfanın sonundaki show() ile aynı çalıştırmada açılır (fazladan bir çalıştırma beklenmez). Raf bir parçanın
    (fragment, işlenen not varken) içindeyse o çalıştırmada show()'a gelinmez → sayfa baştan çalıştırılır."""
    if action == "add":
        library.add_to_library(ident, data.uid())
        st.cache_data.clear()
        st.toast(f"“{data.short(ident)}” notlarına eklendi.", icon=":material/library_add:")
        st.rerun()
    elif action in ("exam", "cards"):
        _study(action, ident)
    else:
        open_doc(ident)
        if in_fragment:
            st.rerun()


def _study(kind: str, stem: str) -> None:
    st.session_state.pop("doc_open", None)
    if kind == "exam":
        st.session_state.pop("exam", None)  # yarım sınav kaybolmaz: ana sayfada "kaldığın yerden devam et"te durur
        st.session_state.exam_doc = stem
        st.switch_page("ui/pages/exam.py")
    st.session_state.pop("cards", None)
    st.session_state.cards_doc = stem
    st.switch_page("ui/pages/cards.py")


# ---------------------------------------------------------------- pencere: açma, kapama, okuyucu

def open_doc(stem: str, tab: str = "Konular") -> None:
    st.session_state.doc_open = stem
    st.session_state.dv_tab = tab


def _dismissed() -> None:
    st.session_state.pop("doc_open", None)


def show() -> None:
    """Sayfanın sonunda çağrılır: açık not varsa penceresi."""
    stem = st.session_state.get("doc_open")
    if not stem:
        return
    if stem not in data.visible():
        st.session_state.pop("doc_open", None)
        return
    st.dialog(data.short(stem), width="large", on_dismiss=_dismissed)(_body)(stem)


def reading() -> bool:
    """Tam ekran okuyucu açık mı (açıksa sayfa kendini çizmez, yalnızca okuyucuyu)."""
    return reader.active()


def reader_view() -> None:
    reader.show(on_close=_back)


def _back(r: dict, page: int) -> None:
    """Okuyucu kapandı: pencere geldiği sekmede, okunan sayfada yeniden açılsın."""
    open_doc(r["doc"], r.get("tab", "Sayfalar"))
    st.session_state[f"dv_pg_{r['doc']}"] = page


def _read(stem: str, page: int, tab: str, topic: int | None = None) -> None:
    """Okuyucuyu aç (pencere kapanır). topic: Konular'dan gelindiyse o konunun sırası (sayfa iki konuda geçse de
    okuyucunun üst şeridinde tıklanan konu yazsın)."""
    st.session_state.pop("doc_open", None)
    reader.open_reader(stem, page, tab=tab, topic=topic)
    st.rerun()


# ---------------------------------------------------------------- pencerenin içi

def _body(stem: str) -> None:
    d = next((x for x in data.documents() if x["stem"] == stem), None)
    if d is None:
        st.info("Bu not artık bulunamadı.", icon=":material/search_off:")
        return
    style.html(_CSS)
    meta = data.doc_meta().get(stem, {})
    n_ready = data.ready().get(stem, 0)  # önbellekli: sekme değiştirmek dosya okumasın
    left, right = st.columns([1.5, 1], vertical_alignment="center", gap="medium")
    with left:
        _hero(d, meta, n_ready)
    with right:
        _actions(d, meta, n_ready)
    _state(d)
    if not d["parsed"]:
        return
    tabs = st.tabs(TABS, key="dv_tab", on_change="rerun")
    for tab, draw in zip(tabs, (_topics_tab, _pages_tab, _quality_tab)):
        if tab.open:  # yalnızca seçili sekme çalışır (sayfa görüntüsü boşuna hazırlanmasın)
            with tab:
                draw(d)


def _hero(d: dict, meta: dict, n_ready: int) -> None:
    stem = d["stem"]
    c1, c2, ink, a = palette(stem, meta.get("order"))
    name = data.short(stem)
    first = (name.strip() or "?")[0]
    mono = style.esc({"i": "İ", "ı": "I"}.get(first, first.upper()))  # Türkçe büyük harf (kartlardaki gibi)
    n_topics = len(data.topics(stem)) if d["chunks"] else 0
    facts = [f"<b>{d['pages']}</b> sayfa" if d["pages"] else "okunmadı",
             d["language"].upper() if d["language"] != "?" else "",
             f"<b>{n_topics}</b> konu" if n_topics else "", f"<b>{n_ready}</b> hazır soru"]
    if meta.get("public"):
        vis = f'{_GLOBE}<span><b>Herkese açık</b> · bütün hesaplar görebilir ve kendi notlarına ekleyebilir</span>'
    else:
        vis = f'{_LOCK}<span><b>Gizli</b> · yalnızca bu notu yükleyenler görüyor</span>'
    prog = next((p for p in data.mastery()["docs"] if p["doc"] == stem), None)
    bar = ""
    if prog and prog["n"]:
        pct = round(100 * prog["known"] / prog["n"])
        bar = (f'<div class="dv-prog"><div class="bar"><i style="width:{max(2, pct)}%"></i></div>'
               f'<span>Bildiğin <b>{prog["known"]} / {prog["n"]}</b> soru</span></div>')
    title = d["title"].strip()  # PDF'in kendi başlığı: yalnızca anlamlıysa (bazı PDF'lerde "01" ya da dosya adı)
    orig = (f'<div class="dv-orig">{style.esc(title)}</div>'
            if title not in (name, stem) and len(title) > 3 and sum(c.isalpha() for c in title) > 2 else "")
    style.html(f'<div class="dv-hero" style="--c1:{c1};--c2:{c2};--ink:{ink};--a:{a}">'
               f'<div class="dv-cover"><span>{mono}</span></div><div class="dv-info">{orig}'
               f'<div class="dv-facts">{"".join(f"<span>{x}</span>" for x in facts if x)}</div>'
               f'<div class="dv-vis">{vis}</div>{bar}</div></div>')


def _actions(d: dict, meta: dict, n_ready: int) -> None:
    stem, uid = d["stem"], data.uid()
    row = st.container(horizontal=True, horizontal_alignment="right", gap="small")
    if meta.get("public") and stem not in data.mine():
        if row.button("Notlarıma ekle", icon=":material/library_add:", key="dv_add", type="primary"):
            library.add_to_library(stem, uid)
            st.cache_data.clear()
            st.toast(f"“{data.short(stem)}” notlarına eklendi.", icon=":material/library_add:")
            st.rerun()
    if n_ready:
        if row.button("Sınav hazırla", icon=":material/quiz:", key="dv_exam",
                      type="secondary" if meta.get("public") and stem not in data.mine() else "primary"):
            _study("exam", stem)
        if row.button("Kartları çalış", icon=":material/style:", key="dv_cards"):
            _study("cards", stem)
    row2 = st.container(horizontal=True, horizontal_alignment="right", gap="small")
    if meta.get("owner") == uid:
        with row2.popover("Adını değiştir", icon=":material/edit:", type="tertiary"):
            new = st.text_input("Görünen ad", value=data.short(stem), key=f"dv_ren_{stem}", max_chars=80)
            if st.button("Kaydet", key=f"dv_renb_{stem}", type="primary"):
                try:
                    library.rename(stem, uid, new)
                    st.cache_data.clear()
                    st.rerun()  # pencere yeni adıyla yeniden açılır (doc_open duruyor)
                except library.LibraryError as e:
                    st.error(str(e))
    if not meta.get("public") and library.has_access(stem, uid):
        with row2.popover("Herkese aç", icon=":material/public:", type="tertiary"):
            st.markdown(f"**{data.short(stem)}** bütün hesaplara açılacak: sayfaları, sistemin çıkardığı metin, "
                        "soruları ve kanıt alıntıları herkes görebilecek, bu nottan sınav hazırlayıp kart çalışabilecek.")
            st.warning("Bu işlem geri alınamaz: herkese açılan not yeniden gizlenemez.", icon=":material/warning:")
            if st.button("Anladım, herkese aç", type="primary", key=f"dv_pub_{stem}", width="stretch"):
                library.publish(stem, uid)
                st.cache_data.clear()
                st.toast("Not artık herkese açık.", icon=":material/public:")
                st.rerun()


def _state(d: dict) -> None:
    """Not işleniyorsa adım ve ayrıntı (kendiliğinden yenilenir); hiç işlenmediyse "Notu işle"."""
    stem = d["stem"]
    if running(stem, dict(data.jobs())):
        st.fragment(run_every=4)(_job)(stem)
    elif not d["parsed"]:
        st.info("Bu not henüz işlenmedi. İşlenince konuları, sayfaları ve hazır soruları burada görünür.",
                icon=":material/hourglass_empty:")
        if st.button("Notu işle", type="primary", icon=":material/play_arrow:", key=f"dv_run_{stem}"):
            upload.start(d["file"], None)
            st.rerun()


def _job(stem: str) -> None:
    j = data.job_status(stem)
    if not j or j["done"] or j["failed"]:
        st.rerun()  # iş bitti: pencere yeni verilerle baştan
    step = max(1, j["step"])
    st.progress(step / 6, text=f"İşleniyor · {STEPS[step - 1]} ({step}/6)")
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


# ---------------------------------------------------------------- sekmeler

def _topics_tab(d: dict) -> None:
    stem, ts = d["stem"], data.topics(d["stem"])
    if not ts:
        st.info("Bu not için konu bulunamadı.", icon=":material/info:")
        return
    prog = next((p for p in data.mastery()["docs"] if p["doc"] == stem), None)
    status = {t["title"]: t["status"] for t in (prog["topics"] if prog else [])}
    qp = reader.per_page(stem)
    rows = []
    for i, t in enumerate(ts, 1):
        if not t.get("pages"):
            continue
        sc, si, sl = style.MASTERY[status.get(t["title"], "başlanmadı")]
        rows.append({"i": i, "t": t["title"], "p": min(t["pages"]), "pl": reader.pages_label(t["pages"]),
                     "q": sum(qp.get(p, 0) for p in set(t["pages"])), "sc": sc, "si": si, "sl": sl})
    count = Counter(r["sl"] for r in rows)
    legend = "".join(f'<span><i style="background:{c}">{s}</i>{n} {lab.lower()}</span>'
                     for c, s, lab in style.MASTERY.values() if (n := count[lab]))
    note = ("Konu haritası henüz çıkarılmadı; PDF'teki bölüm başlıkları gösteriliyor. "
            if ts[0].get("source") == "sections" else "")
    style.html(f'<div class="dv-legend">{legend}<em>{note}Bir konuya tıkla: sayfaları tam ekranda açılır.</em></div>')
    res = _TOPICS(key=f"dv_topics_{stem}", data={"rows": rows}, on_open_change=lambda: None)
    if res.open is not None and 0 <= int(res.open) < len(rows):  # tıklanan satırın sırası = okuyucunun içindekiler sırası
        k = int(res.open)
        _read(stem, rows[k]["p"], "Konular", topic=k)


def _step(key: str, delta: int, n: int) -> None:
    st.session_state[key] = max(1, min(n, st.session_state.get(key, 1) + delta))


def _pages_tab(d: dict) -> None:
    stem, p = d["stem"], data.parsed(d["stem"])
    if not p or not p["pages"]:
        st.info("Bu not henüz okunmadı.", icon=":material/info:")
        return
    pages, key = p["pages"], f"dv_pg_{stem}"
    n = len(pages)
    st.session_state[key] = max(1, min(n, int(st.session_state.get(key, 1))))
    cur = st.session_state[key]
    bar = st.container(horizontal=True, vertical_alignment="center", gap="small")
    bar.button("", icon=":material/chevron_left:", key="dv_prev", on_click=_step, args=(key, -1, n), disabled=cur <= 1,
               help="Önceki sayfa")
    bar.slider("Sayfa", 1, max(n, 2), key=key, label_visibility="collapsed", disabled=n < 2,
               format="Sayfa %d")
    bar.button("", icon=":material/chevron_right:", key="dv_next", on_click=_step, args=(key, 1, n), disabled=cur >= n,
               help="Sonraki sayfa")
    if bar.button("Tam ekran çalış", icon=":material/fullscreen:", type="primary", key="dv_full",
                  help="Sayfalara tam ekranda çalış: ← → ile ileri geri, Esc ile geri dön"):
        _read(stem, cur, "Sayfalar")
    pg = pages[cur - 1]
    img, txt = st.columns([1.08, 1], gap="large")
    with img:
        style.html(f'<div class="dv-sheet"><img alt="Sayfa {cur}" src="{reader.data_url(d["file"], cur)}"></div>')
    with txt:
        toc = reader.toc(stem)
        k = next((i for i, t in enumerate(toc) if cur in t["pages"]), None)
        here = reader.per_page(stem).get(cur, 0)
        bits = [f'Konu: <b>{style.esc(toc[k]["t"])}</b>' if k is not None else "",
                f"bu sayfadan <b>{here}</b> hazır soru" if here else ""]
        style.html(f'<div class="dv-ptopic">{" · ".join(b for b in bits if b) or "&nbsp;"}</div>')
        b = st.container(horizontal=True, gap="small")
        b.badge(SOURCE_TR.get(pg.get("source", "text"), "?"), color="violet" if pg.get("source") == "vision" else "gray")
        if pg.get("quality") == "needs_vision":
            b.badge("Görsel okuma bekliyor", color="orange")
        for f in pg.get("flags", []):
            b.badge(FLAG_TR.get(f, f), color="blue")
        style.html(f'<div class="dv-text">{style.esc(pg["text"]) or "(metin yok)"}</div>')
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

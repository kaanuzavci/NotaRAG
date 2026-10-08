"""Tam ekran PDF okuyucu: notun sayfalarına tam ekranda çalışma (not penceresi → Sayfalar → "Tam ekran çalış", ya da
Konular'da bir konuya tıklayınca o konunun ilk sayfası).

Bütün pencereyi kaplayan koyu bir sahne (Streamlit özel bileşeni, CCv2): ortada sayfa görüntüsü, üstte notun adı ve
sayfanın konusu, altta sayaç ve sayfa kaydırıcısı, solda açılır içindekiler (konu haritası; tıklayınca o konunun ilk
sayfası). Klavye: ← → (PageUp/PageDown, boşluk) sayfa, Home/End baş/son, İ içindekiler, G genişliğe yay, F tarayıcıda
tam ekran, Esc kapat. Dokunmatikte parmakla kaydırınca sayfa çevrilir.

Sayfa görüntüleri istendikçe çizilir (PyMuPDF, uzun kenarı 1700 px JPEG, önbellekli). Bileşene açık sayfa ile komşuları
gönderilir; JS aldığı her sayfayı saklar → bir sonraki ve önceki sayfa anında açılır. Sayfa değişince yalnızca okuyucu
parçası (st.fragment) yeniden çalışır, sayfanın geri kalanı değil. Okuyucu açıkken sayfa kendini çizmez (docview);
kapanınca on_close(okuyucu durumu, son sayfa) çağrılır ve uygulama baştan çalışır (not penceresi geri gelir).
"""

from __future__ import annotations

import base64
import time
from collections import Counter

import pymupdf
import streamlit as st

from src import request as R
from src.ui import data
from src.ui.shelf import Component

LONG_EDGE = 1700      # px: tam ekranda keskin, sayfa başına ~150-300 KB
AHEAD = (1, 2, -1)    # açık sayfaya ek olarak gönderilenler (önce ileri)

_CSS = """
:host { display: block; }
.rd { position: fixed; inset: 0; z-index: 1000200; display: grid; grid-template-rows: 60px minmax(0, 1fr) 56px;
  background: #141922; color: #EDE6D6; font-family: 'Instrument Sans', sans-serif; animation: rd-in .22s ease-out both; }
@keyframes rd-in { from { opacity: 0; } }
button { font: inherit; color: inherit; }
svg { width: 20px; height: 20px; fill: currentColor; flex: none; }

/* üst şerit */
.top { display: flex; align-items: center; gap: 12px; padding: 0 14px; border-bottom: 1px solid rgba(237, 230, 214, .08); }
.ib { width: 40px; height: 40px; border-radius: 12px; border: 0; background: transparent; display: grid; place-items: center;
  cursor: pointer; transition: background .15s; }
.ib:hover { background: rgba(237, 230, 214, .1); }
.ttl { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.ttl b { font: 600 1.05rem/1.2 'Fraunces', serif; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ttl span { font-size: .8rem; color: #A9A18C; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 3px; }
.ttl span i { font-style: normal; color: #F2D64B; }
.tools { display: flex; gap: 6px; }
.tb { display: inline-flex; align-items: center; gap: 7px; height: 38px; padding: 0 13px; border-radius: 11px;
  border: 1px solid rgba(237, 230, 214, .16); background: transparent; font-size: .84rem; font-weight: 500; cursor: pointer;
  white-space: nowrap; transition: background .15s, color .15s, border-color .15s; }
.tb:hover { background: rgba(237, 230, 214, .08); }
.tb.on { background: #EDE6D6; color: #141922; border-color: #EDE6D6; }
.tb svg { width: 18px; height: 18px; }

/* orta: içindekiler + sahne */
.mid { display: grid; grid-template-columns: 0 minmax(0, 1fr); min-height: 0; transition: grid-template-columns .26s ease; }
.rd.toc-on .mid { grid-template-columns: 310px minmax(0, 1fr); }
.toc { overflow: hidden auto; background: #19202C; border-right: 1px solid rgba(237, 230, 214, .07); min-width: 0; }
.toch { padding: 16px 18px 6px; font: 500 .68rem 'JetBrains Mono', monospace; letter-spacing: .14em; text-transform: uppercase;
  color: #8F876F; white-space: nowrap; }
.toc ol { list-style: none; margin: 0; padding: 4px 8px 22px; width: 294px; box-sizing: border-box; }
.toc li { display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 2px 8px; padding: 9px 10px; border-radius: 11px;
  cursor: pointer; transition: background .15s; }
.toc li:hover { background: rgba(237, 230, 214, .06); }
.toc li.on { background: rgba(242, 214, 75, .13); }
.toc li .tn { font: 500 .72rem/1.5 'JetBrains Mono', monospace; color: #7F7966; }
.toc li.on .tn { color: #F2D64B; }
.toc li .tt { font-size: .87rem; line-height: 1.35; color: #EDE6D6; }
.toc li .tp { grid-column: 2; font-size: .73rem; color: #8F876F; }
.toc li .tp b { font-weight: 500; color: #B9B09A; }
.toc .none { padding: 10px 18px; font-size: .84rem; color: #8F876F; width: 274px; }

.stage { position: relative; min-height: 0; overflow: hidden; padding: 20px 84px; touch-action: pan-y; }
.paper { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; position: relative; }
.paper img { display: block; max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 4px; background: #FFFFFF;
  box-shadow: 0 2px 6px rgba(0, 0, 0, .3), 0 34px 70px -24px rgba(0, 0, 0, .7); user-select: none; -webkit-user-drag: none; }
.rd.wide .stage { overflow-y: auto; }
.rd.wide .paper { height: auto; min-height: 100%; align-items: flex-start; }
.rd.wide .paper img { width: min(100%, 1500px); max-height: none; }
.load { position: absolute; inset: 0; display: none; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; color: #A9A18C; font-size: .86rem; }
.load i { width: 30px; height: 30px; border-radius: 50%; border: 3px solid rgba(237, 230, 214, .15); border-top-color: #F2D64B;
  animation: spin .8s linear infinite; }
.paper.loading img { visibility: hidden; }
.paper.loading .load { display: flex; }
@keyframes spin { to { transform: rotate(360deg); } }
.nav { position: absolute; top: 50%; width: 54px; height: 54px; margin-top: -27px; border-radius: 50%; border: 0;
  background: rgba(237, 230, 214, .09); display: grid; place-items: center; cursor: pointer; z-index: 2;
  transition: background .15s, transform .15s, opacity .15s; }
.nav svg { width: 28px; height: 28px; }
.nav:hover { background: rgba(237, 230, 214, .18); }
.nav.prev { left: 16px; } .nav.next { right: 16px; }
.nav.prev:hover { transform: translateX(-2px); } .nav.next:hover { transform: translateX(2px); }
.nav:disabled { opacity: .22; cursor: default; transform: none; background: rgba(237, 230, 214, .09); }
.rd.wide .nav { position: fixed; }
.rd.wide.toc-on .nav.prev { left: 326px; }
.rd:focus { outline: none; }

/* alt şerit */
.bot { display: flex; align-items: center; gap: 18px; padding: 0 22px; border-top: 1px solid rgba(237, 230, 214, .08); }
.cnt { font: 500 .9rem 'JetBrains Mono', monospace; white-space: nowrap; min-width: 92px; color: #A9A18C; }
.cnt b { color: #EDE6D6; font-weight: 500; }
.scrub { flex: 1; min-width: 80px; -webkit-appearance: none; appearance: none; height: 22px; background: transparent; cursor: pointer; }
.scrub::-webkit-slider-runnable-track { height: 4px; border-radius: 4px;
  background: linear-gradient(to right, #F2D64B var(--p, 0%), rgba(237, 230, 214, .16) var(--p, 0%)); }
.scrub::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; margin-top: -6px; border-radius: 50%;
  background: #F2D64B; border: 3px solid #141922; box-shadow: 0 0 0 1px #F2D64B; }
.scrub:focus-visible { outline: none; }
.scrub:focus-visible::-webkit-slider-thumb { box-shadow: 0 0 0 4px rgba(242, 214, 75, .35); }
.qs { font-size: .8rem; color: #A9A18C; white-space: nowrap; }
.qs b { color: #EDE6D6; font-weight: 600; }
.keys { font-size: .76rem; color: #7F7966; white-space: nowrap; }
.keys kbd { font: 500 .7rem 'JetBrains Mono', monospace; color: #B9B09A; border: 1px solid rgba(237, 230, 214, .18);
  border-bottom-width: 2px; border-radius: 5px; padding: 0 5px; }
button:focus-visible, li:focus-visible { outline: 2px solid #F2D64B; outline-offset: 2px; }

@media (max-width: 860px) {
  .tb span, .keys { display: none; } .tb { padding: 0 10px; }
  .stage { padding: 12px 12px 64px; } .nav { top: auto; bottom: 8px; margin-top: 0; width: 46px; height: 46px; }
  .rd.toc-on .mid { grid-template-columns: minmax(0, 1fr) 0; } .rd.toc-on .toc { position: absolute; inset: 60px 0 56px 0; z-index: 3; }
}
@media (prefers-reduced-motion: reduce) { .rd, .load i { animation: none; } .mid, .nav, .tb { transition: none; } }
"""

_HTML = '<div class="rd" role="dialog" aria-modal="true" aria-label="Tam ekran okuyucu" tabindex="-1"></div>'

_JS = """
const ICON = {
  close: '<svg viewBox="0 0 24 24"><path d="M6.4 19 5 17.6l5.6-5.6L5 6.4 6.4 5l5.6 5.6L17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4-5.6-5.6Z"/></svg>',
  toc: '<svg viewBox="0 0 24 24"><path d="M3 17h12v-2H3Zm0-4h12v-2H3Zm0-6v2h12V7Zm14 10h2v-2h-2Zm0-10v2h2V7Zm0 6h2v-2h-2Z"/></svg>',
  wide: '<svg viewBox="0 0 24 24"><path d="M4 12l4-4v3h8V8l4 4-4 4v-3H8v3Z"/></svg>',
  full: '<svg viewBox="0 0 24 24"><path d="M5 19v-5h2v3h3v2Zm0-9V5h5v2H7v3Zm9 9v-2h3v-3h2v5Zm3-9V7h-3V5h5v5Z"/></svg>',
  unfull: '<svg viewBox="0 0 24 24"><path d="M8 19v-3H5v-2h5v5Zm6 0v-5h5v2h-3v3ZM5 10V8h3V5h2v5Zm9 0V5h2v3h3v2Z"/></svg>',
  prev: '<svg viewBox="0 0 24 24"><path d="m14 18-6-6 6-6 1.4 1.4-4.6 4.6 4.6 4.6Z"/></svg>',
  next: '<svg viewBox="0 0 24 24"><path d="M9.4 18 8 16.6l4.6-4.6L8 7.4 9.4 6l6 6Z"/></svg>'
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]))
}

function build(rd) {
  rd.innerHTML = `
    <header class="top">
      <button class="ib" data-a="close" title="Kapat (Esc)" aria-label="Kapat">${ICON.close}</button>
      <div class="ttl"><b class="doc"></b><span class="topic"></span></div>
      <div class="tools">
        <button class="tb" data-a="toc" title="İçindekiler (İ)">${ICON.toc}<span>İçindekiler</span></button>
        <button class="tb" data-a="wide" title="Genişliğe yay / ekrana sığdır (G)">${ICON.wide}<span class="wl">Genişliğe yay</span></button>
        <button class="tb" data-a="full" title="Tam ekran (F)"><i class="fi">${ICON.full}</i><span class="fl">Tam ekran</span></button>
      </div>
    </header>
    <div class="mid">
      <aside class="toc" aria-label="İçindekiler"><div class="toch">İçindekiler</div><ol></ol></aside>
      <main class="stage">
        <button class="nav prev" data-a="prev" aria-label="Önceki sayfa" title="Önceki sayfa (←)">${ICON.prev}</button>
        <div class="paper"><img alt=""><div class="load"><i></i><span></span></div></div>
        <button class="nav next" data-a="next" aria-label="Sonraki sayfa" title="Sonraki sayfa (→)">${ICON.next}</button>
      </main>
    </div>
    <footer class="bot">
      <span class="cnt"><b class="c"></b> / <span class="n"></span></span>
      <input type="range" class="scrub" min="1" max="1" value="1" aria-label="Sayfa">
      <span class="qs"></span>
      <span class="keys"><kbd>←</kbd> <kbd>→</kbd> sayfa · <kbd>Esc</kbd> kapat</span>
    </footer>`
}

// Sayfanın konusu: sayfası o konunun sayfaları arasında olan ilk konu; yoksa ilk sayfası bu sayfadan önce gelen son konu
function topicOf(toc, p) {
  let hit = toc.findIndex(t => t.pages.includes(p))
  if (hit < 0) toc.forEach((t, k) => { if (t.p <= p) hit = k })
  return hit
}

export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component
  const rd = parentElement.querySelector(".rd")
  if (!rd || !data) return
  if (!rd._s || rd._s.nonce !== data.nonce) {  // yeni açılış: durumu sıfırla
    build(rd)
    rd._s = { nonce: data.nonce, cache: {}, cur: data.cur, pin: data.topic ?? null, toc: false, wide: false, tocSig: "" }
    rd.focus()
  }
  const S = rd._s
  Object.assign(S.cache, data.img || {})
  const $ = (sel) => rd.querySelector(sel)
  const toc = data.toc || []

  if (S.tocSig !== JSON.stringify(toc)) {  // içindekiler bir kez çizilir
    S.tocSig = JSON.stringify(toc)
    $(".toc ol").innerHTML = toc.length ? toc.map((t, k) =>
      `<li tabindex="0" data-p="${t.p}" data-k="${k}"><span class="tn">${String(k + 1).padStart(2, "0")}</span><span class="tt">${esc(t.t)}</span>
       <span class="tp">${esc(t.pl)}${t.q ? ` · <b>${t.q} soru</b>` : ""}</span></li>`).join("")
      : '<li class="none">Bu notun konu haritası yok.</li>'
  }

  const render = (dir) => {
    const p = S.cur, n = data.n
    $(".doc").textContent = data.title
    // tıklanan konu (içindekiler ya da pencerenin Konular sekmesi) bu sayfayı kapsıyorsa o; yoksa sayfanın ilk konusu
    if (S.pin != null && !(toc[S.pin] && toc[S.pin].pages.includes(p))) S.pin = null
    const k = S.pin != null ? S.pin : topicOf(toc, p)
    $(".topic").innerHTML = k >= 0 ? `<i>${String(k + 1).padStart(2, "0")}</i> · ${esc(toc[k].t)}` : ""
    rd.querySelectorAll(".toc li[data-p]").forEach((li, j) => li.classList.toggle("on", j === k))
    $(".c").textContent = p
    $(".n").textContent = n
    const sc = $(".scrub")
    sc.max = n; sc.value = p
    sc.style.setProperty("--p", (n > 1 ? (p - 1) / (n - 1) * 100 : 100) + "%")
    const q = (data.qp || {})[p]
    $(".qs").innerHTML = q ? `Bu sayfadan <b>${q}</b> hazır soru` : ""
    $(".nav.prev").disabled = p <= 1
    $(".nav.next").disabled = p >= n
    const paper = $(".paper"), img = $(".paper img"), src = S.cache[p]
    $(".load span").textContent = `Sayfa ${p} hazırlanıyor`
    if (src) {
      paper.classList.remove("loading")
      if (img.dataset.p !== String(p)) {
        img.src = src
        img.dataset.p = String(p)
        img.alt = `Sayfa ${p}`
        if (dir && !matchMedia("(prefers-reduced-motion: reduce)").matches)
          img.animate([{ opacity: .25, transform: `translateX(${dir * 26}px)` }, { opacity: 1, transform: "none" }],
                      { duration: 230, easing: "cubic-bezier(.2,.8,.2,1)" })
        if (S.wide) $(".stage").scrollTop = 0
      }
    } else {
      paper.classList.add("loading")
    }
    rd.classList.toggle("toc-on", S.toc)
    rd.classList.toggle("wide", S.wide)
    $('[data-a="toc"]').classList.toggle("on", S.toc)
    $('[data-a="wide"]').classList.toggle("on", S.wide)
    $(".wl").textContent = S.wide ? "Ekrana sığdır" : "Genişliğe yay"
    const fs = !!document.fullscreenElement
    $('[data-a="full"]').classList.toggle("on", fs)
    $(".fi").innerHTML = fs ? ICON.unfull : ICON.full
    $(".fl").textContent = fs ? "Tam ekrandan çık" : "Tam ekran"
  }

  const go = (p) => {
    p = Math.max(1, Math.min(data.n, p))
    if (p === S.cur) return
    const dir = Math.sign(p - S.cur)
    S.cur = p
    render(dir)
    setStateValue("page", p)  // Python yeni komşu sayfaları gönderir (yalnızca okuyucu parçası yeniden çalışır)
  }
  const close = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    setTriggerValue("close", S.cur)
  }
  const fullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
    else rd.requestFullscreen().catch(() => {})
  }
  const act = (a) => {
    if (a === "close") close()
    else if (a === "prev") go(S.cur - 1)
    else if (a === "next") go(S.cur + 1)
    else if (a === "toc") { S.toc = !S.toc; render() }
    else if (a === "wide") { S.wide = !S.wide; render() }
    else if (a === "full") fullscreen()
  }

  rd.onclick = (e) => {
    const b = e.target.closest("[data-a]")
    if (b) return act(b.dataset.a)
    const li = e.target.closest("li[data-p]")
    if (li) { S.pin = Number(li.dataset.k); go(Number(li.dataset.p)); render() }
  }
  $(".scrub").oninput = (e) => go(Number(e.target.value))
  const onKey = (e) => {
    const t = e.composedPath()[0]
    if (t && t.classList && t.classList.contains("scrub") && e.key.startsWith("Arrow")) return  // kaydırıcı kendisi yapar
    if (t && t.tagName === "LI" && e.key === "Enter") { S.pin = Number(t.dataset.k); go(Number(t.dataset.p)); render(); e.preventDefault(); return }
    if (e.ctrlKey || e.metaKey || e.altKey) return
    const k = e.key
    if (k === "ArrowRight" || k === "PageDown" || (k === " " && !e.shiftKey)) go(S.cur + 1)
    else if (k === "ArrowLeft" || k === "PageUp" || (k === " " && e.shiftKey)) go(S.cur - 1)
    else if (k === "Home") go(1)
    else if (k === "End") go(data.n)
    else if (k === "Escape") close()
    else if (k === "f" || k === "F") fullscreen()
    else if ("iİIı".includes(k)) act("toc")
    else if (k === "g" || k === "G" || k === "ğ" || k === "Ğ") act("wide")
    else return
    e.preventDefault()
    e.stopPropagation()
  }
  if (rd._onkey) window.removeEventListener("keydown", rd._onkey, true)
  rd._onkey = onKey
  window.addEventListener("keydown", onKey, true)
  document.onfullscreenchange = () => render()

  // dokunmatik: yatay kaydırma sayfa çevirir
  const stage = $(".stage")
  stage.onpointerdown = (e) => { S.px = e.clientX; S.py = e.clientY }
  stage.onpointerup = (e) => {
    if (S.px == null) return
    const dx = e.clientX - S.px, dy = e.clientY - S.py
    S.px = null
    if (e.pointerType !== "mouse" && Math.abs(dx) > 60 && Math.abs(dy) < 60) go(S.cur + (dx < 0 ? 1 : -1))
  }

  render()
  return () => { window.removeEventListener("keydown", onKey, true); document.onfullscreenchange = null }
}
"""

_READER = Component("nr_reader", html=_HTML, css=_CSS, js=_JS)


# ---------------------------------------------------------------- sayfa görüntüleri ve içindekiler

@st.cache_data(max_entries=200, show_spinner=False)
def page_jpeg(file: str, page: int) -> bytes:
    """Sayfanın görüntüsü (JPEG; uzun kenarı LONG_EDGE). Not penceresi de aynısını kullanır."""
    with pymupdf.open(data.DOCS_DIR / file) as doc:
        pg = doc[page - 1]
        z = LONG_EDGE / max(pg.rect.width, pg.rect.height)
        return pg.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False).tobytes("jpg", jpg_quality=82)


def data_url(file: str, page: int) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(page_jpeg(file, page)).decode("ascii")


def pages_label(pages: list[int]) -> str:
    """[3] → 's. 3'; [6, 7] → 's. 6–7'; [3, 5, 6] → 's. 3, 5–6' (ardışık sayfalar aralık olarak)."""
    ps, out = sorted(set(pages)), []
    for p in ps:
        if out and p == out[-1][1] + 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return "s. " + ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in out) if out else ""


@st.cache_data(ttl=30, show_spinner=False)
def per_page(stem: str) -> dict[int, int]:
    """Sayfa → o sayfaya dayanan hazır soru sayısı (data.ready ile aynı süzgeç: doğrulanmış, reddedilmemiş, hatalı
    bildirilmemiş). Önbellekli: okuyucu her sayfa çevirişinde, pencere her sekmede çağırıyor."""
    blocked = R.blocked_ids()
    return dict(Counter(it["check"].get("evidence_page") for it in data.items().values()
                        if it["doc"] == stem and R.usable(it) and it["id"] not in blocked))


def toc(stem: str) -> list[dict]:
    """İçindekiler: notun konu haritası (yoksa bölüm başlıkları), her konunun ilk sayfası ve soru sayısı."""
    qp = per_page(stem)
    return [{"t": t["title"], "pages": sorted(t["pages"]), "p": min(t["pages"]), "pl": pages_label(t["pages"]),
             "q": sum(qp.get(p, 0) for p in set(t["pages"]))} for t in data.topics(stem) if t.get("pages")]


# ---------------------------------------------------------------- açma, gösterme

def open_reader(stem: str, page: int = 1, **back) -> None:
    """Okuyucuyu açar (sayfa baştan çalışınca görünür). back: kapanınca geri dönmek için saklanan bilgiler."""
    st.session_state.reader = {"doc": stem, "page": page, "nonce": time.time_ns(), **back}


def active() -> bool:
    return bool(st.session_state.get("reader"))


def show(on_close) -> None:
    """Açık okuyucuyu çizer. on_close(okuyucu durumu, son sayfa): kapatılınca (uygulama sonra baştan çalışır)."""
    _view(on_close)


@st.fragment
def _view(on_close) -> None:
    r = st.session_state.get("reader")
    if not r:
        return
    d = next((x for x in data.documents() if x["stem"] == r["doc"] and x["stem"] in data.visible()), None)
    if not d or not d["pages"]:
        st.session_state.pop("reader", None)
        st.rerun()
    key, n = f"nr_reader_{r['nonce']}", d["pages"]
    if (state := st.session_state.get(key)) and state.get("page"):  # JS'teki son sayfa (bu çalıştırmadan önce geldi)
        r["page"] = max(1, min(n, int(state["page"])))
    cur = r["page"]
    pages = [p for p in (cur, *(cur + k for k in AHEAD)) if 1 <= p <= n]
    qp = per_page(d["stem"])
    res = _READER(key=key, data={"nonce": r["nonce"], "title": data.short(d["stem"]), "n": n, "cur": cur,
                                 "img": {p: data_url(d["file"], p) for p in pages}, "toc": toc(d["stem"]),
                                 "qp": {p: c for p, c in qp.items() if p}, "topic": r.get("topic")},
                  default={"page": cur}, on_page_change=lambda: None, on_close_change=lambda: None)
    if res.close:
        st.session_state.pop("reader", None)
        on_close(r, max(1, min(n, int(res.close))))
        st.rerun()

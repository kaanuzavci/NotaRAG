"""Ana sayfanın kart desteleri (Streamlit özel bileşeni, CCv2): not rafı ve "kaldığın yerden devam et".

Her not bir deste gibi çizilir: üstte ders fişi görünümlü kart (renkli kapak, baş harf, ince satır çizgileri ve kenar
boşluğu çizgisi), arkasında çapraz duran yapraklar. Üzerine gelince üstteki kart kalkar, arkadakiler yelpaze gibi
açılır ve hızlı eylemler (Sınav, Kartlar) belirir. Destedeki yaprak sayısı notun soru sayısını kabaca gösterir.
Dokunmatik ekranda (üzerine gelme yok) eylemler hep görünür. "Hareketi azalt" tercihinde animasyon yok.

Neden özel bileşen? Streamlit düğmeleri kart biçiminde çizilemiyor; düz HTML ise tıklamayı Python'a iletemiyor
(bağlantı sayfayı yeniden yükler, oturum düşer). CCv2 bileşeni iframe'siz, Shadow DOM'da çizilir ve tıklamayı
setTriggerValue ile bir sonraki çalıştırmaya "doc|eylem" olarak verir. Görünüm verisi değişmedikçe yeniden çizmez
(üzerine gelme durumu ve giriş animasyonu her tıklamada sıfırlanmasın).
"""

from __future__ import annotations

import hashlib

import streamlit as st

from src.ui import style

_CSS = """
:host { display: block; }
.root { font-family: 'Instrument Sans', sans-serif; color: #1E2433; }

/* ---- raf: dikey kartlar ---- */
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(178px, 206px)); gap: 34px 30px;
  padding: 16px 16px 24px 12px; }
.stack { position: relative; aspect-ratio: 3 / 4.15; cursor: pointer; outline: none; border-radius: 18px;
  -webkit-tap-highlight-color: transparent; animation: rise .5s cubic-bezier(.2, .8, .2, 1) both;
  animation-delay: calc(var(--i) * 45ms); }
.sheet, .card { position: absolute; inset: 0; border-radius: 18px;
  transition: transform .34s cubic-bezier(.2, .8, .2, 1), box-shadow .34s, opacity .2s; }
.sheet { border: 1px solid rgba(30, 36, 51, .09); box-shadow: 0 8px 18px -16px rgba(30, 36, 51, .55); }
.s1 { background: var(--c2); transform: rotate(3.4deg) translate(5px, 4px); }
.s2 { background: var(--c1); transform: rotate(-4.4deg) translate(-6px, 6px); }
.card { background: #FFFDF8; border: 1px solid #E4DCC9; overflow: hidden; display: flex; flex-direction: column;
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 18px 34px -26px rgba(30, 36, 51, .6); }
.stack:hover .card, .stack:focus-visible .card { transform: translateY(-8px) rotate(-.8deg);
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 30px 42px -28px rgba(30, 36, 51, .65); }
.stack:hover .s1, .stack:focus-visible .s1 { transform: rotate(8deg) translate(15px, 1px); }
.stack:hover .s2, .stack:focus-visible .s2 { transform: rotate(-9deg) translate(-16px, 6px); }
.stack:focus-visible .card { outline: 2px solid #1F3A5F; outline-offset: 3px; }

.cover { position: relative; height: 41%; background: var(--c1); overflow: hidden; flex: none; }
.cover::after { content: ""; position: absolute; inset: 0;
  background-image: repeating-linear-gradient(135deg, transparent 0 11px, rgba(255, 255, 255, .32) 11px 12px); }
.mono { position: absolute; left: 16px; bottom: 8px; z-index: 1; font: 600 62px/.8 'Fraunces', serif;
  color: var(--a); letter-spacing: -.02em; }
.badge { position: absolute; top: 10px; right: 10px; z-index: 2; display: inline-flex; align-items: center; gap: 5px;
  font: 500 .6rem/1 'JetBrains Mono', monospace; letter-spacing: .09em; text-transform: uppercase; padding: 5px 8px;
  border-radius: 999px; background: rgba(255, 253, 248, .9); color: var(--ink); }
.badge svg { width: 11px; height: 11px; }
.body { position: relative; flex: 1; min-height: 0; padding: 15px 14px 12px 23px; display: flex; flex-direction: column;
  gap: 6px; background-image:
    linear-gradient(to right, transparent 13px, rgba(219, 39, 119, .22) 13px 14px, transparent 14px),
    repeating-linear-gradient(to bottom, transparent 0 21px, rgba(58, 123, 184, .11) 21px 22px);
  background-position: 0 3px; }
.title { flex: none; font: 600 1rem/1.27 'Fraunces', serif; color: #1E2433; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.meta, .lines { flex: none; }
.meta { font: 500 .6rem/1.4 'JetBrains Mono', monospace; letter-spacing: .1em; text-transform: uppercase; color: #7A6F57; }
.lines { max-height: 44px; overflow: hidden; margin-top: 2px; }  /* en çok iki tam satır: yarım satır görünmesin */
.lines div { font-size: .74rem; line-height: 22px; color: #4A5163; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.lines div::before { content: "– "; color: #B6A98C; }
.foot { margin-top: auto; padding-top: 4px; transition: opacity .18s; }
.bar { height: 4px; border-radius: 4px; background: #EFE8D8; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 4px; background: var(--a); }
.bar.live i { background-image: linear-gradient(90deg, var(--a) 0%, #FFFFFF99 50%, var(--a) 100%);
  background-size: 200% 100%; animation: shimmer 1.6s linear infinite; }
.pl { display: flex; justify-content: space-between; gap: 6px; margin-top: 6px; font-size: .72rem; color: #5B5F6B; }
.pl b { color: #1E2433; font-weight: 600; }
.actions { position: absolute; left: 11px; right: 11px; bottom: 11px; display: flex; gap: 6px; opacity: 0;
  transform: translateY(8px); transition: opacity .2s, transform .24s cubic-bezier(.2, .8, .2, 1); }
.stack:hover .actions, .stack:focus-within .actions { opacity: 1; transform: none; }
.stack:hover .foot, .stack:focus-within .foot { opacity: 0; }
.actions button { flex: 1; font: 600 .76rem/1 'Instrument Sans', sans-serif; border: 1px solid #1E2433; border-radius: 10px;
  padding: 9px 6px; background: #1E2433; color: #FFFDF8; cursor: pointer; transition: background .15s, transform .15s; }
.actions button:hover { background: #2B3550; transform: translateY(-1px); }
.actions button.alt { background: #FFFDF8; color: #1E2433; border-color: #D3C9B3; }
.actions button.alt:hover { background: #F4EFE3; }
.actions button:focus-visible { outline: 2px solid #1F3A5F; outline-offset: 2px; }

/* yeni not */
.stack.new .card { background: rgba(255, 253, 248, .45); border: 1.5px dashed #C3B79D; box-shadow: none;
  align-items: center; justify-content: center; text-align: center; gap: 13px; padding: 18px; }
.stack.new:hover .card, .stack.new:focus-visible .card { transform: translateY(-5px); border-color: #1F3A5F;
  background: rgba(255, 253, 248, .85); box-shadow: 0 22px 36px -30px rgba(30, 36, 51, .6); }
.plus { width: 58px; height: 58px; border-radius: 50%; background: #1E2433; color: #FFFDF8; display: grid; place-items: center;
  transition: transform .34s cubic-bezier(.2, .8, .2, 1); box-shadow: 0 10px 22px -12px rgba(30, 36, 51, .7); }
.plus svg { width: 26px; height: 26px; }
.stack.new:hover .plus, .stack.new:focus-visible .plus { transform: rotate(90deg) scale(1.04); }
.nt { font: 600 1.06rem/1.2 'Fraunces', serif; }
.ns { font-size: .78rem; line-height: 1.45; color: #6B6F7B; max-width: 150px; }

/* ---- kaldığın yerden devam et ---- */
.rgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 22px; padding: 8px 6px 18px; }
.rcard { position: relative; display: flex; align-items: center; gap: 22px; min-height: 148px; padding: 20px 22px;
  border-radius: 20px; background: #FFFDF8; border: 1px solid #E4DCC9; cursor: pointer; outline: none;
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 18px 34px -28px rgba(30, 36, 51, .6);
  transition: transform .28s cubic-bezier(.2, .8, .2, 1), box-shadow .28s, border-color .2s;
  animation: rise .5s cubic-bezier(.2, .8, .2, 1) both; animation-delay: calc(var(--i) * 60ms); }
.rcard:hover, .rcard:focus-visible { transform: translateY(-4px); border-color: #CFC4AC;
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 26px 40px -28px rgba(30, 36, 51, .65); }
.rcard:focus-visible { outline: 2px solid #1F3A5F; outline-offset: 3px; }
.rcard.empty { background: transparent; border-style: dashed; box-shadow: none; }
.rcard.empty .illu { opacity: .55; filter: saturate(.5); }
.rtext { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.kick { font: 500 .62rem/1 'JetBrains Mono', monospace; letter-spacing: .14em; text-transform: uppercase; color: #8A7E63; }
.rtitle { font: 600 1.12rem/1.28 'Fraunces', serif; color: #1E2433; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.rmeta { font-size: .8rem; color: #5B5F6B; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rprog { display: flex; align-items: center; gap: 10px; margin-top: 6px; font-size: .76rem; color: #5B5F6B; }
.rprog .bar { flex: 1; height: 6px; }
.rprog b { color: #1E2433; font-weight: 600; white-space: nowrap; }
.cta { align-self: flex-end; display: inline-flex; align-items: center; gap: 6px; padding: 9px 14px; border-radius: 999px;
  background: #1E2433; color: #FFFDF8; font: 600 .78rem/1 'Instrument Sans', sans-serif; white-space: nowrap;
  transition: gap .2s, background .15s; }
.rcard:hover .cta { gap: 10px; background: #2B3550; }
.rcard.empty .cta { background: transparent; color: #1E2433; border: 1px solid #CFC4AC; }
.cta svg { width: 14px; height: 14px; }

/* küçük çizimler: deste ve sınav kâğıdı */
.illu { position: relative; width: 74px; height: 92px; flex: none; }
.illu i { position: absolute; inset: 6px 8px; border-radius: 9px; border: 1px solid rgba(30, 36, 51, .1); }
.illu.cards i:nth-child(1) { background: #DDD6FE; transform: rotate(-9deg) translate(-5px, 3px); }
.illu.cards i:nth-child(2) { background: #99F6E4; transform: rotate(6deg) translate(5px, 2px); }
.illu.cards i:nth-child(3) { background: #FFFDF8;
  background-image: repeating-linear-gradient(to bottom, transparent 0 9px, rgba(58, 123, 184, .16) 9px 10px); }
.illu.exam i:nth-child(1) { background: #FED7AA; transform: rotate(-5deg) translate(-4px, 4px); }
.illu.exam i:nth-child(2) { background: #FFFDF8; transform: rotate(3deg);
  background-image: radial-gradient(circle at 12px 18px, #1E2433 2.2px, transparent 2.6px),
    radial-gradient(circle at 12px 36px, #1E2433 2.2px, transparent 2.6px),
    radial-gradient(circle at 12px 54px, #CFC4AC 2.2px, transparent 2.6px),
    linear-gradient(#E4DCC9, #E4DCC9), linear-gradient(#E4DCC9, #E4DCC9), linear-gradient(#EFE8D8, #EFE8D8);
  background-size: auto, auto, auto, 30px 3px, 26px 3px, 28px 3px;
  background-position: 0 0, 0 0, 0 0, 22px 17px, 22px 35px, 22px 53px; background-repeat: no-repeat; }
.illu.exam i:nth-child(3) { display: none; }

.empty-note { padding: 18px 6px; color: #6B6F7B; font-size: .9rem; }

@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
@media (hover: none) {
  .actions { opacity: 1; transform: none; }
  .foot { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .stack, .rcard { animation: none; }
  .sheet, .card, .actions, .rcard, .plus { transition: none; }
  .bar.live i { animation: none; }
}
"""

_HTML = """
<div class="root"></div>
"""

# Simgeler (Material Symbols'ün sade karşılıkları, satır içi SVG: bileşen kendi kabuğunda yazı tipi yüklemesin)
_JS = """
const ICON = {
  lock: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 22q-.8 0-1.4-.6T4 20V10q0-.8.6-1.4T6 8h1V6q0-2.1 1.5-3.5T12 1q2.1 0 3.5 1.5T17 6v2h1q.8 0 1.4.6T20 10v10q0 .8-.6 1.4T18 22Zm3-14h6V6q0-1.3-.9-2.1T12 3q-1.3 0-2.1.9T9 6Z"/></svg>',
  globe: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 22q-2.1 0-3.9-.8t-3.2-2.1q-1.4-1.4-2.1-3.2T2 12q0-2.1.8-3.9t2.1-3.2Q6.3 3.5 8.1 2.8T12 2q2.1 0 3.9.8t3.2 2.1q1.4 1.4 2.1 3.2T22 12q0 2.1-.8 3.9t-2.1 3.2q-1.4 1.4-3.2 2.1T12 22Zm-1-2.1V18q-.8 0-1.4-.6T9 16v-1l-4.8-4.8q-.1.5-.1.9V12q0 3 2 5.3t4.9 2.6Zm6.9-2.5q1-1.1 1.6-2.5T20 12q0-2.5-1.4-4.5T15 4.6V5q0 .8-.6 1.4T13 7h-2v2q0 .4-.3.7T10 10H8v2h6q.4 0 .7.3t.3.7v3h1q.7 0 1.2.4t.7 1Z"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M11 13H5v-2h6V5h2v6h6v2h-6v6h-2Z"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16.2 13H4v-2h12.2l-5.6-5.6L12 4l8 8-8 8-1.4-1.4Z"/></svg>',
  sync: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 20v-2h2.7l-.4-.3q-1.3-1.2-1.8-2.6T4 12.2q0-2.8 1.7-4.9T10 4.4v2.1Q8.2 7 7.1 8.6T6 12.2q0 1.1.4 2.2t1.3 1.9l.3.3V14h2v6Zm10-.3v-2.2q1.8-.5 2.9-2.1t1.1-3.6q0-1.1-.4-2.2t-1.3-1.9l-.3-.3V10h-2V4h6v2h-2.7l.4.3q1.2 1.2 1.8 2.6t.5 2.9q0 2.8-1.7 4.9T14 19.7Z"/></svg>'
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]))
}

function colors(it) {
  const p = it.palette || ["#EDE9FE", "#DDD6FE", "#2E1065", "#7C3AED"]
  return `--c1:${p[0]};--c2:${p[1]};--ink:${p[2]};--a:${p[3]}`
}

function stackCard(it, i) {
  if (it.kind === "new") {
    return `<div class="stack new" role="button" tabindex="0" data-id="${esc(it.id)}" data-default="open" style="--i:${i}">
      <div class="card"><div class="plus">${ICON.plus}</div><div class="nt">${esc(it.title)}</div>
      <div class="ns">${esc(it.sub)}</div></div></div>`
  }
  const sheets = (it.sheets >= 2 ? '<span class="sheet s2"></span>' : "") + (it.sheets >= 1 ? '<span class="sheet s1"></span>' : "")
  const badge = it.badge ? `<span class="badge">${ICON[it.badge_icon] || ""}${esc(it.badge)}</span>` : ""
  const bar = it.progress == null ? "" :
    `<div class="bar${it.live ? " live" : ""}"><i style="width:${Math.max(3, Math.round(it.progress * 100))}%"></i></div>`
  const pl = it.plabel ? `<div class="pl"><span>${esc(it.plabel)}</span><b>${esc(it.pvalue || "")}</b></div>` : ""
  const acts = (it.actions || []).map((a, k) =>
    `<button type="button" class="${k ? "alt" : ""}" data-act="${esc(a.id)}">${esc(a.label)}</button>`).join("")
  const mono = esc(String(it.title || "?").trim().charAt(0).toLocaleUpperCase("tr"))
  return `<div class="stack" role="button" tabindex="0" aria-label="${esc(it.title)}" data-id="${esc(it.id)}"
      data-default="open" style="--i:${i};${colors(it)}">${sheets}
    <div class="card"><div class="cover">${badge}<span class="mono">${mono}</span></div>
      <div class="body"><div class="title">${esc(it.title)}</div><div class="meta">${esc(it.meta)}</div>
        <div class="lines">${(it.lines || []).map(l => `<div>${esc(l)}</div>`).join("")}</div>
        <div class="foot">${bar}${pl}</div>
        ${acts ? `<div class="actions">${acts}</div>` : ""}</div></div></div>`
}

function resumeCard(it, i) {
  const bar = it.progress == null ? "" :
    `<div class="rprog"><div class="bar"><i style="width:${Math.max(3, Math.round(it.progress * 100))}%"></i></div><b>${esc(it.pvalue)}</b></div>`
  return `<div class="rcard${it.empty ? " empty" : ""}" role="button" tabindex="0" data-id="${esc(it.id)}"
      data-default="open" style="--i:${i};${colors(it)}">
    <div class="illu ${esc(it.illu)}"><i></i><i></i><i></i></div>
    <div class="rtext"><div class="kick">${esc(it.kicker)}</div><div class="rtitle">${esc(it.title)}</div>
      <div class="rmeta">${esc(it.meta)}</div>${bar}</div>
    <span class="cta">${esc(it.cta)}${ICON.arrow}</span></div>`
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root = parentElement.querySelector(".root")
  if (!root) return
  const sig = JSON.stringify(data)
  if (root.dataset.sig !== sig) {  // görünüm değişmediyse yeniden çizme (üzerine gelme ve animasyon sıfırlanmasın)
    root.dataset.sig = sig
    const items = (data && data.items) || []
    if (!items.length) {
      root.innerHTML = `<div class="empty-note">${esc(data.empty || "")}</div>`
    } else if (data.layout === "resume") {
      root.innerHTML = `<div class="rgrid">${items.map(resumeCard).join("")}</div>`
    } else {
      root.innerHTML = `<div class="grid">${items.map(stackCard).join("")}</div>`
    }
  }
  const fire = (target) => {
    const card = target.closest("[data-id]")
    if (!card) return
    const btn = target.closest("[data-act]")
    setTriggerValue("action", card.dataset.id + "|" + (btn ? btn.dataset.act : card.dataset.default))
  }
  root.onclick = (e) => fire(e.target)
  root.onkeydown = (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-id], [data-act]")) {
      e.preventDefault()
      fire(e.target)
    }
  }
}
"""

_NAME = "nr_shelf"
_SHELF = st.components.v2.component(_NAME, html=_HTML, css=_CSS, js=_JS)


def _component():
    """Bileşen kaydı çalışma ortamına (Runtime) bağlı; modül bir kez yüklendiği hâlde ortam yeniden kurulursa (test
    aracı AppTest, Streamlit'in yeniden başlaması) kayıt yoksa yeniden kaydedilir."""
    global _SHELF
    from streamlit.runtime import Runtime
    if Runtime.exists() and Runtime.instance().bidi_component_registry.get(_NAME) is None:
        _SHELF = st.components.v2.component(_NAME, html=_HTML, css=_CSS, js=_JS)
    return _SHELF


def palette(key: str, order: int | None = None) -> list[str]:
    """Belgenin rengi. order: belgenin kütüphaneye giriş sırası (değişmez) → ardışık notlar farklı renk alır ve rengi
    süzme/sıralamayla değişmez (renk varlığı izler, ekrandaki sırayı değil). Sıra yoksa kimliğin özetinden."""
    i = order if order is not None else int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
    return list(style.color(i % len(style.PALETTE)))


def shelf(items: list[dict], *, key: str, layout: str = "grid", empty: str = "") -> tuple[str, str] | None:
    """Kartları çizer; tıklanan kart ve eylem → (kimlik, eylem) ya da None. Eylem: kartın kendisi 'open', düğmeler
    kendi kimliği (ör. 'exam', 'cards', 'add')."""
    res = _component()(key=key, data={"items": items, "layout": layout, "empty": empty}, on_action_change=lambda: None)
    act = getattr(res, "action", None)
    if not act or "|" not in act:
        return None
    ident, _, action = act.rpartition("|")
    return ident, action

"""Not desteleri (Streamlit özel bileşeni, CCv2): ana sayfadaki raflar, Belgeler ızgarası ve "kaldığın yerden devam et".

Her not bir deste gibi çizilir: üstte ders fişi görünümlü kart (renkli kapak, baş harf, ince satır çizgileri ve kenar
boşluğu çizgisi), arkasında çapraz duran yapraklar. Üzerine gelince üstteki kart kalkar, arkadakiler yelpaze gibi
açılır ve hızlı eylemler (Sınav, Kartlar) belirir. Destedeki yaprak sayısı notun soru sayısını kabaca gösterir.
Dokunmatik ekranda (üzerine gelme yok) eylemler hep görünür. "Hareketi azalt" tercihinde animasyon yok.

Sütun sayısı bileşenin genişliğinden (JS, en çok 4; kart ~230-300 px). rows verilirse raf en çok o kadar satır olur
ve son yer "Tümünü gör" kartıdır (all_card): ana sayfa sonsuza uzamaz, bütün notlar Belgeler sayfasında. Genişlik
değişince (kenar çubuğu açılıp kapanınca) yeniden dizilir.

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

/* ---- raf: dikey kartlar; sütun sayısı JS'ten (--cols), kart genişliği ~230-300 px ---- */
.grid { display: grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr)); gap: 34px 28px;
  padding: 16px 16px 26px 12px; }
.stack { position: relative; aspect-ratio: 3 / 4; container-type: inline-size; cursor: pointer; outline: none;
  border-radius: 20px; -webkit-tap-highlight-color: transparent; animation: rise .5s cubic-bezier(.2, .8, .2, 1) both;
  animation-delay: calc(var(--i) * 45ms); }
.still .stack { animation: none; }  /* yeniden dizilince (genişlik, ilerleme) giriş animasyonu tekrar oynamasın */
.sheet, .card { position: absolute; inset: 0; border-radius: 20px;
  transition: transform .34s cubic-bezier(.2, .8, .2, 1), box-shadow .34s, opacity .2s, border-color .2s, background .2s; }
.sheet { border: 1px solid rgba(30, 36, 51, .09); box-shadow: 0 8px 18px -16px rgba(30, 36, 51, .55); }
.s1 { background: var(--c2); transform: rotate(3deg) translate(6px, 4px); }
.s2 { background: var(--c1); transform: rotate(-3.8deg) translate(-7px, 7px); }
.card { background: #FFFDF8; border: 1px solid #E4DCC9; overflow: hidden; display: flex; flex-direction: column;
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 20px 36px -26px rgba(30, 36, 51, .6); }
.stack:hover .card, .stack:focus-visible .card { transform: translateY(-9px) rotate(-.7deg);
  box-shadow: 0 1px 0 rgba(30, 36, 51, .05), 0 34px 46px -28px rgba(30, 36, 51, .65); }
.stack:hover .s1, .stack:focus-visible .s1 { transform: rotate(7.5deg) translate(18px, 1px); }
.stack:hover .s2, .stack:focus-visible .s2 { transform: rotate(-8.5deg) translate(-19px, 7px); }
.stack:focus-visible .card { outline: 2px solid #1F3A5F; outline-offset: 3px; }

.cover { position: relative; height: 37%; background: var(--c1); overflow: hidden; flex: none; }
.cover::after { content: ""; position: absolute; inset: 0;
  background-image: repeating-linear-gradient(135deg, transparent 0 12px, rgba(255, 255, 255, .32) 12px 13px); }
.mono { position: absolute; left: 18px; bottom: 6px; z-index: 1; font: 600 clamp(58px, 29cqi, 88px)/.8 'Fraunces', serif;
  color: var(--a); letter-spacing: -.02em; }
.badge { position: absolute; top: 12px; right: 12px; z-index: 2; display: inline-flex; align-items: center; gap: 5px;
  font: 500 .62rem/1 'JetBrains Mono', monospace; letter-spacing: .09em; text-transform: uppercase; padding: 6px 9px;
  border-radius: 999px; background: rgba(255, 253, 248, .92); color: var(--ink); }
.badge svg { width: 12px; height: 12px; }
.body { position: relative; flex: 1; min-height: 0; padding: 16px 16px 14px 27px; display: flex; flex-direction: column;
  gap: 7px; background-image:
    linear-gradient(to right, transparent 15px, rgba(219, 39, 119, .22) 15px 16px, transparent 16px),
    repeating-linear-gradient(to bottom, transparent 0 23px, rgba(58, 123, 184, .11) 23px 24px);
  background-position: 0 4px; }
.title { flex: none; font: 600 clamp(1.04rem, 6.8cqi, 1.26rem)/1.25 'Fraunces', serif; color: #1E2433;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.meta, .lines { flex: none; }
.meta { font: 500 .62rem/1.4 'JetBrains Mono', monospace; letter-spacing: .1em; text-transform: uppercase; color: #7A6F57; }
.lines { max-height: 72px; overflow: hidden; margin-top: 1px; }  /* en çok üç tam satır: yarım satır görünmesin */
.lines div { font-size: .8rem; line-height: 24px; color: #4A5163; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.lines div::before { content: "– "; color: #B6A98C; }
.foot { margin-top: auto; padding-top: 4px; transition: opacity .18s; }
.bar { height: 5px; border-radius: 5px; background: #EFE8D8; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 5px; background: var(--a); }
.bar.live i { background-image: linear-gradient(90deg, var(--a) 0%, #FFFFFF99 50%, var(--a) 100%);
  background-size: 200% 100%; animation: shimmer 1.6s linear infinite; }
.pl { display: flex; justify-content: space-between; gap: 6px; margin-top: 7px; font-size: .78rem; color: #5B5F6B; }
.pl b { color: #1E2433; font-weight: 600; }
.actions { position: absolute; left: 14px; right: 14px; bottom: 14px; display: flex; gap: 7px; opacity: 0;
  transform: translateY(8px); transition: opacity .2s, transform .24s cubic-bezier(.2, .8, .2, 1); }
.stack:hover .actions, .stack:focus-within .actions { opacity: 1; transform: none; }
.stack:hover .foot, .stack:focus-within .foot { opacity: 0; }
.actions button { flex: 1; font: 600 .82rem/1 'Instrument Sans', sans-serif; border: 1px solid #1E2433; border-radius: 11px;
  padding: 11px 6px; background: #1E2433; color: #FFFDF8; cursor: pointer; transition: background .15s, transform .15s; }
.actions button:hover { background: #2B3550; transform: translateY(-1px); }
.actions button.alt { background: #FFFDF8; color: #1E2433; border-color: #D3C9B3; }
.actions button.alt:hover { background: #F4EFE3; }
.actions button:focus-visible { outline: 2px solid #1F3A5F; outline-offset: 2px; }

/* yeni not */
.stack.new .card { background: rgba(255, 253, 248, .45); border: 1.5px dashed #C3B79D; box-shadow: none;
  align-items: center; justify-content: center; text-align: center; gap: 14px; padding: 22px; }
.stack.new:hover .card, .stack.new:focus-visible .card { transform: translateY(-5px); border-color: #1F3A5F;
  background: rgba(255, 253, 248, .85); box-shadow: 0 22px 36px -30px rgba(30, 36, 51, .6); }
.plus { width: 64px; height: 64px; border-radius: 50%; background: #1E2433; color: #FFFDF8; display: grid; place-items: center;
  transition: transform .34s cubic-bezier(.2, .8, .2, 1); box-shadow: 0 10px 22px -12px rgba(30, 36, 51, .7); }
.plus svg { width: 28px; height: 28px; }
.stack.new:hover .plus, .stack.new:focus-visible .plus { transform: rotate(90deg) scale(1.04); }
.nt { font: 600 1.16rem/1.2 'Fraunces', serif; }
.ns { font-size: .82rem; line-height: 1.5; color: #6B6F7B; max-width: 190px; }

/* tümünü gör: küçük kartlardan bir yelpaze (notların renkleri); üzerine gelince açılır */
.stack.all .card { align-items: center; justify-content: center; text-align: center; gap: 12px; padding: 22px;
  background: #FFFDF8; }
.stack.all:hover .card, .stack.all:focus-visible .card { transform: translateY(-5px); border-color: #CFC4AC; }
.fan { position: relative; width: 150px; height: 112px; margin-bottom: 6px; }
.fan i { position: absolute; left: 50%; top: 10px; width: 62px; height: 84px; margin-left: -31px; border-radius: 10px;
  border: 1px solid rgba(30, 36, 51, .1); background: linear-gradient(var(--c) 0 42%, #FFFDF8 42%);
  box-shadow: 0 8px 16px -12px rgba(30, 36, 51, .7); transform-origin: 50% 130%;
  transform: translateX(calc((var(--k) - var(--m)) * 15px)) rotate(calc((var(--k) - var(--m)) * 9deg));
  transition: transform .34s cubic-bezier(.2, .8, .2, 1); }
.fan i::after { content: ""; position: absolute; left: 9px; right: 9px; top: 46px; height: 3px; border-radius: 2px;
  background: #E4DCC9; box-shadow: 0 9px 0 #EFE8D8, 0 18px 0 #EFE8D8; }
.stack.all:hover .fan i, .stack.all:focus-visible .fan i {
  transform: translateX(calc((var(--k) - var(--m)) * 24px)) translateY(-4px) rotate(calc((var(--k) - var(--m)) * 14deg)); }
.go { width: 42px; height: 42px; border-radius: 50%; background: #1E2433; color: #FFFDF8; display: grid; place-items: center;
  margin-top: 4px; transition: transform .25s cubic-bezier(.2, .8, .2, 1), background .15s; }
.go svg { width: 20px; height: 20px; }
.stack.all:hover .go, .stack.all:focus-visible .go { transform: translateX(5px); background: #2B3550; }

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

/* ---- sayfalı görünüm (Belgeler): ekranda 2 satır × 4 kart, oklarla yana kayar; kart boyu ekrana sığacak kadar (JS) ---- */
.car { position: relative; }
.vp { overflow: hidden; touch-action: pan-y; }
.track { display: flex; transition: transform .5s cubic-bezier(.2, .8, .2, 1); }
.pg { flex: 0 0 100%; box-sizing: border-box; display: grid; grid-template-columns: repeat(var(--cols, 4), var(--cw, 230px));
  grid-template-rows: repeat(2, calc(var(--cw, 230px) * 4 / 3)); gap: 30px 24px; padding: 14px 20px 22px; align-content: start; }
.cnav { position: absolute; z-index: 5; width: 50px; height: 50px; border-radius: 50%; border: 1px solid #D3C9B3;
  background: #FFFDF8; color: #1E2433; display: grid; place-items: center; cursor: pointer; transform: translate(-50%, -50%);
  box-shadow: 0 10px 24px -12px rgba(30, 36, 51, .55); transition: background .15s, color .15s, border-color .15s, transform .2s; }
.cnav svg { width: 24px; height: 24px; }
.cnav:hover { background: #1E2433; color: #FFFDF8; border-color: #1E2433; }
.cnav.next:hover { transform: translate(-50%, -50%) translateX(3px); }
.cnav.prev:hover { transform: translate(-50%, -50%) translateX(-3px); }
.cnav:focus-visible { outline: 2px solid #1F3A5F; outline-offset: 3px; }
.cnav[hidden] { display: none; }
.dots { display: flex; align-items: center; justify-content: center; gap: 8px; height: 26px; }
.dots button { width: 8px; height: 8px; border-radius: 4px; border: 0; padding: 0; background: #D8CFBB; cursor: pointer;
  transition: width .25s, background .2s; }
.dots button.on { width: 22px; background: #1E2433; }
.dots span { font: 500 .72rem 'JetBrains Mono', monospace; color: #8A7E63; margin-left: 6px; }

/* ---- kaydırmalı görünüm (Belgeler): satırlar sayfa kaydıkça birer birer gelir ---- */
.sentinel { height: 1px; }
.stack.q { animation: none; }  /* veri yenilenince (işlenen notun ilerlemesi) görünen kartlar yeniden belirmesin */

/* Küçük kart (kısa ekranda sayfalı görünüm): konu satırları gizlenir, yazılar küçülür */
@container (max-width: 205px) {
  .lines { display: none; }
  .body { padding: 12px 12px 10px 23px; gap: 5px; }
  .title { font-size: .98rem; }
  .badge { font-size: .54rem; padding: 4px 7px; top: 9px; right: 9px; }
  .pl { font-size: .72rem; }
  .actions { left: 10px; right: 10px; bottom: 10px; gap: 5px; }
  .actions button { font-size: .74rem; padding: 9px 4px; }
  .plus { width: 50px; height: 50px; } .nt { font-size: 1.02rem; } .ns { font-size: .74rem; }
}

@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
@media (hover: none) {
  .actions { opacity: 1; transform: none; }
  .foot { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .stack, .rcard { animation: none; }
  .sheet, .card, .actions, .rcard, .plus, .fan i, .go, .track, .cnav { transition: none; }
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
  back: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7.8 13l5.6 5.6L12 20l-8-8 8-8 1.4 1.4L7.8 11H20v2Z"/></svg>',
  sync: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 20v-2h2.7l-.4-.3q-1.3-1.2-1.8-2.6T4 12.2q0-2.8 1.7-4.9T10 4.4v2.1Q8.2 7 7.1 8.6T6 12.2q0 1.1.4 2.2t1.3 1.9l.3.3V14h2v6Zm10-.3v-2.2q1.8-.5 2.9-2.1t1.1-3.6q0-1.1-.4-2.2t-1.3-1.9l-.3-.3V10h-2V4h6v2h-2.7l.4.3q1.2 1.2 1.8 2.6t.5 2.9q0 2.8-1.7 4.9T14 19.7Z"/></svg>'
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]))
}

function colors(it) {
  const p = it.palette || ["#EDE9FE", "#DDD6FE", "#2E1065", "#7C3AED"]
  return `--c1:${p[0]};--c2:${p[1]};--ink:${p[2]};--a:${p[3]}`
}

// Sütun: kart en az ~228 px + 28 px aralık; en çok 4 (geniş ekranda kart büyür, küçülmez). Genişlik henüz yoksa 4.
const COL = 256
function colsFor(w) { return w ? Math.max(1, Math.min(4, Math.floor(w / COL))) : 4 }

function stackCard(it, i) {
  if (it.kind === "new") {
    return `<div class="stack new" role="button" tabindex="0" data-id="${esc(it.id)}" data-default="open" style="--i:${i}">
      <div class="card"><div class="plus">${ICON.plus}</div><div class="nt">${esc(it.title)}</div>
      <div class="ns">${esc(it.sub)}</div></div></div>`
  }
  if (it.kind === "all") {
    const ps = (it.palettes || []).slice(0, 4)
    const fan = ps.map((p, k) => `<i style="--c:${p[1]};--k:${k}"></i>`).join("")
    return `<div class="stack all" role="button" tabindex="0" aria-label="${esc(it.title)}" data-id="${esc(it.id)}"
        data-default="open" style="--i:${i}">
      <div class="card"><div class="fan" style="--m:${(ps.length - 1) / 2}">${fan}</div><div class="nt">${esc(it.title)}</div>
      <div class="ns">${esc(it.sub)}</div><span class="go">${ICON.arrow}</span></div></div>`
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

// ---- sayfalı görünüm: 2 satır × 4 sütun; kart boyu genişliğe ve ekranın kalan yüksekliğine sığacak kadar (sayfa kaymaz)
const PG = { t: 14, r: 20, b: 22, l: 20, gx: 24, gy: 30, dots: 26, foot: 16 }

function pagesLayout(root) {
  const W = root.clientWidth
  const cols = W >= 700 ? 4 : 2
  const top = Math.max(0, root.getBoundingClientRect().top)
  const byH = ((innerHeight - top - PG.dots - PG.foot - PG.t - PG.b - PG.gy) / 2) * 0.75
  const byW = (W - PG.l - PG.r - (cols - 1) * PG.gx) / cols
  return { cols, cw: Math.floor(Math.max(120, Math.min(byW, byH))) }
}

function renderPages(root, items, cols) {
  const per = cols * 2, pages = []
  for (let i = 0; i < items.length; i += per) pages.push(items.slice(i, i + per))
  root.innerHTML = `<div class="car"><div class="vp"><div class="track">${pages.map((p, k) =>
      `<div class="pg">${p.map((it, j) => stackCard(it, k ? 0 : j)).join("")}</div>`).join("")}</div></div>
    <button type="button" class="cnav prev" data-nav="-1" aria-label="Önceki belgeler" title="Önceki belgeler (←)">${ICON.back}</button>
    <button type="button" class="cnav next" data-nav="1" aria-label="Sonraki belgeler" title="Sonraki belgeler (→)">${ICON.arrow}</button>
    <div class="dots">${pages.length > 1 ? pages.map((_, k) =>
      `<button type="button" data-pg="${k}" aria-label="${k + 1}. sayfa"></button>`).join("") + "<span></span>" : ""}</div></div>`
  return pages.length
}

function goPage(root, S, p) {
  S.page = Math.max(0, Math.min((S.pages || 1) - 1, p))
  const track = root.querySelector(".track")
  if (!track) return
  track.style.transform = `translateX(${-S.page * 100}%)`
  root.querySelector(".cnav.prev").hidden = S.page <= 0
  root.querySelector(".cnav.next").hidden = S.page >= S.pages - 1
  root.querySelectorAll(".dots button").forEach((b, k) => b.classList.toggle("on", k === S.page))
  const label = root.querySelector(".dots span")
  if (label) label.textContent = `${S.page + 1} / ${S.pages}`
}

function drawPages(root, S, items, data) {
  const L = pagesLayout(root)
  const ids = items.map(it => it.id).join("|")
  if (ids !== S.ids) { S.ids = ids; S.page = 0 }  // süzgeç ya da arama değişti: ilk sayfadan
  const sig = JSON.stringify(data) + "|" + L.cols
  if (root.dataset.sig !== sig) {
    root.classList.toggle("still", !!root.dataset.sig)
    root.dataset.sig = sig
    if (!items.length) { root.innerHTML = `<div class="empty-note">${esc(data.empty || "")}</div>`; return }
    S.pages = renderPages(root, items, L.cols)
  }
  if (!items.length) return
  root.style.setProperty("--cols", L.cols)
  root.style.setProperty("--cw", L.cw + "px")
  // oklar: 1. ve 2. satırın arasında, sağdaki (soldaki) iki kartın tam ortasında, ızgaranın kenarında
  const y = PG.t + L.cw * 4 / 3 + PG.gy / 2
  const next = root.querySelector(".cnav.next"), prev = root.querySelector(".cnav.prev")
  next.style.left = (PG.l + L.cols * L.cw + (L.cols - 1) * PG.gx) + "px"
  prev.style.left = PG.l + "px"
  next.style.top = prev.style.top = y + "px"
  goPage(root, S, S.page)
}

// ---- kaydırmalı görünüm: ekrana sığan satırlar hemen, kalanlar sayfa kaydıkça birer satır
function drawLazy(root, S, items, cols, quiet) {
  const keep = quiet ? S.shown || 0 : 0  // veri yenilendi (aynı kartlar): gösterilen satırlar sessizce yerinde kalsın
  root.innerHTML = `<div class="grid" style="--cols:${cols}"></div><div class="sentinel"></div>`
  const grid = root.querySelector(".grid"), sent = root.querySelector(".sentinel")
  S.shown = 0
  const addRow = () => {
    const next = items.slice(S.shown, S.shown + cols)
    grid.insertAdjacentHTML("beforeend", next.map((it, k) => stackCard(it, k)).join(""))
    S.shown += next.length
    return next.length
  }
  const fill = () => {
    while (S.shown < items.length && sent.getBoundingClientRect().top < innerHeight + 24) if (!addRow()) break
  }
  while (S.shown < keep) if (!addRow()) break
  if (quiet) grid.querySelectorAll(".stack").forEach(e => e.classList.add("q"))
  fill()
  if (S.io) S.io.disconnect()
  S.io = new IntersectionObserver((es) => { if (es.some(e => e.isIntersecting)) fill() }, { rootMargin: "0px 0px 24px 0px" })
  S.io.observe(sent)
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const root = parentElement.querySelector(".root")
  if (!root) return
  const S = root._s || (root._s = { page: 0, ids: "" })
  const draw = () => {
    const items = (data && data.items) || []
    if (data.layout === "pages") return drawPages(root, S, items, data)
    const grid = data.layout !== "resume"
    const cols = grid ? colsFor(root.clientWidth) : 0
    const sig = JSON.stringify(data) + "|" + cols
    if (root.dataset.sig === sig) return  // görünüm değişmediyse yeniden çizme (üzerine gelme ve animasyon sıfırlanmasın)
    const ids = items.map(it => it.id).join("|")
    const quiet = !!root.dataset.sig && ids === S.ids
    S.ids = ids
    root.classList.toggle("still", !!root.dataset.sig && !data.lazy)
    root.dataset.sig = sig
    if (!items.length) {
      root.innerHTML = `<div class="empty-note">${esc(data.empty || "")}</div>`
    } else if (!grid) {
      root.innerHTML = `<div class="rgrid">${items.map(resumeCard).join("")}</div>`
    } else if (data.lazy) {
      drawLazy(root, S, items, cols, quiet)
    } else {
      // rows: raf en çok bu kadar satır; son yer "Tümünü gör" (data.all). rows yoksa hepsi + (varsa) "Tümünü gör"
      const shown = data.all ? items.slice(0, data.rows ? data.rows * cols - 1 : items.length).concat([data.all]) : items
      root.innerHTML = `<div class="grid" style="--cols:${cols}">${shown.map(stackCard).join("")}</div>`
    }
  }
  root._draw = draw
  draw()
  if (!root._ro) {  // pencere daralınca sütun sayısı (sayfalı görünümde kart boyu da) değişir
    root._ro = new ResizeObserver(() => root._draw && root._draw())
    root._ro.observe(root)
  }
  const fire = (target) => {
    const card = target.closest("[data-id]")
    if (!card) return
    const btn = target.closest("[data-act]")
    setTriggerValue("action", card.dataset.id + "|" + (btn ? btn.dataset.act : card.dataset.default))
  }
  root.onclick = (e) => {
    const nav = e.target.closest("[data-nav]"), dot = e.target.closest("[data-pg]")
    if (nav) return goPage(root, S, S.page + Number(nav.dataset.nav))
    if (dot) return goPage(root, S, Number(dot.dataset.pg))
    fire(e.target)
  }
  root.onkeydown = (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-id], [data-act]")) {
      e.preventDefault()
      fire(e.target)
    }
  }
  if (root._off) { root._off(); root._off = null }
  if (data.layout !== "pages") return
  // sayfalı görünüm: ← → tuşları, yatay kaydırma (dokunmatik yüzey), parmakla kaydırma; ekran yüksekliği değişince kart boyu.
  // Dinleyiciler pencereye bağlı: bileşen sayfadan kalkınca (görünüm değişince) kendilerini çıkarırlar.
  const off = () => { removeEventListener("keydown", onKey); removeEventListener("resize", onResize) }
  const onKey = (e) => {
    if (!root.isConnected) return off()
    const t = e.composedPath()[0]
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return
    if (document.querySelector('[data-testid="stDialog"]') || e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === "ArrowRight") goPage(root, S, S.page + 1)
    else if (e.key === "ArrowLeft") goPage(root, S, S.page - 1)
  }
  const onResize = () => root.isConnected ? root._draw && root._draw() : off()
  addEventListener("keydown", onKey)
  addEventListener("resize", onResize)
  root._off = off
  setTimeout(onResize, 350)  // üstteki öğeler (yazı tipleri, süzgeç) yerleşince kalan yükseklik yeniden ölçülsün
  root.onwheel = (e) => {
    if (!e.target.closest(".vp") || Math.abs(e.deltaX) <= Math.abs(e.deltaY) || Math.abs(e.deltaX) < 25 || S.lock) return
    S.lock = true
    setTimeout(() => { S.lock = false }, 650)
    goPage(root, S, S.page + (e.deltaX > 0 ? 1 : -1))
  }
  root.onpointerdown = (e) => { S.px = e.clientX; S.py = e.clientY }
  root.onpointerup = (e) => {
    if (S.px == null) return
    const dx = e.clientX - S.px, dy = e.clientY - S.py
    S.px = null
    if (e.pointerType !== "mouse" && Math.abs(dx) > 60 && Math.abs(dy) < 60) goPage(root, S, S.page + (dx < 0 ? 1 : -1))
  }
  return off
}
"""

class Component:
    """CCv2 bileşeni (raf, okuyucu, konu listesi). Kayıt çalışma ortamına (Runtime) bağlı; modül bir kez yüklendiği
    hâlde ortam yeniden kurulursa (test aracı AppTest, Streamlit'in yeniden başlaması) kayıt yoksa yeniden kaydedilir
    (yoksa "not registered")."""

    def __init__(self, name: str, **spec) -> None:
        self.name, self.spec = name, spec
        self.mount = st.components.v2.component(name, **spec)

    def __call__(self, **kwargs):
        from streamlit.runtime import Runtime
        if Runtime.exists() and Runtime.instance().bidi_component_registry.get(self.name) is None:
            self.mount = st.components.v2.component(self.name, **self.spec)
        return self.mount(**kwargs)


_SHELF = Component("nr_shelf", html=_HTML, css=_CSS, js=_JS)


def palette(key: str, order: int | None = None) -> list[str]:
    """Belgenin rengi. order: belgenin kütüphaneye giriş sırası (değişmez) → ardışık notlar farklı renk alır ve rengi
    süzme/sıralamayla değişmez (renk varlığı izler, ekrandaki sırayı değil). Sıra yoksa kimliğin özetinden."""
    i = order if order is not None else int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
    return list(style.color(i % len(style.PALETTE)))


def all_card(palettes: list[list[str]], sub: str) -> dict:
    """Rafın son kartı: "Tümünü gör" (notların renklerinden küçük bir yelpaze). Tıklanınca kimliği 'all'."""
    return {"id": "all", "kind": "all", "title": "Tümünü gör", "sub": sub, "palettes": palettes[:4]}


def shelf(items: list[dict], *, key: str, layout: str = "grid", empty: str = "", rows: int | None = None,
          more: dict | None = None, lazy: bool = False) -> tuple[str, str] | None:
    """Kartları çizer; tıklanan kart ve eylem → (kimlik, eylem) ya da None. Eylem: kartın kendisi 'open', düğmeler
    kendi kimliği (ör. 'exam', 'cards', 'add').
    layout: 'grid' (raf) · 'pages' (sayfalı: 2 satır × 4, oklarla yana kayar, sayfa kaymaz) · 'resume' (kaldığın yer).
    rows + more (all_card): raf en çok rows satır, son yer "Tümünü gör". lazy: satırlar sayfa kaydıkça birer birer."""
    res = _SHELF(key=key, data={"items": items, "layout": layout, "empty": empty, "rows": rows, "all": more,
                                "lazy": lazy}, on_action_change=lambda: None)
    act = getattr(res, "action", None)
    if not act or "|" not in act:
        return None
    ident, _, action = act.rpartition("|")
    return ident, action

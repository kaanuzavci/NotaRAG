"""Bilgi kartı oturumu ekranı (Streamlit özel bileşeni, CCv2): src/ui/pages/cards.py'nin oturum ekranı.

Kullanıcı isteği (2026-10-12): eski ekran her geçişte kasıyordu, ilerleme çubuğu (emoji yüzler) yapmacık, düz parlak
zemin kalitesiz duruyordu, bazı düğmeler kartın üstüne biniyordu → ekran baştan yapıldı.

Neden özel bileşen? Eskiden her değerlendirmede bütün sayfa Streamlit'te baştan çalışıyor, sahne HTML'i sıfırdan
kuruluyordu (sunucuya gidip gelme + yeniden yerleşim); üstüne sürekli oynayan animasyonlar (alevin drop-shadow süzgeci,
kayan çizgiler, sallanan yüzler) her karede yeniden çizim yaptırıyordu. Şimdi bütün deste bir kez tarayıcıya gönderilir:
çevirme, sonraki karta geçiş, sürükleme, karıştırma tarayıcıda anında olur. Hareketler yalnızca transform ve opacity
(ekran kartında, ekranın yenileme hızında), sürekli dönen animasyon yok. Her değerlendirmeden sonra JS destenin durumunu
(sıra, değerlendirme günlüğü) setStateValue ile verir; Python yalnızca oturum parçasını (st.fragment) yeniden çalıştırıp
yeni satırları cards.jsonl'e yazar. Bileşen aynı oturum belirteci (tok) geldikçe yeniden çizmez.

Ekran (tam pencere, koyu sahne): üstte şerit (geri, destenin adı, bölmeli ilerleme, isabet halkası, seri, süre,
Karıştır, Bitir); ortada kart (önde soru, arkada cevap + çözüm + notundaki kaynak; tıkla ya da Boşluk); kartın altında
Bilemedim / Atla / Bildim ve her birinin sonucu ("bugün yine", "4 gün sonra": FSRS); solda "Bilemediklerin", sağda
"Bildiklerin" yığını (değerlendirilen kart kendi yığınına uçar; son kartların soruları altta). Kartı sola / sağa
sürüklemek de değerlendirir. Klavye: Boşluk / Enter çevir · ← 1 bilemedim · ↓ 2 atla · → 3 bildim · K karıştır.
Kaynak düğmesi (kartın köşesinde) notun kanıt sayfasını okuyucuda açar. "Hareketi azalt" tercihinde uçuş ve dönüş yok.
"""

from __future__ import annotations

from src.ui.shelf import Component

_CSS = """
:host { display: block; }
.fx { position: fixed; inset: 0; z-index: 1000100; display: grid; grid-template-rows: auto minmax(0, 1fr) auto;
  color: #ECEAF7; font-family: 'Instrument Sans', sans-serif; overflow: hidden; user-select: none;
  --ink: #ECEAF7; --sub: #A9AACB; --mute: #7D80A6; --line: rgba(255, 255, 255, .09); --panel: rgba(255, 255, 255, .045);
  --good: #34D399; --good-t: #7EF0C0; --bad: #FF7A66; --bad-t: #FFAB9E; --ease: cubic-bezier(.22, 1, .36, 1);
  background: radial-gradient(1200px 700px at 12% -10%, #2B2A6E 0%, transparent 60%),
    radial-gradient(900px 600px at 105% 110%, #10394A 0%, transparent 60%),
    linear-gradient(180deg, #14163A 0%, #0E1029 100%); }
/* ince nokta deseni: düz zemin "boş" görünmesin (sabit, hareketsiz) */
.fx::before { content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .5;
  background-image: radial-gradient(rgba(255, 255, 255, .07) 1px, transparent 1.2px); background-size: 26px 26px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 45%, #000 0%, transparent 75%); mask-image: radial-gradient(ellipse at 50% 45%, #000 0%, transparent 75%); }
button { font: inherit; color: inherit; cursor: pointer; border: 0; background: none; -webkit-tap-highlight-color: transparent; }
button:focus-visible { outline: 2px solid #B9A4FF; outline-offset: 3px; }
svg { width: 18px; height: 18px; flex: none; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
kbd { font: 500 .7rem/1 'JetBrains Mono', monospace; padding: 3px 6px; border-radius: 6px; color: var(--sub);
  border: 1px solid rgba(255, 255, 255, .14); border-bottom-width: 2px; background: rgba(255, 255, 255, .04); }

/* ---- üst şerit ---- */
.top { position: relative; z-index: 3; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center;
  gap: 22px; padding: 16px 26px 14px; }
.who { display: flex; align-items: center; gap: 12px; min-width: 0; }
.leave { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px;
  color: var(--sub); border: 1px solid var(--line); background: var(--panel); transition: color .15s, border-color .15s, background .15s; }
.leave:hover { color: var(--ink); border-color: rgba(255, 255, 255, .22); background: rgba(255, 255, 255, .08); }
.who .k { font: 500 .66rem/1 'JetBrains Mono', monospace; letter-spacing: .14em; text-transform: uppercase; color: var(--mute); }
.who .t { font: 600 1.02rem/1.25 'Fraunces', serif; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 22vw; margin-top: 4px; }
.prog { min-width: 0; }
.prog .row { white-space: nowrap; display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 7px; font-size: .84rem; color: var(--sub); }
.prog .row b { color: var(--ink); font-size: 1.02rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.prog .row span:last-child { color: var(--mute); font-size: .78rem; }
.bar { display: flex; gap: 3px; height: 8px; }
.bar i { flex: 1 1 0; min-width: 2px; border-radius: 3px; background: rgba(255, 255, 255, .1); transition: background-color .35s; }
.bar i:first-child { border-radius: 5px 3px 3px 5px; } .bar i:last-child { border-radius: 3px 5px 5px 3px; }
.bar i.good { background: var(--good); } .bar i.bad { background: var(--bad); } .bar i.skip { background: #8E8FB5; }
.bar i.cur { background: #F4F1FF; box-shadow: 0 0 0 3px rgba(185, 164, 255, .28); }
.tools { display: flex; align-items: center; gap: 10px; }
.stat { display: flex; align-items: center; gap: 10px; height: 46px; padding: 0 14px 0 10px; border-radius: 14px;
  background: var(--panel); border: 1px solid var(--line); }
.stat b { display: block; font-size: 1.08rem; font-weight: 650; line-height: 1; font-variant-numeric: tabular-nums; }
.stat small { display: block; font-size: .64rem; letter-spacing: .1em; text-transform: uppercase; color: var(--mute); margin-top: 4px; white-space: nowrap; }
.ring { width: 30px; height: 30px; transform: rotate(-90deg); stroke-width: 4; }
.ring .tr { stroke: rgba(255, 255, 255, .12); } .ring .fg { stroke: var(--good); transition: stroke-dashoffset .5s var(--ease), stroke .3s; }
.flame { width: 26px; height: 26px; color: #6F7196; stroke-width: 1.8; transition: color .3s; }
.flame path { fill: currentColor; fill-opacity: .18; }
.stat.warm .flame { color: #FFB454; } .stat.hot .flame { color: #FF7A3D; } .stat.hot .flame path { fill-opacity: .45; }
.stat.pop b { animation: pop .45s var(--ease); }
@keyframes pop { 40% { transform: scale(1.35); } }
.tbtn { display: inline-flex; align-items: center; gap: 8px; height: 46px; padding: 0 16px; border-radius: 14px; font-weight: 600; font-size: .92rem;
  border: 1px solid var(--line); background: var(--panel); color: var(--ink); transition: background .15s, border-color .15s, transform .15s; }
.tbtn:hover { background: rgba(255, 255, 255, .09); border-color: rgba(255, 255, 255, .2); }
.tbtn.end { background: #F1EEFF; color: #1C1747; border-color: #F1EEFF; }
.tbtn.end:hover { background: #FFFFFF; }

/* ---- orta: yığınlar + kart ---- */
.main { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(200px, 270px) minmax(0, 1fr) minmax(200px, 270px);
  grid-template-rows: minmax(0, 660px) auto; align-content: center; gap: 0 30px; padding: 6px 30px 0; min-height: 0; }
/* yan paneller kartla aynı boyda ve sabit: içerik geldikçe büyüyüp zıplamasın */
.side { grid-row: 1; display: flex; flex-direction: column; height: min(100%, 580px); align-self: center; min-height: 0;
  padding: 18px 18px 16px; border-radius: 22px; background: var(--panel); border: 1px solid var(--line); }
.side.bad { grid-column: 1; } .side.good { grid-column: 3; }
.side { position: relative; z-index: 1; }
.side .h { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.side .n { font: 650 2.6rem/1 'Instrument Sans', sans-serif; font-variant-numeric: tabular-nums; }
.side.bad .n { color: var(--bad-t); } .side.good .n { color: var(--good-t); }
.side .l { font-size: .9rem; color: var(--sub); font-weight: 600; }
.side .note { font-size: .78rem; color: var(--mute); margin-top: 3px; min-height: 1.1em; }
.pile { position: relative; flex: 1 1 auto; min-height: 96px; margin: 16px 0 12px; border-radius: 16px; border: 1.5px dashed rgba(255, 255, 255, .12); }
.pile.has { border-color: transparent; }
.pile .empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: .78rem; color: var(--mute); }
.pile .empty kbd { font-size: .74rem; }
.pile.has .empty { display: none; }
.pile i { position: absolute; left: 50%; top: 50%; width: 136px; height: 92px; margin: -46px 0 0 -68px; border-radius: 12px;
  background: linear-gradient(160deg, var(--c1), var(--c2)); box-shadow: 0 6px 14px -6px rgba(0, 0, 0, .55);
  transform: translate(var(--x), var(--y)) rotate(var(--r)); }
.pile i.in { animation: land .38s var(--ease) both; }
@keyframes land { from { transform: translate(var(--x), calc(var(--y) - 14px)) rotate(var(--r)) scale(1.18); opacity: .4; } }
.pile i::after { content: ""; position: absolute; right: 7px; top: 7px; width: 16px; height: 16px; border-radius: 50%; background: var(--st); }
.side.bad .pile i { --st: var(--bad); } .side.good .pile i { --st: var(--good); }
.recent { list-style: none; margin: auto 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; min-height: 0; overflow: hidden; }
.recent li { flex: none; font-size: .8rem; line-height: 1.35; color: var(--sub); padding: 7px 10px; border-radius: 10px;
  background: rgba(255, 255, 255, .035); border-left: 3px solid var(--st, transparent); }
.recent li span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.side.bad .recent li { --st: rgba(255, 122, 102, .7); } .side.good .recent li { --st: rgba(52, 211, 153, .7); }
.recent .h2 { font-size: .64rem; letter-spacing: .12em; text-transform: uppercase; color: var(--mute); background: none; padding: 0 2px; border: 0; margin-top: 4px; }

/* deste panellerin üstünde (perspective ayrı katman açar): sürüklenen ve yığına uçan kart panelin üstünden geçer */
.deck { grid-row: 1; grid-column: 2; position: relative; z-index: 2; min-width: 0; min-height: 240px; perspective: 2000px; touch-action: none; }
.glow { position: absolute; left: 50%; top: 50%; width: 92%; height: 92%; transform: translate(-50%, -50%); border-radius: 50%; pointer-events: none;
  background: radial-gradient(closest-side, var(--g), transparent); opacity: 0; transition: opacity .7s ease; }
.glow.on { opacity: .45; }
/* arkadaki kartlar ~34 px aşağı taşar: kart o kadar kısa ve yukarıda, düğmelerin üstüne binmesin */
.card { position: absolute; left: 50%; top: calc(50% - 17px); width: min(100%, 900px); height: min(calc(100% - 40px), 580px); margin: 0; translate: -50% -50%;
  container-type: size; transform-origin: 50% 60%; will-change: transform;
  transition: transform .46s var(--ease), opacity .32s ease; }
.card.s0 { transform: none; }
.card.s1 { transform: translate3d(18px, 14px, 0) rotate(2.6deg) scale(.965); }
.card.s2 { transform: translate3d(-20px, 22px, 0) rotate(-3.2deg) scale(.935); }
.card.s3 { transform: translate3d(6px, 30px, 0) rotate(1.2deg) scale(.905); }
.card.s4 { transform: translate3d(0, 40px, 0) scale(.88); opacity: 0; transition: none; }
.card.s1, .card.s2, .card.s3 { pointer-events: none; }
.card.drag, .card.fly { transition: none; }
.card.shuffle { animation: riffle .5s var(--ease); }
@keyframes riffle { 30% { transform: translate3d(var(--sx), -10px, 0) rotate(var(--sr)); } }
.flip { position: absolute; inset: 0; transform-style: preserve-3d; transition: transform .6s cubic-bezier(.3, .75, .25, 1); }
.card.flipped .flip { transform: rotateY(180deg); }
.face { position: absolute; inset: 0; border-radius: 28px; backface-visibility: hidden; -webkit-backface-visibility: hidden;
  display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 2px 0 rgba(255, 255, 255, .06) inset, 0 30px 60px -28px rgba(0, 0, 0, .7); }
.front { color: var(--cink); padding: 26px 34px 20px; cursor: grab;
  background: radial-gradient(120% 90% at 0% 0%, rgba(255, 255, 255, .5), transparent 55%), linear-gradient(155deg, var(--c1) 0%, var(--c2) 100%); }
.card.drag .front { cursor: grabbing; }
.back { transform: rotateY(180deg); background: #FFFDF8; color: #1E2433; cursor: pointer; }
.back::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 6px; background: var(--a); }
.chips { display: flex; align-items: center; gap: 7px; min-height: 32px; min-width: 0; }
.chip { flex: 0 1 auto; min-width: 0; font-size: .76rem; font-weight: 600; padding: 5px 11px; border-radius: 999px; background: rgba(255, 255, 255, .62); color: var(--cink);
  max-width: 46cqi; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chip.fix { flex: none; } .chip.new { background: var(--cink); color: var(--c1); }
.src { flex: none; margin-left: auto; display: inline-flex; align-items: center; gap: 7px; padding: 7px 13px; border-radius: 999px; font-size: .8rem; font-weight: 600;
  background: rgba(255, 255, 255, .78); color: var(--cink); transition: background .15s, transform .15s; }
.src:hover { background: #FFFFFF; transform: translateY(-1px); }
.src svg { width: 15px; height: 15px; }
.back .src { background: #F3EEE2; color: #3A3324; } .back .src:hover { background: #EAE3D2; }
.fq { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: 8px 4cqi;
  font: 600 clamp(1.35rem, 4.3cqi, 2.7rem)/1.3 'Fraunces', serif; letter-spacing: -.005em; text-wrap: balance; }
.long .fq { font-size: clamp(1.2rem, 3.3cqi, 2.05rem); } .xlong .fq { font-size: clamp(1.05rem, 2.6cqi, 1.6rem); line-height: 1.38; }
.hint { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: .8rem; color: var(--cink); opacity: .72; }
.hint kbd { color: var(--cink); border-color: rgba(0, 0, 0, .14); background: rgba(255, 255, 255, .4); }
.bs { flex: 1; min-height: 0; overflow-y: auto; padding: 22px 34px 22px; overscroll-behavior: contain; user-select: text; }
.bs .chips { margin-bottom: 4px; }
.lab { font-size: .68rem; font-weight: 650; letter-spacing: .12em; text-transform: uppercase; color: var(--a); margin: 16px 0 6px; }
.q2 { font-size: .9rem; line-height: 1.5; color: #6B6F7B; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.ans { font: 600 clamp(1.25rem, 3.4cqi, 2rem)/1.3 'Fraunces', serif; color: #1E2433; }
.sol { margin: 0; padding-left: 1.3rem; color: #2A3040; line-height: 1.6; font-size: .95rem; }
.ev { border-left: 3px solid var(--a); padding: 10px 14px; background: #FFF8E1; border-radius: 0 12px 12px 0; color: #2A3040;
  line-height: 1.6; font-size: .95rem; }
.ev mark { background: linear-gradient(104deg, rgba(242, 214, 75, 0) .9%, rgba(242, 214, 75, .8) 2.4%, rgba(242, 214, 75, .5) 6%,
  rgba(242, 214, 75, .32) 93%, rgba(242, 214, 75, .7) 96%, rgba(242, 214, 75, 0) 98%); color: inherit; padding: 0 2px;
  -webkit-box-decoration-break: clone; box-decoration-break: clone; }
.stamp { position: absolute; top: 34px; z-index: 4; padding: 8px 18px; border-radius: 12px; font: 700 1.25rem/1 'Instrument Sans', sans-serif;
  letter-spacing: .08em; text-transform: uppercase; border: 3px solid currentColor; background: rgba(255, 255, 255, .88); opacity: 0; pointer-events: none; }
.stamp.good { right: 30px; color: #0E7A50; transform: rotate(8deg); opacity: var(--g, 0); }
.stamp.bad { left: 30px; color: #C23A22; transform: rotate(-8deg); opacity: var(--b, 0); }
.done { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  font: 600 1.6rem/1.2 'Fraunces', serif; color: var(--ink); opacity: 0; pointer-events: none; transition: opacity .3s .25s; }
.done small { font: 500 .9rem 'Instrument Sans', sans-serif; color: var(--sub); }
.fx.over .done { opacity: 1; }

.acts { grid-row: 2; grid-column: 2; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; width: min(100%, 900px); margin: 22px auto 0; }
.act { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; height: 70px; border-radius: 18px;
  border: 1px solid; transition: transform .16s var(--ease), background .16s, border-color .16s; }
.act .l { display: inline-flex; align-items: center; gap: 9px; font-size: 1.02rem; font-weight: 650; }
.act .l svg { width: 19px; height: 19px; stroke-width: 2.4; }
.act .w { font-size: .76rem; opacity: .78; }
.act kbd { position: absolute; right: 12px; top: 10px; }
.act .cnt { display: none; position: absolute; left: 12px; top: 9px; font-size: .78rem; font-weight: 700; padding: 2px 8px; border-radius: 999px; background: rgba(255, 255, 255, .1); }
.act:hover { transform: translateY(-2px); } .act:active { transform: translateY(1px) scale(.99); }
.act.bad { color: var(--bad-t); background: rgba(255, 122, 102, .1); border-color: rgba(255, 122, 102, .32); }
.act.bad:hover { background: rgba(255, 122, 102, .18); border-color: rgba(255, 122, 102, .55); }
.act.skip { color: #CFD0EA; background: rgba(255, 255, 255, .05); border-color: rgba(255, 255, 255, .14); }
.act.skip:hover { background: rgba(255, 255, 255, .1); }
.act.good { color: var(--good-t); background: rgba(52, 211, 153, .1); border-color: rgba(52, 211, 153, .32); }
.act.good:hover { background: rgba(52, 211, 153, .18); border-color: rgba(52, 211, 153, .55); }
.act.flash { animation: flash .35s ease; }
@keyframes flash { 40% { transform: scale(.97); filter: brightness(1.3); } }

/* ---- alt satır: kısayollar ---- */
.foot { position: relative; z-index: 1; display: flex; justify-content: center; align-items: center; gap: 18px; flex-wrap: wrap;
  padding: 14px 20px 16px; font-size: .78rem; color: var(--mute); }
.foot span { display: inline-flex; align-items: center; gap: 6px; }
.toast { position: absolute; left: 50%; top: 84px; z-index: 6; transform: translate(-50%, -10px); padding: 10px 16px; border-radius: 12px;
  background: #F1EEFF; color: #1C1747; font-size: .88rem; font-weight: 600; opacity: 0; pointer-events: none;
  transition: opacity .2s, transform .25s var(--ease); box-shadow: 0 14px 30px -14px rgba(0, 0, 0, .6); }
.toast.on { opacity: 1; transform: translate(-50%, 0); }

/* ---- dar ekran: yığın panelleri yerine düğmelerde sayı ---- */
@media (max-width: 1180px) {
  .main { grid-template-columns: minmax(0, 1fr); padding: 6px 22px 0; }
  .deck, .acts { grid-column: 1; }
  .side { display: none; }
  .act .cnt { display: inline-block; }
  .who .t { max-width: 16vw; }
  .stat.time, .prog .skipn { display: none; }
}
@media (max-width: 860px) {
  .top { grid-template-columns: auto minmax(0, 1fr); gap: 12px 14px; padding: 12px 14px 10px; }
  .tools { grid-column: 1 / -1; justify-content: space-between; }
  .who .k, .who .t, .stat small, .foot { display: none; }
  .main { padding: 4px 12px 12px; } .acts { gap: 8px; margin-top: 14px; } .act { height: 62px; } .act kbd { display: none; }
  .front { padding: 18px 20px 14px; } .bs { padding: 18px 20px; }
}
@media (max-height: 760px) {
  .top { padding-top: 10px; padding-bottom: 8px; } .acts { margin-top: 14px; } .act { height: 60px; }
  .pile { margin: 10px 0 8px; } .foot { padding: 8px 20px 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .card, .flip, .glow, .bar i, .ring .fg { transition: none !important; }
  .pile i.in, .stat.pop b, .act.flash, .card.shuffle { animation: none !important; }
}
"""

_HTML = '<div class="fx" role="application" aria-label="Bilgi kartı oturumu"></div>'

_JS = r"""
const ICON = {
  back: '<svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24"><path d="M16 3h5v5"/><path d="M4 20L21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/></svg>',
  flag: '<svg viewBox="0 0 24 24"><path d="M4 22V4"/><path d="M4 4h12l-2 4 2 4H4"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>',
  skip: '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/></svg>',
  book: '<svg viewBox="0 0 24 24"><path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/></svg>',
  clock: '<svg viewBox="0 0 24 24" style="width:22px;height:22px;color:#A9AACB"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  flame: '<svg class="flame" viewBox="0 0 24 24"><path d="M12 22c4.2 0 7-2.8 7-6.6 0-3.9-2.6-6.2-4.1-9.4-.4 2-1.4 3.4-2.9 4.2C12.3 6.6 10.6 3.9 8 2c.3 3.6-3 6.2-3 11.3C5 18.9 7.9 22 12 22z"/></svg>',
}
const KBD = (k) => `<kbd>${k}</kbd>`
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]))
const gap = (d) => d == null ? "" : d <= 0 ? "bugün yine" : d === 1 ? "yarın" : d < 30 ? `${d} gün sonra` : d < 365 ? `~${Math.round(d / 30)} ay sonra` : "1 yıl sonra"
const mmss = (s) => { s = Math.max(0, Math.floor(s)); const m = Math.floor(s / 60); return m >= 60 ? `${Math.floor(m / 60)} sa ${m % 60} dk` : `${m}:${String(s % 60).padStart(2, "0")}` }
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches

function frame(S) {
  return `
  <header class="top">
    <div class="who"><button class="leave" data-do="leave" title="Ara ver: ana sayfaya dön (oturum kaydedilir, kaldığın yerden devam edersin)">${ICON.back}</button>
      <div style="min-width:0"><div class="k">Bilgi kartları</div><div class="t">${esc(S.title)}</div></div></div>
    <div class="prog"><div class="row"><span><b class="pos"></b> <span class="of"></span></span><span class="skipn"></span></div><div class="bar"></div></div>
    <div class="tools">
      <div class="stat acc" title="İsabet: değerlendirdiğin kartlardan bildiklerinin oranı (atlananlar sayılmaz)">
        <svg class="ring" viewBox="0 0 36 36"><circle class="tr" cx="18" cy="18" r="15" fill="none"/><circle class="fg" cx="18" cy="18" r="15" fill="none" stroke-dasharray="94.25" stroke-dashoffset="94.25"/></svg>
        <div><b class="accv">–</b><small>isabet</small></div></div>
      <div class="stat fire" title="Seri: art arda bildiğin kartlar">${ICON.flame}<div><b class="strk">0</b><small class="bestv">seri</small></div></div>
      <div class="stat time" title="Oturum süresi">${ICON.clock}<div><b class="clock">0:00</b><small>süre</small></div></div>
      <button class="tbtn" data-do="shuffle" title="Kalan kartların sırasını karıştır (K)">${ICON.shuffle}<span>Karıştır</span></button>
      <button class="tbtn end" data-do="end" title="Oturumu bitir ve özeti gör">${ICON.flag}<span>Bitir</span></button>
    </div>
  </header>
  <main class="main">
    <aside class="side bad"><div class="h"><span class="n" data-n="bad">0</span><span class="l">Bilemediklerin</span></div>
      <div class="note" data-note="bad"></div>
      <div class="pile" data-pile="bad"><div class="empty">${ICON.back} sola sürükle ya da ${KBD("←")}</div></div>
      <ul class="recent" data-recent="bad"></ul></aside>
      <div class="deck"><div class="glow a"></div><div class="glow b"></div><div class="done">Deste bitti<small>Özet hazırlanıyor…</small></div></div>
      <div class="acts">
        <button class="act bad" data-grade="bad"><span class="cnt" data-c="bad">0</span><span class="l">${ICON.x}Bilemedim</span><span class="w" data-w="bad"></span>${KBD("←")}</button>
        <button class="act skip" data-grade="skip"><span class="l">${ICON.skip}Atla</span><span class="w" data-w="skip"></span>${KBD("↓")}</button>
        <button class="act good" data-grade="good"><span class="cnt" data-c="good">0</span><span class="l">${ICON.check}Bildim</span><span class="w" data-w="good"></span>${KBD("→")}</button>
      </div>
    <aside class="side good"><div class="h"><span class="n" data-n="good">0</span><span class="l">Bildiklerin</span></div>
      <div class="note" data-note="good"></div>
      <div class="pile" data-pile="good"><div class="empty">sağa sürükle ya da ${KBD("→")}</div></div>
      <ul class="recent" data-recent="good"></ul></aside>
  </main>
  <footer class="foot"><span>${KBD("Boşluk")} çevir</span><span>${KBD("←")} bilemedim</span><span>${KBD("↓")} atla</span>
    <span>${KBD("→")} bildim</span><span>${KBD("K")} karıştır</span><span>Kartı sola / sağa sürükleyerek de değerlendirebilirsin</span></footer>
  <div class="toast"></div>`
}

// ---- kart öğesi: sıradaki k. kart (aynı soru atlanınca sırada iki kez bulunabilir → anahtar sıra numarası)
function cardEl(S, k) {
  const id = S.queue[k], c = S.cards[id] || { q: "(Bu soru havuzdan çıkarıldı.)", ans: "", ev: "" }
  const [c1, c2, ink, a] = S.pal[k % S.pal.length]
  const el = document.createElement("div")
  el.className = "card s4"
  el.style.cssText = `--c1:${c1};--c2:${c2};--cink:${ink};--a:${a}`
  const chips = (c.diff ? `<span class="chip fix">${c.diff}</span>` : "") + (c.topic ? `<span class="chip" title="${c.topic}">${c.topic}</span>` : "")
    + (c.seen ? "" : '<span class="chip fix new">Yeni kart</span>')
  const src = c.page || c.ev ? `<button class="src" data-do="src" title="Notunda kanıt sayfasını aç (kanıt cümlesi işaretli)">${ICON.book}Notta aç${c.page ? " · s. " + c.page : ""}</button>` : ""
  const sol = c.sol && c.sol.length ? `<div class="lab">Çözüm</div><ol class="sol">${c.sol.map(s => `<li>${s}</li>`).join("")}</ol>` : ""
  const ev = c.ev ? `<div class="lab">Notundaki kaynak${c.where ? " · " + c.where : ""}</div><div class="ev"><mark>${c.ev}</mark></div>` : ""
  el.innerHTML = `<div class="flip">
    <div class="face front ${c.len || ""}"><div class="chips">${chips}${src}</div><div class="fq">${c.q}</div>
      <div class="hint">Cevap için karta tıkla ${KBD("Boşluk")}</div></div>
    <div class="face back"><div class="bs"><div class="chips"><span class="lab" style="margin:0">Soru</span>${src}</div>
      <div class="q2">${c.q}</div><div class="lab">Cevap</div><div class="ans">${c.ans}</div>${sol}${ev}</div></div>
  </div><div class="stamp good">Bildim</div><div class="stamp bad">Bilemedim</div>`
  return el
}

// ---- sahne: açık kart ve arkasındaki üç kart (s0-s3); yeni gelen s4'ten (görünmez) yerine kayar
function layout(root, S) {
  const deck = root.querySelector(".deck")
  const want = []
  for (let k = S.pos; k < Math.min(S.queue.length, S.pos + 4); k++) want.push(k)
  for (const [k, el] of S.els) if (!want.includes(k)) { el.remove(); S.els.delete(k) }
  let fresh = false
  want.forEach((k) => { if (!S.els.has(k)) { const el = cardEl(S, k); deck.appendChild(el); S.els.set(k, el); fresh = true } })
  if (fresh) deck.offsetWidth  // yeni kartlar s4'te çizilsin, sonra geçişle yerlerine
  want.forEach((k, slot) => {
    const el = S.els.get(k)
    el.className = "card s" + slot + (slot === 0 && S.flipped ? " flipped" : "")
    el.style.zIndex = 20 - slot
    el.setAttribute("aria-hidden", slot ? "true" : "false")
  })
  // kartın renginde hafif ışık (iki katman sırayla: renk geçişi yalnızca opaklıkla)
  const cur = S.els.get(S.pos)
  if (cur) {
    S.glowIdx = 1 - (S.glowIdx || 0)
    const on = root.querySelectorAll(".glow")[S.glowIdx], off = root.querySelectorAll(".glow")[1 - S.glowIdx]
    on.style.setProperty("--g", S.pal[S.pos % S.pal.length][1]); on.classList.add("on"); off.classList.remove("on")
  }
  hints(root, S)
}

function hints(root, S) {
  const c = S.cards[S.queue[S.pos]] || {}
  root.querySelector('[data-w="bad"]').textContent = S.pos < S.queue.length ? gap(c.gb ?? 0) : ""
  root.querySelector('[data-w="good"]').textContent = S.pos < S.queue.length ? gap(c.gg) : ""
  root.querySelector('[data-w="skip"]').textContent = S.pos < S.queue.length ? (S.skipped.has(S.queue[S.pos]) ? "sonraki oturuma" : "destenin sonuna") : ""
}

// ---- göstergeler: ilerleme, isabet, seri, yığın sayıları
function stats(S) {
  let good = 0, bad = 0, skip = 0, run = 0, best = 0
  for (const [, r] of S.log) {
    if (r === "good") { good++; run++; best = Math.max(best, run) } else if (r === "bad") { bad++; run = 0 } else skip++
  }
  return { good, bad, skip, streak: run, best }
}

function paint(root, S, bumped) {
  const T = stats(S), total = S.queue.length
  root.querySelector(".pos").textContent = `${Math.min(S.pos + 1, total)}`
  root.querySelector(".of").textContent = `/ ${total} kart`
  root.querySelector(".skipn").textContent = T.skip ? `${T.skip} atlandı · sonda yine gelir` : `${Math.max(0, total - S.pos)} kart kaldı`
  const bar = root.querySelector(".bar")
  if (bar.children.length !== total) bar.innerHTML = "<i></i>".repeat(total)
  ;[...bar.children].forEach((i, k) => { i.className = k < S.pos ? (S.log[k] ? S.log[k][1] : "skip") : k === S.pos ? "cur" : "" })
  const acc = T.good + T.bad ? Math.round(100 * T.good / (T.good + T.bad)) : null
  root.querySelector(".accv").textContent = acc == null ? "–" : `%${acc}`
  const fg = root.querySelector(".ring .fg")
  fg.style.strokeDashoffset = 94.25 * (1 - (acc || 0) / 100)
  fg.style.stroke = acc == null ? "transparent" : acc >= 70 ? "#34D399" : acc >= 40 ? "#FBBF24" : "#FF7A66"
  const fire = root.querySelector(".stat.fire")
  fire.classList.toggle("warm", T.streak >= 1 && T.streak < 5); fire.classList.toggle("hot", T.streak >= 5)
  if (bumped === "good" && T.streak > 0) { fire.classList.remove("pop"); fire.offsetWidth; fire.classList.add("pop") }
  root.querySelector(".strk").textContent = T.streak
  root.querySelector(".bestv").textContent = T.best ? `seri · en iyi ${T.best}` : "seri"
  for (const kind of ["bad", "good"]) {
    root.querySelector(`[data-n="${kind}"]`).textContent = T[kind]
    root.querySelector(`[data-c="${kind}"]`).textContent = T[kind]
    const ids = S.log.filter(([, r]) => r === kind).map(([id]) => id)
    let note = ""
    if (kind === "bad" && ids.length) note = "Bunlar bugün yine gelecek"
    if (kind === "good" && ids.length) {
      const gs = ids.map(id => (S.cards[id] || {}).gg).filter(x => x != null)
      note = gs.length ? `En yakın tekrarı ${gap(Math.min(...gs))}` : ""
    }
    root.querySelector(`[data-note="${kind}"]`).textContent = note
    const last = ids.slice(-3).reverse()
    root.querySelector(`[data-recent="${kind}"]`).innerHTML = last.length
      ? '<li class="h2">Son kartlar</li>' + last.map(id => `<li><span>${(S.cards[id] || {}).q || ""}</span></li>`).join("") : ""
  }
}

function pileCard(root, S, kind, k, animate) {
  const pile = root.querySelector(`[data-pile="${kind}"]`)
  pile.classList.add("has")
  const [c1, c2] = S.pal[k % S.pal.length]
  const n = pile.querySelectorAll("i").length
  const i = document.createElement("i")
  const rnd = (Math.sin(k * 12.9898) * 43758.5453) % 1  // sıra numarasından sabit "rastgele" açı: yeniden çizince yerinde kalsın
  i.style.cssText = `--c1:${c1};--c2:${c2};--r:${(rnd * 16).toFixed(1)}deg;--x:${(rnd * 14).toFixed(0)}px;--y:${-Math.min(n, 12) * 3}px`
  if (animate) i.className = "in"
  pile.appendChild(i)
  const all = pile.querySelectorAll("i")
  if (all.length > 13) all[0].remove()
}

// ---- değerlendirme: kart kendi yığınına uçar, arkadaki kart öne kayar (ikisi de transform: kasmaz)
function grade(root, S, result) {
  if (S.over || S.pos >= S.queue.length) return
  const k = S.pos, id = S.queue[k], el = S.els.get(k)
  S.els.delete(k)
  S.log.push([id, result])
  if (result === "skip" && !S.skipped.has(id)) { S.skipped.add(id); S.queue.push(id) }
  S.pos++
  S.flipped = false
  const btn = root.querySelector(`[data-grade="${result}"]`)
  btn.classList.remove("flash"); btn.offsetWidth; btn.classList.add("flash")
  if (el) fly(root, S, el, result, k)
  layout(root, S)
  paint(root, S, result)
  if (S.pos >= S.queue.length) {
    S.over = true
    root.classList.add("over")
    setTimeout(() => sync(S, true), reduced() ? 0 : 650)  // son kart yığına varsın, sonra özet
  } else sync(S)
}

function fly(root, S, el, result, k) {
  const done = () => { el.remove(); if (result !== "skip") pileCard(root, S, result, k, true) }
  if (reduced()) return done()
  const r = el.getBoundingClientRect(), from = getComputedStyle(el).transform
  el.classList.add("fly"); el.classList.remove("drag")
  el.style.zIndex = 40
  el.style.transformOrigin = "50% 50%"  // küçülürken merkezi yığının ortasına otursun
  let to
  const pile = root.querySelector(`[data-pile="${result}"]`)
  const pr = pile && pile.getBoundingClientRect()
  if (result === "skip") to = "translate3d(0, 46px, 0) scale(.84) rotate(2deg)"
  else if (pr && pr.width) {  // yığının ortasına, yığındaki kart boyuna küçülerek
    const s = 136 / r.width, dx = pr.left + pr.width / 2 - (r.left + r.width / 2), dy = pr.top + pr.height / 2 - (r.top + r.height / 2)
    to = `translate3d(${dx}px, ${dy}px, 0) rotate(${result === "good" ? 10 : -10}deg) scale(${s})`
  } else to = `translate3d(${result === "good" ? 120 : -120}%, 10%, 0) rotate(${result === "good" ? 18 : -18}deg)`  // dar ekran: kenardan çıkar
  const a = el.animate([{ transform: from === "none" ? "translate3d(0,0,0)" : from, opacity: 1 },
                        { transform: to, opacity: result === "skip" ? 0 : .85, offset: .82 },
                        { transform: to, opacity: 0 }],
                       { duration: result === "skip" ? 380 : 560, easing: "cubic-bezier(.5, 0, .3, 1)", fill: "forwards" })
  a.onfinish = done
}

function flip(root, S) {
  if (S.over) return
  S.flipped = !S.flipped
  const el = S.els.get(S.pos)
  if (el) el.classList.toggle("flipped", S.flipped)
}

function shuffle(root, S) {
  const rest = S.queue.slice(S.pos)
  if (rest.length < 2) return toast(root, S, "Karıştırılacak başka kart kalmadı.")
  const first = rest[0]
  for (let t = 0; t < 6; t++) {  // ekrandaki kart değişsin (küçük destede rastlantıyla aynı kalabilir)
    for (let i = rest.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [rest[i], rest[j]] = [rest[j], rest[i]] }
    if (rest[0] !== first) break
  }
  S.queue.splice(S.pos, rest.length, ...rest)
  S.flipped = false
  for (const el of S.els.values()) {  // kartlar bir an yana savrulur, sonra yeni sırayla dağıtılır
    el.style.setProperty("--sx", `${(Math.random() * 2 - 1) * 70}px`); el.style.setProperty("--sr", `${(Math.random() * 2 - 1) * 9}deg`)
    el.classList.add("shuffle")
  }
  setTimeout(() => {
    for (const el of S.els.values()) el.remove()
    S.els.clear()
    layout(root, S); paint(root, S)
  }, reduced() ? 0 : 260)
  toast(root, S, `Kalan ${rest.length} kart karıştırıldı.`)
  sync(S)
}

function toast(root, S, text) {
  const t = root.querySelector(".toast")
  t.textContent = text; t.classList.add("on")
  clearTimeout(S.toastT); S.toastT = setTimeout(() => t.classList.remove("on"), 2200)
}

// Python'a destenin durumu: sıra ve değerlendirme günlüğü (birikimli; Python yalnızca yeni satırları yazar)
function sync(S, ended) {
  S.send("sync", { tok: S.tok, queue: S.queue, log: S.log, ended: !!ended })
}

// ---- sürükleme: sola bilemedim, sağa bildim; az sürüklenip bırakılırsa yerine döner; hiç sürüklenmezse çevirir
function drag(root, S) {
  const deck = root.querySelector(".deck")
  deck.onpointerdown = (e) => {
    if (e.button !== 0 || S.over || e.target.closest("button")) return
    const bs = e.target.closest(".bs")  // arka yüzün kaydırma çubuğu sürüklenmesin
    if (bs && e.offsetX > bs.clientWidth) return
    const el = S.els.get(S.pos)
    if (!el || !el.contains(e.target)) return
    S.dr = { x: e.clientX, y: e.clientY, el, moved: false, id: e.pointerId }
  }
  deck.onpointermove = (e) => {
    const d = S.dr
    if (!d || e.pointerId !== d.id) return
    const dx = e.clientX - d.x, dy = e.clientY - d.y
    if (!d.moved) {
      if (Math.hypot(dx, dy) < 8) return
      d.moved = true
      d.el.classList.add("drag")
      try { deck.setPointerCapture(e.pointerId) } catch (_) {}
    }
    d.dx = dx
    if (!d.raf) d.raf = requestAnimationFrame(() => {
      d.raf = 0
      d.el.style.transform = `translate3d(${d.dx}px, ${dy * .2}px, 0) rotate(${d.dx * .035}deg)`
      d.el.style.setProperty("--g", Math.max(0, Math.min(1, d.dx / 130)).toFixed(2))
      d.el.style.setProperty("--b", Math.max(0, Math.min(1, -d.dx / 130)).toFixed(2))
    })
  }
  const up = (e) => {
    const d = S.dr
    if (!d || e.pointerId !== d.id) return
    S.dr = null
    if (d.raf) cancelAnimationFrame(d.raf)
    if (!d.moved) { if (e.type === "pointerup") flip(root, S); return }
    const dx = e.clientX - d.x
    if (Math.abs(dx) > 120 && e.type === "pointerup") return grade(root, S, dx > 0 ? "good" : "bad")
    d.el.classList.remove("drag")  // yerine yaylanarak döner (s0 geçişi)
    d.el.style.transform = ""; d.el.style.removeProperty("--g"); d.el.style.removeProperty("--b")
  }
  deck.onpointerup = up
  deck.onpointercancel = up
}

function init(root, data) {
  const S = root._s = {
    tok: data.tok, title: data.title, cards: data.cards, pal: data.pal, queue: [...data.queue], log: data.log.map(x => [...x]),
    skipped: new Set(data.skipped || []), started: data.started, els: new Map(), flipped: !!data.flip, over: false,
  }
  S.pos = Math.min(S.log.length, S.queue.length)
  root.dataset.tok = data.tok
  root.classList.remove("over")
  root.innerHTML = frame(S)
  S.log.forEach(([, r], k) => { if (r !== "skip") pileCard(root, S, r, k, false) })
  layout(root, S)
  paint(root, S)
  drag(root, S)
  root.onclick = (e) => {
    const g = e.target.closest("[data-grade]"), b = e.target.closest("[data-do]")
    if (g) { g.blur(); return grade(root, S, g.dataset.grade) }
    if (!b) return
    b.blur()
    const act = b.dataset.do
    if (act === "shuffle") shuffle(root, S)
    else if (act === "end") { S.over = true; sync(S, true) }
    else if (act === "leave") S.fire("act", "leave")
    else if (act === "src") S.fire("act", "src|" + S.queue[S.pos])
  }
}

export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component
  const root = parentElement.querySelector(".fx")
  if (!root || !data || !data.tok) return
  if (root.dataset.tok !== data.tok) init(root, data)  // aynı oturum: yeniden çizme (kartlar, animasyonlar yerinde kalsın)
  const S = root._s
  S.send = setStateValue
  S.fire = setTriggerValue
  const tick = () => { const c = root.querySelector(".clock"); if (c) c.textContent = mmss(Date.now() / 1000 - S.started) }
  clearInterval(S.tick); tick(); S.tick = setInterval(tick, 1000)
  if (root._onkey) window.removeEventListener("keydown", root._onkey, true)
  root._onkey = (e) => {
    if (!root.isConnected) return
    const t = e.composedPath()[0]
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || e.ctrlKey || e.metaKey || e.altKey || e.repeat && e.key === " ") return
    if (document.querySelector('[data-testid="stDialog"]')) return
    const k = e.key
    if (t && t.tagName === "BUTTON" && (k === " " || k === "Enter")) return  // Tab ile seçilmiş düğme kendi işini yapsın
    if (k === " " || k === "Enter" || k === "ArrowUp") flip(root, S)
    else if (k === "ArrowLeft" || k === "1") grade(root, S, "bad")
    else if (k === "ArrowDown" || k === "2") grade(root, S, "skip")
    else if (k === "ArrowRight" || k === "3") grade(root, S, "good")
    else if (k === "k" || k === "K") shuffle(root, S)
    else return
    e.preventDefault(); e.stopPropagation()
  }
  window.addEventListener("keydown", root._onkey, true)
  return () => { window.removeEventListener("keydown", root._onkey, true); clearInterval(S.tick) }
}
"""

_DECK = Component("nr_flashcards", html=_HTML, css=_CSS, js=_JS)


def deck(key: str, data: dict):
    """Oturum ekranını çizer. data: tok (oturum belirteci), title, cards {kimlik: görünüm}, queue, log [[kimlik, sonuç]],
    skipped, started, pal (kart renkleri), flip (önizleme: ilk kart çevrili). Dönen değerde .act: "leave" | "src|kimlik"
    (tetik, bir çalıştırmalık); destenin durumu st.session_state[key]['sync']'te (bileşeni çağırmadan önce okunur)."""
    return _DECK(key=key, data=data, default={"sync": None}, on_sync_change=lambda: None, on_act_change=lambda: None)

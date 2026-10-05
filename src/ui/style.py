"""Arayüzün ortak görsel dili: 'akademik baskı + fosforlu kalem'.

Renk ve yazı tipleri .streamlit/config.toml'da; burada yalnızca Streamlit bileşenlerinin karşılamadığı
ayrıntılar (kâğıt dokusu, fosforlu vurgu, kart, akış şeması, sayfa başlığı) ve küçük HTML yardımcıları var.
"""

from __future__ import annotations

import html as _html
import re

import streamlit as st

INK, PAPER, HIGHLIGHT = "#1E2433", "#F7F4ED", "#F2D64B"
STATUS = {  # etiket → (Türkçe, renk, açık zemin)
    "verified": ("Doğrulandı", "#2F6B4F", "#E3EEE7"),
    "needs_review": ("İncelenmeli", "#9A6516", "#F6EBD6"),
    "rejected": ("Reddedildi", "#A0412D", "#F4E1DC"),
}

_CSS = """
<style>
/* Kâğıt dokusu: çok hafif gren (SVG gürültü), göz yormaz */
.stApp {
  background-image:
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.12 0 0 0 0 0.1 0 0 0 0 0.06 0 0 0 .035 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>");
}
.block-container { padding-top: 2rem; max-width: 1180px; }

/* Sayfa başlığı: üst etiket + serif başlık + ince çift çizgi (basılı sınav kâğıdı gibi) */
.nr-kicker { font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .14em;
  text-transform: uppercase; color: #7A6F57; margin-bottom: .15rem; }
.nr-title { font-family: 'Fraunces', serif; font-weight: 650; font-size: 2rem; line-height: 1.1;
  color: #1E2433; margin: 0; padding: 0; }
.nr-lead { color: #4A5163; font-size: 1rem; max-width: 44rem; margin: .45rem 0 0 0; }
.nr-rule { border: 0; border-top: 3px double #CFC5AF; margin: 1rem 0 1.3rem 0; }

/* Fosforlu kalem: sistemin imzası (kanıt vurgusu) */
.nr-hl { background: linear-gradient(104deg, rgba(242,214,75,0) .9%, rgba(242,214,75,.85) 2.4%,
  rgba(242,214,75,.55) 5.8%, rgba(242,214,75,.35) 93%, rgba(242,214,75,.75) 96%, rgba(242,214,75,0) 98%),
  linear-gradient(183deg, rgba(242,214,75,0) 0%, rgba(242,214,75,.25) 7.9%, rgba(242,214,75,0) 15%);
  padding: .05em .35em; border-radius: .6em .3em; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
.nr-hero-hl { background-image: linear-gradient(transparent 62%, rgba(242,214,75,.75) 62%);
  background-size: 0% 100%; background-repeat: no-repeat; animation: nr-swipe 1.1s .25s ease-out forwards; }
@keyframes nr-swipe { to { background-size: 100% 100%; } }

/* Kartlar */
.nr-card { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .8rem; padding: 1.15rem 1.3rem;
  box-shadow: 0 1px 0 rgba(30,36,51,.04), 0 8px 24px -18px rgba(30,36,51,.35);
  animation: nr-rise .5s ease-out both; }
.nr-card h4 { font-family: 'Fraunces', serif; margin: 0 0 .35rem 0; font-size: 1.12rem; color: #1E2433; }
.nr-card p { margin: 0; color: #4A5163; }
.nr-card .nr-meta { font-family: 'JetBrains Mono', monospace; font-size: .78rem; color: #7A6F57; }
@keyframes nr-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* Durum rozeti */
.nr-pill { display: inline-block; font-size: .78rem; font-weight: 600; padding: .18rem .62rem; border-radius: 999px;
  border: 1px solid currentColor; margin-right: .35rem; white-space: nowrap; }

/* Akış şeması (6 adım) */
.nr-flow { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: .6rem; margin: .4rem 0 .2rem; }
.nr-step { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .7rem; padding: .8rem .85rem;
  position: relative; animation: nr-rise .5s ease-out both; }
.nr-step .n { font-family: 'JetBrains Mono', monospace; font-size: .72rem; color: #9A8C6E; }
.nr-step .t { font-weight: 600; color: #1E2433; margin: .15rem 0; }
.nr-step .v { font-family: 'Fraunces', serif; font-size: 1.45rem; color: #1F3A5F; }
.nr-step .d { font-size: .8rem; color: #6B6F7B; }
.nr-step:not(:last-child)::after { content: "→"; position: absolute; right: -.62rem; top: 42%; color: #B6A98C; }
@media (max-width: 900px) { .nr-flow { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .nr-step::after { display: none; } }

/* Soru kartı: basılı sınav kâğıdı */
.nr-exam { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .9rem; padding: 1.5rem 1.6rem 1.3rem;
  box-shadow: 0 1px 0 rgba(30,36,51,.04), 0 10px 28px -20px rgba(30,36,51,.4); animation: nr-rise .35s ease-out both; }
.nr-qhead { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.nr-qnum { font-family: 'JetBrains Mono', monospace; font-size: .78rem; font-weight: 500; letter-spacing: .12em;
  color: #FFFDF8; background: #1E2433; padding: .25rem .6rem; border-radius: .35rem; margin-right: .3rem; }
.nr-chip { font-size: .78rem; color: #5B5F6B; background: #F1ECE0; border: 1px solid #E2DAC8;
  padding: .18rem .55rem; border-radius: 999px; }
.nr-q { font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.32rem; line-height: 1.45; color: #1E2433;
  margin: 0 0 1.25rem; }
.nr-opts { display: grid; gap: .55rem; }
.nr-opt { display: flex; gap: .85rem; align-items: center; padding: .65rem .9rem; border-radius: .6rem;
  border: 1px solid #E6DECD; background: #FFFFFF; font-size: 1rem; color: #2A3040; }
.nr-opt .l { flex: 0 0 auto; width: 1.9rem; height: 1.9rem; border-radius: 50%; border: 1.5px solid #B9AF98;
  display: inline-flex; align-items: center; justify-content: center; font-family: 'JetBrains Mono', monospace;
  font-weight: 500; font-size: .85rem; color: #6B6150; background: #FBF8F1; }
.nr-opt .ck { margin-left: auto; font-size: .78rem; font-weight: 600; color: #2F6B4F; white-space: nowrap; }
.nr-opt.ok { border-color: #8DB29E; background: #EEF5F0; }
.nr-opt.ok .l { background: #2F6B4F; border-color: #2F6B4F; color: #FFFFFF; }
.nr-opt.bad { border-color: #E3B5AA; background: #FBEFEB; }
.nr-opt.bad .l { background: #A0412D; border-color: #A0412D; color: #FFFFFF; }
.nr-opt.bad .ck { color: #A0412D; }
.nr-why { margin-top: .2rem; padding: .55rem .8rem; border-radius: .5rem; background: #FBF3E2; border: 1px solid #EBD9B4;
  font-size: .92rem; color: #5A4A2A; }
.nr-answer .k + .k, .nr-answer br + .k { margin-top: .5rem; }

/* Sınav: soru başlığı (şıklar Streamlit radyo düğmesiyle seçilir) */
.nr-quiz-q { display: flex; gap: .8rem; align-items: baseline; margin: .1rem 0 .3rem; }
.nr-quiz-q .n { font-family: 'JetBrains Mono', monospace; font-size: .78rem; font-weight: 500; letter-spacing: .1em;
  color: #FFFDF8; background: #1E2433; padding: .2rem .5rem; border-radius: .35rem; white-space: nowrap; }
.nr-quiz-q .t { font-family: 'Fraunces', serif; font-size: 1.18rem; line-height: 1.45; color: #1E2433; }
[data-testid="stForm"] [role="radiogroup"] { gap: .35rem; margin-top: .25rem; }
[data-testid="stForm"] [role="radiogroup"] label { padding: .3rem .4rem; border-radius: .45rem; }
[data-testid="stForm"] [role="radiogroup"] label:hover { background: #F1ECE0; }
[data-testid="stForm"] [role="radiogroup"] label p { font-size: 1rem; color: #2A3040; }
/* Modeller ve Kota: kapasite kutuları, model kartları, ince ölçer çubukları (durum rengi + etiket, yalnızca renk değil) */
.nr-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin-bottom: .9rem; }
.nr-tile { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .8rem; padding: 1.1rem 1.2rem; }
.nr-tile .k { font-size: .85rem; color: #6B6F7B; }
.nr-tile .v { font-family: 'Fraunces', serif; font-size: 2rem; font-weight: 600; color: #1E2433; line-height: 1.15;
  margin: .25rem 0 .2rem; }
.nr-tile .d { font-size: .85rem; color: #6B6F7B; }
.nr-st { display: inline-flex; align-items: center; gap: .35rem; font-size: .8rem; font-weight: 600; color: #1E2433;
  padding: .15rem .55rem; border-radius: 999px; background: #F1ECE0; white-space: nowrap; }
.nr-st i { width: .55rem; height: .55rem; border-radius: 50%; display: inline-block; }
.nr-mgrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.nr-mcard { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .8rem; padding: 1rem 1.15rem; }
.nr-mcard .top { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.nr-mcard .name { font-family: 'JetBrains Mono', monospace; font-weight: 500; font-size: .95rem; color: #1E2433; }
.nr-mcard .prov { font-size: .78rem; color: #6B6F7B; border: 1px solid #E2DAC8; border-radius: 999px; padding: .1rem .5rem; }
.nr-mcard .top .nr-st { margin-left: auto; }
.nr-mcard .roles { margin: .55rem 0 .7rem; display: flex; gap: .35rem; flex-wrap: wrap; }
.nr-mcard .meta { display: flex; justify-content: space-between; font-size: .85rem; color: #4A5163; margin-bottom: .3rem; }
.nr-meter { height: 6px; background: #ECE6D8; border-radius: 99px; overflow: hidden; }
.nr-meter b { display: block; height: 100%; border-radius: 99px; }
.nr-mcard .foot { margin-top: .55rem; font-size: .8rem; color: #6B6F7B; }
.nr-chain { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.nr-chain .arrow { color: #B6A98C; }
.nr-role { display: grid; grid-template-columns: 15rem 1fr; gap: 1rem; padding: .8rem 0; border-bottom: 1px dashed #DCD3C1;
  align-items: start; }
.nr-role:last-child { border-bottom: 0; }
.nr-role .r { font-weight: 600; color: #1E2433; }
.nr-role .w { font-size: .82rem; color: #6B6F7B; margin-top: .3rem; }
@media (max-width: 900px) { .nr-tiles, .nr-mgrid { grid-template-columns: minmax(0, 1fr); }
  .nr-role { grid-template-columns: 1fr; } }
/* ---- Sınav: odak modu ---- */
.nr-qprog .lbl { display: flex; justify-content: space-between; font-size: .86rem; color: #4A5163; margin-bottom: .4rem; }
.nr-qprog .lbl b { color: #1E2433; }
.nr-qprog .bar { height: 8px; background: #E7E0D0; border-radius: 99px; overflow: hidden; }
.nr-qprog .bar i { display: block; height: 100%; border-radius: 99px; transition: width .45s ease;
  background: linear-gradient(90deg, #1F3A5F, #3A7BB8); }
/* Sabit yükseklikler: kısa/uzun soru ve farklı soru tiplerinde düzen oynamasın; yeni soru ortadan büyüyerek gelir */
.nr-focus { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: 1.1rem; padding: 1.6rem 1.9rem 1.5rem;
  min-height: 13rem; display: flex; flex-direction: column; justify-content: center; transform-origin: 50% 50%;
  box-shadow: 0 1px 0 rgba(30,36,51,.04), 0 18px 40px -28px rgba(30,36,51,.55); animation: nr-pop .32s ease-out both; }
.nr-focus .nr-qhead { margin-bottom: .7rem; }
.nr-focus .nr-q { font-size: 1.5rem; line-height: 1.42; margin: 0; }
@keyframes nr-pop { from { opacity: 0; transform: scale(.965); } to { opacity: 1; transform: none; } }
.st-key-nr_answer { min-height: 28.5rem; margin-top: .7rem; }
.st-key-nr_opts input { font-size: 1.25rem; padding: 1rem 1.1rem; min-height: 3.6rem; }
.nr-sa-help { font-size: .86rem; color: #6B6F7B; margin-top: .55rem; line-height: 1.55; }
.st-key-nr_opts { min-height: 18.6rem; }
.st-key-nr_nav { position: sticky; bottom: 0; z-index: 20; padding: .9rem 0 .7rem;
  background: linear-gradient(to top, #F4F1EA 72%, rgba(244,241,234,0)); }
.st-key-nr_opts button { justify-content: flex-start; text-align: left; min-height: 4.1rem; padding: .85rem 1.15rem;
  border-radius: .9rem; transition: transform .14s ease, box-shadow .14s ease, background-color .14s ease; }
.st-key-nr_opts button:hover { transform: translateY(-2px); box-shadow: 0 10px 22px -14px rgba(30,36,51,.55); }
.st-key-nr_opts button:active { transform: translateY(0) scale(.995); }
.st-key-nr_opts button p { font-size: 1.06rem; text-align: left; line-height: 1.45; }
.st-key-nr_opts button > div, .st-key-nr_opts button [data-testid="stMarkdownContainer"] { justify-content: flex-start;
  width: 100%; text-align: left; }
.st-key-nr_opts button[kind="primary"] { box-shadow: 0 0 0 3px rgba(58,123,184,.25); }
.nr-hint { border: 1px solid #EBD9B4; background: #FFF8E6; border-radius: .9rem; padding: .85rem 1.1rem; margin: .55rem 0; }
.nr-hint .h { font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .1em; text-transform: uppercase;
  color: #8A5A12; margin-bottom: .3rem; }
.nr-hint .b { color: #3C4253; line-height: 1.6; }
.nr-hint.new { animation: nr-glow 1.8s ease-out both; }
@keyframes nr-glow { 0% { opacity: 0; transform: translateY(-8px); box-shadow: 0 0 0 0 rgba(242,214,75,0); }
  25% { opacity: 1; transform: none; box-shadow: 0 0 0 7px rgba(242,214,75,.55); }
  100% { box-shadow: 0 0 0 0 rgba(242,214,75,0); } }
.nr-keys { font-size: .78rem; color: #8A8576; text-align: center; margin-top: .4rem; }
.nr-kbd { font-family: 'JetBrains Mono', monospace; font-size: .72rem; color: #4A5163; background: #FFFDF8;
  border: 1px solid #DCD3C1; border-bottom-width: 2px; border-radius: .3rem; padding: 0 .35rem; }
.nr-start { background: linear-gradient(135deg, #1F3A5F 0%, #2C5282 55%, #3A7BB8 100%); color: #F7F4ED;
  border-radius: 1.2rem; padding: 1.8rem 2rem; box-shadow: 0 22px 44px -30px rgba(31,58,95,.9); animation: nr-rise .5s ease-out both; }
.nr-start .k { font-family: 'JetBrains Mono', monospace; font-size: .74rem; letter-spacing: .14em; text-transform: uppercase;
  color: #F2D64B; }
.nr-start h2 { font-family: 'Fraunces', serif; font-size: 2rem; margin: .3rem 0 .5rem; color: #FFFFFF; }
.nr-start .facts { display: flex; gap: 1.6rem; flex-wrap: wrap; margin-top: .9rem; }
.nr-start .facts div { font-size: .85rem; color: #D7DEE8; }
.nr-start .facts b { display: block; font-family: 'Fraunces', serif; font-size: 1.45rem; color: #FFFFFF; font-weight: 600; }
/* ---- Sınav: sonuç ---- */
.nr-res { display: grid; grid-template-columns: 220px 1fr; gap: 2rem; align-items: center; background: #FFFDF8;
  border: 1px solid #E2DAC8; border-radius: 1.2rem; padding: 1.6rem 1.8rem; animation: nr-rise .5s ease-out both;
  box-shadow: 0 18px 40px -30px rgba(30,36,51,.55); }
.nr-res .msg { font-family: 'Fraunces', serif; font-size: 1.7rem; color: #1E2433; line-height: 1.2; }
.nr-res .sub { color: #4A5163; margin: .35rem 0 1rem; }
.nr-ring circle.seg { animation: nr-draw 1.1s ease-out both; }
@keyframes nr-draw { from { stroke-dasharray: 0 999; } }
.nr-ring .pct { font-family: 'Fraunces', serif; font-size: 34px; font-weight: 650; fill: #1E2433; }
.nr-ring .lbl { font-size: 12px; fill: #6B6F7B; }
.nr-legend { display: flex; gap: 1rem; justify-content: center; margin-top: .4rem; font-size: .84rem; color: #1E2433; }
.nr-legend i { display: inline-block; width: .65rem; height: .65rem; border-radius: 50%; margin-right: .3rem; }
.nr-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .7rem; }
.nr-kpi { border: 1px solid #E2DAC8; border-radius: .8rem; padding: .7rem .85rem; background: #FFFFFF; }
.nr-kpi .v { font-family: 'Fraunces', serif; font-size: 1.6rem; font-weight: 600; color: #1E2433; }
.nr-kpi .k { font-size: .8rem; color: #6B6F7B; display: flex; align-items: center; gap: .35rem; }
.nr-kpi .k i { width: .55rem; height: .55rem; border-radius: 50%; display: inline-block; }
@media (max-width: 900px) { .nr-res { grid-template-columns: 1fr; } .nr-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.nr-score { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
.nr-score .big { font-family: 'Fraunces', serif; font-size: 3rem; font-weight: 650; color: #1E2433; line-height: 1; }
.nr-score .of { color: #6B6F7B; font-size: 1.05rem; }
.nr-src { font-size: .9rem; color: #4A5163; line-height: 1.7; }
.nr-src b { color: #1E2433; font-weight: 600; }
.nr-answer { border: 1.5px dashed #B9AF98; border-radius: .6rem; padding: .7rem .9rem; background: #FFFFFF; }
.nr-answer .k { display: block; font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .1em;
  text-transform: uppercase; color: #8A7E63; margin-bottom: .25rem; }
.nr-label { font-family: 'JetBrains Mono', monospace; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase;
  color: #8A7E63; margin: 1.4rem 0 .45rem; }
.nr-evidence { border-left: 3px solid #E2C443; padding: .7rem 1rem; background: #FFFBEA; border-radius: 0 .5rem .5rem 0;
  font-size: .97rem; line-height: 1.6; color: #3C4253; }
.nr-verdict { display: flex; align-items: center; gap: .65rem; flex-wrap: wrap; margin-top: 1.1rem; padding-top: 1rem;
  border-top: 1px dashed #DCD3C1; color: #4A5163; font-size: .95rem; }
.nr-verdict .nr-pill { margin-right: 0; }
.nr-solution { margin: 0; padding-left: 1.35rem; color: #2A3040; line-height: 1.6; }
.nr-solution li { margin: .15rem 0; padding-left: .2rem; }
.nr-sympy { margin-top: .55rem; font-family: 'JetBrains Mono', monospace; font-size: .8rem; color: #2F6B4F;
  background: #EEF5F0; border: 1px solid #CFE2D6; border-radius: .45rem; padding: .35rem .65rem; display: inline-block; }
.nr-flags { margin: .8rem 0 0; padding: 0; list-style: none; display: grid; gap: .35rem; }
.nr-flags li { font-size: .86rem; color: #8A5A12; background: #FBF3E2; border: 1px solid #EBD9B4;
  border-radius: .45rem; padding: .35rem .65rem; }

/* İnceleme: soru kartı ve kaynak sayfa tek ızgarada; iki kart aynı genişlik, aynı yükseklik, aynı hizada */
.nr-pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 2rem; align-items: stretch;
  margin: 1.1rem 0 1.6rem; }
.nr-pair > .nr-exam { display: flex; flex-direction: column; }
.nr-pair > .nr-exam .nr-verdict { margin-top: auto; }
.nr-pair > .nr-exam .nr-grow { flex: 1 1 auto; min-height: 1.1rem; }
.nr-page { background: #FFFDF8; border: 1px solid #E2DAC8; border-radius: .9rem; padding: 1.5rem 1.6rem 1.3rem;
  display: flex; flex-direction: column; box-shadow: 0 1px 0 rgba(30,36,51,.04), 0 10px 28px -20px rgba(30,36,51,.4);
  animation: nr-rise .35s ease-out both; }
.nr-page-head { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.nr-page-head .doc { font-weight: 600; color: #1E2433; }
.nr-page-head .sec { color: #6B6F7B; font-size: .92rem; }
.nr-page-frame { flex: 1 1 auto; display: flex; align-items: center; justify-content: center; min-height: 300px;
  background: #EFE9DC; border-radius: .6rem; padding: 1rem; }
.nr-page-frame img { display: block; max-width: 100%; max-height: 720px; border-radius: .2rem;
  box-shadow: 0 2px 4px rgba(30,36,51,.12), 0 12px 30px -12px rgba(30,36,51,.35); background: #FFFFFF; }
.nr-page-frame .hidden { text-align: center; color: #8A7E63; font-size: .95rem; line-height: 1.6; }
.nr-page-note { margin-top: .9rem; padding-top: .8rem; border-top: 1px dashed #DCD3C1; font-size: .88rem; color: #6B6F7B; }
.nr-pager { text-align: center; }
.nr-pager .c { font-family: 'JetBrains Mono', monospace; font-size: .8rem; letter-spacing: .12em; color: #1E2433; }
.nr-pager .bar { height: 4px; background: #E7E0D0; border-radius: 99px; margin: .45rem auto .3rem; max-width: 22rem;
  overflow: hidden; }
.nr-pager .bar i { display: block; height: 100%; background: #1F3A5F; border-radius: 99px; }
.nr-pager .s { font-size: .8rem; color: #7A7468; }
@media (max-width: 1000px) { .nr-pair { grid-template-columns: minmax(0, 1fr); } }

/* Kenar çubuğu marka alanı */
.nr-brand { font-family: 'Fraunces', serif; font-size: 1.5rem; font-weight: 650; color: #EDE6D6; line-height: 1; }
.nr-brand span { background-image: linear-gradient(transparent 60%, rgba(242,214,75,.55) 60%); }
.nr-brand-sub { font-size: .8rem; color: #AFA690; margin-top: .3rem; }
section[data-testid="stSidebar"] .nr-foot { font-size: .74rem; color: #8F876F; }

/* ==== Çalışma ekranları (bilgi kartı + sınav), v3: kâğıt zemin üstünde sakin kartlar; hareket yalnızca anlam taşıyınca
   (kart döner, değerlendirilen kart yığınına gider). Figür, konfeti, süzülen ışık yok (kullanıcı kararı, 2026-10-05). ==== */
:root { --nr-ink: #1E2433; --nr-sub: #4A5163; --nr-mute: #6B6F7B; --nr-paper: #FFFDF8; --nr-edge: #E2DAC8; --nr-hair: #ECE6D8;
  --nr-shadow: 0 1px 2px rgba(30,36,51,.05), 0 12px 30px -18px rgba(30,36,51,.32); --nr-ease: cubic-bezier(.22,1,.36,1);
  --nr-good: #3B8D66; --nr-bad: #C6503A; --nr-skip: #B9AF98; --nr-accent: #3A7BB8; --nr-track: #DCE7F3; }

/* Bilgi kartı (NotebookLM gibi: önde soru, arkada cevap). Ortada ve büyük; tıklayınca 3B döner, yine tıklayınca geri.
   Her yeni kartta sarmalayıcı etiket değişir (div/section) → tarayıcı kartı sıfırdan çizer: animasyon her seferinde
   oynar, çevrilmiş kart bir sonrakine çevrili geçmez (React aynı etiketli öğeyi yeniden kullanıyordu). */
.nr-deck { position: relative; perspective: 1800px; height: 27rem; margin-top: .3rem; }
.nr-stack { position: absolute; inset: 0; border-radius: 26px; background: var(--s); box-shadow: var(--nr-shadow); }
.nr-stack.s1 { transform: translateY(14px) scale(.96); opacity: .8; }
.nr-stack.s2 { transform: translateY(28px) scale(.92); opacity: .5; }
details.nr-fc { position: absolute; inset: 0; z-index: 2; animation: nr-deal .55s .1s var(--nr-ease) both; }
details.nr-fc > summary { list-style: none; display: block; height: 100%; cursor: pointer; outline: none; }
details.nr-fc > summary::-webkit-details-marker { display: none; }
details.nr-fc > summary::marker { content: ""; }
@keyframes nr-deal { from { opacity: 0; transform: translateY(-16px) scale(.975); } to { opacity: 1; transform: none; } }
.nr-flip { position: relative; height: 100%; transform-style: preserve-3d; transition: transform .7s var(--nr-ease); }
details.nr-fc:not([open]) > summary:hover .nr-flip { transform: translateY(-3px); }
details.nr-fc[open] .nr-flip { transform: rotateY(180deg); }
.nr-face { position: absolute; inset: 0; display: flex; flex-direction: column; border-radius: 26px; overflow: hidden;
  backface-visibility: hidden; -webkit-backface-visibility: hidden; padding: 1.8rem 2.6rem 1.4rem; box-shadow: var(--nr-shadow); }
.nr-face.front { background: linear-gradient(160deg, var(--c1) 0%, var(--c2) 100%); color: var(--ink); }
.nr-face.back { transform: rotateY(180deg); background: var(--nr-paper); border: 1px solid var(--nr-edge); color: var(--nr-ink); overflow-y: auto; }
.nr-face.back::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 5px; background: var(--a); }
.nr-fc .meta { display: flex; flex-wrap: wrap; gap: .4rem; }
.nr-fc .meta span { font-size: .76rem; font-weight: 600; color: var(--ink); background: rgba(255,255,255,.6); padding: .2rem .7rem; border-radius: 999px; }
.nr-fc .body { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: .4rem 1rem; }
.nr-fc .fq { font-family: 'Fraunces', serif; font-size: 1.95rem; line-height: 1.36; font-weight: 600; max-width: 38ch; }
.nr-fc.long .fq { font-size: 1.55rem; } .nr-fc.xlong .fq { font-size: 1.28rem; }
.nr-fc .hint { text-align: center; font-size: .84rem; color: var(--ink); opacity: .72; }
.nr-fc .back .lab { font-size: .7rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--a); margin: 1.05rem 0 .3rem; }
.nr-fc .back .lab:first-child { margin-top: .3rem; }
.nr-fc .back .q2 { color: var(--nr-mute); font-size: .92rem; line-height: 1.5; }
.nr-fc .back .ans { font-family: 'Fraunces', serif; font-size: 1.7rem; font-weight: 600; line-height: 1.32; }
.nr-fc .back .nr-evidence { border-left-color: var(--a); border-radius: 0 12px 12px 0; }
.nr-fc .back .flipback { margin-top: auto; padding-top: .9rem; font-size: .8rem; color: var(--nr-mute); text-align: center; }
/* Değerlendirilen kart yığınına gider; üstünde sonuç rozeti */
.nr-ghost { position: absolute; inset: 0; z-index: 5; pointer-events: none; border-radius: 26px; padding: 1.8rem 2.6rem; overflow: hidden;
  color: var(--ink); background: linear-gradient(160deg, var(--c1), var(--c2)); font-family: 'Fraunces', serif; font-size: 1.4rem;
  display: flex; align-items: center; justify-content: center; text-align: center; box-shadow: var(--nr-shadow); }
.nr-ghost::after { content: attr(data-s); position: absolute; right: 1.5rem; top: 1.3rem; width: 3.2rem; height: 3.2rem; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font: 700 1.5rem 'Instrument Sans', sans-serif; color: #FFFFFF; background: var(--st); }
.nr-ghost.good { --st: var(--nr-good); animation: nr-fly-good .8s .08s cubic-bezier(.55,0,.7,.25) both; }
.nr-ghost.bad { --st: var(--nr-bad); animation: nr-fly-bad .8s .08s cubic-bezier(.55,0,.7,.25) both; }
.nr-ghost.skip { --st: #8A826F; animation: nr-fly-skip .8s .08s cubic-bezier(.55,0,.7,.25) both; }
@keyframes nr-fly-good { 20% { transform: translate(2%, -3%) rotate(2deg); } to { transform: translate(34%, 64%) rotate(16deg) scale(.12); opacity: 0; } }
@keyframes nr-fly-bad { 20% { transform: translate(-2%, -3%) rotate(-2deg); } to { transform: translate(-34%, 64%) rotate(-16deg) scale(.12); opacity: 0; } }
@keyframes nr-fly-skip { 20% { transform: translateY(-4%); } to { transform: translateY(66%) scale(.12); opacity: 0; } }
/* Yığınlar (göstergeler) */
.nr-piles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .8rem; margin-top: 2.3rem; }
.nr-pile { display: flex; align-items: center; gap: .7rem; min-height: 4.1rem; padding: .55rem .9rem; border-radius: 18px;
  background: var(--nr-paper); border: 1px solid var(--nr-edge); box-shadow: 0 1px 2px rgba(30,36,51,.04); }
.nr-pile .ico { flex: 0 0 auto; width: 2.3rem; height: 2.3rem; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 1.05rem; color: #FFFFFF; background: var(--pc); }
.nr-pile .n { font-family: 'Instrument Sans', sans-serif; font-size: 1.5rem; font-weight: 650; line-height: 1; color: var(--nr-ink); }
.nr-pile .l { font-size: .8rem; color: var(--nr-sub); }
.nr-pile .mini { margin-left: auto; display: flex; padding-right: .4rem; }
.nr-pile .mini b { display: block; width: 1.05rem; height: 1.45rem; border-radius: .3rem; margin-left: -.5rem; background: var(--mc);
  border: 1.5px solid var(--nr-paper); box-shadow: 0 1px 3px rgba(30,36,51,.25); }
.nr-pile .mini b:nth-child(odd) { transform: rotate(-8deg); } .nr-pile .mini b:nth-child(even) { transform: rotate(7deg); }
.nr-pile.bad { --pc: var(--nr-bad); } .nr-pile.skip { --pc: #8A826F; } .nr-pile.good { --pc: var(--nr-good); }
.nr-pile.bump { animation: nr-bump .5s .8s var(--nr-ease) both; }
@keyframes nr-bump { 40% { transform: scale(1.05); } }
/* Değerlendirme düğmeleri: yumuşak renk tonu, etiket + simge */
div.st-key-fc_bad button, div.st-key-fc_skip button, div.st-key-fc_good button { min-height: 3.4rem; border-radius: 16px;
  border: 1px solid var(--nr-edge); transition: transform .25s var(--nr-ease), background .2s ease; }
div.st-key-fc_bad button p, div.st-key-fc_skip button p, div.st-key-fc_good button p { font-size: 1.02rem; font-weight: 600; color: inherit; }
div.st-key-fc_bad button { color: #A0412D; background: #FBEFEB; } div.st-key-fc_skip button { color: #5B5444; background: #F4F0E6; }
div.st-key-fc_good button { color: #2F6B4F; background: #EEF5F0; }
div.st-key-fc_bad button:hover { background: #F6E1DA; transform: translateY(-2px); }
div.st-key-fc_skip button:hover { background: #ECE6D8; transform: translateY(-2px); }
div.st-key-fc_good button:hover { background: #E1EFE6; transform: translateY(-2px); }
.nr-gap { font-size: .8rem; color: var(--nr-mute); text-align: center; margin-top: .45rem; }
/* Üst şerit: kart sayacı, ilerleme, isabet, seri */
.nr-topbar { display: flex; align-items: center; gap: 1rem; padding: .65rem 1rem; border-radius: 16px; background: var(--nr-paper);
  border: 1px solid var(--nr-edge); }
.nr-topbar .c { font-size: .9rem; color: var(--nr-sub); white-space: nowrap; } .nr-topbar .c b { color: var(--nr-ink); }
.nr-topbar .track { flex: 1; height: 8px; border-radius: 4px; background: var(--nr-track); overflow: hidden; }
.nr-topbar .track i { display: block; height: 100%; border-radius: 4px; background: var(--nr-accent); transition: width .5s var(--nr-ease); }
.nr-topbar .chip { font-size: .82rem; color: var(--nr-sub); background: #F1ECE0; border-radius: 999px; padding: .12rem .6rem; white-space: nowrap; }
.nr-topbar .chip b { color: var(--nr-ink); }
/* Kurulum ekranı sayıları */
.nr-ctiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .8rem; margin: .2rem 0 1.1rem; }
.nr-ctile { border-radius: 18px; padding: .95rem 1.1rem; color: var(--ink); background: linear-gradient(160deg, var(--c1), var(--c2)); }
.nr-ctile .v { font-family: 'Instrument Sans', sans-serif; font-size: 2rem; font-weight: 650; line-height: 1.05; }
.nr-ctile .k { font-size: .84rem; opacity: .85; }
@media (max-width: 900px) { .nr-ctiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* Bitiş özeti (kart oturumu ve sınav sonucu ortak): tek kart — başlık, büyük sayı + durum kutucukları,
   zorluğa / soru tipine göre ölçerler, konulara göre satırlar (en çok zorlandığın önce). Tek seri → lejant yok;
   değerler hep yazılı (renk tek başına anlam taşımaz); çubuk dolgusu #3A7BB8 kâğıt zeminde 4.4:1. */
.nr-sum { background: var(--nr-paper); border: 1px solid var(--nr-edge); border-radius: 22px; box-shadow: var(--nr-shadow); padding: 1.5rem 1.8rem 1.2rem; }
.nr-sum .title { font-family: 'Fraunces', serif; font-size: 1.4rem; font-weight: 600; color: var(--nr-ink); line-height: 1.25; }
.nr-sum .note { font-size: .9rem; color: var(--nr-sub); margin: .25rem 0 1.1rem; }
.nr-sum .head { display: flex; gap: 2rem; align-items: center; flex-wrap: wrap; }
.nr-sum .hero .k { font-size: .84rem; color: var(--nr-mute); }
.nr-sum .hero .v { font-family: 'Instrument Sans', sans-serif; font-size: 3.3rem; font-weight: 650; line-height: 1; color: var(--nr-ink); letter-spacing: -.02em; }
.nr-sum .hero .d { font-size: .86rem; color: var(--nr-sub); margin-top: .35rem; }
.nr-sum .tiles { flex: 1; min-width: 300px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .6rem; }
.nr-sum .tile { border: 1px solid var(--nr-hair); border-radius: 14px; padding: .6rem .8rem; background: #FFFFFF; }
.nr-sum .tile .k { font-size: .8rem; color: var(--nr-sub); display: flex; align-items: center; gap: .4rem; }
.nr-sum .tile .k i { width: .55rem; height: .55rem; border-radius: 50%; display: inline-block; }
.nr-sum .tile .v { font-family: 'Instrument Sans', sans-serif; font-size: 1.45rem; font-weight: 650; color: var(--nr-ink); white-space: nowrap; }
.nr-sum .sec { border-top: 1px solid var(--nr-hair); margin-top: 1.15rem; padding-top: .95rem; }
.nr-sum .sec .h { display: flex; justify-content: space-between; align-items: baseline; font-family: 'Instrument Sans', sans-serif;
  font-size: .76rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--nr-mute); margin: 0 0 .7rem; }
.nr-sum .sec .h small { font-size: .78rem; font-weight: 500; letter-spacing: 0; text-transform: none; }
.nr-sum .meters { display: grid; grid-template-columns: repeat(var(--n, 3), minmax(0, 1fr)); gap: .8rem 1.6rem; }
.nr-m .t { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; }
.nr-m .nm { font-size: .92rem; color: var(--nr-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nr-m .v { font-family: 'Instrument Sans', sans-serif; font-weight: 650; font-size: 1.12rem; color: var(--nr-ink); }
.nr-m .c { font-size: .8rem; color: var(--nr-mute); font-variant-numeric: tabular-nums; }
.nr-m.none .v, .nr-m.none .nm { color: #A39B88; }
.nr-track { height: 8px; border-radius: 4px; background: var(--nr-track); overflow: hidden; margin: .35rem 0 .25rem; }
.nr-track i { display: block; height: 100%; border-radius: 4px; background: var(--nr-accent); }
.nr-tr { display: grid; grid-template-columns: minmax(0, 1fr) 32% 3rem 3.2rem; gap: .9rem; align-items: center; padding: .4rem 0;
  border-bottom: 1px solid #F3EEE3; }
.nr-tr:last-child { border-bottom: 0; }
.nr-tr .nm { display: flex; align-items: center; gap: .5rem; min-width: 0; font-size: .92rem; color: var(--nr-ink); }
.nr-tr .nm span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.nr-tr .nr-track { margin: 0; }
.nr-tr .v { text-align: right; font-weight: 650; color: var(--nr-ink); font-variant-numeric: tabular-nums; }
.nr-tr .c { text-align: right; font-size: .82rem; color: var(--nr-mute); font-variant-numeric: tabular-nums; }
.nr-weak { flex: 0 0 auto; font-size: .72rem; font-weight: 600; color: #A0412D; background: #F4E1DC; border-radius: 999px; padding: .04rem .5rem; }
.nr-sum details > summary { cursor: pointer; font-size: .86rem; color: #2C5F8F; margin-top: .55rem; list-style: none; }
.nr-sum details > summary::-webkit-details-marker { display: none; }
.nr-sum details[open] > summary { margin-bottom: .3rem; }
@media (max-width: 760px) { .nr-sum .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .nr-sum .meters { grid-template-columns: 1fr; } .nr-tr { grid-template-columns: minmax(0, 1fr) 28% 2.8rem 3rem; gap: .6rem; } }

/* Sınav ekranı: kâğıt kart, soru başına renkli ince şerit, sakin şıklar */
.nr-focus { border-radius: 22px; position: relative; overflow: hidden; }
.nr-focus::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 5px; background: var(--c, #3A7BB8); }
div.st-key-nr_opts button { border-radius: 16px; }
div.st-key-nr_opts button[kind="primary"] { background: #EEF2F8; border: 1.5px solid #1F3A5F; box-shadow: 0 0 0 3px rgba(31,58,95,.12); }
div.st-key-nr_opts button[kind="primary"] p { color: #1E2433; }

@media (prefers-reduced-motion: reduce) { .nr-fc, .nr-flip, .nr-ghost, .nr-pile { animation: none !important; transition: none !important; }
  .nr-ghost { display: none; } }
</style>
"""

# Kart renkleri (pastel): (açık, koyu pastel, yazı, vurgu). Yazı her pastelde ≥ 7:1, vurgu etiket/rozet için
PALETTE = [("#EDE9FE", "#DDD6FE", "#2E1065", "#7C3AED"),   # lavanta
           ("#CCFBF1", "#99F6E4", "#134E4A", "#0D9488"),   # nane
           ("#FFEDD5", "#FED7AA", "#7C2D12", "#EA580C"),   # şeftali
           ("#E0F2FE", "#BAE6FD", "#0C4A6E", "#0284C7"),   # gök
           ("#FCE7F3", "#FBCFE8", "#831843", "#DB2777"),   # gül
           ("#FEF9C3", "#FDE68A", "#713F12", "#CA8A04")]   # tereyağı


def color(i: int) -> tuple[str, str, str, str]:
    return PALETTE[i % len(PALETTE)]


def color_vars(i: int) -> str:
    c1, c2, ink, a = color(i)
    return f"--c1:{c1};--c2:{c2};--ink:{ink};--a:{a};--c:{a};--glow:{a}66"


def inject() -> None:
    # st.html içeriği ana sayfanın stillerinden yalıtılıyor (sınıflar uygulanmıyordu: 'CEVAPDoğru' gibi yapışık
    # metinler). Stil ve HTML bloklarını st.markdown(unsafe_allow_html) ile basmak sınıfları ana belgeye bağlar.
    html(_CSS)


def html(markup: str) -> None:
    """HTML bloğunu ana belgeye bas (boş satır içermemeli; Markdown HTML bloğunu orada keser).
    lang="tr": CSS büyük harf dönüşümü Türkçe kuralla yapılsın ('ipucu' → 'İPUCU', 'IPUCU' değil)."""
    markup = re.sub(r"\n\s*\n", "\n", markup)
    st.markdown(markup if markup.lstrip().startswith("<style") else f'<div lang="tr">{markup}</div>',
                unsafe_allow_html=True)


def esc(s: object) -> str:
    return _html.escape(str(s))


def header(kicker: str, title: str, lead: str = "", hero_word: str | None = None) -> None:
    """Sayfa başlığı. hero_word verilirse başlıktaki o kelime fosforlu kalemle 'çizilir'."""
    t = esc(title)
    if hero_word and hero_word in title:
        t = t.replace(esc(hero_word), f'<span class="nr-hero-hl">{esc(hero_word)}</span>', 1)
    lead_html = f'<p class="nr-lead">{esc(lead)}</p>' if lead else ""
    html(f'<div class="nr-kicker">{esc(kicker)}</div><h1 class="nr-title">{t}</h1>{lead_html}<hr class="nr-rule">')


def pill(label: str) -> str:
    name, fg, bg = STATUS.get(label, (label, "#4A5163", "#ECE7DC"))
    return f'<span class="nr-pill" style="color:{fg};background:{bg}">{esc(name)}</span>'


def card(title: str, body: str, meta: str = "", delay: float = 0.0) -> str:
    m = f'<div class="nr-meta">{esc(meta)}</div>' if meta else ""
    return f'<div class="nr-card" style="animation-delay:{delay:.2f}s"><h4>{esc(title)}</h4><p>{body}</p>{m}</div>'


def flow(steps: list[tuple[str, str, str]]) -> None:
    """Akış şeması: [(başlık, değer, açıklama), ...]"""
    cells = "".join(
        f'<div class="nr-step" style="animation-delay:{i * .07:.2f}s"><div class="n">{i + 1:02d}</div>'
        f'<div class="t">{esc(t)}</div><div class="v">{esc(v)}</div><div class="d">{esc(d)}</div></div>'
        for i, (t, v, d) in enumerate(steps))
    html(f'<div class="nr-flow">{cells}</div>')

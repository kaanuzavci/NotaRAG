"""Giriş ekranının görselleri (src/ui/auth.py): arka plandaki "not → makine → soru → beyin" ağı ve sol paneldeki
çalışma akışı. Hepsi satır içi SVG + CSS: dış kütüphane ya da internet gerekmez, çizim tarayıcıda hazır.

Arka plan tek bir SVG (viewBox 1600×1000, pencereyi "slice" ile doldurur; x=800 hep pencerenin ortasına düşer):
  sol yarı koyu lacivert (bilgi paneli), solda not yaprakları → dallar ortadaki makineye (dönen halka) akar →
  sağda soru kartlarına ayrılır → sağ üstte ve altta bilgi ağına ("beyin": iki lobda düğümler) bağlanır.
Dallarda kesik çizgiler akar, birkaç dalda ışık noktası gider (SMIL animateMotion). Hareket çok yavaş ve soluk: içerik
okunurken göz yormasın; prefers-reduced-motion'da durur.
"""

from __future__ import annotations

import math
import random

SEAM = (800, 500)  # makine: iki yarının birleştiği yer


def _curve(a: tuple[float, float], b: tuple[float, float], bend: float = .45) -> str:
    (x1, y1), (x2, y2) = a, b
    dx = (x2 - x1) * bend
    return f"M{x1:.0f} {y1:.0f} C{x1 + dx:.0f} {y1:.0f} {x2 - dx:.0f} {y2:.0f} {x2:.0f} {y2:.0f}"


def _note(x: float, y: float, s: float = 1, rot: float = 0) -> str:
    """Not yaprağı: köşesi kıvrık kâğıt + satırlar."""
    return (f'<g transform="translate({x:.0f} {y:.0f}) rotate({rot}) scale({s})" class="nt">'
            '<path d="M-22 -28 h32 l12 12 v44 h-44 z" />'
            '<path d="M10 -28 v12 h12" class="fold"/>'
            '<path d="M-14 -10 h26 M-14 -2 h28 M-14 6 h22 M-14 14 h26" class="ln"/></g>')


def _qcard(x: float, y: float, s: float = 1) -> str:
    """Soru kartı: başlık, iki satır, onay işareti."""
    return (f'<g transform="translate({x:.0f} {y:.0f}) scale({s})" class="qc">'
            '<rect x="-34" y="-22" width="68" height="44" rx="8"/>'
            '<path d="M-24 -10 h30 M-24 -1 h40 M-24 8 h24" class="ln"/>'
            '<circle cx="22" cy="10" r="6" class="ok"/><path d="M19 10 l2 2 l4 -4" class="tick"/></g>')


def _brain(cx: float, cy: float, r: float, seed: int) -> tuple[str, list[tuple[float, float]]]:
    """Bilgi ağı: iki lob biçiminde dağılmış düğümler, yakın komşular arası kenarlar."""
    rnd = random.Random(seed)
    pts = []
    for lobe in (-1, 1):
        for _ in range(16):
            a, d = rnd.uniform(0, 2 * math.pi), r * math.sqrt(rnd.uniform(.05, 1))
            pts.append((cx + lobe * r * .55 + d * .75 * math.cos(a), cy + d * .62 * math.sin(a)))
    edges = set()
    for i, p in enumerate(pts):
        near = sorted(range(len(pts)), key=lambda j: (pts[j][0] - p[0]) ** 2 + (pts[j][1] - p[1]) ** 2)[1:4]
        edges.update(tuple(sorted((i, j))) for j in near)
    lines = "".join(f'<path d="M{pts[i][0]:.0f} {pts[i][1]:.0f} L{pts[j][0]:.0f} {pts[j][1]:.0f}"/>' for i, j in edges)
    dots = "".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.choice((2.5, 3.5, 4.5))}" style="animation-delay:{rnd.uniform(0, 6):.1f}s"/>'
                   for x, y in pts)
    return f'<g class="br"><g class="be">{lines}</g><g class="bn">{dots}</g></g>', pts


def background() -> str:
    # yazıların üstüne binmesin: sol panelin kenarlarına (üst şerit, alt şerit, makinenin yanı)
    notes = [(470, 70, -6), (690, 210, 6), (730, 640, 5), (740, 820, -5), (300, 60, 4), (640, 20, -3)]
    qcards = [(1530, 320), (1540, 650), (1500, 500), (880, 955), (1470, 860)]  # formun durduğu orta alanın dışında
    brain_a, pts_a = _brain(1360, 150, 120, 7)
    brain_b, pts_b = _brain(1330, 990, 110, 11)
    left = [_curve((x + 24, y), SEAM) for x, y, _ in notes]
    right = [_curve(SEAM, q) for q in qcards]
    up = [_curve((1530, 320), pts_a[3], .5), _curve((1500, 500), pts_a[20], .5), _curve((1540, 650), pts_b[5], .5),
          _curve((1470, 860), pts_b[22], .5)]
    paths = "".join(f'<path id="lgp{i}" d="{d}" class="fl {"l" if i < len(left) else "r"}"/>'
                    for i, d in enumerate(left + right + up))
    # birkaç dalda ilerleyen ışık noktası (notlardan makineye, makineden sorulara, sorulardan beyne)
    movers = "".join(
        f'<circle r="3.2" class="mv {"l" if i < len(left) else "r"}"><animateMotion dur="{dur}s" begin="{beg}s" '
        f'repeatCount="indefinite" rotate="auto"><mpath href="#lgp{i}"/></animateMotion></circle>'
        for i, dur, beg in ((0, 7, 0), (2, 8, 2.5), (4, 7.5, 1), (6, 9, 4), (7, 6, .5), (8, 6.5, 3), (10, 7, 1.5),
                            (12, 6, 2), (13, 6.5, 4.5), (14, 7, .8)))
    engine = (f'<g transform="translate({SEAM[0]} {SEAM[1]})" class="en">'
              '<circle r="58" class="halo"/><circle r="40" class="ring"/><circle r="27" class="core"/>'
              '<path d="M-9 -9 h18 v18 h-18 z M-14 -4 h5 M-14 4 h5 M9 -4 h5 M9 4 h5 M-4 -14 v5 M4 -14 v5 M-4 9 v5 M4 9 v5" class="chip"/></g>')
    return ('<div class="lg-bg" aria-hidden="true"><svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" '
            'xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="lgdark" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#25304A"/><stop offset="1" stop-color="#171C29"/></linearGradient>'
            '<radialGradient id="lgcalm" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#F7F4ED" stop-opacity="1"/>'
            '<stop offset=".62" stop-color="#F7F4ED" stop-opacity=".92"/><stop offset="1" stop-color="#F7F4ED" stop-opacity="0"/></radialGradient>'
            '<pattern id="lgdots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#1F3A5F" opacity=".09"/></pattern></defs>'
            '<rect x="800" y="-50" width="900" height="1100" fill="url(#lgdots)"/>'
            '<rect x="-100" y="-50" width="900" height="1100" fill="url(#lgdark)"/>'
            f'{paths}{brain_a}{brain_b}{"".join(_note(x, y, 1.15, r) for x, y, r in notes)}'
            f'{"".join(_qcard(x, y) for x, y in qcards)}{movers}'
            '<ellipse cx="1200" cy="500" rx="330" ry="420" fill="url(#lgcalm)"/>'  # formun arkası sakin
            f'{engine}</svg></div>')


BG_CSS = """
.lg-bg { position: fixed; inset: 0; z-index: -1; pointer-events: none; }
.lg-bg svg { width: 100%; height: 100%; display: block; }
.lg-bg .fl { fill: none; stroke-width: 1.4; stroke-dasharray: 3 9; animation: lg-flow 2.6s linear infinite; }
.lg-bg .fl.l { stroke: #8FA3C8; opacity: .3; }
.lg-bg .fl.r { stroke: #1F3A5F; opacity: .22; }
@keyframes lg-flow { to { stroke-dashoffset: -24; } }
.lg-bg .mv.l { fill: #F2D64B; opacity: .9; } .lg-bg .mv.r { fill: #3A7BB8; opacity: .6; }
.lg-bg .nt path { fill: #F7F4ED; fill-opacity: .05; stroke: #C9D3E6; stroke-opacity: .32; stroke-width: 1.3; stroke-linejoin: round; }
.lg-bg .nt .ln { fill: none; stroke-opacity: .35; } .lg-bg .nt .fold { fill: none; }
.lg-bg .qc rect { fill: #FFFDF8; stroke: #1F3A5F; stroke-opacity: .25; stroke-width: 1.2; }
.lg-bg .qc .ln { stroke: #1F3A5F; stroke-opacity: .25; stroke-width: 2; stroke-linecap: round; fill: none; }
.lg-bg .qc .ok { fill: #3B8D66; fill-opacity: .55; } .lg-bg .qc .tick { stroke: #FFFFFF; stroke-width: 1.6; fill: none; }
.lg-bg .be path { stroke: #1F3A5F; stroke-opacity: .16; stroke-width: 1; }
.lg-bg .bn circle { fill: #3A7BB8; opacity: .35; animation: lg-pulse 6s ease-in-out infinite; }
@keyframes lg-pulse { 50% { opacity: .75; } }
.lg-bg .en .halo { fill: #F2D64B; opacity: .10; } .lg-bg .en .core { fill: #1E2433; stroke: #F2D64B; stroke-width: 2; }
.lg-bg .en .ring { fill: none; stroke: #F2D64B; stroke-width: 2; stroke-dasharray: 6 8; opacity: .8;
  transform-box: fill-box; transform-origin: center; animation: lg-spin 14s linear infinite; }
.lg-bg .en .chip { fill: none; stroke: #F2D64B; stroke-width: 1.8; stroke-linecap: round; }
@keyframes lg-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .lg-bg * { animation: none !important; } .lg-bg .mv { display: none; } }
"""


# ---------------------------------------------------------------- sol panel: çalışma akışı

_PDF = ('<svg viewBox="0 0 120 80"><rect x="34" y="6" width="50" height="66" rx="5" fill="#FFFDF8"/>'
        '<path d="M42 22 h34 M42 30 h30 M42 38 h34 M42 46 h22 M42 54 h30" stroke="#B9AF98" stroke-width="3" stroke-linecap="round"/>'
        '<rect x="26" y="52" width="26" height="14" rx="3" fill="#C6503A"/><text x="39" y="62.5" font-size="8.5" font-weight="700" '
        'fill="#FFFFFF" text-anchor="middle" font-family="Instrument Sans, sans-serif">PDF</text>'
        '<circle cx="92" cy="18" r="9" fill="#F2D64B"/><path d="M88 18 l3 3 l5 -6" stroke="#1E2433" stroke-width="2" fill="none"/></svg>')
_QUESTION = ('<svg viewBox="0 0 120 80"><rect x="12" y="8" width="96" height="64" rx="8" fill="#FFFDF8"/>'
             '<rect x="20" y="16" width="20" height="9" rx="3" fill="#1E2433"/><text x="30" y="23" font-size="6.5" fill="#FFFDF8" '
             'text-anchor="middle" font-family="JetBrains Mono, monospace">S1</text>'
             '<path d="M20 34 h64 M20 42 h52" stroke="#4A5163" stroke-width="3" stroke-linecap="round"/>'
             '<rect x="18" y="50" width="70" height="10" rx="3" fill="#F2D64B" opacity=".75"/>'
             '<path d="M22 55 h56" stroke="#7A6F57" stroke-width="2.5" stroke-linecap="round"/>'
             '<circle cx="98" cy="60" r="8" fill="#3B8D66"/><path d="M94 60 l3 3 l5 -6" stroke="#FFFFFF" stroke-width="2" fill="none"/></svg>')
_STUDY = ('<svg viewBox="0 0 120 80"><rect x="14" y="20" width="40" height="52" rx="6" fill="#DDD6FE" transform="rotate(-10 34 46)"/>'
          '<rect x="22" y="16" width="40" height="52" rx="6" fill="#99F6E4" transform="rotate(-2 42 42)"/>'
          '<rect x="30" y="14" width="40" height="52" rx="6" fill="#FED7AA" transform="rotate(7 50 40)"/>'
          '<circle cx="92" cy="40" r="20" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="7"/>'
          '<circle cx="92" cy="40" r="20" fill="none" stroke="#F2D64B" stroke-width="7" stroke-dasharray="103 126" '
          'transform="rotate(-90 92 40)" stroke-linecap="round"/><text x="92" y="44" font-size="11" font-weight="700" '
          'fill="#FFFFFF" text-anchor="middle" font-family="Instrument Sans, sans-serif">%82</text></svg>')
_ARROW = '<svg viewBox="0 0 24 24" class="ar"><path d="M16.2 13H4v-2h12.2l-5.6-5.6L12 4l8 8-8 8-1.4-1.4Z"/></svg>'
_MARK = ('<svg viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#F2D64B"/>'
         '<path d="M9 8 h10 l5 5 v11 h-15 z" fill="#1E2433"/><path d="M12 15 h9 M12 19 h7" stroke="#F2D64B" stroke-width="2" '
         'stroke-linecap="round"/></svg>')
_USER = ('<svg viewBox="0 0 24 24"><path d="M12 12q-1.6 0-2.8-1.2T8 8t1.2-2.8T12 4t2.8 1.2T16 8t-1.2 2.8T12 12Zm-8 8v-2.8q0-.9'
         '.4-1.6t1.2-1.1q1.5-.8 3.1-1.1T12 13t3.3.4 3.1 1.1q.8.4 1.2 1.1t.4 1.6V20Z"/></svg>')
_GLOBE = ('<svg viewBox="0 0 24 24"><path d="M12 22q-2.1 0-3.9-.8t-3.2-2.1q-1.4-1.4-2.1-3.2T2 12q0-2.1.8-3.9t2.1-3.2Q6.3 3.5 8.1 '
          '2.8T12 2q2.1 0 3.9.8t3.2 2.1q1.4 1.4 2.1 3.2T22 12q0 2.1-.8 3.9t-2.1 3.2q-1.4 1.4-3.2 2.1T12 22Zm-1-2.1V18q-.8 0-1.4-.6T9 '
          '16v-1l-4.8-4.8q-.1.5-.1.9V12q0 3 2 5.3t4.9 2.6Zm6.9-2.5q1-1.1 1.6-2.5T20 12q0-2.5-1.4-4.5T15 4.6V5q0 .8-.6 1.4T13 7h-2v2'
          'q0 .4-.3.7T10 10H8v2h6q.4 0 .7.3t.3.7v3h1q.7 0 1.2.4t.7 1Z"/></svg>')


def brand() -> str:
    steps = ((_PDF, "1 · Notunu yükle", "PDF okunur, konulara ve sayfalara ayrılır."),
             (_QUESTION, "2 · Sorular üretilir", "Her cevap notundaki cümleye bağlanır, ikinci bir model doğrular."),
             (_STUDY, "3 · Çalış", "Sınav çöz, kart çevir, A4 / A3 sınav kâğıdı indir."))
    flow = _ARROW.join(f'<div class="st"><div class="ill">{svg}</div><b>{t}</b><span>{d}</span></div>' for svg, t, d in steps)
    return ('<div class="lg-left">'
            f'<div class="lg-logo">{_MARK}<span>NotaRAG</span></div>'
            '<div class="lg-body"><div class="lg-head"><div class="lg-eyebrow">Ders notundan sınava</div>'
            '<h1>Notunu yükle,<br>sınavın hazır olsun.</h1>'
            '<p class="lead">Ders notlarından kanıta dayalı sorular ve cevaplar: hangi cevabın notunun hangi sayfasından '
            'geldiğini her zaman görürsün.</p></div>'
            f'<div class="lg-rest"><div class="lg-flow">{flow}</div>'
            '<div class="lg-feats">'
            f'<div><i>{_USER}</i><p><b>Sana özel çalışma</b>Zayıf konularından sınav, bilemediğin kartlar daha sık, '
            'beyin analizinde hangi konuyu öğrendiğin.</p></div>'
            f'<div><i>{_GLOBE}</i><p><b>Herkese açık notlar</b>Arkadaşlarının paylaştığı notları kendi listene ekle, '
            'hazır sorularıyla hemen çalış; kendi notunu da paylaşabilirsin.</p></div></div></div></div>'
            '</div>')


BRAND_CSS = """
.lg-left { height: 100vh; box-sizing: border-box; display: flex; flex-direction: column; padding: 5.5vh 4.5vw 5vh;
  color: #E4E8F0; overflow: hidden; }
.lg-logo { flex: none; display: flex; align-items: center; gap: .65rem; font: 650 1.45rem/1 'Fraunces', serif; color: #FFFDF8; }
.lg-logo svg { width: 34px; height: 34px; }
/* Başlık grubu ve akış/özellikler birbirine yakın, ikisi birlikte logonun altındaki alanın ortasında (kullanıcı isteği:
   yazılar bir tık aşağı, alttakiler bir tık yukarı; arada çok boşluk vardı) */
.lg-body { flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; gap: 5.5vh; max-width: 680px; }
.lg-head { flex: none; }
.lg-rest { flex: none; }
.lg-eyebrow { font: 500 .74rem 'JetBrains Mono', monospace; letter-spacing: .16em; text-transform: uppercase; color: #F2D64B; }
.lg-left h1 { font: 650 clamp(1.9rem, min(3.1vw, 5.6vh), 2.9rem)/1.12 'Fraunces', serif !important; color: #FFFFFF !important;
  margin: .55rem 0 .8rem !important; padding: 0 !important; letter-spacing: -.01em; }
.lg-left .lead { font-size: 1.02rem; line-height: 1.6; color: #C3CBDA; margin: 0; max-width: 46ch; }
.lg-flow { display: grid; grid-template-columns: 1fr 22px 1fr 22px 1fr; gap: .6rem; align-items: start; margin-bottom: 3vh; }
.lg-flow .st { background: rgba(255, 255, 255, .055); border: 1px solid rgba(255, 255, 255, .11); border-radius: 16px;
  padding: .7rem .75rem .85rem; backdrop-filter: none; }
.lg-flow .ill { background: rgba(255, 255, 255, .06); border-radius: 11px; margin-bottom: .6rem; display: flex; justify-content: center; }
.lg-flow .ill svg { display: block; width: 100%; height: auto; max-height: 13vh; }
.lg-flow b { display: block; font-size: .9rem; color: #FFFFFF; margin-bottom: .2rem; }
.lg-flow span { display: block; font-size: .78rem; line-height: 1.4; color: #AEB8CB; }
.lg-flow .ar { width: 22px; height: 22px; fill: #F2D64B; opacity: .8; margin-top: 5vh; }
.lg-feats { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.lg-feats > div { display: flex; gap: .75rem; align-items: flex-start; }
.lg-feats i { flex: none; width: 2.3rem; height: 2.3rem; border-radius: 12px; background: rgba(242, 214, 75, .14);
  display: grid; place-items: center; }
.lg-feats i svg { width: 20px; height: 20px; fill: #F2D64B; }
.lg-feats p { margin: 0; font-size: .84rem; line-height: 1.5; color: #AEB8CB; }
.lg-feats b { display: block; color: #FFFFFF; font-size: .93rem; margin-bottom: .15rem; }
@media (max-width: 1100px) { .lg-flow { grid-template-columns: 1fr; } .lg-flow .ar { display: none; }
  .lg-flow .st { display: grid; grid-template-columns: 110px 1fr; column-gap: .8rem; } .lg-flow .ill { grid-row: span 2; margin: 0; } }
"""

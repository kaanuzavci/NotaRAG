"""Çalışma koçu Fosfor: yan sütunda yapışkan cam panel — animasyonlu avatar, sohbet balonu, küçük istatistik, hızlı eylemler.

Avatar Google'ın Noto animasyonlu emojileri (Lottie, CC BY 4.0) + lottie-web oynatıcısı; ikisi de src/ui/assets altında
yerel (internetsiz çalışır, lisanslar assets/LICENSES.md). Ruh hâli emojiyi seçer:
hello 👋 · happy 😊 · cheer 🤩 · think 🤔 · sad 💪 (cesaretlendirir) · fire 🔥 (seri) · party 🎉 (bitiş).
Kutlama: canvas-confetti (yerel) ana sayfada bir tuval açıp konfeti atar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

from src.ui import style

ASSETS = Path(__file__).parent / "assets"
MOODS = {"hello", "happy", "cheer", "think", "sad", "fire", "party"}


@st.cache_resource
def _asset(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


def avatar(mood: str, status: str = "Çalışma koçun", size: int = 72) -> None:
    """Animasyonlu avatar + ad. İçerik yalnızca ruh hâli değişince değişir → çerçeve gereksiz yere yeniden yüklenmez."""
    mood = mood if mood in MOODS else "happy"
    st.iframe(f"""<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="light"><style>
html, body {{ margin: 0; background: transparent; overflow: hidden; font-family: 'Instrument Sans', 'Segoe UI', system-ui, sans-serif; }}
.row {{ display: flex; align-items: center; gap: 12px; height: {size}px; }}
#a {{ width: {size}px; height: {size}px; flex: 0 0 auto; }}
.n {{ font: 600 18px Georgia, 'Times New Roman', serif; color: #1E1B4B; letter-spacing: -.01em; }}
.s {{ font-size: 12.5px; color: #6B7280; margin-top: 3px; }}
.dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #34D399; margin-right: 6px;
  box-shadow: 0 0 0 3px rgba(52,211,153,.22); vertical-align: 1px; }}
</style></head><body><div class="row"><div id="a"></div><div><div class="n">Fosfor</div>
<div class="s"><span class="dot"></span>{style.esc(status)}</div></div></div>
<script>{_asset("lottie_light.min.js")}</script>
<script>
const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const anim = lottie.loadAnimation({{container: document.getElementById('a'), renderer: 'svg', loop: !still, autoplay: !still,
  animationData: {_asset(f"emoji/{mood}.json")}}});
if (still) anim.goToAndStop(0, true);
</script></body></html>""", height=size + 4)


def panel(mood: str, text: str, actions: list[tuple[str, str, Callable, tuple]] | None = None, stats: str = "",
          status: str = "Çalışma koçun", nonce: str = "", key: str = "nr_coach") -> None:
    """Koç paneli (çağıran bir sütunun içinde çağırır). text: HTML (çağıran kaçışlar). stats: hazır HTML.
    actions: [(etiket, ikon, fonksiyon, argümanlar)]. nonce: söz değişince balon yeniden belirsin."""
    with st.container(key=key):
        avatar(mood, status)
        style.html(f'<div class="nr-say" data-n="{style.esc(nonce)}">{text}</div>{stats}')
        if actions:
            style.html('<div class="nr-acts-h">Hızlı eylemler</div>')
        for i, (label, icon, fn, args) in enumerate(actions or []):
            st.button(label, icon=icon, key=f"{key}_a{i}", on_click=fn, args=args, width="stretch")


def stats(items: list[tuple[str, str]]) -> str:
    """Panelin altındaki küçük sayılar: [(değer, etiket)] (en çok 3)."""
    return '<div class="nr-cstats">' + "".join(f"<div><b>{style.esc(v)}</b><span>{style.esc(k)}</span></div>"
                                               for v, k in items[:3]) + "</div>"


def celebrate(key: str = "nr_party") -> None:
    """Konfeti: ana sayfada tıklamayı engellemeyen bir tuval açar, üç dalga atar (yerel canvas-confetti)."""
    with st.container(key=key):
        style.html(f"<style>.st-key-{key} {{ height: 0; overflow: hidden; margin: 0; }}</style>")
        st.iframe(f"""<body style="margin:0"><script>{_asset("confetti.min.js")}</script><script>
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {{
  const D = window.parent.document;
  let c = D.getElementById('nr-confetti');
  if (!c) {{ c = D.createElement('canvas'); c.id = 'nr-confetti';
    Object.assign(c.style, {{position: 'fixed', inset: '0', width: '100vw', height: '100vh', pointerEvents: 'none', zIndex: 9999}});
    D.body.appendChild(c); }}
  const fire = confetti.create(c, {{resize: true, useWorker: false}});
  const colors = ['#A78BFA', '#60A5FA', '#34D399', '#FBBF24', '#F472B6', '#FB923C'];
  fire({{particleCount: 110, spread: 80, startVelocity: 42, origin: {{y: .62}}, colors, scalar: 1.05}});
  setTimeout(() => fire({{particleCount: 70, angle: 60, spread: 62, origin: {{x: 0, y: .7}}, colors}}), 260);
  setTimeout(() => fire({{particleCount: 70, angle: 120, spread: 62, origin: {{x: 1, y: .7}}, colors}}), 420);
}}
</script></body>""", height=1)

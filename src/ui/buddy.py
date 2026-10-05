"""Yönlendirici figür: gözlü, kollu bir fosforlu kalem (sistemin imzası kanıtı fosforlu kalemle işaretlemek).

Ekranın sağ altında sabit durur; sohbet balonuyla durumu söyler ve hızlı menüyü taşır. Ruh hâli yüzünü ve kollarını
değiştirir: happy (gülümser, el sallar) · cheer (kollar havada, yıldızlar) · sad (cesaretlendirir) ·
think (düşünür) · calm (nötr). Çizim tamamen SVG + CSS (src/ui/style.py: .nr-buddy); dosya, ağ, GPU yok.
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

from src.ui import style

INK, BODY, CAP = "#1E2433", "#FFC53D", "#2A3246"

_MOUTH = {
    "happy": f'<path d="M50 93 Q60 103 70 93" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>',
    "cheer": f'<path d="M49 91 Q60 109 71 91 Z" fill="{INK}"/><path d="M54 99 Q60 104 66 99" fill="#FF7A8A"/>',
    "sad": f'<path d="M51 99 Q60 92 69 99" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>',
    "think": f'<path d="M52 96 L68 93" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>',
    "calm": f'<path d="M53 94 Q60 99 67 94" fill="none" stroke="{INK}" stroke-width="3" stroke-linecap="round"/>',
}
# Kollar: sol sabit, sağ ruh hâline göre (cheer: ikisi de havada)
_ARMS = {
    "cheer": ("M33 82 Q18 70 16 54", "M87 82 Q102 70 104 54"),
    "happy": ("M33 86 Q20 92 17 104", "M87 82 Q101 74 105 60"),
    "sad": ("M33 88 Q22 98 22 110", "M87 88 Q98 98 98 110"),
    "think": ("M33 86 Q20 92 17 104", "M87 88 Q100 84 74 98"),
    "calm": ("M33 86 Q20 92 17 104", "M87 86 Q100 92 103 104"),
}


def svg(mood: str = "calm") -> str:
    mood = mood if mood in _MOUTH else "calm"
    left, right = _ARMS[mood]
    look = 2 if mood == "think" else 0  # düşünürken yukarı-sağa bakar
    brows = (f'<path d="M43 58 L55 62" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>'
             f'<path d="M77 58 L65 62" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>') if mood == "sad" else ""
    stars = ('<g class="stars"><path d="M14 30 l3 7 7 1-5 5 1 7-6-4-6 4 1-7-5-5 7-1z" fill="#14B8A6"/>'
             '<path d="M100 22 l2.4 5.6 5.6.8-4 4 .8 5.6-4.8-3.2-4.8 3.2.8-5.6-4-4 5.6-.8z" fill="#EC4899"/>'
             '<circle cx="106" cy="44" r="3" fill="#8B5CF6"/><circle cx="10" cy="50" r="2.5" fill="#F97316"/></g>'
             ) if mood == "cheer" else ""
    qmark = (f'<text x="96" y="34" font-family="Fraunces, serif" font-size="22" font-weight="700" fill="#8B5CF6">?</text>'
             if mood == "think" else "")
    return f"""<svg class="nr-pen" viewBox="0 0 120 150" width="112" height="140" role="img" aria-label="Fosforlu kalem">
<ellipse class="swipe" cx="60" cy="140" rx="46" ry="7" fill="{BODY}" opacity=".45"/>
<g class="bob">{stars}{qmark}
<path class="arm" d="{left}" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
<path class="arm wave" d="{right}" fill="none" stroke="{INK}" stroke-width="4" stroke-linecap="round"/>
<rect x="38" y="12" width="44" height="30" rx="10" fill="{CAP}" stroke="{INK}" stroke-width="3"/>
<rect x="72" y="16" width="6" height="22" rx="3" fill="#4A5570"/>
<rect x="32" y="36" width="56" height="88" rx="17" fill="{BODY}" stroke="{INK}" stroke-width="3"/>
<rect x="39" y="44" width="8" height="70" rx="4" fill="#FFE49A"/>
<rect x="32" y="108" width="56" height="9" fill="{CAP}" opacity=".9"/>
{brows}
<g class="eyes"><ellipse cx="50" cy="73" rx="7.5" ry="8.5" fill="#FFFFFF" stroke="{INK}" stroke-width="2.5"/>
<ellipse cx="70" cy="73" rx="7.5" ry="8.5" fill="#FFFFFF" stroke="{INK}" stroke-width="2.5"/>
<circle cx="{51 + look}" cy="{74 - look}" r="3.6" fill="{INK}"/><circle cx="{71 + look}" cy="{74 - look}" r="3.6" fill="{INK}"/>
<circle cx="{52 + look}" cy="{72.5 - look}" r="1.2" fill="#FFFFFF"/><circle cx="{72 + look}" cy="{72.5 - look}" r="1.2" fill="#FFFFFF"/></g>
<circle cx="42" cy="86" r="4.5" fill="#FF8FA3" opacity=".55"/><circle cx="78" cy="86" r="4.5" fill="#FF8FA3" opacity=".55"/>
{_MOUTH[mood]}
<ellipse cx="48" cy="128" rx="9" ry="4.5" fill="{INK}"/><ellipse cx="72" cy="128" rx="9" ry="4.5" fill="{INK}"/>
</g></svg>"""


def show(mood: str, text: str, menu: list[tuple[str, str, Callable, tuple]] | None = None,
         key: str = "nr_buddy", nonce: str = "") -> None:
    """Figürü sağ altta göster. text: HTML (çağıran kaçışlar). menu: [(etiket, ikon, fonksiyon, argümanlar)].
    nonce: söz değişince balon yeniden "pop" etsin diye (aynı söz her yeniden çizimde zıplamaz)."""
    with st.container(key=key):
        style.html(f'<div class="nr-buddy {mood}" data-n="{style.esc(nonce)}"><div class="nr-bubble">{text}</div>'
                   f'{svg(mood)}</div>')
        for i, (label, icon, fn, args) in enumerate(menu or []):
            st.button(label, icon=icon, key=f"{key}_m{i}", on_click=fn, args=args, width="stretch")

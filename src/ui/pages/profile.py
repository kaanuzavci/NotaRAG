"""Profil ve beyin analizi.

Üstte profil (resim, ad, tanıtım; düzenle penceresi), altında beyin analizi (src/mastery.py; LLM yok, yalnızca kişinin
kendi kayıtları): bildiğin soru sayısı, bellek (kart kutuları: kısa süreli → uzun süreli), son 14 gün, notlarının
konu haritası (her konu bir kutu: başlanmadı / zayıf / çalışılıyor / öğrenildi) ve zayıf konulardan tek tıkla sınav.

Renkler (dataviz kuralı): konu durumu bir "durum" kodlamasıdır; renk tek başına anlam taşımaz, her kutuda simge ve
sayı, üstte açıklamalı lejant var. Bellek ve etkinlik sıralı (tek ton, açıktan koyuya). Durum renkleri kâğıt zeminde
doğrulayıcıyla denendi (normal görüşte en yakın çift ΔE 20, renk körlüğünde 12).
"""

import time

import streamlit as st

from src import accounts
from src import request as R
from src.ui import data, style

STATUS = style.MASTERY  # durum → (renk, simge, açıklama); not penceresinin konu listesiyle ortak
MEMORY = [("kısa", "Kısa süreli", "#C7D3E6", "yeni ya da yakında yeniden gelecek"),
          ("pekişiyor", "Pekişiyor", "#7C98C2", "birkaç kez bildin"),
          ("uzun", "Uzun süreli", "#1F3A5F", "haftalar arayla bile hatırlıyorsun")]
ACTIVITY = [(0, "#ECE6D8"), (1, "#C7D3E6"), (5, "#7C98C2"), (15, "#1F3A5F")]

_CSS = """<style>
.nr-prof { display: flex; align-items: center; gap: 24px; padding: 6px 0 4px; }
.nr-prof h1 { font-family: 'Fraunces', serif; font-weight: 650; font-size: 2.1rem; margin: 0; padding: 0; color: #1E2433; }
.nr-prof .u { font-family: 'JetBrains Mono', monospace; font-size: .76rem; color: #7A6F57; margin-top: .25rem; }
.nr-prof .a { color: #4A5163; margin-top: .4rem; font-size: .98rem; }
.nr-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 1.2rem 0 .4rem; }
.nr-stat { background: #FFFDF8; border: 1px solid #E4DCC9; border-radius: 16px; padding: 14px 16px; }
.nr-stat .l { font-size: .8rem; color: #5B5F6B; }
.nr-stat .v { font-weight: 650; font-size: 1.6rem; color: #1E2433; margin-top: 2px; }
.nr-stat .d { font-size: .74rem; color: #8A7E63; }
.nr-brain { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 16px; margin-top: .6rem; }
.nr-panel { background: #FFFDF8; border: 1px solid #E4DCC9; border-radius: 18px; padding: 18px 20px; }
.nr-panel h3 { font-family: 'Fraunces', serif; font-size: 1.08rem; margin: 0 0 .2rem; padding: 0; color: #1E2433; }
.nr-panel .s { color: #6B6F7B; font-size: .82rem; margin-bottom: .8rem; }
.nr-hero { font-weight: 650; font-size: 3.2rem; line-height: 1; color: #1E2433; }
.nr-hero small { font-size: 1.1rem; font-weight: 500; color: #6B6F7B; margin-left: 6px; }
.nr-mem { display: flex; height: 14px; border-radius: 7px; overflow: hidden; gap: 2px; background: #FFFDF8; margin: .9rem 0 .7rem; }
.nr-mem i { display: block; height: 100%; border-radius: 4px; }
.nr-memleg { display: flex; flex-direction: column; gap: 7px; }
.nr-memleg div { display: flex; align-items: baseline; gap: 8px; font-size: .78rem; color: #5B5F6B; line-height: 1.35; }
.nr-memleg b { display: inline-flex; align-items: center; gap: 6px; color: #1E2433; font-size: .86rem; white-space: nowrap;
  min-width: 118px; }
.nr-memleg b i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.nr-days { display: grid; grid-template-columns: repeat(14, minmax(0, 1fr)); gap: 4px; margin-top: .9rem; }
.nr-days i { display: block; aspect-ratio: 1; border-radius: 5px; position: relative; }
.nr-days i:hover { outline: 2px solid #1E2433; outline-offset: 1px; }
.nr-daysl { display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: .62rem;
  color: #8A7E63; margin-top: 6px; letter-spacing: .06em; }
.pf-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: .3rem 0 .2rem; font-size: .82rem; color: #4A5163; }
.pf-legend span { display: inline-flex; align-items: center; gap: 6px; }
.pf-legend i { width: 18px; height: 18px; border-radius: 6px; display: inline-grid; place-items: center; font-style: normal;
  font-size: .7rem; font-weight: 700; color: #FFFDF8; }
.nr-map { margin-top: 1rem; }
.nr-mapdoc { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 1.1rem 0 .5rem; }
.nr-mapdoc h4 { font-family: 'Fraunces', serif; font-size: 1.05rem; margin: 0; padding: 0; color: #1E2433; }
.nr-mapdoc span { font-size: .8rem; color: #6B6F7B; white-space: nowrap; }
.pf-tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); gap: 8px; }
.nr-t { position: relative; display: flex; align-items: center; gap: 9px; padding: 9px 11px 9px 13px; border-radius: 12px;
  background: #FFFDF8; border: 1px solid #E4DCC9; overflow: visible; transition: transform .18s, box-shadow .18s; }
.nr-t::before { content: ""; position: absolute; left: -1px; top: 8px; bottom: 8px; width: 4px; border-radius: 0 4px 4px 0;
  background: var(--s); }
.nr-t:hover { transform: translateY(-2px); box-shadow: 0 12px 22px -18px rgba(30, 36, 51, .6); z-index: 3; }
.nr-t i { flex: none; width: 20px; height: 20px; border-radius: 6px; display: grid; place-items: center; font-style: normal;
  font-size: .72rem; font-weight: 700; color: #FFFDF8; background: var(--s); }
.nr-t .n { flex: 1; min-width: 0; font-size: .84rem; color: #1E2433; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.nr-t .c { font-family: 'JetBrains Mono', monospace; font-size: .7rem; color: #6B6F7B; white-space: nowrap; }
.nr-t .tip { position: absolute; left: 10px; bottom: calc(100% + 6px); min-width: 220px; max-width: 300px; padding: 9px 11px;
  border-radius: 10px; background: #1E2433; color: #F4F1EA; font-size: .78rem; line-height: 1.4; opacity: 0;
  pointer-events: none; transform: translateY(4px); transition: opacity .15s, transform .15s; }
.nr-t:hover .tip { opacity: 1; transform: none; }
.pf-weak { display: flex; flex-direction: column; gap: 7px; margin-top: .2rem; }
.pf-weak .w { padding: 8px 12px 9px; border-radius: 10px; background: #FBF3EE; border-left: 3px solid #C4452B; }
.pf-weak .w b { display: block; font-size: .86rem; font-weight: 600; color: #1E2433; line-height: 1.3; }
.pf-weak .w span { display: block; font-size: .76rem; color: #6B6F7B; margin-top: 2px; }
.pf-weak-none { color: #6B6F7B; font-size: .84rem; line-height: 1.45; }
.st-key-weak_box { background: #FFFDF8; border: 1px solid #E4DCC9; border-radius: 18px; padding: 18px 20px 16px; }
@media (max-width: 900px) { .nr-brain, .nr-stats { grid-template-columns: 1fr 1fr; } }
@media (prefers-reduced-motion: reduce) { .nr-t, .nr-t .tip { transition: none; } }
</style>"""


# ---------------------------------------------------------------- profil

@st.dialog("Profili düzenle", width="medium")
def _edit(p: dict) -> None:
    with st.form("nr_profile", border=False):
        name = st.text_input("Adın", value=p["name"], max_chars=60)
        about = st.text_input("Kısa tanıtım", value=p["about"], max_chars=120,
                              placeholder="ör. Bilgisayar Mühendisliği, 3. sınıf")
        pic = st.file_uploader("Profil resmi", type=["jpg", "jpeg", "png", "webp"],
                               help="Ortadan kare kırpılır ve küçültülür; konum gibi fotoğraf bilgileri saklanmaz.")
        drop = p["has_avatar"] and st.checkbox("Resmi kaldır")
        go = st.form_submit_button("Kaydet", type="primary", width="stretch")
    if go:
        try:
            accounts.update_profile(p["id"], name, about)
            if pic is not None:
                accounts.set_avatar(p["id"], pic.getvalue())
            elif drop:
                accounts.remove_avatar(p["id"])
        except accounts.AccountError as e:
            st.error(str(e), icon=":material/error:")
            return
        st.session_state.user["name"] = " ".join(name.split())
        data.avatar_b64.clear()
        st.rerun()


def _password(p: dict) -> None:
    with st.expander("Parolanı değiştir", icon=":material/key:"):
        with st.form("nr_pw", border=False, clear_on_submit=True):
            old = st.text_input("Şu anki parola", type="password", autocomplete="current-password")
            new = st.text_input("Yeni parola", type="password", autocomplete="new-password",
                                help=f"En az {accounts.MIN_PASSWORD} karakter.")
            new2 = st.text_input("Yeni parola (tekrar)", type="password", autocomplete="new-password")
            go = st.form_submit_button("Parolayı değiştir")
        if go:
            if new != new2:
                st.error("Yeni parolalar aynı değil.", icon=":material/error:")
                return
            try:
                accounts.change_password(p["id"], old, new)
            except accounts.AccountError as e:
                st.error(str(e), icon=":material/error:")
                return
            st.session_state.pop("_token", None)  # bu tarayıcının "beni hatırla" oturumu da kapandı
            st.success("Parola değişti. Diğer cihazlardaki açık oturumlar kapatıldı.", icon=":material/check_circle:")


def _header(p: dict) -> None:
    months = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    t = time.localtime(p["created"])
    left, right = st.columns([5, 1.4], vertical_alignment="center")
    with left:
        style.html(f'<div class="nr-prof">{style.avatar(p, data.avatar_b64(p["id"]), 96)}<div>'
                   f'<h1>{style.esc(p["name"])}</h1><div class="u">@{style.esc(p["username"] or "")} · '
                   f'katılım {months[t.tm_mon - 1]} {t.tm_year}</div>'
                   + (f'<div class="a">{style.esc(p["about"])}</div>' if p["about"] else "") + "</div></div>")
    if right.button("Profili düzenle", icon=":material/edit:", width="stretch", key="prof_edit"):
        _edit(p)


# ---------------------------------------------------------------- beyin analizi

def _stats(m: dict) -> None:
    acc = f"%{round(100 * m['correct'] / m['answered'])}" if m.get("answered") else "–"
    tiles = [("Notların", len(data.mine()), "kendi listende"),
             ("Cevapladığın soru", m.get("answered", 0), "sınavlarda"),
             ("Doğru oranı", acc, "sınav cevaplarında"),
             ("Değerlendirdiğin kart", m.get("reviewed", 0), "Bildim / Bilemedim")]
    style.html('<div class="nr-stats">' + "".join(
        f'<div class="nr-stat"><div class="l">{style.esc(l)}</div><div class="v">{v}</div>'
        f'<div class="d">{style.esc(d)}</div></div>' for l, v, d in tiles) + "</div>")


def _memory_panel(m: dict) -> str:
    known = sum(d["known"] for d in m["docs"])
    total = sum(d["n"] for d in m["docs"])
    mem = m.get("memory", {})
    n_mem = sum(mem.values())
    bar = "".join(f'<i style="width:{100 * mem.get(k, 0) / n_mem:.1f}%;background:{c}" title="{lab}: {mem.get(k, 0)}"></i>'
                  for k, lab, c, _ in MEMORY if mem.get(k)) if n_mem else '<i style="width:100%;background:#ECE6D8"></i>'
    leg = "".join(f'<div><b><i style="background:{c}"></i>{lab} · {mem.get(k, 0)}</b>{style.esc(d)}</div>'
                  for k, lab, c, d in MEMORY)
    return (f'<div class="nr-panel"><h3>Bildiğin sorular</h3><div class="s">Görebildiğin notlardaki doğrulanmış '
            f'soruların; son sınav cevabına ya da kartın kutusuna göre.</div>'
            f'<div class="nr-hero">{known}<small>/ {total} soru</small></div>'
            f'<div class="nr-mem">{bar}</div><div class="nr-memleg">{leg}</div></div>')


def _activity_panel(m: dict) -> str:
    days = m.get("activity", [0] * 14)
    cells = []
    for i, n in enumerate(days):
        c = next(col for lim, col in reversed(ACTIVITY) if n >= lim)
        when = "bugün" if i == len(days) - 1 else ("dün" if i == len(days) - 2 else f"{len(days) - 1 - i} gün önce")
        cells.append(f'<i style="background:{c}" title="{when}: {n} çalışma"></i>')
    active = sum(1 for n in days if n)
    return (f'<div class="nr-panel"><h3>Son 14 gün</h3><div class="s">Her kare bir gün: cevapladığın sınav sorusu ve '
            f'değerlendirdiğin kart sayısı (koyu = çok). {active} günde çalıştın.</div>'
            f'<div class="nr-days">{"".join(cells)}</div><div class="nr-daysl"><span>14 GÜN ÖNCE</span>'
            f'<span>BUGÜN</span></div></div>')


def _map(m: dict) -> None:
    docs = [d for d in m["docs"] if d["doc"] in data.mine() or d["seen"]]
    if not docs:
        st.info("Henüz notun yok. Ana sayfadan bir not ekle; konuları burada görünür.", icon=":material/upload_file:")
        return
    counts = {s: sum(d["status"].get(s, 0) for d in docs) for s in STATUS}
    style.html('<div class="pf-legend">' + "".join(
        f'<span><i style="background:{c}">{ic}</i>{lab} · {counts[s]}</span>' for s, (c, ic, lab) in STATUS.items())
        + "</div>")
    blocks = []
    for d in sorted(docs, key=lambda d: (-d["seen"], data.short(d["doc"]))):
        tiles = []
        for t in d["topics"]:
            c, ic, lab = STATUS[t["status"]]
            detail = (f"{t['n']} sorudan {t['seen']}'ini gördün, {t['known']}'ini biliyorsun" if t["seen"]
                      else f"{t['n']} soru, henüz çalışmadın")
            tiles.append(f'<div class="nr-t" style="--s:{c}"><i>{ic}</i><span class="n">{style.esc(t["title"])}</span>'
                         f'<span class="c">{t["known"]}/{t["n"]}</span><span class="tip"><b>{style.esc(t["title"])}</b>'
                         f'<br>{lab}: {detail}</span></div>')
        share = f"{d['n']} sorunun {d['known']}'ini biliyorsun" if d["n"] else "soru yok"
        blocks.append(f'<div class="nr-mapdoc"><h4>{style.esc(data.short(d["doc"]))}</h4><span>{share}</span></div>'
                      f'<div class="pf-tiles">{"".join(tiles)}</div>')
    style.html('<div class="nr-map">' + "".join(blocks) + "</div>")


def _weak(m: dict) -> None:
    weak = m["weak"][:4]
    with st.container(key="weak_box"):
        style.html('<div class="nr-panel" style="padding:0;border:0;background:none"><h3>Zayıf konuların</h3>'
                   '<div class="s">En az iki sorusunu gördüğün ve yarısından azını bildiğin konular.</div></div>')
        if not weak:
            style.html('<div class="pf-weak-none">Şu an zayıf konun yok. Çalıştıkça burada, en çok zorlandığın '
                       'konular listelenir.</div>')
            return
        style.html('<div class="pf-weak">' + "".join(
            f'<div class="w"><b>{style.esc(w["title"])}</b><span>{style.esc(data.short(w["doc"]))} · '
            f'{w["seen"]} sorudan {w["known"]} doğru</span></div>' for w in weak) + "</div>")
        st.space("small")
        if st.button("Bu konulardan sınav hazırla", type="primary", icon=":material/quiz:", key="weak_exam",
                     width="stretch"):
            docs = list(dict.fromkeys(w["doc"] for w in weak))
            topics = [w["title"] for w in weak if w["title"] != "Diğer"]
            req = R.prepare(docs, topics, None, list(R.KINDS), 10, user=data.uid())
            st.session_state.exam = {"id": req["id"], "answers": {}, "submitted": False, "recorded": False,
                                     "phase": "start"}
            st.switch_page("ui/pages/exam.py")


def render() -> None:
    style.html(_CSS)
    p = accounts.profile(data.uid())
    _header(p)
    m = data.mastery()
    _stats(m)
    style.html('<div class="nr-sec"><div class="k">Beyin analizi</div><h2>Notlarında ne kadar hâkimsin?</h2>'
               '<p>Yalnızca kendi kayıtlarından hesaplanır: sınav cevapların ve bilgi kartların. Konunun durumu, '
               'o konudaki sorulara verdiğin en son cevaba göre.</p></div>')
    a, b, c = st.columns([1.15, 1, 1], gap="medium")
    with a:
        style.html(_memory_panel(m))
    with b:
        style.html(_activity_panel(m))
    with c:
        _weak(m)
    style.html('<div class="nr-sec" style="margin-top:1.4rem"><div class="k">Konu haritası</div>'
               '<p>Her kutu notundaki bir konu; sayı, o konunun sorularından kaçını bildiğin. Üzerine gelince ayrıntı.</p>'
               '</div>')
    _map(m)
    st.space("large")
    style.html('<div class="nr-sec"><div class="k">Hesap</div></div>')
    _password(p)


render()

"""Bilgi Kartları — havuzdaki doğrulanmış sorulardan aralıklı tekrar (src/cards.py; LLM çağrısı yok).

Akış: seçim (belgeler, kart sayısı, yalnızca zamanı gelenler) → oturum (odak modu: kart tıklanınca çevrilir;
Bilemedim / Atla / Bildim → kart ilgili yığına uçar, sıradaki desteden gelir; Fosfor konuşur) → özet (konfeti, tekrar).
Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim. Sınav sonucundan "Yanlışlarını kartla çalış" buraya gelir.
"""

import random
import time

import streamlit as st

from src import cards as K
from src import request as R
from src.ui import buddy, data, style
from src.ui import components as C

SYM = {"good": "✓", "bad": "✗", "skip": "↷"}
PILE = {"bad": "Bilemedim", "skip": "Atladım", "good": "Bildim"}
FOCUS_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 860px; padding-top: 1.4rem; }
.st-key-fc_keys { height: 0; overflow: hidden; margin: 0; }
</style>"""


@st.cache_data(ttl=30)
def _items() -> dict[str, dict]:
    return R.all_items()


def _gap(days: int) -> str:
    return "bugün" if days == 0 else ("yarın" if days == 1 else f"{days} gün sonra")


# ---------------------------------------------------------------- Fosfor'un sözleri

def _line(result: str, cs: dict, gap: int, again: bool) -> tuple[str, str, str]:
    """(ruh hâli, HTML söz, nonce). Seçim konuma bağlı: aynı durumda her yeniden çizimde söz değişmez."""
    i, streak = cs["pos"], cs["streak"]
    if result == "good":
        if streak >= 5:
            return "cheer", f"🔥 <b>{streak}</b> kart üst üste! Durdurulamıyorsun.", f"g{i}"
        if streak == 3:
            return "cheer", f"Üç üst üste! Bu kart <b>{_gap(gap)}</b> yeniden gelecek.", f"g{i}"
        says = [f"Harika, bildin! Bunu <b>{_gap(gap)}</b> tekrar soracağım.", "Doğru yığına! 👏 Bir kutu yukarı çıktı.",
                "Süper. Bildiğin kartlar giderek seyrekleşir; vaktin bilmediklerine kalır."]
        return "happy", says[i % len(says)], f"g{i}"
    if result == "bad":
        says = ["Sorun değil, öğrenmenin yolu bu. Bu kart <b>bugün</b> yine gelecek.",
                "Arka yüzdeki kaynak cümleyi bir kez daha oku; birazdan yeniden karşılaşacağız.",
                "Bilemediklerin en değerli kartlar. Sonda onları ayrıca çalışabilirsin."]
        return "sad", says[i % len(says)], f"b{i}"
    if again:
        return "think", "Bunu ikinci kez geçtin; bir sonraki oturuma bıraktım.", f"s{i}"
    says = ["Tamam, bunu destenin sonuna koydum; birazdan yine gelecek.", "Emin değil misin? Sonda bir kez daha deneriz."]
    return "think", says[i % len(says)], f"s{i}"


# ---------------------------------------------------------------- durum değişiklikleri (düğme geri çağrıları)

def _begin(ids: list[str]) -> None:
    st.session_state.cards = {
        "queue": list(ids), "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0, "best": 0, "last": None,
        "started": time.time(), "ended": False, "confetti": False,
        "say": ("happy", "İlk kart geliyor! Kartın üstüne tıkla ya da <b>Boşluk</b>'a bas, arkasını gör.", "start")}


def _grade(result: str) -> None:
    cs = st.session_state.cards
    if cs["pos"] >= len(cs["queue"]):
        return
    qid = cs["queue"][cs["pos"]]
    state = K.history().get(qid)
    K.record(qid, result)
    again = result == "skip" and qid in cs["skipped"]
    if result == "skip" and not again:
        cs["skipped"].append(qid)
        cs["queue"].append(qid)  # destenin sonuna
    cs["res"][qid], cs["col"][qid] = result, cs["pos"]
    cs["streak"] = cs["streak"] + 1 if result == "good" else (cs["streak"] if result == "skip" else 0)
    cs["best"] = max(cs["best"], cs["streak"])
    q = _items().get(qid, {}).get("q", {})
    cs["last"] = {"result": result, "pos": cs["pos"], "text": str(q.get("question", ""))[:140]}
    cs["say"] = _line(result, cs, K.next_gap(state, result), again)
    cs["pos"] += 1


def _shuffle() -> None:
    cs = st.session_state.cards
    rest = cs["queue"][cs["pos"]:]
    random.shuffle(rest)
    cs["queue"][cs["pos"]:] = rest
    cs["say"] = ("happy", "Kalan kartları karıştırdım. 🔀", f"x{time.time()}")


def _only_bad() -> None:
    cs = st.session_state.cards
    bad = [q for q, r in cs["res"].items() if r == "bad"]
    if not bad:
        cs["say"] = ("cheer", "Henüz bilemediğin kart yok! 🎉", f"n{time.time()}")
        return
    _begin(bad)
    st.session_state.cards["say"] = ("think", f"Bilemediğin <b>{len(bad)}</b> kartla yeni tur. Bu sefer olacak!", "rb")


def _end() -> None:
    st.session_state.cards["ended"] = True


def _new() -> None:
    st.session_state.pop("cards", None)


# ---------------------------------------------------------------- HTML parçaları

def _front(it: dict) -> str:
    q = it["q"]
    tags = "".join(f"<span>{style.esc(t)}</span>" for t in (C.type_label(q), C.DIFF_TR.get(q.get("difficulty"), ""),
                                                             data.short(it.get("doc", ""))) if t)
    body = f'<div class="fq">{C.t(q["question"])}</div>'
    if q["type"] == "multiple_choice":
        body += '<div class="fopts">' + "".join(f"<div><b>{C.LETTERS[j]})</b>{C.t(o)}</div>"
                                                for j, o in enumerate(q["options"])) + "</div>"
    elif q["type"] == "true_false":
        body += '<div class="fopts"><div>Doğru mu, yanlış mı?</div></div>'
    return f'<div class="tag">{tags}</div>{body}<div class="tap"><i>👆</i> Çevirmek için tıkla ya da Boşluk</div>'


def _back(it: dict) -> str:
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    if q["type"] == "multiple_choice":
        a = q["answer_index"]
        ans = f'<span class="ltr">{C.LETTERS[a]}</span>{C.t(q["options"][a])}'
    elif q["type"] == "true_false":
        ans = "Doğru ✓" if q["answer"] == "true" else "Yanlış ✗"
    else:
        ans = C.expected(q)
    text = str(q["question"])
    parts = [f'<div class="lab">Soru</div><div class="q2">{C.t(text[:170] + ("…" if len(text) > 170 else ""))}</div>',
             f'<div class="lab">Cevap</div><div class="ans">{ans}</div>']
    if q.get("solution"):
        parts.append('<div class="lab">Çözüm</div><ol class="nr-solution">'
                     + "".join(f"<li>{C.t(s)}</li>" for s in q["solution"]) + "</ol>")
    where = " · ".join(x for x in (data.short(it.get("doc", "")), f"sayfa {page}" if page else "") if x)
    parts.append(f'<div class="lab">Kaynak · {style.esc(where)}</div>'
                 f'<div class="nr-evidence"><span class="nr-hl">{C.t(q.get("evidence_quote", ""))}</span></div>')
    return "".join(parts)


def _piles(cs: dict, bump: str | None = None) -> str:
    out = []
    for kind in ("bad", "skip", "good"):
        ids = [q for q, r in cs["res"].items() if r == kind]
        minis = "".join(f'<b style="background:{style.color(cs["col"][q])[0]}"></b>' for q in ids[-6:])
        out.append(f'<div class="nr-pile {kind}{" bump" if kind == bump else ""}"><span class="ico">{SYM[kind]}</span>'
                   f'<div><div class="n">{len(ids)}</div><div class="l">{PILE[kind]}</div></div>'
                   f'<div class="mini">{minis}</div></div>')
    return '<div class="nr-piles">' + "".join(out) + "</div>"


def _stage(it: dict, cs: dict) -> str:
    pos, left = cs["pos"], len(cs["queue"]) - cs["pos"] - 1
    stacks = ((f'<div class="nr-stack s2" style="background:{style.color(pos + 2)[0]}"></div>' if left > 1 else "")
              + (f'<div class="nr-stack s1" style="background:{style.color(pos + 1)[0]}"></div>' if left > 0 else ""))
    card = (f'<details class="nr-fc" style="{style.color_vars(pos)}" data-k="{it["id"]}-{pos}">'
            f'<summary>{_front(it)}</summary><div class="back">{_back(it)}</div></details>')
    last = cs.pop("last", None)  # uçan kart yalnızca bir kez (değerlendirmenin hemen ardından) çizilir
    ghost = (f'<div class="nr-ghost {last["result"]}" data-s="{SYM[last["result"]]}" style="{style.color_vars(last["pos"])}">'
             f'{style.esc(last["text"])}</div>') if last else ""
    return (f'<div class="nr-stage"><div class="nr-deck">{stacks}{card}{ghost}</div>'
            f'{_piles(cs, last["result"] if last else None)}</div>')


def _keys() -> None:
    """Klavye (tarayıcıda): Boşluk kartı çevirir, ← ↓ → değerlendirir. Odaktaki düğme boşlukla tıklanmasın diye bırakılır."""
    with st.container(key="fc_keys"):
        st.iframe("""<body style="margin:0"><script>
const P = window.parent, D = P.document;
if (P.__nrKeyFn) D.removeEventListener('keydown', P.__nrKeyFn);
P.__nrKeyFn = (e) => {
  const tag = (e.target.tagName || '').toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.ctrlKey || e.metaKey || e.altKey) return;
  const click = (sel) => { const b = D.querySelector(sel); if (b && !b.disabled) { b.click(); e.preventDefault(); } };
  if (e.key === ' ') { const d = D.querySelector('details.nr-fc'); if (d) { if (D.activeElement) D.activeElement.blur();
    d.open = !d.open; e.preventDefault(); } }
  else if (e.key === 'ArrowLeft' || e.key === '1') click('.st-key-fc_bad button');
  else if (e.key === 'ArrowDown' || e.key === '2') click('.st-key-fc_skip button');
  else if (e.key === 'ArrowRight' || e.key === '3') click('.st-key-fc_good button');
};
D.addEventListener('keydown', P.__nrKeyFn);
</script></body>""", height=1)


# ---------------------------------------------------------------- ekranlar

def _setup() -> None:
    style.header("Çalış", "Bilgi Kartları",
                 "Doğrulanmış sorular kart olur: önünde soru, arkasında cevap ve notundaki kaynak cümle. Bildiğin kartlar "
                 "giderek seyrek, bilemediklerin sık gelir (aralıklı tekrar).", hero_word="Kartları")
    docs = [d for d in data.documents() if d["verified"]]
    if not docs:
        st.info("Henüz doğrulanmış soru yok. Önce **Belgeler** sayfasından bir ders notu ekle.", icon=":material/upload_file:")
        return
    chosen = st.pills("Belgeler", [d["stem"] for d in docs], selection_mode="multi", default=[d["stem"] for d in docs],
                      format_func=data.short)
    if not chosen:
        st.caption("En az bir belge seç.")
        return
    items, hist, now = K.pool(chosen), K.history(), time.time()
    s = K.summary(items, hist, now)
    tile = lambda i, v, k: f'<div class="nr-ctile" style="background:linear-gradient(135deg,{style.color(i)[0]},{style.color(i)[1]});animation-delay:{i * .06:.2f}s"><div class="v">{v}</div><div class="k">{k}</div></div>'
    style.html('<div class="nr-ctiles">' + tile(0, s["total"], "kart") + tile(1, s["due"], "tekrar zamanı gelen")
               + tile(2, s["new"], "hiç görmediğin") + tile(3, s["mastered"], "ustalaştığın") + "</div>")
    c = st.columns([3, 3, 2], vertical_alignment="bottom")
    n = c[0].select_slider("Kart sayısı", [10, 20, 30, 50], value=20)
    only_due = c[1].toggle("Yalnızca zamanı gelenler", value=True,
                           help="Açıkken yalnızca hiç görmediğin ve tekrar zamanı gelmiş kartlar gelir.")
    avail = len(K.pick(items, hist, 10 ** 6, now, only_due))
    if c[2].button(f"Başla · {min(n, avail)} kart", key="fc_start", type="primary", icon=":material/style:",
                   width="stretch", disabled=not avail):
        _begin(K.pick(items, hist, n, now, only_due))
        st.rerun()
    if not avail:
        st.caption("Bugün tekrar zamanı gelen kart yok 🎉 Yeni tur istersen \"Yalnızca zamanı gelenler\"i kapat.")
    buddy.show("happy", "Merhaba, ben <b>Fosfor</b>! Kartı çevir; bildiklerini sağa, bilemediklerini sola at. Hangisini "
                        "ne zaman tekrar göstereceğimi ben hatırlarım.", nonce="setup")


def _session() -> None:
    style.html(FOCUS_CSS)
    cs, items = st.session_state.cards, _items()
    while cs["pos"] < len(cs["queue"]) and cs["queue"][cs["pos"]] not in items:  # havuzdan çıkmış soru
        cs["pos"] += 1
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        _summary()
        return
    it, total = items[cs["queue"][cs["pos"]]], len(cs["queue"])
    top = st.columns([5, 1.2], vertical_alignment="center")
    streak = f'<span class="nr-streak">🔥 {cs["streak"]} seri</span>' if cs["streak"] >= 2 else ""
    with top[0]:
        style.html(f'<div class="nr-qprog"><div class="lbl"><span><b>Kart {cs["pos"] + 1}</b> / {total} {streak}</span>'
                   f'<span>{len(cs["res"])} değerlendirildi</span></div><div class="bar"><i style="width:'
                   f'{100 * cs["pos"] / total:.1f}%"></i></div></div>')
    top[1].button("Bitir", key="fc_exit", icon=":material/flag:", width="stretch", on_click=_end)
    st.space("small")
    style.html(_stage(it, cs))
    st.space("small")
    b = st.columns(3)
    b[0].button("Bilemedim", key="fc_bad", icon=":material/close:", width="stretch", on_click=_grade, args=("bad",))
    b[1].button("Atla", key="fc_skip", icon=":material/redo:", width="stretch", on_click=_grade, args=("skip",))
    b[2].button("Bildim", key="fc_good", icon=":material/check:", width="stretch", on_click=_grade, args=("good",))
    gap = K.next_gap(K.history().get(it["id"]), "good")
    style.html(f'<div class="nr-gap">Bildim → {_gap(gap)} tekrar · Bilemedim → bugün yine · Klavye: '
               '<span class="nr-kbd">Boşluk</span> çevir · <span class="nr-kbd">←</span> <span class="nr-kbd">↓</span> '
               '<span class="nr-kbd">→</span></div>')
    _keys()
    mood, text, nonce = cs["say"]
    buddy.show(mood, text, nonce=nonce, menu=[("Karıştır", ":material/shuffle:", _shuffle, ()),
                                              ("Bilemediklerim", ":material/replay:", _only_bad, ()),
                                              ("Oturumu bitir", ":material/flag:", _end, ())])


def _summary() -> None:
    cs = st.session_state.cards
    style.header("Çalış", "Bilgi Kartları")
    res = list(cs["res"].values())
    good, bad, skip = res.count("good"), res.count("bad"), res.count("skip")
    seen = max(1, good + bad)
    if good and good / seen >= .7 and not cs["confetti"]:
        style.html(style.confetti())
        cs["confetti"] = True
    mins = max(1, round((time.time() - cs["started"]) / 60))
    style.html(f'<div class="nr-res" style="grid-template-columns:1fr"><div><div class="msg">Oturum bitti: '
               f'{good} / {len(res)} kart bildin</div><div class="sub">~{mins} dk · en uzun seri {cs["best"]} · '
               f'bilemediklerin bugün yine gelecek, bildiklerin günler sonra.</div>{_piles(cs)}</div></div>')
    st.space("small")
    c = st.columns([2, 1.4, 2])
    if bad:
        c[0].button(f"Bilemediklerimi çalış ({bad})", key="fc_rb", type="primary", icon=":material/replay:",
                    width="stretch", on_click=_only_bad)
    c[1].button("Yeni oturum", key="fc_new", icon=":material/add:", width="stretch", on_click=_new)
    if good / seen >= .7:
        mood, say = "cheer", f"Muhteşem! <b>{good}</b> kartı bildin. Bunlar artık daha seyrek gelecek."
    elif bad:
        mood, say = "sad", f"<b>{bad}</b> kartı bilemedin; hepsi bir sonraki turda. İstersen hemen bir tur daha atalım!"
    else:
        mood, say = "happy", "Güzel bir tur! Yarın tekrar zamanı gelen kartlarla görüşürüz."
    menu = [("Bilemediklerim", ":material/replay:", _only_bad, ())] if bad else []
    buddy.show(mood, say, nonce="end", menu=menu + [("Yeni oturum", ":material/add:", _new, ())])


def render() -> None:
    if "cards_preset" in st.session_state:  # sınav sonucundan: yanlış / boş sorular kart olarak
        _begin(st.session_state.pop("cards_preset"))
        st.session_state.cards["say"] = ("think", "Sınavdaki yanlış ve boşların kart oldu. Hadi bunları "
                                                  "pekiştirelim!", "preset")
    if "cards" in st.session_state:
        _session()
    else:
        _setup()


render()

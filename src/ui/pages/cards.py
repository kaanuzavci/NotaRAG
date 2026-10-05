"""Bilgi Kartları — havuzdaki doğrulanmış sorulardan aralıklı tekrar (src/cards.py; LLM çağrısı yok).

Akış: seçim (belgeler, kart sayısı, yalnızca zamanı gelenler) → oturum (odak modu; solda deste, sağda koç Fosfor:
kart tıklanınca 3B döner ve yine tıklanınca geri döner; Bilemedim / Atla / Bildim → kart ilgili yığına uçar,
sıradaki desteden gelir) → özet (zorluk / soru tipi / konu kırılımı, konfeti, bilemediklerle yeni tur).
Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim. Sınav sonucundan "Yanlışları kartla çalış" buraya gelir.
"""

import random
import time

import streamlit as st

from src import cards as K
from src import request as R
from src.ui import buddy, data, style
from src.ui import components as C

SYM = {"good": "✓", "bad": "✕", "skip": "↷"}
PILE = {"bad": "Bilemedim", "skip": "Atladım", "good": "Bildim"}
FOCUS_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1180px; padding-top: 1.3rem; }
[data-testid="stMain"] { position: relative; z-index: 0; }
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
        if streak >= 3:
            return "fire", f"<b>{streak}</b> kart üst üste! Bu tempoyla deste bitmek üzere.", f"g{i}"
        says = [f"Harika, bildin! Bunu <b>{_gap(gap)}</b> yeniden soracağım.",
                "Bildim yığınına gitti. Bir kutu yukarı çıktı; artık daha seyrek gelecek.",
                "Çok iyi. Bildiklerin seyrekleşir, vaktin bilmediklerine kalır."]
        return ("cheer" if i % 3 == 1 else "happy"), says[i % len(says)], f"g{i}"
    if result == "bad":
        says = ["Sorun değil, öğrenmenin yolu bu. Bu kart <b>bugün</b> yine karşına çıkacak.",
                "Arka yüzdeki kaynak cümleyi bir kez daha oku; birazdan yeniden göreceğiz.",
                "Bilemediklerin en değerli kartlar. Turun sonunda onları ayrıca çalışabiliriz."]
        return "sad", says[i % len(says)], f"b{i}"
    if again:
        return "think", "Bunu ikinci kez geçtin; bir sonraki oturuma bıraktım.", f"s{i}"
    says = ["Tamam, destenin sonuna koydum. Birazdan yine gelecek.", "Emin değil misin? Sonda bir kez daha deneriz."]
    return "think", says[i % len(says)], f"s{i}"


# ---------------------------------------------------------------- durum değişiklikleri (düğme geri çağrıları)

def _begin(ids: list[str]) -> None:
    st.session_state.cards = {
        "queue": list(ids), "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0, "best": 0, "last": None,
        "started": time.time(), "ended": False, "party": False,
        "say": ("hello", "İlk kart geliyor! Kartın üstüne tıkla ya da <b>Boşluk</b>'a bas, arkasını gör. Bir daha "
                         "tıklarsan ön yüze döner.", "start")}


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
    cs["say"] = ("happy", "Kalan kartları karıştırdım. Sıra değişince hafıza daha iyi sınanır.", f"x{time.time()}")


def _only_bad() -> None:
    cs = st.session_state.cards
    bad = [q for q, r in cs["res"].items() if r == "bad"]
    if not bad:
        cs["say"] = ("cheer", "Henüz bilemediğin kart yok!", f"n{time.time()}")
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
    meta = "".join(f"<span>{style.esc(t)}</span>" for t in (C.type_label(q), C.DIFF_TR.get(q.get("difficulty"), ""),
                                                             data.short(it.get("doc", ""))) if t)
    body = f'<div class="fq">{C.t(q["question"])}</div>'
    if q["type"] == "multiple_choice":
        body += '<div class="fopts">' + "".join(f"<div><b>{C.LETTERS[j]}</b>{C.t(o)}</div>"
                                                for j, o in enumerate(q["options"])) + "</div>"
    elif q["type"] == "true_false":
        body += '<div class="fopts" style="grid-template-columns:1fr"><div>Bu ifade doğru mu, yanlış mı?</div></div>'
    return (f'<div class="meta">{meta}</div><div class="body">{body}</div>'
            '<div class="hint"><span class="ico">↻</span>Cevabı görmek için kartı çevir · tıkla ya da Boşluk</div>')


def _back(it: dict) -> str:
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    if q["type"] == "multiple_choice":
        a = q["answer_index"]
        ans = f'<span class="ltr">{C.LETTERS[a]}</span>{C.t(q["options"][a])}'
    elif q["type"] == "true_false":
        ans = "Doğru" if q["answer"] == "true" else "Yanlış"
    else:
        ans = C.expected(q)
    text = str(q["question"])
    parts = [f'<div class="lab">Soru</div><div class="q2">{C.t(text[:170] + ("…" if len(text) > 170 else ""))}</div>',
             f'<div class="lab">Cevap</div><div class="ans">{ans}</div>']
    if q.get("solution"):
        parts.append('<div class="lab">Çözüm</div><ol class="nr-solution">'
                     + "".join(f"<li>{C.t(s)}</li>" for s in q["solution"]) + "</ol>")
    where = " · ".join(x for x in (data.short(it.get("doc", "")), f"sayfa {page}" if page else "") if x)
    parts.append(f'<div class="lab">Notundaki kaynak · {style.esc(where)}</div>'
                 f'<div class="nr-evidence"><span class="nr-hl">{C.t(q.get("evidence_quote", ""))}</span></div>'
                 '<div class="flipback">Ön yüze dönmek için yine tıkla</div>')
    return "".join(parts)


def _length_class(q: dict) -> str:
    n = len(str(q["question"])) + sum(len(str(o)) for o in q.get("options") or [])
    return " xlong" if n > 420 else (" long" if n > 240 else "")


def _piles(cs: dict, bump: str | None = None) -> str:
    out = []
    for kind in ("bad", "skip", "good"):
        ids = [q for q, r in cs["res"].items() if r == kind]
        minis = "".join(f'<b style="--mc:{style.color(cs["col"][q])[1]};--ma:{style.color(cs["col"][q])[3]}"></b>'
                        for q in ids[-6:])
        out.append(f'<div class="nr-pile {kind}{" bump" if kind == bump else ""}"><span class="ico">{SYM[kind]}</span>'
                   f'<div><div class="n">{len(ids)}</div><div class="l">{PILE[kind]}</div></div>'
                   f'<div class="mini">{minis}</div></div>')
    return '<div class="nr-piles">' + "".join(out) + "</div>"


def _stage(it: dict, cs: dict) -> str:
    pos, left = cs["pos"], len(cs["queue"]) - cs["pos"] - 1
    stacks = ((f'<div class="nr-stack s2" style="--s:{style.color(pos + 2)[1]}"></div>' if left > 1 else "")
              + (f'<div class="nr-stack s1" style="--s:{style.color(pos + 1)[1]}"></div>' if left > 0 else ""))
    card = (f'<details class="nr-fc{_length_class(it["q"])}" style="{style.color_vars(pos)}" data-k="{it["id"]}-{pos}">'
            f'<summary><div class="nr-flip"><div class="nr-face front">{_front(it)}</div>'
            f'<div class="nr-face back">{_back(it)}</div></div></summary></details>')
    last = cs.pop("last", None)  # uçan kart yalnızca bir kez (değerlendirmenin hemen ardından) çizilir
    ghost = (f'<div class="nr-ghost {last["result"]}" data-s="{SYM[last["result"]]}" style="{style.color_vars(last["pos"])}">'
             f'{style.esc(last["text"])}</div>') if last else ""
    return (f'<div class="nr-deck">{stacks}{card}{ghost}</div>'
            f'{_piles(cs, last["result"] if last else None)}')


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


def _topic(it: dict) -> str:
    """Kartın konusu: bölüm adı; bölüm adı yalnızca numaraysa ('01') belge adıyla birlikte."""
    unit, doc = str(it.get("unit") or "").strip(), data.short(it.get("doc", ""))
    return unit if len(unit) > 3 and not unit.isdigit() else f"{doc} · bölüm {unit}" if unit else doc


def _counts(cs: dict) -> tuple[int, int, int]:
    res = list(cs["res"].values())
    return res.count("good"), res.count("bad"), res.count("skip")


# ---------------------------------------------------------------- ekranlar

def _setup() -> None:
    style.header("Çalış", "Bilgi Kartları",
                 "Doğrulanmış sorular kart olur: önünde soru, arkasında cevap ve notundaki kaynak cümle. Bildiğin kartlar "
                 "giderek seyrek, bilemediklerin sık gelir (aralıklı tekrar).", hero_word="Kartları")
    docs = [d for d in data.documents() if d["verified"]]
    if not docs:
        st.info("Henüz doğrulanmış soru yok. Önce **Belgeler** sayfasından bir ders notu ekle.", icon=":material/upload_file:")
        return
    main, side = st.columns([3, 1.1], gap="large")
    with main:
        chosen = st.pills("Belgeler", [d["stem"] for d in docs], selection_mode="multi",
                          default=[d["stem"] for d in docs], format_func=data.short)
        if not chosen:
            st.caption("En az bir belge seç.")
            return
        items, hist, now = K.pool(chosen), K.history(), time.time()
        s = K.summary(items, hist, now)
        tile = lambda i, v, k: (f'<div class="nr-ctile" style="{style.color_vars(i)};animation-delay:{i * .07:.2f}s">'
                                f'<div class="v">{v}</div><div class="k">{k}</div></div>')
        style.html('<div class="nr-ctiles">' + tile(0, s["total"], "kart") + tile(1, s["due"], "tekrar zamanı gelen")
                   + tile(2, s["new"], "hiç görmediğin") + tile(3, s["mastered"], "ustalaştığın") + "</div>")
        c = st.columns([3, 3, 2.2], vertical_alignment="bottom")
        n = c[0].select_slider("Kart sayısı", [10, 20, 30, 50], value=20)
        only_due = c[1].toggle("Yalnızca zamanı gelenler", value=True,
                               help="Açıkken yalnızca hiç görmediğin ve tekrar zamanı gelmiş kartlar gelir.")
        avail = len(K.pick(items, hist, 10 ** 6, now, only_due))
        if c[2].button(f"Başla · {min(n, avail)} kart", key="fc_start", type="primary", icon=":material/style:",
                       width="stretch", disabled=not avail):
            _begin(K.pick(items, hist, n, now, only_due))
            st.rerun()
        if not avail:
            st.caption("Bugün tekrar zamanı gelen kart yok. Yeni tur istersen \"Yalnızca zamanı gelenler\"i kapat.")
    with side:
        buddy.panel("hello", "Merhaba, ben <b>Fosfor</b>! Kartı çevir, bildiklerini sağa, bilemediklerini sola at. "
                             "Hangisini ne zaman yeniden göstereceğimi ben hatırlarım.", nonce="setup",
                    stats=buddy.stats([(str(s["due"]), "bugün"), (str(s["new"]), "yeni"), (str(s["mastered"]), "usta")]))


def _session() -> None:
    style.html(FOCUS_CSS)
    style.aurora()
    cs, items = st.session_state.cards, _items()
    while cs["pos"] < len(cs["queue"]) and cs["queue"][cs["pos"]] not in items:  # havuzdan çıkmış soru
        cs["pos"] += 1
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        _summary()
        return
    it, total = items[cs["queue"][cs["pos"]]], len(cs["queue"])
    good, bad, _ = _counts(cs)
    main, side = st.columns([3, 1.1], gap="large")
    with main:
        streak = f'<span class="nr-streak">🔥 {cs["streak"]}</span>' if cs["streak"] >= 2 else ""
        style.html(f'<div class="nr-topbar"><span class="c"><b>Kart {cs["pos"] + 1}</b> / {total}{streak}</span>'
                   f'<div class="track"><i style="width:{100 * cs["pos"] / total:.1f}%"></i></div>'
                   f'<span class="c">{len(cs["res"])} değerlendirildi</span></div>')
        st.space("small")
        style.html(_stage(it, cs))
        st.space("small")
        b = st.columns(3, gap="small")
        b[0].button("Bilemedim", key="fc_bad", icon=":material/close:", width="stretch", on_click=_grade, args=("bad",))
        b[1].button("Atla", key="fc_skip", icon=":material/redo:", width="stretch", on_click=_grade, args=("skip",))
        b[2].button("Bildim", key="fc_good", icon=":material/check:", width="stretch", on_click=_grade, args=("good",))
        gap = K.next_gap(K.history().get(it["id"]), "good")
        style.html(f'<div class="nr-gap">Bildim → {_gap(gap)} yeniden · Bilemedim → bugün yine · '
                   '<span class="nr-kbd">Boşluk</span> çevir · <span class="nr-kbd">←</span> '
                   '<span class="nr-kbd">↓</span> <span class="nr-kbd">→</span></div>')
        _keys()
    with side:
        mood, text, nonce = cs["say"]
        acc = f"%{round(100 * good / (good + bad))}" if good + bad else "–"
        buddy.panel(mood, text, nonce=nonce, stats=buddy.stats([(acc, "isabet"), (str(cs["best"]), "rekor seri"),
                                                                (str(total - cs["pos"]), "kalan")]),
                    actions=[("Kalanları karıştır", ":material/shuffle:", _shuffle, ()),
                             ("Yalnızca bilemediklerim", ":material/replay:", _only_bad, ()),
                             ("Oturumu bitir", ":material/flag:", _end, ())])


def _summary() -> None:
    cs, items = st.session_state.cards, _items()
    good, bad, skip = _counts(cs)
    seen = max(1, good + bad)
    if good and good / seen >= .7 and not cs["party"]:
        buddy.celebrate()
        cs["party"] = True
    mins = max(1, round((time.time() - cs["started"]) / 60))
    records = []
    for qid, r in cs["res"].items():
        it = items.get(qid)
        if it:
            q = it["q"]
            records.append({"status": PILE[r], "diff": C.DIFF_TR.get(q.get("difficulty")), "type": C.type_label(q),
                            "topic": _topic(it)})
    main, side = st.columns([3, 1.1], gap="large")
    with main:
        kpi = lambda v, k, col: (f'<div class="nr-kpi"><div class="k"><i style="background:{col}"></i>{k}</div>'
                                 f'<div class="v">{v}</div></div>')
        style.html(f'<div class="nr-res" style="grid-template-columns:1fr"><div><div class="msg">Oturum bitti: '
                   f'{len(cs["res"])} karttan {good} tanesini bildin</div><div class="sub">~{mins} dk · en uzun seri '
                   f'{cs["best"]} · isabet %{round(100 * good / seen)} · bilemediklerin bugün yine, bildiklerin günler '
                   f'sonra gelecek.</div><div class="nr-kpis">{kpi(good, "Bildim", "#10B981")}'
                   f'{kpi(bad, "Bilemedim", "#F43F5E")}{kpi(skip, "Atladım", "#F59E0B")}'
                   f'{kpi(f"{mins} dk", "Süre", "#A78BFA")}</div></div></div>')
        style.html(C.breakdowns(records, ("Bildim", "Bilemedim", "Atladım")))
        st.space("small")
        c = st.columns([2, 1.4, 2])
        if bad:
            c[0].button(f"Bilemediklerimi çalış ({bad})", key="fc_rb", type="primary", icon=":material/replay:",
                        width="stretch", on_click=_only_bad)
        c[1 if bad else 0].button("Yeni oturum", key="fc_new", icon=":material/add:", width="stretch", on_click=_new,
                                  type="secondary" if bad else "primary")
    with side:
        if good / seen >= .7:
            mood, say = "party", f"Muhteşem bir tur! <b>{good}</b> kartı bildin; bunlar artık daha seyrek gelecek."
        elif bad:
            mood, say = "sad", (f"<b>{bad}</b> kartı bilemedin; hepsi bir sonraki turda. Soldaki kırılıma bak: en çok "
                                "nerede zorlandığını gösteriyor.")
        else:
            mood, say = "happy", "Güzel bir tur! Yarın tekrar zamanı gelen kartlarla görüşürüz."
        actions = [("Bilemediklerimi çalış", ":material/replay:", _only_bad, ())] if bad else []
        buddy.panel(mood, say, nonce="end", actions=actions + [("Yeni oturum", ":material/add:", _new, ())])


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

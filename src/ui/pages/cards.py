"""Bilgi Kartları — havuzdaki doğrulanmış sorulardan aralıklı tekrar (src/cards.py; LLM çağrısı yok).

NotebookLM'deki gibi: önde soru, arkada cevap ve notundaki kaynak cümle; şık yok (şıksız anlaşılmayan sorular karta
dönüşmez: src/cards.card_ok). Akış: seçim → oturum (kart ortada; tıklayınca döner, yine tıklayınca geri; Bilemedim /
Atla / Bildim → kart ilgili yığına gider, sıradaki desteden gelir) → özet (isabet, zorluğa ve konulara göre).
Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim. Sınav sonucundan "Kartla çalış" buraya gelir.
"""

import random
import time

import streamlit as st

from src import cards as K
from src import request as R
from src import resume
from src.ui import data, style
from src.ui import components as C

SYM = {"good": "✓", "bad": "✕", "skip": "↷"}
PILE = {"bad": "Bilemedim", "skip": "Atladım", "good": "Bildim"}
FOCUS_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 900px; padding-top: 1.3rem; }
.st-key-fc_keys { height: 0; overflow: hidden; margin: 0; }
</style>"""


@st.cache_data(ttl=30)
def _items() -> dict[str, dict]:
    return R.all_items()


def _gap(days: int) -> str:
    return "bugün" if days == 0 else ("yarın" if days == 1 else f"{days} gün sonra")


def _topic(it: dict) -> str:
    """Kartın konusu: bölüm adı; bölüm adı yalnızca numaraysa ('01') belge adıyla birlikte."""
    unit, doc = str(it.get("unit") or "").strip(), data.short(it.get("doc", ""))
    return unit if len(unit) > 3 and not unit.isdigit() else (f"{doc} · bölüm {unit}" if unit else doc)


# ---------------------------------------------------------------- durum değişiklikleri (düğme geri çağrıları)

def _remember() -> None:
    """Kaldığın yerden devam et (src/resume.py): yarım oturum kişiye kaydedilir, bitince silinir."""
    cs = st.session_state.get("cards")
    if cs and not cs["ended"] and cs["pos"] < len(cs["queue"]):
        resume.save(data.uid(), "cards", {k: v for k, v in cs.items() if k != "last"})
    else:
        resume.clear(data.uid(), "cards")


def _begin(ids: list[str]) -> None:
    v = st.session_state.get("cards", {}).get("v", 0) + 1  # yeni tur da kartı sıfırdan çizdirsin
    st.session_state.cards = {"queue": list(ids), "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0,
                              "best": 0, "last": None, "started": time.time(), "ended": False, "v": v}
    _remember()


def _grade(result: str) -> None:
    cs = st.session_state.cards
    if cs["pos"] >= len(cs["queue"]):
        return
    qid = cs["queue"][cs["pos"]]
    K.record(qid, result, user=data.uid())
    if result == "skip" and qid not in cs["skipped"]:
        cs["skipped"].append(qid)
        cs["queue"].append(qid)  # destenin sonuna; ikinci kez atlanırsa bir sonraki oturuma kalır
    cs["res"][qid], cs["col"][qid] = result, cs["pos"]
    cs["streak"] = cs["streak"] + 1 if result == "good" else (cs["streak"] if result == "skip" else 0)
    cs["best"] = max(cs["best"], cs["streak"])
    q = _items().get(qid, {}).get("q", {})
    cs["last"] = {"result": result, "pos": cs["pos"], "text": str(q.get("question", ""))[:140]}
    cs["pos"] += 1
    cs["v"] += 1
    _remember()


def _shuffle() -> None:
    cs = st.session_state.cards
    rest = cs["queue"][cs["pos"] + 1:]  # ekrandaki kart yerinde kalır
    random.shuffle(rest)
    cs["queue"][cs["pos"] + 1:] = rest


def _only_bad() -> None:
    bad = [q for q, r in st.session_state.cards["res"].items() if r == "bad"]
    if bad:
        _begin(bad)


def _end() -> None:
    st.session_state.cards["ended"] = True
    _remember()


def _new() -> None:
    st.session_state.pop("cards", None)
    _remember()


# ---------------------------------------------------------------- HTML parçaları

def _front(it: dict) -> str:
    q = it["q"]
    meta = "".join(f"<span>{style.esc(t)}</span>" for t in (C.DIFF_TR.get(q.get("difficulty"), ""), _topic(it)) if t)
    return (f'<div class="meta">{meta}</div><div class="body"><div class="fq">{C.t(q["question"])}</div></div>'
            '<div class="hint">Cevabı görmek için karta tıkla · Boşluk</div>')


def _back(it: dict) -> str:
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    ans = C.t(q["options"][q["answer_index"]]) if q["type"] == "multiple_choice" else C.expected(q)
    text = str(q["question"])
    parts = [f'<div class="lab">Soru</div><div class="q2">{C.t(text[:200] + ("…" if len(text) > 200 else ""))}</div>',
             f'<div class="lab">Cevap</div><div class="ans">{ans}</div>']
    if q.get("solution"):
        parts.append('<div class="lab">Çözüm</div><ol class="nr-solution">'
                     + "".join(f"<li>{C.t(s)}</li>" for s in q["solution"]) + "</ol>")
    where = " · ".join(x for x in (data.short(it.get("doc", "")), f"sayfa {page}" if page else "") if x)
    parts.append(f'<div class="lab">Notundaki kaynak · {style.esc(where)}</div>'
                 f'<div class="nr-evidence"><span class="nr-hl">{C.t(q.get("evidence_quote", ""))}</span></div>'
                 '<div class="flipback">Soruya dönmek için yine tıkla</div>')
    return "".join(parts)


def _length_class(q: dict) -> str:
    n = len(str(q["question"]))
    return " xlong" if n > 320 else (" long" if n > 190 else "")


def _piles(cs: dict, bump: str | None = None) -> str:
    out = []
    for kind in ("bad", "skip", "good"):
        ids = [q for q, r in cs["res"].items() if r == kind]
        minis = "".join(f'<b style="--mc:{style.color(cs["col"][q])[1]}"></b>' for q in ids[-6:])
        out.append(f'<div class="nr-pile {kind}{" bump" if kind == bump else ""}"><span class="ico">{SYM[kind]}</span>'
                   f'<div><div class="n">{len(ids)}</div><div class="l">{PILE[kind]}</div></div>'
                   f'<div class="mini">{minis}</div></div>')
    return '<div class="nr-piles">' + "".join(out) + "</div>"


def _stage(it: dict, cs: dict) -> str:
    pos, left = cs["pos"], len(cs["queue"]) - cs["pos"] - 1
    stacks = ((f'<div class="nr-stack s2" style="--s:{style.color(pos + 2)[1]}"></div>' if left > 1 else "")
              + (f'<div class="nr-stack s1" style="--s:{style.color(pos + 1)[1]}"></div>' if left > 0 else ""))
    card = (f'<details class="nr-fc{_length_class(it["q"])}" style="{style.color_vars(pos)}">'
            f'<summary><div class="nr-flip"><div class="nr-face front">{_front(it)}</div>'
            f'<div class="nr-face back">{_back(it)}</div></div></summary></details>')
    last = cs.pop("last", None)  # giden kart yalnızca değerlendirmenin hemen ardından çizilir
    ghost = (f'<div class="nr-ghost {last["result"]}" data-s="{SYM[last["result"]]}" style="{style.color_vars(last["pos"])}">'
             f'{style.esc(last["text"])}</div>') if last else ""
    # Sarmalayıcı etiketi her değerlendirmede değişir: tarayıcı sahneyi sıfırdan kurar → animasyonlar her seferinde
    # oynar ve çevrilmiş kart (details[open]) bir sonraki karta çevrili geçmez (aynı etiket yeniden kullanılıyordu).
    tag = "section" if cs["v"] % 2 else "div"
    return (f'<{tag} class="nr-stage"><div class="nr-deck">{stacks}{card}{ghost}</div>'
            f'{_piles(cs, last["result"] if last else None)}</{tag}>')


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


def _counts(cs: dict) -> tuple[int, int, int]:
    res = list(cs["res"].values())
    return res.count("good"), res.count("bad"), res.count("skip")


# ---------------------------------------------------------------- ekranlar

def _setup() -> None:
    style.header("Çalış", "Bilgi Kartları",
                 "Doğrulanmış sorular kart olur: önünde soru, arkasında cevap ve notundaki kaynak cümle. Bildiğin kartlar "
                 "giderek seyrek, bilemediklerin sık gelir (aralıklı tekrar).")
    docs = [d for d in data.my_documents() if d["verified"]]
    if not docs:
        st.info("Henüz doğrulanmış soru yok. Önce **Belgeler** sayfasından bir ders notu ekle.", icon=":material/upload_file:")
        return
    names = [d["stem"] for d in docs]
    if (want := st.session_state.pop("cards_doc", None)) in names:  # ana sayfada destedeki "Kartlar" düğmesi
        st.session_state.cards_docs = [want]
    if "cards_docs" not in st.session_state or not set(st.session_state.cards_docs) <= set(names):
        st.session_state.cards_docs = names
    chosen = st.pills("Belgeler", names, selection_mode="multi", format_func=data.short, key="cards_docs")
    if not chosen:
        st.caption("En az bir belge seç.")
        return
    items, hist, now = K.pool(chosen), K.history(user=data.uid()), time.time()  # kutular kişinin kendi geçmişinden
    s = K.summary(items, hist, now)
    tile = lambda i, v, k: f'<div class="nr-ctile" style="{style.color_vars(i)}"><div class="v">{v}</div><div class="k">{k}</div></div>'
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
    st.caption("Şıksız anlaşılmayan sorular (doğru / yanlış, \"aşağıdakilerden hangisi\") kart olmaz; onlar sınavda.")


def _session() -> None:
    cs, items = st.session_state.cards, _items()
    while cs["pos"] < len(cs["queue"]) and cs["queue"][cs["pos"]] not in items:  # havuzdan çıkmış soru
        cs["pos"] += 1
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        _summary()
        return
    style.html(FOCUS_CSS)
    it, total = items[cs["queue"][cs["pos"]]], len(cs["queue"])
    good, bad, _ = _counts(cs)
    acc = f"%{round(100 * good / (good + bad))}" if good + bad else "–"
    top = st.columns([6, 1.15, 1], vertical_alignment="center", gap="small")
    with top[0]:
        style.html(f'<div class="nr-topbar"><span class="c"><b>Kart {cs["pos"] + 1}</b> / {total}</span>'
                   f'<div class="track"><i style="width:{100 * cs["pos"] / total:.1f}%"></i></div>'
                   f'<span class="chip">isabet <b>{acc}</b></span><span class="chip">seri <b>{cs["streak"]}</b></span></div>')
    top[1].button("Karıştır", key="fc_shuffle", icon=":material/shuffle:", type="tertiary", width="stretch",
                  on_click=_shuffle, help="Kalan kartların sırasını karıştır")
    top[2].button("Bitir", key="fc_end", icon=":material/flag:", type="tertiary", width="stretch", on_click=_end,
                  help="Oturumu bitir ve özeti gör")
    st.space("small")
    style.html(_stage(it, cs))
    st.space("small")
    b = st.columns(3, gap="small")
    b[0].button("Bilemedim", key="fc_bad", icon=":material/close:", width="stretch", on_click=_grade, args=("bad",))
    b[1].button("Atla", key="fc_skip", icon=":material/redo:", width="stretch", on_click=_grade, args=("skip",))
    b[2].button("Bildim", key="fc_good", icon=":material/check:", width="stretch", on_click=_grade, args=("good",))
    gap = K.next_gap(K.history(user=data.uid()).get(it["id"]), "good")
    style.html(f'<div class="nr-gap">Bildim → {_gap(gap)} yeniden · Bilemedim → bugün yine · '
               '<span class="nr-kbd">Boşluk</span> çevir · <span class="nr-kbd">←</span> '
               '<span class="nr-kbd">↓</span> <span class="nr-kbd">→</span></div>')
    _keys()


def _summary() -> None:
    cs, items = st.session_state.cards, _items()
    good, bad, skip = _counts(cs)
    mins = max(1, round((time.time() - cs["started"]) / 60))
    records = [{"status": PILE[r], "diff": C.DIFF_TR.get(items[q]["q"].get("difficulty")),
                "type": C.type_label(items[q]["q"]), "topic": _topic(items[q])}
               for q, r in cs["res"].items() if q in items]
    style.header("Çalış", "Bilgi Kartları")
    style.html(C.summary_html(
        records, ("Bildim", "Bilemedim", "Atladım"), title="Oturum özeti", skip_neutral=True,
        note=f"{len(cs['res'])} kart · en uzun seri {cs['best']} · bilemediklerin bugün yine, bildiklerin günler sonra gelecek.",
        hero_label="İsabet", hero_sub=f"değerlendirdiğin {good + bad} kartın {good} tanesini bildin",
        extra_tile=("Süre", f"{mins} dk")))
    st.space("small")
    c = st.columns([2, 1.4, 2.6])
    if bad:
        c[0].button(f"Bilemediklerimi çalış ({bad})", key="fc_rb", type="primary", icon=":material/replay:",
                    width="stretch", on_click=_only_bad)
    c[1 if bad else 0].button("Yeni oturum", key="fc_new", icon=":material/add:", width="stretch", on_click=_new,
                              type="secondary" if bad else "primary")


def render() -> None:
    if "cards_preset" in st.session_state:  # sınav sonucundan: yanlış / boş sorular kart olarak
        items = _items()
        ids = [q for q in st.session_state.pop("cards_preset") if q in items and K.card_ok(items[q]["q"])]
        if ids:
            _begin(ids)
        else:
            st.session_state.pop("cards", None)
            st.toast("Bu sınavdaki yanlışların şıklı ya da doğru / yanlış sorulardı; karta dönüşmüyor.")
    if "cards" in st.session_state:
        _session()
    else:
        _setup()


render()

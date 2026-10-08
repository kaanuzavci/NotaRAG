"""Ana sayfa: notların (deste kartları), herkese açık notlar, kaldığın yerden devam et.

Örnek alınan düzen: NotebookLM'in not defteri ızgarası (ilk kart "+ Yeni", sonra kişinin defterleri, altında öne
çıkanlar) ve Quizlet'in "kaldığın yerden devam et" satırı. Kartlar src/ui/shelf.py'deki özel bileşenle çizilir;
tıklama Python'a "kimlik|eylem" olarak gelir ve burada ilgili sayfaya yönlendirilir.
"""

import time

import streamlit as st

from src import library, resume
from src import request as R
from src.ui import data, style, upload
from src.ui.shelf import palette, shelf

STEPS = ["okunuyor", "görselden okunuyor", "bölümleniyor", "dizine ekleniyor", "sorular üretiliyor", "doğrulanıyor"]


def _ago(t: float | None) -> str:
    if not t:
        return ""
    s = time.time() - t
    if s < 90:
        return "az önce"
    if s < 3600:
        return f"{round(s / 60)} dk önce"
    if s < 86400:
        return f"{round(s / 3600)} saat önce"
    return "dün" if s < 2 * 86400 else f"{int(s // 86400)} gün önce"


def _greeting() -> str:
    h = time.localtime().tm_hour
    return "Günaydın" if 5 <= h < 12 else ("İyi günler" if h < 18 else "İyi akşamlar")


# ---------------------------------------------------------------- veri → kart

def _doc_card(d: dict, meta: dict, jobs: dict, prog: dict, public_view: bool = False) -> dict:
    stem, job = d["stem"], jobs.get(d["stem"])
    running = job and not job["done"] and not job["failed"] and time.time() - job["started"] < 6 * 3600
    n_topics = len(data.topics(stem)) if d["chunks"] else 0
    card = {"id": stem, "kind": "doc", "title": data.short(stem), "palette": palette(stem, meta.get("order")),
            "sheets": 2 if d["verified"] >= 20 else (1 if d["verified"] else 0)}
    if running:
        step = max(1, job["step"])
        card.update(meta=f"{d['pages']} sayfa" if d["pages"] else "yeni not", badge="İşleniyor", badge_icon="sync",
                    progress=step / 6, live=True, plabel=STEPS[step - 1].capitalize(), pvalue=f"{step}/6",
                    actions=[{"id": "open", "label": "Ayrıntı"}])
        return card
    card["meta"] = f"{d['pages']} sayfa · {n_topics} konu" if d["parsed"] else "işlenmeyi bekliyor"
    if n_topics:  # fişin çizgili satırlarında notun ilk konuları (başlık iki satırsa bir konu: yer kalsın)
        card["lines"] = [t["title"] for t in data.topics(stem)[:1 if len(card["title"]) > 20 else 2]]
    if public_view:
        card.update(badge="Herkese açık", badge_icon="globe", plabel=f"{d['verified']} hazır soru",
                    actions=[{"id": "add", "label": "Notlarıma ekle"}, {"id": "open", "label": "Göz at"}])
        return card
    card.update(badge="Herkese açık" if meta.get("public") else "Gizli",
                badge_icon="globe" if meta.get("public") else "lock")
    p = prog.get(stem)
    if d["verified"] and p and p["n"] and p["seen"]:
        card.update(progress=p["known"] / p["n"], plabel="Bildiğin", pvalue=f"{p['known']} / {p['n']} soru")
    elif d["verified"]:
        card.update(progress=0, plabel="Henüz çalışmadın", pvalue=f"{d['verified']} soru")
    elif not d["parsed"]:
        card.update(plabel="Ayrıntıdan işlemeyi başlat")
    else:
        card.update(plabel=f"{d['verified']} hazır soru")
    card["actions"] = ([{"id": "exam", "label": "Sınav"}, {"id": "cards", "label": "Kartlar"}] if d["verified"]
                       else [{"id": "open", "label": "Ayrıntı"}])
    return card


def _resume_cards(items: dict) -> list[dict]:
    uid, out = data.uid(), []
    cs = resume.load(uid, "cards")
    if cs and cs.get("queue"):
        docs = list(dict.fromkeys(items[q]["doc"] for q in cs["queue"] if q in items))
        res = list(cs.get("res", {}).values())
        out.append({"id": "resume-cards", "illu": "cards", "kicker": "Bilgi kartları",
                    "title": " · ".join(data.short(d) for d in docs[:2]) + (" …" if len(docs) > 2 else ""),
                    "meta": f"{res.count('good')} bildim · {res.count('bad')} bilemedim · {_ago(cs.get('updated'))}",
                    "progress": cs["pos"] / max(1, len(cs["queue"])), "pvalue": f"{cs['pos']} / {len(cs['queue'])} kart",
                    "cta": "Devam et"})
    else:
        out.append({"id": "resume-cards", "illu": "cards", "empty": True, "kicker": "Bilgi kartları",
                    "title": "Yarım kalan kart oturumun yok", "meta": "Zamanı gelen kartlarla yeni bir oturum başlat",
                    "cta": "Kartlara git"})
    ex = resume.load(uid, "exam")
    req = R.load(ex["id"]) if ex else None
    if req and set(req["params"]["docs"]) <= data.visible():
        n = len(R.items_of(req))
        answered = sum(v not in (None, "") for v in ex.get("answers", {}).values())
        out.append({"id": "resume-exam", "illu": "exam", "kicker": "Sınav",
                    "title": f"{n} soruluk sınav · " + ", ".join(data.short(d) for d in req["params"]["docs"][:2]),
                    "meta": f"{len(ex.get('hints', {}))} ipucu · {_ago(ex.get('updated'))}",
                    "progress": answered / max(1, n), "pvalue": f"{answered} / {n} cevap", "cta": "Devam et"})
    else:
        out.append({"id": "resume-exam", "illu": "exam", "empty": True, "kicker": "Sınav",
                    "title": "Yarım kalan sınavın yok", "meta": "Konularını seç, sınavın hazır sorulardan kurulsun",
                    "cta": "Sınav hazırla"})
    return out


# ---------------------------------------------------------------- eylemler

@st.dialog("Yeni not ekle", width="medium")
def _new_note() -> None:
    if upload.uploader("home_up"):
        st.rerun()


def _act(ident: str, action: str) -> None:
    uid = data.uid()
    if ident == "new":
        _new_note()
    elif ident == "resume-cards":
        cs = resume.load(uid, "cards")
        if cs:
            st.session_state.cards = {**{k: v for k, v in cs.items() if k != "updated"}, "last": None}
        st.switch_page("ui/pages/cards.py")
    elif ident == "resume-exam":
        ex = resume.load(uid, "exam")
        if ex and R.load(ex["id"]):
            st.session_state.exam = resume.restore_exam(ex)
        else:
            st.session_state.pop("exam", None)
        st.switch_page("ui/pages/exam.py")
    elif action == "add":
        library.add_to_library(ident, uid)
        st.cache_data.clear()
        st.toast(f"“{data.short(ident)}” notlarına eklendi.", icon=":material/library_add:")
        st.rerun()
    elif action == "exam":
        st.session_state.pop("exam", None)  # yarım sınav kaybolmaz: "kaldığın yerden devam et"te durur
        st.session_state.exam_doc = ident
        st.switch_page("ui/pages/exam.py")
    elif action == "cards":
        st.session_state.pop("cards", None)
        st.session_state.cards_doc = ident
        st.switch_page("ui/pages/cards.py")
    else:
        st.session_state.doc_open = ident
        st.switch_page("ui/pages/documents.py")


# ---------------------------------------------------------------- sayfa

def _section(kicker: str, title: str, sub: str = "") -> None:
    style.html(f'<div class="nr-sec"><div class="k">{style.esc(kicker)}</div><h2>{style.esc(title)}</h2>'
               + (f'<p>{style.esc(sub)}</p>' if sub else "") + "</div>")


def _running(jobs: dict) -> set[str]:
    return {s for s, j in jobs.items() if not j["done"] and not j["failed"] and time.time() - j["started"] < 6 * 3600}


def _mine_shelf() -> None:
    docs, meta, jobs, mine = data.documents(), data.doc_meta(), dict(data.jobs()), data.mine()
    prog = {p["doc"]: p for p in data.mastery()["docs"]}
    own = sorted((d for d in docs if d["stem"] in mine), key=lambda d: -(meta.get(d["stem"], {}).get("created") or 0))
    cards = [{"id": "new", "kind": "new", "title": "Yeni not ekle",
              "sub": "PDF yükle; sistem okur, konulara ayırır ve soruları hazırlar."}]
    cards += [_doc_card(d, meta.get(d["stem"], {}), jobs, prog) for d in own]
    if hit := shelf(cards, key="shelf_mine"):
        _act(*hit)


def _public_shelf() -> None:
    docs, meta, jobs, mine = data.documents(), data.doc_meta(), dict(data.jobs()), data.mine()
    public = [d for d in docs if meta.get(d["stem"], {}).get("public") and d["stem"] not in mine]
    pub = [_doc_card(d, meta.get(d["stem"], {}), jobs, {}, public_view=True) for d in public]
    if hit := shelf(pub, key="shelf_public",
                    empty="Henüz herkese açık not yok. Kendi notunu paylaşmak için notun ayrıntısında "
                          "“Herkese aç”ı kullanabilirsin."):
        _act(*hit)


def _review_today(ids: list[str]) -> None:
    """Bugünün tekrarı: zamanı gelen kartlar (en çok 30) doğrudan oturum olarak açılır."""
    st.session_state.pop("cards", None)
    st.session_state.cards_preset = ids[:30]
    st.switch_page("ui/pages/cards.py")


def render() -> None:
    u = data.user()
    left, right = st.columns([4, 1.25], vertical_alignment="center")
    with left:
        style.html(f'<div class="nr-hello">{style.avatar(u, data.avatar_b64(u["id"]), 58)}<div>'
                   f'<div class="nr-kicker">{style.esc(_greeting())}</div>'
                   f'<h1 class="nr-title">{style.esc(u["name"])}</h1>'
                   f'<div class="nr-hello-sub">{data.home_stats()}</div></div></div>')
    due = data.due_cards()
    if due and right.button(f"Bugünün tekrarı · {min(len(due), 30)} kart", type="primary", icon=":material/style:",
                            width="stretch", key="home_due", help="Tekrar zamanı gelen kartlarınla hemen bir oturum"):
        _review_today(due)
    style.html('<hr class="nr-rule">')

    _section("Notların", "Ders notların", "Bir nota tıkla ya da üzerine gelip sınava, kartlara geç.")
    if _running(dict(data.jobs())) & data.mine():
        st.fragment(run_every=5)(_mine_shelf)()  # işlenen notun kartındaki ilerleme kendiliğinden güncellensin
    else:
        _mine_shelf()

    _section("Paylaşılan", "Herkese açık notlar", "Başkalarının herkesle paylaştığı notlar. Notlarına ekleyip "
             "kendi sınavını ve kartlarını çalışabilirsin.")
    _public_shelf()

    _section("Kaldığın yerden", "Kaldığın yerden devam et",
             "En son yarım bıraktığın kart oturumu ve sınav; çıkış yapsan da burada bekler.")
    if hit := shelf(_resume_cards(data.items()), key="shelf_resume", layout="resume"):
        _act(*hit)


render()

"""Ana sayfa: notların (deste kartları), herkese açık notlar, kaldığın yerden devam et.

Örnek alınan düzen: NotebookLM'in not defteri ızgarası (ilk kart "+ Yeni", sonra kişinin defterleri, altında öne
çıkanlar) ve Quizlet'in "kaldığın yerden devam et" satırı. Üstte kısa bir selam satırı (az yer tutsun, sahne kartların).
Raflar sonsuza uzamaz: notların en çok iki satır, herkese açık notlar bir satır; son kart "Tümünü gör" → Belgeler.
Kartlar src/ui/shelf.py'deki özel bileşenle çizilir; tıklama Python'a "kimlik|eylem" olarak gelir. Bir nota tıklayınca
ayrıntısı bu sayfanın üstünde açılır (src/ui/docview.py), sayfa değişmez.
"""

import time

import streamlit as st

from src import library, resume
from src import request as R
from src.ui import data, docview, style, upload
from src.ui.shelf import all_card, palette, shelf

# Sayfaya özgü: kartlara yer açmak için biraz daha geniş içerik alanı (Belgeler de aynısını kullanır)
_CSS = """<style>
.block-container { max-width: 1320px; padding-left: 3rem; padding-right: 3rem; }
</style>"""


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


@st.dialog("Herkese açık not ekle", width="medium")
def _share_note() -> None:
    """Herkese açık rafındaki "+": kendi gizli notlarından birini herkese aç ya da yeni bir not yükle."""
    uid, meta, mine = data.uid(), data.doc_meta(), data.mine()
    private = [d["stem"] for d in data.documents() if d["stem"] in mine and not meta.get(d["stem"], {}).get("public")
               and library.has_access(d["stem"], uid)]
    st.markdown("**Notlarından birini paylaş**")
    if private:
        pick = st.selectbox("Not", private, format_func=data.short, key="share_pick", label_visibility="collapsed")
        st.caption("Bütün hesaplar sayfalarını, sistemin çıkardığı metni, sorularını ve kanıt alıntılarını görebilecek; "
                   "bu nottan sınav hazırlayıp kart çalışabilecek.")
        st.warning("Bu işlem geri alınamaz: herkese açılan not yeniden gizlenemez.", icon=":material/warning:")
        if st.button("Herkese aç", type="primary", icon=":material/public:", key="share_go"):
            library.publish(pick, uid)
            st.cache_data.clear()
            st.toast(f"“{data.short(pick)}” artık herkese açık.", icon=":material/public:")
            st.rerun()
    else:
        st.caption("Paylaşılabilecek gizli notun yok.")
    st.divider()
    st.markdown("**Ya da yeni bir not yükle**")
    st.caption("Yüklenen not önce gizli olur; işlenmeye başlayınca buradan herkese açabilirsin.")
    if upload.uploader("share_up"):
        st.rerun()


def _see_all(which: str) -> None:
    """"Tümünü gör" → Belgeler sayfası, ilgili süzgeç seçili."""
    st.session_state.docs_filter = which
    st.switch_page("ui/pages/documents.py")


def _resume(ident: str) -> None:
    uid = data.uid()
    if ident == "resume-cards":
        cs = resume.load(uid, "cards")
        if cs:
            st.session_state.cards = {**{k: v for k, v in cs.items() if k != "updated"}, "last": None}
        st.switch_page("ui/pages/cards.py")
    ex = resume.load(uid, "exam")
    if ex and R.load(ex["id"]):
        st.session_state.exam = resume.restore_exam(ex)
    else:
        st.session_state.pop("exam", None)
    st.switch_page("ui/pages/exam.py")


def _review_today(ids: list[str]) -> None:
    """Bugünün tekrarı: zamanı gelen kartlar (en çok 30) doğrudan oturum olarak açılır."""
    st.session_state.pop("cards", None)
    st.session_state.cards_preset = ids[:30]
    st.switch_page("ui/pages/cards.py")


# ---------------------------------------------------------------- sayfa

def _section(title: str, sub: str = "", count: int | None = None) -> None:
    n = f"<small>{count}</small>" if count else ""
    style.html(f'<div class="nr-shelf-h"><h2 class="nr-shelf-t">{style.esc(title)}{n}</h2>'
               + (f'<p>{style.esc(sub)}</p>' if sub else "") + "</div>")


def _hello() -> None:
    """Kısa selam satırı: profil resmi, "İyi günler, Kaan", sayılar; sağda bugünün tekrarı."""
    u = data.user()
    first = (u["name"] or u["username"]).split()[0]
    stats = "".join(f"<span><b>{n}</b> {style.esc(label)}</span>" for n, label in data.home_stats())
    due = data.due_cards()
    if not due:
        stats += "<span>bugün tekrar zamanı gelen kart yok</span>"
    left, right = st.columns([4, 1.35], vertical_alignment="center")
    with left:
        style.html(f'<div class="nr-hello">{style.avatar(u, data.avatar_b64(u["id"]), 50)}<div>'
                   f'<h1 class="nr-hello-t">{style.esc(_greeting())}, {style.esc(first)}</h1>'
                   f'<div class="nr-hello-stats">{stats}</div></div></div>')
    if due and right.button(f"Bugünün tekrarı · {min(len(due), 30)} kart", type="primary", icon=":material/style:",
                            width="stretch", key="home_due", help="Tekrar zamanı gelen kartlarınla hemen bir oturum"):
        _review_today(due)


def _mine_shelf(live: bool = False) -> None:
    """Kişinin notları. live: işlenen not var, raf 5 sn'de bir kendiliğinden yenilenen bir parçanın içinde."""
    docs, meta, jobs, mine = data.documents(), data.doc_meta(), dict(data.jobs()), data.mine()
    prog = {p["doc"]: p for p in data.mastery()["docs"]}
    own = sorted((d for d in docs if d["stem"] in mine), key=lambda d: -(meta.get(d["stem"], {}).get("created") or 0))
    cards = [{"id": "new", "kind": "new", "title": "Yeni not ekle",
              "sub": "PDF yükle; sistem okur, konulara ayırır ve soruları hazırlar."}]
    cards += [docview.card(d, meta.get(d["stem"], {}), jobs, prog) for d in own]
    more = all_card([palette(d["stem"], meta.get(d["stem"], {}).get("order")) for d in own],
                    f"{len(own)} notun hepsi · Belgeler") if own else None
    hit = shelf(cards, key="shelf_mine", rows=2, more=more)
    if not hit:
        return
    if hit[0] == "new":
        _new_note()
    elif hit[0] == "all":
        _see_all("Notlarım")
    else:
        docview.act(*hit, in_fragment=live)


def _public_shelf() -> None:
    """Herkese açık notlar: kişinin kendi paylaştıkları da (eskiden yalnızca başkalarınınki vardı; kullanıcı kendi
    açtığı notu burada bulamadı, 2026-10-08). İlk kart hep "+" (hiç açık not yokken de raf boş kalmaz)."""
    docs, meta, jobs, mine = data.documents(), data.doc_meta(), dict(data.jobs()), data.mine()
    prog = {p["doc"]: p for p in data.mastery()["docs"]}
    public = sorted((d for d in docs if meta.get(d["stem"], {}).get("public")),
                    key=lambda d: -(meta[d["stem"]].get("public_since") or 0))  # en son paylaşılan önce
    cards = [{"id": "share", "kind": "new", "title": "Herkese açık not ekle",
              "sub": "Notlarından birini paylaş ya da yeni bir PDF yükle."}]
    cards += [docview.card(d, meta.get(d["stem"], {}), jobs, prog, public_view=d["stem"] not in mine) for d in public]
    more = all_card([palette(d["stem"], meta.get(d["stem"], {}).get("order")) for d in public],
                    f"{len(public)} herkese açık not") if public else None
    hit = shelf(cards, key="shelf_public", rows=1, more=more)
    if not hit:
        return
    if hit[0] == "share":
        _share_note()
    elif hit[0] == "all":
        _see_all("Herkese açık")
    else:
        docview.act(*hit)


def render() -> None:
    if docview.reading():  # tam ekran okuyucu açık (bir notun sayfaları): sayfanın kendisi çizilmez
        docview.reader_view()
        return
    style.html(_CSS)
    _hello()

    mine, jobs = data.mine(), dict(data.jobs())
    _section("Ders notların", "Bir nota tıkla ya da üzerine gelip sınava, kartlara geç.",
             sum(d["stem"] in mine for d in data.documents()))
    if any(docview.running(s, jobs) for s in mine):
        st.fragment(run_every=5)(_mine_shelf)(True)  # işlenen notun kartındaki ilerleme kendiliğinden güncellensin
    else:
        _mine_shelf()

    _section("Herkese açık notlar", "Herkesle paylaşılan notlar (seninkiler de); başkalarınınkini notlarına ekleyip "
             "kendi sınavını ve kartlarını çalışabilirsin.")
    _public_shelf()

    _section("Kaldığın yerden devam et", "En son yarım bıraktığın kart oturumu ve sınav; çıkış yapsan da burada bekler.")
    if hit := shelf(_resume_cards(data.items()), key="shelf_resume", layout="resume"):
        _resume(hit[0])
    docview.show()


render()

"""Belgeler: bütün notların deste kartları olarak (kendi notların ve herkese açık olanlar). Bir nota tıklayınca
ayrıntısı sayfanın üstünde açılır, arkadaki sayfa hafifçe bulanıklaşır (src/ui/docview.py): ad ve görünürlük,
konular, sayfalar (tam ekran okuyucu: src/ui/reader.py), okuma kalitesi. Üstte süzgeç (Tümü / Notlarım / Herkese
açık), arama (not adı ya da konu başlığı), sıralama ve görünüm düğmesi:
  Sayfalı     ekranda 2 satır × 4 not; sayfa aşağı kaymaz, kalanlar sağdaki okla (ya da ← →) yana kayarak gelir
  Kaydırmalı  bütün notlar alt alta; satırlar sayfa aşağı kaydıkça birer birer belirir
(kullanıcı isteği 2026-10-08; kartlar src/ui/shelf.py: layout="pages" / lazy=True).

Not ekleme ana sayfadaki "+ Yeni not ekle" kartından (src/ui/upload.py); ana sayfadaki "Tümünü gör" buraya getirir.
Belge kütüphanesi (src/library.py): yüklenen not yalnızca yükleyene görünür; istenirse herkese açılır (geri
alınamaz). Sistemde zaten olan bir not (aynı dosya ya da aynı içerik, adı farklı olsa da) yeniden işlenmez,
yükleyenin listesine eklenir."""

import streamlit as st

from src.ui import data, docview, style
from src.ui.shelf import shelf

FILTERS = ["Tümü", "Notlarım", "Herkese açık"]
SORTS = ["En yeni", "Ada göre", "En çok soru"]
VIEWS = {"Sayfalı": ":material/view_carousel:", "Kaydırmalı": ":material/view_agenda:"}
_FOLD = str.maketrans("ÇĞİIÖŞÜçğıöşü", "cgiiosucgiosu")

# Sayfaya özgü: kartlara yer açmak için biraz daha geniş içerik alanı (ana sayfa da aynısını kullanır)
_CSS = """<style>
.block-container { max-width: 1320px; padding-left: 3rem; padding-right: 3rem; }
.st-key-docs_bar { margin: .2rem 0 .1rem; }
.st-key-docs_bar [data-testid="stTextInputRootElement"], .st-key-docs_bar [data-testid="stSelectbox"] [role="group"] {
  background: #FFFDF8 !important; border-color: #DCD3C1 !important; }
</style>"""
# Sayfalı görünüm: sayfa aşağı kaymaz (kartlar ekrana sığacak boyda, kalanlar yana kayar)
_NO_SCROLL = """<style>
[data-testid="stMain"] { overflow: hidden !important; }
.block-container { padding-bottom: 0 !important; }
</style>"""


def _fold(s: str) -> str:
    """Aramada büyük/küçük harf ve Türkçe harf farkı gözetilmez ('ogrenme' → 'Öğrenme')."""
    return s.translate(_FOLD).lower()


def _match(d: dict, words: list[str]) -> bool:
    """Not adı, PDF'in kendi başlığı ya da konu başlıklarından biri bütün kelimeleri içeriyor mu."""
    topics = [t["title"] for t in data.topics(d["stem"])] if d["chunks"] else []
    hay = _fold(" ".join([data.short(d["stem"]), d["title"], *topics]))
    return all(w in hay for w in words)


def _grid(stems: list[str], empty: str, view: str, live: bool = False) -> None:
    """Kartlar. live: işlenen not var, ızgara 5 sn'de bir kendiliğinden yenilenen bir parçanın (fragment) içinde."""
    docs = {d["stem"]: d for d in data.documents()}
    meta, jobs, mine = data.doc_meta(), dict(data.jobs()), data.mine()
    prog = {p["doc"]: p for p in data.mastery()["docs"]}
    cards = [docview.card(docs[s], meta.get(s, {}), jobs, prog, public_view=s not in mine) for s in stems if s in docs]
    if view == "Sayfalı":
        hit = shelf(cards, key="shelf_docs_pages", layout="pages", empty=empty)
    else:
        hit = shelf(cards, key="shelf_docs_rows", lazy=True, empty=empty)
    if hit:
        docview.act(*hit, in_fragment=live)


def render() -> None:
    if docview.reading():  # tam ekran okuyucu açık: sayfanın kendisi çizilmez
        docview.reader_view()
        return
    st.session_state.setdefault("docs_view", "Sayfalı")
    style.html(_CSS + (_NO_SCROLL if st.session_state.docs_view == "Sayfalı" else ""))
    style.html('<div class="nr-head"><h1 class="nr-hello-t">Belgeler</h1><p>Bütün notların. Birine tıkla: konuları ve '
               'sayfaları açılsın; sayfalarına tam ekranda çalışabilirsin.</p></div>')
    docs, meta, mine = data.my_documents(), data.doc_meta(), data.mine()
    if not docs:
        st.info("Henüz notun yok. Ana sayfadaki “Yeni not ekle” kartından bir PDF yükleyebilirsin.",
                icon=":material/library_books:")
        st.page_link("ui/pages/home.py", label="Ana sayfaya git", icon=":material/home:")
        return
    public = {s for s, m in meta.items() if m.get("public")}
    counts = {"Tümü": len(docs), "Notlarım": sum(d["stem"] in mine for d in docs),
              "Herkese açık": sum(d["stem"] in public for d in docs)}
    if want := st.session_state.pop("docs_filter", None):  # ana sayfadaki "Tümünü gör"
        st.session_state.docs_f = want
    st.session_state.setdefault("docs_f", "Tümü")
    bar = st.container(key="docs_bar", horizontal=True, vertical_alignment="center", gap="small")
    pick = bar.segmented_control("Süzgeç", FILTERS, required=True, key="docs_f", label_visibility="collapsed",
                                 format_func=lambda x: f"{x} · {counts[x]}")
    q = bar.text_input("Ara", placeholder="Not ya da konu ara", key="docs_q", icon=":material/search:",
                       label_visibility="collapsed")
    order = bar.selectbox("Sırala", SORTS, key="docs_sort", label_visibility="collapsed", width=160)
    view = bar.segmented_control("Görünüm", list(VIEWS), required=True, key="docs_view", label_visibility="collapsed",
                                 format_func=lambda v: f"{VIEWS[v]} {v}",
                                 help="Sayfalı: ekranda 8 not, kalanlar yana kayar. Kaydırmalı: bütün notlar alt alta.")

    shown = [d for d in docs if pick == "Tümü" or (d["stem"] in mine if pick == "Notlarım" else d["stem"] in public)]
    if words := _fold(q or "").split():
        shown = [d for d in shown if _match(d, words)]
    if order == "Ada göre":
        shown.sort(key=lambda d: _fold(data.short(d["stem"])))
    elif order == "En çok soru":
        shown.sort(key=lambda d: -data.ready().get(d["stem"], 0))
    else:
        shown.sort(key=lambda d: -(meta.get(d["stem"], {}).get("created") or 0))
    empty = (f"“{q}” aramasına uyan not yok." if words else
             "Henüz herkese açık not yok." if pick == "Herkese açık" else "Bu süzgece uyan not yok.")

    stems, jobs = [d["stem"] for d in shown], dict(data.jobs())
    if any(docview.running(s, jobs) for s in stems):
        st.fragment(run_every=5)(_grid)(stems, empty, view, True)  # işlenen notun ilerlemesi kendiliğinden güncellensin
    else:
        _grid(stems, empty, view)
    docview.show()


render()

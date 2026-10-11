"""Belgeler: bütün notların deste kartları olarak (kendi notların ve herkese açık olanlar). Bir nota tıklayınca
ayrıntısı sayfanın üstünde açılır (src/ui/docview.py): ad ve görünürlük, konular, sayfalar (tam ekran okuyucu:
src/ui/reader.py), okuma kalitesi. Üstte süzgeç (Tümü / Notlarım / Herkese açık), arama (not adı ya da konu başlığı),
sıralama ve görünüm düğmesi:
  Sayfalı     ekranda 2 satır × 4 not; sayfa aşağı kaymaz, kalanlar sağdaki okla (ya da ← →) yana kayarak gelir
  Kaydırmalı  bütün notlar alt alta; satırlar sayfa aşağı kaydıkça birer birer belirir
(kullanıcı isteği 2026-10-08; kartlar src/ui/shelf.py: layout="pages" / lazy=True).

Klasörler (kullanıcı isteği 2026-10-09; src/library.py): bir dersin birden çok notu diğerleriyle karışmasın diye kişi
notlarını adlandırdığı klasörlerde toplar. Not ilk yüklendiğinde klasörsüzdür. "Klasör oluştur" ayrı pencere açmaz:
sayfa seçim kipine geçer, kartların köşesinde işaret kutusu belirir, üstte klasörün adı yazılır; "Klasörü oluştur" ile
biter. Klasöre tıklayınca içi açılır (üstte "← Belgeler", "Düzenle" = aynı seçim kipi, adı ve işaretler dolu, sil). Başka
klasördeki not işaretlenirse oradan buraya taşınır. Klasör kişiye özeldir; silinince notlar silinmez. Klasördeki notlar
ana görünümde ayrıca görünmez; arama yapılırken klasörlerin içi de aranır.

Not ekleme ana sayfadaki "+ Yeni not ekle" kartından (src/ui/upload.py); ana sayfadaki "Tümünü gör" buraya getirir.
Belge kütüphanesi (src/library.py): yüklenen not yalnızca yükleyene görünür; istenirse herkese açılır (geri
alınamaz). Sistemde zaten olan bir not (aynı dosya ya da aynı içerik, adı farklı olsa da) yeniden işlenmez,
yükleyenin listesine eklenir."""

import streamlit as st

from src import library
from src.ui import data, docview, style
from src.ui.shelf import folder_card, palette, shelf

FILTERS = ["Tümü", "Notlarım", "Herkese açık"]
SORTS = ["En yeni", "Ada göre", "En çok soru"]
VIEWS = {"Sayfalı": ":material/view_carousel:", "Kaydırmalı": ":material/view_agenda:"}
_FOLD = str.maketrans("ÇĞİIÖŞÜçğıöşü", "cgiiosucgiosu")

# Sayfaya özgü: kartlara yer açmak için biraz daha geniş içerik alanı (ana sayfa da aynısını kullanır)
_CSS = """<style>
.block-container { max-width: none; width: min(1320px, calc(100vw - 300px)); margin: 0 auto; padding-left: 3rem;
  padding-right: 3rem; }
@media (max-width: 768px) { .block-container { width: 100%; padding-left: 1rem; padding-right: 1rem; } }
.st-key-docs_bar { margin: .2rem 0 .1rem; }
.st-key-docs_bar [data-testid="stTextInputRootElement"], .st-key-docs_bar [data-testid="stSelectbox"] [role="group"] {
  background: #FFFDF8 !important; border-color: #DCD3C1 !important; }
.nr-crumb { display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }
.nr-crumb .fi { font: 500 .66rem 'JetBrains Mono', monospace; letter-spacing: .14em; text-transform: uppercase; color: #7A6440;
  background: #EADFC6; border-radius: 999px; padding: .2rem .55rem; }
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


def _folders() -> list[dict]:
    """Kişinin klasörleri; içlerinde yalnızca hâlâ görebildiği notlar."""
    vis = data.visible()
    return [{**f, "docs": [d for d in f["docs"] if d in vis]} for f in library.folders(data.uid())]


def _folder_items(folders: list[dict], meta: dict) -> list[dict]:
    ready = data.ready()
    out = []
    for f in folders:
        n, q = len(f["docs"]), sum(ready.get(d, 0) for d in f["docs"])
        info = f"{n} not · {q} hazır soru" if n else "Boş klasör · notlarını ekle"
        out.append(folder_card(f, [palette(d, meta.get(d, {}).get("order")) for d in f["docs"]], info,
                               [data.short(d) for d in f["docs"]]))
    return out


def _grid(stems: list[str], empty: str, view: str, folders: list[dict] = (), live: bool = False,
          select: dict | None = None) -> None:
    """Kartlar (önce klasörler). live: işlenen not var, ızgara 5 sn'de bir kendiliğinden yenilenen bir parçanın içinde.
    select: seçim kipi → {"key": bileşen anahtarı, "picked": işaretliler, "where": not → bulunduğu klasörün adı}."""
    docs = {d["stem"]: d for d in data.documents()}
    meta, jobs, mine = data.doc_meta(), dict(data.jobs()), data.mine()
    prog = {p["doc"]: p for p in data.mastery()["docs"]}
    cards = [] if select else _folder_items(folders, meta)
    for s in stems:
        if s not in docs:
            continue
        c = docview.card(docs[s], meta.get(s, {}), jobs, prog, public_view=s not in mine)
        if select:
            c["selectable"] = True
            if f := select["where"].get(s):  # başka klasörde: işaretlenirse oradan buraya taşınır
                c.update(badge="Klasörde", badge_icon="folder", meta=f"{c['meta']} · {f}")
        cards.append(c)
    if select:
        shelf(cards, key=select["key"], layout="pages" if view == "Sayfalı" else "grid", lazy=view != "Sayfalı", empty=empty,
              select=select["picked"])
        return
    if view == "Sayfalı":
        hit = shelf(cards, key="shelf_docs_pages", layout="pages", empty=empty)
    else:
        hit = shelf(cards, key="shelf_docs_rows", lazy=True, empty=empty)
    if hit and hit[0].startswith("folder:"):
        st.session_state.docs_folder = hit[0].split(":", 1)[1]
        st.rerun()
    elif hit:
        docview.act(*hit, in_fragment=live)


# ---------------------------------------------------------------- klasör: seçim kipi ve silme

def _begin_select(fid: str | None, name: str, pre: list[str]) -> None:
    """Seçim kipine geç (oluşturma ya da düzenleme). n: her girişte yeni bileşen anahtarı → eski işaretler karışmaz."""
    old = st.session_state.get("docs_select") or {}
    st.session_state.docs_select = {"fid": fid, "n": old.get("n", 0) + 1, "picked": list(pre)}
    st.session_state.docs_fname = name


def _end_select() -> None:
    st.session_state.pop("docs_select", None)


def _picked_now(sel: dict, view: str) -> list[str]:
    """İşaretliler: bileşenin durumu (tıklamalar tarayıcıda anında işlenir), bu çalıştırmadan ÖNCE okunur."""
    state = st.session_state.get(_sel_key(sel, view))
    if state and state.get("sel") is not None:
        sel["picked"] = list(state["sel"])
    return sel["picked"]


def _sel_key(sel: dict, view: str) -> str:
    return f"shelf_docs_{'p' if view == 'Sayfalı' else 'r'}_s{sel['n']}"


def _save_select(sel: dict, name: str) -> None:
    uid, picked = data.uid(), sel["picked"]
    try:
        if sel["fid"]:
            cur = next(f for f in library.folders(uid) if f["id"] == sel["fid"])
            library.rename_folder(uid, sel["fid"], name)
            library.move_to_folder(uid, [d for d in cur["docs"] if d not in picked], None)
            library.move_to_folder(uid, picked, sel["fid"])
            fid = sel["fid"]
        else:
            fid = library.create_folder(uid, name, picked)
    except library.LibraryError as e:
        st.session_state.docs_error = str(e)
        return
    st.session_state.docs_folder = fid  # klasörün içi açılsın
    st.session_state.docs_toast = f"“{' '.join(name.split())}” klasörü kaydedildi."
    _end_select()


@st.dialog("Klasörü sil", width="small")
def _delete_folder(fid: str, name: str, n: int) -> None:
    st.markdown(f"**{name}** klasörü silinsin mi?")
    st.caption(f"İçindeki {n} not silinmez; Belgeler'in ana görünümüne döner." if n else "Klasör boş.")
    c = st.container(horizontal=True, horizontal_alignment="right", gap="small")
    if c.button("Vazgeç", type="tertiary", key="fd_cancel"):
        st.rerun()
    if c.button("Klasörü sil", type="primary", icon=":material/delete:", key="fd_ok"):
        library.delete_folder(data.uid(), fid)
        st.session_state.pop("docs_folder", None)
        st.toast(f"“{name}” klasörü silindi; notları Belgeler'de.", icon=":material/folder_off:")
        st.rerun()


# ---------------------------------------------------------------- sayfa

def _sorted(shown: list[dict], order: str, meta: dict) -> list[dict]:
    if order == "Ada göre":
        return sorted(shown, key=lambda d: _fold(data.short(d["stem"])))
    if order == "En çok soru":
        return sorted(shown, key=lambda d: -data.ready().get(d["stem"], 0))
    return sorted(shown, key=lambda d: -(meta.get(d["stem"], {}).get("created") or 0))


def render() -> None:
    if docview.reading():  # tam ekran okuyucu açık: sayfanın kendisi çizilmez
        docview.reader_view()
        return
    st.session_state.setdefault("docs_view", "Sayfalı")
    style.html(_CSS + (_NO_SCROLL if st.session_state.docs_view == "Sayfalı" else ""))
    docs, meta, mine = data.my_documents(), data.doc_meta(), data.mine()
    folders = _folders()
    open_f = next((f for f in folders if f["id"] == st.session_state.get("docs_folder")), None)
    if open_f is None:
        st.session_state.pop("docs_folder", None)
    if open_f:
        style.html(f'<div class="nr-head nr-crumb"><h1 class="nr-hello-t">{style.esc(open_f["name"])}</h1>'
                   f'<span class="fi">Klasör</span><p>{len(open_f["docs"])} not. Notların burada bir arada; '
                   'birine tıkla, konuları ve sayfaları açılsın.</p></div>')
    else:
        style.html('<div class="nr-head"><h1 class="nr-hello-t">Belgeler</h1><p>Bütün notların. Birine tıkla: konuları ve '
                   'sayfaları açılsın. Bir dersin notlarını <b>klasörde</b> toplayabilirsin.</p></div>')
    if not docs:
        st.info("Henüz notun yok. Ana sayfadaki “Yeni not ekle” kartından bir PDF yükleyebilirsin.",
                icon=":material/library_books:")
        st.page_link("ui/pages/home.py", label="Ana sayfaya git", icon=":material/home:")
        return
    public = {s for s, m in meta.items() if m.get("public")}
    if want := st.session_state.pop("docs_filter", None):  # ana sayfadaki "Tümünü gör"
        st.session_state.docs_f = want
        st.session_state.pop("docs_folder", None)
        _end_select()
        open_f = None
    st.session_state.setdefault("docs_f", "Tümü")
    if msg := st.session_state.pop("docs_toast", None):
        st.toast(msg, icon=":material/folder:")
    sel = st.session_state.get("docs_select")
    bar = st.container(key="docs_bar", horizontal=True, vertical_alignment="center", gap="small")
    if sel:  # ---- seçim kipi: kartları işaretle, adı yaz, oluştur (ayrı pencere yok)
        picked = _picked_now(sel, st.session_state.docs_view)
        bar.button("Vazgeç", icon=":material/close:", key="docs_selx", on_click=_end_select)
        name = bar.text_input("Klasörün adı", key="docs_fname", max_chars=60, label_visibility="collapsed",
                              placeholder="Klasörün adı (ör. BIL 201 · Bilgisayar Mimarisi)")
        q = bar.text_input("Ara", placeholder="Not ara", key="docs_q", icon=":material/search:", label_visibility="collapsed")
        bar.segmented_control("Görünüm", list(VIEWS), required=True, key="docs_view", label_visibility="collapsed",
                              format_func=lambda v: f"{VIEWS[v]} {v}")
        label = "Kaydet" if sel["fid"] else "Klasörü oluştur"
        if bar.button(f"{label} · {len(picked)} not", icon=":material/check:", type="primary", key="docs_selok",
                      disabled=not name.strip() or not picked,
                      help="Önce klasöre bir ad yaz ve en az bir not işaretle"):
            _save_select(sel, name)
            st.rerun()
        if err := st.session_state.pop("docs_error", None):
            st.error(err, icon=":material/error:")
        st.caption("Klasöre koymak istediğin notların köşesindeki daireyi işaretle; adı yazıp kaydet. "
                   "Başka bir klasördeki not işaretlenirse oradan buraya taşınır.")
        words = _fold(q or "").split()
        shown = [d for d in docs if not words or _match(d, words)]
        shown = _sorted(shown, st.session_state.get("docs_sort", "En yeni"), meta)
        where = {d: f["name"] for f in folders if f["id"] != sel["fid"] for d in f["docs"]}
        _grid([d["stem"] for d in shown], f"“{q}” aramasına uyan not yok." if words else "Not yok.",
              st.session_state.docs_view, select={"key": _sel_key(sel, st.session_state.docs_view),
                                                  "picked": picked, "where": where})
        return
    if open_f:
        if bar.button("Belgeler", icon=":material/arrow_back:", key="docs_back", help="Bütün belgelere dön"):
            st.session_state.pop("docs_folder", None)
            st.rerun()
        pick = "Tümü"
    else:
        counts = {"Tümü": len(docs), "Notlarım": sum(d["stem"] in mine for d in docs),
                  "Herkese açık": sum(d["stem"] in public for d in docs)}
        pick = bar.segmented_control("Süzgeç", FILTERS, required=True, key="docs_f", label_visibility="collapsed",
                                     format_func=lambda x: f"{x} · {counts[x]}")
    q = bar.text_input("Ara", placeholder="Not ya da konu ara", key="docs_q", icon=":material/search:",
                       label_visibility="collapsed")
    order = bar.selectbox("Sırala", SORTS, key="docs_sort", label_visibility="collapsed", width=160)
    view = bar.segmented_control("Görünüm", list(VIEWS), required=True, key="docs_view", label_visibility="collapsed",
                                 format_func=lambda v: f"{VIEWS[v]} {v}",
                                 help="Sayfalı: ekranda 8 kart, kalanlar yana kayar. Kaydırmalı: hepsi alt alta.")
    if open_f:
        bar.button("Düzenle", icon=":material/edit:", key="docs_fedit", help="Klasörün adı ve içindeki notlar",
                   on_click=_begin_select, args=(open_f["id"], open_f["name"], open_f["docs"]))
        if bar.button("", icon=":material/delete:", key="docs_fdel", help="Klasörü sil (notlar silinmez)"):
            _delete_folder(open_f["id"], open_f["name"], len(open_f["docs"]))
    else:
        bar.button("Klasör oluştur", icon=":material/create_new_folder:", key="docs_fnew",
                   help="Notlarını işaretleyip bir klasörde topla", on_click=_begin_select, args=(None, "", []))

    words = _fold(q or "").split()
    in_folder = {d for f in folders for d in f["docs"]}
    if open_f:
        shown, shown_folders = [d for d in docs if d["stem"] in open_f["docs"]], []
    else:
        shown = [d for d in docs if pick == "Tümü" or (d["stem"] in mine if pick == "Notlarım" else d["stem"] in public)]
        # klasördeki notlar ana görünümde ayrıca görünmez; arama yapılırken klasörlerin içi de aranır
        shown_folders = [] if pick == "Herkese açık" else folders
        if not words:
            shown = [d for d in shown if d["stem"] not in in_folder]
        else:
            shown_folders = [f for f in shown_folders if all(w in _fold(f["name"]) for w in words)]
    if words:
        shown = [d for d in shown if _match(d, words)]
    shown = _sorted(shown, order, meta)
    empty = (f"“{q}” aramasına uyan not yok." if words else
             "Bu klasör boş. “Düzenle” ile notlarını ekle." if open_f else
             "Henüz herkese açık not yok." if pick == "Herkese açık" else "Bu süzgece uyan not yok.")

    stems, jobs = [d["stem"] for d in shown], dict(data.jobs())
    if any(docview.running(s, jobs) for s in stems):
        st.fragment(run_every=5)(_grid)(stems, empty, view, shown_folders, True)  # işlenen notun ilerlemesi güncellensin
    else:
        _grid(stems, empty, view, shown_folders)
    docview.show()


render()

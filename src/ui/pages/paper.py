"""Sınav Kâğıdı — soru bankasından soru seç, A4 / A3 şablona yerleştir, PDF olarak indir (src/exampaper.py).

Üç adım tek sayfada: 1 · Sorular (süz, tek tek ya da rastgele seç) → 2 · Kâğıt (şablon, başlık, ders, tarih, süre) →
3 · Önizleme ve indirme (kâğıt ve ayrı cevap anahtarı). Kâğıt her değişiklikte yeniden yerleştirilir (yarım saniye);
LLM çağrısı yok. Seçilebilen sorular: doğrulanmış, insanın reddetmediği, hatalı bildirilmemiş ve görebildiğin notlardan.
"""

import datetime
import random

import pandas as pd
import streamlit as st

from src import exampaper as X
from src import request as R
from src.ui import components as C
from src.ui import data, style

TYPES = {"multiple_choice": "Çoktan seçmeli", "true_false": "Doğru / Yanlış", "short_answer": "Kısa cevap"}


@st.cache_data(ttl=30, show_spinner=False)
def _bank(visible: tuple[str, ...]) -> list[dict]:
    """Kâğıda konabilecek sorular: satır sözlükleri (kimlik, soru, belge, konu, tip, zorluk, sayfa)."""
    blocked, rows = R.blocked_ids(), []
    topics = {d: data.topics(d) for d in visible}
    for it in data.items().values():
        q = it["q"]
        if it["doc"] not in visible or not R.usable(it) or it["id"] in blocked or q.get("type") not in TYPES:
            continue
        page = it.get("check", {}).get("evidence_page")
        topic = next((t["title"] for t in topics.get(it["doc"], []) if page in (t.get("pages") or [])), "") or str(it.get("unit") or "")
        rows.append({"id": it["id"], "doc": it["doc"], "topic": topic, "kind": "Hesap" if q.get("compute") else TYPES[q["type"]],
                     "type": q["type"], "diff": C.DIFF_TR.get(q.get("difficulty"), "—"), "page": page,
                     "text": " ".join(str(q["question"]).split())})
    rows.sort(key=lambda r: (r["doc"], r["page"] or 0, r["id"]))
    return rows


@st.cache_data(ttl=60, show_spinner="Kâğıt yerleştiriliyor…")
def _paper(ids: tuple[str, ...], template: str, meta: dict, shuffle_seed: int | None, booklets: bool) -> dict:
    """Bütün çıktılar: kitapçık(lar), cevap anahtarı, optik form, belirtke tablosu ve önizlemeler."""
    items = [data.items()[i] for i in ids if i in data.items()]
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(items)
    m = X.Meta(**meta)
    a = X.prepare(items, m)
    books = {"A": a, "B": X.booklet_b(a, seed=shuffle_seed or 7)} if booklets else {"": a}
    out = {"exams": {}, "info": None, "bp": X.blueprint(a)}
    for name, lst in books.items():
        pdf, info = X.build_exam(lst, template, m, booklet=name)
        out["exams"][name] = (pdf, X.previews(pdf, 80))
        out["info"] = out["info"] or info
    out["key"] = X.build_key(books if booklets else a, m)
    out["sheet"] = X.build_sheet(a, m, ("A", "B") if booklets else ())
    out["sheet_png"] = X.previews(out["sheet"], 80)
    return out


def _filter(bar, label: str, key: str, options: list, fmt, icon: str) -> list:
    """Sabit boyutlu süzgeç düğmesi: tıklayınca seçenekler açılır; düğmede seçili sayı ya da tek seçimin adı yazar."""
    chosen = [o for o in st.session_state.get(key, []) if o in options]
    title = label if not chosen else (f"{label}: {fmt(chosen[0])}" if len(chosen) == 1 else f"{label} · {len(chosen)}")
    with bar.popover(title[:34], icon=icon, type="primary" if chosen else "secondary"):
        st.pills(label, options, selection_mode="multi", format_func=fmt, key=key, label_visibility="collapsed")
    return [o for o in st.session_state.get(key, []) if o in options]


def _clear_filters() -> None:
    for k in ("pp_f_doc", "pp_f_kind", "pp_f_diff"):
        st.session_state[k] = []
    st.session_state.pp_q = ""


def _select(ids: list[str], on: bool) -> None:
    sel = st.session_state.pp_sel
    sel.update(ids) if on else sel.difference_update(ids)
    st.session_state.pp_ver += 1  # tablo yeni seçimle baştan çizilsin


def _random(ids: list[str], n: int) -> None:
    st.session_state.pp_sel = set(random.sample(ids, min(n, len(ids))))
    st.session_state.pp_ver += 1


def render() -> None:
    style.html("<style>.st-key-pp_fbar { min-height: 42px; flex-wrap: nowrap; } .st-key-pp_fbar [data-testid='stTextInput'] "
               "{ flex: 1 1 260px; min-width: 200px; } .st-key-pp_fbar [data-testid='stPopover'] button { white-space: nowrap; }</style>")
    style.header("İçerik", "Sınav Kâğıdı",
                 "Soru bankasından soruları seç, A4 ya da A3 kâğıda yerleştir ve PDF olarak indir. Cevap anahtarı ayrı dosyadır: "
                 "öğrenciye verilen kâğıtta cevap bulunmaz.")
    st.session_state.setdefault("pp_sel", set())
    st.session_state.setdefault("pp_ver", 0)
    visible = tuple(sorted(data.visible()))
    bank = _bank(visible)
    if not bank:
        st.info("Henüz kâğıda konabilecek soru yok. **Belgeler** sayfasından bir not ekle; sorular işlenince burada görünür.",
                icon=":material/upload_file:")
        return
    by_id = {r["id"]: r for r in bank}
    st.session_state.pp_sel &= set(by_id)  # artık görünmeyen / bildirilen sorular seçimden düşer

    # ---------------------------------------------------------------- 1 · sorular
    with st.container(key="nr_card_pp1"):
        st.markdown("##### 1 · Sorular")
        docs = sorted({r["doc"] for r in bank})
        # Süzgeç çubuğu sabit yükseklikte: seçimler açılır kutuların (popover) içinde, düğmenin üstünde yalnızca sayı
        # yazar. Eskiden çoklu seçim kutuları seçtikçe aşağı uzuyor, altındaki tabloyu ve kâğıdı itiyordu.
        kinds_all = ["Çoktan seçmeli", "Doğru / Yanlış", "Kısa cevap", "Hesap"]
        fbar = st.container(key="pp_fbar", horizontal=True, vertical_alignment="center", gap="small")
        f_doc = _filter(fbar, "Not", "pp_f_doc", docs, data.short, ":material/description:")
        f_kind = _filter(fbar, "Tip", "pp_f_kind", kinds_all, str, ":material/category:")
        f_diff = _filter(fbar, "Zorluk", "pp_f_diff", list(C.DIFF_TR.values()), str, ":material/signal_cellular_alt:")
        search = fbar.text_input("Ara", placeholder="Soru metni ya da konu ara", label_visibility="collapsed",
                                 icon=":material/search:", key="pp_q")
        if f_doc or f_kind or f_diff or search:
            fbar.button("Süzgeçleri temizle", type="tertiary", icon=":material/filter_alt_off:", key="pp_fclear",
                        on_click=_clear_filters)
        low = search.casefold().strip()
        shown = [r for r in bank if (not f_doc or r["doc"] in f_doc) and (not f_kind or r["kind"] in f_kind)
                 and (not f_diff or r["diff"] in f_diff) and (not low or low in r["text"].casefold() or low in r["topic"].casefold())]
        sel = st.session_state.pp_sel
        shown_ids = [r["id"] for r in shown]
        b = st.container(horizontal=True, vertical_alignment="bottom", gap="small")
        n_rand = b.selectbox("Rastgele sayı", [10, 15, 20, 25, 30], index=2, width=190)
        b.button(f"{min(n_rand, len(shown))} rastgele seç", icon=":material/shuffle:", on_click=_random,
                 args=(shown_ids, n_rand), disabled=not shown, key="pp_rand",
                 help="Süzgeçteki sorulardan rastgele seçer; önceki seçimin yerine geçer.")
        b.button("Görünenlerin hepsini seç", icon=":material/select_all:", on_click=_select, args=(shown_ids, True),
                 disabled=not shown, key="pp_all")
        b.button("Seçimi temizle", icon=":material/deselect:", on_click=_select, args=(list(sel), False),
                 disabled=not sel, key="pp_none")
        df = pd.DataFrame({"Seç": [r["id"] in sel for r in shown], "Soru": [r["text"] for r in shown],
                           "Not": [data.short(r["doc"]) for r in shown], "Konu": [r["topic"] for r in shown],
                           "Tip": [r["kind"] for r in shown], "Zorluk": [r["diff"] for r in shown],
                           "Sayfa": [r["page"] for r in shown]})
        sig = hash((tuple(f_doc), tuple(f_kind), tuple(f_diff), low))  # süzgeç değişince tablo baştan
        edited = st.data_editor(df, hide_index=True, width="stretch", height=360, key=f"pp_tbl_{st.session_state.pp_ver}_{sig}",
                                disabled=["Soru", "Not", "Konu", "Tip", "Zorluk", "Sayfa"],
                                column_config={"Seç": st.column_config.CheckboxColumn(width="small"),
                                               "Soru": st.column_config.TextColumn(width="large"),
                                               "Sayfa": st.column_config.NumberColumn(format="s.%d", width="small")})
        for r, on in zip(shown, edited["Seç"]):  # tabloda yalnızca görünen satırlar değişir; öbür seçimler korunur
            (sel.add if on else sel.discard)(r["id"])
        chosen = [r for r in bank if r["id"] in sel]
        kinds = {k: sum(r["kind"] == k for r in chosen) for k in dict.fromkeys(r["kind"] for r in chosen)}
        st.caption(f"**{len(chosen)}** soru seçildi" + (" · " + " · ".join(f"{n} {k.lower()}" for k, n in kinds.items()) if kinds else "")
                   + f" · süzgeçte {len(shown)} soru var, bankada toplam {len(bank)}")
    if not chosen:
        st.info("Kâğıt için yukarıdan soru seç ya da rastgele seçtir.", icon=":material/edit_note:")
        return

    # ---------------------------------------------------------------- 2 · kâğıt
    st.space("small")
    with st.container(key="nr_card_pp2"):
        st.markdown("##### 2 · Kâğıt")
        keys = list(X.TEMPLATES)
        tkey = st.segmented_control("Şablon", keys, default="a4_2" if len(chosen) > 20 else "a4_1",
                                    format_func=lambda k: X.TEMPLATES[k].label, key="pp_tpl") or keys[0]
        tpl = X.TEMPLATES[tkey]
        lo, hi = tpl.advice
        fit = "" if lo <= len(chosen) <= hi else f" Bu şablon {lo}–{hi} soru için ayarlı; {len(chosen)} soruda yazı ya da sayfa sayısı değişir."
        st.caption(tpl.note + fit)
        top = st.text_area("Üst yazı (isteğe bağlı) · kâğıdın en üstünde ortalanır, her satır ayrı", height=92, max_chars=300,
                           placeholder="T.C.\nÖRNEK ÜNİVERSİTESİ\nMühendislik Fakültesi · 2026-2027 Güz Dönemi",
                           help="Kurum, fakülte, bölüm, dönem gibi satırlar. Boş bırakırsan yalnızca başlık görünür.")
        a, b2 = st.columns([2, 1], gap="medium")
        title = a.text_input("Sınav başlığı", value="Deneme Sınavı", max_chars=70)
        course = a.text_input("Ders / not adı", value=", ".join(dict.fromkeys(data.short(r["doc"]) for r in chosen))[:90])
        date = b2.date_input("Tarih", value=datetime.date.today(), format="DD.MM.YYYY")
        minutes = b2.number_input("Süre (dakika, 0 = yazma)", 0, 300, 60, step=5)
        c1, c2 = st.columns(2, gap="medium")
        note = c1.text_area("Açıklama (başlığın altında, isteğe bağlı)", value="Her soru eşit puanlıdır.", height=92,
                            max_chars=400, help="Yönerge: süre, puanlama, kurallar. Her satır ayrı yazılır.")
        end = c2.text_area("Sınav sonu yazısı (son sorunun ardından, ortalı)", height=92, max_chars=300,
                           placeholder="Başarılar dilerim.\nDr. Öğr. Üyesi Ad Soyad",
                           help="Hocanın notu, imza, iyi dilek… Boş bırakırsan kâğıt son soruyla biter.")
        t = st.container(horizontal=True, gap="medium")
        points = t.toggle("Soru puanlarını yaz", value=True, help="Her sorunun yanına 100 / soru sayısı puan yazılır.")
        name_box = t.toggle("Ad-soyad satırı", value=True, help="Başlığın altında Ad Soyad / Numara / Puan boşlukları.")
        by_type = t.toggle("Türe göre sırala", value=False, help="Önce çoktan seçmeli, sonra doğru / yanlış, en sonda kısa cevaplar.")
        shuffle = t.toggle("Soruları karıştır", value=False, help="Sıra seçime göre; açıksa rastgele. Aynı kâğıtta sıra sabit kalır.")
        booklets = t.toggle("A / B kitapçığı", value=False,
                            help="İkinci kitapçıkta sorular kendi türü içinde yer değiştirir, şıklar karışır. Tür sırası aynı "
                                 "kaldığı için tek optik form iki kitapçıkta da geçer; cevap anahtarında ikisi ayrı.")
    seed = None
    if shuffle:
        st.session_state.setdefault("pp_seed", 1)
        seed = st.session_state.pp_seed

    # ---------------------------------------------------------------- 3 · önizleme ve indirme
    st.space("small")
    ids = tuple(r["id"] for r in chosen)
    meta = {"title": title.strip() or "Sınav", "course": course.strip(), "date": date.strftime("%d.%m.%Y"), "minutes": int(minutes),
            "note": note.strip(), "top": top.strip(), "end": end.strip(), "points": points, "name_box": name_box, "by_type": by_type}
    try:
        res = _paper(ids, tkey, meta, seed, booklets)
    except Exception as e:  # yerleştirme hatası kullanıcıya düz Türkçe
        st.error(f"Kâğıt yerleştirilemedi: {e}", icon=":material/error:")
        return
    info, slug = res["info"], _slug(meta["title"])
    with st.container(key="nr_card_pp3"):
        st.markdown("##### 3 · Önizleme ve indirme")
        row = st.container(horizontal=True, vertical_alignment="center", gap="small")
        for name, (pdf, _) in res["exams"].items():
            row.download_button(f"Sınav kâğıdı{f' · {name}' if name else ''} (PDF)", pdf, mime="application/pdf",
                                file_name=f"{slug}{f'_{name}' if name else ''}.pdf", icon=":material/download:",
                                type="primary", key=f"pp_dl_{name or 'tek'}")
        row.download_button("Optik form (PDF)", res["sheet"], file_name=f"{slug}_optik_form.pdf", mime="application/pdf",
                            icon=":material/radio_button_checked:", key="pp_dl_sheet")
        row.download_button("Cevap anahtarı (PDF)", res["key"], file_name=f"{slug}_cevap_anahtari.pdf",
                            mime="application/pdf", icon=":material/key:", key="pp_dl_key",
                            help="Belirtke tablosu, kitapçıkların cevapları, çözümler ve kaynak cümleler. Öğrenciye verilmez.")
        if shuffle:
            row.button("Yeniden karıştır", icon=":material/shuffle:", key="pp_reshuffle",
                       on_click=lambda: st.session_state.update(pp_seed=random.randint(1, 10 ** 6)))
        style.html(f'<div class="nr-hello-stats"><span><b>{info["paper"]}</b> kâğıt</span><span><b>{info["pages"]}</b> sayfa</span>'
                   f'<span><b>{info["questions"]}</b> soru</span><span>yazı <b>{info["font"]:g}</b> punto</span>'
                   + ("<span><b>A / B</b> kitapçığı</span>" if booklets else "") + "</div>")
        st.space("small")
        names = [f"{n} kitapçığı" if n else "Sınav kâğıdı" for n in res["exams"]]
        tabs = st.tabs(names + ["Optik form", "Belirtke tablosu"], key="pp_tabs")
        for tab, (name, (_, pngs)) in zip(tabs, res["exams"].items()):
            with tab:
                cols = st.columns(min(len(pngs), 2), gap="medium")
                for i, png in enumerate(pngs):
                    cols[i % len(cols)].image(png, caption=f"Sayfa {i + 1} / {len(pngs)}", width="stretch")
        with tabs[-2]:
            c = st.columns([1, 1], gap="medium")
            c[0].image(res["sheet_png"][0], caption="Optik cevap kâğıdı (A4)", width="stretch")
            c[1].markdown("Her soru için A–D yuvarlakları (doğru / yanlışta **D–Y**), kısa cevaplı sorular için “yazılı” "
                          "kutusu, 10 haneli öğrenci numarası ve kitapçık türü. "
                          + ("B kitapçığında sorular kendi türü içinde yer değiştirdiği için aynı form iki kitapçıkta da geçer."
                             if booklets else ""))
        with tabs[-1]:
            _blueprint(res["bp"])
        st.caption("Önizleme düşük çözünürlüktedir; PDF'te yazılar keskin. Yazdırırken “gerçek boyut” (ölçek %100) seç. "
                   "Sorular yapay zekâ ile üretildi ve kaynağa bağlanıp doğrulandı; sınavda kullanmadan önce gözden geçir.")


def _blueprint(bp: dict) -> None:
    """Belirtke tablosu: konu × bilişsel düzey (Bloom) ve zorluk, soru sayısı ve puan (cevap anahtarında da var)."""
    rows = []
    for r in bp["rows"] + [bp["total"]]:
        row = {"Konu": r["topic"]}
        row.update({X.BLOOM_TR[k]: r["levels"][k] for k in bp["levels"]})
        row.update({X.DIFF_TR[k]: r["diffs"][k] for k in bp["diffs"]})
        row.update({"Soru": r["n"], "Puan": r["points"]})
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                 column_config={"Konu": st.column_config.TextColumn(width="large"),
                                "Puan": st.column_config.NumberColumn(format="%.1f")})
    st.caption("Bilişsel düzey (Bloom) ve zorluk, üretim sırasında her soruya verilen etikettir; zorluk gerçek öğrenci "
               "çözümleri geldikçe güncellenir. Tablo cevap anahtarının ilk sayfasında da var.")


def _slug(s: str) -> str:
    import re
    table = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^A-Za-z0-9]+", "_", s.translate(table)).strip("_") or "sinav"


render()

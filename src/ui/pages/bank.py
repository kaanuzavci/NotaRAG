"""Soru Bankası: bütün sorular — süz, göz at, öğrenci başarısını gör, dışa aktar."""

import streamlit as st

from src import export
from src.textnorm import pretty_math
from src import request as R
from src.ui import components as C
from src.ui import data, style

HUMAN_TR = {"approve": "Onaylandı", "reject": "Reddedildi"}


def render() -> None:
    style.header("İçerik", "Soru Bankası", "Üretilen bütün sorular. Süz, göz at ve Moodle'a, sınav kâğıdına ya da "
                 "tabloya aktar.")
    with st.expander("Gelişmiş", icon=":material/tune:"):
        include_pilot = st.toggle("Pilot ve deney setlerini de göster", value=False,
                                  help="Geliştirme sırasındaki model karşılaştırmalarının soruları (farklı istem/modeller).")
        show_all = st.toggle("Doğrulanamayan soruları da göster", value=False)
    qs = [q for q in data.all_questions(include_pilot=include_pilot) if q["q"].get("type") in C.TYPE_TR]
    if not qs:
        st.info("Henüz soru yok. **Belgeler** sayfasından bir not ekle ya da **Sınav Hazırla** ile soru iste.")
        return
    decs, stats, reps = data.decisions(), data.item_stats(), data.reports()

    with st.container(border=True):
        a, b, c, e = st.columns([2, 2, 2, 3], gap="medium")
        docs = sorted({q["doc"] for q in qs})
        f_doc = a.multiselect("Belge", docs, placeholder="Hepsi", format_func=data.short)
        f_kind = b.multiselect("Tip", list(R.KINDS), placeholder="Hepsi", format_func=R.KINDS.get)
        f_diff = c.multiselect("Zorluk", list(C.DIFF_TR), placeholder="Hepsi", format_func=C.DIFF_TR.get)
        search = e.text_input("Ara", placeholder="soru metninde ara…")

    def keep(q: dict) -> bool:
        return ((show_all or q.get("verification", {}).get("label") == "verified")
                and (not f_doc or q["doc"] in f_doc) and (not f_kind or R.kind(q["q"]) in f_kind)
                and (not f_diff or q["q"].get("difficulty") in f_diff)
                and (not search or search.lower() in q["q"].get("question", "").lower()))

    sel = [q for q in qs if keep(q)]
    st.caption(f"**{len(sel)}** soru" + ("" if show_all else " (yalnızca doğrulanmış)") +
               f" · {sum(q['id'] in stats for q in sel)} tanesi öğrenciler tarafından çözüldü")

    def human(q: dict) -> str:
        if q["id"] in reps and q["id"] not in decs:
            return "Bildirildi"
        return HUMAN_TR.get(decs.get(q["id"], {}).get("decision"), "—")

    st.dataframe(
        [{"Soru": pretty_math(q["q"]["question"]), "Belge": data.short(q["doc"]), "Tip": C.type_label(q["q"]),
          "Zorluk": C.DIFF_TR.get(q["q"].get("difficulty"), "—"), "Sayfa": q.get("check", {}).get("evidence_page"),
          "Öğrenci başarısı": stats.get(q["id"], {}).get("rate"),
          "Çözülme": stats.get(q["id"], {}).get("n", 0), "İnceleme": human(q)} for q in sel],
        hide_index=True, width="stretch", height=460,
        column_config={"Soru": st.column_config.TextColumn(width="large"),
                       "Sayfa": st.column_config.NumberColumn(format="s.%d", width="small"),
                       "Öğrenci başarısı": st.column_config.ProgressColumn(
                           format="percent", min_value=0, max_value=1,
                           help="Sınavlarda bu soruyu doğru cevaplayanların oranı (madde güçlüğü). Herkesin "
                                "yanlış yaptığı bir soru, hatalı cevap anahtarının işareti olabilir."),
                       "Çözülme": st.column_config.NumberColumn(width="small")})

    st.space("small")
    st.markdown("##### Dışa aktar")
    title = st.text_input("Sınav başlığı", value="Ara Sınav Hazırlık Soruları")
    x = st.columns(5, gap="small")
    x[0].download_button("Sınav kâğıdı", export.to_exam_html(sel, title), file_name="notarag_sinav.html",
                         mime="text/html", icon=":material/print:", width="stretch", disabled=not sel,
                         help="Tarayıcıda aç → Yazdır → PDF. Cevap anahtarı, çözümler ve kaynaklar ayrı sayfada.")
    x[1].download_button("Moodle XML", export.to_moodle_xml(sel), file_name="notarag_sorular.moodle.xml",
                         mime="application/xml", icon=":material/school:", width="stretch", disabled=not sel,
                         help="Moodle → Soru bankası → İçe aktar → Moodle XML. Konu kategorileri, zorluk etiketleri, şık "
                              "geri bildirimleri ve çözüm de aktarılır; hesap soruları sayısal soru olarak gelir.")
    x[2].download_button("Moodle (GIFT)", export.to_gift(sel), file_name="notarag_sorular.gift.txt",
                         mime="text/plain", icon=":material/description:", width="stretch", disabled=not sel,
                         help="Moodle → Soru bankası → İçe aktar → GIFT. Kategoriler ve geri bildirimler var; etiketler yok.")
    x[3].download_button("Tablo (CSV)", export.to_csv(sel), file_name="notarag_sorular.csv", mime="text/csv",
                         icon=":material/table:", width="stretch", disabled=not sel)
    x[4].download_button("JSON", export.to_json(sel), file_name="notarag_sorular.json", mime="application/json",
                         icon=":material/data_object:", width="stretch", disabled=not sel)


render()

"""Rapor: sistem nasıl çalışır, ne kadar iyi çalışır (ölçümler), hangi modelle ve ne kadar kotayla."""

import pandas as pd
import streamlit as st

from src import request as R
from src.ui import data, style
from src.ui.parts import evaluation as ev


def _how() -> None:
    docs = data.documents()
    qs = data.all_questions(include_pilot=False) or data.all_questions()
    verified = [q for q in qs if q.get("verification", {}).get("label") == "verified"]
    st.markdown("Bir ders notu **bir kez** işlenir: okunur, konulara ayrılır ve aranabilir hale getirilir. Sınav "
                "isteğinde seçilen her konu için notlarda en ilgili sayfalar **anlamsal aramayla** bulunur (RAG); "
                "sorular yalnızca bu sayfalardan seçilir ya da üretilir. Her soru üç aşamadan geçer: kaynağındaki "
                "cümleye bağlanır (kod), hesap sorusuysa sonucu kodla yeniden hesaplanır (SymPy), sonra **farklı bir "
                "model ailesi** soruyu cevap anahtarını görmeden çözer. Uyuşmayan soru öğrenciye gitmez.")
    st.space("small")
    vision = sum(d["vision_pages"] for d in docs)
    passed = [q for q in qs if q.get("check", {}).get("status") != "rejected"]
    topics = sum(len(data.topics(d["stem"])) for d in docs if d["chunks"])
    style.flow([
        ("Okuma", f"{sum(d['pages'] for d in docs)}", f"sayfa · {vision} görselden"),
        ("Konu haritası", f"{topics}", f"konu · {len(docs)} belge"),
        ("Arama", f"{sum(d['chunks'] for d in docs)}", "parça vektör dizininde"),
        ("Üretim", f"{len(qs)}", "soru (havuz + istekler)"),
        ("Kod kontrolü", f"{len(passed)}", "kanıt, şema, SymPy"),
        ("Kör doğrulama", f"{len(verified)}", "farklı model ailesi"),
    ])
    st.space("small")
    st.caption("Değerler şu ana kadar işlenen bütün belgelerin toplamıdır. Havuz büyüdükçe sınav istekleri hiç model "
               "çağrısı yapmadan karşılanır; kota yalnızca yeni konular ve zorluklar için harcanır.")


def _compute() -> None:
    st.subheader("Hesap soruları: kod kontrolü hataları yakalıyor mu?")
    r = data.eval_json("sonuclar_hesap_kontrol")
    if not r:
        st.info("Henüz ölçüm yok: `python -m eval.compute_check`")
        return
    st.caption(f"Kontrolden geçmiş {r['n_clean']} çoktan seçmeli hesap sorusunun her birine ayrı ayrı kasıtlı hata "
               "eklendi; SymPy kontrolünün hepsini yakalaması beklenir. API çağrısı yok.")
    names = {"wrong_key": "Yanlış cevap anahtarı", "two_correct": "İkinci bir doğru şık",
             "text_mismatch": "Şık metni değeriyle çelişiyor"}
    rows = [{"Eklenen hata": names.get(k, k), "Yakalanan": v["caught"] / v["total"], "Sayı": f"{v['caught']}/{v['total']}"}
            for k, v in r["corruptions"].items()]
    rows.append({"Eklenen hata": "Hatasız soruda yanlış alarm", "Yakalanan": r["false_alarms_on_clean"] / r["n_clean"],
                 "Sayı": f"{r['false_alarms_on_clean']}/{r['n_clean']}"})
    st.dataframe(rows, hide_index=True, width="stretch",
                 column_config={"Yakalanan": st.column_config.ProgressColumn("Oran", format="percent", min_value=0,
                                                                             max_value=1)})


def _students() -> None:
    st.subheader("Öğrenci sonuçları (madde analizi)")
    items, seen = R.all_items(), data.visible()
    items = {q: it for q, it in items.items() if it["doc"] in seen}  # yalnızca görebildiğin notların soruları
    stats = {q: s for q, s in data.item_stats().items() if q in items}
    if not stats:
        st.info("Henüz çözülmüş sınav yok. **Sınav Hazırla** sayfasında çözülen her soru burada sayılır.",
                icon=":material/quiz:")
        return
    rows = [{"Soru": items[q]["q"]["question"], "Çözen kişi": s["n"], "Doğru oranı": s["rate"]}
            for q, s in stats.items()]
    df = pd.DataFrame(rows).sort_values(["Doğru oranı", "Çözen kişi"])
    c = st.columns(3, gap="medium")
    c[0].metric("Çözülen soru", len(df), border=True)
    c[1].metric("Ortalama doğru oranı", f"%{100 * df['Doğru oranı'].mean():.0f}", border=True)
    c[2].metric("Bildirilen soru", sum(q in items for q in data.reports()), border=True)
    st.caption("En düşük doğru oranlı sorular üstte. Her kişinin bir soruyu yalnızca ilk görüşü sayılır (yeniden "
               "çözmeler ve kartta görülmüş sorular sayılmaz). Çok kişinin yanlış yaptığı bir soru, cevap anahtarı "
               "hatasının işareti olabilir; İnceleme'de kontrol edilmeli.")
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"Soru": st.column_config.TextColumn(width="large"),
                                "Doğru oranı": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                               max_value=1)})


def render() -> None:
    style.header("Kalite", "Rapor", "Sistem nasıl çalışıyor ve ne kadar iyi çalışıyor: her sonuç tekrar çalıştırılabilir bir betikten gelir.")
    t = st.tabs(["Nasıl çalışır", "Ölçümler"])
    with t[0]:
        _how()
    with t[1]:
        part = st.segmented_control("Ölçüm", ["Arama", "Doğrulayıcı", "Hesap kontrolü", "Bilişsel düzey",
                                              "Toplu üretim", "İnsan değerlendirmesi", "Öğrenci sonuçları"],
                                    default="Arama", label_visibility="collapsed") or "Arama"
        st.space("small")
        {"Arama": ev._retrieval, "Doğrulayıcı": ev._sensitivity, "Hesap kontrolü": _compute, "Bilişsel düzey": ev._bloom,
         "Toplu üretim": ev._batch, "İnsan değerlendirmesi": ev._human, "Öğrenci sonuçları": _students}[part]()


render()

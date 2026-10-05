"""Değerlendirme: sistemin ne kadar iyi çalıştığının ölçümleri (eval/*.json + insan kararları).

Grafik ilkeleri (dataviz yönergesi): biçim önce, renk sonra; tek eksen; ince işaretler, uçları yuvarlatılmış;
vurgu formu (öne çıkan tek seri renkli, gerisi gri); durum renkleri (#3B8D66 / #D49A2A / #C6503A) doğrulama
betiğinden geçti ve her zaman etiketle birlikte kullanılır; her grafiğin bir tablo karşılığı vardır.
"""

import altair as alt
import pandas as pd
import streamlit as st

from src.ui import data, style

ACCENT, MUTED, SURFACE, INK, GRID = "#3A7BB8", "#CFC8B8", "#F7F4ED", "#1E2433", "#E6DFCF"
STATUS_MARK = {"Doğrulandı": "#3B8D66", "İncelenmeli": "#D49A2A", "Reddedildi": "#C6503A"}


def _theme(ch: alt.Chart) -> alt.Chart:
    return (ch.configure(font="Instrument Sans", background="transparent")
            .configure_view(stroke=None)
            .configure_axis(labelColor="#4A5163", titleColor="#4A5163", gridColor=GRID, domainColor=GRID,
                            tickColor=GRID, labelFontSize=12, titleFontSize=12, titleFontWeight=500)
            .configure_legend(labelColor="#4A5163", titleColor="#4A5163", orient="top", labelFontSize=12)
            .configure_header(labelColor=INK, labelFontSize=12, labelFontWeight=600, titleColor=INK))


def _emphasis_bars(df: pd.DataFrame, x: str, y: str, best: str, fmt: str = ".0%", height: int = 190) -> alt.Chart:
    """Vurgu formu: en iyi yöntem renkli, diğerleri gri; değer etiketleri çubuk ucunda."""
    base = alt.Chart(df).encode(
        y=alt.Y(f"{y}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X(f"{x}:Q", title=None, axis=alt.Axis(format=fmt, grid=True, tickCount=5), scale=alt.Scale(domain=[0, 1])),
        tooltip=[alt.Tooltip(f"{y}:N", title="Yöntem"), alt.Tooltip(f"{x}:Q", format=fmt, title="Değer")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=16, stroke=SURFACE, strokeWidth=2).encode(
        color=alt.condition(alt.datum[y] == best, alt.value(ACCENT), alt.value(MUTED)))
    labels = base.mark_text(align="left", dx=6, color=INK, fontSize=12).encode(text=alt.Text(f"{x}:Q", format=fmt))
    return (bars + labels).properties(height=height)


def _retrieval() -> None:
    st.subheader("Arama: doğru sayfa bulunuyor mu?")
    r = data.eval_json("sonuclar_retrieval")
    if not r:
        st.info("Henüz ölçüm yok: `python -m eval.evaluate_retrieval`")
        return
    modes, groups = r["modes"], r["groups"]
    tot = groups["TÜMÜ"]
    n = int(next(iter(tot.values()))["n"])
    rows = [{"Yöntem": modes[m], "İsabet@1": v["@1"] / n, "İsabet@5": v["@5"] / n, "MRR": v["mrr"] / n} for m, v in tot.items()]
    df = pd.DataFrame(rows)
    best = df.sort_values(["İsabet@5", "MRR"], ascending=False).iloc[0]["Yöntem"]
    st.caption(f"{n} sorgu (elle etiketlenmiş konu sorguları + doğrulanmış üretilmiş sorular), 3 belge. "
               f"İsabet@5: doğru sayfa ilk 5 sonuçta mı? Öne çıkan: **{best}**.")
    st.altair_chart(_theme(_emphasis_bars(df, "İsabet@5", "Yöntem", best)), width="stretch")
    # tablo grafiğin altında, tam genişlikte (yan yana sütunlarda kesiliyordu)
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(format="percent" if c != "MRR" else "%.2f")
                                for c in ["İsabet@1", "İsabet@5", "MRR"]})

    cats = [g for g in groups if g != "TÜMÜ"]
    long = []
    for g in cats:
        gn = int(next(iter(groups[g].values()))["n"])
        for m, v in groups[g].items():
            long.append({"Kategori": f"{g} (n={gn})", "Yöntem": modes[m], "İsabet@5": v["@5"] / gn})
    ldf = pd.DataFrame(long)
    with st.expander("Kategorilere göre (Türkçe→Türkçe, Türkçe sorgu→İngilizce slayt, İngilizce→İngilizce…)"):
        ch = alt.Chart(ldf).mark_bar(cornerRadiusEnd=4, height=11, stroke=SURFACE, strokeWidth=2).encode(
            y=alt.Y("Yöntem:N", title=None, sort=list(modes.values()), axis=alt.Axis(labelLimit=200)),
            x=alt.X("İsabet@5:Q", title=None, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format=".0%", tickCount=3)),
            color=alt.condition(alt.datum["Yöntem"] == best, alt.value(ACCENT), alt.value(MUTED)),
            tooltip=["Kategori", "Yöntem", alt.Tooltip("İsabet@5:Q", format=".0%")],
        ).properties(width=230, height=120).facet(facet=alt.Facet("Kategori:N", title=None), columns=3)
        st.altair_chart(_theme(ch))
        st.caption("Türkçe sorgu → İngilizce slayt durumunda BM25 ve hibrit belirgin şekilde geride: sözcük eşleştirmesi "
                   "yanlış dildeki benzer kelimeleri öne çıkarıyor. Bu ölçüm sonucunda varsayılan arama dense yapıldı.")


def _sensitivity() -> None:
    st.subheader("Doğrulayıcı: kasıtlı hataları yakalıyor mu?")
    s = data.eval_json("sonuclar_duyarlilik")
    if not s:
        st.info("Henüz ölçüm yok: `python -m src.verification.sensitivity …`")
        return
    st.caption("Doğrulanmış sorulardan cevabı bilinen bozuk kopyalar üretildi: yanlış anahtar, iki doğru şık, ters "
               "çevrilmiş D/Y, gerçekte doğru ama slaytta olmayan ifade, yanlış kısa cevap.")
    names = {"wrong_key": "Yanlış cevap anahtarı", "two_correct": "İki doğru şık", "tf_flip": "D/Y ters çevrilmiş",
             "not_in_context": "Slaytta olmayan (dış bilgi)", "short_wrong": "Yanlış kısa cevap"}
    cols = st.columns(len(s), gap="medium")
    for col, (model, r) in zip(cols, s.items()):
        caught = sum(v[0] for v in r["kinds"].values())
        total = sum(v[1] for v in r["kinds"].values())
        col.metric(model.split("/")[-1], f"{caught}/{total}", help="Yakalanan / toplam bozulma", border=True)
    rows = []
    for k, label in names.items():
        row = {"Bozulma": label}
        for model, r in s.items():
            c, t = r["kinds"].get(k, [0, 0])
            row[model.split("/")[-1]] = f"{c}/{t}" if t else "—"
        rows.append(row)
    st.dataframe(rows, hide_index=True, width="stretch")
    first = next((r.get("first_version") for r in s.values() if r.get("first_version")), None)
    if first:
        st.caption(f"İlk sürüm (tek şık seçtiren istem) iki doğru şıkkın {first['two_correct'][0]}/{first['two_correct'][1]}'ini "
                   "yakalıyordu; her şıkkı ayrı değerlendiren istemle tamamı yakalandı.")


def _stacked(df: pd.DataFrame, y: str, title_order: list[str]) -> alt.Chart:
    base = alt.Chart(df).encode(
        y=alt.Y(f"{y}:N", title=None, sort=title_order, axis=alt.Axis(labelLimit=220)),
        x=alt.X("Soru:Q", stack="zero", title=None, axis=alt.Axis(tickCount=5)),
        order=alt.Order("sıra:Q"),
        tooltip=[f"{y}:N", "Durum:N", "Soru:Q"])
    bars = base.mark_bar(height=22, stroke=SURFACE, strokeWidth=2).encode(
        color=alt.Color("Durum:N", scale=alt.Scale(domain=list(STATUS_MARK), range=list(STATUS_MARK.values())),
                        legend=alt.Legend(title=None)))
    labels = base.mark_text(color="white", fontSize=12, fontWeight=600, dx=-6, align="right").encode(
        x=alt.X("bitis:Q"), text=alt.Text("Soru:Q"),
        opacity=alt.condition(alt.datum.Soru >= 2, alt.value(1), alt.value(0)))
    return (bars + labels).properties(height=40 * len(title_order) + 30)


def _with_ends(df: pd.DataFrame, key: str) -> pd.DataFrame:
    df = df.sort_values([key, "sıra"]).copy()
    df["bitis"] = df.groupby(key)["Soru"].cumsum()
    return df


def _bloom() -> None:
    st.subheader("Sadakat ve bilişsel düzey")
    b = data.eval_json("sonuclar_bloom")
    if not b:
        st.info("Henüz ölçüm yok: `python -m eval.bloom_experiment`")
        return
    st.caption("Aynı bölümlerden iki koşulda soru üretildi: yalnızca hatırlama, yalnızca uygulama. Beklenti: uygulama "
               "sorularında dayanaksız soru artar. **Sonuç: iki koşulda da dayanaksız soru oranı "
               + " / ".join(f"%{r['dayanaksız oranı'] * 100:.0f}" for r in b)
               + "**; uygulanacak kural olmayan bölümlerde model soru uydurmak yerine boş liste döndürdü.")
    cond_tr = {"remember": "Yalnızca hatırlama", "apply": "Yalnızca uygulama"}
    rows = []
    for r in b:
        for i, (lab, key) in enumerate([("Doğrulandı", "verified"), ("İncelenmeli", "needs_review"), ("Reddedildi", "rejected")]):
            rows.append({"Koşul": cond_tr.get(r["koşul"], r["koşul"]), "Durum": lab, "Soru": r[key], "sıra": i})
    df = _with_ends(pd.DataFrame(rows), "Koşul")
    a, c = st.columns([3, 2], gap="large")
    with a:
        st.altair_chart(_theme(_stacked(df, "Koşul", [cond_tr[r["koşul"]] for r in b])), width="stretch")
    with c:
        st.dataframe([{"Koşul": cond_tr.get(r["koşul"]), "Soru": r["soru"], "Soru üretmeyen bölüm": r["soru üretmeyen birim"],
                       "Dayanaksız": r["dayanaksız"]} for r in b], hide_index=True, width="stretch")


def _batch() -> None:
    st.subheader("Toplu üretim: tek istek, aynı kalite")
    r = data.eval_json("sonuclar_toplu_uretim")
    if not r:
        st.info("Henüz ölçüm yok: `python -m eval.batch_compare`")
        return
    st.caption("Aynı 12 bölüm (İngilizce slayt → Türkçe soru), aynı kontroller ve aynı doğrulayıcı. Taban: bölüm başına "
               "bir istek. Aday: bütün bölümler tek istekte. Ölçekleri farklı olduğu için tek grafikte gösterilmez.")
    st.dataframe(
        [{"Yöntem": x["yöntem"], "İstek": 12 if "taban" in x["yöntem"] else 1, "Soru": x["soru"],
          "Doğrulanan": x["verified"], "Doğrulanma oranı": x["verified oranı"], "Dayanaksız": x["dayanaksız"]} for x in r],
        hide_index=True, width="stretch",
        column_config={"Doğrulanma oranı": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                       "İstek": st.column_config.NumberColumn(help="Bu iş için yapılan LLM isteği")})


def _human() -> None:
    st.subheader("İnsan değerlendirmesi")
    qs = {q["id"]: q for q in data.all_questions()}
    decs = data.decisions()
    rows = []
    for qid, d in decs.items():
        if qid in qs:
            lab = style.STATUS.get(qs[qid].get("verification", {}).get("label"), ("?",))[0]
            rows.append({"Sistem": lab, "Karar": "Onaylandı" if d["decision"] == "approve" else "Reddedildi"})
    if not rows:
        st.info("Henüz insan kararı yok. **İnceleme** sayfasında verdiğin her karar burada; 'doğrulanan soruların yüzde "
                "kaçı gerçekten iyi?' sorusunun cevabı bu ölçüm.", icon=":material/rate_review:")
        return
    df = pd.DataFrame(rows).value_counts().reset_index(name="Soru")
    ok = df[(df.Sistem == "Doğrulandı") & (df.Karar == "Onaylandı")].Soru.sum()
    tot = df[df.Sistem == "Doğrulandı"].Soru.sum()
    c = st.columns(3, gap="medium")
    c[0].metric("İncelenen", int(df.Soru.sum()), border=True)
    c[1].metric("Doğrulananlarda kabul", f"%{100 * ok / tot:.0f}" if tot else "—", help="Doğrulayıcının isabeti", border=True)
    c[2].metric("Reddedilen", int(df[df.Karar == "Reddedildi"].Soru.sum()), border=True)
    reasons = [r for d in decs.values() for r in d.get("reasons", [])]
    if reasons:
        st.dataframe(pd.Series(reasons).value_counts().rename_axis("Red nedeni").reset_index(name="Kez"),
                     hide_index=True, width="stretch")


def render() -> None:
    style.header("Kalite", "Değerlendirme",
                 "Sistemin ne kadar iyi çalıştığının ölçümleri. Her sonuç, tekrar çalıştırılabilir bir betikten gelir.")
    t = st.tabs(["Arama", "Doğrulayıcı", "Bilişsel düzey", "Toplu üretim", "İnsan değerlendirmesi"])
    with t[0]:
        _retrieval()
    with t[1]:
        _sensitivity()
    with t[2]:
        _bloom()
    with t[3]:
        _batch()
    with t[4]:
        _human()



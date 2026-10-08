"""Sınav Hazırla — sistemin ana kullanımı (src/request.py).

Kullanıcı hazır listeden SEÇER (belge, konu, zorluk, tip, sayı); serbest metin yok. Sistem seçilen konular için
notlarda ilgili sayfaları arar, sınavı önce doğrulanmış hazır sorulardan kurar, eksikleri isteğe bağlı üretir.
Sonra: çöz (puan, zayıf konular, yanlışlarda çözüm ve kaynak, hatalı soru bildirimi) ya da yazdır / Moodle'a aktar.
"""

import streamlit as st

from src import export, resume
from src import request as R
from src.ui import data, style
from src.ui import quiz as Q

DIFF = {"Karışık": None, "Kolay": "easy", "Orta": "medium", "Zor": "hard"}


# ---------------------------------------------------------------- 1. seçim

def _builder() -> None:
    docs = [d for d in data.my_documents() if d["chunks"]]
    if not docs:
        st.info("Önce **Belgeler** sayfasından bir ders notu ekle.", icon=":material/upload_file:")
        return
    names = [d["stem"] for d in docs]
    if (want := st.session_state.pop("exam_doc", None)) in names:  # ana sayfada destedeki "Sınav" düğmesi
        st.session_state.exam_docs = [want]
    if not st.session_state.get("exam_docs") or not set(st.session_state.exam_docs) <= set(names):
        st.session_state.exam_docs = [max(docs, key=lambda d: d["verified"])["stem"]]
    with st.container(key="nr_card_exam"):
        st.markdown("##### 1 · Hangi notlardan?")
        chosen = st.pills("Belgeler", names, selection_mode="multi", format_func=data.short, key="exam_docs",
                          label_visibility="collapsed")
        if not chosen:
            st.caption("En az bir belge seç.")
            return
        st.space("small")
        st.markdown("##### 2 · Hangi konular?")
        opts = [(d, t["title"]) for d in chosen for t in data.topics(d)]
        picked = st.multiselect("Konular", opts, label_visibility="collapsed",
                                placeholder="Boş bırakırsan bütün konulardan",
                                format_func=lambda o: o[1] if len(chosen) == 1 else f"{data.short(o[0])} · {o[1]}")
        st.space("small")
        st.markdown("##### 3 · Nasıl bir sınav?")
        a, b, c = st.columns([3, 4, 2], gap="medium")
        diff = a.segmented_control("Zorluk", list(DIFF), default="Karışık")
        avail = ["multiple_choice", "true_false", "short_answer"]
        if any(data.has_math(d) for d in chosen):
            avail.append("computed")
        kinds = b.pills("Soru tipleri", avail, selection_mode="multi", default=avail, format_func=R.KINDS.get)
        n = c.select_slider("Soru sayısı", [5, 10, 15, 20], value=10)
        st.space("small")
        go = st.button("Sınavı hazırla", type="primary", icon=":material/auto_awesome:", disabled=not kinds)
    if go:
        with st.spinner("Notlarında bu konuları anlatan sayfalar aranıyor…"):
            req = R.prepare(chosen, list(dict.fromkeys(t for _, t in picked)), DIFF[diff or "Karışık"], kinds, n,
                            user=data.uid())
        _open(req["id"])
        st.rerun()


def _open(req_id: str) -> None:
    st.session_state.exam = {"id": req_id, "answers": {}, "submitted": False, "recorded": False, "phase": "start"}
    st.query_params["sinav"] = req_id  # bağlantı paylaşılabilir / sayfa yenilenince sınav kaybolmaz


# ---------------------------------------------------------------- 2. özet ve durum

def _summary(req: dict) -> None:
    p = req["params"]
    diff = next(k for k, v in DIFF.items() if v == p["difficulty"])
    head = st.columns([5, 1.3], vertical_alignment="center")
    head[0].markdown(f"**{p['n']} soruluk sınav** · {', '.join(data.short(d) for d in p['docs'])} · {diff} · "
                     + ", ".join(R.KINDS[k] for k in p["kinds"]))
    if head[1].button("Yeni sınav", icon=":material/add:", width="stretch", key="new_exam_top"):
        st.session_state.pop("exam", None)
        st.query_params.clear()
        st.rerun()
    with st.expander(f"Notlarında bulunan kaynak sayfalar · {len(req['sources'])} konu"):
        lines = []
        for t, srcs in req["sources"].items():
            pages = list(dict.fromkeys(f"{data.short(s['doc'])} s.{s['page']}" for s in srcs))
            lines.append(f"<b>{style.esc(t)}</b> → {style.esc(', '.join(pages))}")
        style.html('<div class="nr-src">' + "<br>".join(lines) + "</div>")
        st.caption("Her konunun adı, notların içinde arama sorgusu olarak kullanıldı (anlamsal arama). Sorular "
                   "yalnızca bulunan bu sayfalardan seçildi ya da üretildi.")


@st.fragment(run_every=3)
def _live(req_id: str) -> None:
    req = R.load(req_id)
    if req["status"] != "generating":
        st.rerun(scope="app")
    with st.container(border=True):
        st.markdown("**Eksik sorular hazırlanıyor**")
        st.progress(_progress_value(req["progress"]), text=req["progress"] or "Başlıyor")
        st.caption("Yeni sorular üretiliyor, kodla kontrol ediliyor ve farklı bir modele cevabı görmeden çözdürülüyor. "
                   "Sayfadan ayrılabilirsin; sınav burada seni bekler. Hazırlanan sorular havuza eklenir; "
                   "aynı konu bir dahaki sefere anında gelir.")


def _progress_value(text: str) -> float:
    import re
    m = re.search(r"(\d+)/(\d+)", text or "")
    return 0.15 + 0.85 * int(m.group(1)) / int(m.group(2)) if m else 0.08


def _status(req: dict, items: list[dict]) -> bool:
    """Sınava geçilebilir mi? Değilse durumu gösterir."""
    n, have = req["params"]["n"], len(items)
    if req["status"] == "generating":
        _live(req["id"])
        return False
    if req["status"] == "partial":
        missing = n - have
        mins = max(1, round((60 + 25 * missing * 1.4) / 60))
        st.info(f"Hazır sorulardan **{have}** tanesi bulundu, **{missing}** soru eksik. Eksikleri şimdi üretebilirsin "
                f"(yaklaşık {mins} dk) ya da hazır olanlarla başlayabilirsin.", icon=":material/inventory_2:")
        c = st.columns([1, 1, 2])
        if c[0].button(f"Eksik {missing} soruyu üret", type="primary", icon=":material/auto_awesome:", width="stretch"):
            R.start(req)
            st.rerun()
        if have and c[1].button(f"{have} soruyla başla", icon=":material/play_arrow:", width="stretch"):
            req["status"] = "done"
            R.save(req)
            st.rerun()
        return False
    if not items:
        st.warning("Bu seçimle sınav hazırlanamadı: uygun soru bulunamadı ya da üretilen sorular doğrulamadan "
                   "geçemedi. Zorluğu ya da soru tiplerini değiştirip yeniden dene.", icon=":material/search_off:")
        return False
    if have < n:
        st.caption(f"İstenen {n} sorunun {have}'i hazırlanabildi. {req.get('progress', '')}")
    return True


# ---------------------------------------------------------------- 3. dışa aktar

def _export(req: dict, items: list[dict]) -> None:
    st.caption("Sınav kâğıdını tarayıcıda açıp **Yazdır → PDF olarak kaydet** ile çıktı alabilirsin; cevap anahtarı, "
               "çözümler ve kaynaklar ayrı sayfadadır. Moodle'a aktarırken (Soru bankası → İçe aktar) **Moodle XML** "
               "önerilir: konu kategorileri, zorluk etiketleri, şık geri bildirimleri ve çözüm de aktarılır; hesap "
               "soruları sayısal soru olarak gelir.")
    title = st.text_input("Sınav başlığı", value="Deneme Sınavı")
    x = st.columns(4, gap="small")
    x[0].download_button("Sınav kâğıdı", export.to_exam_html(items, title), file_name="sinav.html", mime="text/html",
                         icon=":material/print:", width="stretch", type="primary")
    x[1].download_button("Moodle XML", export.to_moodle_xml(items), file_name="sinav.moodle.xml", mime="application/xml",
                         icon=":material/school:", width="stretch")
    x[2].download_button("Moodle (GIFT)", export.to_gift(items), file_name="sinav.gift.txt", mime="text/plain",
                         icon=":material/description:", width="stretch")
    x[3].download_button("Tablo (CSV)", export.to_csv(items), file_name="sinav.csv", mime="text/csv",
                         icon=":material/table:", width="stretch")


# ---------------------------------------------------------------- sayfa

def _remember(ex: dict | None) -> None:
    """Kaldığın yerden devam et (src/resume.py): başlamış ama bitmemiş sınav kişiye kaydedilir (her tıklamada;
    geri çağırmalar betikten önce çalıştığı için burada en son hâli var), bitince silinir."""
    if not ex:
        return
    if ex.get("submitted"):
        resume.clear(data.uid(), "exam")
    elif ex.get("started"):
        resume.save(data.uid(), "exam", ex)


def render() -> None:
    link = st.query_params.get("sinav")
    if "exam" not in st.session_state and link and (shared := R.load(link)):
        # Sınav bağlantısı: açan kişi kendi hesabıyla çözer; ancak sınavın belgelerini görebiliyorsa
        if set(shared["params"]["docs"]) <= data.visible():
            _open(link)
        else:
            st.query_params.clear()
            st.warning("Bu sınav senin göremediğin bir nottan hazırlanmış. Not herkese açılırsa bağlantı çalışır.",
                       icon=":material/lock:")
    ex = st.session_state.get("exam")
    _remember(ex)
    req = R.load(ex["id"]) if ex else None
    items = R.items_of(req) if req else []
    phase = (ex or {}).get("phase") or ("results" if (ex or {}).get("submitted") else "start")
    if req and phase == "solve" and items and req["status"] in ("ready", "done"):
        Q.solve(req, items)  # odak modu: başlık, özet ve kenar çubuğu yok; yalnızca soru
        return
    style.header("Çalış", "Sınav Hazırla",
                 "Konuları seç; sistem notlarında bu konuları anlatan sayfaları bulur ve sınavını doğrulanmış "
                 "sorulardan hazırlar. Eksik kalırsa yenilerini üretip kontrol eder.")
    if not req:
        _builder()
        return
    _summary(req)
    if not _status(req, items):
        return
    if phase == "results":
        Q.results(req, items)
        return
    Q.start_screen(req, items)
    st.space("small")
    with st.expander("Yazdır ya da Moodle'a aktar", icon=":material/print:"):
        _export(req, items)


render()

"""Not yükleme: dosya seçici + soru dili + belge kaydı + işleme başlatma. Belgeler sayfası (açılır panel) ve ana
sayfadaki "+ Yeni not ekle" penceresi aynı akışı kullanır (src/library.py: aynı not yeniden işlenmez)."""

from __future__ import annotations

import time

import streamlit as st

from src import config, library
from src.ui import data

LANGS = {"Belgenin dili": None, "Türkçe": "tr", "İngilizce": "en"}


def uploader(key: str = "up") -> bool:
    """Akışın tamamı. İşleme başlatıldıysa True (çağıran pencereyi kapatıp sayfayı yenileyebilsin)."""
    up = st.file_uploader("PDF dosyası", type=["pdf"], label_visibility="collapsed", key=f"{key}_file")
    lang = st.segmented_control("Soruların dili", list(LANGS), default="Belgenin dili", key=f"{key}_lang",
                                help="İngilizce bir slayttan Türkçe soru üretilebilir; kanıt alıntısı kaynak dilde kalır.")
    started = False
    if up is None:
        st.session_state.pop(f"{key}_res", None)
    else:
        res = st.session_state.get(f"{key}_res")
        if not res or res["file_id"] != up.file_id:  # her yeniden çalıştırmada değil, dosya başına bir kez
            try:
                doc, status = library.register(up.getvalue(), up.name, data.uid())
                res = {"file_id": up.file_id, "doc": doc, "status": status}
            except library.LibraryError as e:
                res = {"file_id": up.file_id, "error": str(e)}
            st.session_state[f"{key}_res"] = res
            st.cache_data.clear()
        started = _result(res, LANGS[lang or "Belgenin dili"], key)
    st.caption("Not okunur (gerekirse görsel okuma), konu haritası çıkarılır ve her konudan doğrulanmış sorularla "
               "bir başlangıç havuzu hazırlanır. Arka planda yürür; sayfayı kapatsan da devam eder. Yüklediğin notu "
               "yalnızca sen görürsün; istersen sonra herkese açabilirsin.")
    return started


def _result(res: dict, lang: str | None, key: str) -> bool:
    if "error" in res:
        st.error(res["error"], icon=":material/error:")
        return False
    d, status = res["doc"], res["status"]
    if status == "new":
        if st.button(f"“{d['name']}” notunu işle", type="primary", icon=":material/play_arrow:", key=f"{key}_run"):
            start(d["file"], lang, key)
            return True
        return False
    if status == "already_yours":
        st.info(f"Bu not zaten listende: **{d['name']}**.", icon=":material/library_books:")
    else:
        how = "Dosyası farklı ama içeriği aynı. " if status == "same_content" else ""
        st.success(f"Bu not sistemde zaten var: **{d['name']}**. {how}Listene eklendi; yeniden işlenmeyecek, hazır "
                   "soruları hemen kullanabilirsin.", icon=":material/check_circle:")
    if lang and not list((config.DATA_DIR / "questions").glob(f"{d['doc']}_{lang}.jsonl")):
        lang_tr = next(k for k, v in LANGS.items() if v == lang)
        if st.button(f"{lang_tr} sorular da üret", icon=":material/translate:", key=f"{key}_lang_run",
                     help="Okuma, konu haritası ve dizin hazır; yalnızca bu dilde sorular üretilir ve doğrulanır."):
            start(d["file"], lang, key)
            return True
    return False


def start(file: str, lang: str | None, key: str = "up") -> None:
    data.start_job(file, lang)
    st.session_state.pop(f"{key}_res", None)
    st.cache_data.clear()
    st.toast("İşleme başladı; ilerlemeyi notun kartında görebilirsin.", icon=":material/rocket_launch:")
    time.sleep(0.6)

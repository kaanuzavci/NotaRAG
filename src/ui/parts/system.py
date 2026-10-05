"""Sistem ve Kota: hangi iş hangi modelle (kanıtıyla), kota kullanımı, ücretli katman maliyeti."""

import streamlit as st

from src.llm.models import APPROVED, CANDIDATES, MODELS
from src.ui import data, style

ROLE_TR = {"vision": "Görsel okuma", "generate": "Soru üretimi (bölüm başına)",
           "generate_batch": "Soru üretimi (toplu, tek istek) · konu haritası", "verify": "Kör doğrulama",
           "judge": "Kısa cevap hakemi", "verify_math": "Hesap sorusunun kör çözümü"}
# Ücretli katman fiyatları (USD / 1M token, girdi-çıktı). Kaynak: LITERATURE.md §7 — kullanmadan önce teyit edilmeli.
PRICE = {"gemini-2.5-flash": (0.30, 2.50), "gemini-3.5-flash": (1.50, 9.00), "gemini-3.8-flash": (0.75, 3.75),
         "openai/gpt-oss-120b": (0.15, 0.60), "openai/gpt-oss-20b": (0.075, 0.30), "qwen/qwen3.8-27b": (0.80, 4.00)}


def _roles() -> None:
    st.subheader("Kalite kapısı")
    st.caption("Bir model bir işe ancak o işin kalite testini geçince atanır; kota dolduğunda sistem test edilmemiş "
               "bir modele geçmez, bekler. Kota hızı etkiler, kaliteyi değil.")
    for role, models in APPROVED.items():
        with st.container(border=True):
            st.markdown(f"**{ROLE_TR.get(role, role)}**")
            for i, (m, why) in enumerate(models.items()):
                c = st.columns([2, 5], vertical_alignment="center")
                c[0].badge(m.split("/")[-1], icon=":material/verified:", color="green" if i == 0 else "blue")
                c[1].caption(("Birincil · " if i == 0 else "Yedek · ") + why)
            for m, why in CANDIDATES.get(role, {}).items():
                c = st.columns([2, 5], vertical_alignment="center")
                c[0].badge(m.split("/")[-1], icon=":material/science:", color="gray")
                c[1].caption(f"Aday — {why}")


def _quota() -> None:
    st.subheader("Kota kullanımı")
    st.caption("Groq: model başına kayan 24 saatte 200 bin token. Gemini: model başına günde 20 istek (Pasifik gece "
               "yarısı sıfırlanır). Değerler sağlayıcının bildirdiği gerçek kullanımdan.")
    rows = [r for r in data.quota() if r["requests"] or r["tokens_24h"]]
    if not rows:
        st.caption("Son 24 saatte kullanım yok.")
    for r in rows:
        name = r["model"].split("/")[-1]
        if r["tpd"]:
            used, lim, unit = r["tokens_24h"], r["tpd"], "token"
        else:
            used, lim, unit = r["requests"], r["rpd"] or 1, "istek"
        frac = min(1.0, used / lim)
        extra = f" · ⏳ {r['cooldown_s'] // 60} dk bekleme" if r.get("cooldown_s") else ""
        st.progress(frac, text=f"**{name}** — {used:,} / {lim:,} {unit}{extra}".replace(",", "."))


def _cost() -> None:
    st.subheader("Ücretli katmanda maliyet")
    st.caption("Ölçülen kullanımla (üretim ~2.700 token/bölüm, doğrulama ~1.000 token/soru, görsel ~2.700 token/sayfa) "
               "kaba hesap. Ücretsiz katman geliştirme içindir; gerçek kullanımda harcama sınırı konarak ücretli katman önerilir.")
    docs = data.documents()
    if not docs:
        return
    pages = sum(d["pages"] for d in docs)
    gin, gout = PRICE["gemini-3.8-flash"]
    vin, vout = PRICE["openai/gpt-oss-120b"]
    per_page = (1.0 * gin + 0.35 * gout) / 1000 + (0.4 * vin + 0.15 * vout) / 1000  # USD / sayfa (kaba)
    c = [st] * 3  # dar sütunda yan yana kutular kesiliyordu; alt alta
    c[0].metric("Şu anki belgeler", f"${per_page * pages:.2f}", help=f"{pages} sayfa", border=True)
    c[1].metric("25 sayfalık bir not", f"${per_page * 25:.3f}", border=True)
    c[2].metric("Bir dönem (28 not × 25 s.)", f"${per_page * 700:.2f}", border=True)
    with st.expander("Fiyat tablosu (1 milyon token, USD)"):
        st.dataframe([{"Model": m, "Girdi": p[0], "Çıktı": p[1]} for m, p in PRICE.items()], hide_index=True,
                     width="stretch")
        st.caption("Gemini: ai.google.dev/gemini-api/docs/pricing · Groq: üçüncü taraf kaynaklar (Eylül 2026). "
                   "Gemini 3.8 Flash fiyatı 1 Ocak 2027'de iki katına çıkıyor.")


def render() -> None:
    style.header("Kalite", "Sistem ve Kota",
                 "Hangi işin hangi modelle yapıldığı ve neden; kotanın ne kadarının kullanıldığı; "
                 "ücretli katmana geçilirse maliyetin ne olacağı.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        _roles()
    with right:
        _quota()
        st.space("small")
        _cost()



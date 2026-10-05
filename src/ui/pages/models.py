"""Modeller ve Kota: sistemin kullandığı modeller, her birinin bugünkü ücretsiz kotası, ne zaman açılacağı, hangi
işte kullanıldığı (kalite kapısı) ve ücretli kullanımda maliyet. Kotalar sağlayıcının bildirdiği gerçek kullanımdan."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from src.llm import ledger
from src.llm.models import APPROVED, CANDIDATES, MODELS
from src.ui import data, style

GOOD, WARN, BAD = "#3B8D66", "#D49A2A", "#C6503A"  # durum renkleri (dataviz doğrulamasından geçti), hep etiketle
ROLE_TR = {"vision": "Görsel okuma", "generate": "Soru üretimi (bölüm bölüm)", "generate_batch": "Soru üretimi (toplu)",
           "verify": "Kör doğrulama", "verify_math": "Hesap sorusu çözümü", "judge": "Kısa cevap hakemi"}
ROLE_WHY = {"vision": "Metni resim olan sayfaları okur.",
            "generate_batch": "Bir belgenin 12 bölümüne kadar tek istekte soru üretir; konu haritası da bununla çıkar.",
            "generate": "Toplu üretim kotası bittiğinde bölüm bölüm üretir.",
            "verify": "Soruyu, üreten modelden farklı bir aile, cevap anahtarını görmeden çözer.",
            "verify_math": "Hesap sorusunu yalnızca metninden çözer; kodun (SymPy) sonucuyla karşılaştırılır.",
            "judge": "Kısa cevapların anlamca aynı olup olmadığına karar verir."}
PROVIDER = {"gemini": "Google Gemini", "groq": "Groq", "openrouter": "OpenRouter (ücretsiz)", "cerebras": "Cerebras"}
# Ücretli katman fiyatları (USD / 1M token, girdi-çıktı). Kaynak: LITERATURE.md §7 — kullanmadan önce teyit edilmeli.
PRICE = {"gemini-2.5-flash": (0.30, 2.50), "gemini-3.5-flash": (1.50, 9.00), "gemini-3.8-flash": (0.75, 3.75),
         "openai/gpt-oss-120b": (0.15, 0.60), "openai/gpt-oss-20b": (0.075, 0.30), "qwen/qwen3.8-27b": (0.80, 4.00)}
TOK_PER_QUESTION, TOK_PER_PAGE, REQ_PER_DOC = 1500, 2700, 2


def _dur(sec: float) -> str:
    m = max(1, round(sec / 60))
    return f"{m // 60} sa {m % 60} dk" if m >= 60 else f"{m} dk"


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _reset_tr() -> str:
    """Gemini'nin günlük kotası Pasifik gece yarısında sıfırlanır; Türkiye saatiyle kaçta?"""
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.astimezone(ZoneInfo("Europe/Istanbul")).strftime("%H:%M")


def _status(color: str, label: str) -> str:
    return f'<span class="nr-st"><i style="background:{color}"></i>{style.esc(label)}</span>'


def _model_state(m: str) -> dict:
    spec, r = MODELS[m], next(x for x in ledger.report() if x["model"] == m)
    if spec.tpd:
        used, lim, unit = r["tokens_24h"], spec.tpd, "token (son 24 saat)"
    else:
        used, lim, unit = r["requests"], spec.rpd or 1, "istek (bugün)"
    frac = min(1.0, used / lim)
    wait = ledger.time_until_available(m, 3000 if spec.tpd else 0)
    if wait > 0:
        state = (BAD, f"Dolu · {_dur(wait)} sonra açılır")
    elif frac >= 0.8:
        state = (WARN, "Az kaldı")
    else:
        state = (GOOD, "Hazır")
    return {"used": used, "lim": lim, "unit": unit, "frac": frac, "wait": wait, "state": state, "left": max(0, lim - used)}


def _capacity() -> None:
    st.markdown("##### Şu an ne yapılabilir?")
    gen = sum(_model_state(m)["left"] for m in APPROVED["generate_batch"] if not _model_state(m)["wait"])
    # Token sınırlı (Groq) doğrulayıcıda ~1.500 token = 1 soru; istek sınırlı (OpenRouter) doğrulayıcıda 1 istek = 1 soru
    ver = sum(_model_state(m)["left"] // (TOK_PER_QUESTION if MODELS[m].tpd else 1)
              for m in APPROVED["verify"] if not _model_state(m)["wait"])
    vis_req = sum(_model_state(m)["left"] for m in APPROVED["vision"] if MODELS[m].provider == "gemini"
                  and not _model_state(m)["wait"])
    vis_tok = sum(_model_state(m)["left"] for m in APPROVED["vision"] if MODELS[m].provider == "groq"
                  and not _model_state(m)["wait"])
    math_wait = min(_model_state(m)["wait"] for m in APPROVED["verify_math"])

    def tile(k: str, v: str, d: str, state: tuple[str, str]) -> str:
        return (f'<div class="nr-tile"><div class="k">{style.esc(k)} {_status(*state)}</div>'
                f'<div class="v">{style.esc(v)}</div><div class="d">{style.esc(d)}</div></div>')

    ok = lambda n, low: (GOOD, "Hazır") if n > low else ((WARN, "Az kaldı") if n > 0 else (BAD, "Dolu"))
    n_ver = ver
    tiles = [
        tile("Soru üretimi", f"≈ {gen // REQ_PER_DOC} belge", f"{gen} toplu istek kaldı (belge başına ~{REQ_PER_DOC}); "
             f"Gemini {_reset_tr()}'da sıfırlanır", ok(gen, 4)),
        tile("Doğrulama", f"≈ {n_ver} soru", f"{len(APPROVED['verify'])} doğrulayıcının kalan kotası; hesap soruları "
             + ("şu an doğrulanabilir" if not math_wait else f"~{_dur(math_wait)} sonra"), ok(n_ver, 15)),
        tile("Görsel okuma", f"≈ {vis_req + vis_tok // TOK_PER_PAGE} sayfa", "Yalnızca metni resim olan sayfalar için",
             ok(vis_req + vis_tok // TOK_PER_PAGE, 5)),
    ]
    style.html('<div class="nr-tiles">' + "".join(tiles) + "</div>")
    st.caption("Hazır sorulardan kurulan sınavlar kota harcamaz; kota yalnızca yeni belge, yeni konu ya da yeni zorluk "
               "için kullanılır. Kota dolduğunda sistem kalite testini geçmemiş bir modele geçmez, bekler.")


def _models() -> None:
    st.markdown("##### Modeller")
    used = list(dict.fromkeys(m for ms in APPROVED.values() for m in ms))
    cards = []
    for m in used:
        s = _model_state(m)
        roles = [ROLE_TR.get(r, r) for r, ms in APPROVED.items() if m in ms]
        reset = (f"Her gün {_reset_tr()}'da (TR saati) sıfırlanır." if MODELS[m].provider == "gemini" else
                 "Her gün 03:00'te (TR saati) sıfırlanır; tüm ücretsiz modeller için toplam." if MODELS[m].provider == "openrouter" else
                 "Kayan 24 saat: eski kullanım düştükçe yer açılır." + (f" Bu iş için ~{_dur(s['wait'])} sonra." if s["wait"] else ""))
        cards.append(
            f'<div class="nr-mcard"><div class="top"><span class="name">{style.esc(m.split("/")[-1])}</span>'
            f'<span class="prov">{PROVIDER.get(MODELS[m].provider, "")}</span>{_status(*s["state"])}</div>'
            f'<div class="roles">{"".join(f"<span class=nr-chip>{style.esc(r)}</span>" for r in roles)}</div>'
            f'<div class="meta"><span>{_n(s["used"])} / {_n(s["lim"])} {s["unit"]}</span><span>%{round(100 * s["frac"])}</span></div>'
            f'<div class="nr-meter"><b style="width:{100 * s["frac"]:.1f}%;background:{s["state"][0]}"></b></div>'
            f'<div class="foot">{style.esc(reset)}</div></div>')
    style.html('<div class="nr-mgrid">' + "".join(cards) + "</div>")


def _roles() -> None:
    st.markdown("##### Hangi iş hangi modelle?")
    st.caption("Bir model bir işe ancak o işin kalite testini geçince eklenir (kalite kapısı). Sıra önemlidir: önce "
               "birincil denenir, kotası doluysa sıradaki. Üzerine gelince testin sonucu görünür.")
    rows = []
    for role, models in APPROVED.items():
        chain = ' <span class="arrow">→</span> '.join(
            f'<span class="nr-chip" title="{style.esc(why)}">{style.esc(m.split("/")[-1])}</span>' for m, why in models.items())
        cand = CANDIDATES.get(role, {})
        cand_html = ("<div class='w'>Aday (henüz onaylı değil): " + ", ".join(
            f"{style.esc(m.split('/')[-1])} ({style.esc(w)})" for m, w in cand.items()) + "</div>") if cand else ""
        rows.append(f'<div class="nr-role"><div><div class="r">{style.esc(ROLE_TR.get(role, role))}</div>'
                    f'<div class="w">{style.esc(ROLE_WHY.get(role, ""))}</div></div>'
                    f'<div><div class="nr-chain">{chain}</div>{cand_html}</div></div>')
    with st.container(border=True):
        style.html("".join(rows))


def _cost() -> None:
    st.markdown("##### Ücretli kullanımda maliyet")
    st.caption("Ücretsiz kota geliştirme ve sunum içindir. Gerçek kullanımda (ör. bir dönem boyunca bir sınıf) harcama "
               "sınırı konarak ücretli katman önerilir. Ölçülen kullanımla kaba hesap: üretim ~2.700 token/bölüm, "
               "doğrulama ~1.000 token/soru.")
    docs = data.documents()
    pages = sum(d["pages"] for d in docs) or 1
    gin, gout = PRICE["gemini-3.8-flash"]
    vin, vout = PRICE["openai/gpt-oss-120b"]
    per_page = (1.0 * gin + 0.35 * gout) / 1000 + (0.4 * vin + 0.15 * vout) / 1000  # USD / sayfa (kaba)
    tiles = [("25 sayfalık bir ders notu", f"${per_page * 25:.3f}", "okuma + soru üretimi + doğrulama"),
             ("Bir dönem", f"${per_page * 700:.2f}", "28 not × 25 sayfa"),
             ("Şu anki belgelerin hepsi", f"${per_page * pages:.2f}", f"{pages} sayfa")]
    style.html('<div class="nr-tiles">' + "".join(
        f'<div class="nr-tile"><div class="k">{style.esc(k)}</div><div class="v">{v}</div><div class="d">{style.esc(d)}</div></div>'
        for k, v, d in tiles) + "</div>")
    with st.expander("Fiyat tablosu (1 milyon token, USD)"):
        st.dataframe([{"Model": m.split("/")[-1], "Girdi": p[0], "Çıktı": p[1]} for m, p in PRICE.items()],
                     hide_index=True, width="stretch")
        st.caption("Gemini: ai.google.dev/gemini-api/docs/pricing · Groq: üçüncü taraf kaynaklar (Eylül 2026). "
                   "Kullanmadan önce güncel fiyatlar kontrol edilmeli.")


def render() -> None:
    style.header("Kalite", "Modeller ve Kota",
                 "Sistemin kullandığı yapay zekâ modelleri, bugünkü ücretsiz kotaları, ne zaman açılacakları ve ücretli "
                 "kullanımda maliyet. Değerler sağlayıcının bildirdiği gerçek kullanımdan.")
    _capacity()
    st.space("medium")
    _models()
    st.space("medium")
    _roles()
    st.space("medium")
    _cost()


render()

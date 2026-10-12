"""Bilgi Kartları — havuzdaki doğrulanmış sorulardan aralıklı tekrar (src/cards.py; LLM çağrısı yok).

NotebookLM'deki gibi: önde soru, arkada cevap ve notundaki kaynak cümle; şık yok (şıksız anlaşılmayan sorular karta
dönüşmez: src/cards.card_ok). Akış: seçim → oturum (kart ortada; tıklayınca döner, yine tıklayınca geri; Bilemedim /
Atla / Bildim → kart ilgili yığına gider, sıradaki desteden gelir) → özet (isabet, zorluğa ve konulara göre).
Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim · K karıştır. Sınav sonucundan "Kartla çalış" buraya gelir.

Oturum ekranı (kullanıcı isteği 2026-10-12; görünüm ve etkileşim src/ui/flashcards.py): tam pencere koyu sahne, solda
"Bilemediklerin", sağda "Bildiklerin" yığını, ortada kart; değerlendirme, çevirme ve karıştırma tarayıcıda anında olur.
Bu sayfa yalnızca bileşenin gönderdiği durumu (sıra + değerlendirme günlüğü) oturuma işler ve yeni değerlendirmeleri
cards.jsonl'e yazar (_apply); bunu yalnızca oturum parçası (st.fragment) yapar, sayfanın geri kalanı yeniden çalışmaz.
Oturum durumu (st.session_state.cards): queue (sıra; atlanan kart bir kez sona eklenir), pos (= değerlendirilen kart
sayısı), log [[kimlik, sonuç]] (log[i] ↔ queue[i]), res, skipped, streak, best, miss, started, ended, tok (oturum
belirteci: yeni oturumda değişir, bileşen eski oturumun durumunu yok sayar).
"""

import secrets
import time

import streamlit as st

from src import cards as K
from src import request as R
from src import resume
from src.ui import data, flashcards, reader, style
from src.ui import components as C

PILE = {"bad": "Bilemedim", "skip": "Atladım", "good": "Bildim"}
# Oturum sayfası: kenar çubuğu ve üst şerit gizli, zemin bileşenle aynı koyu renk (bileşen yüklenirken beyaz parlamasın)
SESSION_CSS = style.focus_css("100%", top="0", extra="""
.stApp { background: #0E1029 !important; }
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stMainBlockContainer"] { padding: 0 !important; }""")
# Canlı kart renkleri (açık, koyu, yazı, vurgu): style.PALETTE'in pastelinden doygun; yazı her zeminde ≥ 6:1
VIVID = [("#E4DBFF", "#B9A4FF", "#2B0F6B", "#6D28D9"),   # mor
         ("#C8F7EA", "#7FE3C9", "#0B4A40", "#0F9F80"),   # nane
         ("#FFE2C6", "#FFB477", "#6B2A08", "#E8590C"),   # turuncu
         ("#D3EEFF", "#8CCBFF", "#08385E", "#1C7ED6"),   # gök
         ("#FFDCEC", "#FF9FCB", "#6E1340", "#D6336C"),   # pembe
         ("#FFF2B8", "#FFD84D", "#5C3D00", "#C88A00")]   # sarı


@st.cache_data(ttl=30)
def _items() -> dict[str, dict]:
    return R.all_items()


def _topic(it: dict) -> str:
    """Kartın konusu: bölüm adı; bölüm adı yalnızca numaraysa ('01') belge adıyla birlikte."""
    unit, doc = str(it.get("unit") or "").strip(), data.short(it.get("doc", ""))
    return unit if len(unit) > 3 and not unit.isdigit() else (f"{doc} · bölüm {unit}" if unit else doc)


# ---------------------------------------------------------------- durum değişiklikleri (düğme geri çağrıları)

def _remember() -> None:
    """Kaldığın yerden devam et (src/resume.py): yarım oturum kişiye kaydedilir, bitince silinir."""
    cs = st.session_state.get("cards")
    if cs and not cs["ended"] and cs["pos"] < len(cs["queue"]):
        resume.save(data.uid(), "cards", {k: v for k, v in cs.items() if k != "last"})
    else:
        resume.clear(data.uid(), "cards")


def _begin(ids: list[str]) -> None:
    st.session_state.cards = {"queue": list(ids), "pos": 0, "log": [], "res": {}, "skipped": [], "streak": 0, "best": 0,
                              "miss": 0, "started": time.time(), "ended": False, "tok": secrets.token_hex(4)}
    _remember()


def _only_bad() -> None:
    bad = [q for q, r in st.session_state.cards["res"].items() if r == "bad"]
    if bad:
        _begin(bad)


def _new() -> None:
    st.session_state.pop("cards", None)
    _remember()


def _norm(cs: dict, items: dict) -> None:
    """Kaydedilmiş (kaldığın yerden) ya da eski biçimli oturumu bu ekranın beklediği biçime getirir: belirteç yoksa
    verilir ve kalan sıradan havuzdan çıkmış sorular ayıklanır; günlük eski biçimdeyse ([sonuç, yüz], 2026-10-09
    ekranı) sıradan ve sonuçlardan yeniden kurulur."""
    if "tok" not in cs:
        cs["tok"] = secrets.token_hex(4)
        cs["queue"] = cs["queue"][:cs["pos"]] + [q for q in cs["queue"][cs["pos"]:] if q in items]
    log = cs.get("log")
    if log is None or len(log) != cs["pos"] or any(e[0] != q for e, q in zip(log, cs["queue"])):
        cs["log"] = [[q, cs["res"].get(q, "skip")] for q in cs["queue"][:cs["pos"]]]
    cs.setdefault("skipped", [])


def _apply(cs: dict, state: dict | None) -> bool:
    """Bileşenden gelen deste durumu → oturum. Günlük birikimli gelir; yalnızca yeni satırlar cards.jsonl'e yazılır
    (oturumun günlüğüne kayıttan önce eklenir: aynı değerlendirme iki kez yazılmaz). Başka bir oturumun (eski belirteç)
    ya da tanımadığı kartları içeren durum yok sayılır. Değişiklik olduysa True."""
    if not state or state.get("tok") != cs["tok"]:
        return False
    queue, log = list(state.get("queue") or []), state.get("log") or []
    known = set(cs["queue"])
    if not queue or not set(queue) <= known or len(log) < len(cs["log"]) or len(log) > len(queue):
        return False
    changed = queue != cs["queue"]
    cs["queue"] = queue
    for qid, result in log[len(cs["log"]):]:
        if result not in K.RESULTS:
            break
        cs["log"].append([qid, result])
        K.record(qid, result, user=data.uid())
        cs["res"][qid] = result
        if result == "skip" and qid not in cs["skipped"]:
            cs["skipped"].append(qid)
        cs["streak"] = cs["streak"] + 1 if result == "good" else (cs["streak"] if result == "skip" else 0)
        cs["miss"] = cs.get("miss", 0) + 1 if result == "bad" else (cs.get("miss", 0) if result == "skip" else 0)
        cs["best"] = max(cs["best"], cs["streak"])
        changed = True
    cs["pos"] = len(cs["log"])
    if state.get("ended") and not cs["ended"]:
        cs["ended"] = changed = True
    return changed


# ---------------------------------------------------------------- bileşene giden veri

def _view(it: dict, hist: dict, now: float) -> dict:
    """Kartın görünümü (metinler HTML'e kaçışlı): ön yüz (soru, zorluk, konu), arka yüz (cevap, çözüm, kanıt) ve
    aralıklı tekrarın ipucu: bu karta Bilemedim / Bildim denirse kaç gün sonra yine gelir (gb / gg; FSRS)."""
    q, page, h = it["q"], it.get("check", {}).get("evidence_page"), hist.get(it["id"])
    n = len(str(q["question"]))
    return {"q": C.t(q["question"]), "len": "xlong" if n > 320 else ("long" if n > 190 else ""),
            "diff": C.DIFF_TR.get(q.get("difficulty"), ""), "topic": style.esc(_topic(it)),
            "ans": C.t(q["options"][q["answer_index"]]) if q["type"] == "multiple_choice" else C.expected(q),
            "sol": [C.t(s) for s in q.get("solution") or []], "ev": C.t(q.get("evidence_quote", "")),
            "where": style.esc(" · ".join(x for x in (data.short(it.get("doc", "")), f"sayfa {page}" if page else "") if x)),
            "page": page, "seen": bool(h and h.get("seen")),
            "gb": K.next_gap(h, "bad", now), "gg": K.next_gap(h, "good", now)}


def _payload(cs: dict, items: dict) -> dict:
    """Bileşenin verisi. Kartların görünümü oturum başına bir kez kurulur (her değerlendirmede yeniden okunmasın)."""
    cache = st.session_state.get("cards_view")
    if not cache or cache[0] != cs["tok"]:
        hist, now = K.history(user=data.uid()), time.time()
        cache = st.session_state.cards_view = (cs["tok"], {q: _view(items[q], hist, now) for q in dict.fromkeys(cs["queue"])
                                                            if q in items})
    docs = list(dict.fromkeys(items[q]["doc"] for q in cs["queue"] if q in items))
    title = " · ".join(data.short(d) for d in docs[:2]) + (f" +{len(docs) - 2}" if len(docs) > 2 else "")
    return {"tok": cs["tok"], "title": title, "cards": cache[1], "queue": cs["queue"], "log": cs["log"],
            "skipped": cs["skipped"], "started": cs["started"], "pal": VIVID, "flip": bool(cs.get("preview_flip"))}


def _counts(cs: dict) -> tuple[int, int, int]:
    res = list(cs["res"].values())
    return res.count("good"), res.count("bad"), res.count("skip")


# ---------------------------------------------------------------- ekranlar

def _setup() -> None:
    style.header("Çalış", "Bilgi Kartları",
                 "Doğrulanmış sorular kart olur: önünde soru, arkasında cevap ve notundaki kaynak cümle. Bildiğin kartlar "
                 "giderek seyrek, bilemediklerin sık gelir (aralıklı tekrar).")
    docs = [d for d in data.my_documents() if d["verified"]]
    if not docs:
        st.info("Henüz doğrulanmış soru yok. Önce **Belgeler** sayfasından bir ders notu ekle.", icon=":material/upload_file:")
        return
    names = [d["stem"] for d in docs]
    if (want := st.session_state.pop("cards_doc", None)) in names:  # ana sayfada destedeki "Kartlar" düğmesi
        st.session_state.cards_docs = [want]
    if "cards_docs" not in st.session_state or not set(st.session_state.cards_docs) <= set(names):
        st.session_state.cards_docs = names
    chosen = st.pills("Belgeler", names, selection_mode="multi", format_func=data.short, key="cards_docs")
    if not chosen:
        st.caption("En az bir belge seç.")
        return
    items, hist, now = K.pool(chosen), K.history(user=data.uid()), time.time()  # kutular kişinin kendi geçmişinden
    s = K.summary(items, hist, now)
    tile = lambda i, v, k: f'<div class="nr-ctile" style="{style.color_vars(i)}"><div class="v">{v}</div><div class="k">{k}</div></div>'
    style.html('<div class="nr-ctiles">' + tile(0, s["total"], "kart") + tile(1, s["due"], "tekrar zamanı gelen")
               + tile(2, s["new"], "hiç görmediğin") + tile(3, s["mastered"], "ustalaştığın") + "</div>")
    c = st.columns([3, 3, 2.2], vertical_alignment="bottom")
    n = c[0].select_slider("Kart sayısı", [10, 20, 30, 50], value=20)
    only_due = c[1].toggle("Yalnızca zamanı gelenler", value=True,
                           help="Açıkken yalnızca hiç görmediğin ve tekrar zamanı gelmiş kartlar gelir.")
    avail = len(K.pick(items, hist, 10 ** 6, now, only_due))
    if c[2].button(f"Başla · {min(n, avail)} kart", key="fc_start", type="primary", icon=":material/style:",
                   width="stretch", disabled=not avail):
        _begin(K.pick(items, hist, n, now, only_due))
        st.rerun()
    if not avail:
        st.caption("Bugün tekrar zamanı gelen kart yok. Yeni tur istersen \"Yalnızca zamanı gelenler\"i kapat.")
    st.caption("Şıksız anlaşılmayan sorular (doğru / yanlış, \"aşağıdakilerden hangisi\") kart olmaz; onlar sınavda.")


def _session() -> None:
    cs, items = st.session_state.cards, _items()
    _norm(cs, items)
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        _summary()
        return
    style.html(SESSION_CSS)
    _live()


@st.fragment
def _live() -> None:
    """Oturum parçası: bileşenin her değerlendirmesinde yalnızca bu çalışır (durum işlenir, kayıt yazılır)."""
    cs, items = st.session_state.get("cards"), _items()
    if not cs or "tok" not in cs:
        return
    key = f"fc_{cs['tok']}"
    if _apply(cs, (st.session_state.get(key) or {}).get("sync")):
        _remember()
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        st.rerun()  # bütün sayfa: özet
    res = flashcards.deck(key=key, data=_payload(cs, items))
    act = res.act or ""
    if act == "leave":  # ara ver: oturum kayıtlı, ana sayfadaki "kaldığın yerden devam et" geri getirir (ara süreye sayılmaz)
        _remember()
        st.session_state.pop("cards", None)
        st.switch_page("ui/pages/home.py")
    if act.startswith("src|") and (it := items.get(act[4:])):
        reader.open_source(it, "cards")  # okuyucu kapanınca aynı karta dönülür (bileşen durumu Python'dan kurar)
        st.rerun()


def _summary() -> None:
    cs, items = st.session_state.cards, _items()
    good, bad, skip = _counts(cs)
    mins = max(1, round((time.time() - cs["started"]) / 60))
    records = [{"status": PILE[r], "diff": C.DIFF_TR.get(items[q]["q"].get("difficulty")),
                "type": C.type_label(items[q]["q"]), "topic": _topic(items[q])}
               for q, r in cs["res"].items() if q in items]
    style.header("Çalış", "Bilgi Kartları")
    style.html(C.summary_html(
        records, ("Bildim", "Bilemedim", "Atladım"), title="Oturum özeti", skip_neutral=True,
        note=f"{len(cs['res'])} kart · en uzun seri {cs['best']} · bilemediklerin bugün yine, bildiklerin günler sonra gelecek.",
        hero_label="İsabet", hero_sub=f"değerlendirdiğin {good + bad} kartın {good} tanesini bildin",
        extra_tile=("Süre", f"{mins} dk")))
    st.space("small")
    c = st.columns([2, 1.4, 2.6])
    if bad:
        c[0].button(f"Bilemediklerimi çalış ({bad})", key="fc_rb", type="primary", icon=":material/replay:",
                    width="stretch", on_click=_only_bad)
    c[1 if bad else 0].button("Yeni oturum", key="fc_new", icon=":material/add:", width="stretch", on_click=_new,
                              type="secondary" if bad else "primary")


def render() -> None:
    if reader.active():  # kartın "Notta kaynağını aç"ı: okuyucu kapanınca aynı karta dönülür
        reader.show(on_close=lambda r, page: None)
        return
    if "cards_preset" in st.session_state:  # sınav sonucundan: yanlış / boş sorular kart olarak
        items = _items()
        ids = [q for q in st.session_state.pop("cards_preset") if q in items and K.card_ok(items[q]["q"])]
        if ids:
            _begin(ids)
        else:
            st.session_state.pop("cards", None)
            st.toast("Bu sınavdaki yanlışların şıklı ya da doğru / yanlış sorulardı; karta dönüşmüyor.")
    if "cards" in st.session_state:
        _session()
    else:
        _setup()


render()

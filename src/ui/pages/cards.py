"""Bilgi Kartları — havuzdaki doğrulanmış sorulardan aralıklı tekrar (src/cards.py; LLM çağrısı yok).

NotebookLM'deki gibi: önde soru, arkada cevap ve notundaki kaynak cümle; şık yok (şıksız anlaşılmayan sorular karta
dönüşmez: src/cards.card_ok). Akış: seçim → oturum (kart ortada; tıklayınca döner, yine tıklayınca geri; Bilemedim /
Atla / Bildim → kart ilgili yığına gider, sıradaki desteden gelir) → özet (isabet, zorluğa ve konulara göre).
Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim. Sınav sonucundan "Kartla çalış" buraya gelir.

Oturum ekranı (kullanıcı isteği 2026-10-09, önceki "sakin, figürsüz" kararının bu ekran için yerine geçer):
  üstte adım adım ilerleme çubuğu: her kart bir parça, bilinen yeşil, bilinemeyen kırmızı; parçanın üstünde o kartın
  sonucuna ve o anki seriye göre bir yüz (🙂 → 😄 → 🤩 → 🥳; bilemeyince 😕 / 😓 → 😢 → 😭; atlayınca 🤔), sıradaki
  kartta düşünen yüz, çubuğun sonunda 💯 (ilerledikçe belirginleşir). Sağında ayrı isabet (🎯) ve seri (🔥; seri
  büyüdükçe alev büyür ve hızlanır) göstergeleri. Ortada canlı renkli, hafif çapraz kart; arkasında çapraz duran sıradaki
  kartlar. Kartın sağında aynı hizada Karıştır ve Bitir. Sol altta çapraz duran not kâğıdı: "Notta kaynağını aç"
  (üzerine gelince sallanır). Arka plan sıcak renk lekeleri (sabit, hareketsiz).
"""

import random
import time

import streamlit as st

from src import cards as K
from src import request as R
from src import resume
from src.ui import data, reader, style
from src.ui import components as C

SYM = {"good": "✓", "bad": "✕", "skip": "↷"}
PILE = {"bad": "Bilemedim", "skip": "Atladım", "good": "Bildim"}
FOCUS_CSS = style.focus_css("1400px", extra=".st-key-fc_keys { height: 0; overflow: hidden; margin: 0; }")
# Canlı kart renkleri (açık, koyu, yazı, vurgu): style.PALETTE'in pastelinden doygun; yazı her zeminde ≥ 6:1
VIVID = [("#E4DBFF", "#B9A4FF", "#2B0F6B", "#6D28D9"),   # mor
         ("#C8F7EA", "#7FE3C9", "#0B4A40", "#0F9F80"),   # nane
         ("#FFE2C6", "#FFB477", "#6B2A08", "#E8590C"),   # turuncu
         ("#D3EEFF", "#8CCBFF", "#08385E", "#1C7ED6"),   # gök
         ("#FFDCEC", "#FF9FCB", "#6E1340", "#D6336C"),   # pembe
         ("#FFF2B8", "#FFD84D", "#5C3D00", "#C88A00")]   # sarı


def _vars(i: int) -> str:
    c1, c2, ink, a = VIVID[i % len(VIVID)]
    return f"--c1:{c1};--c2:{c2};--ink:{ink};--a:{a};--c:{a}"


def _mood(result: str, streak: int, miss: int, prev_streak: int) -> str:
    """Kartın sonucuna ve o anki seriye göre yüz: seri uzadıkça daha mutlu; üst üste bilemedikçe daha üzgün."""
    if result == "good":
        return "🙂" if streak <= 1 else "😊" if streak == 2 else "😄" if streak == 3 else "😁" if streak <= 5 \
            else "😎" if streak <= 7 else "🤩" if streak <= 9 else "🥳"
    if result == "bad":
        return ("😓" if prev_streak >= 3 else "😕") if miss <= 1 else "😢" if miss == 2 else "😭"
    return "🤔"


SESSION_CSS = """<style>
/* Arka plan: sıcak renk lekeleri (sabit; göz yormasın diye soluk ve hareketsiz) */
.stApp { background-color: #F7F2FB !important; background-attachment: fixed !important;
  background-image: radial-gradient(900px 520px at -8% -12%, rgba(185, 164, 255, .38), transparent 62%),
    radial-gradient(780px 520px at 108% 8%, rgba(127, 227, 201, .32), transparent 60%),
    radial-gradient(900px 620px at 50% 118%, rgba(255, 180, 119, .28), transparent 62%),
    radial-gradient(520px 420px at 92% 88%, rgba(255, 159, 203, .22), transparent 60%) !important; }
/* ---- üst şerit: ilerleme çubuğu (adım adım, yüzlerle) + isabet + seri ---- */
.fc-top { display: flex; align-items: stretch; gap: 14px; margin: .2rem 0 .4rem; }
.fc-prog { flex: 1; min-width: 0; display: flex; align-items: flex-end; gap: 12px; padding: 10px 16px 12px; border-radius: 20px;
  background: rgba(255, 255, 255, .78); border: 1px solid rgba(124, 92, 220, .16); box-shadow: 0 10px 26px -20px rgba(60, 40, 120, .5); }
.fc-count { flex: none; font-size: .9rem; color: #4A4F66; white-space: nowrap; padding-bottom: 1px; }
.fc-count b { color: #24164F; font-size: 1.05rem; }
.fc-steps { flex: 1; min-width: 0; display: flex; gap: 3px; align-items: flex-end; }
.fc-cell { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.fc-cell .em { height: 24px; line-height: 24px; font-size: clamp(11px, calc(26px - var(--n) * .3px), 21px); }
.fc-cell i { display: block; width: 100%; height: 11px; border-radius: 6px; background: #E9E3F6; }
.fc-cell:first-child i { border-radius: 8px 4px 4px 8px; } .fc-cell:last-child i { border-radius: 4px 8px 8px 4px; }
.fc-cell.good i { background: linear-gradient(180deg, #4ADE9B, #22B573); }
.fc-cell.bad i { background: linear-gradient(180deg, #FF8A7A, #F0503C); }
.fc-cell.skip i { background: linear-gradient(180deg, #D9CFF0, #B9AED6); }
.fc-cell.cur i { background: repeating-linear-gradient(-45deg, #8E7CFF 0 6px, #B4A7FF 6px 12px); background-size: 34px 100%;
  animation: fc-stripes 1.2s linear infinite; box-shadow: 0 0 0 2px rgba(142, 124, 255, .25); }
.fc-cell.cur .em { animation: fc-bob 1.8s ease-in-out infinite; }
.fc-cell.new .em { animation: fc-pop .7s cubic-bezier(.2, 1.7, .4, 1) both; }
.fc-goal { flex: none; font-size: 26px; line-height: 1; padding-bottom: 0; opacity: calc(.35 + .65 * var(--p));
  filter: grayscale(calc(1 - var(--p))); transform: scale(calc(.85 + .25 * var(--p))); transform-origin: 50% 100%; }
.fc-goal.near { animation: fc-glow 1.4s ease-in-out infinite; }
.fc-chip { flex: none; min-width: 108px; display: flex; align-items: center; gap: 9px; padding: 8px 16px; border-radius: 20px;
  border: 1px solid transparent; box-shadow: 0 10px 26px -20px rgba(60, 40, 120, .5); }
.fc-chip .ic { font-size: 26px; line-height: 1; }
.fc-chip b { display: block; font: 700 1.35rem/1 'Instrument Sans', sans-serif; }
.fc-chip small { display: block; font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; opacity: .8; margin-top: 2px; }
.fc-chip.acc { background: linear-gradient(135deg, #E3F9EE, #BDF0D6); color: #0E5A37; border-color: #9FE3C1; }
.fc-chip.acc.mid { background: linear-gradient(135deg, #FFF4D6, #FFE19A); color: #6B4A00; border-color: #FFD66B; }
.fc-chip.acc.low { background: linear-gradient(135deg, #FFE7E2, #FFC4B8); color: #7A1E0E; border-color: #FFAC9C; }
.fc-chip.acc.none { background: rgba(255, 255, 255, .78); color: #4A4F66; border-color: rgba(124, 92, 220, .16); }
.fc-chip.fire { background: linear-gradient(135deg, #FFF0DC, #FFD2A1); color: #7A2E00; border-color: #FFC07A; }
.fc-chip.fire.cold { background: rgba(255, 255, 255, .78); color: #4A4F66; border-color: rgba(124, 92, 220, .16); }
.fc-chip.fire.hot { background: linear-gradient(135deg, #FFE1C2, #FF9E6B); border-color: #FF8A4C;
  box-shadow: 0 0 0 3px rgba(255, 138, 76, .18), 0 12px 28px -16px rgba(255, 90, 20, .7); }
.fc-flame { display: inline-block; transform-origin: 50% 92%; font-size: calc(24px + var(--f) * 1.4px);
  animation: fc-flick calc(1.15s - var(--f) * .06s) ease-in-out infinite alternate;
  filter: drop-shadow(0 0 calc(2px + var(--f) * 1px) rgba(255, 110, 20, .65)); }
.fc-chip.fire.cold .fc-flame { animation: none; filter: grayscale(1) opacity(.45); }
@keyframes fc-flick { 0% { transform: rotate(-5deg) scale(1, 1); } 35% { transform: rotate(3deg) scale(1.06, 1.14); }
  70% { transform: rotate(-2deg) scale(.97, 1.04); } 100% { transform: rotate(4deg) scale(1.04, 1.1); } }
@keyframes fc-stripes { to { background-position: 34px 0; } }
@keyframes fc-bob { 0%, 100% { transform: translateY(0) rotate(-4deg); } 50% { transform: translateY(-4px) rotate(4deg); } }
@keyframes fc-pop { 0% { transform: scale(0) translateY(8px); opacity: 0; } 60% { transform: scale(1.45) translateY(-4px); opacity: 1; }
  100% { transform: none; } }
@keyframes fc-glow { 0%, 100% { filter: drop-shadow(0 0 0 rgba(255, 60, 60, 0)); } 50% { filter: drop-shadow(0 0 8px rgba(255, 60, 60, .55)); } }
/* ---- kart: canlı, hafif çapraz; arkasında çapraz duran sıradaki kartlar ---- */
.nr-deck { height: clamp(22rem, calc(100vh - 28.5rem), 40rem); margin-top: .6rem; }
.nr-stack { border: 1px solid rgba(43, 15, 107, .08); background: linear-gradient(160deg, var(--s1), var(--s)); }
.nr-stack.s1 { transform: rotate(4.5deg) translate(16px, 8px); opacity: 1; }
.nr-stack.s2 { transform: rotate(-5deg) translate(-18px, 12px); opacity: .95; }
.nr-stack.s3 { transform: rotate(8.5deg) translate(30px, 20px); opacity: .85; }
details.nr-fc { animation: fc-deal .6s .08s cubic-bezier(.22, 1, .36, 1) both; }
@keyframes fc-deal { from { opacity: 0; transform: translate(-30px, -18px) rotate(-8deg) scale(.97); }
  to { opacity: 1; transform: rotate(-1.4deg); } }
.nr-face { box-shadow: 0 2px 4px rgba(43, 15, 107, .06), 0 26px 44px -26px rgba(43, 15, 107, .55); }
.nr-face.front { background: radial-gradient(120% 90% at 0% 0%, rgba(255, 255, 255, .55), transparent 55%),
  linear-gradient(155deg, var(--c1) 0%, var(--c2) 100%); }
.nr-fc .meta span { background: rgba(255, 255, 255, .72); }
/* ---- kartın sağı: Karıştır ve Bitir (kartla aynı hizada, belirgin) ---- */
.st-key-fc_side { gap: .7rem; }
.st-key-fc_side button { min-height: 58px; border-radius: 18px; font-weight: 600; justify-content: flex-start; padding: 0 18px;
  transition: transform .18s, box-shadow .18s; }
.st-key-fc_side button p { font-size: 1rem; font-weight: 600; }
.st-key-fc_shuffle button { background: linear-gradient(135deg, #EDE6FF, #D7CBFF); border: 1px solid #C2B2FF; color: #3B1E8F; }
.st-key-fc_end button { background: linear-gradient(135deg, #2B2160, #1E2433); border: 1px solid #1E2433; color: #FFFFFF; }
.st-key-fc_end button p { color: #FFFFFF; }
.st-key-fc_side button:hover { transform: translateY(-2px); box-shadow: 0 12px 22px -14px rgba(43, 15, 107, .6); }
.st-key-fc_shuffle button:hover { color: #3B1E8F; border-color: #8E7CFF; }
.st-key-fc_end button:hover { color: #FFFFFF; border-color: #2B2160; }
/* değerlendirme düğmeleri: daha canlı */
div.st-key-fc_bad button { background: linear-gradient(135deg, #FFE9E4, #FFD0C6); border-color: #FFB4A4; color: #A3270F; }
div.st-key-fc_skip button { background: linear-gradient(135deg, #F3EEFF, #E2D9FF); border-color: #CFC2FF; color: #4B3C86; }
div.st-key-fc_good button { background: linear-gradient(135deg, #E2F9EC, #BFF0D4); border-color: #95DFB6; color: #0E6A3E; }
div.st-key-fc_bad button:hover { background: #FFC9BC; } div.st-key-fc_skip button:hover { background: #DCD1FF; }
div.st-key-fc_good button:hover { background: #ADEBC7; }
.nr-pile { background: rgba(255, 255, 255, .8); }
.nr-piles { margin-top: 2.4rem; }
/* ---- sol alt: çapraz duran not kâğıdı ("Notta kaynağını aç"), üzerine gelince sallanır ---- */
.st-key-fc_src { position: fixed; left: 34px; bottom: 34px; z-index: 60; width: auto !important; }
.st-key-fc_src button { position: relative; width: 196px; min-height: 148px; padding: 30px 18px 18px; border: 0; border-radius: 3px 3px 22px 3px;
  background: linear-gradient(175deg, #FFF6B8 0%, #FFE680 100%); color: #4A3800; text-align: left; align-items: flex-start;
  justify-content: flex-start; transform: rotate(-7deg); transform-origin: 50% 0;
  box-shadow: 0 2px 0 rgba(0, 0, 0, .04), 0 18px 26px -16px rgba(80, 60, 0, .55);
  background-image: repeating-linear-gradient(to bottom, transparent 0 25px, rgba(160, 120, 0, .16) 25px 26px),
    linear-gradient(175deg, #FFF6B8 0%, #FFE680 100%); background-position: 0 30px, 0 0; }
.st-key-fc_src button::before { content: ""; position: absolute; top: -9px; left: 50%; width: 78px; height: 22px; margin-left: -39px;
  background: rgba(255, 255, 255, .62); border: 1px solid rgba(0, 0, 0, .05); transform: rotate(4deg); }
.st-key-fc_src button p { font: 600 1.08rem/1.35 'Fraunces', serif; color: #4A3800; text-align: left; white-space: normal; }
.st-key-fc_src button:hover { animation: fc-wiggle .7s ease-in-out infinite; color: #4A3800; }
.st-key-fc_src button:focus-visible { outline: 3px solid #8E7CFF; outline-offset: 4px; }
@keyframes fc-wiggle { 0%, 100% { transform: rotate(-7deg); } 25% { transform: rotate(-2.5deg); } 50% { transform: rotate(-9deg); }
  75% { transform: rotate(-4deg); } }
@media (max-width: 1180px) { .st-key-fc_src { position: static; margin: 1rem auto 0; } .st-key-fc_src button { transform: rotate(-2deg); } }
@media (prefers-reduced-motion: reduce) { .fc-cell .em, .fc-cell i, .fc-flame, .fc-goal, .st-key-fc_src button { animation: none !important; } }
</style>"""


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
    v = st.session_state.get("cards", {}).get("v", 0) + 1  # yeni tur da kartı sıfırdan çizdirsin
    st.session_state.cards = {"queue": list(ids), "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0,
                              "best": 0, "last": None, "started": time.time(), "ended": False, "v": v}
    _remember()


def _grade(result: str) -> None:
    cs = st.session_state.cards
    if cs["pos"] >= len(cs["queue"]):
        return
    qid = cs["queue"][cs["pos"]]
    K.record(qid, result, user=data.uid())
    if result == "skip" and qid not in cs["skipped"]:
        cs["skipped"].append(qid)
        cs["queue"].append(qid)  # destenin sonuna; ikinci kez atlanırsa bir sonraki oturuma kalır
    cs["res"][qid], cs["col"][qid] = result, cs["pos"]
    prev = cs["streak"]
    cs["streak"] = cs["streak"] + 1 if result == "good" else (cs["streak"] if result == "skip" else 0)
    cs["miss"] = cs.get("miss", 0) + 1 if result == "bad" else (cs.get("miss", 0) if result == "skip" else 0)
    cs.setdefault("log", []).append([result, _mood(result, cs["streak"], cs["miss"], prev)])  # parça başına yüz
    cs["best"] = max(cs["best"], cs["streak"])
    q = _items().get(qid, {}).get("q", {})
    cs["last"] = {"result": result, "pos": cs["pos"], "text": str(q.get("question", ""))[:140]}
    cs["pos"] += 1
    cs["v"] += 1
    _remember()


def _shuffle() -> None:
    """Kalan kartların (ekrandaki dahil) sırasını karıştırır. Eskiden ekrandaki kart yerinde kalıyordu, ekranda hiçbir şey
    değişmiyor ve düğme çalışmıyor gibi görünüyordu: şimdi yeni bir kart gelir (v artar → kart yeniden dağıtılır) ve bildirim çıkar."""
    cs = st.session_state.cards
    rest = cs["queue"][cs["pos"]:]
    if len(rest) < 2:
        st.toast("Karıştırılacak başka kart kalmadı.", icon=":material/shuffle:")
        return
    first = rest[0]
    for _ in range(5):  # ekrandaki kart aynı kalmasın (küçük destelerde rastlantı olabilir)
        random.shuffle(rest)
        if rest[0] != first:
            break
    cs["queue"][cs["pos"]:] = rest
    cs["v"] += 1
    _remember()
    st.toast(f"Kalan {len(rest)} kart karıştırıldı.", icon=":material/shuffle:")


def _only_bad() -> None:
    bad = [q for q, r in st.session_state.cards["res"].items() if r == "bad"]
    if bad:
        _begin(bad)


def _end() -> None:
    st.session_state.cards["ended"] = True
    _remember()


def _new() -> None:
    st.session_state.pop("cards", None)
    _remember()


# ---------------------------------------------------------------- HTML parçaları

def _front(it: dict) -> str:
    q = it["q"]
    meta = "".join(f"<span>{style.esc(t)}</span>" for t in (C.DIFF_TR.get(q.get("difficulty"), ""), _topic(it)) if t)
    return (f'<div class="meta">{meta}</div><div class="body"><div class="fq">{C.t(q["question"])}</div></div>'
            '<div class="hint">Cevabı görmek için karta tıkla · Boşluk</div>')


def _back(it: dict) -> str:
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    ans = C.t(q["options"][q["answer_index"]]) if q["type"] == "multiple_choice" else C.expected(q)
    text = str(q["question"])
    parts = [f'<div class="lab">Soru</div><div class="q2">{C.t(text[:200] + ("…" if len(text) > 200 else ""))}</div>',
             f'<div class="lab">Cevap</div><div class="ans">{ans}</div>']
    if q.get("solution"):
        parts.append('<div class="lab">Çözüm</div><ol class="nr-solution">'
                     + "".join(f"<li>{C.t(s)}</li>" for s in q["solution"]) + "</ol>")
    where = " · ".join(x for x in (data.short(it.get("doc", "")), f"sayfa {page}" if page else "") if x)
    parts.append(f'<div class="lab">Notundaki kaynak · {style.esc(where)}</div>'
                 f'<div class="nr-evidence"><span class="nr-hl">{C.t(q.get("evidence_quote", ""))}</span></div>'
                 '<div class="flipback">Soruya dönmek için yine tıkla</div>')
    return "".join(parts)


def _length_class(q: dict) -> str:
    n = len(str(q["question"]))
    return " xlong" if n > 320 else (" long" if n > 190 else "")


def _piles(cs: dict, bump: str | None = None) -> str:
    out = []
    for kind in ("bad", "skip", "good"):
        ids = [q for q, r in cs["res"].items() if r == kind]
        minis = "".join(f'<b style="--mc:{VIVID[cs["col"][q] % len(VIVID)][1]}"></b>' for q in ids[-6:])
        out.append(f'<div class="nr-pile {kind}{" bump" if kind == bump else ""}"><span class="ico">{SYM[kind]}</span>'
                   f'<div><div class="n">{len(ids)}</div><div class="l">{PILE[kind]}</div></div>'
                   f'<div class="mini">{minis}</div></div>')
    return '<div class="nr-piles">' + "".join(out) + "</div>"


def _stage(it: dict, cs: dict, last: dict | None) -> str:
    pos, left = cs["pos"], len(cs["queue"]) - cs["pos"] - 1
    stacks = "".join(f'<div class="nr-stack s{k}" style="--s:{VIVID[(pos + k) % len(VIVID)][1]};'
                     f'--s1:{VIVID[(pos + k) % len(VIVID)][0]}"></div>' for k in (3, 2, 1) if left >= k)
    card = (f'<details class="nr-fc{_length_class(it["q"])}" style="{_vars(pos)}">'
            f'<summary><div class="nr-flip"><div class="nr-face front">{_front(it)}</div>'
            f'<div class="nr-face back">{_back(it)}</div></div></summary></details>')
    ghost = (f'<div class="nr-ghost {last["result"]}" data-s="{SYM[last["result"]]}" style="{_vars(last["pos"])}">'
             f'{style.esc(last["text"])}</div>') if last else ""
    # Sarmalayıcı etiketi her değerlendirmede değişir: tarayıcı sahneyi sıfırdan kurar → animasyonlar her seferinde
    # oynar ve çevrilmiş kart (details[open]) bir sonraki karta çevrili geçmez (aynı etiket yeniden kullanılıyordu).
    tag = "section" if cs["v"] % 2 else "div"
    return f'<{tag} class="nr-stage"><div class="nr-deck">{stacks}{card}{ghost}</div></{tag}>'


def _progress(cs: dict, fresh: bool) -> str:
    """Üst şerit: kart başına bir parça (sonucun rengi + yüz), sıradaki kartta düşünen yüz, sonda 💯; yanında isabet
    ve seri. fresh: az önce değerlendirildi → son yüz zıplayarak gelir."""
    total, pos, log = len(cs["queue"]), cs["pos"], cs.get("log", [])
    cells = []
    for k in range(total):
        if k < pos:
            res, em = log[k] if k < len(log) else (cs["res"].get(cs["queue"][k], "skip"), "")
            cls = res + (" new" if fresh and k == pos - 1 else "")
        elif k == pos:
            cls, em = "cur", "🤔"
        else:
            cls, em = "", ""
        cells.append(f'<div class="fc-cell {cls}"><span class="em">{em}</span><i></i></div>')
    good, bad, _ = _counts(cs)
    acc = round(100 * good / (good + bad)) if good + bad else None
    acc_cls = "none" if acc is None else ("" if acc >= 70 else "mid" if acc >= 40 else "low")
    streak = cs["streak"]
    fire = "cold" if streak == 0 else ("hot" if streak >= 5 else "")
    p = pos / max(1, total)
    return (f'<div class="fc-top"><div class="fc-prog"><div class="fc-count"><b>Kart {pos + 1}</b> / {total}</div>'
            f'<div class="fc-steps" style="--n:{total}">{"".join(cells)}</div>'
            f'<div class="fc-goal{" near" if total - pos <= 2 else ""}" style="--p:{p:.2f}" title="Hedef: bütün kartlar">💯</div></div>'
            f'<div class="fc-chip acc {acc_cls}"><span class="ic">🎯</span><div><b>{"–" if acc is None else f"%{acc}"}</b>'
            f'<small>isabet</small></div></div>'
            f'<div class="fc-chip fire {fire}"><span class="ic fc-flame" style="--f:{min(streak, 10)}">🔥</span>'
            f'<div><b>{streak}</b><small>seri · en iyi {cs["best"]}</small></div></div></div>')


def _keys() -> None:
    """Klavye (tarayıcıda): Boşluk kartı çevirir, ← ↓ → değerlendirir. Odaktaki düğme boşlukla tıklanmasın diye bırakılır."""
    with st.container(key="fc_keys"):
        st.iframe("""<body style="margin:0"><script>
const P = window.parent, D = P.document;
if (P.__nrKeyFn) D.removeEventListener('keydown', P.__nrKeyFn);
P.__nrKeyFn = (e) => {
  const tag = (e.target.tagName || '').toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || e.ctrlKey || e.metaKey || e.altKey) return;
  const click = (sel) => { const b = D.querySelector(sel); if (b && !b.disabled) { b.click(); e.preventDefault(); } };
  if (e.key === ' ') { const d = D.querySelector('details.nr-fc'); if (d) { if (D.activeElement) D.activeElement.blur();
    d.open = !d.open; e.preventDefault(); } }
  else if (e.key === 'ArrowLeft' || e.key === '1') click('.st-key-fc_bad button');
  else if (e.key === 'ArrowDown' || e.key === '2') click('.st-key-fc_skip button');
  else if (e.key === 'ArrowRight' || e.key === '3') click('.st-key-fc_good button');
};
D.addEventListener('keydown', P.__nrKeyFn);
</script></body>""", height=1)


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
    while cs["pos"] < len(cs["queue"]) and cs["queue"][cs["pos"]] not in items:  # havuzdan çıkmış soru
        cs["pos"] += 1
    if cs["ended"] or cs["pos"] >= len(cs["queue"]):
        _summary()
        return
    style.html(FOCUS_CSS)
    style.html(SESSION_CSS)
    it = items[cs["queue"][cs["pos"]]]
    last = cs.pop("last", None)  # giden kart ve zıplayan yüz yalnızca değerlendirmenin hemen ardından
    style.html(_progress(cs, fresh=last is not None))
    mid = st.columns([1, 4.4, 1.15], vertical_alignment="center", gap="medium")
    with mid[1]:
        style.html(_stage(it, cs, last))
    with mid[2], st.container(key="fc_side"):
        st.button("Karıştır", key="fc_shuffle", icon=":material/shuffle:", width="stretch", on_click=_shuffle,
                  help="Kalan kartların sırasını karıştır")
        st.button("Bitir", key="fc_end", icon=":material/flag:", width="stretch", on_click=_end,
                  help="Oturumu bitir ve özeti gör")
    low = st.columns([1, 4.4, 1.15], gap="medium")
    with low[1]:
        style.html(_piles(cs, last["result"] if last else None))
        st.space("small")
        b = st.columns(3, gap="small")
        b[0].button("Bilemedim", key="fc_bad", icon=":material/close:", width="stretch", on_click=_grade, args=("bad",))
        b[1].button("Atla", key="fc_skip", icon=":material/redo:", width="stretch", on_click=_grade, args=("skip",))
        b[2].button("Bildim", key="fc_good", icon=":material/check:", width="stretch", on_click=_grade, args=("good",))
    page = it.get("check", {}).get("evidence_page")
    if st.button(f"📖 Notta kaynağını aç{f' · sayfa {page}' if page else ''}", key="fc_src",
                 help="Kanıt sayfası tam ekranda, kanıt cümlesi sarıyla işaretli (Esc ile karta dön)"):
        reader.open_source(it, "cards")
        st.rerun()
    _keys()


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

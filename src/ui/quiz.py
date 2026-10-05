"""Sınav çözme deneyimi: başlangıç ekranı → odak modu (tek soru, büyük şık kartları, kademeli ipucu, klavye,
süre, geçiş animasyonu) → sonuç ekranı (halka grafik, özet, konulara göre başarı, gözden geçirme).

Grafik ilkeleri (dataviz yönergesi): durum renkleri (doğru #3B8D66, yanlış #C6503A) her zaman etiketle birlikte;
boş için nötr ton; tek eksen; sayılar mürekkep renginde, rengi taşıyan işaret yanında.
"""

from __future__ import annotations

import math
import time

import altair as alt
import pandas as pd
import streamlit as st

from src import request as R
from src.textnorm import pretty_math
from src.ui import components as C
from src.ui import data, style

GOOD, BAD, EMPTY, INK = "#3B8D66", "#C6503A", "#B9AF98", "#1E2433"
TRANSPARENCY = ("Sorular yapay zekâ ile üretildi; her biri kaynağındaki cümleye bağlandı ve farklı bir model tarafından "
                "cevap anahtarı görülmeden çözülerek doğrulandı. Kısa cevaplar otomatik karşılaştırılır; yanlış "
                "değerlendirildiğini düşünürsen sonuçta itiraz edebilirsin.")


# ---------------------------------------------------------------- ortak

def grade(it: dict, ans) -> bool:
    q = it["q"]
    if ans is None or ans == "":
        return False
    if q["type"] == "multiple_choice":
        return ans == q["answer_index"]
    if q["type"] == "true_false":
        return ans == q["answer"]
    # Kısa cevap: matematiksel ise değer karşılaştırması (30240 = 9!/(3!·2!)), değilse sıkı metin eşleşmesi
    from src.grading import grade_short
    computed = it["check"].get("computed", {}).get("value") if q.get("compute") else None
    return grade_short(str(ans), q["answer"], computed)


def topic_of(req: dict, it: dict) -> str:
    """Sorunun konusu: kanıt sayfası, isteğin aramada bulduğu hangi konunun sayfalarındaysa o konu."""
    where = (it.get("doc"), it.get("check", {}).get("evidence_page"))
    for t, srcs in req["sources"].items():
        if any((s["doc"], s["page"]) == where for s in srcs):
            return t
    return it.get("unit", "") or "Genel"


def view(items: list[dict]) -> list[dict]:
    """İkinci denemede yalnızca yanlış yapılan sorular."""
    retry = st.session_state.exam.get("retry")
    return [it for it in items if not retry or it["id"] in retry]


def hints(req: dict, it: dict) -> list[tuple[str, str]]:
    """Kademeli ipuçları (Sokratik), HTML: önce nereye bakacağı, sonra kural / kaynak cümle, hesapta ilk adım."""
    q, page = it["q"], it.get("check", {}).get("evidence_page")
    where = style.esc(f"{data.short(it.get('doc', ''))}{f', {page}. sayfa' if page else ''}")
    out = [("Nereye bakmalı?", f"Bu soru <b>{style.esc(topic_of(req, it))}</b> konusundan. Notunda <b>{where}</b> "
                               f"kısmına bak.")]
    quote = C.t(q.get("evidence_quote", ""))
    if q.get("compute"):
        out.append(("Hangi kural?", f"Uygulanacak kural: “{quote}”"))
        if q.get("solution"):
            out.append(("İlk adım", C.t(q["solution"][0])))
    else:
        out.append(("Kaynaktaki cümle", f"“{quote}”<br><i style='color:#8A7E63'>Bu ipucu cevabı büyük ölçüde verir.</i>"))
    return out


def _answered(ans) -> bool:
    return ans is not None and str(ans).strip() != ""


def _fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


# ---------------------------------------------------------------- 1. başlangıç ekranı

def start_screen(req: dict, items: list[dict]) -> None:
    ex = st.session_state.exam
    v = view(items)
    topics = list(dict.fromkeys(topic_of(req, it) for it in v))
    kinds = list(dict.fromkeys(C.type_label(it["q"]) for it in v))
    title = "İkinci deneme: yanlışların" if ex.get("retry") else f"{len(v)} soruluk deneme sınavı"
    style.html(
        f'<div class="nr-start"><div class="k">Sınav hazır</div><h2>{style.esc(title)}</h2>'
        f'<div style="color:#D7DEE8">{style.esc(" · ".join(topics[:4]))}{" …" if len(topics) > 4 else ""}</div>'
        f'<div class="facts"><div><b>{len(v)}</b>soru</div><div><b>~{max(1, round(len(v) * 1.2))} dk</b>tahmini süre</div>'
        f'<div><b>{len(topics)}</b>konu</div><div><b>{len(kinds)}</b>soru tipi</div></div></div>')
    st.space("small")
    c = st.columns([1.4, 3], vertical_alignment="center")
    if c[0].button("Sınava başla", type="primary", icon=":material/play_arrow:", width="stretch", key="nr_start"):
        ex.update({"phase": "solve", "cur": 0, "started": time.time(), "hints": {}})
        st.rerun()
    c[1].markdown('<div class="nr-keys" style="text-align:left">Sınav odak modunda açılır. Klavye: '
                  '<span class="nr-kbd">A</span>–<span class="nr-kbd">D</span> şık · <span class="nr-kbd">←</span> '
                  '<span class="nr-kbd">→</span> soru · <span class="nr-kbd">H</span> ipucu</div>', unsafe_allow_html=True)
    st.caption(TRANSPARENCY)


# ---------------------------------------------------------------- 2. odak modu

_FOCUS_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 880px; padding-top: 1.4rem; }
</style>"""


def _pick(qid: str, value) -> None:
    st.session_state.exam["answers"][qid] = value
    st.session_state.exam.pop("hint_flash", None)


def _sync_text(qid: str) -> None:
    key = f"sa_{qid}"
    if key in st.session_state:
        st.session_state.exam["answers"][qid] = st.session_state[key]


def _go(target: int, qid: str) -> None:
    _sync_text(qid)
    ex = st.session_state.exam
    ex["cur"] = target
    ex.pop("hint_flash", None)


def _hint(qid: str) -> None:
    ex = st.session_state.exam
    ex["hints"][qid] = ex["hints"].get(qid, 0) + 1
    ex["hint_flash"] = qid


def _jump(key: str, qid: str) -> None:
    if st.session_state.get(key) is not None:
        _go(int(st.session_state[key]), qid)


def _finish() -> None:
    ex = st.session_state.exam
    ex.update({"phase": "results", "submitted": True, "finished": time.time()})


@st.dialog("Sınavı bitir")
def _confirm_finish(empty: int, qid: str) -> None:
    _sync_text(qid)
    st.markdown(f"**{empty} soru boş.** Boş sorular yanlış sayılır. Yine de bitirmek istiyor musun?")
    c = st.columns(2)
    if c[0].button("Geri dön", width="stretch"):
        st.rerun()
    if c[1].button("Bitir", type="primary", width="stretch"):
        _finish()
        st.rerun()


def _keys_and_scroll(started: float, flash: str = "") -> None:
    """Süre sayacı + klavye kısayolları + yeni ipucuna yumuşak kaydırma (tarayıcıda; sunucuya istek yok).
    İçerik yalnızca yeni ipucu açıldığında değişir (flash); aksi halde Streamlit çerçeveyi yeniden yüklemez ve
    sayaç her tıklamada titremez. Zemin sayfayla aynı, ilk değer sunucuda hesaplanır (yüklenirken '00:00' görünmez)."""
    elapsed = _fmt_time(time.time() - started)
    st.iframe(f"""<body style="margin:0;background:transparent"><!-- {flash} -->
<div id="t" style="font:600 15px ui-monospace,Consolas,monospace;color:#1E2433;text-align:right;padding-top:9px">⏱ {elapsed}</div>
<script>
const s = {int(started * 1000)}, el = document.getElementById('t');
function f() {{ const d = Math.max(0, Math.floor((Date.now() - s) / 1000));
  el.textContent = '⏱ ' + String(Math.floor(d / 60)).padStart(2, '0') + ':' + String(d % 60).padStart(2, '0'); }}
f(); setInterval(f, 1000);
const P = window.parent, D = P.document;
{{
  if (P.__nrKeyFn) D.removeEventListener('keydown', P.__nrKeyFn);  // çerçeve yenilenince eski dinleyici kalmasın
  P.__nrKeyFn = (e) => {{
    const tag = (e.target.tagName || '').toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || e.ctrlKey || e.metaKey || e.altKey) return;
    const click = (sel) => {{ const b = D.querySelector(sel); if (b && !b.disabled) {{ b.click(); e.preventDefault(); }} }};
    const k = e.key.toLowerCase(), bs = D.querySelectorAll('.st-key-nr_opts button');
    const map = bs.length === 2 ? {{d: 0, y: 1, '1': 0, '2': 1}} : {{a: 0, b: 1, c: 2, d: 3, '1': 0, '2': 1, '3': 2, '4': 3}};
    if (k in map && bs[map[k]]) {{ bs[map[k]].click(); e.preventDefault(); }}
    else if (e.key === 'ArrowRight') click('.st-key-nav_next button');
    else if (e.key === 'ArrowLeft') click('.st-key-nav_prev button');
    else if (k === 'h') click('[class*="st-key-hint_"] button');
  }};
  D.addEventListener('keydown', P.__nrKeyFn);
}}
setTimeout(() => {{ const h = D.querySelector('.nr-hint.new');
  if (h) h.scrollIntoView({{behavior: 'smooth', block: 'center'}}); }}, 150);
</script></body>""", height=36)


def solve(req: dict, items: list[dict]) -> None:
    style.html(_FOCUS_CSS)
    ex = st.session_state.exam
    v = view(items)
    n = len(v)
    ex.setdefault("hints", {})
    ex.setdefault("started", time.time())
    cur = min(ex.get("cur", 0), n - 1)
    it, q = v[cur], v[cur]["q"]
    qid, answers = it["id"], ex["answers"]
    done = sum(_answered(answers.get(x["id"])) for x in v)

    # Üst şerit: ilerleme, süre, çıkış
    top = st.columns([5, 1.2, 1.1], vertical_alignment="center")
    with top[0]:
        style.html(f'<div class="nr-qprog"><div class="lbl"><span><b>Soru {cur + 1}</b> / {n}</span>'
                   f'<span>{done} cevaplandı</span></div><div class="bar"><i style="width:{100 * done / n:.1f}%"></i>'
                   f'</div></div>')
    hs, level = hints(req, it), ex["hints"].get(qid, 0)
    with top[1]:
        _keys_and_scroll(ex["started"], f"{qid}:{level}" if ex.get("hint_flash") == qid else "")
    if top[2].button("Çık", icon=":material/close:", width="stretch", help="Cevapların saklanır; sonra kaldığın yerden devam edersin."):
        _sync_text(qid)
        ex["phase"] = "start"
        st.rerun()

    # Soru haritası en üstte (yeri hiç değişmez): numaraya tıklayıp atla (✓ = cevaplandı)
    key = f"nr_map_{cur}"
    st.pills("Sorular", list(range(n)), default=cur, key=key, label_visibility="collapsed", on_change=_jump,
             args=(key, qid), format_func=lambda i: f"{i + 1}{' ✓' if _answered(answers.get(v[i]['id'])) else ''}")

    # Soru kartı: sabit asgari yükseklik (kısa / uzun soruda düzen oynamaz); yeni soru ortadan büyüyerek gelir
    chips = "".join(f'<span class="nr-chip">{style.esc(c)}</span>'
                    for c in (C.type_label(q), C.DIFF_TR.get(q.get("difficulty"), ""), topic_of(req, it)) if c)
    style.html(f'<div class="nr-focus" data-q="{cur}"><div class="nr-qhead"><span class="nr-qnum">SORU {cur + 1}</span>'
               f'{chips}</div><div class="nr-q">{C.t(q["question"])}</div></div>')

    # Cevap alanı: soru tipi ne olursa olsun aynı yükseklik → gezinme düğmeleri yerinde kalır
    with st.container(key="nr_answer"):
        with st.container(key="nr_opts"):
            if q["type"] == "multiple_choice":
                for j, o in enumerate(q["options"]):
                    st.button(f"**{C.LETTERS[j]}**  ·  {pretty_math(o)}", key=f"opt_{qid}_{j}", width="stretch",
                              type="primary" if answers.get(qid) == j else "secondary", on_click=_pick, args=(qid, j))
            elif q["type"] == "true_false":
                cc = st.columns(2)
                for col, (val, label) in zip(cc, (("true", "Doğru"), ("false", "Yanlış"))):
                    col.button(label, key=f"opt_{qid}_{val}", width="stretch", on_click=_pick, args=(qid, val),
                               type="primary" if answers.get(qid) == val else "secondary",
                               icon=":material/check:" if val == "true" else ":material/close:")
            else:
                st.text_input("Cevabın", key=f"sa_{qid}", value=answers.get(qid) or "", label_visibility="collapsed",
                              placeholder="Sonucu yaz ve Enter'a bas" if q.get("compute") else "Kısa cevabını yaz ve Enter'a bas",
                              on_change=_sync_text, args=(qid,))
                style.html('<div class="nr-sa-help">' + (
                    "Sayı ya da ifade yazabilirsin: <b>30240</b> ile <b>9!/(3!·2!)</b> aynı sayılır; <b>2^n</b>, "
                    "<b>C(n,2)</b>, <b>n(n-1)</b> gibi yazımlar da tanınır." if q.get("compute") or any(
                        ch.isdigit() for ch in str(q.get("answer", ""))) else
                    "Bir kelime ya da kısa bir ifade yeterli. Küçük yazım hataları ve ekler (ör. -dır) sorun değil.")
                    + "</div>")
        # Kademeli ipucu: yeni açılan parlayarak gelir ve ekran ona kayar
        for k in range(min(level, len(hs))):
            new = " new" if (k == level - 1 and ex.get("hint_flash") == qid) else ""
            style.html(f'<div class="nr-hint{new}"><div class="h">💡 {k + 1}. ipucu · {style.esc(hs[k][0])}</div>'
                       f'<div class="b">{hs[k][1]}</div></div>')

    # Gezinme: ekranın altına yapışık
    nav_box = st.container(key="nr_nav")
    nav = nav_box.columns([1.2, 1.3, 1.5], vertical_alignment="center")
    nav[0].button("Önceki", key="nav_prev", icon=":material/arrow_back:", width="stretch", disabled=cur == 0,
                  on_click=_go, args=(cur - 1, qid))
    if level < len(hs):
        nav[1].button(f"İpucu al ({level + 1}/{len(hs)})", key=f"hint_{qid}", icon=":material/lightbulb:",
                      width="stretch", on_click=_hint, args=(qid,))
    else:
        nav[1].button("İpuçları bitti", key=f"hint_{qid}", icon=":material/lightbulb:", width="stretch", disabled=True)
    if cur < n - 1:
        nav[2].button("Sonraki", key="nav_next", icon=":material/arrow_forward:", type="primary", width="stretch",
                      on_click=_go, args=(cur + 1, qid))
    elif nav[2].button("Sınavı bitir", key="nav_next", icon=":material/flag:", type="primary", width="stretch"):
        _sync_text(qid)
        empty = sum(not _answered(answers.get(x["id"])) for x in v)
        if empty:
            _confirm_finish(empty, qid)
        else:
            _finish()
            st.rerun()

    with nav_box:
        style.html('<div class="nr-keys">Klavye: <span class="nr-kbd">A</span>–<span class="nr-kbd">D</span> şık · '
                   '<span class="nr-kbd">←</span> <span class="nr-kbd">→</span> soru · <span class="nr-kbd">H</span> ipucu</div>')


# ---------------------------------------------------------------- 3. sonuç

def _ring(c: int, w: int, e: int) -> str:
    """Halka grafik (SVG): doğru / yanlış / boş; dilimler arasında 2 px boşluk, ortada yüzde."""
    total = max(1, c + w + e)
    r, circ, gap = 70, 2 * math.pi * 70, 2.5
    segs, off = [], 0.0
    for val, color in ((c, GOOD), (w, BAD), (e, EMPTY)):
        if val:
            length = circ * val / total
            segs.append(f'<circle class="seg" cx="90" cy="90" r="{r}" fill="none" stroke="{color}" stroke-width="18" '
                        f'stroke-dasharray="{max(length - gap, 0.5):.2f} {circ:.2f}" stroke-dashoffset="{-off:.2f}" '
                        f'transform="rotate(-90 90 90)"/>')
            off += length
    pct = round(100 * c / total)
    return (f'<svg class="nr-ring" viewBox="0 0 180 180" width="190" height="190" role="img" '
            f'aria-label="{c} doğru, {w} yanlış, {e} boş">'
            f'<circle cx="90" cy="90" r="{r}" fill="none" stroke="#ECE6D8" stroke-width="18"/>{"".join(segs)}'
            f'<text x="90" y="92" text-anchor="middle" class="pct">%{pct}</text>'
            f'<text x="90" y="114" text-anchor="middle" class="lbl">{c} / {total} doğru</text></svg>')


def _message(pct: int) -> tuple[str, str]:
    if pct >= 90:
        return "Harika bir sonuç!", "Konulara hâkimsin. Bir sonraki sınavda zorluğu artırmayı dene."
    if pct >= 70:
        return "İyi gidiyorsun.", "Birkaç noktayı tekrar edersen tam puana çok yakınsın."
    if pct >= 40:
        return "Temel oturuyor.", "Aşağıdaki konulara notlarından bir kez daha göz atıp yanlışlarını tekrar çöz."
    return "Tekrar zamanı.", "Konuları notlarından yeniden çalış; ipuçlarını kullanarak yanlışlarını tekrar çöz."


def _topic_chart(rows: list[dict]) -> alt.Chart:
    df = pd.DataFrame(rows)
    order = ["Doğru", "Yanlış", "Boş"]
    sort = df.groupby("Konu")["Sayı"].sum().sort_values(ascending=False).index.tolist()
    base = alt.Chart(df).encode(
        y=alt.Y("Konu:N", sort=sort, title=None, axis=alt.Axis(labelLimit=260)),
        x=alt.X("Sayı:Q", stack="zero", title=None, axis=alt.Axis(tickMinStep=1, format="d", grid=True)),
        tooltip=["Konu:N", "Durum:N", "Sayı:Q"])
    bars = base.mark_bar(height=18, stroke="#FFFDF8", strokeWidth=2, cornerRadius=3).encode(
        color=alt.Color("Durum:N", scale=alt.Scale(domain=order, range=[GOOD, BAD, EMPTY]),
                        legend=alt.Legend(orient="top", title=None)),
        order=alt.Order("sira:Q"))
    text = base.mark_text(dx=-8, align="right", color="#FFFFFF", fontWeight=600).encode(
        x=alt.X("Sayı:Q", stack="zero"), detail="Durum:N", order=alt.Order("sira:Q"),
        text=alt.condition(alt.datum.Sayı > 0, alt.Text("Sayı:Q"), alt.value("")))
    return (bars + text).properties(height=max(90, 40 * len(sort))).configure(
        font="Instrument Sans", background="transparent").configure_view(stroke=None).configure_axis(
        labelColor="#4A5163", gridColor="#E6DFCF", domainColor="#E6DFCF", tickColor="#E6DFCF", labelFontSize=12
    ).configure_legend(labelColor="#4A5163", labelFontSize=12)


def restart(req: dict, items: list[dict], retry: list[str] | None) -> None:
    """Sınavı baştan (retry=None) ya da yalnızca verilen sorularla ikinci deneme olarak yeniden aç."""
    ex = st.session_state.exam
    for it in items:
        if retry is None or it["id"] in retry:
            st.session_state.pop(f"sa_{it['id']}", None)
    keep = {k: v for k, v in ex.get("answers", {}).items() if retry is not None and k not in retry}
    st.session_state.exam = {"id": ex["id"], "answers": keep, "submitted": False, "recorded": False, "retry": retry,
                             "overrides": [] if retry is None else ex.get("overrides", []), "phase": "start"}
    st.rerun()


def results(req: dict, items: list[dict]) -> None:
    ex = st.session_state.exam
    v = view(items)
    overrides = set(ex.get("overrides", []))
    graded = {it["id"]: grade(it, ex["answers"].get(it["id"])) for it in v}
    if not ex["recorded"]:  # madde analizi (ilk deneme; itirazlar ve ikinci denemeler istatistiği değiştirmez)
        R.record_attempt(req["id"], graded, retry=bool(ex.get("retry")),
                         answers={k: ex["answers"].get(k) for k in graded}, hints=ex.get("hints", {}))
        ex["recorded"] = True
        data.item_stats.clear()
    ok = {k: g or k in overrides for k, g in graded.items()}
    empty = {it["id"] for it in v if not _answered(ex["answers"].get(it["id"]))}
    c = sum(ok.values())
    w = sum(1 for k, g in ok.items() if not g and k not in empty)
    e = len(empty - {k for k, g in ok.items() if g})
    pct = round(100 * c / max(1, len(v)))
    head, sub = _message(pct)
    used = sum(ex.get("hints", {}).get(it["id"], 0) for it in v)
    dur = (ex.get("finished") or time.time()) - (ex.get("started") or time.time())
    extra = " · ikinci deneme" if ex.get("retry") else ""
    extra += " · itirazla" if overrides & set(ok) else ""
    kpi = lambda k, val, color=None: (f'<div class="nr-kpi"><div class="k">{f"<i style=background:{color}></i>" if color else ""}'
                                      f'{k}</div><div class="v">{val}</div></div>')
    style.html(
        f'<div class="nr-res"><div>{_ring(c, w, e)}<div class="nr-legend"><span><i style="background:{GOOD}"></i>Doğru</span>'
        f'<span><i style="background:{BAD}"></i>Yanlış</span><span><i style="background:{EMPTY}"></i>Boş</span></div></div>'
        f'<div><div class="msg">{style.esc(head)}</div><div class="sub">{style.esc(sub)}{style.esc(extra)}</div>'
        f'<div class="nr-kpis">{kpi("Doğru", c, GOOD)}{kpi("Yanlış", w, BAD)}{kpi("Boş", e, EMPTY)}'
        f'{kpi("Süre", _fmt_time(dur))}</div>'
        f'<div style="margin-top:.6rem;color:#6B6F7B;font-size:.88rem">💡 {used} ipucu kullandın</div></div></div>')
    st.space("small")

    wrong = [k for k, g in ok.items() if not g]
    b = st.columns([1.9, 1.3, 1.3], vertical_alignment="center")
    # Anahtarlar şart: üstteki özette de "Yeni sınav" var (aynı etiketli iki düğme Streamlit'te çakışıyordu)
    if wrong and b[0].button(f"Yanlışları tekrar çöz ({len(wrong)})", icon=":material/refresh:", type="primary",
                             width="stretch", key="res_retry"):
        restart(req, items, wrong)
    if b[1].button("Baştan çöz", icon=":material/replay:", width="stretch", key="res_restart"):
        restart(req, items, None)
    if b[2].button("Yeni sınav", icon=":material/add:", width="stretch", key="new_exam_bottom"):
        st.session_state.pop("exam", None)
        st.query_params.clear()
        st.rerun()

    # Konulara göre başarı
    rows = []
    for it in v:
        status = "Doğru" if ok[it["id"]] else ("Boş" if it["id"] in empty else "Yanlış")
        rows.append({"Konu": topic_of(req, it), "Durum": status, "Sayı": 1,
                     "sira": {"Doğru": 0, "Yanlış": 1, "Boş": 2}[status]})
    agg = (pd.DataFrame(rows).groupby(["Konu", "Durum", "sira"], as_index=False)["Sayı"].sum().to_dict("records"))
    st.markdown("#### Konulara göre")
    st.altair_chart(_topic_chart(agg), width="stretch")
    weak = [t for t in dict.fromkeys(r["Konu"] for r in rows if r["Durum"] != "Doğru")]
    if weak:
        st.caption("Tekrar etmen gereken konular: " + " · ".join(weak[:6]))

    # Gözden geçirme
    st.markdown("#### Soruları gözden geçir")
    show = st.segmented_control("Göster", ["Yanlış ve boşlar", "Tümü", "Doğrular"],
                                default="Yanlış ve boşlar" if wrong else "Tümü", label_visibility="collapsed")
    st.space("small")
    for i, it in enumerate(v, 1):
        good = ok[it["id"]]
        if (show == "Yanlış ve boşlar" and good) or (show == "Doğrular" and not good):
            continue
        ans = ex["answers"].get(it["id"])
        style.html(C.question_card(it, i, reveal=True, chosen=ans, verdict=False))
        row = st.columns([1.3, 1.4, 1.8, 2.5], vertical_alignment="center")
        label = ("İtirazla doğru" if it["id"] in overrides and not graded[it["id"]] else "Doğru") if good else \
            ("Boş" if it["id"] in empty else "Yanlış")
        row[0].badge(label, icon=":material/check:" if good else ":material/close:",
                     color="green" if good else ("gray" if it["id"] in empty else "red"))
        with row[1].popover("Hatalı bildir", icon=":material/flag:"):
            note = st.text_input("Ne yanlış?", key=f"rep_{it['id']}", placeholder="ör. iki şık da doğru")
            if st.button("Gönder", key=f"repb_{it['id']}", type="primary"):
                R.report(it["id"], note, req["id"])
                data.reports.clear()
                st.toast("Bildirildi. Soru incelenene kadar sınavlara konmayacak.", icon=":material/flag:")
        # Kısa cevap otomatik karşılaştırılır ve yanılabilir: öğrenci itiraz eder, soru öğretmen incelemesine düşer
        if it["q"]["type"] == "short_answer" and not graded[it["id"]] and it["id"] not in overrides and _answered(ans):
            with row[2].popover("Cevabım doğruydu", icon=":material/gavel:"):
                st.caption(f"Senin cevabın: “{ans}” · Beklenen: “{pretty_math(it['q']['answer'])}”. İtirazın puanına "
                           "yansır ve soru öğretmen incelemesine gönderilir.")
                why = st.text_input("Neden doğru? (isteğe bağlı)", key=f"obj_{it['id']}")
                if st.button("İtiraz et", key=f"objb_{it['id']}", type="primary"):
                    R.report(it["id"], f"Kısa cevap itirazı: öğrenci '{ans}' yazdı, beklenen "
                                       f"'{it['q']['answer']}'. {why}".strip(), req["id"])
                    ex["overrides"] = sorted(overrides | {it["id"]})
                    data.reports.clear()
                    st.rerun()
        hn = ex.get("hints", {}).get(it["id"], 0)
        if hn:
            row[3].caption(f"💡 Bu soruda {hn} ipucu kullandın")
        st.space("small")

"""İnceleme (öğretmen / kalite kontrol): soru ile cevabın geçtiği kaynak sayfa yan yana, aynı boyda; altında karar
ve doğrulama ayrıntıları. Kararlar doğrulama katmanının isabetini ölçer; reddedilen ya da öğrencinin hatalı bildirdiği
soru sınavlara konmaz."""

from pathlib import Path

import streamlit as st

from src import review_store as rs
from src.ui import components as C
from src.ui import data, style

VERDICT_TR = {"correct": "doğru", "incorrect": "yanlış", "unknown": "belirsiz"}
SHOW = ["İncelenmemiş", "İncelenmeli", "Bildirilen", "Tümü"]

# İki kart yan yana: bu sayfada içerik genişliği sınırı açılır
_WIDE = """<style>
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1640px; padding-left: 3rem; padding-right: 3rem; }
</style>"""


@st.cache_data(max_entries=64)
def _evidence_png(qid: str, key: str) -> tuple:
    item = next(i for s in data.question_sets() if s["key"] == key for i in s["items"] if i["id"] == qid)
    return rs.render_evidence(item, data.chunks(), dpi=144)


def _mine(s: dict) -> dict:
    """Setin yalnızca görebildiğin notlara ait soruları (istek setinde birden çok notun sorusu olabilir)."""
    seen = data.visible()
    return {**s, "items": [i for i in s["items"] if i["doc"] in seen]}


def _filters() -> tuple[dict, list[dict]]:
    sets = [s for s in data.question_sets() if s["kind"] == "belge"] or data.question_sets()
    sets = [s for s in map(_mine, sets) if s["items"]]
    if not sets:
        return {}, []
    sets = sorted(sets, key=lambda s: (s["name"].startswith("istek_"), -len(s["items"])))  # en büyük belge seti önce
    labels = {s["key"]: data.set_label(s["name"], s["kind"]) for s in sets}
    with st.container(border=True):
        a, b, c = st.columns([3, 4, 2], gap="medium", vertical_alignment="bottom")
        key = a.selectbox("Soru seti", list(labels), format_func=labels.get)
        show = b.segmented_control("Göster", SHOW, default="İncelenmemiş") or "Tümü"
        c.toggle("Önce kendin çöz", key="blind", help="Doğru cevabı ve kaynak sayfayı gizler.")
    s = next(x for x in sets if x["key"] == key)
    decs, reps = data.decisions(), data.reports()
    pick = {"İncelenmemiş": lambda i: i["id"] not in decs and i.get("verification", {}).get("label") != "rejected",
            "İncelenmeli": lambda i: i.get("verification", {}).get("label") == "needs_review",
            "Bildirilen": lambda i: i["id"] in reps,
            "Tümü": lambda i: True}[show]
    return s, [i for i in s["items"] if i["q"].get("type") in C.TYPE_TR and pick(i)]


def _pager(idx: int, n_view: int, done: int, total: int) -> None:
    nav = st.columns([1, 3, 1], vertical_alignment="center")
    if nav[0].button("Önceki", icon=":material/chevron_left:", disabled=idx == 0, width="stretch"):
        st.session_state.idx -= 1
        st.rerun()
    with nav[1]:
        pct = 100 * done / max(1, total)
        style.html(f'<div class="nr-pager"><div class="c">SORU {idx + 1} / {n_view}</div>'
                   f'<div class="bar"><i style="width:{pct:.1f}%"></i></div>'
                   f'<div class="s">Bu sette incelenen: {done} / {total}</div></div>')
    if nav[2].button("Sonraki", icon=":material/chevron_right:", disabled=idx >= n_view - 1, width="stretch"):
        st.session_state.idx += 1
        st.rerun()


def _decide(item: dict, source: str, n_view: int) -> None:
    prev = data.decisions().get(item["id"])
    with st.container(border=True):
        st.markdown("#### Kararın")
        if prev:
            st.caption(("✅ Onaylamıştın" if prev["decision"] == "approve" else "❌ Reddetmiştin")
                       + (f" — {', '.join(prev.get('reasons', []))}" if prev.get("reasons") else "")
                       + (f" — {prev['note']}" if prev.get("note") else ""))
        reasons = st.pills("Reddediyorsan neden?", rs.REJECT_REASONS, selection_mode="multi", key=f"r_{item['id']}")
        note = st.text_input("Not (isteğe bağlı)", key=f"n_{item['id']}", placeholder="ör. ikinci şık da savunulabilir")
        b1, b2, b3 = st.columns([2, 2, 1])
        if b1.button("Onayla", type="primary", icon=":material/check:", width="stretch"):
            rs.save_decision(item, "approve", note, source, user=data.uid())
            _advance(n_view)
        if b2.button("Reddet", icon=":material/close:", width="stretch"):
            rs.save_decision(item, "reject", note, source, reasons, user=data.uid())
            _advance(n_view)
        if b3.button("Atla", width="stretch"):
            _advance(n_view)


def _details(item: dict, reveal: bool) -> None:
    ver, chk = item.get("verification", {}), item.get("check", {})
    with st.container(border=True):
        st.markdown("#### Doğrulama ayrıntıları")
        if not reveal:
            st.caption("Cevap gizliyken gösterilmiyor.")
            return
        lines = []
        if ver.get("verifier"):
            lines.append(f"**Üreten:** `{item.get('model')}` · **Doğrulayan:** `{ver['verifier']}` "
                         "(farklı model ailesi, cevap anahtarını görmeden)")
        if chk.get("computed", {}).get("ok"):
            lines.append(f"**Kodla hesap (SymPy):** sonuç = {chk['computed'].get('value')}")
        if ver.get("option_verdicts"):
            lines.append("**Şıklar için karar:** " + " · ".join(
                f"{k}: {VERDICT_TR.get(v, v or '?')}" for k, v in ver["option_verdicts"].items()))
        if ver.get("blind_answer"):
            lines.append(f"**Doğrulayıcının kendi cevabı:** {ver['blind_answer']}")
        if ver.get("verifier_reason"):
            lines.append(f"**Gerekçe:** {ver['verifier_reason']}")
        st.markdown("  \n".join(lines) or "Doğrulayıcı kaydı yok.")
        warns = [rs.FLAG_TR.get(f, f) for f in chk.get("flags", [])]
        if ver.get("choices_cue"):
            warns.append("Doğru şık, soru gösterilmeden yalnızca şıklardan bulundu")
        for w in warns:
            st.caption(f"⚑ {w}")


def _advance(n_view: int) -> None:
    st.session_state.idx = min(st.session_state.idx + 1, n_view - 1)
    st.rerun()


def render() -> None:
    style.html(_WIDE)
    style.header("Kalite", "İnceleme", "Her soruyu cevabın geçtiği sayfayla yan yana değerlendir. Reddettiğin ya da "
                 "öğrencinin hatalı bildirdiği soru sınavlara konmaz.")
    s, view = _filters()
    if not s:
        st.info("Görebildiğin notlarda henüz soru yok. **Belgeler** sayfasından bir not ekle.",
                icon=":material/upload_file:")
        return
    decs = data.decisions()
    done = sum(i["id"] in decs for i in s["items"])
    if not view:
        st.success("Bu görünümde incelenecek soru kalmadı.", icon=":material/task_alt:")
        return
    if st.session_state.get("set_key") != s["key"]:
        st.session_state.idx, st.session_state.set_key = 0, s["key"]
    st.session_state.idx = min(st.session_state.get("idx", 0), len(view) - 1)
    idx = st.session_state.idx
    item = view[idx]
    reveal = not st.session_state.get("blind", False)

    _pager(idx, len(view), done, len(s["items"]))
    for r in data.reports().get(item["id"], []):
        st.warning(f"Öğrenci bu soruyu hatalı bildirdi ({r['time'][:16]}): {r['note'] or 'açıklama yok'}",
                   icon=":material/flag:")
    png, note = _evidence_png(item["id"], s["key"]) if reveal else (None, "")
    style.html(f'<div class="nr-pair">{C.question_card(item, idx + 1, reveal=reveal)}'
               f'{C.page_card(item, png, note, reveal)}</div>')

    left, right = st.columns(2, gap="medium")
    with left:
        _decide(item, Path(s["key"]).stem, len(view))
    with right:
        _details(item, reveal)


render()

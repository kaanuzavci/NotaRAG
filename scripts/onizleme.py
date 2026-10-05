"""Görsel önizleme (yalnızca geliştirme): çalışma ekranlarını hazır verilerle açar; gerçek kayıtlara yazmaz.

    .venv\\Scripts\\streamlit run scripts/onizleme.py --server.port 8502 --server.headless true
    → http://localhost:8502/?v=setup|session|flip|summary|quiz|results   (ekran görüntüsü: scripts/ekran.py)
"""

import json
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st

st.set_page_config(page_title="NotaRAG önizleme", layout="wide", initial_sidebar_state="expanded")
from src.ui import style

style.inject()
import src.cards as K
from src import request as R

K.LOG = Path(tempfile.gettempdir()) / "nr_preview_cards.jsonl"  # kart değerlendirmeleri gerçek kayda gitmez
v = st.query_params.get("v", "session")
rnd = random.Random(7)


def run_page(rel: str) -> None:
    exec(compile((ROOT / rel).read_text(encoding="utf-8"), rel, "exec"), {"__name__": "__page__"})


if v in ("setup", "session", "flip", "summary"):
    if v != "setup" and "cards" not in st.session_state:
        items = [it for it in R.all_items().values() if R.usable(it)]
        mcq = [it for it in items if it["q"]["type"] == "multiple_choice"]
        ids = [mcq[3]["id"]] + [it["id"] for it in rnd.sample(items, 14)]
        st.session_state.cards = {"queue": ids, "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0, "best": 0,
                                  "last": None, "started": time.time() - 400, "ended": False, "party": True,
                                  "say": ("happy", "Harika, bildin! Bunu <b>yarın</b> yeniden soracağım.", "p")}
        cs = st.session_state.cards
        if v in ("session", "flip"):
            for i, r in enumerate(["good", "bad", "good", "skip", "good"]):
                cs["res"][ids[i + 1]], cs["col"][ids[i + 1]] = r, i
            cs["queue"] = [ids[0]] + ids[6:]
            cs["streak"], cs["best"] = 2, 2
        if v == "summary":
            for i, q in enumerate(ids):
                cs["res"][q], cs["col"][q] = rnd.choice(["good", "good", "bad", "skip"]), i
            cs["ended"], cs["best"] = True, 4
    if v == "flip":
        style.html("<style>details.nr-fc .nr-flip { transform: rotateY(180deg) !important; transition: none !important; }</style>")
    run_page("src/ui/pages/cards.py")
else:
    from src.ui import quiz as Q
    req = next(r for p in sorted((ROOT / "data/requests").glob("*.json"), reverse=True)
               if (r := json.loads(p.read_text(encoding="utf-8"))).get("status") in ("ready", "done") and len(R.items_of(r)) >= 8)
    items = R.items_of(req)
    if "exam" not in st.session_state:  # recorded=True: sonuç ekranı çözüm kaydı (attempts.jsonl) yazmaz
        ans = {it["id"]: (0 if it["q"]["type"] == "multiple_choice" else "true") for it in items[:6]}
        st.session_state.exam = {"id": req["id"], "answers": ans if v == "results" else {items[0]["id"]: 1},
                                 "submitted": v == "results", "recorded": True, "phase": "solve" if v == "quiz" else "results",
                                 "cur": 0, "started": time.time() - 300, "finished": time.time(), "hints": {},
                                 "event": ("pick", items[0]["id"]), "confetti": True}
    if v == "quiz":
        Q.solve(req, items)
    else:
        style.header("Çalış", "Sınav Hazırla")
        Q.results(req, items)

"""Görsel önizleme (yalnızca geliştirme): çalışma ekranlarını hazır verilerle açar; gerçek kayıtlara yazmaz.

    .venv\\Scripts\\streamlit run scripts/onizleme.py --server.port 8502 --server.headless true
    → http://localhost:8502/?v=setup|session|flip|summary|quiz|results|login|docs|home|home0|profile
      (ekran görüntüsü: scripts/ekran.py; home = dolu ana sayfa, home0 = yarım oturum yok)

Hesaplar ve belge kaydı geçici bir veritabanında (gerçek data/app.sqlite'a dokunulmaz): içinde tek bir "önizleme"
hesabı var; ilk hesap olduğu için mevcut belgelerin sahibi o.
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
from src import accounts, appdb, library
from src import request as R

K.LOG = Path(tempfile.gettempdir()) / "nr_preview_cards.jsonl"  # kart değerlendirmeleri gerçek kayda gitmez
appdb.PATH = Path(tempfile.gettempdir()) / "nr_preview_app.sqlite"  # hesaplar ve belge kaydı da
if accounts.count() == 0:
    accounts.create("onizleme", "onizleme-parola", "Önizleme")
library.sync()
v = st.query_params.get("v", "session")
rnd = random.Random(7)
if v != "login":
    st.session_state.setdefault("user", accounts.get(accounts.legacy_owner()))


def run_page(rel: str) -> None:
    exec(compile((ROOT / rel).read_text(encoding="utf-8"), rel, "exec"), {"__name__": "__page__"})


if v == "login":
    from src.ui import auth
    auth.page()
elif v == "docs":
    run_page("src/ui/pages/documents.py")
elif v in ("home", "home0", "profile"):
    from src import resume
    uid = st.session_state.user["id"]
    if v == "home":  # dolu görünüm: yarım kart oturumu, yarım sınav ve bir herkese açık not (yalnızca geçici veritabanında)
        pool = K.pool(sorted({it["doc"] for it in R.all_items().values()}))
        ids = [it["id"] for it in rnd.sample(pool, 20)]
        resume.save(uid, "cards", {"queue": ids, "pos": 7, "res": {q: r for q, r in zip(ids, "ggbgsgb")}, "col": {},
                                   "skipped": [], "streak": 1, "best": 3, "started": time.time() - 900,
                                   "ended": False, "v": 7})
        req = next(r for p in sorted((ROOT / "data/requests").glob("*.json"), reverse=True)
                   if (r := json.loads(p.read_text(encoding="utf-8"))).get("status") in ("ready", "done")
                   and len(R.items_of(r)) >= 8)
        first = [it["id"] for it in R.items_of(req)[:4]]
        resume.save(uid, "exam", {"id": req["id"], "answers": {q: 0 for q in first}, "submitted": False,
                                  "recorded": False, "phase": "solve", "cur": 4, "started": time.time() - 600,
                                  "hints": {first[0]: 1}})
        with appdb.connect() as con:
            con.execute("UPDATE documents SET public_since = 1 WHERE doc = 'english'")
            con.execute("DELETE FROM doc_access WHERE doc = 'english'")
    elif v == "home0":
        resume.clear(uid, "cards")
        resume.clear(uid, "exam")
    run_page("src/ui/pages/profile.py" if v == "profile" else "src/ui/pages/home.py")
elif v in ("setup", "session", "flip", "summary"):
    if v != "setup" and "cards" not in st.session_state:
        items = K.pool(sorted({it["doc"] for it in R.all_items().values()}))
        ids = [it["id"] for it in rnd.sample(items, 15)]
        st.session_state.cards = {"queue": ids, "pos": 0, "res": {}, "col": {}, "skipped": [], "streak": 0, "best": 0,
                                  "last": None, "started": time.time() - 400, "ended": False, "v": 0}
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

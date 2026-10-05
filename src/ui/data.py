"""Arayüzün okuduğu veriler (yalnızca yerel dosyalar; API çağrısı yok)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

from src import config
from src import review_store as rs

DOCS_DIR = config.DATA_DIR / "sample_docs"
JOBS_DIR = config.DATA_DIR / "jobs"
EVAL_DIR = config.ROOT / "eval"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


@st.cache_data(ttl=20)
def chunks() -> dict[str, dict]:
    return {c["id"]: c for c in _jsonl(config.DATA_DIR / "chunks" / "chunks.jsonl")}


@st.cache_data(ttl=20)
def sections() -> list[dict]:
    return _jsonl(config.DATA_DIR / "chunks" / "sections.jsonl")


@st.cache_data(ttl=20)
def parsed(stem: str) -> dict | None:
    p = config.PARSED_DIR / f"{stem}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


DOC_SHORT = config.DOC_NAMES


def short(doc: str) -> str:
    return config.doc_name(doc)


@st.cache_data(ttl=60)
def topics(doc: str) -> list[dict]:
    """Konu haritası (src/topics.py). Arayüz LLM'e gitmez: harita yoksa bölüm başlıkları."""
    from src.topics import topic_map
    return topic_map(doc, build_missing=False)


@st.cache_data(ttl=300)
def has_math(doc: str) -> bool:
    """Belgede formül içeren bölüm var mı (hesap sorusu seçeneği yalnızca o zaman gösterilir)."""
    from src.generation.generate import build_units, math_units
    try:
        return bool(math_units(build_units(doc)))
    except Exception:
        return False


@st.cache_data(ttl=10)
def item_stats() -> dict[str, dict]:
    from src.request import item_stats as _s
    return _s()


@st.cache_data(ttl=10)
def reports() -> dict[str, list[dict]]:
    from src.request import reported
    return reported()


def set_label(name: str, kind: str) -> str:
    """Dosya adından okunur set adı: 'qwen_qwen3.8-27b_english_tr' → 'Genetic Algorithms → TR · qwen3.8-27b (pilot)'"""
    if kind == "belge":
        stem, _, lang = name.rpartition("_")
        return f"{short(stem)} · {lang.upper()}"
    if name.startswith("bloom_"):
        return f"Deney · yalnızca {'hatırlama' if 'remember' in name else 'uygulama'}"
    if name.startswith("toplu_"):
        return f"Toplu üretim · {name.split('_')[1]} (karşılaştırma)"
    if name.startswith("v1_"):
        return f"Eski sürüm · {name[3:]}"
    model = "qwen3.8-27b" if "qwen" in name else ("gpt-oss-120b" if "gpt-oss" in name else name)
    target = "Genetic Algorithms → TR" if "english_tr" in name else "Yapay Zeka"
    return f"{target} · {model} (pilot)"


def doc_of(item: dict) -> str:
    cid = next(iter(item.get("chunk_ids") or []), "")
    return cid.split(":")[0] if cid else "?"


@st.cache_data(ttl=10)
def question_sets() -> list[dict]:
    """[{key, name, kind ('belge' | 'pilot'), path, items}] — tam akış çıktıları önce."""
    out = []
    for p in rs.question_sets():
        kind = "belge" if p.parent.name == "questions" else "pilot"
        name = p.stem.replace("_dogrulama", "")
        items = rs.load_set(p)
        for it in items:
            it["doc"] = doc_of(it)
            it["set"], it["set_kind"] = name, kind
        out.append({"key": str(p), "name": name, "kind": kind, "items": items})
    return out


def all_questions(include_pilot: bool = True) -> list[dict]:
    seen, out = set(), []
    for s in question_sets():
        if s["kind"] == "pilot" and not include_pilot:
            continue
        for it in s["items"]:
            if it["id"] not in seen:
                seen.add(it["id"])
                out.append(it)
    return out


def decisions() -> dict[str, dict]:
    return rs.decisions()


@st.cache_data(ttl=20)
def documents() -> list[dict]:
    secs = sections()
    chs = chunks().values()
    qs = all_questions()
    out = []
    for pdf in sorted(DOCS_DIR.glob("*.pdf")):
        p = parsed(pdf.stem) or {}
        pages = p.get("pages", [])
        mine = [q for q in qs if q["doc"] == pdf.stem]
        out.append({
            "stem": pdf.stem, "file": pdf.name, "title": p.get("title") or pdf.stem, "language": p.get("language", "?"),
            "pages": p.get("n_pages", 0), "size_mb": pdf.stat().st_size / 1e6,
            "vision_pages": sum(pg.get("source") == "vision" for pg in pages),
            "pending_vision": sum(pg.get("quality") == "needs_vision" for pg in pages),
            "table_pages": sum("tables_extracted" in pg.get("flags", []) for pg in pages),
            "chunks": sum(c["doc"] == pdf.stem for c in chs),
            "sections": sum(s["doc"] == pdf.stem for s in secs),
            "questions": len(mine),
            "verified": sum(q.get("verification", {}).get("label") == "verified" for q in mine),
            "parsed": bool(p),
        })
    return out


@st.cache_data(ttl=60)
def eval_json(name: str) -> dict | list | None:
    p = EVAL_DIR / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def quota() -> list[dict]:
    from src.llm import ledger
    return ledger.report()


# --- Arka plan işleri (Yükle ve Üret) -------------------------------------------------------------

STEP_RE = re.compile(r"^(\d)/6 (.*)$")


def start_job(pdf_name: str, language: str | None) -> Path:
    """Tam akışı ayrı bir süreçte başlatır; arayüz kapansa da devam eder. Çıktı data/jobs/<belge>.log"""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(pdf_name).stem
    log = JOBS_DIR / f"{stem}.log"
    args = [sys.executable, "-m", "src.pipeline", pdf_name] + ([language] if language else [])
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    with log.open("w", encoding="utf-8") as fh:
        subprocess.Popen(args, cwd=config.ROOT, stdout=fh, stderr=subprocess.STDOUT, creationflags=flags,
                         env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    (JOBS_DIR / f"{stem}.json").write_text(json.dumps({"file": pdf_name, "started": time.time()}), encoding="utf-8")
    return log


def job_status(stem: str) -> dict | None:
    meta, log = JOBS_DIR / f"{stem}.json", JOBS_DIR / f"{stem}.log"
    if not meta.exists():
        return None
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []
    step, label = 0, "Başlıyor"
    for ln in lines:
        m = STEP_RE.match(ln.strip())
        if m:
            step, label = int(m.group(1)), m.group(2)
    done = any(ln.startswith("Bitti") for ln in lines)
    failed = any("Traceback" in ln for ln in lines) and not done
    waiting = next((ln.strip() for ln in reversed(lines[-5:]) if "⏳" in ln), None)
    return {"step": 6 if done else step, "label": label, "done": done, "failed": failed, "waiting": waiting,
            "tail": [ln for ln in lines if ln.strip()][-8:], "started": json.loads(meta.read_text())["started"]}


def jobs() -> list[tuple[str, dict]]:
    if not JOBS_DIR.exists():
        return []
    return [(p.stem, s) for p in sorted(JOBS_DIR.glob("*.json"), key=lambda p: -p.stat().st_mtime)
            if (s := job_status(p.stem))]

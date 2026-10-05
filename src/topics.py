"""Konu haritası (PROMPTS.md §7): sınav hazırlarken kullanıcının SEÇTİĞİ konular.

Serbest metin yerine hazır konu listesi: anlamsız istek yazılamaz, kullanıcı belgenin neyi kapsadığını görür.
Seçilen konunun adı arama sorgusudur (src/request.py): bağlamı haritanın sayfaları değil, arama belirler.

Kullanım: python -m src.topics [belge ...]   (belge verilmezse hepsi; var olan haritalar yeniden yapılmaz)
"""

from __future__ import annotations

import json
import re
import sys

from src import config
from src.llm.router import AllModelsExhausted, call
from src.prompts import load_prompt

TOPIC_DIR = config.DATA_DIR / "topics"
LANG_NAMES = {"tr": "Turkish", "en": "English"}


def _chunks(doc: str) -> list[dict]:
    path = config.DATA_DIR / "chunks" / "chunks.jsonl"
    return [c for c in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip())
            if c["doc"] == doc]


def _fallback(doc: str) -> list[dict]:
    """Konu haritası yapılamazsa: bölüm başlıkları (yalnızca sayıdan oluşan başlıklar 'Sayfa N' olur)."""
    path = config.DATA_DIR / "chunks" / "sections.jsonl"
    out = []
    for s in (json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()):
        if s["doc"] != doc:
            continue
        title = (s.get("title") or "").strip(" •-")
        if not title or re.fullmatch(r"[\d\s.]+", title) or len(title) > 70:
            p = s["pages"]
            title = f"Sayfa {p[0]}" if len(p) == 1 else f"Sayfa {p[0]}-{p[-1]}"
        out.append({"title": title, "pages": s["pages"]})
    return out


def build(doc: str, language: str = "tr") -> list[dict]:
    chunks = _chunks(doc)
    by_page: dict[int, list[str]] = {}
    for c in chunks:
        if not c.get("pending_vision"):
            by_page.setdefault(c["page"], []).append(c["text"])
    document = "\n\n".join(f"[s.{p}] " + "\n".join(t) for p, t in sorted(by_page.items()))
    prompt = (load_prompt("7").replace("{output_language}", LANG_NAMES.get(language, language))
              .replace("{document}", document))
    r = call("generate_batch", prompt, json_mode=True, max_tokens=16000, temperature=0.2)
    raw = json.loads(r.text).get("topics", [])
    pages, seen, out = set(by_page), set(), []
    for t in raw:
        title = re.sub(r"\s+", " ", str(t.get("title", ""))).strip(" .-•")
        ps = sorted({int(p) for p in t.get("pages", []) if str(p).isdigit() and int(p) in pages})
        if not title or not ps or title.lower() in seen:
            continue
        seen.add(title.lower())
        out.append({"title": title, "pages": ps})
    return out


def topic_map(doc: str, rebuild: bool = False, build_missing: bool = True) -> list[dict]:
    """[{"title", "pages", "source": "llm"|"sections"}]; önce disk önbelleği.
    build_missing=False (arayüz): harita yoksa LLM'e gitmeden bölüm başlıkları döner."""
    path = TOPIC_DIR / f"{doc}.json"
    if path.exists() and not rebuild:
        return json.loads(path.read_text(encoding="utf-8"))
    if not build_missing:
        return [{**t, "source": "sections"} for t in _fallback(doc)]
    try:
        topics = [{**t, "source": "llm"} for t in build(doc)]
    except (AllModelsExhausted, json.JSONDecodeError, AttributeError):
        topics = []
    if not topics:  # kota yoksa ya da yanıt bozuksa: bölüm başlıkları (diske yazılmaz; sonra yeniden denenir)
        return [{**t, "source": "sections"} for t in _fallback(doc)]
    TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    return topics


if __name__ == "__main__":
    docs = sys.argv[1:] or sorted({c["doc"] for c in (json.loads(x) for x in (config.DATA_DIR / "chunks" / "chunks.jsonl")
                                                           .read_text(encoding="utf-8").splitlines() if x.strip())})
    for d in docs:
        ts = topic_map(d)
        print(f"■ {d}: {len(ts)} konu ({ts[0]['source'] if ts else '-'})")
        for t in ts:
            print(f"   - {t['title']}  s.{','.join(map(str, t['pages']))}")

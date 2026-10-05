"""Tek komutla uçtan uca: PDF → okuma → görsel okuma → bölümleme → dizin → soru üretimi → doğrulama.

Kullanım: python -m src.pipeline "<data/sample_docs içindeki PDF adı ya da kök adı>" [çıktı_dili]
          python -m src.pipeline --hepsi [çıktı_dili]   (klasördeki tüm PDF'ler, bitmişler atlanır)
Çıktı:    data/questions/<belge>_<dil>.jsonl  (arayüzde inceleme listesinde görünür)

Kota davranışı (KALİTE KAPISI + KUYRUK): yalnızca onaylı modeller kullanılır (src/llm/models.py APPROVED).
Onaylı modellerin kotası dolunca iş BEKLER ve kaldığı yerden devam eder; daha zayıf bir modele geçmez.
Her LLM yanıtı önbellekte olduğundan yarıda kesilen iş yeniden çalıştırılınca yalnızca eksik kısmı yapar.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter

from src import config
from src.llm import ledger
from src.llm.router import AllModelsExhausted

OUT = config.DATA_DIR / "questions"


def patient(fn, *args, what: str = "", on_wait=None, **kwargs):
    """Tüm onaylı modeller kota/bekleme yüzünden kapalıysa en kısa bekleme kadar uyuyup yeniden dener.
    on_wait(neden, saniye): beklemeyi arayüze bildirmek için (ör. sınav isteğinin ilerleme satırı)."""
    for _ in range(200):
        try:
            return fn(*args, **kwargs)
        except AllModelsExhausted as e:
            if e.transient:  # kota değil: sağlayıcı yoğun / dakikalık sınır → kısa bekleme
                wait = 120
                why = "sağlayıcı şu an yoğun (geçici, kota değil)"
            else:  # kayan pencereden hesaplanan gerçek süre; bilinmiyorsa 15 dk sonra yeniden bak
                wait = min(e.retry_in, 3600) if e.retry_in > 0 else 900
                why = "onaylı modellerin kotası dolu"
            print(f"   ⏳ {what}: {why} → {max(1, round(wait / 60))} dk bekleniyor (daha zayıf modele geçilmez)",
                  flush=True)
            if on_wait:
                on_wait(why, wait)
            time.sleep(wait + 5)
    raise RuntimeError("kota çok uzun süre açılmadı")


def _generate(units: list[dict], lang: str) -> list[dict]:
    """Önce toplu üretim (onaylı Gemini, grup başına 1 istek). Gruplar ayrı ayrı: biri başarısız olsa diğerleri
    korunur. Gemini yalnızca YOĞUNSA (503) birkaç kez bekleyip yeniden denenir; günlük kotası gerçekten
    bittiyse o grubun birimleri birim başına üretime (qwen) gider, o da kota dolarsa bekler."""
    from src.generation.generate import RELATED_CHARS, batch_groups, generate_group, generate_unit

    items, start = [], 0
    groups = batch_groups(units)
    for gi, g in enumerate(groups, 1):
        done = _batch_try(lambda: generate_group(g, start, lang, "generate_batch"),
                          f"toplu üretim grup {gi}/{len(groups)}", len(g), "birim başına üretim (qwen)")
        if done is None:
            done = []
            for k, u in enumerate(g):
                i = start + k
                related = "\n\n".join(units[j]["text"][:RELATED_CHARS] for j in (i - 1, i + 1) if 0 <= j < len(units))
                done += patient(generate_unit, u, related, lang, "generate", unit_index=i,
                                what=f"üretim {i + 1}/{len(units)}")
                print(f"   üretim {i + 1}/{len(units)} (qwen)", flush=True)  # arayüz ilerlemeyi görsün
        items += done
        start += len(g)
    return items


def _batch_try(fn, what: str, n_units: int, fallback: str):
    """Tek toplu istek. Gemini yalnızca YOĞUNSA (503) 2, 4, 8 dk bekleyip yeniden dener; kota gerçekten bittiyse
    None döner (çağıran yedek yolu seçer)."""
    for attempt in range(4):
        try:
            done = fn()
            print(f"   {what}: {n_units} birim → {len(done)} soru ({done[0]['model'] if done else '-'})", flush=True)
            return done
        except AllModelsExhausted as e:
            if not e.transient or attempt == 3:
                print(f"   {what} yapılamadı ({e}) → {fallback}", flush=True)
                return None
            wait = 120 * 2 ** attempt
            print(f"   ⏳ {what}: Gemini şu an yoğun (geçici, kota değil) → {wait // 60} dk sonra yeniden", flush=True)
            time.sleep(wait)
    return None


def _generate_worked(units: list[dict], lang: str) -> list[dict]:
    """Hesap soruları (PROMPTS.md §2c) yalnızca formüllü birimlerden. §2c için yedek (birim başına) yol yok:
    kota biterse bu adım atlanır, sınanmamış bir modele devredilmez; sonraki çalıştırmada önbellekle tamamlanır."""
    from src.generation.generate import batch_groups, generate_worked_group, math_units

    mu = math_units(units)
    if not mu:
        print("   hesap soruları: formül içeren bölüm yok, atlandı", flush=True)
        return []
    items, start = [], 0
    groups = batch_groups(mu)
    for gi, g in enumerate(groups, 1):
        done = _batch_try(lambda: generate_worked_group(g, start, lang, "generate_batch"),
                          f"hesap soruları grup {gi}/{len(groups)}", len(g), "bu grup atlandı (kota açılınca yeniden)")
        items += done or []
        start += len(g)
    ok = sum(i["check"]["status"] != "rejected" for i in items)
    print(f"   hesap soruları: {len(items)} üretildi, {ok} tanesi SymPy kontrolünden geçti", flush=True)
    return items


def _vision_until_done(parsed_path, pdf) -> None:
    from src.ingestion.vision import pending_pages, run_vision
    while True:
        if run_vision(parsed_path, pdf):
            return
        left = pending_pages(json.loads(parsed_path.read_text(encoding="utf-8")), pdf)
        if not left:
            return
        waits = [ledger.cooldown_left(m) for m in ledger.MODELS]
        wait = min([w for w in waits if w > 0] or [3600])
        print(f"   ⏳ görsel okuma: {len(left)} sayfa kaldı, kota bekleniyor ({wait / 60:.0f} dk)", flush=True)
        time.sleep(wait + 5)


def merge_existing(old: list[dict], items: list[dict], chunks: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Yeniden çalıştırma EKLER, silmez: dosyadaki sorular (doğrulama, insan kararı ve çözüm kayıtları onların
    kimliğine bağlı) korunur; önbellekten aynen gelenler atlanır, eskilerin tekrarı olan yeni sorular reddedilir
    (doğrulamaya gitmez). Belge değiştiyse parçası artık olmayan eski sorular düşer.
    → (korunan eskiler, düşen eskiler, doğrulanacak yeniler)"""
    from src.review_store import question_id
    from src.verification.checks import mark_duplicates

    stale = [i for i in old if not all(c in chunks for c in i.get("chunk_ids", []))]
    kept = [i for i in old if i not in stale]
    known = {question_id(i) for i in kept}
    new = [i for i in items if question_id(i) not in known]
    mark_duplicates(new, keep=kept)
    return kept, stale, new


def run(name: str, output_language: str | None = None) -> list[dict]:
    from src.chunking.__main__ import main as chunk_all
    from src.generation.generate import build_units
    from src.ingestion.pdf_parser import parse_pdf
    from src.ingestion.vision import apply_cached_vision
    from src.retrieval.index import Index
    from src.verification.verify import verify_item

    pdf = next(p for p in (config.DATA_DIR / "sample_docs").glob("*.pdf") if name in (p.name, p.stem))
    t0 = time.time()
    print(f"■ {pdf.name}", flush=True)

    print("1/6 PDF okuma (yerel)", flush=True)
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    parsed_path = config.PARSED_DIR / f"{pdf.stem}.json"
    parsed_path.write_text(json.dumps(parse_pdf(pdf), ensure_ascii=False, indent=2), encoding="utf-8")
    apply_cached_vision(parsed_path, pdf)

    print("2/6 görsel okuma (yalnızca okunmamış sayfalar)", flush=True)
    _vision_until_done(parsed_path, pdf)

    print("3/6 bölümleme (yerel)", flush=True)
    chunk_all()

    print("4/6 dizin (yalnızca yeni/değişen parçaların embedding'i)", flush=True)
    print("   ", Index().build(), flush=True)
    from src.topics import topic_map  # sınav hazırlarken seçilecek konular (PROMPTS.md §7); kota yoksa bölüm başlıkları
    ts = topic_map(pdf.stem)
    print(f"    konu haritası: {len(ts)} konu ({'model' if ts and ts[0]['source'] == 'llm' else 'bölüm başlıkları'})",
          flush=True)

    lang = output_language or json.loads(parsed_path.read_text(encoding="utf-8"))["language"]
    units = build_units(pdf.stem)
    print(f"5/6 soru üretimi: {len(units)} birim, çıktı dili {lang}", flush=True)
    items = _generate(units, lang)
    items += _generate_worked(units, lang)

    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    out = OUT / f"{pdf.stem}_{lang}.jsonl"
    old = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()] if out.exists() else []
    old, stale, items = merge_existing(old, items, chunks)

    note = ""
    if old or stale:
        note = (f" (dosyadaki {len(old)} soru korunuyor"
                + (f", parçası kalmayan {len(stale)} soru çıkarıldı" if stale else "") + ")")
    print(f"6/6 doğrulama: {len(items)} yeni soru{note}", flush=True)
    for n, it in enumerate(items, 1):
        it["verification"] = patient(verify_item, it, chunks, light=True, what=f"doğrulama {n}/{len(items)}")
        if n % 5 == 0 or n == len(items):  # arayüzde ilerleme görünsün (uzun adım; takılma sanılmasın)
            print(f"   doğrulama {n}/{len(items)} · iş başlayalı {(time.time() - t0) / 60:.1f} dk", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in old + items), encoding="utf-8")
    labels = Counter(i["verification"]["label"] for i in items)
    print(f"\nBitti ({(time.time() - t0) / 60:.1f} dk): yeni {dict(labels)}, dosyada toplam {len(old) + len(items)} "
          f"→ {out}", flush=True)
    return items


def run_all(output_language: str | None = None) -> None:
    """data/sample_docs/ içindeki tüm PDF'leri sırayla işler. Çıktısı PDF'ten yeni olan belge atlanır
    (bitmiş iş tekrar yapılmaz); yarıda kalan belge önbellek sayesinde kaldığı yerden devam eder."""
    from src.llm.capacity import doc_cost

    pdfs = sorted((config.DATA_DIR / "sample_docs").glob("*.pdf"))
    todo = []
    for pdf in pdfs:
        done = list(OUT.glob(f"{pdf.stem}_*.jsonl")) if OUT.exists() else []
        if any(p.stat().st_mtime > pdf.stat().st_mtime for p in done):
            print(f"✓ {pdf.name}: zaten işlenmiş, atlanıyor", flush=True)
        else:
            todo.append(pdf)
    if not todo:
        print("Tüm belgeler işlenmiş.")
        return
    print(f"\nKuyruk: {len(todo)} belge", flush=True)
    for n, pdf in enumerate(todo, 1):
        print(f"\n===== [{n}/{len(todo)}] =====", flush=True)
        run(pdf.name, output_language)
        try:
            c = doc_cost(pdf.stem)
            print(f"   (bu belge ≈ {c['üretim token'] + c['doğrulama token']:,} token)", flush=True)
        except Exception:
            pass
    print("\nKUYRUK BİTTİ — sorular arayüzde: .venv\\Scripts\\streamlit run src/app.py", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--hepsi", "--all"):
        run_all(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

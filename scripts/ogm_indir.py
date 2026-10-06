"""MEB OGM Materyal'den seçili PDF koleksiyonlarını indirir (yalnızca geliştirme ve deney verisi; depoya girmez).

Katalog: ogmmateryal.eba.gov.tr ön yüz paketindeki pdfUrl kayıtları (başlık, ders, sınıf, kategori). Koleksiyonlar:
  mebi-konu-ozetleri  TYT/AYT konu özeti kitapları (ders notu yerine sistem denemesi)
  3adim               3 Adım Soru Bankası: uzmanlarca adım adım zorlaşan sorular (zorluk karşılaştırması)
  kazanim_kavrama     9-12. sınıf kazanım kavrama testleri (cevap anahtarlı)
  tarama              TYT/AYT tarama testleri
  yks-deneme          2024 TYT/AYT/YDT deneme sınavları
Çıktı: data/kaynak_veri/ogm/<koleksiyon>/*.pdf ve data/kaynak_veri/ogm/katalog.json. İnen dosya atlanır.

Kullanım: python scripts\\ogm_indir.py <katalog.json>
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "kaynak_veri" / "ogm"
WANT = ("mebi-konu-ozetleri", "3adim", "kazanim_kavrama", "tarama", "yks-deneme")
TR = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_")


def collection(url: str) -> str | None:
    return next((c for c in WANT if f"/{c}/" in url), None)


def slug(*parts: str) -> str:
    s = "_".join(p for p in parts if p).translate(TR)
    return re.sub(r"[^A-Za-z0-9_.-]+", "", s)[:90] or "dosya"


def fetch(job: dict) -> str:
    dest = OUT / job["collection"] / job["file"]
    if dest.exists() and dest.stat().st_size > 1000:
        return f"var    {job['file']}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            req = urllib.request.Request(job["pdfUrl"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest.with_suffix(".part"), "wb") as fh:
                while chunk := r.read(1 << 20):
                    fh.write(chunk)
            part = dest.with_suffix(".part")
            if part.read_bytes()[:5] != b"%PDF-":
                part.unlink()
                return f"PDF değil {job['file']}"
            part.replace(dest)
            return f"indi   {job['file']} ({dest.stat().st_size // 1_000_000} MB)"
        except Exception as e:  # ağ kesintisi: biraz bekle, yeniden dene
            time.sleep(20 * (attempt + 1))
            err = e
    return f"HATA   {job['file']}: {err}"


def main() -> None:
    rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    jobs, seen = [], set()
    for r in rows:
        c = collection(r["pdfUrl"])
        if not c or r["pdfUrl"] in seen:
            continue
        seen.add(r["pdfUrl"])
        name = slug(r.get("category", ""), r.get("grade", ""), r.get("lesson", ""), r.get("title", ""))
        jobs.append({"collection": c, "file": f"{name}_{len(jobs):03d}.pdf", **{k: r.get(k, "") for k in
                     ("title", "category", "grade", "lesson", "pdfUrl")}})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "katalog.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(jobs)} PDF: " + ", ".join(f"{c} {sum(j['collection'] == c for j in jobs)}" for c in WANT), flush=True)
    with ThreadPoolExecutor(3) as ex:
        for i, msg in enumerate(ex.map(fetch, jobs), 1):
            print(f"{i}/{len(jobs)} {msg}", flush=True)
    print("bitti", flush=True)


if __name__ == "__main__":
    main()

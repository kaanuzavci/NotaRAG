"""Ankara Üniversitesi Açık Ders'ten (Moodle, girişsiz) farklı fakültelerin ders notlarını indirir — "her türlü PDF"
denemesi için üniversite düzeyinde çeşitli belge (yalnızca geliştirme ve deney verisi; depoya girmez).

Fakülte başına rastgele (sabit tohum) DERS dersten ilk HAFTA kaynak; yalnızca PDF olanlar. İstekler sırayla ve
aralıklı (sunucuya yük bindirmez). Çıktı: data/kaynak_veri/auad/<fakülte>/<ders>__<dosya>.pdf + katalog.json.

Kullanım: python scripts\\auad_indir.py [ders_sayısı=6] [hafta=3]
"""
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://acikders.ankara.edu.tr/"
OUT = Path(__file__).resolve().parents[1] / "data" / "kaynak_veri" / "auad"
FACULTIES = {18: "muhendislik", 23: "fen", 78: "tip", 32: "hukuk", 19: "siyasal", 29: "ziraat", 93: "eczacilik",
             15: "egitim", 17: "dtcf", 11: "veteriner", 57: "saglik", 25: "iletisim"}
TR = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_")


def get(url: str, binary: bool = False):
    time.sleep(1.0)  # nazik tarama
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (NotaRAG ders projesi)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
        return (data, r.geturl(), r.headers.get("Content-Type", "")) if binary else data.decode("utf-8", "replace")


def courses(cat: int, depth: int = 0) -> set[int]:
    html = get(f"{BASE}course/index.php?categoryid={cat}&perpage=200")
    found = {int(x) for x in re.findall(r"course/view\.php\?id=(\d+)", html)}
    if depth < 2 and len(found) < 40:
        subs = {int(x) for x in re.findall(r"course/index\.php\?categoryid=(\d+)", html)} - {cat}
        for s in sorted(subs)[:8]:
            found |= courses(s, depth + 1)
    return found


def main() -> None:
    n_course = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_week = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rnd, catalog = random.Random(7), []
    OUT.mkdir(parents=True, exist_ok=True)
    for cat, name in FACULTIES.items():
        try:
            ids = sorted(courses(cat))
        except Exception as e:
            print(f"{name}: kategori okunamadı ({e})", flush=True)
            continue
        picked = rnd.sample(ids, min(n_course, len(ids)))
        print(f"{name}: {len(ids)} ders, {len(picked)} seçildi", flush=True)
        for cid in picked:
            try:
                page = get(f"{BASE}course/view.php?id={cid}")
            except Exception as e:
                print(f"  ders {cid}: okunamadı ({e})", flush=True)
                continue
            title = re.search(r"<title>(?:Kurs|Course)\s*:\s*([^|<]+)", page)
            title = (title.group(1).strip() if title else str(cid))[:60]
            got = 0
            for rid in dict.fromkeys(re.findall(r"mod/resource/view\.php\?id=(\d+)", page)):
                if got >= n_week:
                    break
                try:
                    data, final, ctype = get(f"{BASE}mod/resource/view.php?id={rid}&redirect=1", binary=True)
                except Exception as e:
                    print(f"  {title}: kaynak {rid} indirilemedi ({e})", flush=True)
                    continue
                if not data.startswith(b"%PDF-"):
                    continue  # pptx/docx/video sayfası: yalnızca PDF
                fname = urllib.parse.unquote(final.rsplit("/", 1)[-1].split("?")[0])
                dest = OUT / name / re.sub(r"[^A-Za-z0-9_.-]+", "", f"{title}__{fname}".translate(TR))[:120]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                catalog.append({"faculty": name, "course_id": cid, "course": title, "resource_id": rid,
                                "file": str(dest.relative_to(OUT)), "url": final, "bytes": len(data)})
                got += 1
                print(f"  {title}: {fname} ({len(data) // 1000} KB)", flush=True)
            (OUT / "katalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"bitti: {len(catalog)} PDF, {sum(c['bytes'] for c in catalog) // 1_000_000} MB", flush=True)


if __name__ == "__main__":
    main()

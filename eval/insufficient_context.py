"""Yetersiz bağlam testi (README §7.3): soru çıkmaması gereken sayfalarda üretici boş liste döndürüyor mu?

Sayfalar: dizin dışı bırakılanlar (kapak, içindekiler, kaynakça). Normalde üretime hiç girmezler; bu test
modelin kendi başına da 'bu içerikten soru çıkmaz' diyebildiğini ölçer (ikinci savunma hattı).
Çalıştırma: python -m eval.insufficient_context
"""

import json

from src import config
from src.generation.generate import generate_unit

PAGES = [("4_ENERJİ, TARIM, BESLENME", 1, "kapak"), ("4_ENERJİ, TARIM, BESLENME", 2, "içindekiler"),
         ("4_ENERJİ, TARIM, BESLENME", 23, "kaynakça"), ("7.Hafta Sunu Dosyası", 1, "kapak"),
         ("english", 1, "kapak"), ("english", 2, "kaynakça")]


def main() -> None:
    empty = 0
    for doc, page, kind in PAGES:
        p = json.loads((config.PARSED_DIR / f"{doc}.json").read_text(encoding="utf-8"))["pages"][page - 1]
        text = "\n".join(x for x in [p["heading"] or "", p["text"]] if x)
        unit = {"title": kind, "pages": [page], "text": f"[s.{page}] {text}",
                "chunks": [{"id": f"{doc}:p{page:03d}:1", "doc": doc, "page": page, "text": text, "source": "text"}]}
        items = generate_unit(unit, "", "tr")
        passed = [i for i in items if i["check"]["status"] != "rejected"]
        empty += not items
        print(f"{doc[:14]:14} s{page:<3} {kind:12} → {len(items)} soru üretildi, {len(passed)} kontrolden geçti"
              + "".join(f"\n      • {i['q'].get('question', '')[:100]}" for i in items))
    print(f"\nBoş liste döndürülen: {empty}/{len(PAGES)}")


if __name__ == "__main__":
    main()

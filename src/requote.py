"""Kaynak metin düzeltildikten sonra (ör. üst simgeler, satır sonu tireleri) mevcut soruların bakımı. LLM yok.

1. Kanıt alıntısı, güncel parça metninden BİREBİR yeniden alıntılanır (normalize edilmiş kelime dizisi eşleşmesi):
   'bü-tün' → 'bütün', '2n' → '2ⁿ'. Anlam değişmez; yalnızca yazım kaynağa eşitlenir.
2. Kod kontrolleri güncel metinle yeniden çalışır (kanıt hâlâ bulunuyor mu; sonradan eklenen kurallar —
   ör. soru yazım hataları — mevcut sorulara da uygulanır).
3. Bozuk metinden etkilenmiş olabilecek sorular işaretlenir: sorunun/şıkların içinde, kaynakta artık üst/alt
   simgeli yazılan bir ifadenin düz hali geçiyorsa ('2n' ↔ '2ⁿ', '1.24' ↔ '1.2⁴') soru 'needs_review' olur ve
   nedeni yazılır — model düz yazımı 2·n diye okumuş olabilir.

Kullanım: python -m src.requote [--yaz]   (--yaz verilmezse yalnızca rapor)
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata

from src import config
from src.generation.schema import Question
from src.textnorm import SUP, normalize_for_match as norm
from src.verification.checks import check

SETS = sorted((config.DATA_DIR / "questions").glob("*.jsonl")) + sorted((config.DATA_DIR / "pilot").glob("*_dogrulama.jsonl"))


def _words(text: str) -> list[tuple[str, int, int]]:
    """Metnin normalize kelimeleri ve her birinin metindeki (başlangıç, bitiş) konumu."""
    out = []
    for m in re.finditer(r"\S+", text):
        for w in norm(m.group(0)).split():
            out.append((w, m.start(), m.end()))
    return out


def requote(quote: str, texts: list[str]) -> str | None:
    """Alıntının güncel metindeki birebir karşılığı (kelime dizisi eşleşmesi); bulunamazsa None."""
    q = norm(quote).split()
    if not q:
        return None
    for text in texts:
        ws = _words(text)
        for i in range(len(ws) - len(q) + 1):
            if [w for w, _, _ in ws[i:i + len(q)]] == q:
                s, e = ws[i][1], ws[i + len(q) - 1][2]
                return text[s:e].strip(" ,;:")
    return None


def degraded_forms(texts: list[str]) -> set[str]:
    """Kaynakta ÜSLÜ yazılan ifadelerin düz halleri ('2ⁿ' → '2n', '1.2⁴' → '1.24'). Alt simgeler anlamı
    değiştirmez ('x1' = 'x₁'), yalnızca üsler aranır."""
    out = set()
    for t in texts:
        for tok in re.findall(r"\S*[" + re.escape("".join(set(SUP.values()) - {"′"})) + r"]\S*", t):
            plain = unicodedata.normalize("NFKC", tok).strip(".,;:()")
            if plain != tok.strip(".,;:()") and len(plain) >= 2 and re.search(r"\d", plain):
                out.add(plain)
    return out


def main(write: bool) -> None:
    chunks = {json.loads(x)["id"]: json.loads(x)
              for x in (config.DATA_DIR / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    for path in SETS:
        items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        n_quote = n_flag = n_lost = 0
        for it in items:
            q = it.get("q", {})
            if "question" not in q or not it.get("chunk_ids"):
                continue
            unit = [chunks[c] for c in it["chunk_ids"] if c in chunks]
            texts = [c["text"] for c in unit]
            new = requote(q.get("evidence_quote", ""), texts)
            if new and new != q["evidence_quote"]:
                q["evidence_quote"] = new
                n_quote += 1
            # Yeniden kod kontrolü (yalnızca daha önce kontrolden geçmiş sorular; reddedilenler değişmez)
            if it.get("check", {}).get("status") != "rejected":
                try:
                    res = check(Question(**q), unit)
                    it["check"] = {**it["check"], "evidence_match": res["evidence_match"],
                                   "evidence_page": res["evidence_page"] or it["check"].get("evidence_page"),
                                   # yeni kod kontrollerinin uyarıları (ör. soru yazım kuralları) eskilere eklenir
                                   "flags": sorted(set(it["check"].get("flags", [])) | set(res["flags"]))}
                    new_rej = [r for r in res["rejected"] if r not in ("evidence_not_found",)]
                    if new_rej:  # yeni eklenen bir red kuralına takılıyorsa (ör. 'hepsi / hiçbiri' şıkkı)
                        it["check"] = {**it["check"], "status": "rejected", "rejected": new_rej}
                        it["verification"] = {"label": "rejected", "why": "kod kontrolü: " + ", ".join(new_rej)}
                    if res["evidence_match"] is None:
                        n_lost += 1
                except Exception:
                    pass
            fields = " ".join([q.get("question", ""), q.get("answer", "")] + list(q.get("options") or []))
            hits = [f for f in degraded_forms(texts) if re.search(rf"(?<![\w.]){re.escape(f)}(?![\w])", fields)]
            ver = it.get("verification") or {}
            if ver.get("requote_flag") and not hits:  # önceki çalıştırmanın yanlış işareti (metin yeniden düzeldi)
                ver = {k: v for k, v in ver.items() if k != "requote_flag"}
                it["verification"] = {**ver, "label": "verified", "why": "doğrulayıcı yalnızca anahtar şıkkı doğru buldu"}
            if hits and ver.get("label") == "verified":
                it["verification"] = {**ver, "label": "needs_review",
                                      "why": f"kaynak metin düzeltildi: soruda '{hits[0]}' geçiyor, kaynakta üslü/indisli "
                                             f"yazılıyor; soru bozuk metinden üretilmiş olabilir", "requote_flag": hits}
                n_flag += 1
        print(f"{path.name}: {len(items)} soru · alıntısı güncellenen {n_quote} · işaretlenen {n_flag} · "
              f"kanıtı artık bulunamayan {n_lost}")
        if write:
            path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")


if __name__ == "__main__":
    main("--yaz" in sys.argv)

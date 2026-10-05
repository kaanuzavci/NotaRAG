"""Kapasite hesaplayıcı: bugün (kayan 24 saat) ne kadar iş yapılabilir, bir belge ne kadar tutar?

Kullanım: python -m src.llm.capacity [belge ...]
Internet kullanmaz; kota defteri (data/llm.sqlite) ve parçalar üzerinden hesaplar.

Birim maliyetler 2026-10-03 ölçümlerinden (gerçek kullanım; tahmin değil):
  soru üretimi  ~2.700 token / üretim birimi (≈1.400'ü sabit kural metni)
  doğrulama     ~650 token / çağrı; hafif modda soru başına ~1,1 çağrı (kısa cevapta hakem)
  görsel okuma  ~2.700 token / sayfa (Groq) — Gemini'de token değil istek sınırı (20/gün/model)
"""

from __future__ import annotations

import sys
import time

from src.generation.generate import _n_questions, build_units
from src.llm import ledger
from src.llm.models import MODELS, ROLES

GEN_TOKENS_PER_UNIT = 2700
VERIFY_TOKENS_PER_QUESTION = 650 * 1.1


def pool_left(role: str) -> tuple[int, int]:
    """(rol zincirindeki token bütçesi kalanı, istek bütçesi kalanı) — token sınırı olmayanlar istekle sayılır."""
    tok = req = 0
    for m in ROLES[role]:
        spec = MODELS.get(m)
        if not spec or not ledger.available(m):
            continue
        if spec.tpd:
            tok += max(0, spec.tpd - int(ledger.tokens_24h(m) * 1.05))
        elif spec.rpd:
            req += max(0, spec.rpd - ledger.usage(m)[0])
    return tok, req


def doc_cost(doc: str) -> dict:
    units = build_units(doc)
    n_q = sum(_n_questions(u["text"]) for u in units)
    return {"birim": len(units), "soru": n_q, "üretim token": len(units) * GEN_TOKENS_PER_UNIT,
            "doğrulama token": int(n_q * VERIFY_TOKENS_PER_QUESTION)}


def main() -> None:
    print("Son 24 saat kullanım / sınır:")
    for r in ledger.report():
        if r["tpd"] or r["requests"]:
            lim = f"{r['tokens_24h']:>7} / {r['tpd']:>7} token" if r["tpd"] else f"{r['requests']:>3} / {r['rpd']} istek"
            extra = f"  ⏳ {r['cooldown_s'] // 60} dk bekleme" if r["cooldown_s"] else ""
            if r["cached_24h"]:
                extra += f"  (istem önbelleğinden {r['cached_24h']:,})"
            print(f"  {r['model']:24} {lim}{extra}")
    syncs = [(r["model"], s) for r in ledger.report() if (s := ledger.last_sync(r["model"]))]
    if syncs:  # sağlayıcı ≈ kaydımız − önbellekli → önbellekli token kotadan düşmüyor (kayıtta düşülebilir)
        print("\nSon token/gün hatasında sağlayıcının bildirdiği kullanım (istem önbelleği ölçümü):")
        for model, (ts, used, ours, cached) in syncs:
            print(f"  {model:24} sağlayıcı {used:>7,} · kaydımız {ours:>7,} (önbellekli {cached:,})"
                  f" · {time.strftime('%d.%m %H:%M', time.localtime(ts))}")
    g_tok, _ = pool_left("generate")
    v_tok, _ = pool_left("verify")
    print(f"\nŞu an kullanılabilir: üretim havuzu ~{g_tok:,} token, doğrulama havuzu ~{v_tok:,} token")
    for doc in sys.argv[1:]:
        c = doc_cost(doc)
        days = max(c["üretim token"] / max(1, sum(MODELS[m].tpd or 0 for m in ROLES["generate"])),
                   c["doğrulama token"] / max(1, sum(MODELS[m].tpd or 0 for m in ROLES["verify"])))
        ok_now = c["üretim token"] <= g_tok and c["doğrulama token"] <= v_tok
        print(f"\n{doc}: {c['birim']} birim, ~{c['soru']} soru → üretim ~{c['üretim token']:,}, doğrulama ~{c['doğrulama token']:,} token"
              f"\n   tam kotayla ~{days:.1f} günlük iş · şu anki kalanla {'hemen biter' if ok_now else 'kuyrukta bekleyerek biter'}")


if __name__ == "__main__":
    main()

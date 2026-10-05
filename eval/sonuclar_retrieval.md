# Arama Değerlendirmesi

İsabet@k: ilk k sonuçta doğru sayfa var mı. MRR@10: doğru sayfanın sırasının tersinin ortalaması.


## TÜMÜ (n=145)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 77% | 97% | 99% | 0.86 |
| BM25, köklemesiz | 49% | 58% | 62% | 0.54 |
| BM25, ilk 5 harf (F5) | 46% | 59% | 63% | 0.54 |
| Hibrit (RRF + dil kuralı) | 50% | 65% | 76% | 0.62 |
| Hibrit, dil kuralı kapalı | 57% | 78% | 83% | 0.70 |

## elle: en→en (n=5)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 100% | 100% | 100% | 1.00 |
| BM25, köklemesiz **★** | 80% | 100% | 100% | 0.90 |
| BM25, ilk 5 harf (F5) **★** | 60% | 100% | 100% | 0.80 |
| Hibrit (RRF + dil kuralı) **★** | 100% | 100% | 100% | 1.00 |
| Hibrit, dil kuralı kapalı **★** | 100% | 100% | 100% | 1.00 |

## elle: iki belge (n=3)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 100% | 100% | 100% | 1.00 |
| BM25, köklemesiz **★** | 67% | 100% | 100% | 0.83 |
| BM25, ilk 5 harf (F5) **★** | 67% | 67% | 100% | 0.73 |
| Hibrit (RRF + dil kuralı) **★** | 100% | 100% | 100% | 1.00 |
| Hibrit, dil kuralı kapalı **★** | 100% | 100% | 100% | 1.00 |

## elle: tr→en (n=12)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 75% | 92% | 100% | 0.84 |
| BM25, köklemesiz | 0% | 0% | 0% | 0.00 |
| BM25, ilk 5 harf (F5) | 8% | 8% | 17% | 0.12 |
| Hibrit (RRF + dil kuralı) | 0% | 33% | 58% | 0.26 |
| Hibrit, dil kuralı kapalı | 8% | 67% | 83% | 0.40 |

## elle: tr→tr (n=15)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 93% | 100% | 100% | 0.97 |
| BM25, köklemesiz **★** | 93% | 100% | 100% | 0.97 |
| BM25, ilk 5 harf (F5) **★** | 80% | 100% | 100% | 0.89 |
| Hibrit (RRF + dil kuralı) **★** | 100% | 100% | 100% | 1.00 |
| Hibrit, dil kuralı kapalı **★** | 100% | 100% | 100% | 1.00 |

## üretim: tr→en (n=45)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 64% | 93% | 98% | 0.78 |
| BM25, köklemesiz | 9% | 18% | 24% | 0.15 |
| BM25, ilk 5 harf (F5) | 7% | 16% | 24% | 0.15 |
| Hibrit (RRF + dil kuralı) | 2% | 20% | 47% | 0.22 |
| Hibrit, dil kuralı kapalı | 24% | 53% | 62% | 0.44 |

## üretim: tr→tr (n=65)

| Yöntem | İsabet@1 | İsabet@3 | İsabet@5 | MRR@10 |
|---|---|---|---|---|
| Yalnızca vektör (dense) **★** | 80% | 98% | 98% | 0.88 |
| BM25, köklemesiz | 72% | 82% | 86% | 0.78 |
| BM25, ilk 5 harf (F5) | 71% | 85% | 86% | 0.77 |
| Hibrit (RRF + dil kuralı) | 74% | 89% | 91% | 0.83 |
| Hibrit, dil kuralı kapalı | 74% | 89% | 92% | 0.83 |

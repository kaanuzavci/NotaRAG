# Uzman zorluk adımları ↔ sistemin zorluk sinyalleri (3 Adım Soru Bankası)

MEB 3 Adım Soru Bankası'nda (TYT) her konunun soruları uzmanlarca üç adımda zorlaşır. Aynı sinyaller (eval/turkishmmlu_zorluk.py) bu uzman sıralamasına karşı: ρ = adım (1, 2, 3) ile Spearman sıra korelasyonu. Zorluğu izleyen bir sinyalde beklenen: p için −, çaba ve LLM etiketi için +.

Soru çıkarma: Tarih: 618 soru (16 görselli atlandı, 0 ayrıştırılamadı); Coğrafya: 368 soru (307 görselli atlandı, 17 ayrıştırılamadı); Felsefe: 597 soru (77 görselli atlandı, 2 ayrıştırılamadı); Biyoloji: 0 soru (0 görselli atlandı, 0 ayrıştırılamadı)

## Sinyaller (90 soru)

| Sinyal | ρ (adımla) | %95 aralık | Beklenen |
|---|---|---|---|
| Benzetilmiş öğrenci p | +0.07 | -0.14 … +0.29 | − |
| Çaba (düşünme token'ı) | -0.06 | -0.24 … +0.15 | + |
| LLM zorluk etiketi | +0.16 | -0.05 … +0.36 | + |

| Adım | n | ort. p | ort. çaba | LLM etiketi kolay / orta / zor | sim_level: bilgi yok / orta / zor | dikkatli çözücü doğru¹ |
|---|---|---|---|---|---|---|
| 1. adım | 30 | 0.88 | 488 (medyan) | 20 / 9 / 1 | 18 / 7 / 5 | 27/30 |
| 2. adım | 30 | 0.89 | 504 (medyan) | 15 / 14 / 1 | 18 / 6 / 6 | 27/30 |
| 3. adım | 30 | 0.92 | 472 (medyan) | 14 / 15 / 1 | 19 / 5 / 6 | 30/30 |

¹ Anahtar sağlaması: dikkatli çözücü (Gemma, uzun düşünme) bir adımda belirgin biçimde düşükse o adımın anahtarı şüphelidir (ilk çalıştırmada 1. adımın anahtarı başka konudandı: 1. adımda 17/30, 2. adımda 30/30).

Ders bazında ρ (adımla): Coğrafya çaba +0.25 · etiket +0.25, Felsefe çaba -0.11 · etiket +0.19, Tarih çaba -0.26 · etiket +0.05


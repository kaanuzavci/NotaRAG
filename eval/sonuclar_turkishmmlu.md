# Zorluk sinyalleri ↔ gerçek öğrenci (TurkishMMLU)

Veri: TurkishMMLU (Yüksel ve ark. 2024) alt kümesi, 900 lise sorusu (9 ders × 100, 5 şık); her sorunun çevrim içi platformdaki **öğrenci doğru oranı** ve ondan türetilen etiketi (kolay ≥ %42, orta %28-41, zor ≤ %27). ρ = öğrenci doğru oranıyla Spearman sıra korelasyonu: **+** sinyal yükseldikçe öğrenci daha çok bildi, **−** daha az. Zorluğu izleyen bir sinyalde beklenen: model doğru oranı p için +, çaba ve zorluk etiketi için −. |ρ| < 0,1 ≈ ilişki yok; 0,3 civarı orta; 0,5+ güçlü.

## 1. Metin özellikleri (kota yok, 900 soru)

| Özellik | ρ | Ortalama (kolay / orta / zor) |
|---|---|---|
| uzunluk | -0.12 | 241.9 / 312.4 / 301.8 |
| öncül sayısı | +0.00 | 0.7 / 0.7 / 0.8 |
| olumsuz kök | +0.05 | 0.0 / 0.0 / 0.0 |
| formül/sayı | -0.33 | 0.1 / 0.3 / 0.5 |
| şık uzunluğu | +0.10 | 21.9 / 27.8 / 20.9 |
| çeldirici benzerliği | -0.15 | 58.7 / 61.6 / 66.4 |

Uzunluğun ders içi ρ'su (ders karışımının etkisi olmadan): Biology -0.44, Chemistry -0.52, Geography +0.05, History -0.26, Mathematics -0.19, Philosophy -0.15, Physics -0.29, Religion and Ethics -0.24, Turkish Language and Literature -0.12

## 2-4. Gemma ölçümleri (0 / 180 soru ölçüldü)

Henüz yeterli ölçüm yok.


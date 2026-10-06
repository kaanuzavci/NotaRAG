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

## 2-4. Gemma ölçümleri (180 / 180 soru ölçüldü)

| Sinyal | ρ (öğrenci doğru oranıyla) | %95 aralık | Beklenen işaret |
|---|---|---|---|
| Benzetilmiş öğrenci p (kapalı kitap, düşünmeden, 4 örneklem) | +0.29 | +0.16 … +0.43 | + |
| Dikkatli çözüm doğru mu (0/1) | +0.22 | +0.12 … +0.32 | + |
| Çaba (dikkatli çözümün düşünme token'ı) | -0.42 | -0.54 … -0.30 | − |
| LLM zorluk etiketi (kolay 0 · orta 1 · zor 2) | -0.36 | -0.48 … -0.23 | − |
| Birleşik: etiket + çaba (sıra toplamı) | -0.46 | -0.57 … -0.35 | − |

Aralık sıfırı kesiyorsa ilişki bu örneklemde kanıtlanmış sayılmaz.

Tavan (4 örneklemin 4'ü doğru): 114/180 · dikkatli çözüm doğru: 162/180 · ortalama p: 0.79

| Gerçek düzey (öğrenci) | n | ort. p | tavan oranı | ort. çaba | LLM etiketi kolay / orta / zor |
|---|---|---|---|---|---|
| kolay | 60 | 0.87 | %77 | 518 | 46 / 13 / 1 |
| orta | 64 | 0.82 | %64 | 785 | 35 / 26 / 3 |
| zor | 56 | 0.66 | %48 | 1947 | 20 / 25 / 11 |

Sistemin benzetim kuralı (difficulty.sim_level: yanılma ya da ÇS'de çaba ≥ 600 / 1200 → alt sınır; ikisi de yoksa bilgi yok) → gerçek düzey dağılımı. Not: çaba eşikleri bu veriden seçildi; aynı veride gösterilen isabet iyimserdir.

| Benzetim sonucu | n | gerçek kolay / orta / zor | ort. öğrenci doğru oranı |
|---|---|---|---|
| tavan | 85 | 42 / 31 / 12 | %40 |
| orta | 45 | 11 / 19 / 15 | %33 |
| zor | 50 | 7 / 14 / 29 | %29 |

LLM etiketinin gerçek düzeyi tutturma oranı: 83/180 (şans ≈ 1/3).

Ders bazında benzetim p'si ↔ öğrenci: Biology -0.01 (ort. p 0.78), Chemistry +0.59 (ort. p 0.75), Geography +0.37 (ort. p 0.85), History +0.42 (ort. p 0.89), Mathematics -0.01 (ort. p 0.60), Philosophy +0.36 (ort. p 0.99), Physics +0.33 (ort. p 0.76), Religion and Ethics +0.30 (ort. p 0.80), Turkish Language and Literature +0.46 (ort. p 0.68)


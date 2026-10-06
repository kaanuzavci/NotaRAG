# Zorluk ölçümü pilotu

Etkin düzey = ölçüm (sözel ÇS ve D/Y'de benzetilmiş öğrenci: Gemma 4 sınıfı, kaynak açık, çalışma yazmadan; p = doğru oranı; hepsi doğruysa tavan, bilgi yok; çaba = dikkatli çözümün düşünme token'ı, yalnızca kayıt) ya da üretecin iddiası; ikisine de yapı tavanı (src/difficulty.py): **zor için en az iki ayrı bilgi/kural ya da çok adımlı hesap**. Hesap ve sözel kısa cevap benzetilmez (Gemma 4 lise matematiğinde doyuyor; kısa cevap metin eşleşmesiyle puanlanıyor, PROMPTS §8). "Bilgi" = notta bulunan ayrı kanıt alıntısı.

## A · TYT 'zor' isteği (hesap) (10 soru)

Elle sütunu: Claude'un değerlendirmesi, öğrenci verisi değil.

| Soru | İstenen | Üretecin iddiası | Bilgi / adım / işlem | p / çaba | Etkin düzey | Elle |
|---|---|---|---|---|---|---|
| İki basamaklı AB ve BA doğal sayıları için AB - BA = 54 eşitliği… | – | orta | 1 / 3 / – | – | **orta**  | orta |
| 1,27 (7 devirli) devirli ondalık sayısının rasyonel sayı değeri … | – | orta | 1 / 4 / 1 | – | **kolay** (tavan: tek formül / tek işlem) | kolay |
| x² - y² = 40 ve x - y = 4 olduğuna göre, x · y çarpımı kaçtır? | – | orta | 1 / 4 / – | – | **orta**  | orta |
| İki pozitif sayının aritmetik ortalaması 10, geometrik ortalamas… | – | zor | 1 / 4 / 3 | – | **zor**  | orta |
| Tuz oranı %20 olan 40 gram tuzlu su ile tuz oranı %30 olan 60 gr… | – | orta | 1 / 4 / – | – | **orta**  | kolay |
| 4, 6, 8, 8, 10, 12, 16 veri grubunun medyanı, modu ve açıklığını… | – | orta | 1 / 4 / 2 | – | **orta**  | kolay |
| x² - 6x + 4 = 0 denkleminin kökleri x₁ ve x₂ olduğuna göre, x₁² … | – | orta | 1 / 4 / 3 | – | **orta**  | orta |
| f(x) = 2x² - 12x + 11 parabolünün tepe noktasının koordinatları … | – | orta | 1 / 3 / 1 | – | **kolay** (tavan: tek formül / tek işlem) | kolay |
| P(x) = (2x² - x - 2)⁵ polinomunun tek dereceli katsayılar toplam… | – | orta | 1 / 4 / 13 | – | **orta**  | orta |
| (x² - 2/x)⁶ açılımındaki sabit terim kaçtır? | – | zor | 1 / 3 / 4 | – | **zor**  | zor |

## C · Sözel havuz örneklemi (12 soru)

| Soru | İstenen | Üretecin iddiası | Bilgi / adım / işlem | p / çaba | Etkin düzey | Elle |
|---|---|---|---|---|---|---|
| Organik tarımda çiftçilerin tutarsız getirilerle karşılaşmasının… | – | zor | 1 / 0 / – | 1.00 / 365 | **orta** (tavan: tek bilgi ya da kurala dayanıyor: zor için en az iki ayrı bilgi ya da çok adımlı hesap gerekir) | – |
| Tarım ilaçlarının keşfedilip kullanılmaya başlanmasından sonra, … | – | orta | 1 / 0 / – | 1.00 / 252 | **orta**  | – |
| Giriş/çıkış performansını iyileştirmek için kullanılan DMA (Dire… | – | kolay | 1 / 0 / – | 1.00 / 393 | **kolay**  | – |
| Tarım ekosistemlerinde bazı zararlı böceklerin doğal ekosistemle… | – | zor | 1 / 0 / – | 1.00 / 475 | **orta** (tavan: tek bilgi ya da kurala dayanıyor: zor için en az iki ayrı bilgi ya da çok adımlı hesap gerekir) | – |
| Endüstriyel tarım ürünleriyle karşılaştırıldığında, organik tarı… | – | orta | 1 / 0 / – | 1.00 / 428 | **orta**  | – |
| Genetik algoritmalarda kromozom kodlama mekanizmaları temel olar… | – | kolay | 1 / 0 / – | 1.00 / 253 | **kolay**  | – |
| Ekolojik açıdan ele alındığında, tarım alanlarında ortaya çıkan … | – | orta | 1 / 0 / – | 1.00 / 538 | **orta**  | – |
| Bir sistemin tek bir görüntüyü 2 saniyede işlemesi ile dakikada … | – | kolay | 1 / 0 / – | 1.00 / 458 | **kolay**  | – |
| Aşağıdakilerden hangisi kromozom kodlama mekanizmalarından biri … | – | orta | 1 / 0 / – | 1.00 / 373 | **orta**  | – |
| Sistem performansını etkileyen faktörler arasında, işlem kaynakl… | – | kolay | 1 / 0 / – | 1.00 / 441 | **kolay**  | – |
| Organik tarım yapan üreticilerin, sentetik gübre ve pestisit kul… | – | orta | 1 / 0 / – | 1.00 / 545 | **orta**  | – |
| Yapılan araştırmalara göre, organik tarım yapılan alanlar endüst… | – | kolay | 1 / 0 / – | 1.00 / 221 | **kolay**  | – |

_D1, D2, E (üretim gerektiren gruplar) bu çalıştırmada yok: `--uretimsiz`._

A'da elle değerlendirmeyle uyum: etkin düzey 7/10, üretecin iddiası 5/10, eski zorla yazılmış etiket ('zor') 1/10.


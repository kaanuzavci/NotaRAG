# Kaynak desteğinin cevap doğruluğuna etkisi

Aynı soru Gemma 4 26B-A4B'ye (düşünmeden, sıcaklık 0) üç koşulda soruldu: **kaynaksız** (PROMPTS §6), **doğru kaynakla** ve **yanlış kaynakla** (başka bir sorunun kaynağı; §6c). Belebele-TR: insan yazımı okuduğunu anlama soruları (300). Havuz: sistemin doğrulanmış çoktan seçmeli soruları; kaynak = sorunun üretildiği not sayfaları. Doğruluğun yanında %95 Wilson aralığı. Her ölçümün üç koşulu da aynı modelle (meşgulse beklenir, başka modele geçilmez). Hesap soruları da düşünmeden ve 60 token sınırıyla cevaplandı: model hesabı yazamaz, bu satır kaynağın hesapsız cevaba etkisini gösterir (notta hazır sonuç yoksa kaynak az yardım eder).

| Veri | n | Kaynaksız | Doğru kaynakla | Yanlış kaynakla | Kaynağa muhtaç¹ | Yanlış kaynağın zararı² | Eşli test p³ (doğru / yanlış kaynak) |
|---|---|---|---|---|---|---|---|
| Belebele-TR · okuma | 300 | %56 (50–61) | %90 (86–93) | %46 (41–52) | %38 | %18 | 1,7e-23 (+114 −10) / 0,0026 (−55 +27) |
| Havuz · hesap | 38 | %55 (40–70) | %68 (53–81) | %58 (42–72) | %26 | %16 | 0,3 (+10 −5) / 1 (−6 +7) |
| Havuz · sözel | 129 | %92 (86–96) | %99 (96–100) | %92 (86–96) | %8 | %3 | 0,012 (+10 −1) / 1 (−4 +4) |

¹ Doğru kaynakla doğru, kaynaksız yanlış cevaplanan soruların oranı: cevabı gerçekten kaynağa bağlı sorular. Havuzda düşükse sorular genel bilgiyle cevaplanabiliyor (ders notuna özgü değil).
² Kaynaksız doğru cevaplanıp yanlış kaynakla yanlışa dönen soruların oranı: arama yanlış sayfa getirirse doğruluk ne kadar düşer.
³ Kesin McNemar testi (aynı sorunun iki koşuldaki cevabı eşli): kaynaksıza göre kaç soru doğruya (+) ve yanlışa (−) döndü; p < 0,05 ise fark şansla açıklanamaz.

## Havuz: belgeye ve etkin zorluğa göre

| Grup | n | Kaynaksız | Doğru kaynakla | Kaynağa muhtaç |
|---|---|---|---|---|
| belge: 4_ENERJİ, TARIM, BESLENME | 8 | %88 | %100 | %12 |
| belge: 7.Hafta Sunu Dosyası | 9 | %78 | %89 | %11 |
| belge: Hafta_01_Bilgisayar_Mimarisi_ve_Organizasyonuna_Giris | 19 | %89 | %95 | %11 |
| belge: Hafta_02_Bilgisayar_Performansina_Giris | 37 | %95 | %100 | %5 |
| belge: english | 34 | %76 | %94 | %18 |
| belge: tyt-matematik | 60 | %80 | %85 | %13 |
| zorluk: easy | 90 | %84 | %94 | %11 |
| zorluk: hard | 1 | %100 | %100 | %0 |
| zorluk: medium | 76 | %83 | %89 | %13 |


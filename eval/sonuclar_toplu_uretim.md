# Toplu Üretim Kalite Karşılaştırması

Aynı 12 birim (EN slayt → Türkçe soru), aynı kontroller, aynı doğrulayıcı (gpt-oss-120b).

| Yöntem | İstek | Token | Soru | Verified | Verified oranı | Dayanaksız | Kod red | Uyarılar |
|---|---|---|---|---|---|---|---|---|
| qwen, birim başına istek (taban) | 12 | 32,400 | 12 | 11 | 92% | 0 | {'context_reference': 1} | {'vision_evidence': 5, 'length_cue': 1} |
| gemini-2.5-flash, TEK istek | 0 | 0 | 12 | 11 | 92% | 1 | - | {'vision_evidence': 3, 'length_cue': 1} |
| gemini-3.5-flash, TEK istek | 0 | 0 | 12 | 11 | 92% | 1 | - | {'vision_evidence': 4} |
| gemini-3.8-flash, TEK istek | 0 | 0 | 11 | 11 | 100% | 0 | - | {'vision_evidence': 2} |

Tipler / bloom (doğrulananlar): qwen, birim başına istek (taban): {'multiple_choice': 9, 'short_answer': 2, 'true_false': 1} / {'remember': 7, 'understand': 3, 'apply': 1}; gemini-2.5-flash, TEK istek: {'multiple_choice': 6, 'true_false': 3, 'short_answer': 3} / {'remember': 9, 'understand': 2}; gemini-3.5-flash, TEK istek: {'multiple_choice': 6, 'true_false': 3, 'short_answer': 3} / {'understand': 8, 'remember': 3}; gemini-3.8-flash, TEK istek: {'true_false': 3, 'short_answer': 3, 'multiple_choice': 5} / {'remember': 6, 'understand': 5}

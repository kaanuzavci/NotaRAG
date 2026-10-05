# Sadakat ↔ Bilişsel Düzey Deneyi

Aynı 17 üretim birimi; üretici gemini-2.5-flash (toplu, yedeksiz), doğrulayıcı gpt-oss-120b (hafif mod).

**Dayanaksız** = kanıtı metinde bulunamayan + kod kontrolünü geçip doğrulayıcının onaylamadığı sorular.

| Koşul | Soru | Soru üretmeyen birim | Verified | Needs review | Rejected | Dayanaksız oranı |
|---|---|---|---|---|---|---|
| remember | 32 | 0 | 30 | 0 | 2 | 0% |
| apply | 29 | 3 | 29 | 0 | 0 | 0% |

Kod red nedenleri: remember: {'near_duplicate_options': 2}; apply: {}

Modelin kendi bloom etiketi: remember: {'remember': 32}; apply: {'apply': 29}

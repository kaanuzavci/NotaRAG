# Hesap sorusu kod kontrolü — duyarlılık (tyt-matematik_tr.jsonl)

Kontrolden geçmiş 20 çoktan seçmeli hesap sorusu; her birine ayrı ayrı kasıtlı hata eklendi.

| Bozulma | Yakalanan | Beklenen red nedeni |
|---|---|---|
| wrong_key | 20/20 | `compute_mismatch` |
| two_correct | 20/20 | `compute_two_correct` |
| text_mismatch | 19/20 | `compute_text_mismatch` |

Bozulmamış sorularda yanlış alarm: **0/20**

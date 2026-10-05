# 6. Doğrulama ve kalite kapısı

[← 5. Soru üretimi](05-uretim.md) · [Ana sayfa](README.md) · Sonraki: [7. Sınav isteği →](07-sinav-istegi.md)

Projenin farkı bu katmanda. Üretilen her soru iki kontrolden geçer:
1. **Kod kontrolü** ([`checks.py`](../src/verification/checks.py)): ücretsiz, deterministik, LLM'siz. Reddedilen soru LLM'e hiç gitmez.
2. **Kör doğrulama** ([`verify.py`](../src/verification/verify.py)): soruyu üreten modelden **farklı aileden** bir model, cevap anahtarını görmeden soruyu çözer.

Kalan üç dosya doğrulayıcının kendisini sınar:
- [`sensitivity.py`](../src/verification/sensitivity.py): kasıtlı bozulmuş soruları yakalıyor mu?
- [`qualify.py`](../src/qualify.py): yeni bir model onaylanabilir mi?
- [`verification/__main__.py`](../src/verification/__main__.py): pilot setlerini doğrulama aracı.

---

## `src/verification/checks.py` — kod kontrolleri (188 satır)

**Ne işe yarar?** Bir soruyu, üretildiği parçalarla birlikte denetler ve `{status, rejected, flags, evidence_match, evidence_page, computed?}` döndürür.
- `rejected` listesi boş değilse soru reddedilir.
- `flags` yalnızca uyarıdır; arayüzde gösterilir.

**Bağlantılar**
- ← `generate._postprocess`, `pipeline.merge_existing`, `request.run` (`mark_duplicates`), `requote`, eval, `tests/test_checks`.
- → `schema.Question`, `textnorm.normalize_for_match`, `rapidfuzz`, `compute` (hesap sorularında).

**Eşikler:**
- `NEAR_VERBATIM = 90`: kanıt "neredeyse birebir" sayılmak için benzerlik.
- `LENGTH_CUE = 1.5`: doğru şık çeldiricilerin ortalamasından 1,5 kat uzunsa ipucu.
- `VERBATIM_CUE = 0.8`: doğru şıkkın kelimelerinin %80'i bir bağlam cümlesinden geliyorsa ipucu.
- `DUPLICATE = 85`: iki soru metni bu kadar benzerse tekrar.

**Düzenli ifadeler**
- [`_CONTEXT_REF`](../src/verification/checks.py#L23): "metinde", "yukarıda bahsedilen", "verilen örnekte", "bu stratejinin" gibi **metne atıflar**. Öğrenci metni görmeyecek; böyle bir soru anlamsız olur.
- [`_DEMONSTRATIVE_START`](../src/verification/checks.py#L34): "Bu yöntem…", "Söz konusu algoritma…" ile başlayan sorular. "Bu nedenle", "bu yüzden" hariç.
- [`_ABSOLUTE`](../src/verification/checks.py#L31): "yalnızca, her zaman, asla, only, always…". Kesin ifadeli çeldiriciler doğru şıkkı ele verir.

**Yardımcılar**
- [`_tokens(s)`](../src/verification/checks.py#L39): normalize edilmiş, 3+ harfli kelimeler kümesi.
- [`_overlap_with_context(option, sentences)`](../src/verification/checks.py#L43): şıkkın kelimelerinin en çok örtüştüğü bağlam cümlesindeki oran.
- [`_option_support(option, answer)`](../src/verification/checks.py#L50): şıkkın kelimelerinin `answer` metninde geçme oranı.
- [`locate_evidence(quote, chunks)`](../src/verification/checks.py#L64): **kaynak göstermenin kalbi.** Normalize edilmiş alıntı bir parçanın normalize metninde aynen geçiyorsa `("exact", parça)` döner. Geçmiyorsa en benzer parçaya bakılır; benzerlik ≥90 ise `("near", parça)`, değilse `(None, None)`. Bulunan parçanın sayfası sorunun `evidence_page`'i olur.

**[`check(q, chunks)`](../src/verification/checks.py#L106) neleri denetler?**

| Kod | Tür | Ne zaman |
|---|---|---|
| `context_reference` | Red | Soru metne atıf yapıyor ya da "Bu yöntem…" diye başlıyor |
| `tf_not_statement` | Uyarı | D/Y bir ifade değil, soru biçiminde (`?` ile bitiyor) |
| `evidence_not_found` | **Red** | Kanıt alıntısı verilen parçalarda yok: model uydurmuş |
| `near_verbatim` | Uyarı | Alıntı birebir değil, çok yakın |
| `vision_evidence` | Uyarı | Kanıt, görsel modelin yazdığı metinden geliyor (slaytın kendi metni değil) |
| `answer_option_mismatch` | Red | `answer` metni anahtardan çok **başka** bir şıkkı anlatıyor |
| `near_duplicate_options` | Red | Bir şıkkın kelimeleri diğerininkinin **öz alt kümesi** ("Üç" ⊂ "Başka bir deyişle: Üç") |
| `absolute_distractors` | Uyarı | Çeldiricilerin en az ikisi kesin ifadeli, doğru şık değil |
| `length_cue` | Uyarı | Doğru şık belirgin uzun |
| `verbatim_cue` | Uyarı | Doğru şık metindeki cümlenin aynısı, çeldiriciler değil |
| `all_none_option` | Red | "Hepsi / hiçbiri / A ve B" şıkkı (soru yazım hatası) |
| `negative_stem` | Uyarı | "…değildir" kökü vurgulanmamış |
| `clang_cue` | Uyarı | Doğru şık kökteki bir kelimeyi tekrar ediyor, çeldiriciler etmiyor |
| `compute_*` | Red / Uyarı | Hesap sorularında SymPy sonucu (bölüm 5) |

Son üç yazım kuralı [`iwf_checks(q)`](../src/verification/checks.py#L87) içindedir (Item-Writing Flaws; SAQUET'in 19 kuralından kodla güvenilir yakalanabilenler).

**Neden bazı kurallar böyle ince ayarlı?** Yorumlarda her biri için bir "yanlış alarm" hikâyesi var:
- **"Öz alt küme" kuralı:** "0.25'ten büyük" ile "0.75'ten büyük" %97 benzer çıkıyordu ama anlamları farklı; metin benzerlik oranı bu yüzden kullanılmaz. Aynı kelimelerin farklı sırası (sıra soran sorular) da tekrar sayılmaz.
- **Cevap–şık tutarlılığı:** `answer_index` belirleyicidir. Gemini `answer` alanına açıklamalı cümle yazıyordu ve bir deneyde 12 geçerli soru bu yüzden boşuna reddedilmişti.

**[`mark_duplicates(items, keep)`](../src/verification/checks.py#L176):** aynı partide neredeyse aynı soru metinleri varsa (token kümesi benzerliği ≥85) ilkini tutar, sonrakileri `duplicate` diye reddeder. `keep` verilirse zaten havuzda olan soruların tekrarı da reddedilir. Böylece tekrarlar doğrulamaya gidip kota harcamaz.

Testler: [`tests/test_checks.py`](../tests/test_checks.py).

---

## `src/verification/verify.py` — kör doğrulama (205 satır)

**Ne işe yarar?** Kod kontrolünden geçen soruyu, üreticiden farklı aileden onaylı bir modele **cevap anahtarını göstermeden** çözdürür ve üç etiketten birini verir: `verified`, `needs_review`, `rejected` (+ gerekçe).

**Bağlantılar**
- ← `pipeline.run`, `request.run`, `qualify`, `sensitivity`, `verification/__main__`, eval betikleri.
- → `router.call`, `prompts.load_prompt` (§4a-4e, §6, §6b), `models.ROLES`, `textnorm`, `rapidfuzz`, `compute.numbers_in`.

**Aile kuralı**
- [`family(model)`](../src/verification/verify.py#L40): model adından aile adını çıkarır: `'openai/gpt-oss-120b'` → `'gpt-oss'`, `'qwen/qwen3.8-27b'` → `'qwen'`, `'gemini-3.8-flash'` → `'gemini'`.
  - Sağlayıcı öneki (`openrouter/`, `cerebras/`) atılır; aynı model farklı sağlayıcıda aynı aile sayılır.
  - [`_FAMILY_ALIASES`](../src/verification/verify.py#L36): aynı şirketin farklı adlı modelleri aynı aileye bağlanır: `gemma` → `gemini` (ikisi de Google), `magistral` / `codestral` / … → `mistral`.
  - Neden? Ad önekine bakan kural Gemma'yı ayrı aile sanıp Gemini'nin sorusunu ona doğrulatırdı; aile kuralı sessizce çiğnenirdi.
- [`verifier_role(generator, allow_candidates, task)`](../src/verification/verify.py#L47): onaylı doğrulayıcılardan **üreticiyle aynı aileden olmayanları** süzüp `_verify_not_gemini` gibi geçici bir rol kurar. Böyle bir model yoksa hata verir; kalite kapısı gereği onaysız modele düşmez.
  - Neden? Bir model kendi yazdığı hatayı görmekte zorlanır.

**Yardımcılar**
- [`_json(text)`](../src/verification/verify.py#L70): doğrulayıcının yanıtını sözlüğe çevirir. JSON bozuksa önce `{...}` bloğunu arar, sonra `"A": "correct"` gibi alanları tek tek çıkarır. Hiçbiri yoksa `{}` döner; karar temkinli tarafta (`needs_review`) kalır.
- [`_fill(section, **kw)`](../src/verification/verify.py#L92): istemi yükleyip yer tutucuları doldurur.
- [`_option_label(verdict, key)`](../src/verification/verify.py#L99): şık bazlı kararlar → etiket.
  - **Yalnızca** anahtar şık "correct" ise `verified`.
  - Anahtarla birlikte başka şık da doğruysa, hiçbiri doğru değilse ya da başka bir şık doğruysa `needs_review`.

**Tipe özel doğrulayıcılar**
- [`verify_mcq(q, context, role, light)`](../src/verification/verify.py#L112) (§4a): doğrulayıcı her şıkkı ayrı ayrı "correct / incorrect / unknown" diye değerlendirir.
  - İlk sürümde "tek şık seç" isteniyordu ve iki doğru şıkkın yalnızca 5/7'si yakalanıyordu; şık başına değerlendirmeyle 6/6 oldu.
  - `light=False` ise iki bilgi testi daha yapılır (ret nedeni değil):
    - §6, bağlamsız: `closed_book_correct`.
    - §6b, yalnızca şıklar: `choices_cue`.

    Üretim akışı `light=True` kullanır; bu testler kota yer.
- [`verify_tf(q, context, role)`](../src/verification/verify.py#L160) (§4b): üç sınıflı karar.
  - Cevap "doğru" ise metnin ifadeyi **desteklemesi** (SUPPORTED), "yanlış" ise **çürütmesi** (CONTRADICTED) gerekir.
  - NOT_IN_CONTEXT → `rejected`: metinde geçmeyen bir ifade "yanlış" sayılamaz.
- [`verify_short(q, context, role)`](../src/verification/verify.py#L174) (§4c → §4d): doğrulayıcı cevabı **kendisi yazar**.
  - Kodla eşleşirse (normalize eşit ya da benzerlik ≥90) `verified`.
  - Eşleşmezse aynı rol hakem olarak sorulur (§4d): "iki cevap eşdeğer mi?"
  - Doğrulayıcı `INSUFFICIENT_CONTEXT` derse `needs_review`.
- [`verify_computed(q, computed, context, role)`](../src/verification/verify.py#L130) (§4e): hesap sorusunu doğrulayıcı **yalnızca metinden** çözer; SymPy ifadesi, çözüm ve anahtar gösterilmez.
  - Çoktan seçmelide şık kararlarıyla, kısa cevapta sonuçtaki sayıyla kodun değeri karşılaştırılır; olmazsa hakeme sorulur.
  - Neden gerekli? Kod yalnızca **modelin kendi ifadesini** doğrular. Sorunun metninin gerçekten o ifadeyi sorduğunu (ör. metin kombinasyon sorarken ifade permütasyon hesaplıyor mu?) ancak kör çözüm gösterir.

**Giriş noktası: [`verify_item(item, chunks_by_id, light, allow_candidates)`](../src/verification/verify.py#L191)**
1. Kod kontrolü reddettiyse dokunmaz; `rejected` + nedenleri döndürür. `CHECK_TR` hesap nedenlerini Türkçeleştirir.
2. Bağlamı, sorunun `chunk_ids` parçalarından yeniden kurar: üreticinin gördüğü metnin aynısı.
3. Hesap sorusuysa `verify_math` rolüyle `verify_computed`; değilse `verify` rolüyle tipe göre `verify_mcq` / `verify_tf` / `verify_short`.

**Bu katmanın ölçümü:** doğrulayıcı duyarlılık testi (`sensitivity.py`). Örneğin gpt-oss-120b kasıtlı hataların 17/17'sini yakaladı.

---

## `src/verification/sensitivity.py` — doğrulayıcı duyarlılık testi (124 satır)

**Ne işe yarar?** "Doğrulanan soruların hepsi geçti" sonucu, doğrulayıcı her şeye "doğru" diyorsa anlamsızdır. Bu betik doğrulanmış sorulardan **cevabı bilinen bozuk kopyalar** üretir ve doğrulayıcının onları yakalayıp yakalamadığını sayar.

**Bağlantılar**
- ← `qualify` (`NOT_IN_CONTEXT`, `corruptions`).
- → `verify` (`verify_item`, `verifier_role`, `_fill`, `_json`), `router.call`.
- 💾 Yazar: `eval/sonuclar_duyarlilik.json` (Rapor sayfası okur).

**İçindekiler**
- [`NOT_IN_CONTEXT`](../src/verification/sensitivity.py#L29): gerçekte doğru ama slaytta **olmayan** üç ifade ("GA'yı John Holland önerdi"). Doğrulayıcı dış bilgisiyle "doğru" derse hatalıdır; beklenen karar `rejected`.
- [`corruptions(item)`](../src/verification/sensitivity.py#L36): bir sorudan bozuk kopyalar üretir:
  - `wrong_key`: anahtar başka şıkka kaydırılır.
  - `two_correct`: bir çeldirici "Başka bir deyişle: <doğru şık>" yapılır.
  - `tf_flip`: D/Y ters çevrilir.
  - `short_wrong`: kısa cevap yanlış bir değerle değiştirilir.

  Hepsinde beklenen karar "verified olmamalı".
- [`choices_only(item)`](../src/verification/sensitivity.py#L59): soru gizlenip yalnızca şıklar gösterilince doğru şık bulunuyor mu (§6b)? Bulunuyorsa çeldiriciler zayıftır.
- [`main()`](../src/verification/sensitivity.py#L69): bir `_dogrulama.jsonl` dosyası alır.
  - İkinci argüman bir model adıysa **yalnızca o model** sınanır (`LIGHT=True`: yalnızca karar veren doğrulama).
  - Sonuç tür bazında "yakalanan / toplam" olarak basılır ve JSON'a yazılır.

---

## `src/verification/__main__.py` — `python -m src.verification <dosya>` (54 satır)

**Ne işe yarar?** Pilot sorularını (`data/pilot/<model>.jsonl`) kör doğrulamadan geçirir. `<dosya>_dogrulama.jsonl` ve okunur bir `data/pilot/dogrulama.md` yazar. Model karşılaştırması için `allow_candidates=True` kullanır, yani aday modeller de doğrulayıcı olabilir.

- [`main()`](../src/verification/__main__.py#L18): her soru için `verify_item` çağırır. Etiket dağılımını ve **"dokümansız da doğru bilinen çoktan seçmeli"** sayısını (§6) basar.
  - Pilotta bu sayı 11'de 9 çıkmıştı: genel konularda model dünya bilgisiyle cevabı biliyor. Bu tek başına zayıf bir sinyal.

---

## `src/qualify.py` — aday model yeterlilik testi (164 satır)

**Ne işe yarar?** `python -m src.qualify <model> [--kisa]` komutu aday bir modeli doğrulayıcı olarak onaylamadan önce tek seferde sınar. Sonuç `eval/yeterlilik/<model>.json` + `.md` dosyalarına ve bir onay önerisine dönüşür. **Onayı insan verir**: `models.py`'deki `APPROVED`'a kanıtıyla eklenir.

**Bağlantılar**
- → `verify` (`family`, `verify_item`), `sensitivity` (`NOT_IN_CONTEXT`, `corruptions`), `review_store.load_chunks`, `models`, `router.has_key`.
- 💾 Okur: `data/pilot/*_dogrulama.jsonl` (metin soruları), `data/questions/tyt-matematik_tr.jsonl` ve `istek_tr.jsonl` (hesap soruları).

**İçindekiler**
- `PASS`: geçme eşikleri.
  - Kasıtlı hataların ≥%95'i yakalanmalı.
  - Sağlam soruların ≥%80'i doğrulanmalı.
  - Hesapta ≥%90 aynı sonuç, ≥%95 kaydırılmış anahtar yakalanmalı.
- [`_text_items(model)`](../src/qualify.py#L37): doğrulanmış GA soruları. **Üreticisi adayla aynı aileden olmayan** set seçilir (aile kuralı test sırasında da geçerli).
- [`_math_items(model)`](../src/qualify.py#L46): SymPy'nin doğruladığı TYT hesap soruları + istek setindeki zor hesap soruları. Aday Gemini ise boş döner (üretici Gemini).
- [`run(model, short)`](../src/qualify.py#L59): `verify` ve `verify_math` rollerini **yalnızca adaya** ayarlar, sonra:
  1. Metin: sağlam sorular doğrulanıyor mu, bozuk kopyalar yakalanıyor mu, metinde olmayan ifadeler reddediliyor mu?
  2. Hesap: kodla aynı sonucu buluyor mu, anahtarı kaydırılmış soruyu fark ediyor mu?
  3. Eşiklere göre `recommend`: hangi rol için onaylanabilir?
- [`report(res)`](../src/qualify.py#L127): Markdown tablosu + kaçırılanlar listesi.
- [`main()`](../src/qualify.py#L145): anahtar yoksa hangi satırın `.env`'e ekleneceğini söyler. Günlük istek sınırı ≤50 olan modelde kısa mod kendiliğinden açılır (~30 çağrı).

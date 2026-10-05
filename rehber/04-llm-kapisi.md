# 4. LLM kapısı: model, kota, önbellek

[← 3. Bölümleme ve arama](03-bolumleme-ve-arama.md) · [Ana sayfa](README.md) · Sonraki: [5. Soru üretimi →](05-uretim.md)

Projede bir LLM'e giden **her** istek tek bir fonksiyondan geçer: [`router.call(rol, istem)`](../src/llm/router.py#L239). Embedding tek istisnadır; `embedder.py` kendi isteğini atar. Bu katman dört dosyadan oluşur:

| Dosya | Sorusu |
|---|---|
| [`models.py`](../src/llm/models.py) | Hangi modeller var, kotaları ne, hangi işe **onaylı**? |
| [`ledger.py`](../src/llm/ledger.py) | Bugün ne kadar kullandık, bu yanıtı daha önce aldık mı? |
| [`router.py`](../src/llm/router.py) | Bu istemi hangi modele göndereyim, hata gelirse ne yapayım? |
| [`capacity.py`](../src/llm/capacity.py) | Kalan kotayla ne kadar iş yapılabilir? |

**Neden tek kapı?** Kota, önbellek, hata yönetimi ve kalite kapısı bir kez yazılır, her yerde geçerli olur. Üretim kodunun "Gemini doluysa qwen'e geç" diye düşünmesine gerek kalmaz.

---

## `src/llm/models.py` — model kayıt defteri ve kalite kapısı (123 satır)

**Ne işe yarar?** Üç şeyi tanımlar:
- Bilinen modeller ve ücretsiz kotaları.
- Her **rol** (iş) için onaylı modeller ve onayın **kanıtı**.
- Onay bekleyen adaylar.

**Bağlantılar**
- ← 13 dosya: router, ledger, capacity, verify, qualify, sensitivity, pilot, ingestion, ui sayfaları, eval, `tests/test_router`.
- Hiçbir proje modülünü içe aktarmaz.

**İçindekiler**
- [`ModelSpec`](../src/llm/models.py#L15) (dondurulmuş dataclass): bir modelin bilgileri.
  - `name`, `provider` (`gemini` / `groq` / `openrouter` / `cerebras`)
  - `rpd`: günlük istek sınırı; `rpm`: dakikalık istek sınırı
  - `tpm`: dakikalık token sınırı; `tpd`: günlük token sınırı
  - `vision`: görüntü kabul ediyor mu
  - `tz`: günlük kotanın sıfırlandığı saat dilimi
- [`MODELS`](../src/llm/models.py#L26): ad → `ModelSpec` sözlüğü. Örnekler:
  - Gemini modelleri: günde 20 istek, Pasifik gece yarısı (TR ~10:00) sıfırlanır.
  - Groq modelleri: kayan 24 saatte 200.000 token.
  - OpenRouter ücretsiz modelleri: günde 50 istek.
- [`_chain(env, default)`](../src/llm/models.py#L56): `.env`'de `ROLE_VERIFY=model1,model2` gibi bir satır varsa zinciri elle değiştirmeye izin verir.
- [`APPROVED`](../src/llm/models.py#L64): **kalite kapısı**. Rol → {model: kanıt}. Sıra önceliktir (ilk yazılan önce denenir).

  | Rol | Ne iş | Onaylı zincir |
  |---|---|---|
  | `vision` | Resim sayfa okuma | gemini-2.5-flash → gemini-3.5-flash → qwen |
  | `generate` | Birim başına üretim (yedek) | qwen |
  | `generate_batch` | Toplu üretim, konu haritası | gemini-3.8-flash → gemini-3.5-flash |
  | `verify` | Kör doğrulama | gpt-oss-120b → gpt-oss-20b → Nemotron → qwen |
  | `judge` | Kısa cevap hakemi | gpt-oss-120b (**kodda kullanılmıyor**, bkz. aşağıdaki not) |
  | `verify_math` | Hesap sorusunu kör çözme | gpt-oss-120b → gpt-oss-20b → Nemotron |

  Her kanıt bir ölçümdür, örneğin "duyarlılık testi: kasıtlı hataların 17/17'si yakalandı".
- [`CANDIDATES`](../src/llm/models.py#L100): test bekleyen ya da testi geçemeyen modeller (gerekçeleriyle). Otomatik zincire **girmezler**.
- [`ROLES`](../src/llm/models.py#L113): rol → model adı listesi. Router bunu kullanır. Çalışma anında geçici roller de eklenir:
  - `verify.verifier_role` `_verify_not_gemini` gibi roller kurar;
  - `pilot.py` `_pilot` rolünü kurar.
- [`reasoning(role)`](../src/llm/models.py#L116): gpt-oss'un gizli akıl yürütme düzeyi (`low` / `medium` / `high`). Diğer modeller bu ayarı yok sayar.
  - Varsayılan `medium`, çünkü bütün onay testleri bununla yapıldı.
  - Deney için `.env`'de `REASONING_VERIFY=low` gibi bir satırla değiştirilebilir.
  - Geçici roller ana rolün ayarını alır: `_verify_not_gemini` → `verify`.
  - Neden? Düşük düzey daha az token harcar ama kaliteyi düşürebilir. Önce ölçülmesi gerekir.

**Kalite kapısının anlamı:** Bir rolün bütün onaylı modellerinin kotası dolarsa sistem onaysız bir modele **sessizce geçmez**; iş bekler. ("Kota hızı etkiler, kaliteyi değil.") Yeni model eklemenin yolu: [`python -m src.qualify <model>`](../src/qualify.py), sonra kanıtla `APPROVED`'a eklemek.

**Not:** `"judge"` rolü tanımlı ve arayüzde listeleniyor ama hiçbir kod `call("judge", ...)` yapmıyor. Kısa cevap eşdeğerliği (§4d), o sorunun doğrulayıcı rolüyle soruluyor.

---

## `src/llm/ledger.py` — kota defteri ve yanıt önbelleği (223 satır)

**Ne işe yarar?** Yerel bir SQLite veritabanında (`data/llm.sqlite`) kim ne kadar kullandı, hangi model ne zamana kadar beklemede, hangi istemin yanıtı ne, bunları tutar. Ayrıca dakikalık hız sınırına çarpmadan önce bekleten `Throttle` sınıfı buradadır.

**Bağlantılar**
- ← router, capacity, pipeline, ingestion, ui (data, models sayfası), eval, `scripts/bekci`.
- → `models.MODELS`, `sqlite3`.

**Veritabanı tabloları** ([`_conn`](../src/llm/ledger.py#L23) her açılışta yoksa oluşturur):

| Tablo | Sütunlar | Ne için |
|---|---|---|
| `usage` | model, day, requests, tokens, exhausted | Modelin **kota günündeki** istek/token sayısı ve "bugün dolu" işareti |
| `calls` | model, ts, tokens | Her çağrının zamanı ve token'ı. Groq'un **kayan 24 saat** sınırı bununla hesaplanır |
| `cooldown` | model, until | Sağlayıcı "X dakika sonra dene" dediyse model o saate kadar kullanılmaz |
| `cache` | key, model, response, created | Yanıt önbelleği |
| `prompt_cache` | model, ts, tokens | Groq'un **istem önbelleğinden** okuduğu giriş token'ları (`calls.tokens`'ın içinde) |
| `quota_sync` | model, ts, used, ours, cached | TPD hatasında sağlayıcının bildirdiği kullanım ile bizim kaydımız yan yana |

**İstem önbelleği ölçümü nedir?** Groq, gpt-oss'a art arda birebir aynı başlangıçla (kurallar + bağlam) gelen istemlerde o kısmı kendi önbelleğinden okur. Açık soru: bu token'lar günlük 200 bin sınırından düşülüyor mu? `quota_sync`'te "sağlayıcının söylediği ≈ bizim kaydımız − önbellekli" çıkarsa düşülmüyor demektir. O zaman kendi sayacımız da onları saymamalı ve doğrulama kapasitesi artar. Ölçülene kadar ayrı tabloda tutuluyor.

Neden `calls` tablosuna yeni sütun eklenmedi? O sırada çalışan eski süreçlerin `INSERT INTO calls VALUES (?, ?, ?)` satırı üç sütun bekliyor; tabloya sütun eklemek onları bozardı.

**İçindekiler**
- [`quota_day(model)`](../src/llm/ledger.py#L42): modelin kendi saat dilimine göre bugünün tarihi. Gemini için Pasifik saati.
- [`usage(model)`](../src/llm/ledger.py#L47): (istek, token, dolu mu) — bugün için.
- [`tokens_24h(model, table)`](../src/llm/ledger.py#L54): son 24 saatteki toplam token (`calls` ya da `prompt_cache` tablosundan).
- [`cached_24h(model)`](../src/llm/ledger.py#L61): son 24 saatte istem önbelleğinden okunan token.
- [`cooldown_left(model)`](../src/llm/ledger.py#L66) / [`set_cooldown(model, s)`](../src/llm/ledger.py#L72): bekleme süresini okur / ayarlar.
- [`available(model, need_tokens)`](../src/llm/ledger.py#L77): şu an kullanılabilir mi? Dört koşula bakar:
  - dolu işareti yok,
  - bekleme süresi yok,
  - günlük istek sınırı aşılmamış,
  - son 24 saatin token'ı + bu işin tahmini sınırı aşmıyor (tahmin gerçeğin biraz altında kaldığı için %5 pay).
- [`time_until_available(model, need_tokens)`](../src/llm/ledger.py#L89): ne zaman açılır?
  - Gemini (takvim günü): sağlayıcının gece yarısına kalan süre.
  - Groq (kayan pencere): eski çağrılar 24 saatten düştükçe yer açılır; yeterli yer açılana kadarki süre hesaplanır.
  - Arayüzdeki "~1 sa 40 dk sonra devam" yazısı buradan gelir.
- [`record(model, tokens, cached)`](../src/llm/ledger.py#L116): her başarılı çağrıdan sonra `calls`'a bir satır ekler ve `usage`'ı artırır. Önbellekli token varsa `prompt_cache`'e de yazar.
- [`record_correction(model, tokens)`](../src/llm/ledger.py#L126): Groq'un hata mesajı gerçek kullanımı söylerse ("Used 198765") aradaki farkı yalnızca kayan pencereye ekler.
- [`record_sync(model, used)`](../src/llm/ledger.py#L133) / [`last_sync(model)`](../src/llm/ledger.py#L140): TPD hatasındaki gerçek kullanımı, o anki kaydımız ve önbellekli kısımla birlikte saklar / en sonuncusunu okur (istem önbelleği ölçümü).
- [`mark_exhausted(model)`](../src/llm/ledger.py#L147): "bugün dolu" işareti koyar.
- [`cache_key(model, prompt, image, params)`](../src/llm/ledger.py#L153): model + istem + görüntü özeti + parametrelerin sha1'i.
- [`cache_get(key)`](../src/llm/ledger.py#L158) / [`cache_put(key, model, response)`](../src/llm/ledger.py#L164): önbellekten okur / önbelleğe yazar.
- [`report()`](../src/llm/ledger.py#L169): bütün modellerin bugünkü durumu. Modeller ve Kota sayfası, capacity ve bekçi kullanır.
- [`Throttle`](../src/llm/ledger.py#L181): **süreç içi** dakikalık kayan pencere.
  - [`wait(model, tokens)`](../src/llm/ledger.py#L187): son 60 saniyedeki istek/token sayısı sınırı aşacaksa uyur. `rpm`/`tpm` tanımsızsa hiç beklemez.
  - [`can(model, tokens)`](../src/llm/ledger.py#L203): aynı kontrol ama bekletmez; "şu an çağrılabilir mi?" sorusunu cevaplar.
  - [`settle(model, actual)`](../src/llm/ledger.py#L214): çağrı bitince rezerve edilen en kötü durum token'ını gerçek kullanımla değiştirir. Bu yapılmadan Groq'ta dakikada yalnızca 1 çağrı yapılabiliyordu.

**Önbelleğin etkisi:** Aynı model, aynı istem ve aynı parametrelerle yapılan ikinci çağrı API'ye gitmez, **0 kota** harcar. Yarıda kesilen bir işi yeniden başlatmak bu yüzden ucuzdur. İstemi bir harf bile değiştirmek önbelleği geçersiz kılar.

---

## `src/llm/router.py` — tek kapı (311 satır)

**Ne işe yarar?** `call(rol, istem, ...)` rolün model zincirini sırayla dener. Önbelleğe bakar, kotayı denetler, sağlayıcıya göre doğru API'yi çağırır, hatayı sınıflandırır ve sonucu kaydeder. Hiçbir model cevap veremezse `AllModelsExhausted` fırlatır.

**Bağlantılar**
- ← generate, verify, vision, topics, request, pipeline, qualify, sensitivity, eval, tests.
- → `ledger`, `models`, `config`, `google.genai`, `groq`, `httpx`.

**İçindekiler**
- [`AllModelsExhausted`](../src/llm/router.py#L28): özel hata sınıfı.
  - `kinds`: her modelin neden başarısız olduğu.
  - `transient`: bütün nedenler geçiciyse (`busy` / `minute` / `network`) `True`. Bu durumda kısa bekleyip **aynı** modelle tekrar denemek doğrudur, yedeğe geçilmez.
  - `retry_in`: zincirdeki ilk modelin ne zaman açılacağı (saniye).

  `pipeline.patient` bu alanlara bakarak ne kadar bekleyeceğine karar verir.
- [`Result`](../src/llm/router.py#L43): dönüş değeri. `text` (yanıt), `model` (hangi model cevapladı), `cached` (önbellekten mi geldi).
- Modül düzeyi değişkenler:
  - `_throttle`: tek `Throttle` nesnesi.
  - `_clients`: sağlayıcı istemcileri ilk kullanımda kurulup saklanır.
  - `_last_usage`: son çağrının gerçek token sayısı (`tokens`) ve istem önbelleğinden okunan kısmı (`cached`).
- [`_gemini()`](../src/llm/router.py#L57) / [`_groq()`](../src/llm/router.py#L64): istemcileri tembel kurar. `max_retries=0` ile Groq kütüphanesinin kendi tekrar denemesi kapatılır; tekrar politikası bizim.
- [`_OPENAI_COMPAT`](../src/llm/router.py#L72): OpenAI uyumlu sağlayıcılar (OpenRouter, Cerebras) → (adres, anahtar).
- [`has_key(model)`](../src/llm/router.py#L79): sağlayıcının anahtarı `.env`'de var mı? Yoksa model zincirde atlanır.
- Üç sağlayıcı fonksiyonu (hepsi düz metin döndürür):
  - [`_call_openai_compat`](../src/llm/router.py#L89): `httpx` ile `/chat/completions` isteği atar (ek kütüphane yok). Görüntü base64 olarak eklenir.
    - Nemotron'da JSON modu kapatılır: o modda cevap yazamadan sınıra dayanıyordu.
    - gpt-oss'ta `reasoning_effort` (`effort` parametresi, `models.reasoning`'den) ayarlanır.
    - `<think>…</think>` blokları silinir.
    - Yanıttaki `cached_tokens` değeri `_last_usage`'a yazılır.
  - [`_call_gemini`](../src/llm/router.py#L124): `generate_content` çağırır. JSON modunda `response_mime_type`; gemini-2.5'te "düşünme" kapalı (`thinking_budget=0`).
  - [`_call_groq`](../src/llm/router.py#L140): Groq sohbet API'si.
    - gpt-oss gizli akıl yürütme token'ları da harcadığı için en az 2000 token sınırı verilir; düzeyi `effort` belirler.
    - Groq'un istem önbelleğinden okuduğu token'lar kaydedilir.
- [`_valid_json(text)`](../src/llm/router.py#L163): yanıt ayrıştırılabilir **ve boş olmayan** bir JSON mu? Yarıda kesilmiş ya da `{}` olan yanıt önbelleğe alınmaz; yoksa bozuk cevap her seferinde geri gelirdi.
- [`parse_wait(s)`](../src/llm/router.py#L172): hata mesajındaki "try again in 10m28.992s" ifadesini saniyeye çevirir.
- [`_classify(err)`](../src/llm/router.py#L181): hatayı türüne ayırır.

  | Tür | Nasıl anlaşılır | Ne yapılır |
  |---|---|---|
  | `network` | Timeout / Connection | 15 sn bekle, aynı modeli tekrar dene |
  | `daily` | 429 + "per day" / TPD / RPD | Groq: mesajdaki süre kadar beklet; Gemini: bugün kapat |
  | `minute` | 429 (günlük değil) | Önerilen süre kadar bekle, 1 kez tekrar |
  | `busy` | 500 / 502 / 503 / overloaded | 20 sn bekle, 1 kez tekrar; sonra sıradaki model |
  | `missing` | 404 | Model yok → bugün kapat |
  | `json` | `json_validate_failed` | Token sınırını 3 katına çıkarıp 1 kez tekrar |
  | `other` | Diğer | Hatayı yukarı fırlat (beklenmeyen hata gizlenmez) |
- [`_sync_used(model, err)`](../src/llm/router.py#L205): Groq TPD hatasındaki gerçek kullanımı deftere işler. Önce ölçüm için `record_sync`, sonra kaydımız eksikse `record_correction`.
- [`_block(model, kind, wait)`](../src/llm/router.py#L216): kota hatasından sonra modeli kapatır. Süreli bekleme (`set_cooldown`) ya da günün geri kalanı (`mark_exhausted`).
- [`_raw(model, prompt, image, ...)`](../src/llm/router.py#L224): tek bir modele tek çağrı. Önce `Throttle.wait`, sonra görüntü desteği kontrolü, sonra sağlayıcıya göre doğru fonksiyon.

**Ana fonksiyon: [`call(role, prompt, image, json_mode, max_tokens, temperature, use_cache)`](../src/llm/router.py#L239)**
1. `chain = ROLES[role]`: bu rolün modelleri. `effort = reasoning(role)`: akıl yürütme düzeyi.
   - Düzey varsayılandan (`medium`) farklıysa önbellek anahtarına eklenir. Yoksa `low` denemesi eski `medium` yanıtlarını önbellekten okuyup sahte sonuç verirdi.
   - Varsayılanda eklenmez; böylece `llm.sqlite`'taki eski yanıtların anahtarı değişmez.
2. **Önbellek:** zincirdeki herhangi bir modelin bu istem için kayıtlı yanıtı varsa hemen onu döndür (`cached=True`).
3. **Taşma:** dakikalık sınırı o an dolu olan modelleri sıranın sonuna al (sıra korunur).
4. Her model için:
   - Kayıtlı değilse, anahtarı yoksa ya da `ledger.available` hayır diyorsa atla.
   - Görüntülü çağrıda model bugün hiç kullanılmamışsa önce küçük bir "OK" yoklaması yap. Kotası dolu modele ~150 KB'lık görüntü boşuna yüklenmesin.
   - En çok 2 deneme: `_raw` başarılıysa gerçek token'ı (ve önbellekli kısmı) `ledger.record` ile yaz, `Throttle.settle` et, geçerliyse önbelleğe koy, `Result` döndür. Hata gelirse yukarıdaki tabloya göre davran.
5. Hiçbiri olmadıysa: zincirin en erken açılacağı süreyi hesapla ve `AllModelsExhausted` fırlat.

Testler: [`tests/test_router.py`](../tests/test_router.py): hata sınıflandırma, bekleme süresi ayrıştırma, model ailesi ve önbellek anahtarı (internetsiz).

---

## `src/llm/capacity.py` — `python -m src.llm.capacity` (74 satır)

**Ne işe yarar?** İnternetsiz çalışır. Son 24 saatin kullanımını, rollerin kalan bütçesini ve bir belgenin tahmini maliyetini gösterir.

**Bağlantılar**
- ← `pipeline.run_all` (`doc_cost`).
- → `ledger`, `models`, `generate` (`build_units`, `_n_questions`).

**İçindekiler**
- Ölçülmüş birim maliyetler:
  - `GEN_TOKENS_PER_UNIT = 2700`: üretim birimi başına token.
  - `VERIFY_TOKENS_PER_QUESTION = 650 × 1,1`: doğrulama, soru başına token.
- [`pool_left(role)`](../src/llm/capacity.py#L25): rolün kullanılabilir modellerinde kalan (token, istek) bütçesi.
- [`doc_cost(doc)`](../src/llm/capacity.py#L39): belgenin birim sayısı, tahmini soru sayısı, üretim ve doğrulama token'ı.
- [`main()`](../src/llm/capacity.py#L46): şunları basar:
  - kullanım tablosu (istem önbelleğinden okunan token'larla);
  - son TPD hatasında sağlayıcının bildirdiği kullanım ile bizim kaydımızın karşılaştırması (istem önbelleği ölçümü);
  - kalan bütçe;
  - istenen belgeler için "tam kotayla ~X günlük iş".

**Not:** Bu dosya `generate` rolünün (qwen) token bütçesine bakar. Asıl üretim artık Gemini toplu üretimle (`generate_batch`, istek sınırlı) yapıldığı için hesap kaba bir tahmindir.

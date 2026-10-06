# 5. Soru üretimi

[← 4. LLM kapısı](04-llm-kapisi.md) · [Ana sayfa](README.md) · Sonraki: [6. Doğrulama →](06-dogrulama.md)

LLM'in soru ve cevabı yazdığı katman. Dört dosya:
- [`schema.py`](../src/generation/schema.py): bir soru neye benzemeli?
- [`generate.py`](../src/generation/generate.py): istemi kur, LLM'i çağır, çıktıyı işle.
- [`compute.py`](../src/generation/compute.py): hesap sorusunun cevabını kodla yeniden hesapla.
- [`pilot.py`](../src/generation/pilot.py): modelleri karşılaştırma aracı.

---

## `src/generation/schema.py` — soru şeması (69 satır)

**Ne işe yarar?** LLM'in JSON çıktısındaki her soru önce bu Pydantic sınıfından geçer. Alan eksikse, tip yanlışsa ya da kural bozuksa soru `schema` nedeniyle reddedilir. Bozuk soru tek tek elenir; partinin tamamı atılmaz.

**Bağlantılar**
- ← `generate`, `checks`, `requote`, `tests/test_checks`.
- → `pydantic`.

**[`Question`](../src/generation/schema.py#L11) alanları**

| Alan | Tip | Anlamı |
|---|---|---|
| `question` | metin (≥8 karakter) | Soru kökü |
| `type` | `multiple_choice` / `short_answer` / `true_false` | Soru tipi |
| `options` | 4 metin ya da yok | Çoktan seçmelide şıklar |
| `answer_index` | 0-3 ya da yok | Doğru şıkkın sırası |
| `answer` | metin | Cevap (D/Y'de `"true"` / `"false"`) |
| `evidence_quote` | metin (≥3) | Cevabın dayandığı **birebir alıntı**: "kaynak gösterme"nin kendisi |
| `bloom_level` | `remember` / `understand` / `apply` | Bilişsel düzey (hatırlama / anlama / uygulama) |
| `evidence_quotes` | metin listesi ya da yok | Sorunun dayandığı **her ayrı bilgi/kural** için birebir alıntı; notta bulunan ayrı alıntı sayısı zorluğun yapısal ölçüsü (bölüm 10) |
| `difficulty` | `easy` / `medium` / `hard` | Üretecin **kendi** zorluk etiketi (iddia). Ekranda görünen düzey ölçülür ve yüklenirken bindirilir (bölüm 10) |
| `solution` | adımlar listesi | Hesap sorusunun çözümü |
| `compute` | SymPy ifadesi | Cevabı hesaplayan ifade (ör. `binomial(6, 2)`) |
| `option_values` | 4 SymPy ifadesi | Her şıkkın sayısal değeri |
| `answer_value` | SymPy ifadesi | Kısa cevaplı hesap sorusunun değeri |
| `option_notes` | 4 metin | Her çeldiricinin temsil ettiği hata ("Bu şıkkı seçtiysen: …") |

**Doğrulayıcılar (validator)**
- [`_normalize_tf`](../src/generation/schema.py#L34) (`mode="before"`, alanlar denetlenmeden **önce**): D/Y cevabı çıktı dilinde gelebilir (`"Yanlış. Çünkü…"`). İlk kelimeye bakıp `"true"` / `"false"`'a çevirir; şıkları boşaltır.
- [`_shape`](../src/generation/schema.py#L49) (`mode="after"`, alanlar denetlendikten **sonra**):
  - Çoktan seçmelide tam 4 **farklı** şık ve geçerli `answer_index` olmalı.
  - D/Y cevabı `true` / `false` olmalı.
  - `option_notes` bozuksa soru reddedilmez, yalnızca notlar düşer.
  - Hesap sorusu D/Y olamaz; çoktan seçmelide 4 `option_values`, kısa cevapta `answer_value` şart.

[`Batch`](../src/generation/schema.py#L71): tanımlı ama kullanılmıyor.

---

## `src/generation/generate.py` — soru üretimi (355 satır)

**Ne işe yarar?** Bölümlerden **üretim birimi** kurar, PROMPTS.md §2 / §2b / §2c ile istem hazırlar ve `router.call` ile LLM'i çağırır. Dönen JSON'daki her soruyu şemadan ve kod kontrolünden geçirir, şıklarını karıştırır.

**Bağlantılar**
- ← `pipeline` (`build_units`, `batch_groups`, `generate_group`, `generate_unit`, `math_units`, `generate_worked_group`), `request` (`generate_request`, `generate_unit`, `evolve_request`, `_render`), `capacity`, `ui/data` (`has_math`), `pilot` (`generate_doc`), eval betikleri, `tests/test_compute` (`_shuffle`).
- → `router.call`, `prompts.load_prompt`, `schema.Question`, `checks.check`, `checks.mark_duplicates`.
- 💾 Okur: `data/chunks/chunks.jsonl`, `sections.jsonl`.

**Sabitler**
- `MIN_CONTEXT = 400`: bundan kısa bölüm sonrakiyle birleştirilir.
- `MAX_CONTEXT = 4000`: bundan uzun birim bölünür.
- `RELATED_CHARS = 600`: komşu birimden çeldirici malzemesi olarak verilen uzunluk.

### Birimler

- [`_load(name)`](../src/generation/generate.py#L28): `data/chunks/` altından bir JSONL okur.
- [`_render(chunks)`](../src/generation/generate.py#L33): parçaları `"[s.12] metin"` biçiminde birleştirir. Sayfa etiketi sayesinde model kanıtın hangi sayfadan geldiğini bilir.
- [`build_units(doc)`](../src/generation/generate.py#L37): bir belgenin üretim birimleri `[{title, chunks, text, pages}]`.
  - Bölümleri sırayla alır; görsel okuma bekleyen parçaları dışarıda bırakır.
  - 400 karakterden kısa birime sonraki bölümü ekler (İngilizce slaytta tek satırlık başlık sayfaları vardı).
  - 4000 karakteri aşan birimi parça sınırlarından böler.

### Kaç soru, hangi tip, hangi sıra?

- [`_n_questions(text)`](../src/generation/generate.py#L68): her 500 karakter için 1 soru (en az 1, en çok 4).
- [`_type_plan(n, unit_index)`](../src/generation/generate.py#L75): tip dağılımını **kod** belirler: ÇS → D/Y → KC → ÇS döngüsü, birim sırasına göre kaydırılır.
  - Neden? Model "tipleri çeşitlendir" talimatına uymuyordu (bir pilotta 12/12 çoktan seçmeli).
- [`_shuffle(q, seed)`](../src/generation/generate.py#L84): çoktan seçmeli şıkları **deterministik** karıştırır.
  - Tohum `sha1(model|soru)` olduğu için aynı soru her çalıştırmada aynı sırada çıkar.
  - Şık değerleri (`option_values`) ve notları (`option_notes`) şıklarla birlikte taşınır.
  - Neden? Pilotta modeller doğru cevabı 7 sorunun 6'sında aynı harfe koymuştu (konum yanlılığı).

### İsteme eklenen hedef kurallar

- [`BLOOM_TARGET`](../src/generation/generate.py#L100): "bütün sorular hatırlama düzeyinde" / "bütün sorular uygulama düzeyinde". Yalnızca Bloom deneyinde kullanılır.
- [`DIFFICULTY_TARGET`](../src/generation/generate.py#L113): kolay / orta / zorun **işlemsel, alandan bağımsız tanımı**: kolay = cevap tek cümlede, tanıma; orta = başka sözlerle anlama / karşılaştırma / iki adım; zor = notun farklı yerlerinden en az iki ayrı bilgi ya da kural, ya da üç+ adım / durum analizi, çeldiriciler "yalnızca bir bilgiyi kullananın cevabı".
  - Bu bir **hedef**: sonuç ölçülür, etiket zorla yazılmaz. 2026-10-05'e kadar kod istenen düzeyi her soruya yazıyordu; TYT "zor" isteğinde Gemini kendi 17 sorusunun 14'üne "orta" demişti (bölüm 10).
- [`_target_rules(prompt, bloom_target, difficulty)`](../src/generation/generate.py#L127): bu kuralları §2'deki `"Rules:\n"` satırının hemen altına ekler.

### Tek birim, tek istek (yedek yol ve sınav isteği yedeği)

- [`generate_unit(unit, related, language, role, unit_index, bloom_target, n, types, difficulty)`](../src/generation/generate.py#L135): §2 istemini doldurur (soru sayısı, tip planı, bağlam, komşu metin, çıktı dili) ve `call(role, ..., json_mode=True)` çağırır.
  - Yanıt JSON değilse tek bir `invalid_json` reddi döndürür.
  - Zorluk istendiyse `requested_difficulty` alanına yazılır; sorunun `difficulty` alanı üretecin kendi iddiasıdır.
  - Sonra `_postprocess`.
- [`_postprocess(raw, unit, model)`](../src/generation/generate.py#L159): LLM çıktısı → soru öğeleri. Her soru için:
  1. Temel alanlar: `unit`, `pages`, `model`, `chunk_ids`. Bunlar sayesinde doğrulayıcı aynı bağlamı görür.
  2. `Question(**item)`: şemadan geçmezse `schema` reddi.
  3. [`check(q, unit["chunks"])`](../src/verification/checks.py#L106): kod kontrolleri (bölüm 6).
  4. `generated_answer_index`: karıştırmadan önceki doğru şık (yanlılık ölçümü için).
  5. `_shuffle`.

### Toplu üretim (bir istekte çok birim; Gemini için)

Gemini'nin sınırı istek sayısıdır (günde 20), token değil. Bu yüzden bir belgenin 12 birimine kadarı tek istekte gönderilir.

- [`_batch_prompt(units, start_index, language, bloom_target)`](../src/generation/generate.py#L183): §2'nin kural kısmı (`"Context:\n{context}"`'ten önceki her şey) + §2b. Her birim `### U1 — pages [..] — at most N question(s); types: ...` başlığıyla eklenir.
- [`batch_groups(units)`](../src/generation/generate.py#L211): birimleri en çok 12 birim / 40.000 karakterlik gruplara böler.
- [`generate_group(g, start, language, role, bloom_target)`](../src/generation/generate.py#L224): bir grup = bir istek.
  - Token sınırı geniş tutulur (≥32.000): Gemini 3.x önce "düşünüyor" ve düşünme token'ları çıktı sınırından düşüyor. 8 bin sınırda JSON yarıda kesilmişti.
- [`_split_units(r, g, force)`](../src/generation/generate.py#L234): toplu yanıtı (`{"units": [{"unit": "U1", "questions": [...]}]}`) birimlere dağıtır. Her birimin sorularını **kendi** parçalarıyla `_postprocess`'ten geçirir. `force` verilirse her soruya o alanları yazar (hesap sorusunda Bloom `apply`).
- [`generate_batched(units, language, role, bloom_target)`](../src/generation/generate.py#L200): bütün grupları sırayla üretir + `mark_duplicates`. Yalnızca eval betikleri kullanır; pipeline grupları kendisi yönetir.

### Hesap soruları (PROMPTS.md §2c)

- [`_MATH`](../src/generation/generate.py#L255) / [`math_units(units)`](../src/generation/generate.py#L259): içinde en az 4 formül işareti (`=`, `≤`, `√`, `²`, `!`, `∑`, `3 + 4` gibi işlemler) geçen birimler. Hesap sorusu yalnızca bunlardan istenir.
- [`_worked_prompt(units, start_index, language)`](../src/generation/generate.py#L264): §2c istemi. Kısa birimden 1, uzundan 2 problem istenir.
- [`generate_worked_group(g, start, language, role)`](../src/generation/generate.py#L338): tek istek. Her problemin Bloom düzeyi `apply` (uygulama) diye zorlanır. Cevap kod kontrolünde SymPy ile yeniden hesaplanır.

### Sınav isteği üretimi

- [`_spec_blocks(spec, noun)`](../src/generation/generate.py#L275): sınav isteğinin özel sayı ve tip planlarıyla birim blokları.
- [`generate_request(spec, language, difficulty, role, worked)`](../src/generation/generate.py#L281): [`request.run`](../src/request.py#L211) çağırır.
  - `spec` listesinin her elemanı `(birim, kaç soru, tipler)` üçlüsüdür; birim = bir konunun **aramayla bulunan** parçaları.
  - `worked=False`: §2 kuralları + §2b. `worked=True`: §2c.
  - Zorluk istemde hedef olarak verilir ve `requested_difficulty` alanına yazılır; düzey ölçülür (bölüm 10).
- [`evolve_request(pairs, language, target, worked, role)`](../src/generation/generate.py#L304): **zorlaştırma** (PROMPTS.md §2d). Sınav isteğinde istenen düzeyin altında ölçülen sorular için: her soru (A: kendi parçaları) başka bir konunun notuyla (B) birlikte verilir; model somut işlemlerle (iki bilgiyi birleştir, koşul ekle, uygulamaya çevir, çeldiricileri yakın yap) yeni bir soru yazar ve her bilgi için alıntı verir.
  - §2d bloğu §2b'nin (sözel) ya da §2c'nin (hesap) `{units}` yerine konur: çıktı şeması ve bütün kontroller aynı kalır.
  - Neden? "Zor yaz" sıfatı işe yaramadı; Evol-Instruct'ın somut işlemleri ve çok adımlı birleştirme literatürde zorluğu artıran yollar (LITERATURE §8).

### Belgeyi birim birim üretme (pilot için)

- [`generate_doc(doc, role, limit_units, output_language, bloom_target)`](../src/generation/generate.py#L345): her birim için ayrı istek (`generate_unit`). Komşu birimlerin metni çeldirici malzemesi olarak verilir. Yalnızca `pilot.py` kullanır.

---

## `src/generation/compute.py` — hesap sorusunu kodla doğrulama (231 satır)

**Ne işe yarar?** Hesap sorusunda model, cevabı hesaplayan bir SymPy ifadesi (`compute`) ve her şıkkın değerini (`option_values`) de yazar. Bu dosya o ifadeyi **güvenli** biçimde hesaplar ve üç şeyi denetler:
1. Anahtar gerçekten doğru sonuç mu?
2. Başka bir şık da aynı sonuca eşit mi (iki doğru şık)?
3. Şık **metnindeki** sayı şıkkın değeriyle tutarlı mı? Öğrenci metni görür, değeri değil.

LLM çağrısı yoktur; sonuç deterministiktir.

**Bağlantılar**
- ← `checks.check` (`judge`, `reasons`), `verify.verify_computed` (`numbers_in`), `grading` (`validate`, `_eval`, `_ns`), `eval/compute_check`, `tests/test_compute`.
- → `sympy` (yalnızca işçi süreçte), `ast`, `multiprocessing`.

**Güvenlik neden önemli?** Model ne yazarsa `eval()` ile çalıştırılacak. `__import__('os').system(...)` gibi bir ifade bilgisayara zarar verebilirdi. Bu yüzden üç kat koruma var:

1. **Beyaz liste.** [`validate(expr)`](../src/generation/compute.py#L35) ifadeyi çalıştırmadan `ast.parse` ile ağaca çevirir ve her düğümü denetler:
   - Yalnızca izinli yapılar (`_NODES`: sayılar, `+ - * / ** %`, çağrı, köşeli parantez).
   - Yalnızca izinli fonksiyonlar (`FUNCS`: `binomial`, `factorial`, `solve`, `sqrt`…).
   - Yalnızca tek harfli semboller (`x`, `n`, `x1`).
   - Metin sabiti, öznitelik erişimi (`x.__class__`), anahtar kelimeli argüman yok; 1000'den büyük üs yok; 300 karakterden uzun ifade yok.
2. **Boş ortam.** [`_eval(expr, ns)`](../src/generation/compute.py#L82) `eval`'i `{"__builtins__": {}}` ile çalıştırır; Python'un yerleşik fonksiyonlarına erişim yoktur.
   - [`_ns()`](../src/generation/compute.py#L70) izinli SymPy fonksiyonlarını ve sembolleri hazırlar. `e` ve `i` sembol yapılmaz; `E` ve `I` sabitleriyle karışmasınlar.
3. **Ayrı süreç + süre sınırı.** [`judge(q)`](../src/generation/compute.py#L200) hesabı tek işçili bir süreç havuzunda ([`_get_pool`](../src/generation/compute.py#L187), `spawn`) 10 saniye sınırla yapar. Süre aşılırsa süreç öldürülür, hata döner. SymPy bazı ifadelerde çok uzun sürebiliyor.

**Diğer fonksiyonlar**
- [`_equal(a, b)`](../src/generation/compute.py#L96): iki değer eşit mi? Önce sembolik (`simplify(a - b) == 0`), sonra 30 basamaklı sayısal karşılaştırma. Çözüm kümeleri için eleman eleman bakar.
- [`numbers_in(text)`](../src/generation/compute.py#L114): metindeki sayılar `Fraction` olarak. Türkçe ondalık virgül (`2,5`), kesir (`3/4`) ve tipografik eksi tanınır; `%25` için hem 25 hem 1/4 döner.
- [`_text_consistent(text, value)`](../src/generation/compute.py#L133): şık metnindeki sayılardan biri değere eşit mi? Değer rasyonel değilse (√2) ya da metinde sayı yoksa `None` (denetlenemez).
- [`_judge_worker(payload)`](../src/generation/compute.py#L145): **işçi süreçte** çalışır. `compute`'u ve şık değerlerini hesaplar. `key_ok`, `others_equal`, `text_ok`, `distractor_text_shows_answer` alanlarını içeren düz bir sözlük döndürür.
- [`_close()`](../src/generation/compute.py#L195) (`@atexit.register`): program kapanırken işçi süreci kapatır.
- [`reasons(res)`](../src/generation/compute.py#L217): sonuç → (red nedenleri, uyarılar).

  | Kod | Anlamı | Etki |
  |---|---|---|
  | `compute_error` | İfade reddedildi ya da hesaplanamadı | Red |
  | `compute_mismatch` | Anahtar, kodun hesapladığı sonuç değil | Red |
  | `compute_two_correct` | Başka bir şık da doğru sonuca eşit (değeri ya da metni) | Red |
  | `compute_text_mismatch` | Şık metnindeki sayı değeriyle çelişiyor | Red |
  | `compute_text_unchecked` | Şıklarda düz sayı yok (√2 gibi) | Uyarı |

Ölçüm: [`eval/compute_check.py`](../eval/compute_check.py) (kasıtlı hatalar 20/20, 20/20, 19/20 yakalandı; yanlış alarm 0/20).

---

## `src/generation/pilot.py` — model karşılaştırma pilotu (81 satır)

**Ne işe yarar?** `python -m src.generation.pilot "<belge>" model1,model2 [dil] [birim_sınırı]` komutu aynı belgeden her modelle ayrı ayrı soru üretir. Sonuçları `data/pilot/<model>.jsonl` ve okunur bir `rapor.md` dosyasına yazar. Proje başında "üretim hangi modelle yapılmalı?" sorusu bununla cevaplandı.

- [`main()`](../src/generation/pilot.py#L53): her model için geçici bir `_pilot` rolü kurar (yalnızca o model, yedek yok) ve `generate_doc` çağırır.
- [`_stats(items)`](../src/generation/pilot.py#L20): üretilen / geçen sayıları, red nedenleri, uyarılar, tipler, Bloom düzeyi ve **LLM'in doğru şıkkı koyduğu harf** (karıştırmadan önce).
- [`_md_question(n, it)`](../src/generation/pilot.py#L34): bir sorunun Markdown görünümü (✅ / ❌, şıklar, kanıt).

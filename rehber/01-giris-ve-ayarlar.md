# 1. Giriş kapıları ve ayarlar

[← Rehber ana sayfa](README.md) · Sonraki: [2. PDF okuma →](02-pdf-okuma.md)

Bu bölüm dört dosyayı ve bir istem dosyasını anlatıyor:
- [`config.py`](../src/config.py) ve [`prompts.py`](../src/prompts.py): herkesin kullandığı iki küçük temel.
- [`PROMPTS.md`](../PROMPTS.md): kodun okuduğu istemler.
- [`app.py`](../src/app.py) ve [`pipeline.py`](../src/pipeline.py): sistemin iki giriş kapısı.

---

## `src/config.py` — proje ayarları (33 satır)

**Ne işe yarar?** Bütün klasör yolları ve API anahtarları tek yerde tanımlanır. Başka bir dosya "veri klasörü nerede?" diye sorduğunda cevabı buradan alır. Yol bir gün değişirse tek satır değişir.

**Bağlantılar**
- ← 26 dosya içe aktarıyor (projede en çok kullanılan modül).
- → `python-dotenv` (`.env` dosyasını okur).
- 💾 Okur: `.env`.

**İçindekiler**
- [Satır 8 `ROOT`](../src/config.py#L8): proje kök klasörü.
  - `Path(__file__)` bu dosyanın yoludur (`.../NotaRAG/src/config.py`).
  - `.resolve()` tam yola çevirir; `.parent.parent` iki üst klasöre çıkar (`.../NotaRAG`).
  - Böylece kod hangi klasörden çalıştırılırsa çalıştırılsın doğru yeri bulur.
- [Satır 9 `load_dotenv(...)`](../src/config.py#L9): `.env` dosyasındaki `ANAHTAR=değer` satırlarını ortam değişkenlerine yükler.
- [Satır 11-15](../src/config.py#L11): `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`.
  - `os.getenv("X", "")` değişken yoksa boş metin döndürür; program çökmez.
  - Anahtarı olmayan sağlayıcının modelleri [`router.has_key`](../src/llm/router.py#L88) tarafından atlanır.
- [Satır 19-22](../src/config.py#L19): `DATA_DIR` (`data/`), `PARSED_DIR` (`data/parsed/`), `VISION_CACHE_DIR` (`data/vision_cache/`), `VISION_DPI = 150` (görsel okuma için sayfa görüntüsünün çözünürlüğü).
- [Satır 25 `DOC_NAMES`](../src/config.py#L26): dosya adı → ekranda görünen kısa ad (ör. `"english"` → `"Genetic Algorithms"`).
- [Satır 31 `doc_name(stem)`](../src/config.py#L32): kısa adı döndürür. Listede olmayan (arayüzden yeni yüklenmiş) belgede alt çizgileri boşluğa çevirir.

**Neden böyle?** Anahtarlar koda yazılmaz, `.env`'de durur; `.env` de `.gitignore` sayesinde repoya girmez. Şablonu [`.env.example`](../.env.example).

---

## `src/prompts.py` — istemleri PROMPTS.md'den okuma (16 satır)

**Ne işe yarar?** LLM'e gönderilen istem metinleri kodun içinde değil, [`PROMPTS.md`](../PROMPTS.md) içinde durur. Bu dosyadaki tek fonksiyon istenen bölümün metnini çıkarır. Böylece belge ile kod hiçbir zaman birbirinden ayrışmaz.

**Bağlantılar**
- ← `generation/generate.py` (§2, §2b, §2c), `ingestion/vision.py` (§1), `topics.py` (§7), `verification/verify.py` (§4a-4e, §6, §6b).
- 💾 Okur: `PROMPTS.md`.

**İçindekiler**
- [`load_prompt(section)`](../src/prompts.py#L10): örneğin `load_prompt("4a")`.
  - Düzenli ifade (regex), `## 4a.` ya da `### 4a.` başlığını bulur.
  - O başlığın altındaki **ilk** ` ``` ` kod bloğunun içini döndürür.
  - Bulamazsa `KeyError` verir.
  - `@lru_cache` sayesinde dosya her süreçte bir kez okunur.

**Dikkat:** `lru_cache` yüzünden PROMPTS.md'de yaptığın değişiklik çalışan Streamlit sürecine yansımaz; yeniden başlatman gerekir. Arka plan işleri (pipeline, request) her seferinde yeni süreç olduğu için değişikliği hemen görür.

---

## `PROMPTS.md` — kodun okuduğu istemler

Bu bir Markdown belgesi ama aslında kodun parçası. Her bölümün ilk kod bloğu bir istem şablonudur. `{ad}` biçimindeki yer tutucuları kod `.replace()` ile doldurur.

| § | Ne için | Okuyan fonksiyon | Yer tutucular |
|---|---|---|---|
| 1 | Resim olan sayfayı okuma | [`vision.run_vision`](../src/ingestion/vision.py#L63) | `{text_layer}` |
| 2 | Soru + cevap üretimi (kurallar) | [`generate_unit`](../src/generation/generate.py#L135), `_batch_prompt`, `generate_request` | `{n_questions}`, `{type_plan}`, `{context}`, `{related}`, `{output_language}` |
| 2b | Toplu üretim (çok birim, tek istek) | `_batch_prompt`, `generate_request` | `{units}` |
| 2c | Hesap problemleri (SymPy ifadesiyle) | `_worked_prompt`, `generate_request(worked=True)` | `{output_language}`, `{units}` |
| 3 | (Ayrılmış) sohbet modu | — kullanılmıyor | |
| 4a | Çoktan seçmeli kör doğrulama | [`verify_mcq`](../src/verification/verify.py#L112) | `{context}`, `{question}`, `{option_a..d}` |
| 4b | Doğru/Yanlış: SUPPORTED / CONTRADICTED / NOT_IN_CONTEXT | `verify_tf` | `{context}`, `{question}` |
| 4c | Kısa cevap: kör cevap | `verify_short` | `{context}`, `{question}` |
| 4d | İki cevap eşdeğer mi (hakem) | `verify_short`, `verify_computed` | `{question}`, `{answer_1}`, `{answer_2}` |
| 4e | Hesap sorusunu kör çözme | `verify_computed` | `{context}`, `{question}`, `{options}` |
| 5 | Soru → önerme (RAGAS için) | — henüz kullanılmıyor (planlı) | |
| 6 | Bağlamsız tahmin testi | `verify_mcq` (yalnızca `light=False`) | `{question}`, `{option_a..d}` |
| 6b | Yalnızca şıklar testi | `verify_mcq`, `sensitivity.choices_only` | `{option_a..d}` |
| 7 | Konu haritası | [`topics.build`](../src/topics.py#L44) | `{output_language}`, `{document}` |
| "Programmatic Checks" | `checks.py`'nin açıklaması | — istem değil, belge | |

**Dikkat:** kod §2'nin içinde iki sabit metne güveniyor:
- [`_target_rules`](../src/generation/generate.py#L127) yeni kuralları `"Rules:\n"` satırının hemen altına ekler.
- `_batch_prompt` / `generate_request` kural kısmını `"Context:\n{context}"` metninden keserek alır.

Bu iki ifadeyi PROMPTS.md'de değiştirirsen kural ekleme sessizce çalışmaz ya da kesme `ValueError` verir.

---

## `src/app.py` — arayüzün giriş noktası (41 satır)

**Ne işe yarar?** `streamlit run src/app.py` komutu bu dosyayı çalıştırır. Sayfa ayarlarını yapar, ortak stili basar, kenar çubuğundaki menüyü kurar ve seçilen sayfayı çalıştırır.

**Bağlantılar**
- → `ui/style.py` (`inject`).
- → 6 sayfa dosyası (Streamlit onları ayrı betik olarak çalıştırır).
- 💾 Okur: `src/ui/logo.svg`, `.streamlit/config.toml` (Streamlit kendisi okur: renkler, yazı tipleri).

**İçindekiler (yukarıdan aşağı)**
- [Satır 10](../src/app.py#L10) `sys.path.insert(0, ...)`: Streamlit `src/app.py`'yi paket olarak değil, düz betik olarak çalıştırır. Bu durumda `from src.ui import style` çalışmaz, çünkü Python `src` paketini bilmez. Proje kökü arama yoluna eklenerek sorun çözülür.
- [Satır 16](../src/app.py#L16) `st.set_page_config(...)`: sekme başlığı "NotaRAG", geniş düzen, kenar çubuğu açık.
- [Satır 18](../src/app.py#L18) `style.inject()`: bütün sayfalarda geçerli CSS (bkz. bölüm 8).
- [Satır 22-36](../src/app.py#L22) `pages`: menü üç gruptan oluşur:
  - **Çalış:** Sınav Hazırla (varsayılan sayfa), Bilgi Kartları
  - **İçerik:** Belgeler, Soru Bankası
  - **Kalite:** İnceleme, Rapor, Modeller ve Kota
- [Satır 37-42](../src/app.py#L37): `st.navigation(...)` menüyü kurar, `nav.run()` seçilen sayfanın dosyasını çalıştırır.

**Streamlit'in çalışma biçimi:** Her sayfa dosyası (ör. [`ui/pages/exam.py`](../src/ui/pages/exam.py)) en altta `render()` çağırır. Streamlit sayfayı her açtığında ve her tıklamada o dosyayı **baştan sona** yeniden çalıştırır. Ayrıntısı bölüm 8'de.

---

## `src/pipeline.py` — belge işlemenin orkestra şefi (233 satır)

**Ne işe yarar?** Bir PDF'i baştan sona işler: okuma → görsel okuma → bölümleme → dizin + konu haritası → soru üretimi → doğrulama. Sonuç `data/questions/<belge>_<dil>.jsonl` dosyasıdır. Kendisi pek az iş yapar; diğer modülleri doğru sırayla çağırır ve kota dolunca bekler. Projeyi anlamak için okunacak **ilk** dosya budur.

**Bağlantılar**
- ← `ui/data.start_job` bunu ayrı süreçte başlatır (`python -m src.pipeline "<pdf>"`).
- ← `request.py` yalnızca `patient` fonksiyonunu kullanır.
- ← `tests/test_pipeline.py` `merge_existing`'i sınar.
- → `ingestion` (pdf_parser, vision), `chunking`, `retrieval.index`, `topics`, `generation.generate`, `verification` (checks, verify), `review_store`, `llm` (ledger, router, capacity).
- 💾 Okur: `data/sample_docs/*.pdf`, `data/chunks/chunks.jsonl`, var olan soru dosyası.
- 💾 Yazar: `data/parsed/<belge>.json`, `data/questions/<belge>_<dil>.jsonl`. Diğer dosyaları çağırdığı modüller yazar.

### Ana fonksiyon: [`run(name, output_language)`](../src/pipeline.py#L140)

Adım adım ne yaptığı (konsola yazdığı `1/6 ...` satırları arayüzdeki ilerleme çubuğunu da besler):

1. **PDF'i bul.** `data/sample_docs/` içinde adı ya da kök adı eşleşen dosya.
2. **`1/6 PDF okuma`.** [`parse_pdf`](../src/ingestion/pdf_parser.py#L401) PDF'i okur, sonuç `data/parsed/<belge>.json`'a yazılır. Hemen ardından [`apply_cached_vision`](../src/ingestion/vision.py#L134) daha önce görselden okunmuş sayfaları önbellekten geri koyar. Yeniden ayrıştırma bu sayfaların okumasını kaybetmesin diye yapılır.
3. **`2/6 görsel okuma`.** [`_vision_until_done`](../src/pipeline.py#L110) yalnızca henüz okunmamış resim sayfalarını okutur; kota biterse bekler.
4. **`3/6 bölümleme`.** [`chunking.__main__.main`](../src/chunking/__main__.py#L17) **bütün** ayrıştırılmış belgeleri yeniden parçalar ve `chunks.jsonl` / `sections.jsonl` dosyalarını baştan yazar. Yereldir, hızlıdır.
5. **`4/6 dizin`.**
   - [`Index().build()`](../src/retrieval/index.py#L38) Chroma koleksiyonunu baştan kurar. Embedding'i yalnızca yeni ya da değişen parçalar için ister; gerisi önbellekten gelir.
   - Ardından [`topic_map`](../src/topics.py#L66) konu haritasını çıkarır. Kota yoksa bölüm başlıklarına düşer.
6. **Çıktı dilini belirle.** Parametre verilmediyse belgenin kendi dili kullanılır. Örneğin İngilizce slayttan Türkçe soru istenebilir.
7. **`5/6 soru üretimi`.** [`build_units`](../src/generation/generate.py#L37) üretim birimlerini kurar. Ardından:
   - [`_generate`](../src/pipeline.py#L47): normal sorular.
   - [`_generate_worked`](../src/pipeline.py#L89): hesap soruları.
8. **Eskilerle birleştir.** Dosyada daha önce üretilmiş sorular varsa [`merge_existing`](../src/pipeline.py#L124) onları korur ve yalnızca gerçekten yeni olanları ayırır.
9. **`6/6 doğrulama`.** Her yeni soru için [`verify_item`](../src/verification/verify.py#L191) çağrılır:
   - `patient` ile sarılıdır: kota dolarsa bekler.
   - `light=True`: yalnızca karar veren doğrulama yapılır, bilgi amaçlı ek testler atlanır.
   - Her 5 soruda bir ilerleme satırı yazar.
10. **Yaz.** `eskiler + yeniler` dosyaya yazılır, etiket sayıları (`verified` / `needs_review` / `rejected`) basılır.

### Yardımcı fonksiyonlar

- [`patient(fn, *args, what, on_wait, **kwargs)`](../src/pipeline.py#L26): "sabırlı çağrı". `fn`'yi çağırır; [`AllModelsExhausted`](../src/llm/router.py#L28) hatası gelirse uyuyup yeniden dener (en çok 200 kez).
  - Hata **geçiciyse** (`e.transient`: sağlayıcı yoğun, dakikalık sınır, ağ) 2 dakika bekler.
  - **Kota** dolduysa `e.retry_in` kadar (en çok 1 saat; bilinmiyorsa 15 dk) bekler.
  - `on_wait(neden, saniye)` verilirse beklemeyi bildirir; sınav isteği bunu ekrana "~1 sa 40 dk sonra devam" diye yazar.
  - **Neden önemli?** Kalite kapısı gereği kota dolunca daha zayıf bir modele geçilmez; iş bekler. Bu fonksiyon o beklemeyi yapar.
- [`_generate(units, lang)`](../src/pipeline.py#L47): önce **toplu üretim** dener. Birimler [`batch_groups`](../src/generation/generate.py#L211) ile en çok 12 birimlik gruplara bölünür; her grup Gemini'ye tek istek olarak gider.
  - Bir grup başarısız olursa yalnızca o grubun birimleri **birim başına üretime** (`generate_unit`, rol `"generate"` = qwen) geçer.
  - Komşu birimlerin ilk 600 karakteri `related` olarak verilir: model çeldiricileri oradan seçebilir.
  - Gruplar ayrı ayrı işlendiği için biri bozulsa diğerlerinin soruları kaybolmaz.
- [`_batch_try(fn, what, n_units, fallback)`](../src/pipeline.py#L71): tek toplu istek denemesi. Gemini yalnızca **yoğunsa** 2, 4, 8 dk bekleyip yeniden dener. Kota gerçekten bittiyse `None` döndürür; çağıran yedek yolu seçer.
- [`_generate_worked(units, lang)`](../src/pipeline.py#L89): hesap soruları yalnızca formüllü birimlerden ([`math_units`](../src/generation/generate.py#L259)) istenir.
  - Bu iş için onaylı bir yedek model yoktur. Kota biterse adım **atlanır**; sınanmamış modele devredilmez.
  - Sonraki çalıştırmada önbellek sayesinde kalan kısım tamamlanır.
- [`_vision_until_done(parsed_path, pdf)`](../src/pipeline.py#L110): [`run_vision`](../src/ingestion/vision.py#L63) `False` dönerse (bütün görsel modellerin kotası dolu) en kısa bekleme süresi kadar uyur ve tekrar dener. Okunacak sayfa kalmayınca çıkar.
- [`merge_existing(old, items, chunks)`](../src/pipeline.py#L124): **"yeniden çalıştırma ekler, silmez"** kuralı. Üç liste döndürür:
  1. `stale`: parçası artık var olmayan eski sorular (belge değiştiyse) düşer.
  2. `kept`: geri kalan eskiler aynen korunur.
  3. `new`: kimliği (`question_id`) eskilerde olmayan yeni sorular. Önbellekten aynen gelenler zaten aynı kimliği taşıdığı için elenir. [`mark_duplicates(new, keep=kept)`](../src/verification/checks.py#L203) eskilerin tekrarı olan yenileri reddeder; böylece tekrarlar doğrulamaya gidip kota harcamaz.

  Bu fonksiyon 2026-10-05'te bulunan bir hatayı düzeltiyor: eskiden `run` dosyanın üzerine yazıyordu ve doğrulanmış sorular, onlara bağlı kararlarla birlikte kaybolacaktı. Test: [`tests/test_pipeline.py`](../tests/test_pipeline.py).
- [`run_all(output_language)`](../src/pipeline.py#L203): `--hepsi` ile klasördeki bütün PDF'leri sırayla işler. Soru dosyası PDF'ten yeniyse belgeyi "zaten işlenmiş" sayıp atlar. Her belgeden sonra [`doc_cost`](../src/llm/capacity.py#L39) ile tahmini token maliyetini basar.
- [`if __name__ == "__main__"`](../src/pipeline.py#L229): komut satırı argümanlarını okur.

**Neden içe aktarmalar fonksiyonların içinde?** `request.py` bu dosyayı yalnızca `patient` için içe aktarır. Üstte `pymupdf`, `chromadb` gibi ağır kütüphaneler olsaydı sınav isteği gereksiz yere hepsini yüklerdi. Fonksiyon içi içe aktarma bu yükü yalnızca `run` çalışınca öder.

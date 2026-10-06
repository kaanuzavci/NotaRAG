# 7. Sınav isteği ve yardımcı modüller

[← 6. Doğrulama](06-dogrulama.md) · [Ana sayfa](README.md) · Sonraki: [8. Arayüz →](08-arayuz.md)

Bu bölümde sistemin asıl kullanım akışı var. Kullanıcı konu seçer, sistem notlarda arar, havuzdan soru verir, eksikse üretir. Ona hizmet eden dört yardımcı modül de burada:

| Dosya | Görevi |
|---|---|
| [`topics.py`](../src/topics.py) | Seçilebilir konu listesi (konu haritası) |
| [`request.py`](../src/request.py) | Sınav isteği: arama → havuz → hedefli üretim; çözüm kayıtları |
| [`grading.py`](../src/grading.py) | Öğrencinin kısa cevabını puanlama |
| [`review_store.py`](../src/review_store.py) | Soru kimliği, öğretmen kararları, kanıtı PDF'te işaretleme |
| [`export.py`](../src/export.py) | Moodle XML / GIFT, yazdırılabilir sınav, CSV, JSON |
| [`requote.py`](../src/requote.py) | Kaynak metin düzelince eski soruların bakımı |

---

## `src/topics.py` — konu haritası (92 satır)

**Ne işe yarar?** Bir belgeyi bir kez Gemini'ye verir (PROMPTS.md §7) ve "bu belgede hangi konular, hangi sayfalarda?" listesini çıkarır. Sınav Hazırla sayfasında kullanıcı konuları bu listeden **seçer**; serbest metin yazmaz.

**Neden seçim?** Serbest metin anlamsız ya da belgede olmayan bir konu olabilir. Hazır liste bunu engeller, belgenin neyi kapsadığını da gösterir. Seçilen konunun **adı arama sorgusudur**; üretim bağlamını konu haritasındaki sayfalar değil, **arama** belirler.

**Bağlantılar**
- ← `pipeline.run`, `request.prepare`, `export._topic`, `ui/data.topics`.
- → `router.call("generate_batch", ...)`, `prompts.load_prompt("7")`.
- 💾 Okur: `data/chunks/chunks.jsonl`, `sections.jsonl`. Yazar: `data/topics/<belge>.json`.

**İçindekiler**
- [`_chunks(doc)`](../src/topics.py#L23): belgenin parçaları.
- [`_fallback(doc)`](../src/topics.py#L29): konu haritası çıkarılamazsa bölüm başlıklarını konu olarak kullanır. Yalnızca sayıdan oluşan ya da çok uzun başlıklar "Sayfa 3-5" olur.
- [`build(doc, language)`](../src/topics.py#L44): belgenin bütün sayfa metnini (`[s.N] ...`) §7 istemine koyar ve tek istekte konu listesini alır. Belgede olmayan sayfa numaralarını ve tekrar eden başlıkları ayıklar.
- [`topic_map(doc, rebuild, build_missing)`](../src/topics.py#L66): giriş noktası.
  1. Disk önbelleğinde varsa onu döndürür.
  2. `build_missing=False` ise (arayüz) LLM'e hiç gitmez, bölüm başlıklarını döndürür.
  3. Değilse `build` dener. Kota yoksa ya da yanıt bozuksa bölüm başlıklarına düşer ve bu sonucu **diske yazmaz**; böylece sonraki çalıştırmada yeniden denenir.

  Her konuda `source` alanı `"llm"` ya da `"sections"` olur.

---

## `src/request.py` — sınav isteği: sistemin RAG akışı (379 satır)

**Ne işe yarar?** Sınav Hazırla sayfasındaki her istek burada işlenir. Üç aşama var:
1. **Arama:** her konu adı → seçili belgelerde dense arama → en ilgili parçalar.
2. **Havuz:** o sayfalara bağlı, istenen tip ve zorlukta, doğrulanmış ve engellenmemiş sorular → anında, 0 token.
3. **Eksikler:** yalnızca bulunan parçalardan, seçilen zorluğu hedefleyen üretim → kod kontrolü → kör doğrulama → havuza ekle → **zorluk ölçümü**; istenen düzeyde ölçülmeyen sınava girmez, gerekirse zorlaştırılır. Bu aşama arka planda, ayrı bir süreçte çalışır.

Öğrenci çözümlerini, madde istatistiğini ve "hatalı bildir" kayıtlarını da bu dosya tutar.

**Bağlantılar**
- ← `ui/pages/exam`, `ui/quiz`, `ui/data`, `ui/pages/bank`, `ui/pages/documents`, `ui/pages/report`. Kendini `python -m src.request <id>` olarak ayrı süreçte de çalıştırır.
- → `retrieval.index.Index`, `topics`, `generate` (`generate_request`, `generate_unit`, `evolve_request`, `_render`), `checks.mark_duplicates`, `verify.verify_item`, `pipeline.patient`, `review_store`, `difficulty` (`apply`), `simulate` (`run`).
- 💾 Okur: `data/questions/*.jsonl`, `data/reviews.jsonl` (review_store aracılığıyla), `data/review/reports.jsonl`, `attempts.jsonl`.
- 💾 Yazar: `data/requests/<id>.json` / `.log`, `data/questions/istek_<dil>.jsonl`, `data/review/attempts.jsonl`, `reports.jsonl`.

**Sabitler:**
- `KINDS`: tip → Türkçe ad (hesap sorusu ayrı bir "tip" sayılır).
- `DIFFS`: zorluk → Türkçe ad.
- `MAX_CONTEXT = 4000`: normal bağlam sınırı.
- `TOPIC_K = 4`: konu başına en çok 4 parça.
- `SLACK = 0.08`: en iyi eşleşmeden 0,08'den uzak (kosinüs mesafesi) parçalar alınmaz.

### 1. Arama
- [`kind(q)`](../src/request.py#L40): `compute` varsa `"computed"`, yoksa sorunun tipi.
- [`_index()`](../src/request.py#L47) (`@lru_cache`): `Index` nesnesi süreç başına bir kez kurulur.
- [`retrieve(topic, docs)`](../src/request.py#L52): **RAG'in R'si.**
  1. Konu adını gömer (`embed_query`).
  2. Chroma'da yalnızca seçili belgelerde (`where`) en yakın 12 parçayı mesafeleriyle ister.
  3. En iyi eşleşmeye `SLACK` kadar yakın olanları ve görsel okuma beklemeyenleri tutar; ilk 4'ünü döndürür.

### 2. Havuz
- [`_jsonl(path)`](../src/request.py#L68): dosya varsa JSONL okur.
- [`all_items()`](../src/request.py#L72): `data/questions/` altındaki bütün sorular, kimliğe göre sözlük. Her soruya `id` ve `doc` eklenir, sonra **etkin zorluk bindirilir** (`difficulty.apply`; dosyaya yazılmaz, bölüm 10). Pilot setleri havuza girmez.
- [`reported()`](../src/request.py#L85): soru kimliği → "hatalı bildir" kayıtları.
- [`blocked_ids()`](../src/request.py#L92): havuzdan çıkarılan sorular. Öğretmenin reddettikleri ve öğrencinin bildirdiği ama bildirimden **sonra** öğretmenin onaylamadığı sorular.
- [`usable(it)`](../src/request.py#L103): `verified` ve kod kontrolünden geçmiş mi?
- [`_split(n, k)`](../src/request.py#L109): `n` soruyu `k` konuya mümkün olduğunca eşit böler (10, 3 → 4, 3, 3).
- [`prepare(docs, topics, difficulty, kinds, n, language)`](../src/request.py#L113): sayfadaki "Sınavı hazırla" düğmesi bunu çağırır, **anında** biter.
  1. Konu seçilmediyse belgelerin bütün konuları alınır.
  2. Her konu için `retrieve`. Sonucu boş olan konular düşer.
  3. Her konunun payı (`_split`) kadar soru, havuzdaki uygun sorulardan **rastgele** seçilir. Uygunluk: kanıt sayfası aramanın bulduğu sayfalardan biri, tip ve zorluk uygun, engellenmemiş.
  4. Eksik kalan konular `missing` sözlüğüne yazılır.
  5. İstek dosyası kaydedilir; `status` eksik yoksa `"ready"`, varsa `"partial"`.
- [`save(req)`](../src/request.py#L146): önce `.tmp` dosyasına yazar, sonra `replace` ile asıl dosyanın yerine koyar (**atomik yazma**). Arayüz dosyayı her 3 sn'de okurken yarım yazılmış bir JSON görmez.
- [`load(req_id)`](../src/request.py#L153) / [`items_of(req)`](../src/request.py#L158): isteği ve sınavın sorularını (havuzdan + yeni üretilen; en çok `n` tane) yükler.
- [`start(req)`](../src/request.py#L164): durumu `"generating"` yapar ve `python -m src.request <id>`'yi **bağımsız bir süreç** olarak başlatır (`DETACHED_PROCESS`). Çıktı `data/requests/<id>.log`'a gider. Sayfa kapansa da iş sürer.

### 3. Eksikleri üret ve doğrula (arka plan süreci)
- [`_unit(topic, refs, chunks, wide)`](../src/request.py#L179): bir konunun **üretim bağlamı**, aramanın bulduğu parçalardır.
  - Bir konudan 4'ten fazla soru isteniyorsa (`wide=True`) aynı sayfalardaki diğer parçalar da eklenir. Konu dışına çıkılmaz, sınır 6.000 karakterdir.
  - Bu, toplu akıştaki "bölüm" biriminin sınav isteğindeki karşılığıdır.
- [`_dur(seconds)`](../src/request.py#L200): "1 sa 40 dk" biçimi.
- [`_progress(req, text)`](../src/request.py#L205): ilerleme metnini istek dosyasına yazar; arayüz bunu gösterir.
- [`run(req_id)`](../src/request.py#L211):
  1. Her eksik konu için birim kurar ve eksiğin **%40 fazlasını** ister (en çok 12): elenenleri telafi etmek için. Fazlası havuza kalır, boşa gitmez.
  2. Hesap sorusu seçildiyse pay ayrılır.
  3. `generate_request` ile tek istekte üretir. Gemini dolarsa normal sorular onaylı yedekle (`generate_unit`, qwen) üretilir; hesap soruları için yedek yoktur, atlanır.
  4. `mark_duplicates(new, keep=havuz)`: havuzdakinin tekrarı doğrulamaya gitmez.
  5. [`_settle(req, new, chunks)`](../src/request.py#L293): kontrol → doğrulama → kayıt → ölçüm (aşağıda).
  6. Zorluk istendiyse ve yeterli soru istenen düzeyde ölçülmediyse **ikinci tur**: düzeyin altında kalanlar [`evolve_request`](../src/generation/generate.py#L304) ile zorlaştırılır (PROMPTS §2d), yenileri de `_settle`'dan geçer.
  7. Sınava yalnızca istenen düzeyde ölçülenlerin kimlikleri yazılır; ilerleme metni kaçının zorlaştırılarak geldiğini ve eksiği söyler. Durum `"done"`.
- [`_settle(req, new, chunks)`](../src/request.py#L293): `mark_duplicates(new, keep=havuz)` → her geçerli soru `patient(verify_item, ...)` ile doğrulanır (kota dolarsa "~X dk sonra kendiliğinden devam edecek") → bütün yeni sorular `istek_<dil>.jsonl`'a **üretecin etiketiyle eklenir** → zorluk istendiyse sözel sorular benzetilir (`simulate.run`), hepsine `apply` → (istenen düzeydekiler, düzeyin altındakiler) kopyaları döner.
- [`_part_b(it, req, chunks)`](../src/request.py#L284): zorlaştırmada birleştirilecek ikinci not parçası: aynı sınavın bir sonraki konusu (tek konuysa aynı konunun geniş bağlamı).

### Öğrenci kayıtları
- [`record_attempt(req_id, results, retry, answers, hints)`](../src/request.py#L341): sınav bitince her soru için bir satır yazar: doğru mu, öğrencinin cevabı, kullandığı ipucu sayısı.
  - `retry=True` (yanlışları tekrar çözme) satırları istatistiğe girmez; güçlük ilk denemeden ölçülür.
  - Cevap da saklanır: puanlama düzeltilirse eski denemeler yeniden puanlanabilir, hangi çeldiricinin seçildiği görülür.
- [`item_stats()`](../src/request.py#L359): **madde analizi**. Soru başına çözülme sayısı ve doğru oranı.
  - Herkesin yanlış yaptığı bir soru, hatalı cevap anahtarının işareti olabilir.
- [`report(qid, note, req_id)`](../src/request.py#L371): "hatalı bildir" ve kısa cevap itirazı kaydı. Bildirilen soru öğretmen onaylayana kadar sınavlara girmez (`blocked_ids`).

---

## `src/grading.py` — kısa cevap puanlama (130 satır)

**Ne işe yarar?** Öğrencinin yazdığı kısa cevap doğru mu? LLM kullanmaz.
- Beklenen cevap **matematiksel** ise iki taraf SymPy ile hesaplanır ve **değerler** karşılaştırılır: `30240` = `9!/(3!·2!)` = `362880/12`.
- **Metin** cevapta sıkı bir benzerlik eşleşmesi yapılır.

**Neden?** Eski yöntem (kelime kümesi benzerliği) bir kümenin diğerini içermesine 100 puan veriyordu. Beklenen `(n choose 2) * 2` iken öğrencinin `2` cevabı DOĞRU sayılıyordu (2026-10-05, kullanıcı ekran görüntüsüyle buldu).

**Bağlantılar**
- ← `ui/quiz.grade`, `ui/components.expected`, `tests/test_grading`.
- → `compute` (`validate`, `_eval`, `_ns`), `textnorm` (`SUP`, `SUB`, `normalize_for_match`), `rapidfuzz`, `sympy`.

**İçindekiler**
- [`to_sympy(text)`](../src/grading.py#L33): okul gösterimini SymPy ifadesine çevirir.
  - `9!` → `factorial(9)`
  - `C(n, 2)` ve `(n choose 2)` → `binomial(n, 2)`; `P(n, 2)` → `ff(n, 2)`
  - `2ⁿ`, `2^n` → `2**n`; `√x` → `sqrt(x)`; `2,5` → `2.5`
  - Örtük çarpma: `2n` → `2*n`, `n(n-1)` → `n*(n-1)`
  - Sondaki "tane, adet, farklı şekilde" gibi kelimeler atılır. Başka kelime varsa metin cevaptır, `None` döner.
- [`_bounded(expr)`](../src/grading.py#L67): öğrencinin girdisi **güvenilmez girdi**dir. Beyaz listeye ek olarak büyüklük sınırları uygulanır: sayı ≤10⁷, üs küçük ya da tek sembol, iç içe üs yok, faktöriyel ≤170. `9^9^9` sistemi kilitleyemez.
- [`safe_value(text)`](../src/grading.py#L91): çevir → `compute.validate` → `_bounded` → hesapla. Herhangi bir adım başarısızsa `None`.
- [`same_value(a, b)`](../src/grading.py#L103): sembolik ya da sayısal eşitlik. `expand_func` sayesinde `binomial(n, 2)*2` ile `n*(n-1)` eşit çıkar.
- [`grade_short(answer, expected, computed_value)`](../src/grading.py#L113):
  1. Hedef değer (kodun hesapladığı değer, yoksa beklenen cevabın değeri) hesaplanabiliyorsa öğrencinin cevabını da hesapla ve karşılaştır. "30240 farklı kelime" gibi cevaplarda içindeki tek sayı kullanılır.
  2. Değilse metin karşılaştırması: Türkçe ek-fiil atılır (`tanımsızdır` = `tanımsız`). Eşitlik ya da benzerlik ≥90 doğrudur. Kelime kümesi eşleşmesi yalnızca uzunluklar yakınsa sayılır: `böcek` ≠ `Faydalı böcekler (parazitoid)`.

Testler: [`tests/test_grading.py`](../tests/test_grading.py) (29 durum, güvenlik girdileri dahil).

---

## `src/review_store.py` — soru kimliği, kararlar, kanıt işaretleme (232 satır)

**Ne işe yarar?** Üç iş yapar:
1. Soru kimliğini hesaplar ve soru setlerini listeler.
2. Öğretmenin onay/red kararlarını kaydeder.
3. Kanıt alıntısını PDF sayfasında **sarıyla işaretleyip** görüntü olarak verir.

Arayüzden bağımsız tutulmuştur; testler ve değerlendirme de kullanabilir.

**Bağlantılar**
- ← `ui/data`, `ui/pages/review`, `request`, `pipeline.merge_existing`, `qualify`, `tests/test_pipeline`.
- → `textnorm.normalize_for_match`, `pymupdf`, `config`.
- 💾 Okur/yazar: `data/reviews.jsonl`. Okur: PDF'ler, `chunks.jsonl`, soru setleri.

**İçindekiler**
- `FLAG_TR`: uyarı kodu → Türkçe açıklama (İnceleme sayfası gösterir).
- `REJECT_REASONS`: öğretmenin seçebileceği red nedenleri.
- [`question_id(item)`](../src/review_store.py#L36): `sha1(model|soru metni)`'nin ilk 12 karakteri. **Projenin en kritik tek satırı**: bütün kayıtlar bu kimliğe bağlı.
- [`question_sets()`](../src/review_store.py#L40): önce `data/questions/*.jsonl`, sonra pilot `_dogrulama.jsonl` dosyaları.
- [`load_set(path)`](../src/review_store.py#L46): seti okuyup her soruya `id` ekler ve etkin zorluğu bindirir (`difficulty.apply`; bölüm 10).
- [`load_chunks()`](../src/review_store.py#L54): kimlik → parça.
- [`decisions()`](../src/review_store.py#L59): soru kimliği → **son** karar. Dosyaya yalnızca eklenir; aynı soru için sonraki karar öncekini geçersiz kılar.
- [`save_decision(item, decision, note, source, reasons)`](../src/review_store.py#L74): kararı sistemin etiketi ve uyarılarıyla birlikte kaydeder. Böylece "doğrulayıcı ile insan ne kadar uyuşuyor?" ölçülebilir.
- **Kanıtı işaretleme zinciri:**
  - [`_pdf_for(doc_stem)`](../src/review_store.py#L85): belge adından PDF dosyasını bulur.
  - [`_page_tokens(page)`](../src/review_store.py#L90): sayfanın kelimeleri ve normalize belirteçleri. Satır sonunda bölünmüş kelime (`bü-` + `tün`) tek belirteç olur ve iki kelimeyi birden işaretler.
  - [`_same(a, b)`](../src/review_store.py#L106): iki belirteç aynı mı? Türkçe ek farkına tolerans var: kısa olan uzunun başıysa ve uzunluğunun %70'i kadarsa eşit sayılır.
  - [`_align(q, toks)`](../src/review_store.py#L113): **Smith-Waterman yerel hizalama** (biyoinformatikte DNA dizilerini hizalamak için kullanılan dinamik programlama algoritması), kelime düzeyinde. Alıntının kelimelerini sayfanın kelime dizisinde arar; araya giren birkaç kelimeye izin verir (kesir çizgisi, `=` işareti, satır sonu). Eşleşme +2, boşluk −1 puan.
  - [`_highlight_rects(page, quote)`](../src/review_store.py#L138):
    1. Önce `page.search_for` ile birebir arama (harf düzeyinde kesin konum).
    2. Bulamazsa `_align`. Alıntının en az %60'ı eşleşmezse vazgeçer.
    3. Uçlarda başka satıra taşan tek harfleri atar, eşleşen kelimeler arasındaki en çok 3 kelimelik boşluğu da doldurur.
    4. Satır başına bir dikdörtgen döndürür.
  - [`_evidence_clip(page, rects)`](../src/review_store.py#L177): yoğun sayfada (ör. formül posteri) kanıtın çevresini bağlamıyla birlikte kırpar.
  - [`render_evidence(item, chunks, dpi)`](../src/review_store.py#L195): PDF'i **bellekte** açar (dosya değişmez), sarı vurgu notları ekler, PNG üretir. Açıklama metni de döndürür. İşaretlenemediyse nedenini söyler: sayfa görselden okunduysa PDF'te o metin yoktur.
- [`agreement(items_by_id, decs)`](../src/review_store.py#L224): sistem etiketi × insan kararı tablosu. Şu an kullanılmıyor; Rapor sayfası kendi hesabını yapıyor.

---

## `src/export.py` — dışa aktarma (243 satır)

**Ne işe yarar?** Seçilen soruları beş biçime çevirir. Arayüzden bağımsızdır (yalnızca metin üretir):
1. **Moodle XML**: önerilen; en zengin biçim.
2. **GIFT**: Moodle'ın metin biçimi.
3. **Yazdırılabilir sınav kâğıdı** (HTML; tarayıcıda Yazdır → PDF).
4. **CSV** (Excel uyumlu).
5. **JSON**.

**Bağlantılar**
- ← `ui/pages/exam._export`, `ui/pages/bank`.
- → `textnorm.pretty_math`, `topics.topic_map`, `config.doc_name`.

**İçindekiler**
- `TRANSPARENCY`: "Bu soru yapay zekâ ile üretildi; kaynağa bağlandı; farklı bir modelle doğrulandı" notu. YÖK 2024 rehberine uygun şeffaflık için her geri bildirime eklenir.
- [`_pretty`](../src/export.py#L20), [`_doc`](../src/export.py#L25), [`_doc_name`](../src/export.py#L42): gösterim, belge adı ve kısa ad yardımcıları.
- [`_topic(it)`](../src/export.py#L29): sorunun konusu, kanıt sayfasının konu haritasındaki karşılığı. Moodle kategorisi olarak kullanılır.
- [`_source(it)`](../src/export.py#L47): `"Bilgisayar Mimarisi, s.12: “alıntı”"` biçiminde kaynak satırı.
- [`_general_feedback(it)`](../src/export.py#L52): çözüm adımları + kaynak + şeffaflık notu.
- [`_option_feedback(q, i)`](../src/export.py#L59): şık geri bildirimi. Doğru şıkta "Doğru."; yanlış şıkta varsa çeldiricinin temsil ettiği hata (`option_notes`) ve doğru cevap.
- [`_numeric(it)`](../src/export.py#L69): kısa cevaplı hesap sorusunun sayısal değeri ve toleransı. Moodle "sayısal soru" tipi olur; `300` ve `300,0` ikisi de doğru sayılır.
- [`_ordered(items)`](../src/export.py#L82): soruları `$course$/NotaRAG/<belge>/<konu>` kategori yoluna göre sıralar.
- [`_gift_escape`](../src/export.py#L88): GIFT'in özel karakterlerini (`~ = # { } :`) kaçışlar.
- [`to_gift(items)`](../src/export.py#L96): her tip için GIFT sözdizimi (`{=doğru#geri bildirim ~yanlış#...}`).
- [`_cdata_html`](../src/export.py#L123): metni XML içinde güvenle taşımak için `<![CDATA[...]]>`.
- [`to_moodle_xml(items)`](../src/export.py#L131): kategori soruları, `multichoice` / `truefalse` / `numerical` / `shortanswer` tipleri, şık başına geri bildirim ve etiketler (`zorluk-kolay`, `hesap`, `dogrulandi`).
- [`to_csv(items)`](../src/export.py#L179): başa BOM (`﻿`) eklenir; Excel Türkçe karakterleri doğru açsın diye.
- [`to_json(items)`](../src/export.py#L194): ham veri.
- [`to_exam_html(items, title, with_key)`](../src/export.py#L199): sınav kâğıdı. Cevap anahtarı, kanıtlar ve çözümler **ayrı sayfada** (`break-before: page`); sonda "öğretmen gözden geçirmeden not vermek için kullanılmamalı" uyarısı var.

---

## `src/requote.py` — kaynak metin düzelince soru bakımı (114 satır)

**Ne işe yarar?** Ayrıştırıcı düzeltildiğinde (ör. üst simgeler artık `2ⁿ` diye okunuyor) eski soruların kanıt alıntıları eski bozuk yazımı taşır. `python -m src.requote [--yaz]` bunları onarır. LLM kullanmaz. `--yaz` verilmezse yalnızca rapor basar.

**Bağlantılar**
- → `checks.check`, `schema.Question`, `textnorm`.
- 💾 Okur/yazar: `data/questions/*.jsonl`, `data/pilot/*_dogrulama.jsonl`.

**İçindekiler**
- [`_words(text)`](../src/requote.py#L29): metnin normalize kelimeleri ve her birinin orijinal metindeki konumu.
- [`requote(quote, texts)`](../src/requote.py#L38): alıntının güncel metindeki **birebir** karşılığını bulur (normalize kelime dizisi eşleşmesi) ve orijinal yazımla döndürür: `bü-tün` → `bütün`, `2n` → `2ⁿ`.
- [`degraded_forms(texts)`](../src/requote.py#L52): kaynakta **üslü** yazılan ifadelerin düz halleri (`2ⁿ` → `2n`, `1.2⁴` → `1.24`).
- [`main(write)`](../src/requote.py#L64): her soru için:
  1. Alıntıyı yeniden alır.
  2. Kod kontrolünü güncel metinle yeniden çalıştırır. Sonradan eklenen kurallar (soru yazım hataları) eski sorulara da uygulanır.
  3. Soru ya da şık bozuk yazımı içeriyorsa (`'2n'`) soruyu `needs_review`'a düşürür; model `2·n` diye okumuş olabilir.

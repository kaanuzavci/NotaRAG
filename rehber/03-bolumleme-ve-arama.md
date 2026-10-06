# 3. Bölümleme ve arama (RAG'in "R"si)

[← 2. PDF okuma](02-pdf-okuma.md) · [Ana sayfa](README.md) · Sonraki: [4. LLM kapısı →](04-llm-kapisi.md)

Okunan sayfalar burada iki şeye dönüşür:
- **Parça (chunk):** aramanın birimi. Genelde bir sayfa; uzun sayfalar bölünür.
- **Bölüm (section):** aynı ya da benzer başlıklı ardışık sayfalar. Soru üretiminin birimi.

Parçalar vektöre çevrilip ChromaDB'ye konur; sınav isteğinde konu adıyla bu veritabanında arama yapılır.

---

## Önce kavramlar: embedding, kosinüs, ChromaDB, BM25, RRF

- **Embedding:** bir metni sabit uzunlukta bir sayı dizisine (vektöre) çeviren model. Burada `gemini-embedding-001` kullanılıyor ve vektör 768 boyutlu. Anlamca yakın metinlerin vektörleri birbirine yakın düşer.
  - Bu model çok dillidir: Türkçe "çaprazlama" ile İngilizce "crossover" vektörleri birbirine yakındır (benzerlik 0,89).
- **Kosinüs benzerliği / mesafesi:** iki vektörün arasındaki açıya bakar. Benzerlik 1'e yakınsa metinler çok benzer. ChromaDB **mesafe** döndürür: `1 − benzerlik`, yani küçük olan daha yakındır.
- **ChromaDB:** vektörleri diskte saklayan ve "şu vektöre en yakın 12 parçayı ver" sorusunu hızlı cevaplayan yerel bir **vektör veritabanı**. Ödevin istediği teknolojilerden biri.
- **Dense (yoğun) arama:** sorguyu da vektöre çevirip en yakın parçaları bulmak. Anlam üzerinden çalışır; diller arası da çalışır.
- **BM25:** klasik kelime eşleştirmeli arama. Sorgudaki kelimeler parçada geçiyor mu, nadir kelimeler daha değerli. Dil bağımsız değildir.
- **RRF (Reciprocal Rank Fusion):** iki sıralamayı birleştirir. Her parçanın puanı, her listedeki sırası için `1 / (60 + sıra + 1)` değerlerinin toplamıdır.

**Ölçüm sonucu ([`eval/sonuclar_retrieval.md`](../eval/sonuclar_retrieval.md)):** Dense isabet@5 %100 çıktı, hibrit %85, BM25 %72. Türkçe sorgu İngilizce slaytta aranınca BM25 yanlış dildeki belgeyi öne çıkarıyor. Bu yüzden **varsayılan dense**; hibrit ve BM25 kodda yalnızca karşılaştırma için duruyor.

---

## `src/chunking/chunker.py` — sayfalardan parça ve bölüme (105 satır)

**Ne işe yarar?** Bir belgenin ayrıştırılmış sayfalarından üç liste üretir: parçalar, bölümler ve dizine alınmayan sayfalar (gerekçesiyle).

**Bağlantılar**
- ← `chunking/__main__`.
- → `textnorm.normalize_for_match`, `rapidfuzz` (başlık benzerliği).

**Sabitler:**
- `MAX_CHUNK_CHARS = 1500`: bundan uzun sayfa bölünür; parçaların hedef boyutu 1000.
- `MAX_SECTION_CHARS = 4000`: bölüm bundan uzunsa üretimde parça parça verilir.
- `HEADING_MERGE_RATIO = 90`: başlık benzerliği ≥%90 ise aynı bölüm sayılır.
- `_REFERENCES`: "Kaynakça", "References" gibi başlıklar.

**İçindekiler**
- [`_same_section(a, b)`](../src/chunking/chunker.py#L25): iki başlık aynı bölüm mü?
  - Eşit, biri diğerinin başı (`"Organik Tarım"` ⊂ `"Organik Tarım suyu korur"`) ya da çok benzer (`"Simple Genetic Algorithms"` ≈ `"...Algorithm"`) ise evet.
- [`_split_long(text)`](../src/chunking/chunker.py#L33): 1500 karakterden uzun metni boş satır ya da Markdown başlığı sınırlarından ~1000 karakterlik parçalara böler.
- [`_skip_reason(page, section_title)`](../src/chunking/chunker.py#L47): sayfa dizine alınmayacaksa nedenini döndürür: `"kapak"`, `"içindekiler"`, `"kaynakça"`, `"boş"`. Bu sayfalardan soru çıkmaz; "künye sorusu" üretilmesinin ilk engeli budur.
- [`chunk_document(parsed)`](../src/chunking/chunker.py#L59): ana fonksiyon. Sayfaları sırayla gezer:
  1. Başlık bir öncekinden farklıysa yeni bölüm açar (bölüm kimliği `<belge>:sec03`).
  2. Atlanacak sayfayı `skipped` listesine yazar.
  3. Sayfa metnini böler ve her parça için bir sözlük kurar:

     ```jsonc
     {"id": "english:p052:1",        // belge : p + 3 haneli sayfa : parça sırası
      "doc": "english", "doc_title": "...", "page": 52, "section_id": "english:sec07",
      "heading": "Binary encoding", "text": "...",
      "embed_text": "Binary encoding\n...",   // başlık metinde yoksa başa eklenir → aramada başlık da sayılır
      "language": "en",                       // BELGENİN dili (sayfanın değil)
      "source": "text|vision", "vision_model": null,
      "pending_vision": false,                // görsel okuma bekliyorsa: aranır ama üretimde kullanılmaz
      "hash": "a1b2..."}                      // embed_text'in özeti
     ```
  4. Her bölüm için sayfa etiketli birleşik metni (`[s.12] ...`), karakter sayısını ve `too_long` bayrağını hesaplar.

## `src/chunking/__main__.py` — `python -m src.chunking` (36 satır)

- [`main()`](../src/chunking/__main__.py#L17): `data/parsed/*.json` dosyalarının **hepsini** parçalar. `chunks.jsonl`, `sections.jsonl` ve `skipped.jsonl` dosyalarını **baştan** yazar, belge başına özet basar. Yereldir, saniyeler sürer.
  - `pipeline.run` bunu 3. adımda çağırır. Yeni bir belge eklenince eski belgeler de yeniden parçalanır; aynı metin aynı parça kimliğini ürettiği için bir şey kaybolmaz.
- [`_write_jsonl(path, rows)`](../src/chunking/__main__.py#L13): liste → JSONL dosyası.

---

## `src/retrieval/embedder.py` — metni vektöre çevirme + önbellek (92 satır)

**Ne işe yarar?** Gemini embedding API'siyle metinleri 768 boyutlu vektörlere çevirir ve her vektörü diske kaydeder. Aynı metin bir daha gönderilmez.

**Bağlantılar**
- ← `retrieval/index.py`.
- → `google.genai`, `numpy`, `config`.
- 💾 Okur/yazar: `data/embeddings/cache_gemini-embedding-001_768.npz`.

**Modelin gerekçesi (dosyanın başındaki açıklama):**
- `gemini-embedding-2` bir metin listesini tek vektöre birleştiriyor. `001` tek istekte 100 metni ayrı ayrı alıyor.
- 768 boyut, 3072 boyuta göre 4 kat daha az veri indiriyor (mobil internet).

**İçindekiler**
- [`_key(text, task)`](../src/retrieval/embedder.py#L29): `sha1(model|boyut|görev|metin)`. Önbellek anahtarıdır. Metin bir harf değişirse anahtar da değişir ve yeniden gönderilir.
- [`Embedder.__init__`](../src/retrieval/embedder.py#L34): önbellek dosyasını belleğe yükler (`np.load`).
- [`_save()`](../src/retrieval/embedder.py#L45): önbelleği sıkıştırılmış `.npz` olarak yazar.
- [`_call(texts, task)`](../src/retrieval/embedder.py#L50): API'yi çağırır.
  - Ücretsiz katman dakikada 100 metin kabul ediyor. "PerMinute" hatasında mesajdaki süre kadar bekleyip en çok 3 kez dener.
  - Gelen vektörleri **normalize eder** (uzunluğu 1 yapar); boyut küçültülünce Gemini normalize etmeden gönderiyor.
- [`missing(texts, task)`](../src/retrieval/embedder.py#L79): önbellekte olmayan metinler.
- [`embed(texts, task)`](../src/retrieval/embedder.py#L82): eksikleri 100'lük gruplarla alır, her gruptan sonra kaydeder ve bütün vektörleri sırasıyla döndürür.
- [`embed_query(text)`](../src/retrieval/embedder.py#L91): sorgu için tek vektör.
  - Görev türü `RETRIEVAL_QUERY`. Parçalar `RETRIEVAL_DOCUMENT` ile gömülür; Gemini sorgu ve belgeyi farklı biçimde gömerek aramayı iyileştiriyor.

---

## `src/retrieval/index.py` — ChromaDB dizini ve arama (103 satır)

**Ne işe yarar?** Parçaları ChromaDB'ye koyar ve dört yöntemle arama yapar: dense (varsayılan), BM25 (F5 köklemeli), köklemesiz BM25 ve hibrit (RRF).

**Bağlantılar**
- ← `pipeline` (build), `request` (`_index` ile; bkz. bölüm 7), `retrieval/__main__`, `eval/evaluate_retrieval`.
- → `embedder`, `chromadb`, `rank_bm25`, `textnorm` (`f5_tokens`, `detect_language`).
- 💾 Okur: `data/chunks/chunks.jsonl`. Okur/yazar: `data/chroma/`.

**İçindekiler**
- [`load_chunks()`](../src/retrieval/index.py#L24): `chunks.jsonl` → liste.
- [`Index.__init__`](../src/retrieval/index.py#L30): parçaları ve kimlik → parça sözlüğünü (`by_id`) yükler, `Embedder`'ı kurar.
  - `chromadb.PersistentClient(path="data/chroma")` diskteki veritabanını açar.
  - `anonymized_telemetry=False`: Chroma kullanım verisi göndermesin.
- [`build()`](../src/retrieval/index.py#L38):
  1. Bütün parçaların `embed_text`'ini gömer; çoğu önbellekten gelir.
  2. `chunks` koleksiyonunu **silip yeniden** oluşturur. Kosinüs mesafesi kullanılır; `embedding_function=None` ile vektörü Chroma'ya biz veririz, Chroma kendi modelini indirmez.
  3. Her parçayı kimliği, vektörü, metni ve metadata'sıyla (belge, sayfa, bölüm, dil, kaynak) ekler.
  4. Kaç parça, kaçının yeni gömüldüğü bilgisini döndürür.
- [`_bm25_f5`](../src/retrieval/index.py#L56) / [`_bm25_plain`](../src/retrieval/index.py#L60) (`@cached_property`): BM25 dizinleri ilk kullanımda kurulur. Biri ilk 5 harfle, diğeri tam kelimeyle (ablasyon için).
- [`dense(query, n, where)`](../src/retrieval/index.py#L64): sorgu vektörüyle Chroma'ya sorar. `where={"doc": ...}` ile belge süzgeci verilebilir. Parça kimliklerini döndürür.
- [`bm25(query, n, f5, docs)`](../src/retrieval/index.py#L69): bütün parçaları puanlar, sıfırdan büyük olanları sıralar.
- [`search(query, k, mode, doc, lang_rule)`](../src/retrieval/index.py#L80): tek giriş noktası.
  - `mode="hybrid"` iken **dil kuralı** uygulanır: sorgunun dili parçanın dilinden farklıysa o parça için BM25 yok sayılır.
  - Sonuçlar RRF ile birleştirilir; parça sözlükleri döndürülür.

**Dikkat:** Sınav isteğindeki asıl arama ([`request.retrieve`](../src/request.py#L52)) bu sınıfın `search` metodunu kullanmaz. Chroma koleksiyonunu doğrudan sorgular, çünkü **mesafeleri** de istiyor: "en iyi eşleşmeden 0,08'den uzak olanları alma" kuralı için. `Index`'ten yalnızca bağlantıyı, embedder'ı ve `by_id`'yi alır.

## `src/retrieval/__main__.py` — `python -m src.retrieval` (27 satır)

- [`main()`](../src/retrieval/__main__.py#L11):
  - `build`: eksik embedding sayısını ve tahmini indirme boyutunu basar, sonra dizini kurar.
  - `search "sorgu" [mod]`: ilk 5 sonucu belge, sayfa, başlık ve metnin başıyla gösterir. Aramayı denemek için en kolay yol budur (sorgunun embedding'i için 1 küçük API isteği).

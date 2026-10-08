# RAG Tabanlı Ders Dokümanlarından Soru ve Cevap Üretim Sistemi

## 1. Amaç

Ders dokümanlarını (PDF, slayt, ders notu) girdi olarak alıp, bu dokümanlara **sadık kalarak** (halüsinasyon üretmeden) soru-cevap çiftleri üreten bir RAG (Retrieval-Augmented Generation) sistemi. Kullanıcı dokümana soru sormaz; sistem dokümandan soru **ve** cevabını üretir.

Hedefimiz "her soruyu doğru üreten" bir sistem değil; **hangi sorusuna güvenilebileceğini bilen** bir sistem. Literatür (bkz. LITERATURE.md §3) doğrulamasız üretilen soruların ciddi oranda insan düzeltmesi gerektirdiğini gösteriyor. Bu yüzden sistemin asıl işi, iyi soruyu kötü sorudan ayırmak ve insan incelemesini ucuzlatmak.

## 2. Kapsam

**Çekirdek gereksinim (ödev tanımı):**
- Ders dokümanı yükleme ve işleme (PDF öncelikli)
- Dokümanların vektör veritabanında indekslenmesi (retrieval)
- Dokümana dayalı soru ve cevap üretimi (çoktan seçmeli, kısa cevap, doğru/yanlış), her biri kaynak sayfa ve kanıt alıntısıyla
- Konu/bölüm seçerek üretim (ör. "Bölüm 3'ten 10 soru")

**Farklılaştırıcı özellikler (öncelik sırasıyla):**
1. Soru tipine özel doğrulama katmanı (kanıt alıntısı kontrolü + tipe göre kör doğrulama, farklı model ailesiyle, bkz. §4)
2. Hesap soruları: model cevabı veren bir SymPy ifadesi de yazar; kod ayrı süreçte yeniden hesaplar, farklı aileden model soruyu kör çözer
3. Sınav deneyimi: seçimle sınav isteği (belge · konu · zorluk · tip · sayı), odak modunda çözme, kademeli ipucu, sonuç grafikleri, yanlışlarda çözüm + kaynak sayfa, kısa cevapta değer karşılaştırması (`src/grading.py`)
4. Kanıt vurgulamalı inceleme: her sorunun kanıtı PDF sayfası üzerinde işaretli gösterilir; onay/red tek tıkla yapılır
5. Öğrenci geri bildirimi: "hatalı bildir", kısa cevap itirazı, soru başına doğru oranı (madde analizi)
6. Dışa aktarma: Moodle XML (konu kategorileri, şık geri bildirimi, sayısal soru), GIFT, yazdırılabilir sınav kâğıdı, CSV
7. Ölçülmüş retrieval kararı: dense (Gemini embedding) — hibrit ve 5 harf köklemeli BM25 ile karşılaştırıldı, varsayılan dense (bkz. §7 ve `eval/sonuclar_retrieval.md`)
8. Çıktı dilini belge dilinden bağımsız seçebilme (ör. İngilizce PDF → Türkçe soru)
9. Görsel/taranmış PDF desteği (Gemini, yedek qwen görsel okuma) ve Türkçe metin düzeltmeleri (üs/alt simge, satır sonu tiresi)

**Kapsam dışı:**
- Model eğitimi / fine-tuning (hazır embedding + LLM API'leri kullanılıyor)
- Ders dokümanı dışı genel bilgi ile soru/cevap üretimi
- Kullanıcının dokümana serbest soru sorduğu chat modu (şimdilik kapsam dışı; mimari ileride eklenmesine engel değil)
- El yazısı ve taranmış (yalnızca görüntü) ders notları (şimdilik; odak metinli PDF — kullanıcı kararı 2026-10-07). Taranmış sayfalar algılanıp görsel okumaya ayrılır, ama bu belge türleri ayrıca denenmez

## 3. Mimari

```
   PDF girişi
       ↓
 ┌──────────────────────────┐
 │ Ayrıştırma               │  PyMuPDF; düşük kaliteli sayfada Gemini görsel fallback
 │ + belge dili tespiti     │  Türkçe metin normalizasyonu (bkz. §4.3)
 └────────────┬─────────────┘
              ↓
 ┌──────────────────────────┐
 │ Başlık/bölüm duyarlı     │  metadata: dosya, sayfa, başlık yolu, dil
 │ chunking (küçük chunk +  │  "küçük chunk ile bul, bölümün tamamını LLM'e ver"
 │ üst bölüm bağlantısı)    │
 └────────────┬─────────────┘
              ↓
 ┌──────────────────────────┐
 │ İndeksleme + konu haritası│ Dense: Gemini Embedding → ChromaDB (ölçüm sonrası varsayılan)
 │                          │  Konu haritası: belge başına 1 istek, seçilebilir konular (PROMPTS §7)
 └────────────┬─────────────┘
              ↓
 SINAV İSTEĞİ (kullanıcı seçer: belge · konu · zorluk · tip · sayı — serbest metin yok)
              ↓
 Konu adı = arama sorgusu → dense arama → konunun geçtiği sayfalar   (RAG'in "R"si)
              ↓
 Havuz: o sayfalara bağlı, doğrulanmış soru var mı? ──evet──→ anında (0 token)
              │ eksik
              ↓
 Hedefli üretim yalnızca bulunan sayfalardan (Gemini, JSON şema, seçilen zorluk; hesap: §2c)
              ↓
 ┌──────────────────────────┐
 │ Doğrulama (çalışma anı)  │  1) kod: şema, kanıt alıntısı, şık karıştırma, ipucu; hesapta SymPy
 │                          │  2) farklı model ailesinde kör doğrulama (tipe özel; hesapta kör çözüm)
 └────────────┬─────────────┘
              ↓
   verified → havuza ve sınava · needs_review / rejected → yalnızca İnceleme'de
              ↓
   Sınav: çöz (puan, zayıf konular, kaynak sayfa) ya da yazdır / Moodle'a aktar
   Geri bildirim: öğrenci "hatalı" bildirimi + soru başına doğru oranı (madde analizi) → İnceleme
              ↓
   Değerlendirme (çevrimdışı): retrieval metrikleri, doğrulayıcı duyarlılığı, insan etiketleri
```

**Retrieval'ın rolleri:** (1) seçilen konunun anlatıldığı sayfaları bulur — üretim bağlamı yalnızca bunlardır, ayrıca hazır havuzdan hangi soruların o konuya ait olduğunu belirler; (2) belgeler arası çalışır: Türkçe bir konu seçildiğinde İngilizce slayttaki ilgili sayfalar da bulunur (dense, diller arası); (3) değerlendirmede ölçülür (145 sorgu, isabet@5 %98,6). Tekrar eden soru tespiti şimdilik metin benzerliğiyle yapılıyor (`mark_duplicates`), embedding ile değil.

**Neden serbest metin değil, seçim:** Kullanıcının serbest yazdığı istek anlamsız ya da belgede olmayan bir konu olabilir; hazır konu listesi (konu haritası) hem bunu engeller hem de belgenin neyi kapsadığını gösterir. Konular belge başına bir kez çıkarılır ve önbelleğe alınır.

**Neden havuz + hedefli üretim (tamamen anlık üretim değil):** Bir sorunun doğrulanması dakikalar sürer ve kota harcar; sınav haftasında herkesin aynı anda yeni soru istemesi kota sorununu büyütür. Havuz bir önbellek gibi çalışır: bir konu bir kez üretilip doğrulandıktan sonra o konudan gelen istekler anında ve token harcamadan karşılanır; kota yalnızca yeni konu/zorluk birleşimleri için kullanılır.

## 4. Temel Tasarım Kararları

### 4.1 RAGAS nerede kullanılıyor, nerede kullanılmıyor
LITERATURE.md §4'teki "kendi doğrulamamızı yazmak yerine RAGAS kullanalım" önerisini **değerlendirme katmanında** uyguluyoruz, çalışma anındaki doğrulama katmanında değil. Gerekçe:
- RAGAS bir **değerlendirme** aracı: tek bir soru için çok sayıda LLM çağrısı yapıyor. Ücretsiz API kotalarında her üretilen soruya uygulanamaz.
- RAGAS faithfulness, uzun cevapları iddialara bölerek çalışıyor. Quiz cevapları ise "B", "Yanlış", "2 adet" gibi kısa ifadeler; bölünecek bir iddia yok. Bu yüzden RAGAS'a vermeden önce soru+cevabı tek bir **önermeye** dönüştürüyoruz (PROMPTS.md §5).
- RAGAS çoktan seçmeli soruya özgü hataları göremiyor: ikinci bir doğru şık bulunması, cevabın şık uzunluğundan tahmin edilebilmesi gibi. Bu hataları bizim tipe özel kontrollerimiz yakalıyor.
- Kanıt alıntısı kontrolü deterministik ve ücretsiz. Hiçbir LLM tabanlı metrik onun yerini tutmuyor.

### 4.2 Soru tipine özel doğrulama
| Tip | Kör doğrulama | Geçme koşulu |
|---|---|---|
| Çoktan seçmeli | Doğrulayıcı soruyu **karıştırılmış şıklarla** ve cevap anahtarı olmadan görür, tek bir şık seçer | Doğru şıkkı seçmesi ve başka hiçbir şıkkın bağlamca desteklenmemesi |
| Doğru/Yanlış | 3 sınıflı çıkarım: SUPPORTED / CONTRADICTED / NOT_IN_CONTEXT | "Doğru" ise SUPPORTED, "Yanlış" ise **CONTRADICTED** olmalı. Bağlamda hiç geçmeyen bir ifade "yanlış" sayılmaz, sorulamaz |
| Kısa cevap | Doğrulayıcı cevabı kör üretir | Anlamsal eşleşme (embedding + gerekirse LLM hakem) |
| Hesap sorusu (§2c) | Önce **kod**: modelin yazdığı SymPy ifadesi beyaz listeden geçip ayrı süreçte yeniden hesaplanır; sonra doğrulayıcı soruyu **yalnızca metinden kör çözer** (§4e) | Anahtar = kodun sonucu, başka hiçbir şık o sonuca eşit değil, şık metni değeriyle tutarlı **ve** kör çözüm aynı şıkkı/sonucu buluyor |

Hesap sorularında kanıt ikiye ayrılır: **kural** notta geçmelidir (birebir alıntı), **sonuç** kodla doğrulanır. Sayılar yeni olduğu için "cevap metinde geçiyor" koşulu burada anlamsızdır. Kod yalnızca modelin kendi ifadesini doğrular; sorunun metninin gerçekten o ifadeyi sorduğunu ise kör çözüm doğrular (ör. metin kombinasyon sorarken ifade permütasyon hesaplıyorsa).

Ek olarak **bağlamsız tahmin testi** yapılır: soru ve şıklar bağlam verilmeden sorulur. Bağlamsız da doğru cevaplanan sorular ya genel bilgi ölçüyordur ya da cevabı ele veren bir ipucu taşıyordur. Bu sorular reddedilmez, ancak "dokümana bağlılığı düşük" olarak işaretlenir.

### 4.3 Türkçe'ye özgü mühendislik ayrıntıları
- **Büyük/küçük harf:** Python'un `lower()` fonksiyonu "I" harfini "i" yapar, Türkçe'de doğrusu "ı". Kanıt kontrolü ve BM25'te Türkçe'ye özel dönüşüm kullanılır.
- **PDF artıkları:** satır sonu tirelemesi ("bilgisa-\nyar"), yumuşak tire (U+00AD), bitişik harfler (ﬁ) ve tırnak türleri normalize edilir. Bu yapılmazsa doğru alıntılar da birebir eşleşme kontrolünden geçemez.
- **BM25 için kök bulma:** kelimenin ilk 5 harfini almak (F5), Türkçe bilgi erişiminde kök bulucularla yarışabilir sonuç veriyor (Can vd., 2008). Bunun için ek kütüphane ya da model gerekmiyor.
- **Diller arası sorgu:** sorgu dili ile belge dili farklıysa (Türkçe soru, İngilizce PDF) BM25 işe yaramaz. Bu durumda füzyon yalnızca dense sonuçlarla yapılır.

### 4.4 Kota mimarisi: kota hızı etkiler, kaliteyi değil

Ücretsiz API'lerin sınırları kaçınılmaz: Groq model başına günde 200 bin token (kayan 24 saat), Gemini model başına günde
20 istek (Pasifik gece yarısı = 10:00 TR), OpenRouter ücretsiz modeller günde 50 istek (03:00 TR).
Tasarım ilkesi: **kota dolduğunda sistem yavaşlar ama kaliteden ödün vermez ve çökmez.**

1. **Kalite kapısı** (`src/llm/models.py` → `APPROVED` / `CANDIDATES`): bir model bir role ancak o rolün kalite testini geçince
   eklenir; her onayın yanında kanıtı yazılıdır (ör. doğrulayıcı: duyarlılık testi 17/17). Kota dolunca sistem onaysız bir
   modele **sessizce geçmez**; bir deneyde bunun sonucu bozduğunu yaşadık. Aday onayı: `python -m src.qualify <model>`.
2. **Roller ve zincirler** (2026-10-05): görsel okuma Gemini 2.5 → 3.5 Flash → qwen; toplu üretim ve konu haritası Gemini 3.8 /
   3.5 Flash; birim başına üretim (yedek) qwen; doğrulama gpt-oss-120b → gpt-oss-20b → Nemotron 3 Ultra (OpenRouter) → qwen
   (yalnızca qwen'in üretmediği sorular); hesap kör çözümü gpt-oss + Nemotron. **Aile kuralı:** doğrulayıcı üreticiden farklı ailedendir.
3. **İsraf yok:** her yanıt önbellekte; gerçek token kullanımı API'den okunur (Groq'un bildirdiği kullanımla eşitlenir);
   havuzdaki sorunun tekrarı doğrulamaya gönderilmez; bilgi amaçlı ek testler (§6/§6b) üretim akışında kapalı.
4. **Kuyruk:** `python -m src.pipeline "<pdf>"` tüm adımları çalıştırır; kota dolunca sağlayıcının söylediği süre kadar bekler
   ve kaldığı yerden devam eder. Yeniden çalıştırma **ekler, silmez** (doğrulanmış sorular ve onlara bağlı kayıtlar korunur).
   `python -m src.llm.capacity "<belge>"` kalan bütçeyi ve bir belgenin maliyetini gösterir.
5. **Havuz:** sınav istekleri önce doğrulanmış havuzdan karşılanır (0 token); kota yalnızca yeni konu/zorluk birleşimine harcanır.
6. **Ölçülen darboğaz ve plan:** Groq token bütçesini görsel okuma + üretim + doğrulama paylaşıyor; Gemini'nin 20 isteğini
   görsel okuma ile toplu üretim paylaşıyor. Doğrulanmış soru başına ~4.500 token. Seçenekler ve karar (Google Cloud deneme
   kredisiyle Vertex AI, 2026-10-12'den teslime kadar): ROADMAP "Kota — kök çözüm analizi". Ücretli katman yalnızca kullanıcı kararıyla.

## 5. Teknoloji Seçimleri

| Katman | Seçim | Gerekçe |
|---|---|---|
| Python | 3.11 sanal ortam (venv) | Bilgisayardaki pip önbelleğinde 3.11 wheel'leri var; 3.14 için bazı paketlerin (onnxruntime vb.) hazır wheel'i olmayabilir |
| PDF ayrıştırma | PyMuPDF | Hızlı ve yerel; `search_for` ile kanıtın sayfadaki konumunu bulup vurgulayabiliyor |
| Görsel/OCR fallback | Gemini 2.5 / 3.5 Flash → Groq `qwen3.8-27b` | Gemini istek sınırlı (20/gün/model), böylece qwen'in token bütçesi üretime/doğrulamaya kalır; qwen Groq'ta görüntü kabul eden tek model. Tablolar önce işlemcide (`find_tables`) çıkarılır, GPU kullanılmaz |
| Embedding (ana) | `gemini-embedding-001`, 768 boyut (API) | Çok dilli; model indirmek gerekmiyor. Toplu istek destekliyor (`gemini-embedding-2` listeyi tek vektöre birleştiriyor). 768 boyut, 3072'ye göre indirmeyi 4 kat azaltıyor |
| Embedding (deney) | bge-m3 / Türkçe'ye özel model, yerel GPU | Yapılmayacak: kullanıcı tercihi dizüstünde GPU iş yükü yok (yalnızca açık istekle) |
| Vektör DB | ChromaDB (yerel, dosya tabanlı) | Ödev "vektör veritabanı" istiyor. Embedding'i biz veriyoruz, böylece Chroma kendi varsayılan modelini indirmiyor |
| Sparse retrieval | rank-bm25 + F5 kökleme (yalnızca karşılaştırma) | 68 sorguluk değerlendirmede dense'ten geride kaldı (isabet@5 %72'ye %100) |
| Füzyon | Reciprocal Rank Fusion (yalnızca karşılaştırma) | TR sorgu → EN slaytta zarar verdi (isabet@5 %58'e %100); varsayılan değil |
| LLM (üretim) | Gemini 3.8 / 3.5 Flash, toplu (bir istekte bir grubun tüm birimleri); yedek: Groq `qwen3.8-27b` birim başına | Aynı 12 birimde toplu Gemini %92-100, qwen %92 doğrulandı; Gemini daha çeşitli ve zor soru üretiyor. Hesap soruları (§2c) yalnızca Gemini'de (yedek yok) |
| Doğrulama | gpt-oss-120b / 20b (Groq), Nemotron 3 Ultra (OpenRouter ücretsiz), qwen — üreticiden farklı aile | Kendi hatasını görememe riskini azaltır; duyarlılık testleri: 120b 17/17, 20b 20/20, Nemotron 10/10 + hesap 12/12, qwen 19/19 |
| LLM düzenleme | Kendi yönlendiricimiz (`src/llm/router.py` + `ledger.py`); LangChain kullanılmıyor | Ödevin teknoloji listesinde var, ama asıl zorluk ücretsiz kota ve kalite kuralları: günlük istek/token kotası süreçler arasında ortak defterde izlenir (LangChain'in hız sınırlayıcısı süreç içi ve saniyelik), kota dolunca zayıf modele geçilmez (LangChain `with_fallbacks` sıradaki modele geçer), doğrulayıcı üreticiden farklı aileden. PDF için PyMuPDF zaten doğrudan gerekiyordu (sayfa kalitesi, kanıt vurgulama), Chroma doğrudan kullanılıyor → LangChain yeni yetenek eklemiyor (karar 2026-10-07) |
| Hesap kontrolü | SymPy (AST beyaz listesi, ayrı süreçte 10 sn sınırı) | Model kendi hesabını ifade olarak yazar; kod yeniden hesaplar (`src/generation/compute.py`) |
| Öğrenci cevabı puanlama | SymPy değer karşılaştırması + sıkı metin eşleşmesi (`src/grading.py`) | '30240' = '9!/(3!·2!)'; '2' ≠ '(n choose 2)·2'; güvenilmez girdi için büyüklük sınırları |
| Bulanık eşleşme | rapidfuzz | Kanıt alıntısı için "neredeyse birebir" eşleşme |
| Değerlendirme | Kendi betikleri (`eval/`); RAGAS planlı | Retrieval ablasyonu, doğrulayıcı duyarlılığı, hesap kontrolü, toplu üretim, Bloom deneyi |
| Arayüz | Streamlit 1.59 | Hızlı prototipleme; giriş + 9 sayfa (`src/app.py`). Ana sayfanın kart desteleri Streamlit özel bileşeni (CCv2, iframe'siz Shadow DOM): düz HTML tıklamayı Python'a iletemiyor, bağlantı ise sayfayı yeniden yükleyip oturumu düşürüyordu |
| Beyin analizi | Kendi kayıtlarından kural tabanlı (`src/mastery.py`) | Soru → konu bağı konu haritasının sayfalarından (kalıcı); konunun durumu son sınav cevabı ve kart kutusundan; açıklanabilir eşikler, LLM ve kota yok |
| Hesaplar ve belge kaydı | SQLite (`data/app.sqlite`), parola özeti scrypt (Python `hashlib`) | Kurulum ve ek paket gerektirmez, tek dosya; şema adım adım sürümlü (yeni alan var olan veriyi bozmadan eklenir); hesap kimliği giriş yönteminden bağımsız → ileride Google ya da telefonla giriş aynı hesaba bağlanır. Rol yok: herkes aynı sayfaları kullanır, verisi kendisinindir; belge varsayılan gizli, istenirse herkese açılır (geri alınamaz). Sona eklenen geçmiş (çözümler, kartlar) JSONL'de kişi kimliğiyle (`rehber/11`) |

> **Ölçülen ücretsiz kotalar (2026-10-03/05):** Groq'ta bağlayıcı sınır istek sayısı değil, **model başına günde 200.000 token** (kayan 24 saat; ör. qwen için hata mesajı: "tokens per day (TPD): Limit 200000") ve dakikada 8.000 token. Gemini modelleri günde 20 istek/model (Google bazen bizim sayacımız 17'deyken "dolu" diyor), embedding dakikada 100 metin. OpenRouter ücretsiz modelleri günde 50 istek (bir kez 10 $ kredi → 1.000). Kota defteri (`src/llm/ledger.py`) kayan 24 saatlik token kullanımını izler; sınıra takılan model yalnızca sağlayıcının söylediği süre kadar bekletilir.
>
> API kotaları sık değişir. Groq ve Gemini ücretsiz katman limitleri (günlük istek/token) kurulum anında kontrol edilmeli. Üretim, doğrulama ve değerlendirme farklı sağlayıcı ve modellere dağıtılarak tek bir kotanın tükenmesi önlenir.

## 6. Klasör Yapısı

```
NotaRAG/
├── README.md, ROADMAP.md (durum + sıradaki işler), PROMPTS.md (istemler — kod buradan okur!), LITERATURE.md, CLAUDE.md
├── requirements.txt, constraints.txt   # sürümler sabitlenmiş (pip önbelleğiyle uyumlu)
├── .env                      # API anahtarları (repoya girmez; şablon .env.example)
├── src/
│   ├── app.py                # Streamlit girişi: önce giriş (ui/auth.py), sonra 9 sayfa (Ana sayfa varsayılan)
│   ├── pipeline.py           # uçtan uca akış: PDF → … → doğrulanmış sorular (ekleyerek)
│   ├── request.py            # sınav isteği: arama, havuz, hedefli üretim, çözüm kayıtları
│   ├── topics.py             # konu haritası (PROMPTS §7)
│   ├── grading.py            # öğrenci cevabı puanlama (SymPy)
│   ├── export.py             # Moodle XML, GIFT, sınav kâğıdı HTML, CSV
│   ├── textnorm.py           # Türkçe normalizasyon, üs/alt simge, tire, pretty_math
│   ├── review_store.py       # soru kimliği, insan kararları, kanıt vurgulama
│   ├── qualify.py            # aday model yeterlilik testi
│   ├── requote.py            # kanıt alıntılarını güncel metinden yeniden alma
│   ├── prompts.py            # PROMPTS.md'den istem okuma
│   ├── accounts.py           # hesaplar, parola (scrypt), "beni hatırla" oturumları; rol yok
│   ├── library.py            # belge kütüphanesi: kimlik, gizli/herkese açık, aynı belgeyi içerikten tanıma
│   ├── appdb.py              # data/app.sqlite (hesaplar + belge kaydı) ve şema adımları
│   ├── jsonl.py              # kayıt dosyalarına kilitli ekleme
│   ├── mastery.py            # beyin analizi: konu konu ne kadar hâkimsin (kendi kayıtlarından; LLM yok)
│   ├── resume.py             # kaldığın yerden devam et: yarım kart oturumu ve sınav
│   ├── ingestion/            # PDF okuma, görsel okuma, dil tespiti
│   ├── chunking/             # başlık duyarlı bölme + metadata
│   ├── retrieval/            # embedding, Chroma, BM25-F5, RRF
│   ├── generation/           # üretim (generate.py), şema, hesap (compute.py), pilot
│   ├── verification/         # kod kontrolleri, kör doğrulama, duyarlılık testi
│   ├── llm/                  # router (tek kapı), models (kalite kapısı), ledger (kota + önbellek), capacity
│   └── ui/                   # auth.py (giriş), shelf.py (not desteleri, CCv2), docview.py (not penceresi),
│                             # reader.py (tam ekran PDF okuyucu, CCv2), upload.py, quiz.py (sınav deneyimi),
│                             # style.py, components.py, data.py, pages/ (home, profile, documents, exam, cards, …), parts/
├── data/                     # sample_docs/ (PDF'ler), parsed/, chunks/, chroma/, topics/, questions/, requests/,
│                             # jobs/ (arka plan iş günlükleri), review/ (attempts, cards, reports: kişi kimliğiyle),
│                             # llm.sqlite (kota + önbellek), app.sqlite (hesaplar, oturumlar, belge kaydı)
├── eval/                     # değerlendirme betikleri + sonuclar_*.md, yeterlilik/
├── tests/                    # python -m tests.<ad>
├── rehber/                   # dosya dosya kod rehberi (her fonksiyon, bağlantılar, nedenleri)
└── scripts/                  # bekci.py: iş ve kota izleyici · rehber_satirlari.py: rehber bağlantılarını koda hizalar
```

## 7. Değerlendirme Planı

1. **Retrieval:** Hit rate@k ve MRR. Test seti iki kaynaktan oluşur:
   - 20-30 elle yazılmış konu sorgusu ("normalizasyon", "TCP el sıkışması" gibi), her biri doğru bölüm/sayfa ile etiketli. Türkçe sorgu + İngilizce doküman örnekleri de dahil.
   - Sistemin ürettiği ve insanın onayladığı sorular. Bunların kaynak chunk'ı zaten bilindiğinden yüzlerce sorgu bedavaya elde edilir. Kelime örtüşmesi yanlılığını azaltmak için bu soruların Türkçe versiyonları İngilizce dokümanda aranır.
   - Ablasyon: yalnızca dense, yalnızca BM25, BM25-F5 ve hibrit karşılaştırılır.
2. **Üretim kalitesi:**
   - **İnsan kabul oranı:** doğrulama açıkken ve kapalıyken üretilen sorulardan insanın onayladığı oran. *2026-10-04: kullanıcı kararıyla şimdilik yapılmıyor;* yerine doğrulayıcı duyarlılık testleri (kasıtlı bozulmuş sorular) ve öğrenci geri bildirimi (hatalı bildir, madde analizi).
   - **Doğrulayıcı isabeti:** `verified` etiketli soruların kaçının insan tarafından reddedildiği ve kötü soruların kaçının yakalandığı.
   - **RAGAS faithfulness:** önermeye dönüştürülmüş soru+cevap üzerinden hesaplanır.
3. **Yetersiz bağlam testi ("üretmemeyi bilmek"):** içindekiler, kaynakça, kapak, yalnızca görsel içeren sayfalar gibi 10-15 bağlam. Sistemin bunlardan soru uydurmayıp boş liste döndürme oranı ölçülür. "Halüsinasyon üretmiyor" iddiası bu test olmadan kanıtlanamaz.
4. **Sadakat ve bilişsel düzey dengesi (özgün analiz):** Sorular Bloom düzeyine göre (hatırlama, anlama, uygulama) etiketlenir ve faithfulness her düzey için ayrı raporlanır. Beklentimiz şu: dokümana sadakat zorlandıkça sistem hatırlama düzeyine kayacak, uygulama düzeyindeki sorularda ise halüsinasyon artacak. Bu ödünleşimi sayıyla göstermek raporun özgün bulgusu olabilir. *İlk ölçüm (`eval/sonuclar_bloom.md`, 17 birim): iki koşulda da dayanaksız oranı %0 — beklenen ödünleşim bu örneklemde görülmedi.*

Durum, ölçüm sonuçları ve sıradaki işler: **ROADMAP.md** (en üstteki "Şu an neredeyiz?").

## 8. Çalıştırma

Windows, Python 3.11 sanal ortamı (`.venv`). Anahtarlar `.env` dosyasında (şablon: `.env.example`).

```powershell
.venv\Scripts\streamlit run src/app.py                 # arayüz → http://localhost:8501 (önce giriş; ilk hesap eski kayıtların sahibi)
.venv\Scripts\python -m src.pipeline "<pdf kökü>" [tr|en]   # data/sample_docs içindeki PDF'i uçtan uca işle (arayüzden yüklemek de bunu başlatır)
.venv\Scripts\python -m src.topics <belge ...>          # konu haritası (yoksa / kota yüzünden bölüm başlıklarına düştüyse)
.venv\Scripts\python -m src.llm.capacity [belge]        # kalan kota, belge maliyeti
.venv\Scripts\python -m src.qualify <model> [--kisa]    # aday modelin yeterlilik testi → eval/yeterlilik/
.venv\Scripts\python -m src.simulate --doc <belge> [--limit N]   # zorluk ölçümü: benzetilmiş öğrenci (Gemma; soru başına 5 çağrı)
.venv\Scripts\python -m eval.zorluk_olcumu              # zorluk pilotu → eval/sonuclar_zorluk.md
.venv\Scripts\python -m eval.turkishmmlu_zorluk         # zorluk sinyalleri ↔ gerçek öğrenci (TurkishMMLU, Gemma) → eval/sonuclar_turkishmmlu.md
.venv\Scripts\python -m eval.kaynak_etkisi             # kaynak desteğinin cevap doğruluğuna etkisi (Belebele-TR + havuz, Gemma) → eval/sonuclar_kaynak_etkisi.md
.venv\Scripts\python -m eval.uc_adim                   # uzman zorluk adımları ↔ sistem (MEB 3 Adım, Gemma) → eval/sonuclar_uc_adim.md
# eval betikleri kaldığı yerden devam eder; uzun ölçümde --parca k/4 ile 4 ayrı süreç (ROADMAP "Yeni oturumda ilk işler")
.venv\Scripts\python scripts\bekci.py [sn]              # iş ve kota izleyici (olayda çıkar)
.venv\Scripts\python -m src.accounts [sifirla <ad>]     # hesapları listele / unutulan parolayı sıfırla
.venv\Scripts\python -m src.library [gizle <belge>]     # belge kaydı / acil durumda herkese açık belgeyi gizle
.venv\Scripts\python scripts\tasarim.py baslat|ekran|tikla|durdur   # tasarım denemesi: geçici hesap veritabanıyla 8503
```

Testler (internetsiz, API çağrısı yok): `.venv\Scripts\python -m tests.<ad>` — `test_pipeline`, `test_checks`, `test_compute`,
`test_grading`, `test_textnorm`, `test_router`, `test_parser`, `test_cards`, `test_difficulty`, `test_accounts`,
`test_mastery`.

# NotaRAG Kod Rehberi

Bu klasör projedeki **bütün kod dosyalarını tek tek** anlatır. Her dosya için şunları bulacaksın:

- Dosya ne işe yarar?
- İçindeki her fonksiyon ne yapar?
- Onu kim çağırır (←), o kimi çağırır (→)?
- Hangi veri dosyasını okur ya da yazar (💾)?
- Neden öyle yazılmış?

Fonksiyon adları bağlantıdır; tıklayınca VS Code o satırı açar. Rehberi önizlemede okumak için dosya açıkken `Ctrl+Shift+V` (yan yana: `Ctrl+K V`).

> Rehber **2026-10-05**'teki koda göre yazıldı; 2026-10-06'da bilgi kartları ve zorluk ölçümü eklendi. Kod değiştikçe satır numaraları kayabilir. Bağlantıları koda göre yeniden hizalamak için `python scripts\rehber_satirlari.py --yaz` çalıştır (fonksiyon adına bakarak düzeltir; internetsiz). Bağlantı yanlış satıra gidiyorsa dosyada `Ctrl+Shift+O` ile ada göre atla.

## Bölümler (verinin aktığı sırayla)

| # | Bölüm | Dosyalar |
|---|---|---|
| 1 | [Giriş kapıları ve ayarlar](01-giris-ve-ayarlar.md) | `config.py`, `prompts.py`, `PROMPTS.md`, `app.py`, `pipeline.py` |
| 2 | [Metin işleme ve PDF okuma](02-pdf-okuma.md) | `textnorm.py`, `ingestion/` (4 dosya) |
| 3 | [Bölümleme ve arama (RAG'in R'si)](03-bolumleme-ve-arama.md) | `chunking/` (2), `retrieval/` (3) |
| 4 | [LLM kapısı: model, kota, önbellek](04-llm-kapisi.md) | `llm/` (4 dosya) |
| 5 | [Soru üretimi](05-uretim.md) | `generation/` (4 dosya) |
| 6 | [Doğrulama ve kalite kapısı](06-dogrulama.md) | `verification/` (4), `qualify.py` |
| 7 | [Sınav isteği ve yardımcılar](07-sinav-istegi.md) | `topics.py`, `request.py`, `grading.py`, `review_store.py`, `export.py`, `requote.py` |
| 8 | [Arayüz (Streamlit)](08-arayuz.md) | `ui/` (13 dosya), `cards.py` |
| 9 | [Ölçüm, testler ve araçlar](09-olcum-ve-test.md) | `eval/` (9), `tests/` (9), `scripts/` (6) |
| 10 | [Zorluk: iddia değil ölçüm](10-zorluk.md) | `difficulty.py`, `simulate.py` |

Acele edenler için okuma sırası: bu sayfa → 1 (özellikle `pipeline.py`) → 7'deki `request.py` → 5 → 6. Bu beşi sistemin omurgasıdır; gerisi bu omurgaya hizmet eder.

---

## Rakamlarla proje

- **80** Python dosyası var; bunların **12**'si boş `__init__.py`.
  - `__init__.py`, Python'a "bu klasör bir paket, içinden `from src.llm import ...` diye içe aktarabilirsin" der. İçinin boş olması normaldir.
- Geriye **68 gerçek dosya** kalıyor: boş satırlar hariç yaklaşık **8.200 satır**.

| Katman | Klasör | Satır | Görevi |
|---|---|---|---|
| PDF okuma | `src/ingestion/` | ~670 | PDF'ten metin, başlık ve tablo çıkarır; resim olan sayfayı görsel modele okutur |
| Bölümleme | `src/chunking/` | ~120 | Metni sayfa parçalarına ve bölümlere ayırır |
| Arama | `src/retrieval/` | ~180 | Parçaları vektöre çevirir, ChromaDB'de saklar ve arar |
| LLM kapısı | `src/llm/` | ~630 | Bütün yapay zekâ çağrılarının geçtiği tek kapı |
| Üretim | `src/generation/` | ~625 | Soru ve cevap üretir; hesap sorularını SymPy ile yeniden hesaplar |
| Doğrulama | `src/verification/` | ~500 | Soruyu önce kodla, sonra başka bir model ailesiyle denetler |
| Kök dosyalar | `src/*.py` | ~1.950 | Akışlar (pipeline, request), puanlama, dışa aktarma, Türkçe metin, bilgi kartları, zorluk ölçümü |
| **Arayüz** | `src/ui/` | **~2.260** | Streamlit sayfaları, sınav ve bilgi kartı ekranları (en büyük katman) |
| Ölçüm ve test | `eval/`, `tests/`, `scripts/` | ~1.270 | Deneyler, API çağırmayan testler, izleme ve önizleme araçları |

---

## Büyük resim: iki akış ve tek kapı

```
AKIŞ 1: BELGE İŞLEME  (Belgeler sayfası "notu işle" → ayrı süreçte: python -m src.pipeline "<pdf>")
   data/sample_docs/X.pdf
     │ 1) ingestion/pdf_parser.py  parse_pdf()           → data/parsed/X.json
     │ 2) ingestion/vision.py      run_vision()          → data/vision_cache/X_p007.md  (resim sayfalar)
     │ 3) chunking/chunker.py      chunk_document()      → data/chunks/chunks.jsonl, sections.jsonl
     │ 4) retrieval/index.py       Index().build()       → data/chroma/ (+ data/embeddings/ önbellek)
     │    topics.py                topic_map()           → data/topics/X.json
     │ 5) generation/generate.py   build_units() → generate_group() / generate_unit()
     │       └ her soru: schema.Question → verification/checks.py check() → şık karıştırma
     │ 6) verification/verify.py   verify_item()         (farklı aileden kör doğrulama)
     ▼
   data/questions/X_tr.jsonl   ← SORU HAVUZU

AKIŞ 2: SINAV İSTEĞİ  (Sınav Hazırla sayfası → request.py)
   kullanıcı belge + konu + zorluk + tip + sayı SEÇER
     │ request.prepare():  her konu adı → request.retrieve() → ChromaDB'de anlamsal arama → sayfalar
     │                     havuzda o sayfalara bağlı, doğrulanmış soru var mı? → varsa hemen (0 token)
     │ eksik varsa request.start() → ayrı süreçte request.run():
     │                     yalnızca bulunan sayfalardan generate_request() → checks → verify_item()
     │                     simulate.run() → zorluk ölçülür; istenen düzeyin altındaysa evolve_request() (zorlaştırma)
     ▼
   data/questions/istek_tr.jsonl  → ui/quiz.py (çöz, puanla, sonuç) → data/review/attempts.jsonl

TEK KAPI: her LLM çağrısı → llm/router.py call("rol", istem)
     → llm/models.py  (bu rolde hangi modeller ONAYLI, hangi sırayla?)
     → llm/ledger.py  (kota sayacı + yanıt önbelleği: data/llm.sqlite)
     → Gemini / Groq / OpenRouter API
```

Kodu okurken akılda tutman gereken beş fikir:

1. **Modüller birbirine çoğunlukla dosyayla bağlı.** Her adım `data/` altına bir dosya yazar, sonraki adım onu okur. Bu yüzden adımlar ayrı ayrı çalıştırılabilir ve yarıda kalan iş kaldığı yerden devam eder.
2. **Model adı değil rol adı.** Kod "gpt-oss'u çağır" demez, `call("verify", ...)` der. Hangi modelin çağrılacağına [`models.py`](../src/llm/models.py) karar verir.
3. **İstemler kodda değil, [`PROMPTS.md`](../PROMPTS.md)'de.** Kod onları bölüm numarasıyla okur. O dosyayı değiştirmek sistemin davranışını değiştirir.
4. **Üretilen hiçbir şeye güvenilmez.** Her soru üç süzgeçten geçer:
   - Şema: Pydantic
   - Kod kontrolü: kanıt alıntısı metinde var mı, şıklar tutarlı mı?
   - Kör doğrulama: başka aileden bir model soruyu cevap anahtarını görmeden çözer.
5. **RAG'in "R"si (retrieval, yani arama) Akış 2'de.** Akış 1 belgenin bütün bölümlerini sırayla gezdiği için aramaya ihtiyaç duymaz. Arama [`request.retrieve`](../src/request.py#L52) içinde yapılır.

---

## Veri dosyaları sözlüğü: kim yazar, kim okur?

Modüller birbirleriyle en çok bu dosyalar üzerinden konuşur. Bir dosyanın nereden geldiğini merak ettiğinde buraya bak.

| Dosya | İçinde ne var? | Yazan | Okuyan |
|---|---|---|---|
| `data/sample_docs/*.pdf` | Ders notları | `ui/pages/documents._add` (yükleme) | pipeline, ingestion, vision, review_store (vurgu), documents (sayfa görüntüsü) |
| `data/parsed/<belge>.json` | Sayfa sayfa metin, başlık, kalite etiketi | `pipeline.run`, `ingestion/__main__`, `vision.apply_cached_vision` | `chunking/__main__`, `ui/data.parsed`, `ingestion/review`, `eval/insufficient_context` |
| `data/vision_cache/<belge>_pNNN.md` (+ `_models.json`) | Görsel modelin okuduğu sayfa metni (önbellek) | `vision.run_vision` | `vision.apply_cached_vision` |
| `data/chunks/chunks.jsonl` | Parçalar (arama birimi): id, belge, sayfa, metin, dil | `chunking/__main__` | index, generate, topics, review_store, pipeline, request, verify araçları, ui |
| `data/chunks/sections.jsonl` | Bölümler (aynı başlıklı ardışık sayfalar) | `chunking/__main__` | `generate.build_units`, `topics._fallback`, `ui/data.sections` |
| `data/chunks/skipped.jsonl` | Dizine alınmayan sayfalar ve nedeni | `chunking/__main__` | `ingestion/review` |
| `data/embeddings/cache_*.npz` | Metin → vektör önbelleği | `retrieval/embedder` | `retrieval/embedder` |
| `data/chroma/` | ChromaDB vektör veritabanı (koleksiyon `chunks`) | `retrieval/index.build` | `index.dense`, `request.retrieve` |
| `data/topics/<belge>.json` | Konu haritası: konu adı + sayfalar | `topics.topic_map` | request, export, ui (Sınav Hazırla, Belgeler) |
| `data/questions/<belge>_<dil>.jsonl` | Belge havuzu soruları | `pipeline.run` (ekleyerek) | request, review_store, ui, qualify, requote |
| `data/questions/istek_<dil>.jsonl` | Sınav isteklerinde üretilen sorular | `request.run` (sonuna ekler) | aynı |
| `data/requests/<id>.json` / `.log` | Bir sınav isteğinin durumu / arka plan işinin çıktısı | `request.save`, `request.start` | exam sayfası, `scripts/bekci` |
| `data/jobs/<belge>.json` / `.log` | Belge işleme işinin başlangıcı / çıktısı | `ui/data.start_job` | `ui/data.job_status`, `scripts/bekci` |
| `data/review/attempts.jsonl` | Her öğrenci çözümü (soru kimliği, doğru mu, cevap, ipucu) | `request.record_attempt` | `request.item_stats` (madde analizi) |
| `data/review/cards.jsonl` | Bilgi kartı değerlendirmeleri (Bildim / Bilemedim / Atla) | `cards.record` | `cards.history` (Leitner kutuları) |
| `data/review/difficulty.jsonl` | Zorluk ölçümleri (benzetilmiş öğrenci: p, çaba) | `difficulty.record` (`simulate.measure`) | `difficulty.measurements` → `apply` |
| `data/review/reports.jsonl` | "Hatalı bildir" ve kısa cevap itirazları | `request.report` | `request.reported`, `blocked_ids` |
| `data/reviews.jsonl` | Öğretmenin onay/red kararları | `review_store.save_decision` | `review_store.decisions` |
| `data/llm.sqlite` | Kota sayaçları + LLM yanıt önbelleği | `llm/ledger` | `llm/ledger`, `scripts/bekci` |
| `data/pilot/` | Geliştirme sırasındaki model karşılaştırmaları | `generation/pilot`, `verification/__main__`, eval betikleri | `review_store.question_sets`, eval, qualify |
| `eval/sonuclar_*.json` / `.md` | Ölçüm sonuçları | eval betikleri, `verification/sensitivity` | Rapor sayfası (`ui/parts/evaluation`) |

> Dikkat: **`data/review/`** (klasör: öğrenci çözümleri, bildirimler, okuma kontrol sayfası) ile **`data/reviews.jsonl`** (dosya: öğretmen kararları) farklı şeylerdir.

**JSONL nedir?** Her satırı ayrı bir JSON nesnesi olan metin dosyası. Sonuna yeni satır eklemek ucuzdur (dosyanın tamamını yeniden yazmak gerekmez). Bu yüzden kayıt tutan dosyalar (çözümler, kararlar, sorular) JSONL'dir.

---

## Bir sorunun hayatı: hangi alanı kim ekler?

Sistemde dolaşan temel nesne bir **soru öğesidir** (kodda genelde `it` ya da `item`). `data/questions/*.jsonl` dosyalarının her satırı bunlardan biridir:

```jsonc
{
  // generation/generate.py  _postprocess()
  "unit": "Rulet Tekerleği Seçimi",          // hangi üretim biriminden (bölüm başlığı)
  "pages": [15, 16],                         // birimin sayfaları
  "model": "gemini-3.8-flash",               // üreten model (soru kimliğinin parçası!)
  "chunk_ids": ["7.Hafta Sunu Dosyası:p015:1", "..."],   // üretimde verilen bağlam parçaları
  "q": {                                     // generation/schema.py Question (şıklar karıştırılmış)
    "question": "...", "type": "multiple_choice", "options": ["...", "...", "...", "..."],
    "answer_index": 2, "answer": "...", "evidence_quote": "...", "evidence_quotes": ["...", "..."],   // ayrı bilgiler
    "bloom_level": "understand", "difficulty": "medium",
    "compute": null, "option_values": null, "solution": null, "option_notes": ["...", "", "...", "..."]
  },
  // verification/checks.py  check()
  "check": {"status": "passed_checks", "rejected": [], "flags": ["length_cue"],
            "evidence_match": "exact", "evidence_page": 16,
            "facts": 2, "fact_pages": [15, 16],   // notta bulunan ayrı kanıt alıntısı sayısı (zorluk yapısı)
            "generated_answer_index": 0,      // karıştırmadan önceki doğru şık (konum yanlılığı ölçümü)
            "computed": {"ok": true, "value": "30240", "key_ok": true}},   // yalnızca hesap sorularında
  // verification/verify.py  verify_item()
  "verification": {"label": "verified", "why": "doğrulayıcı yalnızca anahtar şıkkı doğru buldu",
                   "verifier": "openai/gpt-oss-120b", "option_verdicts": {"A": "incorrect", "B": "...", "...": "..."}},
  "request": "20261005-141210-ab12",         // request.run(): yalnızca sınav isteğinde üretilenlerde
  "requested_difficulty": "hard"             // istenen düzey (etiket artık zorla yazılmaz)
}
```

Belleğe yüklenirken eklenen ama dosyaya yazılmayan alanlar:

- `id`: [`review_store.question_id`](../src/review_store.py#L36) hesaplar: `sha1(model + "|" + soru metni)` değerinin ilk 12 karakteri.
- `doc`: ilk parçanın kimliğinden çıkarılan belge adı.
- `set`, `set_kind`: hangi dosyadan geldiği (`ui/data.question_sets`).
- `difficulty`: etkin zorluk `{level, claim, source, …}` ([`apply`](../src/difficulty.py#L234); bölüm 10). `q.difficulty` da bu düzeye çevrilir; üretecin iddiası `claim`'de kalır. Dosya değişmez.

**Soru kimliği neden önemli?** Öğretmen kararları, öğrenci çözümleri ve "hatalı bildir" kayıtları hep bu kimlikle bağlanır. Aynı model aynı soruyu yeniden üretirse kimlik aynı çıkar. Bu yüzden [`pipeline.merge_existing`](../src/pipeline.py#L124) soru dosyasının üzerine yazmaz, yeni soruları ekler. Üzerine yazsaydı bu kayıtların bağlandığı sorular kaybolurdu.

**Üç etiket:**
- `verified` (doğrulandı): sınavlarda kullanılır.
- `needs_review` (incelenmeli): yalnızca İnceleme sayfasında görünür.
- `rejected` (reddedildi): kod kontrolüne ya da doğrulayıcıya takılmıştır.

---

## Kim kimi içe aktarıyor?

En çok kullanılan modüller (← kaç dosya onu içe aktarıyor):

| Modül | ← | Neden bu kadar çok? |
|---|---|---|
| [`config.py`](../src/config.py) | 26 | Bütün klasör yolları ve anahtarlar burada |
| [`textnorm.py`](../src/textnorm.py) | 14 | Okuma, arama, kanıt kontrolü ve ekranda gösterim aynı metin dönüşümlerini kullanmak zorunda |
| [`llm/models.py`](../src/llm/models.py) | 13 | Hangi model, hangi rol, hangi kota |
| [`ui/style.py`](../src/ui/style.py) | 11 | Bütün sayfaların görsel dili |
| [`llm/router.py`](../src/llm/router.py) | 10 | LLM çağıran her yer buradan geçer |
| [`ui/data.py`](../src/ui/data.py) | 10 | Arayüzün dosya okuma katmanı |
| [`generation/generate.py`](../src/generation/generate.py) | 9 | Üretim birimleri ve üretim fonksiyonları |
| [`llm/ledger.py`](../src/llm/ledger.py) | 10 | Kota durumu |

"**Kimse içe aktarmıyor**" görünen dosyaların neredeyse hepsi bir **giriş noktasıdır**: ya `python -m ...` ile çalıştırılır ya da Streamlit onu sayfa olarak açar. Tek istisna [`ui/parts/system.py`](../src/ui/parts/system.py): onu hiçbir şey kullanmıyor, yani ölü kod (bkz. bölüm 8).

### Çalıştırılabilir giriş noktaları

| Komut | Dosya | API çağırır mı? |
|---|---|---|
| `streamlit run src/app.py` | [`app.py`](../src/app.py) | Arayüz kendisi çağırmaz; başlattığı işler çağırır |
| `python -m src.pipeline "<pdf>" [dil]` | [`pipeline.py`](../src/pipeline.py) | Evet (görsel okuma, embedding, üretim, doğrulama) |
| `python -m src.request <id>` | [`request.py`](../src/request.py) | Evet (arayüz başlatır) |
| `python -m src.ingestion [--vision [--yes]]` | [`ingestion/__main__.py`](../src/ingestion/__main__.py) | Yalnızca `--vision --yes` ile |
| `python -m src.ingestion.review` | [`ingestion/review.py`](../src/ingestion/review.py) | Hayır |
| `python -m src.chunking` | [`chunking/__main__.py`](../src/chunking/__main__.py) | Hayır |
| `python -m src.retrieval build` / `search "..."` | [`retrieval/__main__.py`](../src/retrieval/__main__.py) | Embedding (önbellekte yoksa) |
| `python -m src.topics [belge]` | [`topics.py`](../src/topics.py) | Evet (belge başına 1 istek) |
| `python -m src.llm.capacity [belge]` | [`llm/capacity.py`](../src/llm/capacity.py) | Hayır |
| `python -m src.qualify <model>` | [`qualify.py`](../src/qualify.py) | Evet |
| `python -m src.simulate [--doc X] [--ids …] [--limit N]` | [`simulate.py`](../src/simulate.py) | Evet (Gemma; soru başına 5 çağrı) |
| `python -m src.requote [--yaz]` | [`requote.py`](../src/requote.py) | Hayır |
| `python -m src.generation.pilot ...` | [`generation/pilot.py`](../src/generation/pilot.py) | Evet |
| `python -m src.verification <dosya>` | [`verification/__main__.py`](../src/verification/__main__.py) | Evet |
| `python -m src.verification.sensitivity <dosya>` | [`verification/sensitivity.py`](../src/verification/sensitivity.py) | Evet |
| `python -m eval.<ad>` | [`eval/`](../eval/) | `compute_check` hayır, diğerleri evet |
| `python -m tests.<ad>` | [`tests/`](../tests/) | Hayır |
| `python scripts\bekci.py` | [`scripts/bekci.py`](../scripts/bekci.py) | Hayır |
| `streamlit run scripts/onizleme.py` + `python scripts\ekran.py <url> <png>` | [`scripts/onizleme.py`](../scripts/onizleme.py), [`scripts/ekran.py`](../scripts/ekran.py) | Hayır (arayüzü hazır veriyle açar, ekran görüntüsü alır) |
| `python scripts\rehber_satirlari.py [--yaz]` | [`scripts/rehber_satirlari.py`](../scripts/rehber_satirlari.py) | Hayır (bu rehberin bağlantılarını koda hizalar) |

**`python -m paket` nasıl çalışır?** Python bir paketi `-m` ile çalıştırınca paketin içindeki `__main__.py` dosyasını çalıştırır (ör. `python -m src.ingestion` → `src/ingestion/__main__.py`). Tek bir modülü çalıştırınca da (ör. `python -m src.pipeline`) dosyanın sonundaki `if __name__ == "__main__":` bloğu çalışır. Aynı dosya başka bir dosya tarafından içe aktarıldığında bu blok **çalışmaz**. Bu yüzden `pipeline.py` hem komut olarak çalışabilir hem de `request.py` içinden fonksiyonu kullanılabilir.

---

## Kodda sık geçen Python ve Streamlit kavramları

| Kavram | Nerede | Ne işe yarar |
|---|---|---|
| `from __future__ import annotations` | Çoğu dosyanın başında | Tip ipuçlarını (`list[dict] \| None`) metin olarak saklar; eski Python sürümlerinde de çalışır, döngüsel tip başvurusu sorun olmaz |
| `@dataclass` | `pdf_parser.Line`, `router.Result`, `models.ModelSpec` | Sınıfa otomatik `__init__` ve `__repr__` yazar; veri taşıyan küçük nesneler için |
| `@lru_cache` | `prompts.load_prompt`, `request._index` | Fonksiyonun sonucunu bellekte tutar; aynı argümanla ikinci çağrı hesaplanmaz |
| `@cached_property` | `index.Index._bm25_f5` | Özellik ilk erişimde hesaplanır, sonra saklanır (BM25 dizini yalnızca gerekirse kurulur) |
| Pydantic `BaseModel` | `generation/schema.py` | Alan tiplerini ve kuralları otomatik denetler; LLM'in bozuk JSON'unu ayıklar |
| `ast` modülü | `compute.validate`, `grading._bounded` | Python ifadesini çalıştırmadan ağaç olarak inceler (güvenlik denetimi) |
| `subprocess.Popen(... DETACHED_PROCESS)` | `request.start`, `ui/data.start_job` | Uzun işi ayrı süreçte başlatır; arayüz kapansa da iş sürer |
| `multiprocessing` (`spawn` havuzu) | `generation/compute.py` | SymPy hesabını ayrı süreçte, süre sınırıyla yapar |
| `sqlite3` | `llm/ledger.py` | Dosya tabanlı küçük veritabanı (kurulum gerektirmez) |
| İçe aktarmanın fonksiyon içinde olması | `pipeline.run`, `request.run`... | "Tembel içe aktarma": ağır kütüphaneler (chromadb, pymupdf) yalnızca gerçekten gerektiğinde yüklenir |
| Streamlit yeniden çalıştırma | Bütün `ui/` | Her tıklamada sayfa betiği **baştan sona yeniden çalışır**; durum `st.session_state`'te saklanır (bölüm 8) |
| `@st.cache_data(ttl=20)` | `ui/data.py` | Dosya okuma sonucunu 20 sn önbellekte tutar; her tıklamada diskten okunmaz |

---

## Kod sağlığı notları (okurken fark ettiklerim)

Bunlar hata değil; projenin nasıl büyüdüğünü gösteren izler. İleride temizlemek istersen buradan başla.

1. **Ölü kod** (kimse kullanmıyor):
   - [`ui/parts/system.py`](../src/ui/parts/system.py): dosyanın tamamı; yerini `ui/pages/models.py` aldı.
   - [`ui/parts/evaluation.render`](../src/ui/parts/evaluation.py#L194): Rapor sayfası alt fonksiyonları doğrudan çağırıyor.
   - [`schema.Batch`](../src/generation/schema.py#L71), [`review_store.agreement`](../src/review_store.py#L224), `review_store.LABEL_TR`, [`style.card`](../src/ui/style.py#L450), `ui/data.DOC_SHORT`, `style.INK / PAPER / HIGHLIGHT`.
2. **Tanımlı ama hiç çağrılmayan rol:** `models.py`'deki `"judge"` (kısa cevap hakemi). Hakem istemi (§4d) aslında doğrulayıcı rolüyle çağrılıyor ([`verify_short`](../src/verification/verify.py#L174)). Arayüz bu rolü listeliyor, kod kullanmıyor.
3. **Tekrarlanan kod:**
   - `chunks.jsonl` okuyan fonksiyonun yaklaşık 9 kopyası var (`index.load_chunks`, `generate._load`, `review_store.load_chunks`, `topics._chunks`, `pipeline.run` içinde, `verification/__main__`, `sensitivity`, `requote`, `eval/batch_compare`).
   - `patient` iki yerde var (`pipeline`, `eval/bloom_experiment`).
   - `LANG_NAMES`, `TYPE_TR`, `LETTERS`, `PRICE` gibi sözlükler birden çok dosyada tekrar ediyor.
4. **Ters yönde bağımlılık:** [`request.py`](../src/request.py) yalnızca `patient` fonksiyonu için [`pipeline.py`](../src/pipeline.py)'yi içe aktarıyor. Normalde ortak yardımcılar akışlardan ayrı bir modülde durur.
5. **Arama kodu iki yerde:** `request.retrieve` ChromaDB'yi doğrudan sorguluyor (mesafeyi de alabilmek için). `Index.dense` aynı işi mesafesiz yapıyor.
6. **Dakikalık hız sınırlayıcı süreç içi:** `ledger.Throttle` bellekte tutulur. Aynı anda çalışan iki süreç (belge işleme + sınav isteği) birbirinin dakikalık kullanımını görmez; günlük kota ise SQLite'ta ortak olduğu için doğru sayılır.
7. **Öğrenci girdisi ana süreçte hesaplanıyor:** [`grading.safe_value`](../src/grading.py#L91) SymPy'yi Streamlit sürecinde çalıştırıyor. Beyaz liste ve büyüklük sınırları var ama `compute.judge`'daki gibi süre sınırı yok.

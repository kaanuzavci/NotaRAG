# Yol Haritası

İnternet etiketi: 🟢 internet gerekmez · 🟡 az (birkaç MB) · 🔴 yüksek (yüzlerce MB+). 🔴 adımları yalnızca Wi-Fi'da yapılır.

## Şu an neredeyiz? (2026-10-06) — yeni oturum buradan başlar

**Teslim: 3 Ocak 2027.** Sistem uçtan uca çalışıyor: PDF yükle → oku (gerekirse görselden) → konu haritası → havuz (üret + doğrula) → **Sınav Hazırla** (seçimle istek, odak modunda çöz, sonuç grafikleri, Moodle/yazdır).
- Havuz: 6 belgede **200 kullanılabilir soru** (122 ÇS, 31 D/Y, 47 KC; 50'si SymPy'li hesap sorusu). Zorluk artık **etkin düzey** (aşağıda): 118 kolay / 79 orta / **3 zor** (üretecin iddiası 112 / 81 / 7; eskiden kodun zorla yazdığı etiketle 18 zor vardı). 62 çözüm kaydı (madde analizi).
- **Zorluk = ölçüm, iddia değil (2026-10-06, madde 8'in uygulaması):** `src/difficulty.py` + `src/simulate.py` (rehber bölüm 10). Etiketi en güvenilir katman verir: gerçek öğrenci (Elo, ≥5 ilk deneme) > benzetilmiş öğrenci (Gemma 4 sınıfı, açık kitap, düşünmeden 4 örneklem → p; **yalnızca sınıf yanılırsa alt sınır**, hepsi doğruysa tavan = bilgi yok) > üretecin önbellekten geri yüklenen kendi etiketi. Hepsine kodla açıklanabilir **yapı tavanı**: kopya soru / kaynağın aynısı D/Y / tek işlem → kolay; tek bilgi ya da kural → orta; hatırlama → orta. **"Zor"un yapısal koşulu: en az iki ayrı bilgi/kural** (notta bulunan ayrı kanıt alıntısı, `evidence_quotes` → `check.facts`) **ya da çok adımlı hesap** (≥3 adım, ≥3 işlem) — AIG'deki "zorluğu değiştiren değişken". Ölçümler `data/review/difficulty.jsonl`'de, yüklemede bindirilir (soru dosyaları değişmez). Sınav isteği: üretim → doğrulama → ölçüm → **yalnızca istenen düzeyde ölçülenler** sınava girer; yetmezse altında kalanlar **zorlaştırılır** (PROMPTS §2d: Evol-Instruct + başka konunun notuyla birleştirme) ve yeniden ölçülür; ilerleme metni kaç sorunun hangi düzeyde ölçüldüğünü söyler. Üretim istemleri zorluğu işlemsel tanımlıyor (alandan bağımsız). **Benzetilmeyenler:** hesap soruları (Gemma 4 lise matematiğinde doyuyor) ve sözel kısa cevap (metin eşleşmesi anlamı yakalamıyor: pilotta doğru cevap 0/4 sayıldı → sahte "zor"); bunlarda iddia + tavan. Pilot: `eval/zorluk_olcumu.py` → `eval/sonuclar_zorluk.md`
  - **Pilot bulgusu (2026-10-06): benzetim bu havuzda neredeyse bilgi vermiyor.** Ölçülebilir 14 sözel sorunun (ÇS + D/Y) **14'ünde p = 1** (Gemma 4 açık kitapta öğrenciden çok güçlü). Çaba (dikkatli çözümün düşünme token'ı) zorluğu değil **soru tipini** ölçtü: D/Y 221-269, ÇS 365-545 token; ÇS içinde üretecin iddiasıyla ilişkisiz. Eski kural (çaba ≥ 300 orta, ≥ 900 zor) D/Y'yi hep kolay, ÇS'yi hep orta yapıyordu → kaldırıldı: çaba yalnızca kaydediliyor, benzetim yalnızca sınıf yanıldığında düzeyi yükseltiyor. Yani bugün sözel sorularda etiketi fiilen **üretecin iddiası + yapı tavanı** veriyor; "zor"un tek güvenilir koşulu yapısal (iki ayrı bilgi/kural). Ücretsiz erişilebilir daha zayıf öğrenci modeli yok (Gemini API'de yalnızca Gemma 4 26B/31B; Groq'ta Llama 8B kaldırılmış). TYT isteğinde (A) etkin düzey elle değerlendirmeyle 7/10 uyuşuyor (üretecin iddiası 5/10, eski zorla yazılmış etiket 1/10)
- Belgeler: TYT matematik (14 s., hepsi görselden), Çevre/Ekoloji (23 s.), YZ–Genetik Algoritmalar TR (18 s.), Genetic Algorithms EN (90 s.), **Bilgisayar Mimarisi Hafta 01 (35 s.)** ve **Hafta 02 – Performans (72 s.)** (ikisi 2026-10-05 gecesi eklendi; görsel okuma kuyruğu boş).
- Testler (hepsi geçiyor): `test_pipeline`, `test_checks`, `test_compute`, `test_grading`, `test_textnorm`, `test_router`, `test_parser`, `test_cards`, `test_difficulty` → `python -m tests.<ad>`.
- **Bilgi Kartları (2026-10-05, LLM çağrısı yok):** yeni sayfa (`src/ui/pages/cards.py`, mantık `src/cards.py`). NotebookLM gibi **soru → cevap, şık yok**: yalnızca şıksız anlaşılan sorular kart olur (`card_ok`: kısa cevap + kökü kendi başına soru olan çoktan seçmeli; doğru/yanlış, "aşağıdakilerden hangisi", olumsuz kök sınavda kalır) → havuzdan 139 kart. Arka yüz: cevap + notundaki kaynak cümle + çözüm. Leitner aralıklı tekrar (kutu 1-5: hemen / 1 / 3 / 7 / 14 gün; kayıt `data/review/cards.jsonl`, sınav istatistiğine karışmaz). Kart ortada ve büyük; tıklayınca 3B döner, yine tıklayınca geri (Boşluk da); Bilemedim / Atla / Bildim → kart yığınına gider, sıradaki desteden gelir; klavye ← ↓ →. Sınav sonucunda "Kartla çalış" (yanlış ve boşlar)
- **Tasarım kararları (2026-10-05, iki tur kullanıcı geri bildirimi):** önce figür (Fosfor), canlı renkler, konfeti; sonra pastel zemin + cam + Noto animasyonlu emoji koç denendi → kullanıcı: **figür, konfeti, el/surat animasyonları istenmiyor; gökkuşağı zemin yerine eski düz kâğıt zemin; ana sayfalarda eski görünüm** (yeni zeminde bej sekme/tablo/seçim kutuları "sarımsı yama" gibi duruyordu). Son hâl (v3): kâğıt zemin + lacivert tema geri; yalnızca kart ve sınav ekranlarında sakin pastel kartlar; hareket yalnızca anlam taşıyınca (kart dönüşü, yığına gitme). **Hata düzeltildi:** aynı düğmeye art arda basınca animasyon oynamıyordu ve çevrilmiş kart bir sonrakine çevrili geçebiliyordu — React aynı etiketli öğeyi yeniden kullanıyordu → sahnenin sarmalayıcı etiketi her değerlendirmede değişiyor (div/section; sınavda soru kartı için de). Bitiş ekranları (kart ve sınav) tek **özet kartı**: büyük isabet sayısı, durum kutucukları, zorluğa (ve sınavda soru tipine) göre ölçerler, konular en çok zorlanılandan başlayarak (< %50 "tekrar et"); dataviz ilkeleri (tek seri tek renk #3A7BB8 = 4,4:1, lejant yok, değerler yazılı, büyük sayılar düz yazı tipi). Görsel kontrol: `scripts/onizleme.py` + `scripts/ekran.py` (görünmez Edge + CDP)
- **"Her türlü PDF" testi (2026-10-06, internetsiz ayrıştırma, LLM yok):** `data/pdf_testi/`'de 13 farklı belge (depoda değil): Ankara Üni. açık ders notları ve slaytları, tıp notları, MEB 9. sınıf biyoloji, iki sütunlu arXiv makalesi, eski dergi sayısı, 276 sayfalık LaTeX matematik notu (kısmi türevli DD), TÜİK tablolu rapor, Hakas Türkçesi (Kiril), **taranmış ders kitabı** (192 sayfa, yalnızca görüntü), **el yazısı ders notu** (bozuk OCR katmanlı). Bulunan ve düzeltilen hatalar: (1) taranmış sayfa `ok` sanılıp bölümleyicide "boş" diye atlanıyordu → taranmış PDF sessizce **hiç soru üretmiyordu**; artık `needs_vision` + `scanned` (`_full_page_image`); (2) tarayıcının sayfa başına yer imleri (`…_Sayfa_001`) başlık sanılıyordu; (3) belge dili bozuk OCR katmanından hesaplanıyordu (Türkçe el yazısı → `en` → sorular İngilizce olurdu); artık yalnızca sağlam sayfalardan, görsel okumadan sonra yeniden; belirsizse `tr`; (4) PDF olmayan dosya (HTML hata sayfası) "1 sayfalık belge" sanılıyordu → açık hata. Mevcut 6 belgede hiçbir sayfanın kalitesi değişmedi; test `test_parser.test_scanned_pages_need_vision`. **Açık sorun:** LaTeX matematik notunda 276 sayfanın 255'i (kesirler/integraller metin katmanında dağılmış: ∫ → "Z") görsel okumaya gidiyor ve okunana kadar soru üretiminde kullanılmıyor → ücretsiz kotayla günler sürer (Vertex'le birkaç sent). Bu akşam ayrıca: Gemini istemcisinde zaman aşımı yoktu (ağ değişince süreçler asılı kaldı) → 10 dk zaman aşımı; LangChain + RAGAS paketleri `wheelhouse/`'a indirildi (kurulmadı)
- **İnternet varken indirilenler (2026-10-06, hotspot dışı):** `data/kaynaklar/` LITERATURE'daki 29 arXiv makalesi (54 MB, rapor için internetsiz okuma; depoda değil); `wheelhouse/` LangChain + RAGAS + google-cloud-storage (Vertex toplu iş) + pymupdf4llm + pymupdf_layout (CPU'da küçük ONNX düzen modeli, ~40 MB; formüllü notlar için denenebilir — yerel model sayılır, kullanmadan önce kullanıcıya sor) + python-docx (kurulmadı: `pip install --no-index --find-links wheelhouse <paket>`); `data/turkishmmlu/` (alt küme + herkese açık 945 soru); `data/pdf_testi/` 13 PDF; arayüz yazı tipleri yerelde (`src/static/fonts`). Hâlâ internet isteyen: `src/export.py`'nin yazdırılabilir sınav HTML'i Google Fonts bağlantısı kullanıyor (internetsizde yedek yazı tipi)
- **Deney verisi (2026-10-06, ~2,6 GB, `data/kaynak_veri/BENIOKU.md`):** MEB OGM'den TYT/AYT MEBİ konu özetleri (19 kitap: sistem denemesi için gerçek ders notu), **3 Adım soru bankası** (uzmanlarca adım adım zorlaşan sorular → zorluk tanımlarımızı uzman etiketine karşı sınama), kazanım kavrama / konu pekiştirme / tarama testleri, 2024 denemeler; ÖSYM resmî TYT (6 yıl) ve AYT (4 yıl) kitapçıkları; Ankara Üni. Açık Ders'ten 12 fakültenin notları; Belebele-TR (paragraf→soru, insan yazımı), SciQ, EXAMS-TR, RACE; Tesseract OCR + Türkçe veri (kurulmadı; taranmış sayfaları kota harcamadan okuma seçeneği — yerel OCR, kullanıcı onayı gerekir). İndirme araçları: `scripts/ogm_indir.py`, `scripts/auad_indir.py`
- Asıl sorun **kota** — ölçümler ve karar aşağıda: [Kota — kök çözüm analizi](#kota--kök-çözüm-analizi-ve-karar-2026-10-05).

### Sıradaki işler (öncelik sırasıyla)
1. **Hafta 01 / 02 havuz kalitesi** — belgeler 2026-10-05'te yüklemeyle işlendi ve kullanılabilir, ama Gemini dolu olduğu için 49 sorunun **hepsi yedek qwen'den**: 43 kolay / 6 orta / 0 zor, hesap sorusu 0 (Hafta 02 performans konusu CPI / çalışma süresi hesabına çok uygun), konu haritası yok. Öneri: Vertex açılınca (Gemini krediden; ücretsiz 20/gün harcanmaz):
   - [ ] Konu haritası: `python -m src.topics Hafta_01_Bilgisayar_Mimarisi_ve_Organizasyonuna_Giris Hafta_02_Bilgisayar_Performansina_Giris` — 2026-10-05 15:12'de Gemini "busy" (503) verdi; şu an Sınav Hazırla'da 34 ve 61 bölüm başlığı listeleniyor
   - [ ] Yeniden çalıştır: `python -m src.pipeline Hafta_02_Bilgisayar_Performansina_Giris` (sonra Hafta_01). Artık **ekler, silmez** (`merge_existing`): mevcut 44 soru korunur, Gemini'nin yeni soruları ve hesap soruları (CPI, çalışma süresi) eklenir, eskilerin tekrarı doğrulamaya gitmez. Tahmini maliyet: ~4-6 Gemini isteği + ~80-100 doğrulama çağrısı
2. **Kota planı — hazırlık (kullanıcı onayı bekliyor, anahtar gerekmez):**
   - [ ] Vertex AI sağlayıcısı (`google-genai` zaten kurulu: `genai.Client(vertexai=True, project=…, location=…)`, kimlik `secrets/vertex.json` servis hesabı); Gemini modelleri `vertex/…` kopyaları olarak üretim + görsel okuma zincirlerinin başına
   - [ ] Harcama sayacı + tavan (≈250 $'da dur), Modeller ve Kota sayfasında kalan kredi ve gün
   - [ ] **Toplu doğrulama** (4-5 soru tek çağrıda; kural metni bir kez) → önce `src.qualify` / duyarlılık testiyle (kasıtlı hatalar) tek tek doğrulamayla karşılaştır; yakalama düşerse kullanılmaz. Literatür: yalnızca aynı birim, ≤5 soru, soru başına ayrı JSON anahtarı ("Q1": {"A": …}; indeks listesi doğruluğu düşürüyor). İstem önbelleği yeterse gerek kalmayabilir
   - [x] **API çağırmayan üç düzeltme (2026-10-05, sektör araştırması sonrası):** (1) `verify.family`: Gemma = Gemini ailesi, *stral = Mistral (eskiden 'gemma' ayrı aile sayılırdı → aile kuralı sessizce çiğnenirdi); (2) istem önbelleği ölçümü: `cached_tokens` → `ledger.prompt_cache`, TPD hatasında sağlayıcının "Used" değeri kaydımızla yan yana → `ledger.quota_sync`, `python -m src.llm.capacity` gösterir; kotadan **düşülmüyor**, önce ölçülecek; (3) akıl yürütme düzeyi rol başına (`REASONING_<ROL>=low`, varsayılan medium) ve önbellek anahtarında (yalnızca medium değilse → eski yanıtların anahtarı değişmedi). Testler: `test_router` (`test_family`, `test_cache_key`)
   - [ ] **reasoning_effort=low deneyi** (~40 Groq çağrısı): `$env:REASONING_VERIFY="low"; python -m src.verification.sensitivity data/pilot/<model>_dogrulama.jsonl openai/gpt-oss-120b` (ve 20b) → 17/17 ve 20/20 korunursa §4a/§4b için low. §4e (`verify_math`) medium kalır. Not: n=17 küçük; tek kaçırma bile anlamlı sayılır
   - [ ] **İstem önbelleği** (Groq, yalnızca gpt-oss; birebir aynı önek, 2 saat): doğrulamayı birim + tip sırasıyla çalıştır (§4a/§4b/§4c talimatları farklı ve Context'ten önce → önek ancak aynı birim **ve** aynı tipte tutar). Önce `capacity`'deki "istem önbelleğinden" ve TPD satırıyla Groq'un önbellekli token'ı kotadan düşüp düşmediğini gör; düşüyorsa `record`'da çıkar
   - [ ] **Mistral hesabı** → Mistral Large 3 doğrulayıcı adayı (`src.qualify`). Vertex sonrası asıl darboğaz Google dışı doğrulayıcı; Mistral yeni aile (hem Gemini'nin hem qwen'in sorusunu doğrular). **Düzeltme (2026-10-05):** araştırmadaki "Experiment planı, ayda 1 milyar token" artık yok (Ağustos-Eylül 2026'da kalktı; yardım makalesi 404). Yeni durum: Studio'da Free plan, **ayda 10 $ API kredisi** (Large 3: 0,5 $ / 1,5 $ / M token → kabaca ayda ~5-8 bin doğrulama çağrısı); eğitimde kullanılmayı kapatma (opt-out) Free'de de var. Hesap açıldı, kart girilmedi, anahtar `.env`'de (2026-10-05). Free planda açık modeller (`/v1/models`): **Large yok**; en güçlüsü Medium 3.5 (`mistral-medium-2604`, akıl yürütme + görüntü), Small 4, Ministral 3, `mistral-ocr-2512` (görsel okuma için fikir: Google dışı, GPU'suz). Kod hazır: `mistral/mistral-medium-2604` aday (`verify`, `verify_math`), sağlayıcı `router._OPENAI_COMPAT`. **Engel:** her istekte `429`, `x-ratelimit-limit-req-minute: 0` (iki modelde de, iki denemede). Sebep büyük olasılıkla: Billing'de **kredi 0,00 $** (plan kartındaki "10 $/ay" yüklenmemiş), ödeme yöntemi yok, telefon doğrulanmadı. Limits sayfası (plan tanımı): medium 1 istek/sn, 20.000 token/dk; listede `mistral-large-2512` ve GLM (`glm-5-2`, `zai-glm-5-3`; Zhipu = başka bir yeni aile) da var ama `/v1/models`'te yoklar. Konsolda telefon doğrulama / kredi açma adımı bulunamadı → **rafa kaldırıldı (2026-10-05)**; kod aday listesinde hazır, kredi gelirse tek komutla test. Billing'e kart/kredi **eklenmez**. Gerekçe: teslime kadar kalan doğrulama ihtiyacı (~500-700 çağrı: Hafta 01/02 yeniden üretim, GA tam havuz, kaynak desteği deneyi) ücretsiz günlük kapasitenin (~550 çağrı; Vertex sonrası qwen'in bütçesi de doğrulamaya kalınca daha fazla) 1-2 günü; aile çeşitliliği zaten yeterli (Gemini sorularını gpt-oss, Nemotron, qwen doğrulayabiliyor). Ek sağlayıcı ancak çok kullanıcılı canlı kullanımda ya da 10 Ocak sonrasında gerekir; NVIDIA NIM de şimdilik aranmıyor Açılınca: `python -m src.qualify mistral/mistral-medium-2604` (~62 Mistral çağrısı ≈ 0,1 $ + kısa cevap hakemi için birkaç Groq çağrısı)
   - [ ] Düşük öncelik (yalnızca bu hafta ve 10 Ocak sonrası için): Gemma 4 31B adayı (görsel okuma + yedek üretim; aile = gemini, doğrulayıcısı Google dışı), Flash-Lite ile konu haritası. Önce AI Studio'nun rate-limit sayfasından gerçek sınırlar (models.py'de Flash-Lite `rpd=20` varsayım, araştırma 500 diyor; Gemma 30/dk, 16K token/dk iddiası)
3. **~12 Ekim: kullanıcı Google Cloud 300 $ denemesini açar** (90 gün → ~10 Ocak, teslimi bir hafta payla kapsar): Vertex AI API'yi etkinleştir, "Vertex AI User" rollü servis hesabı, JSON anahtar → `secrets/vertex.json` (sohbete yapıştırılmaz). Sonra: birkaç sentlik test (model adları Vertex'te aynı mı, kredi düşüyor mu), devreye al. Ayrıca bak: Model Garden'daki açık modeller (gpt-oss, Qwen, DeepSeek) krediye dahil mi (iş ortağı MaaS modelleri hariç tutuluyor olabilir; plan buna dayanmıyor); deneme hesabı kota artışı isteyemez (429'da ücretsiz düzene düşme korunur); havuz doldurma ve toplu görsel okuma Vertex Batch ile (%50 indirim)
4. [ ] **Ödev gereksinimi karşılanmadı — kaynak desteğinin cevap doğruluğuna etkisi** (2026-10-05 tespiti). Ödev: "Kaynak metinlerle desteklenen üretimin cevap doğruluğuna etkisi değerlendirilecektir." Mevcut ölçümlerin hepsi kaynaklı koşulda (retrieval, duyarlılık, Bloom, toplu üretim, yetersiz bağlam) → kaynaksız taban çizgisi yok, "etki" hesaplanamıyor. §6 (bağlamsız) üretim akışında kapalı (`light=True`); tek veri pilottaki 11 soru (9'u belgesiz bilindi). Deney önerisi (`eval/rag_etkisi.py` → `eval/sonuclar_rag_etkisi.md`, kota ister → Vertex sonrası):
   - A, üretim: aynı konular ve üretici; (1) kaynaksız (yalnızca konu adı), (2) RAG (`request.retrieve` sayfaları), isteğe bağlı (3) yanlış sayfa. Ölçüt: anahtar doğruluğu (farklı aileden doğrulayıcı, belgeye göre), dayanaksız oranı, hesap sorularında SymPy
   - B, cevaplama: havuzdaki doğrulanmış sorular kaynaksız / aramanın bulduğu sayfa / doğru sayfa ile cevaplatılır (§6 istemi hazır)
   - "Gerçekte doğru" ile "ders notuna dayanıyor" ayrı raporlanır (kaynaksız model genel konuyu bilir ama notun gösterimi/ayrıntısıyla çelişebilir)
5. [ ] Teknoloji listesi: ödev "Python, LangChain, LLM API veya Ollama, ChromaDB, PyMuPDF, Streamlit" diyor; **LangChain hiç kullanılmıyor** (kendi `src/llm/router.py`). Kullanıcı hocaya soracak; gerekirse çekirdek yeniden yazılmaz, 4. maddedeki deney LangChain ile (langchain-core, Chroma retriever) yapılır; raporda gerekçe
6. [x] Gemini sayaç farkı: Google 3.5-flash'ı bizim sayacımız 17/20'deyken "dolu" dedi (muhtemelen başarısız/tekrarlanan istekler de sayılıyor) → Groq'taki `_sync_used` gibi eşitleme ya da 503 denemelerini de saymak
   - **Doğrulandı ve düzeltildi (2026-10-06):** akşam Gemini sürekli 503 "high demand" verdi; pilotun 2 dakikada bir yeniden denemesi (yönlendirici her modeli de iki kez soruyordu) **0 başarılı istekle** iki modelin günlük kotasını bitirdi (Google: "günlük kota doldu"). Yani **503 denemeleri de günlük 20 isteğe sayılıyor.** Düzeltme (`router._busy_rpd`): Gemini'nin rpd'li modelinde yoğunluk → deneme sayaca yazılır, aynı model hemen tekrar sorulmaz, artan sürelerle kapatılır (15 → 30 → 60 → 120 dk). Böylece uzun bir yoğunlukta bile birkaç saatte model başına ~4-5 istek gider. Test: `test_router.test_busy_gemini`. Not: küçük istekler (birkaç token) o sırada geçiyordu, birkaç bin token'lık üretim istekleri reddediliyordu
7. [ ] Genetic Algorithms (EN, 90 s.) için tam havuz (şu an yalnızca sınav isteklerinden 12 soru)
8. [ ] Zorluk dengesi: havuzda zor soru çok az (9/191) → zor üretim hedefi + öğrenci doğru oranıyla kalibrasyon
   - **Uygulandı (2026-10-06, kota harcamayan katmanlar + Gemma ölçümü):** (1) etiket artık zorlanmıyor, `requested_difficulty` ayrı yazılıyor, eski etiketler önbellekteki ham yanıttan geri yüklendi; (2) yapı tavanı + "zor" için iki ayrı bilgi/kural ya da çok adımlı hesap; (3) benzetilmiş öğrenci (sözel ÇS ve D/Y); (4) gerçek çözümlerden Elo; (5) zorlaştırma döngüsü (§2d) sınav isteğinde; (6) istemlerde işlemsel zorluk tanımları ve `evidence_quotes`. Ayrıntı: "Şu an neredeyiz?" ve rehber bölüm 10
   - **Kalan:** (a) pilotun üretim grupları (sözel/hesap merdiveni, zorlaştırma): zor üretilen sorularda sınıf yanılıyor mu? (2026-10-06 akşamı Gemini sürekli 503 verdi; `python -m eval.zorluk_olcumu` önbellekten devam eder); (b) hesap soruları için daha zayıf bir öğrenci modeli (Ministral 3B/8B; Mistral kredisi yok) ya da yalnızca gerçek çözümler; (c) sözel kısa cevap için anlamı karşılaştıran puanlayıcı (hakem §4d; soru başına ek çağrı) → ölçülebilir olur; (d) havuzu ölçmek: `python -m src.simulate --doc <belge>` (sözel ÇS + D/Y ~120 soru × 5 Gemma çağrısı; Gemma kotası ayrı, dakikada 15 istek → saatler sürer); (e) TurkishMMLU (gerçek öğrenci doğru oranlı Türkçe sorular) ile benzetimin geçerliliği — yazarlardan izin; (f) Vertex sonrası zor hedefli havuz üretimi
   - **Bulgu (2026-10-05): "zor" etiketi güvenilir değil.** Zor 11 sorunun hepsi gemini-3.5-flash'tan (qwen 0/56, 3.8-flash 0/14). 8'i sınav isteğinden ve etiket kodla **zorla** konuyor (`generate.py:147`): bunların Bloom düzeyi 1 hatırlama, 5 anlama (kendi tanımımıza göre orta), 2 uygulama. Gerçekten zor olan 2 hesap sorusu (yuvarlak masa, ANANAS) o gün doğrulayıcı qwen yanlış çözdüğü için `needs_review`'da; Nemotron bu ikisini yeterlilik testinde doğru çözmüştü → yeniden doğrulanabilir. Yani doğrulanmış gerçek zor soru ≈ 2-4 / 191. Öneri: (1) Vertex ile qwen yedeğine düşmemek, (2) kod kontrolü: zor istenip Bloom 'remember' / 'understand' gelen soru zor etiketlenmez (üreticinin kendi Bloom alanı; kota yok) — **yalnızca tutarlılık sağlar**: An ve Wang (2026, LITERATURE §7) LLM'in zorluk etiketinin de Bloom düzeyinin de gerçek öğrenci güçlüğünü öngörmediğini gösterdi (ρ=0,06 / 0,02), (3) asıl ölçüm öğrenci yanıtıyla: benzetilmiş öğrenci + varsa gerçek çözümler
   - **Kanıt (2026-10-05, kullanıcının TYT "zor" hesap sorusu isteği, `20261005-225845-db0c`):** Gemini'nin ham yanıtında (llm.sqlite önbelleği) kendi etiketleri 17 sorudan **14 orta, 1 kolay, 2 zor** — "zor üret" talimatına rağmen; kod hepsini "zor" yaptı (istek üretiminde etiket zorlanıyor). Teslim edilen 10 sorunun incelemesi: ~4 kolay (devirli ondalık, tuz karışımı, medyan-mod-açıklık, tepe noktası), 5 orta (klasik özdeşlik / Vieta / basamak), 1 orta-zor (binom sabit terim); durum analizi ya da iki konuyu birleştiren kurgu yok. Kullanıcı da "orta gibi" dedi. Ayrıca istenen sayı tutmadı: 20 istendi, kod 38 aday istedi, Gemini birim başına 1 soru döndürdü (17) → 7 kod kontrolünde elendi, 9 doğrulandı + 1 havuzdan = 10
   - **Araştırma (LITERATURE §8, kullanıcı kararı bekliyor):** sorun yaygın (saha çalışmasında yapay zekâ soruları %60 ↔ uzman %39 doğru; "en zor 10/20'yi seç" bile yetmedi). Önerilen yöntem değişikliği: (a) hesap dersleri için soru başına LLM yerine **konu başına madde modeli** (LLM değişkenli kalıp + SymPy çözümü yazar, kod sınırsız örnek üretir; zorluk "radikal" değişkenlerle: adım, kısıt, durum analizi; kalıp bir kez doğrulanır) → kota ve havuz birlikte çözülür; (b) **zorlaştırma döngüsü** (Evol-Instruct: kısıt ekle / adım artır / iki konuyu birleştir) havuzdaki doğrulanmış sorulardan; (c) zorluk **ölçümle**: zayıf/orta modelle benzetilmiş öğrenci (Gemma 4 bol kotalı adayı), gerçek çözüm oranı biriktikçe kalibrasyon, mümkünse TurkishMMLU (yazarlardan izin) ile sınama; (d) metin dersleri için **kavram grafiği** (çok adımlı = zor); (e) havuz **ders/koleksiyon + konu × zorluk planı** ile (alakasız PDF kendi koleksiyonunda kalır)
   - Öneri: (1) etiket zorlanmasın — modelin kendi etiketi + işlemsel kural; istenen zorlukta soru yoksa açıkça söylensin; eski zorlanmış etiketler önbellekteki ham yanıtlardan geri yüklenebilir (kota yok); (2) zor üretim: iki konudan bağlam, TYT-zor kalıpları (durum analizi, modelleme, tuzak), fazla aday üretip en zorunu seçme; (3) ölçüm: benzetilmiş öğrenci (zayıf model bağlamsız çözer, başarı oranı) + gerçek çözüm oranı biriktikçe
   - Veri sınırı (2026-10-05): `attempts.jsonl` 62 kayıt, 47 farklı soru, soru başına en çok 3, tek kişi → klasik madde analizi (üst/alt %27 ayırt edicilik, %5 altı "işlemeyen çeldirici") **anlamsız**; bir sınava giren bir grup ve soru başına ~20+ çözüm ister. Tek kullanıcıda da anlamlı olan: maruz kalma oranı (soru kaç sınavda çıktı)
   - Fikir (araştırma): benzetilmiş öğrenciler — her soruyu 3 "öğrenci profili" ile çözdürüp doğru oranından ön zorluk; metinden zorluk tahmini zayıf, zayıf modeller zorlanan öğrenciyi daha iyi taklit ediyor. Gerçek kayıtla karşılaştırma için veri yetersiz. "Zor" hedefinde iki kuralı birleştiren soru + yakın kavram çeldiricisi (komşu konular §7'den)
9a. [ ] **Formüllü (LaTeX) notlar:** metin katmanında dağılmış formüllü sayfalar tamamen görsel okumayı bekliyor (test notunda 255/276). Seçenekler: (a) Vertex açılınca toplu görsel okuma (Batch, %50 indirim); (b) ara çözüm: düz yazı satırları sağlam sayfalarda yalnızca sözel sorular için metin katmanını kullanmak, hesap soruları görsel okuma sonrası (kanıt alıntısı kontrolü dağılmış formülü zaten yakalar); (c) sayfaları konu önceliğine göre okutmak (sınavda istenen konular önce). (Bozuk OCR katmanı riski giderildi, 2026-10-07: tam sayfa görüntü + metin = `ocr_layer` → görsel okumada katman ipucu ve yazım düzeltmesi kullanılmaz; mevcut belgelerde böyle sayfa yok)
9. [ ] Rapor (Adım 9): ölçümler hazır (retrieval, duyarlılık, hesap kontrolü, toplu üretim, Bloom); insan değerlendirmesi kullanıcı kararıyla **atlandı** (2026-10-04); 4. maddedeki deney raporun ana bulgusu olmalı

## Adım 1 — Ortam ve API Kurulumu
- [x] 🟡 Groq API hesabı ve anahtarı (test edildi; Llama 3.3 70B artık listede yok → adaylar: `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`)
- [x] 🟡 Google AI Studio (Gemini) API hesabı ve anahtarı (test edildi; `gemini-embedding-2` mevcut)
- [x] 🟢 Python **3.11** ile proje içinde `.venv` oluştur (3.14 değil, gerekçe README §5)
- [x] 🟢 pip önbelleğindeki uygun wheel'leri yerel bir `wheelhouse/` klasörüne çıkar (internetsiz)
- [x] 🟡 Paket kurulumu: `requirements.txt` + `constraints.txt` (önbellekteki sürümlere sabitli). 112 paketin 75'i internetsiz kuruldu, **gerçek indirme ~76 MB**
- [x] 🟢 API anahtarlarını `.env` dosyasında sakla, repoya koyma
- [x] 🟢 Telemetriyi kapat: Streamlit `.streamlit/config.toml` ✓; Chroma için kodda `Settings(anonymized_telemetry=False)` kullanılacak
- [x] 🟢 Sağlayıcıların güncel ücretsiz kota limitlerini not et → `src/llm/models.py` (her modelin rpd/rpm/tpd'si, kaynağıyla) ve README §4.4

## Adım 2 — Örnek Doküman Havuzu
- [x] Slayt PDF'leri: YZ / Genetik Algoritmalar (TR, 18 s.), Çevre ve Ekoloji (TR, 23 s.), Genetic Algorithms (EN, 90 s., döndürülmüş), Bilgisayar Mimarisi Hafta 01 (TR, 35 s.) ve Hafta 02 – Performans (TR, 72 s.)
- [x] Ders notu: TYT matematik özeti (TR, 14 s., formül ağırlıklı → hesap soruları)
- [x] Görsel ağırlıklı: TYT'nin 14 sayfası da görselden okundu; Hafta 02'de 22, GA'da 42 sayfa
- [x] Hepsi `data/sample_docs/` altında (arayüzden yüklenenler de buraya kaydedilir)

## Adım 3 — Ayrıştırma Katmanı 🟢 (fallback 🟡)
Kod: `src/ingestion/` · Çalıştırma: `python -m src.ingestion` · Çıktı: `data/parsed/*.json`
- [x] PyMuPDF ile metin katmanı çıkarımı (blok, font boyutu, **döndürülmüş sayfa** düzeltmesi)
- [x] Üst/alt bilgi temizliği: belgenin ≥%40'ında tekrar eden ve o sayfalarda en büyük yazı olmayan satırlar (tekrar eden slayt başlıkları korunur) + sayfa numaraları
- [x] Başlık tespiti: içindekiler listesi → yazı boyutu → en üst şerit → önceki sayfadan devralma
- [x] Şekil metni ayrımı: gövdeden belirgin küçük kısa satırlar `figure_text` alanına ayrılır (silinmez)
- [x] Türkçe normalizasyon modülü (`src/textnorm.py`, testler: `python -m tests.test_textnorm`)
- [x] Belge dili tespiti (Türkçe harf + stopword sezgiseli)
- [x] Sayfa kalitesi: `ok` / `needs_vision` / `empty` + bayraklar (`title_page`, `toc_like`, `image_heavy`)
- [x] Arka plan tespiti: sayfanın ≥%90'ını kaplayan ya da sayfaların ≥%40'ında tekrar eden görsel = şablon
- [x] Metin kaybı kontrolü: ham PDF kelimeleriyle karşılaştırıldı, gerçek kayıp yok
- [x] Gemini görsel fallback kodu (`src/ingestion/vision.py`): önbellekli, `--yes` olmadan hiçbir şey göndermez
- [x] 🟡 Görsel fallback (2026-10-05: tüm belgelerde bekleyen sayfa yok) — ilk tur: 37 sayfanın 31'i okundu (21'i `gemini-2.5-flash`, 10'u `gemini-3.5-flash`; hangi sayfanın hangi modelle okunduğu `data/vision_cache/_models.json` ve sayfa JSON'undaki `vision_model` alanında). Kalan 6 EN sayfa (63, 76, 81, 86-88; ~0,7 MB) kota sıfırlanınca → `python -m src.ingestion --vision --yes`
- [x] Görsel okuma doğrulaması: EN s52 tablosu matematiksel olarak tutarlı (ikili→ondalık, x=2n/63, f=|sin πx|); EN s62 Matlab kodu görselle birebir. Not: s62'deki `x0(i)*randn(1)*sigma` slaytın kendisinde böyle (muhtemelen slayt hatası) — sistem dokümana sadık kaldığı için dokümandaki hatayı da yansıtır (rapor için "bilinen sınır" örneği)
- [x] Görsel okuma kontrolü: YZ s11'deki 10 tablonun rakamları görselle birebir tuttu; Ekoloji s21 kolajı yalnızca [FIGURE] olarak geçti
- [x] Görsel okumanın yazım hatasına karşı iki önlem: (1) istemde metin katmanı ipucu (yeni sayfalar için), (2) metin katmanına ≥%88 benzeyen satırların düzeltilmesi (`snap_to_text_layer`, internetsiz)
- [x] Kota/yoğunluk dayanıklılığı: 503'te sınırlı tekrar; 429 iki kez gelirse tüm iş durur (her tekrar görüntüyü yeniden yüklediği için)

**Okuma doğruluğu kontrolü (2026-10-02):** `python -m src.ingestion.review` → `data/review/index.html` (her sayfanın görüntüsü + çıkarılan metin yan yana, internetsiz). Bulgular:
- [x] Düz metinli slaytlar birebir doğru (Ekoloji s13 vb.); görselden okunan sayfalar kontrol edilenlerde doğru (YZ s11, EN s40, s52, s62)
- [x] HATA düzeltildi: sayfa numarası kuralı (`sayfa_no ± 2`) içerikteki sayıları siliyordu (EN s20 diyagramındaki dört "22"). Artık belge başına tek bir numara kayması hesaplanıp sayfa başına yalnızca bir satır siliniyor
- [x] HATA bulundu: tablo/formül içeren sayfalarda metin katmanı bozuk (düzleşmiş tablo, formül parçaları, özel font kodlaması) ama sayfa "ok" sayılıyordu. Yeni `noisy_text` ölçütü (satırların ≥%40'ı parça) 17 sayfa buldu (YZ 3, EN 14); incelenen 5'in 5'i gerçekten bozuk. Bunlar artık görsel okumaya gidiyor; parçaları `pending_vision` ile işaretli, soru üretiminde kullanılmayacak
- [x] 🟡 Görsel okuma kuyruğu: 23 sayfa (~3 MB; 6 eski + 17 bozuk metinli) — okundu

**Ortak model katmanı ve GPU'suz okuma (2026-10-02):**
- [x] `src/llm/`: tüm LLM çağrıları tek kapıdan (`router.call(rol, istem, görüntü)`): rol → model zinciri (`models.py`), kota defteri + yanıt önbelleği (`data/llm.sqlite`), dakikalık hız ayarı, günlük kota dolunca sıradaki modele geçiş, görüntü yüklemeden önce metin yoklaması. Görsel okuma artık bu katmandan geçiyor
- [x] GPU kullanılmıyor (kullanıcı tercihi): bozuk metinli tablo sayfaları PyMuPDF `find_tables` ile işlemcide (~ms) okunuyor → EN s22, 33, 35, 36 Gemini'ye gitmiyor. Sahte tablo filtreleri: doluluk < %50, tek hücreli satır > %40, 8 satırdan uzun "konteyner" hücre; hücrelere bölünerek sızan alt bilgi temizleniyor
- [x] Bozuk formül dedektörü (token'ların yarısından fazlası tek karakter) → YZ s4/s6, EN s28/41/43/82/89 görsel okumaya
- [x] Bloklara bölünmüş cümleler birleştiriliyor ("...rotasyonuna" + "dayandığından...")
- [x] Regresyon testleri: `python -m tests.test_parser` (11 test, her biri bulunan bir hatayı sabitliyor) + `python -m tests.test_textnorm`
- [x] 🟡 Görsel okuma kuyruğu: 22 sayfa (~2,8 MB) — okundu

**Kota gözlemi (2026-10-03) — Groq:** asıl sınır **token/gün = 200.000 / model** (kayan 24 saat; istek sınırı 1000/gün değil). Bir günde qwen ile görsel okuma (22 sayfa) + iki pilot + deney başlangıcı bunu doldurdu. İlk sürümde kod bu hatayı 'gün boyu dolu' sanıp yedek modele geçti ve deneyi bozdu → düzeltildi: süreli bekleme (`parse_wait`, `set_cooldown`), kayan token sayacı (`tokens_24h`), testler `python -m tests.test_router`.

**Kota gözlemi (2026-10-01):** `gemini-2.5-flash` ücretsiz katmanı **20 istek/gün** (hata mesajındaki `GenerateRequestsPerDayPerProjectPerModel-FreeTier: 20`); kota model başına ayrı. `gemini-3.5-flash` da ~10-15 istekten sonra doldu. Bu, Gemini'yi doğrulama katmanında (soru başına 1-2 çağrı) ana model olarak kullanmayı imkânsız kılıyor → Adım 7'de doğrulayıcı model seçimi buna göre yeniden yapılacak (Groq'ta farklı model ailesi ya da kotası ayrı bir Gemini modeli).

Sonuçlar (3 örnek PDF):
| Belge | Sayfa | Görsel okuma | Not |
|---|---|---|---|
| Yapay Zeka (TR slayt) | 18 | 1 (s11: taranmış akış şeması + tablolar) | Başlıklar TOC + üst şeritten doğru |
| Çevre ve Ekoloji (TR slayt) | 23 | 6 (s8, 17-21) | s2 ünite listesi `toc_like` |
| Genetic Algorithms (EN slayt, 90° döndürülmüş) | 90 | 30 (tablo, grafik, kod görüntüsü) | Üst bilgi + tarih 279 satır temizlendi |

Bilinen sınırlar: metin katmanındaki formüllerde üs/alt indis kaybolur ("x2" = x²); dağınık formül parçaları (YZ s4, s6) gövde metninde kalabilir.

## Adım 4 — Chunking ve Embedding
Kod: `src/chunking/`, `src/retrieval/embedder.py` · Çalıştırma: `python -m src.chunking` (internetsiz)
- [x] 🟢 Parça = sayfa/slayt (uzun sayfa paragraf sınırından bölünür); bölüm = aynı/benzer başlıklı ardışık sayfalar ("Simple Genetic Algorithm(s)", "Organik Tarım" ⊂ "Organik Tarım suyu korur")
- [x] 🟢 Dizin dışı: kapak (ilk sayfa < 300 karakter), içindekiler benzeri sayfa, kaynakça — gerekçesiyle `skipped.jsonl`
- [x] 🟢 Metadata: dosya, sayfa, bölüm id, başlık, dil, kaynak (`text`/`vision`), görsel model, içerik özeti (hash)
- [x] 🟡 Embedding: **`gemini-embedding-001`, 768 boyut** (README'deki "Embedding 2" yerine — gerekçe `embedder.py` başında: 2 numaralı model metin listesini tek vektöre birleştiriyor; 768 boyut indirmeyi 4 kat azaltıyor)
- [x] 🟢 Embedding önbelleği (metin özeti → vektör): aynı metin bir daha gönderilmez; yeniden ayrıştırmada yalnızca değişen parçalar gider
- [x] 🟡 Çok dillilik: TR "çaprazlama" ↔ EN "crossover" benzerliği 0,89, alakasız cümle 0,67
- Sonuç: 3 belge → **124 parça, 63 bölüm**; gönderilen metin 43 KB, toplam ~1,5 MB
- Kota: embedding ücretsiz katmanı **dakikada 100 metin** (toplu istekte her metin sayılır) → kod dakikalık sınırda bekleyip devam ediyor
- [x] Kısa bölümler üretimde birleştiriliyor (Adım 6: <400 karakterlik bölüm sonrakiyle bir birim olur)

## Adım 5 — Vektör DB ve Hibrit Retrieval 🟢
Kod: `src/retrieval/index.py` · `python -m src.retrieval build` · `python -m src.retrieval search "sorgu" [hybrid|dense|bm25|bm25_plain]`
- [x] ChromaDB (yerel, cosine). Embedding'leri biz veriyoruz → Chroma'nın varsayılan modeli indirilmedi
- [x] BM25: normalize + stopword'süz + kelimenin ilk 5 harfi (F5). Köklemesiz BM25 ablasyon için ayrıca var
- [x] RRF (k=60) ile dense + BM25 füzyonu; sorgu dili parça dilinden farklıysa o parça için BM25 yok sayılır
- [x] Elle kontrol (6 konu sorgusu):
  - F5, köklemesiz BM25'ten açıkça iyi ("turnuva seçimi", "çaprazlama operatörleri" sorgularında köklemesiz BM25 neredeyse hiç sonuç bulamıyor)
  - Dense, diller arası çalışıyor (TR "turnuva seçimi" → yalnızca EN'de olan "Tournament selection" 2.-3. sırada)
  - Görselden okunan sayfa bulunabiliyor (Ekoloji s18 "su tutma" sorgusunda 1. sırada)
  - ⚠️ "turnuva seçimi"nde hibrit < dense: TR slaytlardaki genel "seçim" kelimesi BM25'te rulet seçimini öne çıkarıyor
- [x] Etiketli test setiyle karar verildi (Adım 9 ablasyonu): **varsayılan dense**; hibrit ve BM25 yalnızca karşılaştırma için kodda
- [~] Bağlam genişletme: sınav isteğinde bir konudan çok soru istenince komşu parçalar da bağlama eklenir (`request._unit(wide=True)`); bölümün tamamı verilmiyor

## Adım 6 — Soru/Cevap Üretimi 🟡
Kod: `src/generation/` · Pilot: `python -m src.generation.pilot "<belge>" model1,model2` → `data/pilot/rapor.md`
- [x] PROMPTS.md §2 şeması + Pydantic (`schema.py`); bozuk soru tek tek elenir, partinin tamamı atılmaz
- [x] Üretim birimi = bölüm; <400 karakterlik bölümler sonrakilerle birleşir, >4000 bölünür; görsel okuma bekleyen parçalar kullanılmaz; komşu bölümler çeldirici havuzu (`{related}`)
- [x] Şıklar kodda deterministik karıştırılıyor (konum yanlılığı)
- [x] Kod kontrolleri (`src/verification/checks.py`, testler: `python -m tests.test_checks`): kanıt metinde mi (normalize + rapidfuzz; LaTeX temizlenir), metne atıf ("metinde", "bu … stratejisi", "verilen örnekte"), cevap–şık tutarlılığı, uzunluk ipucu, kelimesi kelimesine kopya ipucu, D/Y'nin ifade olması, tekrar
- [x] **Pilot (YZ slaytı, 6 birim, 10'ar soru, Groq):**
  | Model | Kontrolden geçen | Gözlem |
  |---|---|---|
  | `qwen/qwen3.8-27b` | **9/10** | Daha çok anlama/uygulama sorusu (ör. "pc=0.25 iken ρ hangi koşulu sağlamalı?"), çeldiricileri komşu slaytlardan alıyor; kökler bazen uzun ve ipucu veriyor |
  | `openai/gpt-oss-120b` | 7/10 | Daha kısa ve basit sorular; doğru şık sık sık daha uzun (uzunluk ipucu); 1 soruda alıntıyı iki yerden birleştirmiş |
  - İlk sürümde redlerin 4'ü **kontrol hatasıydı** (D/Y cevabı "Yanlış" yazılmış, cevap–şık tek yönlü içerme, LaTeX'li kanıt); düzeltildi ve önbellekten (0 API çağrısı) yeniden puanlandı
  - Konum yanlılığı: gpt-oss doğru cevabı 7'nin 6'sında A'ya, qwen 7'nin 6'sında B'ye koydu → karıştırma şart
  - Karar: **üretim = qwen, doğrulama = gpt-oss-120b** (farklı aileler)
- [x] **`output_language` testi — İngilizce GA slaytı → Türkçe soru** (`python -m src.generation.pilot english qwen/qwen3.8-27b tr 12`): sorular Türkçe, kanıt alıntıları İngilizce slayttan birebir
  | | v1 (ilk istem) | v2 (tip planı + aynı türden şıklar) |
  |---|---|---|
  | Doğrulanan | 9/12 | **12/12** |
  | Tipler | 12 ÇS | 9 ÇS, 2 KC, 1 D/Y |
  | Uzunluk ipucu | 4 | 1 |
  | Yalnızca-şıklarla bulunan ÇS | 6/10 | 6/9 (değişmedi) |
  - v1'de iki "aynı şık" reddi **kontrol hatasıydı** (sıra soran soru, yer değiştirince anlamı dönen şıklar) → kural "öz alt küme" olarak düzeltildi
  - Model doğru cevabı bir kez yalnızca çeldirici için verilen komşu bölümden aldı → kanıt kontrolü yakaladı
  - **Bulgu:** yalnızca-şıklar testi de (dokümansız test gibi) modelin dünya bilgisiyle karışıyor — tanım türü şıklarda çeldiriciler gerçekte yanlış ifadeler olduğu için konuyu bilen model (ve öğrenci) doğruyu soru görmeden tanır. Ret nedeni değil, bilgi olarak kullanılacak
  - Yeni bayrak `vision_evidence`: kanıt, görsel okuma modelinin yazdığı metinden (5/12) → arayüzde daha düşük güven
  - Bilinen sorun: Türkçe yazım hataları ("grafikinde", "çöüzümleri") — Qwen'in Türkçe üretimi
  - **YZ slaytında v1 → v2 (yeni istem):** qwen 9/10 → **11/13** doğrulandı (D/Y 1 → 4); gpt-oss 7/10 → 10/13, uzunluk ipucu 4 → 0. Doğrulanan soruların çoğu hâlâ "hatırlama" düzeyinde (qwen 7/11, gpt-oss 9/10) → README §7.4'teki "sadakat ↔ bilişsel düzey" ödünleşimi beklentisiyle tutarlı; Adım 9'da ölçülecek
- [x] **Hesap soruları (2026-10-04, PROMPTS.md §2c, `src/generation/compute.py`):** TYT matematik özetinde §2 64 soru üretti ama yalnızca 2'si hesaptı (gerisi "formül ne anlama gelir?"). Formül içeren bölümlerden (`math_units`) toplu istekle uygulama problemleri; model cevabı hesaplayan bir SymPy ifadesi ve her şıkkın değerini de yazar
  - Kod kontrolü: ifade AST beyaz listesinden geçer (öznitelik, dunder, string, import yok), ayrı süreçte 10 sn sınırla hesaplanır; anahtar ≠ sonuç, iki şık sonuca eşit, şık metni ≠ değeri → red. Testler: `python -m tests.test_compute`
  - Kör çözüm (§4e): farklı aileden doğrulayıcı soruyu ifadeyi/çözümü/anahtarı görmeden çözer
  - **Sonuç (TYT, gemini-3.5-flash, 18 formüllü bölüm, 2 istek):** 33 problem → SymPy 33/33, tekrar 3, **kör çözümle doğrulanan 30/30** (23 ÇS + 10 KC; zorluk 17 kolay / 15 orta / 1 zor). İlk çalıştırmada 1 red **kontrol hatasıydı** (denklem sisteminde `[x]` indeksi beyaz listede yoktu) → düzeltildi, önbellekten yeniden puanlandı
  - **Kod kontrolünün duyarlılığı** (`python -m eval.compute_check`, API yok): yanlış anahtar 20/20, iki doğru şık 20/20, şık metni–değer çelişkisi 19/20 yakalandı; bozulmamış sorularda yanlış alarm 0/20
  - Kalite kapısı: §2c yeni bir görev; Gemini kotası biterse hesap adımı **atlanır**, sınanmamış modele devredilmez
  - Açık: "zor" problem çok az (1/33) — zorluk hedefi istemde ayrı verilmeli; öğrenci istatistikleriyle zorluk kalibrasyonu
- [-] Kullanıcı incelemesi (`data/pilot/rapor.md`) — insan değerlendirmesi kullanıcı kararıyla atlandı (2026-10-04)

## Adım 7 — Doğrulama Katmanı
Kod: `src/verification/` · `python -m src.verification <sorular.jsonl>` → `data/pilot/dogrulama.md` · Duyarlılık: `python -m src.verification.sensitivity <..._dogrulama.jsonl>`
- [x] 🟢 Kod kontrolleri (Adım 6) + yeni: neredeyse aynı şıklar (bir şıkkın kelimeleri diğerini kapsıyorsa; sayısı/anlamı farklı şıklar hariç), kesin ifadeli çeldiriciler ("yalnızca", "her zaman", "zorunlu"…)
- [x] 🟡 Kör doğrulama, **üreticiden farklı model ailesi** (qwen soruları → gpt-oss, gpt-oss soruları → qwen):
  - Çoktan seçmeli: her şık ayrı ayrı "correct / incorrect / unknown" (§4a); yalnızca anahtar doğruysa `verified`
  - Doğru/Yanlış: SUPPORTED / CONTRADICTED / NOT_IN_CONTEXT (§4b); metinde olmayan ifade → `rejected`
  - Kısa cevap: kör cevap → kodla eşleşme, olmazsa hakem (§4d)
  - Dokümansız (§6) ve **yalnızca-şıklar** (§6b) testleri → `closed_book_correct`, `choices_cue`
- [x] **Doğrulayıcı duyarlılık testi** (kasıtlı bozulmuş 17-19 soru, cevabı bilinen):
  | Bozulma | 1. sürüm (tek seçim) | 2. sürüm (her şık ayrı) |
  |---|---|---|
  | Yanlış cevap anahtarı | 7/7 | 6/6 |
  | İki doğru şık | **5/7** | **6/6** |
  | D/Y ters çevrilmiş | 1/1 | 1/1 |
  | Gerçekte doğru ama slaytta yok ("GA'yı Holland önerdi") | 3/3 | 3/3 |
  | Yanlış kısa cevap | 1/1 | 1/1 |
- [x] Pilot sonucu: qwen 9/10 `verified`, gpt-oss 7/10. **Yalnızca-şıklar testi:** gpt-oss'un çoktan seçmelilerinin 3/4'ünde, qwen'in 2/7'sinde doğru şık soru görülmeden bulundu (çeldiriciler zayıf) → üretim = qwen kararını destekliyor
- [x] Bulgu: dokümansız test (§6) genel konularda modelin dünya bilgisini ölçüyor (11 sorunun 9'u bilindi) → tek başına zayıf sinyal; asıl kalite sinyali §6b
- [ ] Toplu doğrulama (4-5 soru tek çağrıda) — tek tek doğrulamayla isabet karşılaştırması; artık kota planının parçası (en üstte "Sıradaki işler" 2)
- [ ] Nihai etiket politikası: `verified` + (`choices_cue` | `length_cue` | `absolute_distractors`) → arayüzde "zayıf çeldirici" uyarısı

## Adım 8 — Arayüz 🟢
Çalıştırma: `.venv\Scripts\streamlit run src/app.py` → http://localhost:8501 · Kod: `src/app.py`, `src/ui/` (sayfalar, `style.py`, `data.py`), `src/export.py`
Görsel dil: "akademik baskı + fosforlu kalem" — kâğıt dokulu zemin, mürekkep laciverdi, kanıt için sarı vurgu; Fraunces (başlık) + Instrument Sans (gövde) + JetBrains Mono; koyu kenar çubuğu (`.streamlit/config.toml`)
- [x] **Genel Bakış:** ana sayılar, 6 adımlı akış şeması (gerçek sayılarla), belge kartları, inceleme ilerlemesi, arka plan işleri
- [x] **Yükle ve Üret:** PDF yükleme, soru dili seçimi (EN slayt → TR soru), maliyet tahmini, akışı ayrı süreçte başlatma (sayfa kapansa da sürer), canlı adım/kota bekleme göstergesi
- [x] **Belgeler:** sayfa sayfa PDF görüntüsü + çıkarılan metin + kaynak rozetleri (metin/görsel/tablo/bekleyen), bölümler tablosu, okuma kalitesi
- [x] **İnceleme:** tek soru kartı, kanıt sayfada fosforlu, "önce kendin çöz" (cevabı gizle) modu, yapılandırılmış red nedenleri, doğrulama ayrıntıları (her şık için karar)
- [x] **Soru Bankası:** belge/durum/tip/düzey/insan kararı süzgeçleri; dışa aktarma: **Moodle GIFT**, yazdırılabilir sınav kâğıdı (cevap anahtarı + kanıtlar ayrı sayfada), CSV (Excel uyumlu), JSON
- [x] **Değerlendirme:** arama (vurgu çubuğu + kategori küçük çoklu), doğrulayıcı duyarlılığı, bilişsel düzey deneyi, toplu üretim, insan değerlendirmesi — grafikler `dataviz` yönergesiyle; durum ve kategorik paletler `validate_palette.js` ile doğrulandı
- [x] **Sistem ve Kota:** kalite kapısı (onaylı/aday modeller ve kanıtları), 24 saatlik kota kullanımı, ücretli katman maliyet tahmini
- [x] Testler: 7 sayfanın hepsi Streamlit `AppTest` ile tarayıcısız açıldı (hata yok); dışa aktarma biçimleri test edildi
- [x] Gerçek tarayıcıda görsel kontrol (kullanıcı ekran görüntüleriyle geri bildirim verdi; düzeltmeler aşağıda "Sınav İsteği" bölümünde)
- Not: sayfa yapısı 2026-10-04'te değişti → 6 sayfa: Sınav Hazırla · Belgeler (yükleme dahil) · Soru Bankası · İnceleme · Rapor · Modeller ve Kota

## Sınav İsteği — RAG akışı ve kullanıcı odaklı arayüz (2026-10-04)
Kod: `src/topics.py`, `src/request.py`, `src/ui/pages/exam.py` · İstem: PROMPTS.md §7
- [x] **Konu haritası** (belge başına 1 Gemini isteği, önbellekte): TYT'nin "01, 02…" bölüm başlıkları yerine 18 konu ("Bölme, Bölünebilme ve EBOB-EKOK"…); Ekoloji 15, YZ 12, GA 18. Kota yoksa bölüm başlıkları
- [x] **Seçimle istek** (serbest metin yok): belge · konu · zorluk (Kolay/Orta/Zor/Karışık) · tip (hesap yalnızca formüllü belgede) · sayı
- [x] **Arama:** konu adı = sorgu, seçili belgelerde dense arama; örnek: "Rulet Tekerleği Seçimi" → YZ s.15-17; "Permütasyon ve Kombinasyon" → TYT s.10
- [x] **Havuz:** o sayfalara bağlı, doğrulanmış, reddedilmemiş/bildirilmemiş sorular anında; TYT'den 10 soruluk istek tamamen havuzdan (0 token)
- [x] **Hedefli üretim** (eksik varsa, arka planda): yalnızca bulunan sayfalar, zorluk istemde kural olarak (`DIFFICULTY_TARGET`), %40 fazla istenir (fazlası havuza)
- [x] **Sınav:** çöz → puan, zayıf konular, yanlışlarda çözüm + kaynak; "hatalı bildir" (soru incelenene kadar sınavlara girmez); yazdır / Moodle / CSV
- [x] **Madde analizi:** her çözüm kaydedilir (`data/review/attempts.jsonl`); Soru Bankası ve Rapor'da soru başına doğru oranı
- [x] **Doğrulama kapasitesi:** iki gpt-oss'un kayan 24 saatlik kotası dolunca sınav istekleri bekliyordu → qwen üçüncü doğrulayıcı (duyarlılık 19/19; sağlam sorularda 9/11, 2'si temkinli "incelemeye") — yalnızca qwen'in üretmediği sorular için
- [x] **Bulgu — hesapta ayrı onay (`verify_math`):** zor kombinatorikte qwen iki problemde de yanıldı (yuvarlak masa 1440 ≠ 360; ANANAS 120 ≠ 12), SymPy doğruydu → hesap sorularının kör çözümü yalnızca gpt-oss'ta; uyuşmazlık "incelenmeli"ye düşer, yanlış soru geçmez
- [x] Bekleme süresi artık kayan pencereden hesaplanıyor (`ledger.time_until_available`) ve arayüzde gösteriliyor ("~1 sa 40 dk sonra devam")
- [x] Arayüz 7 sayfadan 5'e: Sınav Hazırla · Belgeler (yükleme dahil) · Soru Bankası · İnceleme · Rapor (nasıl çalışır / ölçümler / modeller ve kota); kartta yalnızca tip + zorluk, teknik uyarılar ayrıntı panelinde; yoğun sayfada kaynak görüntüsü kanıtın çevresine yakınlaştırılır
- [x] **Kaynak metin düzeltmesi (kullanıcı geri bildirimi, ekran görüntüleriyle):** kanıt alıntısında 'bü-tün', '2n' (2ⁿ olmalı), LaTeX ('\frac{100 \cdot a}{a+b}'); PDF'te sarı işaret eksik/parçalı
  - Kök neden 1: metin katmanı üst simgeleri kaybediyordu — TYT'de 449, YZ'de 26 üs; YZ s9 '11010 = 1·2⁴ + 1·2³…' metne '1.24 + 1.23…' diye geçmişti (soruların kaynağı matematiksel olarak yanlıştı). Ayrıştırıcı artık küçük+yükseltilmiş yazıyı üst simgeye, alçaltılmışı alt simgeye çeviriyor (yön satırın yazı yönüne göre; döndürülmüş EN slaytında x₁…xₙ doğru). Denklem editörü satırlarında (𝑥, 𝑓) konum güvenilmez → dönüştürülmez (ilk denemede x₁ → 'x¹' yaptı, yakalandı)
  - Kök neden 2: görsel okuma istem kuralı 6 metin katmanının yazımını kopyalatıyordu → bozuk '2n' görsel metne de geçmişti. Önbellekteki okumalar düzeltilmiş metin katmanından onarıldı (`vision.repair_from_layer`), yeni Gemini isteği yok; kural 4 artık Unicode üst/alt simge istiyor
  - Kök neden 3: Unicode normalleştirmesi (NFKC) 'x²'yi 'x2' yapıyordu → simgeler korunuyor; karşılaştırmada düzleşiyor
  - Satır sonu tireleri belge düzeyinde: birleşik yazım belgede geçiyorsa 'bü-tün' → 'bütün', 'meta-sezgisel' korunur
  - Mevcut sorular: kanıt alıntıları güncel metinden birebir yeniden alındı (`python -m src.requote --yaz`); kanıtı kaybolan soru 0; üssü bozuk metinden etkilenmiş soru 0 (alt simgeler anlamı değiştirmediği için sayılmıyor)
  - İşaretleme: birebir arama yerine kelime düzeyinde yerel hizalama (satır sonu, kesir, LaTeX, üs farkına dayanıklı); metin katmanlı sayfalarda 280 sorunun 246'sı işaretleniyor, kalanların hepsi metni resim olan sayfalar
  - Ekranda LaTeX ve '^' gösterimi okunur Unicode (`textnorm.pretty_math`): kesir, 2ⁿ, x₁, ≤
- [x] **Modeller ve Kota** ayrı sayfa olarak geri geldi: şu an kaç belge/soru/sayfa işlenebilir, model kartları (durum, kullanım, TR saatiyle sıfırlanma), hangi iş hangi modelle (kalite kapısı kanıtları), ücretli maliyet
- [x] **Ek sağlayıcı altyapısı (2026-10-04):** OpenAI uyumlu genel çağrı (`router._call_openai_compat`, ek kütüphane yok); OpenRouter ve Cerebras; anahtarı olmayan sağlayıcının modeli zincirde atlanır. Groq'un OpenAI uyumlu ucuyla gerçek istekle sınandı (JSON modu, token sayımı, 404 → 'missing')
  - Araştırma: Cerebras'ta kalıcı ücretsiz katman yok (2026-10-05 araştırması bununla çelişiyor → Kota bölümü) (kart + 30 günlük 5 $ kredi; model başına 1M token/gün; modeller zaten kullandığımız gpt-oss-120b ve qwen3.8-27b). OpenRouter ücretsiz modelleri: günde 50 istek, bir kez 10 $ kredi alınınca günde 1.000; Nemotron 3 Ultra yeni bir aile (hem Gemini'nin hem qwen'in sorularını doğrulayabilir)
  - Adaylar `CANDIDATES`'ta; onay için `python -m src.qualify <model>`: metin doğrulama (kasıtlı hatalar + sağlam sorular), hesap (SymPy'nin doğruladığı TYT problemleri, kaydırılmış anahtar, qwen'in yanıldığı 2 zor problem) → `eval/yeterlilik/` ve onay önerisi
- [x] **Nemotron 3 Ultra onaylandı (OpenRouter ücretsiz, 2026-10-04):** kasıtlı hatalar 10/10, sağlam sorular 6/6, hesap 12/12 (qwen'in yanıldığı iki zor problem dahil), kaydırılmış anahtar 5/5 → `verify` (gpt-oss'lardan sonra, qwen'den önce) ve `verify_math`. Yeni aile: qwen'in ürettiği sorular için de üçüncü doğrulayıcı
  - İlk çalıştırma 'onaylanmamalı' dedi ama **ölçüm hatasıydı**: zorunlu JSON modunda Nemotron cevap yazamadan sınıra dayanıyordu (finish=length, içerik '{}'); modsuz aynı istem 288 token'da doğru. Ayrıca boş '{}' geçerli JSON sayılıp önbelleğe alınmıştı → düzeltildi (boş JSON önbelleğe alınmaz), doğrulayıcı JSON ayrıştırıcısı bozuk JSON'da alanları tek tek çıkarıyor
  - Sınır: günde 50 istek (10 $ tek seferlik kredi → 1.000); örneklem kısa (6 sağlam + 12 bozuk metin, 12 + 5 hesap)
- [x] **Öğrenme ve öğretmen özellikleri (2026-10-04, ek istek yok):**
  - Kademeli ipucu (Sokratik): her soruda 1) nereye bakmalı (konu + sayfa), 2) kural / kaynak cümle, 3) hesapta ilk adım
  - Yanlışları tekrar çöz: ikinci deneme yalnızca yanlışlarla; ikinci denemeler madde istatistiğine girmez (güçlük ilk denemeden)
  - Kısa cevap itirazı: otomatik karşılaştırma yanılabilir → öğrenci itiraz eder, puanına yansır ("itirazla"), soru İnceleme'ye düşer
  - Şeffaflık: sınav ekranı, sınav kâğıdı ve Moodle geri bildiriminde "yapay zekâ ile üretildi, kaynağa bağlandı, farklı modelle doğrulandı" notu (YÖK 2024 rehberi)
  - Moodle XML: konu kategorileri (konu haritasından), zorluk/tip/doğrulandı etiketleri, şık başına geri bildirim, genel geri bildirimde çözüm + kaynak; kısa cevaplı hesap soruları **sayısal** soru tipi. GIFT de kategori ve geri bildirimle zenginleşti
  - Soru yazım kuralları (SAQUET'in 19 kuralından): 'hepsi / hiçbiri' şıkkı → red; vurgulanmamış olumsuz kök ve kökle tekrar ipucu (5 harflik köklerle) → uyarı. Havuzda: 0 red, 8 tekrar ipucu, 1 olumsuz kök
  - Hata adıyla çeldirici (DiVERT fikri): yeni sorularda `option_notes` — her çeldiricinin temsil ettiği hata; öğrenci o şıkkı seçince "Bu şıkkı seçtiysen: …", Moodle'da şık geri bildirimi. Yalnızca istem değişikliğinden sonra üretilen sorularda
- [x] **Kısa cevap puanlama hatası (kullanıcı ekran görüntüsü, 2026-10-05):** beklenen '(n choose 2) * 2' iken '2' cevabı DOĞRU sayılıyordu (token_set_ratio bir kümenin diğerini içermesine 100 veriyor); beklenen '9! / (3! · 2!)' iken doğru sonucu (30240) yazan öğrenci YANLIŞ sayılırdı
  - `src/grading.py`: matematiksel cevaplarda iki taraf SymPy ile hesaplanıp değer karşılaştırılıyor (30240 = 9!/(3!·2!) = 362880/12; n(n−1) = 2·C(n,2)); metin cevaplarda uzunluğu da yakın eşleşme, Türkçe ek-fiil ('tanımsızdır' = 'tanımsız'). Öğrencinin ifadesi güvenilmez girdi: AST beyaz listesi + büyüklük sınırları (iç içe üs, büyük faktöriyel reddedilir). Testler: `python -m tests.test_grading` (29 durum)
  - Gösterim: '(n choose 2) * 2' → 'C(n, 2) · 2 = n·(n − 1)'; '9! / (3! · 2!) = 30240'
  - İstem §2 (yeni üretimler): kısa cevap sonuçlanmış değer olmalı; nottaki çözümlü örnek aynı sayılarla soruya dönüştürülmemeli (ÇANAKKALE örneği nottan kopyaydı)
- [x] **Sınav deneyimi yeniden tasarlandı (2026-10-05, `src/ui/quiz.py`):** başlangıç ekranı (özet, tahmini süre, kısayollar) → **odak modu** (kenar çubuğu gizli, tek soru, büyük şık kartları, ilerleme çubuğu, süre sayacı, soru haritası, geçiş animasyonu, klavye: A–D / ← → / H, boş soru varken onay penceresi; ipucu parlayarak açılır ve ekran ona kayar) → **sonuç ekranı** (halka grafik doğru/yanlış/boş, süre ve ipucu sayısı, konulara göre yığılmış çubuk grafik, gözden geçirme süzgeci). İpucu kullanımı da kaydediliyor. CSS büyük harf dönüşümü Türkçe (`lang="tr"`: 'İPUCU')
- [x] **Sınav ekranı düzeltmeleri (kullanıcı ekran görüntüsü, 2026-10-05):**
  - `StreamlitDuplicateElementId`: sonuç ekranında iki "Yeni sınav" düğmesi aynı kimliği alıyordu → anahtarlar (`new_exam_top`, `new_exam_bottom`, `res_retry`, `res_restart`)
  - Ekran oynamasın: soru kartı sabit en az yükseklikte ve metin ortada (`.nr-focus`), cevap alanı tipten bağımsız sabit yükseklikte (`.st-key-nr_answer`, `.st-key-nr_opts`), gezinme (Önceki / İpucu / Sonraki) altta yapışık (`.st-key-nr_nav`), soru haritası en üstte; ÇS ve kısa cevap ekran görüntülerinde düğmeler aynı yükseklikte
  - Yeni soru ekranın ortasından ölçeklenerek gelir (`nr-pop`); süre sayacı her tıklamada titremez (şeffaf, içeriği sabit `st.iframe`; klavye dinleyicisi her yüklemede değiştirilir)
  - Kısa cevapta büyük giriş kutusu + yazım yardımı ("30240 ile 9!/(3!·2!) aynı sayılır…")
- [-] Kullanıcı başına kota (kendi anahtarını getir, BYOK) — **reddedildi** (kullanıcı: "millet kendi apisini getirmekle uğraşırsa sistem kullanılabilir olmaz"); kapasite sistem tarafında çözülecek → Kota bölümü
- Genetic Algorithms havuzu ve zorluk kalibrasyonu → en üstteki "Sıradaki işler"

## Kota Mimarisi (2026-10-03) — kota hızı etkiler, kaliteyi değil
- [x] Gerçek token sayımı: sağlayıcının bildirdiği kullanım (gpt-oss'un gizli akıl yürütme token'ları dahil); kayan 24 saat sayacı
- [x] Kalite kapısı: `APPROVED` (kanıtlı) / `CANDIDATES` (test bekleyen); otomatik zincirde yalnızca onaylılar; onaylı doğrulayıcı yoksa açık hata
- [x] Görsel okuma sırası: Gemini → Qwen (Qwen'in token bütçesi üretime)
- [x] `python -m src.llm.capacity` — kalan bütçe ve belge başına maliyet/süre
- [x] `python -m src.pipeline "<pdf>" [dil]` — uçtan uca, kota dolunca bekleyip devam eden akış → `data/questions/`; arayüz bu setleri de listeler
- [x] 🟡 Aday testleri: gpt-oss-20b doğrulayıcı onaylandı (20/20); Gemini 3.8 / 3.5 Flash toplu üretici onaylandı (`generate_batch`); Nemotron 3 Ultra onaylandı (2026-10-04). Hâlâ aday: gemini-2.5-flash (doğrulayıcı, test edilmedi), Nemotron Super, Cerebras kopyaları (anahtar yok)
- [x] 🟡 Sabit kural metnini paylaştırma: toplu üretim (§2b) — bir istekte bir grubun tüm birimleri (`eval/sonuclar_toplu_uretim.md`)
- [ ] Ölçülmemiş: TPD sınırının gpt-oss için de 200k olduğu varsayımı (ilk 429'da mesajdan doğrulanacak)

## Kota — kök çözüm analizi ve karar (2026-10-05)
**Ölçüm** (`data/llm.sqlite`, 1-5 Ekim; gerçek kullanım):
- Doğrulanmış soru başına ~2.700 token üretim + ~1.800 token doğrulama (sınav isteği üretimi, ~%20 fire dahil; tek oturumdan, ±%50)
- **Darboğaz 1 — Groq günlük token** (model başına 200 bin, kayan 24 saat): qwen aynı bütçeden görsel okuma + üretim + doğrulama yapıyor; gpt-oss'lar doğrulama + kısa cevap hakemi + hesap kör çözümü. 3 Ekim'de qwen 204 bin, 120b 207 bin → aynı gün hem "üretim bekleniyor" hem "doğrulama 60 dk bekleniyor"
- **Darboğaz 2 — Gemini istek sınırı** (model başına 20/gün): görsel okuma ile toplu üretim aynı kotayı paylaşıyor; 3 Ekim'de 2.5-flash 20/20; 5 Ekim gecesi Hafta 02'nin görsel sayfaları tek başına günü bitirdi
- OpenRouter (Nemotron, 50/gün) darboğaz değil, yükün küçük kısmı
- Ücretsiz günlük tavan (kabaca): üretim ~160 soru (sınav isteği) / ~480 (toplu); doğrulama ~550 çağrı ≈ ~400 soru; görsel okuma birkaç düzine sayfa
- Gemini dolunca yedek: qwen birim başına üretir — dakikada ~2 birim (Groq 8.000 token/dk), birim başına 1 soru, çoğu kolay; hesap soruları atlanır (§2c'nin onaylı yedeği yok)

**Değerlendirilen seçenekler:**
| Seçenek | Karar | Neden |
|---|---|---|
| Yerel RTX (4060 Laptop, 8 GB VRAM, 31 GB RAM) | Hayır | Sığan modeller 8-20B (şu an 120-550B + Gemini Flash) → özellikle Türkçe soru yazımında düşüş; soru başına ~1 dk, 100 sayfa ≈ 5-8 saat tam GPU; laptop sunucu olur, aynı anda tek iş; ~13 GB indirme. Tek istisna: onaylı doğrulayıcı gpt-oss-20b yerelde çalışabilir — üretimi çözmez |
| Birden çok hesap / anahtar döndürme | Hayır | Groq kullanım politikası, OpenRouter koşulları ve Google ("quota circumvention") açıkça yasaklıyor; kapatılma riski; en fazla 3× |
| BYOK | Hayır | Kullanıcı reddetti |
| Claude Pro aboneliği | Hayır | Yalnızca Anthropic'in kendi uygulamalarında (claude.ai, Claude Code); başkasına hizmet eden sisteme bağlanamaz |
| Google AI Plus / Pro aboneliği | Hayır | Abonelik limitleri yalnızca Gemini uygulaması ve AI Studio web'de; Pro'nun aylık 10 $ Cloud kredisi hiç etkinleştirilmemiş (faturalandırma hesabı yok), kullanıcı Plus'a geçti |
| Ücretli API, ön ödemeli | Kalıcı çözüm (teslim sonrası) | Doğrulanmış soru ≈ 0,3-1,1 sent (1M token: Gemini 3.5 Flash 1,50/9,00 $; 2.5/3 Flash ~0,3-0,5/2,5-3 $; gpt-oss-120b OpenRouter 0,039/0,18 $). OpenRouter'a bir kez 10 $ → ücretsiz modeller 50 → 1.000 istek/gün. Kullanıcı şimdilik ödeme yapmıyor |
| **Google Cloud 300 $ deneme → Vertex AI** | **Seçildi (teslime kadar)** | 90 gün; kart doğrulama ama otomatik ücret yok. Kredi AI Studio Gemini API'sinde ve iş ortağı modellerinde geçmez, **Vertex üzerinden Gemini'de geçer**. Üretim + görsel okuma darboğazını kaldırır; 300 $ ≈ 27-100 bin soru |

**Karar:** deneme ~12 Ekim'de açılır (bitiş ~10 Ocak; teslim 3 Ocak). Doğrulama ücretsiz katmanda kalır (aile kuralı: Gemini'nin sorusunu Gemini doğrulayamaz); üretim Gemini'ye geçince qwen'in Groq bütçesi doğrulamaya kalır, ayrıca toplu doğrulama; yetmezse OpenRouter 10 $. Deneme bitince router kendiliğinden ücretsiz düzene döner. Adımlar en üstte ("Sıradaki işler" 2-3).
Bekletilen öneriler (Vertex sonrası gerekirse): "havuz bakıcısı" (boş kotayla konu × zorluk havuzunu doldurma), kullanıcı istekleri için kota rezervi (~%30), aynı isteklerin birleştirilmesi.

**Sektör araştırması (2026-10-05, Claude Projects belgesi; yalnızca README/ROADMAP/PROMPTS'un eski kopyalarını görmüştü) — kodla karşılaştırma:**
- Doğrulandı: Gemma 4 (`gemma-4-31b-it`, `gemma-4-26b-a4b-it`, 262K bağlam) AI Studio anahtarında var (model listesi, kotasız sorgu). Sınırları (30/dk, 16K token/dk, ~14.400/gün) doğrulanmadı; asıl sınır büyük olasılıkla dakikalık token
- Açık bulundu ve kapatıldı: `family('gemma-4-31b-it')` 'gemma' dönüyordu (Gemini'den ayrı aile) → Gemma eklendiği gün aile kuralı sessizce çiğnenirdi. Aynı aile yanlılığı literatürde de ölçülmüş (iddia: 3,4-8,4 puan; özetten alındı)
- Önbellek kazancı abartılıydı: aynı bağlamı paylaşan soru — TYT 97 soru / 19 bağlam, 7.Hafta 18/6, istek 32/13, Hafta 01 15/14, Hafta 02 34/33 (qwen yedeği birim başına 1 soru). Önek tip başına ayrı. Asıl kazanç toplu üretimden (Vertex) sonra
- Öncelik: Vertex sonrası Google tarafı (üretim, görsel okuma, konu haritası) bollaşır, darboğaz Google dışı doğrulayıcıya kayar → Mistral > Gemma / Flash-Lite
- Çelişki: araştırma Cerebras'ta kalıcı 1M token/gün ücretsiz katman diyor; yukarıdaki 2026-10-04 notu "kart + 30 günlük 5 $" diyor → kayıtta doğrulanacak. GitHub Models (iddia: 30 Temmuz 2026'da kapandı) ve Azure for Students planda yok
- Rapor için: sektör kotayı ödeyerek ya da önceden üretilmiş havuzla çözüyor (Duolingo Item Factory: üret → filtrele → insan incele → öğrenci yanıtıyla kalibre et); biz ikincisini ücretsiz katmanda kurduk. Kaynakların sayıları (AUC 0,77-0,90, LLM çeldiricilerinin %53'ü kullanılabilir vb.) kısmen özetlerden → rapora koymadan makalenin kendisinden doğrulanmalı; "bu çalışmalardan farklı olarak" ifadesi, "önünde" değil

## Yeni belgeler ve akış düzeltmeleri (2026-10-05)
- [x] **Hafta 01 – Bilgisayar Mimarisi** (35 s., 7 görsel sayfa): 15 birim → 15 soru, **14 doğrulandı**, 1 red (kanıt alıntısı metinde yok); 9,5 dk. Gemini dolu → qwen birim başına; hesap soruları atlandı; konu haritası yok (bölüm başlıkları)
- [x] **Hafta 02 – Bilgisayar Performansı** (72 s., 22 görsel sayfa): 34 birim → 34 soru, **30 doğrulandı** (27 kolay, 3 orta), 2 red (cevabı notta yok; benzer şıklar), 2 incelemeye; 24,6 dk (~20 dk görsel okuma + qwen üretim; doğrulama ~1 dk)
- [x] **HATA: yeniden çalıştırma havuzu siliyordu.** `pipeline.run` soru dosyasının üzerine yazıyordu → Gemini açılınca Hafta belgelerini yeniden çalıştırmak 44 doğrulanmış soruyu ve onlara bağlı insan kararları / çözüm istatistiklerini (soru kimliğiyle bağlı) kaybettirecekti. Düzeltme `merge_existing`: eskiler korunur, önbellekten aynen gelen atlanır, eskinin tekrarı reddedilir (doğrulamaya gitmez), parçası artık olmayan eski soru düşer. Sınav isteğinde de havuzdaki sorunun tekrarı doğrulamaya gitmiyor (`mark_duplicates(keep=…)`). Test: `python -m tests.test_pipeline`
- [x] İlerleme görünürlüğü: Belgeler sayfası adımın içindeki son satırı gösteriyor ("üretim 9/34 (qwen)"; Gemini doluysa açıklaması); doğrulama satırındaki süre artık "iş başlayalı X dk" (kullanıcı doğrulamanın süresi sanmıştı)
- [x] Bekçi: `scripts/bekci.py` — belge işlerini, sınav isteklerini ve kotayı izler; bitince / hata / kota beklemesi / takılma / periyodik raporda çıkar (Claude oturumunda arka planda çalıştırılır)

## Adım 9 — Değerlendirme ve Rapor
- [ ] 🟢 Test seti: 20-30 elle yazılmış konu sorgusu (sayfa referanslı) + 10-15 **yetersiz bağlam** örneği (içindekiler, kaynakça, kapak vb.; boş liste beklenir)
- [ ] 🟢 Onaylanmış üretilmiş sorulardan otomatik retrieval test seti (+ diller arası varyantlar)
- [x] 🟡 **Retrieval ablasyonu** (`python -m eval.evaluate_retrieval` → `eval/sonuclar_retrieval.md`): 68 sorgu (35 elle etiketli `eval/retrieval_queries.json` + 33 doğrulanmış üretilmiş soru)
  | Yöntem | İsabet@1 | İsabet@5 | MRR@10 |
  |---|---|---|---|
  | **Dense (varsayılan yapıldı)** | **82%** | **100%** | **0.90** |
  | Hibrit, dil kuralı kapalı | 65% | 94% | 0.77 |
  | Hibrit + dil kuralı (eski varsayılan) | 59% | 85% | 0.70 |
  | BM25 F5 | 50% | 72% | 0.59 |
  | BM25 köklemesiz | 56% | 71% | 0.62 |
  - TR sorgu → EN slayt: dense %100, hibrit %58 → BM25 yanlış dildeki belgeyi öne çıkarıyor
  - F5'in köklemesiz BM25'e tutarlı üstünlüğü yok (LITERATURE.md "Ölçüm sonucu")
- [x] 🟡 **Yetersiz bağlam testi** (`python -m eval.insufficient_context`): kapak ×3, içindekiler, kaynakça ×2 doğrudan üreticiye verildi
  - İlk sürüm: 5/6 boş liste; EN kaynakçasından "Scientific American 1992 makalesini kim yazdı?" üretildi (kontrollerden de geçti)
  - İsteme "künye/idari bilgi sorma" kuralı eklendi → **6/6 boş liste**
  - Normal akışta bu sayfalar zaten dizin dışı (ilk savunma hattı); bu test ikinci hattı ölçüyor
- [-] 🟢 İnsan kabul oranı: doğrulama açık vs kapalı; doğrulayıcı isabeti — **kullanıcı kararıyla atlandı** (2026-10-04); yerine doğrulayıcı duyarlılık testleri (kasıtlı hatalar) ve öğrenci geri bildirimi (hatalı bildir, madde analizi) kullanılıyor
- [ ] 🟡 RAGAS (yalnızca `eval/`): önermeye dönüştürülmüş soru+cevap ile faithfulness (PROMPTS.md §5). Kota için hakem modeli üretim modelinden ayrı tutulur. Paketler ~20-40 MB
- [x] 🟢 Sadakat ↔ bilişsel düzey deneyi (`python -m eval.bloom_experiment` → `eval/sonuclar_bloom.md`): aynı 17 birim, gemini-2.5-flash; "hatırlama" 32 soru → 30 doğrulandı, "uygulama" 29 → 29; dayanaksız oranı ikisinde de %0 (beklenen ödünleşim bu örneklemde görülmedi; 3 birim uygulama sorusu üretmedi)
- [x] 🟡 Toplu üretim karşılaştırması (`eval/sonuclar_toplu_uretim.md`): aynı 12 birim — qwen birim başına 12 istek %92, Gemini tek istek %92-100
- [-] 🔴 Yerel embedding karşılaştırması (bge-m3, RTX 4060) — kullanıcı tercihi: dizüstünde GPU iş yükü yok; yalnızca açık istekle
- [ ] Rapor: kapsam, mimari, sonuçlar, bilinen sınırlar (ör. görsel fallback sayfalarında vurgulama yok, tablo/formül ağırlıklı sayfalar), kota analizi ve maliyet (yukarıdaki "Kota — kök çözüm analizi")

# Literatür Taraması

Bu tarama altı başlıkta yapılmıştır: (1) RAG mimarisi, (2) otomatik soru üretimi, (3) eğitim alanında RAG tabanlı soru üretimi, (4) halüsinasyon/doğruluk değerlendirmesi, (5) Türkçe ve çok dilli RAG, (6) doküman ayrıştırma / layout-farkında chunking. Her başlığın sonunda projeye doğrudan etkisi belirtilmiştir.

---

## 1. RAG Mimarisi — Temel ve Güncel Taramalar

RAG, 2020'de Lewis ve arkadaşları tarafından, bir dil modelinin çıktısını dış bir retrieval mekanizmasıyla zenginleştiren bir mimari olarak önerilmiştir (Lewis et al., 2020). O tarihten bu yana konu hızla olgunlaşmış ve 2024-2025 arasında birden fazla kapsamlı tarama yayımlanmıştır:

- Huang & Huang (2024), RAG'i dört aşamaya ayırıyor: pre-retrieval, retrieval, post-retrieval, generation. Bu dört aşamalı çerçeve, projenin mimarisini (ayrıştırma → chunking → embedding/retrieval → üretim) raporda konumlandırmak için doğrudan kullanılabilir.
- Gupta, Ranjan ve Singh (2024) ile Sharma (2025), RAG'in evrimini ve güncel zorluklarını (ölçeklenebilirlik, retrieval hassasiyeti ile üretim esnekliği arasındaki denge, halüsinasyon) ele alıyor.
- Brown, Roman ve Devereux (2025), 2020-2025 arası en çok atıf alan çalışmaları sistematik olarak inceleyip hibrit retrieval, yinelemeli retrieval döngüleri ve grafik tabanlı retrieval gibi yönelimleri tespit ediyor.
- Bir diğer sistematik derleme (TASK Quarterly, 2025), 41 akademik çalışmayı PRISMA yöntemiyle incelemiş ve literatürün büyük ölçüde İngilizce ve yüksek-kaynaklı dillere odaklandığını, düşük-kaynaklı dillerde ciddi bir boşluk olduğunu vurguluyor.

**Projeye etkisi:** Mimarimizi literatürdeki standart dört aşamalı RAG çerçevesine oturtabiliriz. Ayrıca son maddedeki bulgu (düşük-kaynaklı dil boşluğu) Türkçe odaklı çalışmamızın akademik olarak neden anlamlı olduğunu doğrudan destekliyor.

## 2. Otomatik Soru Üretimi (Automatic/Neural Question Generation)

Soru üretimi, NLP'de kendi başına yerleşik bir alt alan. Guo, Liao, Li ve Chua (2024), nöral soru üretiminin (NQG) kural tabanlı yöntemlerden RNN/Transformer'a, oradan da büyük dil modellerine evrimini kapsamlı şekilde inceliyor ve girdi türüne göre (metin, bilgi tabanı, görsel) bir sınıflandırma sunuyor. Daha erken bir derleme (Lu & Lu, 2021), 2019-2021 arası çalışmaları incelemiş ve standart, yaygın kabul görmüş bir değerlendirme metriğinin eksikliğine dikkat çekmiş — bu durum hâlâ geçerli bir sorun.

**Projeye etkisi:** Soru üretiminde "tek doğru" bir değerlendirme metriği olmadığı için, kendi test setimizle (hit rate, faithfulness) ölçüm yapma kararımız literatürle tutarlı; alan zaten bunu gerektiriyor.

## 3. Eğitim Alanında RAG Tabanlı Soru Üretimi — Doğrudan İlgili Çalışmalar

Bu başlık, projenle neredeyse birebir örtüşen, en değerli bulgu grubu:

- **Lohr, Berges, Chugh, Kohlhase ve Müller (2025)**, bilgisayar bilimi dersleri için RAG tabanlı, anlamsal olarak etiketlenmiş quiz soruları üretiyor. Önemli bulgu: üretilen soruların kalitesi çoğunlukla eğitim standartlarını tam karşılamıyor ve **ciddi oranda insan müdahalesi/doğrulama gerektiriyor.** Bu, bizim planladığımız doğrulama katmanının (kanıt kontrolü + ikinci geçiş) sadece "bonus" değil, literatürde de kritik bulunan bir bileşen olduğunu gösteriyor.
- **ICL + RAG hibrit yaklaşımı** üzerine bir çalışma (2025), yalnızca RAG veya yalnızca in-context learning yerine ikisini birleştiren bir hibrit modelin eğitim alanında soru kalitesini artırdığını gösteriyor.
- **POSCOMP çalışması** (SBC, 2025), RAG destekli çoktan seçmeli soru üretiminde LLM-as-a-judge ve insan değerlendiricileri birlikte kullanıyor; bu, değerlendirme metodolojimiz için bir model teşkil edebilir.
- **SLIIT çalışması** (2025), ders PDF'lerinden bağlama özgü quiz üretimi yapıyor ve ölçeklenebilirlik ile karmaşık içerik doğruluğunda iyileştirme gerektiğini belirtiyor — bizim "her PDF'te kusursuz değil, güvenilir" hedefimizi destekliyor.
- **Haas (2025, TU Graz yüksek lisans tezi)**, standart RAG ile Grafik tabanlı RAG'i (GRAG) karşılaştırıyor; GRAG soru bazında RAG'i geçmese de quiz bazında (bütünsel tutarlılık) daha iyi sonuç veriyor.

**Projeye etkisi:** Bu çalışmaların ortak sonucu şu: RAG tabanlı soru üretimi çalışıyor ama **doğrulamasız bırakılırsa güvenilir değil**. Bu, önceki konuşmamızdaki "doğrulama katmanı riskli mi?" sorusuna literatürden gelen net bir cevap: riskli olan doğrulamasız sistem, doğrulama katmanının kendisi değil.

## 4. Halüsinasyon ve Doğruluk (Faithfulness) Değerlendirmesi

Burada en önemli bulgu, bizim kendi yazacağımız doğrulama mantığının literatürde zaten standart bir aracı olduğu:

- **RAGAS (Es et al., 2023)** — RAG sistemlerini referans cevaba ihtiyaç duymadan değerlendiren açık kaynaklı bir çerçeve. "Faithfulness" metriği, üretilen cevabı iddialara (claims) ayırıp her iddianın bağlamdan çıkarılıp çıkarılamayacağını bir LLM ile kontrol ediyor. Faithfulness = desteklenen iddia sayısı / toplam iddia sayısı.
- Malin, Kalganova ve Boulgouris (2025)'in derlemesi, faithfulness değerlendirmesinde LLM'i hakem (judge) olarak kullanmanın insan değerlendirmesiyle en yüksek korelasyonu verdiğini gösteriyor; RAG ve prompt mühendisliğinin halüsinasyonu azaltmada etkili olduğunu doğruluyor.
- Vectara'nın halüsinasyon lider tablosu ve FaithJudge gibi çalışmalar, farklı LLM'lerin RAG bağlamında halüsinasyon oranlarını sistematik olarak karşılaştırıyor.

**Projeye etkisi (önemli, plan güncellemesi):** Kendi "kanıt alıntısı kontrolü + ikinci LLM geçişi" tasarımımızı sıfırdan yazmak yerine, **RAGAS kütüphanesini doğrudan kullanmayı** değerlendirmeliyiz. `pip install ragas` ile faithfulness, answer relevancy, context precision ve context recall metriklerini hazır alabiliriz. Bu hem geliştirme süresini kısaltır hem de "tanınmış, akademik olarak kabul görmüş bir araç kullandım" demeyi sağlar — raporda ciddi bir artı.

## 5. Türkçe ve Çok Dilli RAG

Bu başlık son derece güncel (2025-2026) ve doğrudan bizim dil kararımızı etkiliyor:

- **RAGSmith** (2025) analizi: Türkçe gibi morfolojik olarak zengin (agglutinative) dillerde, aynı anlamsal birim çok farklı çekim ekleriyle görünebildiği için saf sözcük eşleştirmeli (BM25 gibi) retrieval yetersiz kalabiliyor; bu yüzden retrieval'in dile duyarlı tasarlanması gerekiyor.
- **Turk-LettuceDetect** (2025) — Türkçe RAG uygulamaları için özel olarak geliştirilmiş, literatürdeki **ilk** halüsinasyon tespit modeli ailesi. Türkçe'nin düşük kaynaklı ve morfolojik olarak karmaşık olması nedeniyle genel çok dilli yaklaşımların yetersiz kaldığını, Türkçe'ye özel modellerin daha tutarlı sonuç verdiğini gösteriyor.
- **TurkColBERT** (2025) — Türkçe bilgi erişimi için yoğun (dense) ve geç-etkileşimli (late-interaction) modelleri karşılaştıran ilk kapsamlı karşılaştırma.
- **TurkEmbed / EmbedTurk** (2025) — Türkçe'ye özel embedding modelleri; çok dilli genel modellerin (bge-m3 gibi) Türkçe'de genelleme kaybı yaşayabileceğini, dile özel modellerin NLI/STS görevlerinde daha iyi performans gösterdiğini öne sürüyor.
- **Pubmed-RAG-TR / WikiRAG-TR** (2025) — Türkçe RAG için retrieval ve reranking bileşenlerinin alan-özel (domain-specific) veriyle ince ayarının performansı ciddi şekilde artırdığını gösteren bir çalışma; tıp alanında ama metodolojisi genellenebilir.

**Projeye etkisi (plan güncellemesi):** Daha önce "çok dilli embedding modeli (bge-m3/multilingual-e5) baştan yeterli" demiştik. Literatür bunu kısmen doğruluyor ama bir uyarı ekliyor: Türkçe'de **gerçekten en iyi sonuç** istiyorsak, bonus bir deney olarak **Türkçe'ye özel bir embedding modelini (TurkEmbed, EmbedTurk gibi)** çok dilli modelle karşılaştırmak, hem akademik değer katar hem de raporu güçlendirir. Zorunlu değil ama "literatürü okudum ve ona göre karşılaştırma yaptım" demek için ucuz bir ek deney.

## 6. Doküman Ayrıştırma ve Layout-Farkında Chunking

- Genel kabul gören bulgu: sabit karakter/token tabanlı ("naive") chunking, bir kavramın tanımını örneğinden koparabiliyor; **layout-farkında (layout-aware) ayrıştırma**, başlık, tablo, görsel gibi yapısal unsurları koruyarak chunking yapıyor ve retrieval kalitesini artırıyor (Omdena, 2025 teknik incelemesi; Panicker, 2023, LayoutPDFReader üzerinden).
- **D-RAC** (Yellow.ai, 2025) — Herhangi bir doküman formatını (DOCX, PPTX, taranmış görsel dahil) önce PDF'e normalize edip, ardından tek bir multimodal dönüşüm geçişiyle retrieval-farkında Markdown'a çeviren bir boru hattı. Bizim "farklı formatlarda tutarlı ayrıştırma" ihtiyacımızla doğrudan örtüşüyor.
- **MinerU tabanlı section-aware chunking** (CMIP-Forge, 2026) — Başlık hiyerarşisini ve bölüm yollarını koruyarak chunk üreten bir vizyon-dil modeli tabanlı ayrıştırıcı; akademik/bilimsel dokümanlarda düzenli kullanılıyor.
- **AgenticOCR** (2026) — OCR'ı "her şeyi oku" yerine "sadece gerekeni oku" şeklinde sorgu-güdümlü hale getiren yeni bir yaklaşım; verimlilik ve doğruluk artışı sağlıyor ama bizim ölçeğimiz için muhtemelen gereğinden karmaşık.

**Projeye etkisi:** "Başlık/bölüm duyarlı chunking" kararımız literatürle tam örtüşüyor. D-RAC'ın "her formatı PDF'e normalize et, tek geçişte işle" fikri, bizim PyMuPDF + Gemini görsel fallback ikili yaklaşımımızı sadeleştirmek için ileride değerlendirilebilir (opsiyonel, kapsam dışı tutulabilir).

---

## 7. Benzer Sistemler ve Maliyet Modeli (2026-10-03)

Kota sorunu üzerine yapılan bu tarama, "token karşılığı API kullanan bir sistem kurmak mantıklı mı?" sorusuna cevap aramak içindir.

**Ticari ürünler.** PDF/ders notundan quiz üreten araçların ortak modeli: ücretli LLM API'si + kullanıcı başına kullanım sınırı + abonelik. StudyFetch temel planı ($5-12/ay) ayda 10 materyal yükleme ve quiz başına en fazla 20 soru ile sınırlıyor; uzun belgelerde üretim 4-5 dakika sürüyor. Knowt temel özellikleri ücretsiz sunup gelişmiş yapay zeka özelliklerini ücretli planda ($9.99/ay) veriyor; Quizgecko ücretsiz planda quiz/soru sayısını sınırlıyor. Yani sektör kota sorununu ücretsiz katmana sığmaya çalışarak değil, sağlayıcıya ödeyip maliyeti **kullanıcı başına plan sınırıyla** yöneterek çözüyor.

**Açık kaynak projeler.** Ders/PDF RAG projelerinin çoğu tamamen yereldir (Ollama ile Llama 3.2 / Phi-3 / Gemma 2, Sentence Transformers, Qdrant/Faiss/Chroma, Streamlit/Gradio). Kota yoktur ama GPU gerekir ve küçük modellerin soru kalitesi düşüktür; ince ayarlı T5 gibi küçük soru üretim modelleri ucuz ancak GPT sınıfı modellerin gerisindedir.

**API mi, kendi sunucusu mu?** 2026 maliyet analizleri kendi model barındırmanın ancak günde ~10-15 milyon token'ın üzerinde ucuzladığını gösteriyor; altında GPU boşta kalma ve bakım yükü nedeniyle API kazanıyor ("üretim iş yüklerinin %95'inde API"). Bu projenin ölçeği: 10 ders notu ≈ 350 bin token; bir bölümün dönemlik materyali ≈ günde 0,5 milyon token → eşiğin 20-30 kat altı.

**Ölçülen maliyet.** Ücretli katman fiyatlarıyla (Gemini 2.5 Flash $0.30/$2.50, Groq gpt-oss-120b $0.15/$0.60 — milyon token başına girdi/çıktı) 25 sayfalık bir not ≈ $0.02-0.03, bir dersin dönemlik materyali ≈ $1'in altı.

**Kalite tarafı.** GPT-4 ile üretilen çoktan seçmeli soruların %4,9'unda birden çok doğru şık, %4'ünde cevabı ele veren çeldirici bulunmuş (insan yazımında %1,1 ve %0,9). Bu, bizim doğrulama katmanımızın yakaladığı hata türleriyle (iki doğru şık, yalnızca-şıklar ipucu) birebir örtüşüyor.

**Zorluk etiketi (2026-10-05 eklendi).** An ve Wang (2026), üç veri bilimi dersinde 311 soru ve 7.888 öğrenci yanıtıyla LLM'in verdiği Kolay/Orta/Zor etiketinin Bloom düzeyiyle çok güçlü ilişkili olduğunu (ρ=0,90) ama gerçek madde güçlüğünü **öngörmediğini** gösterdi (etiket ρ=0,06; Bloom ρ=0,02): etiket sorunun biçimini yansıtıyor, öğrencinin zorlanmasını değil. Bizim havuzdaki bulguyla örtüşüyor (ROADMAP 8): zorluk ancak öğrenci yanıtıyla (gerçek ya da benzetilmiş) ölçülebilir; Bloom'a dayalı kod kontrolü yalnızca etiketi kendi tanımımızla tutarlı kılar.

**Yerel ders notu → soru hattı.** Shintani (2026) ders PDF'lerinden yerel LLM ile çoktan seçmeli soru üreten uçtan uca bir hat yayımladı (kod ve not defteri açık): şema uyumu, tek doğru şık ve sayısal eşdeğerlik kontrolleri; 122 denemede 120 soru kabul. Kontroller biçim düzeyinde — farklı aileden kör doğrulama, kanıt alıntısı ve kasıtlı hata testi yok; bizim doğrulama katmanımızla karşılaştırma için uygun bir taban.

**Projeye etkisi.** Token tabanlı API mimarisi doğru seçim; değişmesi gereken ücretsiz katmana bağımlılık. Gerçek kullanımda: ücretli katman + harcama sınırı, kullanıcı başına kullanım sınırı, belge başına bir kez üretilip paylaşılan soru havuzu. Ücretsiz katman geliştirme/test için kalır. Ticari araçlarda görmediğimiz farkımız: kanıtı sayfada gösteren, farklı model ailesiyle kör doğrulanan, kasıtlı hata testinden geçmiş, Türkçe'ye özel bir soru üretimi.

## Genel Sonuç

Literatür üç ana noktada planımızı doğruluyor, bir noktada güçlendiriyor:

1. **Doğrulanmış:** RAG tabanlı eğitimsel soru üretimi aktif ve güncel bir araştırma alanı (2025'te en az 5 doğrudan ilgili çalışma).
2. **Doğrulanmış:** Doğrulama/insan kontrolü katmanı olmadan üretilen soruların kalitesi literatürde de yetersiz bulunuyor — bizim doğrulama katmanı kararımız gerekli, "riskli" değil.
3. **Doğrulanmış:** Başlık/bölüm duyarlı chunking, sabit boyutlu chunking'den daha iyi sonuç veriyor.
4. **Güçlendirildi (plan güncellemesi):** Kendi doğrulama mantığımızı sıfırdan yazmak yerine RAGAS kütüphanesini kullanmalıyız. Türkçe performansı gerçekten önemsiyorsak, Türkçe'ye özel bir embedding modelini bonus karşılaştırma olarak eklemeliyiz.
5. **Boşluk/fırsat:** Türkçe ders dokümanlarına özel, doğrulamalı bir RAG soru-cevap sistemi literatürde yok denecek kadar az. Bu, projenin özgün katkı iddiasını güçlendiriyor.

---

## Karar Güncellemesi (2026-10-01) — Literatürden Tasarıma

Yukarıdaki 4. maddedeki öneri ("RAGAS'ı kullanalım, Türkçe'ye özel embedding'i karşılaştıralım") uygulandı, ancak bir düzeltmeyle:

- **RAGAS doğrulama katmanının yerine geçmiyor, değerlendirme katmanına giriyor.** RAGAS bir değerlendirme çerçevesi. Soru başına çok sayıda LLM çağrısı yaptığı için ücretsiz kotalarda her üretilen soruya uygulanamaz. Faithfulness metriği uzun cevapları iddialara bölmek üzere tasarlanmış; "B" ya da "Yanlış" gibi quiz cevaplarında bölünecek iddia yok. Bu yüzden soru+cevap önce tek bir önermeye dönüştürülüyor (PROMPTS.md §5). Ayrıca RAGAS, çoktan seçmeli sorulara özgü kusurları (ikinci bir doğru şık, cevabı ele veren ipuçları) ölçmüyor. Çalışma anındaki doğrulama bu nedenle kendi tipe özel tasarımımızla kalıyor (README §4.2). RAGAS, raporda akademik olarak tanınmış bir metrik sağlamak için `eval/` altında kullanılıyor.
- **Doğru/Yanlış sorularında "desteklenmiyor" ile "yanlış" aynı şey değil.** NLI literatüründeki 3 sınıflı ayrım (entailment / contradiction / neutral) doğrulamaya taşındı: "Yanlış" cevaplı bir ifade bağlamla çelişmeli. Bağlamda hiç geçmeyen bir ifade yanlış sayılmaz.
- **RAGSmith'in Türkçe BM25 uyarısına ucuz bir cevap:** Can vd. (2008), Türkçe metinlerde kelimelerin ilk 5 harfinin alınmasının (F5) kök bulucularla yarışabilir sonuç verdiğini gösteriyor. Hibrit retrieval'da BM25 bu şekilde, ek model ya da kütüphane olmadan uygulanıyor. Dense ve sparse sonuçlar Reciprocal Rank Fusion (Cormack vd., 2009) ile birleştiriliyor.
- **Türkçe'ye özel embedding deneyi opsiyonel.** Model indirmeleri (~1-2 GB) mobil internet kotasını aştığı için bu deney Wi-Fi bağlantısına bırakıldı. Kod, embedding modelini tek satırla değiştirilebilir tutacak şekilde yazılıyor.
- **Lohr vd. (2025) bulgusunun ölçülmesi:** Literatür "insan müdahalesi gerekiyor" diyor. Biz bunu bir metriğe çeviriyoruz: doğrulama açıkken ve kapalıyken **insan kabul oranı**. İnceleme kararları kaydedildiği için bu ölçüm geliştirme sırasında kendiliğinden birikiyor.

### Ölçüm sonucu (2026-10-03): literatürden çıkan iki retrieval hipotezi kendi verimizde

`eval/evaluate_retrieval.py`, 68 sorgu (35 elle etiketli + 33 doğrulanmış üretilmiş soru), 3 belge:

| Hipotez (kaynak) | Beklenti | Sonuç |
|---|---|---|
| F5 kökleme Türkçe BM25'i iyileştirir (Can vd., 2008) | F5 > köklemesiz | **Doğrulanmadı.** TR→TR elle sorgularda isabet@1 %80'e %93 (köklemesiz önde); üretilmiş TR→TR sorgularda isabet@3 %95'e %86 (F5 önde). Küçük örneklemde tutarlı bir üstünlük yok |
| Hibrit (dense + BM25, RRF) dense'ten iyidir (Brown vd., 2025; RAGSmith) | Hibrit ≥ dense | **Çürütüldü (bu ortamda).** Dense isabet@5 %100, hibrit %85. TR sorgu → EN slayt durumunda hibrit %58: BM25, Türkçe slayttaki benzer kelimeleri öne çıkarıp doğru İngilizce sayfayı aşağı itiyor |

Yorum: Literatürdeki hibrit/kökleme kazançları tek dilli ve geniş derlemlerde ölçülmüş. Bizim ortamımız **çok dilli** (TR+EN) ve **küçük** (140 parça); güçlü bir çok dilli embedding modeli (gemini-embedding-001) burada sözcük eşleştirmesine ihtiyaç bırakmıyor. Karar: varsayılan arama dense; BM25/hibrit karşılaştırma için kodda kalıyor. Bu, "literatürü uyguladık ama kendi verimizde ölçtük" sonucunun somut örneği.

Not: Kaynakçadaki bazı yazarı belirtilmemiş girişlerin (özellikle 2026 tarihli arXiv çalışmaları) künyeleri, rapora girmeden önce arXiv üzerinden teyit edilmelidir.

---

## Kaynakça

1. Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.*
2. Huang, Y. & Huang, J. (2024). *A Survey on Retrieval-Augmented Text Generation for Large Language Models.* arXiv:2404.10981
3. Gupta, S., Ranjan, R., & Singh, S. N. (2024). *A Comprehensive Survey of Retrieval-Augmented Generation (RAG).* arXiv:2410.12837
4. Sharma, C. (2025). *Retrieval-Augmented Generation: A Comprehensive Survey of Architectures, Enhancements, and Robustness Frontiers.* arXiv:2506.00054
5. Brown, A., Roman, M., & Devereux, B. (2025). *A Systematic Literature Review of Retrieval-Augmented Generation.* arXiv:2508.06401
6. TASK Quarterly (2025). *An Analysis of Retrieval-Augmented Generation: A Systematic Review.*
7. Guo, S., Liao, L., Li, C., & Chua, T-S. (2024). *A Survey on Neural Question Generation.* IJCAI 2024. arXiv:2402.18267
8. Lu, C-Y. & Lu, S-E. (2021). *A Survey of Approaches to Automatic Question Generation: 2019-2021.* ROCLING 2021
9. Lohr, D., Berges, M., Chugh, A., Kohlhase, M., & Müller, D. (2025). *Leveraging LLMs to Generate Course-Specific Semantically Annotated Learning Objects.*
10. (2025). *Leveraging In-Context Learning and RAG for Automatic Question Generation in Educational Domains.* arXiv:2501.17397
11. (2025). *Smarter Questions, Smaller Models: RAG-Enhanced MCQ Generation for POSCOMP.* SBC
12. (2025). *Leveraging LLMs for Dynamic Content Generation and Contextual Quizzes.* SLIIT
13. Haas, S. (2025). *Leveraging Contemporary LLMs and Knowledge Graph-based RAG for Quiz Content Creation.* TU Graz Master's Thesis
14. Es, S. et al. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* arXiv:2309.15217
15. Malin, B., Kalganova, T., & Boulgouris, N. (2025). *A Review of Faithfulness Metrics for Hallucination Assessment in LLMs.* arXiv:2501.00269
16. (2025). *Benchmarking LLM Faithfulness in RAG with Evolving Leaderboards.* arXiv:2505.04847
17. (2025). *RAGSmith: A Framework for Finding the Optimal Composition of RAG Methods.* arXiv:2511.01386
18. (2025). *Turk-LettuceDetect: A Hallucination Detection Model Suite for Turkish RAG Applications.* arXiv:2509.17671
19. (2025). *TurkColBERT: A Benchmark of Dense and Late-Interaction Models for Turkish IR.* arXiv:2511.16528
20. Ezerceli, Ö. et al. (2025). *TurkEmbed: Turkish Embedding Model on NLI & STS Tasks.* ASYU 2025
21. Oytac, D. et al. (2025). *EmbedTurk: Leveraging LLMs as Text Encoders for Turkish.* INFUS 2025
22. (2025). *Pubmed-RAG-TR / WikiRAG-TR: Turkish Medical RAG Dataset.* Çankaya Üniversitesi Tez Merkezi
23. Yellow.ai AI Research Team (2025). *D-RAC: Universal Retrieval-Aware Ingestion of Enterprise Documents.* arXiv:2609.24220
24. (2026). *CMIP-Forge: An Agentic System using MinerU-based Document Parsing.* arXiv:2606.17076
25. Wang, Z. et al. (2026). *AgenticOCR: Parsing Only What You Need for Efficient RAG.* arXiv:2602.24134
26. Can, F., Koçberber, S., Balçık, E., Kaynak, C., Öcalan, H. Ç., & Vursavaş, O. M. (2008). *Information Retrieval on Turkish Texts.* Journal of the American Society for Information Science and Technology, 59(3), 407-421.
27. Cormack, G. V., Clarke, C. L. A., & Büttcher, S. (2009). *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods.* SIGIR 2009.
28. StudyFetch incelemeleri (2026): dupple.com/reviews/study-fetch; toolchase.com/tool/studyfetch
29. Knowt / Quizlet / Anki / StudyFetch karşılaştırması (2026): laxuai.com/blog/laxu-ai-vs-quizlet-vs-anki-comparison
30. Particula (2026). *Self-Host LLM vs API: When the Break-Even Math Flips.* particula.tech
31. SitePoint (2026). *Local LLMs vs Cloud APIs: 2026 Total Cost of Ownership Analysis.*
32. (2024). *A Comparative Study of AI-Generated (GPT-4) and Human-crafted MCQs in Programming Education.* ACM, doi:10.1145/3636243.3636256
33. Google (2026). *Gemini API pricing.* ai.google.dev/gemini-api/docs/pricing
34. Glamdring Research (2026). *Groq API pricing: Groq model list, September 2026.*
35. An, Y., Wang, L. (2026). *Student Use of LLMs and the Limits of AI-Generated Question Difficulty in Data Science Courses.* arXiv:2609.27063
36. Shintani, S. A. (2026). *Self-hosted Lecture-to-Quiz: Local LLM MCQ Generation with Deterministic Quality Control.* arXiv:2603.08729

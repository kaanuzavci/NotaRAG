# 9. Ölçüm, testler ve araçlar

[← 8. Arayüz](08-arayuz.md) · [Ana sayfa](README.md)

Üç tür dosya var:
- **`eval/`:** "sistem ne kadar iyi?" sorusunu sayıyla cevaplayan **deney betikleri**. Sonuçlarını `eval/sonuclar_*.json` / `.md` dosyalarına yazar; Rapor sayfası bunları okur. Çoğu API çağırır, yani kota harcar.
- **`tests/`:** "kod hâlâ doğru mu?" sorusunu cevaplayan **regresyon testleri**. API çağırmaz, saniyeler sürer. Her test bulunmuş bir hatanın geri gelmesini önler.
- **`scripts/`:** geliştirme araçları: arka plan işlerini izleyen `bekci.py`, arayüzü görerek kontrol eden `onizleme.py` + `ekran.py`, bu rehberin bakımı `rehber_satirlari.py`.

> Testler pytest kullanmıyor. Her dosya `python -m tests.<ad>` ile çalışan düz bir betik; içindeki `assert` başarısız olursa `AssertionError` ile durur.

---

## `eval/` — deney betikleri

### `eval/evaluate_retrieval.py` — arama değerlendirmesi (101 satır)

**Ne ölçer?** Konu adıyla arama yapıldığında doğru sayfa ilk sonuçlarda çıkıyor mu? Beş yöntem karşılaştırılır:
- dense
- köklemesiz BM25
- F5 BM25
- hibrit (dil kuralıyla)
- hibrit (dil kuralı kapalı)

**Sonuç ve karar:** dense isabet@5 %100 → varsayılan dense yapıldı.

- **Ölçüler:**
  - İsabet@k: doğru sayfa ilk k sonuçta mı?
  - MRR@10: doğru sayfanın sırasının tersinin ortalaması (1. sıra = 1, 2. sıra = 0,5…).
- [`hand_queries()`](../eval/evaluate_retrieval.py#L28): elle etiketlenmiş 35 konu sorgusu ([`retrieval_queries.json`](../eval/retrieval_queries.json)).
- [`generated_queries()`](../eval/evaluate_retrieval.py#L37): doğrulanmış üretilmiş soruların metni sorgu olarak kullanılır; doğru sayfa = kanıtın sayfası. "Bedava" test verisi.
- [`evaluate(idx, queries)`](../eval/evaluate_retrieval.py#L56): her sorgu × her yöntem için sıra hesabı. Sonuçlar "TÜMÜ" ve sorgu türüne göre (TR→TR, TR→EN…) gruplanır.
- [`to_markdown(res)`](../eval/evaluate_retrieval.py#L71) / [`main()`](../eval/evaluate_retrieval.py#L85): tabloyu ve JSON'u yazar.
- API: yalnızca sorgu embedding'leri (önbellekli).

### `eval/bloom_experiment.py` — sadakat ↔ bilişsel düzey deneyi (104 satır)

**Hipotez:** "Uygulama" düzeyinde soru istenince modelin dokümanda dayanağı olmayan soru üretme oranı artar.

**Tasarım:** aynı 17 birim, iki koşul (yalnızca `remember` / yalnızca `apply`), aynı üretici (gemini-2.5-flash), aynı doğrulayıcı.

**Sonuç:** iki koşulda da dayanaksız oranı %0. Beklenen ödünleşim bu örneklemde görülmedi.

- [`patient`](../eval/bloom_experiment.py#L34): `pipeline.patient`'in eski bir kopyası.
- [`run(cond, chunks)`](../eval/bloom_experiment.py#L47): üç belgeden `generate_batched(..., bloom_target=cond)` ile üretir, doğrular, `data/pilot/bloom_<koşul>_dogrulama.jsonl`'a yazar.
- [`summarize(cond, items, n_units)`](../eval/bloom_experiment.py#L63): **"dayanaksız"** = kanıtı bulunamayan + kod kontrolünü geçip doğrulayıcının onaylamadığı sorular.
- [`main()`](../eval/bloom_experiment.py#L77): `eval/sonuclar_bloom.md` / `.json`.

### `eval/batch_compare.py` — toplu üretim kalite karşılaştırması (96 satır)

**Soru:** 12 birimi tek istekte üretmek (Gemini) kaliteyi düşürüyor mu? Taban: qwen ile birim başına 12 istek.

**Sonuç:** taban %92; Gemini 3.8 tek istekte 11/11, 3.5 tek istekte 11/12. Gemini toplu üretici olarak onaylandı.

- [`stats(name, items, requests, tokens, secs)`](../eval/batch_compare.py#L35): doğrulanma oranı, dayanaksız, uyarılar, tipler, Bloom, istek ve token.
- [`main()`](../eval/batch_compare.py#L49): tabanı yeniden doğrular, her aday model için `generate_batched` (503 "yoğun" hatasında 45 sn arayla 4 deneme) → `eval/sonuclar_toplu_uretim.md` / `.json`.

### `eval/compute_check.py` — hesap kontrolünün duyarlılığı (61 satır)

**Ne ölçer?** API çağırmaz. SymPy kontrolü kasıtlı hataları yakalıyor mu?
- [`corrupt(q, kind)`](../eval/compute_check.py#L25): kontrolden geçmiş bir hesap sorusunu bozar.
  - `wrong_key`: anahtar kaydırılır.
  - `two_correct`: bir çeldirici doğru sonuca eşitlenir.
  - `text_mismatch`: doğru şıkkın metni başka sayı yapılır, değeri aynı kalır.
- [`main(path)`](../eval/compute_check.py#L40): her bozulmanın beklenen red nedenini üretip üretmediğini ve bozulmamış sorularda yanlış alarm olup olmadığını sayar. Sonuç `eval/sonuclar_hesap_kontrol.md` / `.json`.

**Sonuç:** 20/20, 20/20, 19/20 yakalandı; yanlış alarm 0/20.

### `eval/insufficient_context.py` — "üretmemeyi bilmek" testi (34 satır)

**Ne ölçer?** Kapak, içindekiler ve kaynakça sayfaları üreticiye **doğrudan** verilir. Normalde bu sayfalar dizine hiç girmez; bu test ikinci savunma hattını ölçer: model kendi başına "buradan soru çıkmaz" deyip boş liste döndürüyor mu?
- [`main()`](../eval/insufficient_context.py#L18): 6 sayfa; her biri için `generate_unit`.

**Sonuç:** İlk sürüm 5/6 boş liste döndürdü; kaynakçadan "Scientific American makalesini kim yazdı?" diye bir soru üretmişti. İsteme "künye sorma" kuralı eklenince 6/6 oldu.

### `eval/zorluk_olcumu.py` — zorluk ölçümü pilotu (158 satır)

**Soru:** Zorluk etiketi iddia değil ölçüm olabilir mi, ve yeni tanımlarla üretim istenen düzeyi tutuyor mu? (ROADMAP 8, LITERATURE §8, bölüm 10.)

**Gruplar:**
- **A.** Kullanıcının TYT "zor" isteği (10 hesap sorusu): üretecin iddiası, yapı (ayrı kural, adım, işlem sayısı) ve Claude'un elle değerlendirmesi (`MANUAL`) yan yana. Elle değerlendirme gerçek öğrenci verisi **değildir**.
- **C.** Sözel belgelerden 12 soruluk örneklem (`_pick`: iddiaya göre dengeli): benzetilmiş öğrenci + yapı.
- **D1 / D2.** "Merdiven": aynı birimlerden kolay / orta / zor üretim (sözel ve hesap). Ölçüm sırayı görüyor mu, ayrı bilgi ve adım sayısı artıyor mu?
- **E.** Zorlaştırma (PROMPTS §2d): C'de orta ölçülen sorular, başka bir belgenin notuyla birleştirilip zor istenir; önce/sonra.

Merdiven ve zorlaştırma soruları yalnızca kod kontrolünden geçer (LLM doğrulaması yok; burada ölçülen şey zorluk).

- [`_pick(items, n, seed)`](../eval/zorluk_olcumu.py#L41): iddiaya göre dengeli örneklem.
- [`_ladder(units, worked)`](../eval/zorluk_olcumu.py#L55): her düzey için `generate_request` → etkin düzey.
- [`_units_text()`](../eval/zorluk_olcumu.py#L67): her sözel belgeden yeterince uzun bir birim.
- [`_cell`](../eval/zorluk_olcumu.py#L75), [`_table`](../eval/zorluk_olcumu.py#L86): tablo satırı ve grup tablosu; istenen düzeye göre "tutan" sayısı, ortalama bilgi sayısı, ortalama p.
- [`main()`](../eval/zorluk_olcumu.py#L105): grupları kurar, ölçer, `eval/sonuclar_zorluk.md`'yi yazar.
- API: ~7 Gemini çağrısı (üretim), sözel soru başına 5 Gemma çağrısı (benzetim). Yanıtlar önbellekte, ölçümler `data/review/difficulty.jsonl`'de; yeniden çalıştırma kota harcamaz.

### `eval/turkishmmlu_zorluk.py` — zorluk sinyalleri ↔ gerçek öğrenci

**Soru:** Elimizdeki ücretsiz zorluk sinyallerinden hangisi **gerçek** öğrenci zorluğunu izliyor? Projenin kendi öğrenci verisi yok (62 çözüm, tek kişi). TurkishMMLU'nun (Yüksel ve ark. 2024) 900 soruluk alt kümesinde her lise sorusu için çevrim içi platformdaki öğrencilerin doğru oranı var. Bu, sistemin zorluk yöntemlerini dışarıdan bir ölçüte karşı sınamayı mümkün kılıyor.

**Sinyaller:**
1. Metin özellikleri (kota yok, 900 soru): uzunluk, öncül sayısı (I. II. III.), olumsuz kök, formül/sayı, şık uzunluğu, doğru şıkla en yakın çeldiricinin benzerliği.
2. Benzetilmiş öğrenci, **kapalı kitap** (PROMPTS §8b): soruların ders notu yok, öğrenci kendi bilgisiyle cevaplar.
3. Çaba: dikkatli çözümün düşünme token'ı. Hepsi 5 şıklı çoktan seçmeli olduğu için soru tipi karışmaz (sözel pilotta çaba tipi ölçmüştü).
4. LLM'in kendi zorluk etiketi (PROMPTS §8c): An ve Wang'ın (2026) "LLM etiketi öğrenci zorluğunu öngörmüyor" bulgusunun Türkçe tekrarı.

**Ölçüt:** öğrenci doğru oranıyla Spearman sıra korelasyonu (ρ) ve 3 düzeyde tutma oranı.

- Veri `data/turkishmmlu/`'ya indirilir (635 KB). Lisans belirtilmediği için depoya girmez; yalnızca toplu sonuçlar yazılır.
- [`sample(rows, n, seed)`](../eval/turkishmmlu_zorluk.py#L65): ders × zorluk tabakalı örneklem (ders başına `n`, varsayılan 20 → 180 soru).
- [`features(x)`](../eval/turkishmmlu_zorluk.py#L84), [`spearman(a, b)`](../eval/turkishmmlu_zorluk.py#L109): metin özellikleri ve sıra korelasyonu (scipy yok; eşitlere ortalama sıra).
- [`measure(x)`](../eval/turkishmmlu_zorluk.py#L153): bir soru = 4 hızlı öğrenci + 1 dikkatli öğrenci + 1 etiket çağrısı (hepsi Gemma).
- [`run(todo)`](../eval/turkishmmlu_zorluk.py#L181): ölçülmemiş soruları ölçer, `data/turkishmmlu/olcumler.jsonl`'e ekler. Gemma yoğunsa bekler, kota dolarsa durur.
- [`report(rows, picked)`](../eval/turkishmmlu_zorluk.py#L213): `eval/sonuclar_turkishmmlu.md`. Ayrıca sistemin benzetim kuralının (`difficulty.sim_level`) gerçek düzeylere nasıl dağıldığını gösterir.
- API: soru başına 6 Gemma çağrısı (ayrı ücretsiz kota); `--rapor` yeni çağrı yapmaz.
- `--parca k/m`: örneklemi `m` sürece böler. Darboğaz dakikalık sınır değil, Gemma'nın yanıt süresi (dikkatli çözüm uzun düşünüyor; soru başına ~2,5 dk). 4 paralel süreçle 180 soru ~2 saat.

### `eval/kaynak_etkisi.py` — kaynak desteğinin cevap doğruluğuna etkisi (ödev gereksinimi)

**Soru:** Kaynak metin, modelin cevap doğruluğunu ne kadar değiştiriyor? Aynı soru Gemma 4 26B-A4B'ye (düşünmeden, sıcaklık 0) üç koşulda sorulur: **kaynaksız** (PROMPTS §6), **doğru kaynakla** ve **yanlış kaynakla** (başka bir sorunun kaynağı: arama yanlış sayfa getirirse; §6c).

- Veri: Belebele-TR'den 300 okuduğunu anlama sorusu (insan yazımı, paragraflı) ve havuzun doğrulanmış 122 çoktan seçmeli sorusu (kaynak = sorunun üretildiği not sayfaları; sözel ve hesap ayrı).
- Ölçüt: doğruluk (%95 Wilson aralığı); "kaynağa muhtaç" (doğru kaynakla doğru, kaynaksız yanlış) ve "yanlış kaynağın zararı" (kaynaksız doğru, yanlış kaynakla yanlış) oranları; havuzda belge ve etkin zorluğa göre. Koşullar arası fark [`mcnemar(b, c)`](../eval/kaynak_etkisi.py#L148) ile sınanır: aynı soru iki koşulda cevaplandığı için ölçümler eşli; yalnızca yön değiştiren sorular (kaynakla doğruya dönen `b`, yanlışa dönen `c`) sayılır, kesin binom testi.
- Gemma 4 31B gece aşırı yüklüyken (basit çağrı 26-40 sn) cevaplayıcı 26B-A4B'ye alındı.
- **Tek model:** üç koşul aynı modelle karşılaştırıldığı için `simulate._role` (meşgulde 31B'ye geçen öğrenci rolü) kullanılmaz; deney kendi tek modelli rolünü (`ROLE`) kaydeder, model meşgulse [`run`](../eval/kaynak_etkisi.py#L116) 2 dk bekler. [`done()`](../eval/kaynak_etkisi.py#L96) başka modelle ölçülmüş satırı ölçülmemiş sayar → bir sonraki çalıştırmada yeniden ölçülür (ilk çalıştırmada 422 satırın 36'sı kısmen 31B'ydi).
- Hesap soruları da düşünmeden ve 60 token sınırıyla cevaplanır: model hesabı yazamaz, o satır kaynağın hesapsız cevaba etkisini gösterir.
- Soru başına 3 Gemma çağrısı; `--parca k/m`, `--rapor`; ölçümler `data/kaynak_etkisi/olcumler.jsonl`.

### `eval/uc_adim.py` — uzman zorluk adımları ↔ sistemin sinyalleri

**Soru:** MEB 3 Adım Soru Bankası'nda her konunun soruları uzmanlarca 1 → 2 → 3. adımda zorlaşır. TurkishMMLU deneyindeki sinyaller (benzetilmiş öğrenci p, çaba, LLM etiketi, `difficulty.sim_level`) bu uzman sıralamasını izliyor mu?

- Soru çıkarma (kota yok): sayfa başlığından adım ve konu, satır başındaki `N.` ile soru sınırı, `A)…E)` ile şıklar; cevap anahtarı kitabın sonunda konu konu. Görsele dayanan sorular (harita, grafik, tablo, şekil, koordinat sistemi, taralı alan…) atlanır. Tarih 618, Coğrafya 368, Felsefe 597 soru; Biyoloji'nin anahtar biçimi farklı (eşleşmiyor).
- [`_page_keys(page)`](../eval/uc_adim.py#L46): bir anahtar sayfası → konular. **Metin sırasına değil konuma bakar:** her konu bir tablo, adı tablonun üstünde, satır başında "1. ADIM / 2. ADIM / 3. ADIM"; her harf (`7-C`) dikeyde en yakın adım satırına, her tablo üstündeki ada atanır. İlk sürüm metin sırasıyla çalışıyordu: başlıkları ayrı satırda duran tablolar öncekine karışıyor, sayfanın ilk konusunun adı metnin sonunda çıkıyordu → 1. adımın anahtarı çoğu zaman başka konudandı ve ilk ölçüm geçersiz oldu (2026-10-07; dikkatli çözücü 1. adımda 17/30, 2. adımda 30/30 doğru → fark buradan anlaşıldı).
- [`_keys(doc)`](../eval/uc_adim.py#L79): son 16 sayfadaki anahtar sayfalarını toplar (liste: aynı adlı iki konu olabilir).
- [`_match_keys(triples, keys)`](../eval/uc_adim.py#L96): test üçlüsü (aynı konunun 1-2-3. adım testleri) → anahtar konusu, üç kuralla: (1) ad aynı ([`_norm`](../eval/uc_adim.py#L90): Türkçe küçük harf, boşluk/noktalama yok); (2) ad kesik ya da yazımı farklı → benzer adlılar arasında soru sayıları en çok tutan, eşitlikte adı test adıyla başlayan; (3) başlık yerine soru cümlesi okunmuşsa → üç adımın soru sayısı boşta kalan tek bir konununkiyle birebir aynıysa. Soru sayısı anahtarla tutmayan adım alınmaz.
- [`_tests(doc)`](../eval/uc_adim.py#L130), [`extract()`](../eval/uc_adim.py#L165): çıkarma; `--cikar` yalnızca sayıları yazar.
- Raporda adım başına **dikkatli çözücü doğruluğu** anahtar sağlaması olarak durur: bir adımda belirgin düşükse o adımın anahtarı şüphelidir.
- Ölçüm `turkishmmlu_zorluk.measure` ile (soru başına 6 Gemma çağrısı); ders × adım başına `--n` (varsayılan 10) soru.

### `eval/retrieval_queries.json`

Elle yazılmış konu sorguları ve her birinin doğru sayfaları. Sorgu türleri: Türkçe→Türkçe, Türkçe sorgu→İngilizce slayt, İngilizce→İngilizce.

> **Ödev gereksinimi:** "Kaynak metinlerle desteklenen üretimin cevap doğruluğuna etkisi". Cevaplama tarafı (B) `eval/kaynak_etkisi.py` ile ölçüldü; üretim tarafı (A: kaynaksız üretim ↔ RAG ile üretim) kota ister, Vertex sonrası. Plan ve sonuçlar: ROADMAP "Sıradaki işler" 4. madde.

---

## `tests/` — regresyon testleri (API yok)

| Dosya | Neyi sabitliyor? |
|---|---|
| [`test_textnorm.py`](../tests/test_textnorm.py) | Türkçe küçük harf (`IŞIK` → `ışık`), `İSTANBUL` = `Istanbul` eşleşmesi, satır sonu tiresi çözümü (`bü-tün` → `bütün`, `meta-sezgisel` korunur), Wingdings madde işareti, üst/alt simgelerin korunması, `pretty_math` (LaTeX kesir → `(100 · a)/(a + b)`) |
| [`test_parser.py`](../tests/test_parser.py) | Gerçek PDF'lerle (`data/sample_docs/` gerekir): dil tespiti, döndürülmüş sayfada üst bilgi temizliği, içerikteki `22` sayılarının silinmemesi, tekrar eden slayt başlıklarının korunması, şekil etiketlerinin ayrılması, kapak/içindekiler bayrakları, resim sayfalarının görsele gitmesi, işlemcide tablo çıkarma, bozuk formül tespiti, Türkçe karakterler. 11 test; her birinin yorumunda hangi hatayı önlediği yazılı |
| [`test_checks.py`](../tests/test_checks.py) | Metne atıf tespiti ("Bu seçim stratejisinin…" yakalanır, "Bu nedenle…" yakalanmaz), D/Y "Yanlış" → `false`, LaTeX'li kanıtın bulunması, uydurma kanıtın reddi, "öz alt küme" tekrar kuralı ve onun **yanlış alarm vermemesi** (sayısı farklı ya da sırası farklı şıklar), açıklamalı cevap metni, kesin ifadeli çeldiriciler, havuzla tekrar tespiti |
| [`test_compute.py`](../tests/test_compute.py) | Güvenlik: `__import__`, `x.__class__`, `open(...)`, `lambda`, dev üs reddedilir. Doğru soru reddedilmez. Yanlış anahtar, iki doğru şık, metin–değer çelişkisi yakalanır. `%25` ve `2,5` gibi Türkçe yazımlar. Şık karıştırmanın değerleri de taşıması |
| [`test_grading.py`](../tests/test_grading.py) | 29 durum: `2` ≠ `(n choose 2)·2`, `30240` = `9!/(3!·2!)`, `n²-n` = `2C(n,2)`, `tanımsızdır` = `tanımsız`, `böcek` ≠ `Faydalı böcekler (parazitoid)`; güvenlik girdileri (`9^9^9`, `__import__('os')`) yanlış sayılır ve sistemi kilitlemez |
| [`test_router.py`](../tests/test_router.py) | Hata mesajından bekleme süresi (`10m28.992s` → 628,992 sn). Groq TPD = süreli bekleme, Gemini günlük = gün boyu kapatma. Ağ zaman aşımı, "Server disconnected" (`RemoteProtocolError`) ve DNS hatası ("getaddrinfo failed", `ConnectError`) kota sayılmaz, süreci çökertmez. `AllModelsExhausted.transient` mantığı. `test_family`: aynı model farklı sağlayıcıda aynı aile; Gemma = Gemini; Mistral takma adları. `test_cache_key`: varsayılan akıl yürütme düzeyinde önbellek anahtarı eskisiyle aynı kalır, `REASONING_VERIFY=low` ayrı anahtar alır |
| [`test_pipeline.py`](../tests/test_pipeline.py) | `merge_existing`: eskiler korunur, parçası kalmayan eski düşer, önbellekten aynen gelen atlanır, başka modelden gelen aynı metin `duplicate` olarak reddedilir |
| [`test_cards.py`](../tests/test_cards.py) | Leitner kutuları: Bildim bir üst kutu (tavan 5), Bilemedim 1. kutu, Atla değişmez; aralıklar; deste sırası (zamanı gelen tekrar → yeni, zamanı gelmeyen dışarıda); kayıt baştan oynatılınca aynı durum. Kart kuralı: "aşağıdakilerden hangisi", olumsuz kök ve doğru/yanlış karta dönüşmez, "yaklaşık" içindeki "şık" şık sayılmaz. `test_per_user`: kutular kişiye özel, kişi alanı olmayan eski satırlar ilk hesabın, "Atla" kartta görülmüş sayılmaz |
| [`test_mastery.py`](../tests/test_mastery.py) | Beyin analizi (bölüm 12): sayfa → konu, son kanıtın kazanması (sınavdan sonra kartta bildi → biliyor), konu durumu eşikleri (tek yanlış zayıf değil, "öğrenildi" en az 4 soru), belge/konu sırası ve zayıf konular, bellek özeti, son 14 gün ("Atla" sayılmaz) |
| [`test_accounts.py`](../tests/test_accounts.py) | Hesaplar ve belge kütüphanesi (bölüm 11; geçici veritabanı). `test_profile_and_resume` (bölüm 12): profil kuralları, resmin 256×256 JPEG olması, kendi parolanı değiştirme, herkese açık notu listeye ekleme, kaldığın yer (üzerine yazma, kişiye özel, sınavda bekleme süresi sayılmaz). Parola özeti (tuz, yanlış parola, bozuk özet); kullanıcı adı kuralları, aynı ad ikinci kez alınamaz, büyük/küçük harf duyarsız giriş, ilk hesap eski kayıtların sahibi; oturum (çıkış, süre dolması, parola sıfırlayınca kapanma); Google için `link`/`by_identity`; şema adımlarının bir kez uygulanması. Belge: elle konan belge ilk hesaba bağlanır; aynı dosya başka adla ve aynı içerik farklı dosyayla tanınır; aynı ad farklı içerik üzerine yazmaz; yeni sürüm ayrı belge; iki taranmış belge birbirine eşlenmez; PDF olmayan dosya reddedilir; gizli/açık ve tek yönlülük; adı yalnızca sahibi değiştirir; silinmiş belgenin artığı olan ad yeni belgeye verilmez |
| [`test_difficulty.py`](../tests/test_difficulty.py) | Zorluk katmanı (bölüm 10). Yapı tavanları: kopya soru → kolay, tek kural (Vieta) → orta, tek formül → kolay, çok adımlı hesap → tavan yok, tek bilgi → orta, iki ayrı bilgi → zor olabilir, şişirilmiş adım + düz sayı → orta. `count_facts`: aynı bilgiyi tekrar eden ve notta olmayan alıntı sayılmaz. Etkin düzey sırası: gerçek öğrenci (≥5) > benzetim > iddia; hesap sorusunda benzetim yok sayılır. Önbellekten iddia geri yükleme, Elo (ikinci denemeler sayılmaz; yetenek kişi başına), `test_fresh_attempts` (yalnızca kişinin ilk görüşü: tekrar çözme, ikinci deneme, kartta görülmüş soru sayılmaz), benzetilmiş cevabın şık karıştırmayla kontrolü, zorlaştırmanın LLM'siz denemesi (istem A ve B parçalarını taşır, iki parçadan alıntı = 2 bilgi) |

Hepsini çalıştırmak için (PowerShell):
```powershell
foreach ($t in "test_textnorm","test_parser","test_checks","test_compute","test_grading","test_router","test_pipeline","test_cards","test_difficulty","test_accounts","test_mastery") { .venv\Scripts\python -m tests.$t }
```

---

## `scripts/bekci.py` — iş ve kota izleyici (115 satır)

**Ne işe yarar?** Belge işlerini (`data/jobs/*.log`), sınav isteklerini (`data/requests/*.log`) ve kotayı 45 saniyede bir yoklar. Bir **olay** olunca durumu yazdırıp **çıkar**. Claude Code oturumunda arka planda çalıştırılır: süreç çıkınca oturum uyanır ve kullanıcıya haber verir. Ürünün parçası değil, bir geliştirme aracı.

**Çıkış olayları:**
- iş bitti
- hata (Traceback)
- kota beklemesi başladı (⏳)
- süreç kayboldu
- 8 dakika ilerleme yok
- bir model yeni "dolu" işaretlendi
- periyot doldu (varsayılan 90 dk; periyodik rapor)

**İçindekiler**
- [`q(sql, *a)`](../scripts/bekci.py#L25): `data/llm.sqlite`'a doğrudan SQL sorgusu.
- [`exhausted()`](../scripts/bekci.py#L33): "dolu" işaretli (model, gün) çiftleri.
- [`text(p)`](../scripts/bekci.py#L37): dosyayı hata vermeden okur.
- [`procs()`](../scripts/bekci.py#L44): çalışan `python.exe` süreçlerinin komut satırları (PowerShell `Get-CimInstance` ile). `src.pipeline` ya da `src.request` çalışıyor mu?
- [`req_status(log)`](../scripts/bekci.py#L51): sınav isteğinin durumu (`generating` / `done`…).
- [`scan()`](../scripts/bekci.py#L62): izlenecek log dosyalarını bulur (etkin olanlar ya da bekçi başladıktan sonra değişenler).
- [`report(msg, log)`](../scripts/bekci.py#L74): olayı, log'un son 6 satırını ve kota özetini basar, `sys.exit(0)` ile çıkar.
- Alttaki `while True` döngüsü: 45 sn bekle → tara → her log için olay koşullarını denetle.

---

## `scripts/onizleme.py` ve `scripts/ekran.py` — arayüzü görerek kontrol

Tasarım değişikliği kullanıcıya gösterilmeden önce ekran görüntüsüyle bakılır. İkisi de geliştirme aracı; gerçek kayıtlara yazmaz.

**`onizleme.py` (85 satır):** çalışma ekranlarını hazır verilerle açan küçük bir Streamlit uygulaması (ayrı kapıda: 8502).
- Adres: `http://localhost:8502/?v=setup|session|flip|summary|quiz|results|login|docs|home|home0|profile`.
- Kart ekranları için havuzdan 15 kart seçer, birkaçını önceden değerlendirilmiş gösterir. `flip` kartı arka yüzü dönük çizer. `login` giriş ekranı, `docs` Belgeler sayfası, `profile` profil ve beyin analizi.
- `home`: dolu ana sayfa. Geçici veritabanına yarım bir kart oturumu, yarım bir sınav ve başkasınınmış gibi herkese açık bir not (Genetic Algorithms) yazar. `home0`: yarım oturum yok.
- Not: önizlemede yazı tipleri yüklenmiyor (Fraunces yerine yedek yazı tipi); yazı tipini doğru görmek için gerçek uygulamayı geçici hesap veritabanıyla açmak gerekir (bölüm 11).
- Kart değerlendirmeleri geçici dosyaya gider (`K.LOG` yönlendirilir); sınav ekranında `recorded=True` olduğu için `attempts.jsonl`'e yazılmaz.
- Hesaplar ve belge kaydı da geçici bir veritabanında (`appdb.PATH` yönlendirilir). İçinde tek bir "önizleme" hesabı var; ilk hesap olduğu için mevcut belgelerin sahibi o ve sayfalar onunla açılır.
- Gerçek uygulamayı (giriş dahil) gerçek hesaplara dokunmadan denemek için: `NOTARAG_APP_DB` ortam değişkeniyle geçici bir veritabanı verip `src/app.py`'yi başka bir kapıda açmak (bölüm 11). Dikkat: o kurulumda sınav çözmek ya da kart değerlendirmek yine gerçek `attempts.jsonl` / `cards.jsonl`'e yazar; yalnızca hesaplar ve belge kaydı ayrıdır.
- [`run_page(rel)`](../scripts/onizleme.py#L42): sayfa dosyasını (`src/ui/pages/cards.py`) burada çalıştırır.

**`tasarim.py` (2026-10-08):** önizlemenin göremediğini gösterir (yazı tipleri, giriş, menü, sayfa geçişleri). Gerçek uygulamayı **geçici bir hesap veritabanıyla** (`data/tasarim/app.sqlite`, `NOTARAG_APP_DB`) 8503'te açar; gerçek hesaplara dokunmaz.
- [`hazirla()`](../scripts/tasarim.py#L53): iki hesap (deneme / arkadas, parola `parola123`), yarım kart oturumu, yarım sınav, "arkadaşın" paylaştığı herkese açık bir not.
- [`baslat()`](../scripts/tasarim.py#L98), [`durdur()`](../scripts/tasarim.py#L90): uygulamayı ayrı süreçte açar / kapatır (her `baslat` önce durdurur: src/ui/pages dışı modül değişince yeniden başlatmak gerekir).
- [`ekran(specs)`](../scripts/tasarim.py#L238): giriş yapar, `"yol:ad[:adımlar]"` sayfalarının ekran görüntüsünü `data/tasarim/ekran/`'a alır. Adımlar `" > "` ile ayrılır ve sırayla yapılır ([`Tab.steps`](../scripts/tasarim.py#L190), 2026-10-08 akşamı):
  - `seçici`: fareyle üzerine gel (sayfada ya da bileşenlerin Shadow DOM'unda arar); `!seçici`: gerçek fare tıklaması;
  - `~2`: bekle; `^ArrowRight`: tuşa bas; `#ifade`: JS çalıştır, sonucu yaz; `@ad`: akışın ortasında ekran görüntüsü;
  - `$COLLAPSE` / `$EXPAND`: kenar çubuğunu kapatan / açan düğme. Streamlit çubuğun durumunu tarayıcıda sakladığı için her açılış çubuk açık başlar.
  - Örnek: `"documents:okuyucu:!.stack:nth-child(2) > ~2 > ![role=tab]:nth-child(2) > @sayfalar > !.st-key-dv_full button > ^ArrowRight"` (kart → pencere → Sayfalar → tam ekran → sonraki sayfa).
  - Ekran boyutu: `$env:NR_EKRAN="1280x720"` (varsayılan 1440x1000).
- [`tikla(specs)`](../scripts/tasarim.py#L250): ana sayfada `"seçici|ad"` öğesine gerçek fare tıklaması; gidilen adres, başlık ve seçili düğmeleri yazar. Kart üzerine gelince kalktığı için konum yeniden ölçülür ([`Tab.hover`](../scripts/tasarim.py#L163)).
- Dikkat: o kurulumda da sınav bitirmek ya da kart değerlendirmek gerçek `attempts.jsonl` / `cards.jsonl`'e yazar; betik bu düğmelere basmaz.

**`ekran.py` (65 satır):** tarayıcı kurulumu olmadan ekran görüntüsü. Windows'taki Edge görünmez modda açılır ve CDP (Chrome DevTools Protocol) ile sürülür; Streamlit çizimini bitirsin diye beklenir. Edge'in tek seferlik `--screenshot` seçeneği yalnızca yükleme iskeletini yakalıyordu.
```powershell
.venv\Scripts\python scripts\ekran.py <url> <çıktı.png> [bekleme_sn] [genişlik] [yükseklik] [js]
```

---

## `scripts/ogm_indir.py` ve `scripts/auad_indir.py` — deney verisi indirme

İnternet varken bir kez çalıştırılan geliştirme araçları; indirdikleri `data/kaynak_veri/`'ye gider (depoya girmez; içerik ve kaynaklar `data/kaynak_veri/BENIOKU.md`'de).
- `ogm_indir.py`: MEB OGM Materyal'in ön yüz paketinden çıkarılan katalogdan seçili koleksiyonları indirir (MEBİ konu özetleri, 3 Adım soru bankası, kazanım kavrama, tarama, 2024 denemeleri). 3 paralel indirme, yarım kalan dosya `.part`, PDF olmayan yanıt atılır.
- `auad_indir.py`: Ankara Üniversitesi Açık Ders (Moodle, girişsiz) — 12 fakülteden rastgele (sabit tohum) derslerin ilk haftalarının yalnızca PDF notları. İstekler sırayla ve 1 sn aralıklı.

## `scripts/rehber_satirlari.py` — bu rehberin bakımı

**Ne işe yarar?** Rehberdeki fonksiyon bağlantılarının (ör. ``[`ad`](…/dosya.py#L42)``) satır numaralarını koda göre düzeltir. Kod değiştikçe fonksiyonlar aşağı yukarı kayar; bu betik sayesinde bağlantılar doğru satırı göstermeye devam eder.

- [`definitions(path)`](../scripts/rehber_satirlari.py#L19): dosyayı `ast` ile okur. Her fonksiyonun, sınıfın, metodun (`Sınıf.metot`) ve modül düzeyi atamanın satırını çıkarır.
- [`symbol(text)`](../scripts/rehber_satirlari.py#L39): bağlantı metnindeki ilk `…` içinden aranacak adı çıkarır (`Index().build()` → `Index.build`).
- [`main(write)`](../scripts/rehber_satirlari.py#L49): bütün `rehber/*.md` bağlantılarını gezer, satırı değişenleri raporlar; `--yaz` ile dosyaları günceller. Adı bulunamayan bağlantıları listeler.

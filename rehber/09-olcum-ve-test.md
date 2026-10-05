# 9. Ölçüm, testler ve araçlar

[← 8. Arayüz](08-arayuz.md) · [Ana sayfa](README.md)

Üç tür dosya var:
- **`eval/`:** "sistem ne kadar iyi?" sorusunu sayıyla cevaplayan **deney betikleri**. Sonuçlarını `eval/sonuclar_*.json` / `.md` dosyalarına yazar; Rapor sayfası bunları okur. Çoğu API çağırır, yani kota harcar.
- **`tests/`:** "kod hâlâ doğru mu?" sorusunu cevaplayan **regresyon testleri**. API çağırmaz, saniyeler sürer. Her test bulunmuş bir hatanın geri gelmesini önler.
- **`scripts/bekci.py`:** arka plan işlerini izleyen geliştirme aracı.

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

### `eval/retrieval_queries.json`

Elle yazılmış konu sorguları ve her birinin doğru sayfaları. Sorgu türleri: Türkçe→Türkçe, Türkçe sorgu→İngilizce slayt, İngilizce→İngilizce.

> **Eksik deney (ödev gereksinimi):** "Kaynak metinlerle desteklenen üretimin cevap doğruluğuna etkisi". Yukarıdaki deneylerin hepsi **kaynaklı** koşulda; kaynaksız bir karşılaştırma noktası yok. Plan için ROADMAP "Sıradaki işler" 4. maddeye bak.

---

## `tests/` — regresyon testleri (API yok)

| Dosya | Neyi sabitliyor? |
|---|---|
| [`test_textnorm.py`](../tests/test_textnorm.py) | Türkçe küçük harf (`IŞIK` → `ışık`), `İSTANBUL` = `Istanbul` eşleşmesi, satır sonu tiresi çözümü (`bü-tün` → `bütün`, `meta-sezgisel` korunur), Wingdings madde işareti, üst/alt simgelerin korunması, `pretty_math` (LaTeX kesir → `(100 · a)/(a + b)`) |
| [`test_parser.py`](../tests/test_parser.py) | Gerçek PDF'lerle (`data/sample_docs/` gerekir): dil tespiti, döndürülmüş sayfada üst bilgi temizliği, içerikteki `22` sayılarının silinmemesi, tekrar eden slayt başlıklarının korunması, şekil etiketlerinin ayrılması, kapak/içindekiler bayrakları, resim sayfalarının görsele gitmesi, işlemcide tablo çıkarma, bozuk formül tespiti, Türkçe karakterler. 11 test; her birinin yorumunda hangi hatayı önlediği yazılı |
| [`test_checks.py`](../tests/test_checks.py) | Metne atıf tespiti ("Bu seçim stratejisinin…" yakalanır, "Bu nedenle…" yakalanmaz), D/Y "Yanlış" → `false`, LaTeX'li kanıtın bulunması, uydurma kanıtın reddi, "öz alt küme" tekrar kuralı ve onun **yanlış alarm vermemesi** (sayısı farklı ya da sırası farklı şıklar), açıklamalı cevap metni, kesin ifadeli çeldiriciler, havuzla tekrar tespiti |
| [`test_compute.py`](../tests/test_compute.py) | Güvenlik: `__import__`, `x.__class__`, `open(...)`, `lambda`, dev üs reddedilir. Doğru soru reddedilmez. Yanlış anahtar, iki doğru şık, metin–değer çelişkisi yakalanır. `%25` ve `2,5` gibi Türkçe yazımlar. Şık karıştırmanın değerleri de taşıması |
| [`test_grading.py`](../tests/test_grading.py) | 29 durum: `2` ≠ `(n choose 2)·2`, `30240` = `9!/(3!·2!)`, `n²-n` = `2C(n,2)`, `tanımsızdır` = `tanımsız`, `böcek` ≠ `Faydalı böcekler (parazitoid)`; güvenlik girdileri (`9^9^9`, `__import__('os')`) yanlış sayılır ve sistemi kilitlemez |
| [`test_router.py`](../tests/test_router.py) | Hata mesajından bekleme süresi (`10m28.992s` → 628,992 sn). Groq TPD = süreli bekleme, Gemini günlük = gün boyu kapatma. Ağ zaman aşımı kota sayılmaz. `AllModelsExhausted.transient` mantığı. `test_family`: aynı model farklı sağlayıcıda aynı aile; Gemma = Gemini; Mistral takma adları. `test_cache_key`: varsayılan akıl yürütme düzeyinde önbellek anahtarı eskisiyle aynı kalır, `REASONING_VERIFY=low` ayrı anahtar alır |
| [`test_pipeline.py`](../tests/test_pipeline.py) | `merge_existing`: eskiler korunur, parçası kalmayan eski düşer, önbellekten aynen gelen atlanır, başka modelden gelen aynı metin `duplicate` olarak reddedilir |

Hepsini çalıştırmak için (PowerShell):
```powershell
foreach ($t in "test_textnorm","test_parser","test_checks","test_compute","test_grading","test_router","test_pipeline") { .venv\Scripts\python -m tests.$t }
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

## `scripts/rehber_satirlari.py` — bu rehberin bakımı

**Ne işe yarar?** Rehberdeki fonksiyon bağlantılarının (ör. ``[`ad`](…/dosya.py#L42)``) satır numaralarını koda göre düzeltir. Kod değiştikçe fonksiyonlar aşağı yukarı kayar; bu betik sayesinde bağlantılar doğru satırı göstermeye devam eder.

- [`definitions(path)`](../scripts/rehber_satirlari.py#L19): dosyayı `ast` ile okur. Her fonksiyonun, sınıfın, metodun (`Sınıf.metot`) ve modül düzeyi atamanın satırını çıkarır.
- [`symbol(text)`](../scripts/rehber_satirlari.py#L39): bağlantı metnindeki ilk `…` içinden aranacak adı çıkarır (`Index().build()` → `Index.build`).
- [`main(write)`](../scripts/rehber_satirlari.py#L49): bütün `rehber/*.md` bağlantılarını gezer, satırı değişenleri raporlar; `--yaz` ile dosyaları günceller. Adı bulunamayan bağlantıları listeler.

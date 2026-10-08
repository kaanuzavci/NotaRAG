# 10 · Zorluk: iddia değil ölçüm

[← Rehber ana sayfası](README.md)

Bu bölüm iki dosyayı anlatır: `src/difficulty.py` (zorluğun nereden geldiği) ve `src/simulate.py` (benzetilmiş öğrenci).

## Neden ayrı bir katman?

2026-10-05'te kullanıcı TYT için 20 "zor" hesap sorusu istedi; sorular orta gibi geldi. Bakınca iki şey çıktı:

1. Kod, sınav isteğinde **her soruya istenen zorluğu zorla yazıyordu**. Gemini'nin önbellekteki ham yanıtında kendi etiketleri 17 sorudan 14 "orta", 1 "kolay", 2 "zor"du.
2. Literatür de aynı şeyi söylüyor (LITERATURE.md §8): LLM'in "bu soru zor" demesi gerçek öğrenci zorluğunu neredeyse hiç öngörmüyor; yapay zekâ soruları uzman sorularından belirgin biçimde kolay çıkıyor.

Çözüm: etiketi **ölçmek**. Etiket eldeki en güvenilir katmandan gelir ve kaynağı yanında saklanır:

```
gerçek öğrenci (Elo, ≥5 ilk deneme)          ← en güvenilir, tavanla kısılmaz
  yoksa → benzetilmiş öğrenci (yalnızca sözel sorular; Gemma 4 sınıfı)
  yoksa → üretecin kendi etiketi (önbellekteki ham yanıttan)
        ↓
   yapı tavanı (kod, kota yok): "en fazla şu düzey olabilir" + nedeni
        ↓
   q["difficulty"] = etkin düzey   ·   q["difficulty_claim"] = üretecin etiketi   ·   it["difficulty"] = {level, source, ...}
```

Soru dosyalarına (`data/questions/*.jsonl`) **hiçbir şey yazılmaz** (veri bütünlüğü kuralı). Etkin düzey, sorular yüklenirken bindirilir ([`request.all_items`](../src/request.py#L72) ve [`review_store.load_set`](../src/review_store.py#L46) içinde `apply`). Bu yüzden arayüz, sınav, kartlar ve dışa aktarma hiç değişmeden doğru etiketi görür; hepsi `q["difficulty"]` okuyor.

---

## `src/difficulty.py` — etkin zorluk

**Bağlantılar**
- ← `request.all_items`, `review_store.load_set` (`apply`), `request._settle` (`apply`, `RANK`), `simulate` (`record`, `measurements`, `sim_level`), `eval/zorluk_olcumu.py`, `tests/test_difficulty`.
- → `textnorm.normalize_for_match`, `rapidfuzz`.
- 💾 Okur: `data/review/difficulty.jsonl` (ölçümler), `data/review/attempts.jsonl` (çözümler), `data/llm.sqlite` (ham yanıtlar). Yazar: `difficulty.jsonl` (yalnızca ekler).

**Sabitler**
- [`LEVELS`](../src/difficulty.py#L36) / [`RANK`](../src/difficulty.py#L37): `easy < medium < hard` sıralaması (karşılaştırma için 0, 1, 2).
- [`MIN_REAL`](../src/difficulty.py#L38) `= 5`: gerçek öğrenci etiketi için en az ilk deneme sayısı.
- [`P_EASY`](../src/difficulty.py#L40): doğru oranı eşikleri (`P_EASY` = 0,75, `P_HARD` = 0,40).

### 1. Yapı: kodla ölçülen özellikler

- [`features(q, check)`](../src/difficulty.py#L64): her soru için, dilden ve konudan bağımsız:

| Özellik | Ne ölçer? | Neden? |
|---|---|---|
| `facts` | Notta bulunan **ayrı** kanıt alıntısı sayısı (`check["facts"]`; eski sorularda 1) | Soru kaç ayrı bilgiyi ya da kuralı birleştiriyor? (otomatik madde üretiminde zorluğu değiştiren asıl değişken) |
| `overlap` | Soru kelimelerinin kaynak cümlede geçen payı | Soru kaynak cümleyi kopyalıyorsa tanıma düzeyindedir |
| `answer_in_source` | Doğru cevap kaynak cümlede aynen geçiyor mu? | Aynen geçiyorsa bulmak kolaydır |
| `bloom` | Üretecin verdiği bilişsel düzey | Hatırlama sorusu "zor" olamaz |
| `steps`, `ops` | Hesap sorusunda çözüm adımı ve SymPy ifadesindeki işlem sayısı | Tek işlem = tek formül |
| `negation` | Olumsuz kök ("değildir") | Kayıt için (tavan kuralı değil) |
| `distractor_sim` | Doğru şıkka en yakın çeldiricinin benzerliği | Yakın çeldirici zorlaştırır (Susanti ve Tokunaga) |

- [`answer_text(q)`](../src/difficulty.py#L57): doğru cevabın metni (ÇS'de doğru şık, KC'de cevap, D/Y'de boş).
- [`cap(q, f)`](../src/difficulty.py#L87): **tavan**, yani yapının izin verdiği en yüksek düzey ve nedeni. Kurallar sırayla:

| Koşul | Tavan | Neden |
|---|---|---|
| Cevap kaynakta aynen yazılı **ve** soru o cümleyi büyük ölçüde tekrar ediyor | kolay | Tanıma sorusu |
| D/Y ifadesi kaynak cümlenin neredeyse aynısı | kolay | |
| Hesap sorusu tek işlem (ör. `binomial(8, 3)`) | kolay | Tek formül |
| Tek bilgi/kural **ve** çok adımlı hesap değil | orta | "Zor" en az iki ayrı bilgi ya da çok adım ister |
| Hatırlama düzeyi (hesap değil) | orta | |

### 2. Benzetim ve gerçek öğrenci

- [`measurable(q)`](../src/difficulty.py#L106): benzetim bu soruda ölçüm verebilir mi? Yalnızca sözel ve nesnel puanlanan sorular: çoktan seçmeli ve doğru/yanlış. Kural tek yerde; `simulate.simulable` ve `effective` bunu kullanır.
- [`sim_level(p, think, qtype)`](../src/difficulty.py#L113): benzetim ölçümünü düzeyin **alt sınırına** çevirir; iki sinyalden zor olanı.
  - Doğru oranı: sınıf yanıldıysa `p < 0,40` zor, öbür durumlarda orta. Hepsi doğruysa (`p = 1`, tavan) bu sinyal bilgi vermez.
  - Çaba, **yalnızca çoktan seçmelide**: dikkatli çözüm ≥ 600 token orta, ≥ 1200 zor (`THINK_MEDIUM_MC`, `THINK_HARD_MC`). Eşikler gerçek öğrenci verisinden: TurkishMMLU'da (180 soru) ≥ 600 → %85 orta ya da zor (taban %67), ≥ 1200 → %70 zor (taban %31). Doğru/yanlışta kullanılmaz: 2026-10-06 sözel pilotunda çaba soru tipini ölçtü (D/Y 221-269, ÇS 365-545 token); eski tek eşikli kural (300 / 900) D/Y'yi hep kolay, ÇS'yi hep orta yapıyordu.
  - İkisi de bilgi vermiyorsa `None`: etiketi iddia + yapı tavanı verir. `effective` iddiayla alt sınırın büyüğünü alır: ölçüm kolay iddiayı yükseltir, zor iddiayı düşürmez.
  - TurkishMMLU doğrulaması (2026-10-07, 180 soru, gerçek öğrenci doğru oranı, `eval/sonuclar_turkishmmlu.md`): öğrenci zorluğuyla Spearman ρ — **çaba −0,42** [−0,54 … −0,30] (soru tipi sabitken en güçlü tek sinyal; dokuz dersin dokuzunda doğru yönde), **LLM'in zorluk etiketi −0,36** [−0,48 … −0,23] (isabet 83/180 = %46, şans %33; "zor" etiketi %73 kesin ama zorların yalnızca %20'sini yakalıyor, "kolay" etiketi %45 kesin: LLM zorluğu hafife alıyor), benzetilmiş öğrenci p +0,29 [+0,16 … +0,43] (matematikte −0,01: sinyal yok), etiket + çaba birlikte −0,46. An ve Wang'ın (2026) İngilizce bulgusundan (ρ ≈ 0,06) belirgin biçimde iyi; fark kısmen bu verinin sınav tarzı 5 şıklı lise soruları olmasından gelebilir.
- [`record(entry)`](../src/difficulty.py#L131) / [`measurements(path)`](../src/difficulty.py#L137): ölçüm kaydı; aynı soru yeniden ölçülürse son ölçüm geçerli.
- [`claims_from_cache(db)`](../src/difficulty.py#L153): `llm.sqlite`'taki üretim yanıtlarını tarar, "soru metni → üretecin etiketi" eşlemesi çıkarır. Eski kayıtlarda zorla yazılmış etiketin yerine gerçek iddia buradan gelir. Dosya değişmedikçe sonuç bellekte tutulur.
- [`elo(attempts, prior)`](../src/difficulty.py#L180): satrançtaki Elo puanının eğitimdeki kullanımı (Pelánek 2016). Her çözümde maddenin zorluğu `d` ve öğrencinin yeteneği `θ` birlikte güncellenir: doğru cevap → madde kolaylaşır, öğrenci güçlenir. Adım her güncellemede küçülür. İkinci denemeler sayılmaz. **Sorunun zorluğu `d` herkesin denemelerinden ortak, yetenek `θ` kişi başına** (satırdaki `user` alanı; 2026-10-07'ye kadar kişi bilgisi yoktu, tek öğrenci varsayılıyordu). Kişi başına θ önemli: güçlü bir öğrencinin doğruları, yeni gelen birinin yanlışını "soru zor" diye fazla okutmaz.
- [`_epoch(a)`](../src/difficulty.py#L204): denemenin zamanı. Yeni satırlarda kesin `t`, eskilerde `time` metninden.
- [`fresh_attempts(rows, legacy, card_seen)`](../src/difficulty.py#L213): **ölçüme giren denemeler = kişinin soruyu ilk görüşü.** Sayılmayanlar:
  - ikinci denemeler (yalnızca yanlışlar, `retry`);
  - aynı kişinin aynı soruyu yeniden çözmesi ("Baştan çöz", soru başka bir sınavda yine çıktı). Eskiden bunlar da ilk deneme sayılıyor, doğru oranını şişiriyordu;
  - önce kartta cevabı görülmüş soru (`card_seen`: [`cards.first_seen`](../src/cards.py#L74)).

  `legacy`: kişi alanı olmayan eski satırların sahibi (ilk hesap; bölüm 11). Bu yüzden [`MIN_REAL`](../src/difficulty.py#L38) = 5 artık "5 farklı kişi" demek: 1-2 hesapla (ikisi de aynı kişi) gerçek öğrenci etiketi devreye girmez, zorluk öbür katmanlardan gelir.
- [`real_attempts()`](../src/difficulty.py#L234): `attempts.jsonl` → `fresh_attempts`. Madde analizi ([`request.item_stats`](../src/request.py#L364)) ve Elo aynı listeyi kullanır.
- [`_real()`](../src/difficulty.py#L241): taze ilk denemelerden Elo, düzey eşikleri benzetimle aynı.

### 3. Bindirme

- [`effective(it, sim, real, claims)`](../src/difficulty.py#L253): yukarıdaki sırayla etkin düzeyi seçer, tavanı uygular. Tavan düzeyi düşürdüyse `capped_from` ve `cap_why` alanlarına eski düzey ve neden yazılır. Ölçülemeyen sorularda (`measurable` değil) benzetim kaydı olsa bile yok sayılır.
- [`apply(items)`](../src/difficulty.py#L274): her soruya `effective` sonucunu bindirir.

---

## `src/simulate.py` — benzetilmiş öğrenci

**Ne işe yarar?** Sözel çoktan seçmeli ve doğru/yanlış soruların zorluğunu **ölçer**. Zayıf ya da orta boy modellerden bir "sınıf" (Gemma 4: 26B-A4B ×2, 31B ×2) her soruyu:
- **açık kitap** çözer: kaynak sayfa önünde, yani ezber değil sorunun istediği düşünme ölçülür;
- **çalışma yazmadan** çözer (`thinking_level="minimal"`): cevap hemen görünmüyorsa (birden çok bilgi, çok adım) daha sık yanılır.

Doğru oranı `p`. Ayrıca bir "dikkatli öğrenci" (`thinking_level="high"`) soruyu çözerken kaç düşünme token'ı harcadığını söyler: çaba (kaydedilir, düzeye katılmaz; yukarıda `sim_level`). İstem PROMPTS.md §8.

Neden Gemma? Literatür, güçlü modellerin zorlanan öğrenciyi taklit edemediğini, zayıfların daha iyi olduğunu söylüyor; Gemma aynı anahtarda ve kotası ayrı.

**Hesap soruları benzetilmez.** 2026-10-05 denemesinde Gemma 4 lise matematiğinde ya kafadan aritmetiğe takıldı (tuz karışımı p = 0,25) ya da karalama kâğıdı verilince her şeyi çözdü (4 sorunun 4'ünde p = 1,0). Onların zorluğu yapıdan gelir.

**Sözel kısa cevap da benzetilmez.** Cevap metin eşleşmesiyle puanlanıyor; anlamı yakalamıyor. 2026-10-06 pilotunda dört örneklemin dördü de doğru cevabı farklı sözcüklerle verdi ("verimlerinin önemli bir kısmını kaybetme"; anahtar: "büyük ürün ve verim kayıpları riskine karşı savunmasızlık") ve 0/4 sayıldı: sahte bir "zor". Bu sorularda etiketi üretecin iddiası ve yapı tavanı verir.

**Bağlantılar**
- ← `request._settle`, `eval/zorluk_olcumu.py`, komut satırı (`python -m src.simulate`).
- → `router.call(..., think=...)`, `prompts.load_prompt("8")`, `grading.grade_short`, `difficulty.record`.
- 💾 Yazar: `data/review/difficulty.jsonl`. Yanıtlar `llm.sqlite`'ta önbellekte; yeniden çalıştırma kota harcamaz.

- [`CLASS`](../src/simulate.py#L36) / [`CAREFUL`](../src/simulate.py#L37): sınıf (model, örneklem sayısı) ve dikkatli öğrenci.
- [`_role(model)`](../src/simulate.py#L44): geçici ölçüm rolü. Model meşgulse (503) örneklem sınıftaki öbür modele geçer. Bu bir kalite kapısı rolü değil: model içerik üretmiyor, doğrulamıyor, yalnızca ölçüyor.
- [`simulable(it)`](../src/simulate.py#L50): `difficulty.measurable`.
- [`_prompt(it, context, student)`](../src/simulate.py#L54): §8 istemi. Her örneklem şıkları **farklı karıştırır** ve öğrenci numarası taşır, böylece örneklemler bağımsızdır (önbellekten aynı cevap gelmez) ve modelin harf yanlılığı ölçümü bozmaz.
- [`correct(it, reply, perm)`](../src/simulate.py#L67): cevap doğru mu? ÇS'de yanıttaki ilk şık harfi karıştırma geri çevrilerek kontrol edilir; D/Y'de "doğru/yanlış"; KC'de sınavdaki puanlama kuralı (`grade_short`; bugün yalnızca testte kullanılıyor, KC benzetilmiyor).
- [`context_of(it, chunks)`](../src/simulate.py#L82): sorunun parçaları, doğrulayıcının gördüğü bağlamla aynı.
- [`measure(it, chunks)`](../src/simulate.py#L86): bir soru = 4 hızlı + 1 dikkatli çağrı. Dikkatli çağrı önbelleğe bakmaz: önbellekten gelen yanıt düşünme token'ını taşımaz, çaba ölçülemezdi.
- [`run(items, chunks, skip_measured, log, waits)`](../src/simulate.py#L108): ölçülmemiş ölçülebilir soruları ölçer.
  - Gemma geçici yoğunsa (503, iki model birden) 2 dk bekleyip yeniden dener, en çok `waits` kez. Önceki örneklemler önbellekte olduğu için yeniden deneme yalnızca eksik çağrıları yapar.
  - Kota doluysa ya da yoğunluk sürerse ölçüm durur; sınav beklemez. Ölçülemeyen soruda etiketi iddia + yapı tavanı verir.

---

## Akışa nasıl bağlanıyor?

Sınav isteğinde zorluk seçildiyse ([`request._settle`](../src/request.py#L294)):
1. Yeni sorular kod kontrolü ve doğrulamadan geçer, dosyaya **üretecin etiketiyle** yazılır.
2. Ölçülebilir olanlar (sözel ÇS ve D/Y) benzetilir, sonra hepsine `apply`.
3. Yalnızca **istenen düzeyde ölçülenler** sınava girer; gerisi havuzda kendi düzeyiyle kalır.
4. Yeterli soru yoksa düzeyin altında kalanlar **zorlaştırılır** ([`generate.evolve_request`](../src/generation/generate.py#L304), PROMPTS §2d): başka bir konunun notuyla birleştirme, koşul ekleme, uygulamaya çevirme. Yeni sorular aynı zincirden geçer.

Üretimde de değişiklik var: istemler zorluğu ölçülebilir ölçütlerle tanımlıyor ve her ayrı bilgi ya da kural için ayrı alıntı istiyor (`evidence_quotes`). "Zor" en az iki farklı yerden iki alıntı ister.

## Sınırlar (dürüst not)

- Benzetim **göreli** bir sinyal; gerçek öğrenci verisiyle doğrulanmadan kesin etiket sayılmamalı. Literatürde en iyi sonuçlar bile mükemmel değil (gerçek zorlukla ~0,6-0,8 korelasyon).
- Hesap ve sözel kısa cevap sorularında ölçüm yok, etiket yapı tavanlı iddia. Kısa cevap için anlamı karşılaştıran bir puanlayıcı (ör. doğrulayıcı ailesinden hakem, PROMPTS §4d) eklenirse ölçülebilir; her soru için ek çağrı demek.
- Hesap sorularında model benzetimi bugün işe yaramıyor; daha zayıf bir model (ör. Mistral'ın 3B/8B modelleri) ya da gerçek çözümler gerekiyor.
- Elo tek kullanıcıda öğrenci yeteneği ile madde zorluğunu tam ayıramaz; sınıf kullanımında güçlenir.
- Pilot sonuçları: `eval/sonuclar_zorluk.md`.

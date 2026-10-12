# 8. Arayüz (Streamlit)

[← 7. Sınav isteği](07-sinav-istegi.md) · [Ana sayfa](README.md) · Sonraki: [9. Ölçüm ve testler →](09-olcum-ve-test.md)

Projenin en büyük katmanı (boş satırlar hariç ~2.260 satır, 13 dosya). Arayüz hiçbir LLM'i doğrudan çağırmaz. Dosyaları okur, sonuçları gösterir; uzun işleri ayrı süreç olarak başlatır (`pipeline`, `request`).

Sayfalar yalnızca **giriş yapılınca** çalışır (bölüm 11). Rol yok: herkes aynı sayfaları görür. Belge ya da içeriği gösteren her sayfa, kişinin görebildiği belgelerle süzer ([`data.visible()`](../src/ui/data.py#L67)); kişiye ait kayıtlar (sınav çözümü, kart, bildirim, inceleme kararı) giriş yapan kişinin kimliğiyle ([`data.uid()`](../src/ui/data.py#L55)) yazılır.

Sorulardaki zorluk etiketi, arayüze gelmeden önce ölçümle değiştirilir (`request.all_items` ve `review_store.load_set` içinde `difficulty.apply`; bölüm 10). Bu yüzden arayüzün gösterdiği "Kolay / Orta / Zor" etkin düzeydir, üretecin iddiası değil.

```
src/app.py                 menü ve giriş (bölüm 1)
src/ui/auth.py             giriş ekranı, "beni hatırla" çerezi, çıkış (bölüm 11)
src/ui/pages/home.py       Ana sayfa (varsayılan): not desteleri, herkese açık notlar, kaldığın yer (bölüm 12)
src/ui/pages/profile.py    Profil ve beyin analizi (bölüm 12)
src/ui/shelf.py            kart desteleri (ana sayfa + Belgeler): Streamlit özel bileşeni, CCv2 (bölüm 12)
src/ui/docview.py          not penceresi (konular, sayfalar, hazır sorular, ad, görünürlük) ve not kartı (bölüm 13)
src/ui/reader.py           tam ekran PDF okuyucu: CCv2 (bölüm 13)
src/ui/upload.py           not yükleme akışı (ana sayfadaki "+ Yeni not ekle" penceresi; bölüm 12)
src/ui/style.py            görsel dil: CSS + küçük HTML yardımcıları
src/ui/data.py             arayüzün veri katmanı (dosya okuma, önbellek, arka plan işleri)
src/ui/components.py       ortak soru kartı, kaynak sayfa kartı, bitiş özeti
src/ui/quiz.py             sınav çözme deneyimi (başlangıç → odak modu → sonuç)
src/cards.py               bilgi kartı mantığı: deste, aralıklı tekrar (Streamlit'siz)
src/ui/pages/exam.py       Sınav Hazırla
src/ui/pages/cards.py      Bilgi Kartları (seçim, oturum durumu, özet)
src/ui/flashcards.py       kart oturumu ekranı: CCv2 (çevirme, sürükleme, yığınlar tarayıcıda)
src/ui/pages/documents.py  Belgeler: bütün notlar kart kart, süzgeç / arama / sıralama (bölüm 13)
src/ui/pages/bank.py       Soru Bankası
src/ui/pages/review.py     İnceleme (kalite kontrol; rol yok, her hesap görür)
src/ui/pages/report.py     Rapor (nasıl çalışır + ölçümler)
src/ui/pages/models.py     Modeller ve Kota
src/ui/parts/evaluation.py Rapor'un ölçüm grafikleri
src/ui/parts/system.py     (ÖLÜ KOD: hiçbir yerden çağrılmıyor)
```

---

## Önce Streamlit'in çalışma modeli

Streamlit'i ilk okuyanı en çok şaşırtan şey şu: **her etkileşimde sayfa dosyası baştan sona yeniden çalışır.** Düğmeye basmak, seçim değiştirmek, yazı yazıp Enter'a basmak, hepsi betiği tepeden yeniden çalıştırır. Bu modelin sonuçları:

- **Değişkenler kaybolur.** Tıklamalar arasında saklanması gereken her şey `st.session_state`'e konur. Sınavda bu `st.session_state.exam` sözlüğüdür: şu an hangi sorudasın, cevapların, ipuçların.
- **`if st.button(...)`** düğmeye basıldığı **o** çalıştırmada `True` döner.
- **`on_click=fonksiyon`** ile verilen geri çağırma, yeniden çalıştırmadan **önce** çalışır. Sınavda şık seçimi böyle yapılır (`_pick`).
- **`st.rerun()`** betiği hemen baştan başlatır (ör. faz değişince).
- **`@st.cache_data(ttl=20)`** fonksiyonun sonucunu 20 saniye saklar; her tıklamada diskten okunmaz. `fonksiyon.clear()` önbelleği boşaltır.
- **`@st.fragment(run_every=3)`** sayfanın yalnızca o parçasını 3 saniyede bir yeniden çalıştırır. Arka plandaki işin ilerleme çubuğu böyle canlı kalır.
- **`key=`**: aynı etiketli iki düğme aynı kimliği alır ve `StreamlitDuplicateElementId` hatası verir; bu yüzden anahtar verilir. `st.container(key="nr_opts")` ayrıca CSS sınıfı `.st-key-nr_opts` üretir. Stil dosyası bu sınıfları hedefler.
- **`st.query_params`**: adres çubuğundaki `?sinav=<id>`. Sayfa yenilense de sınav kaybolmaz, bağlantı paylaşılabilir.

---

## `src/ui/style.py` — görsel dil (509 satır)

**Ne işe yarar?** "Akademik baskı + fosforlu kalem" görünümü.
- Renkler ve yazı tipleri [`.streamlit/config.toml`](../.streamlit/config.toml)'da: kâğıt zemin `#F7F4ED`, mürekkep laciverdi, Fraunces / Instrument Sans / JetBrains Mono.
  - Yazı tipleri yerelden sunulur (`src/static/fonts/`, `[[theme.fontFaces]]`, `server.enableStaticServing`): internetsiz sunumda da aynı görünüm. Yalnızca latin + latin-ext (Türkçe harfler). Lisans: SIL OFL 1.1.
- Bu dosyada Streamlit bileşenlerinin karşılamadığı ayrıntılar var: kâğıt dokusu, sarı vurgu, kartlar, sınav ekranı düzeni.
- Ayrıca HTML üreten küçük yardımcılar.
- Çalışma ekranlarının (kart kurulumu ve özeti, sınav) tasarım ilkesi, "v3": düz kâğıt zemin üstünde sakin kartlar. Hareket yalnızca bir anlam taşıyınca var. Kart oturumunun kendisi 2026-10-12'den beri ayrı bir bileşen, kendi stiliyle (`flashcards.py`).

**Bağlantılar:** ← `app.py` ve bütün `ui/` dosyaları.

**İçindekiler**
- `INK, PAPER, HIGHLIGHT`: renk sabitleri (dışarıda kullanılmıyor).
- `STATUS`: etiket → (Türkçe ad, yazı rengi, zemin rengi).
- `_CSS` ([satır 21-398](../src/ui/style.py#L21)): bütün özel stiller. Bölümleri:
  - kâğıt dokusu (SVG gürültü);
  - sayfa başlığı (`.nr-kicker`, `.nr-title`, çift çizgi);
  - kenar çubuğunda giriş yapan kişi (`.nr-who`; bölüm 11);
  - fosforlu vurgu (`.nr-hl`);
  - kartlar, durum rozeti (`.nr-pill`), 6 adımlı akış şeması (`.nr-flow`);
  - soru kartı (`.nr-exam`, `.nr-opt`);
  - Modeller ve Kota kutuları (`.nr-tile`, `.nr-mcard`, `.nr-meter`);
  - **sınav odak modu**: sabit yükseklikler (`.st-key-nr_answer`, `.st-key-nr_opts`), alta yapışık gezinme çubuğu (`.st-key-nr_nav`), ipucu kutusu (`.nr-hint`);
  - İnceleme sayfasının iki kart düzeni (`.nr-pair`);
  - **çalışma ekranları (v3)**: ortak renk değişkenleri (`:root` içinde `--nr-good`, `--nr-bad`, `--nr-accent`…);
    - kart kurulum ekranının sayı kutuları (`.nr-ctiles`; oturum ekranının stilleri `flashcards.py`'de);
    - bitiş özeti (`.nr-sum`, ölçer `.nr-m`, konu satırı `.nr-tr`): kart oturumu ve sınav sonucu ortak;
    - sınav kartının üstündeki soru başına renkli şerit (`.nr-focus::before`);
- `PALETTE`: altı pastel kart rengi `(açık, koyu pastel, yazı, vurgu)`. Yazı rengi her pastelde en az 7:1 karşıtlıkta.
- [`color(i)`](../src/ui/style.py#L431): i. kartın rengi (palet döner).
- [`color_vars(i)`](../src/ui/style.py#L435): o rengi CSS değişkenleri olarak verir (`--c1`, `--ink`, `--a`…); kart HTML'inin `style=` özniteliğine yazılır.
- [`inject()`](../src/ui/style.py#L454): CSS'i sayfaya basar (`app.py` çağırır).
- [`html(markup)`](../src/ui/style.py#L460): HTML'i `st.markdown(..., unsafe_allow_html=True)` ile basar.
  - Neden `st.html` değil? `st.html` içeriği ana sayfanın stillerinden yalıtıyor; sınıflar uygulanmıyordu.
  - Boş satırlar silinir: Markdown boş satırda HTML bloğunu keser.
  - `<div lang="tr">` sarmalayıcısı CSS büyük harf dönüşümünü Türkçe yapar: "ipucu" → "İPUCU" (İngilizce kuralla "IPUCU" olurdu).
- [`esc(s)`](../src/ui/style.py#L468): HTML kaçışı (`<` → `&lt;`). Metinde `<` geçerse sayfa bozulmasın, betik enjeksiyonu olmasın.
- [`header(kicker, title, lead, hero_word)`](../src/ui/style.py#L472): sayfa başlığı.
- [`pill(label)`](../src/ui/style.py#L493): "Doğrulandı / İncelenmeli / Reddedildi" rozeti.
- [`card(...)`](../src/ui/style.py#L498): kullanılmıyor.
- [`flow(steps)`](../src/ui/style.py#L503): akış şeması (Rapor → Nasıl çalışır).

---

## `src/ui/data.py` — arayüzün veri katmanı (318 satır)

**Ne işe yarar?** Arayüzün okuduğu her şey buradan geçer: parçalar, bölümler, belgeler, soru setleri, kararlar, kota, ölçüm sonuçları. Yalnızca yerel dosyalar okunur, API çağrısı yoktur. Çoğu fonksiyon `st.cache_data` ile kısa süreli önbelleklenir. Belge işleme işini başlatma ve izleme de buradadır.

**Bağlantılar**
- ← bütün sayfalar, `components`, `quiz`, `parts`.
- → `review_store`, `config`, `topics`, `generate`, `request`, `ledger`.

**İçindekiler**
- [`chunks()`](../src/ui/data.py#L27), [`sections()`](../src/ui/data.py#L32), [`parsed(stem)`](../src/ui/data.py#L37): veri dosyalarını okur (20 sn önbellek).
- [`short(doc)`](../src/ui/data.py#L42): belgenin görünen adı, belge kaydından ([`library.display_name`](../src/library.py#L299); sahibi değiştirebilir).
- **Kişi ve görünürlük (bölüm 11):**
  - [`user()`](../src/ui/data.py#L50), [`uid()`](../src/ui/data.py#L55): giriş yapmış kişi `{id, name, username}` ve kimliği (`auth.py` `session_state.user`'a koyar).
  - [`_visible(user_id)`](../src/ui/data.py#L61): kişinin görebildiği belgeler (10 sn önbellek). Önce `library.sync()` çalışır: elle konan PDF'ler ve girişten önceki belgeler de kayda girer.
  - [`visible()`](../src/ui/data.py#L67): giriş yapan kişi için `_visible`. Belge gösteren her sayfa bununla süzer.
  - [`doc_meta()`](../src/ui/data.py#L74): belge kaydı `{doc: {name, owner, public, …}}` (Belgeler sayfasındaki rozet ve düğmeler).
  - [`my_documents()`](../src/ui/data.py#L80): `documents()`'ın görünür olanları.
- **Ana sayfa ve profil (bölüm 12):** [`mine()`](../src/ui/data.py#L91) (kişinin kendi listesi), [`items()`](../src/ui/data.py#L97) (bütün sorular, 30 sn önbellek), [`mastery()`](../src/ui/data.py#L120) (beyin analizi), [`home_stats()`](../src/ui/data.py#L137) ve [`due_cards()`](../src/ui/data.py#L142) (selam satırındaki sayı hapları, bugünün tekrarı), [`avatar_b64(user_id)`](../src/ui/data.py#L148) (profil resmi; değişince `.clear()`). `mastery()` ve `home_stats()` / `due_cards()` kendi işlerini 20 sn önbellekli iç işçilere bırakır: [`_mastery(user_id, docs)`](../src/ui/data.py#L115) `mastery.for_user`'ı çağırır; [`_home(user_id, docs)`](../src/ui/data.py#L126) kart havuzundan ve kişinin kart geçmişinden iki şey çıkarır: sayı hapları (`[(not sayısı, "not"), (hazır soru, "hazır soru"), (kart, "kart")]`) ve zamanı gelen kartların kimlikleri. İkisinin anahtarı (kişi kimliği, görünür belge kümesi) olduğu için biri başka birinin verisini görmez.
- **Hazır soru sayısı (bölüm 13):** [`ready()`](../src/ui/data.py#L104): not → doğrulanmış, reddedilmemiş, hatalı bildirilmemiş soru sayısı (sınavlar ve kartlar bunlardan kurulur). Kişiye gösterilen sayı bu; `documents()`'teki `verified` deney (pilot) setlerini de sayar.
- [`topics(doc)`](../src/ui/data.py#L158): konu haritası, `build_missing=False` ile. Arayüz konu haritası için LLM'e gitmez.
- [`has_math(doc)`](../src/ui/data.py#L165): belgede formüllü birim var mı? Varsa Sınav Hazırla'da "Hesap sorusu" tipi gösterilir.
- [`item_stats()`](../src/ui/data.py#L175), [`reports()`](../src/ui/data.py#L181): `request` modülündekilerin önbellekli hali.
- [`set_label(name, kind)`](../src/ui/data.py#L186): dosya adından okunur set adı (`'qwen_..._english_tr'` → `'Genetic Algorithms → TR · qwen3.8-27b (pilot)'`).
- [`doc_of(item)`](../src/ui/data.py#L202): sorunun belgesi (ilk parça kimliğinden).
- [`question_sets()`](../src/ui/data.py#L208): bütün soru setleri `[{key, name, kind ('belge'|'pilot'), items}]`. Her soruya `doc`, `set`, `set_kind` eklenir.
- [`all_questions(include_pilot)`](../src/ui/data.py#L222): setlerdeki soruların kimliğe göre tekilleştirilmiş listesi.
- [`decisions()`](../src/ui/data.py#L234): inceleme kararları (önbelleksiz; karar verilince hemen görünsün).
- [`documents()`](../src/ui/data.py#L239): her PDF için özet. Sayfa sayısı, görselden okunan ve bekleyen sayfa, tablo sayfası, parça / bölüm / soru / doğrulanmış soru sayısı. **Bütün** belgeler; sayfalar `my_documents()` kullanır (Rapor ve Modeller ve Kota'daki sistem toplamları hariç: içerik göstermezler).
- [`eval_json(name)`](../src/ui/data.py#L264): `eval/<ad>.json` ölçüm sonucu.
- [`quota()`](../src/ui/data.py#L269): `ledger.report()`.
- **Arka plan işleri:**
  - [`start_job(pdf_name, language)`](../src/ui/data.py#L279): `python -m src.pipeline "<pdf>"`'i bağımsız süreçte başlatır. Çıktı `data/jobs/<belge>.log`'a, başlangıç zamanı `.json`'a yazılır.
  - [`job_status(stem)`](../src/ui/data.py#L295): log dosyasını okuyup durumu çıkarır. `STEP_RE` `"3/6 bölümleme"` satırlarını yakalar; "Bitti" görünce iş bitti, "Traceback" görünce hata, "⏳" görünce kota beklemesi sayılır.
  - [`jobs()`](../src/ui/data.py#L314): bütün işler, en yeni önce.

  Ayrı süreç ile arayüz arasındaki "iletişim" bu log dosyasıdır.

---

## `src/ui/components.py` — ortak soru kartı ve bitiş özeti (187 satır)

**Ne işe yarar?** İki ortak HTML parçası üretir:
- Bir soruyu "basılı sınav kâğıdı" görünümünde gösteren kart. İnceleme sayfası ve sınav sonuç ekranı aynı kartı kullanır.
- Bitiş özeti: kart oturumunun ve sınav sonucunun "nerede zorlandım?" kartı.

**Bağlantılar**
- ← `quiz`, `pages/review`, `pages/bank`, `pages/cards`.
- → `style`, `data`, `textnorm.pretty_math`, `grading.safe_value`.

**İçindekiler**
- [`t(x)`](../src/ui/components.py#L16): ekranda gösterilecek metin. `pretty_math` + HTML kaçışı. Saklanan veri değişmez.
- [`expected(q)`](../src/ui/components.py#L22): beklenen cevap. Hesaplanmamış bir formülse değerini de gösterir (`9!/(3!·2!) = 30240`, `C(n, 2)·2 = n·(n − 1)`); öğrenci sayıyı yazabileceğini görsün.
- [`type_label(q)`](../src/ui/components.py#L38): "Hesap sorusu" ya da tipin Türkçe adı.
- [`_options(q, reveal, chosen)`](../src/ui/components.py#L42): şıklar. `reveal` ise doğru şık yeşil, öğrencinin yanlış seçimi kırmızı. Yanlış seçilen şıkkın notu varsa "Bu şıkkı seçtiysen: …" yazar. Kısa cevapta "Senin cevabın / Beklenen cevap" kutusu.
- [`question_card(item, number, reveal, chosen, verdict, options)`](../src/ui/components.py#L72): kartın tamamı. Başlık (SORU N + tip + zorluk), soru, şıklar; `reveal` ise çözüm adımları, kaynak (belge + sayfa + sarı vurgulu alıntı) ve sistemin kararı.
- [`page_card(item, png, note, reveal)`](../src/ui/components.py#L175): kaynak sayfa kartı. Kanıtın sarıyla işaretlendiği sayfa görüntüsü base64 olarak `<img>` içine gömülür.

**Bitiş özeti.** Grafik ilkeleri: tek soru sorulur ("nerede zorlandım?"), her grup için tek oran (isabet) ince bir ölçer çubuğuyla gösterilir. Tek seri olduğu için tek renk (`#3A7BB8`) ve lejant yok. Her değer yazıyla da yazılır; renk tek başına anlam taşımaz. Durum renkleri (doğru yeşil, yanlış kırmızı, boş gri) yalnızca etiketli kutucuklarda.
- `STATUS_DOT`: durum etiketi → renk. Sınavın "Doğru / Yanlış / Boş"u ile kartın "Bildim / Bilemedim / Atladım"ı aynı renkleri paylaşır.
- `DIFF_ORDER`: ölçerlerin sırası (Kolay, Orta, Zor).
- [`_rate(counts, skip_neutral)`](../src/ui/components.py#L105): (bilinen, payda). Kartta atlanan kart paydaya girmez (değerlendirilmedi); sınavda boş soru yanlış sayılır.
- [`_group(records, key, labels)`](../src/ui/components.py#L110): kayıtları bir alana göre (zorluk, tip, konu) gruplayıp durum sayılarını toplar.
- [`_detail`](../src/ui/components.py#L117): fareyle üstüne gelince görünen ayrıntı metni ("Orta — Doğru: 3 · Yanlış: 1 · Boş: 0").
- [`_meter(name, counts, labels, skip_neutral)`](../src/ui/components.py#L121): bir ölçer (ad, yüzde, çubuk, "3 / 4"). O turda o gruptan soru yoksa "bu turda yok".
- [`_topic_row`](../src/ui/components.py#L133): konu satırı. Yüzde %50'nin altındaysa "↻ tekrar et" işareti.
- [`summary_html(records, labels, title, note, hero_label, hero_sub, extra_tile, by_type, skip_neutral, topics_shown)`](../src/ui/components.py#L142): özetin tamamı. `records` her soru için `{"status", "diff", "type", "topic"}`.
  1. Başlık, not, büyük yüzde ve durum kutucukları (+ süre kutusu).
  2. "Zorluğa göre" ölçerleri (her zaman üçü de).
  3. `by_type` ise "Soru tipine göre" (yalnızca sınavda).
  4. "Konulara göre" satırları, en çok zorlanılan önce. İlk 6'dan fazlası "+ N konu daha" altında katlanır.

---

## `src/ui/quiz.py` — sınav çözme deneyimi (402 satır)

**Ne işe yarar?** Sınav Hazırla sayfasında sınav hazır olunca üç ekranı yönetir:
1. **Başlangıç ekranı:** özet, tahmini süre, kısayollar, şeffaflık notu (`TRANSPARENCY`: sorular yapay zekâyla üretildi, kaynağa bağlandı, başka modelle doğrulandı).
2. **Odak modu:** kenar çubuğu gizli; tek soru, büyük şık düğmeleri, ilerleme çubuğu, süre sayacı, soru haritası, kademeli ipucu, klavye kısayolları.
3. **Sonuç ekranı:** ortak bitiş özeti (`components.summary_html`), gözden geçirme, hatalı bildir ve itiraz, "Kartla çalış".

**Bağlantılar**
- ← `pages/exam`.
- → `request` (`record_attempt`, `report`), `grading.grade_short`, `components`, `data`, `style`; "Kartla çalış" → `pages/cards`.

**Durum: `st.session_state.exam` sözlüğü** (sınavın bütün hafızası)

| Alan | Anlamı |
|---|---|
| `id` | İstek kimliği |
| `phase` | `"start"` / `"solve"` / `"results"` |
| `cur` | Şu anki sorunun sırası |
| `answers` | Soru kimliği → cevap (şık sırası, `"true"`/`"false"` ya da metin) |
| `started`, `finished` | Zaman damgaları (süre için) |
| `hints` | Soru kimliği → kullanılan ipucu sayısı |
| `hint_flash` | Az önce ipucu açılan soru (animasyon + kaydırma) |
| `submitted`, `recorded` | Bitirildi mi, çözüm kaydedildi mi (iki kez kaydedilmesin) |
| `retry` | İkinci denemede yalnızca yanlış soruların kimlikleri |
| `overrides` | İtirazla doğru sayılan sorular |

**Ortak fonksiyonlar**
- [`grade(it, ans)`](../src/ui/quiz.py#L29): cevap doğru mu? ÇS'de şık sırası, D/Y'de değer, kısa cevapta `grade_short`.
- [`topic_of(req, it)`](../src/ui/quiz.py#L43): sorunun konusu. Kanıt sayfası, aramanın hangi konu için bulduğu sayfalar arasındaysa o konu.
- [`view(items)`](../src/ui/quiz.py#L52): ikinci denemede yalnızca yanlışlar.
- [`_answered(ans)`](../src/ui/quiz.py#L74): cevap verilmiş mi? `None` ve yalnızca boşluktan oluşan metin cevap sayılmaz (yanıtlanan sayısı, soru haritasındaki ✓ ve boş bırakılan soruların sayımı bununla yapılır). [`_fmt_time(sec)`](../src/ui/quiz.py#L78): saniyeyi `dk:sn` (`mm:ss`) biçimine çevirir (negatifse 0); süre sayacında ve sonuç özetindeki "Süre" kutusunda.
- [`hints(req, it)`](../src/ui/quiz.py#L58): **kademeli (Sokratik) ipuçları.** 1) Nereye bakmalı (konu + sayfa). 2) Kaynak cümle ya da uygulanacak kural. 3) Hesapta çözümün ilk adımı.

**1. Başlangıç:** [`start_screen(req, items)`](../src/ui/quiz.py#L85): özet kutusu ve "Sınava başla" düğmesi. Düğme fazı `"solve"` yapar.

**2. Odak modu:** [`solve(req, items)`](../src/ui/quiz.py#L192)
- `_FOCUS_CSS` kenar çubuğunu gizler ve içeriği daraltır.
- Üst şerit: ilerleme, süre sayacı, "Çık" düğmesi.
- Soru haritası (`st.pills`): numaraya tıklayıp soruya atlanır, cevaplananlarda ✓.
- Soru kartı ve cevap alanı:
  - Kartın üstünde soru başına değişen ince renkli şerit (`style.color(cur)`).
  - Kartın sarmalayıcısı her soruda `div` ↔ `section` arasında değişir: tarayıcı kartı sıfırdan çizer, geçiş animasyonu her soruda oynar (React aynı etiketli öğeyi yeniden kullanıyordu).
  - ÇS: dört büyük düğme. Şık harfi renkli rozet (`LETTER_COLORS`: mavi, turuncu, mor, gri); yeşil ve kırmızı bilerek yok, doğru/yanlış ipucu sanılmasın.
  - D/Y: iki düğme.
  - Kısa cevap: giriş kutusu + yazım yardımı.

  Cevap alanı tipten bağımsız **sabit yükseklikte**; gezinme düğmeleri yer değiştirmez.
- Açılmış ipuçları; yeni açılan parlayarak gelir.
- Gezinme: Önceki / İpucu al / Sonraki ya da Sınavı bitir. Boş soru varsa onay penceresi açılır.
- Geri çağırmalar:
  - [`_pick`](../src/ui/quiz.py#L113): şık seçimi.
  - [`_sync_text`](../src/ui/quiz.py#L118): kısa cevabı `answers`'a kopyalar.
  - [`_go`](../src/ui/quiz.py#L124): soru değiştirir.
  - [`_hint`](../src/ui/quiz.py#L131): ipucu sayısını artırır.
  - [`_jump`](../src/ui/quiz.py#L137): haritadan atlar.
  - [`_finish`](../src/ui/quiz.py#L142): sonuca geçer.
- [`_confirm_finish`](../src/ui/quiz.py#L148) (`@st.dialog`): "N soru boş, yine de bitir?" penceresi.
- [`_keys_and_scroll(started, flash)`](../src/ui/quiz.py#L159): tarayıcıda çalışan küçük bir JavaScript (`st.iframe` içinde). İki işi var:
  - Süre sayacını her saniye günceller; sunucuya istek atmaz.
  - Klavye kısayollarını kurar: A–D şık, ← → soru, H ipucu. Basılan tuş, CSS sınıfıyla bulunan düğmeye `click()` yaptırır.

  İçerik yalnızca yeni ipucu açılınca değişir; böylece Streamlit çerçeveyi her tıklamada yeniden yüklemez ve sayaç titremez.

**3. Sonuç:** [`results(req, items)`](../src/ui/quiz.py#L313)
1. Her soruyu puanla. İlk kez geliniyorsa `record_attempt` ile, giriş yapan kişinin kimliğiyle kaydet (madde analizi); `recorded=True` yap. "Baştan çöz" yeniden kaydeder ama ölçüme yalnızca kişinin ilk çözümü girer (bölüm 10).
2. Doğru / yanlış / boş sayıları (itirazlar doğru sayılır).
3. Özet: her soru için `{durum, zorluk, tip, konu}` kaydı → `components.summary_html` (sınavda soru tipine göre ölçer de var).
   - [`_message`](../src/ui/quiz.py#L291): yüzdeye göre başlık ve not.
   - Süre kutusu; ipucu kullanıldıysa sayısı.
   - Zorluk sütunu etkin düzeydir (ölçülmüş), üretecin iddiası değil.
4. Düğmeler:
   - "Yanlışları tekrar çöz": [`restart`](../src/ui/quiz.py#L301) `retry` ile yeni deneme açar.
   - "Kartla çalış": yanlış ve boş soruları `st.session_state.cards_preset`'e koyup Bilgi Kartları sayfasına geçer. Orada yalnızca şıksız anlaşılan sorular karta dönüşür.
   - "Baştan çöz" ve "Yeni sınav".
5. Gözden geçirme ("Yanlış ve boşlar / Tümü / Doğrular" süzgeci): her soru kartıyla, ardından:
   - "Hatalı bildir": `request.report`; soru inceleme bitene kadar sınavlardan çıkar.
   - Kısa cevapta "Cevabım doğruydu" itirazı: puana yansır, soru İnceleme sayfasına düşer.

---

## `src/cards.py` — bilgi kartı mantığı (185 satır)

**Ne işe yarar?** NotebookLM'deki gibi bilgi kartları: önde soru, arkada cevap. Kartlar havuzdaki **doğrulanmış** sorulardan yapılır; LLM çağrısı yoktur, kota harcamaz. Bu dosyada Streamlit yok (test edilebilsin diye); ekran `pages/cards.py`'de.

**Hangi soru kart olur?** Kartta şık yok. Bu yüzden yalnızca şıksız da anlaşılan sorular:
- kısa cevap soruları;
- kökü kendi başına soru olan çoktan seçmeliler (arka yüzde cevap = doğru şıkkın metni).

Doğru / yanlış ifadeleri, "aşağıdakilerden hangisi" ve olumsuz kök ("…değildir") gibi şıklara dayanan sorular sınavda kalır.

**Aralıklı tekrar (FSRS-5; 2026-10-09'a kadar Leitner kutularıydı, bölüm 14).** FSRS (Free Spaced Repetition Scheduler; Anki 23.10'dan beri varsayılan) her kartın iki sayısını tutar: **kararlılık S** (gün; hatırlama olasılığının %90'a düşmesine kadar geçen süre) ve **zorluk D** (1-10).
- Bildim → S büyür; ne kadar büyüyeceği kartın D'sine, mevcut S'ye ve "unutmaya ne kadar yakındı"ya bağlıdır (geç tekrar edilip yine de bilinen kart daha çok büyür). Bilemedim → S küçülür, kart **bugün yine** gelir, D artar. Atla → hiçbir şey değişmez.
- Sonraki tekrar: hatırlama olasılığı %90'a indiğinde (`RETENTION`, bu değerde aralık S gündür, en çok 365). İlk değerlendirmede S, FSRS-5'in 4 başlangıç sayısından gelir (`W[0..3]`; Bilemedim 0,4 gün, Bildim 3,2 gün).
- Parametreler (`W`, 19 sayı) FSRS-5'in milyonlarca Anki tekrarından öğrenilmiş **varsayılanlarıdır**; kişiye göre eğitilmedi (bunun için yüzlerce tekrar gerekir). Yalnızca "Tekrar" ve "İyi" notları kullanılır (`GRADE`); "Zor" ve "Kolay" düğmeleri yok.
- Sonuç öğrencinin kendi değerlendirmesidir. Sınavın madde istatistiğine (`attempts.jsonl`) karışmaz; ayrı dosyaya yalnızca eklenir: `data/review/cards.jsonl` (soru ve kişi kimliğine bağlı). **Kayıt biçimi Leitner'dan beri değişmedi:** durum bu kayıt baştan oynatılarak bulunur, bu yüzden eski değerlendirmeler de FSRS'le yeniden hesaplanır. Eski kutu sayısı (`box`, 1-5) geriye uyum için S'den türetilir; profilin bellek özeti ve ustalık durumu hâlâ onu kullanır.
- **Durum kişiye özeldir:** herkes aynı kuralla, yalnızca kendi değerlendirmeleriyle ilerler. Kişi alanı olmayan eski satırlar ilk hesabındır (bölüm 11).

**Bağlantılar:** ← `pages/cards`, `difficulty.real_attempts` (`first_seen`), `tests/test_cards`. → `request` (`all_items`, `usable`, `blocked_ids`), `accounts.legacy_owner`, `jsonl`, `config`.

**İçindekiler**
- `LOG` (kayıt dosyası), `RESULTS` (`good`, `bad`, `skip`), `GRADE` (Bilemedim → 1, Bildim → 3), `RETENTION` (0,9), `MAX_DAYS` (365), `W` (FSRS-5 varsayılan parametreleri), `DECAY`/`FACTOR` (unutma eğrisi `R = (1 + FACTOR·t/S)^DECAY`; `R(S, S) = 0,9`).
- `_OPTION_BOUND`: kökü şıklara dayanan soruyu yakalayan düzenli ifade ("aşağıdaki", "seçenek", "şık", "değildir", "which of"…). `\bşık\b`: "yaklaşık" yakalanmasın.
- [`card_ok(q)`](../src/cards.py#L45): soru şıksız bir karta dönüşebilir mi?
- [`_retrievability(elapsed_days, stability)`](../src/cards.py#L54): unutma eğrisi: S ve geçen güne göre şu an hatırlama olasılığı (1'den başlayıp düşer). `pick` sıralamada, `step` S'yi güncellerken kullanır.
- [`_d0(g)`](../src/cards.py#L58), [`_clamp_d(d)`](../src/cards.py#L62): ilk değerlendirmedeki başlangıç zorluğu; zorluğu 1-10 arasında tutar.
- [`interval_days(s)`](../src/cards.py#L66): S kararlılığındaki kart için, hatırlama olasılığı `RETENTION`'a inene kadar geçen gün (en az 1, en çok `MAX_DAYS`; `RETENTION` 0,9 iken tam S).
- [`_box(state)`](../src/cards.py#L71): geriye uyum için eski 1-5 kutu: S ≥ 1, 3, 7, 21 gün eşikleriyle yükselir; son değerlendirme Bilemedim ise 1.
- [`step(state, result, t)`](../src/cards.py#L81): bir değerlendirmeden sonra kartın yeni durumu `{s, d, last, seen, good, bad, lapsed, box}`. Saf fonksiyon (dosyaya dokunmaz). İlk değerlendirmede S, `W`'den gelir; sonrasında geçen süre bir günden kısaysa FSRS-5'in gün içi formülü, değilse hatırlama olasılığına bağlı büyüme (Bildim) ya da küçülme (Bilemedim) uygulanır; D değişir ve ortalamaya doğru çekilir.
- [`_mine(rows, user)`](../src/cards.py#L107): yalnızca o kişinin satırları (`user` verilmezse hepsi).
- [`history(path, user)`](../src/cards.py#L116): kayıt dosyasını baştan oynatır → kart kimliği → durum. Sayfa `user=` ile çağırır: kişinin kendi durumları.
- [`first_seen(path)`](../src/cards.py#L124): (kişi, soru) → kartta ilk değerlendirildiği an. Kartta cevabı görülmüş soru sonra sınavda çıkarsa o deneme "taze" sayılmaz (bölüm 10). "Atla" sayılmaz: cevap görülmemiş olabilir.
- [`record(qid, result, path, user)`](../src/cards.py#L135): bir değerlendirmeyi kişiyle birlikte dosyaya ekler. `path` çağrı anında okunur; testler geçici dosyaya yönlendirebilsin.
- [`gap_days(state)`](../src/cards.py#L143): değerlendirilmiş kartın sonraki tekrarına kaç gün var: son değerlendirme Bilemedim ise 0 (bugün yine), değilse `interval_days(S)`.
- [`is_due(state, now)`](../src/cards.py#L148): hiç görülmemiş ya da son değerlendirmeden `gap_days` kadar gün geçmiş kart.
- [`next_gap(state, result)`](../src/cards.py#L153): bu sonuçtan sonra kart kaç gün sonra gelir (ekrandaki "Bildim → 3 gün sonra yeniden" ipucu).
- [`pick(items, hist, n, now, only_due, seed)`](../src/cards.py#L158): deste. Önce zamanı gelmiş tekrar kartları (**unutulmaya en yakın önce**, yani hatırlama olasılığı en düşük; Bilemedim'liler en başta), sonra hiç görülmemişler; eşitlerde karışık.
- [`pool(docs)`](../src/cards.py#L174): seçili belgelerdeki kart olabilen sorular. Sınavla aynı kural: doğrulanmış, reddedilmemiş, bildirilmemiş.
- [`summary(items, hist, now)`](../src/cards.py#L182): kurulum ekranındaki sayılar (toplam, yeni, zamanı gelen, ustalaşılan = kararlılık S ≥ 21 gün).

---

## `src/ui/pages/cards.py` — Bilgi Kartları (269 satır)

**Ne işe yarar?** Üç ekran:
1. **Seçim:** belgeler, kart sayısı, "yalnızca zamanı gelenler" anahtarı; dört sayı kutusu (kart, tekrar zamanı gelen, hiç görmediğin, ustalaştığın).
2. **Oturum:** tam pencere koyu sahne; ekranın kendisi ayrı bir bileşen (`flashcards.py`, aşağıda). Bu sayfa yalnızca bileşenin bildirdiği durumu oturuma işler ve yeni değerlendirmeleri kaydeder.
3. **Özet:** ortak bitiş özeti (`components.summary_html`): isabet, zorluğa ve konulara göre; "Bilemediklerimi çalış" ve "Yeni oturum".

**Neden ekran ayrı bileşen? (kullanıcı isteği 2026-10-12)** Eski ekranda her değerlendirmede bütün sayfa Streamlit'te baştan çalışıyor, kart sahnesi HTML olarak sıfırdan kuruluyordu: sunucuya gidip gelme ve yeniden yerleşim her geçişte "kasma" olarak görünüyordu. Üstüne sürekli oynayan animasyonlar (alevin `drop-shadow` süzgeci, kayan çizgiler, sallanan yüzler) her karede yeniden çizim yaptırıyordu. Şimdi bütün deste oturumun başında bir kez tarayıcıya gider; çevirme, geçiş, sürükleme ve karıştırma tarayıcıda anında olur. Python'a yalnızca "şu kart şöyle değerlendirildi" bilgisi gider ve onu da yalnızca oturum parçası (`st.fragment`) işler.

**Veri akışı (bir değerlendirme):**
1. Kişi ← / → basar ya da kartı sürükler. JS kartı yığınına uçurur, sıradakini öne getirir ve `setStateValue("sync", {tok, queue, log, ended})` çağırır. `log` birikimlidir: oturumun bütün değerlendirmeleri.
2. Streamlit yalnızca [`_live()`](../src/ui/pages/cards.py#L208) parçasını yeniden çalıştırır. Parça, bileşeni çağırmadan **önce** `st.session_state["fc_<tok>"]["sync"]`'i okur ve [`_apply`](../src/ui/pages/cards.py#L95)'e verir.
3. `_apply` günlükte oturumun bilmediği satırları bulur ve her birini `cards.record` ile yazar.
4. Bileşen aynı `tok` ile yeniden çağrılır; JS aynı oturum olduğunu görür ve yeniden çizmez.

**Durum: `st.session_state.cards`**

| Alan | Anlamı |
|---|---|
| `queue` | Destedeki soru kimlikleri. Atlanan kart sona bir kez eklenir (ikinci kez atlanırsa bir sonraki oturuma kalır); karıştırma kalan kısmın sırasını değiştirir |
| `pos` | Değerlendirilen kart sayısı (= `len(log)`); açık kart `queue[pos]` |
| `log` | `[[kimlik, sonuç], …]`; `log[i]` her zaman `queue[i]`'nin sonucu |
| `res`, `skipped` | Kimlik → son sonuç (özet ve ana sayfadaki "kaldığın yerden" kartı bunu okur); atlananlar |
| `streak`, `best`, `miss` | Üst üste "Bildim" serisi, en uzunu, üst üste "Bilemedim" |
| `started`, `ended` | Süre ve "Bitir" |
| `tok` | Oturum belirteci (rastgele 8 hane). Yeni oturumda değişir; bileşenin anahtarı `fc_<tok>`. Bileşen eski oturumun durumunu gönderirse yok sayılır |

**İçindekiler**
- Sabitler: `PILE` (sonuç → özetteki adı), `SESSION_CSS` (oturum sayfası: kenar çubuğu ve Streamlit'in üst şeridi gizli, zemin bileşenle aynı koyu renk; bileşen yüklenirken beyaz parlamasın), `VIVID` (altı canlı kart paleti: açık, koyu, yazı, vurgu; yazı her zeminde ≥ 6:1 kontrast; bileşene gönderilir).
- [`_items()`](../src/ui/pages/cards.py#L44): bütün sorular (30 sn önbellek).
- [`_topic(it)`](../src/ui/pages/cards.py#L48): kartın konusu. Bölüm adı yalnızca numaraysa ("01") belge adıyla birlikte.
- [`_remember()`](../src/ui/pages/cards.py#L56): "kaldığın yerden devam et" (`src/resume.py`, bölüm 12): yarım oturum kişiye kaydedilir; oturum bitince silinir.
- [`_begin(ids)`](../src/ui/pages/cards.py#L65): yeni oturum durumu (yeni `tok`). [`_only_bad`](../src/ui/pages/cards.py#L71): yalnızca bilinemeyenlerle yeni tur. [`_new`](../src/ui/pages/cards.py#L77): seçime dön.
- [`_norm(cs, items)`](../src/ui/pages/cards.py#L82): kayıtlı ya da eski biçimli oturumu bu ekranın biçimine getirir. `tok` yoksa verir ve kalan sıradan havuzdan çıkmış soruları ayıklar. `log` yoksa ya da eski biçimdeyse (`[sonuç, yüz]`, 2026-10-09 ekranı) `queue` ve `res`'ten yeniden kurar. **Bulgu (düzeldi, 2026-10-12):** hiç kart değerlendirilmemiş kayıtlı oturumda (`pos` 0) `log` oluşturulmuyordu → "kaldığın yerden" açılınca `KeyError`.
- [`_apply(cs, state)`](../src/ui/pages/cards.py#L95): bileşenin durumu → oturum. Belirteç tutmuyorsa, tanımadığı kart varsa ya da günlük kısalmışsa hiçbir şey yapmaz. Yeni satırlar önce oturumun günlüğüne eklenir, sonra yazılır. Aynı durum ikinci kez gelirse (parça yeniden çalışınca) yeni satır kalmadığı için bir şey yazılmaz.
- [`_view(it, hist, now)`](../src/ui/pages/cards.py#L127): bir kartın görünümü (metinler HTML'e kaçışlı): soru, uzunluk sınıfı (`long`, `xlong`: uzun soruda yazı küçülür), zorluk, konu, cevap (çoktan seçmelide doğru şıkkın metni), çözüm adımları, kanıt cümlesi, belge ve sayfa, kartın daha önce görülüp görülmediği ("Yeni kart" etiketi). `gb` / `gg`: bu karta Bilemedim / Bildim denirse kaç gün sonra yine gelir (`cards.next_gap`; düğmelerin altındaki "bugün yine", "4 gün sonra").
- [`_payload(cs, items)`](../src/ui/pages/cards.py#L141): bileşenin verisi. Kart görünümleri oturum başına bir kez kurulur (`session_state.cards_view`), her değerlendirmede `history` yeniden okunmaz. `flip`: önizleme için ilk kart çevrili.
- [`_counts(cs)`](../src/ui/pages/cards.py#L154): oturumdaki (bildim, bilemedim, atladım) sayıları.
- Ekranlar: [`_setup()`](../src/ui/pages/cards.py#L161), [`_session()`](../src/ui/pages/cards.py#L197), [`_summary()`](../src/ui/pages/cards.py#L229). Seçimde yalnızca görebildiğin belgeler listelenir; sayılar ve deste kişinin kendi kutularından (`history(user=…)`).
- [`_live()`](../src/ui/pages/cards.py#L208) (`@st.fragment`): yukarıdaki veri akışı. Oturum bittiyse (`ended` ya da kart kalmadı) bütün sayfayı yeniler (özet). Bileşenin tetikleri: `"leave"` (Ara ver: oturum kaydedilir, ana sayfaya dönülür; "kaldığın yerden devam et" geri getirir ve aradaki süre sayılmaz, `resume.restore_cards`), `"src|kimlik"` (kanıt sayfası okuyucuda; okuyucu kapanınca bileşen durumu Python'dan kurar, aynı karta dönülür).
- [`render()`](../src/ui/pages/cards.py#L251): okuyucu açıksa okuyucu; sınavdan `cards_preset` geldiyse o sorularla oturum açar (hiçbiri karta dönüşmüyorsa bildirim gösterir); oturum varsa oturum, yoksa seçim ekranı.

---

## `src/ui/flashcards.py` — kart oturumu ekranı (Streamlit özel bileşeni, 622 satır)

**Ne işe yarar?** Bilgi kartı oturumunun bütün ekranı: tam pencere, koyu bir sahne (düz parlak zemin yerine; kullanıcı isteği 2026-10-12). Yerleşim Quizlet'in kart modundan: kart ortada, solunda "Bilemediklerin", sağında "Bildiklerin" yığını.

```
[‹] Bilgi kartları · <not adları>   [▬▬▬▬ 6 / 20 kart]   (◔ %80 isabet) (alev 3 seri) (4:12 süre) [Karıştır] [Bitir]
┌ Bilemediklerin ┐   ┌──────────────── kart ─────────────────┐   ┌ Bildiklerin ┐
│ 2   yığın      │   │ Orta · konu · Yeni kart   [Notta aç]  │   │ 4   yığın   │
│ son 3 kartın   │   │            soru (Fraunces)            │   │ son kartlar │
│ soruları       │   └───────────────────────────────────────┘   │             │
└────────────────┘   [✕ Bilemedim: bugün yine][↷ Atla][✓ Bildim: 4 gün sonra]
                      Boşluk çevir · ← bilemedim · ↓ atla · → bildim · K karıştır
```

- **Kart:** önde soru, zorluk, konu, "Yeni kart" etiketi ve "Notta aç · s. N" (kanıt sayfası okuyucuda, kanıt cümlesi işaretli). Arkada soru (soluk), cevap, çözüm adımları, notundaki kaynak cümle sarı vurguyla. Tıkla, Boşluk ya da Enter → 3B döner.
- **Değerlendirme:** düğmeler, ← ↓ → (ya da 1 2 3) ya da kartı sola / sağa sürüklemek. Sürüklerken kartın köşesinde "BİLDİM" / "BİLEMEDİM" damgası belirir; 120 px'ten az sürüklenip bırakılırsa kart yerine yaylanarak döner, hiç sürüklenmezse tıklama sayılır (çevirir). Kart kendi yığınına uçar (atlanan aşağı kayıp kaybolur, destenin sonunda yine gelir); arkadaki kart öne kayar.
- **Üst şerit:** kart başına bir parça (bildiklerin yeşil, bilemediklerin kırmızı, atladıkların gri, açık kart beyaz), isabet halkası (atlananlar sayılmaz; %70+ yeşil, %40+ sarı, altı kırmızı), seri (1-4 turuncu, 5+ koyu turuncu alev; artınca sayı bir kez zıplar), süre.
- **Yan paneller:** sayı, açıklama ("Bunlar bugün yine gelecek", "En yakın tekrarı 3 gün sonra"), yığın (değerlendirilen kartın renginde küçük kart; en çok 13 tanesi görünür, yığın her kartla biraz yükselir) ve son üç kartın sorusu. Paneller kartla aynı boyda ve sabit (içerik geldikçe büyüyüp zıplamaz). Dar ekranda (< 1180 px) paneller gizlenir, sayılar düğmelerin köşesine geçer.

**Neden akıcı?** Bütün hareketler yalnızca `transform` ve `opacity` (ekran kartında, ekranın yenileme hızında çizilir); sürekli dönen animasyon yok (boşta GPU ve ana iş parçacığı neredeyse hiç çalışmıyor). Sürükleme `requestAnimationFrame` ile kare başına bir kez güncellenir. Uçuş Web Animations API ile (`el.animate`). Açık kart ve arkasındaki üç kart (`s0`-`s3`) sınıf değişince geçişle yer değiştirir. "Hareketi azalt" tercihinde uçuş, dönüş ve geçişler kapanır.

**İkinci tur (2026-10-13, kullanıcı: "Edge'de hâlâ hafif kasıyor").** Görünmez Edge'de ölçüldü (CDP izleme; geçici kayıtlı önizleme sunucusunda 6-10 değerlendirme). Kareler arası boşluk `requestAnimationFrame` ile ölçüldü; işlemci 4 kat yavaşlatılınca (pildeki dizüstünü taklit) eski sürümde en uzun takılma **79 ms** (~5 kare), 40 ms'yi aşan 3-4 takılma vardı. Yeni sürümde en uzun takılma 18-30 ms, 40 ms'yi aşan yok; normal hızda 36 ms → 12 ms. Yapılanlar:
- **Tuşa basılan karede yerleşim yok.** Sıradaki kartın sıradakisi (`s4`, görünmez) hareket bitince boşta eklenir. Geçişte kartlar yalnızca sınıf değiştirir. Uçuş için kartın ve yığınların yeri de boşta ölçülür (`measure`) ve pencere boyu değişince yenilenir. Eskiden bu iki iş tuş karesinde 3-14 ms tutuyordu. Ölçülen yerle sürüklenip bırakılan kart da tam yığına iner (eskiden sürükleme kadar kayık iniyordu).
- **Python'a haber hareket bitince gider** (`sync(…, 700)`). Streamlit'in yeniden çalışıp veriyi işlemesi kart uçarken ana iş parçacığını meşgul etmez. Art arda değerlendirmeler tek haberde birleşir. "Notta aç" ve "Ara ver" bekleyen haberi önce gönderir (`flush`).
- **Paneller sonra.** Yan panellerin açıklaması ve son kartları hareket bitince yazılır; sayılar hemen yazılır.
- **GPU yükü azaldı.** Ölçümde geçiş sırasındaki GPU işinin ~üçte biri iki kalemdendi: zemindeki nokta deseninin tam ekran maskesi ve kartın arkasında renk değiştiren ışık. İkisi kalktı; desen maskesiz olarak zeminin kendisinde. Ön yüzde `overflow: hidden` (dönen katmanda yuvarlak köşe maskesi) yok, gölgeler küçüldü.
- **Ufak işler:** düğme ve seri "zıplaması" sınıf söküp takmak (zorunlu yerleşim) yerine Web Animations ile. `.fx`'te `contain: strict`.
- **Ölçülemeyen:** görünmez Edge yazılımsal GPU kullanır; gerçek ekran kartındaki çizim ve Edge ayarları (donanım hızlandırma, verimlilik modu) burada görülemez.

**Bağlantılar:** ← `pages/cards.py` (`deck`). → `shelf.Component` (CCv2 kaydı).

**İçindekiler**
- `_CSS`: bileşenin stili (Shadow DOM'da: sayfanın CSS'i içeri girmez, yazı tipleri girer). Renkler `.fx` üzerinde değişken (`--good`, `--bad`, `--panel`…). Dikkat: `.deck`'teki `perspective` ayrı bir katman açar; deste `z-index: 2` ile panellerin üstünde durur, yoksa sürüklenen kart sağdaki yığının altında kalıyordu. `@starting-style` kuralı `.card.s0`-`.card.s3` özgüllüğünde: yalnızca `.card` yazılırsa yuva kuralları onu ezer. Geri düğmesinin sınıfı `.leave`: `.back` kartın arka yüzüyle çakıştı (düğme ayna gibi dönmüştü).
- `_HTML`: tek sarmalayıcı (`.fx`); içini JS kurar.
- `_JS`: JavaScript (Python dizgisi içinde; satır bağlantısı yok). Başlıca işlevler:
  - `frame(S)`: ekranın iskeleti (şerit, paneller, deste, düğmeler, kısayollar).
  - `cardEl(S, k)`: sıradaki k. kartın öğesi (iki yüz + iki damga). Anahtar sıra numarası: atlanan soru sırada iki kez bulunabilir.
  - `layout(root, S)`: açık kart ve arkasındaki üç kart (`s0`-`s3`) + görünmez `s4`; eksik kart (açılışta, karıştırınca) eklenir ve girişini `@starting-style` oynatır.
  - `settle(root, S)`: hareket bitince (0,65 sn) `s4`'ü ekler, konumları ölçer, panelleri yazar.
  - `measure(root, S)`: destenin ortası ve iki yığının ortası (uçuş için).
  - `stats(S)`, `paint(root, S, bumped)`, `panels(root, S)`: günlükten sayılar; ilerleme, isabet, seri, yığın sayıları (hemen), panellerin açıklaması ve son kartlar (değerlendirmede hareket bitince).
  - `grade(root, S, result)`: değerlendirme. Günlüğe ekler, atlanan kartı (bir kez) sona ekler, `fly` ve `layout`'u çağırır, `sync` ile Python'a bildirir. Son kartta "Deste bitti" yazısı belirir; kart yığına varınca (0,65 sn) `ended` gönderilir.
  - `fly(root, S, el, result, k)`: kartı yığının ortasına, yığındaki kart boyuna küçülterek uçurur; varınca yığına küçük kart ekler (`pileCard`).
  - `flip`, `shuffle` (kalan kartlar karışır, ekrandaki kart değişir; kartlar bir an yana savrulup yeniden dağıtılır), `toast` (kısa bildirim, şeridin altında), `drag` (sürükleme), `sync` / `flush` (Python'a haber: değerlendirmede 0,7 sn sonra, birleştirerek).
  - `init(root, data)`: oturumu veriden kurar (kaldığın yerden ya da okuyucudan dönünce de: yığınlar günlükten yeniden dizilir).
  - Dışa açılan işlev: belirteç (`tok`) değişmedikçe yeniden çizmez; klavye dinleyicisini ve süre sayacını her çağrıda yeniden bağlar, bileşen sayfadan kalkınca söker. Tab ile seçilmiş bir düğmede Boşluk / Enter düğmenin kendi işini yapar.
- [`deck(key, data)`](../src/ui/flashcards.py#L618): bileşeni çizer. Dönen değerin `act`'ı tetik (`"leave"` ya da `"src|kimlik"`); destenin durumu `st.session_state[key]["sync"]`'te.

---

## `src/ui/pages/exam.py` — Sınav Hazırla (207 satır)

**Ne işe yarar?** Sistemin ana sayfası. Önce seçim formu gelir; sınav hazırlanınca durum, sınav ve dışa aktarma gösterilir.

**Bağlantılar:** → `request` (`prepare`, `load`, `items_of`, `start`, `save`, `KINDS`), `quiz`, `export`, `data`, `style`.

**İçindekiler**
- `DIFF`: ekrandaki zorluk adı → kod değeri ("Karışık" → `None`).
- `KINDS`: sınavın soru tipleri. **Şimdilik yalnızca çoktan seçmeli** (kullanıcı kararı 2026-10-12: ilk aşamada çoktan seçmeli + bilgi kartları; doğru / yanlış, kısa cevap ve hesap soruları sonra). `request.py` hepsini desteklemeye devam ediyor; tip seçimi formdan kalktı.
- [`_builder()`](../src/ui/pages/exam.py#L22): seçim formu.
  1. Belgeler (yalnızca görebildiklerin; varsayılan: en çok doğrulanmış sorusu olan).
  2. Konular (konu haritasından; boşsa hepsi).
  3. Zorluk ve sayı (5/10/15/20); altında "Sorular çoktan seçmeli" notu.

  "Sınavı hazırla" düğmesi `R.prepare(...)` çağırır; arama ve havuz eşleştirmesi saniyeler sürer.
- [`_open(req_id)`](../src/ui/pages/exam.py#L61): `session_state.exam`'ı kurar, adres çubuğuna `?sinav=<id>` yazar.
- [`_summary(req)`](../src/ui/pages/exam.py#L68): sınavın özeti ve "Notlarında bulunan kaynak sayfalar" açılır paneli: her konunun aramada bulduğu sayfalar. RAG'in görünür kanıtı budur.
- [`_live(req_id)`](../src/ui/pages/exam.py#L89) (`@st.fragment(run_every=3)`): eksik sorular üretilirken her 3 saniyede istek dosyasını okuyup ilerleme çubuğunu günceller. İş bitince bütün sayfayı yeniler.
- [`_progress_value(text)`](../src/ui/pages/exam.py#L101): `"Doğrulanıyor 3/8"` metninden çubuk değeri.
- [`_status(req, items)`](../src/ui/pages/exam.py#L107): sınava geçilebilir mi?
  - Üretiliyorsa canlı ilerleme.
  - `"partial"` ise "eksik N soruyu üret" (`R.start`) ya da "hazır olanlarla başla".
  - Hiç soru yoksa uyarı.
- [`_export(req, items)`](../src/ui/pages/exam.py#L138): dört indirme düğmesi (sınav kâğıdı, Moodle XML, GIFT, CSV).
- [`render()`](../src/ui/pages/exam.py#L168): sayfanın akışı. Adreste `?sinav=` varsa sınavı açar; ama yalnızca sınavın belgelerinin hepsini görebiliyorsan (bağlantıyı açan herkes kendi hesabıyla çözer; göremiyorsan "not herkese açılırsa bağlantı çalışır" uyarısı). Faz `"solve"` ise yalnızca odak modu gösterilir (başlık yok). Değilse başlık → form ya da özet → durum → sonuç ya da başlangıç ekranı → dışa aktarma.

---

## `src/ui/pages/documents.py` — Belgeler (~100 satır)

**2026-10-08 akşamı baştan yazıldı; ayrıntısı bölüm 13'te.** Kişinin görebildiği bütün notlar, ana sayfadaki desteler gibi kart kart (süzgeç: Tümü / Notlarım / Herkese açık; arama: not adı ya da konu; sıralama; iki görünüm: **Sayfalı** — sayfa kaymaz, 2×4 kart, kalanlar okla yana kayar — ve **Kaydırmalı** — satırlar sayfa kaydıkça gelir). Bir nota tıklayınca ayrıntısı sayfanın üstünde, arkası hafifçe bulanık bir pencerede açılır ([`ui/docview.py`](../src/ui/docview.py)): ad ve görünürlük (gizli / herkese aç, geri alınamaz), konular, sayfalar (tam ekran okuyucu: [`ui/reader.py`](../src/ui/reader.py)), okuma kalitesi. Belge kütüphanesinin (bölüm 11) arayüzü de bu pencerede.

Eski hâlinden farkı: yükleme kutusu ve "çalışan işler" kutusu kalktı (not ekleme ana sayfadaki "+ Yeni not ekle" kartından; işlenen notun kartı canlı ilerleme gösterir, ayrıntısı pencerede), üstteki belge seçici yerine kart ızgarası, konu tablosu yerine tıklanabilir konu listesi (ustalık durumuyla), "Herkese aç" onayı ayrı pencere yerine açılır kutuda (Streamlit pencere içinde pencere açamaz).

**Bağlantılar:** → `docview` (kart, tıklama, pencere, okuyucu), `shelf`, `data` (`my_documents`, `documents`, `doc_meta`, `mine`, `jobs`, `mastery`, `topics`, `ready`, `short`), `style`.

---

## `src/ui/pages/bank.py` — Soru Bankası (88 satır)

**Ne işe yarar?** Bütün sorular süzülebilir bir tabloda. Tabloda öğrenci başarısı (madde güçlüğü) ve inceleme durumu da var; buradan dışa aktarılabilir.

**Bağlantılar:** → `data`, `request` (`KINDS`, `kind`), `components` (`TYPE_TR`, `DIFF_TR`, `type_label`), `export`, `textnorm.pretty_math`.

- [`render()`](../src/ui/pages/bank.py#L14):
  - Yalnızca görebildiğin belgelerin soruları.
  - "Gelişmiş" anahtarları: pilot setleri göster, doğrulanamayanları göster.
  - Süzgeçler: belge, tip, zorluk, metin arama.
  - `st.dataframe` tablosu: "Öğrenci başarısı" ilerleme çubuğu olarak; "Çözen kişi" her kişinin yalnızca ilk çözümünü sayar.
  - Beş indirme düğmesi (sınav kâğıdı, Moodle XML, GIFT, CSV, JSON).
- İç fonksiyon `human(q)`: "Onaylandı / Reddedildi / Bildirildi / —".

---

## `src/ui/pages/review.py` — İnceleme (160 satır)

**Ne işe yarar?** Kalite kontrol ekranı (rol yok, her hesap görür). Soru kartı ile kanıtın sarıyla işaretlendiği PDF sayfası yan yana durur; altında onay/red kararı ve doğrulama ayrıntıları. Kararlar doğrulayıcının isabetini ölçmeye yarar. Reddedilen soru sınavlara konmaz (ortak havuz); kararı kimin verdiği kayda yazılır.

**Bağlantılar:** → `review_store` (`render_evidence`, `save_decision`, `REJECT_REASONS`, `FLAG_TR`), `components`, `data`, `style`.

**İçindekiler**
- `_WIDE`: bu sayfada içerik genişliği artırılır (iki kart yan yana sığsın).
- [`_evidence_png(qid, key)`](../src/ui/pages/review.py#L23) (önbellekli): `render_evidence` ile işaretli sayfa görüntüsü.
- [`_mine(s)`](../src/ui/pages/review.py#L28): setin yalnızca görebildiğin belgelere ait soruları (istek setinde birden çok belgenin sorusu olabilir).
- [`_filters()`](../src/ui/pages/review.py#L34): set seçimi (belge setleri önce, en büyük önce; görünür sorusu olmayan set listelenmez), görünüm (İncelenmemiş / İncelenmeli / Bildirilen / Tümü), "Önce kendin çöz" anahtarı (cevabı ve sayfayı gizler).
- [`_pager(idx, n_view, done, total)`](../src/ui/pages/review.py#L55): Önceki / Sonraki + "Bu sette incelenen: X / Y" çubuğu.
- [`_decide(item, source, n_view)`](../src/ui/pages/review.py#L70): red nedenleri, not, Onayla / Reddet / Atla. Karar verilince sonraki soruya geçilir.
- [`_details(item, reveal)`](../src/ui/pages/review.py#L91): üreten ve doğrulayan model, SymPy sonucu, şık kararları, doğrulayıcının kendi cevabı ve gerekçesi, uyarılar.
- [`_advance(n_view)`](../src/ui/pages/review.py#L119): sıradaki soruya geçer.
- [`render()`](../src/ui/pages/review.py#L124): öğrenci bildirimi varsa uyarı gösterir. `.nr-pair` ızgarasında iki kart, altında karar ve ayrıntılar. Sıra `st.session_state.idx`'te tutulur.

---

## `src/ui/pages/report.py` — Rapor (95 satır)

**Ne işe yarar?** İki sekme:
- **Nasıl çalışır:** gerçek sayılarla 6 adımlı akış şeması.
- **Ölçümler:** arama, doğrulayıcı, hesap kontrolü, bilişsel düzey, toplu üretim, insan değerlendirmesi, öğrenci sonuçları.

Her sonuç tekrar çalıştırılabilir bir eval betiğinden gelir.

**Bağlantılar:** → `parts/evaluation` (alt fonksiyonlar), `data`, `request.all_items`, `style.flow`, `pandas`.

- [`_how()`](../src/ui/pages/report.py#L11): açıklama paragrafı ve `style.flow`. Okunan sayfa → konu → parça → üretilen → kod kontrolünden geçen → doğrulanan.
- [`_compute()`](../src/ui/pages/report.py#L37): hesap kontrolü duyarlılığı (`eval/sonuclar_hesap_kontrol.json`).
- [`_students()`](../src/ui/pages/report.py#L56): madde analizi tablosu (en düşük doğru oranı üstte), yalnızca görebildiğin belgelerin soruları. "Çözen kişi": her kişinin yalnızca soruyu ilk görüşü sayılır.
- [`render()`](../src/ui/pages/report.py#L81): ölçüm seçici → ilgili fonksiyon. Çoğu `parts/evaluation.py`'den alınır.

---

## `src/ui/pages/models.py` — Modeller ve Kota (171 satır)

**Ne işe yarar?** Şu an kalan kotayla ne yapılabileceğini gösterir (kaç belge, kaç soru doğrulanır, kaç sayfa okunur). Ayrıca her modelin durum kartı, hangi işin hangi modelle yapıldığı (kalite kapısı kanıtlarıyla) ve ücretli kullanımda maliyet tahmini burada.

**Bağlantılar:** → `ledger` (`report`, `time_until_available`), `models` (`APPROVED`, `CANDIDATES`, `MODELS`), `data`, `style`.

- Sabitler:
  - `ROLE_TR`, `ROLE_WHY`: rol adları ve açıklamaları.
  - `PROVIDER`: sağlayıcı adları.
  - `PRICE`: USD / 1M token. Kaynağı LITERATURE.md; kullanmadan önce teyit edilmeli.
- [`_reset_tr()`](../src/ui/pages/models.py#L38): Gemini kotasının Türkiye saatiyle sıfırlandığı saat.
- [`_model_state(m)`](../src/ui/pages/models.py#L49): kullanım / sınır, doluluk oranı, ne zaman açılacağı. Durum "Hazır" / "Az kaldı" / "Dolu · X sonra" olur.
- [`_capacity()`](../src/ui/pages/models.py#L66): üç kutu (soru üretimi, doğrulama, görsel okuma).
- [`_models()`](../src/ui/pages/models.py#L97): model kartları (rol çipleri, ölçer çubuğu, sıfırlanma bilgisi).
- [`_roles()`](../src/ui/pages/models.py#L117): rol → zincir. Çipin üzerine gelince onayın kanıtı görünür; adaylar da listelenir.
- [`_cost()`](../src/ui/pages/models.py#L135): sayfa başına kaba maliyetle 25 sayfalık not, bir dönem, şu anki belgeler.
- [`_n(x)`](../src/ui/pages/models.py#L34): tamsayıyı Türkçe binlik ayraçla yazar (`12345` → `12.345`); kota ölçerlerinde.

---

## `src/ui/parts/evaluation.py` — ölçüm grafikleri (209 satır)

**Ne işe yarar?** Rapor sayfasının ölçüm bölümlerini Altair grafikleri ve tablolarla çizer. Grafik ilkeleri dataviz yönergesinden gelir:
- tek seri vurgulu, gerisi gri;
- durum renkleri her zaman etiketle birlikte;
- her grafiğin bir tablo karşılığı var.

**Bağlantılar:** ← `pages/report` (yalnızca `_retrieval`, `_sensitivity`, `_bloom`, `_batch`, `_human`). → `data.eval_json`, `style`.

- [`_theme(ch)`](../src/ui/parts/evaluation.py#L18): ortak yazı tipi ve renkler.
- [`_emphasis_bars(df, x, y, best)`](../src/ui/parts/evaluation.py#L27): en iyi yöntemi renkli, diğerlerini gri gösteren yatay çubuklar.
- [`_retrieval()`](../src/ui/parts/evaluation.py#L39): arama ölçümü (isabet@1/5, MRR) ve kategorilere göre küçük grafikler.
- [`_sensitivity()`](../src/ui/parts/evaluation.py#L78): doğrulayıcı başına "yakalanan / toplam" ve bozulma türü tablosu.
- [`_stacked`](../src/ui/parts/evaluation.py#L107) / [`_with_ends`](../src/ui/parts/evaluation.py#L122): yığılmış çubuk ve etiket konumları.
- [`_bloom()`](../src/ui/parts/evaluation.py#L128): hatırlama ve uygulama koşullarında doğrulandı / incelenmeli / reddedildi.
- [`_batch()`](../src/ui/parts/evaluation.py#L152): toplu üretim karşılaştırma tablosu.
- [`_human()`](../src/ui/parts/evaluation.py#L168): inceleme kararları. "Doğrulananlarda kabul" oranı doğrulayıcının isabetidir.
- [`render()`](../src/ui/parts/evaluation.py#L194): **hiç çağrılmıyor.** Eskiden ayrı bir "Değerlendirme" sayfasıydı.

## `src/ui/parts/system.py` — (ölü kod) (85 satır)

(Tek özel işlev [`_quota()`](../src/ui/parts/system.py#L33): "Kota kullanımı" başlığı ve son 24 saatte kullanılmış her model için ilerleme çubuğu; Groq'ta token, Gemini'de istek; bekleme varsa "⏳ N dk bekleme". Yerini `pages/models.py` aldı, çağıran yok.)

Eski "Sistem ve Kota" sayfasının parçası. Kalite kapısı rozetleri, kota çubukları, maliyet. Hiçbir dosya içe aktarmıyor; yerini [`pages/models.py`](../src/ui/pages/models.py) aldı. Silinebilir. (`PRICE` sözlüğü iki dosyada da tekrar ediyor.)

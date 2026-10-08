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
src/ui/shelf.py            ana sayfanın kart desteleri: Streamlit özel bileşeni, CCv2 (bölüm 12)
src/ui/upload.py           not yükleme akışı (Belgeler + ana sayfa penceresi; bölüm 12)
src/ui/style.py            görsel dil: CSS + küçük HTML yardımcıları
src/ui/data.py             arayüzün veri katmanı (dosya okuma, önbellek, arka plan işleri)
src/ui/components.py       ortak soru kartı, kaynak sayfa kartı, bitiş özeti
src/ui/quiz.py             sınav çözme deneyimi (başlangıç → odak modu → sonuç)
src/cards.py               bilgi kartı mantığı: deste, aralıklı tekrar (Streamlit'siz)
src/ui/pages/exam.py       Sınav Hazırla
src/ui/pages/cards.py      Bilgi Kartları
src/ui/pages/documents.py  Belgeler (PDF yükleme dahil)
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

## `src/ui/style.py` — görsel dil (461 satır)

**Ne işe yarar?** "Akademik baskı + fosforlu kalem" görünümü.
- Renkler ve yazı tipleri [`.streamlit/config.toml`](../.streamlit/config.toml)'da: kâğıt zemin `#F7F4ED`, mürekkep laciverdi, Fraunces / Instrument Sans / JetBrains Mono.
  - Yazı tipleri yerelden sunulur (`src/static/fonts/`, `[[theme.fontFaces]]`, `server.enableStaticServing`): internetsiz sunumda da aynı görünüm. Yalnızca latin + latin-ext (Türkçe harfler). Lisans: SIL OFL 1.1.
- Bu dosyada Streamlit bileşenlerinin karşılamadığı ayrıntılar var: kâğıt dokusu, sarı vurgu, kartlar, sınav ekranı düzeni.
- Ayrıca HTML üreten küçük yardımcılar.
- Çalışma ekranlarının (bilgi kartı, sınav) tasarım ilkesi, "v3": düz kâğıt zemin üstünde sakin kartlar. Hareket yalnızca bir anlam taşıyınca var: kart döner, değerlendirilen kart yığınına gider. Figür, konfeti ve animasyonlu emoji kullanıcı kararıyla kaldırıldı.

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
    - bilgi kartı: deste (`.nr-deck`, `.nr-stack`), dönen kart (`.nr-fc`, `.nr-flip`, `.nr-face`), yığınına giden kart (`.nr-ghost`), üç yığın (`.nr-piles`), üst şerit (`.nr-topbar`), kurulum sayıları (`.nr-ctiles`);
    - bitiş özeti (`.nr-sum`, ölçer `.nr-m`, konu satırı `.nr-tr`): kart oturumu ve sınav sonucu ortak;
    - sınav kartının üstündeki soru başına renkli şerit (`.nr-focus::before`);
    - hareket azaltma tercihi (`prefers-reduced-motion`) açıksa animasyonlar kapanır.
- `PALETTE`: altı pastel kart rengi `(açık, koyu pastel, yazı, vurgu)`. Yazı rengi her pastelde en az 7:1 karşıtlıkta.
- [`color(i)`](../src/ui/style.py#L445): i. kartın rengi (palet döner).
- [`color_vars(i)`](../src/ui/style.py#L449): o rengi CSS değişkenleri olarak verir (`--c1`, `--ink`, `--a`…); kart HTML'inin `style=` özniteliğine yazılır.
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

## `src/ui/data.py` — arayüzün veri katmanı (208 satır)

**Ne işe yarar?** Arayüzün okuduğu her şey buradan geçer: parçalar, bölümler, belgeler, soru setleri, kararlar, kota, ölçüm sonuçları. Yalnızca yerel dosyalar okunur, API çağrısı yoktur. Çoğu fonksiyon `st.cache_data` ile kısa süreli önbelleklenir. Belge işleme işini başlatma ve izleme de buradadır.

**Bağlantılar**
- ← bütün sayfalar, `components`, `quiz`, `parts`.
- → `review_store`, `config`, `topics`, `generate`, `request`, `ledger`.

**İçindekiler**
- [`chunks()`](../src/ui/data.py#L27), [`sections()`](../src/ui/data.py#L32), [`parsed(stem)`](../src/ui/data.py#L37): veri dosyalarını okur (20 sn önbellek).
- [`short(doc)`](../src/ui/data.py#L42): belgenin görünen adı, belge kaydından ([`library.display_name`](../src/library.py#L233); sahibi değiştirebilir).
- **Kişi ve görünürlük (bölüm 11):**
  - [`user()`](../src/ui/data.py#L50), [`uid()`](../src/ui/data.py#L55): giriş yapmış kişi `{id, name, username}` ve kimliği (`auth.py` `session_state.user`'a koyar).
  - [`_visible(user_id)`](../src/ui/data.py#L61): kişinin görebildiği belgeler (10 sn önbellek). Önce `library.sync()` çalışır: elle konan PDF'ler ve girişten önceki belgeler de kayda girer.
  - [`visible()`](../src/ui/data.py#L67): giriş yapan kişi için `_visible`. Belge gösteren her sayfa bununla süzer.
  - [`doc_meta()`](../src/ui/data.py#L74): belge kaydı `{doc: {name, owner, public, …}}` (Belgeler sayfasındaki rozet ve düğmeler).
  - [`my_documents()`](../src/ui/data.py#L80): `documents()`'ın görünür olanları.
- **Ana sayfa ve profil (bölüm 12):** [`mine()`](../src/ui/data.py#L91) (kişinin kendi listesi), [`items()`](../src/ui/data.py#L97) (bütün sorular, 30 sn önbellek), [`mastery()`](../src/ui/data.py#L109) (beyin analizi), [`home_stats()`](../src/ui/data.py#L129) ve [`due_cards()`](../src/ui/data.py#L134) (selam satırı, bugünün tekrarı), [`avatar_b64(user_id)`](../src/ui/data.py#L140) (profil resmi; değişince `.clear()`).
- [`topics(doc)`](../src/ui/data.py#L150): konu haritası, `build_missing=False` ile. Arayüz konu haritası için LLM'e gitmez.
- [`has_math(doc)`](../src/ui/data.py#L157): belgede formüllü birim var mı? Varsa Sınav Hazırla'da "Hesap sorusu" tipi gösterilir.
- [`item_stats()`](../src/ui/data.py#L167), [`reports()`](../src/ui/data.py#L173): `request` modülündekilerin önbellekli hali.
- [`set_label(name, kind)`](../src/ui/data.py#L178): dosya adından okunur set adı (`'qwen_..._english_tr'` → `'Genetic Algorithms → TR · qwen3.8-27b (pilot)'`).
- [`doc_of(item)`](../src/ui/data.py#L194): sorunun belgesi (ilk parça kimliğinden).
- [`question_sets()`](../src/ui/data.py#L200): bütün soru setleri `[{key, name, kind ('belge'|'pilot'), items}]`. Her soruya `doc`, `set`, `set_kind` eklenir.
- [`all_questions(include_pilot)`](../src/ui/data.py#L214): setlerdeki soruların kimliğe göre tekilleştirilmiş listesi.
- [`decisions()`](../src/ui/data.py#L226): inceleme kararları (önbelleksiz; karar verilince hemen görünsün).
- [`documents()`](../src/ui/data.py#L231): her PDF için özet. Sayfa sayısı, görselden okunan ve bekleyen sayfa, tablo sayfası, parça / bölüm / soru / doğrulanmış soru sayısı. **Bütün** belgeler; sayfalar `my_documents()` kullanır (Rapor ve Modeller ve Kota'daki sistem toplamları hariç: içerik göstermezler).
- [`eval_json(name)`](../src/ui/data.py#L256): `eval/<ad>.json` ölçüm sonucu.
- [`quota()`](../src/ui/data.py#L261): `ledger.report()`.
- **Arka plan işleri:**
  - [`start_job(pdf_name, language)`](../src/ui/data.py#L271): `python -m src.pipeline "<pdf>"`'i bağımsız süreçte başlatır. Çıktı `data/jobs/<belge>.log`'a, başlangıç zamanı `.json`'a yazılır.
  - [`job_status(stem)`](../src/ui/data.py#L287): log dosyasını okuyup durumu çıkarır. `STEP_RE` `"3/6 bölümleme"` satırlarını yakalar; "Bitti" görünce iş bitti, "Traceback" görünce hata, "⏳" görünce kota beklemesi sayılır.
  - [`jobs()`](../src/ui/data.py#L304): bütün işler, en yeni önce.

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

## `src/ui/quiz.py` — sınav çözme deneyimi (400 satır)

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
- [`hints(req, it)`](../src/ui/quiz.py#L58): **kademeli (Sokratik) ipuçları.** 1) Nereye bakmalı (konu + sayfa). 2) Kaynak cümle ya da uygulanacak kural. 3) Hesapta çözümün ilk adımı.

**1. Başlangıç:** [`start_screen(req, items)`](../src/ui/quiz.py#L85): özet kutusu ve "Sınava başla" düğmesi. Düğme fazı `"solve"` yapar.

**2. Odak modu:** [`solve(req, items)`](../src/ui/quiz.py#L195)
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
  - [`_pick`](../src/ui/quiz.py#L116): şık seçimi.
  - [`_sync_text`](../src/ui/quiz.py#L121): kısa cevabı `answers`'a kopyalar.
  - [`_go`](../src/ui/quiz.py#L127): soru değiştirir.
  - [`_hint`](../src/ui/quiz.py#L134): ipucu sayısını artırır.
  - [`_jump`](../src/ui/quiz.py#L140): haritadan atlar.
  - [`_finish`](../src/ui/quiz.py#L145): sonuca geçer.
- [`_confirm_finish`](../src/ui/quiz.py#L151) (`@st.dialog`): "N soru boş, yine de bitir?" penceresi.
- [`_keys_and_scroll(started, flash)`](../src/ui/quiz.py#L162): tarayıcıda çalışan küçük bir JavaScript (`st.iframe` içinde). İki işi var:
  - Süre sayacını her saniye günceller; sunucuya istek atmaz.
  - Klavye kısayollarını kurar: A–D şık, ← → soru, H ipucu. Basılan tuş, CSS sınıfıyla bulunan düğmeye `click()` yaptırır.

  İçerik yalnızca yeni ipucu açılınca değişir; böylece Streamlit çerçeveyi her tıklamada yeniden yüklemez ve sayaç titremez.

**3. Sonuç:** [`results(req, items)`](../src/ui/quiz.py#L316)
1. Her soruyu puanla. İlk kez geliniyorsa `record_attempt` ile, giriş yapan kişinin kimliğiyle kaydet (madde analizi); `recorded=True` yap. "Baştan çöz" yeniden kaydeder ama ölçüme yalnızca kişinin ilk çözümü girer (bölüm 10).
2. Doğru / yanlış / boş sayıları (itirazlar doğru sayılır).
3. Özet: her soru için `{durum, zorluk, tip, konu}` kaydı → `components.summary_html` (sınavda soru tipine göre ölçer de var).
   - [`_message`](../src/ui/quiz.py#L294): yüzdeye göre başlık ve not.
   - Süre kutusu; ipucu kullanıldıysa sayısı.
   - Zorluk sütunu etkin düzeydir (ölçülmüş), üretecin iddiası değil.
4. Düğmeler:
   - "Yanlışları tekrar çöz": [`restart`](../src/ui/quiz.py#L304) `retry` ile yeni deneme açar.
   - "Kartla çalış": yanlış ve boş soruları `st.session_state.cards_preset`'e koyup Bilgi Kartları sayfasına geçer. Orada yalnızca şıksız anlaşılan sorular karta dönüşür.
   - "Baştan çöz" ve "Yeni sınav".
5. Gözden geçirme ("Yanlış ve boşlar / Tümü / Doğrular" süzgeci): her soru kartıyla, ardından:
   - "Hatalı bildir": `request.report`; soru inceleme bitene kadar sınavlardan çıkar.
   - Kısa cevapta "Cevabım doğruydu" itirazı: puana yansır, soru İnceleme sayfasına düşer.

---

## `src/cards.py` — bilgi kartı mantığı (106 satır)

**Ne işe yarar?** NotebookLM'deki gibi bilgi kartları: önde soru, arkada cevap. Kartlar havuzdaki **doğrulanmış** sorulardan yapılır; LLM çağrısı yoktur, kota harcamaz. Bu dosyada Streamlit yok (test edilebilsin diye); ekran `pages/cards.py`'de.

**Hangi soru kart olur?** Kartta şık yok. Bu yüzden yalnızca şıksız da anlaşılan sorular:
- kısa cevap soruları;
- kökü kendi başına soru olan çoktan seçmeliler (arka yüzde cevap = doğru şıkkın metni).

Doğru / yanlış ifadeleri, "aşağıdakilerden hangisi" ve olumsuz kök ("…değildir") gibi şıklara dayanan sorular sınavda kalır.

**Aralıklı tekrar (Leitner kutuları).** Her kart 1-5 arası bir kutudadır:
- Bildim → bir üst kutu; Bilemedim → 1. kutu; Atla → değişmez.
- Kutu yükseldikçe kart seyrekleşir: 1. kutu her oturumda, sonra 1, 3, 7, 14 gün.
- Sonuç öğrencinin kendi değerlendirmesidir. Sınavın madde istatistiğine (`attempts.jsonl`) karışmaz; ayrı dosyaya yalnızca eklenir: `data/review/cards.jsonl` (soru ve kişi kimliğine bağlı). Kutular bu kayıt baştan oynatılarak bulunur.
- **Kutular kişiye özeldir:** herkes aynı kuralla, yalnızca kendi değerlendirmeleriyle ilerler. Kişi alanı olmayan eski satırlar ilk hesabındır (bölüm 11).

**Bağlantılar:** ← `pages/cards`, `difficulty.real_attempts` (`first_seen`), `tests/test_cards`. → `request` (`all_items`, `usable`, `blocked_ids`), `accounts.legacy_owner`, `jsonl`, `config`.

**İçindekiler**
- `LOG`, `INTERVAL_DAYS` (kutu → gün), `RESULTS` (`good`, `bad`, `skip`).
- `_OPTION_BOUND`: kökü şıklara dayanan soruyu yakalayan düzenli ifade ("aşağıdaki", "seçenek", "şık", "değildir", "which of"…). `\bşık\b`: "yaklaşık" yakalanmasın.
- [`card_ok(q)`](../src/cards.py#L32): soru şıksız bir karta dönüşebilir mi?
- [`step(state, result, t)`](../src/cards.py#L41): bir değerlendirmeden sonra kartın yeni durumu `{box, last, seen, good, bad}`. Saf fonksiyon (dosyaya dokunmaz).
- [`_mine(rows, user)`](../src/cards.py#L57): yalnızca o kişinin satırları (`user` verilmezse hepsi).
- [`history(path, user)`](../src/cards.py#L66): kayıt dosyasını baştan oynatır → kart kimliği → durum. Sayfa `user=` ile çağırır: kişinin kendi kutuları.
- [`first_seen(path)`](../src/cards.py#L74): (kişi, soru) → kartta ilk değerlendirildiği an. Kartta cevabı görülmüş soru sonra sınavda çıkarsa o deneme "taze" sayılmaz (bölüm 10). "Atla" sayılmaz: cevap görülmemiş olabilir.
- [`record(qid, result, path, user)`](../src/cards.py#L85): bir değerlendirmeyi kişiyle birlikte dosyaya ekler. `path` çağrı anında okunur; testler geçici dosyaya yönlendirebilsin.
- [`is_due(state, now)`](../src/cards.py#L93): hiç görülmemiş ya da kutusunun aralığı dolmuş kart.
- [`next_gap(state, result)`](../src/cards.py#L98): bu sonuçtan sonra kart kaç gün sonra gelir (ekrandaki "Bildim → 3 gün sonra yeniden" ipucu).
- [`pick(items, hist, n, now, only_due, seed)`](../src/cards.py#L103): deste. Önce zamanı gelmiş tekrar kartları (düşük kutu önce), sonra hiç görülmemişler; eşitlerde karışık.
- [`pool(docs)`](../src/cards.py#L112): seçili belgelerdeki kart olabilen sorular. Sınavla aynı kural: doğrulanmış, reddedilmemiş, bildirilmemiş.
- [`summary(items, hist, now)`](../src/cards.py#L120): kurulum ekranındaki sayılar (toplam, yeni, zamanı gelen, ustalaşılan = kutu ≥ 4).

---

## `src/ui/pages/cards.py` — Bilgi Kartları (278 satır)

**Ne işe yarar?** Üç ekran:
1. **Seçim:** belgeler, kart sayısı, "yalnızca zamanı gelenler" anahtarı; dört sayı kutusu (kart, tekrar zamanı gelen, hiç görmediğin, ustalaştığın).
2. **Oturum:** kart ortada ve büyük. Tıklayınca döner (arkada soru özeti, cevap, varsa çözüm adımları, notundaki kaynak cümle sarı vurguyla); yine tıklayınca geri. Bilemedim / Atla / Bildim → kart ilgili yığına uçar, sıradaki desteden gelir.
3. **Özet:** ortak bitiş özeti (`components.summary_html`): isabet, zorluğa ve konulara göre; "Bilemediklerimi çalış" ve "Yeni oturum".

Klavye: Boşluk çevir · ← bilemedim · ↓ atla · → bildim.

**Bağlantılar:** ← `app.py` menüsü, `quiz.results` ("Kartla çalış"). → `cards`, `request.all_items`, `components`, `data`, `style`.

**Durum: `st.session_state.cards`**

| Alan | Anlamı |
|---|---|
| `queue`, `pos` | Destedeki soru kimlikleri ve şu anki sıra |
| `res`, `col` | Kimlik → sonuç; kimlik → kartın renk sırası (yığındaki küçük kart aynı renkte görünsün) |
| `skipped` | Atlanan kartlar destenin sonuna bir kez eklenir; ikinci kez atlanırsa bir sonraki oturuma kalır |
| `streak`, `best` | Üst üste "Bildim" serisi ve en uzunu |
| `last` | Az önce değerlendirilen kart (yığına uçan "hayalet" kart bir kez çizilir) |
| `v` | Her değerlendirmede artan sayaç; sahnenin `div`/`section` etiketini değiştirir |
| `started`, `ended` | Süre ve "Bitir" |

**İçindekiler**
- [`_items()`](../src/ui/pages/cards.py#L30): bütün sorular (30 sn önbellek).
- [`_topic(it)`](../src/ui/pages/cards.py#L38): kartın konusu. Bölüm adı yalnızca numaraysa ("01") belge adıyla birlikte.
- Geri çağırmalar:
  - [`_begin(ids)`](../src/ui/pages/cards.py#L55): yeni oturum durumu.
  - [`_grade(result)`](../src/ui/pages/cards.py#L62): sonucu `cards.record` ile, giriş yapan kişinin kimliğiyle kaydeder; seriyi, yığınları ve sırayı günceller.
  - [`_shuffle`](../src/ui/pages/cards.py#L81): kalan kartları karıştırır (ekrandaki kart yerinde kalır).
  - [`_only_bad`](../src/ui/pages/cards.py#L88): yalnızca bilinemeyenlerle yeni tur.
  - [`_end`](../src/ui/pages/cards.py#L94), [`_new`](../src/ui/pages/cards.py#L99): bitir, baştan.
- HTML parçaları:
  - [`_front(it)`](../src/ui/pages/cards.py#L106), [`_back(it)`](../src/ui/pages/cards.py#L113): kartın iki yüzü.
  - [`_length_class(q)`](../src/ui/pages/cards.py#L129): uzun soruda yazı küçülür (`long`, `xlong`).
  - [`_piles(cs, bump)`](../src/ui/pages/cards.py#L134): üç yığın; az önce kart düşen yığın hafifçe büyür.
  - [`_stage(it, cs)`](../src/ui/pages/cards.py#L145): deste + kart + uçan kart + yığınlar.
    - Kart bir `<details>` öğesidir: tıklamak onu açıp kapatır, CSS bunu 3B dönüşe çevirir. Böylece çevirmek sunucuya gitmez.
    - Sarmalayıcı etiketi her değerlendirmede `div` ↔ `section` değişir. Tarayıcı sahneyi sıfırdan kurar: animasyon her seferinde oynar ve çevrilmiş kart bir sonraki karta çevrili geçmez.
- [`_keys()`](../src/ui/pages/cards.py#L162): klavye kısayolları (`st.iframe` içinde küçük JavaScript). Boşluk `<details>`'i açıp kapatır; ok tuşları CSS sınıfıyla bulunan düğmeye `click()` yaptırır.
- Ekranlar: [`_setup()`](../src/ui/pages/cards.py#L189), [`_session()`](../src/ui/pages/cards.py#L225), [`_summary()`](../src/ui/pages/cards.py#L259). Seçimde yalnızca görebildiğin belgeler listelenir; sayılar ve deste kişinin kendi kutularından (`history(user=…)`).
- [`render()`](../src/ui/pages/cards.py#L281): sınavdan `cards_preset` geldiyse o sorularla oturum açar (hiçbiri karta dönüşmüyorsa bildirim gösterir); oturum varsa oturum, yoksa seçim ekranı.

---

## `src/ui/pages/exam.py` — Sınav Hazırla (181 satır)

**Ne işe yarar?** Sistemin ana sayfası. Önce seçim formu gelir; sınav hazırlanınca durum, sınav ve dışa aktarma gösterilir.

**Bağlantılar:** → `request` (`prepare`, `load`, `items_of`, `start`, `save`, `KINDS`), `quiz`, `export`, `data`, `style`.

**İçindekiler**
- `DIFF`: ekrandaki zorluk adı → kod değeri ("Karışık" → `None`).
- [`_builder()`](../src/ui/pages/exam.py#L20): seçim formu.
  1. Belgeler (yalnızca görebildiklerin; varsayılan: en çok doğrulanmış sorusu olan).
  2. Konular (konu haritasından; boşsa hepsi).
  3. Zorluk, tipler ("Hesap sorusu" yalnızca formüllü belgede), sayı (5/10/15/20).

  "Sınavı hazırla" düğmesi `R.prepare(...)` çağırır; arama ve havuz eşleştirmesi saniyeler sürer.
- [`_open(req_id)`](../src/ui/pages/exam.py#L62): `session_state.exam`'ı kurar, adres çubuğuna `?sinav=<id>` yazar.
- [`_summary(req)`](../src/ui/pages/exam.py#L69): sınavın özeti ve "Notlarında bulunan kaynak sayfalar" açılır paneli: her konunun aramada bulduğu sayfalar. RAG'in görünür kanıtı budur.
- [`_live(req_id)`](../src/ui/pages/exam.py#L90) (`@st.fragment(run_every=3)`): eksik sorular üretilirken her 3 saniyede istek dosyasını okuyup ilerleme çubuğunu günceller. İş bitince bütün sayfayı yeniler.
- [`_progress_value(text)`](../src/ui/pages/exam.py#L102): `"Doğrulanıyor 3/8"` metninden çubuk değeri.
- [`_status(req, items)`](../src/ui/pages/exam.py#L108): sınava geçilebilir mi?
  - Üretiliyorsa canlı ilerleme.
  - `"partial"` ise "eksik N soruyu üret" (`R.start`) ya da "hazır olanlarla başla".
  - Hiç soru yoksa uyarı.
- [`_export(req, items)`](../src/ui/pages/exam.py#L139): dört indirme düğmesi (sınav kâğıdı, Moodle XML, GIFT, CSV).
- [`render()`](../src/ui/pages/exam.py#L169): sayfanın akışı. Adreste `?sinav=` varsa sınavı açar; ama yalnızca sınavın belgelerinin hepsini görebiliyorsan (bağlantıyı açan herkes kendi hesabıyla çözer; göremiyorsan "not herkese açılırsa bağlantı çalışır" uyarısı). Faz `"solve"` ise yalnızca odak modu gösterilir (başlık yok). Değilse başlık → form ya da özet → durum → sonuç ya da başlangıç ekranı → dışa aktarma.

---

## `src/ui/pages/documents.py` — Belgeler (152 satır)

**Ne işe yarar?** Yeni PDF yüklenir ve işlenir. Çalışan işler izlenir. Her belgenin konuları, sayfaları (görüntü + çıkarılan metin) ve okuma kalitesi gösterilir. Belge kütüphanesinin (bölüm 11) arayüzü de burada: yüklenen not yalnızca yükleyene görünür, istenirse herkese açılır; sistemde zaten olan not yeniden işlenmez.

**Bağlantılar:** → `library` (`register`, `publish`, `rename`, `has_access`), `data` (`start_job`, `jobs`, `my_documents`, `visible`, `doc_meta`, `topics`, `parsed`), `request` (`all_items`, `usable`), `config`, `pymupdf`.

**İçindekiler**
- [`_add()`](../src/ui/pages/documents.py#L25): "Yeni ders notu ekle" açılır paneli. İçindeki akış (dosya seçici, soru dili, `library.register`, sonuç, işleme başlatma) 2026-10-08'de [`ui/upload.py`](../src/ui/upload.py)'ye taşındı; ana sayfadaki "+ Yeni not ekle" penceresi de aynısını kullanır (bölüm 12).
- [`_start(file, lang)`](../src/ui/pages/documents.py#L32): `upload.start` + sayfayı yenile ("Notu işle" düğmesi).
- Seçili not: ana sayfada bir karta tıklanınca `session_state.doc_open` ile gelir ve belge seçici (`doc_sel`) o nota ayarlanır.
- [`_publish(d)`](../src/ui/pages/documents.py#L38) (`@st.dialog`): "Notu herkese aç" onay penceresi. Neyin açılacağını (sayfalar, metin, sorular, kanıtlar) ve **geri alınamayacağını** söyler.
- [`_actions(d)`](../src/ui/pages/documents.py#L51): seçili belgenin rozeti (Gizli / Herkese açık), "Herkese aç" düğmesi (erişimin varsa), "Adını değiştir" (yalnızca sahibi). Not henüz işlenmediyse "Notu işle" düğmesi.
- [`_jobs()`](../src/ui/pages/documents.py#L82) (`fragment`, 4 sn): çalışan işlerin adım adı, ilerleme çubuğu ve son satırı (yalnızca görebildiğin belgelerin işleri). Kota bekleniyorsa "iş duraklamadı" notu.
- [`_detail(tail)`](../src/ui/pages/documents.py#L96): log'un son satırını kullanıcıya uygun metne çevirir ("Gemini'nin kotası dolu, qwen ile tek tek üretiliyor").
- [`_page_png(file, page)`](../src/ui/pages/documents.py#L109): sayfa görüntüsü (85 dpi, önbellekli).
- [`_topics_tab(d)`](../src/ui/pages/documents.py#L114): konu tablosu. Konu, sayfalar ve **hazır soru** sayısı (o sayfalara bağlı doğrulanmış sorular).
- [`_pages_tab(d)`](../src/ui/pages/documents.py#L132): sayfa kaydırıcısı. Solda PDF görüntüsü, sağda sistemin çıkardığı metin ve rozetler (metin katmanı / görselden okundu / bekliyor / bayraklar).
- [`_quality_tab(d)`](../src/ui/pages/documents.py#L156): görselden okunan sayfa, tablosu çıkarılan sayfa, silinen üst/alt bilgi satırı, üretimden çıkarılan sayfalar.
- [`render()`](../src/ui/pages/documents.py#L170): yükleme → işler → belge seçici (görebildiğin belgeler) → rozet ve düğmeler → üç sekme.

---

## `src/ui/pages/bank.py` — Soru Bankası (84 satır)

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

## `src/ui/pages/review.py` — İnceleme (147 satır)

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

## `src/ui/pages/report.py` — Rapor (93 satır)

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

Eski "Sistem ve Kota" sayfasının parçası. Kalite kapısı rozetleri, kota çubukları, maliyet. Hiçbir dosya içe aktarmıyor; yerini [`pages/models.py`](../src/ui/pages/models.py) aldı. Silinebilir. (`PRICE` sözlüğü iki dosyada da tekrar ediyor.)

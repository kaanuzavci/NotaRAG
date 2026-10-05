# 8. Arayüz (Streamlit)

[← 7. Sınav isteği](07-sinav-istegi.md) · [Ana sayfa](README.md) · Sonraki: [9. Ölçüm ve testler →](09-olcum-ve-test.md)

Projenin en büyük katmanı (~1.865 satır, 12 dosya). Arayüz hiçbir LLM'i doğrudan çağırmaz. Dosyaları okur, sonuçları gösterir; uzun işleri ayrı süreç olarak başlatır (`pipeline`, `request`).

```
src/app.py                 menü ve giriş (bölüm 1)
src/ui/style.py            görsel dil: CSS + küçük HTML yardımcıları
src/ui/data.py             arayüzün veri katmanı (dosya okuma, önbellek, arka plan işleri)
src/ui/components.py       ortak soru kartı ve kaynak sayfa kartı
src/ui/quiz.py             sınav çözme deneyimi (başlangıç → odak modu → sonuç)
src/ui/pages/exam.py       Sınav Hazırla        (varsayılan sayfa)
src/ui/pages/documents.py  Belgeler (PDF yükleme dahil)
src/ui/pages/bank.py       Soru Bankası
src/ui/pages/review.py     İnceleme (öğretmen)
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

## `src/ui/style.py` — görsel dil (302 satır)

**Ne işe yarar?** "Akademik baskı + fosforlu kalem" görünümü.
- Renkler ve yazı tipleri [`.streamlit/config.toml`](../.streamlit/config.toml)'da: kâğıt zemin `#F7F4ED`, mürekkep laciverdi, Fraunces / Instrument Sans / JetBrains Mono.
- Bu dosyada Streamlit bileşenlerinin karşılamadığı ayrıntılar var: kâğıt dokusu, sarı vurgu, kartlar, sınav ekranı düzeni.
- Ayrıca HTML üreten küçük yardımcılar.

**Bağlantılar:** ← `app.py` ve bütün `ui/` dosyaları.

**İçindekiler**
- `INK, PAPER, HIGHLIGHT`: renk sabitleri (dışarıda kullanılmıyor).
- `STATUS`: etiket → (Türkçe ad, yazı rengi, zemin rengi).
- `_CSS` ([satır 21-256](../src/ui/style.py#L21)): bütün özel stiller. Bölümleri:
  - kâğıt dokusu (SVG gürültü);
  - sayfa başlığı (`.nr-kicker`, `.nr-title`, çift çizgi);
  - fosforlu vurgu (`.nr-hl`);
  - kartlar, durum rozeti (`.nr-pill`), 6 adımlı akış şeması (`.nr-flow`);
  - soru kartı (`.nr-exam`, `.nr-opt`);
  - Modeller ve Kota kutuları (`.nr-tile`, `.nr-mcard`, `.nr-meter`);
  - **sınav odak modu**: sabit yükseklikler (`.st-key-nr_answer`, `.st-key-nr_opts`), alta yapışık gezinme çubuğu (`.st-key-nr_nav`), ipucu kutusu (`.nr-hint`);
  - sonuç ekranı (`.nr-res`, `.nr-kpi`);
  - İnceleme sayfasının iki kart düzeni (`.nr-pair`).
- [`inject()`](../src/ui/style.py#L259): CSS'i sayfaya basar (`app.py` çağırır).
- [`html(markup)`](../src/ui/style.py#L265): HTML'i `st.markdown(..., unsafe_allow_html=True)` ile basar.
  - Neden `st.html` değil? `st.html` içeriği ana sayfanın stillerinden yalıtıyor; sınıflar uygulanmıyordu.
  - Boş satırlar silinir: Markdown boş satırda HTML bloğunu keser.
  - `<div lang="tr">` sarmalayıcısı CSS büyük harf dönüşümünü Türkçe yapar: "ipucu" → "İPUCU" (İngilizce kuralla "IPUCU" olurdu).
- [`esc(s)`](../src/ui/style.py#L273): HTML kaçışı (`<` → `&lt;`). Metinde `<` geçerse sayfa bozulmasın, betik enjeksiyonu olmasın.
- [`header(kicker, title, lead, hero_word)`](../src/ui/style.py#L277): sayfa başlığı.
- [`pill(label)`](../src/ui/style.py#L286): "Doğrulandı / İncelenmeli / Reddedildi" rozeti.
- [`card(...)`](../src/ui/style.py#L291): kullanılmıyor.
- [`flow(steps)`](../src/ui/style.py#L296): akış şeması (Rapor → Nasıl çalışır).

---

## `src/ui/data.py` — arayüzün veri katmanı (208 satır)

**Ne işe yarar?** Arayüzün okuduğu her şey buradan geçer: parçalar, bölümler, belgeler, soru setleri, kararlar, kota, ölçüm sonuçları. Yalnızca yerel dosyalar okunur, API çağrısı yoktur. Çoğu fonksiyon `st.cache_data` ile kısa süreli önbelleklenir. Belge işleme işini başlatma ve izleme de buradadır.

**Bağlantılar**
- ← bütün sayfalar, `components`, `quiz`, `parts`.
- → `review_store`, `config`, `topics`, `generate`, `request`, `ledger`.

**İçindekiler**
- [`chunks()`](../src/ui/data.py#L27), [`sections()`](../src/ui/data.py#L32), [`parsed(stem)`](../src/ui/data.py#L37): veri dosyalarını okur (20 sn önbellek).
- [`short(doc)`](../src/ui/data.py#L45): belgenin kısa adı (`config.doc_name`).
- [`topics(doc)`](../src/ui/data.py#L50): konu haritası, `build_missing=False` ile. Arayüz konu haritası için LLM'e gitmez.
- [`has_math(doc)`](../src/ui/data.py#L57): belgede formüllü birim var mı? Varsa Sınav Hazırla'da "Hesap sorusu" tipi gösterilir.
- [`item_stats()`](../src/ui/data.py#L67), [`reports()`](../src/ui/data.py#L73): `request` modülündekilerin önbellekli hali.
- [`set_label(name, kind)`](../src/ui/data.py#L78): dosya adından okunur set adı (`'qwen_..._english_tr'` → `'Genetic Algorithms → TR · qwen3.8-27b (pilot)'`).
- [`doc_of(item)`](../src/ui/data.py#L94): sorunun belgesi (ilk parça kimliğinden).
- [`question_sets()`](../src/ui/data.py#L100): bütün soru setleri `[{key, name, kind ('belge'|'pilot'), items}]`. Her soruya `doc`, `set`, `set_kind` eklenir.
- [`all_questions(include_pilot)`](../src/ui/data.py#L114): setlerdeki soruların kimliğe göre tekilleştirilmiş listesi.
- [`decisions()`](../src/ui/data.py#L126): öğretmen kararları (önbelleksiz; karar verilince hemen görünsün).
- [`documents()`](../src/ui/data.py#L131): her PDF için özet. Sayfa sayısı, görselden okunan ve bekleyen sayfa, tablo sayfası, parça / bölüm / soru / doğrulanmış soru sayısı.
- [`eval_json(name)`](../src/ui/data.py#L156): `eval/<ad>.json` ölçüm sonucu.
- [`quota()`](../src/ui/data.py#L161): `ledger.report()`.
- **Arka plan işleri:**
  - [`start_job(pdf_name, language)`](../src/ui/data.py#L171): `python -m src.pipeline "<pdf>"`'i bağımsız süreçte başlatır. Çıktı `data/jobs/<belge>.log`'a, başlangıç zamanı `.json`'a yazılır.
  - [`job_status(stem)`](../src/ui/data.py#L187): log dosyasını okuyup durumu çıkarır. `STEP_RE` `"3/6 bölümleme"` satırlarını yakalar; "Bitti" görünce iş bitti, "Traceback" görünce hata, "⏳" görünce kota beklemesi sayılır.
  - [`jobs()`](../src/ui/data.py#L204): bütün işler, en yeni önce.

  Ayrı süreç ile arayüz arasındaki "iletişim" bu log dosyasıdır.

---

## `src/ui/components.py` — ortak soru kartı (109 satır)

**Ne işe yarar?** Bir soruyu "basılı sınav kâğıdı" görünümünde HTML olarak üretir. İnceleme sayfası ve sınav sonuç ekranı aynı kartı kullanır.

**Bağlantılar**
- ← `quiz`, `pages/review`, `pages/bank`.
- → `style`, `data`, `textnorm.pretty_math`, `grading.safe_value`.

**İçindekiler**
- [`t(x)`](../src/ui/components.py#L16): ekranda gösterilecek metin. `pretty_math` + HTML kaçışı. Saklanan veri değişmez.
- [`expected(q)`](../src/ui/components.py#L22): beklenen cevap. Hesaplanmamış bir formülse değerini de gösterir (`9!/(3!·2!) = 30240`, `C(n, 2)·2 = n·(n − 1)`); öğrenci sayıyı yazabileceğini görsün.
- [`type_label(q)`](../src/ui/components.py#L38): "Hesap sorusu" ya da tipin Türkçe adı.
- [`_options(q, reveal, chosen)`](../src/ui/components.py#L42): şıklar. `reveal` ise doğru şık yeşil, öğrencinin yanlış seçimi kırmızı. Yanlış seçilen şıkkın notu varsa "Bu şıkkı seçtiysen: …" yazar. Kısa cevapta "Senin cevabın / Beklenen cevap" kutusu.
- [`question_card(item, number, reveal, chosen, verdict, options)`](../src/ui/components.py#L72): kartın tamamı. Başlık (SORU N + tip + zorluk), soru, şıklar; `reveal` ise çözüm adımları, kaynak (belge + sayfa + sarı vurgulu alıntı) ve sistemin kararı.
- [`page_card(item, png, note, reveal)`](../src/ui/components.py#L97): kaynak sayfa kartı. Kanıtın sarıyla işaretlendiği sayfa görüntüsü base64 olarak `<img>` içine gömülür.

---

## `src/ui/quiz.py` — sınav çözme deneyimi (448 satır)

**Ne işe yarar?** Sınav Hazırla sayfasında sınav hazır olunca üç ekranı yönetir:
1. **Başlangıç ekranı:** özet, tahmini süre, kısayollar.
2. **Odak modu:** kenar çubuğu gizli; tek soru, büyük şık düğmeleri, ilerleme çubuğu, süre sayacı, soru haritası, kademeli ipucu, klavye kısayolları.
3. **Sonuç ekranı:** halka grafik, özet kutular, konulara göre başarı grafiği, gözden geçirme, hatalı bildir ve itiraz.

**Bağlantılar**
- ← `pages/exam`.
- → `request` (`record_attempt`, `report`), `grading.grade_short`, `components`, `data`, `style`, `altair`, `pandas`.

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
- [`grade(it, ans)`](../src/ui/quiz.py#L30): cevap doğru mu? ÇS'de şık sırası, D/Y'de değer, kısa cevapta `grade_short`.
- [`topic_of(req, it)`](../src/ui/quiz.py#L44): sorunun konusu. Kanıt sayfası, aramanın hangi konu için bulduğu sayfalar arasındaysa o konu.
- [`view(items)`](../src/ui/quiz.py#L53): ikinci denemede yalnızca yanlışlar.
- [`hints(req, it)`](../src/ui/quiz.py#L59): **kademeli (Sokratik) ipuçları.** 1) Nereye bakmalı (konu + sayfa). 2) Kaynak cümle ya da uygulanacak kural. 3) Hesapta çözümün ilk adımı.

**1. Başlangıç:** [`start_screen(req, items)`](../src/ui/quiz.py#L86): özet kutusu ve "Sınava başla" düğmesi. Düğme fazı `"solve"` yapar.

**2. Odak modu:** [`solve(req, items)`](../src/ui/quiz.py#L195)
- `_FOCUS_CSS` kenar çubuğunu gizler ve içeriği daraltır.
- Üst şerit: ilerleme, süre sayacı, "Çık" düğmesi.
- Soru haritası (`st.pills`): numaraya tıklayıp soruya atlanır, cevaplananlarda ✓.
- Soru kartı ve cevap alanı:
  - ÇS: dört büyük düğme.
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

**3. Sonuç:** [`results(req, items)`](../src/ui/quiz.py#L353)
1. Her soruyu puanla. İlk kez geliniyorsa `record_attempt` ile kaydet (madde analizi); `recorded=True` yap.
2. Doğru / yanlış / boş sayıları (itirazlar doğru sayılır).
3. Özet bloğu:
   - [`_ring`](../src/ui/quiz.py#L290): SVG halka grafik.
   - [`_message`](../src/ui/quiz.py#L310): yüzdeye göre mesaj.
   - Doğru / Yanlış / Boş / Süre kutuları ve ipucu sayısı.
4. Düğmeler:
   - "Yanlışları tekrar çöz": [`restart`](../src/ui/quiz.py#L341) `retry` ile yeni deneme açar.
   - "Baştan çöz" ve "Yeni sınav".
5. [`_topic_chart`](../src/ui/quiz.py#L320): konulara göre yığılmış çubuk grafik (Altair) ve "tekrar etmen gereken konular".
6. Gözden geçirme: her soru kartıyla, ardından:
   - "Hatalı bildir": `request.report`; soru inceleme bitene kadar sınavlardan çıkar.
   - Kısa cevapta "Cevabım doğruydu" itirazı: puana yansır, soru öğretmene gider.

---

## `src/ui/pages/exam.py` — Sınav Hazırla (181 satır)

**Ne işe yarar?** Sistemin ana sayfası. Önce seçim formu gelir; sınav hazırlanınca durum, sınav ve dışa aktarma gösterilir.

**Bağlantılar:** → `request` (`prepare`, `load`, `items_of`, `start`, `save`, `KINDS`), `quiz`, `export`, `data`, `style`.

**İçindekiler**
- `DIFF`: ekrandaki zorluk adı → kod değeri ("Karışık" → `None`).
- [`_builder()`](../src/ui/pages/exam.py#L20): seçim formu.
  1. Belgeler (varsayılan: en çok doğrulanmış sorusu olan).
  2. Konular (konu haritasından; boşsa hepsi).
  3. Zorluk, tipler ("Hesap sorusu" yalnızca formüllü belgede), sayı (5/10/15/20).

  "Sınavı hazırla" düğmesi `R.prepare(...)` çağırır; arama ve havuz eşleştirmesi saniyeler sürer.
- [`_open(req_id)`](../src/ui/pages/exam.py#L57): `session_state.exam`'ı kurar, adres çubuğuna `?sinav=<id>` yazar.
- [`_summary(req)`](../src/ui/pages/exam.py#L64): sınavın özeti ve "Notlarında bulunan kaynak sayfalar" açılır paneli: her konunun aramada bulduğu sayfalar. RAG'in görünür kanıtı budur.
- [`_live(req_id)`](../src/ui/pages/exam.py#L85) (`@st.fragment(run_every=3)`): eksik sorular üretilirken her 3 saniyede istek dosyasını okuyup ilerleme çubuğunu günceller. İş bitince bütün sayfayı yeniler.
- [`_progress_value(text)`](../src/ui/pages/exam.py#L97): `"Doğrulanıyor 3/8"` metninden çubuk değeri.
- [`_status(req, items)`](../src/ui/pages/exam.py#L103): sınava geçilebilir mi?
  - Üretiliyorsa canlı ilerleme.
  - `"partial"` ise "eksik N soruyu üret" (`R.start`) ya da "hazır olanlarla başla".
  - Hiç soru yoksa uyarı.
- [`_export(req, items)`](../src/ui/pages/exam.py#L134): dört indirme düğmesi (sınav kâğıdı, Moodle XML, GIFT, CSV).
- [`render()`](../src/ui/pages/exam.py#L153): sayfanın akışı. Adreste `?sinav=` varsa sınavı açar. Faz `"solve"` ise yalnızca odak modu gösterilir (başlık yok). Değilse başlık → form ya da özet → durum → sonuç ya da başlangıç ekranı → dışa aktarma.

---

## `src/ui/pages/documents.py` — Belgeler (152 satır)

**Ne işe yarar?** Yeni PDF yüklenir ve işlenir. Çalışan işler izlenir. Her belgenin konuları, sayfaları (görüntü + çıkarılan metin) ve okuma kalitesi gösterilir.

**Bağlantılar:** → `data` (`start_job`, `jobs`, `documents`, `topics`, `parsed`), `request` (`all_items`, `usable`), `pymupdf`.

**İçindekiler**
- [`_add()`](../src/ui/pages/documents.py#L21): dosya yükleyici + "Soruların dili" seçimi. PDF `data/sample_docs/`'a kaydedilir; düğmeyle `data.start_job` çağrılır.
- [`_jobs()`](../src/ui/pages/documents.py#L41) (`fragment`, 4 sn): çalışan işlerin adım adı, ilerleme çubuğu ve son satırı. Kota bekleniyorsa "iş duraklamadı" notu.
- [`_detail(tail)`](../src/ui/pages/documents.py#L54): log'un son satırını kullanıcıya uygun metne çevirir ("Gemini'nin kotası dolu, qwen ile tek tek üretiliyor").
- [`_page_png(file, page)`](../src/ui/pages/documents.py#L67): sayfa görüntüsü (85 dpi, önbellekli).
- [`_topics_tab(d)`](../src/ui/pages/documents.py#L72): konu tablosu. Konu, sayfalar ve **hazır soru** sayısı (o sayfalara bağlı doğrulanmış sorular).
- [`_pages_tab(d)`](../src/ui/pages/documents.py#L90): sayfa kaydırıcısı. Solda PDF görüntüsü, sağda sistemin çıkardığı metin ve rozetler (metin katmanı / görselden okundu / bekliyor / bayraklar).
- [`_quality_tab(d)`](../src/ui/pages/documents.py#L114): görselden okunan sayfa, tablosu çıkarılan sayfa, silinen üst/alt bilgi satırı, üretimden çıkarılan sayfalar.
- [`render()`](../src/ui/pages/documents.py#L128): yükleme → işler → belge seçici → üç sekme.

---

## `src/ui/pages/bank.py` — Soru Bankası (84 satır)

**Ne işe yarar?** Bütün sorular süzülebilir bir tabloda. Tabloda öğrenci başarısı (madde güçlüğü) ve inceleme durumu da var; buradan dışa aktarılabilir.

**Bağlantılar:** → `data`, `request` (`KINDS`, `kind`), `components` (`TYPE_TR`, `DIFF_TR`, `type_label`), `export`, `textnorm.pretty_math`.

- [`render()`](../src/ui/pages/bank.py#L14):
  - "Gelişmiş" anahtarları: pilot setleri göster, doğrulanamayanları göster.
  - Süzgeçler: belge, tip, zorluk, metin arama.
  - `st.dataframe` tablosu: "Öğrenci başarısı" ilerleme çubuğu olarak.
  - Beş indirme düğmesi (sınav kâğıdı, Moodle XML, GIFT, CSV, JSON).
- İç fonksiyon `human(q)`: "Onaylandı / Reddedildi / Bildirildi / —".

---

## `src/ui/pages/review.py` — İnceleme (147 satır)

**Ne işe yarar?** Öğretmen ya da kalite kontrol ekranı. Soru kartı ile kanıtın sarıyla işaretlendiği PDF sayfası yan yana durur; altında onay/red kararı ve doğrulama ayrıntıları. Kararlar doğrulayıcının isabetini ölçmeye yarar. Reddedilen soru sınavlara konmaz.

**Bağlantılar:** → `review_store` (`render_evidence`, `save_decision`, `REJECT_REASONS`, `FLAG_TR`), `components`, `data`, `style`.

**İçindekiler**
- `_WIDE`: bu sayfada içerik genişliği artırılır (iki kart yan yana sığsın).
- [`_evidence_png(qid, key)`](../src/ui/pages/review.py#L23) (önbellekli): `render_evidence` ile işaretli sayfa görüntüsü.
- [`_filters()`](../src/ui/pages/review.py#L28): set seçimi (belge setleri önce, en büyük önce), görünüm (İncelenmemiş / İncelenmeli / Bildirilen / Tümü), "Önce kendin çöz" anahtarı (cevabı ve sayfayı gizler).
- [`_pager(idx, n_view, done, total)`](../src/ui/pages/review.py#L46): Önceki / Sonraki + "Bu sette incelenen: X / Y" çubuğu.
- [`_decide(item, source, n_view)`](../src/ui/pages/review.py#L61): red nedenleri, not, Onayla / Reddet / Atla. Karar verilince sonraki soruya geçilir.
- [`_details(item, reveal)`](../src/ui/pages/review.py#L82): üreten ve doğrulayan model, SymPy sonucu, şık kararları, doğrulayıcının kendi cevabı ve gerekçesi, uyarılar.
- [`_advance(n_view)`](../src/ui/pages/review.py#L110): sıradaki soruya geçer.
- [`render()`](../src/ui/pages/review.py#L115): öğrenci bildirimi varsa uyarı gösterir. `.nr-pair` ızgarasında iki kart, altında karar ve ayrıntılar. Sıra `st.session_state.idx`'te tutulur.

---

## `src/ui/pages/report.py` — Rapor (93 satır)

**Ne işe yarar?** İki sekme:
- **Nasıl çalışır:** gerçek sayılarla 6 adımlı akış şeması.
- **Ölçümler:** arama, doğrulayıcı, hesap kontrolü, bilişsel düzey, toplu üretim, insan değerlendirmesi, öğrenci sonuçları.

Her sonuç tekrar çalıştırılabilir bir eval betiğinden gelir.

**Bağlantılar:** → `parts/evaluation` (alt fonksiyonlar), `data`, `request.all_items`, `style.flow`, `pandas`.

- [`_how()`](../src/ui/pages/report.py#L11): açıklama paragrafı ve `style.flow`. Okunan sayfa → konu → parça → üretilen → kod kontrolünden geçen → doğrulanan.
- [`_compute()`](../src/ui/pages/report.py#L37): hesap kontrolü duyarlılığı (`eval/sonuclar_hesap_kontrol.json`).
- [`_students()`](../src/ui/pages/report.py#L56): madde analizi tablosu (en düşük doğru oranı üstte).
- [`render()`](../src/ui/pages/report.py#L79): ölçüm seçici → ilgili fonksiyon. Çoğu `parts/evaluation.py`'den alınır.

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
- [`_human()`](../src/ui/parts/evaluation.py#L168): öğretmen kararları. "Doğrulananlarda kabul" oranı doğrulayıcının isabetidir.
- [`render()`](../src/ui/parts/evaluation.py#L194): **hiç çağrılmıyor.** Eskiden ayrı bir "Değerlendirme" sayfasıydı.

## `src/ui/parts/system.py` — (ölü kod) (85 satır)

Eski "Sistem ve Kota" sayfasının parçası. Kalite kapısı rozetleri, kota çubukları, maliyet. Hiçbir dosya içe aktarmıyor; yerini [`pages/models.py`](../src/ui/pages/models.py) aldı. Silinebilir. (`PRICE` sözlüğü iki dosyada da tekrar ediyor.)

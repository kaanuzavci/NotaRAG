# 14 · Giriş ekranı, odak ekranları, yayımlama düzeltmesi, sınav kâğıdı (2026-10-09)

- **Giriş** (`src/ui/auth.py` + görseller `src/ui/loginart.py`, ikinci tur aynı gün): pencere tam ikiye bölünür
  (`st.columns(2, gap=None)`). Sol yarı koyu bilgi paneli: başlık, 1-2-3 akışı küçük SVG çizimlerle (PDF → kanıtlı soru →
  kartlar ve puan halkası), "Sana özel çalışma" ve "Herkese açık notlar". Sağ yarı: anahtar görünümlü sekmeler (Giriş yap /
  Hesap aç), beyaz yuvarlak alanlar, "ya da" ayracı, **Google ile devam et** (şimdilik yalnızca görünüm: tıklayınca
  "yakında" bildirimi). Arkada tek bir sabit SVG (`loginart.background`): notlardan dallar ortadaki makineye akar, oradan
  soru kartlarına ve iki bilgi ağına ("beyin") gider; kesik çizgiler ve ışık noktaları yavaşça ilerler (SMIL animateMotion),
  hareket azaltma tercihinde durur. Dış kütüphane yok: internetsiz çalışır.
  Tuzak: Streamlit 1.59'da alanlar ve sekmeler baseweb değil → `[data-testid=stTextInputRootElement]`, `[role=tab]`,
  seçili sekmenin alt çizgisi `.react-aria-SelectionIndicator`.
- **Odak ekranları ortalama** (`style.focus_css`): kart oturumu, sınav çözme ve giriş kenar çubuğunu gizliyordu ama ana alan 300 px
  `margin-left`'i tutuyordu → içerik yamuk duruyordu. Artık `stMain` sıfırlanır; kart ve soru alanı büyüdü (`cards.py`, `quiz.py`, `style.py`).
- **Karıştır** (`cards._shuffle`; 2026-10-12'den beri kart oturumu bileşeninin JS'inde, bölüm 8 `flashcards.py`): ekrandaki kart da karışır, yeni kart dağıtılır, bildirim çıkar (eskiden hiçbir şey görünmüyordu).
- **Herkese aç** (`docview._confirm_publish`, `_rename`): açılır kutu (`st.popover`) konu listesinin üstüne biniyordu,
  "Anladım" tıklaması alttaki satıra geçip okuyucuyu açıyor, not yayımlanmıyordu. Şimdi düğmeye basınca aynı yerde (sağ
  sütun) kısa uyarı + "Vazgeç / Herkese aç" çıkar; ayrı kutu yok. Ad değiştirme de aynı yerde (alan + Vazgeç / Kaydet).
- **Pencere kasması**: `backdrop-filter: blur` kaldırıldı (içerik kayarken her karede arka sayfa yeniden bulanıyordu).
- **Sınav kâğıdı** (`src/exampaper.py`, `src/ui/pages/paper.py`): bankadan soru seç → A4 tek/iki sütun, A3 yatay iki/üç sütun →
  PDF + ayrı cevap anahtarı PDF. Yerleşim: soru bölünmez, yazı boyu en az sayfaya sığacak en büyük boy (PyMuPDF `insert_htmlbox`).
  Ölçüm de `insert_htmlbox` ile yapılır (`Story.place` ~%40 büyük ölçüyordu). Test: `python -m tests.test_exampaper`.
- **Sınav kâğıdı başlığı** (ikinci tur): ilk sayfanın başlığı ortalı — isteğe bağlı **üst yazı** (kurum, fakülte, dönem;
  her satır ayrı), başlık, ders · tarih · süre · soru sayısı, Ad Soyad / Numara / Puan satırı, açıklama (çok satır). Son
  sorunun ardından isteğe bağlı ortalı **sınav sonu yazısı** (`Meta.top`, `Meta.end`). Başlığın yüksekliği ölçülür, sorular
  hemen altından başlar. Soru Bankası'ndaki "Dışa aktar"da bu sayfaya bağlantı var.

## Üçüncü tur (2026-10-09 akşamı)

- **Giriş ekranı kaymaz**: her şey bir pencereye sığar (`overflow: hidden`; çok alçak ekranda yalnızca sağdaki form kendi
  içinde kayar). Form artık ayrı bir kutu değil: sağ yarının kendisi giriş alanı, dikey ve yatay ortalı; arkadaki ağ formun
  durduğu yerde kâğıt rengine söner (`loginart`, `lgcalm`), altta küçük alt bilgi satırı. Sol panelde logo, etiket, başlık ve
  açıklama yukarıda; akış ve özellikler altta, aralarında boşluk. Hesap aç'ta iki parola alanı yan yana.
  Tuzaklar: gizli stil blokları sütunları ~65 px aşağı itiyordu (`stVerticalBlock` gap 0); `height: 100vh` Streamlit'in
  kuralına yeniliyor → `min-height` + `max-height`.
- **Klasörler** (`library.folders / create_folder / rename_folder / delete_folder / move_to_folder`; veritabanı adım 3:
  `folders`, `folder_docs`): kişiye özel; bir not bir kişide en çok bir klasörde. Belgeler'de "Klasör oluştur" penceresi
  (ad + not seçimi; başka klasördeki not seçilirse taşınır), klasör kartı (`shelf.folder_card`: açık kahve dosya klasörü,
  içinden notların kapakları görünür), klasörün içi (← Belgeler, Düzenle, Sil — silinince notlar silinmez). Ana görünümde
  klasördeki notlar ayrıca görünmez; arama klasörlerin içini de arar. Test: `tests.test_accounts → test_folders`.
- **Sınav kâğıdı süzgeçleri**: Not / Tip / Zorluk çoklu seçim kutuları seçtikçe uzayıp aşağıyı itiyordu → sabit boyutlu
  açılır düğmeler (`paper._filter`, içinde st.pills; düğmede "Tip: Hesap" ya da "Not · 2"), "Süzgeçleri temizle".
- **Kenar çubuğu kapanınca** (`style.py`): ana alan pencerenin tamamına yayılır, içerik yumuşakça ortaya kayar. Ana sayfa ve
  Belgeler'de içerik genişliği sabit (`min(1320px, 100vw − 300px)`): kartlar büyüyüp küçülmez, yeniden dizilmez.

## Dördüncü tur (2026-10-09, akşam)

- **Klasör oluşturma artık ayrı pencere açmaz**: "Klasör oluştur" sayfayı seçim kipine geçirir. Kartların köşesinde işaret
  dairesi belirir (tıklayınca ✓), üstte klasörün adı yazılır, "Klasörü oluştur · N not" ile biter (ad boşsa ya da hiç not
  işaretlenmemişse düğme kapalı). "Düzenle" de aynı kip: ad ve işaretler dolu gelir. Başka klasördeki notun kartında "Klasörde"
  etiketi var; işaretlenirse oradan taşınır. İşaretler bileşenin durumudur (`shelf.py`: `setStateValue("sel")`, Python
  `st.session_state[anahtar]["sel"]`'i sayfayı çizmeden önce okur → sayaç ve düğme güncel); her girişte yeni bileşen anahtarı
  (`docs_select["n"]`) → eski işaretler karışmaz. Kartlar işaret değişince yeniden çizilmez (`stable(data)` imzadan `selected`'ı atar).
- **Giriş ekranı**: sol panelde başlık grubu ile akış / özellikler artık birlikte, logonun altındaki alanın dikey ortasında
  (aralarında sabit 5,5vh boşluk). Sağdaki form pencerenin sağ yarısının tam ortasında (önceden sola yaslıydı:
  `margin: auto` yoktu), biraz büyüdü (460 px, 52 px alanlar, 54 px düğmeler).

## Beşinci tur (2026-10-09 gecesi): pazardaki araçlardan seçilen beş ekleme

- **Kaynağı aç** (`reader.open_source`): sınav sonucundaki her sorunun yanında ve bilgi kartının altında. Notun kanıt
  sayfası tam ekran okuyucuda açılır, kanıt cümlesi sarıyla işaretli (`reader.page_jpeg(..., mark=alıntı)`, eşleştirme
  İnceleme sayfasıyla aynı: `review_store._highlight_rects`; PDF'in kendisi değişmez). Esc ile aynı yere (sonuç ekranı ya da
  aynı kart) dönülür: `exam.py` ve `cards.py` okuyucu açıkken yalnızca okuyucuyu çizer.
- **A / B kitapçığı** (`exampaper.booklet_b`): sorular kendi türü içinde yer değiştirir, çoktan seçmeli şıklar karışır
  (şık notları ve şık değerleri de aynı sırayla). Tür yuvaları aynı kaldığı için tek optik form iki kitapçıkta da geçer.
  Sınav Kâğıdı'nda "A / B kitapçığı" anahtarı → iki kâğıt, iki önizleme sekmesi; cevap anahtarında iki tablo, ayrıntılarda
  "B kitapçığında N. soru".
- **Optik form** (`exampaper.build_sheet`): A4; ad-soyad, imza, kitapçık türü, 10 haneli öğrenci numarası ızgarası, her soru
  için A-D (doğru/yanlışta D-Y) yuvarlakları, kısa cevaplılara "yazılı" kutusu; en çok 4 sütun, satır yüksekliği kalan yere göre.
- **Belirtke tablosu** (`exampaper.blueprint`): konu × Bloom düzeyi ve zorluk, soru sayısı ve puan. Sınav Kâğıdı'nda sekme,
  cevap anahtarının ilk sayfasında tablo.
- **FSRS-5 aralıklı tekrar** (`src/cards.py`): Leitner kutularının yerine. Her kartın kararlılığı S (gün) ve zorluğu D;
  Bildim → S büyür (ilk 3 gün, sonra 11, 35, 101…; geç tekrar edilip bilinen kart daha çok büyür), Bilemedim → bugün yine,
  D artar. Sonraki tekrar hatırlama olasılığı %90'a inince. Deste unutulmaya en yakın kartla başlar. Varsayılan FSRS-5
  parametreleri (kişiye göre eğitilmedi). Kayıt biçimi aynı: eski değerlendirmeler geçmiş oynatılınca FSRS'le yeniden
  hesaplanır; `box` geriye uyum için S'den türetilir (profilin bellek özeti ve ustalık durumu).
- Testler: `tests.test_cards` (FSRS), `tests.test_exampaper` (kitapçık, optik form, belirtke). AppTest'le Sınav Kâğıdı'nda
  A/B anahtarı → 4 sekme, 4 indirme. Not: görünmez Edge'de `st.toggle`'a gerçek fare tıklaması işlemiyor (react-aria);
  anahtarlı akışları AppTest'le dene.

## Altıncı tur (2026-10-09 gecesi): kart çalışma ekranı

`src/ui/pages/cards.py` (`SESSION_CSS`, `_progress`, `_mood`, `VIVID`). Önceki "figürsüz, sakin" kararı bu ekran için
kullanıcı isteğiyle değişti (diğer ekranlarda geçerli).
- **Üst şerit:** kart başına bir parça (bilinen yeşil, bilinemeyen kırmızı, atlanan lila); parçanın üstünde o kartın yüzü
  (`_mood`: seri uzadıkça 🙂 😊 😄 😁 😎 🤩 🥳; bilemeyince 😕, seri bozulduysa 😓, üst üste 😢 😭; atlayınca 🤔), az önce
  değerlendirilen yüz zıplayarak gelir; sıradaki kartta sallanan 🤔 ve kayan çizgili parça; sonda 💯 (ilerledikçe
  belirginleşir, son iki kartta parlar). Yüzler `cs["log"]`'da saklanır (parça başına sabit kalsın); üst üste bilememe `cs["miss"]`.
- **Sağında ayrı göstergeler:** 🎯 isabet (yeşil / sarı / pembe zemin, orana göre), 🔥 seri (seri büyüdükçe alev büyür ve
  hızlanır, 5+ "sıcak" zemin; seri 0'da gri ve durgun).
- **Kart:** canlı renk paleti (`VIVID`, yazı her zeminde ≥ 6:1), ön kart hafif çapraz (-1,4°) gelir, arkada 3'e kadar
  çapraz duran sıradaki kart (sıradaki kartların renkleri).
- **Karıştır / Bitir:** kartın sağında, kartla aynı hizada iki büyük düğme.
- **Notta kaynağını aç:** sol altta çapraz duran sarı not kâğıdı (bant, çizgiler), üzerine gelince sallanır; dar ekranda
  akışa iner. Alttaki "Bildim → N gün sonra · kısayollar" satırı kaldırıldı (klavye kısayolları çalışmaya devam ediyor).
- **Arka plan:** sabit, soluk mor / nane / turuncu / pembe ışık lekeleri.
- Deneme: `scripts/onizleme.py` (`?v=session`, kart değerlendirmeleri geçici dosyaya gider) üzerinde gerçek tıklamalarla
  seri ve bilememe senaryoları; son bakış `tasarim.py` ile (değerlendirme yapmadan).

---

## Dosya dosya (2026-10-11 eklendi)

Yukarıdaki turlar değişiklik günlüğü gibi yazıldı; yeni dosyaların işlevleri burada tek tek.

### `src/exampaper.py` — basılı sınav kâğıdı (482 satır)

**Ne işe yarar?** Soru bankasından seçilen soruları A4 / A3 kâğıda şablonla yerleştirip PDF üretir: sınav kâğıdı (isteğe bağlı A ve B kitapçığı), ayrı cevap anahtarı, optik cevap kâğıdı, belirtke tablosu. Arayüzden bağımsızdır (Streamlit yok), LLM çağrısı yoktur. Neden PDF ve neden PyMuPDF: kâğıdın boyu, sütunları ve sayfa sonları kesin olsun; yeni bağımlılık gerekmesin (`Page.insert_htmlbox` HTML + CSS'i doğrudan sayfaya yazar, Türkçe harfler ve matematik simgeleri gömülü yazı tiplerinde var).

**Bağlantılar:** ← `ui/pages/paper.py`, `tests/test_exampaper`. → `textnorm.pretty_math`, `export._topic` (belirtkede konu adı), `pymupdf`.

**İçindekiler**
- [`Template`](../src/exampaper.py#L41) (donmuş veri sınıfı) ve `TEMPLATES`: dört şablon — `a4_1` (A4 tek sütun, 10-20 soru), `a4_2` (A4 iki sütun, 20-30), `a3_2` (A3 yatay iki sütun), `a3_3` (A3 yatay üç sütun). Her şablonun kâğıdı, sütun sayısı, en büyük ve en küçük yazı boyu (`font_max`, `font_min`), hedef sayfa sayısı ve önerilen soru aralığı (`advice`) var.
- [`Meta`](../src/exampaper.py#L63): kâğıdın başlığı ve ayarları: `title`, `course`, `date`, `minutes`, `note` (yönerge), `top` (en üstte ortalı serbest yazı: kurum, bölüm, dönem), `end` (son sorudan sonra ortalı yazı), `points` (her sorunun puanı yazılsın: 100 / soru sayısı), `name_box` (ad-soyad / numara / puan satırı), `by_type` (çoktan seçmeli → doğru-yanlış → kısa cevap sırası).
- Sabitler: `LETTERS` (A-E), `BLOOM_TR`, `DIFF_TR` (etiketlerin Türkçesi), `INK` (yazı rengi).
- Küçük yardımcılar: [`_e`](../src/exampaper.py#L76) (kaçışlı ve `pretty_math`'lı metin), [`_lines`](../src/exampaper.py#L80) (çok satırlı metin → `<br>`'lü HTML, boş satırlar atılır), [`_points`](../src/exampaper.py#L87) (soru başına puan: `100 / n`, tam sayı değilse bir ondalık ve virgül).
- [`_question_html(n, it, meta, total)`](../src/exampaper.py#L92): bir sorunun HTML'i: "N. soru (puan p)"; çoktan seçmelide A) B) C) şıkları; doğru/yanlışta "( ) Doğru ( ) Yanlış"; hesap sorusunda "Cevap: ____"; kısa cevapta iki yazı çizgisi. [`_css(font)`](../src/exampaper.py#L107) yazı boyuna göre aralıkları verir.
- **Yerleşim:**
  - [`_measure(html_, width, css)`](../src/exampaper.py#L120): bir bloğun gerçek yüksekliği. `Story.place()` ölçümü çizimden ~%40 büyüktü (gövde kenar boşlukları), bu yüzden ölçüm de çizimle aynı yoldan yapılır: boş bir deneme sayfasına `insert_htmlbox` ile çizilir, artan yükseklik çıkarılır. [`_scratch()`](../src/exampaper.py#L132) o deneme belgesini tutar (400 sayfayı geçince yenilenir).
  - [`_geometry(t)`](../src/exampaper.py#L140): kâğıt boyu (yataysa en-boy yer değiştirir), kenar boşluğu (A4 36 pt, A3 42 pt), sütun arası 18 pt, sütun genişliği, başlık bandı ve alt bilgi yüksekliği.
  - [`_layout(blocks, font, t, g)`](../src/exampaper.py#L152): soruları sırayla `(sayfa, sütun, y, yükseklik)` olarak yerleştirir. **Bir soru iki sütuna ya da sayfaya bölünmez:** sığmazsa sonraki sütunun başına geçer.
  - [`_fit(blocks, t, g)`](../src/exampaper.py#L171): `font_max`'tan başlayıp yarım punto adımlarla küçülerek **en az sayfaya sığdıran en büyük** yazı boyunu seçer; `font_min`'de durur (okunmayacak kadar küçük kâğıt çıkmasın), sığmazsa sayfa eklenir.
- [`_head_html(meta, n, booklet)`](../src/exampaper.py#L184) ve `_HEAD_CSS`: ilk sayfanın ortalı başlığı: üst yazı, başlık, "ders · tarih · süre · soru sayısı · A kitapçığı", ad-soyad satırı, yönerge.
- [`_order(items, by_type)`](../src/exampaper.py#L207), [`prepare(items, meta)`](../src/exampaper.py#L214): kâğıttaki soru sırası (A kitapçığı); tür sıralaması kararlıdır (tür içinde seçim sırası korunur).
- [`build_exam(items, template, meta, booklet)`](../src/exampaper.py#L219): sınav kâğıdı PDF'i → `(pdf, bilgi)`; bilgi: sayfa sayısı, yazı boyu, kâğıt, soru sayısı. Başlığın yüksekliğini ölçüp soruları hemen altından başlatır, sınav sonu yazısını (`meta.end`) son blok olarak koyar, sütun ayraçlarını, başlık altı çizgisini ve her sayfanın altına "Başlık · Sayfa n / N · NotaRAG" yazar. Soru yoksa `ValueError`.
- [`_answer_text(q)`](../src/exampaper.py#L262), [`_short(q)`](../src/exampaper.py#L270): cevabın tam metni / özet tablodaki kısa hâli (şık harfi, Doğru / Yanlış ya da cevabın ilk 14 karakteri).
- [`_kind(it)`](../src/exampaper.py#L275): optik formdaki yuva türü: `mc`, `tf`, `sa` (kısa cevap ve hesap "yazılı").
- [`_shuffle_options(it, rnd)`](../src/exampaper.py#L280): şıkları karıştırır (doğru cevabın yeri değişir); şık notları ve şık değerleri aynı sırayla taşınır, öbür türler olduğu gibi kalır.
- [`booklet_b(items, seed)`](../src/exampaper.py#L298): A'dan B kitapçığı: sorular **kendi türü içinde** yer değiştirir (tür yuvaları aynı kalır → tek optik form iki kitapçıkta da geçer) ve şıklar karışır.
- [`blueprint(items)`](../src/exampaper.py#L312) ve `_blueprint_html`: **belirtke tablosu**: konu × bilişsel düzey (Bloom) ve zorluk, soru sayısı ve puan; her soru eşit puanlı, toplam 100.
- [`build_key(items, meta)`](../src/exampaper.py#L349): cevap anahtarı PDF'i (A4): belirtke tablosu, özet tablo(lar), her sorunun cevabı, çözümü ve kaynak cümlesi. Tek liste ya da `{"A": …, "B": …}` kitapçıkları alır; B'de ayrıntıda "B kitapçığında N. soru" yazar. **Ayrı dosya olması bilinçli:** öğrenciye verilen kâğıtta cevap bulunmasın.
- [`build_sheet(items, meta, booklets)`](../src/exampaper.py#L403): optik cevap kâğıdı (A4): ad-soyad, imza, kitapçık türü, 10 haneli öğrenci numarası ızgarası, her soru için A-D (doğru/yanlışta D-Y) yuvarlakları, kısa cevaplılara "yazılı" kutusu; en çok 4 sütun, satır yüksekliği kalan yere göre.
- [`previews(pdf, dpi)`](../src/exampaper.py#L478): her sayfanın PNG önizlemesi (arayüzde kâğıdı indirmeden görmek için).

### `src/ui/pages/paper.py` — Sınav Kâğıdı sayfası (264 satır)

**Ne işe yarar?** Üç adım tek sayfada: 1 · Sorular (süz, tek tek ya da rastgele seç) → 2 · Kâğıt (şablon, başlık, ders, tarih, süre, A / B anahtarı) → 3 · Önizleme ve indirme (kâğıt, ayrı cevap anahtarı, optik form, belirtke). Kâğıt her değişiklikte yeniden yerleştirilir (yarım saniye). Seçilebilen sorular: doğrulanmış, insanın reddetmediği, hatalı bildirilmemiş ve kişinin görebildiği notlardan.

**İçindekiler**
- `TYPES`: kâğıda konabilecek soru tipleri → Türkçe ad. **Şimdilik yalnızca çoktan seçmeli** (kullanıcı kararı 2026-10-12; doğru / yanlış ve kısa cevap sonra); "Tip" süzgecinin seçenekleri bankadaki tiplerden.
- [`_bank(visible)`](../src/ui/pages/paper.py#L24) (30 sn önbellek): kâğıda konabilecek sorular, satır sözlükleri olarak. Sorunun konusu: kanıt sayfasını içeren konu haritası konusu, yoksa üretim birimi. Hesap sorusu türü "Hesap" görünür.
- [`_paper(ids, template, meta, shuffle_seed, booklets)`](../src/ui/pages/paper.py#L42) (60 sn önbellek): bütün çıktıları üretir (kitapçık(lar), cevap anahtarı, optik form, belirtke ve önizlemeler) — `exampaper` fonksiyonlarını sırayla çağırır.
- [`_filter(bar, label, key, options, fmt, icon)`](../src/ui/pages/paper.py#L61): sabit boyutlu süzgeç düğmesi: tıklayınca seçenekler açılır (`st.pills`); düğmede seçili sayı ya da tek seçimin adı yazar. Çoklu seçim kutuları seçtikçe uzayıp aşağıyı itiyordu, bu yüzden böyle.
- [`_clear_filters()`](../src/ui/pages/paper.py#L70), [`_select(ids, on)`](../src/ui/pages/paper.py#L76), [`_random(ids, n)`](../src/ui/pages/paper.py#L82): süzgeçleri sıfırlar; verilen soruları seçer / bırakır; rastgele `n` soru seçer. Seçim `st.session_state.pp_sel` kümesindedir, `pp_ver` artınca tablo yeni seçimle baştan çizilir.
- [`render()`](../src/ui/pages/paper.py#L87): sayfanın kendisi. Hiç soru yoksa Belgeler'e yönlendirir.
- [`_blueprint(bp)`](../src/ui/pages/paper.py#L242): belirtke tablosunu `st.dataframe` olarak çizer.
- [`_slug(s)`](../src/ui/pages/paper.py#L258): indirilen dosyanın adı için Türkçe harfleri ASCII'ye çevirip özel karakterleri `_` yapar.

### `src/ui/loginart.py` — giriş ekranının görselleri (203 satır)

**Ne işe yarar?** Giriş ekranının (`ui/auth.py`) arka planı ve sol paneli. Hepsi satır içi SVG + CSS: dış kütüphane ya da internet gerekmez. Arka plan tek SVG (1600×1000, pencereyi "slice" ile doldurur): sol yarı koyu lacivert bilgi paneli, solda not yaprakları → dallar → ortadaki makine (dönen halka) → sağda soru kartları → sağ üstte ve altta bilgi ağına ("beyin") bağlanır. Kesik çizgiler akar, birkaç dalda ışık noktası gider (SMIL `animateMotion`); hareket çok yavaş ve soluk, `prefers-reduced-motion`'da durur.

**İçindekiler**
- `SEAM`: makinenin durduğu nokta (iki yarının birleştiği yer).
- [`_curve(a, b, bend)`](../src/ui/loginart.py#L19): iki nokta arasında SVG eğri yolu (`C` komutu).
- [`_note(x, y, s, rot)`](../src/ui/loginart.py#L25), [`_qcard(x, y, s)`](../src/ui/loginart.py#L33): arka plandaki not yaprağı / soru kartı çizimleri.
- [`_brain(cx, cy, r, seed)`](../src/ui/loginart.py#L41): "beyin": iki lobda düğümler ve aralarında bağlar; `seed` ile aynı çizim her seferinde aynı çıkar. Düğüm noktalarını da döndürür (dallar oraya bağlanır).
- [`background()`](../src/ui/loginart.py#L59): bütün arka plan SVG'si. Yaprak ve kart konumları yazıların üstüne binmesin diye sol panelin kenarlarına ve formun durduğu orta alanın dışına yerleştirilmiş. `BG_CSS` animasyonları (`lg-flow`, `lg-pulse`, `lg-spin`) verir.
- [`brand()`](../src/ui/loginart.py#L152): sol panelin HTML'i: logo, başlık, 1-2-3 akışı (PDF → kanıtlı soru → çalış) küçük SVG çizimlerle, "Sana özel çalışma" ve "Herkese açık notlar". `BRAND_CSS` biçimini verir; dar ekranda akış alt alta iner.

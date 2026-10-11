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
- **Karıştır** (`cards._shuffle`): ekrandaki kart da karışır, yeni kart dağıtılır, bildirim çıkar (eskiden hiçbir şey görünmüyordu).
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

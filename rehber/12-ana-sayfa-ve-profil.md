# 12. Ana sayfa, profil ve beyin analizi

[← Rehber ana sayfa](README.md) · Önceki: [11. Hesaplar ve belge kütüphanesi ←](11-hesaplar-ve-belgeler.md) · Sonraki: [13. Not penceresi ve okuyucu →](13-not-penceresi-ve-okuyucu.md)

Bu bölüm 2026-10-08'de eklenen kişisel çalışma ekranlarını anlatıyor:

- [`ui/pages/home.py`](../src/ui/pages/home.py): ana sayfa (giriş yapınca ilk açılan sayfa).
- [`ui/shelf.py`](../src/ui/shelf.py): kart desteleri (ana sayfa ve Belgeler). Streamlit'in özel bileşeni (CCv2).
- [`ui/upload.py`](../src/ui/upload.py): not yükleme akışı (ana sayfadaki "+ Yeni not ekle" penceresi; Belgeler'deki yükleme kutusu 2026-10-08 akşamı kaldırıldı).
- [`ui/pages/profile.py`](../src/ui/pages/profile.py): profil ve beyin analizi.
- [`mastery.py`](../src/mastery.py): beyin analizinin hesabı (LLM yok).
- [`resume.py`](../src/resume.py): "kaldığın yerden devam et".

Örnek alınan sistemler:
- **NotebookLM:** not defteri ızgarası. İlk kart "+ Yeni", sonra kişinin defterleri, altında öne çıkanlar.
- **Quizlet:** "kaldığın yerden devam et" satırı.
- **Anki / Leitner:** bellek kutuları.

Tasarım ilkesi değişmedi: kâğıt zemin, lacivert mürekkep, sakin. Hareket yalnızca bir anlam taşıyınca kullanılıyor: üzerine gelince deste açılır ve eylemler görünür; işlenen notun ilerleme çubuğu canlıdır.

---

## `src/ui/pages/home.py` — ana sayfa (~200 satır)

> 2026-10-08 akşamı değişti (bölüm 13): kısa selam satırı, daha büyük kartlar, raflar en çok 2 / 1 satır ve "Tümünü gör", karta tıklayınca pencere bu sayfanın üstünde açılır. Kart verisi ve tıklama yönlendirmesi [`ui/docview.py`](../src/ui/docview.py)'ye taşındı.

**Ne işe yarar?** Yukarıdan aşağı:
1. **Selam satırı** (az yer tutsun, sahne kartların): profil resmi, "İyi günler, Kaan", sayı hapları ("5 not · 188 hazır soru · 137 kart"). Tekrar zamanı gelen kart varsa sağda **"Bugünün tekrarı"** düğmesi: o kartlarla (en çok 30) hemen bir oturum açar.
2. **Ders notların:** dikey kart desteleri, **en çok iki satır**. İlki "+ Yeni not ekle", sonra kişinin kendi listesindeki notlar (en yeni önce), son yer **"Tümünü gör"** → Belgeler ("Notlarım" seçili).
3. **Herkese açık notlar:** herkesle paylaşılan notlar, kişinin kendi paylaştıkları da (başkasınınkinde "Notlarıma ekle", "Göz at"), bir satır. İlk kart hep **"+ Herkese açık not ekle"** (hiç açık not yokken de); son kart "Tümünü gör" → Belgeler ("Herkese açık" seçili).
4. **Kaldığın yerden devam et:** en son yarım kalan kart oturumu ve sınav, yan yana. Yoksa boş kart ve "Kartlara git" / "Sınav hazırla".

**Bağlantılar**
- ← `app.py` (varsayılan sayfa).
- → `shelf` (çizim, `all_card`), `docview` (not kartı, tıklama, pencere, okuyucu), `upload` (pencere), `resume`, `request` (`load`, `items_of`), `data` (`documents`, `doc_meta`, `jobs`, `mine`, `mastery`, `home_stats`, `due_cards`, `items`, `avatar_b64`).
- Yönlendirdiği sayfalar: `documents` ("Tümünü gör"), `exam` ("Sınav", yarım sınav), `cards` ("Kartlar", yarım oturum, bugünün tekrarı). Karta tıklamak sayfa değiştirmez: pencere burada açılır.

**İçindekiler**
- `_CSS`: sayfaya özgü daha geniş içerik alanı (en çok 1320 px), kartlara yer açmak için.
- [`_ago(t)`](../src/ui/pages/home.py#L25): "az önce", "12 dk önce", "dün"…
- [`_greeting()`](../src/ui/pages/home.py#L38): saate göre "Günaydın / İyi günler / İyi akşamlar".
- [`_resume_cards(items)`](../src/ui/pages/home.py#L43): iki "kaldığın yer" kartı. Kart oturumunda kaçıncı kartta olunduğu ve bildim/bilemedim sayısı; sınavda kaç sorunun cevaplandığı. Sınavın belgeleri artık görünmüyorsa gösterilmez.
- [`_new_note()`](../src/ui/pages/home.py#L77) (`@st.dialog`): "Yeni not ekle" penceresi (`upload.uploader`).
- [`_see_all(which)`](../src/ui/pages/home.py#L108): "Tümünü gör" → Belgeler; hangi süzgecin seçili geleceği `session_state.docs_filter`'da.
- [`_resume(ident)`](../src/ui/pages/home.py#L114): yarım kart oturumu ya da sınav: kayıtlı durum `session_state`'e konur, ilgili sayfaya gidilir (sınavda `resume.restore_exam`).
- [`_review_today(ids)`](../src/ui/pages/home.py#L129): bugünün tekrarı. Kart sayfasının sınav sonucundan gelen `cards_preset` yolunu kullanır.
- [`_section(title, sub, count)`](../src/ui/pages/home.py#L138): bölüm başlığı (`.nr-shelf-h`: başlık, sayı hapı ve yanında kısa açıklama tek satırda).
- [`_hello()`](../src/ui/pages/home.py#L144): selam satırı ve bugünün tekrarı düğmesi.
- [`_mine_shelf()`](../src/ui/pages/home.py#L162), [`_public_shelf()`](../src/ui/pages/home.py#L183): iki raf (`rows=2` / `rows=1`, son kart `all_card`). Tıklama: "+ Yeni" → yükleme penceresi, herkese açık raftaki "+" → [`_share_note()`](../src/ui/pages/home.py#L83) (kendi gizli notlarından birini herkese aç, geri alınamaz uyarısıyla; ya da yeni not yükle), "Tümünü gör" → Belgeler, diğerleri `docview.act`. Kişinin işlenen bir notu varsa raf `st.fragment(run_every=5)` içinde çizilir: ilerleme kendiliğinden güncellenir, sayfanın geri kalanı yeniden çalışmaz.
- [`render()`](../src/ui/pages/home.py#L206): tam ekran okuyucu açıksa yalnızca onu çizer; değilse selam → raflar → kaldığın yer → (açıksa) not penceresi (`docview.show`).

---

## `src/ui/shelf.py` — kart desteleri (Streamlit özel bileşeni, ~330 satır)

**Ne işe yarar?** İki görünümü çizer:
- `layout="grid"`: dikey not desteleri (ana sayfadaki raflar ve Belgeler ızgarası).
- `layout="resume"`: yatay "kaldığın yer" kartları.

**Neden özel bileşen?** Streamlit düğmeleri kart biçiminde çizilemiyor. Düz HTML ise tıklamayı Python'a iletemiyor: bir bağlantı sayfayı yeniden yükler ve "beni hatırla" seçili değilse oturum düşer. **CCv2** (Custom Components v2):
- iframe kullanmaz, ana sayfada kendi **Shadow DOM** kabuğunda çizilir; stiller sayfaya taşmaz, sayfanınkiler de içeri girmez;
- yazı tipleri (Fraunces, Instrument Sans, JetBrains Mono) belge düzeyinde yüklü olduğu için kabuğun içinde de çalışır;
- JS tarafı tıklamayı `setTriggerValue("action", "kimlik|eylem")` ile bildirir. Python bir sonraki çalıştırmada bunu `shelf()`'in dönüş değeri olarak alır; tetikleyici bir çalıştırma sonra kendiliğinden sıfırlanır.

**Görünüm (CSS, `_CSS`)**
- **Boyut ve sütun:** kart genişliği ~230-300 px, oranı 3:4. Sütun sayısını JS bileşenin genişliğinden hesaplar (`colsFor`: kart en az ~228 px + 28 px aralık, en çok 4 sütun; geniş ekranda kart büyür, sayısı artmaz). Kenar çubuğu açılıp kapanınca `ResizeObserver` yeniden dizer. 1440 px ekranda kenar çubuğu açıkken 4 sütun (~233 px), kapalıyken 4 sütun (~277 px); 1280 px'te 3 sütun.
- **Satır sınırı:** `rows` verilirse raf en çok o kadar satır olur ve son yer "Tümünü gör" kartıdır (notların renklerinden dört küçük kart yelpazesi + ok; üzerine gelince yelpaze açılır, ok sağa kayar).
- **Deste:** üstteki kart bir ders fişi:
  - renkli kapakta ince çapraz çizgiler ve notun baş harfi (Fraunces; boyutu kart genişliğiyle büyür, `cqi`);
  - altta mavi satır çizgileri, pembe kenar boşluğu çizgisi ve notun ilk üç konusu;
  - arkasında çapraz duran iki yaprak (`.s1` +3°, `.s2` −3,8°).
- **Üzerine gelince:** kart kalkar (`translateY(-9px) rotate(-.7deg)`), arka yapraklar yelpaze gibi açılır, "Sınav / Kartlar" düğmeleri alttan belirir (ilerleme satırının yerine). Klavyeyle odaklanınca da aynısı olur (`:focus-visible`).
- **Dokunmatik ekran** (`hover: none`): düğmeler hep görünür.
- **Hareketi azalt** tercihi: animasyon yok.
- **"Yeni not":** kesik çizgili çerçeve, lacivert yuvarlak "+"; üzerine gelince "+" 90° döner.
- **"Kaldığın yer":** solda küçük çizim (deste ya da işaretli sınav kâğıdı; CSS ile çizilir, resim yok), başlık, ilerleme çubuğu ve "Devam et →" düğmesi. Boşsa kesik çizgili ve soluk.
- **Sayfa açılışı:** kartlar sırayla (45 ms arayla) belirir; sonraki yeniden dizilişlerde (genişlik, canlı ilerleme) animasyon oynamaz (`.still`). Veri ve sütun sayısı değişmedikçe JS yeniden çizmez (`root.dataset.sig`); böylece üzerine gelme durumu her tıklamada sıfırlanmaz.

**İçindekiler**
- `_CSS`, `_HTML`, `_JS`: bileşenin kendisi. Simgeler (kilit, dünya, artı, ok, yenile) satır içi SVG.
  - `esc()`: kullanıcının verdiği adlar HTML'e kaçışla girer.
  - `colsFor()`: sütun sayısı. `stackCard` / `resumeCard`: kartları çizer ("yeni", "tümünü gör" ve not kartı).
  - Tıklama ve Enter/Boşluk aynı yoldan tetikler.
- [`Component`](../src/ui/shelf.py#L457): CCv2 bileşeni kaydı (raf, okuyucu ve konu listesi ortak). Kayıt çalışma ortamına (Runtime) bağlı; modül bir kez yüklendiği hâlde ortam yeniden kurulursa kayıt yoksa yeniden kaydedilir (test aracı `AppTest` böyle bir durumda "kayıtlı değil" hatası veriyordu).
- [`palette(key, order)`](../src/ui/shelf.py#L476): notun rengi. Kütüphaneye giriş sırasından alınır (`library.all_docs` → `order`): ardışık notlar farklı renk alır ve renk, süzme ya da sıralama değişse de aynı kalır. İlk denemede kimliğin özetiyle seçiliyordu; altı notun beşi iki renkte toplandı.
- [`all_card(palettes, sub)`](../src/ui/shelf.py#L483): "Tümünü gör" kartının verisi.
- [`shelf(items, key, layout, empty, rows, more)`](../src/ui/shelf.py#L488): bileşeni çizer; tıklandıysa `(kimlik, eylem)`, yoksa `None`. "Tümünü gör"ün kimliği `all`.

---

## `src/ui/upload.py` — not yükleme (71 satır)

**Ne işe yarar?** Belgeler sayfasındaki eski yükleme kodunun ortak modüle taşınmış hâli.

**İçindekiler**
- [`uploader(key)`](../src/ui/upload.py#L16): dosya seçici, soru dili, `library.register` (dosya başına bir kez), sonuç. İşleme başlatıldıysa `True` döner; çağıran pencereyi kapatıp sayfayı yeniler. `key` iki yerin durumunu ayırır (`docs_up`, `home_up`).
- [`_result(res, lang, key)`](../src/ui/upload.py#L41): yeni not → "notunu işle"; sistemde var → "listene eklendi, yeniden işlenmeyecek"; istenen dilde soru yoksa "… sorular da üret".
- [`start(file, lang, key)`](../src/ui/upload.py#L66): `data.start_job` ile işi başlatır.

---

## `src/ui/pages/profile.py` — profil ve beyin analizi (269 satır)

**Ne işe yarar?**
- **Profil:** profil resmi (yoksa adın baş harfleri kişiye özgü pastel zeminde), ad, kullanıcı adı, katılım ayı, kısa tanıtım. "Profili düzenle" penceresi.
- **Özet kutuları:** not sayısı, cevaplanan soru, doğru oranı, değerlendirilen kart.
- **Beyin analizi:** üç panel ve konu haritası.
  - *Bildiğin sorular:* büyük sayı; altında bellek çubuğu (kısa süreli / pekişiyor / uzun süreli).
  - *Son 14 gün:* her gün bir kare, koyuluk çalışma sayısı.
  - *Zayıf konuların:* en çok dört konu ve **"Bu konulardan sınav hazırla"** düğmesi.
  - *Konu haritası:* her not için konu kutuları.
- **Hesap:** "Parolanı değiştir" (önce şu anki parola).

**Renk kararları (dataviz kuralları)**
- **Konu durumu** bir durum kodlaması: öğrenildi yeşil, çalışılıyor amber, zayıf kırmızı, başlanmadı nötr gri.
  - Renk tek başına anlam taşımaz: her kutuda simge (✓ ◐ ! ○) ve sayı (bildiğin/toplam), üstte sayılı lejant, üzerine gelince açıklama var.
  - Renkler kâğıt zeminde doğrulayıcıyla (`validate_palette.js`) denendi. Normal görüşte en yakın çift ΔE 20, renk körlüğünde 12,4. Amberin kontrastı düşük (2,4:1), bu yüzden yazı ve simge şart.
- **Bellek ve etkinlik** sıralı veri: tek ton (lacivert), açıktan koyuya.
- **Büyük sayı** düz yazı tipiyle (Instrument Sans), sayfada tek.

**İçindekiler**
- `STATUS` (= `style.MASTERY`, not penceresinin konu listesiyle ortak), `MEMORY`, `ACTIVITY`: renkler ve açıklamalar.
- `_CSS`: sayfaya özgü stiller. Sınıf adları `pf-` önekli: genel stil dosyasında aynı adlı `.nr-weak` (sınav özetindeki pembe hap), `.nr-tiles` ve `.nr-legend` vardı, çakışınca zayıf konular kutusunun arkasında pembe bir daire çıkıyordu.
- [`_edit(p)`](../src/ui/pages/profile.py#L91) (`@st.dialog`): ad, tanıtım, resim (jpg/png/webp) ya da "Resmi kaldır". Kaydedince kenar çubuğundaki ad ve resim de güncellenir (`data.avatar_b64.clear()`).
- [`_password(p)`](../src/ui/pages/profile.py#L115): `accounts.change_password`; diğer cihazlardaki oturumlar kapanır.
- [`_header(p)`](../src/ui/pages/profile.py#L136), [`_stats(m)`](../src/ui/pages/profile.py#L151): üst kısım.
- [`_memory_panel(m)`](../src/ui/pages/profile.py#L162), [`_activity_panel(m)`](../src/ui/pages/profile.py#L177): paneller (HTML).
- [`_map(m)`](../src/ui/pages/profile.py#L191): konu haritası. Kişinin listesindeki ya da çalıştığı notlar, en çok çalışılan önce.
- [`_weak(m)`](../src/ui/pages/profile.py#L216): zayıf konular; düğme `request.prepare` ile o konulardan 10 soruluk sınav hazırlar ve Sınav Hazırla'ya geçer ("Diğer" konusu aramaya verilmez).
- [`render()`](../src/ui/pages/profile.py#L239).

---

## `src/mastery.py` — beyin analizinin hesabı (138 satır)

**Ne işe yarar?** Kişinin görebildiği notlarda, konu konu ne kadar hâkim olduğunu **yalnızca kendi kayıtlarından** hesaplar. LLM yoktur.

**Soru → konu bağı kalıcıdır.** Sorunun kanıt sayfası konu haritasında hangi konunun sayfalarındaysa o konu sayılır. Haritası olmayan belgede bölüm başlıkları kullanılır; hiçbirine düşmeyen soru "Diğer"e gider. Sınav ekranındaki konu ise o sınavın arama sonucuna göre değişebiliyordu; ustalık için sabit bir bağ gerekiyordu.

**Bir sorunun durumu, ona dair en son kanıttan gelir:**
- sınavdaki son cevap (ikinci denemeler dahil, çünkü öğrenmeyi gösterir);
- kartın kutusu: 1. kutu bilemedi, 2-3. kutu bildi, 4-5. kutu uzun süreli bellekte.

Bu, ölçümden (madde güçlüğü, Elo; bölüm 10) farklıdır: orada yalnızca kişinin soruyu ilk görüşü sayılır. Burada amaç ölçmek değil, kişinin şu anki durumunu göstermek.

**İçindekiler**
- [`topic_of(page, topics)`](../src/mastery.py#L29): sayfa → konu.
- [`question_states(attempts, card_hist)`](../src/mastery.py#L36): soru → `known` / `strong` / `weak` (son kanıt).
- [`topic_status(n, seen, known)`](../src/mastery.py#L53): konu durumu.
  - Hiç görülmediyse "başlanmadı".
  - En az 2 soru görülüp yarısından azı biliniyorsa "zayıf".
  - En az 4 farklı soru (konuda daha az soru varsa hepsi) görülüp %80'i biliniyorsa "öğrenildi".
  - Değilse "çalışılıyor".
  - Tek yanlış "zayıf" sayılmaz: küçük sayıda karar verilmez.
- [`analyze(items, topic_maps, states)`](../src/mastery.py#L64): belge → konular (haritadaki sırayla) ve zayıf konular listesi (en düşük doğru oranı önce).
- [`memory(card_hist, alive)`](../src/mastery.py#L91): kutulardan bellek özeti; havuzdan çıkmış sorular sayılmaz.
- [`activity(attempts, card_rows, days, now)`](../src/mastery.py#L101): son 14 günün her biri için çalışma sayısı ("Atla" sayılmaz).
- [`for_user(user_id, visible)`](../src/mastery.py#L113): profil sayfasının bütün verisi. Arayüzde `data.mastery()` 20 saniye önbellekle çağırır; ana sayfadaki "Bildiğin x / y soru" da buradan gelir.

---

## `src/resume.py` — kaldığın yerden devam et (55 satır)

**Ne işe yarar?** Kişinin en son yarım bıraktığı kart oturumunu ve sınavı `data/app.sqlite`'ın `progress` tablosunda saklar. Kişi ve tür başına (`cards` / `exam`) tek satır vardır: ekrandaki durumun (`session_state.cards` / `.exam`) kopyası. Sekme kapansa, çıkış yapılsa ya da başka cihazdan girilse de ana sayfa yarım kalanı gösterir.

**Kim yazar?**
- Kart sayfası: her değerlendirmede (`_remember`), oturum bitince ya da "Yeni oturum"da siler.
- Sınav sayfası: sınav başlamış ama bitmemişse her çalıştırmada; sınav bitince siler.

**İçindekiler**
- [`save(user_id, kind, state)`](../src/resume.py#L19): üzerine yazarak kaydeder (`ON CONFLICT … DO UPDATE`).
- [`load(user_id, kind)`](../src/resume.py#L29): durum + `updated` (son değişiklik zamanı).
- [`restore_exam(state)`](../src/resume.py#L42): sınava dönüş. Beklenen süre sayaca eklenmez: başlangıç zamanı, aradaki süre kadar ileri alınır (10. dakikada bırakılan sınav ertesi gün 10. dakikadan devam eder).
- [`clear(user_id, kind)`](../src/resume.py#L51).

---

## Diğer dosyalarda değişenler (2026-10-08)

- **[`appdb.py`](../src/appdb.py)**, `MIGRATIONS` 2. adım: `users.avatar`, `users.about` ve `progress` tablosu. Var olan veritabanı açılışta kendiliğinden bu adıma geçer; kayıtlara dokunulmaz. Şema sürümlemesinin ilk gerçek kullanımı.
- **[`accounts.py`](../src/accounts.py):**
  - [`profile`](../src/accounts.py#L72), [`update_profile`](../src/accounts.py#L179), [`change_password`](../src/accounts.py#L163).
  - [`set_avatar`](../src/accounts.py#L189): resim ortadan kare kırpılıp 256×256 JPEG'e küçültülür. Telefon fotoğrafı yan dönmesin diye EXIF yönü uygulanır; konum gibi üst veriler saklanmaz.
  - [`avatar`](../src/accounts.py#L209), [`remove_avatar`](../src/accounts.py#L215).
- **[`library.py`](../src/library.py):** [`add_to_library`](../src/library.py#L201) (yalnızca herkese açık not), [`mine`](../src/library.py#L210), kayıtta `order` (giriş sırası; renk için).
- **[`ui/data.py`](../src/ui/data.py):** [`mine`](../src/ui/data.py#L91), [`items`](../src/ui/data.py#L97), [`mastery`](../src/ui/data.py#L120), [`home_stats`](../src/ui/data.py#L137), [`due_cards`](../src/ui/data.py#L142), [`avatar_b64`](../src/ui/data.py#L148).
- **[`ui/style.py`](../src/ui/style.py):**
  - [`avatar(user, b64, size)`](../src/ui/style.py#L540), `.nr-hello`, `.nr-sec` (profil), `.nr-avatar`; ana sayfa başlıkları bölüm 13'te `.nr-shelf-h`'ye geçti.
  - Sitenin genelinde seçili hap ve bölmeli düğmeler artık lacivert dolgulu (`[data-selected="true"]`); eskiden açık griydi, seçilmemişle neredeyse aynı görünüyordu.
  - `st.container(key="nr_card_…")` kâğıt beyazı kart görünümü alır (Sınav Hazırla formu).
- **Sayfalar:**
  - Sınav Hazırla ve Bilgi Kartları ana sayfadan gelen seçimi alır (`exam_doc`, `cards_doc` → seçim anahtarları `exam_docs`, `cards_docs`). Not penceresi `doc_open` ile açılır (bölüm 13; eskiden Belgeler'deki belge seçiciyi ayarlıyordu).
  - Kart ve sınav sayfaları yarım oturumu `resume`'a yazar.
  - Belgeler sayfasının yükleme kodu `upload.py`'ye taşındı.
- **[`app.py`](../src/app.py):** menünün başında "Ana sayfa" (varsayılan), sonunda "Hesap → Profil ve beyin analizi". Kenar çubuğunda profil resmi (2026-10-08 akşamından beri çubuğun en altında; bölüm 13).

## Testler

- [`tests/test_mastery.py`](../tests/test_mastery.py):
  - sayfa → konu;
  - son kanıtın kazanması (sınavdan sonra kartta bildi → biliyor);
  - konu durumu eşikleri (tek yanlış zayıf değil, en az 4 soru);
  - belge/konu sırası ve zayıf konular;
  - bellek özeti (havuzdan çıkmış soru sayılmaz);
  - son 14 gün ("Atla" sayılmaz).
- [`tests/test_accounts.py`](../tests/test_accounts.py) `test_profile_and_resume`:
  - profil kuralları;
  - resmin 256×256 JPEG olması, resim olmayan dosyanın reddi;
  - kendi parolanı değiştirme;
  - gizli not listeye eklenemez, herkese açık eklenir;
  - kaldığın yer: üzerine yazma, kişiye özel, sınavda bekleme süresinin sayılmaması;
  - şemanın 2. adımda olması.

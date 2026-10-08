# 13. Not penceresi, tam ekran okuyucu ve Belgeler

[← Rehber ana sayfa](README.md) · Önceki: [12. Ana sayfa, profil ve beyin analizi ←](12-ana-sayfa-ve-profil.md)

Bu bölüm 2026-10-08 akşamı yapılan tasarım değişikliklerini anlatıyor. Kullanıcının istekleri şunlardı:
- Ana sayfada kartlar daha büyük olsun, üstteki selam kısmı daha az yer tutsun.
- Raf sonsuza uzamasın: 2. satırın son kartı "Tümünü gör" olsun ve Belgeler sayfasına götürsün.
- Belgeler de notları kart olarak göstersin. Bir nota tıklayınca sayfanın üstünde, arkası hafifçe bulanık bir pencere açılsın. Pencerede gizli/herkese açık, adını değiştir, konular, sayfalar ve hazır soru bilgisi olsun.
- Sayfalara tam ekranda, ileri geri çalışılabilsin.
- Kenar çubuğu: "Ders notlarından kanıta dayalı sorular" yazısı kalksın, hesap kutusu en alta sabitlensin. Çubuk kapalıyken üst şerit sayfa başlığını kesmesin, logo okunur olsun.

Aynı gece ikinci tur (kullanıcı ilk hâli gördükten sonra):
- Belgeler'de iki görünüm, üstte bir düğmeyle seçilir. **Sayfalı:** sayfa aşağı kaymaz, ekranda 2 satır × 4 not; kalanlar 1. ve 2. satırın arasında, sağdaki iki kartın ortasındaki okla yana kayarak gelir, geri de dönülür. **Kaydırmalı:** bütün notlar alt alta, satırlar sayfa kaydıkça birer birer gelir.
- Kenar çubuğu açılıp kapanınca sayfa yerinden oynamasın (kartlar büyüyor, her şey aşağı kayıyordu): yalnızca çubuk açılıp kapansın.
- Ana sayfada "Herkese açık notlar"da hiç not yokken de "+" kartı olsun. Kullanıcının herkese açtığı not orada görünmüyordu (raf yalnızca başkalarının notlarını gösteriyordu) → düzeldi.
- Pencere hafif kasıyor; "Hazır sorular" sekmesi gereksiz (sorular sınavın işi) → kaldırıldı. Konular kendi içinde kaysın, pencerenin altı ekranın dibine değmesin.

Yeni dosyalar:
- [`ui/docview.py`](../src/ui/docview.py): not penceresi ve not kartı. Ana sayfa da Belgeler de bunu kullanır.
- [`ui/reader.py`](../src/ui/reader.py): tam ekran PDF okuyucu (Streamlit özel bileşeni, CCv2).
- [`ui/logo_ink.svg`](../src/ui/logo_ink.svg): kenar çubuğu kapalıyken üst şeritteki koyu logo.

Baştan yazılan: [`ui/pages/documents.py`](../src/ui/pages/documents.py) (Belgeler). Değişen: `home.py`, `shelf.py`, `auth.py`, `app.py`, `style.py`, `data.py`, `profile.py` (bkz. sondaki liste).

---

## Akış: karttan pencereye, pencereden okuyucuya

```
ana sayfa ya da Belgeler: not kartına tıkla
   shelf → ("tyt-matematik", "open") → docview.act → open_doc: session_state.doc_open = "tyt-matematik"
   aynı çalıştırmada sayfanın sonunda docview.show() → st.dialog(...) açılır (arka plan bulanık)
   (raf bir parçanın içindeyse, işlenen not varken, o çalıştırma show()'a gelmez → st.rerun())

pencere: Sayfalar → "Tam ekran çalış"   ya da   Konular → bir konuya tıkla
   docview._read → doc_open silinir, reader.open_reader(...) → session_state.reader = {doc, page, nonce, tab, topic}
   st.rerun() → sayfa docview.reading() görür → yalnızca okuyucuyu çizer (sayfanın kendisini değil)

okuyucu: ← → ile sayfa çevir (yalnızca okuyucu parçası yeniden çalışır), Esc ya da ✕
   reader → on_close → docview._back: pencere geldiği sekmede, okunan sayfada yeniden açılır
```

Pencere neden `session_state.doc_open` ile tutuluyor? Streamlit'te pencere (`st.dialog`), açan fonksiyon o çalıştırmada çağrıldığı sürece açık kalır. Sayfa baştan çalışınca (ör. ad değişince `st.rerun()`) pencere kapanırdı. Şimdi her çalıştırmanın sonunda `docview.show()` açık notu yeniden açıyor. Kişi pencereyi kendisi kapatınca (X, Esc, dışarı tıklama) `on_dismiss` geri çağrısı `doc_open`'ı siler.

---

## `src/ui/docview.py` — not penceresi ve not kartı (~400 satır)

**Ne işe yarar?**
- Not kartının verisini hazırlar (rafta ve Belgeler ızgarasında aynı kart).
- Karttaki tıklamaları yönlendirir.
- Geniş bir pencerede notun her şeyini gösterir:
  - **Üst kısım:** renkli kapak (notun rengi ve baş harfi, arkasında bir yaprak), PDF'in kendi başlığı (anlamlıysa), sayfa · dil · konu · hazır soru hapları, gizli ya da herkese açık, "Bildiğin x / y soru" çubuğu.
  - **Sağ üst:** "Sınav hazırla", "Kartları çalış", "Notlarıma ekle" (başkasının notuysa), "Adını değiştir" (yalnızca sahibi), "Herkese aç" (geri alınamaz uyarısıyla).
  - **Üç sekme** (ilk hâlinde dördüncü olarak "Hazır sorular" vardı; kullanıcı kararıyla kaldırıldı: sorular sınavın işi):
    - **Konular:** her konu bir satır: sıra, ad, sayfalar ("s. 6–7"), senin ustalık durumun (öğrenildi / çalışılıyor / zayıf / başlanmadı; renk + simge + yazı) ve hazır soru sayısı. Satıra tıklayınca o konunun ilk sayfası tam ekran okuyucuda açılır. Liste **kendi içinde kayar**.
    - **Sayfalar:** sayfa görüntüsü ve sistemin o sayfadan çıkardığı metin (kendi içinde kayar), sayfanın konusu ve o sayfadan kaç hazır soru olduğu. ‹ › düğmeleri, kaydırıcı ve "Tam ekran çalış".
    - **Okuma kalitesi:** görselden okunan, tablosu çıkarılan sayfalar, silinen üst/alt bilgi satırları, üretimden çıkarılan sayfalar.

**Pencere neden kasıyordu, ne yapıldı?** Görünmez test tarayıcısı ekrana gerçekten çizmediği için takılma orada ölçülemedi; bilinen nedenler giderildi:
- Pencere ekrandan uzundu ve kaydırınca **bütün ekranı kaplayan bulanık örtü** kayıyordu: arka plan bulanıklığı her karede yeniden hesaplanır. Şimdi pencere ekrana sığar (alt boşluk ~60 px), yalnızca konu listesi ya da sayfa metni kendi içinde kayar; örtü yerinde durur.
- Bulanıklık 5 px → 3 px, pencere gölgesi küçüldü; konu satırlarında gölge ve kalkma animasyonu yok (yalnızca renk değişir), liste `contain: content` ile ayrı katman.
- Hesap: her sekme değişiminde inceleme kararları ve bildirimler diskten okunuyordu (`R.blocked_ids`) → `data.ready()` ve `reader.per_page()` önbellekli.
- Açılış: karta tıklayınca fazladan bir `st.rerun()` vardı → pencere aynı çalıştırmada açılıyor (tıklamadan konu listesine 216 → 146 ms).

**Bağlantılar**
- ← `ui/pages/home.py`, `ui/pages/documents.py`.
- → `reader` (okuyucu, sayfa görüntüsü, içindekiler, sayfa başına soru sayısı), `shelf` (`Component`, `palette`), `library` (`publish`, `rename`, `add_to_library`, `has_access`), `upload.start`, `data` (`documents`, `doc_meta`, `ready`, `mastery`, `topics`, `parsed`, `jobs`, `job_status`, `mine`, `visible`).
- Yönlendirdiği sayfalar: `exam` ("Sınav", `exam_doc`), `cards` ("Kartlar", `cards_doc`).

**İçindekiler**
- `STEPS`, `TABS`, `SOURCE_TR`, `FLAG_TR`: adım adları, sekmeler, rozet yazıları.
- `_CSS`: pencerenin stilleri. Sınıflar `dv-` önekli (genel stil dosyasıyla çakışmasın).
- `_TOPICS` (`_TOPICS_CSS`, `_TOPICS_JS`): Konular sekmesindeki tıklanabilir satırlar. Düz HTML tıklamayı Python'a iletemediği için küçük bir CCv2 bileşeni. Tıklanan satırın sırasını `setTriggerValue("open", k)` ile verir. Listenin yüksekliğini JS ölçer: ekran yüksekliği − listenin üstü − pencerenin alt payı (pencere açılış animasyonundan sonra ve ekran boyu değişince yeniden).
- [`running(stem, jobs)`](../src/ui/docview.py#L152): notun süren işi (son 6 saatte başlamış, bitmemiş, çökmemiş) ya da `None`.
- [`card(d, meta, jobs, prog, public_view)`](../src/ui/docview.py#L158): notu bileşenin anlayacağı karta çevirir (eskiden `home._doc_card`):
  - başlık, sayfa ve konu sayısı; çizgili satırlarda notun ilk 3 konusu (başlık uzunsa 2);
  - rozet: Gizli / Herkese açık / İşleniyor; renk kütüphaneye giriş sırasından;
  - deste kalınlığı ve "Henüz çalışmadın · 18 soru" gibi yazılar **hazır soru** sayısından (`data.ready`, aşağıda);
  - işleniyorsa adım ("Sorular üretiliyor 5/6") ve canlı çubuk.
- [`act(ident, action, in_fragment)`](../src/ui/docview.py#L193): karttaki tıklama. `in_fragment`: raf, işlenen not varken kendiliğinden yenilenen bir parçanın içinde çizildiyse (o çalıştırma sayfanın sonundaki `show()`'a gelmez, sayfa baştan çalıştırılır).

  | Tıklanan | Ne olur |
  |---|---|
  | Kartın kendisi, "Ayrıntı", "Göz at" | Pencere aynı çalıştırmada açılır (`open_doc`; parçadaysa `st.rerun()`) |
  | "Sınav" / "Kartlar" | `_study`: Sınav Hazırla / Bilgi Kartları o not seçili açılır |
  | "Notlarıma ekle" | `library.add_to_library`; not kişinin rafına geçer |

- [`_study(kind, stem)`](../src/ui/docview.py#L210): pencereyi kapatır, sınav ya da kart sayfasına geçer. Yarım sınav kaybolmaz ("kaldığın yer"de durur).
- [`open_doc(stem, tab)`](../src/ui/docview.py#L223), [`_dismissed()`](../src/ui/docview.py#L228), [`show()`](../src/ui/docview.py#L232): pencereyi açma, kişi kapatınca temizleme, sayfanın sonunda açık pencereyi çizme. Pencere başlığı notun adı, genişliği `large` (en çok 1280 px).
- [`reading()`](../src/ui/docview.py#L243), [`reader_view()`](../src/ui/docview.py#L248), [`_back(r, page)`](../src/ui/docview.py#L252), [`_read(stem, page, tab, topic)`](../src/ui/docview.py#L258): okuyucuya geçiş ve dönüş. `_read` okuyucuya hangi sekmeden geldiğini ve (Konular'dan geldiyse) hangi konuya tıklandığını da yazar.
- [`_body(stem)`](../src/ui/docview.py#L268): pencerenin içi. Sekmeler durum tutar (`st.tabs(key="dv_tab", on_change="rerun")`): yalnızca seçili sekme çalışır, sayfa görüntüsü boşuna hazırlanmaz. Sekme değiştirmek yalnızca pencereyi yeniden çalıştırır. Hazır soru sayısı `data.ready()`'den (önbellekli).
- [`_hero(d, meta, n_ready)`](../src/ui/docview.py#L291), [`_actions(d, meta, n_ready)`](../src/ui/docview.py#L320): üst kısım ve düğmeler. "Herkese aç" eskiden ayrı bir onay penceresiydi; Streamlit pencere içinde pencere açamadığı için artık açılır kutu (`st.popover`) içinde uyarı + "Anladım, herkese aç".
- [`_state(d)`](../src/ui/docview.py#L358), [`_job(stem)`](../src/ui/docview.py#L371), [`_detail(tail)`](../src/ui/docview.py#L383): not işleniyorsa adım ve son ilerleme satırı (pencerenin içinde 4 saniyede bir kendiliğinden yenilenen parça; iş bitince pencere yeni verilerle baştan çizilir). Hiç işlenmediyse "Notu işle".
- [`_topics_tab`](../src/ui/docview.py#L395), [`_pages_tab`](../src/ui/docview.py#L426), [`_step`](../src/ui/docview.py#L422), [`_quality_tab`](../src/ui/docview.py#L467): sekmeler. Sayfalar sekmesindeki sayfa numarası `dv_pg_<not>` anahtarında; okuyucu kapanınca buraya son okunan sayfa yazılır. Sayfa görüntüsü ve metin kutusunun yüksekliği ekran yüksekliğinden (`calc(100vh - …)`): pencere ekrandan taşmaz.

---

## `src/ui/reader.py` — tam ekran PDF okuyucu (~390 satır)

**Ne işe yarar?** Notun sayfalarına tam ekranda çalışmak için bütün pencereyi kaplayan koyu bir sahne:
- ortada sayfa görüntüsü (gölgeli kâğıt), iki yanda büyük ‹ › düğmeleri;
- üstte notun adı ve **sayfanın konusu** ("04 · Basit Eşitsizlikler ve Aralıklar"), sağda İçindekiler, Genişliğe yay / Ekrana sığdır, Tam ekran;
- altta sayaç ("3 / 23"), sarı sayfa kaydırıcısı, "Bu sayfadan 9 hazır soru" ve tuş ipucu;
- solda açılır **içindekiler**: konu haritası, her konunun sayfaları ve soru sayısı; tıklayınca o konunun ilk sayfası.

**Klavye:** ← → (PageUp/PageDown, boşluk) sayfa · Home/End baş/son · İ içindekiler · G genişliğe yay · F tarayıcıda gerçek tam ekran · Esc kapat. Dokunmatikte parmakla yana kaydırınca sayfa çevrilir. "Hareketi azalt" tercihinde sayfa geçiş animasyonu yok.

**Neden özel bileşen ve neden parça (fragment)?**
- Sayfa görüntüleri büyük (uzun kenarı 1700 px JPEG, ~150-300 KB). Hepsini bir kerede göndermek 70 sayfalık notta ~15 MB eder. Okuyucu yalnızca açık sayfayı ve komşularını gönderir (`AHEAD`: bir sonraki, ondan sonraki, bir önceki). JS aldığı her sayfayı saklar: ileri ve geri sayfa anında açılır, ilk kez gidilen uzak sayfada kısa bir "Sayfa 13 hazırlanıyor" görünür.
- JS sayfa değişince `setStateValue("page", p)` der. Okuyucu `@st.fragment` içinde olduğu için yalnızca okuyucu yeniden çalışır, sayfanın geri kalanı değil. Python yeni sayfa numarasını bileşenin durumundan **çizmeden önce** okur (`st.session_state[anahtar]`), böylece doğru komşuları gönderir.
- Her açılış yeni bir anahtar alır (`nonce`): okuyucu her açılışta istenen sayfadan başlar, eski durum taşınmaz.
- Okuyucu açıkken sayfanın kendisi çizilmez (`docview.reading()`): arkada boşuna çalışan bir sayfa olmasın.

**İçindekiler**
- `_CSS`, `_HTML`, `_JS`: bileşen. `build()` iskeleti bir kez kurar, `render()` her değişiklikte günceller; `topicOf()` sayfanın konusunu bulur (tıklanan konu o sayfayı kapsıyorsa o, yoksa sayfayı içeren ilk konu). Klavye dinleyicisi pencereye bağlanır ve bileşen kaldırılınca çıkarılır.
- [`page_jpeg(file, page)`](../src/ui/reader.py#L319): sayfa görüntüsü (PyMuPDF, önbellekli, en çok 200 sayfa). Pencerenin Sayfalar sekmesi de bunu kullanır ([`data_url`](../src/ui/reader.py#L327) ile).
- [`pages_label(pages)`](../src/ui/reader.py#L331): `[3, 5, 6]` → `"s. 3, 5–6"`.
- [`per_page(stem)`](../src/ui/reader.py#L343): sayfa → o sayfaya dayanan hazır soru sayısı (`data.ready` ile aynı süzgeç; 30 sn önbellekli: okuyucu her sayfa çevirişinde, pencere her sekmede çağırıyor).
- [`toc(stem)`](../src/ui/reader.py#L351): içindekiler: konu haritası (yoksa bölüm başlıkları), ilk sayfa, soru sayısı.
- [`open_reader(stem, page, **back)`](../src/ui/reader.py#L360), [`active()`](../src/ui/reader.py#L365), [`show(on_close)`](../src/ui/reader.py#L369), [`_view(on_close)`](../src/ui/reader.py#L375): açma ve çizme. Kapatılınca (`setTriggerValue("close", sayfa)`) `on_close(okuyucu durumu, son sayfa)` çağrılır ve uygulama baştan çalışır.

---

## `src/ui/pages/documents.py` — Belgeler (baştan yazıldı, ~120 satır)

**Ne işe yarar?** Kişinin görebildiği bütün notlar (kendi notları ve herkese açık olanlar), ana sayfadaki desteler gibi kart kart. Üstte:
- **süzgeç:** Tümü · Notlarım · Herkese açık (sayılarıyla);
- **arama:** not adı, PDF'in kendi başlığı ya da konu başlıkları; büyük/küçük harf ve Türkçe harf farkı gözetilmez ("monokultur" → "Monokültür ve Öncü Türler" konusu olan Ekoloji);
- **sıralama:** En yeni · Ada göre · En çok soru;
- **görünüm:** Sayfalı · Kaydırmalı (`session_state.docs_view`, varsayılan Sayfalı).

**İki görünüm** (kartlar `shelf.py`'de):
- **Sayfalı** (`layout="pages"`): sayfa aşağı **kaymaz** (`stMain`'e `overflow: hidden`, yalnızca bu görünümde). Ekranda 2 satır × 4 kart; kart boyunu JS hesaplar: genişliğe ve bileşenin altında kalan ekran yüksekliğine sığacak en büyük kart (1440×1000'de ~233 px, 1280×720'de ~176 px; küçük kartta konu satırları gizlenir). Kalan notlar yandaki "sayfalarda": **sağ ok 1. ve 2. satırın arasında, sağdaki iki kartın tam ortasında**, ızgaranın kenarında; tıklayınca 4'lü bölüm sola kayar ve sonraki 8 not gelir; ikinci sayfada sol ok belirir, geri dönülür. Altta noktalar ve "2 / 3". Klavyede ← →, dokunmatik yüzeyde yatay kaydırma, telefonda parmakla kaydırma. Arama ya da süzgeç değişince ilk sayfaya döner.
- **Kaydırmalı** (`lazy=True`): bütün notlar alt alta satırlarda; ekrana sığan satırlar hemen, kalanlar sayfa aşağı kaydıkça **birer satır** gelir (alttaki görünmez işaretçi ekrana girince bir satır eklenir; `IntersectionObserver`).

Bir karta tıklayınca pencere bu sayfanın üstünde açılır. **Yükleme kutusu artık burada yok** (kullanıcı kararı): not ekleme ana sayfadaki "+ Yeni not ekle" kartından. Eski "çalışan işler" kutusu da kalktı: işlenen notun kartı canlı ilerleme gösteriyor, ayrıntısı (adım, kota bekleniyor mu) pencerede.

**İçindekiler**
- [`_fold(s)`](../src/ui/pages/documents.py#L38), [`_match(d, words)`](../src/ui/pages/documents.py#L43): arama.
- [`_grid(stems, empty, view, live)`](../src/ui/pages/documents.py#L50): kartlar, seçili görünümde (iki görünümün bileşen anahtarı ayrı: görünüm değişince eskisi kendi dinleyicileriyle birlikte kalkar). Kişinin listesinde olmayan herkese açık not "Notlarıma ekle / Göz at" düğmeli kartla gelir. İşlenen bir not varsa ızgara 5 saniyede bir kendiliğinden yenilenen bir parçada çizilir (`live`).
- [`render()`](../src/ui/pages/documents.py#L64): okuyucu açıksa yalnızca onu çizer; değilse başlık, süzgeç, kartlar ve (açıksa) pencere. Ana sayfadaki "Tümünü gör" `session_state.docs_filter` ile hangi süzgecin seçili geleceğini söyler.

---

## Diğer dosyalarda değişenler

- **[`ui/pages/home.py`](../src/ui/pages/home.py)** (bölüm 12):
  - Selam satırı kısaldı: profil resmi, "İyi günler, Kaan", sayı hapları (not, hazır soru, kart). Eskiden üst etiket + büyük ad + çift çizgi ~190 px tutuyordu.
  - "Ders notların" rafı en çok **2 satır**, "Herkese açık notlar" **1 satır**; son kart "Tümünü gör" → Belgeler (ilgili süzgeç seçili).
  - "Herkese açık notlar": ilk kart hep **"+ Herkese açık not ekle"** (hiç açık not yokken de raf boş kalmaz); penceresi (`_share_note`) kendi gizli notlarından birini herkese açar (geri alınamaz uyarısıyla) ya da yeni not yükletir. Raf artık kişinin **kendi** herkese açık notlarını da gösterir (en son paylaşılan önce). **Bulgu:** kullanıcı "Bilgisayar Performansı"nı herkese açmıştı ama raf yalnızca başkalarının notlarını gösterdiği için orada göremiyordu.
  - Karta tıklayınca pencere ana sayfanın üstünde açılır (eskiden Belgeler'e gidiyordu).
  - Kart verisi ve tıklama yönlendirmesi `docview`'a taşındı (`_doc_card` → `docview.card`, `_act` → `docview.act`).
  - Sayfaya özgü daha geniş içerik alanı (en çok 1320 px; Belgeler de aynı).
- **[`ui/shelf.py`](../src/ui/shelf.py)** (bölüm 12):
  - Kartlar büyüdü (genişlik ~230-300 px, oran 3:4, 3 konu satırı) ve **sütun sayısı JS'te** bileşenin genişliğinden hesaplanır (en çok 4). Pencere daralınca `ResizeObserver` yeniden dizer; ilk çizimden sonraki yeniden dizilişlerde giriş animasyonu oynamaz (`.still`).
  - İki yeni görünüm (Belgeler): `layout="pages"` (`pagesLayout`, `renderPages`, `goPage`, `drawPages`) ve `lazy=True` (`drawLazy`). Ayrıntı yukarıda, Belgeler bölümünde. Küçük kartlar için kap sorgusu (`@container`): konu satırları gizlenir, yazılar küçülür.
  - `shelf(..., rows, more)`: raf en çok `rows` satır, son yer `more` kartı ([`all_card`](../src/ui/shelf.py#L483): notların renklerinden küçük bir yelpaze, "Tümünü gör", ok).
  - [`Component`](../src/ui/shelf.py#L457): üç CCv2 bileşeninin (raf, okuyucu, konu listesi) ortak kaydı. Kayıt yoksa (AppTest, Streamlit'in yeniden başlaması) yeniden kaydeder; eskiden yalnızca rafta `_component()` vardı.
- **[`ui/auth.py`](../src/ui/auth.py)** [`sidebar(u)`](../src/ui/auth.py#L65): hesap kutusu yatay (resim, ad, @kullanıcı adı, "Çıkış") ve `st.container(key="nr_account")` içinde; CSS kutuyu kenar çubuğunun dibine iter.
- **[`app.py`](../src/app.py):** "Ders notlarından kanıta dayalı sorular" yazısı kalktı. `st.logo(..., icon_image=logo_ink.svg)`: kenar çubuğu kapalıyken üst şeritte koyu logo (açık renkli logo kâğıt zeminde parlıyor, okunmuyordu).
- **[`ui/style.py`](../src/ui/style.py):**
  - Kenar çubuğu içeriği dikey esnek kutu, hesap kutusu üstten `auto` boşlukla en altta; menü ile hesap arasındaki ayırıcı çizgi kalktı (kutunun kendi üst çizgisi var).
  - **Kenar çubuğu sayfayı itmez** (ikinci tur): Streamlit çubuğu kapatınca genişliğini sıfırlıyor, ana alan 1140 → 1440 px genişliyor, kartlar büyüyüp her şey aşağı kayıyordu. Şimdi geniş ekranda (≥ 769 px) çubuk sabit konumda (`position: fixed`, 300 px) içeriğin üstünde durur; ana alan hep `margin-left: 300px; width: calc(100% - 300px)`. Kapatınca yalnızca çubuk kayarak gider. Ölçüm: açık / kapalı / yeniden açık hâllerde selam başlığı, ilk kart ve ana alan piksel piksel aynı, yatay taşma 0. Kapalıyken logo ve "»" çubuğun boşalttığı sol alanda görünür. Dar ekranda (telefon) Streamlit'in kendi davranışı kalır.
  - Üst şerit (`stHeader`) her zaman saydam, sabit ve tıklamayı geçirir (yalnızca düğmeleri tıklanır). İlk turdaki "kapalıyken içerik 4,9rem aşağıdan başlasın" kuralı kalktı (içeriği aşağı itiyordu).
  - Pencerelerin arka planı hafifçe kararır ve bulanıklaşır (`backdrop-filter: blur(3px)`; ilk turda 5 px); pencere kâğıt beyazı, köşeleri yuvarlak. Bütün pencereler için geçerli ("Yeni not ekle" dahil).
  - Yeni sınıflar: `.nr-hello-t`, `.nr-hello-stats`, `.nr-shelf-h` (ana sayfa bölüm başlıkları), `.nr-head` (Belgeler başlığı). **Ders:** ana sayfa başlıkları için önce `.nr-sec` değiştirildi; profil de aynı sınıfı kullandığı için "Beyin analizi" başlığı bozuldu. Ana sayfaya ayrı sınıf verildi, `.nr-sec` eski hâline döndü.
  - `MASTERY`: konu durumu renkleri (profil ve pencerenin konu listesi ortak; eskiden `profile.STATUS`).
- **[`ui/data.py`](../src/ui/data.py)** [`ready()`](../src/ui/data.py#L104): not → hazır soru sayısı (doğrulanmış, reddedilmemiş, hatalı bildirilmemiş). **Bulgu:** kartlar eskiden `documents()`'teki `verified` sayısını gösteriyordu; o sayı deney (pilot) setlerini de sayıyor. Genetic Algorithms kartında "72 hazır soru" yazarken sınavın kullanabildiği 12'ydi. Kartlar, selam satırı ve "En çok soru" sıralaması artık `ready()` kullanıyor. `home_stats()` artık `[(sayı, ad), …]` döndürüyor (haplar için).
- **[`scripts/tasarim.py`](../scripts/tasarim.py)** (bölüm 9): `ekran` adımları (`!tıkla`, `~bekle`, `^tuş`, `#js`, `@ara ekran`, `$COLLAPSE`), ekran boyutu (`$env:NR_EKRAN="1280x720"`), her açılışta kenar çubuğu açık başlar.

## Doğrulama (2026-10-08)

- 11 test dosyası geçiyor (API çağırmaz).
- Tarayıcısız `AppTest`, iki hesapla: bütün sayfalar, pencerenin dört sekmesi, ana sayfada pencere, başkasının herkese açık notu, okuyucu, süzgeç ve arama hatasız. Sahte bir iş durumuyla (gerçek `data/jobs`'a yazmadan) "not işleniyor" penceresi de denendi.
- Görünmez Edge'de gerçek tıklamalar (`tasarim.py`, 1440×1000 ve 1280×720):
  - kart → pencere;
  - Sayfalar → "Tam ekran çalış" → → → (3. sayfa, konu yazısı) → İ (içindekiler) → Esc → pencere 3. sayfada;
  - Konular → 4. konu → okuyucu o konunun sayfasında, üstte o konu → G (genişliğe yay) → Esc → Konular sekmesi;
  - "Tümünü gör" → Belgeler, "Notlarım" seçili;
  - kenar çubuğu kapalı: koyu logo, başlık kesilmiyor.
- İkinci tur:
  - Sayfalı görünüm, 18 sahte kartla uygulamadan bağımsız bir deneme sayfasında (bileşenin gerçek CSS/JS'i; gerçek PDF klasörüne dosya eklenmedi): 1440×1000'de kart 233×311, 1280×720'de 176×235; belge yüksekliği = ekran yüksekliği (kaymıyor); sağ ok → 2/3, sol ok belirir → 3/3, sağ ok kaybolur. Kaydırmalı: önce 3 satır, kaydırdıkça 18 kartın hepsi.
  - Kenar çubuğu aç / kapa / aç: konumlar aynı (yukarıda).
  - Pencere: örtü kaymıyor, konu listesi 548 px'te kendi içinde kayıyor (içerik 938 px), alt boşluk 59 px.
  - AppTest: iki görünüm, üç sekme, yeni herkese açık raf hatasız; 11 test geçiyor.

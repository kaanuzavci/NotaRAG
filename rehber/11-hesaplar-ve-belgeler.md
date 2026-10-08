# 11. Hesaplar ve belge kütüphanesi

[← Rehber ana sayfa](README.md) · Önceki: [10. Zorluk ←](10-zorluk.md)

Bu bölüm 2026-10-07'de eklenen **kullanıcı girişi** katmanını anlatıyor. Beş dosya var:

- [`appdb.py`](../src/appdb.py): hesapların ve belge kaydının durduğu veritabanı (`data/app.sqlite`) ve şemanın sürümlenmesi.
- [`accounts.py`](../src/accounts.py): hesaplar, parolalar, "beni hatırla" oturumları.
- [`library.py`](../src/library.py): belge kütüphanesi. Her belgenin kimliği, sahibi, gizli ya da herkese açık oluşu, aynı belgeyi tanıma.
- [`jsonl.py`](../src/jsonl.py): kayıt dosyalarına (çözümler, kartlar, bildirimler, kararlar) güvenli ekleme.
- [`ui/auth.py`](../src/ui/auth.py): giriş ekranı, çerez, çıkış.

## Önce büyük resim

**Rol yok.** Öğretmen/öğrenci ayrımı yapılmaz. Her hesap aynı sayfaları görür ve aynı şeyleri yapar: belge yükler, sınav çözer, kart çalışır, inceler. Hesapları ayıran yalnızca **kendi verisi** ve **görebildiği belgeler**dir.

**Mantık tek, veri kişisel.** Hangi kartın bugün geleceği, bir sorunun "ilk deneme" sayılıp sayılmayacağı gibi kurallar herkes için aynı koddur. Kişiye göre değişen, o kodun girdisidir: kişinin kendi kayıtları.

| Kişisel (her hesabın kendi) | Ortak (herkesin) |
|---|---|
| Sınav çözümleri, kart değerlendirmeleri, Leitner kutuları | Soru havuzu (`data/questions/`), parçalar, ChromaDB dizini, konu haritaları |
| Görebildiği belgeler (yükledikleri + herkese açık olanlar) | Kota ve LLM önbelleği (`data/llm.sqlite`) |
| Yeteneği θ (Elo; bölüm 10) | Sorunun zorluğu (herkesin ilk denemelerinden) |

**Veri iki yerde durur:**

1. **Değişebilen ve tekil olması gereken kayıtlar** SQLite'ta (`data/app.sqlite`). Örnekler: hesaplar (aynı kullanıcı adı iki kez alınamaz, parola değişebilir), oturumlar (süresi dolar, çıkışta silinir), belge kaydı (görünürlük değişir).
2. **Sona eklenen geçmiş** bugünkü JSONL dosyalarında kalır, her satıra kişinin kimliği (`"user"`) eklenir. Örnekler: `attempts.jsonl`, `cards.jsonl`, `reports.jsonl`, `reviews.jsonl`.

Kutular, "ilk deneme" ve seviye **saklanmaz, kayıtlardan hesaplanır**. Aynı bilginin ikinci bir kopyası olsaydı ikisinin birbirini tutmaması mümkün olurdu.

**Eski kayıtlar.** Girişten önceki dönemin kayıtlarında kişi alanı yok. Bunlar **ilk açılan hesaba** aittir ([`legacy_owner`](../src/accounts.py#L220)). Dosyalar yeniden yazılmaz: okuyan kod, kişi alanı olmayan satırı o hesabınki sayar. Girişten önce yüklenmiş belgeler de ilk hesaba bağlanır ([`library.sync`](../src/library.py#L128)).

---

## `src/appdb.py` — uygulama veritabanı (106 satır)

**Ne işe yarar?** `data/app.sqlite` dosyasını açar ve şemasını günceller. Hesaplar, oturumlar ve belge kaydı buradaki tablolardadır.

**Bağlantılar**
- ← `accounts`, `library`, testler, `scripts/onizleme.py`.
- → `config` (`APP_DB`), `sqlite3`.
- 💾 Okur/yazar: `data/app.sqlite`. `NOTARAG_APP_DB` ortam değişkeniyle başka dosyaya yönlendirilebilir; deneme kurulumu gerçek hesaplara dokunmadan çalışsın diye.

**İçindekiler**
- [`PATH`](../src/appdb.py#L21): veritabanının yolu. Testler ve önizleme bunu geçici bir dosyaya çevirir.
- [`MIGRATIONS`](../src/appdb.py#L23): şemanın **adım adım** geçmişi. 1. adım bütün tabloları kurar:
  - `users`: hesabın değişmeyen kimliği ve görünen adı.
  - `identities`: giriş yolları. Bugün yalnızca `password`; ileride Google ya da telefon buraya yeni bir satır olarak eklenir.
  - `sessions`: "beni hatırla" belirteçlerinin **özeti** ve son geçerlilik zamanı.
  - `settings`: küçük ayarlar (`legacy_owner`).
  - `documents` ve `doc_access`: belge kaydı ve kimin hangi belgeye erişimi olduğu.

  2. adım (2026-10-08, bölüm 12): `users.avatar` (profil resmi), `users.about` (kısa tanıtım), `progress` (kaldığın yerden devam et). Var olan veritabanı açılışta bu adıma kendiliğinden geçti; kayıtlara dokunulmadı.
- [`_migrate(con)`](../src/appdb.py#L85): dosyanın sürümünü (`PRAGMA user_version`) okur, eksik adımları sırayla uygular.
- [`connect()`](../src/appdb.py#L97): `with appdb.connect() as con:` biçiminde kullanılır. Çıkışta değişiklikleri kaydeder; hata olursa geri alır; bağlantıyı kapatır.
- [`version()`](../src/appdb.py#L116): şemanın şu anki adımı (testler kullanır).

**Neden böyle?**
- **Şema sürümlemesi:** yarın bir alan ya da tablo eklemek gerekirse listenin **sonuna** yeni bir adım yazılır, eskilere dokunulmaz. Açılışta eksik adım uygulanır, var olan veri bozulmaz. "Sonradan bir şey eklersek sorun yaşamayalım" isteğinin karşılığı budur.
- **WAL kipi:** arayüz ve arka plan işleri (belge işleme ayrı süreçte çalışır) aynı anda okuyup yazabilir.
- **`llm.sqlite`'tan ayrı:** LLM önbelleği silinirse kotayla yeniden üretilir; hesaplar ve kayıtlar yeniden üretilemez. İkisinin yedeklenmesi ve ömrü farklıdır.
- **`BEGIN IMMEDIATE`:** iki süreç aynı anda ilk kez açarsa ikincisi bekler, sonra sürümü güncel okur; adımlar iki kez uygulanmaz.

---

## `src/accounts.py` — hesaplar ve giriş (209 satır)

**Ne işe yarar?** Hesap açar, kullanıcı adı ve parolayı doğrular, "beni hatırla" oturumlarını yönetir.

**Bağlantılar**
- ← `ui/auth.py`, `library.sync` (`legacy_owner`), `cards`, `difficulty.real_attempts`, testler.
- → `appdb`, `hashlib` (scrypt), `secrets`, `hmac`.
- 💾 Okur/yazar: `data/app.sqlite` (`users`, `identities`, `sessions`, `settings`).

**İçindekiler**
- [`USERNAME`](../src/accounts.py#L29), [`MIN_PASSWORD`](../src/accounts.py#L30): kullanıcı adı yalnızca küçük harf a-z, rakam, `.`, `_`, `-` (3-32 karakter). Türkçe harfler görünen adda serbest; kullanıcı adında yok, çünkü `I`/`İ` gibi harflerin küçük harfe çevrilmesi dile göre değişir ve girişte eşleşme şaşabilirdi. Parola en az 8 karakter.
- [`hash_password(password)`](../src/accounts.py#L42): parolayı **scrypt** ile özetler. Sonuç `scrypt$15$8$1$<tuz>$<özet>` biçimindedir; parametreler ve tuz özetin içinde saklanır.
- [`check_password(password, stored)`](../src/accounts.py#L49): özeti saklanan parametrelerle yeniden hesaplar, `hmac.compare_digest` ile karşılaştırır.
- [`create(username, password, name)`](../src/accounts.py#L87): yeni hesap. Kuralları denetler, kullanıcı adı alınmışsa `AccountError` verir. **İlk hesap** eski kayıtların sahibi olur (`settings.legacy_owner`).
- [`link(con, user_id, provider, subject, secret)`](../src/accounts.py#L111): hesaba bir giriş yolu bağlar. Bugün `create` bunu `"password"` ile çağırıyor. Google eklenince aynı fonksiyon `"google"` ve Google'ın kişi kimliğiyle (`sub`) çağrılacak.
- [`by_identity(provider, subject)`](../src/accounts.py#L117): giriş yolundan hesabı bulur.
- [`authenticate(username, password)`](../src/accounts.py#L125): doğruysa hesabı, değilse `None` döndürür. Olmayan bir kullanıcı adında da parola özeti hesaplanır; böylece cevap süresinden "bu kullanıcı adı var mı" anlaşılamaz.
- [`get`](../src/accounts.py#L134), [`all_users`](../src/accounts.py#L139), [`count`](../src/accounts.py#L144): okuma yardımcıları.
- [`set_password(username, password)`](../src/accounts.py#L149): parolayı değiştirir ve o hesabın açık oturumlarını kapatır.
- [`legacy_owner()`](../src/accounts.py#L220): eski kayıtların sahibi. Bir kez okunup bellekte tutulur. Veritabanı yoksa **oluşturmadan** `None` döner: testler ve ölçüm betikleri gerçek `data/` klasöründe dosya yaratmasın.
- Oturumlar:
  - [`new_session(user_id, days)`](../src/accounts.py#L240): rastgele bir belirteç üretir (`secrets.token_urlsafe`), veritabanına yalnızca **SHA-256 özetini** yazar, belirtecin kendisini döndürür (tarayıcı çerezine gidecek). Süresi geçmiş oturumları da temizler.
  - [`session_user(token)`](../src/accounts.py#L249): çerezden gelen belirteç geçerliyse hesabı döndürür. Çerez tarayıcıdan geldiği için her türlü değer olabilir; metin değilse `None`.
  - [`end_session(token)`](../src/accounts.py#L258): çıkışta oturumu siler.
- Komut satırı: `python -m src.accounts` hesapları listeler; `python -m src.accounts sifirla <kullanıcı_adı>` parolayı sıfırlar (unutulursa).

**Neden böyle?**
- **Kimlik giriş yönteminden ayrı:** kayıtlara `users.id` yazılır, kullanıcı adı yazılmaz. Böylece ileride aynı hesaba Google ya da telefonla girilse de geçmiş kopmaz; şema ve kayıtlar değişmez.
- **scrypt:** Python'un kendi `hashlib`'inde var, ek paket gerektirmez. Bilerek yavaş ve bellek isteyen bir özet işlevidir (~0,1 sn, 32 MB); parola dosyası ele geçse bile tahminle kırmayı pahalılaştırır. Parametreler özetin içinde durduğu için ileride güçlendirilirse eski parolalar yine doğrulanır.
- **Oturumda özet:** veritabanı dosyası kopyalansa bile içindeki özetlerle oturum açılamaz.

---

## `src/library.py` — belge kütüphanesi (240 satır)

**Ne işe yarar?** Her belgenin kaydını tutar: kimliği, görünen adı, sahibi, gizli ya da herkese açık oluşu, kimlerin erişebildiği. Yüklenen bir PDF'in sistemde zaten olup olmadığını **içeriğine bakarak** anlar.

**Bağlantılar**
- ← `ui/pages/documents.py` (yükleme, herkese açma, ad), `ui/data.py` (görünürlük, adlar), `export._doc_name`, `pipeline.run` (`sync`), `ui/auth.py`, testler.
- → `appdb`, `accounts.legacy_owner`, `pymupdf`, `config`.
- 💾 Okur/yazar: `data/app.sqlite` (`documents`, `doc_access`). Yazar: `data/sample_docs/<kimlik>.pdf`.

**Belge kimliği.** Kimlik (`doc`), belgenin veri dosyalarındaki anahtardır: `sample_docs/<doc>.pdf`, `parsed/<doc>.json`, parça kimliklerinin başı (`<doc>:p003:1`), `questions/<doc>_tr.jsonl`. Bir kez verilir ve **değişmez**; görünen ad ayrıdır ve sahibi değiştirebilir.
- Mevcut 6 belgenin kimliği bugünkü dosya adlarıdır. Değiştirmek bütün veriyi yeniden yazmak demekti; yerine kayda içerik özetleri eklendi.
- Yeni belgenin kimliği dosya adının köküdür. O ad alınmışsa sonuna içerik özetinin ilk 6 hanesi eklenir (`Hafta 3-1a2b3c`).

**Aynı belgeyi tanıma (yeniden işleme yok).** Karşılaştırma ad ya da sayfa sayısıyla değil, içerikle yapılır:
1. **Dosya özeti (SHA-256):** birebir aynı dosya, adı ne olursa olsun.
2. **Sayfa sayısı + her sayfanın metninin özeti:** dosyası farklı (yeniden kaydedilmiş, üst verisi değişmiş) ama içeriği aynı belge. Metni az olan (taranmış) belgede bu kademe atlanır, çünkü boş sayfalar her taranmış belgede eşleşirdi.
3. **Kısmen aynı** (notun yeni sürümü): ayrı belge sayılır. Değişen sayfalarda eski soruların kanıtı tutmazdı.

Eşleşen belge yükleyene açılır: hazır sorular, konu haritası ve dizin olduğu gibi kullanılır, kota harcanmaz.

**Görünürlük.** Belge, erişimi olanlara (onu yükleyenlere) görünür. Erişimi olan biri belgeyi herkese açabilir. Açılan belge **arayüzden yeniden gizlenemez**: başkalarının o belgeden hazırladığı sınavlar ve kayıtları boşa düşmesin diye. Acil durumda (ör. telif) bu bilgisayarda `python -m src.library gizle <belge>` ile kaldırılır.

**İçindekiler**
- [`file_hash(data)`](../src/library.py#L47): dosya baytlarının SHA-256 özeti.
- [`text_signature(data)`](../src/library.py#L51): (sayfa sayısı, sayfa metinlerinin özeti). Metin boşluk ve büyük/küçük harf farkından arındırılır. Sayfaların en az %80'i en az 30 karakter metin içermiyorsa özet `None` olur. PDF değilse `ValueError` verir; PyMuPDF HTML ve düz metni de açabildiği için `pdf_parser`'daki gibi biçime bakılır.
- [`_taken(con, key)`](../src/library.py#L75): bir anahtar kullanılmış mı? Kayıt, PDF ya da ondan türemiş veri (`parsed`, `topics`, `questions`) varsa evet. Silinmiş bir belgenin artığı kalmışsa yeni belge o artıkları devralmasın diye. Windows'ta dosya adları büyük/küçük harf duyarsız olduğu için karşılaştırma da öyle.
- [`_free_key(con, stem, sha)`](../src/library.py#L85): boş bir kimlik bulur: önce dosya adı, sonra `ad-<6 hane>`, sonra `ad-<12 hane>`. `:` işareti parça kimliğinde ayırıcı olduğu için atılır.
- [`_grant(con, doc, user_id)`](../src/library.py#L93): erişim verir; zaten varsa `False`.
- [`register(data, filename, user_id)`](../src/library.py#L100): yüklenen PDF'i kaydeder. Dönen durum:
  - `new`: yeni belge; dosya yazıldı, işlenmeyi bekliyor.
  - `same_file` / `same_content`: sistemde vardı (aynı dosya / aynı içerik); yükleyene açıldı, yeniden işlenmeyecek.
  - `already_yours`: zaten listesindeydi.
- [`sync()`](../src/library.py#L128): `sample_docs`'ta olup kayıtta olmayan PDF'leri kaydeder (girişten önceki belgeler, elle konanlar) ve sahipsiz kayıtları ilk hesaba bağlar. Arayüz 10 saniyede bir, `pipeline.run` her işte çağırır.
- [`visible(user_id)`](../src/library.py#L167): kişinin görebildiği belgeler: herkese açık olanlar + erişimi olanlar.
- [`get`](../src/library.py#L175), [`all_docs`](../src/library.py#L181), [`has_access`](../src/library.py#L186): okuma yardımcıları.
- [`publish(doc, user_id)`](../src/library.py#L191): belgeyi herkese açar. Yalnızca erişimi olan açabilir. Geri alma fonksiyonu yoktur (testi de bunu denetler).
- [`rename(doc, user_id, name)`](../src/library.py#L216): görünen adı değiştirir; yalnızca sahibi.
- [`display_name(doc)`](../src/library.py#L233): görünen ad. Dışa aktarma ve soru kartları her soru için çağırdığı için adlar 10 saniye bellekte tutulur.
- Komut satırı: `python -m src.library` kayıtlı belgeleri listeler (sahip, görünürlük, erişim sayısı).

**Neden böyle?** Eskiden belgenin kimliği dosya adıydı. Aynı adla farklı bir PDF yüklenince, boyutu farklıysa eskisinin üzerine yazılıyordu ve eski sorular, sayfa metinleri ve konu haritası yeni dosyayla karışıyordu. Boyutu aynıysa yeni dosya sessizce yok sayılıyordu. Şimdi hiçbir yükleme var olan bir belgenin üzerine yazmaz.

---

## `src/jsonl.py` — kayıt dosyalarına ekleme (28 satır)

**Ne işe yarar?** Kayıt dosyalarını okur ve sonlarına satır ekler.

**Bağlantılar**
- ← `request` (`record_attempt`, `report`), `cards` (`record`, `history`, `first_seen`), `review_store.save_decision`, `difficulty.real_attempts`.

**İçindekiler**
- [`read(path)`](../src/jsonl.py#L16): dosya yoksa boş liste.
- [`append(path, rows)`](../src/jsonl.py#L22): satırları **tek seferde** ve bir kilit altında ekler.

**Neden böyle?** Streamlit bütün oturumları tek süreçte, ayrı iş parçacıklarında çalıştırır. İki kişi aynı anda sınav bitirirse satırlar birbirine karışabilirdi; kilit bunu önler.

---

## `src/ui/auth.py` — giriş ekranı ve oturum (130 satır)

**Ne işe yarar?** Giriş yapılmamışsa giriş ekranını gösterir. Kenar çubuğunun altına kimin giriş yaptığını ve "Çıkış yap" düğmesini koyar.

**Bağlantılar**
- ← `app.py` (`current`, `page`, `sidebar`), `scripts/onizleme.py` (`?v=login`).
- → `accounts`, `library.sync`, `style`.
- Tarayıcı çerezi: `nr_oturum`.

**İçindekiler**
- [`current()`](../src/ui/auth.py#L26): giriş yapmış kişi. `session_state`'te yoksa tarayıcının gönderdiği çerezde geçerli bir oturum var mı diye **bir kez** bakar.
- [`_cookie(value, max_age)`](../src/ui/auth.py#L40): çerezi ana sayfaya yazar.
  - Streamlit çerezi okuyabiliyor (`st.context.cookies`) ama yazamıyor.
  - Bu yüzden görünmez bir çerçeve (`st.iframe`) içindeki küçük bir betik `window.parent.document.cookie`'ye yazar. Sınav ekranındaki klavye kısayolları da aynı yolla ana sayfaya erişiyor (bölüm 8).
- [`_sign_in(u, remember)`](../src/ui/auth.py#L48): kişiyi oturuma koyar. "Beni hatırla" seçiliyse yeni bir oturum belirteci alır ve çerez yazılmak üzere işaretlenir.
- [`_logout()`](../src/ui/auth.py#L56): oturumu veritabanından siler ve `session_state`'i tamamen temizler; açık sınav ve kart oturumu sıradaki kişiye kalmasın. Çerezi silmek için işaret bırakır.
- [`sidebar(u)`](../src/ui/auth.py#L65): kenar çubuğunun en altı (CSS ile dibe sabit; bölüm 13). Çerezi bu oturumda yazılacaksa burada yazar; profil resmi, ad, @kullanıcı adı ve "Çıkış".
- [`_login_form()`](../src/ui/auth.py#L81), [`_create_form(first)`](../src/ui/auth.py#L95): iki form. Hiç hesap yoksa "Hesap oluştur" açık gelir ve ilk hesabın eski kayıtların sahibi olacağı söylenir.
- [`page()`](../src/ui/auth.py#L121): giriş ekranının kendisi. Kenar çubuğu gizli, dar ve ortalı.

**Akış (tarayıcıda denendi):** giriş → çerez yazılır → sayfa yenilenince `current()` çerezden oturumu geri getirir → çıkış → oturum silinir, çerez temizlenir → yenileyince giriş ekranı.

**Dikkat:** çerezi sayfanın kendisi yazdığı için `HttpOnly` olamaz (sayfadaki bir betik okuyabilir). Bu bilgisayarda yerel kullanım için yeterli. Sistem internete açılırsa Google girişi (`st.login`) çerezi sunucuda, güvenli biçimde yazar.

---

## Kişiye bağlanan yerler (özet)

| Kayıt | Yazan | Kişi alanı | Okuyan |
|---|---|---|---|
| `attempts.jsonl` | [`request.record_attempt`](../src/request.py#L342) | `user`, ayrıca kesin zaman `t` | [`difficulty.real_attempts`](../src/difficulty.py#L234) → madde analizi ve Elo |
| `cards.jsonl` | [`cards.record`](../src/cards.py#L85) | `user` | [`cards.history(user=…)`](../src/cards.py#L66) → kişinin kutuları |
| `reports.jsonl` | [`request.report`](../src/request.py#L378) | `user` | `blocked_ids` (ortak havuz) |
| `reviews.jsonl` | [`review_store.save_decision`](../src/review_store.py#L74) | `user` | `decisions` (ortak havuz) |
| `requests/<id>.json` | [`request.prepare`](../src/request.py#L113) | `user` (hazırlayan) | — (sınavı bağlantıyla açan herkes kendi hesabıyla çözer) |

**"İlk deneme" artık kişinin ilk görüşü.** Eskiden "Baştan çöz" ve başka sınavda yine çıkan aynı soru da ilk deneme sayılıyordu; doğru oranı ve Elo şişiyordu. Şimdi [`fresh_attempts`](../src/difficulty.py#L213) her (kişi, soru) için yalnızca ilk çözümü ölçüme alır. Kartta cevabı daha önce görülmüş soru da sayılmaz (bölüm 10).

**Sayfalarda görünürlük.** Belge ya da içeriği gösteren her sayfa [`data.visible()`](../src/ui/data.py#L67) ile süzer: Belgeler (işlenmekte olanlar dahil), Sınav Hazırla, Bilgi Kartları, Soru Bankası, İnceleme ve Rapor'daki soru tablosu. Sınav bağlantısı (`?sinav=`) yalnızca sınavın belgelerini görebilen kişide açılır. Rapor'daki sistem toplamları (sayfa, soru sayısı) ve Modeller ve Kota sayfası ortaktır; içerik göstermez.

## İleride: Google ya da telefonla giriş

Bugünkü yapı bunun için hazır, şema değişikliği gerekmez:
1. **Google:** `pip install Authlib`, Google Cloud'da bir OAuth istemcisi, `.streamlit/secrets.toml`'a `[auth]` ayarları, giriş ekranına `st.login("google")` düğmesi. Dönüşte `st.user.sub` → `accounts.by_identity("google", sub)`; yoksa yeni hesap ya da var olan hesaba `accounts.link(..., "google", sub)`. Sabit bir https adresi ister, yani ancak sistem internete açılınca.
2. **Telefon:** doğrulama kodu (SMS) için dış bir servis gerekir. Hesaba `link(..., "phone", "+90…")` ile bağlanır.

## Testler

[`tests/test_accounts.py`](../tests/test_accounts.py) (geçici veritabanıyla, gerçek kayda dokunmaz):
- Parola özeti: tuz, yanlış parola, bozuk özet.
- Hesap kuralları: geçersiz kullanıcı adı, kısa parola, aynı ad ikinci kez alınamaz, kullanıcı adı büyük/küçük harf duyarsız, ilk hesap eski kayıtların sahibi.
- Oturum: geçerli belirteç, çıkış, süresi dolmuş, parola sıfırlayınca açık oturumların kapanması.
- Google için `link` / `by_identity`.
- Şema adımlarının bir kez uygulanması.
- Belge kütüphanesi: elle konan belge ilk hesaba bağlanır; aynı dosya başka adla ve aynı içerik farklı dosyayla tanınır; aynı ad farklı içerik üzerine yazmaz; yeni sürüm ayrı belge; iki farklı taranmış belge birbirine eşlenmez; PDF olmayan dosya reddedilir; gizli/açık ve tek yönlülük; adı yalnızca sahibi değiştirir; silinmiş belgenin artığı olan ad yeni belgeye verilmez.

`test_cards.test_per_user` (kutular kişiye özel, eski satırlar ilk hesabın) ve `test_difficulty.test_fresh_attempts` (tekrar çözme, ikinci deneme ve kartta görülmüş soru sayılmaz) de bu katmanı sınar.

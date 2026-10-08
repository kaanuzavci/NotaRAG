# NotaRAG — Claude için çalışma notları

"RAG Tabanlı Ders Dokümanlarından Soru ve Cevap Üretim Sistemi" (üniversite projesi, **teslim 3 Ocak 2027**). Sistem PDF ders
notlarından soru **ve** cevap üretir, doğrular, sınav olarak sunar; kullanıcı dokümana soru sormaz (chat modu kapsam dışı).
Odak **metinli (bilgisayarda yazılmış) PDF**; el yazısı ve taranmış notlar sonraki aşamada (kullanıcı kararı, 2026-10-07).
Kullanıcı Türkçe yazar; arayüz, belgeler ve istem dışı metinler Türkçe.

## Önce oku
- **ROADMAP.md → "Şu an neredeyiz?"**: güncel durum ve öncelik sıralı sıradaki işler; site tasarımı için hemen altındaki
  **"Tasarım: yeni oturumda devam"** bölümü (kullanıcının isteği, çalışma yöntemi, sıradaki işler, bilinen tuzaklar). Önemli bulgu, karar ve ölçümleri
  ROADMAP'in ilgili bölümüne yaz, "Sıradaki işler"i güncel tut.
- **README.md**: mimari, tasarım kararları (§4), kota mimarisi (§4.4), klasör yapısı (§6), çalıştırma (§8).
- **PROMPTS.md**: istemler. Kod istemleri buradan okur (`src/prompts.py`, `load_prompt("2c")` gibi) → bu dosyayı değiştirmek
  davranışı değiştirir; bölüm numaraları (§1, §2, §2b, §2c, §4a-e, §5-7) kodda geçer.
- **rehber/**: dosya dosya kod rehberi (kullanıcı kodu öğrenmek için okuyor). Kod değiştirince ilgili bölümü güncelle
  (yeni/silinen fonksiyon, değişen davranış), sonra `python scripts\rehber_satirlari.py --yaz` ile satır bağlantılarını hizala.
  Kullanıcıya hangi dosyaları neden değiştirdiğini ve nereye bağlandığını anlat.
- **data/kaynak_veri/BENIOKU.md**: indirilmiş deney verisi (MEB/ÖSYM soruları, Açık Ders notları, Belebele, TurkishMMLU…),
  `data/kaynaklar/` makaleler, `wheelhouse/` kurulmamış paketler (`pip install --no-index --find-links wheelhouse <paket>`).

## Çalıştırma (Windows, PowerShell 5.1, `.venv` Python 3.11)
- Arayüz arka planda: `Start-Process .venv\Scripts\streamlit.exe -ArgumentList "run src/app.py --server.headless true --server.port 8501" -RedirectStandardOutput data\streamlit.log -RedirectStandardError data\streamlit.err.log -WindowStyle Hidden`
  → http://localhost:8501 (sağlık: `/_stcore/health`). `src/ui/pages/*` dışındaki modüller değişince Streamlit'i yeniden başlat.
- Belge işleme: `python -m src.pipeline "<pdf kökü>"` (arayüzden yükleme de bunu ayrı süreçte başlatır → `data/jobs/<belge>.log`).
  Sınav istekleri → `data/requests/<id>.log`. İzleme: `python scripts\bekci.py` arka planda; çıkınca kullanıcıya bildir, yeniden başlat.
- Arayüz **giriş ister** (rehber 11; rol yok). Gerçek `data/app.sqlite`'ta **hesap açma/silme**: kullanıcının hesabı `kagan` (ilk hesap → eski kayıtların ve belgelerin sahibi).
- **Tasarım denemesi** (gerçek uygulama, geçici hesap veritabanı `data/tasarim/app.sqlite`, giriş deneme/parola123):
  `python scripts\tasarim.py baslat` → `ekran ":ana" "profile:profil" ":ana_hover:.stack:nth-child(3)"` (→ `data/tasarim/ekran/*.png`,
  Read ile bak) → `tikla "<seçici>|ad"` (gerçek fare tıklaması) → `durdur`. Yöntem ve tuzaklar: ROADMAP "Tasarım" bölümü.
  O kurulumda da sınav bitirmek / kart değerlendirmek gerçek JSONL'lere yazar: basma.
- Arayüzü görerek kontrol: `streamlit run scripts/onizleme.py --server.port 8502` (hazır verili ekranlar, geçici hesap veritabanıyla; `?v=session|flip|summary|quiz|results|setup|login|docs|home|home0|profile`; yazı tipleri önizlemede yüklenmez → son bakış `scripts\tasarim.py` ile) + `python scripts\ekran.py <url> <png>` (görünmez Edge + CDP; Read ile bak). Tasarım değişikliğini kullanıcıya göstermeden önce bununla bak.
- Kota durumu: `python -m src.llm.capacity`. Testler (API çağırmaz): `python -m tests.<ad>` (README §8'deki liste).
- **Uzun ölçüm/deney** (`eval/*`): ayrı Windows süreci olarak başlat (`Start-Process … -WindowStyle Hidden`, günlük `data/*.log`);
  Bash arka plan görevi VS Code / oturum yeniden başlayınca ölüyor. Betikler kaldığı yerden devam eder (`data/<deney>/olcumler.jsonl`),
  4 parça paralel en hızlısı (`--parca k/4`); örnek komut ROADMAP "Yeni oturumda ilk işler"de. Süreç asılı kalırsa ilerleme
  dosyasının satır sayısı artmaz: `tasklist` + günlüğe bak, gerekirse durdurup yeniden başlat (veri kaybolmaz).

## Kurallar
- **Anahtarlar** yalnızca `.env` (ileride `secrets/vertex.json`); asla tam anahtar yazdırma (maskele), kullanıcıdan sohbete
  yapıştırmasını isteme.
- **Kalite kapısı**: bir rolde yalnızca `APPROVED` modeller (`src/llm/models.py`); kota dolunca daha zayıf modele geçilmez,
  iş bekler. Yeni model → `python -m src.qualify <model>` + kanıtıyla `APPROVED`. **Aile kuralı**: doğrulayıcı üreticiden farklı aileden.
- **Kota pahalı**: her LLM çağrısı ücretsiz kotadan yer. Belge işleme / toplu üretim gibi büyük işleri başlatmadan önce
  kullanıcıya söyle; yanıtlar `data/llm.sqlite`'ta önbellekli. Gemini'de **başarısız (503) istek de günlük kotadan düşer**: elle
  sık yeniden deneme döngüsü kurma (router zaten artan sürelerle bekler). Gemma (ölçüm rolü) ayrı ve bol kotalı ama 31B bazen çok yavaş.
- **Yasak yollar** (kullanıcı kararı / sağlayıcı kuralları): yerel LLM/GPU iş yükü (dizüstü RTX 4060), BYOK, birden çok hesap
  ya da anahtar döndürme. İnternet çoğunlukla hotspot: büyük indirmelerden (onlarca MB+) önce sor. Yerel OCR (Tesseract) ve
  yerel ONNX modelleri (`pymupdf_layout`) indirildi ama kullanılmadan önce kullanıcı onayı ister.
- **Veri bütünlüğü**: soru kimliği = sha1(model|soru metni)[:12]; insan kararları, çözüm kayıtları (`data/review/attempts.jsonl`)
  ve bildirimler bu kimliğe bağlı → `data/questions/*.jsonl` üzerine yazılmaz (`pipeline.merge_existing` ekler).
  Kişiye ait kayıtlar (`attempts`, `cards`, `reports`, `reviews`) `"user"` alanıyla; alanı olmayan eski satırlar ilk hesabın
  (`accounts.legacy_owner`). Belge kimliği = veri dosyalarındaki anahtar, değişmez; yükleme `library.register` ile (üzerine yazmaz).
- **Kod yazımı**: kaçış karakteri içeren Python kodunu bash heredoc ile yazma (`\b`, `\\` bozuldu) → Edit/Write kullan.
  Çevredeki kodun yoğunluğu ve Türkçe yorum/isim üslubuyla yaz.
- **Streamlit 1.59**: aynı etiketli düğmelere `key=` (yoksa `StreamlitDuplicateElementId`); `st.iframe` (components.html
  kullanımdan kalktı); `st.container(key="x")` → CSS sınıfı `.st-key-x`; tarayıcısız test `streamlit.testing.v1.AppTest`.
  Geçici betiklere pip paketi adı verme (`bottleneck.py` pandas'ın içe aktarmasını bozdu).
  Tıklanabilir özel HTML (ana sayfa desteleri) → CCv2 (`st.components.v2.component`, `src/ui/shelf.py`; v1 API'leri yasak).
  Sınıf adı seçmeden önce `src/ui/style.py`'de aynı ad var mı bak (`.nr-weak`, `.nr-tiles`, `.nr-legend` çakıştı).

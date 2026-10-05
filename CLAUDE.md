# NotaRAG — Claude için çalışma notları

"RAG Tabanlı Ders Dokümanlarından Soru ve Cevap Üretim Sistemi" (üniversite projesi, **teslim 3 Ocak 2027**). Sistem PDF ders
notlarından soru **ve** cevap üretir, doğrular, sınav olarak sunar; kullanıcı dokümana soru sormaz (chat modu kapsam dışı).
Kullanıcı Türkçe yazar; arayüz, belgeler ve istem dışı metinler Türkçe.

## Önce oku
- **ROADMAP.md → "Şu an neredeyiz?"**: güncel durum ve öncelik sıralı sıradaki işler. Önemli bulgu, karar ve ölçümleri
  ROADMAP'in ilgili bölümüne yaz, "Sıradaki işler"i güncel tut.
- **README.md**: mimari, tasarım kararları (§4), kota mimarisi (§4.4), klasör yapısı (§6), çalıştırma (§8).
- **PROMPTS.md**: istemler. Kod istemleri buradan okur (`src/prompts.py`, `load_prompt("2c")` gibi) → bu dosyayı değiştirmek
  davranışı değiştirir; bölüm numaraları (§1, §2, §2b, §2c, §4a-e, §5-7) kodda geçer.
- **rehber/**: dosya dosya kod rehberi (kullanıcı kodu öğrenmek için okuyor). Kod değiştirince ilgili bölümü güncelle
  (yeni/silinen fonksiyon, değişen davranış), sonra `python scripts\rehber_satirlari.py --yaz` ile satır bağlantılarını hizala.
  Kullanıcıya hangi dosyaları neden değiştirdiğini ve nereye bağlandığını anlat.

## Çalıştırma (Windows, PowerShell 5.1, `.venv` Python 3.11)
- Arayüz arka planda: `Start-Process .venv\Scripts\streamlit.exe -ArgumentList "run src/app.py --server.headless true --server.port 8501" -RedirectStandardOutput data\streamlit.log -RedirectStandardError data\streamlit.err.log -WindowStyle Hidden`
  → http://localhost:8501 (sağlık: `/_stcore/health`). `src/ui/pages/*` dışındaki modüller değişince Streamlit'i yeniden başlat.
- Belge işleme: `python -m src.pipeline "<pdf kökü>"` (arayüzden yükleme de bunu ayrı süreçte başlatır → `data/jobs/<belge>.log`).
  Sınav istekleri → `data/requests/<id>.log`. İzleme: `python scripts\bekci.py` arka planda; çıkınca kullanıcıya bildir, yeniden başlat.
- Arayüzü görerek kontrol: `streamlit run scripts/onizleme.py --server.port 8502` (hazır verili ekranlar, `?v=session|flip|summary|quiz|results|setup`) + `python scripts\ekran.py <url> <png>` (görünmez Edge + CDP; Read ile bak). Tasarım değişikliğini kullanıcıya göstermeden önce bununla bak.
- Kota durumu: `python -m src.llm.capacity`. Testler (API çağırmaz): `python -m tests.<ad>` (README §8'deki liste).

## Kurallar
- **Anahtarlar** yalnızca `.env` (ileride `secrets/vertex.json`); asla tam anahtar yazdırma (maskele), kullanıcıdan sohbete
  yapıştırmasını isteme.
- **Kalite kapısı**: bir rolde yalnızca `APPROVED` modeller (`src/llm/models.py`); kota dolunca daha zayıf modele geçilmez,
  iş bekler. Yeni model → `python -m src.qualify <model>` + kanıtıyla `APPROVED`. **Aile kuralı**: doğrulayıcı üreticiden farklı aileden.
- **Kota pahalı**: her LLM çağrısı ücretsiz kotadan yer. Belge işleme / toplu üretim gibi büyük işleri başlatmadan önce
  kullanıcıya söyle; yanıtlar `data/llm.sqlite`'ta önbellekli.
- **Yasak yollar** (kullanıcı kararı / sağlayıcı kuralları): yerel LLM/GPU iş yükü (dizüstü RTX 4060), BYOK, birden çok hesap
  ya da anahtar döndürme. İnternet hotspot: büyük indirmelerden (onlarca MB+) önce sor.
- **Veri bütünlüğü**: soru kimliği = sha1(model|soru metni)[:12]; insan kararları, çözüm kayıtları (`data/review/attempts.jsonl`)
  ve bildirimler bu kimliğe bağlı → `data/questions/*.jsonl` üzerine yazılmaz (`pipeline.merge_existing` ekler).
- **Kod yazımı**: kaçış karakteri içeren Python kodunu bash heredoc ile yazma (`\b`, `\\` bozuldu) → Edit/Write kullan.
  Çevredeki kodun yoğunluğu ve Türkçe yorum/isim üslubuyla yaz.
- **Streamlit 1.59**: aynı etiketli düğmelere `key=` (yoksa `StreamlitDuplicateElementId`); `st.iframe` (components.html
  kullanımdan kalktı); `st.container(key="x")` → CSS sınıfı `.st-key-x`; tarayıcısız test `streamlit.testing.v1.AppTest`.
  Geçici betiklere pip paketi adı verme (`bottleneck.py` pandas'ın içe aktarmasını bozdu).

# 2. Metin işleme ve PDF okuma

[← 1. Giriş kapıları](01-giris-ve-ayarlar.md) · [Ana sayfa](README.md) · Sonraki: [3. Bölümleme ve arama →](03-bolumleme-ve-arama.md)

Sistemin kalitesi burada başlar. PDF'ten yanlış okunan bir metin yanlış soruya dönüşür (ör. `2ⁿ`'in `2n` diye okunması). Bu bölümde beş dosya var:
- [`textnorm.py`](../src/textnorm.py): ortak metin dönüşümleri.
- [`pdf_parser.py`](../src/ingestion/pdf_parser.py): PDF → yapılandırılmış sayfalar.
- [`vision.py`](../src/ingestion/vision.py): resim olan sayfaları görsel modele okutur.
- [`ingestion/__main__.py`](../src/ingestion/__main__.py): komut satırı.
- [`ingestion/review.py`](../src/ingestion/review.py): okuma kontrol sayfası.

---

## `src/textnorm.py` — Türkçe'ye duyarlı metin dönüşümleri (211 satır)

**Ne işe yarar?** PDF'ten gelen satırları temizler, Türkçe büyük/küçük harf sorununu çözer ve karşılaştırma için metni "düzleştirir". Ayrıca BM25 için kelime kökü çıkarır, dili tahmin eder ve formülleri ekranda okunur gösterir. Kendisi hiçbir proje modülünü içe aktarmaz: en alttaki yapı taşıdır.

**Neden tek dosyada?** Kanıt alıntısı kontrolü, LLM'in yazdığı alıntıyla PDF'ten okunan metni karşılaştırır. İki taraf **aynı** dönüşümden geçmezse doğru bir alıntı bile "metinde yok" sayılır. Bu yüzden herkes aynı fonksiyonu kullanır.

**Bağlantılar**
- ← 14 dosya: pdf_parser, vision, chunker, index, checks, verify, grading, review_store, requote, export, ui (components, quiz, bank), tests.

**İçindekiler**

*Sabitler (satır 10-25):*
- `_PUA`: sembol fontlarından gelen özel karakterler (Wingdings madde işaretleri).
- `_CONTROL`: kontrol karakterleri.
- `_BULLET_CHARS`: madde işaretleri.
- `_QUOTES`: tırnak türlerini düz tırnağa çeviren tablo.
- `SUP` / `SUB`: normal karakter → üst/alt simge (`"2"` → `"²"`, `"1"` → `"₁"`).
- `LINEBREAK_HYPHEN`: satır sonu tiresini işaretleyen özel karakter (U+2010).

*Fonksiyonlar:*
- [`to_script(text, sup)`](../src/textnorm.py#L28): `"n"` → `"ⁿ"`, `"12"` → `"¹²"`. Karşılığı olmayan karakter varsa `^(…)` / `_(…)` yazar. PDF okuyucu küçük ve yükseltilmiş yazıyı bununla üs yapar.
- [`nfkc_keep_scripts(s)`](../src/textnorm.py#L42): Unicode **NFKC** normalleştirmesi uygular (`ﬁ` → `fi`, `𝑓` → `f`) ama üst/alt simgeleri korur. Düz NFKC `x²`'yi `x2` yapıyordu; metin matematiksel olarak yanlışlaşıyordu.
- [`clean_line(line)`](../src/textnorm.py#L48): tek bir PDF satırını temizler. Satır başındaki tuhaf madde işaretini `"• "` yapar, yumuşak tireyi ve kontrol karakterlerini siler, tırnakları düzler, fazla boşlukları teke indirir.
- [`is_bullet(line)`](../src/textnorm.py#L62): satır madde işaretiyle mi başlıyor?
- [`join_lines(lines)`](../src/textnorm.py#L66): aynı bloktaki satırları paragrafa birleştirir.
  - Madde işaretli satır yeni satırda başlar.
  - `bilgisa-` + `yar` gibi satır sonu tirelemesini `bilgisa‐yar` diye **işaretler**, henüz birleştirmez. Çünkü `meta-sezgisel` gerçek bir bileşik kelime de olabilir; tek satıra bakarak bu anlaşılmaz.
- [`resolve_hyphens(texts, language)`](../src/textnorm.py#L91): işaretlenen tireleri **belgenin tamamına bakarak** çözer:
  - Belgede başka yerde `bütün` geçiyorsa `bü‐tün` → `bütün`.
  - `meta-sezgisel` geçiyorsa tire korunur.
  - İkisi de yoksa Türkçe'de birleştirir (satır sonu bölmesi hecedir), İngilizce'de tireyi korur.
- [`pretty_math(s)`](../src/textnorm.py#L128): **yalnızca ekranda gösterim** için. Saklanan veri değişmez. Görsel modelin yazdığı LaTeX'i ve `^` gösterimini okunur Unicode'a çevirir (`\frac{a}{b}` → `a/b`, `2^n` → `2ⁿ`, `(n choose 2)` → `C(n, 2)`).
- [`tr_lower(s)`](../src/textnorm.py#L155): Türkçe küçük harf. Python'un `"I".lower()` sonucu `"i"`'dir, Türkçe'de doğrusu `"ı"`.
- [`normalize_for_match(s)`](../src/textnorm.py#L160): karşılaştırma için agresif düzleştirme. Satır sonu tirelerini ve LaTeX komutlarını atar, küçük harf yapar, **ı/i farkını da siler**, noktalamayı boşluğa çevirir.
  - LLM `İstanbul` yerine `Istanbul` yazabilir; İngilizce `IITG` Türkçe kurala göre `ııtg` olur. Bu yüzden ı/i katlanır.
  - Başka dosyalarda genelde `norm` takma adıyla içe aktarılır.
- [`f5_tokens(text, prefix=5)`](../src/textnorm.py#L188): BM25 araması için kelime listesi. Normalize eder, gereksiz kelimeleri (`ve`, `the`) atar, her kelimenin **ilk 5 harfini** alır.
  - Türkçe eklemeli bir dil: `algoritmalarda`, `algoritmanın`, `algoritma` → hepsi `algor`.
  - Kaynak: Can vd., 2008.
- [`detect_language(text)`](../src/textnorm.py#L201): `"tr"` / `"en"` / `"unknown"`. Türkçe harf sayısı (ç, ğ, ı, ö, ş, ü) ve sık kelimelerle basit bir puanlama yapar; ek paket gerektirmez.

Testler: [`tests/test_textnorm.py`](../tests/test_textnorm.py).

---

## `src/ingestion/pdf_parser.py` — PDF'ten yapılandırılmış sayfalara (528 satır)

**Ne işe yarar?** PyMuPDF ile PDF'in metin katmanını okur ve her sayfa için şunları çıkarır:
- başlık (ve başlığın nereden bulunduğu)
- gövde metni
- şekil üzerindeki metin
- kalite etiketi (`ok` / `needs_vision` / `empty`)
- bayraklar ve dil

Bu dosya kendisi hiçbir LLM çağırmaz. Resim olan sayfaları yalnızca `needs_vision` diye **işaretler**; okumayı `vision.py` yapar.

**Bağlantılar**
- ← `pipeline.run`, `ingestion/__main__`, `tests/test_parser`.
- → `textnorm` (clean_line, join_lines, resolve_hyphens, to_script, detect_language), `pymupdf`.

**Çıktısı** (`data/parsed/<belge>.json`):
```jsonc
{"file": "english.pdf", "title": "...", "language": "en", "n_pages": 90,
 "header_footer_patterns": ["r.k. bhattacharjya/ce/iitg", "..."],
 "pages": [{"page": 5, "heading": "...", "heading_source": "toc|visual|inherited", "text": "...",
            "figure_text": "etiket | etiket", "quality": "ok|needs_vision|empty", "char_count": 812,
            "language": "en", "flags": ["tables_extracted"], "removed_lines": 3, "source": "text"}]}
```
`vision.apply_cached_vision` sonradan bu yapıya `source: "vision"`, `vision_model`, `text_layer` gibi alanlar ekler.

**Sabitler ([satır 19-35](../src/ingestion/pdf_parser.py#L19)):** Her eşik bir ölçümden ya da bulunmuş bir hatadan gelir. Örnekler:
- `REPEAT_MIN_RATIO = 0.4`: sayfaların %40'ında tekrar eden satır üst/alt bilgi adayıdır.
- `MIN_TEXT_CHARS = 80`: bundan kısa gövde "az metinli" sayılır.
- `NOISY_RATIO = 0.4`: satırların %40'ı anlamsız parçaysa metin katmanı bozuktur.

**Veri sınıfları:**
- [`Line`](../src/ingestion/pdf_parser.py#L39): bir satırın metni, yazı boyutu, kutusu (bbox) ve blok numarası.
- [`PageResult`](../src/ingestion/pdf_parser.py#L47): sayfa sonucu. `asdict()` ile JSON'a çevrilir.

**Fonksiyonlar (gruplar halinde):**

*a) Satırları okuma*
- [`_line_text(l)`](../src/ingestion/pdf_parser.py#L64): bir satırın parçalarını (span) birleştirir. En önemli inceliği **üs ve indis tespiti**: küçük yazılmış ve satır tabanından yukarıdaysa üst simge (`2ⁿ`), aşağıdaysa alt simge (`x₁`) yapar.
  - "Yukarı" yönü satırın yazı yönüne göre hesaplanır (`dir` = cos, sin). Böylece 90° döndürülmüş slaytlarda da doğru çalışır.
  - Matematik italik harfli (𝑥, 𝑓) denklem editörü satırlarında konum güvenilmez olduğu için dokunmaz.
- [`_visual_lines(page)`](../src/ingestion/pdf_parser.py#L91): sayfanın bütün metin satırlarını `Line` listesi olarak döndürür.
  - Koordinatlar sayfanın döndürme matrisiyle çarpılıp "görünen" koordinatlara çevrilir.
  - Bloklar ekrandaki konumlarına göre (yukarıdan aşağı, soldan sağa) sıralanır. Blok içindeki satırların sırası korunur; satır bazında sıralama liste numaralarını metnin sonuna kaydırıyordu.

*b) Görseller ve şekiller*
- [`_template_xrefs(doc)`](../src/ingestion/pdf_parser.py#L115): sayfaların ≥%40'ında tekrar eden görseller (slayt şablonu, logo).
- [`_content_images(page, template)`](../src/ingestion/pdf_parser.py#L123): şablon olmayan ve sayfanın %90'ından küçük görsellerin konumları.
- [`_full_page_image(page, template)`](../src/ingestion/pdf_parser.py#L135): sayfayı (%90+) kaplayan, şablon olmayan görsel var mı? Taranmış sayfa ya da tam sayfa fotoğraf. `_content_images` bunları slayt arka planı sayıp atıyor; metin de yoksa sayfa `ok` sanılıyor, bölümleyici "boş" diye atlıyordu. 2026-10-06 testinde 192 sayfalık taranmış bir ders kitabından bu yüzden hiç soru çıkmazdı.
- [`_figure_regions(page, images)`](../src/ingestion/pdf_parser.py#L147): görseller + vektör çizim kümeleri (diyagramlar).
- [`_cover(rects, page)`](../src/ingestion/pdf_parser.py#L161): bu alanlar sayfanın yüzde kaçını kaplıyor?

*c) Üst/alt bilgi ve sayfa numarası temizliği*
- [`_hf_key(text)`](../src/ingestion/pdf_parser.py#L165): karşılaştırma anahtarı (küçük harf, rakamlar `#`). `"Sayfa 7"` ile `"Sayfa 8"` aynı kalıp sayılır.
- [`_find_header_footer(pages_lines)`](../src/ingestion/pdf_parser.py#L169): belgenin ≥%40'ında (en az 3 sayfada) tekrar eden satırları bulur. Bir koşulu daha var: bulunduğu sayfalarda **en büyük yazı olmayanlar**. Bu sayede ardışık slaytlarda tekrar eden başlıklar ("Organik Tarım") silinmez.
- [`_page_number_offset(pages_lines)`](../src/ingestion/pdf_parser.py#L321): basılı sayfa numarası ile PDF sayfa sırası arasındaki sabit farkı belge genelinde oylamayla bulur.
  - Aday satır `isdecimal()` ile seçilir, `isdigit()` ile değil: "²" `isdigit()` geçer ama sayıya çevrilemez; üslü bir fizik notu ayrıştırıcıyı çökertiyordu (2026-10-06).
  - Eski kural her sayfada "sayfa_no ± 2" olan sayıları siliyordu; bir diyagramdaki dört `22` değeri bu yüzden silinmişti.
- [`_page_number_line(lines, number, rect)`](../src/ingestion/pdf_parser.py#L337): o sayfada numarayı taşıyan **tek** satır (kenara en yakın aday).
- [`_strip_split_footer(row, hf_texts)`](../src/ingestion/pdf_parser.py#L303): tablo hücrelerine bölünerek sızmış alt bilgiyi temizler (`'2 7 Novem' | '0.286 ber 2013'`).

*d) Paragraflar ve tablolar*
- [`_paragraphs(lines)`](../src/ingestion/pdf_parser.py#L190): aynı bloktaki satırları `join_lines` ile paragraf yapar. PowerPoint'in ayrı bloğa koyduğu devam satırlarını (küçük harfle başlayan, önceki noktalamasız biten) birleştirir.
- [`_tables(page, hf, pno, hf_texts)`](../src/ingestion/pdf_parser.py#L246): PyMuPDF'in `find_tables()` tablo bulucusunu işlemcide çalıştırır (GPU yok, milisaniyeler sürer). Sahte tabloları eler:
  - 2×2'den küçük olanlar
  - hücrelerinin yarısından azı dolu olanlar
  - satırlarının %40'ından fazlasında tek hücre dolu olanlar
- [`_clean_cell(cell, hf, pno)`](../src/ingestion/pdf_parser.py#L238): hücredeki üst/alt bilgiyi ve sayfa numarasını siler. 8 satırdan uzun hücre aslında başka tabloları içine almış bir "konteyner"dır; boşaltılır.
- [`_table_md(rows)`](../src/ingestion/pdf_parser.py#L214): tabloyu Markdown tablosuna çevirir. Hücrelerin hepsi aynı sayıda alt satır içeriyorsa satır satır açar; eşleşmeler korunur.

*e) Bozuk metin dedektörleri*
- [`_is_noisy(text)`](../src/ingestion/pdf_parser.py#L279): satırların ≥%40'ı (en az 4 satır) "parça" mı? Parça satır, 3+ harfli en az 2 kelime içermeyen satırdır. Ya da herhangi bir satır dağılmış formül mü?
  - Tablo/formül içeren sayfalarda metin katmanı bozuk geliyor ama eskiden `ok` sayılıyordu. Bu dedektör 17 sayfa buldu; incelenen 5'in 5'i gerçekten bozuktu.
- [`_garbled_formula(line)`](../src/ingestion/pdf_parser.py#L291): en az 6 kelime ve kelimelerin yarısından fazlası tek karakter (`'( ) nx x x ,... , 2 1'`) ise dağılmış formüldür. Yalnızca sayılardan oluşan satır (tablo satırı) formül sayılmaz.

*f) Başlık bulma (dört kaynak, öncelik sırasıyla)*
1. [`_toc_titles(doc)`](../src/ingestion/pdf_parser.py#L344): PDF'in içindekiler listesi (yer imleri). `"Slayt 11"` gibi içeriksiz girişler atlanır. Tarayıcı yer imleri (`"B1 Ders Kitabı 22.07.2015_Sayfa_001"`, …: sayfaların ≥%80'inde bir giriş ve rakamlar dışında hepsi aynı) başlık sayılmaz; liste hiç kullanılmaz.
2. [`_visual_heading(lines, page_h)`](../src/ingestion/pdf_parser.py#L380): sayfanın üst %35'inde, gövdeden en az 1,2 kat büyük yazılmış satır(lar).
   - Tek satırlık slaytta ≥24 punto satır başlıktır.
   - Bulamazsa [`_top_band_heading`](../src/ingestion/pdf_parser.py#L371)'e bakar: gövdeyle aynı puntoda ama en üst %12'lik şeritteki satırlar.
3. Bulunamazsa önceki sayfanın başlığı devralınır (`heading_source = "inherited"`).
4. [`_body_size(pages_lines)`](../src/ingestion/pdf_parser.py#L360) belgenin baskın gövde yazı boyutunu verir (karakter sayısıyla ağırlıklı medyan). Başlık ve etiket kararlarında ölçü olarak kullanılır.

**Ana fonksiyon: [`parse_pdf(path)`](../src/ingestion/pdf_parser.py#L401)**
1. Dosya gerçekten PDF mi? (PyMuPDF HTML/metin de açıyor; `.pdf` adlı bir hata sayfası "1 sayfalık belge" sanılıyordu → `ValueError`.) Sonra bütün sayfaların satırlarını oku, belge genelinde üst/alt bilgi kalıplarını, içindekileri, şablon görselleri, gövde boyutunu ve sayfa numarası farkını hesapla.
2. Her sayfa için:
   - sayfa numarası satırını ve üst/alt bilgiyi at (`removed_lines`);
   - başlığı bul;
   - kısa ve küçük yazılmış ya da şeklin üstünde duran satırları **şekil etiketi** (`figure_text`) olarak ayır. Bunlar silinmez, gövdeye de karışmaz.
3. Gövde bozuksa (`_is_noisy`): önce tabloyu işlemcide çıkarmayı dene, tablo alanındaki dağınık satırları metinden düş.
4. Kaliteye karar ver:
   - taranmış sayfa (metin <80 karakter ve sayfayı kaplayan görsel, `_full_page_image`) → `needs_vision` + `scanned`; kapak kuralından önce gelir, çünkü taranmış notun 1. sayfası çoğu zaman içeriktir;
   - kapak (ilk sayfa, <300 karakter) → `ok` + `title_page`;
   - hâlâ bozuk → `needs_vision` + `noisy_text`;
   - yeterli metin → `ok`;
   - az metin + büyük görsel → `needs_vision`;
   - hiç metin yok → `empty`.
5. Bayraklar: içindekiler benzeri sayfa (`toc_like`: satırların ≥%80'i kısa numaralı başlık), görsel ağırlıklı sayfa (`image_heavy`), taranıp OCR'lanmış sayfa (`ocr_layer`: sayfayı kaplayan görüntünün üstünde metin var; bu metin PDF'ten birebir gelmez, OCR tahminidir).
6. Bütün sayfalar bitince satır sonu tirelerini **belge düzeyinde** çöz (`resolve_hyphens`), belge dilini ve başlığını belirle.
   - Dil yalnızca `ok` sayfalardan hesaplanır. Taranmış notun bozuk OCR katmanı (`'rmuuumvmuuıuuuuuııui'`) Türkçe el yazısını `en` gösteriyordu, sorular İngilizce üretilirdi. Hiç sağlam sayfa yoksa dil `unknown` olur; görsel okumadan sonra `vision.apply_cached_vision` yeniden belirler.
   - İlk sayfa görsel okuma bekliyorsa (taranmış ya da bozuk) başlık dosya adıdır.

Testler: [`tests/test_parser.py`](../tests/test_parser.py). Her test bulunmuş bir hatayı sabitler.

---

## `src/ingestion/vision.py` — resim olan sayfaları okuma (150 satır)

**Ne işe yarar?** `needs_vision` işaretli sayfaları 150 dpi JPEG'e çevirir ve görsel modele (Gemini, yedeği qwen) **PROMPTS.md §1** ile okutur. Sonucu önbelleğe yazar. Her sayfa yalnızca bir kez gönderilir.

**Bağlantılar**
- ← `pipeline` (`run_vision`, `pending_pages`, `apply_cached_vision`), `ingestion/__main__`.
- → `llm.router.call("vision", ...)`, `prompts.load_prompt("1")`, `textnorm`, `rapidfuzz`, `pymupdf`.
- 💾 Okur/yazar: `data/vision_cache/<belge>_pNNN.md`, `data/vision_cache/_models.json`, `data/parsed/<belge>.json`.

**İçindekiler**
- [`_cache_path(pdf, page)`](../src/ingestion/vision.py#L19): önbellek dosyasının yolu (`english_p052.md`).
- [`_models()`](../src/ingestion/vision.py#L27) / [`_record_model(cache, model)`](../src/ingestion/vision.py#L32): hangi sayfanın hangi modelle okunduğunu `_models.json`'da tutar. Arayüzde ve raporda gösterilir.
- [`_render(pdf, page)`](../src/ingestion/vision.py#L38): sayfayı JPEG baytlarına çevirir.
- [`pending_pages(parsed, pdf)`](../src/ingestion/vision.py#L43): `needs_vision` olup önbellekte henüz olmayan sayfalar.
- [`estimate_upload_bytes(pdf, pages)`](../src/ingestion/vision.py#L49): gönderilecek toplam boyut. Mobil internet için önce sorulur.
- [`_text_layer(page)`](../src/ingestion/vision.py#L53): ayrıştırıcının o sayfadan çıkardığı (bozuk da olsa) metin. İsteme **yazım ipucu** olarak eklenir; model kelimeleri doğru yazsın diye. `ocr_layer` sayfasında `(empty)` döner: OCR katmanı tahmindir (el yazısında çöp), ne ipucu ne de `snap_to_text_layer` için yazım otoritesi olur ("ΔT" doğru okuması "AT" katmanına çekilmesin).
- [`run_vision(parsed_path, pdf)`](../src/ingestion/vision.py#L63): bekleyen her sayfa için `call("vision", istem, image=...)` çağırır ve sonucu önbelleğe yazar.
  - Bütün görsel modellerin kotası doluysa (`AllModelsExhausted`) o ana kadar okunanları uygular ve `False` döner. `pipeline._vision_until_done` bekleyip tekrar çağırır.
- [`snap_to_text_layer(md, layer)`](../src/ingestion/vision.py#L88): görsel modelin satırı metin katmanındaki bir satıra ≥%88 benziyor ama aynı değilse, satırı metin katmanının yazımıyla değiştirir.
  - Metin katmanı PDF'ten birebir geldiği için yazımda otoritedir; görsel model `"çöpe gidiyor"` yerine `"çöp gidiyor"` yazabilir.
- [`repair_from_layer(md, layer)`](../src/ingestion/vision.py#L108): eski önbellek kayıtlarındaki bozuk üs ve tire yazımlarını düzeltilmiş metin katmanından onarır. Yeni istek atmaz, kota harcamaz.
- [`apply_cached_vision(parsed_path, pdf)`](../src/ingestion/vision.py#L134): internetsiz çalışır. Önbellekteki okumaları JSON'a yazar:
  - `text` = görsel okuma (snap + repair'den geçmiş);
  - eski metin `text_layer` alanına taşınır;
  - `source = "vision"`, `quality = "ok"`.
  - Sonra belge dili görsel okunan sayfalar dahil yeniden hesaplanır (taranmış belgede okuma öncesi `unknown` ya da yanlıştı).

---

## `src/ingestion/__main__.py` — `python -m src.ingestion` (73 satır)

**Ne işe yarar?** Bütün PDF'leri ayrıştırır, önbellekteki görsel okumaları uygular ve her belge için bir özet basar. Pipeline'dan bağımsız, elle çalıştırılan bir araçtır.

- [`main()`](../src/ingestion/__main__.py#L36):
  - Argümansız: yalnızca ayrıştırır (internetsiz).
  - `--vision`: kaç sayfa / kaç MB gönderileceğini ve bugün hangi görsel modellerin kotası olduğunu gösterir; **hiçbir şey göndermez**.
  - `--vision --yes`: gerçekten gönderir. Kota dolunca diğer belgeleri denemez.
- [`_summary(doc)`](../src/ingestion/__main__.py#L21): belge özeti. Başlık kaynakları, silinen satırlar, görsel okuma bekleyen ve okunmuş sayfalar, bayraklar.

## `src/ingestion/review.py` — okuma kontrol sayfası (87 satır)

**Ne işe yarar?** `python -m src.ingestion.review` → `data/review/index.html`. Her sayfanın küçük görüntüsü solda, sistemin çıkardığı metin sağda durur. Okumanın doğruluğunu gözle denetlemek için kullanılır; internetsizdir.

- [`main()`](../src/ingestion/review.py#L38): `data/parsed/*.json` ve `data/chunks/skipped.jsonl` dosyalarını okur. Her sayfayı 70 dpi JPEG olarak `data/review/img/` altına kaydeder ve etiketlerle (görselden okundu, kalite, bayraklar, dizin dışı nedeni) tek bir HTML dosyası yazar. `CSS` sabiti açık/koyu tema renklerini içerir.

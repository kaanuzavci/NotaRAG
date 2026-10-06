"""Model kayıt defteri: her iş (rol) için sıralı model zinciri ve bilinen ücretsiz katman limitleri.

Kotalar model başına ayrı tutulur; bir model günlük kotasını doldurunca zincirdeki sıradakine geçilir.
Limitler ölçümle bulundu (2026-10-01/02) ve sağlayıcılar değiştirebilir; 429 gelirse defter
modeli o gün için zaten "dolu" işaretler, buradaki sayılar yalnızca gereksiz denemeyi önler.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str            # gemini | groq | openrouter | cerebras | mistral (son üçü OpenAI uyumlu, router._OPENAI_COMPAT)
    rpd: int | None          # istek/gün (None = bilinmiyor)
    rpm: int | None = None   # istek/dakika
    tpm: int | None = None   # token/dakika
    tpd: int | None = None   # token/gün (Groq: kayan 24 saat penceresi; asıl bağlayıcı sınır)
    vision: bool = False
    tz: str = "UTC"          # günlük kotanın sıfırlandığı saat dilimi


MODELS: dict[str, ModelSpec] = {m.name: m for m in [
    # Gemini: günlük kota Pasifik gece yarısı sıfırlanır (Türkiye ~10:00). 2.5-flash: 20/gün (hata mesajından).
    ModelSpec("gemini-2.5-flash", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    ModelSpec("gemini-3.5-flash", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    ModelSpec("gemini-3.5-flash-lite", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    ModelSpec("gemini-3.1-flash-lite", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    # Hesapta listelenen yeni flash modelleri (2026-10-01 model listesi); kotaları model başına ayrı.
    # İstek sınırlı, token sınırlı değil → toplu üretim (§2b) için uygun. Kalite kapısından geçmeden zincire girmez.
    ModelSpec("gemini-3.6-flash", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    ModelSpec("gemini-3.7-flash", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    ModelSpec("gemini-3.8-flash", "gemini", rpd=20, rpm=5, vision=True, tz="America/Los_Angeles"),
    # Gemma 4 (AI Studio, aynı anahtar; 2026-10-05 model listesinde var). İçerik üretmez/doğrulamaz: zorluk ölçümünde
    # "benzetilmiş öğrenci" (src/simulate.py) — literatürde zayıf/orta modeller öğrenci zorluğunu güçlülerden iyi taklit
    # ediyor. Kota iddiası dakikada 30 istek / 15 bin token (topluluk listesi, doğrulanmadı) → temkinli sınırlar.
    ModelSpec("gemma-4-26b-a4b-it", "gemini", rpd=None, rpm=15, tpm=15_000, tz="America/Los_Angeles"),
    ModelSpec("gemma-4-31b-it", "gemini", rpd=None, rpm=15, tpm=15_000, tz="America/Los_Angeles"),
    # Groq: yanıt başlıklarından 1000 istek/gün, 8000 token/dk. Asıl bağlayıcı sınır token/gün:
    # qwen için hata mesajından "tokens per day (TPD): Limit 200000" (2026-10-03). gpt-oss için henüz görülmedi;
    # aynı varsayıldı (429 gelince mesajdaki bekleme süresi uygulanır, değer gerekirse güncellenir).
    ModelSpec("openai/gpt-oss-120b", "groq", rpd=1000, tpm=8000, tpd=200_000),
    # Groq'ta görüntü kabul eden tek model (2026-10-03 testi; gpt-oss 400 veriyor). EN s53 tablosu 36/36 doğru.
    ModelSpec("qwen/qwen3.8-27b", "groq", rpd=1000, tpm=8000, tpd=200_000, vision=True),
    ModelSpec("openai/gpt-oss-20b", "groq", rpd=1000, tpm=8000, tpd=200_000),
    # Ek doğrulama kapasitesi adayları (2026-10-04 araştırması; anahtar .env'de yoksa hiç denenmez):
    # OpenRouter ücretsiz modelleri: dakikada 20, günde 50 istek (bir kez 10 $ kredi alınınca günde 1.000), UTC'de sıfırlanır.
    # Nemotron yeni bir model ailesi: hem Gemini'nin hem qwen'in ürettiği soruları doğrulayabilir.
    ModelSpec("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter", rpd=50, rpm=20),
    ModelSpec("openrouter/nvidia/nemotron-3-super-120b-a12b:free", "openrouter", rpd=50, rpm=20),
    ModelSpec("openrouter/qwen/qwen3.8-27b:free", "openrouter", rpd=50, rpm=20, vision=True),
    # Cerebras: kalıcı ücretsiz katman yok (kart + 30 günlük 5 $ deneme kredisi); model başına günde 1M token, dk'da 5 istek.
    ModelSpec("cerebras/gpt-oss-120b", "cerebras", rpd=None, rpm=5, tpm=30_000, tpd=1_000_000),
    ModelSpec("cerebras/qwen-3.8-27b", "cerebras", rpd=None, rpm=5, tpm=30_000, tpd=1_000_000),
    # Mistral (2026-10-05): Experiment planı (ayda 1 milyar token) kalktı; Free planda ayda 10 $ API kredisi, Large yok.
    # En güçlü açık model Medium 3.5 (sabit sürüm adı; 'latest' takma adı onay kanıtını kayan bir modele bağlardı).
    # Yeni aile: hem Gemini'nin hem qwen'in sorularını doğrulayabilir. Sınırlar Admin → API → Limits'ten (2026-10-05):
    # medium 1 istek/sn, 20.000 token/dk (asıl bağlayıcı: doğrulama çağrısı ~2.000 token → dakikada ~10 çağrı).
    ModelSpec("mistral/mistral-medium-2604", "mistral", rpd=None, rpm=60, tpm=20_000),
]}


def _chain(env: str, default: list[str]) -> list[str]:
    v = os.getenv(env)
    return [x.strip() for x in v.split(",")] if v else default


# KALİTE KAPISI: bir model bir role ancak o rolün kalite testini geçtiyse ONAYLI olur ve otomatik zincire girer.
# Kota dolunca sistem onaysız bir modele sessizce GEÇMEZ; bekler (kuyruk). Kota hızı etkiler, kaliteyi değil.
# Aday modeller test edilene kadar yalnızca elle (.env ROLE_<ROL>=…) kullanılabilir.
APPROVED: dict[str, dict[str, str]] = {
    "vision": {
        # Gemini önde: token değil istek sınırlı (20/gün/model) → qwen'in token bütçesi üretime kalır
        "gemini-2.5-flash": "21 sayfa; YZ s11 10 tablo + EN s52/62 görselle birebir (2026-10-01/02)",
        "gemini-3.5-flash": "10 sayfa; EN s52 tablo matematiksel tutarlı, s62 kod birebir (2026-10-02)",
        "qwen/qwen3.8-27b": "21 sayfa; EN s53 36/36 hücre, YZ s4 + EN s41/s89 formüller birebir (2026-10-03)",
    },
    "generate": {
        "qwen/qwen3.8-27b": "pilot v2: YZ 11/13, EN→TR 12/12 doğrulandı; anlama/uygulama sorusu üretiyor",
    },
    # Toplu üretim (§2b): bir istekte bir belgenin tüm birimleri. Kalite kapısı: aynı 12 birimde (EN→TR)
    # qwen birim başına 12 istekle 11/12 iken tek istekle 3.8-flash 11/11, 3.5-flash 11/12 (eval/sonuclar_toplu_uretim.md)
    "generate_batch": {
        "gemini-3.8-flash": "toplu: 12 birim tek istek, 11/11 doğrulandı, 0 dayanaksız (2026-10-03)",
        "gemini-3.5-flash": "toplu: 12 birim tek istek, 11/12 doğrulandı; doğrulananların 8/11'i anlama düzeyi",
    },
    "verify": {
        "openai/gpt-oss-120b": "duyarlılık testi: kasıtlı hataların 17/17'si yakalandı (2026-10-03)",
        "openai/gpt-oss-20b": "duyarlılık testi (sade mod): 20/20 yakalandı (2026-10-03); 120b'nin yedeği → doğrulama kapasitesi 2×",
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free": ("yeterlilik testi (kısa, 2026-10-04): kasıtlı hatalar 10/10, sağlam sorular 6/6; OpenRouter ücretsiz, günde 50 istek; yeni aile → hem Gemini'nin hem qwen'in sorularını doğrulayabilir"),
        # Üçüncü sırada: iki gpt-oss'un kayan 24 saatlik kotası dolunca (sınav istekleri doğrulamayı bekletiyordu).
        # Ailesi farklı olduğundan yalnızca qwen'in ÜRETMEDİĞİ soruları doğrular (Gemini'nin ürettikleri).
        "qwen/qwen3.8-27b": ("duyarlılık testi (sade mod, Gemini 3.8 soruları): 19/19 yakalandı; sağlam sorularda "
                             "9/11 doğrulandı, 2 kısa cevap 'bağlamda yok' deyip incelemeye düştü — temkinli, "
                             "hatalı soru geçirmedi (2026-10-04)"),
    },
    "judge": {
        "openai/gpt-oss-120b": "kısa cevap eşdeğerliği; duyarlılık testinde yanlış kısa cevap 1/1",
    },
    # Hesap sorusunun kör çözümü (§4e) ayrı bir yetenek: metin doğrulamayı geçen her model matematikte güçlü değil.
    "verify_math": {
        "openai/gpt-oss-120b": "akıl yürütme modeli; §4e için 20b ile aynı aile",
        "openai/gpt-oss-20b": "TYT hesap soruları: SymPy'den geçen 30 problemin 30'unda aynı sonucu buldu (2026-10-04)",
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free": ("yeterlilik testi (kısa, 2026-10-04): SymPy'nin doğruladığı 12 hesap sorusunda 12/12 (qwen'in yanıldığı yuvarlak masa ve ANANAS dahil), kaydırılmış anahtar 5/5"),
    },
}
CANDIDATES: dict[str, dict[str, str]] = {
    "vision": {"gemini-3.5-flash-lite": "test edilmedi", "gemini-3.1-flash-lite": "test edilmedi"},
    "generate": {"openai/gpt-oss-120b": "pilot v2: 10/13; çeldiriciler zayıf (yalnızca-şıklar 5/6), çoğu hatırlama"},
    "verify": {"gemini-2.5-flash": "duyarlılık testi yapılmadı",
               "openrouter/nvidia/nemotron-3-super-120b-a12b:free": "yeterlilik testi bekliyor (OPENROUTER_API_KEY)",
               "cerebras/gpt-oss-120b": "onaylı modelin başka sağlayıcıdaki kopyası; kısa yeterlilik testi bekliyor (CEREBRAS_API_KEY)",
               "mistral/mistral-medium-2604": "yeterlilik testi bekliyor (MISTRAL_API_KEY; Free plan, ayda 10 $ kredi)"},
    "verify_math": {"cerebras/gpt-oss-120b": "yeterlilik testi bekliyor (CEREBRAS_API_KEY)",
                    "mistral/mistral-medium-2604": "yeterlilik testi bekliyor (MISTRAL_API_KEY)",
                    "qwen/qwen3.8-27b": ("zor kombinatorik iki problemde ikisinde de yanıldı (yuvarlak masayı düz sıra "
                                         "saydı: 1440 ≠ 360; ANANAS: 120 ≠ 12); SymPy doğruydu (2026-10-04)")},
    "judge": {"openai/gpt-oss-20b": "test edilmedi"},
}

# Rol → model zinciri: yalnızca onaylılar (.env'den ROLE_<ROL>=m1,m2 ile elle değiştirilebilir)
ROLES: dict[str, list[str]] = {role: _chain(f"ROLE_{role.upper()}", list(models)) for role, models in APPROVED.items()}


def reasoning(role: str) -> str:
    """gpt-oss'un gizli akıl yürütme düzeyi (low | medium | high); diğer modeller yok sayar.

    Varsayılan medium: bütün onay testleri bununla yapıldı. Deney için .env ya da ortamda REASONING_<ROL>=low.
    Geçici doğrulayıcı rolleri ('_verify_not_gemini', '_verify_math_not_qwen_cand') ana rolün ayarını alır.
    """
    base = role.lstrip("_").split("_not_")[0]
    return os.getenv(f"REASONING_{base.upper()}", "medium")

"""Proje ayarları. API anahtarları ve model adları .env'den okunur."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# OpenAI uyumlu ek sağlayıcılar (isteğe bağlı; anahtar yoksa bu modeller hiç denenmez)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# Model seçimi ve sırası: src/llm/models.py (ROLES), .env'den ROLE_<ROL>=model1,model2 ile değiştirilebilir.

DATA_DIR = ROOT / "data"
PARSED_DIR = DATA_DIR / "parsed"
VISION_CACHE_DIR = DATA_DIR / "vision_cache"
VISION_DPI = 150

# Belgelerin arayüzde ve dışa aktarımda görünen kısa adları (dosya adı → ad)
DOC_NAMES = {"7.Hafta Sunu Dosyası": "Yapay Zeka", "4_ENERJİ, TARIM, BESLENME": "Ekoloji",
             "english": "Genetic Algorithms", "tyt-matematik": "TYT Matematik", "istek": "Sınav isteklerinden",
             "Hafta_01_Bilgisayar_Mimarisi_ve_Organizasyonuna_Giris": "Bilgisayar Mimarisi",
             "Hafta_02_Bilgisayar_Performansina_Giris": "Bilgisayar Performansı"}


def doc_name(stem: str) -> str:
    """Listede adı yoksa (arayüzden yeni yüklenen belge) dosya adının okunur hali: alt çizgi → boşluk."""
    return DOC_NAMES.get(stem) or stem.replace("_", " ").strip()

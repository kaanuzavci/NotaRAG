"""NotaRAG arayüzü. Çalıştırma: .venv\\Scripts\\streamlit run src/app.py  →  http://localhost:8501

Sayfalar (src/ui/pages): Sınav Hazırla · Belgeler · Soru Bankası · İnceleme · Rapor · Modeller ve Kota
Görsel dil: .streamlit/config.toml (tema) + src/ui/style.py (ayrıntılar); ortak soru kartı src/ui/components.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 'streamlit run src/app.py' için

import streamlit as st

from src.ui import style

st.set_page_config(page_title="NotaRAG", page_icon=":material/menu_book:", layout="wide",
                   initial_sidebar_state="expanded")
style.inject()

st.logo(str(Path(__file__).parent / "ui" / "logo.svg"), size="large")

pages = {
    "Çalış": [
        st.Page("ui/pages/exam.py", title="Sınav Hazırla", icon=":material/quiz:", default=True),
    ],
    "İçerik": [
        st.Page("ui/pages/documents.py", title="Belgeler", icon=":material/library_books:"),
        st.Page("ui/pages/bank.py", title="Soru Bankası", icon=":material/inventory_2:"),
    ],
    "Kalite": [
        st.Page("ui/pages/review.py", title="İnceleme", icon=":material/rate_review:"),
        st.Page("ui/pages/report.py", title="Rapor", icon=":material/insights:"),
        st.Page("ui/pages/models.py", title="Modeller ve Kota", icon=":material/speed:"),
    ],
}
nav = st.navigation(pages, position="sidebar")

with st.sidebar:
    style.html('<div class="nr-brand-sub">Ders notlarından kanıta dayalı sorular</div>')

nav.run()

"""NotaRAG arayüzü. Çalıştırma: .venv\\Scripts\\streamlit run src/app.py  →  http://localhost:8501

Önce giriş (src/ui/auth.py); giriş yapılmadan hiçbir sayfa görünmez. Rol yok: herkes aynı sayfaları görür.
Sayfalar (src/ui/pages): Ana sayfa · Sınav Hazırla · Bilgi Kartları · Belgeler · Soru Bankası · İnceleme · Rapor ·
Modeller ve Kota · Profil ve beyin analizi
Görsel dil: .streamlit/config.toml (tema) + src/ui/style.py (ayrıntılar); ortak soru kartı src/ui/components.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 'streamlit run src/app.py' için

import streamlit as st

from src.ui import auth, style

st.set_page_config(page_title="NotaRAG", page_icon=":material/menu_book:", layout="wide",
                   initial_sidebar_state="expanded")
style.inject()

user = auth.current()
if user is None:
    st.navigation([st.Page(auth.page, title="Giriş", icon=":material/login:", default=True)], position="hidden").run()
    st.stop()

# Kenar çubuğunda açık renkli logo (koyu zemin); kenar çubuğu kapalıyken üst şeritte mürekkep renkli olanı (kâğıt zemin)
st.logo(str(Path(__file__).parent / "ui" / "logo.svg"), icon_image=str(Path(__file__).parent / "ui" / "logo_ink.svg"),
        size="large")

pages = {
    "": [st.Page("ui/pages/home.py", title="Ana sayfa", icon=":material/home:", default=True)],
    "Çalış": [
        st.Page("ui/pages/exam.py", title="Sınav Hazırla", icon=":material/quiz:"),
        st.Page("ui/pages/cards.py", title="Bilgi Kartları", icon=":material/style:"),
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
    "Hesap": [st.Page("ui/pages/profile.py", title="Profil ve beyin analizi", icon=":material/psychology:")],
}
nav = st.navigation(pages, position="sidebar")
auth.sidebar(user)  # kenar çubuğunun en altında sabit: kim giriş yaptı, çıkış

nav.run()

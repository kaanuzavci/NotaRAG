"""Giriş ekranı ve oturum (hesaplar: src/accounts.py). Giriş yapılmadan hiçbir sayfa görünmez (src/app.py).

Rol yok: herkes aynı sayfaları görür; farkı kendi verisi (kartları, çözümleri) ve görebildiği belgelerdir.
"Beni hatırla": rastgele belirteç tarayıcı çerezinde (nr_oturum, 30 gün), veritabanında yalnızca özeti. Streamlit
çerezi okuyabiliyor (st.context.cookies) ama yazamıyor: çerez, sınav ekranındaki klavye kısayolları gibi bir
çerçeveden ana sayfaya yazılır. Sayfa yenilenince ya da sınav bağlantısı yeni sekmede açılınca oturum çerezden gelir.
Not: çerezi sayfa yazdığı için HttpOnly olamaz; sistem internete açılırsa Google girişi (st.login) bunu sunucuda yapar.
"""

from __future__ import annotations

import streamlit as st

from src import accounts, library
from src.ui import style

COOKIE = "nr_oturum"
_CSS = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 470px; padding-top: 8vh; }
h1.nr-title { font-size: 1.6rem !important; }  /* dar sütunda iki satır (Streamlit'in h1 stili .nr-title'ı eziyor) */
input[type=password]::-ms-reveal { display: none; }  /* Edge'in kendi göz düğmesi Streamlit'inkiyle üst üste biniyordu */
</style>"""


def current() -> dict | None:
    """Giriş yapmış kişi; yoksa geçerli bir "beni hatırla" çerezi var mı diye bir kez bakar."""
    if u := st.session_state.get("user"):
        return u
    if not st.session_state.get("_no_cookie"):
        token = st.context.cookies.get(COOKIE)
        u = accounts.session_user(token) if token else None
        if u:
            st.session_state.user, st.session_state._token = u, token
            return u
        st.session_state._no_cookie = True  # bu tarayıcı oturumunda yeniden bakmaya gerek yok
    return None


def _cookie(value: str, max_age: int) -> None:
    """Çerezi ana sayfaya yazar (görünmez çerçeve). İçerik değişmedikçe Streamlit çerçeveyi yeniden yüklemez."""
    style.html("<style>.st-key-nr_cookie { height: 0; overflow: hidden; margin: 0; }</style>")
    with st.container(key="nr_cookie"):
        st.iframe(f"<script>window.parent.document.cookie = '{COOKIE}={value}; Max-Age={max_age}; Path=/; "
                  "SameSite=Strict';</script>", height=1)


def _sign_in(u: dict, remember: bool) -> None:
    st.session_state.user = {k: u[k] for k in ("id", "name", "username")}
    if remember:
        st.session_state._token = accounts.new_session(u["id"])
        st.session_state._set_cookie = True
    st.rerun()


def _logout() -> None:
    if token := st.session_state.get("_token"):
        accounts.end_session(token)
    st.session_state.clear()  # açık sınav, kart oturumu ve seçimler de gider (sıradaki kişi görmesin)
    st.session_state._no_cookie = True
    st.session_state._clear_cookie = True
    st.query_params.clear()


def sidebar(u: dict) -> None:
    """Kenar çubuğunun altı: kim giriş yapmış, çıkış."""
    with st.sidebar:
        if st.session_state.get("_set_cookie") and st.session_state.get("_token"):
            _cookie(st.session_state._token, accounts.SESSION_DAYS * 86400)
        st.space("small")
        from src.ui import data
        style.html(f'<div class="nr-who">{style.avatar(u, data.avatar_b64(u["id"]), 38)}'
                   f'<div><span>Hesap</span><b>{style.esc(u["name"])}</b></div></div>')
        st.button("Çıkış yap", key="nr_logout", icon=":material/logout:", type="tertiary", on_click=_logout)


# ---------------------------------------------------------------- giriş ekranı

def _login_form() -> None:
    with st.form("nr_login", border=True, enter_to_submit=True):
        name = st.text_input("Kullanıcı adı", autocomplete="username")
        pw = st.text_input("Parola", type="password", autocomplete="current-password")
        remember = st.checkbox("Beni hatırla (30 gün)", value=True,
                               help="Bu tarayıcıda sayfa yenilense de oturum açık kalır. Ortak bilgisayarda kapat.")
        go = st.form_submit_button("Giriş yap", type="primary", width="stretch")
    if go:
        u = accounts.authenticate(name, pw)
        if u:
            _sign_in(u, remember)
        st.error("Kullanıcı adı ya da parola yanlış.", icon=":material/error:")


def _create_form(first: bool) -> None:
    if first:
        st.info("Sistemde henüz hesap yok. İlk açılan hesap, şimdiye kadar yüklenen belgelerin, sınav çözümlerinin ve "
                "kart kayıtlarının sahibi olur.", icon=":material/info:")
    with st.form("nr_create", border=True, enter_to_submit=True):
        display = st.text_input("Adın", placeholder="ör. Kaan", help="Ekranda görünen ad.")
        name = st.text_input("Kullanıcı adı", autocomplete="username", placeholder="ör. kaan",
                             help="Girişte kullanılır: 3-32 karakter, küçük harf (a-z), rakam, nokta, alt çizgi, tire.")
        pw = st.text_input("Parola", type="password", autocomplete="new-password",
                           help=f"En az {accounts.MIN_PASSWORD} karakter.")
        pw2 = st.text_input("Parola (tekrar)", type="password", autocomplete="new-password")
        remember = st.checkbox("Beni hatırla (30 gün)", value=True)
        go = st.form_submit_button("Hesap oluştur", type="primary", width="stretch")
    if go:
        if pw != pw2:
            st.error("Parolalar aynı değil.", icon=":material/error:")
            return
        try:
            u = accounts.create(name, pw, display)
        except accounts.AccountError as e:
            st.error(str(e), icon=":material/error:")
            return
        library.sync()  # ilk hesapsa girişten önceki belgeler ona bağlanır
        _sign_in(u, remember)


def page() -> None:
    style.html(_CSS)
    if st.session_state.pop("_clear_cookie", False):
        _cookie("", 0)
    first = accounts.count() == 0
    style.html('<div class="nr-kicker">NotaRAG</div><h1 class="nr-title">Ders notlarından kanıta dayalı sorular</h1>'
               '<hr class="nr-rule">')
    modes = ["Giriş yap", "Hesap oluştur"]
    mode = st.segmented_control("Giriş", modes, default=modes[1] if first else modes[0],
                                label_visibility="collapsed", key="nr_auth_mode") or modes[0]
    if mode == modes[0]:
        _login_form()
    else:
        _create_form(first)

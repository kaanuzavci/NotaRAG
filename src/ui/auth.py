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
from src.ui import loginart, style

COOKIE = "nr_oturum"
_GOOGLE = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'>"
           "<path fill='%23FFC107' d='M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 "
           "0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z'/>"
           "<path fill='%23FF3D00' d='M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 "
           "16.3 4 9.7 8.3 6.3 14.7z'/><path fill='%234CAF50' d='M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 "
           "0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z'/><path fill='%231976D2' d='M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 "
           "4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z'/></svg>")

# Giriş ekranı (kullanıcı isteği 2026-10-09): pencere ikiye bölünür. Sol yarı koyu bilgi paneli (ne işe yarar, 1-2-3 akışı
# küçük çizimlerle, sana özel çalışma, herkese açık notlar), sağ yarı kâğıt zeminde giriş / hesap açma kartı. Arkada
# "not → makine → soru → beyin" ağı (src/ui/loginart.py). Sütunlar boşluksuz, her biri tam olarak pencerenin yarısı;
# arka plandaki koyu dikdörtgen de pencerenin tam ortasında biter.
_CSS = style.focus_css("100%", "0", extra=loginart.BG_CSS + loginart.BRAND_CSS + """
.block-container, [data-testid="stMainBlockContainer"] { max-width: 100% !important; padding: 0 !important;
  position: relative; z-index: 1; }
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"] { gap: 0 !important; }
/* Sayfa kaymaz: her şey bir pencereye sığar */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow: hidden !important; }
.st-key-lg_right { min-height: 100vh; max-height: 100vh; justify-content: center; align-items: center; padding: 4vh 4vw; box-sizing: border-box;
  position: relative; overflow-y: auto; scrollbar-width: none; }  /* çok alçak ekranda yalnızca form kayar */
@media (max-height: 800px) { .lg-sub { display: none; } .lg-hi { font-size: 1.6rem; margin: .5rem 0 .3rem; } }
input[type=password]::-ms-reveal { display: none; }  /* Edge'in kendi göz düğmesi Streamlit'inkiyle üst üste biniyordu */
/* Form ayrı bir kutu değil: sağ yarının kendisi giriş alanı (kullanıcı isteği 2026-10-09) */
.st-key-lg_form { width: 100%; max-width: 460px; margin-left: auto; margin-right: auto; gap: .65rem; }
.lg-hi { font: 650 2.3rem/1.15 'Fraunces', serif; color: #1E2433; margin: .9rem 0 .3rem; letter-spacing: -.01em; }
.lg-sub { color: #6B6F7B; font-size: .96rem; line-height: 1.5; margin: 0 0 1rem; }
.st-key-lg_form [data-testid="stForm"] { border: 0; padding: 0; }
.st-key-lg_form [data-testid="stHorizontalBlock"] { gap: .8rem !important; }  /* iki parola alanı yan yana */
/* Sekmeler: anahtar görünümü (iki eşit parça, seçili olan beyaz). Streamlit 1.59: role=tablist / role=tab */
.st-key-lg_form [role="tablist"] { background: #EFE8D8; border-radius: 13px; padding: 4px; gap: 4px; border: 0; box-shadow: none; }
.st-key-lg_form [role="tablist"]::after, .st-key-lg_form [role="tablist"]::before { display: none; }
.st-key-lg_form [role="tablist"] > :not([role="tab"]) { display: none; }  /* altı çizili vurgu */
.st-key-lg_form [role="tab"] { flex: 1 1 0; justify-content: center; height: 44px; margin: 0 !important; border-radius: 10px;
  color: #5B5F6B; border: 0 !important; transition: background .15s, color .15s; }
.st-key-lg_form [role="tab"] p { font-weight: 600; font-size: .92rem; }
.st-key-lg_form .react-aria-SelectionIndicator { display: none !important; }  /* seçili sekmenin alt çizgisi */
.st-key-lg_form [role="tab"], .st-key-lg_form [role="tab"] * { border-bottom: 0 !important; }
.st-key-lg_form [role="tab"][aria-selected="true"] { background: #FFFDF8; color: #1E2433; box-shadow: 0 1px 3px rgba(30, 36, 51, .16); }
/* Alanlar: beyaz, yuvarlak, odakta lacivert halka */
.st-key-lg_form [data-testid="stTextInput"] label p { font-weight: 600; font-size: .84rem; color: #2A3040; }
.st-key-lg_form [data-testid="stTextInputRootElement"] { background: #FFFFFF !important; border: 1px solid #DCD3C1 !important;
  border-radius: 12px !important; min-height: 52px; transition: border-color .15s, box-shadow .15s; }
.st-key-lg_form [data-testid="stTextInputRootElement"]:focus-within { border-color: #1F3A5F !important;
  box-shadow: 0 0 0 3px rgba(31, 58, 95, .14); }
.st-key-lg_form [data-testid="stTextInputRootElement"] input { background: transparent !important; font-size: 1.04rem; padding-left: 1rem; }
.st-key-lg_form [data-testid="stFormSubmitButton"] button { min-height: 54px; border-radius: 13px; margin-top: .3rem; }
.st-key-lg_form [data-testid="stFormSubmitButton"] button p { font-size: 1rem; font-weight: 600; }
.lg-or { display: flex; align-items: center; gap: .8rem; color: #8A8576; font-size: .8rem; margin: .4rem 0 .1rem; }
.lg-or::before, .lg-or::after { content: ""; flex: 1; border-top: 1px solid #E4DCC9; }
.st-key-lg_google button { min-height: 54px; border-radius: 13px; background: #FFFFFF; border: 1px solid #DCD3C1; color: #1E2433; }
.st-key-lg_google button:hover { border-color: #1F3A5F; color: #1E2433; background: #FFFFFF; }
.st-key-lg_google button p { font-weight: 600; font-size: .95rem; }
.st-key-lg_google button::before { content: ""; width: 20px; height: 20px; margin-right: .6rem; flex: none;
  background: url("GOOGLE") center / contain no-repeat; }
.lg-legal { font-size: .76rem; color: #8A8576; text-align: center; margin-top: .3rem; line-height: 1.5; }
/* Stil ve arka plan blokları yer kaplamasın: sütunlar pencerenin en üstünden başlar */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: 0 !important; }
.st-key-lg_right > [data-testid="stElementContainer"]:has(.lg-foot) { position: absolute; left: 0; right: 0; bottom: 3vh; }
.lg-foot { display: flex; justify-content: center; gap: 1.4rem; font-size: .76rem; color: #8A8576; }
.lg-foot span + span::before { content: "·"; margin-right: 1.4rem; color: #C9BFA9; }
@media (max-width: 900px) { .lg-bg { display: none; } .lg-left { min-height: auto; background: #1E2433; }
  .st-key-lg_right { min-height: auto; } }
""".replace("GOOGLE", _GOOGLE))


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
    """Kenar çubuğunun en altı: kim giriş yapmış, çıkış. Kutu, menü ne kadar uzun olursa olsun çubuğun dibinde durur
    (style.py: kenar çubuğu içeriği dikey esnek kutu, .st-key-nr_account üstten 'auto' boşlukla aşağı itilir)."""
    from src.ui import data
    with st.sidebar:
        if st.session_state.get("_set_cookie") and st.session_state.get("_token"):
            _cookie(st.session_state._token, accounts.SESSION_DAYS * 86400)
        with st.container(key="nr_account", horizontal=True, vertical_alignment="center", gap="small"):
            style.html(f'<div class="nr-who">{style.avatar(u, data.avatar_b64(u["id"]), 38)}'
                       f'<div><b>{style.esc(u["name"])}</b><span>@{style.esc(u["username"])}</span></div></div>')
            st.button("Çıkış", key="nr_logout", icon=":material/logout:", type="tertiary", on_click=_logout,
                      help="Çıkış yap")


# ---------------------------------------------------------------- giriş ekranı

def _login_form() -> None:
    with st.form("nr_login", border=False, enter_to_submit=True):
        name = st.text_input("Kullanıcı adı", autocomplete="username", placeholder="ör. kaan")
        pw = st.text_input("Parola", type="password", autocomplete="current-password", placeholder="Parolan")
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
    with st.form("nr_create", border=False, enter_to_submit=True):
        display = st.text_input("Adın", placeholder="ör. Kaan", help="Ekranda görünen ad.")
        name = st.text_input("Kullanıcı adı", autocomplete="username", placeholder="ör. kaan",
                             help="Girişte kullanılır: 3-32 karakter, küçük harf (a-z), rakam, nokta, alt çizgi, tire.")
        c1, c2 = st.columns(2, gap="small")  # yan yana: form bir pencereye sığsın (giriş ekranı kaymaz)
        pw = c1.text_input("Parola", type="password", autocomplete="new-password",
                           help=f"En az {accounts.MIN_PASSWORD} karakter.")
        pw2 = c2.text_input("Parola (tekrar)", type="password", autocomplete="new-password")
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


def _google() -> None:
    st.toast("Google ile giriş yakında. Şimdilik kullanıcı adı ve parolayla giriş yap.", icon=":material/schedule:")


def page() -> None:
    style.html(_CSS)
    style.html(loginart.background())
    if st.session_state.pop("_clear_cookie", False):
        _cookie("", 0)
    first = accounts.count() == 0
    left, right = st.columns(2, gap=None)
    with left:
        style.html(loginart.brand())
    with right, st.container(key="lg_right"):
        with st.container(key="lg_form"):
            t_in, t_new = st.tabs(["Giriş yap", "Hesap aç"], default="Hesap aç" if first else "Giriş yap", key="nr_auth_mode")
            with t_in:
                style.html('<div class="lg-hi">Tekrar hoş geldin</div><div class="lg-sub">Notların, sınavların ve kartların '
                           'kaldığın yerde seni bekliyor.</div>')
                _login_form()
            with t_new:
                style.html('<div class="lg-hi">Hesap oluştur</div><div class="lg-sub">Bir dakikada hazır: kendi notların, '
                           'sınavların ve kartların yalnızca sana görünür.</div>')
                _create_form(first)
            style.html('<div class="lg-or">ya da</div>')
            st.button("Google ile devam et", key="lg_google", width="stretch", on_click=_google,
                      help="Yakında: Google hesabınla tek tıkla giriş.")
            style.html('<div class="lg-legal">Notların sen herkese açmadıkça yalnızca sana görünür.</div>')
        style.html('<div class="lg-foot"><span>© 2026 NotaRAG</span><span>Ders notlarından kanıta dayalı sorular</span>'
                   '<span>Türkçe</span></div>')

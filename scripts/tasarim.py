"""Tasarım denemesi (yalnızca geliştirme): gerçek uygulamayı GEÇİCİ bir hesap veritabanıyla açar, giriş yapıp sayfaların
ekran görüntüsünü alır, ana sayfadaki kartlara gerçek fare tıklamasıyla basar. Gerçek hesaplara dokunmaz.

    .venv\\Scripts\\python scripts\\tasarim.py hazirla            # data/tasarim/app.sqlite: deneme + arkadas hesabı,
                                                                  # yarım kart oturumu, yarım sınav, herkese açık bir not
    .venv\\Scripts\\python scripts\\tasarim.py baslat             # uygulama 8503'te (geçici veritabanıyla; yeniden başlatır)
    .venv\\Scripts\\python scripts\\tasarim.py ekran ":ana" "profile:profil" ":ana_hover:.stack:nth-child(3)"
    .venv\\Scripts\\python scripts\\tasarim.py ekran ":kapali:!$COLLAPSE" "documents:pencere:!.stack:nth-child(2) > ~2"
    .venv\\Scripts\\python scripts\\tasarim.py tikla ".stack.new|yeni" ".stack[data-id='tyt-matematik'] [data-act=exam]|sinav"
    .venv\\Scripts\\python scripts\\tasarim.py durdur

ekran: "yol:ad[:adımlar]" (yol '' = ana sayfa). Adımlar " > " ile ayrılır, sırayla yapılır, sonra ekran alınır:
  seçici      üzerine gel (seçici sayfada ya da bileşenlerin Shadow DOM'unda aranır)
  !seçici     gerçek fare tıklaması          ~2      2 sn bekle
  ^ArrowRight tuşa bas (ArrowLeft, Escape, Enter, f, i…)       #ifade  JS çalıştır
  @ad         ara ekran görüntüsü (akışın ortasında; sonda yine "ad" adıyla alınır)
  $COLLAPSE / $EXPAND: kenar çubuğunu kapatan / açan düğme. Her açılışta kenar çubuğu açık başlar.
  Dikkat: " > " adım ayırıcı; seçicilerde çocuk birleştiricisi (a > b) yerine boşluk (a b) kullan.
tikla: "seçici|ad" — her tıklamadan önce ana sayfaya dönülür; sonra adres, başlık ve seçili düğmeler yazılır.
Çıktılar data/tasarim/ekran/*.png (Read ile bakılır). Giriş: deneme / parola123. Görünmez Edge + CDP (scripts/ekran.py gibi).

Neden önizleme (scripts/onizleme.py) yetmiyor? Önizlemede yazı tipleri yüklenmiyor ve giriş, menü, sayfa geçişleri yok.
Dikkat: bu kurulumda kart değerlendirmek ya da sınav bitirmek yine gerçek attempts.jsonl / cards.jsonl'e yazar;
yalnızca hesaplar, belge kaydı ve "kaldığın yer" ayrıdır. Bu yüzden betik hiçbir değerlendirme düğmesine basmaz.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "tasarim"
DB = DIR / "app.sqlite"
OUT = DIR / "ekran"
PORT = 8503
URL = f"http://localhost:{PORT}"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
USER, PASSWORD = "deneme", "parola123"
W, H = map(int, os.environ.get("NR_EKRAN", "1440x1000").split("x"))  # ör. $env:NR_EKRAN="1280x720" (dizüstü, %150)


# ---------------------------------------------------------------- hazırlık ve sunucu

def hazirla() -> None:
    os.environ["NOTARAG_APP_DB"] = str(DB)
    sys.path.insert(0, str(ROOT))
    import random

    from src import accounts, appdb, library, resume
    from src import cards as K
    from src import request as R

    assert "tasarim" in str(appdb.PATH), appdb.PATH  # gerçek veritabanına asla
    DIR.mkdir(parents=True, exist_ok=True)
    if accounts.count() == 0:
        accounts.create(USER, PASSWORD, "Kaan Uzavcı")  # ilk hesap: eski kayıtlar ve belgeler onun
        accounts.create("arkadas", PASSWORD, "Arkadaş")
    library.sync()
    uid = accounts.legacy_owner()
    other = next(u["id"] for u in accounts.all_users() if u["username"] == "arkadas")
    pool = K.pool(sorted({it["doc"] for it in R.all_items().values()}))
    ids = [it["id"] for it in random.Random(3).sample(pool, min(20, len(pool)))]
    resume.save(uid, "cards", {"queue": ids, "pos": 7, "res": dict(zip(ids, ["good", "good", "bad", "good", "skip",
                                                                           "good", "bad"])),
                               "col": {}, "skipped": [], "streak": 1, "best": 3, "started": time.time() - 900,
                               "ended": False, "v": 7})
    req = next(r for p in sorted((ROOT / "data" / "requests").glob("*.json"), reverse=True)
               if (r := json.loads(p.read_text(encoding="utf-8"))).get("status") in ("ready", "done")
               and len(R.items_of(r)) >= 8)
    first = [it["id"] for it in R.items_of(req)[:4]]
    resume.save(uid, "exam", {"id": req["id"], "answers": {q: 0 for q in first}, "submitted": False,
                              "recorded": False, "phase": "solve", "cur": 4, "started": time.time() - 600,
                              "hints": {first[0]: 1}})
    with appdb.connect() as con:  # Genetic Algorithms: arkadaşın paylaştığı not gibi (herkese açık bölüm dolu görünsün)
        con.execute("UPDATE documents SET public_since = ?, owner = ? WHERE doc = 'english'", (time.time(), other))
        con.execute("DELETE FROM doc_access WHERE doc = 'english' AND user_id = ?", (uid,))
        con.execute("INSERT OR IGNORE INTO doc_access (doc, user_id, since) VALUES ('english', ?, ?)", (other, time.time()))
    print(f"hazır: {DB} (giriş {USER} / {PASSWORD})")


def durdur() -> None:
    pid_file = DIR / "sunucu.pid"
    if pid_file.exists():
        subprocess.run(["taskkill", "/F", "/T", "/PID", pid_file.read_text().strip()], capture_output=True)
        pid_file.unlink()
        print("8503 durduruldu")


def baslat() -> None:
    """src/ dışındaki modüller değişince Streamlit yeniden başlatılmalı: her çağrıda önce durdurur."""
    durdur()
    if not DB.exists():
        hazirla()
    env = {**os.environ, "NOTARAG_APP_DB": str(DB), "PYTHONIOENCODING": "utf-8"}
    log = (DIR / "sunucu.log").open("w", encoding="utf-8")
    p = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "streamlit.exe"), "run", "src/app.py", "--server.headless",
                          "true", "--server.port", str(PORT)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    (DIR / "sunucu.pid").write_text(str(p.pid))
    for _ in range(30):
        time.sleep(1)
        try:
            if urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2).read() == b"ok":
                print(f"hazır: {URL} (günlük {DIR / 'sunucu.log'})")
                return
        except OSError:
            pass
    print("uygulama açılmadı; günlüğe bak:", DIR / "sunucu.log")


# ---------------------------------------------------------------- tarayıcı (CDP)

def _targets() -> list[dict]:
    try:
        return json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list", timeout=2))
    except OSError:  # Edge açık değil → görünmez modda başlat
        subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                          "--remote-debugging-port=9333",
                          f"--user-data-dir={os.path.join(tempfile.gettempdir(), 'nr_edge_profile')}", "about:blank"])
        time.sleep(4)
        return json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list", timeout=5))


class Tab:
    def __init__(self, ws) -> None:
        self.ws, self.n = ws, 0

    async def cmd(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", msg)

    async def js(self, expr: str):
        return (await self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})).get("result", {}).get("value")

    async def shot(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        s = await self.cmd("Page.captureScreenshot", {"format": "png"})
        (OUT / f"{name}.png").write_bytes(base64.b64decode(s["data"]))

    async def center(self, sel: str) -> list[float] | None:
        """Seçicinin ortası: önce sayfada, yoksa bileşenlerin Shadow DOM'unda (ana sayfa desteleri orada)."""
        return await self.js(f"""(() => {{
          let r = document.querySelector({json.dumps(sel)});
          if (!r) for (const h of document.querySelectorAll('*')) {{
            r = h.shadowRoot && h.shadowRoot.querySelector({json.dumps(sel)}); if (r) break; }}
          if (!r) return null;
          r.scrollIntoView({{block: 'center'}}); const b = r.getBoundingClientRect();
          return [b.x + b.width / 2, b.y + b.height / 2]; }})()""")

    async def hover(self, sel: str) -> list[float] | None:
        """Üzerine gel; kart kalktığı için konum yeniden ölçülür."""
        box = await self.center(sel)
        if not box:
            return None
        await self.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]})
        await asyncio.sleep(0.6)
        box = await self.center(sel)
        await self.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]})
        await asyncio.sleep(0.5)
        return box

    async def click(self, sel: str) -> bool:
        box = await self.hover(sel)
        if not box:
            return False
        for t in ("mousePressed", "mouseReleased"):
            await self.cmd("Input.dispatchMouseEvent", {"type": t, "x": box[0], "y": box[1], "button": "left",
                                                       "clickCount": 1})
        return True

    async def key(self, key: str) -> None:
        code = KEYS.get(key, ord(key.upper()) if len(key) == 1 else 0)
        for t in ("keyDown", "keyUp"):
            await self.cmd("Input.dispatchKeyEvent", {"type": t, "key": key, "code": key if len(key) > 1 else
                                                      f"Key{key.upper()}", "windowsVirtualKeyCode": code})

    async def steps(self, spec: str, name: str) -> None:
        """ekran komutunun adımları (bkz. modül açıklaması)."""
        for s in (x.strip() for x in spec.split(" > ") if x.strip()):
            for alias, sel in ALIAS.items():
                s = s.replace(alias, sel)
            if s[0] == "~":
                await asyncio.sleep(float(s[1:]))
            elif s[0] == "@":
                await self.shot(s[1:])
                print("ekran:", OUT / f"{s[1:]}.png")
            elif s[0] == "#":
                print(f"{name}: {s[1:40]}… → {await self.js(s[1:])}")
            elif s[0] == "^":
                await self.key(s[1:])
                await asyncio.sleep(1.2)
            elif s[0] == "!":
                if not await self.click(s[1:]):
                    print(f"{name}: tıklanacak seçici bulunamadı ({s[1:]})")
                await asyncio.sleep(4)
            elif not await self.hover(s.lstrip("?")):
                print(f"{name}: seçici bulunamadı ({s})")


KEYS = {"ArrowRight": 39, "ArrowLeft": 37, "Escape": 27, "Enter": 13, "Home": 36, "End": 35, " ": 32}
ALIAS = {"$COLLAPSE": "[data-testid=stSidebarCollapseButton] button", "$EXPAND": "[data-testid=stExpandSidebarButton]"}


async def _open() -> Tab:
    import websockets
    page = next(t for t in _targets() if t["type"] == "page")
    tab = Tab(await websockets.connect(page["webSocketDebuggerUrl"], max_size=300 * 1024 * 1024))
    await tab.cmd("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
    await tab.cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})
    await tab.cmd("Network.enable")
    await tab.cmd("Network.clearBrowserCookies")
    await tab.cmd("Page.navigate", {"url": URL})
    await asyncio.sleep(8)
    if await tab.js("!!document.querySelector('input[type=password]')"):
        for sel, text in (("input[type=text]", USER), ("input[type=password]", PASSWORD)):
            await tab.js(f"document.querySelector('{sel}').focus()")
            await tab.cmd("Input.insertText", {"text": text})
        await tab.js("document.querySelector('[data-testid=stFormSubmitButton] button').click()")
        await asyncio.sleep(8)
    # Streamlit kenar çubuğunun açık/kapalı durumunu tarayıcıda saklıyor: her deneme açık başlasın (kullanıcının varsayılanı)
    await tab.js("localStorage.setItem('stSidebarCollapsed-', 'false')")
    return tab


async def ekran(specs: list[str]) -> None:
    tab = await _open()
    for spec in specs:
        path, name, *rest = spec.split(":", 2)
        await tab.cmd("Page.navigate", {"url": f"{URL}/{path}"})
        await asyncio.sleep(9)
        if rest:
            await tab.steps(rest[0], name)
        await tab.shot(name)
        print("ekran:", OUT / f"{name}.png")


async def tikla(specs: list[str]) -> None:
    tab = await _open()
    for spec in specs:
        sel, name = spec.split("|")
        await tab.cmd("Page.navigate", {"url": URL})
        await asyncio.sleep(9)
        if not await tab.click(sel):
            print(f"{name}: bulunamadı")
            continue
        await asyncio.sleep(8)
        where = await tab.js("location.pathname + location.search")
        what = await tab.js("document.querySelector('[role=dialog]') ? 'PENCERE: ' + document.querySelector('[role=dialog]')"
                            ".innerText.split('\\n')[0] : ((document.querySelector('h1') || {}).innerText || '(başlıksız)')")
        sel_now = await tab.js("[...document.querySelectorAll('button[data-selected=true]')].map(b => b.innerText.trim())"
                               ".slice(0, 4).join(', ')")
        await tab.shot(name)
        print(f"{name}: {where} · {what} · seçili: {sel_now}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if cmd == "hazirla":
        hazirla()
    elif cmd == "baslat":
        baslat()
    elif cmd == "durdur":
        durdur()
    elif cmd == "ekran":
        asyncio.run(ekran(args or [":ana"]))
    elif cmd == "tikla":
        asyncio.run(tikla(args))
    else:
        print(__doc__)

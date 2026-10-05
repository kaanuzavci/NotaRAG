"""Ekran görüntüsü (tarayıcı kurulumu yok): Windows'taki Edge görünmez modda açılır ve CDP ile sürülür; Streamlit
çizimini bitirsin diye beklenir (Edge'in tek seferlik --screenshot'ı yalnızca yükleme iskeletini yakalıyordu).

    .venv\\Scripts\\python scripts\\ekran.py <url> <çıktı.png> [bekleme_sn] [genişlik] [yükseklik] [js]
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
url, out = sys.argv[1], sys.argv[2]
wait = float(sys.argv[3]) if len(sys.argv) > 3 else 12
w = int(sys.argv[4]) if len(sys.argv) > 4 else 1440
h = int(sys.argv[5]) if len(sys.argv) > 5 else 1050
js = sys.argv[6] if len(sys.argv) > 6 else ""


def _targets() -> list[dict]:
    try:
        return json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list", timeout=2))
    except OSError:  # Edge açık değil → görünmez modda başlat
        prof = os.path.join(tempfile.gettempdir(), "nr_edge_profile")
        subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                          "--remote-debugging-port=9333", f"--user-data-dir={prof}", "about:blank"])
        time.sleep(4)
        return json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list", timeout=5))


async def main() -> None:
    page = next(t for t in _targets() if t["type"] == "page")
    ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=200 * 1024 * 1024)
    n = 0

    async def cmd(method: str, params: dict | None = None) -> dict:
        nonlocal n
        n += 1
        await ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == n:
                return msg.get("result", msg)

    await cmd("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
    await cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})
    await cmd("Page.navigate", {"url": url})
    await asyncio.sleep(wait)
    if js:
        await cmd("Runtime.evaluate", {"expression": js})
        await asyncio.sleep(1.5)
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open(out, "wb") as fh:
        fh.write(base64.b64decode(shot["data"]))
    print("kaydedildi", out)


asyncio.run(main())

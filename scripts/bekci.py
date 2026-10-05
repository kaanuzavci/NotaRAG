"""Bekçi: belge işlerini (data/jobs), sınav isteklerini (data/requests) ve kotayı izler; bir olay olunca yazdırıp ÇIKAR.
Claude Code'da arka planda çalıştırılır (çıkınca oturum uyanır, durumu kullanıcıya bildirir, bekçiyi yeniden başlatır).

Çıkış koşulları:
  - bir iş bitti / hata verdi / süreci kayboldu / kota beklemesine girdi / 8 dk ilerlemesiz kaldı (kota beklemesi hariç)
  - bir model yeni "dolu" işaretlendi
  - PERIOD saniye boyunca olay yoksa periyodik kota raporu
Kullanım (proje kökünden): .venv\\Scripts\\python.exe scripts\\bekci.py [periyot_sn=5400]
"""
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PERIOD = int(sys.argv[1]) if len(sys.argv) > 1 else 5400
STALL = 480
T0 = time.time()
DB = ROOT / "data" / "llm.sqlite"


def q(sql, *a):
    c = sqlite3.connect(DB)
    try:
        return c.execute(sql, a).fetchall()
    finally:
        c.close()


def exhausted() -> set:
    return set(q("SELECT model, day FROM usage WHERE exhausted=1"))


def text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def procs() -> str:
    return subprocess.run(["powershell", "-NoProfile", "-Command",
                           "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                           "Select-Object -ExpandProperty CommandLine"],
                          capture_output=True, text=True, errors="replace").stdout


def req_status(log: Path) -> str:
    try:
        return json.loads(log.with_suffix(".json").read_text(encoding="utf-8")).get("status", "?")
    except (OSError, ValueError):
        return "?"


start_ex = exhausted()
state: dict[Path, dict] = {}  # günlük → {size, changed, waits, kind}


def scan() -> None:
    for kind, d in (("belge", ROOT / "data" / "jobs"), ("istek", ROOT / "data" / "requests")):
        for log in d.glob("*.log"):
            if log in state:
                continue
            body = text(log)
            active = (kind == "belge" and "Bitti" not in body and "Traceback" not in body) or \
                     (kind == "istek" and req_status(log) == "generating")
            if active or log.stat().st_mtime > T0:
                state[log] = {"size": len(body), "changed": time.time(), "waits": body.count("⏳"), "kind": kind}


def report(msg: str, log: Path | None = None) -> None:
    from src.llm import ledger
    print(time.strftime("%H:%M"), msg)
    if log is not None:
        print(f"-- {log.parent.name}/{log.name}")
        print("\n".join(text(log).strip().splitlines()[-6:]))
    print("-- kota (son 24 saat / gün):")
    for r in ledger.report():
        if r["requests"] or r["exhausted"] or r["cooldown_s"]:
            lim = f"{r['tokens_24h']:,}/{r['tpd']:,} tkn" if r["tpd"] else f"{r['requests']}/{r['rpd']} istek"
            print(f"   {r['model']:52} {lim}{' DOLU' if r['exhausted'] else ''}"
                  f"{' bekleme ' + str(r['cooldown_s'] // 60) + ' dk' if r['cooldown_s'] else ''}")
    sys.stdout.flush()
    sys.exit(0)


while True:
    time.sleep(45)
    scan()
    running = procs()
    alive = "src.pipeline" in running or "src.request" in running
    recent = q("SELECT COUNT(*) FROM calls WHERE ts>?", time.time() - STALL)[0][0]
    for log, s in state.items():
        body = text(log)
        if len(body) != s["size"]:
            s["size"], s["changed"] = len(body), time.time()
        last = (body.strip().splitlines() or [""])[-1]
        if "Traceback" in body:
            report("HATA", log)
        if (s["kind"] == "belge" and "Bitti" in body) or (s["kind"] == "istek" and req_status(log) != "generating"):
            report("BİTTİ", log)
        if body.count("⏳") > s["waits"]:
            report("KOTA BEKLEMESİ BAŞLADI", log)
        if not alive and time.time() - s["changed"] > 90:
            report("SÜREÇ YOK (iş durmuş olabilir)", log)
        if alive and "⏳" not in last and recent == 0 and time.time() - s["changed"] > STALL:
            report("8 DK İLERLEME YOK (takılmış olabilir)", log)
    new_ex = exhausted() - start_ex
    if new_ex:
        report("KOTA DOLDU: " + ", ".join(sorted(m for m, _ in new_ex)))
    if time.time() - T0 > PERIOD:
        report("PERİYODİK DURUM (olay yok)")

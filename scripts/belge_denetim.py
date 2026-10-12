"""Belgeler (md) kodla uyumlu mu? Oturum sonunda ya da bir sürü değişiklikten sonra çalıştır. LLM yok, internet yok.

Kullanım: python scripts\\belge_denetim.py          (rapor; HATA varsa çıkış kodu 1)

HATA (düzeltilmeli): testi README §8'de yok · rehber bölümü rehber/README tablosunda yok · kod dosyası hiçbir rehber
bölümünde anılmıyor · kök kod dosyası README §6'da yok · README'deki sayfa sayısı app.py ile tutmuyor · ROADMAP'teki
test sayısı gerçekten farklı.
UYARI (bilgi): rehberde hiç geçmeyen genel (başında _ olmayan) tanımlar · rehberden yeni kod · teknoloji adı belgede var,
kodda import edilmiyor (ör. belgede "RAGAS" yazıyor ama paket hiç kullanılmıyor).
Bağlantı satırları ve bölüm başlıklarındaki "(N satır)" için ayrıca: python scripts\\rehber_satirlari.py [--yaz]
"""
import ast
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TECH = ("langchain", "ragas", "ollama", "chromadb", "pymupdf", "streamlit", "sympy", "rapidfuzz", "rank_bm25", "pydantic",
        "groq", "google.genai", "sentence_transformers", "torch")
errors: list[str] = []
warnings: list[str] = []


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def code_files() -> list[Path]:
    return sorted(f for d in ("src", "scripts", "eval") for f in (ROOT / d).rglob("*.py")
                  if "__pycache__" not in f.parts and f.name != "__init__.py")


def public_names(f: Path) -> list[str]:
    out = []
    for n in ast.parse(read(f)).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_"):
            out.append(n.name)
    return out


def main() -> None:
    readme, roadmap = read(ROOT / "README.md"), read(ROOT / "ROADMAP.md")
    rehber = {p: read(p) for p in sorted((ROOT / "rehber").glob("*.md"))}
    rehber_all = "\n".join(rehber.values())
    rel = lambda f: f.relative_to(ROOT).as_posix()

    # 1) testler
    tests = sorted(p.stem for p in (ROOT / "tests").glob("test_*.py"))
    for t in tests:
        if t not in readme:
            errors.append(f"test README'de (§8) yok: {t}")
    m = re.search(r"Testler \((\d+) dosya", roadmap)
    if m and int(m.group(1)) != len(tests):
        errors.append(f"ROADMAP 'Testler ({m.group(1)} dosya…)' diyor, gerçekte {len(tests)} test dosyası var")

    # 2) rehber bölümleri tabloda mı
    index = read(ROOT / "rehber" / "README.md")
    for p in rehber:
        if p.name != "README.md" and p.name not in index:
            errors.append(f"rehber bölümü rehber/README tablosunda yok: {p.name}")

    # 3) kod dosyaları rehberde, kök dosyalar README §6'da
    section6 = readme.split("## 6. Klasör Yapısı")[1].split("## 7.")[0] if "## 6. Klasör Yapısı" in readme else readme
    for f in code_files():
        if f.name not in rehber_all:
            errors.append(f"hiçbir rehber bölümünde anılmıyor: {rel(f)}")
        if f.parent in (ROOT / "src", ROOT / "src" / "ui") and f.name not in section6:
            errors.append(f"README §6 klasör yapısında yok: {rel(f)}")
        if f.parent == ROOT / "src" / "ui" / "pages" and not re.search(rf"\b{f.stem}\b", section6):  # §6'da "pages/ (home, profile, …)"
            errors.append(f"README §6'da sayfa adı geçmiyor: {rel(f)}")

    # 4) sayfa sayısı
    pages = len(re.findall(r"st\.Page\(\"ui/pages/", read(ROOT / "src" / "app.py")))
    for m in re.finditer(r"(\d+) sayfa\b", section6 + readme.split("## 5.")[1].split("## 6.")[0]):
        if int(m.group(1)) != pages and "hesaplanan" not in m.group(0):
            errors.append(f"README '{m.group(0)}' diyor, app.py'de {pages} sayfa var")

    # 5) rehberde geçmeyen genel tanımlar (bilgi)
    missing = []
    for f in code_files():
        for n in public_names(f):
            if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", rehber_all):
                missing.append(f"{rel(f)}:{n}")
    if missing:
        warnings.append(f"rehberde hiç geçmeyen {len(missing)} genel tanım: " + ", ".join(missing[:12]) + (" …" if len(missing) > 12 else ""))

    # 6) kod, ilgili rehber bölümlerinden yeni mi (mtime; git checkout hepsini yeniler → yalnızca ipucu)
    stale = []
    for f in code_files():
        docs = [p for p, text in rehber.items() if f.name in text]
        if docs and f.stat().st_mtime > max(p.stat().st_mtime for p in docs) + 3600:
            days = (f.stat().st_mtime - max(p.stat().st_mtime for p in docs)) / 86400
            stale.append(f"{rel(f)} (+{days:.1f} gün)")
    if stale:
        warnings.append(f"kod ilgili rehber bölümlerinden en az 1 saat yeni ({len(stale)}): " + ", ".join(stale[:10]) + (" …" if len(stale) > 10 else ""))

    # 7) belgede anılan teknoloji kodda import ediliyor mu (bilgi tablosu)
    code = "\n".join(read(f) for f in code_files())
    docs_text = (readme + roadmap + read(ROOT / "LITERATURE.md")).lower()
    rows = []
    for t in TECH:
        used = bool(re.search(rf"^\s*(import|from)\s+{re.escape(t)}", code, re.M)) or (f"import {t}" in code)
        base = t.split(".")[0].lower()
        named = sum(docs_text.count(v) for v in {base, base.replace("_", "-"), base.replace("_", "")})
        if named and not used:
            warnings.append(f"belgede anılıyor ama kodda import edilmiyor: {t} (belgelerde ~{named} kez)")
        rows.append((t, "kodda var" if used else "kodda YOK", named))

    # 8) ROADMAP başlık tarihi
    m = re.search(r"## Şu an neredeyiz\? \((\d{4})-(\d\d)-(\d\d)", roadmap)
    if m:
        age = (time.time() - time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, 0, 0, 0, -1))) / 86400
        if age > 3:
            warnings.append(f"ROADMAP 'Şu an neredeyiz?' başlığı {age:.0f} gün önceki tarihli ({m.group(0)[-11:-1]})")

    print("== Teknoloji: belgede ↔ kodda ==")
    for t, state, n in rows:
        print(f"  {t:<22} {state:<10} belgede ~{n}")
    print()
    for title, items in (("HATA", errors), ("UYARI", warnings)):
        print(f"== {title} ({len(items)}) ==")
        for e in items:
            print("  -", e)
    print("\nBağlantılar ve başlık satır sayıları için: python scripts\\rehber_satirlari.py")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()

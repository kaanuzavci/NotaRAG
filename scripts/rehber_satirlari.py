"""Kod rehberindeki (rehber/*.md) satır bağlantılarını koda göre günceller. LLM yok, internet yok.

Bağlantı metnindeki ilk `ad` (ör. [`parse_pdf(path)`](../src/ingestion/pdf_parser.py#L382), [`Index.build`](...))
hedef dosyada AST ile aranır (fonksiyon, sınıf, metot ya da modül düzeyi atama) ve #L numarası düzeltilir.
Adı bulunamayan bağlantılar listelenir (elle bakılmalı).

Kullanım: python scripts\\rehber_satirlari.py          (yalnızca rapor)
          python scripts\\rehber_satirlari.py --yaz    (dosyaları günceller)
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[([^\]]+)\]\(([^)#\s]+)#L(\d+)\)")


def definitions(path: Path) -> dict[str, int]:
    """'ad' ve 'Sınıf.metot' → satır (modül düzeyi fonksiyon, sınıf, metot, atama)."""
    out: dict[str, int] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):  # async: scripts/tasarim.py
            out.setdefault(node.name, node.lineno)
            if isinstance(node, ast.ClassDef):
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out[f"{node.name}.{m.name}"] = m.lineno
                        out.setdefault(m.name, m.lineno)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out.setdefault(n.id, node.lineno)
    return out


def symbol(text: str) -> list[str]:
    """Bağlantı metnindeki ilk `…` içinden aranacak ad adayları (en özelden en genele)."""
    m = re.search(r"`([^`]+)`", text)
    if not m:
        return []
    name = re.sub(r"\([^()]*\)", "", m.group(1)).strip().split()[0]  # 'Index().build()' → 'Index.build'
    parts = [p for p in name.split(".") if p]
    return [".".join(parts[-2:]), parts[-1]] if len(parts) > 1 else parts


def main(write: bool) -> None:
    cache: dict[Path, dict[str, int]] = {}
    fixed = unresolved = 0
    for md in sorted((ROOT / "rehber").glob("*.md")):
        body = md.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            nonlocal fixed, unresolved
            text, path, line = m.group(1), m.group(2), int(m.group(3))
            target = (md.parent / path).resolve()
            if target.suffix != ".py" or not target.exists():
                return m.group(0)
            defs = cache.setdefault(target, definitions(target))
            names = symbol(text)
            new = next((defs[n] for n in names if n in defs), None)
            if new is None:
                if names:
                    unresolved += 1
                    print(f"  ? {md.name}: {text[:50]} → {path}#L{line}")
                return m.group(0)
            if new != line:
                fixed += 1
                print(f"  {md.name}: {names[-1]} L{line} → L{new}")
            return f"[{text}]({path}#L{new})"

        new_body = LINK.sub(repl, body)
        if write and new_body != body:
            md.write_text(new_body, encoding="utf-8")
    print(f"{fixed} bağlantı {'güncellendi' if write else 'güncellenecek (--yaz)'}, {unresolved} ad bulunamadı")


if __name__ == "__main__":
    main("--yaz" in sys.argv)

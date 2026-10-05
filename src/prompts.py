"""İstemler PROMPTS.md'den okunur; böylece doküman ile kod hiçbir zaman birbirinden ayrışmaz."""

import re
from functools import lru_cache

from src.config import ROOT


@lru_cache
def load_prompt(section: str) -> str:
    """'## <section>.' ya da '### <section>.' başlığının altındaki ilk ``` bloğunu döndürür (ör. '1', '4a')."""
    md = (ROOT / "PROMPTS.md").read_text(encoding="utf-8")
    m = re.search(rf"^#{{2,3}} {re.escape(section)}\..*?^```\n(.*?)^```", md, flags=re.S | re.M)
    if not m:
        raise KeyError(f"PROMPTS.md içinde §{section} istemi bulunamadı")
    return m.group(1).strip()

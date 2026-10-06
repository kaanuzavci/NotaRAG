"""Üretilen soru şeması (PROMPTS.md §2). LLM çıktısı önce bu şemadan geçer; geçemeyen soru reddedilir."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Question(BaseModel):
    question: str = Field(min_length=8)
    type: Literal["multiple_choice", "short_answer", "true_false"]
    options: list[str] | None = None
    answer_index: int | None = None
    answer: str = Field(min_length=1)
    evidence_quote: str = Field(min_length=3)
    # Sorunun dayandığı her ayrı bilgi/kural için birebir alıntı (PROMPTS.md §2): notta bulunan ayrı alıntı sayısı
    # zorluğun yapısal ölçüsü — "zor" en az iki ayrı bilgi/kural ister (src/difficulty.py). İsteğe bağlı (eski sorular).
    evidence_quotes: list[str] | None = None
    bloom_level: Literal["remember", "understand", "apply"] = "remember"
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    # Hesap soruları (PROMPTS.md §2c): cevap kodla (SymPy) yeniden hesaplanır — src/generation/compute.py
    solution: list[str] | None = None        # çözüm adımları; öğrenciye cevapla birlikte gösterilir
    compute: str | None = None               # cevabı hesaplayan SymPy ifadesi
    option_values: list[str] | None = None   # her şıkkın SymPy değeri (şıklarla aynı sırada)
    answer_value: str | None = None          # kısa cevaplı hesap sorusunda cevabın SymPy değeri
    # Çoktan seçmelide her şıkkın notu (şıklarla aynı sırada): çeldiricinin temsil ettiği hata / kavram yanılgısı,
    # doğru şıkta boş. Öğrenci o şıkkı seçince "neden yanlış" geri bildirimi olur (DiVERT fikri; PROMPTS.md §2).
    option_notes: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_tf(cls, data: dict) -> dict:
        """Doğru/Yanlış cevabı çıktı dilinde gelebilir ('Yanlış', 'Doğru'): dilden bağımsız 'true'/'false'ye çevir.

        Pilotta gpt-oss iki geçerli D/Y sorusunu 'Yanlış' cevabıyla üretti ve şema yüzünden boşuna reddedildi.
        """
        if isinstance(data, dict) and data.get("type") == "true_false":
            raw = str(data.get("answer", "")).strip()
            # Cevap açıklamalı gelebilir ("Yanlış. Çünkü …", "True — the context …"): ilk kelime belirleyici
            first = re.split(r"[\s.,;:!—–-]+", raw.replace("İ", "i").lower(), maxsplit=1)[0] if raw else ""
            mapping = {"true": "true", "doğru": "true", "dogru": "true", "evet": "true",
                       "false": "false", "yanlış": "false", "yanlis": "false", "hayır": "false"}
            data = {**data, "answer": mapping.get(first, raw.lower()), "options": None, "answer_index": None}
        return data

    @model_validator(mode="after")
    def _shape(self) -> "Question":
        if self.type == "multiple_choice":
            if not self.options or len(self.options) != 4:
                raise ValueError("çoktan seçmeli soruda tam 4 şık olmalı")
            if len({o.strip().lower() for o in self.options}) != 4:
                raise ValueError("şıklar birbirinden farklı olmalı")
            if self.answer_index is None or not 0 <= self.answer_index < 4:
                raise ValueError("answer_index 0-3 arasında olmalı")
        if self.type == "true_false" and self.answer.strip().lower() not in ("true", "false"):
            raise ValueError("doğru/yanlış cevabı 'true' ya da 'false' olmalı")
        if self.option_notes is not None and (self.type != "multiple_choice" or len(self.option_notes) != 4):
            self.option_notes = None  # notlar isteğe bağlı: biçimi bozuksa soru reddedilmez, yalnızca notlar düşer
        if self.compute is not None:
            if self.type == "true_false":
                raise ValueError("hesap sorusu doğru/yanlış olamaz")
            if self.type == "multiple_choice" and (not self.option_values or len(self.option_values) != 4):
                raise ValueError("hesap sorusunda her şıkkın değeri (option_values, 4 adet) olmalı")
            if self.type == "short_answer" and not self.answer_value:
                raise ValueError("kısa cevaplı hesap sorusunda answer_value olmalı")
        return self


class Batch(BaseModel):
    questions: list[dict] = Field(default_factory=list)  # tek tek doğrulanır; biri bozuk diye hepsi atılmaz

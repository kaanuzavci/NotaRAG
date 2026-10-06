"""Kota hatası yorumlama, model ailesi ve önbellek anahtarı testleri (internetsiz). Çalıştırma: python -m tests.test_router"""

import os

from src.llm import ledger
from src.llm.models import reasoning
from src.llm.router import AllModelsExhausted, _classify, call, parse_wait
from src.verification.verify import family

TPD = ("Error code: 429 - rate_limit_exceeded ... on tokens per day (TPD): Limit 200000, Used 198132, "
       "Requested 3324. Please try again in 10m28.992s.")
GEMINI_DAY = "429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier Please retry in 58s"


def test_all() -> None:
    assert abs(parse_wait("Please retry in 57.2s.") - 57.2) < 1e-6
    assert abs(parse_wait("Please try again in 10m28.992s. Need more") - 628.992) < 1e-6
    assert parse_wait("try again in 1h2m3s") == 3723
    assert parse_wait("no wait here") == 0
    # Groq token/gün: kayan pencere → süreli bekleme (2026-10-03'te gün boyu kapatma hatası yapılmıştı)
    kind, wait = _classify(Exception(TPD))
    assert kind == "daily" and abs(wait - 628.992) < 1e-6
    # Gemini takvim günü kotası → gün boyu kapat (bekleme 0)
    assert _classify(Exception(GEMINI_DAY)) == ("daily", 0)
    assert _classify(Exception("429 rate_limit_exceeded tokens per minute (TPM). Please try again in 3.2s"))[0] == "minute"
    assert _classify(Exception("503 UNAVAILABLE high demand"))[0] == "busy"
    # Ağ kesintisi (hotspot): kota sanılmamalı, kısa beklenip tekrar denenmeli (2026-10-03'te bir çalıştırmayı çökertti)
    class ConnectTimeout(Exception):
        pass
    assert _classify(ConnectTimeout("_ssl.c:975: The handshake operation timed out"))[0] == "network"
    assert _classify(Exception("Request timed out."))[0] == "network"
    class RemoteProtocolError(Exception):
        pass
    assert _classify(RemoteProtocolError("Server disconnected without sending a response."))[0] == "network"
    # Gemini 503 'high demand' kota değil: iş yedeğe geçmeden kısa bekleyip aynı modeli denemeli
    # (2026-10-04'te matematik notunda yoğunluk 'kota dolu' sanılıp qwen'e geçilmişti)
    assert AllModelsExhausted("x", ["busy", "busy"]).transient
    assert AllModelsExhausted("x", ["busy", "minute", "network"]).transient
    assert not AllModelsExhausted("x", ["busy", "daily"]).transient
    assert not AllModelsExhausted("x", []).transient  # hiç denenemedi = hepsi kayıtlara göre dolu


def test_family() -> None:
    assert family("openai/gpt-oss-120b") == family("cerebras/gpt-oss-120b") == "gpt-oss"
    assert family("qwen/qwen3.8-27b") == family("openrouter/qwen/qwen3.8-27b:free") == family("cerebras/qwen-3.8-27b")
    assert family("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free") == "nemotron"
    # Gemma Google'ın modeli: Gemini'nin sorusunu doğrulayamaz (ad önekine bakan eski kural 'gemma' diyordu)
    assert family("gemma-4-31b-it") == family("gemini-3.5-flash") == "gemini"
    assert family("mistral-large-3") == family("magistral-medium-1.2") == "mistral"


def test_cache_key() -> None:
    """Varsayılan (medium) çağrının önbellek anahtarı eskisiyle aynı kalmalı (yoksa llm.sqlite'taki bütün yanıtlar
    yeniden istenir); farklı akıl yürütme düzeyi ise ayrı anahtar almalı (yoksa deney eski yanıtları okur)."""
    seen: list[dict] = []
    orig = ledger.cache_key, ledger.cache_get
    ledger.cache_key = lambda model, prompt, image, params: seen.append(params) or "k"
    ledger.cache_get = lambda key: "{}"  # önbellek isabeti → ağa çıkılmaz
    try:
        os.environ.pop("REASONING_VERIFY", None)
        assert call("verify", "x").cached
        assert seen[-1] == {"json": False, "max_tokens": 4096, "temperature": 0.0}
        os.environ["REASONING_VERIFY"] = "low"
        call("verify", "x")
        assert seen[-1]["reasoning"] == "low"
        assert reasoning("_verify_not_gemini_cand") == "low" and reasoning("verify_math") == "medium"
    finally:
        ledger.cache_key, ledger.cache_get = orig
        os.environ.pop("REASONING_VERIFY", None)


if __name__ == "__main__":
    test_all()
    test_family()
    test_cache_key()
    print("router: tüm testler geçti")

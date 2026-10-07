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
    assert _classify(Exception("504 DEADLINE_EXCEEDED. {'error': {'code': 504, 'message': 'Deadline expired before "
                               "operation could complete.', 'status': 'DEADLINE_EXCEEDED'}}"))[0] == "busy"
    # Ağ kesintisi (hotspot): kota sanılmamalı, kısa beklenip tekrar denenmeli (2026-10-03'te bir çalıştırmayı çökertti)
    class ConnectTimeout(Exception):
        pass
    assert _classify(ConnectTimeout("_ssl.c:975: The handshake operation timed out"))[0] == "network"
    assert _classify(Exception("Request timed out."))[0] == "network"
    class RemoteProtocolError(Exception):
        pass
    assert _classify(RemoteProtocolError("Server disconnected without sending a response."))[0] == "network"
    # İnternet kesilince DNS hatası: süreci çökertmemeli, ağ beklemesi sayılmalı (2026-10-06)
    class ConnectError(Exception):
        pass
    assert _classify(ConnectError("[Errno 11001] getaddrinfo failed"))[0] == "network"
    assert _classify(OSError("[Errno -3] Temporary failure in name resolution"))[0] == "network"
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


def test_busy_gemini() -> None:
    """Gemini'de 503 'yoğun' da günlük kotadan düşüyor (2026-10-06: 0 başarılı, ~20 deneme → 'günlük kota doldu'):
    deneme sayaca yazılır, aynı model hemen yeniden sorulmaz, artan sürelerle kapatılır. Gemma (rpd yok) iki kez dener."""
    from src.llm import router
    from src.llm.models import ROLES
    rec, cool, tried = [], {}, []

    def busy(model, *a, **k):
        tried.append(model)
        raise Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")

    saved = (router._raw, router.has_key, router.time.sleep, ledger.record, ledger.set_cooldown, ledger.available,
             ledger.cache_get, ledger.time_until_available)
    router._raw, router.has_key, router.time.sleep = busy, (lambda m: True), (lambda s: None)
    ledger.record = lambda m, tokens=0, cached=0: rec.append(m)
    ledger.set_cooldown = lambda m, s: cool.__setitem__(m, s)
    ledger.available = lambda m, need_tokens=0: m not in cool
    ledger.cache_get = lambda k: None
    ledger.time_until_available = lambda m, need_tokens=0: cool.get(m, 0.0)
    router._busy_streak.clear()
    ROLES["_t_busy"] = ["gemini-3.8-flash", "gemma-4-26b-a4b-it"]
    try:
        for expect in (900, 1800):  # ikinci yoğunlukta süre iki katı
            tried.clear(), rec.clear(), cool.clear()
            try:
                call("_t_busy", "x")
                raise AssertionError("yoğunlukta hata bekleniyordu")
            except AllModelsExhausted as e:
                assert e.transient  # kota değil: iş bekler, zayıf modele geçmez
            assert tried == ["gemini-3.8-flash", "gemma-4-26b-a4b-it", "gemma-4-26b-a4b-it"]  # Gemini bir, Gemma iki
            assert rec == ["gemini-3.8-flash"] and cool == {"gemini-3.8-flash": expect}
        tried.clear()
        try:  # kapalıyken Gemini hiç sorulmaz
            call("_t_busy", "x")
        except AllModelsExhausted:
            pass
        assert "gemini-3.8-flash" not in tried
    finally:
        (router._raw, router.has_key, router.time.sleep, ledger.record, ledger.set_cooldown, ledger.available,
         ledger.cache_get, ledger.time_until_available) = saved
        ROLES.pop("_t_busy", None)
        router._busy_streak.clear()


if __name__ == "__main__":
    test_all()
    test_family()
    test_cache_key()
    test_busy_gemini()
    print("router: tüm testler geçti")

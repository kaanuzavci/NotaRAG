"""Tüm LLM çağrılarının geçtiği tek kapı: rol → model zinciri, kota, önbellek, hız ayarı.

    from src.llm.router import call
    r = call("vision", prompt, image=jpeg_bytes)          # r.text, r.model, r.cached
    r = call("generate", prompt, json_mode=True)

Hata politikası (internet ve kota israfını önlemek için):
  günlük kota (429 'PerDay' / 'per day')  → model bugün için "dolu" işaretlenir, sıradakine geçilir
  dakikalık sınır (429 'PerMinute' / TPM) → önerilen süre beklenip aynı model 1 kez daha denenir
  sunucu yoğun / iç hata (500, 503)       → aynı modeli zorlamadan sıradakine geçilir
  model yok (404)                         → bugün için kullanılamaz işaretlenir
Görüntülü çağrıda o gün hiç kullanılmamış modele önce küçük bir metin yoklaması yapılır; böylece
kotası dolu bir modele görüntü (~150 KB) boşuna yüklenmez.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from src import config
from src.llm import ledger
from src.llm.models import MODELS, ROLES, reasoning


class AllModelsExhausted(RuntimeError):
    """Roldeki tüm modellerin günlük kotası dolu ya da hepsi geçici olarak kullanılamıyor.

    transient=True: hiçbir model kota yüzünden değil, geçici sebeple (sağlayıcı yoğun 503, dakikalık sınır,
    ağ) cevap vermedi → kısa bekleyip AYNI modelle tekrar denemek doğru; kota doldu sanılıp yedeğe geçilmez.
    """

    def __init__(self, msg: str, kinds: list[str] | None = None, retry_in: float = 0.0):
        super().__init__(msg)
        self.kinds = kinds or []
        self.transient = bool(self.kinds) and all(k in ("busy", "minute", "network") for k in self.kinds)
        self.retry_in = retry_in  # zincirdeki ilk modelin yeniden kullanılabileceği süre (sn); bilinmiyorsa 0


@dataclass
class Result:
    text: str
    model: str
    cached: bool
    thoughts: int = 0  # modelin gizli düşünme token'ları (Gemini/Gemma bildiriyorsa; önbellekten gelen yanıtta 0)


_throttle = ledger.Throttle()
_clients: dict[str, object] = {}
# Son çağrının sağlayıcının bildirdiği gerçek token kullanımı (gpt-oss'un gizli akıl yürütme token'ları dahil).
# Tahmin (karakter/3) bunları saymıyordu; kota hesabı artık gerçek değerle yapılır.
# cached: sağlayıcının istem önbelleğinden okuduğu giriş token'ları (tokens'ın içinde; ledger.prompt_cache).
# thoughts: düşünme token'ları (zorluk ölçümünde "gereken çaba" sinyali, src/simulate.py)
_last_usage: dict[str, int] = {"tokens": 0, "cached": 0, "thoughts": 0}
GEMINI_TIMEOUT_MS = 600_000


def _gemini():
    if "gemini" not in _clients:
        from google import genai
        # Zaman aşımı şart: yoksa kopan bağlantıda çağrı sonsuza dek asılı kalıyor (2026-10-06: ağ değişince dört
        # ölçüm süreci 25 dk hiçbir şey yazmadan bekledi). 10 dk: düşünmeli uzun üretim çağrısına yeter.
        # Aşılınca httpx ReadTimeout → 'network' → kısa bekleme, bir kez daha, sonra sıradaki model.
        from google.genai import types
        _clients["gemini"] = genai.Client(api_key=config.GEMINI_API_KEY,
                                          http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS))
    return _clients["gemini"]


def _groq():
    if "groq" not in _clients:
        from groq import Groq
        _clients["groq"] = Groq(api_key=config.GROQ_API_KEY, max_retries=0)
    return _clients["groq"]


# OpenAI uyumlu sağlayıcılar: model adı "<sağlayıcı>/<sağlayıcının model kimliği>" (ör. "openrouter/qwen/qwen3.8-27b:free")
_OPENAI_COMPAT = {
    "openrouter": ("https://openrouter.ai/api/v1", lambda: config.OPENROUTER_API_KEY),
    "cerebras": ("https://api.cerebras.ai/v1", lambda: config.CEREBRAS_API_KEY),
    "mistral": ("https://api.mistral.ai/v1", lambda: config.MISTRAL_API_KEY),
    "groqcompat": ("https://api.groq.com/openai/v1", lambda: config.GROQ_API_KEY),  # yalnızca bağlantı testi
}


def has_key(model: str) -> bool:
    """Modelin sağlayıcı anahtarı tanımlı mı? (Anahtarı olmayan sağlayıcının modeli zincirde atlanır.)"""
    spec = MODELS.get(model)
    if spec is None:
        return False
    if spec.provider in _OPENAI_COMPAT:
        return bool(_OPENAI_COMPAT[spec.provider][1]())
    return bool(config.GEMINI_API_KEY if spec.provider == "gemini" else config.GROQ_API_KEY)


def _call_openai_compat(model: str, prompt: str, json_mode: bool, max_tokens: int, temperature: float,
                        image: bytes | None = None, effort: str = "medium") -> str:
    """OpenRouter / Cerebras / Mistral: OpenAI uyumlu /chat/completions (ek kütüphane yok; httpx zaten kurulu)."""
    import httpx

    provider, api_model = model.split("/", 1)
    base, key = _OPENAI_COMPAT[provider]
    content: str | list = prompt
    if image is not None:
        import base64
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}}]
    body: dict = {"model": api_model, "messages": [{"role": "user", "content": content}],
                  "max_tokens": max_tokens, "temperature": temperature}
    # Nemotron (OpenRouter) zorunlu JSON modunda cevap yazamadan sınıra dayanıyordu (finish=length, içerik '{}');
    # modsuz aynı istem 288 token'da doğru JSON verdi (2026-10-04). İstemler zaten 'yalnızca JSON' istiyor.
    if json_mode and "nemotron" not in api_model:
        body["response_format"] = {"type": "json_object"}
    if "gpt-oss" in api_model:
        body["reasoning_effort"] = effort
        body["max_tokens"] = max(max_tokens, 2000)
    r = httpx.post(f"{base}/chat/completions", json=body, timeout=180,
                   headers={"Authorization": f"Bearer {key()}", "X-Title": "NotaRAG"})
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text[:600]}")
    data = r.json()
    if data.get("error"):  # OpenRouter bazı hataları 200 ile döndürür
        raise RuntimeError(f"{data['error'].get('code', '')} {json.dumps(data['error'], ensure_ascii=False)[:600]}")
    usage = data.get("usage") or {}
    _last_usage["tokens"] = int(usage.get("total_tokens", 0) or 0)
    _last_usage["cached"] = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0)
    text = (data["choices"][0]["message"].get("content") or "")
    if isinstance(text, list):  # Mistral'ın akıl yürütmeli modelleri: [{"type": "thinking", …}, {"type": "text", "text": …}]
        text = "".join(p.get("text", "") for p in text if isinstance(p, dict) and p.get("type") == "text")
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _call_gemini(model: str, prompt: str, image: bytes | None, json_mode: bool, max_tokens: int,
                 temperature: float, think: str | None = None) -> str:
    from google.genai import types

    cfg = {"temperature": temperature, "max_output_tokens": max_tokens,
           "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)}
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    if think:  # Gemma 4: 'minimal' (düşünmeden cevap) ya da 'high'; düşünme bütçesi (thinking_budget) desteklenmiyor
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=think)
    elif model.startswith("gemini-2.5"):
        cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    contents = [types.Part.from_bytes(data=image, mime_type="image/jpeg"), prompt] if image else prompt
    r = _gemini().models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(**cfg))
    _last_usage["tokens"] = int(getattr(r.usage_metadata, "total_token_count", 0) or 0)
    _last_usage["thoughts"] = int(getattr(r.usage_metadata, "thoughts_token_count", 0) or 0)
    return (r.text or "").strip()


def _call_groq(model: str, prompt: str, json_mode: bool, max_tokens: int, temperature: float,
               image: bytes | None = None, effort: str = "medium") -> str:
    kw = {"response_format": {"type": "json_object"}} if json_mode else {}
    content: str | list = prompt
    if image is not None:  # OpenAI uyumlu çok parçalı mesaj (yalnızca vision=True modeller)
        import base64
        content = [{"type": "text", "text": prompt},
                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image).decode()}}]
    if "gpt-oss" in model:
        # Gizli akıl yürütme token'ları max_tokens'tan düşer; düşük sınırda cevaba yer kalmayabiliyor
        # (pilotta 300 token'lık bağlamsız testte boş JSON → 400 json_validate_failed).
        kw["reasoning_effort"] = effort
        max_tokens = max(max_tokens, 2000)
    r = _groq().chat.completions.create(
        model=model, messages=[{"role": "user", "content": content}],
        max_tokens=max_tokens, temperature=temperature, **kw)
    _last_usage["tokens"] = int(getattr(r.usage, "total_tokens", 0) or 0)
    # Groq istem önbelleği (yalnızca gpt-oss): birebir aynı önek (talimat + Context) art arda gelirse okunur
    _last_usage["cached"] = int(getattr(getattr(r.usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0)
    text = r.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _valid_json(text: str) -> bool:
    """Önbelleğe alınacak JSON: ayrıştırılabilir VE boş değil ('{}' sınıra dayanmış cevaptır; Nemotron JSON modunda
    böyle dönüyordu ve önbellekten her seferinde aynı boş cevap okunuyordu)."""
    try:
        return bool(json.loads(text))
    except (json.JSONDecodeError, TypeError):
        return False


def parse_wait(s: str) -> float:
    """'retry in 57.2s', 'try again in 10m28.992s', 'try again in 1h2m3s' → saniye (yoksa 0)."""
    m = re.search(r"(?:retry|try again) in ((?:\d+h)?(?:\d+m)?(?:[\d.]+s)?)", s)
    if not m or not m.group(1):
        return 0.0
    parts = {unit: value for value, unit in re.findall(r"([\d.]+)([hms])", m.group(1))}
    return float(parts.get("h", 0)) * 3600 + float(parts.get("m", 0)) * 60 + float(parts.get("s", 0))


def _classify(err: Exception) -> tuple[str, float]:
    """('daily' | 'minute' | 'busy' | 'missing' | 'json' | 'other', bekleme_sn)

    'daily' + bekleme > 0: Groq'un kayan token/gün penceresi ("try again in 10m28s") → model yalnızca o süre
    bekletilir. 'daily' + 0: Gemini'nin takvim günü kotası → model o gün için kapatılır.
    """
    s = str(err)
    wait = parse_wait(s)
    # Ağ kesintisi (telefon hotspot'unda sık): kota değil → kısa bekleyip aynı modeli tekrar dene.
    # "Server disconnected without sending a response" (httpx RemoteProtocolError) de böyle (Gemma, 2026-10-05)
    if (any(x in type(err).__name__ for x in ("Timeout", "Connection", "RemoteProtocol"))
            or "timed out" in s.lower() or "disconnected" in s.lower()):
        return "network", 15
    if "429" in s or "RESOURCE_EXHAUSTED" in s or "rate_limit" in s.lower():
        if "PerDay" in s or "per day" in s.lower() or "per-day" in s.lower() or "(RPD)" in s or "(TPD)" in s:
            return "daily", (wait if "(TPD)" in s or "(RPD)" in s else 0)
        return "minute", wait or 30
    if any(x in s for x in ("503", "UNAVAILABLE", "500", "INTERNAL", "502", "overloaded")):
        return "busy", 0
    if "404" in s or "NOT_FOUND" in s or "model_not_found" in s:
        return "missing", 0
    if "json_validate_failed" in s:
        return "json", 0
    return "other", 0


def _sync_used(model: str, err: Exception) -> None:
    """Groq'un TPD hatası gerçek kullanımı söyler ('Limit 200000, Used 198765'): kendi kaydımız eksikse
    (ör. kayıt tutulmaya başlamadan önceki çağrılar) farkı ekleyerek kota tahminini gerçeğe eşitle."""
    m = re.search(r"Used (\d+)", str(err))
    if m:
        ledger.record_sync(model, int(m.group(1)))  # istem önbelleği ölçümü: python -m src.llm.capacity gösterir
        gap = int(m.group(1)) - ledger.tokens_24h(model)
        if gap > 0:
            ledger.record_correction(model, gap)


# Gemini'de başarısız (503 "yoğun") istek de günlük istek kotasından düşüyor: 2026-10-06'da 0 başarılı istek ve
# ~20 '503' denemesinden sonra Google iki modeli de "günlük kota doldu" diye kapattı (ROADMAP 6'daki şüphe doğrulandı).
# Gemini'nin günlük istek sınırlı modellerinde (rpd) yoğunluk: deneme sayaca yazılır, aynı model hemen yeniden
# sorulmaz, artan sürelerle kapatılır (15 → 30 → 60 → 120 dk). Öbürleri (Groq, Gemma) eskisi gibi kısa bekleyip dener.
BUSY_COOLDOWN = 900
_busy_streak: dict[str, int] = {}


def _busy_rpd(model: str) -> bool:
    """Gemini'nin günlük istek sınırlı modelinde yoğunluk → sayaca yaz + kapat (True). Öbürlerinde False (kısa bekle)."""
    spec = MODELS[model]
    if spec.provider != "gemini" or spec.rpd is None:
        return False
    n = _busy_streak.get(model, 0)
    _busy_streak[model] = n + 1
    ledger.record(model, 0)
    ledger.set_cooldown(model, BUSY_COOLDOWN * 2 ** min(n, 3))
    return True


def _block(model: str, kind: str, wait: float) -> None:
    """Kota hatası sonrası modeli kapat: süreli bekleme (Groq TPD) ya da günün geri kalanı (Gemini, yok model)."""
    if kind == "daily" and wait > 0:
        ledger.set_cooldown(model, wait + 5)
    elif kind in ("daily", "missing"):
        ledger.mark_exhausted(model)


def _raw(model: str, prompt: str, image: bytes | None, json_mode: bool, max_tokens: int, temperature: float,
         effort: str = "medium", think: str | None = None) -> str:
    spec = MODELS[model]
    # Görüntü ~2000 giriş token'ı tutuyor (EN s53, 150 dpi: 2410 token, metin istemi dahil)
    _throttle.wait(model, len(prompt) // 3 + max_tokens + (2000 if image is not None else 0))
    if image is not None and not spec.vision:
        raise ValueError(f"{model} görüntü desteklemiyor")
    _last_usage.update(tokens=0, cached=0, thoughts=0)  # başarısız çağrıdan eski değer kalmasın
    if spec.provider == "gemini":
        return _call_gemini(model, prompt, image, json_mode, max_tokens, temperature, think)
    if spec.provider in _OPENAI_COMPAT:
        return _call_openai_compat(model, prompt, json_mode, max_tokens, temperature, image, effort)
    return _call_groq(model, prompt, json_mode, max_tokens, temperature, image, effort)


def call(role: str, prompt: str, image: bytes | None = None, json_mode: bool = False,
         max_tokens: int = 4096, temperature: float = 0.0, use_cache: bool = True, think: str | None = None) -> Result:
    """think: Gemini/Gemma düşünme düzeyi ('minimal' | 'high'); verilmezse modelin varsayılanı."""
    chain = ROLES[role]
    params = {"json": json_mode, "max_tokens": max_tokens, "temperature": temperature}
    effort = reasoning(role)
    # Akıl yürütme düzeyi önbellek anahtarına girer, yoksa 'low' denemesi eski 'medium' yanıtlarını okuyup sahte
    # sonuç verirdi. Yalnızca varsayılandan farklıysa eklenir: llm.sqlite'taki eski yanıtların anahtarı değişmez.
    if effort != "medium":
        params["reasoning"] = effort
    if think:
        params["think"] = think

    if use_cache:  # zincirdeki herhangi bir modelden daha önce alınmış yanıt varsa onu kullan
        for model in chain:
            hit = ledger.cache_get(ledger.cache_key(model, prompt, image, params))
            if hit is not None:
                return Result(hit, model, True)

    # Taşma: dakikalık sınırı o an dolu olan modeli beklemek yerine, zincirde boşta olan modeli öne al
    # (sıra korunur; hepsi doluysa ilk model beklenir).
    est = len(prompt) // 3 + max_tokens + (2000 if image is not None else 0)
    chain = [m for m in chain if _throttle.can(m, est)] + [m for m in chain if not _throttle.can(m, est)]

    errors, kinds = [], []
    for model in chain:
        if model not in MODELS or not has_key(model) or not ledger.available(model, need_tokens=est):
            continue
        if image is not None and ledger.usage(model)[0] == 0:  # yoklama: bugün hiç kullanılmadıysa
            try:
                _raw(model, "OK", None, False, 5, 0.0)
                ledger.record(model, 5)
            except Exception as e:
                kind, wait = _classify(e)
                _block(model, kind, wait)
                if kind == "busy":
                    _busy_rpd(model)
                errors.append(f"{model}: {kind}")
                kinds.append(kind)
                continue
        budget = max_tokens
        for attempt in range(2):
            try:
                text = _raw(model, prompt, image, json_mode, budget, temperature, effort, think)
                used = _last_usage["tokens"] or (len(prompt) // 3 + len(text) // 3 + (2000 if image is not None else 0))
                ledger.record(model, used, cached=_last_usage["cached"])
                _throttle.settle(model, used)
                _busy_streak.pop(model, None)
                if use_cache and (not json_mode or _valid_json(text)):
                    # Yarıda kesilmiş JSON önbelleğe alınmaz; yoksa bozuk cevap her seferinde geri gelirdi
                    # (Gemini 3.5 toplu üretimde düşünme token'ları çıktı sınırını doldurup JSON'u kesmişti).
                    ledger.cache_put(ledger.cache_key(model, prompt, image, params), model, text)
                return Result(text, model, False, _last_usage["thoughts"])
            except Exception as e:
                kind, wait = _classify(e)
                errors.append(f"{model}: {kind}")
                kinds.append(kind)
                if kind in ("daily", "missing"):
                    if kind == "daily":
                        _sync_used(model, e)
                    _block(model, kind, wait)
                    break
                if kind in ("minute", "network") and attempt == 0:
                    time.sleep(min(wait + 1, 90))
                    continue
                if kind == "busy" and _busy_rpd(model):  # Gemini: her deneme bir istek yakar → sıradaki model
                    break
                if kind == "busy" and attempt == 0:  # sağlayıcı yoğun (503): çoğu zaman saniyeler içinde geçer
                    time.sleep(20)
                    continue
                if kind == "json" and attempt == 0:  # cevap sığmadı: daha geniş token sınırıyla bir kez daha
                    budget = budget * 3
                    continue
                if kind == "json":
                    break
                if kind == "other":
                    raise
                break  # busy ya da ikinci dakikalık sınır → sıradaki model
    retry = min((ledger.time_until_available(m, est) for m in chain if m in MODELS), default=0.0)
    raise AllModelsExhausted(f"'{role}' rolündeki modeller kullanılamıyor: {'; '.join(errors) or 'hepsi şu an kapalı (günlük kota ya da yoğunluk beklemesi)'}",
                             kinds, retry)

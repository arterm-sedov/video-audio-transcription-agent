"""Live per-provider VLM model discovery with offline fallback.

Providers expose model catalogs over HTTP; capability signals differ:
- OpenRouter: ``input_modalities`` lists e.g. ``["text","image","video"]``.
- Polza: OpenAI-compatible ``/models`` (modality fields may be empty, so we
  filter by vision/video/audio keywords in the id as a heuristic).
- Gemini: no modality field on the list endpoint; filter by Gemini model id
  patterns and keep only models that support content generation.

When a provider endpoint is unreachable (e.g. Polza over VPN, or OpenRouter
without one), we fall back to the curated catalog so the UI always works.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

from .models_catalog import MODEL_CATALOG

VISION_OR_VIDEO_KEYWORDS = (
    "-vl",
    "vision",
    "omni",
    "video",
    "vlm",
    "glm-4.6v",
    "glm-5v",
    "ernie",
    "mimo",
    "gemini",
    "qwen3",
    "kimi",
    "minimax",
)


def _fetch_json(url: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "video-audio-transcription-agent/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _polza_base() -> str:
    return os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1").rstrip("/")


def _openrouter_base() -> str:
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


def _model_supports_media(model_id: str, modalities: list[str] | None) -> bool:
    if modalities:
        return any(m in modalities for m in ("image", "video", "audio"))
    lowered = model_id.lower()
    return any(k in lowered for k in VISION_OR_VIDEO_KEYWORDS)


def _fetch_openrouter(timeout: float = 20.0) -> tuple[str, ...]:
    payload = _fetch_json(f"{_openrouter_base()}/models", timeout)
    result = []
    for item in payload.get("data", []):
        model_id = item.get("id")
        if not model_id:
            continue
        modalities = item.get("input_modalities") or []
        if _model_supports_media(model_id, modalities):
            result.append(model_id)
    return tuple(result)


def _fetch_polza(timeout: float = 20.0) -> tuple[str, ...]:
    payload = _fetch_json(f"{_polza_base()}/models", timeout)
    result = []
    for item in payload.get("data", []):
        model_id = item.get("id")
        if not model_id:
            continue
        modalities = item.get("modality") or item.get("input_modalities")
        if _model_supports_media(model_id, modalities):
            result.append(model_id)
    return tuple(result)


def _fetch_gemini(timeout: float = 20.0) -> tuple[str, ...]:
    api_key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ()
    payload = _fetch_json(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        timeout,
    )
    result = []
    for item in payload.get("models", []):
        model_id = item.get("name", "").replace("models/", "")
        methods = item.get("supportedGenerationMethods") or []
        if not model_id or "generateContent" not in methods:
            continue
        if model_id.startswith(("gemini-", "google/gemini-")):
            result.append(model_id)
    return tuple(result)


def _price_for(model_id: str) -> float:
    from .models_catalog import PRICES

    return PRICES.get(model_id, 1e9)


def live_model_choices_for(provider: str) -> tuple[str, ...]:
    """Fetch live VLM models for a provider; fall back to the curated catalog."""
    key = provider.strip().lower()
    fetcher = {
        "openrouter": _fetch_openrouter,
        "polza": _fetch_polza,
        "gemini": _fetch_gemini,
    }.get(key)
    if fetcher is None:
        return MODEL_CATALOG["polza"]
    try:
        models = fetcher()
    except Exception:  # noqa: BLE001 - network fallback boundary
        models = MODEL_CATALOG.get(key, ())
    if not models:
        models = MODEL_CATALOG.get(key, ())
    return tuple(sorted(models, key=_price_for))


def live_model_choices_cached(
    provider: str, *, ttl_seconds: int = 3600, cache: dict | None = None
) -> tuple[str, ...]:
    """TTL-cached variant to avoid refetching on every dropdown change."""
    store = cache if cache is not None else {}
    now = time.time()
    hit = store.get(provider)
    if hit and now - hit[0] < ttl_seconds:
        return hit[1]
    choices = live_model_choices_for(provider)
    store[provider] = (now, choices)
    return choices

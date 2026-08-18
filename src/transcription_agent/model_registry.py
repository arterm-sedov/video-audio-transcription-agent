"""Live per-provider VLM model discovery with offline fallback.

Providers expose model catalogs over HTTP; capability signals differ:
- OpenRouter: ``input_modalities`` lists e.g. ``["text","image","video"]``.
- Polza: OpenAI-compatible ``/models`` with the same explicit modality field.
- Gemini: no modality field on the list endpoint; filter by Gemini model id
  patterns and keep only models that support content generation.

Live candidates must explicitly accept **audio and video** input: acceptance
of video alone does not mean a model hears a video's audio track, and
id-keyword guessing is too noisy (every ``qwen3*`` or ``gemini*`` id matches).
Models with missing/empty modality metadata are not guessed at; the curated
catalog is the stable evidence-grounded floor and always keeps selectors
non-blank even when an endpoint is unreachable (e.g. Polza over VPN or
OpenRouter without a key).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

from .models_catalog import (
    EXCLUDED,
    MODEL_CATALOG,
    canonical_model_id,
    model_sort_key,
)

# OpenRouter/Polza variant suffixes that are not general transcription models
# (image-only, batch-async, preview, tooling flavors). Filtered out of selectors.
VARIANT_SUFFIX_MARKERS = (
    ":batch",
    "-image",
    "-preview",
    "-customtools",
    "-tts",
    "-embedding",
    ":free",
    "-free",
    "openrouter/",  # routing pseudomodels (openrouter/auto, auto-beta)
    "anthropic/claude",  # Polza 400: no video endpoints
    "meta/muse-spark",  # OpenRouter 403: 18+ attestation gate
    "-codex",  # coding/tooling models, not transcription
)

# "~..." ids are OpenRouter weekly aliases (e.g. ~google/gemini-pro-latest); keep
# them, they always track the newest model.
_GEMINI_VERSION_RE = __import__("re").compile(
    r"^~?(?:google/)?gemini-(?P<family>[a-z0-9.-]+)$"
)


def _fetch_json(url: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "video-audio-transcription-agent/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _fetch_json_httpx(url: str, *, proxy: str = "", timeout: float = 20.0) -> dict:
    """Fetch JSON through an optional SOCKS/HTTP proxy (httpx transport)."""
    import httpx

    transport = httpx.HTTPTransport(proxy=proxy) if proxy else None
    with httpx.Client(transport=transport, timeout=timeout) as client:
        response = client.get(
            url, headers={"User-Agent": "video-audio-transcription-agent/0.1"}
        )
        response.raise_for_status()
        return response.json()


def _polza_base() -> str:
    return os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1").rstrip("/")


def _openrouter_base() -> str:
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")


def _model_supports_transcription(modalities: list[str] | None) -> bool:
    """True for live candidates that explicitly accept audio AND video input.

    Providers advertise video input for many models that never process the
    audio track (vision/video-only). Requiring both modalities keeps discovery
    aligned with the transcription use case. When metadata is missing we do
    not guess from the id; the curated catalog covers those known models.
    """
    if not modalities:
        return False
    has = set(modalities)
    return "audio" in has and "video" in has


def _extract_modalities(item: dict) -> list[str] | None:
    """Read modalities from any source providers expose."""
    for source in ("modality", "input_modalities"):
        value = item.get(source)
        if value:
            return list(value)
    arch = item.get("architecture") or {}
    value = arch.get("input_modalities")
    return list(value) if value else None


def _is_model_variant(model_id: str) -> bool:
    """True for batch/image/preview/tooling variants to drop from selectors."""
    return any(marker in model_id for marker in VARIANT_SUFFIX_MARKERS)


def _dedupe_gemini_latest(model_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Keep the newest version per Gemini family plus the ~ latest aliases."""
    keep: set[str] = set()
    family_best: dict[str, tuple[tuple[int, ...], str]] = {}
    for mid in model_ids:
        lowered = mid.lower()
        match = _GEMINI_VERSION_RE.match(mid)
        if not match or "gemini" not in lowered:
            keep.add(mid)  # non-gemini go through unchanged
            continue
        family = match.group("family")
        # Weekly alias (no numeric version) or a family without a version:
        # keep as-is (it always tracks latest).
        parts = family.split("-")
        version: tuple[int, ...] = ()
        for i, part in enumerate(parts):
            if part[0].isdigit():
                try:
                    version = tuple(int(x) for x in part.split("."))
                    family_kind = "-".join(parts[:i] + parts[i + 1 :])
                    break
                except ValueError:
                    version = ()
        if not version:
            # e.g. pro-latest, omni-video with no numeric version -> keep alias
            if "latest" in family or "omni" in family:
                keep.add(mid)
            continue
        key = family_kind or "gemini"
        if key not in family_best or version > family_best[key][0]:
            family_best[key] = (version, mid)
    keep.update(v for (_, v) in family_best.values())
    return tuple(keep)


def _fetch_openrouter(timeout: float = 20.0) -> tuple[str, ...]:
    payload = _fetch_json(f"{_openrouter_base()}/models", timeout)
    result = []
    for item in payload.get("data", []):
        model_id = item.get("id")
        if not model_id or _is_model_variant(model_id):
            continue
        modalities = _extract_modalities(item)
        if _model_supports_transcription(modalities):
            result.append(model_id)
    return _dedupe_gemini_latest(tuple(result))


def _fetch_polza(timeout: float = 20.0) -> tuple[str, ...]:
    proxy = os.getenv("TRANSCRIPTION_POLZA_PROXY", "").strip()
    payload = _fetch_json_httpx(f"{_polza_base()}/models", proxy=proxy, timeout=timeout)
    result = []
    for item in payload.get("data", []):
        model_id = item.get("id")
        if not model_id or _is_model_variant(model_id):
            continue
        modalities = _extract_modalities(item)
        if _model_supports_transcription(modalities):
            result.append(model_id)
    return _dedupe_gemini_latest(tuple(result))


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
            result.append(canonical_model_id(model_id))
    return tuple(result)


def live_model_choices_for(provider: str) -> tuple[str, ...]:
    """Combine the curated catalog with gated live candidates, minus excluded.

    The static catalog is the stable evidence-grounded floor: tested models
    first, then the other curated entries. Live discovery adds only candidates
    whose provider metadata explicitly lists both audio and video input
    (video-only acceptance cannot transcribe a video's audio track). Models
    marked excluded (tested and found vision-only or audio-silent) are always
    dropped, even if live discovery reports them media-capable.
    """
    key = provider.strip().lower()
    fetcher = {
        "openrouter": _fetch_openrouter,
        "polza": _fetch_polza,
        "gemini": _fetch_gemini,
    }.get(key)
    catalog_floor = set(MODEL_CATALOG.get(key, ()))
    try:
        live = set(fetcher()) if fetcher is not None else set()
    except Exception:  # noqa: BLE001 - network fallback boundary
        live = set()
    combined = catalog_floor | live
    if not combined:
        combined = set(MODEL_CATALOG.get(key, ()))
    combined -= EXCLUDED
    return tuple(sorted(combined, key=model_sort_key))


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

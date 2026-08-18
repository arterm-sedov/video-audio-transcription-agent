"""Per-provider VLM model catalog loaded from YAML.

Data lives in ``models_catalog.yaml`` (lean, DRY, editable without code).
This module only loads and exposes it. Live discovery is in
``model_registry.py``; this catalog is the offline fallback.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).with_name("models_catalog.yaml")


@lru_cache(maxsize=1)
def _load_catalog() -> dict:
    import yaml

    return yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))


def canonical_model_id(model_id: str) -> str:
    """Normalize Gemini ids to the google/ prefix used by Polza/OpenRouter."""
    if model_id.startswith("gemini-"):
        return f"google/{model_id}"
    return model_id


def _merge_gemini_twins(models: dict) -> dict:
    """Collapse bare gemini-* twins into a single google/gemini-* entry."""
    merged: dict = {}
    for model_id, entry in models.items():
        canonical = canonical_model_id(model_id)
        existing = merged.get(canonical)
        if existing is None:
            merged[canonical] = {
                **entry,
                "providers": list(entry.get("providers", [])),
            }
            continue
        providers = list(
            dict.fromkeys([*existing.get("providers", []), *entry.get("providers", [])])
        )
        combined = {**existing, **entry, "providers": providers}
        if existing.get("tested") or entry.get("tested"):
            combined["tested"] = True
        if existing.get("excluded") or entry.get("excluded"):
            combined["excluded"] = True
        merged[canonical] = combined
    return merged


_MODELS_DATA = _merge_gemini_twins(_load_catalog()["models"])

# Evidence-grounded primer (verified speech-from-video) and known-bad models:
# live discovery should keep the former and always drop the latter.
TESTED: frozenset[str] = frozenset(
    model_id for model_id, entry in _MODELS_DATA.items() if entry.get("tested")
)
EXCLUDED: frozenset[str] = frozenset(
    model_id for model_id, entry in _MODELS_DATA.items() if entry.get("excluded")
)

PRICES: dict[str, float] = {
    model_id: float(entry["price"]) for model_id, entry in _MODELS_DATA.items()
}

RUSSIAN_QUALITY: dict[str, str] = {
    model_id: str(entry.get("russian_quality", "unknown"))
    for model_id, entry in _MODELS_DATA.items()
}

_RUSSIAN_QUALITY_RANK = {"strong": 0, "good": 1, "unknown": 2}

SPEED: dict[str, str] = {
    model_id: str(entry.get("speed", "unknown"))
    for model_id, entry in _MODELS_DATA.items()
}

SPEED_S: dict[str, float] = {
    model_id: float(entry.get("speed_s", 1e9))
    for model_id, entry in _MODELS_DATA.items()
}

RELIABILITY: dict[str, str] = {
    model_id: str(entry.get("reliability", "unknown"))
    for model_id, entry in _MODELS_DATA.items()
}

_SPEED_RANK = {"fast": 0, "medium": 1, "slow": 2, "unknown": 3}

PROVIDERS_BY_MODEL: dict[str, tuple[str, ...]] = {
    model_id: tuple(entry["providers"]) for model_id, entry in _MODELS_DATA.items()
}

_MODEL_CATALOG: dict[str, list[str]] = {}
for model_id, providers in PROVIDERS_BY_MODEL.items():
    for provider in providers:
        _MODEL_CATALOG.setdefault(provider, []).append(model_id)
MODEL_CATALOG: dict[str, tuple[str, ...]] = {
    provider: tuple(models) for provider, models in _MODEL_CATALOG.items()
}


def model_sort_key(model_id: str) -> tuple[int, int, float, float, str]:
    """Sort tested first, then quality, then price, then speed."""
    return (
        0 if model_id in TESTED else 1,
        _RUSSIAN_QUALITY_RANK.get(RUSSIAN_QUALITY.get(model_id, "unknown"), 2),
        PRICES.get(model_id, 1e9),
        SPEED_S.get(model_id, 1e9),
        model_id,
    )


def rating_label(model_id: str) -> str:
    """Compact quality/speed/reliability label for CLI listings."""
    quality = RUSSIAN_QUALITY.get(model_id, "unknown")
    speed = SPEED.get(model_id, "unknown")
    reliability = RELIABILITY.get(model_id, "unknown")
    return f"quality={quality} speed={speed} reliability={reliability}"


def model_choices_for(provider: str) -> tuple[str, ...]:
    """Static catalog models, ranked quality then price then speed."""
    key = provider.strip().lower()
    models = MODEL_CATALOG.get(key, MODEL_CATALOG["polza"])
    eligible = [m for m in models if m not in EXCLUDED]
    return tuple(sorted(eligible, key=model_sort_key))

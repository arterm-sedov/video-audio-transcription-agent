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


_MODELS_DATA = _load_catalog()["models"]

# Evidence-grounded primer (verified speech-from-video) and known-bad models:
# live discovery should keep the former and always drop the latter.
TESTED: frozenset[str] = frozenset(
    model_id
    for model_id, entry in _MODELS_DATA.items()
    if entry.get("tested")
)
EXCLUDED: frozenset[str] = frozenset(
    model_id
    for model_id, entry in _MODELS_DATA.items()
    if entry.get("excluded")
)

PRICES: dict[str, float] = {
    model_id: float(entry["price"]) for model_id, entry in _MODELS_DATA.items()
}

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


def model_choices_for(provider: str) -> tuple[str, ...]:
    """Static catalog models for a provider, cheapest first, minus excluded."""
    key = provider.strip().lower()
    models = MODEL_CATALOG.get(key, MODEL_CATALOG["polza"])
    eligible = [m for m in models if m not in EXCLUDED]
    return tuple(sorted(eligible, key=lambda mid: PRICES.get(mid, 1e9)))

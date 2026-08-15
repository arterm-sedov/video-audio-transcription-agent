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


MODEL_CATALOG: dict[str, tuple[str, ...]] = {
    provider: tuple(models) for provider, models in _load_catalog()["providers"].items()
}

PRICES: dict[str, float] = dict(_load_catalog()["prices"])


def model_choices_for(provider: str) -> tuple[str, ...]:
    """Models available for a provider, cheapest first."""
    key = provider.strip().lower()
    models = MODEL_CATALOG.get(key, MODEL_CATALOG["polza"])
    return tuple(sorted(models, key=lambda mid: PRICES.get(mid, 1e9)))

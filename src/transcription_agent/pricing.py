"""Small dynamic model-pricing connector with cached fallback."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ModelPricing:
    model: str
    input_per_token: float | None
    output_per_token: float | None
    source: str


def fetch_openrouter_pricing(
    models: list[str],
    *,
    api_key: str | None = None,
    cache_file: str | Path | None = None,
) -> dict[str, ModelPricing]:
    """Fetch only requested model prices and optionally cache the result."""
    cache_path = Path(cache_file) if cache_file else None
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        request = Request("https://openrouter.ai/api/v1/models", headers=headers)
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        entries = {item.get("id"): item for item in payload.get("data", [])}
        result = {
            model: ModelPricing(
                model,
                _float_or_none(entries[model].get("pricing", {}).get("prompt")),
                _float_or_none(entries[model].get("pricing", {}).get("completion")),
                "openrouter-api",
            )
            for model in models
            if model in entries
        }
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps({key: asdict(value) for key, value in result.items()}),
                encoding="utf-8",
            )
        return result
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        if not cache_path or not cache_path.is_file():
            return {}
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return {
            key: ModelPricing(**value)
            for key, value in payload.items()
            if key in models
        }


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

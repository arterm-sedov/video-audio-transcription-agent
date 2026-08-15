"""Provider usage and cost normalization."""

import os
from dataclasses import dataclass

POLZA_DEFAULT_RATE = 90.0  # RUB per 1 USD, used when env var is absent


def get_polza_rate() -> float:
    """Return RUB-per-USD rate from env or the built-in default."""
    raw = os.getenv("POLZA_RUB_TO_USD_RATE", "").strip()
    if raw:
        try:
            rate = float(raw)
            if rate > 0:
                return rate
        except ValueError:
            pass
    return POLZA_DEFAULT_RATE


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    currency: str = "USD"

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def normalize_usage(provider: str, usage: dict | None) -> Usage:
    """Normalize OpenAI/OpenRouter/Polza usage dictionaries."""
    usage = usage or {}
    input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
    output_tokens = int(
        usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    )
    if provider == "polza" and usage.get("cost_rub") is not None:
        # Polza: cost_rub is authoritative (rubles); cost is an alias in rubles too.
        return Usage(
            input_tokens,
            output_tokens,
            float(usage["cost_rub"]) / get_polza_rate(),
        )
    raw_cost = usage.get("cost")
    return Usage(
        input_tokens, output_tokens, float(raw_cost) if raw_cost is not None else None
    )


def format_cost(cost_usd: float | None) -> str:
    if cost_usd is None:
        return "—"
    if cost_usd == 0:
        return "$0.0000"
    return f"${cost_usd:.4f}".rstrip("0").rstrip(".")

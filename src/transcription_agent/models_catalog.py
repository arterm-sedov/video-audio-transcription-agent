"""Per-provider video-capable model catalog shared by CLI and GUI.

Not every provider serves every model. Each provider lists exactly the
models it can serve:
- ``polza`` — OpenAI-compatible catalog (Polza list endpoint, 387 models).
- ``openrouter`` — OpenAI-compatible catalog, may differ from Polza.
- ``gemini`` — direct Gemini API, Google models only.

Pricing order is a curated estimate (cheapest first) because live pricing
endpoints are geo-blocked from the development network; the prices below
are per-1M input tokens and are indicative only.
"""

from __future__ import annotations

MODEL_CATALOG: dict[str, tuple[str, ...]] = {
    "polza": (
        "google/gemini-3.5-flash-lite",
        "google/gemini-3.6-flash",
        "google/gemini-3-flash-preview",
        "google/gemini-2.5-flash",
        "google/gemini-3.1-pro-preview",
        "qwen/qwen3.6-flash",
        "qwen/qwen3.6-plus",
        "qwen/qwen3.7-max",
        "qwen/qwen3-vl-8b-instruct",
        "qwen/qwen3-vl-32b-instruct",
        "qwen/qwen3-vl-235b-a22b-instruct",
        "qwen/qwen2.5-vl-72b-instruct",
        "z-ai/glm-4.6v",
        "z-ai/glm-5v-turbo",
        "z-ai/glm-5.1",
        "z-ai/glm-5.2",
        "stepfun/step-3.7-flash",
        "minimax/minimax-m2.7",
        "minimax/minimax-m3",
        "moonshotai/kimi-k2.6",
        "moonshotai/kimi-k3",
        "xiaomi/mimo-v2.5-pro",
        "baidu/ernie-4.5-vl-424b-a47b",
        "gemini-omni-video",
    ),
    "openrouter": (
        "google/gemini-3.5-flash-lite",
        "google/gemini-3.6-flash",
        "google/gemini-3-flash-preview",
        "google/gemini-2.5-flash",
        "google/gemini-3.1-pro-preview",
        "qwen/qwen3.6-plus",
        "qwen/qwen3-vl-32b-instruct",
        "minimax/minimax-m3",
        "moonshotai/kimi-k3",
        "z-ai/glm-5.2",
        "gemini-omni-video",
    ),
    "gemini": (
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-pro-preview",
    ),
}

# Est. USD per 1M input tokens for ranking (cheapest first per provider).
PRICES: dict[str, float] = {
    "google/gemini-3.5-flash-lite": 0.05,
    "gemini-3.5-flash-lite": 0.05,
    "gemini-3.6-flash": 0.10,
    "google/gemini-3.6-flash": 0.10,
    "google/gemini-3-flash-preview": 0.10,
    "gemini-3-flash-preview": 0.10,
    "qwen/qwen3.6-flash": 0.10,
    "stepfun/step-3.7-flash": 0.10,
    "qwen/qwen3-vl-8b-instruct": 0.05,
    "qwen/qwen3-vl-32b-instruct": 0.15,
    "z-ai/glm-4.6v": 0.15,
    "z-ai/glm-5v-turbo": 0.20,
    "google/gemini-2.5-flash": 0.30,
    "gemini-2.5-flash": 0.30,
    "qwen/qwen3.6-plus": 0.40,
    "qwen/qwen2.5-vl-72b-instruct": 0.40,
    "minimax/minimax-m2.7": 0.40,
    "moonshotai/kimi-k2.6": 0.40,
    "z-ai/glm-5.1": 0.50,
    "qwen/qwen3-vl-235b-a22b-instruct": 0.60,
    "minimax/minimax-m3": 0.60,
    "moonshotai/kimi-k3": 0.60,
    "xiaomi/mimo-v2.5-pro": 0.60,
    "z-ai/glm-5.2": 0.70,
    "qwen/qwen3.7-max": 0.80,
    "baidu/ernie-4.5-vl-424b-a47b": 0.80,
    "gemini-3.1-flash-lite-preview": 0.40,
    "gemini-2.5-pro": 1.25,
    "google/gemini-3.1-pro-preview": 1.25,
    "gemini-3.1-pro-preview": 1.25,
    "gemini-omni-video": 1.50,
}


def model_choices_for(provider: str) -> tuple[str, ...]:
    """Models available for a provider, cheapest first."""
    key = provider.strip().lower()
    models = MODEL_CATALOG.get(key, MODEL_CATALOG["polza"])
    return tuple(sorted(models, key=lambda mid: PRICES.get(mid, 1e9)))

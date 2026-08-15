"""Curated video-capable model catalog shared by CLI and GUI.

Polza and OpenRouter share the same OpenAI-compatible model namespace.
Direct Gemini only serves Gemini models. Pricing order is a curated
estimate (cheapest first) because OpenRouter's pricing endpoint is
geo-blocked from the development network; the prices below are per-1M
input tokens and are indicative only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogModel:
    id: str
    family: str
    price_per_1m_input_usd: float | None
    note: str = ""

    @property
    def provider(self) -> str:
        return (
            "gemini" if self.id.startswith(("gemini-", "google/gemini-")) else "openai"
        )


SHARED_VIDEO_MODELS: tuple[CatalogModel, ...] = (
    CatalogModel(
        "google/gemini-3.5-flash-lite", "Gemini", 0.05, "cheapest gemini tier"
    ),
    CatalogModel("qwen/qwen3-vl-8b-instruct", "Qwen", 0.05, "small VLM"),
    CatalogModel("google/gemini-3.6-flash", "Gemini", 0.10, "fast flash tier"),
    CatalogModel("google/gemini-3-flash-preview", "Gemini", 0.10, "flash preview"),
    CatalogModel("qwen/qwen3.6-flash", "Qwen", 0.10, "fast qwen tier"),
    CatalogModel("stepfun/step-3.7-flash", "StepFun", 0.10, "multimodal flash"),
    CatalogModel("qwen/qwen3-vl-32b-instruct", "Qwen", 0.15, "mid VLM"),
    CatalogModel("z-ai/glm-4.6v", "GLM", 0.15, "vision GLM"),
    CatalogModel("z-ai/glm-5v-turbo", "GLM", 0.20, "fast vision GLM"),
    CatalogModel("google/gemini-2.5-flash", "Gemini", 0.30, "battle-tested"),
    CatalogModel("qwen/qwen3.6-plus", "Qwen", 0.40, "plus tier"),
    CatalogModel("qwen/qwen2.5-vl-72b-instruct", "Qwen", 0.40, "proven 72B VLM"),
    CatalogModel("minimax/minimax-m2.7", "MiniMax", 0.40, "omni"),
    CatalogModel("moonshotai/kimi-k2.6", "Kimi", 0.40, "kimi tier"),
    CatalogModel("z-ai/glm-5.1", "GLM", 0.50, "glm tier"),
    CatalogModel("qwen/qwen3-vl-235b-a22b-instruct", "Qwen", 0.60, "large VLM"),
    CatalogModel("minimax/minimax-m3", "MiniMax", 0.60, "newest omni"),
    CatalogModel("moonshotai/kimi-k3", "Kimi", 0.60, "newest kimi"),
    CatalogModel("xiaomi/mimo-v2.5-pro", "MiMo", 0.60, "omni video"),
    CatalogModel("z-ai/glm-5.2", "GLM", 0.70, "newest glm"),
    CatalogModel("qwen/qwen3.7-max", "Qwen", 0.80, "max tier"),
    CatalogModel("baidu/ernie-4.5-vl-424b-a47b", "ERNIE", 0.80, "Baidu VL 424B"),
    CatalogModel("google/gemini-3.1-pro-preview", "Gemini", 1.25, "pro tier"),
    CatalogModel("gemini-omni-video", "Gemini", 1.50, "dedicated video"),
)

GEMINI_ONLY_MODELS: tuple[CatalogModel, ...] = tuple(
    model for model in SHARED_VIDEO_MODELS if model.provider == "gemini"
)

SHARED_MODEL_IDS: tuple[str, ...] = tuple(model.id for model in SHARED_VIDEO_MODELS)
GEMINI_MODEL_IDS: tuple[str, ...] = tuple(model.id for model in GEMINI_ONLY_MODELS)


def model_choices_for(provider: str) -> tuple[str, ...]:
    if provider.strip().lower() == "gemini":
        return GEMINI_MODEL_IDS
    return SHARED_MODEL_IDS

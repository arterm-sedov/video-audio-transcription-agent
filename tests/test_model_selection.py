from dataclasses import replace

from transcription_agent.app import build_demo
from transcription_agent.config import Settings
from transcription_agent.models_catalog import model_choices_for
from transcription_agent.providers import configured_providers


def test_cli_model_flag_replaces_settings() -> None:
    settings = Settings.from_env()
    updated = replace(settings, model="qwen/qwen3.6-plus")
    assert updated.model == "qwen/qwen3.6-plus"
    assert settings.model != updated.model


def test_configured_providers_normalize_model_per_provider(monkeypatch) -> None:
    monkeypatch.setenv("POLZA_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    providers = configured_providers(
        "google/gemini-2.5-flash", ("polza", "gemini", "openrouter")
    )
    assert providers["polza"].model == "google/gemini-2.5-flash"
    assert providers["openrouter"].model == "google/gemini-2.5-flash"
    assert providers["gemini"].model == "gemini-2.5-flash"


def test_model_choices_are_provider_aware() -> None:
    gemini_models = model_choices_for("gemini")
    assert all(choice.startswith("gemini-") for choice in gemini_models)
    assert "gemini-2.5-flash" in gemini_models
    assert "gemini-2.5-pro" in gemini_models
    assert "qwen/qwen3.6-plus" in model_choices_for("polza")
    assert all("qwen" not in choice for choice in model_choices_for("gemini"))


def test_model_choices_are_price_sorted() -> None:
    from transcription_agent.models_catalog import PRICES

    for provider in ("polza", "openrouter", "gemini"):
        prices = [PRICES.get(model, 1e9) for model in model_choices_for(provider)]
        assert prices == sorted(prices), provider


def test_demo_still_builds() -> None:
    demo = build_demo()
    assert type(demo).__name__ == "Blocks"

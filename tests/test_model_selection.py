from dataclasses import replace

from transcription_agent.app import MODEL_CHOICES
from transcription_agent.config import Settings
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


def test_model_choices_include_default() -> None:
    assert "google/gemini-2.5-flash" in MODEL_CHOICES
    assert any(choice.startswith("qwen/") for choice in MODEL_CHOICES)

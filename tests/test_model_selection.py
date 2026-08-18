from dataclasses import replace

from transcription_agent.app import build_demo
from transcription_agent.config import Settings
from transcription_agent.models_catalog import model_choices_for
from transcription_agent.providers import configured_providers

# Placeholder proxy used only to exercise proxy propagation. The real value in
# this repo comes from TRANSCRIPTION_POLZA_PROXY / TRANSCRIPTION_PROXY (no host
# is baked into the source).
PROXY_EXAMPLE = "socks5h://<proxy-host>:1080"


def test_cli_model_flag_replaces_settings() -> None:
    settings = Settings.from_env()
    updated = replace(settings, model="qwen/qwen3.6-plus")
    assert updated.model == "qwen/qwen3.6-plus"
    assert settings.model != updated.model


def test_default_model_is_gemini_31_flash_lite(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTION_MODEL", raising=False)
    assert Settings().model == "google/gemini-3.1-flash-lite"
    settings = Settings.from_env(None)
    assert settings.model == "google/gemini-3.1-flash-lite"


def test_configured_providers_normalize_model_per_provider(monkeypatch) -> None:
    monkeypatch.setenv("POLZA_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    providers = configured_providers(
        "google/gemini-2.5-flash", ("polza", "gemini", "openrouter")
    )
    assert providers["polza"].model == "google/gemini-2.5-flash"
    assert providers["openrouter"].model == "google/gemini-2.5-flash"
    assert providers["gemini"].model == "gemini-2.5-flash"


def test_configured_providers_pass_proxy(monkeypatch) -> None:
    monkeypatch.setenv("POLZA_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    providers = configured_providers(
        "google/gemini-2.5-flash",
        ("polza", "gemini", "openrouter"),
        proxy=PROXY_EXAMPLE,
    )
    assert providers["polza"].proxy == PROXY_EXAMPLE
    assert providers["openrouter"].proxy == PROXY_EXAMPLE
    assert providers["gemini"].proxy == PROXY_EXAMPLE


def test_empty_openrouter_proxy_env_does_not_inherit_global(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTION_POLZA_PROXY", PROXY_EXAMPLE)
    monkeypatch.setenv("TRANSCRIPTION_OPENROUTER_PROXY", "")
    monkeypatch.setenv("TRANSCRIPTION_PROXY", PROXY_EXAMPLE)
    monkeypatch.delenv("TRANSCRIPTION_GEMINI_PROXY", raising=False)
    settings = Settings.from_env(None)
    assert settings.provider_proxy("polza") == PROXY_EXAMPLE
    assert settings.provider_proxy("openrouter") == ""
    assert settings.provider_proxy("gemini") == PROXY_EXAMPLE


def test_model_choices_are_provider_aware() -> None:
    gemini_models = model_choices_for("gemini")
    assert all(choice.startswith("google/gemini-") for choice in gemini_models)
    assert "google/gemini-2.5-flash" in gemini_models
    assert "google/gemini-2.5-pro" in gemini_models
    assert "google/gemini-3.5-flash-lite" in model_choices_for("polza")
    assert "xiaomi/mimo-v2.5" in model_choices_for("polza")
    assert all("qwen" not in choice for choice in model_choices_for("gemini"))


def test_model_choices_prioritize_tested_and_russian_evidence() -> None:
    from transcription_agent.models_catalog import EXCLUDED, TESTED

    for provider in ("polza", "openrouter", "gemini"):
        choices = model_choices_for(provider)
        assert not (set(choices) & EXCLUDED), provider
        first_untested = next(
            (index for index, model in enumerate(choices) if model not in TESTED),
            len(choices),
        )
        assert all(model in TESTED for model in choices[:first_untested]), provider

    polza_choices = model_choices_for("polza")
    assert polza_choices.index("google/gemini-3.5-flash-lite") < polza_choices.index(
        "xiaomi/mimo-v2.5"
    )


def test_model_choices_rank_quality_then_price_then_speed() -> None:
    from transcription_agent.models_catalog import TESTED, rating_label

    assert "xiaomi/mimo-v2.5" in TESTED
    assert "xiaomi/qwens-v2.5" not in TESTED
    polza = model_choices_for("polza")
    assert polza[0] == "google/gemini-3.1-flash-lite"
    assert polza.index("google/gemini-3.1-flash-lite") < polza.index(
        "google/gemini-3.5-flash-lite"
    )
    assert polza.index("google/gemini-3.5-flash-lite") < polza.index(
        "google/gemini-3.6-flash"
    )
    assert polza.index("google/gemini-3.6-flash") < polza.index(
        "google/gemini-3.7-flash"
    )
    assert polza.index("google/gemini-3.7-flash") < polza.index(
        "google/gemini-2.5-flash"
    )
    assert polza.index("google/gemini-2.5-flash") < polza.index(
        "google/gemini-3.5-flash"
    )
    assert polza.index("google/gemini-3.5-flash") < polza.index("google/gemini-2.5-pro")
    assert polza.index("google/gemini-2.5-pro") < polza.index(
        "google/gemini-2.5-flash-lite"
    )
    assert polza.index("google/gemini-2.5-flash-lite") < polza.index("xiaomi/mimo-v2.5")
    label = rating_label("google/gemini-3.1-flash-lite")
    assert "quality=strong" in label
    assert "speed=fast" in label
    assert "reliability=high" in label


def test_demo_still_builds() -> None:
    demo = build_demo()
    assert type(demo).__name__ == "Blocks"


def test_upload_timeout_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTION_UPLOAD_TIMEOUT", "25")
    settings = Settings.from_env(None)
    assert settings.upload_timeout_seconds == 25.0


def test_catalog_gemini_ids_are_canonical_google_prefixed() -> None:
    from transcription_agent.models_catalog import (
        MODEL_CATALOG,
        PROVIDERS_BY_MODEL,
        canonical_model_id,
    )

    assert canonical_model_id("gemini-2.5-flash") == "google/gemini-2.5-flash"
    assert canonical_model_id("google/gemini-2.5-flash") == "google/gemini-2.5-flash"
    assert canonical_model_id("xiaomi/mimo-v2.5") == "xiaomi/mimo-v2.5"
    assert all(not key.startswith("gemini-") for key in PROVIDERS_BY_MODEL)
    assert "google/gemini-2.5-flash" in MODEL_CATALOG["gemini"]
    assert "google/gemini-2.5-flash" in MODEL_CATALOG["polza"]
    assert "google/gemini-2.5-flash" in MODEL_CATALOG["openrouter"]
    assert "gemini" in PROVIDERS_BY_MODEL["google/gemini-2.5-flash"]

from transcription_agent.model_registry import (
    _model_supports_media,
    live_model_choices_cached,
    live_model_choices_for,
)
from transcription_agent.models_catalog import MODEL_CATALOG


def test_model_supports_media_by_modality() -> None:
    assert _model_supports_media("x/y", ["text", "image", "video"])
    assert not _model_supports_media("x/y", ["text"])
    assert _model_supports_media("qwen/qwen3-vl-32b-instruct", None)
    assert not _model_supports_media("deepseek/deepseek-chat", None)


def test_live_fetch_falls_back_to_catalog(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("unreachable")

    monkeypatch.setattr("transcription_agent.model_registry._fetch_openrouter", boom)
    monkeypatch.setattr("transcription_agent.model_registry._fetch_polza", boom)
    monkeypatch.setattr("transcription_agent.model_registry._fetch_gemini", boom)
    for provider in ("polza", "openrouter", "gemini"):
        choices = live_model_choices_for(provider)
        assert choices, provider
        assert set(choices) <= set(MODEL_CATALOG.get(provider, ())), provider


def test_cached_choices_reuse(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_fetch(*_args, **_kwargs):
        calls["n"] += 1
        return ("a", "b")

    monkeypatch.setattr("transcription_agent.model_registry._fetch_polza", fake_fetch)
    cache = {}
    live_model_choices_cached("polza", cache=cache)
    live_model_choices_cached("polza", cache=cache)
    assert calls["n"] == 1

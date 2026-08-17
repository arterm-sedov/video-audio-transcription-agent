from transcription_agent.model_registry import (
    _dedupe_gemini_latest,
    _is_model_variant,
    _model_supports_video,
    live_model_choices_cached,
    live_model_choices_for,
)
from transcription_agent.models_catalog import (
    EXCLUDED,
    MODEL_CATALOG,
    TESTED,
)


def test_model_supports_video_only_accepts_video() -> None:
    assert _model_supports_video("x/y", ["text", "image", "video"])
    assert _model_supports_video("x/y", ["video", "audio"])
    assert not _model_supports_video("x/y", ["text", "image"])
    assert not _model_supports_video("x/y", ["audio"])  # audio alone isn't video
    # Name-keyword heuristic still applies when modalities are unknown.
    assert _model_supports_video("qwen/qwen3-vl-32b-instruct", None)
    assert not _model_supports_video("deepseek/deepseek-chat", None)


def test_variant_suffixes_are_filtered() -> None:
    for mid in (
        "google/gemini-2.5-flash:batch",
        "google/gemini-2.5-flash-image",
        "google/gemini-3.6-flash:batch",
        "google/gemini-3.1-flash-lite-preview",
        "google/gemini-3.1-pro-preview-customtools",
    ):
        assert _is_model_variant(mid), mid
    assert not _is_model_variant("google/gemini-3.7-flash")
    assert not _is_model_variant("minimax/minimax-m3")


def test_gemini_latest_of_family_dedup() -> None:
    models = (
        "google/gemini-3.7-flash",
        "google/gemini-3.6-flash",
        "google/gemini-3.5-flash-lite",
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro",
        "~google/gemini-flash-latest",
        "~google/gemini-pro-latest",
        "minimax/minimax-m3",
    )
    out = _dedupe_gemini_latest(models)
    ids = set(out)
    # newest flash kept, older flash dropped
    assert "google/gemini-3.7-flash" in ids
    assert "google/gemini-3.6-flash" not in ids
    assert "google/gemini-2.5-flash" not in ids
    # different families + latest aliases + non-gemini preserved
    assert "google/gemini-3.5-flash-lite" in ids
    assert "google/gemini-2.5-pro" in ids
    assert "~google/gemini-flash-latest" in ids
    assert "~google/gemini-pro-latest" in ids
    assert "minimax/minimax-m3" in ids


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


def test_selector_union_keeps_primer_drops_excluded(monkeypatch) -> None:
    import transcription_agent.model_registry as reg

    live = ("minimax/minimax-m3", "moonshotai/kimi-k3", "some/new-omni-video")
    monkeypatch.setattr(reg, "_fetch_openrouter", lambda *a, **k: live)

    choices = live_model_choices_for("openrouter")
    ids = set(choices)
    # Primer (tested) models are always kept.
    assert {"minimax/minimax-m3", "qwen/qwen3.6-plus"} <= ids
    # Known-bad models are dropped even if live discovery lists them.
    assert "moonshotai/kimi-k3" not in ids
    assert "moonshotai/kimi-k3" in EXCLUDED
    # New live candidates are added.
    assert "some/new-omni-video" in ids


def test_static_choices_exclude_known_bad() -> None:
    import transcription_agent.models_catalog as mc

    for provider in ("polza", "openrouter"):
        ids = set(mc.model_choices_for(provider))
        assert not (ids & EXCLUDED)
    # Sanity: the primer is non-empty so selectors aren't blank.
    assert TESTED
    assert {"minimax/minimax-m3", "qwen/qwen3.6-plus"} <= set(TESTED)


def test_polza_fetch_reads_nested_arch_modalities(monkeypatch) -> None:
    # Polza reports modalities under architecture.input_modalities (top-level
    # modality fields are None), so Gemini/etc. must still be discovered.
    import transcription_agent.model_registry as reg

    payload = {"data": [
        {"id": "google/gemini-3.7-flash",
         "modality": None,
         "input_modalities": None,
         "architecture": {"input_modalities": ["text", "image", "video", "audio"]}},
        {"id": "anthropic/claude-sonnet", "modality": None, "input_modalities": None},
    ]}
    monkeypatch.setattr(reg, "_fetch_json_httpx", lambda *a, **k: payload)
    models = reg._fetch_polza(timeout=1)
    assert "google/gemini-3.7-flash" in models
    assert "anthropic/claude-sonnet" not in models

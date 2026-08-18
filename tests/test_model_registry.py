from transcription_agent.model_registry import (
    _dedupe_gemini_latest,
    _is_model_variant,
    _model_supports_transcription,
    live_model_choices_cached,
    live_model_choices_for,
)
from transcription_agent.models_catalog import (
    EXCLUDED,
    MODEL_CATALOG,
    TESTED,
)


def test_model_supports_transcription_requires_audio_and_video() -> None:
    # Transcription needs a model that hears the audio track of a video.
    assert _model_supports_transcription(["text", "image", "video", "audio"])
    assert _model_supports_transcription(["audio", "video"])
    # Video-only acceptance (common on provider listings) is not enough.
    assert not _model_supports_transcription(["text", "image", "video"])
    # Audio-only STT models cannot consume the video path.
    assert not _model_supports_transcription(["audio"])
    # Missing metadata gets no id-keyword guessing from live discovery.
    assert not _model_supports_transcription(None)


def test_variant_suffixes_are_filtered() -> None:
    for mid in (
        "google/gemini-2.5-flash:batch",
        "google/gemini-2.5-flash-image",
        "google/gemini-3.6-flash:batch",
        "google/gemini-3.1-flash-lite-preview",
        "google/gemini-3.1-pro-preview-customtools",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "openrouter/auto",
        "openrouter/auto-beta",
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
    assert {"google/gemini-3.5-flash-lite", "xiaomi/mimo-v2.5"} <= ids
    assert "minimax/minimax-m3" not in ids
    assert "qwen/qwen3.6-plus" not in ids
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
    # Official Z.AI docs and Baidu's model card confirm no audio + video input,
    # so these models must never surface in any selector.
    assert {
        "baidu/ernie-4.5-vl-424b-a47b",
        "z-ai/glm-5v-turbo",
        "z-ai/glm-5.1",
        "z-ai/glm-5.2",
    } <= EXCLUDED
    # Sanity: the primer is non-empty so selectors aren't blank.
    assert TESTED
    assert {"google/gemini-3.5-flash-lite", "xiaomi/mimo-v2.5"} <= set(TESTED)
    assert {"minimax/minimax-m3", "qwen/qwen3.6-plus"} <= EXCLUDED


def test_polza_fetch_reads_nested_arch_modalities(monkeypatch) -> None:
    # Polza reports modalities under architecture.input_modalities (top-level
    # modality fields are None), so Gemini/etc. must still be discovered.
    import transcription_agent.model_registry as reg

    payload = {
        "data": [
            {
                "id": "google/gemini-3.7-flash",
                "modality": None,
                "input_modalities": None,
                "architecture": {
                    "input_modalities": ["text", "image", "video", "audio"]
                },
            },
            {
                "id": "anthropic/claude-sonnet",
                "modality": None,
                "input_modalities": None,
            },
        ]
    }
    monkeypatch.setattr(reg, "_fetch_json_httpx", lambda *a, **k: payload)
    models = reg._fetch_polza(timeout=1)
    assert "google/gemini-3.7-flash" in models
    assert "anthropic/claude-sonnet" not in models


def test_live_fetch_drops_video_only_and_unknown_metadata(monkeypatch) -> None:
    # Video-only models, metadata-less ids, and routing pseudomodels must not
    # enter the live roster even when they are not in the EXCLUDED set.
    import transcription_agent.model_registry as reg

    payload = {
        "data": [
            {
                "id": "qwen/qwen3.5-27b",
                "modality": None,
                "input_modalities": None,
                "architecture": {"input_modalities": ["text", "image", "video"]},
            },
            {
                "id": "google/gemini-3.7-flash",
                "modality": None,
                "input_modalities": None,
                "architecture": {
                    "input_modalities": ["text", "image", "video", "audio"]
                },
            },
            {"id": "topaz/video-upscale", "modality": None, "input_modalities": None},
            {
                "id": "openrouter/auto",
                "modality": None,
                "input_modalities": None,
                "architecture": {
                    "input_modalities": ["text", "image", "video", "audio"]
                },
            },
        ]
    }
    monkeypatch.setattr(reg, "_fetch_json_httpx", lambda *a, **k: payload)
    models = reg._fetch_polza(timeout=1)
    assert "google/gemini-3.7-flash" in models
    assert "qwen/qwen3.5-27b" not in models
    assert "topaz/video-upscale" not in models
    assert "openrouter/auto" not in models
    for mid in (
        "anthropic/claude-haiku-4.5",
        "anthropic/claude-sonnet-4.6",
        "meta/muse-spark-1.1",
        "openai/gpt-5.3-codex",
    ):
        assert _is_model_variant(mid), mid


def test_fetch_gemini_prefixes_bare_ids(monkeypatch) -> None:
    import transcription_agent.model_registry as reg

    payload = {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/google/gemini-3.5-flash-lite",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-2.5-flash-image",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }
    monkeypatch.setenv("GEMINI_KEY", "test")
    monkeypatch.setattr(reg, "_fetch_json", lambda *a, **k: payload)
    models = reg._fetch_gemini(timeout=1)
    assert "google/gemini-2.5-flash" in models
    assert "google/gemini-3.5-flash-lite" in models
    assert "gemini-2.5-flash" not in models

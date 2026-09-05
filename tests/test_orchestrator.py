"""Behavior tests for provider routing and upload/base64 fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

import transcription_agent.orchestrator as orch
from transcription_agent.config import Settings
from transcription_agent.costs import Usage
from transcription_agent.media import VisualCheckpoint
from transcription_agent.orchestrator import TranscriptionService, parse_segments
from transcription_agent.providers import ProviderResult
from transcription_agent.upload_adapters import MediaRef, UploadDeclined


class _RecordingAdapter:
    """Adapter that records calls and can decline or fail uploads."""

    def __init__(self, outcome: str = "ok"):
        self.outcome = outcome
        self.calls = 0

    @property
    def name(self) -> str:
        return "adapter"

    def upload(self, path, *, ttl: str = "temp") -> MediaRef:
        self.calls += 1
        if self.outcome == "decline":
            raise UploadDeclined("media type not supported")
        if self.outcome == "fail":
            raise RuntimeError("upstream exploded")
        return MediaRef("url", f"https://host/{Path(path).name}", "provider")

    def delete(self, ref: MediaRef) -> None:
        return None


class _RecordingProvider:
    """Provider that records whether it was called via URL or base64 path."""

    def __init__(self, name: str, *, fail: int = 0):
        self.name = name
        self.remaining_failures = fail
        self.url_calls = 0
        self.base64_calls = 0

    def transcribe_media(
        self,
        ref: MediaRef,
        prompt: str,
        media_path: str = "",
        visual_checkpoints=(),
    ) -> ProviderResult:
        self.url_calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise RuntimeError("provider failed")
        return ProviderResult("[00:00] Speaker 1: ok", Usage(10, 5))

    def transcribe(
        self, media_path: str, prompt: str, visual_checkpoints=()
    ) -> ProviderResult:
        self.base64_calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise RuntimeError("provider failed")
        return ProviderResult("[00:00] Speaker 1: ok", Usage(20, 5))


class _NormalizingProvider(_RecordingProvider):
    def __init__(self) -> None:
        super().__init__("polza")
        self.normalization_calls = 0
        self.normalization_visuals = ()

    def transcribe_media(
        self,
        ref: MediaRef,
        prompt: str,
        media_path: str = "",
        visual_checkpoints=(),
    ) -> ProviderResult:
        return ProviderResult(
            "[00:01] Variant: exact words\n[00:03] Canonical: more words",
            Usage(10, 5),
        )

    def normalize_speaker_labels(
        self, transcript_text, labels, visual_checkpoints=()
    ) -> ProviderResult:
        self.normalization_calls += 1
        self.normalization_visuals = visual_checkpoints
        return ProviderResult(
            '{"confidence": 0.95, "mapping": {"Variant": "Canonical"}}',
            Usage(2, 1),
        )


class _InvalidNormalizingProvider(_NormalizingProvider):
    def normalize_speaker_labels(
        self, transcript_text, labels, visual_checkpoints=()
    ) -> ProviderResult:
        return ProviderResult("not-json", Usage(3, 4))


def _settings(tmp_path: Path, order: tuple[str, ...]) -> Settings:
    return Settings(
        provider_order=order,
        model="google/gemini-2.5-flash",
        output_dir=tmp_path / "out",
        database_path=tmp_path / "jobs.sqlite3",
    )


def _patch(monkeypatch, adapters: dict, providers: dict) -> None:
    monkeypatch.setattr(
        orch, "build_upload_adapter", lambda provider, settings: adapters.get(provider)
    )
    monkeypatch.setattr(
        orch,
        "configured_providers",
        lambda model, order, proxies: providers,
    )


def test_upload_declined_falls_back_to_base64_without_error_note(
    tmp_path: Path, monkeypatch
) -> None:
    adapter = _RecordingAdapter("decline")
    provider = _RecordingProvider("openrouter")
    _patch(monkeypatch, {"openrouter": adapter}, {"openrouter": provider})
    service = TranscriptionService(_settings(tmp_path, ("openrouter",)))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    transcript = service.transcribe_clips(str(clip), [(0.0, str(clip))])

    assert provider.base64_calls == 1
    assert provider.url_calls == 0
    assert adapter.calls == 1
    assert transcript.provider == "openrouter"
    # A route decline is expected, not an error: no note noise.
    assert transcript.notes == ()


def test_provider_order_routes_to_working_provider(tmp_path: Path, monkeypatch) -> None:
    failing = _RecordingProvider("gemini", fail=1)
    working = _RecordingProvider("openrouter")
    _patch(
        monkeypatch,
        {"gemini": _RecordingAdapter("ok"), "openrouter": _RecordingAdapter("ok")},
        {"gemini": failing, "openrouter": working},
    )
    service = TranscriptionService(_settings(tmp_path, ("gemini", "openrouter")))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    transcript = service.transcribe_clips(str(clip), [(0.0, str(clip))])

    assert transcript.provider == "openrouter"
    assert failing.url_calls == 1  # first provider was attempted
    assert working.url_calls == 1
    assert any("gemini" in note for note in transcript.notes)


def test_all_providers_fail_raises(tmp_path: Path, monkeypatch) -> None:
    _patch(
        monkeypatch,
        {"gemini": _RecordingAdapter("fail")},
        {"gemini": _RecordingProvider("gemini", fail=5)},
    )
    service = TranscriptionService(_settings(tmp_path, ("gemini",)))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    with pytest.raises(RuntimeError, match="All providers failed"):
        service.transcribe_clips(str(clip), [(0.0, str(clip))])


class _HangingAdapter:
    """Adapter whose upload never returns within the test timeout."""

    name = "adapter"

    def upload(self, path, *, ttl: str = "temp") -> MediaRef:
        import time

        time.sleep(10)
        return MediaRef("url", "https://host/never", "provider")

    def delete(self, ref: MediaRef) -> None:
        return None


def test_hung_upload_times_out_and_falls_back_to_base64(
    tmp_path: Path, monkeypatch
) -> None:
    from dataclasses import replace

    adapter = _HangingAdapter()
    provider = _RecordingProvider("polza")
    _patch(monkeypatch, {"polza": adapter}, {"polza": provider})
    settings = replace(_settings(tmp_path, ("polza",)), upload_timeout_seconds=0.3)
    service = TranscriptionService(settings)
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    transcript = service.transcribe_clips(str(clip), [(0.0, str(clip))])

    assert provider.base64_calls == 1
    assert provider.url_calls == 0
    assert transcript.provider == "polza"
    assert any("upload timeout" in note for note in transcript.notes)


def test_visual_label_normalization_changes_only_speaker_labels(
    tmp_path: Path, monkeypatch
) -> None:
    provider = _NormalizingProvider()
    _patch(monkeypatch, {"polza": _RecordingAdapter("ok")}, {"polza": provider})
    frame = tmp_path / "checkpoint.png"
    frame.write_bytes(b"png")
    monkeypatch.setattr(
        orch,
        "extract_visual_checkpoints",
        lambda path, offset, output_dir: (
            VisualCheckpoint(1.0, offset + 1.0, frame, "periodic layout checkpoint"),
        ),
    )
    monkeypatch.setattr(
        orch,
        "extract_label_checkpoints",
        lambda source, label_times, output_dir: (
            VisualCheckpoint(61.0, 61.0, frame, "speaker-label occurrence: Variant"),
        ),
    )
    service = TranscriptionService(_settings(tmp_path, ("polza",)))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    transcript = service.transcribe_clips(str(clip), [(60.0, str(clip))])

    assert provider.normalization_calls == 1
    assert provider.normalization_visuals[0].reason.startswith(
        "speaker-label occurrence:"
    )
    assert [(s.start, s.speaker, s.text) for s in transcript.segments] == [
        (61.0, "Canonical", "exact words"),
        (63.0, "Canonical", "more words"),
    ]
    assert transcript.metadata["speaker_normalization"]["status"] == "applied"
    assert transcript.metadata["usage"]["output_tokens"] == 6


def test_failed_label_normalization_preserves_transcript_and_records_usage(
    tmp_path: Path, monkeypatch
) -> None:
    provider = _InvalidNormalizingProvider()
    _patch(monkeypatch, {"polza": _RecordingAdapter("ok")}, {"polza": provider})
    frame = tmp_path / "checkpoint.png"
    frame.write_bytes(b"png")
    monkeypatch.setattr(
        orch,
        "extract_visual_checkpoints",
        lambda path, offset, output_dir: (
            VisualCheckpoint(1.0, offset + 1.0, frame, "periodic layout checkpoint"),
        ),
    )
    service = TranscriptionService(_settings(tmp_path, ("polza",)))
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    transcript = service.transcribe_clips(str(clip), [(60.0, str(clip))])

    assert [(s.start, s.speaker, s.text) for s in transcript.segments] == [
        (61.0, "Variant", "exact words"),
        (63.0, "Canonical", "more words"),
    ]
    assert transcript.metadata["speaker_normalization"]["status"] == "failed"
    assert transcript.metadata["usage"]["output_tokens"] == 9
    assert any("speaker-label normalization" in note for note in transcript.notes)


def test_parse_segments_splits_collapsed_timestamped_line_without_loss() -> None:
    text = (
        "[00:10] **Alice**: first words. [00:33] Bob: second words. "
        "[00:37] **Alice**: final words."
    )

    segments = parse_segments(text)

    assert [(s.start, s.speaker, s.text) for s in segments] == [
        (10, "Alice", "first words."),
        (33, "Bob", "second words."),
        (37, "Alice", "final words."),
    ]


def test_parallel_chunks_merge_in_source_order(tmp_path: Path, monkeypatch) -> None:
    import time
    from dataclasses import replace

    class DelayedProvider(_RecordingProvider):
        def transcribe(self, media_path: str, prompt: str, visual_checkpoints=()):
            if Path(media_path).name == "first.mp4":
                time.sleep(0.05)
            return ProviderResult(
                "[00:00] Speaker 1: " + Path(media_path).stem,
                Usage(1, 1),
            )

    provider = DelayedProvider("polza")
    _patch(monkeypatch, {"polza": _RecordingAdapter("decline")}, {"polza": provider})
    monkeypatch.setattr(orch, "extract_visual_checkpoints", lambda *args: ())
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    settings = replace(
        _settings(tmp_path, ("polza",)),
        chunk_launch_interval_seconds=0,
        speaker_normalization_enabled=False,
    )

    transcript = TranscriptionService(settings).transcribe_clips(
        str(first), [(0.0, str(first)), (300.0, str(second))]
    )

    assert [segment.text for segment in transcript.segments] == ["first", "second"]

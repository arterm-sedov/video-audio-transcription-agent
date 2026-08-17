"""Behavior tests for provider routing and upload/base64 fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

import transcription_agent.orchestrator as orch
from transcription_agent.config import Settings
from transcription_agent.costs import Usage
from transcription_agent.orchestrator import TranscriptionService
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

    def transcribe_media(self, ref: MediaRef, prompt: str, media_path: str = "") -> ProviderResult:
        self.url_calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise RuntimeError("provider failed")
        return ProviderResult("[00:00] Speaker 1: ok", Usage(10, 5))

    def transcribe(self, media_path: str, prompt: str) -> ProviderResult:
        self.base64_calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise RuntimeError("provider failed")
        return ProviderResult("[00:00] Speaker 1: ok", Usage(20, 5))


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

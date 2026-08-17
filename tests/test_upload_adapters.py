"""Unit tests for upload adapters (URL/file reference transport)."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcription_agent.upload_adapters import (
    GeminiUploadAdapter,
    MediaRef,
    OpenRouterUploadAdapter,
    PolzaUploadAdapter,
    UploadDeclined,
    UrlPassThroughAdapter,
    build_upload_adapter,
)


class _FakeResponse:
    def __init__(self, payload: dict, ok: bool = True):
        self._payload = payload
        self.ok = ok

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError("status")

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal httpx.Client stand-in that records calls."""

    def __init__(self, post_payload=None, delete_ok=True):
        self._post_payload = post_payload or {"url": "https://s3.polza.ai/f/x.mp4"}
        self.delete_ok = delete_ok
        self.post_calls = []
        self.delete_calls = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _FakeResponse(self._post_payload)

    def delete(self, url, **kwargs):
        self.delete_calls.append((url, kwargs))
        if not self.delete_ok:
            raise RuntimeError("delete failed")
        return _FakeResponse({})


def _patch_client(monkeypatch, fake: _FakeClient):
    import transcription_agent.upload_adapters as ua

    monkeypatch.setattr(ua, "_http_client", lambda proxy: fake)


def test_media_ref_as_url_accepts_url_and_file_id(tmp_path: Path) -> None:
    assert MediaRef("url", "https://x/y.mp4").as_url() == "https://x/y.mp4"
    assert MediaRef("file_id", "abc123").as_url() == "abc123"


def test_media_ref_as_url_rejects_non_url() -> None:
    with pytest.raises(ValueError):
        MediaRef("base64", "Zm9v").as_url()
    with pytest.raises(ValueError):
        MediaRef("data_url", "data:video/mp4;base64,...").as_url()


def test_build_upload_adapter_returns_correct_class() -> None:
    class _Settings:
        def provider_proxy(self, provider: str) -> str:
            return ""

    settings = _Settings()
    # The factory must return an adapter exposing the upload/delete contract for
    # every wired provider, each identified by its stable `name` (part of the
    # public contract). We assert the contract + identity, not the concrete class.
    # Each wired provider resolves to an adapter exposing the contract and
    # carrying its provider identity (used by the orchestrator for routing).
    for provider in ("polza", "openrouter", "gemini", "url"):
        adapter = build_upload_adapter(provider, settings)
        assert hasattr(adapter, "upload")
        assert hasattr(adapter, "delete")
        assert adapter.name == provider


def test_build_upload_adapter_unknown_provider_raises() -> None:
    class _Settings:
        def provider_proxy(self, provider: str) -> str:
            return ""

    with pytest.raises(ValueError):
        build_upload_adapter("unknown", _Settings())


def test_url_pass_through_returns_url_ref() -> None:
    adapter = UrlPassThroughAdapter()
    ref = adapter.upload("https://host/remote.mp4")
    assert ref.kind == "url"
    assert ref.value == "https://host/remote.mp4"
    # delete is a no-op for pass-through
    assert adapter.delete(ref) is None


def test_polza_upload_returns_url_ref_and_deletes_best_effort(
    tmp_path: Path, monkeypatch
) -> None:
    fake = _FakeClient(post_payload={"url": "https://s3.polza.ai/f/abc.mp4"})
    _patch_client(monkeypatch, fake)
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake-bytes")

    adapter = PolzaUploadAdapter("https://polza.ai/api/v1", "key", "")
    ref = adapter.upload(media)
    # Contract: a successful upload yields a URL-kind MediaRef the caller can embed.
    assert ref.kind == "url"
    assert ref.value.startswith("https://")
    # The client must have been used and closed (resource hygiene).
    assert fake.post_calls
    assert fake.closed is True

    # delete best-effort must not raise even when the route 404s
    adapter.delete(ref)


def test_polza_upload_raises_when_no_url_returned(
    tmp_path: Path, monkeypatch
) -> None:
    fake = _FakeClient(post_payload={"unexpected": "shape"})
    _patch_client(monkeypatch, fake)
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake-bytes")
    adapter = PolzaUploadAdapter("https://polza.ai/api/v1", "key", "")
    with pytest.raises(RuntimeError):
        adapter.upload(media)


def test_polza_upload_sends_real_mime_type(tmp_path: Path, monkeypatch) -> None:
    # Polza enforces a media whitelist and rejects octet-stream; the multipart
    # must carry the file's real content type.
    fake = _FakeClient(post_payload={"url": "https://s3.polza.ai/f/abc.mp4"})
    _patch_client(monkeypatch, fake)
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake-bytes")

    adapter = PolzaUploadAdapter("https://polza.ai/api/v1", "key", "")
    adapter.upload(media)

    _, kwargs = fake.post_calls[-1]
    file_tuple = kwargs["files"]["file"]
    assert file_tuple[2] == "video/mp4"


def test_openrouter_upload_returns_url_ref_and_deletes_best_effort(
    tmp_path: Path, monkeypatch
) -> None:
    # Audio/image/text upload through /files; video is declined by file type
    # (OpenRouter rejects video uploads server-side), so the orchestrator can
    # fall back to inline base64 without a doomed POST.
    # Video must be declined before any HTTP call.
    fake = _FakeClient(post_payload={"data": {"id": "fid", "url": "https://or/files/fid"}})
    _patch_client(monkeypatch, fake)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-bytes")
    adapter = OpenRouterUploadAdapter("https://openrouter.ai/api/v1", "key", "")
    with pytest.raises(UploadDeclined):
        adapter.upload(video)
    # No POST should have been attempted for a declined video file.
    assert fake.post_calls == []

    # Non-video files still upload via /files and yield a URL-kind MediaRef.
    audio = tmp_path / "clip.mp3"
    audio.write_bytes(b"fake-bytes")
    ref = adapter.upload(audio)
    assert ref.kind == "url"
    assert ref.value.startswith("https://")
    assert fake.post_calls
    assert fake.closed is True
    # delete is best-effort and returns nothing (no value contract)
    assert adapter.delete(ref) is None


def test_openrouter_upload_video_declined_by_type(tmp_path: Path, monkeypatch) -> None:
    # Every known video container suffix must be declined up front.
    _patch_client(monkeypatch, _FakeClient())
    adapter = OpenRouterUploadAdapter("https://openrouter.ai/api/v1", "key", "")
    for suffix in (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".flv", ".wmv"):
        clip = tmp_path / f"clip{suffix}"
        clip.write_bytes(b"fake-bytes")
        with pytest.raises(UploadDeclined):
            adapter.upload(clip)


def test_openrouter_upload_audio_uses_files_endpoint(
    tmp_path: Path, monkeypatch
) -> None:
    # Audio references should be carried by URL /file-id, not inlined base64.
    fake = _FakeClient(post_payload={"data": {"id": "fid", "url": "https://or/files/fid"}})
    _patch_client(monkeypatch, fake)
    audio = tmp_path / "voice.m4a"
    audio.write_bytes(b"fake-bytes")
    adapter = OpenRouterUploadAdapter("https://openrouter.ai/api/v1", "key", "")
    ref = adapter.upload(audio)
    assert ref.kind == "url"
    assert "/files/" in ref.value
    adapter.delete(ref)


def test_gemini_upload_polls_active(monkeypatch) -> None:
    class _State:
        def __init__(self, name):
            self.name = name

    class _File:
        name = "files/abc"
        state = _State("ACTIVE")
        uri = "https://generativelanguage.googleapis.com/v1/files/abc"

    class _Files:
        def upload(self, file):
            return _File()

        def get(self, name):
            return _File()

    class _Client:
        def __init__(self, api_key=None, http_options=None):
            self.files = _Files()

    class _Genai:
        Client = _Client

    import transcription_agent.upload_adapters as ua

    monkeypatch.setattr(ua, "_http_client", lambda proxy: _FakeClient())
    monkeypatch.setitem(__import__("sys").modules, "google.genai", _Genai)

    adapter = GeminiUploadAdapter("key", "")
    ref = adapter.upload("ignored.mp4")
    assert ref.kind == "url"
    assert ref.value.endswith("/abc")


def test_gemini_adapter_delete_best_effort(monkeypatch) -> None:
    class _Files:
        def delete(self, name):
            return None

    class _Client:
        def __init__(self, api_key=None):
            self.files = _Files()

    class _Genai:
        Client = _Client

    import sys

    import transcription_agent.upload_adapters as ua

    monkeypatch.setattr(ua, "_http_client", lambda proxy: _FakeClient())
    monkeypatch.setitem(sys.modules, "google.genai", _Genai)
    adapter = GeminiUploadAdapter("key", "")
    # should not raise
    adapter.delete(MediaRef("url", "https://x/files/abc"))

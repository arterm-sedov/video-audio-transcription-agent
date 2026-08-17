"""Provider upload adapters: host media once, reference it by URL/file-id.

Each adapter turns a local media path into a provider-accepted ``MediaRef`` so
transcription calls reference hosted bytes instead of re-inlining base64 every
request. This removes the base64 payload ceiling that previously forced small
chunks and lets us size chunks from the model's real context window.

Key features:
- ``MediaRef`` is a small value object describing how a provider should reference
  the uploaded media (``url`` / ``file_id`` / ``data_url`` / ``base64``).
- Each provider implements ``upload`` / ``delete``; failures raise so the
  orchestrator can fall back to inline base64 (non-breaking).
- A ``build_upload_adapter`` factory returns the right adapter for a provider.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol, runtime_checkable

from .config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MediaRef:
    """Provider-accepted reference to uploaded/referenced media."""

    kind: str  # "url" | "file_id" | "data_url" | "base64"
    value: str
    provider: str = ""
    expires_at: float | None = None

    def as_url(self) -> str:
        """Return the URL the provider should embed, or raise if not a URL ref."""
        if self.kind in {"url", "file_id"}:
            return self.value
        raise ValueError(f"MediaRef kind {self.kind!r} is not a URL reference")


@runtime_checkable
class UploadAdapter(Protocol):
    """Minimal contract every provider upload adapter satisfies."""

    name: str

    def upload(self, path: str | Path, *, ttl: str = "temp") -> MediaRef: ...

    def delete(self, ref: MediaRef) -> None: ...


class UploadDeclined(Exception):
    """Adapter does not support this media type; caller should use base64."""


def _media_type(path: str | Path) -> str:
    """Best-effort MIME type for a media file (Polza requires a real type)."""
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _http_client(proxy: str):
    import httpx

    if not proxy:
        return httpx.Client(timeout=httpx.Timeout(120.0))
    return httpx.Client(
        transport=httpx.HTTPTransport(proxy=proxy),
        timeout=httpx.Timeout(120.0),
    )


class PolzaUploadAdapter:
    """Polza storage upload (``POST /storage/upload``) -> hosted URL."""

    name = "polza"

    def __init__(self, base_url: str, api_key: str, proxy: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.proxy = proxy

    def upload(self, path: str | Path, *, ttl: str = "temp") -> MediaRef:
        policy = "PERMANENT" if ttl == "permanent" else "TEMP_UPLOAD"
        with _http_client(self.proxy) as client:
            with open(path, "rb") as handle:
                response = client.post(
                    f"{self.base_url}/storage/upload",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={
                        "file": (
                            Path(path).name,
                            handle,
                            _media_type(path),
                        )
                    },
                    data={"policy": policy},
                )
            response.raise_for_status()
            payload = response.json()
            url = payload.get("url") or payload.get("data", {}).get("url")
            if not url:
                raise RuntimeError(f"Polza upload returned no url: {payload}")
            return MediaRef("url", url, self.name)

    def delete(self, ref: MediaRef) -> None:  # pragma: no cover - best effort
        # Live probing shows Polza's assumed delete routes (POST /storage/delete,
        # DELETE /storage/{id}) currently 404; TEMP_UPLOAD auto-expires in 24h, so
        # cleanup is best-effort and TTL will reclaim the bytes.
        try:
            with _http_client(self.proxy) as client:
                client.delete(
                    f"{self.base_url}/storage/delete",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"url": ref.value},
                )
        except Exception as exc:  # noqa: BLE001 - cleanup is best-effort; TTL reclaims
            logger.debug("polza upload cleanup failed: %s", exc)


class OpenRouterUploadAdapter:
    """OpenRouter file storage (``POST /files``) -> hosted file reference."""

    name = "openrouter"
    # OpenRouter's /files endpoint accepts audio/image/text but rejects video
    # uploads server-side (HTTP 400, content-sniffed) — video is still sent
    # inline as a base64 data-URL via the chat endpoint. Decline video by type
    # so the orchestrator falls back to inline base64 instead of a doomed POST.
    _VIDEO_SUFFIXES: ClassVar[set[str]] = {
        ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"
    }

    def __init__(self, base_url: str, api_key: str, proxy: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.proxy = proxy

    def upload(self, path: str | Path, *, ttl: str = "temp") -> MediaRef:
        if Path(path).suffix.lower() in self._VIDEO_SUFFIXES:
            raise UploadDeclined(
                "OpenRouter /files rejects video uploads; send video inline "
                "(base64 data-URL) instead of via the upload adapter."
            )
        with _http_client(self.proxy) as client:
            with open(path, "rb") as handle:
                response = client.post(
                    f"{self.base_url}/files",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={
                        "file": (
                            Path(path).name,
                            handle,
                            _media_type(path),
                        )
                    },
                )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload)
            file_id = data.get("id")
            url = data.get("url") or (
                f"{self.base_url}/files/{file_id}" if file_id else None
            )
            if not url:
                raise RuntimeError(f"OpenRouter upload returned no url: {payload}")
            return MediaRef("url", url, self.name)

    def delete(self, ref: MediaRef) -> None:  # pragma: no cover - best effort
        try:
            with _http_client(self.proxy) as client:
                file_id = ref.value.rsplit("/", 1)[-1]
                client.delete(
                    f"{self.base_url}/files/{file_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
            logger.debug("openrouter upload cleanup failed: %s", exc)


class GeminiUploadAdapter:
    """Direct Gemini Files API upload (poll until ACTIVE)."""

    name = "gemini"

    def __init__(self, api_key: str, proxy: str = ""):
        self.api_key = api_key
        self.proxy = proxy

    def upload(self, path: str | Path, *, ttl: str = "temp") -> MediaRef:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for Gemini uploads"
            ) from exc
        transport = _http_client(self.proxy)._transport if self.proxy else None
        client = genai.Client(
            api_key=self.api_key,
            http_options={
                "timeout": 300000,
                **({"httpx_client": transport} if transport else {}),
            },
        )
        uploaded = client.files.upload(file=str(path))
        for _ in range(40):
            state = client.files.get(name=uploaded.name)
            state_name = getattr(getattr(state, "state", None), "name", "")
            if state_name == "ACTIVE":
                return MediaRef("url", state.uri, self.name)
            if state_name == "FAILED":
                raise RuntimeError("Gemini file processing failed")
            time.sleep(2)
        raise TimeoutError("Gemini file did not become ACTIVE")

    def delete(self, ref: MediaRef) -> None:  # pragma: no cover - best effort
        try:
            from google import genai

            client = genai.Client(api_key=self.api_key)
            name = ref.value.rsplit("/", 1)[-1]
            client.files.delete(name=name)
        except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
            logger.debug("gemini upload cleanup failed: %s", exc)


class UrlPassThroughAdapter:
    """Adapter for already-hosted media (remote sources)."""

    name = "url"

    def upload(self, path: str | Path, *, ttl: str = "temp") -> MediaRef:
        return MediaRef("url", str(path), self.name)

    def delete(self, ref: MediaRef) -> None:  # pragma: no cover
        return None


def build_upload_adapter(provider: str, settings: Settings) -> UploadAdapter:
    """Return the upload adapter for a provider, configured from settings."""
    key = provider.strip().lower()
    proxy = settings.provider_proxy(provider)
    if key == "polza":
        return PolzaUploadAdapter(
            os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1"),
            os.getenv("POLZA_API_KEY", ""),
            proxy,
        )
    if key == "openrouter":
        return OpenRouterUploadAdapter(
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            os.getenv("OPENROUTER_API_KEY", ""),
            proxy,
        )
    if key == "gemini":
        return GeminiUploadAdapter(
            os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY", ""),
            proxy,
        )
    if key == "url":
        return UrlPassThroughAdapter()
    raise ValueError(f"No upload adapter for provider {provider!r}")

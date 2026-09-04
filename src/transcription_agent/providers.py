"""Provider adapters for multimodal transcription."""

import base64
import logging
import mimetypes
import os
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .costs import Usage, normalize_usage
from .media import VisualCheckpoint
from .upload_adapters import MediaRef

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (
    Path(__file__).with_name("prompt-transcription.md").read_text(encoding="utf-8")
)


def _checkpoint_metadata(checkpoint: VisualCheckpoint) -> str:
    return (
        "original-video time "
        f"{checkpoint.original_seconds:.3f}s; "
        f"clip-relative {checkpoint.relative_seconds:.3f}s; "
        f"reason: {checkpoint.reason}"
    )


def _label_normalization_prompt(transcript_text: str, labels: tuple[str, ...]) -> str:
    observed = "\n".join(f"- {label}" for label in labels)
    return (
        f"{PROMPT_TEMPLATE.format(start='relative', end='relative')}\n\n"
        "LABEL_ONLY_NORMALIZATION mode: do not transcribe, summarize, or rewrite "
        "the transcript. Inspect the supplied visual checkpoints and map only "
        "clearly evidenced observed labels to one canonical observed label. "
        "Return exactly one JSON object of the form "
        '{"confidence": 0.0, "mapping": {"variant": "canonical"}}. '
        "Include only mappings supported by clear evidence and omit uncertain "
        "labels; confidence rates only the mappings you returned, not labels you "
        "omitted. Keys and values must be copied exactly from the observed-label "
        "list; do not invent names. This is an "
        "override of the transcript-output rules above: write no Markdown fence, "
        "explanation, or transcript; the first response character must be '{' and "
        "the last must be '}'.\n\n"
        f"Observed labels:\n{observed}\n\n"
        f"Transcript label occurrences (timestamps and labels only):\n{transcript_text}"
    )


class Provider(Protocol):
    name: str

    def transcribe(
        self,
        media_path: str,
        prompt: str,
        *,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> "ProviderResult": ...

    def normalize_speaker_labels(
        self,
        transcript_text: str,
        labels: tuple[str, ...],
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> "ProviderResult": ...


@dataclass(frozen=True, slots=True)
class ProviderResult:
    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass(slots=True)
class OpenAICompatibleProvider:
    """Polza/OpenRouter adapter using the OpenAI-compatible chat contract."""

    name: str
    base_url: str
    api_key_env: str
    model: str
    timeout_seconds: float = 120.0
    retries: int = 2
    retry_delay_seconds: float = 3.0
    proxy: str = ""

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for OpenAI-compatible calls"
            ) from exc
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {self.api_key_env}")
        return OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            http_client=_http_client(self.proxy),
        )

    @staticmethod
    def _visual_content(
        visual_checkpoints: tuple[VisualCheckpoint, ...],
    ) -> list[dict]:
        if not visual_checkpoints:
            return []
        content: list[dict] = [
            {
                "type": "text",
                "text": "Supplementary visual checkpoints (video/audio remains authoritative):",
            }
        ]
        for checkpoint in visual_checkpoints:
            mime = mimetypes.guess_type(checkpoint.path.name)[0] or "image/png"
            encoded = base64.b64encode(checkpoint.path.read_bytes()).decode("ascii")
            content.append({"type": "text", "text": _checkpoint_metadata(checkpoint)})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                }
            )
        return content

    @classmethod
    def _content_from_ref(
        cls,
        ref: MediaRef,
        prompt: str,
        media_path: str,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> list[dict]:
        visual_content = cls._visual_content(visual_checkpoints)

        def with_visuals(content: list[dict]) -> list[dict]:
            return [*content, *visual_content]

        if ref.kind == "url":
            if ref.value.startswith("data:"):
                # data-URL reference: treat as video data url
                return with_visuals(
                    [
                        {"type": "text", "text": prompt},
                        {"type": "video_url", "video_url": {"url": ref.value}},
                    ]
                )
            # hosted url; audio supports input_audio url, video uses video_url url
            suffix = Path(media_path).suffix.lower()
            if suffix in {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"}:
                return with_visuals(
                    [
                        {"type": "text", "text": prompt},
                        {"type": "input_audio", "input_audio": {"url": ref.value}},
                    ]
                )
            return with_visuals(
                [
                    {"type": "text", "text": prompt},
                    {"type": "video_url", "video_url": {"url": ref.value}},
                ]
            )
        # fallback to inline base64 (data_url / base64 / path)
        mime = mimetypes.guess_type(media_path)[0] or "video/mp4"
        with open(media_path, "rb") as source:
            encoded = base64.b64encode(source.read()).decode()
        data_url = f"data:{mime};base64,{encoded}"
        if mime.startswith("audio/"):
            audio_format = Path(media_path).suffix.lstrip(".") or "m4a"
            return with_visuals(
                [
                    {"type": "text", "text": prompt},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": encoded, "format": audio_format},
                    },
                ]
            )
        return with_visuals(
            [
                {"type": "text", "text": prompt},
                {"type": "video_url", "video_url": {"url": data_url}},
            ]
        )

    def _complete(self, content: list[dict]) -> ProviderResult:
        client = self._client()
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": content}],
                )
                break
            except Exception as exc:  # noqa: BLE001 - provider retry boundary
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay_seconds * (attempt + 1))
        if last_error is not None:
            raise last_error
        usage = getattr(response, "usage", None)
        usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else usage
        return ProviderResult(
            response.choices[0].message.content or "",
            normalize_usage(self.name, usage_dict),
        )

    def transcribe_media(
        self,
        ref: MediaRef,
        prompt: str,
        media_path: str = "",
        *,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Transcribe a MediaRef (url/file_id) or fall back to inline base64."""
        content = self._content_from_ref(ref, prompt, media_path, visual_checkpoints)
        return self._complete(content)

    def normalize_speaker_labels(
        self,
        transcript_text: str,
        labels: tuple[str, ...],
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Return a JSON-only label mapping; never regenerate transcript text."""
        content = [
            {
                "type": "text",
                "text": _label_normalization_prompt(transcript_text, labels),
            },
            *self._visual_content(visual_checkpoints),
        ]
        return self._complete(content)

    def transcribe(
        self,
        media_path: str,
        prompt: str,
        *,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Transcribe media inlined as base64 (upload-unavailable fallback)."""
        return self.transcribe_media(
            MediaRef("base64", "", self.name),
            prompt,
            media_path,
            visual_checkpoints=visual_checkpoints,
        )


@dataclass(slots=True)
class GeminiProvider:
    """Direct Gemini adapter with upload readiness polling."""

    name: str = "gemini"
    model: str = "gemini-2.5-flash"
    poll_seconds: float = 2.0
    poll_attempts: int = 40
    timeout_seconds: float = 300.0
    proxy: str = ""

    def _client(self):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for direct Gemini calls"
            ) from exc
        api_key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_KEY or GEMINI_API_KEY")
        return genai.Client(
            api_key=api_key,
            http_options={
                "timeout": self.timeout_seconds * 1000,
                "httpx_client": _http_client(self.proxy),
            },
        )

    def _generate_parts(self, client, parts) -> ProviderResult:
        """Generate from already assembled multimodal parts and normalize usage."""
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for direct Gemini calls"
            ) from exc
        response = client.models.generate_content(
            model=self.model,
            contents=types.Content(parts=parts),
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=int(
                    os.getenv("TRANSCRIPTION_MAX_OUTPUT_TOKENS", "8192")
                ),
            ),
        )
        usage = getattr(response, "usage_metadata", None)
        usage_dict = usage if isinstance(usage, dict) else None
        return ProviderResult(
            response.text or "", normalize_usage(self.name, usage_dict)
        )

    def _generate(
        self,
        client,
        file_uri: str,
        prompt: str,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Generate content for a hosted file URI and normalize usage."""
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for direct Gemini calls"
            ) from exc
        parts = [
            types.Part(file_data=types.FileData(file_uri=file_uri)),
            types.Part(text=prompt),
        ]
        if visual_checkpoints:
            parts.append(
                types.Part(
                    text="Supplementary visual checkpoints (video/audio remains authoritative):"
                )
            )
            for checkpoint in visual_checkpoints:
                parts.append(types.Part(text=_checkpoint_metadata(checkpoint)))
                parts.append(
                    types.Part.from_bytes(
                        data=checkpoint.path.read_bytes(), mime_type="image/png"
                    )
                )
        return self._generate_parts(client, parts)

    def transcribe_media(
        self,
        ref: MediaRef,
        prompt: str,
        media_path: str = "",
        *,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Transcribe a hosted MediaRef (url/file_id) via Gemini Files API."""
        client = self._client()
        return self._generate(client, ref.as_url(), prompt, visual_checkpoints)

    def normalize_speaker_labels(
        self,
        transcript_text: str,
        labels: tuple[str, ...],
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Return a JSON-only label mapping; never regenerate transcript text."""
        try:
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for direct Gemini calls"
            ) from exc
        parts = [
            types.Part(text=_label_normalization_prompt(transcript_text, labels)),
        ]
        if visual_checkpoints:
            parts.append(
                types.Part(
                    text="Supplementary visual checkpoints (video/audio remains authoritative):"
                )
            )
            for checkpoint in visual_checkpoints:
                parts.append(types.Part(text=_checkpoint_metadata(checkpoint)))
                parts.append(
                    types.Part.from_bytes(
                        data=checkpoint.path.read_bytes(), mime_type="image/png"
                    )
                )
        return self._generate_parts(self._client(), parts)

    def transcribe(
        self,
        media_path: str,
        prompt: str,
        *,
        visual_checkpoints: tuple[VisualCheckpoint, ...] = (),
    ) -> ProviderResult:
        """Upload media inline, wait for ACTIVE, then generate (no adapter)."""
        client = self._client()
        uploaded = client.files.upload(file=media_path)
        active = None
        try:
            for _ in range(self.poll_attempts):
                state = client.files.get(name=uploaded.name)
                state_name = getattr(getattr(state, "state", None), "name", "")
                if state_name == "ACTIVE":
                    active = state
                    break
                if state_name == "FAILED":
                    raise RuntimeError(f"Gemini file processing failed: {state}")
                time.sleep(self.poll_seconds)
            if active is None:
                raise TimeoutError("Gemini file did not become ACTIVE")
            return self._generate(client, active.uri, prompt, visual_checkpoints)
        finally:
            with suppress(Exception):
                client.files.delete(name=uploaded.name)


def _http_client(proxy: str):
    """Build an httpx client routed through an optional proxy."""
    import httpx

    if not proxy:
        return None
    return httpx.Client(
        transport=httpx.HTTPTransport(proxy=proxy),
        timeout=httpx.Timeout(300.0),
    )


def configured_providers(
    model: str, order: tuple[str, ...], proxy: str | dict[str, str] = ""
) -> dict[str, Provider]:
    """Build configured provider instances without requiring optional imports."""
    if isinstance(proxy, str):
        proxy_map = {"polza": proxy, "openrouter": proxy, "gemini": proxy}
    else:
        proxy_map = proxy
    return {
        "polza": OpenAICompatibleProvider(
            "polza",
            os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1"),
            "POLZA_API_KEY",
            model,
            proxy=proxy_map.get("polza", ""),
        ),
        "openrouter": OpenAICompatibleProvider(
            "openrouter",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "OPENROUTER_API_KEY",
            model,
            proxy=proxy_map.get("openrouter", ""),
        ),
        "gemini": GeminiProvider(
            model=model.removeprefix("google/"), proxy=proxy_map.get("gemini", "")
        ),
    }

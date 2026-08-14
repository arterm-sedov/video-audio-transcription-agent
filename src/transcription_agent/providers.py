"""Provider adapters for multimodal transcription."""

import base64
import mimetypes
import os
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Protocol

from .costs import Usage, normalize_usage

PROMPT_TEMPLATE = """Transcribe all spoken dialogue in this video clip. The clip covers original-video time {start} through {end}. Return only a chronological transcript, one line per speaker turn, in this format: [MM:SS] Speaker: words. Timestamps must be relative to this clip; do not use hours. Keep speaker labels consistent by using any visible active-speaker indicator—green frame, highlighted frame, colored outline, focus box, or equivalent. Use actual participant names when displayed; otherwise use neutral Speaker 1, Speaker 2 labels. Use voice characteristics as a secondary cue. If visual and audio evidence are ambiguous, use an uncertain SpeakerN label rather than guessing. Do not summarize, skip, or paraphrase. Use [inaudible] only when necessary. Begin with a short speaker key only if useful."""


class Provider(Protocol):
    name: str

    def transcribe(self, media_path: str, prompt: str) -> "ProviderResult": ...


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

    def transcribe(self, media_path: str, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for OpenAI-compatible calls"
            ) from exc
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing {self.api_key_env}")
        with open(media_path, "rb") as source:
            raw = source.read()

        mime = mimetypes.guess_type(media_path)[0] or "video/mp4"
        data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        client = OpenAI(api_key=api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "video_url", "video_url": {"url": data_url}},
                    ],
                }
            ],
        )
        usage = getattr(response, "usage", None)
        usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else usage
        return ProviderResult(
            response.choices[0].message.content or "",
            normalize_usage(self.name, usage_dict),
        )


@dataclass(slots=True)
class GeminiProvider:
    """Direct Gemini adapter with upload readiness polling."""

    name: str = "gemini"
    model: str = "gemini-2.5-flash"
    poll_seconds: float = 2.0
    poll_attempts: int = 40

    def transcribe(self, media_path: str, prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the providers extra for direct Gemini calls"
            ) from exc
        api_key = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_KEY or GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
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
            response = client.models.generate_content(
                model=self.model,
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=active.uri)),
                        types.Part(text=prompt),
                    ]
                ),
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
        finally:
            with suppress(Exception):
                client.files.delete(name=uploaded.name)


def configured_providers(model: str, order: tuple[str, ...]) -> dict[str, Provider]:
    """Build configured provider instances without requiring optional imports."""
    return {
        "polza": OpenAICompatibleProvider(
            "polza",
            os.getenv("POLZA_BASE_URL", "https://polza.ai/api/v1"),
            "POLZA_API_KEY",
            model,
        ),
        "openrouter": OpenAICompatibleProvider(
            "openrouter",
            os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "OPENROUTER_API_KEY",
            model,
        ),
        "gemini": GeminiProvider(model=model.removeprefix("google/")),
    }

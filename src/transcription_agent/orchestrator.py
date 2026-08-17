"""Chunked transcription orchestration."""

import logging
import re
from pathlib import Path

from .config import Settings
from .merge import merge_segments
from .models import Segment, Transcript
from .progress import ProgressCallback, ProgressEvent, emit
from .providers import PROMPT_TEMPLATE, configured_providers
from .timestamps import parse_model_timestamp
from .upload_adapters import MediaRef, UploadDeclined, build_upload_adapter

_LINE = re.compile(r"^\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.*)$")

logger = logging.getLogger(__name__)


def parse_segments(text: str) -> list[Segment]:
    """Parse the stable line format emitted by the transcription prompt."""
    segments = []
    for line in text.splitlines():
        match = _LINE.match(line)
        if match:
            stamp, speaker, words = match.groups()
            segments.append(
                Segment(parse_model_timestamp(stamp), 0, speaker.strip(), words.strip())
            )
    return [
        segment.with_end(following.start if following else segment.start)
        for segment, following in zip(segments, [*segments[1:], None])
    ]


class TranscriptionService:
    """Transcribe prepared clip paths with configurable provider fallback."""

    def __init__(self, settings: Settings):
        settings.validate()
        self.settings = settings
        proxies = {
            provider: settings.provider_proxy(provider)
            for provider in settings.provider_order
        }
        self.providers = configured_providers(
            settings.model, settings.provider_order, proxies
        )
        self.settings = settings
        self._adapters = {
            provider: build_upload_adapter(provider, settings)
            for provider in settings.provider_order
        }

    def transcribe_clips(
        self,
        source: str,
        clips: list[tuple[float, str]],
        *,
        duration: float | None = None,
        progress: ProgressCallback | None = None,
        prompt: str | None = None,
    ) -> Transcript:
        chunks: list[tuple[float, list[Segment]]] = []
        errors: list[str] = []
        selected_provider = None
        total = len(clips)
        emit(
            progress, ProgressEvent("transcribing", "Starting transcription", 0, total)
        )
        total_usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        for index, (offset, path) in enumerate(clips, 1):
            active_prompt = (prompt or PROMPT_TEMPLATE).format(
                start="relative", end="relative"
            )
            result = None
            uploaded: MediaRef | None = None
            for provider_name in self.settings.provider_order:
                adapter = self._adapters.get(provider_name)
                provider = self.providers[provider_name]
                try:
                    # Upload once; fall back to inline base64 if upload fails.
                    if adapter is not None:
                        try:
                            uploaded = adapter.upload(path)
                        except UploadDeclined:
                            # Expected routing decision: this provider+file type
                            # is not uploadable; fall back to inline base64
                            # without error noise.
                            uploaded = None
                        except Exception as up_exc:  # noqa: BLE001 - fallback boundary
                            errors.append(
                                f"{provider_name} upload({Path(path).name}): {up_exc}"
                            )
                            uploaded = None
                    if uploaded is not None and hasattr(
                        provider, "transcribe_media"
                    ):
                        result = provider.transcribe_media(uploaded, active_prompt, path)
                    else:
                        result = provider.transcribe(path, active_prompt)
                    selected_provider = provider_name
                    break
                except Exception as exc:  # noqa: BLE001 - provider fallback boundary
                    errors.append(f"{provider_name} ({Path(path).name}): {exc}")
                finally:
                    if uploaded is not None and adapter is not None:
                        try:
                            adapter.delete(uploaded)
                        except Exception as del_exc:  # noqa: BLE001 - cleanup best-effort
                            logger.debug("upload cleanup failed: %s", del_exc)
                        uploaded = None
            if result is None:
                raise RuntimeError("All providers failed: " + "; ".join(errors))
            chunks.append((offset, parse_segments(result.text)))
            total_usage["input_tokens"] += result.usage.input_tokens
            total_usage["output_tokens"] += result.usage.output_tokens
            if result.usage.cost_usd is not None:
                total_usage["cost_usd"] += result.usage.cost_usd
            emit(
                progress,
                ProgressEvent(
                    "transcribing", f"Completed clip {index}/{total}", index, total
                ),
            )
        return merge_segments(
            source,
            chunks,
            duration=duration,
            model=self.settings.model,
            provider=selected_provider,
            notes=tuple(errors),
            metadata={"usage": total_usage},
        )

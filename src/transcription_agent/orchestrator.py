"""Chunked transcription orchestration."""

import logging
import re
import subprocess
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .media import extract_label_checkpoints, extract_visual_checkpoints
from .merge import merge_segments
from .models import Segment, Transcript
from .normalization import apply_label_mapping, parse_label_mapping
from .progress import ProgressCallback, ProgressEvent, emit
from .providers import PROMPT_TEMPLATE, configured_providers
from .timestamps import format_timestamp, parse_model_timestamp
from .upload_adapters import MediaRef, UploadDeclined, build_upload_adapter

_LINE = re.compile(
    r"\[(?P<stamp>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]"
    r"\s*(?:\*\*)?(?P<speaker>[^:*\n]+?)(?:\*\*)?:\s*"
)

logger = logging.getLogger(__name__)


def _accumulate_usage(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    if usage.cost_usd is not None:
        total["cost_usd"] += usage.cost_usd


def _label_occurrences(transcript: Transcript) -> str:
    return "\n".join(
        f"[{format_timestamp(segment.start)}] {segment.speaker}"
        for segment in transcript.segments
    )


def _first_label_times(transcript: Transcript) -> dict[str, float]:
    """Use each observed label's first turn as focused visual evidence."""
    times: dict[str, float] = {}
    for segment in transcript.segments:
        times.setdefault(segment.speaker, segment.start)
    return times


def _upload_with_timeout(adapter, path: str, timeout_seconds: float):
    """Run adapter.upload with a hard timeout so a hung POST can fall back.

    A TimeoutError is raised to the caller; the worker is abandoned so a
    stalled HTTP request cannot block the rest of the job.
    """
    import concurrent.futures

    if timeout_seconds <= 0:
        return adapter.upload(path)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(adapter.upload, path)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"upload timeout after {timeout_seconds:g}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def parse_segments(text: str) -> list[Segment]:
    """Parse turns, splitting provider-collapsed timestamped lines losslessly."""
    segments = []
    for line in text.splitlines():
        matches = list(_LINE.finditer(line))
        for index, match in enumerate(matches):
            words_end = (
                matches[index + 1].start() if index + 1 < len(matches) else len(line)
            )
            stamp = match.group("stamp")
            speaker = match.group("speaker")
            words = line[match.end() : words_end]
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
        all_visual_checkpoints = []
        for index, (offset, path) in enumerate(clips, 1):
            active_prompt = (prompt or PROMPT_TEMPLATE).format(
                start="relative", end="relative"
            )
            try:
                visual_checkpoints = extract_visual_checkpoints(
                    path,
                    offset,
                    self.settings.output_dir
                    / "visual_checkpoints"
                    / f"chunk_{index:04d}",
                )
            except (
                OSError,
                RuntimeError,
                ValueError,
                TypeError,
                subprocess.CalledProcessError,
            ) as visual_exc:
                logger.warning(
                    "optional visual checkpoints unavailable for %s: %s",
                    Path(path).name,
                    visual_exc,
                )
                visual_checkpoints = ()
            all_visual_checkpoints.extend(visual_checkpoints)
            result = None
            uploaded: MediaRef | None = None
            for provider_name in self.settings.provider_order:
                adapter = self._adapters.get(provider_name)
                provider = self.providers[provider_name]
                try:
                    # Upload once; fall back to inline base64 if upload fails.
                    if adapter is not None:
                        try:
                            uploaded = _upload_with_timeout(
                                adapter,
                                path,
                                self.settings.upload_timeout_seconds,
                            )
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
                    if uploaded is not None and hasattr(provider, "transcribe_media"):
                        if visual_checkpoints:
                            result = provider.transcribe_media(
                                uploaded,
                                active_prompt,
                                path,
                                visual_checkpoints=visual_checkpoints,
                            )
                        else:
                            result = provider.transcribe_media(
                                uploaded, active_prompt, path
                            )
                    else:
                        if visual_checkpoints:
                            result = provider.transcribe(
                                path,
                                active_prompt,
                                visual_checkpoints=visual_checkpoints,
                            )
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
            _accumulate_usage(total_usage, result.usage)
            emit(
                progress,
                ProgressEvent(
                    "transcribing", f"Completed clip {index}/{total}", index, total
                ),
            )
        transcript = merge_segments(
            source,
            chunks,
            duration=duration,
            model=self.settings.model,
            provider=selected_provider,
            notes=tuple(errors),
            metadata={"usage": total_usage},
        )
        if not (
            self.settings.speaker_normalization_enabled
            and selected_provider
            and all_visual_checkpoints
        ):
            return transcript
        try:
            label_checkpoints = extract_label_checkpoints(
                source,
                _first_label_times(transcript),
                self.settings.output_dir / "visual_checkpoints" / "label_occurrences",
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            subprocess.CalledProcessError,
        ) as visual_exc:
            logger.warning("label checkpoints unavailable: %s", visual_exc)
            label_checkpoints = ()
        normalizer = getattr(
            self.providers.get(selected_provider), "normalize_speaker_labels", None
        )
        if not callable(normalizer):
            return transcript
        labels = tuple(sorted({segment.speaker for segment in transcript.segments}))
        try:
            result = normalizer(
                _label_occurrences(transcript),
                labels,
                label_checkpoints or tuple(all_visual_checkpoints),
            )
            _accumulate_usage(total_usage, result.usage)
            mapping = parse_label_mapping(result.text, labels)
        except Exception as exc:  # noqa: BLE001 - optional normalization boundary
            errors.append(f"{selected_provider} speaker-label normalization: {exc}")
            logger.warning("speaker-label normalization unavailable: %s", exc)
            return replace(
                transcript,
                notes=tuple(errors),
                metadata={
                    **transcript.metadata,
                    "usage": total_usage,
                    "speaker_normalization": {"status": "failed", "mapping": {}},
                },
            )
        metadata = {
            **transcript.metadata,
            "usage": total_usage,
            "speaker_normalization": {
                "status": "applied" if mapping else "no_change",
                "mapping": mapping,
            },
        }
        return replace(
            transcript,
            segments=apply_label_mapping(transcript.segments, mapping),
            metadata=metadata,
            notes=tuple(errors),
        )

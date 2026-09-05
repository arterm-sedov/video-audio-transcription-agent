"""Chunked transcription orchestration."""

import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path

from .config import Settings
from .media import (
    create_chunks,
    extract_label_checkpoints,
    extract_visual_checkpoints,
    speech_seconds,
)
from .merge import merge_segments
from .models import Segment, Transcript
from .normalization import apply_label_mapping, parse_label_mapping
from .progress import ProgressCallback, ProgressEvent, emit
from .providers import PROMPT_TEMPLATE, configured_providers
from .quality import find_speech_backed_gaps, splice_repair
from .timestamps import format_timestamp, parse_model_timestamp
from .upload_adapters import MediaRef, UploadDeclined, build_upload_adapter

_LINE = re.compile(
    r"\[(?P<stamp>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]"
    r"\s*(?:\*\*)?(?P<speaker>[^:*\n]+?)(?:\*\*)?:\s*"
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _ClipResult:
    index: int
    offset: float
    segments: list[Segment]
    provider: str
    errors: tuple[str, ...]
    usage: object
    checkpoints: tuple


def _accumulate_usage(total: dict, usage) -> None:
    total["input_tokens"] += usage.input_tokens
    total["output_tokens"] += usage.output_tokens
    if usage.cost_usd is not None:
        total["cost_usd"] += usage.cost_usd


def _label_occurrences(transcript: Transcript) -> str:
    return "\n".join(
        f"[{format_timestamp(s.start)}] {s.speaker}" for s in transcript.segments
    )


def _first_label_times(transcript: Transcript) -> dict[str, float]:
    times: dict[str, float] = {}
    for segment in transcript.segments:
        times.setdefault(segment.speaker, segment.start)
    return times


def _upload_with_timeout(adapter, path: str, timeout_seconds: float):
    if timeout_seconds <= 0:
        return adapter.upload(path)
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(adapter.upload, path)
    try:
        return future.result(timeout=timeout_seconds)
    except TimeoutError as exc:
        future.cancel()
        raise TimeoutError(f"upload timeout after {timeout_seconds:g}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def parse_segments(text: str) -> list[Segment]:
    """Parse output, including multiple timestamped turns collapsed on one line."""
    segments = []
    for line in text.splitlines():
        matches = list(_LINE.finditer(line))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            segments.append(
                Segment(
                    parse_model_timestamp(match.group("stamp")),
                    0,
                    match.group("speaker").strip(),
                    line[match.end() : end].strip(),
                )
            )
    return [
        segment.with_end(next_segment.start if next_segment else segment.start)
        for segment, next_segment in zip(segments, [*segments[1:], None])
    ]


class TranscriptionService:
    """Transcribe independent chunks, then repair only speech-backed omissions."""

    def __init__(self, settings: Settings):
        settings.validate()
        self.settings = settings
        proxies = {
            name: settings.provider_proxy(name) for name in settings.provider_order
        }
        self.providers = configured_providers(
            settings.model, settings.provider_order, proxies
        )
        self._adapters = {
            name: build_upload_adapter(name, settings)
            for name in settings.provider_order
        }

    def _transcribe_clip(
        self, index: int, offset: float, path: str, prompt: str
    ) -> _ClipResult:
        errors: list[str] = []
        try:
            checkpoints = extract_visual_checkpoints(
                path,
                offset,
                self.settings.output_dir / "visual_checkpoints" / f"chunk_{index:04d}",
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            subprocess.CalledProcessError,
        ) as exc:
            logger.warning(
                "optional visual checkpoints unavailable for %s: %s",
                Path(path).name,
                exc,
            )
            checkpoints = ()
        result = None
        selected = ""
        for name in self.settings.provider_order:
            adapter = self._adapters.get(name)
            provider = self.providers[name]
            uploaded: MediaRef | None = None
            try:
                if adapter is not None:
                    try:
                        uploaded = _upload_with_timeout(
                            adapter, path, self.settings.upload_timeout_seconds
                        )
                    except UploadDeclined:
                        uploaded = None
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{name} upload({Path(path).name}): {exc}")
                if uploaded is not None and hasattr(provider, "transcribe_media"):
                    result = (
                        provider.transcribe_media(
                            uploaded, prompt, path, visual_checkpoints=checkpoints
                        )
                        if checkpoints
                        else provider.transcribe_media(uploaded, prompt, path)
                    )
                else:
                    result = (
                        provider.transcribe(
                            path, prompt, visual_checkpoints=checkpoints
                        )
                        if checkpoints
                        else provider.transcribe(path, prompt)
                    )
                selected = name
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name} ({Path(path).name}): {exc}")
            finally:
                if uploaded is not None and adapter is not None:
                    try:
                        adapter.delete(uploaded)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("upload cleanup failed: %s", exc)
        if result is None:
            raise RuntimeError("All providers failed: " + "; ".join(errors))
        return _ClipResult(
            index,
            offset,
            parse_segments(result.text),
            selected,
            tuple(errors),
            result.usage,
            tuple(checkpoints),
        )

    def _repair_gaps(
        self,
        transcript: Transcript,
        source: str,
        prompt: str,
        errors: list[str],
        usage: dict,
    ) -> Transcript:
        if not self.settings.gap_rechecks_enabled or not Path(source).is_file():
            return replace(
                transcript,
                metadata={**transcript.metadata, "quality_gate": {"status": "skipped"}},
            )
        try:
            gaps = find_speech_backed_gaps(
                transcript.segments,
                speech_seconds=lambda start, end: speech_seconds(source, start, end),
                min_span_seconds=self.settings.gap_recheck_min_span_seconds,
                max_words_per_second=self.settings.gap_recheck_max_words_per_second,
                max_candidates=self.settings.gap_recheck_max_intervals,
            )
        except (
            OSError,
            RuntimeError,
            ValueError,
            subprocess.CalledProcessError,
        ) as exc:
            errors.append(f"speech-backed gap check: {exc}")
            return replace(transcript, notes=tuple(errors))
        if not gaps:
            return replace(
                transcript,
                metadata={
                    **transcript.metadata,
                    "quality_gate": {"status": "checked", "candidates": 0},
                },
            )
        repaired = list(transcript.segments)
        evidence = []
        reminder = "\n\nFocused completeness recheck: transcribe every audible word, including static-layout or screen-share speech. Do not replace continued speech with a short acknowledgement."
        for number, gap in enumerate(gaps, 1):
            start = max(0.0, gap.start - self.settings.gap_recheck_padding_seconds)
            limit = (
                transcript.duration
                if transcript.duration is not None
                else gap.end + self.settings.gap_recheck_padding_seconds
            )
            end = min(limit, gap.end + self.settings.gap_recheck_padding_seconds)
            destination = (
                self.settings.output_dir / "gap_rechecks" / f"gap_{number:02d}"
            )
            try:
                from .media import create_interval_clip

                interval = create_interval_clip(
                    source, start, end, destination / "interval.mp4"
                )
                _, clips = create_chunks(
                    interval,
                    destination / "chunks",
                    self.settings.gap_recheck_chunk_seconds,
                    provider=self.settings.provider_order[0],
                    model=self.settings.model,
                    overlap_seconds=self.settings.chunk_overlap_seconds,
                    floor_seconds=1,
                )
                settings = replace(
                    self.settings,
                    gap_rechecks_enabled=False,
                    speaker_normalization_enabled=False,
                    chunk_launch_interval_seconds=0,
                )
                recheck = TranscriptionService(settings).transcribe_clips(
                    str(interval),
                    [(chunk.start, str(path)) for chunk, path in clips],
                    duration=end - start,
                    prompt=prompt + reminder,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"gap recheck {gap.start:.3f}-{gap.end:.3f}: {exc}")
                continue
            for key, value in recheck.metadata.get("usage", {}).items():
                usage[key] = usage.get(key, 0) + (value or 0)
            absolute = [segment.shifted(start) for segment in recheck.segments]
            words = sum(
                len(segment.text.split())
                for segment in absolute
                if gap.start <= segment.start < gap.end
            )
            item = {
                "start": gap.start,
                "end": gap.end,
                "original_words": gap.word_count,
                "recheck_words": words,
            }
            if words < gap.word_count + max(10, gap.word_count // 2):
                evidence.append({**item, "status": "not_proven"})
                continue
            repaired = splice_repair(repaired, gap.start, gap.end, absolute)
            evidence.append({**item, "status": "repaired"})
        return replace(
            transcript,
            segments=tuple(repaired),
            notes=tuple(errors),
            metadata={
                **transcript.metadata,
                "usage": usage,
                "quality_gate": {"status": "checked", "candidates": len(gaps)},
                "gap_repairs": evidence,
            },
        )

    def transcribe_clips(
        self,
        source: str,
        clips: list[tuple[float, str]],
        *,
        duration: float | None = None,
        progress: ProgressCallback | None = None,
        prompt: str | None = None,
    ) -> Transcript:
        total = len(clips)
        emit(
            progress, ProgressEvent("transcribing", "Starting transcription", 0, total)
        )
        active_prompt = (prompt or PROMPT_TEMPLATE).format(
            start="relative", end="relative"
        )
        errors: list[str] = []
        usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
        results: list[_ClipResult] = []
        with ThreadPoolExecutor(max_workers=max(1, total)) as executor:
            futures = []
            for index, (offset, path) in enumerate(clips, 1):
                if futures and self.settings.chunk_launch_interval_seconds:
                    time.sleep(self.settings.chunk_launch_interval_seconds)
                futures.append(
                    executor.submit(
                        self._transcribe_clip, index, offset, path, active_prompt
                    )
                )
            for completed, future in enumerate(as_completed(futures), 1):
                result = future.result()
                results.append(result)
                errors.extend(result.errors)
                _accumulate_usage(usage, result.usage)
                emit(
                    progress,
                    ProgressEvent(
                        "transcribing",
                        f"Completed clip {result.index}/{total}",
                        completed,
                        total,
                    ),
                )
        results.sort(key=lambda result: result.index)
        providers = {result.provider for result in results}
        selected = results[0].provider if results and len(providers) == 1 else None
        transcript = merge_segments(
            source,
            [(result.offset, result.segments) for result in results],
            duration=duration,
            model=self.settings.model,
            provider=selected,
            notes=tuple(errors),
            metadata={"usage": usage},
            overlap_seconds=self.settings.chunk_overlap_seconds,
        )
        transcript = self._repair_gaps(transcript, source, active_prompt, errors, usage)
        checkpoints = tuple(
            checkpoint for result in results for checkpoint in result.checkpoints
        )
        if not (
            self.settings.speaker_normalization_enabled and selected and checkpoints
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
        ) as exc:
            logger.warning("label checkpoints unavailable: %s", exc)
            label_checkpoints = ()
        normalizer = getattr(
            self.providers.get(selected), "normalize_speaker_labels", None
        )
        if not callable(normalizer):
            return transcript
        labels = tuple(sorted({segment.speaker for segment in transcript.segments}))
        try:
            result = normalizer(
                _label_occurrences(transcript), labels, label_checkpoints or checkpoints
            )
            _accumulate_usage(usage, result.usage)
            mapping = parse_label_mapping(result.text, labels)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{selected} speaker-label normalization: {exc}")
            logger.warning("speaker-label normalization unavailable: %s", exc)
            return replace(
                transcript,
                notes=tuple(errors),
                metadata={
                    **transcript.metadata,
                    "usage": usage,
                    "speaker_normalization": {"status": "failed", "mapping": {}},
                },
            )
        return replace(
            transcript,
            segments=apply_label_mapping(transcript.segments, mapping),
            notes=tuple(errors),
            metadata={
                **transcript.metadata,
                "usage": usage,
                "speaker_normalization": {
                    "status": "applied" if mapping else "no_change",
                    "mapping": mapping,
                },
            },
        )

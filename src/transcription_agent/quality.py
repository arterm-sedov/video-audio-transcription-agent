"""Focused, speech-backed transcript omission detection and safe repair."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .models import Segment


@dataclass(frozen=True, slots=True)
class SpeechBackedGap:
    start: float
    end: float
    word_count: int
    speech_seconds: float


def _word_count(text: str) -> int:
    return len(text.split())


def find_speech_backed_gaps(
    segments: Iterable[Segment],
    *,
    speech_seconds: Callable[[float, float], float],
    min_span_seconds: float,
    max_words_per_second: float,
    max_candidates: int = 3,
) -> tuple[SpeechBackedGap, ...]:
    """Find long, near-empty turns only when the corresponding audio has speech."""
    candidates = []
    for segment in segments:
        span = segment.end - segment.start
        words = _word_count(segment.text)
        if span < min_span_seconds or words / span > max_words_per_second:
            continue
        audible = speech_seconds(segment.start, segment.end)
        if audible >= max(10.0, span * 0.25):
            candidates.append(
                SpeechBackedGap(segment.start, segment.end, words, audible)
            )
    return tuple(candidates[:max_candidates])


def splice_repair(
    original: Iterable[Segment],
    start: float,
    end: float,
    repair: Iterable[Segment],
) -> list[Segment]:
    """Replace only turns that start inside the proven missing interval."""
    retained = [segment for segment in original if not start <= segment.start < end]
    inserted = [segment for segment in repair if start <= segment.start < end]
    return sorted(
        [*retained, *inserted], key=lambda segment: (segment.start, segment.end)
    )

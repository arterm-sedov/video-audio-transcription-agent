"""Deterministic chunk planning independent of media backend."""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    start: float
    end: float


def plan_chunks(duration: float, chunk_seconds: int = 300) -> tuple[Chunk, ...]:
    """Return contiguous, non-overlapping chunks covering the full duration."""
    if duration < 0:
        raise ValueError("duration must not be negative")
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds must be positive")
    if duration == 0:
        return ()
    count = math.ceil(duration / chunk_seconds)
    return tuple(
        Chunk(i, i * chunk_seconds, min((i + 1) * chunk_seconds, duration))
        for i in range(count)
    )

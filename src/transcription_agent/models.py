"""Stable data contracts shared by providers, orchestration, and exporters."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Segment:
    """One timestamped speaker turn."""

    start: float
    end: float
    speaker: str
    text: str
    confidence: float | None = None
    evidence: tuple[str, ...] = ()

    def shifted(self, offset: float) -> "Segment":
        return Segment(
            start=self.start + offset,
            end=self.end + offset,
            speaker=self.speaker,
            text=self.text,
            confidence=self.confidence,
            evidence=self.evidence,
        )

    def with_end(self, end: float) -> "Segment":
        return Segment(
            start=self.start,
            end=max(self.start, end),
            speaker=self.speaker,
            text=self.text,
            confidence=self.confidence,
            evidence=self.evidence,
        )


@dataclass(frozen=True, slots=True)
class Transcript:
    """Completed transcript and processing metadata."""

    source: str
    segments: tuple[Segment, ...]
    duration: float | None = None
    model: str | None = None
    provider: str | None = None
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

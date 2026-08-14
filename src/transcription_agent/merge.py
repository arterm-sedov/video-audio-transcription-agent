"""Speaker-aware transcript merge logic."""

from .models import Segment, Transcript


def merge_segments(
    source: str,
    chunks: list[tuple[float, list[Segment]]],
    *,
    duration: float | None = None,
    model: str | None = None,
    provider: str | None = None,
    notes: tuple[str, ...] = (),
    metadata: dict | None = None,
) -> Transcript:
    """Offset chunk-local segments and return a stable chronological transcript."""
    merged = [
        segment.shifted(offset) for offset, segments in chunks for segment in segments
    ]
    merged.sort(key=lambda segment: (segment.start, segment.end))
    return Transcript(
        source=source,
        segments=tuple(merged),
        duration=duration,
        model=model,
        provider=provider,
        notes=notes,
        metadata=metadata or {},
    )

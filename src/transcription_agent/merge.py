"""Speaker-aware transcript merge logic."""

from .models import Segment, Transcript


def _words(segment: Segment) -> list[str]:
    return segment.text.split()


def _shared_boundary_words(left: list[str], right: list[str]) -> int:
    """Return the longest exact suffix/prefix phrase, not a fuzzy guess."""
    for size in range(min(len(left), len(right)), 0, -1):
        if [word.casefold() for word in left[-size:]] == [
            word.casefold() for word in right[:size]
        ]:
            return size
    return 0


def _merge_overlap(
    entries: list[tuple[Segment, float]], overlap_seconds: float
) -> list[Segment]:
    """Semantically join same-speaker turns on a proven repeated boundary phrase."""
    if overlap_seconds <= 0:
        return [segment for segment, _ in entries]
    kept: list[tuple[Segment, float]] = []
    for segment, chunk_start in entries:
        prior = next(
            (
                item
                for item, item_chunk_start in reversed(kept)
                if item.speaker == segment.speaker
                and item_chunk_start < chunk_start
                and item.start <= segment.start + overlap_seconds
                and (
                    item.end >= chunk_start - overlap_seconds
                    or item.start >= chunk_start - overlap_seconds
                )
            ),
            None,
        )
        if prior is None or segment.start > chunk_start + overlap_seconds:
            kept.append((segment, chunk_start))
            continue
        shared = _shared_boundary_words(_words(prior), _words(segment))
        if not shared:
            kept.append((segment, chunk_start))
            continue
        combined = [*_words(prior), *_words(segment)[shared:]]
        index = next(index for index, (item, _) in enumerate(kept) if item is prior)
        kept[index] = (
            Segment(
                prior.start,
                max(prior.end, segment.end),
                prior.speaker,
                " ".join(combined),
                prior.confidence,
                prior.evidence,
            ),
            kept[index][1],
        )
    return [segment for segment, _ in kept]


def merge_segments(
    source: str,
    chunks: list[tuple[float, list[Segment]]],
    *,
    duration: float | None = None,
    model: str | None = None,
    provider: str | None = None,
    notes: tuple[str, ...] = (),
    metadata: dict | None = None,
    overlap_seconds: float = 0.0,
) -> Transcript:
    """Offset chunk-local segments and return a stable chronological transcript."""
    merged = [
        (segment.shifted(offset), offset)
        for offset, segments in chunks
        for segment in segments
    ]
    # Earlier chunk wins ties at the same absolute timestamp, so its text is
    # the left side of any boundary phrase.
    merged.sort(key=lambda entry: (entry[0].start, entry[1], entry[0].end))
    merged = _merge_overlap(merged, overlap_seconds)
    return Transcript(
        source=source,
        segments=tuple(merged),
        duration=duration,
        model=model,
        provider=provider,
        notes=notes,
        metadata=metadata or {},
    )

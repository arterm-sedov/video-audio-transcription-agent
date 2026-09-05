from transcription_agent.models import Segment
from transcription_agent.quality import find_speech_backed_gaps, splice_repair


def test_find_speech_backed_gap_requires_low_word_density_and_voice() -> None:
    segments = [
        Segment(10, 155, "A", "угу"),
        Segment(155, 160, "B", "next words"),
    ]

    gaps = find_speech_backed_gaps(
        segments,
        speech_seconds=lambda start, end: end - start,
        min_span_seconds=45,
        max_words_per_second=0.2,
    )

    assert [(gap.start, gap.end, gap.word_count) for gap in gaps] == [(10, 155, 1)]


def test_splice_repair_preserves_segments_outside_proven_interval() -> None:
    original = [
        Segment(0, 10, "A", "before"),
        Segment(10, 155, "A", "угу"),
        Segment(155, 160, "B", "after"),
    ]
    repaired = [Segment(10, 155, "A", "all missing words")]

    merged = splice_repair(original, 10, 155, repaired)

    assert [(item.start, item.text) for item in merged] == [
        (0, "before"),
        (10, "all missing words"),
        (155, "after"),
    ]

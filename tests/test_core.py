from pathlib import Path

from transcription_agent.chunking import plan_chunks
from transcription_agent.exporters import export_transcript
from transcription_agent.merge import merge_segments
from transcription_agent.models import Segment
from transcription_agent.registry import JobRegistry
from transcription_agent.timestamps import format_timestamp, parse_model_timestamp


def test_chunk_plan_covers_duration_without_gaps() -> None:
    chunks = plan_chunks(967.8, 300)
    assert [(chunk.start, chunk.end) for chunk in chunks] == [
        (0, 300),
        (300, 600),
        (600, 900),
        (900, 967.8),
    ]


def test_timestamp_round_trip_formats_subtitles() -> None:
    assert parse_model_timestamp("01:02") == 62
    assert parse_model_timestamp("01:02:03") == 3723
    assert format_timestamp(62.25, subtitle=True) == "00:01:02,250"


def test_merge_offsets_and_sorts_segments() -> None:
    transcript = merge_segments(
        "meeting.mp4",
        [
            (300, [Segment(0, 2, "Speaker 2", "second")]),
            (0, [Segment(4, 5, "Speaker 1", "first")]),
        ],
    )
    assert [segment.text for segment in transcript.segments] == ["first", "second"]
    assert transcript.segments[1].start == 300


def test_exporters_write_all_formats(tmp_path: Path) -> None:
    transcript = merge_segments(
        "meeting.mp4", [(0, [Segment(0, 1.5, "Speaker 1", "Hello")])]
    )
    paths = export_transcript(transcript, tmp_path)
    assert set(paths) == {"markdown", "json", "srt", "vtt"}
    assert "Speaker 1" in paths["markdown"].read_text(encoding="utf-8")
    assert "WEBVTT" in paths["vtt"].read_text(encoding="utf-8")


def test_registry_tracks_job_status(tmp_path: Path) -> None:
    registry = JobRegistry(tmp_path / "jobs.sqlite3")
    job_id = registry.create("meeting.mp4", "polza", "google/gemini-2.5-flash")
    registry.update(job_id, "completed")
    assert registry.get(job_id)["status"] == "completed"

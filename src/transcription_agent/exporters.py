"""Markdown, JSON, SRT, and WebVTT transcript exporters."""

import json
from pathlib import Path

from .costs import format_cost
from .models import Transcript
from .timestamps import format_timestamp


def _payload(transcript: Transcript) -> dict:
    return {
        "source": transcript.source,
        "duration": transcript.duration,
        "model": transcript.model,
        "provider": transcript.provider,
        "created_at": transcript.created_at,
        "notes": list(transcript.notes),
        "metadata": transcript.metadata,
        "segments": [
            {
                "start": segment.start,
                "end": segment.end,
                "speaker": segment.speaker,
                "text": segment.text,
                "confidence": segment.confidence,
                "evidence": list(segment.evidence),
            }
            for segment in transcript.segments
        ],
    }


def export_transcript(
    transcript: Transcript, output_dir: str | Path
) -> dict[str, Path]:
    """Write all supported formats and return their paths."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(transcript.source).stem
    paths = {
        "markdown": directory / f"{stem}_transcription.md",
        "json": directory / f"{stem}_transcription.json",
        "srt": directory / f"{stem}_transcription.srt",
        "vtt": directory / f"{stem}_transcription.vtt",
    }
    speakers = sorted({segment.speaker for segment in transcript.segments})
    markdown = [f"# Transcription: {stem}", "", "## Speaker key", ""]
    markdown.extend(f"- {speaker}" for speaker in speakers)
    markdown.extend(["", "## Transcript", ""])
    markdown.extend(
        f"[{format_timestamp(s.start)}] **{s.speaker}**: {s.text}"
        for s in transcript.segments
    )
    usage = transcript.metadata.get("usage", {})
    if usage:
        markdown.extend(
            [
                "",
                "## Processing",
                "",
                f"- Input tokens: {usage.get('input_tokens', 0):,}",
                f"- Output tokens: {usage.get('output_tokens', 0):,}",
                f"- Estimated cost: {format_cost(usage.get('cost_usd'))}",
            ]
        )
    if transcript.notes:
        markdown.extend(["", "## Notes", ""])
        markdown.extend(f"- {note}" for note in transcript.notes)
    paths["markdown"].write_text("\n".join(markdown) + "\n", encoding="utf-8")
    paths["json"].write_text(
        json.dumps(_payload(transcript), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    srt = []
    for index, segment in enumerate(transcript.segments, 1):
        srt.extend(
            [
                str(index),
                (
                    f"{format_timestamp(segment.start, subtitle=True)} --> "
                    f"{format_timestamp(segment.end, subtitle=True)}"
                ),
                f"{segment.speaker}: {segment.text}",
                "",
            ]
        )
    paths["srt"].write_text("\n".join(srt), encoding="utf-8")
    vtt = ["WEBVTT", ""]
    for segment in transcript.segments:
        vtt.extend(
            [
                f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}",
                f"{segment.speaker}: {segment.text}",
                "",
            ]
        )
    paths["vtt"].write_text("\n".join(vtt), encoding="utf-8")
    return paths

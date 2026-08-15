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
    transcript: Transcript,
    output_dir: str | Path,
    *,
    formats: tuple[str, ...] | None = None,
    markdown_name: str | None = None,
) -> dict[str, Path]:
    """Write requested formats (default: all) and return their paths.

    ``markdown_name`` overrides the Markdown filename; other format names are
    derived from it. ``formats`` restricts which files are written.
    """
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(transcript.source).stem
    output_stem = Path(markdown_name).stem if markdown_name else f"{stem}_transcription"
    if formats:
        wanted = set(formats)
    else:
        wanted = {"markdown", "json", "srt", "vtt"}
    paths: dict[str, Path] = {}
    if "markdown" in wanted:
        paths["markdown"] = directory / f"{output_stem}.md"
    if "json" in wanted:
        paths["json"] = directory / f"{output_stem}.json"
    if "srt" in wanted:
        paths["srt"] = directory / f"{output_stem}.srt"
    if "vtt" in wanted:
        paths["vtt"] = directory / f"{output_stem}.vtt"
    speakers = sorted({segment.speaker for segment in transcript.segments})
    if "markdown" in wanted:
        markdown = [f"# Transcription: {stem}", "", "## Speaker key", ""]
        markdown.extend(f"- {speaker}" for speaker in speakers)
        markdown.extend(["", "## Transcript", ""])
        markdown.extend(
            f"[{format_timestamp(s.start)}] **{s.speaker}**: {s.text}"
            for s in transcript.segments
        )
        usage = transcript.metadata.get("usage", {})
        if usage:
            total_cost = format_cost(usage.get("cost_usd"))
            markdown.extend(
                [
                    "",
                    "## Processing",
                    "",
                    f"- Input tokens: {usage.get('input_tokens', 0):,}",
                    f"- Output tokens: {usage.get('output_tokens', 0):,}",
                    f"- Estimated total cost: {total_cost}",
                ]
            )
        if transcript.notes:
            markdown.extend(["", "## Notes", ""])
            markdown.extend(f"- {note}" for note in transcript.notes)
        paths["markdown"].write_text("\n".join(markdown) + "\n", encoding="utf-8")
    if "json" in wanted:
        paths["json"].write_text(
            json.dumps(_payload(transcript), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if "srt" in wanted:
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
    if "vtt" in wanted:
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

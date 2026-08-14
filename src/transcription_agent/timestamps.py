"""Timestamp parsing and normalization."""

import re

_STAMP = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")


def parse_model_timestamp(value: str) -> float:
    """Parse MM:SS, HH:MM:SS, or Gemini's MM:SS:frames form."""
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        hours, minutes, seconds = parts
        if hours == 0 and seconds == 0 and minutes < 60:
            return minutes * 60
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported timestamp: {value}")


def format_timestamp(seconds: float, *, subtitle: bool = False) -> str:
    """Format seconds as HH:MM:SS or HH:MM:SS,mmm."""
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if subtitle else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"

"""Safe speaker-label normalization helpers."""

import json
import re
from collections.abc import Iterable
from dataclasses import replace

from .models import Segment

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _json_object(response_text: str) -> dict:
    """Extract one JSON object while rejecting non-JSON model syntax."""
    raw = _JSON_FENCE.sub("", response_text.strip())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            raise
        payload, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(payload, dict):
        raise TypeError("label normalization must return a JSON mapping object")
    return payload


def parse_label_mapping(response_text: str, labels: Iterable[str]) -> dict[str, str]:
    """Parse a conservative provider mapping whose keys and values are labels."""
    payload = _json_object(response_text)
    if not isinstance(payload.get("mapping"), dict):
        raise TypeError("label normalization must return a JSON mapping object")
    confidence = payload.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, (int, float)) or confidence < 0.8
    ):
        raise ValueError("label normalization confidence is below 0.8")
    known = set(labels)
    mapping = {}
    for source, target in payload["mapping"].items():
        if not isinstance(source, str) or not isinstance(target, str):
            raise TypeError("label normalization keys and values must be strings")
        if source not in known or target not in known:
            raise ValueError("label normalization may only use observed labels")
        if source != target:
            mapping[source] = target
    return mapping


def apply_label_mapping(
    segments: Iterable[Segment], mapping: dict[str, str]
) -> tuple[Segment, ...]:
    """Apply only speaker-label changes; preserve every other segment field."""

    def resolve(label: str) -> str:
        seen = set()
        current = label
        while current in mapping and current not in seen:
            seen.add(current)
            current = mapping[current]
        return label if current in seen else current

    return tuple(
        replace(segment, speaker=resolve(segment.speaker)) for segment in segments
    )

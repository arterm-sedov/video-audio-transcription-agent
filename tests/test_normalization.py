import pytest

from transcription_agent.models import Segment
from transcription_agent.normalization import apply_label_mapping, parse_label_mapping


def test_parse_label_mapping_rejects_unobserved_names() -> None:
    with pytest.raises(ValueError, match="observed labels"):
        parse_label_mapping(
            '{"confidence": 0.95, "mapping": {"Variant": "Invented"}}',
            ("Variant", "Canonical"),
        )


def test_parse_label_mapping_accepts_json_wrapped_in_model_prose() -> None:
    mapping = parse_label_mapping(
        'Result:\n```json\n{"confidence": 0.95, "mapping": '
        '{"Variant": "Canonical"}}\n```',
        ("Variant", "Canonical"),
    )

    assert mapping == {"Variant": "Canonical"}


def test_apply_label_mapping_changes_only_speaker_field() -> None:
    segment = Segment(
        12.0,
        18.0,
        "Variant",
        "exact words",
        confidence=0.7,
        evidence=("frame",),
    )

    [normalized] = apply_label_mapping([segment], {"Variant": "Canonical"})

    assert normalized == Segment(
        12.0,
        18.0,
        "Canonical",
        "exact words",
        confidence=0.7,
        evidence=("frame",),
    )

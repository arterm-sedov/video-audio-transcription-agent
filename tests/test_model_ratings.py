"""Roster ratings: price, speed, quality, reliability."""

from transcription_agent.models_catalog import (
    TESTED,
    model_choices_for,
    rating_label,
)


def test_primer_includes_mimo_not_qwens() -> None:
    assert "xiaomi/mimo-v2.5" in TESTED
    assert "xiaomi/qwens-v2.5" not in TESTED
    assert "xiaomi/mimo-v2.5" in model_choices_for("polza")


def test_polza_roster_ranks_quality_then_price_then_speed() -> None:
    polza = model_choices_for("polza")
    assert polza[0] == "google/gemini-3.1-flash-lite"
    assert polza.index("google/gemini-3.1-flash-lite") < polza.index(
        "google/gemini-3.5-flash-lite"
    )
    assert polza.index("google/gemini-3.5-flash-lite") < polza.index(
        "google/gemini-3.6-flash"
    )
    assert polza.index("google/gemini-3.6-flash") < polza.index(
        "google/gemini-3.7-flash"
    )
    assert polza.index("google/gemini-3.7-flash") < polza.index(
        "google/gemini-2.5-flash"
    )
    assert polza.index("google/gemini-2.5-flash") < polza.index(
        "google/gemini-3.5-flash"
    )
    assert polza.index("google/gemini-3.5-flash") < polza.index("google/gemini-2.5-pro")
    assert polza.index("google/gemini-2.5-pro") < polza.index(
        "google/gemini-2.5-flash-lite"
    )
    assert polza.index("google/gemini-2.5-flash-lite") < polza.index("xiaomi/mimo-v2.5")


def test_rating_label_exposes_price_speed_quality_axes() -> None:
    label = rating_label("google/gemini-3.1-flash-lite")
    assert "quality=strong" in label
    assert "speed=fast" in label
    assert "reliability=high" in label
    mixed = rating_label("google/gemini-2.5-flash")
    assert "reliability=mixed" in mixed
    demoted = rating_label("google/gemini-2.5-flash-lite")
    assert "quality=good" in demoted
    assert "reliability=low" in demoted
    mimo = rating_label("xiaomi/mimo-v2.5")
    assert "quality=good" in mimo
    assert "reliability=mixed" in mimo

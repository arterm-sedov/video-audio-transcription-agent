from pathlib import Path

from transcription_agent.artifacts import build_artifact_zip
from transcription_agent.costs import format_cost, normalize_usage


def test_polza_cost_is_converted_from_rubles(monkeypatch) -> None:
    monkeypatch.setenv("POLZA_RUB_TO_USD_RATE", "100")
    usage = normalize_usage("polza", {"cost_rub": 25, "prompt_tokens": 10})
    assert usage.cost_usd == 0.25
    assert usage.total_tokens == 10


def test_cost_formatting() -> None:
    assert format_cost(0.0) == "$0.0000"
    assert format_cost(None) == "—"


def test_artifact_zip_contains_manifest(tmp_path: Path) -> None:
    source = tmp_path / "out.md"
    source.write_text("hello", encoding="utf-8")
    package = build_artifact_zip([source])
    assert package is not None and package.exists()

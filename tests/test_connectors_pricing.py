from pathlib import Path

from transcription_agent.connectors import resolve_source
from transcription_agent.pricing import ModelPricing


def test_local_connector_resolves_path(tmp_path: Path) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"media")
    assert resolve_source(str(source)) == source.resolve()


def test_model_pricing_contract() -> None:
    pricing = ModelPricing("model", 0.1, 0.2, "test")
    assert pricing.output_per_token == 0.2

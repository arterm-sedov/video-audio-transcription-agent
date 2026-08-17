from pathlib import Path

from transcription_agent.config import Settings
from transcription_agent.media import MediaInfo


def test_settings_are_cross_platform(tmp_path: Path) -> None:
    settings = Settings(
        output_dir=tmp_path / "out", database_path=tmp_path / "jobs.sqlite3"
    )
    settings.validate()
    assert settings.output_dir.name == "out"


def test_media_info_contract() -> None:
    info = MediaInfo("clip.mp4", 12.5, True, True)
    assert info.has_audio and info.has_video


def test_settings_allow_auto_chunk_size() -> None:
    # 0 means "auto from model context window"; it is valid, not an error.
    settings = Settings(chunk_seconds=0)
    settings.validate()
    assert settings.chunk_seconds == 0

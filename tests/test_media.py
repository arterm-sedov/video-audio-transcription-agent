from pathlib import Path
from types import SimpleNamespace

from transcription_agent import media
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


def test_visual_checkpoints_bracket_scene_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(
        media,
        "probe",
        lambda path: MediaInfo(str(path), 10.0, True, True),
    )
    monkeypatch.setattr(media, "ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr(media, "_scene_candidates", lambda path: (5.0,))
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if any("metadata=print:file=-" in part for part in command):
            return SimpleNamespace(stderr="", stdout="")
        Path(command[-1]).write_bytes(b"png")
        return SimpleNamespace(stderr="", stdout="")

    monkeypatch.setattr(media.subprocess, "run", fake_run)

    checkpoints = media.extract_visual_checkpoints(
        source, 60.0, tmp_path / "frames", max_checkpoints=6
    )

    assert [checkpoint.relative_seconds for checkpoint in checkpoints] == [
        0.0,
        4.25,
        5.0,
        5.75,
        9.5,
    ]
    assert all(checkpoint.original_seconds >= 60.0 for checkpoint in checkpoints)
    assert len(commands) == len(checkpoints) * 2


def test_label_checkpoints_use_observed_label_timestamps(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "meeting.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(
        media,
        "probe",
        lambda path: MediaInfo(str(path), 10.0, True, True),
    )
    monkeypatch.setattr(media, "ffmpeg_binary", lambda: "ffmpeg")

    def fake_run(command, **kwargs):
        if any("metadata=print:file=-" in part for part in command):
            return SimpleNamespace(stderr="", stdout="")
        Path(command[-1]).write_bytes(b"png")
        return SimpleNamespace(stderr="", stdout="")

    monkeypatch.setattr(media.subprocess, "run", fake_run)

    checkpoints = media.extract_label_checkpoints(
        source,
        {"Variant": 2.5, "Canonical": 7.5},
        tmp_path / "label_frames",
    )

    assert [(item.relative_seconds, item.original_seconds) for item in checkpoints] == [
        (2.5, 2.5),
        (7.5, 7.5),
    ]
    assert all(
        item.reason.startswith("speaker-label occurrence:") for item in checkpoints
    )

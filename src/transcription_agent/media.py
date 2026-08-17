"""Portable media probing and FFmpeg chunk creation."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk, plan_chunks, plan_chunks_for_model


@dataclass(frozen=True, slots=True)
class MediaInfo:
    path: str
    duration: float
    has_audio: bool
    has_video: bool


def ffmpeg_binary() -> str:
    """Resolve FFmpeg from PATH or fail with an actionable message."""
    binary = shutil.which("ffmpeg")
    if not binary:
        try:
            import imageio_ffmpeg

            binary = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "Install the media extra or provide FFmpeg on PATH"
            ) from exc
    return binary


def probe(path: str | Path) -> MediaInfo:
    """Probe media through ffprobe, which ships with FFmpeg."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        return MediaInfo(
            str(path),
            float(payload["format"]["duration"]),
            any(s.get("codec_type") == "audio" for s in streams),
            any(s.get("codec_type") == "video" for s in streams),
        )
    try:
        import av

        with av.open(str(path)) as container:
            return MediaInfo(
                str(path),
                float(container.duration / av.time_base),
                bool(container.streams.audio),
                bool(container.streams.video),
            )
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Install the media extra or provide ffprobe on PATH"
        ) from exc


def create_chunks(
    path: str | Path,
    output_dir: str | Path,
    chunk_seconds: int = 300,
    provider: str | None = None,
    model: str | None = None,
) -> tuple[MediaInfo, tuple[tuple[Chunk, Path], ...]]:
    """Create portable, speech-preserving MP4 chunks using FFmpeg."""
    source = Path(path)
    info = probe(source)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if provider and model:
        # chunk_seconds <= 0 means "auto from model context window"
        auto = None if chunk_seconds is not None and chunk_seconds <= 0 else chunk_seconds
        chunks = plan_chunks_for_model(info.duration, provider, model, chunk_seconds=auto)
    else:
        chunks = plan_chunks(info.duration, chunk_seconds=chunk_seconds)
    ffmpeg = ffmpeg_binary()
    result = []
    for chunk in chunks:
        extension = ".mp4" if info.has_video else ".m4a"
        output = (
            destination / f"chunk_{chunk.index:04d}_{int(chunk.start):08d}{extension}"
        )
        duration = chunk.end - chunk.start
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(chunk.start),
            "-i",
            str(source),
            "-t",
            str(duration),
        ]
        if info.has_video:
            command.extend(
                [
                    "-vf",
                    "scale=960:-2,fps=2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "28",
                ]
            )
        else:
            command.append("-vn")
        command.extend(["-c:a", "aac", "-b:a", "96k", "-y", str(output)])
        subprocess.run(command, check=True)
        result.append((chunk, output))
    return info, tuple(result)

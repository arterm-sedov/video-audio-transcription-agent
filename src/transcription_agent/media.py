"""Portable media probing and FFmpeg chunk creation."""

import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .chunking import Chunk, plan_chunks, plan_chunks_for_model


@dataclass(frozen=True, slots=True)
class MediaInfo:
    path: str
    duration: float
    has_audio: bool
    has_video: bool


@dataclass(frozen=True, slots=True)
class VisualCheckpoint:
    """A still frame with chunk-relative and original-media timestamps."""

    relative_seconds: float
    original_seconds: float
    path: Path
    reason: str


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
    overlap_seconds: float = 0.0,
    floor_seconds: int = 300,
) -> tuple[MediaInfo, tuple[tuple[Chunk, Path], ...]]:
    """Create portable, speech-preserving MP4 chunks using FFmpeg."""
    source = Path(path)
    info = probe(source)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if provider and model:
        # chunk_seconds <= 0 means "auto from model context window"
        auto = (
            None if chunk_seconds is not None and chunk_seconds <= 0 else chunk_seconds
        )
        chunks = plan_chunks_for_model(
            info.duration,
            provider,
            model,
            chunk_seconds=auto,
            floor_seconds=floor_seconds,
            overlap_seconds=overlap_seconds,
        )
    else:
        chunks = plan_chunks(
            info.duration,
            chunk_seconds=chunk_seconds,
            floor_seconds=floor_seconds,
            overlap_seconds=overlap_seconds,
        )
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


def create_interval_clip(
    source: str | Path, start: float, end: float, output: str | Path
) -> Path:
    """Create one bounded, speech-preserving recheck clip from original media."""
    info = probe(source)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end - start)
    command = [
        ffmpeg_binary(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start),
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
    command.extend(["-c:a", "aac", "-b:a", "96k", "-y", str(destination)])
    subprocess.run(command, check=True)
    return destination


_SILENCE_DURATION = re.compile(r"silence_duration: (?P<seconds>[0-9]+(?:\.[0-9]+)?)")


def speech_seconds(path: str | Path, start: float, end: float) -> float:
    """Estimate speech-bearing duration with FFmpeg silence detection.

    This is deliberately supporting evidence: it confirms a suspicious sparse
    turn before a focused recheck, but does not invent transcript boundaries.
    """
    duration = max(0.0, end - start)
    if duration == 0:
        return 0.0
    result = subprocess.run(
        [
            ffmpeg_binary(),
            "-hide_banner",
            "-ss",
            str(start),
            "-i",
            str(path),
            "-t",
            str(duration),
            "-af",
            "silencedetect=n=-35dB:d=1",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    silence = sum(
        float(match.group("seconds"))
        for match in _SILENCE_DURATION.finditer(result.stderr)
    )
    return max(0.0, duration - silence)


_SCENE_TIME = re.compile(r"pts_time:(?P<seconds>[0-9]+(?:\.[0-9]+)?)")
_SIGNALSTAT = re.compile(
    r"lavfi\.signalstats\.(?P<name>YMIN|YMAX)=(?P<value>[0-9]+(?:\.[0-9]+)?)"
)


def _scene_candidates(path: Path, threshold: float = 0.08) -> tuple[float, ...]:
    """Return FFmpeg scene-change candidates for one video chunk."""
    ffmpeg = ffmpeg_binary()
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values = [
        float(match.group("seconds")) for match in _SCENE_TIME.finditer(result.stderr)
    ]
    return tuple(sorted(set(values)))


def _is_uniform_black_frame(path: Path) -> bool:
    """Detect an all-black extraction artifact without rejecting dark UI cues."""
    ffmpeg = ffmpeg_binary()
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vf",
            "signalstats,metadata=print:file=-",
            "-an",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values = {
        match.group("name"): float(match.group("value"))
        for match in _SIGNALSTAT.finditer(result.stdout)
    }
    # 16 is the black level in limited-range YUV. Keep a small tolerance for
    # encoder rounding, and require both extrema to avoid rejecting dark frames.
    return values.get("YMIN", 255.0) <= 17.0 and values.get("YMAX", 255.0) <= 17.0


def _extract_checkpoint(
    source: Path,
    relative_seconds: float,
    original_offset: float,
    output: Path,
    reason: str,
) -> VisualCheckpoint | None:
    """Extract one usable still without treating a dark interface as blank."""
    subprocess.run(
        [
            ffmpeg_binary(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(relative_seconds),
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=1280:-2",
            "-y",
            str(output),
        ],
        check=True,
    )
    if not output.is_file():
        return None
    try:
        is_black = _is_uniform_black_frame(output)
    except (OSError, subprocess.CalledProcessError):
        is_black = False
    if is_black:
        output.unlink(missing_ok=True)
        return None
    return VisualCheckpoint(
        relative_seconds, original_offset + relative_seconds, output, reason
    )


def extract_visual_checkpoints(
    path: str | Path,
    original_offset: float,
    output_dir: str | Path,
    *,
    max_checkpoints: int = 12,
) -> tuple[VisualCheckpoint, ...]:
    """Extract periodic and scene-change stills as multimodal evidence.

    Checkpoints are hints only. The chunk's video/audio remains authoritative
    for spoken words; original timestamps prevent visual mapping drift.
    """
    source = Path(path)
    info = probe(source)
    if not info.has_video or info.duration <= 0 or max_checkpoints <= 0:
        return ()
    periodic = {
        0.0,
        max(0.0, info.duration / 2),
        max(0.0, info.duration - 0.5),
    }
    if len(periodic) > max_checkpoints:
        periodic_values = sorted(periodic)
        indexes = (
            {
                round(index * (len(periodic_values) - 1) / (max_checkpoints - 1))
                for index in range(max_checkpoints)
            }
            if max_checkpoints > 1
            else {0}
        )
        periodic = {periodic_values[index] for index in sorted(indexes)}
    try:
        candidates = _scene_candidates(source)
    except (OSError, subprocess.CalledProcessError):
        candidates = ()
    usable_candidates = sorted(
        {max(0.0, min(info.duration - 0.5, value)) for value in candidates}
    )
    # A scene candidate is useful only with context. Keep a bounded number of
    # well-spaced candidates and take stills before, at, and after each one.
    event_budget = max(0, (max_checkpoints - len(periodic)) // 3)
    if event_budget and usable_candidates:
        if len(usable_candidates) <= event_budget:
            selected_candidates = usable_candidates
        elif event_budget == 1:
            selected_candidates = [usable_candidates[len(usable_candidates) // 2]]
        else:
            indexes = {
                round(index * (len(usable_candidates) - 1) / (event_budget - 1))
                for index in range(event_budget)
            }
            selected_candidates = [
                usable_candidates[index] for index in sorted(indexes)
            ]
    else:
        selected_candidates = []
    event_times = {
        max(0.0, min(info.duration - 0.5, candidate + delta))
        for candidate in selected_candidates
        for delta in (-0.75, 0.0, 0.75)
    }
    times = sorted(periodic | event_times)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    checkpoints = []
    for index, relative in enumerate(times):
        output = destination / f"{source.stem}_visual_{index:02d}.png"
        reason = "periodic layout checkpoint"
        if any(abs(relative - candidate) < 0.01 for candidate in candidates):
            reason = "FFmpeg scene-change candidate"
        checkpoint = _extract_checkpoint(
            source, relative, original_offset, output, reason
        )
        if checkpoint is not None:
            checkpoints.append(checkpoint)
    return tuple(checkpoints)


def extract_label_checkpoints(
    path: str | Path,
    label_times: Mapping[str, float],
    output_dir: str | Path,
    *,
    max_checkpoints: int = 24,
) -> tuple[VisualCheckpoint, ...]:
    """Capture one still at each observed label's original-media timestamp.

    These frames are only for the label-only vision pass. The transcription
    continues to derive words and timestamps from the media chunks.
    """
    source = Path(path)
    info = probe(source)
    if not info.has_video or info.duration <= 0 or max_checkpoints <= 0:
        return ()
    items = sorted(label_times.items(), key=lambda item: (item[1], item[0]))
    if len(items) > max_checkpoints:
        indexes = (
            {
                round(index * (len(items) - 1) / (max_checkpoints - 1))
                for index in range(max_checkpoints)
            }
            if max_checkpoints > 1
            else {0}
        )
        items = [items[index] for index in sorted(indexes)]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    checkpoints = []
    for index, (label, timestamp) in enumerate(items):
        relative = max(0.0, min(info.duration - 0.5, timestamp))
        checkpoint = _extract_checkpoint(
            source,
            relative,
            0.0,
            destination / f"{source.stem}_label_{index:02d}.png",
            f"speaker-label occurrence: {label}",
        )
        if checkpoint is not None:
            checkpoints.append(checkpoint)
    return tuple(checkpoints)

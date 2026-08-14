"""Input connectors for local files and HTTP(S) media URLs."""

import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def resolve_source(source: str, directory: str | Path | None = None) -> Path:
    """Resolve a local path or download an HTTP(S) source to a temporary file."""
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"}:
        path = Path(source).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    target_dir = Path(directory) if directory else Path(tempfile.mkdtemp())
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (Path(parsed.path).name or "media-input")
    request = Request(
        source, headers={"User-Agent": "video-audio-transcription-agent/0.1"}
    )
    with urlopen(request, timeout=120) as response, target.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    return target

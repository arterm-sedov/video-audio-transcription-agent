"""Downloadable artifact packages with deterministic manifests."""

import hashlib
import json
import re
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def _safe_name(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip(" .")
    return name or "artifact"


def build_artifact_zip(
    files: list[str | Path], *, prefix: str = "transcription"
) -> Path | None:
    existing = [Path(path) for path in files if Path(path).is_file()]
    if not existing:
        return None
    destination = (
        Path(tempfile.mkdtemp()) / f"{prefix}_{datetime.now(UTC):%Y%m%d_%H%M%S}.zip"
    )
    manifest = {"created_at": datetime.now(UTC).isoformat(), "files": []}
    used: set[str] = set()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in existing:
            name = _safe_name(source.name)
            stem, suffix = source.stem, source.suffix
            counter = 2
            while name.lower() in used:
                name = f"{stem}_{counter}{suffix}"
                counter += 1
            used.add(name.lower())
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            archive.write(source, f"files/{name}")
            manifest["files"].append(
                {"name": name, "path": f"files/{name}", "sha256": digest}
            )
        archive.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
        )
    return destination

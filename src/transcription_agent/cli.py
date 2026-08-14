"""Command-line interface for the transcription agent."""

import argparse
import json
from dataclasses import replace

from .config import Settings
from .connectors import resolve_source
from .exporters import export_transcript
from .media import create_chunks
from .orchestrator import TranscriptionService
from .registry import JobRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="transcription-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-config")
    transcribe = subparsers.add_parser("transcribe")
    transcribe.add_argument("media")
    transcribe.add_argument("--provider-order")
    transcribe.add_argument(
        "--model",
        default=None,
        help="Model id, e.g. google/gemini-2.5-flash or qwen/qwen3.6-plus",
    )
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if args.command == "validate-config":
        settings.validate()
        print(
            json.dumps(
                {"provider_order": settings.provider_order, "model": settings.model}
            )
        )
        return 0
    if args.provider_order:
        settings = replace(
            settings, provider_order=tuple(args.provider_order.split(","))
        )
    if args.model:
        settings = replace(settings, model=args.model)
    settings.validate()
    source = resolve_source(args.media, settings.output_dir / "inputs")
    registry = JobRegistry(settings.database_path)
    job_id = registry.create(str(source), settings.provider_order[0], settings.model)
    try:
        registry.update(job_id, "chunking")
        info, chunks = create_chunks(
            source, settings.output_dir / "chunks", settings.chunk_seconds
        )
        registry.update(job_id, "transcribing")
        transcript = TranscriptionService(settings).transcribe_clips(
            str(source),
            [(chunk.start, str(path)) for chunk, path in chunks],
            duration=info.duration,
        )
        registry.update(job_id, "exporting")
        paths = export_transcript(transcript, settings.output_dir)
        from .artifacts import build_artifact_zip

        package = build_artifact_zip(list(paths.values()), prefix=source.stem)
        registry.update(job_id, "completed")
    except Exception as exc:
        registry.update(job_id, "failed", str(exc))
        raise
    output = {key: str(value) for key, value in paths.items()}
    output.update({"zip": str(package) if package else "", "job_id": str(job_id)})
    print(json.dumps(output, indent=2))
    return 0

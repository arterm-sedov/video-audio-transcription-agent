"""Optional Gradio interface for Hugging Face Spaces and local use."""

import logging
from pathlib import Path

from .config import Settings
from .exporters import export_transcript
from .media import create_chunks
from .orchestrator import TranscriptionService
from .progress import ProgressEvent
from .registry import JobRegistry

logger = logging.getLogger(__name__)


def transcribe_upload(
    file_path: str, provider_order: str, diarization: bool, progress=None
):
    settings = Settings.from_env()
    settings = settings.__class__(
        provider_order=tuple(
            item.strip() for item in provider_order.split(",") if item.strip()
        ),
        model=settings.model,
        chunk_seconds=settings.chunk_seconds,
        output_dir=settings.output_dir,
        database_path=settings.database_path,
        diarization_enabled=diarization,
        max_output_tokens=settings.max_output_tokens,
    )
    registry = JobRegistry(settings.database_path)
    job_id = registry.create(file_path, settings.provider_order[0], settings.model)

    def update(event: ProgressEvent) -> None:
        if progress is not None:
            progress(event.fraction, desc=event.message)

    try:
        registry.update(job_id, "chunking")
        info, chunks = create_chunks(
            file_path, settings.output_dir / "chunks", settings.chunk_seconds
        )
        registry.update(job_id, "transcribing")
        transcript = TranscriptionService(settings).transcribe_clips(
            file_path,
            [(chunk.start, str(path)) for chunk, path in chunks],
            duration=info.duration,
            progress=update,
        )
        registry.update(job_id, "exporting")
        outputs = export_transcript(transcript, settings.output_dir)
        registry.update(job_id, "completed")
    except Exception as exc:
        registry.update(job_id, "failed", str(exc))
        logger.exception("Transcription job %s failed", job_id)
        return f"## Transcription failed\n\n`{exc}`\n\nJob ID: `{job_id}`", []
    markdown = outputs["markdown"].read_text(encoding="utf-8")
    from .artifacts import build_artifact_zip

    zip_path = build_artifact_zip(list(outputs.values()), prefix=Path(file_path).stem)
    return markdown, [str(path) for path in outputs.values()] + (
        [str(zip_path)] if zip_path else []
    )


def build_demo():
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Install the ui extra to run the Gradio application"
        ) from exc
    with gr.Blocks(title="Video and Audio Transcription") as demo:
        gr.Markdown("# Video and Audio Transcription")
        upload = gr.File(type="filepath", label="Video or audio")
        provider = gr.Textbox(value="polza,gemini,openrouter", label="Provider order")
        diarization = gr.Checkbox(
            value=True, label="Use voice diarization when available"
        )
        run = gr.Button("Transcribe", variant="primary")
        transcript = gr.Markdown()
        outputs = gr.Files(label="Downloads")
        run.click(
            transcribe_upload,
            inputs=[upload, provider, diarization],
            outputs=[transcript, outputs],
            api_visibility="private",
            concurrency_limit=1,
            concurrency_id="transcription_jobs",
        )
    demo.queue(default_concurrency_limit=1, status_update_rate="auto")
    return demo


if __name__ == "__main__":  # pragma: no cover
    build_demo().launch(server_name="0.0.0.0", server_port=7860)

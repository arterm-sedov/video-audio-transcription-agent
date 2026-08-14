# AGENTS.md — Video and Audio Transcription Agent

## Mission

This repository is a focused, business-neutral video/audio transcription agent.
Keep it lean, deterministic, cross-platform, and suitable for local execution
and Hugging Face Gradio Spaces.

## Engineering rules

- Follow SDD before implementation and TDD for behavior changes.
- Prefer small, composable functions with one responsibility.
- Reuse existing contracts and utilities before adding abstractions.
- Do not add chat-agent, enterprise, or business-specific concepts here.
- Do not commit secrets, uploaded media, generated transcripts, caches, or virtual environments.
- Do not silently catch exceptions. Provider fallback boundaries must record the failure.
- Validate external data and preserve actionable error messages.
- Keep provider-specific code behind the provider interface.
- Preserve CLI, Gradio, and Hugging Face compatibility when changing shared code.

## Tooling

Use `uv`; do not add `requirements.txt` files or pip-only setup instructions.

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check src tests
uv run ruff format src tests
uv run transcription-agent --help
uv run transcription-agent validate-config
```

The project targets Python 3.12+ and uses `pyproject.toml` plus `uv.lock` as
the dependency source of truth.

## Architecture

- `src/transcription_agent/models.py` — stable segment/transcript contracts.
- `config.py` — environment-backed settings and validation.
- `media.py` — FFmpeg/PyAV probing and portable chunk creation.
- `providers.py` — Polza, direct Gemini, and OpenRouter adapters.
- `orchestrator.py` — provider fallback, progress, parsing, and merging.
- `exporters.py` — Markdown, JSON, SRT, and VTT outputs.
- `registry.py` — SQLite job state.
- `artifacts.py` — downloadable ZIP packages with manifest and hashes.
- `app.py` — Gradio UI and Hugging Face entrypoint.
- `skills/video-transcription/` — reusable prompt and agent skill.

## Provider behavior

Default order is configured by `TRANSCRIPTION_PROVIDER_ORDER` and is normally:

```text
polza,gemini,openrouter
```

Polza and OpenRouter use the OpenAI-compatible multimodal contract. Direct
Gemini uploads must be polled until the uploaded file is `ACTIVE` before
generation. Provider errors must be retained in job metadata and surfaced in
the UI/CLI.

Polza `cost_rub` is authoritative and must be converted with
`POLZA_RUB_TO_USD_RATE`; never treat it as USD.

## Speaker attribution

Use any visible active-speaker cue—green border, highlighted frame, colored
outline, focus box, or equivalent—as the primary visual signal. Voice
diarization is secondary. If evidence conflicts or is absent, use an explicit
`SpeakerN` label instead of guessing an identity.

## Media and portability

- Use `pathlib`, not hard-coded Windows paths.
- Resolve local paths and HTTP(S) sources through connectors.
- Prefer FFmpeg on `PATH`; fall back to the bundled `imageio-ffmpeg` binary.
- Use PyAV probing when `ffprobe` is unavailable.
- Temporary chunks belong under the configured output directory and must not be committed.
- Preserve audio when creating video chunks.

## Gradio/Hugging Face

- Keep long transcription jobs on the Gradio queue.
- Use explicit concurrency limits for provider work.
- Show progress through structured progress events.
- Keep API visibility private unless a public API is intentionally added.
- Store provider credentials in Hugging Face Space Secrets, never repository files.
- `app.py` must remain a direct Space entrypoint.

## Outputs and compatibility

Every completed job should produce Markdown, JSON, SRT, and VTT outputs plus a
ZIP artifact package. Keep timestamps chronological and offset chunk-local
timestamps to the original media timeline.

## Change verification

Before completion:

1. Add or update behavior tests first when changing contracts.
2. Run Ruff and the full pytest suite.
3. Run CLI/config smoke checks.
4. Construct the Gradio Blocks app in a clean process.
5. Verify `uv lock --check`.
6. Confirm `.env`, `.venv`, `.transcriptions`, caches, and media are ignored.
7. Update README/skill docs when workflows or configuration change.

Only create commits or push changes when explicitly requested.

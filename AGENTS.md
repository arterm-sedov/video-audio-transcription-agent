# AGENTS.md — Video and Audio Transcription Agent

## Mission

This repository is a focused, business-neutral video/audio transcription agent.
Keep it lean, deterministic, cross-platform, and suitable for local execution
and Hugging Face Gradio Spaces.

## Engineering rules

- Follow SDD before implementation and TDD for behavior changes.
- Prefer small, composable functions with one responsibility.
- Reuse existing contracts and utilities before adding abstractions.
- DRY: extract shared helpers on second use so behavior lives in exactly one place.
- Do not add chat-agent, enterprise, or business-specific concepts here.
- Do not commit secrets, uploaded media, generated transcripts, caches, or virtual environments.
- Do not silently catch exceptions. Provider fallback boundaries must record the failure.
- Validate external data and preserve actionable error messages.
- Keep provider-specific code behind the provider interface.
- Keep provider calls agnostic to transport: use a hosted media reference when
  the provider and media type support it, and fall back to inline base64
  otherwise. A media type a provider does not accept is a routing decision
  (use base64), not a failure, so it must not appear as an error note.
- Bound hosted uploads with TRANSCRIPTION_UPLOAD_TIMEOUT (default 30s) so a
  hung POST raises and the orchestrator falls back to inline base64.
- A present TRANSCRIPTION_<PROVIDER>_PROXY (even empty) wins; only a missing
  key inherits TRANSCRIPTION_PROXY.
- Size chunks from the model's context window and worst-case token-per-second
  rate; treat fixed chunk seconds as an explicit override, not the default.
- If an auto-sized chunk is rejected as an invalid/oversized provider request,
  retry the affected job or interval with a smaller explicit bounded chunk size;
  do not turn that workaround into the global default.
- When regenerating or comparing a transcript, never overwrite an existing
  transcript implicitly. Use a distinct output name and verify the old file's
  hash before and after the run.
- Do not start a parallel or identical retry while a provider attempt is still
  live. Stop it once when authorized or let its bounded failure resolve; a
  client-side timeout/kill may not cancel upstream work or its billing.
- Main chunks are independent and may be launched concurrently with a bounded
  stagger. Use a small overlap and merge only a proven repeated word sequence;
  never discard a non-identical turn merely because it is near a boundary.
- Keep the canonical prompt as the only prompt resource. A custom `--prompt`
  may add task-specific context only when it preserves the canonical prompt's
  completeness, visual-attribution, and output-format rules.
- Never hardcode hosts, addresses, credentials, or account identifiers in
  source or committed docs; routes and proxies come from per-provider
  environment variables.
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
- `media.py` — FFmpeg/PyAV probing, portable chunk creation, and bounded visual
  checkpoints around periodic and scene-change candidates.
- `chunking.py` — chunk planning driven by model context windows and token rates.
- `limits.py` — per-model context-window resolution used by chunk planning.
- `upload_adapters.py` — hosted media references (URL/file id) with graceful
  inline-base64 fallback per provider and media type.
- `model_registry.py` / `models_catalog.py` — live and offline model discovery.
- `providers.py` — Polza, direct Gemini, and OpenRouter adapters.
- `orchestrator.py` — provider fallback, progress, parsing, and merging.
- `normalization.py` — strict JSON mapping and label-only segment rewriting.
- `exporters.py` — Markdown, JSON, SRT, and VTT outputs.
- `registry.py` — SQLite job state.
- `artifacts.py` — downloadable ZIP packages with manifest and hashes.
- `app.py` — Gradio UI and Hugging Face entrypoint.
- `prompt-transcription.md` — the single canonical prompt loaded by providers
  and referenced by the skill; do not create a second prompt resource.
- `.agents/skills/transcribe-video/` — reusable workflow and agent skill that
  links to the canonical prompt and these repository utilities.

## Provider behavior

Default order is configured by `TRANSCRIPTION_PROVIDER_ORDER` and is normally:

```text
polza,openrouter,gemini
```
The first entry is the default provider for the CLI and GUI; later entries are
fallbacks tried in order when a provider call fails.

Polza and OpenRouter use the OpenAI-compatible multimodal contract. Direct
Gemini uploads must be polled until the uploaded file is `ACTIVE` before
generation. Provider errors must be retained in job metadata and surfaced in
the UI/CLI.

After a successful transcription, the orchestrator may make one label-only
vision request using a bounded still at each observed label's first occurrence
(with collected scene/layout checkpoints only as fallback). Accept only mappings
between labels already observed in the transcript; apply them to speaker fields
only. A failed or invalid normalization leaves words,
timestamps, segment count, and ordering untouched and is recorded as a note.

Polza `cost_rub` is authoritative and must be converted with
`POLZA_RUB_TO_USD_RATE`; never treat it as USD.

OpenRouter video requests use inline base64 and can hit a provider payload
limit even when the model context window is large. If OpenRouter returns a
payload-size error, use a smaller explicit per-job chunk override; do not
reuse the same auto-sized chunk or route the request through Polza SOCKS.

## Speaker attribution

Use any visible active-speaker cue—green border, highlighted frame, colored
outline, focus box, or equivalent—as the primary visual signal. Voice
diarization is secondary. If evidence conflicts or is absent, use an explicit
`SpeakerN` label instead of guessing an identity.

Treat provider-produced names as candidate aliases. Before delivery, inspect
frames at the candidate's turns and nearby moments, map aliases to one
canonical displayed name when the current green active-speaker cue supports
it, and preserve the displayed script. Normalize only speaker labels; never
rewrite spoken words. Do not retain phonetic/ASR variants, OCR errors,
truncations, or company-suffixed variants for the same visually confirmed
participant. Use `SpeakerN` when frames do not establish identity or exact
spelling. OCR may support reading a name but is not authoritative over the
current active border and layout.

Do not assume a fixed meeting-grid geometry or that a cue has one fixed color,
shape, contrast, or location. Inspect an actual representative frame, verify
the tile bounds and current layout, and interpret every color/brightness
change, outline, background, avatar ring/illumination, border, badge, status
icon, or label according to whether it identifies the active speaker. Cues may
appear on any side, in the center, around an avatar, or around a tile. A cue
that is an icon is not thereby invalid; discard it only when it is demonstrably
unrelated to speaker activity.

Visual checkpoint labels use original-media time; transcript timestamps remain
clip-relative. FFmpeg scene/layout detections are candidate events only. Check
frames before/at/after each candidate, rebuild the current mapping, and pass
the stills with compact timestamp/reason metadata as supplementary evidence.
Never infer a speaker change, silence, timestamp shift, or omitted audio from a
scene score alone.

## Media and portability

- Use `pathlib`, not hard-coded Windows paths.
- Resolve local paths and HTTP(S) sources through connectors.
- Prefer FFmpeg on `PATH`; fall back to the bundled `imageio-ffmpeg` binary.
- Use PyAV probing when `ffprobe` is unavailable.
- Temporary chunks belong under the configured output directory and must not be committed.
- Put one-off diagnostics and scratch scripts under the ignored `.tmp/` directory
  (legacy root `.tmp_*.py` files are ignored too); put reusable helpers under
  the repository's source or test tree and document their contract.
- Preserve audio when creating video chunks.

## Transcript gap verification

A large timestamp gap is not by itself evidence of silence or omitted speech:
a single speaker turn may span the interval while the model emits only its
start timestamp. When a gap looks suspicious, extract a short recheck clip
with padding on both boundaries, run the canonical transcription prompt, and
map the clip-relative timestamps back to the original timeline. Use audio
silence/energy analysis as supporting evidence. If the recheck contains speech,
do not invent a silence marker or split a continuous turn solely because its
timestamps are sparse. If it proves that speech is absent from the main
transcript, replace only the affected interval, preserve original offsets, and
deduplicate overlap from the padded retry.

Do not repeat an identical provider request after a failure. Change a
diagnostic variable (for example, the affected interval, bounded chunk size,
transport, or model), or stop and report the unchanged failure.

The quality gate is intentionally narrow: inspect only long, low-word-density
turns and require voice activity before a padded 60--120 second recheck. A
recheck replaces an interval only when it proves materially more words there;
everything outside that interval remains unchanged.

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

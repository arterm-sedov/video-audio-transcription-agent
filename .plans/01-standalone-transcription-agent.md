# Plan: standalone-transcription-agent

## Goal

Build a business-neutral video/audio transcription agent with configurable Polza, direct Gemini, and OpenRouter providers, speaker attribution, persistent jobs, and Markdown/JSON/SRT/VTT exports.

## Prerequisites

- [x] Confirm reusable media/provider patterns in `cmw-platform-agent`.
- [ ] Implement a dependency-light core with optional provider/UI integrations.
- [ ] Verify deterministic unit behavior before live provider calls.

## Phases

### Phase 1: Core contracts

- [ ] Define settings, segment, job, provider, and export contracts.
- [ ] Implement timestamp normalization, chunk planning, registry, and exporters.
- [ ] Add behavior-first tests.

### Phase 2: Provider and orchestration layer

- [ ] Implement configurable provider chain.
- [ ] Implement chunk transcription orchestration and timestamp/speaker merge.
- [ ] Add optional visual/audio evidence fields without requiring local diarization.

### Phase 3: Interfaces and skill

- [ ] Add CLI commands and Gradio job UI.
- [ ] Add bundled transcription skill and prompt.
- [ ] Add configuration and operational documentation.

## Affected Files

| File | Change |
|------|--------|
| `src/transcription_agent/` | New standalone implementation |
| `tests/` | TDD coverage for core behavior and provider routing |
| `skills/video-transcription/` | Reusable skill and prompt |

## Verification

- [ ] `python -m pytest -q`
- [ ] `python -m transcription_agent --help`
- [ ] `python -m transcription_agent validate-config`
- [ ] Optional live provider smoke test when keys are configured.

## Dependencies

- Python 3.12+ with `uv` for dependency and lockfile management.
- Optional: `google-genai`, `openai`, `gradio`, `av`, and `ffmpeg` for live media/provider work.

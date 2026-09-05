# Research plan: video-transcription model catalog (2026-08-18)

## Scope

Determine which models in the Polza/OpenRouter/Gemini union are suitable for this repository's video-transcription workflow, whether Polza exposes a batch equivalent, whether batch changes quality/semantics, and how to bias the selector toward Russian-capable models.

## Decision criteria

1. Video input is necessary but not sufficient: the model must actually process speech/audio from video.
2. A documented batch path must accept multimodal video/audio content to be useful here; text-only batching is out of scope.
3. Russian grades distinguish direct Russian-video evidence from provider/model language support and from unverified claims.
4. Exclusions are conservative: hard exclusion requires direct project evidence or an explicit modality/API mismatch; absence of public Russian benchmarks is not an exclusion.

## Planned evidence tracks

- Provider API capability and batch semantics: Polza, OpenRouter, Gemini.
- Candidate model modality and language support: Gemini, Qwen, GLM, MiniMax, plus live project probes.
- Implementation implications: catalog metadata, filtering, ordering, tests.

# Gateway Modality Limitations — opencode.ai / zen / go

**Date:** 2026-08-17
**Scope:** Transcription-agent model/proxy routing. Findings below are about the
**opencode.ai** gateway (and its `zen` / `go` endpoints), which is a *separate*
route from the three providers wired in `providers.py` (`polza`, `openrouter`,
`gemini`). They describe what the gateway will not carry, not what the underlying
models can do on other providers.

## Summary

| Model | Video | Audio | Verdict via opencode.ai gateway |
|-------|-------|-------|--------------------------------|
| **GLM-5.2** (`z-ai/glm-5.2`) | Needs `video_placeholder` config that the gateway does not expose | `audio_url` rejected outright | Not usable through this gateway |
| **qwen3.8-max** | — | — | 503 — endpoint unavailable (alias not in `models_catalog.yaml`; closest catalog entry is `qwen/qwen3.7-max`) |
| **kimi-k3** (`moonshotai/kimi-k3`) | Accepts frames | Explicitly reports no audio access | Vision-only through this gateway |

## What this means for routing

- The opencode.ai / zen / go endpoints are **not a viable transcription route** for
  this agent.
- Gemini (direct, via `GeminiProvider`, or via Polza) remains the only working
  provider for this use case in this repo.
- Do **not** record these as model defects in `models_catalog.yaml`. The catalog
  is an offline fallback of model→provider availability and prices; it should not
  encode transient gateway breakage. These notes are the right place.

## Notes / caveats

- `openrouter` in `providers.py` points at `openrouter.ai`, not opencode.ai. The
  failures here are specific to the opencode.ai gateway and do not necessarily
  imply `openrouter` is broken for the same models.
- `qwen3.8-max` is not a catalog-listed model; verify the exact alias before
  treating the 503 as a model limitation.
- Re-test if the opencode.ai gateway is updated to expose `video_placeholder`
  and accept `audio_url`; these conclusions are gateway-version dependent.

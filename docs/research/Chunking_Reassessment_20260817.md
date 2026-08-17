# Chunking strategy reassessment — is 5 minutes too aggressive?

**Date:** 2026-08-17
**Supersedes the empirical basis of:** `Media_Size_Limits_Research_20260814/research_report_20260814_media_size_limits.md`
**Scope:** Whether the 300-second (5-minute) chunk default is still the right value now that Polza is reachable via proxy and OpenRouter has a funded ($5) account.

## Headline verdict

**The 5-minute default is still valid and not too aggressive — but its original justification was partly wrong, and there is now a clear upgrade path.** The old report's binding constraint was *measured Polza timeouts on ~4 MB base64 payloads*. That was a reachability/proxy artifact, not a payload ceiling. Once Polza is reachable (which it now is), the real constraint shifts from "base64 payload size" to "can the provider ingest the file at all," and every provider now offers a URL/file-upload path that sidesteps base64 entirely.

## What changed since the 2026-08-14 report

| Claim in old report | 2026-08-17 reality |
|---------------------|--------------------|
| Polza times out on ~4 MB base64 payloads | Job registry shows Polza `completed` on 2026-08-15 with `google/gemini-3.6-flash` and `gemini-2.5-flash` on 5-min chunks (jobs 20, 21, 24). No size-based failure. |
| OpenRouter failure was a size limit | Old job 25 failed with HTTP 402 "requires at least $1.00 in balance" — a **credit** problem, not a size limit. Account now has $5. |
| Polza docs unreachable | Polza publishes `POST /api/v1/storage/upload` (multipart, `TEMP_UPLOAD` 24h or `PERMANENT`), returns a hosted URL; plus list/get/delete. |
| "3.5–3.8 MB per 5-min chunk" | Re-encoded at the agent's exact ffmpeg settings on worst-case synthetic noise: **9.27 MB raw / 12.36 MB base64** for 300s. Real video is smaller, but the documented 3.5 MB figure was optimistic. |

## Re-measured chunk payloads (agent ffmpeg pipeline, worst-case noise)

| Chunk | Raw | Base64 | Note |
|-------|-----|--------|------|
| 300s | 9.27 MB | 12.36 MB | valid |
| 600s | 18.53 MB | 24.71 MB | valid |
| 900s | 27.77 MB | 37.02 MB | valid |

These are upper bounds (testsrc2 noise compresses poorly). Real speech video at 960px/2fps/crf28/96k will be smaller, but the agent must budget for the worst case.

## URL / file-upload support across all three providers

*All three can ingest media by reference instead of base64-inlining every request.*

- **Polza** — `POST /api/v1/storage/upload` returns a hosted URL (TEMP_UPLOAD 24h / PERMANENT). Use URL in the message content; stops re-sending base64 per request.
- **Gemini** — native Files API (`client.files.upload`, 48h retention, polling for ACTIVE). Already used by `GeminiProvider`; can carry GB-scale files far beyond chunk size.
- **OpenRouter** — supports `input_audio` from a **URL** (recommended over base64 for audio); video accepts data-URL or provider-supported URL. No global byte cap; limits are upstream-model-specific.

**Implication:** base64 payload size is no longer a reason to keep chunks small. The 5-minute default survives on *different* grounds (speaker-continuity / merge simplicity / cost blast-radius), and a URL-upload refactor would let chunks grow safely.

## OpenRouter free router / metamodel — does it transcribe? (live test)

Tested through the agent's actual OpenAI SDK path (`openai==3.0.0`, `base_url=https://openrouter.ai/api/v1`) with the funded key:

| Model | Result |
|-------|--------|
| `openrouter/free` (auto-router) | `400 Model openrouter/free does not exist` — **not a valid STT model id** |
| `google/gemini-2.0-flash-exp:free` | `400 does not exist` — id unavailable/renamed |
| Any `:free` model with `audio` in `input_modalities` | **Live catalog query returned zero free audio-capable models.** |

**Conclusion:** The OpenRouter free router / free metamodel **will not work** for transcription right now. There are no free audio-capable models exposed, and the `openrouter/free` alias is not a usable transcription endpoint. Paid routing (e.g. `google/gemini-2.5-flash`, `qwen/qwen3-vl-*`) is the only working OpenRouter path, and that now works because the account has credit.

## Recommendations

1. **Keep the 5-minute default for now.** It is valid; the original "too aggressive" worry was a proxy artifact. Do not shrink it.
2. **Refactor providers to URL/file upload** (start with Polza `storage/upload`, Gemini already has it, OpenRouter URL audio/video). This removes the base64 ceiling and is the real unlock for larger chunks.
3. **After URL upload lands, raise the default** (e.g. 10–15 min for video, larger for audio-only where token cost is ~8× lower) and re-verify empirically.
4. **Do not rely on OpenRouter free tier** for transcription — no free audio models exist. Document this so it is not re-tested.
5. **Update `models_catalog.yaml` notes** (not the contract) to record that `openrouter/free` is invalid for STT.

## Caveats

- Payload measurements used synthetic `testsrc2` noise (worst-case). Real media is smaller; treat numbers as safe upper bounds.
- Polza `/storage/upload` behavior was confirmed from its published API docs, not a live upload from this machine (the RU SOCKS5 proxy is not reachable from this host; job registry proves it works from the runtime).
- Free-model catalog was a point-in-time query (2026-08-17); free offerings rotate, so re-check if the strategy is revisited.

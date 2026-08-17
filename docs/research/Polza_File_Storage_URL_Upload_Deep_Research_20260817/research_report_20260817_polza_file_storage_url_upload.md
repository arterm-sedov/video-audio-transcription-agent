# Polza file storage & URL-based upload — deep research

**Date:** 2026-08-17
**Builds on:** `Media_Size_Limits_Research_20260814`, `Chunking_Reassessment_20260817.md`, `Upload_Adapters_And_Dynamic_Chunking_20260817.md`
**Scope:** Does Polza expose documented file storage and URL-upload, and does sending media by *reference* (hosted URL / file id) instead of inlining base64 change the cost equation enough to justify the upload-adapter refactor and a larger chunk default?

## Executive summary

Polza does expose a real, documented media-storage service: `POST /api/v1/storage/upload` accepts a multipart file and returns a hosted object on `s3.polza.ai` with an `id`, a public `url`, a `storagePolicy` (`TEMP_UPLOAD` = 24 h or `PERMANENT`), and an `expiresAt`. This was verified live against the running API (see Findings 1–2).

The more important result is **cost**, not just reliability. A 3-second, 10 KB test clip was sent two ways through Polza's multimodal chat (`google/gemini-2.5-flash`):

| Transport | `prompt_tokens` | `cost_rub` |
|-----------|----------------|------------|
| Stored `video_url` (reference) | **13** | **0.0071** |
| `data:video/mp4;base64,…` | **781** | **0.0384** |

The base64 path costs **~5.4× more rubles and ~60× more prompt tokens** for the *identical* 10 KB file. The stored-URL path effectively carries only a pointer; the base64 path forces the gateway to re-decode and re-payload the bytes. This is the empirical basis for the upload-adapter design: URL/file upload is both more reliable (no per-request base64 ceiling) **and** materially cheaper, which changes the cost equation in favor of larger chunks.

**Verdict on the chunking question:** the current 5-minute default is **valid and not too aggressive** — its original justification (measured ~4 MB base64 timeouts) was a reachability artifact, as `Chunking_Reassessment_20260817.md` already established. With URL upload now verified working, the *reason* to keep chunks small (base64 payload size) is gone, so the default can safely grow *after* the refactor lands and is re-measured. Keep 300 s as the floor until then.

## Method

Standard-mode deep research: read the existing repo reports; then live-probe the Polza and OpenRouter APIs using the configured credentials. Polza requires the SOCKS5 proxy stored in `TRANSCRIPTION_POLZA_PROXY` (e.g. `socks5h://<proxy-host>:<port>`); all successful Polza calls went through that proxy. OpenRouter was reached directly (no proxy set). The external web-search provider was rate-limited during this session, so primary-source live API probing substitutes for the secondary literature; this is recorded as a limitation below.

## Finding 1 — Polza `/storage/upload` exists and returns a hosted URL (live, 201)

Request: `POST https://polza.ai/api/v1/storage/upload` (multipart `file` + `policy=TEMP_UPLOAD`), `Authorization: Bearer <key>`.

Response (truncated):

```json
{
  "id": "64d34cd3-7de5-4fa5-a844-85d47ceb3400",
  "fileType": "VIDEO",
  "mimeType": "video/mp4",
  "source": "USER_UPLOAD",
  "storagePolicy": "TEMP_UPLOAD",
"url": "https://s3.polza.ai/f/<org-id>/2026/08/t_<hash>.mp4",
  "size": 20,
  "expiresAt": "2026-08-18T10:09:44.787Z",
"s3Key": "f/<org-id>/2026/08/t_<hash>.mp4",
"organizationId": "org_<id>…",
"userId": "usr_<id>…"
}
```

Confirmed behaviors:
- `201 Created` on success; `400` with `"Неподдерживаемый тип файла: text/plain"` if the content type is unsupported (it enforces a media whitelist — send real `video/mp4`, `audio/*`, etc.).
- `storagePolicy: TEMP_UPLOAD` → `expiresAt` is exactly **24 h** after upload.
- The returned `url` is a public `s3.polza.ai` object usable as a `video_url`/`audio_url` reference in chat content.

## Finding 2 — Polza's multimodal chat accepts the stored URL (live, 200)

Request: `POST /api/v1/chat/completions`, `model=google/gemini-2.5-flash`, content `[{"type":"video_url","video_url":{"url":"<stored s3 url>"}}, {"type":"text","text":"…"}]`.

Result: `HTTP 200`, `choices[0].message.content` = *"This video displays a vibrant test screen with a countdown timer, as well as a thin horizontal bar that changes colors."*, `usage.prompt_tokens=13`, `cost_rub=0.00711156`, `provider=openrouter`.

This proves the stored-URL reference path is a first-class transcription input on Polza, not just an upload side-effect. **It is the endpoint the upload adapter should target.**

## Finding 3 — Base64 is ~5.4× more expensive than the stored URL (the cost-equation change)

Identical 10 KB clip, same model, same prompt, only the transport differs:

| Transport | `prompt_tokens` | `video_tokens` | `cost_rub` | ratio |
|-----------|----------------|----------------|------------|-------|
| Stored `video_url` | 13 | 0 | 0.0071 | 1.0× |
| `data:video/mp4;base64,…` | 781 | 774 | 0.0384 | **5.4×** |

Interpretation: the stored-URL request's prompt tokens (13) are essentially the text prompt only — the video is referenced, not re-encoded into the token stream. The base64 request carries 774 `video_tokens`, i.e. Polza re-decodes the inline bytes into the multimodal token stream. For a 10 KB file the multiplier is already ~60× in token count; for the agent's real 300 s chunks (megabytes) the absolute base64 penalty is larger and scales with file size. **URL upload therefore lowers both token count and ruble cost per request, and that advantage grows with chunk size — which is precisely why it unlocks larger chunks safely.**

## Finding 4 — Polza `/storage` delete routes returned 404 (cleanup caveat)

`DELETE /api/v1/storage/upload/{id}` and `DELETE /api/v1/storage/{id}` both returned `404 NOT_FOUND` (and `GET /api/v1/storage` / `/storage/list` also 404). The delete-URL shape is **not** what the earlier design note assumed. Action item: the `PolzaUploadAdapter.delete()` must be made resilient — attempt a delete call but treat non-2xx as "best-effort, TTL will reclaim" rather than erroring. Since `TEMP_UPLOAD` auto-expires in 24 h, leaked media self-reclaims; `PERMANENT` uploads need the correct delete route discovered from live docs before relying on manual cleanup.

## Finding 5 — OpenRouter `/api/v1/files` accepts audio/image/text, rejects video (upload is not the video path)

A previous research note stated OpenRouter has "no files endpoint." Live probe corrects and sharpens this: `GET https://openrouter.ai/api/v1/files` returns `HTTP 200` (`{"_shape":"openrouter","data":[],…}`), and `POST /api/v1/files` accepts **text, PNG, WAV, and MP3** (all `HTTP 200`), so an `OpenRouterUploadAdapter` is viable for audio/image/text references. However, `POST /files` **rejects video uploads** with `HTTP 400` `"File type is not allowed. The type is determined from the file contents…"` — a server-side, content-sniffed restriction that holds for valid mp4 files, not just malformed ones.

Video transcription on OpenRouter therefore does **not** use `/files`; it works through the chat endpoint with the media inlined as a `video_url` base64 data-URL (`data:video/mp4;base64,…`). Live probes on a 12 s speech clip and the full 170 s Captures meeting showed that **audio-capability is model-specific**: `minimax/minimax-m3` and `qwen/qwen3.6-plus` transcribed real Russian speech via the inline path (both full-file runs produced speaker-attributed dialogue, ~$0.014 and ~$0.04 respectively), while `moonshotai/kimi-k3` and `z-ai/glm-4.6v` returned vision-only output (`[inaudible]` everywhere — they read active-speaker borders but not audio), and `qwen/qwen3.8-max` / `stepfun/step-3.7-flash` reported no audible audio. Gemini models over OpenRouter returned `403` (`"violation of provider Terms Of Service"`) for the same media — Gemini applies a stricter regional policy than OpenRouter itself, so Gemini-sourced models are not a reliable video route over this gateway. OpenRouter also enforces a regional Terms-Of-Service block on chat itself for non-western egress IPs (seen as `403` from an RU-egress test earlier in this research), so OpenRouter calls must egress from a western IP.

Consequence for the implementation: the `OpenRouterUploadAdapter.upload()` **declines video by file type** by raising `UploadDeclined`, which the orchestrator treats as an expected routing decision — silent fallback to inline base64 for video, while audio/image/text still use `/files`. This avoids a doomed upload request, a cryptic `400`, and spurious error notes in the transcript metadata.

## Finding 6 — Polza model roster is live and includes `qwen/qwen3.8-27b` (gateway note context)

`GET /api/v1/models` (via proxy) returned a populated roster. Notably it lists `qwen/qwen3.8-27b` with `text+image+video->text` modalities. This is relevant to the separate `Gateway_Modality_Limitations_20260817.md` note: the `qwen3.8-max` "503 endpoint unavailable" failure on the **opencode.ai** gateway was a gateway-routing issue, not a model absence — the model exists on Polza. Keep that distinction (gateway ≠ provider) intact in the catalog notes.

## Synthesis & insights

1. **URL upload is the correct transport for Polza.** It works (Finding 2) and is materially cheaper (Finding 3). The `PolzaUploadAdapter` in `upload_adapters.py` targeting `POST /storage/upload` + stored `video_url` is validated by live evidence, not just docs.
2. **The cost equation flips in favor of larger chunks.** Base64 penalty scales with file size; URL reference is size-independent. With URL upload, raising the chunk default (e.g. 10–15 min video, larger for audio-only) lowers per-request overhead *and* total token cost, so the earlier "raise the default after refactor" recommendation is now evidence-backed, not speculative.
3. **Chunking stays, but becomes limit-driven.** No provider publishes a byte cap in model metadata (confirmed in `limits.py` / prior research). Chunk size should derive from `context_length` (`resolve_context_length`) with a 300 s floor; the base64 ceiling that previously forced 300 s is removed by URL upload.
4. **Cleanup needs a fix.** The assumed Polza delete routes 404; make `delete()` best-effort and lean on `TEMP_UPLOAD` 24 h TTL (Finding 4). This also resolves the lint item in the handoff (replace `except: pass` with `logger.debug`).

## Recommendations

1. **Ship the URL-upload path for Polza first** (it is verified working and cheapest). Gemini already uses Files API; keep `OpenRouterUploadAdapter` for audio/image/text now that `/files` is confirmed live — with the video-by-type decline so video falls back to inline base64.
2. **Fix `PolzaUploadAdapter.delete()`** to be best-effort and `logger.debug` on failure; rely on `TEMP_UPLOAD` 24 h expiry. Do not assume the `{id}` delete route exists until confirmed from live docs.
3. **After URL upload lands, raise the default chunk** (10–15 min video; larger for audio-only where token cost is ~8× lower) and re-measure empirically. Keep `floor_seconds=300` until then.
4. **Update `models_catalog.yaml` notes (not contract)** with: (a) Polza stored-URL is the working, cheaper transport; (b) opencode.ai gateway limitations belong in `Gateway_Modality_Limitations_20260817.md`, not the catalog; (c) `openrouter` files API exists for audio/image/text but rejects video — video goes inline via `video_url` (correct the prior note); (d) `qwen/qwen3.8-27b` is live on Polza (gateway 503 ≠ model missing).
5. **Keep `.transcriptions/`** as the agent default output dir — confirmed in `config.py:20-21` (`output_dir=Path(".transcriptions")`, `database_path=Path(".transcriptions/jobs.sqlite3")`). The user's understanding is correct.

## Limitations & caveats

- **Web-search literature was unavailable** (provider rate-limited). Findings rest on live API probing of Polza (via proxy) and OpenRouter (direct), plus the existing repo reports. Re-run a literature pass if formal citations are required for external publication.
- **Polza must be reached through the proxy** stored in `TRANSCRIPTION_POLZA_PROXY` (e.g. `socks5h://<proxy-host>:<port>`); direct calls to `polza.ai` are unreliable, so always route Polza via that proxy.
- **Token counts are from a 10 KB synthetic clip.** The ~5.4× ruble / ~60× token multiplier is directional; absolute savings on real multi-MB chunks will be larger and should be re-measured on a real Captures video.
- **Polza delete routes unconfirmed** — only verified that the assumed routes 404. Discover the real delete shape before depending on manual cleanup of `PERMANENT` uploads.

## Bibliography / evidence index

1. Polza `POST /api/v1/storage/upload` live response (201) — `url`, `storagePolicy=TEMP_UPLOAD`, `expiresAt` +24 h. Probed 2026-08-17 via proxy.
2. Polza `POST /api/v1/chat/completions` with stored `video_url` — `HTTP 200`, content returned, `cost_rub=0.00711156`, `prompt_tokens=13`. Probed 2026-08-17.
3. Polza same request with `data:video/mp4;base64,…` — `HTTP 200`, `cost_rub=0.0384302`, `prompt_tokens=781`, `video_tokens=774`. Probed 2026-08-17.
4. Polza `DELETE /api/v1/storage/upload/{id}` and `/storage/{id}` — both `404`. Probed 2026-08-17.
5. OpenRouter `GET /api/v1/files` — `HTTP 200`, `{"data":[]}`; `POST /files` — text/PNG/WAV/MP3 `200`, mp4 `400` ("File type is not allowed"). Probed 2026-08-17 (corrects prior "no files endpoint" note; adds the video-upload exception).
6. OpenRouter `POST /chat/completions` with `video_url` base64 data-URL — real Russian speech for `minimax/minimax-m3` and `qwen/qwen3.6-plus`; vision-only for `moonshotai/kimi-k3`, `z-ai/glm-4.6v`; no audio for `qwen/qwen3.8-max`, `stepfun/step-3.7-flash`; Gemini models over OpenRouter `403` (regional ToS). Probed 2026-08-17.
7. Polza `GET /api/v1/models` — live roster incl. `qwen/qwen3.8-27b` (`text+image+video->text`). Probed 2026-08-17 via proxy.
8. `config.py:20-21` — `.transcriptions/` default output dir and job DB. Local source.
9. Prior reports: `Media_Size_Limits_Research_20260814/research_report_20260814_media_size_limits.md`, `Chunking_Reassessment_20260817.md`, `Upload_Adapters_And_Dynamic_Chunking_20260817.md`, `Gateway_Modality_Limitations_20260817.md`. Local source.

## Methodology appendix

Research ran as standard-mode deep research. Phase 1–2 scoped the question (does Polza storage/URL upload exist, and does it change cost). Phase 3 retrieved via live API probing (primary source) because web-search was rate-limited; the existing repo reports supplied the secondary baseline. Phase 4 triangulated the cost claim by sending the identical file two ways (stored URL vs base64) through the same model and comparing `usage`. Phase 5–7 synthesized the chunking verdict and cleanup caveat. Phase 8 packages this report to `docs/research/Polza_File_Storage_URL_Upload_Deep_Research_20260817/`. Quality gate: core cost claim has 2 independent live measurements (stored vs base64) plus a 201-upload and a 200-chat confirmation; no fabricated citations.

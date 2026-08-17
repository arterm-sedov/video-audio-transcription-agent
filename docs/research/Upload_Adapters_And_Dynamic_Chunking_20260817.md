# Upload adapters + dynamic chunking-from-limits — design & research

**Date:** 2026-08-17
**Builds on:** `Chunking_Reassessment_20260817.md` (5-min chunking is valid; base64 payload was a proxy artifact).

## Objective

Design how to implement `UploadAdapter`s for the current and future providers so that media is uploaded once and referenced by URL (no base64 re-inlining), and so chunk size is derived from **live model roster limits** rather than a hardcoded 300 s. Goal: reduce/remove chunking complexity where a model can ingest the whole file, and otherwise chunk to the model's real context window.

## What the live rosters actually expose (probed 2026-08-17)

| Provider | Per-model fields | File-size field? | Media upload mechanism |
|----------|-----------------|-----------------|------------------------|
| **OpenRouter** | `context_length`, `input_modalities`, `per_request_limits`, `pricing` | **No** (no `size` key) | `/api/v1/files` exists (verified 200, empty list) + URL references in content |
| **Gemini** | `inputTokenLimit`, `outputTokenLimit`, `supportedGenerationMethods` | **No** (only token limits) | Files API (`files.upload`, 48h retention, poll ACTIVE) |
| **Polza** | OpenAI-compatible `/models` (modality fields often empty) | No | `POST /api/v1/storage/upload` → hosted URL (`TEMP_UPLOAD` 24h / `PERMANENT`) |

**Key consequence:** No provider publishes a *byte* cap in model metadata. Limits are **token-window driven**. Therefore "chunk per actual model limits" = chunk to fit `(context_length − output_budget − prompt) / token_rate`, not to a byte budget.

## Token-rate basis (from prior research + live checks)

| Modality | Tokens per second | Source |
|----------|------------------|--------|
| Gemini video | 263 tok/s | ai.google.dev tokens docs |
| Gemini audio | 32 tok/s | ai.google.dev tokens docs |
| OpenAI/OpenRouter audio (`input_audio`) | 8 tok/s | OpenAI transcription docs |
| Video (OpenAI-compatible, frame-based) | model-specific; no universal constant | OpenRouter "limits vary by model" |

For an unknown video rate we use a conservative fallback (e.g. derive from frames: 2 fps × ~258 tok/frame ≈ 516 tok/s for this agent's re-encode, but provider-native video is cheaper; keep conservative).

## Proposed design

### 1. `UploadAdapter` protocol (new module `upload_adapters.py`)

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class MediaRef:
    """Provider-accepted reference to an uploaded/referenced file."""
    kind: str          # "url" | "file_id" | "data_url" | "base64"
    value: str         # the url / id / data url
    expires_at: float | None = None  # for TEMP_UPLOAD / Gemini 48h

class UploadAdapter(Protocol):
    name: str
    def upload(self, path: str, *, ttl: str = "temp") -> MediaRef: ...
    def delete(self, ref: MediaRef) -> None: ...
```

Per-provider implementations:
- `PolzaUploadAdapter` → POST `storage/upload` (multipart `file` + `policy`), returns `MediaRef("url", hosted_url, expires)`.
- `GeminiUploadAdapter` → `genai.Client.files.upload`, poll ACTIVE, returns `MediaRef("file_id", uri, +48h)`.
- `OpenRouterUploadAdapter` → `POST /api/v1/files` (multipart), returns `MediaRef("file_id"/"url", id/url)`.
- `UrlPassThroughAdapter` (future/remote sources) → returns `MediaRef("url", source_url)` if provider supports it.

### 2. `providers.py` consumes `MediaRef` instead of base64

Each `Provider.transcribe` takes a `MediaRef`; OpenAI-compatible providers build the content part from the ref kind (`video_url`/`input_audio` from url or file_id), Gemini uses `FileData(file_uri=...)`. Removes the `base64` + `data:` URL construction from `providers.py`.

### 3. Dynamic chunk sizing (`plan_chunks` gains a budget)

```python
def plan_chunks(duration, *, token_budget: int, video_rate=263, audio_rate=32) -> tuple[Chunk, ...]:
    # seconds that fit = budget / rate; split by the binding modality
    max_seconds = token_budget / max(video_rate, audio_rate)
    chunk_seconds = max(MIN_CHUNK_SECONDS, int(max_seconds))
    ...
```

The `token_budget` is produced by a `limit_resolver`:
- OpenRouter/Gemini: `context_length` (live, cached via `model_registry`) − `max_output_tokens` − prompt tokens.
- Polza: upstream model's `context_length` if resolvable, else safe default.
- A conservative floor (e.g. 300 s) remains so we never produce sub-clip fragments.

### 4. "Reduce/remove chunking" path

- **Gemini direct:** Files API + 1M window → for files whose `duration × (263+32)` < ~900k tokens, send the whole file in one request (no chunking, no re-encode). `plan_chunks` returns a single chunk.
- **OpenRouter/Polza:** if the resolved `token_budget` fits the whole file, skip chunking; otherwise chunk to the budget. Base64 is no longer the constraint because `UploadAdapter` hosts the bytes.

## Risks / caveats

- **OpenRouter video URL acceptance is model-route dependent.** Gemini-via-OpenRouter reliably accepts only YouTube URLs or base64, not arbitrary direct `.mp4` URLs. The `OpenRouterUploadAdapter` (hosted file) sidesteps this; prefer it over raw URL pass-through for video.
- **Token-rate constants are approximations** for non-Gemini video; the floor of 300 s prevents reckless oversizing. Re-derive per provider when better data exists.
- **Polza modality fields are often empty** in `/models`; the resolver falls back to the configured model's known context window.
- **Upload TTLs** (Polza 24h, Gemini 48h) must be tracked so `delete()` is called and we don't leak stored media; for very long jobs, refresh or re-upload.
- **Transient/upload-failure handling:** if `upload()` fails, fall back to base64 (current behavior) so the system stays non-breaking.

## Implementation order (lean, TDD)

1. Add `tests/test_upload_adapters.py` (contract: each adapter returns a `MediaRef`; deletes cleanly; failure falls back).
2. Add `upload_adapters.py` with the three adapters + `UrlPassThrough`.
3. Refactor `providers.py` to accept `MediaRef`.
4. Add `limit_resolver` using `model_registry` live data; extend `plan_chunks` with a token budget.
5. Wire `Settings` to allow `chunk_seconds=0` meaning "auto from model limits".
6. Update `models_catalog.yaml` notes (NOT the contract) with the "no byte cap, token-driven" finding.

## Verification

- Unit: `plan_chunks` with a known `token_budget` yields expected chunk count; single-chunk when budget fits.
- Unit: each adapter's `upload`/`delete` against mocked HTTP.
- Integration (live, with keys+proxy): Polza upload→URL→transcribe on a 5-min clip; Gemini whole-file on a short clip; OpenRouter file-upload on a clip.
- Non-breaking: existing base64 path retained as fallback; default `chunk_seconds=300` unchanged unless user opts into auto.

## Conclusion

Chunking should **stay** (it is valid and non-aggressive), but its size should become **model-limit-driven and upload-anchored**: implement `UploadAdapter`s so providers host the bytes (killing the base64 ceiling), and derive chunk duration from live `context_length` with a 300 s safety floor. This reduces complexity (whole-file when the model allows) without sacrificing reliability.

---
name: transcribe-video
description: Transcribe local video or audio into a chronological, speaker-attributed Markdown transcript using the transcription-agent CLI or Gradio UI. Use whenever the user asks to transcribe a video/audio file, produce a transcript, or attribute speakers from on-screen active-speaker cues.
---

# Transcribe Video

Turn a local video or audio file into a chronological, speaker-attributed transcript, then write the requested outputs.

## Run it

- Default model: `google/gemini-2.5-flash`. Default provider order comes from `TRANSCRIPTION_PROVIDER_ORDER` (Polza, OpenRouter, Gemini).
- CLI: `uv run transcription-agent transcribe <media> --formats markdown` writes `<source>_transcription.md` beside the media. Add `--formats json,srt,vtt,zip` for more; `--output-md <name>` renames the Markdown.
- GUI: run `app.py`; it always writes Markdown, JSON, SRT, VTT, and a ZIP.

## Attribution

Use the single canonical prompt at [src/transcription_agent/prompt-transcription.md](../../../src/transcription_agent/prompt-transcription.md) without weakening its completeness requirements. The `{start}` and `{end}` placeholders are filled by the CLI/GUI; replace them with `relative` or actual clip boundaries when applying the prompt manually. Every audible word by every speaker is required; omission, summarization, paraphrase, or cleanup of fillers/repetitions is a transcription failure. Treat any visible active-speaker cue (green border, highlight, outline, focus box) as primary evidence; use the displayed name on the active tile as the strongest label, voice as a secondary cue, and `SpeakerN` when ambiguous. Never guess an identity.

## Workflow and quality gate

Use the repository CLI and utilities rather than a one-off transcription script: [media.py](../../../src/transcription_agent/media.py) for probing/chunks and bounded visual checkpoints, [chunking.py](../../../src/transcription_agent/chunking.py) for model-aware planning, [orchestrator.py](../../../src/transcription_agent/orchestrator.py) for provider fallback/merge, and [exporters.py](../../../src/transcription_agent/exporters.py) for Markdown. Keep dynamic, model-aware chunking as the default; use a fixed duration only when the user explicitly requests one or a focused retry needs a bounded interval. Preserve the original chunk offset when merging.

For every chunk, inspect the audio and multiple current frames across each temporal portion. Rebuild the name-to-tile mapping whenever a participant joins, leaves, moves, or screen sharing starts/stops. During screen sharing, participant tiles may be in a sidebar or compact strip: follow every explicit speaker cue available in the current layout, regardless of color, brightness, contrast, shape, size, or position. This includes a colored/dark/light border or highlight, changed tile background, avatar illumination or ring, speaking indicator, label, or equivalent marker on any side, in the center, around an avatar, or around the tile; use the displayed name on the identified tile. Do not treat shared-screen text, faces, or stale tile positions as attribution evidence. A status icon/badge can be valid evidence when its platform meaning identifies the speaker; reject it only when the frame shows that it is unrelated to speaker activity. The visual pass supplies names and attribution; it must not replace or shorten the word-for-word audio pass.

When visual checkpoints are available, their labels must state original-media
timestamps, while transcript timestamps remain clip-relative. Inspect frames
before, at, and after each FFmpeg candidate event and compare the current
layout, participant membership, sidebar/grid position, screen-sharing state,
and active-speaker cue. Treat scene detection as a candidate, not proof of a
speaker change: it may miss subtle cues and must never cause audio to be
dropped, marked silent, or shifted without checking the media. Pass the stills
and compact timestamp/reason metadata as supplementary evidence alongside the
video; keep the canonical prompt's lossless audio requirements authoritative.

Before accepting a provider response, run a lossless format check:

- Require one hard-newline-separated speaker turn per output line, with a timestamp at the start and no embedded timestamp/name marker later in the line.
- If a provider puts several timestamped turns into one long line, split at every embedded marker, preserve all text between markers, and convert timestamps using the chunk's original offset. Never discard a remainder merely because the first parser did not recognize it.
- Treat empty/near-empty output, large unexplained timestamp gaps, a long collapsed line, or missing speech around a screen-share/layout transition as a failed quality gate, not as a successful short transcript.
- A large timestamp gap is not automatically silence: a single speaker turn may span it while reporting only its start time. For a suspicious gap, create a short recheck clip with padding on both boundaries, run the canonical prompt, map clip-relative timestamps back to the original timeline, and use audio silence/energy analysis as supporting evidence. If the recheck contains speech, preserve it as a continuous turn unless the main transcript actually lacks the words; do not manufacture silence or split solely because timestamps are sparse.
- If the quality gate proves an omission, rerun only the affected interval with the canonical prompt plus a concise completeness/screen-share reminder, then merge by original offset and deduplicate padded overlap. Record the failed attempt in job metadata when the normal orchestrator path is used.
- Main chunks are independent: start them with the configured stagger rather than waiting for previous chunks to finish. Use the configured five-second overlap for boundary context, then semantically merge only an exact repeated word sequence from the same speaker. Retain non-identical turns: proximity to a boundary is never proof that words are duplicates.
- Keep the gate narrow: inspect only a long, low-word-density turn after audio analysis confirms voice activity. Split only its padded recheck interval into 60--120-second chunks, and replace it only when the recheck contains materially more speech. Static video or screen sharing never establishes silence.
- If an auto-sized chunk is rejected as an invalid/oversized provider request, retry the affected job or interval with a smaller explicit bounded chunk size; keep dynamic model-aware chunking as the default for ordinary runs.
- Do not repeat an identical provider request after a failure. Change a diagnostic variable (affected interval, bounded chunk size, transport, or model), or stop and report the unchanged failure.
- Do not launch a parallel or identical retry while the previous provider attempt is live. A local timeout or process kill may not cancel upstream work or billing; stop once when authorized or let the bounded failure resolve before changing one diagnostic variable.

After merging, run the mandatory frame-based speaker-name normalization pass. Treat provider-produced names as candidate aliases; inspect frames at their turns and nearby moments, then map visually confirmed variants (phonetic/ASR or OCR errors, clipping, and company suffixes) to one canonical displayed name across all chunks. Normalize only speaker-label prefixes when frame evidence supports it; do not rewrite spoken words. If frames cannot establish the identity or exact spelling, use `SpeakerN` instead of guessing. Finally check chronological order, timestamp bounds, duplicate retry overlap, embedded markers, unexplained gaps, and the requested media-adjacent Markdown output.

The CLI and GUI implement this as a bounded label-only vision pass after the
audio/video pass: the provider receives the transcript's timestamps and labels
plus one still at each observed label's first occurrence (falling back to
checkpoint stills only when direct frames are unavailable) and must return only
a strict JSON mapping. Apply a mapping only between labels already present and
only to `speaker` fields; verify that words, timestamps, segment count, and
ordering are unchanged. If the pass fails or returns invalid/low-confidence
JSON, keep the pre-normalization transcript and record the failure. Set
`TRANSCRIPTION_SPEAKER_NORMALIZATION=false` or use the CLI
`--no-speaker-normalization` switch to skip this optional pass.

When regenerating or comparing a transcript, never overwrite an existing transcript implicitly. Use a distinct output name, verify the old file's hash before and after the run, and keep all recheck clips/transcripts disposable and outside Git.

For frame review, inspect an actual representative frame before interpreting
the visual cues: verify the current tile geometry and determine whether each
color, contrast change, shape, border, avatar treatment, badge, status icon,
or label actually identifies the active speaker. Cues may occur anywhere in or
around a tile and are not limited to green, rectangles, or a fixed position.
Do not discard a cue merely because it is an icon, and do not carry assumed
grid coordinates across layout changes. If using `--prompt`, start from the
canonical prompt and add context only; never replace its completeness,
visual-attribution, or output-format rules with a shorter custom prompt.

## Provider routing

Set per-provider proxies via `TRANSCRIPTION_POLZA_PROXY`, `TRANSCRIPTION_OPENROUTER_PROXY`, `TRANSCRIPTION_GEMINI_PROXY`. A present key wins even when empty; only a missing key falls back to `TRANSCRIPTION_PROXY`, CLI `--proxy`, or the GUI field. Hung hosted uploads time out after `TRANSCRIPTION_UPLOAD_TIMEOUT` (default 30s) and fall back to inline base64. Polza accepts a Russian IP and also answers over VPN; OpenRouter and Gemini require non-Russian egress. Do not route OpenRouter through the Polza SOCKS proxy: test and use each provider's own configured transport. OpenRouter video is inline base64 and may return a payload-size error for model-sized chunks; retry that job with a smaller explicit chunk override, not the same auto-sized payload. See the parent repo README for the full region matrix.

## Roster

Model-level ratings are shared across Polza, OpenRouter, and Gemini: selectors rank tested speech-from-video, then quality, then price, then speed. The maintained ranks, exclusions, and per-provider cost reporting are in [references/model-roster.md](references/model-roster.md); the live source of truth is `uv run transcription-agent models --provider polza`.

## Good to know

Do not replace the canonical prompt with a shorter prompt that drops the completeness, per-temporal-portion, visual-attribution, or screen-share requirements. Use frame inspection/vision analysis for visual cues; OCR can support a legible-name check but is not authoritative over the active border and current layout. Do not re-probe models without evidence of audio+video support. Temporary chunks and remote provider files are disposable; never commit them.

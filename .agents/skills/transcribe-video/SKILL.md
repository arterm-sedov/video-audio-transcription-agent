---
name: transcribe-video
description: Transcribe local video or audio into a chronological, speaker-attributed Markdown transcript using the transcription-agent CLI or Gradio UI. Use whenever the user asks to transcribe a video/audio file, produce a transcript, or attribute speakers from on-screen active-speaker cues.
---

# Transcribe Video

Turn a local video or audio file into a chronological, speaker-attributed transcript, then write the requested outputs.

## Run it

- Default model: `google/gemini-3.1-flash-lite`. Default provider order comes from `TRANSCRIPTION_PROVIDER_ORDER` (Polza, OpenRouter, Gemini).
- CLI: `uv run transcription-agent transcribe <media> --formats markdown` writes `<source>_transcription.md` beside the media. Add `--formats json,srt,vtt,zip` for more; `--output-md <name>` renames the Markdown.
- GUI: run `app.py`; it always writes Markdown, JSON, SRT, VTT, and a ZIP.

## Attribution

Use the canonical prompt at [references/prompt-transcription.md](references/prompt-transcription.md). Treat any visible active-speaker cue (green border, highlight, outline, focus box) as primary evidence; use a displayed name as the strongest label, voice as a secondary cue, and `SpeakerN` when ambiguous. Never guess an identity.

## Provider routing

Set per-provider proxies via `TRANSCRIPTION_POLZA_PROXY`, `TRANSCRIPTION_OPENROUTER_PROXY`, `TRANSCRIPTION_GEMINI_PROXY`. A present key wins even when empty; only a missing key falls back to `TRANSCRIPTION_PROXY`, CLI `--proxy`, or the GUI field. Hung hosted uploads time out after `TRANSCRIPTION_UPLOAD_TIMEOUT` (default 30s) and fall back to inline base64. Polza accepts a Russian IP and also answers over VPN; OpenRouter and Gemini require non-Russian egress. See the parent repo README for the full region matrix.

## Roster

Model-level ratings are shared across Polza, OpenRouter, and Gemini: selectors rank tested speech-from-video, then quality, then price, then speed. The maintained ranks, exclusions, and per-provider cost reporting are in [references/model-roster.md](references/model-roster.md); the live source of truth is `uv run transcription-agent models --provider polza`.

## Good to know

Do not re-probe Qwen, MiniMax, Claude, Muse, or GPT for speech unless Polza advertises audio+video on those ids. Temporary chunks and remote provider files are disposable; never commit them.

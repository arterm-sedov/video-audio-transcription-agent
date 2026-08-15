---
name: video-transcription
description: Transcribe video and audio with speaker attribution using visual active-speaker cues and optional voice diarization.
---

# Video and Audio Transcription

Use the standalone `transcription-agent` CLI or Gradio UI. The default provider chain is Polza, direct Gemini, then OpenRouter. The prompt treats any active-speaker border, highlight, focus box, or equivalent visual cue as evidence and falls back to `SpeakerN` when evidence is ambiguous.

Outputs are Markdown, JSON, SRT, and VTT. The CLI and GUI report total processing price in USD (Polza `cost_rub` is converted via `POLZA_RUB_TO_USD_RATE`, default 90 RUB/USD; OpenRouter reports `cost` in USD; Gemini cost is only available in its dashboard). Temporary media chunks and remote provider files are disposable and must not be committed.

Provider routing by IP region: Polza prefers Russian customer IPs and rejects VPN exits; OpenRouter and Gemini require non-Russian IPs (VPN or hosting such as Hugging Face Spaces) and fail from Russian IPs. The provider chain retries and falls back automatically per job.

Optional proxy: set per provider via `TRANSCRIPTION_POLZA_PROXY`, `TRANSCRIPTION_OPENROUTER_PROXY`, `TRANSCRIPTION_GEMINI_PROXY` (e.g. Polza default `socks5h://192.168.122.1:1080` on the corporate gateway). Unset values fall back to `TRANSCRIPTION_PROXY`, CLI `--proxy`, or the GUI field. Both OpenAI-compatible (Polza/OpenRouter) and direct Gemini clients honor it.

Output control (CLI): `--output-md <name>` sets the Markdown filename (default `<source>_transcription.md`); `--formats json,srt,vtt,zip` selects which additional formats to write. The GUI always produces the same four files plus the ZIP artifact.

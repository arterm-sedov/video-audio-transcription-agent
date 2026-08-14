---
name: video-transcription
description: Transcribe video and audio with speaker attribution using visual active-speaker cues and optional voice diarization.
---

# Video and Audio Transcription

Use the standalone `transcription-agent` CLI or Gradio UI. The default provider chain is Polza, direct Gemini, then OpenRouter. The prompt treats any active-speaker border, highlight, focus box, or equivalent visual cue as evidence and falls back to `SpeakerN` when evidence is ambiguous.

Outputs are Markdown, JSON, SRT, and VTT. Temporary media chunks and remote provider files are disposable and must not be committed.

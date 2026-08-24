---
name: video-transcription
description: Transcribe video and audio with speaker attribution using visual active-speaker cues and optional voice diarization.
---

# Video and Audio Transcription

Use the standalone `transcription-agent` CLI or Gradio UI. The default provider chain is Polza, direct Gemini, then OpenRouter. The prompt treats any active-speaker border, highlight, focus box, or equivalent visual cue as evidence and falls back to `SpeakerN` when evidence is ambiguous.

Outputs are Markdown, JSON, SRT, and VTT. The CLI and GUI report total processing price in USD (Polza `cost_rub` is converted via `POLZA_RUB_TO_USD_RATE`, default 90 RUB/USD; OpenRouter reports `cost` in USD; Gemini cost is only available in its dashboard). Temporary media chunks and remote provider files are disposable and must not be committed.

Provider routing by IP region: Polza accepts Russian customer IPs and, on this network, also answers over a VPN (`TRANSCRIPTION_POLZA_PROXY` is optional). OpenRouter and Gemini require non-Russian IPs (VPN or hosting such as Hugging Face Spaces) and fail from Russian IPs; OpenRouter Gemini may additionally 403 TOS from this account and stays in the roster for western/HF hosting. The provider chain retries and falls back automatically per job.

Optional proxy: set per provider via `TRANSCRIPTION_POLZA_PROXY`, `TRANSCRIPTION_OPENROUTER_PROXY`, `TRANSCRIPTION_GEMINI_PROXY` (e.g. Polza uses a SOCKS5 proxy such as `socks5h://<proxy-host>:<port>` on the corporate gateway). A present per-provider key wins even when empty; only a missing key falls back to `TRANSCRIPTION_PROXY`, CLI `--proxy`, or the GUI field. An empty OpenRouter proxy stays direct and does not inherit Polza SOCKS. Hung hosted uploads time out after `TRANSCRIPTION_UPLOAD_TIMEOUT` (default 30s) and fall back to inline base64. OpenRouter declines video uploads, so video is always sent inline. Both OpenAI-compatible (Polza/OpenRouter) and direct Gemini clients honor the proxy.

Output control (CLI): `--output-md <name>` sets the Markdown filename (default `<source>_transcription.md`). Default output is Markdown only; `--formats json,srt,vtt,zip` adds those files. The GUI always produces the full set (Markdown, JSON, SRT, VTT, ZIP).

Roster ratings are model-level (same ranks on Polza, OpenRouter, and Gemini). Selectors sort **tested speech-from-video first**, then **quality, price, speed**. Reliability is documented, not a sort key. Do not re-probe Qwen, MiniMax, Claude, Muse, or GPT unless Polza advertises audio+video on those ids.

| model | quality | price | speed | reliability | note |
|---|---|---:|---|---|---|
| google/gemini-3.1-flash-lite | strong | 0.05 | fast (13.1s) | high | default; named speakers on 5 min |
| google/gemini-3.5-flash-lite | strong | 0.05 | fast (25.7s) | high | strong, slightly slower |
| google/gemini-3.6-flash | strong | 0.10 | medium (44s) | high | keep |
| google/gemini-3.7-flash | strong | 0.15 | fast (26.1s) | high | keep |
| google/gemini-2.5-flash | strong | 0.30 | fast (25.8s) | mixed | cheapest 5-min job ($0.0034); SOCKS flake |
| google/gemini-3.5-flash | strong | 0.30 | medium (43s) | high | keep |
| google/gemini-2.5-pro | strong | 1.25 | slow (114s) | high | over-segmented, expensive |
| google/gemini-2.5-flash-lite | good | 0.05 | slow (123s) | low | 5-min hallucinated 3453 "Да." lines |
| xiaomi/mimo-v2.5 | good | 0.14 | medium (86s) | mixed | gold at 60s, empty speech at 5 min |

Excluded: Qwen 3.6/3.7 and MiniMax M3 (video, no audio), Claude/GPT (400 no video endpoints), Muse Spark (OpenRouter 18+ gate).

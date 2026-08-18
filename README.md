# Video and audio transcription agent

Transcribe video or audio with speaker labels, timestamps, and downloadable artifacts.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- One provider key: Polza, Gemini, or OpenRouter

## Install

```bash
uv sync --all-extras --dev
cp .env.example .env
```

On Windows PowerShell:

```powershell
uv sync --all-extras --dev
Copy-Item .env.example .env
```

Set provider credentials in `.env`. Never commit `.env`.

## CLI

Validate configuration:

```bash
uv run transcription-agent validate-config
```

Transcribe a local file:

```bash
uv run transcription-agent transcribe path/to/recording.mp4
```

Override provider order for one job:

```bash
uv run transcription-agent transcribe recording.mp4 \
  --provider-order polza,gemini,openrouter
```
The first provider in `TRANSCRIPTION_PROVIDER_ORDER` is the default provider for
the CLI and GUI; pass `--provider <name>` to use a single provider for one job.

Select a model for one job:

```bash
uv run transcription-agent transcribe recording.mp4 \
  --model google/gemini-3.1-flash-lite
```

Route provider calls through an optional proxy:

```bash
uv run transcription-agent transcribe recording.mp4 \
  --provider-order polza \
  --proxy socks5h://<proxy-host>:<port>
```

The GUI has a matching Proxy field. Per-provider env vars (`TRANSCRIPTION_POLZA_PROXY`, `TRANSCRIPTION_OPENROUTER_PROXY`, `TRANSCRIPTION_GEMINI_PROXY`) win when present, even as an empty string; only a missing key inherits `TRANSCRIPTION_PROXY` or the CLI/GUI value. An empty OpenRouter proxy therefore stays direct and does not inherit Polza SOCKS. HTTP and SOCKS5 (`socks5h://`, DNS via proxy) are supported for both OpenAI-compatible and Gemini clients. Hung hosted uploads time out after `TRANSCRIPTION_UPLOAD_TIMEOUT` (default 30s) and fall back to inline base64. OpenRouter declines video uploads (`UploadDeclined`), so video is always sent inline.

List available video-capable models ranked by quality, then price, then speed:

```bash
uv run transcription-agent models --provider polza
uv run transcription-agent models --provider gemini
```

The default provider order is `polza,openrouter,gemini`, so Polza is the default provider and Gemini is tried last. The GUI exposes the same provider and model selectors; the model list is provider-aware (direct Gemini shows only Gemini models). The agent splits long media into temporary chunks, preserves audio and video, merges timestamps, and writes all outputs to `TRANSCRIPTION_OUTPUT_DIR`. Chunking is model-driven by default: `TRANSCRIPTION_CHUNK_SECONDS=0` sizes each chunk from the model's context window and worst-case token-per-second rate, so a larger-window model yields larger chunks automatically (set a positive value for fixed-size chunks). The planner never drops below a 300-second floor, so a 300-second split is an explicit override or a tiny-window clamp, not the default. A Gemini ~1M-token window typically covers a 25-minute file in one chunk.

CLI output control: by default only the Markdown transcript is written. Add other formats explicitly:

```bash
uv run transcription-agent transcribe recording.mp4 --formats json,srt,vtt,zip
uv run transcription-agent transcribe recording.mp4 --output-md notes.md
```

The GUI always writes the full set (Markdown, JSON, SRT, VTT, ZIP).

## Provider routing by IP region

Provider reachability depends on the IP region the request egresses from:

- **Polza** accepts Russian customer IPs and, on this network, also answers over a VPN. `TRANSCRIPTION_POLZA_PROXY` is the intended corporate SOCKS route; it is optional while Polza remains reachable without it.
- **OpenRouter** and **Gemini** allow only non-Russian IPs — reachable over a VPN, or natively from non-Russian hosting such as Hugging Face Spaces — and fail with `403` / `400 User location is not supported` from a Russian IP. OpenRouter Gemini can additionally return provider TOS `403` from this account; keep those models in the roster for western/HF hosting.

The provider chain retries and falls back automatically, so a job completes through whichever provider is reachable from the current egress IP. On Hugging Face Spaces, OpenRouter and Gemini are the natural choices; on a Russian-local host, Polza is the natural choice.

Live selectors keep evidence-tested speech-from-video models first, ranked quality then price then speed (`google/gemini-3.1-flash-lite` default; cheapest usable 5-minute job `google/gemini-2.5-flash` with mixed reliability; `google/gemini-2.5-flash-lite` and `xiaomi/mimo-v2.5` demoted after the 5-minute clip). Dead ends stay excluded: Qwen/MiniMax vision-only on Polza, Claude no-video endpoints, Muse Spark 18+ attestation, VL/Kimi/GLM/Ernie. Live discovery only adds models whose provider metadata lists both audio and video input. Ratings are model-level and shared across Polza, OpenRouter, and Gemini.

## Skill

Load [`skills/video-transcription/SKILL.md`](skills/video-transcription/SKILL.md) when an agent needs the transcription workflow. The canonical prompt is [`skills/video-transcription/prompts/transcription.md`](skills/video-transcription/prompts/transcription.md).

The prompt requires:

- chronological speaker turns;
- timestamps relative to each clip;
- any active-speaker cue: border, highlight, outline, focus box, or equivalent;
- voice evidence as a secondary signal;
- `SpeakerN` when evidence is ambiguous;
- no summary or paraphrase.

## Gradio

Run locally:

```bash
uv run python app.py
```

Open `http://127.0.0.1:7860`.

The UI supports file upload, provider-order selection, diarization configuration, progress updates, transcript preview, individual downloads, and a ZIP artifact package.

## Hugging Face Spaces

Create a Gradio Space and upload this repository. `app.py` is the Space entrypoint.

Add provider keys as Space Secrets:

```text
POLZA_API_KEY
GEMINI_KEY
OPENROUTER_API_KEY
```

Set non-secret options as Space Variables. See [`README_HF.md`](README_HF.md).

## Outputs

Each completed job produces:

```text
<name>_transcription.md
<name>_transcription.json
<name>_transcription.srt
<name>_transcription.vtt
<name>_<timestamp>.zip
```

JSON includes segments, speakers, timestamps, provider/model metadata, usage, and normalized cost. ZIP packages include a SHA-256 manifest.

## Configuration

See [`.env.example`](.env.example) for documented settings, including provider order, model, chunk duration, output directory, SQLite registry, diarization, and token limits.

## Development

```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv lock --check
```

License: [MIT](LICENSE).

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

Select a model for one job:

```bash
uv run transcription-agent transcribe recording.mp4 \
  --model google/gemini-3.6-flash
```

Route provider calls through an optional proxy:

```bash
uv run transcription-agent transcribe recording.mp4 \
  --provider-order polza \
  --proxy socks5h://192.168.122.1:1080
```

The GUI has a matching Proxy field; `TRANSCRIPTION_PROXY` configures it globally. HTTP and SOCKS5 (`socks5h://`, DNS via proxy) are supported for both OpenAI-compatible and Gemini clients.

List available video-capable models with curated price ranking:

```bash
uv run transcription-agent models --provider polza
uv run transcription-agent models --provider gemini
```

The default provider order is `polza,gemini,openrouter`. The GUI exposes the same provider and model selectors; the model list is provider-aware (direct Gemini shows only Gemini models). The agent splits long media into temporary chunks, preserves audio and video, merges timestamps, and writes all outputs to `TRANSCRIPTION_OUTPUT_DIR`.

## Provider routing by IP region

Provider reachability depends on the IP region the request egresses from:

- **Polza** prefers Russian customer IPs and rejects VPN exits (connection timeouts while a VPN is active).
- **OpenRouter** and **Gemini** allow only non-Russian IPs — reachable over a VPN, or natively from non-Russian hosting such as Hugging Face Spaces — and fail with `403` / `400 User location is not supported` from a Russian IP.

The provider chain retries and falls back automatically, so a job completes through whichever provider is reachable from the current egress IP. On Hugging Face Spaces, OpenRouter and Gemini are the natural choices; on a Russian-local host without VPN, Polza is the natural choice.

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

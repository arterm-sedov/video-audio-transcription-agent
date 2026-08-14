# Video Audio Transcription Agent

Focused, business-neutral transcription agent for video and audio files. It supports Polza, direct Gemini, and OpenRouter provider routing, active-speaker visual cues, optional voice diarization, persistent jobs, and Markdown/JSON/SRT/VTT exports.

## Development

```powershell
uv sync --all-extras
uv run pytest -q
uv run transcription-agent validate-config
```

For a development environment with the optional diarization/provider/UI/media
dependencies and the development group:

```bash
uv sync --all-extras --dev
uv run transcription-agent transcribe path/to/recording.mp4
```

Keep credentials in `.env`; never commit them.

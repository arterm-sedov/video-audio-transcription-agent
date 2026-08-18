# Hugging Face Spaces deployment

Create a Gradio Space and upload this repository. The Space uses `app.py` as its entrypoint. Dependencies are declared in `pyproject.toml`; the Space runtime should install the project with its declared optional extras.

Add provider credentials as Space Secrets, never as repository files:

- `POLZA_API_KEY`
- `GEMINI_KEY` or `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`

Optional public variables:

```text
TRANSCRIPTION_PROVIDER_ORDER=polza,gemini,openrouter
TRANSCRIPTION_MODEL=google/gemini-3.1-flash-lite
TRANSCRIPTION_CHUNK_SECONDS=0
TRANSCRIPTION_OUTPUT_DIR=.transcriptions
TRANSCRIPTION_DIARIZATION=true
```

The container must provide FFmpeg and ffprobe. The application does not use Windows paths or shell syntax.

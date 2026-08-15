"""Environment-backed configuration with safe, explicit defaults."""

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional runtime dependency
    load_dotenv = None


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for CLI, UI, and provider orchestration."""

    provider_order: tuple[str, ...] = ("polza", "gemini", "openrouter")
    model: str = "google/gemini-2.5-flash"
    chunk_seconds: int = 300
    output_dir: Path = Path(".transcriptions")
    database_path: Path = Path(".transcriptions/jobs.sqlite3")
    diarization_enabled: bool = True
    max_output_tokens: int = 8192
    proxy: str = ""

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> "Settings":
        if load_dotenv is not None and env_file:
            load_dotenv(Path(env_file), override=False)
        order = tuple(
            item.strip().lower()
            for item in os.getenv(
                "TRANSCRIPTION_PROVIDER_ORDER", "polza,gemini,openrouter"
            ).split(",")
            if item.strip()
        )
        if not order:
            raise ValueError("TRANSCRIPTION_PROVIDER_ORDER must not be empty")
        chunk_seconds = int(os.getenv("TRANSCRIPTION_CHUNK_SECONDS", "300"))
        if chunk_seconds <= 0:
            raise ValueError("TRANSCRIPTION_CHUNK_SECONDS must be positive")
        return cls(
            provider_order=order,
            model=os.getenv("TRANSCRIPTION_MODEL", "google/gemini-2.5-flash"),
            chunk_seconds=chunk_seconds,
            output_dir=Path(os.getenv("TRANSCRIPTION_OUTPUT_DIR", ".transcriptions")),
            database_path=Path(
                os.getenv("TRANSCRIPTION_DATABASE", ".transcriptions/jobs.sqlite3")
            ),
            diarization_enabled=os.getenv("TRANSCRIPTION_DIARIZATION", "true").lower()
            in {"1", "true", "yes", "on"},
            max_output_tokens=int(os.getenv("TRANSCRIPTION_MAX_OUTPUT_TOKENS", "8192")),
            proxy=os.getenv("TRANSCRIPTION_PROXY", "").strip(),
        )

    def validate(self) -> None:
        supported = {"polza", "gemini", "openrouter"}
        unknown = set(self.provider_order) - supported
        if unknown:
            raise ValueError(f"Unsupported providers: {sorted(unknown)}")
        if not self.model.strip():
            raise ValueError("TRANSCRIPTION_MODEL must not be empty")
        if self.chunk_seconds <= 0:
            raise ValueError("chunk_seconds must be positive")
        if self.max_output_tokens <= 0:
            raise ValueError("TRANSCRIPTION_MAX_OUTPUT_TOKENS must be positive")

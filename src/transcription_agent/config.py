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

    provider_order: tuple[str, ...] = ("polza", "openrouter", "gemini")
    model: str = "google/gemini-2.5-flash"
    chunk_seconds: int = 0
    output_dir: Path = Path(".transcriptions")
    database_path: Path = Path(".transcriptions/jobs.sqlite3")
    diarization_enabled: bool = True
    max_output_tokens: int = 8192
    proxy: str = ""
    polza_proxy: str = ""
    openrouter_proxy: str = ""
    gemini_proxy: str = ""
    upload_timeout_seconds: float = 30.0
    speaker_normalization_enabled: bool = True

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> "Settings":
        if load_dotenv is not None and env_file:
            load_dotenv(Path(env_file), override=False)
        order = tuple(
            item.strip().lower()
            for item in os.getenv(
                "TRANSCRIPTION_PROVIDER_ORDER", "polza,openrouter,gemini"
            ).split(",")
            if item.strip()
        )
        if not order:
            raise ValueError("TRANSCRIPTION_PROVIDER_ORDER must not be empty")
        # 0 or negative => auto: chunk size derives from the model's context
        # window and worst-case token-per-second rate
        # (see chunking.plan_chunks_for_model).
        chunk_seconds = int(os.getenv("TRANSCRIPTION_CHUNK_SECONDS", "0"))
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
            polza_proxy=os.getenv("TRANSCRIPTION_POLZA_PROXY", "").strip(),
            openrouter_proxy=os.getenv("TRANSCRIPTION_OPENROUTER_PROXY", "").strip(),
            gemini_proxy=os.getenv("TRANSCRIPTION_GEMINI_PROXY", "").strip(),
            upload_timeout_seconds=float(
                os.getenv("TRANSCRIPTION_UPLOAD_TIMEOUT", "30") or "30"
            ),
            speaker_normalization_enabled=os.getenv(
                "TRANSCRIPTION_SPEAKER_NORMALIZATION", "true"
            ).lower()
            in {"1", "true", "yes", "on"},
        )

    def provider_proxy(self, provider: str) -> str:
        """Per-provider proxy; an explicit empty env var stays empty.

        TRANSCRIPTION_<PROVIDER>_PROXY, when present in the environment
        (even as an empty string), wins over TRANSCRIPTION_PROXY. That is
        how OpenRouter stays direct: .env sets TRANSCRIPTION_OPENROUTER_PROXY=
        so it does not inherit Polza SOCKS. A missing per-provider key still
        falls back to the global proxy.
        """
        key = provider.strip().lower()
        env_name = {
            "polza": "TRANSCRIPTION_POLZA_PROXY",
            "openrouter": "TRANSCRIPTION_OPENROUTER_PROXY",
            "gemini": "TRANSCRIPTION_GEMINI_PROXY",
        }.get(key)
        if env_name is not None and env_name in os.environ:
            return os.environ[env_name].strip()
        per_provider = {
            "polza": self.polza_proxy,
            "openrouter": self.openrouter_proxy,
            "gemini": self.gemini_proxy,
        }.get(key, "")
        return per_provider or self.proxy

    def validate(self) -> None:
        supported = {"polza", "gemini", "openrouter"}
        unknown = set(self.provider_order) - supported
        if unknown:
            raise ValueError(f"Unsupported providers: {sorted(unknown)}")
        if not self.model.strip():
            raise ValueError("TRANSCRIPTION_MODEL must not be empty")
        if self.max_output_tokens <= 0:
            raise ValueError("TRANSCRIPTION_MAX_OUTPUT_TOKENS must be positive")
        if self.upload_timeout_seconds < 0:
            raise ValueError("TRANSCRIPTION_UPLOAD_TIMEOUT must not be negative")

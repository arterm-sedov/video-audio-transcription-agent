"""Deterministic chunk planning independent of media backend."""

from dataclasses import dataclass

try:
    from .limits import resolve_context_length, token_rate
except ImportError:  # pragma: no cover - test shim
    from transcription_agent.limits import resolve_context_length, token_rate


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    start: float
    end: float


# Safety floor: never produce sub-clip fragments even when a model window is tiny.
FLOOR_SECONDS = 300
# Reserve tokens for the prompt and model output so we don't fill the window.
OUTPUT_RESERVE_TOKENS = 8_192


def plan_chunks(
    duration: float,
    chunk_seconds: int | None = None,
    token_budget: int | None = None,
    floor_seconds: int = FLOOR_SECONDS,
    prompt_tokens: int = 512,
    overlap_seconds: float = 0.0,
) -> tuple[Chunk, ...]:
    """Return chunks covering the full duration with an optional bounded overlap.

    Chunk size is chosen from (in priority order):
    1. ``chunk_seconds`` when explicitly provided and positive (back-compat).
    2. ``token_budget`` (tokens that fit the model context window) divided by the
       worst-case token rate, so the chunk never overflows the model.
    3. The default floor (300 s).

    The result is clamped to ``floor_seconds`` minimum so we never fragment a
    short clip into tiny pieces.
    """
    if duration < 0:
        raise ValueError("duration must not be negative")
    if duration == 0:
        return ()
    if overlap_seconds < 0:
        raise ValueError("overlap_seconds must not be negative")
    if chunk_seconds is not None and chunk_seconds > 0:
        seconds = chunk_seconds
    elif token_budget:
        usable = max(0, token_budget - OUTPUT_RESERVE_TOKENS - prompt_tokens)
        seconds = int(usable / token_rate())
    else:
        seconds = FLOOR_SECONDS
    seconds = max(floor_seconds, seconds)
    if overlap_seconds >= seconds:
        raise ValueError("overlap_seconds must be smaller than chunk duration")
    step = seconds - overlap_seconds
    chunks = []
    start = 0.0
    index = 0
    while start < duration:
        end = min(start + seconds, duration)
        chunks.append(Chunk(index, start, end))
        if end >= duration:
            break
        start += step
        index += 1
    return tuple(chunks)


def plan_chunks_for_model(
    duration: float,
    provider: str,
    model: str,
    *,
    chunk_seconds: int | None = None,
    floor_seconds: int = FLOOR_SECONDS,
    overlap_seconds: float = 0.0,
) -> tuple[Chunk, ...]:
    """Plan chunks from the model's live context window when no fixed size given."""
    if chunk_seconds is not None and chunk_seconds > 0:
        return plan_chunks(
            duration,
            chunk_seconds=chunk_seconds,
            floor_seconds=floor_seconds,
            overlap_seconds=overlap_seconds,
        )
    window = resolve_context_length(provider, model)
    return plan_chunks(
        duration,
        token_budget=window,
        floor_seconds=floor_seconds,
        overlap_seconds=overlap_seconds,
    )

"""Resolve per-model context windows so chunk size can be limit-driven.

No provider publishes a reliable per-model context length on its list endpoint;
limits are token-window driven. This module turns a ``(provider, model)`` pair
into a context length (tokens) from a curated name heuristic, with a fixed
large window for Gemini and a safe default otherwise. Never raises and never
hits the network, so chunk planning stays deterministic and offline.
"""

from __future__ import annotations

DEFAULT_CONTEXT_TOKENS = 200_000
GEMINI_CONTEXT_TOKENS = 1_000_000

# Conservative context windows for well-known models when live lookup misses.
_CONTEXT_BY_SUBSTRING = (
    ("gemini-3", 1_000_000),
    ("gemini-2.5", 1_000_000),
    ("gemini-2.0", 1_000_000),
    ("gemini", 1_000_000),
    ("qwen3.8", 262_144),
    ("qwen3.7", 262_144),
    ("qwen3.6", 262_144),
    ("qwen3", 262_144),
    ("kimi-k3", 200_000),
    ("kimi", 200_000),
    ("glm-5.2", 200_000),
    ("glm-5", 200_000),
    ("minimax", 200_000),
)


def _context_from_catalog(model: str) -> int:
    lowered = model.lower()
    for needle, window in _CONTEXT_BY_SUBSTRING:
        if needle in lowered:
            return window
    return DEFAULT_CONTEXT_TOKENS


def resolve_context_length(provider: str, model: str) -> int:
    """Return the context window (tokens) for a provider/model.

    Gemini uses a fixed large window (its endpoint does not expose per-model
    limits). All other providers use the curated model-name heuristic; the
    function never raises and never performs network I/O.
    """
    key = provider.strip().lower()
    if key == "gemini":
        return GEMINI_CONTEXT_TOKENS
    return _context_from_catalog(model)


def token_rate(video_rate: int = 263, audio_rate: int = 32) -> int:
    """Worst-case token rate per second across modalities."""
    return max(video_rate, audio_rate)

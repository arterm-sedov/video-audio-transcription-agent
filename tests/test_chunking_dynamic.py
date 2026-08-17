"""Unit tests for limit-driven (dynamic) chunk planning."""

from __future__ import annotations

from itertools import pairwise

from transcription_agent.chunking import (
    FLOOR_SECONDS,
    plan_chunks,
    plan_chunks_for_model,
)


def test_plan_chunks_fixed_seconds_back_compat() -> None:
    chunks = plan_chunks(967.8, chunk_seconds=300)
    assert [(c.start, c.end) for c in chunks] == [
        (0, 300),
        (300, 600),
        (600, 900),
        (900, 967.8),
    ]


def test_plan_chunks_single_chunk_when_budget_fits_whole_file() -> None:
    # 1M window, worst-case rate 263 tok/s -> ~3.8k s; 600 s file fits in one chunk
    chunks = plan_chunks(600.0, token_budget=1_000_000)
    assert len(chunks) == 1
    assert chunks[0].start == 0
    assert chunks[0].end == 600.0


def test_plan_chunks_token_budget_splits_large_file() -> None:
    # Budget maps to ~400 s of usable video; a 1000 s file must split into chunks.
    token_budget = 400 * 263 + 8_192 + 512  # usable ~ 400 s before reserve/prompt
    chunks = plan_chunks(1000.0, token_budget=token_budget)
    # 1000 / 400 => 3 chunks
    assert len(chunks) >= 2
    # contiguous and covering
    assert chunks[0].start == 0
    assert chunks[-1].end == 1000.0
    for a, b in pairwise(chunks):
        assert a.end == b.start


def test_plan_chunks_clamps_to_floor_seconds() -> None:
    # A tiny model window would suggest a tiny chunk; floor prevents fragmentation.
    chunks = plan_chunks(1000.0, token_budget=10_000)
    seconds = chunks[0].end - chunks[0].start
    assert seconds >= FLOOR_SECONDS


def test_plan_chunks_empty_for_zero_duration() -> None:
    assert plan_chunks(0, chunk_seconds=300) == ()


def test_plan_chunks_rejects_negative_duration() -> None:
    import pytest

    with pytest.raises(ValueError):
        plan_chunks(-5, chunk_seconds=300)


def test_plan_chunks_for_model_uses_resolved_window(monkeypatch) -> None:
    import transcription_agent.chunking as ch

    calls = {}

    def fake_resolve(provider: str, model: str) -> int:
        calls["args"] = (provider, model)
        return 1_000_000

    monkeypatch.setattr(ch, "resolve_context_length", fake_resolve)
    chunks = plan_chunks_for_model(600.0, "gemini", "google/gemini-2.5-flash")
    assert calls["args"] == ("gemini", "google/gemini-2.5-flash")
    assert len(chunks) == 1  # whole file fits the 1M window
    assert chunks[0].end == 600.0


def test_plan_chunks_for_model_fixed_overrides_budget(monkeypatch) -> None:
    import transcription_agent.chunking as ch

    monkeypatch.setattr(ch, "resolve_context_length", lambda p, m: 1_000_000)
    # explicit chunk_seconds wins over the resolved window
    chunks = plan_chunks_for_model(
        967.8, "polza", "google/gemini-2.5-flash", chunk_seconds=300
    )
    assert [(c.start, c.end) for c in chunks] == [
        (0, 300),
        (300, 600),
        (600, 900),
        (900, 967.8),
    ]

from pathlib import Path

from transcription_agent.providers import PROMPT_TEMPLATE

CANONICAL_PROMPT = (
    Path(__file__).parents[1]
    / "src"
    / "transcription_agent"
    / "prompt-transcription.md"
).read_text(encoding="utf-8")


def test_all_transcription_prompts_require_complete_screen_share_transcription() -> (
    None
):
    required_phrases = (
        "every audible word",
        "screen sharing",
        "exactly one speaker turn per line",
        "one line",
        "completeness pass",
        "across chunks",
        "speaker-name language",
        "separate checks",
        "embedded timestamp/name markers",
        "shared application",
        "speaker-name normalization",
        "candidate alias",
        "canonical displayed name",
        "frame-based speaker-name normalization",
        "regardless of color, brightness, contrast, shape, size, or position",
        "around an avatar",
        "every explicit platform cue",
        "status icon or badge is not automatically irrelevant",
    )

    for prompt in (PROMPT_TEMPLATE, CANONICAL_PROMPT):
        prompt = prompt.lower()
        for phrase in required_phrases:
            assert phrase in prompt


def test_provider_prompt_is_loaded_from_the_single_canonical_file() -> None:
    assert PROMPT_TEMPLATE == CANONICAL_PROMPT


def test_skill_points_to_the_single_canonical_prompt() -> None:
    skill = (
        Path(__file__).parents[1]
        / ".agents"
        / "skills"
        / "transcribe-video"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "../../../src/transcription_agent/prompt-transcription.md" in skill
    assert not (
        Path(__file__).parents[1]
        / ".agents"
        / "skills"
        / "transcribe-video"
        / "references"
        / "prompt-transcription.md"
    ).exists()


def test_skill_documents_lossless_retry_and_visual_mapping_gate() -> None:
    skill = (
        (
            Path(__file__).parents[1]
            / ".agents"
            / "skills"
            / "transcribe-video"
            / "SKILL.md"
        )
        .read_text(encoding="utf-8")
        .lower()
    )

    for phrase in (
        "dynamic, model-aware chunking",
        "multiple current frames",
        "screen sharing",
        "lossless format check",
        "embedded marker",
        "preserve all text",
        "rerun only the affected interval",
        "do not rewrite spoken words",
        "ocr can support",
        "candidate aliases",
        "canonical displayed name",
        "not limited to green",
        "status icon/badge can be valid evidence",
    ):
        assert phrase in skill


def test_agents_documents_gap_recheck_and_non_destructive_regeneration() -> None:
    agents = (
        (Path(__file__).parents[1] / "AGENTS.md").read_text(encoding="utf-8").lower()
    )

    for phrase in (
        "invalid/oversized provider request",
        "distinct output name",
        "verify the old file's",
        "hash before and after",
        "large timestamp gap is not by itself evidence of silence",
        "recheck clip",
        "silence/energy analysis",
        "replace only the affected interval",
        "deduplicate overlap",
        "canonical displayed name",
        "do not repeat an identical provider request",
        "single canonical prompt loaded by providers",
        "client-side timeout/kill",
        "fixed meeting-grid geometry",
        "openrouter video requests use inline base64",
    ):
        assert phrase in agents

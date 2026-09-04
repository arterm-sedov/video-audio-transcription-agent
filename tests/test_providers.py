from pathlib import Path

from transcription_agent.media import VisualCheckpoint
from transcription_agent.providers import OpenAICompatibleProvider
from transcription_agent.upload_adapters import MediaRef


def test_openai_content_keeps_media_and_adds_timestamped_visual_evidence(
    tmp_path: Path,
) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    frame = tmp_path / "checkpoint.png"
    frame.write_bytes(b"png")
    checkpoint = VisualCheckpoint(2.5, 62.5, frame, "FFmpeg scene-change candidate")

    content = OpenAICompatibleProvider._content_from_ref(
        MediaRef("base64", "", "polza"),
        "transcribe every word",
        str(clip),
        (checkpoint,),
    )

    assert content[0]["type"] == "text"
    assert content[1]["type"] == "video_url"
    evidence_index = next(
        index for index, item in enumerate(content) if item["type"] == "image_url"
    )
    evidence = content[evidence_index]
    assert "original-video time 62.500s" in content[evidence_index - 1]["text"]
    assert "clip-relative 2.500s" in content[evidence_index - 1]["text"]
    assert evidence["image_url"]["url"].startswith("data:image/png;base64,")

"""Hugging Face Spaces entrypoint."""

from transcription_agent.app import build_demo

demo = build_demo()

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

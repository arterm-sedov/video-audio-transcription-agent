"""Small structured progress stream used by CLI and Gradio."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    status: str
    message: str
    completed: int = 0
    total: int = 0

    @property
    def fraction(self) -> float:
        return self.completed / self.total if self.total else 0.0


ProgressCallback = Callable[[ProgressEvent], None]


def emit(callback: ProgressCallback | None, event: ProgressEvent) -> None:
    if callback is not None:
        callback(event)

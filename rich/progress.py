"""Minimal progress stubs for rich."""

from __future__ import annotations

from typing import Any


class SpinnerColumn:
    """Placeholder spinner column."""


class TextColumn:
    """Placeholder text column."""

    def __init__(self, text: str) -> None:
        self.text = text


class Progress:
    """Minimal stand-in for rich.progress.Progress."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._task_id = 0

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def add_task(self, _: str, total: Any = None, **kwargs: Any) -> int:
        self._task_id += 1
        return self._task_id

    def update(self, task_id: int, advance: Any = None, **kwargs: Any) -> None:
        return None

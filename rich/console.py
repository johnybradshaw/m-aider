"""Minimal Console stub for rich."""

from __future__ import annotations

from typing import Any


class Console:
    """Minimal stand-in for rich.console.Console."""

    def print(self, *args: Any, **kwargs: Any) -> None:
        end = kwargs.get("end", "\n")
        text = " ".join(str(arg) for arg in args)
        print(text, end=end)

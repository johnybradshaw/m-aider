"""Minimal prompt stubs for rich."""

from __future__ import annotations

from typing import Any


class Prompt:
    """Minimal stand-in for rich.prompt.Prompt."""

    @staticmethod
    def ask(prompt: str, default: str | None = None, **kwargs: Any) -> str:
        response = input(f"{prompt} ")
        if response == "" and default is not None:
            return default
        return response


class Confirm:
    """Minimal stand-in for rich.prompt.Confirm."""

    @staticmethod
    def ask(prompt: str, default: bool = False, **kwargs: Any) -> bool:
        response = input(f"{prompt} ").strip().lower()
        if response == "":
            return default
        return response in {"y", "yes", "true", "1"}

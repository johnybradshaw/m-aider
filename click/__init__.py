"""Minimal click stub for test environments without click installed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


class Abort(Exception):
    """Raised to abort command execution."""


@dataclass
class Choice:
    """Minimal click.Choice replacement."""

    choices: Iterable[str]
    case_sensitive: bool = True


class Context:
    """Minimal click.Context replacement."""

    def __init__(self, command: Callable[..., Any]):
        self.command = command


def _passthrough_decorator(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


command = _passthrough_decorator
group = _passthrough_decorator
option = _passthrough_decorator
argument = _passthrough_decorator
version_option = _passthrough_decorator


__all__ = [
    "Abort",
    "Choice",
    "Context",
    "argument",
    "command",
    "group",
    "option",
    "version_option",
]

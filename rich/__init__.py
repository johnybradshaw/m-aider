"""Minimal rich stub for test environments without rich installed."""

from .console import Console
from .panel import Panel
from .progress import Progress, SpinnerColumn, TextColumn
from .prompt import Confirm, Prompt
from .table import Table

__all__ = [
    "Console",
    "Confirm",
    "Panel",
    "Progress",
    "Prompt",
    "SpinnerColumn",
    "Table",
    "TextColumn",
]

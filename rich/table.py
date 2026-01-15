"""Minimal table stub for rich."""

from __future__ import annotations

from typing import Any, Iterable


class Table:
    """Minimal stand-in for rich.table.Table."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.rows: list[Iterable[Any]] = []

    def add_column(self, *args: Any, **kwargs: Any) -> None:
        return None

    def add_row(self, *args: Any, **kwargs: Any) -> None:
        self.rows.append(args)

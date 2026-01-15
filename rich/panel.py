"""Minimal panel stub for rich."""

from __future__ import annotations


class Panel:
    """Minimal stand-in for rich.panel.Panel."""

    def __init__(self, renderable, **kwargs):
        self.renderable = renderable
        self.kwargs = kwargs

    @classmethod
    def fit(cls, renderable, **kwargs):
        return cls(renderable, **kwargs)

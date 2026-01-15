"""Minimal linode_api4 stubs used for tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Instance:
    """Minimal stand-in for linode_api4.Instance."""

    client: Any
    id: int
    data: dict[str, Any]


class _LinodeEndpoint:
    def types(self) -> list[Any]:
        return []


class LinodeClient:
    """Minimal stand-in for linode_api4.LinodeClient."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token
        self.linode = _LinodeEndpoint()

    def regions(self) -> list[Any]:
        return []

    def load(self, model: type, instance_id: int) -> Any:
        return model(self, instance_id, {})


__all__ = ["Instance", "LinodeClient"]

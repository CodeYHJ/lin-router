"""Generic optional runtime capabilities supplied by a composition root."""
from __future__ import annotations

from typing import Collection, Mapping, Protocol


class OptionalCapabilities(Protocol):
    """Optional settings and side effects owned outside the Server runtime."""

    def setting_keys(self) -> Collection[str]: ...

    def read_settings(self) -> Mapping[str, object]: ...

    def snapshot(self) -> object: ...

    def apply_settings(self, patch: Mapping[str, object]) -> None: ...

    def restore(self, snapshot: object) -> None: ...


__all__ = ["OptionalCapabilities"]

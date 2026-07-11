"""Internal context for upstream protocol failures; not an external API error."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class UpstreamAdapterError(Exception):
    operation: str
    provider: str
    group_id: str
    original: Exception
    status_code: Optional[int] = None

    def __str__(self) -> str:
        return str(self.original)

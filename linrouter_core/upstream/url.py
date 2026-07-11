"""Existing upstream URL normalization facade."""
from __future__ import annotations


def resolve_endpoint(base_url: str, path: str) -> str:
    """Return the existing upstream endpoint shape without route decisions."""
    base = base_url.rstrip("/")
    suffix = path.lstrip("/")
    if suffix.startswith("v1/"):
        suffix = suffix[3:]
    return f"{base}/{suffix}"

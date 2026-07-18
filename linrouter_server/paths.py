"""Filesystem-only paths and capabilities for the headless server."""
from __future__ import annotations

from pathlib import Path


class ServerPlatform:
    """Filesystem adapter used by Docker and other headless server launches."""

    def __init__(self, config_path: str | Path | None = None, resource_root: str | Path | None = None) -> None:
        self._config_path = Path(config_path).expanduser().resolve() if config_path else None
        self._resource_root = (
            Path(resource_root).expanduser().resolve()
            if resource_root is not None
            else Path(__file__).resolve().parents[1]
        )

    def get_project_root(self) -> Path:
        return self._resource_root

    def get_config_path(self, filename: str = "lin-router-config.json") -> Path:
        path = self._config_path or (Path.home() / ".config" / "LinRouter" / filename)
        if self._config_path is None and filename != path.name:
            path = path.parent / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def get_log_dir(self) -> Path:
        path = (self._config_path.parent if self._config_path else Path.home() / ".local" / "share" / "LinRouter") / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_resource_path(self, *parts: str) -> Path:
        root = self._resource_root.resolve()
        candidate = root.joinpath(*parts).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("resource path escapes runtime resource root") from exc
        return candidate

"""Desktop capability adapter injected into the shared server runtime."""
from __future__ import annotations

from typing import Any, Mapping

from .settings import DESKTOP_SETTINGS


class DesktopCapabilities:
    def __init__(self, platform: Any, settings_store: Any) -> None:
        self.platform = platform
        self.settings_store = settings_store

    def describe(self) -> Mapping[str, Mapping[str, bool]]:
        return {
            "desktop": {
                "available": True,
                "supports_autostart": True,
                "supports_start_minimized": True,
            }
        }

    def setting_keys(self) -> tuple[str, ...]:
        return tuple(DESKTOP_SETTINGS)

    def read_settings(self) -> Mapping[str, object]:
        return {
            "auto_start": bool(self.platform.is_autostart_enabled()),
            "start_minimized": bool(self.settings_store.get("start_minimized", False)),
        }

    def validate_settings(self, patch: Mapping[str, object]) -> Mapping[str, object]:
        allowed = {"auto_start", "start_minimized"}
        if any(key not in allowed or not isinstance(value, bool) for key, value in patch.items()):
            raise ValueError("invalid desktop setting")
        return dict(patch)

    def snapshot(self) -> Mapping[str, object]:
        return dict(self.read_settings())

    def apply_settings(self, patch: Mapping[str, object]) -> None:
        self.validate_settings(patch)
        if "auto_start" in patch and not self.platform.set_autostart(bool(patch["auto_start"])):
            raise RuntimeError("desktop autostart update failed")

    def restore(self, snapshot: Mapping[str, object]) -> None:
        if "auto_start" in snapshot and not self.platform.set_autostart(bool(snapshot["auto_start"])):
            raise RuntimeError("desktop autostart restore failed")

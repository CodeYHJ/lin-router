from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Mapping

DEFAULT_SETTINGS = {
    "theme": "system",
    "auto_refresh_logs": True,
    "debug_mode": False,
    "upstream_http_client": "urllib",
    "upstream_http2": False,
    "upstream_keepalive": False,
    "debug_capture_enabled": False,
    "debug_capture_last_body": False,
    "normalize_tools_order": False,
    "smart_breaker_enabled": False,
}


class SettingsStore:
    """独立存放用户设置，避免污染 lin-router-config.json。"""

    def __init__(
        self,
        config_path: Path,
        *,
        extra_defaults: Mapping[str, Any] | None = None,
    ) -> None:
        # settings 文件与配置文件放在同一目录，便于一起迁移
        self.path = config_path.parent / "lin-router-settings.json"
        self._lock = threading.RLock()
        self._defaults: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        if extra_defaults:
            self._defaults.update(dict(extra_defaults))
        self._allowed_keys = frozenset(self._defaults)
        self._settings: Dict[str, Any] = dict(self._defaults)
        self.load()

    def _normalize(self, raw: Mapping[str, Any]) -> Dict[str, Any]:
        values = {
            key: value
            for key, value in raw.items()
            if key in self._allowed_keys
        }
        # 兼容旧配置：将已废弃的 debug_capture_body 迁移到 PRD 指定的
        # debug_capture_last_body，但仍需通过当前运行方式的 schema 过滤。
        if "debug_capture_body" in raw and "debug_capture_last_body" in self._allowed_keys:
            values["debug_capture_last_body"] = bool(raw["debug_capture_body"])
        return {**self._defaults, **values}

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                with self._lock:
                    self._settings = self._normalize(raw)
        except Exception:
            pass

    def save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            tmp.replace(self.path)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def update(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            allowed_updates = {
                key: value
                for key, value in new_settings.items()
                if key in self._allowed_keys
            }
            self._settings = {**self._defaults, **self._settings, **allowed_updates}
            self.save()
            return dict(self._settings)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._settings)

    @property
    def allowed_keys(self) -> frozenset[str]:
        return self._allowed_keys

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import linrouter_server.application as app
import linrouter_desktop.tray as desktop


class FakeGuard:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self) -> bool:
        self.acquire_calls += 1
        return self.acquired

    def release(self) -> None:
        self.release_calls += 1

    def is_already_running(self) -> bool:
        return not self.acquired


class FakePlatform:
    def __init__(self, guard: FakeGuard) -> None:
        self.guard = guard
        self.create_guard_calls = 0

    def create_single_instance_guard(self) -> FakeGuard:
        self.create_guard_calls += 1
        return self.guard


class CapturedTray:
    instances: list["CapturedTray"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.run_calls = 0
        CapturedTray.instances.append(self)

    def run(self) -> None:
        self.run_calls += 1


def test_desktop_parse_args_accepts_explicit_host_port_and_marks_isolated() -> None:
    args = desktop.parse_args(["--host", "127.0.0.1", "--port", "18561", "--config", "empty.json"])

    assert args.host == "127.0.0.1"
    assert args.port == 18561
    assert args.config == "empty.json"
    assert args.isolated_launch is True


def test_desktop_default_launch_keeps_single_instance_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = FakeGuard(acquired=True)
    platform = FakePlatform(guard)
    CapturedTray.instances.clear()

    monkeypatch.setattr(desktop, "get_platform", lambda: platform)
    monkeypatch.setattr(desktop, "LinRouterTray", CapturedTray)

    desktop.main([])

    assert platform.create_guard_calls == 1
    assert guard.acquire_calls == 1
    assert guard.release_calls == 1
    assert len(CapturedTray.instances) == 1
    assert CapturedTray.instances[0].kwargs == {
        "tray_mode": False,
        "config_path": None,
        "host": desktop.HOST,
        "port": desktop.DEFAULT_START_PORT,
    }
    assert CapturedTray.instances[0].run_calls == 1


def test_desktop_existing_default_instance_focuses_default_port_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = FakeGuard(acquired=False)
    platform = FakePlatform(guard)
    focused: list[tuple[int, str]] = []

    monkeypatch.setattr(desktop, "get_platform", lambda: platform)
    monkeypatch.setattr(desktop, "focus_existing_instance", lambda port, host=desktop.HOST: focused.append((port, host)) or True)

    with pytest.raises(SystemExit) as exc_info:
        desktop.main([])

    assert exc_info.value.code == 0
    assert focused == [(desktop.DEFAULT_START_PORT, desktop.HOST)]
    assert platform.create_guard_calls == 1
    assert guard.acquire_calls == 1
    assert guard.release_calls == 0


def test_desktop_isolated_launch_skips_single_instance_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    guard = FakeGuard(acquired=False)
    platform = FakePlatform(guard)
    CapturedTray.instances.clear()
    config_path = tmp_path / "lin-router-config.json"

    monkeypatch.setattr(desktop, "get_platform", lambda: platform)
    monkeypatch.setattr(desktop, "LinRouterTray", CapturedTray)

    desktop.main(["--host", "127.0.0.1", "--port", "18562", "--config", str(config_path)])

    assert platform.create_guard_calls == 0
    assert guard.acquire_calls == 0
    assert guard.release_calls == 0
    assert len(CapturedTray.instances) == 1
    assert CapturedTray.instances[0].kwargs == {
        "tray_mode": False,
        "config_path": config_path,
        "host": "127.0.0.1",
        "port": 18562,
    }
    assert CapturedTray.instances[0].run_calls == 1


def test_desktop_tray_start_server_forwards_isolated_host_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    class FakeDesktopPlatform:
        def is_autostart_enabled(self) -> bool:
            return False

    class FakeRouter:
        log_file = tmp_path / "lin-router-logs.jsonl"

    class FakeServer:
        router = FakeRouter()

        def serve_forever(self) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def server_close(self) -> None:
            return None

    platform = FakeDesktopPlatform()

    def fake_create_server(
        host: str,
        port: int,
        config_path: Path,
        *,
        platform: Any,
        optional_capabilities: Any,
        settings_store_instance: Any,
        optional_resource_root: Path,
        optional_resource_prefix: str,
        optional_runtime_script: str,
    ) -> tuple[FakeServer, int, Path]:
        calls.append(
            {
                "host": host,
                "port": port,
                "config_path": config_path,
                "platform": platform,
                "optional_capabilities": optional_capabilities,
                "settings_store_instance": settings_store_instance,
                "optional_resource_root": optional_resource_root,
                "optional_resource_prefix": optional_resource_prefix,
                "optional_runtime_script": optional_runtime_script,
            }
        )
        return FakeServer(), port, config_path

    monkeypatch.setattr(app, "create_server", fake_create_server)
    monkeypatch.setattr(desktop, "get_platform", lambda: platform)

    config_path = tmp_path / "lin-router-config.json"
    tray = desktop.LinRouterTray(config_path=config_path, host="127.0.0.1", port=18563)

    assert tray.start_server() is True
    try:
        assert len(calls) == 1
        assert calls[0] == {
            "host": "127.0.0.1",
            "port": 18563,
            "config_path": config_path,
            "platform": platform,
            "optional_capabilities": tray.optional_capabilities,
            "settings_store_instance": tray.settings_store,
            "optional_resource_root": Path(desktop.__file__).resolve().parents[1] / "web" / "desktop",
            "optional_resource_prefix": "desktop",
            "optional_runtime_script": '<script src="desktop/js/settings-startup.js"></script>',
        }
        assert tray.ui_url == "http://127.0.0.1:18563"
        assert tray.base_url == "http://127.0.0.1:18563/v1"
        assert tray.log_file == tmp_path / "lin-router-logs.jsonl"
    finally:
        tray.stop_server()


def test_desktop_tray_create_server_type_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeDesktopPlatform:
        def is_autostart_enabled(self) -> bool:
            return False

    def fake_create_server(*args: Any, **kwargs: Any) -> tuple[Any, int, Path]:
        calls.append({"args": args, "kwargs": kwargs})
        raise TypeError("unexpected keyword argument: optional_capabilities")

    platform = FakeDesktopPlatform()
    monkeypatch.setattr(app, "create_server", fake_create_server)
    monkeypatch.setattr(desktop, "get_platform", lambda: platform)

    tray = desktop.LinRouterTray(config_path=tmp_path / "lin-router-config.json", port=18564)

    assert tray.start_server() is False
    assert len(calls) == 1
    assert len(calls[0]["args"]) == 3
    assert set(calls[0]["kwargs"]) == {
        "platform",
        "optional_capabilities",
        "settings_store_instance",
        "optional_resource_root",
        "optional_resource_prefix",
        "optional_runtime_script",
    }
    assert tray.server is None
    assert tray.server_thread is None

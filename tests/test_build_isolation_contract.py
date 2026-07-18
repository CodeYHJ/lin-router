"""Fast, dependency-free contracts for the Docker/Desktop split."""

from __future__ import annotations

import ast
import json
import threading
import urllib.request
from pathlib import Path

from linrouter_desktop.capabilities import DesktopCapabilities
from linrouter_desktop.settings import DESKTOP_SETTINGS
from linrouter_server.application import create_server
from linrouter_server.settings_store import SettingsStore


ROOT = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_server_and_core_do_not_import_desktop_or_packaging() -> None:
    forbidden = ("linrouter_desktop", "linrouter_platform", "packaging")
    for package in ("linrouter_server", "linrouter_core"):
        for source in (ROOT / package).rglob("*.py"):
            assert not any(
                imported == name or imported.startswith(f"{name}.")
                for imported in _imports(source)
                for name in forbidden
            ), source


def test_server_and_core_sources_do_not_contain_desktop_runtime_tokens() -> None:
    forbidden = ("desktop", "auto_start", "start_minimized", "autostart", "single_instance", "pystray")
    for package in (ROOT / "linrouter_server", ROOT / "linrouter_core"):
        for source in package.rglob("*.py"):
            text = source.read_text(encoding="utf-8").lower()
            assert not any(token in text for token in forbidden), source


def test_shared_web_assets_have_no_desktop_only_identifiers() -> None:
    forbidden = ("desktop", "auto_start", "start_minimized", "pystray")
    for source in (ROOT / "web" / "shared").rglob("*"):
        if source.is_file():
            text = source.read_text(encoding="utf-8").lower()
            assert not any(token in text for token in forbidden), source


def test_docker_context_is_explicit_and_excludes_desktop() -> None:
    dockerfile = (ROOT / "packaging" / "docker" / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (ROOT / "packaging" / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    dockerignore = (ROOT / "packaging" / "docker" / "Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "COPY ." not in dockerfile
    assert "COPY linrouter_server/" in dockerfile
    assert "COPY linrouter_core/" in dockerfile
    assert "linrouter_desktop" not in dockerfile
    assert "packaging/desktop" not in dockerfile
    assert 'exec "$@"' in entrypoint
    assert "-m linrouter_server" in entrypoint
    assert "CMD-SHELL" not in dockerfile
    assert "HEALTHCHECK" in dockerfile and "CMD [\"/app/.venv/bin/python\"" in dockerfile
    assert "LINROUTER_PORT" in dockerfile
    for excluded in ("linrouter_desktop", "web/desktop", "packaging/desktop", "resources", ".venvs"):
        assert excluded in dockerignore


def test_desktop_spec_does_not_collect_docker_files() -> None:
    spec = (ROOT / "packaging" / "desktop" / "LinRouter.spec").read_text(encoding="utf-8").lower()
    for forbidden in ("packaging/docker", "dockerfile", "entrypoint.sh"):
        assert forbidden not in spec


def test_desktop_build_uses_a_selected_dependency_manager_neutral_interpreter() -> None:
    build = (ROOT / "packaging" / "desktop" / "build.sh").read_text(encoding="utf-8")
    assert 'LINROUTER_DESKTOP_PYTHON' in build
    assert 'command -v python' in build
    assert 'PYTHON_BIN=' in build
    assert '"$PYTHON_BIN" -m PyInstaller' in build
    assert 'python -m PyInstaller' not in build
    assert 'UV_PROJECT_ENVIRONMENT' not in build
    assert 'uv run' not in build


def test_docker_ci_and_readme_use_isolated_persistent_outputs() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "build_docker_smoke:" in ci
    assert "package_windows_preview:" in ci
    assert "package_macos_preview:" in ci
    assert "packaging/desktop/build.sh" in ci
    assert "docker volume create" in ci
    assert "-v \"$volume_name:/data\"" in ci
    assert "--workpath build/desktop/direct" in readme
    assert "--distpath dist/desktop/direct" in readme
    assert "-v lin-router-data:/data" in readme


def test_desktop_spec_uses_pyinstaller_context_and_root_entry() -> None:
    spec = (ROOT / "packaging" / "desktop" / "LinRouter.spec").read_text(encoding="utf-8")
    assert "SPECPATH" in spec
    assert "Path(__file__)" not in spec
    assert 'PROJECT_ROOT / "desktop.py"' in spec
    assert not (ROOT / "packaging" / "__init__.py").exists()


def test_desktop_composition_can_share_one_settings_store(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.json", extra_defaults=DESKTOP_SETTINGS)
    platform = type(
        "Platform",
        (),
        {
            "is_autostart_enabled": lambda self: False,
            "set_autostart": lambda self, _enabled: True,
            "get_resource_path": lambda self, *parts: tmp_path.joinpath(*parts),
            "get_log_dir": lambda self: tmp_path / "logs",
        },
    )()
    server, _port, _config = create_server(
        "127.0.0.1",
        0,
        tmp_path / "config.json",
        platform=platform,
        settings_store_instance=store,
    )
    try:
        assert server.settings_store is store
    finally:
        server.server_close()


def test_desktop_settings_update_is_visible_through_shared_composition(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.json", extra_defaults=DESKTOP_SETTINGS)
    platform = type(
        "Platform",
        (),
        {
            "is_autostart_enabled": lambda self: False,
            "set_autostart": lambda self, _enabled: True,
            "get_resource_path": lambda self, *parts: tmp_path.joinpath(*parts),
            "get_log_dir": lambda self: tmp_path / "logs",
        },
    )()
    capabilities = DesktopCapabilities(platform, store)
    server, _port, _config = create_server(
        "127.0.0.1",
        0,
        tmp_path / "config.json",
        platform=platform,
        optional_capabilities=capabilities,
        settings_store_instance=store,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = f"http://127.0.0.1:{server.server_address[1]}"
        request = urllib.request.Request(
            f"{address}/api/settings",
            data=json.dumps({"start_minimized": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = json.load(urllib.request.urlopen(request))
        assert response["start_minimized"] is True
        assert store.get("start_minimized") is True
    finally:
        server.shutdown()
        server.server_close()


def test_server_settings_schema_filters_legacy_desktop_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    settings_path = config_path.parent / "lin-router-settings.json"
    settings_path.write_text(
        json.dumps({"theme": "dark", "auto_start": True, "start_minimized": True, "unknown": 1}),
        encoding="utf-8",
    )

    server_store = SettingsStore(config_path)
    assert server_store.to_dict() == {
        "theme": "dark",
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
    server_store.update({"theme": "light"})
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "auto_start" not in persisted
    assert "start_minimized" not in persisted
    assert "unknown" not in persisted

    desktop_store = SettingsStore(config_path, extra_defaults=DESKTOP_SETTINGS)
    assert desktop_store.get("auto_start") is False
    assert desktop_store.get("start_minimized") is False


def test_server_backup_export_excludes_legacy_desktop_keys(tmp_path: Path) -> None:
    from linrouter_core.runtime.config_api_runtime import export_backup_payload
    from linrouter_core.config.store import ConfigStore

    config_path = tmp_path / "config.json"
    settings_path = config_path.parent / "lin-router-settings.json"
    settings_path.write_text(
        json.dumps({"theme": "dark", "auto_start": True, "start_minimized": True}),
        encoding="utf-8",
    )
    payload = export_backup_payload(ConfigStore(config_path), SettingsStore(config_path))
    assert payload["settings"] == {
        "theme": "dark",
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


def test_server_backup_round_trip_and_desktop_setting_rejection(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    (tmp_path / "lin-router-settings.json").write_text(
        json.dumps({"theme": "dark", "auto_start": True, "start_minimized": True}),
        encoding="utf-8",
    )
    server, _port, _config = create_server("127.0.0.1", 0, config_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{address}/api/backup/export") as response:
            backup = json.load(response)
        assert "auto_start" not in backup["settings"]
        assert "start_minimized" not in backup["settings"]

        request = urllib.request.Request(
            f"{address}/api/backup/import",
            data=json.dumps(backup).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            assert response.status == 200

        unsupported = dict(backup)
        unsupported["settings"] = {**backup["settings"], "auto_start": True}
        request = urllib.request.Request(
            f"{address}/api/backup/import",
            data=json.dumps(unsupported).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            assert error.code == 400
            assert json.load(error)["error"]["code"] == "unsupported_capability"
        else:
            raise AssertionError("server must reject Desktop settings in a backup")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

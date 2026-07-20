"""Dependency-manager-neutral contracts for the Server/Desktop split."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _requirements(name: str) -> str:
    return (ROOT / "requirements" / name).read_text(encoding="utf-8")


def test_role_requirements_keep_server_free_of_desktop_and_packaging_dependencies() -> None:
    server = _requirements("server.txt")
    assert "certifi" in server
    assert "httpx[http2]" in server
    for desktop_only in ("pystray", "Pillow", "pyobjc", "pyinstaller", "pytest"):
        assert desktop_only.lower() not in server.lower()


def test_desktop_and_package_requirements_are_layered_on_server() -> None:
    desktop = _requirements("desktop.txt")
    package = _requirements("package.txt")
    test = _requirements("test.txt")
    assert "-r server.txt" in desktop
    assert "pystray" in desktop
    assert "Pillow" in desktop
    assert "pyobjc" in desktop
    assert "-r desktop.txt" in package
    assert "pyinstaller" in package.lower()
    assert "-r server.txt" in test
    assert "pytest" in test


def test_root_requirements_preserves_a_compatibility_install_entrypoint() -> None:
    root_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "-r requirements/desktop.txt" in root_requirements


def test_docker_installs_only_server_requirements_without_uv() -> None:
    dockerfile = (ROOT / "packaging" / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim-bookworm AS dependencies" in dockerfile
    assert "COPY requirements/server.txt /tmp/requirements/server.txt" in dockerfile
    assert "python -m venv /app/.venv" in dockerfile
    assert "/app/.venv/bin/python -m pip install" in dockerfile
    assert "uv" not in dockerfile.lower()
    assert "requirements/desktop.txt" not in dockerfile
    assert "pystray" not in dockerfile.lower()
    assert "pillow" not in dockerfile.lower()
    assert "pyinstaller" not in dockerfile.lower()


def test_project_does_not_require_uv_manifests() -> None:
    assert not (ROOT / "pyproject.toml").exists()
    assert not (ROOT / "uv.lock").exists()
    assert not (ROOT / ".python-version").exists()


def test_preview_entrypoint_does_not_bind_the_local_environment_layout() -> None:
    preview = (ROOT / "scripts" / "server" / "start-preview-18409.bat").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "LINROUTER_SERVER_PYTHON" in preview
    assert ".venvs" not in preview
    assert "uv run" not in preview.lower()
    assert "uv sync" not in preview.lower()
    assert ".venvs" not in readme

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


def test_github_workflows_use_role_requirements_without_uv() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    lowered = ci.lower()
    assert "astral-sh/setup-uv" not in lowered
    assert "uv_project_environment" not in lowered
    assert "uv sync" not in lowered
    assert "uv run" not in lowered
    assert "cache: pip" in ci
    assert "python -m pip install -r requirements/package.txt" in ci
    assert "python -m pip install -r requirements/test.txt" in ci
    assert not (ROOT / ".github" / "workflows" / "package.yml").exists()


def test_github_workflows_use_node24_action_versions() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    docker = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(encoding="utf-8")
    combined = f"{ci}\n{docker}"
    for deprecated in (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/upload-artifact@v4",
        "actions/download-artifact@v4",
        "softprops/action-gh-release@v2",
    ):
        assert deprecated not in combined
    assert "actions/checkout@v6" in combined
    assert "actions/setup-python@v6" in combined
    assert "actions/upload-artifact@v7" in combined


def test_docker_build_workflow_only_builds_the_server_image() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "branches: [main]" in workflow
    assert "refactor/desktop-docker-isolation" not in workflow
    assert "packaging/docker/**" in workflow
    assert "requirements/server.txt" in workflow
    assert "scripts/ci/verify_build_isolation.py" in workflow
    assert "docker build" in workflow
    assert "--file packaging/docker/Dockerfile" in workflow
    assert "docker image inspect" in workflow
    assert "docker run" not in workflow
    assert "packaging/desktop" not in workflow


def test_docker_hub_publish_job_uses_the_server_context_and_shared_secrets() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "branches: [main]" in workflow
    assert "refactor/desktop-docker-isolation" not in workflow
    assert "publish:" in workflow
    assert "needs: build" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "docker/login-action@v3" in workflow
    assert "secrets.DOCKER_USERNAME" in workflow
    assert "secrets.DOCKER_TOKEN" in workflow
    assert "docker/build-push-action@v6" in workflow
    assert "context: ." in workflow
    assert "file: ./packaging/docker/Dockerfile" in workflow
    assert "platforms: linux/amd64,linux/arm64" in workflow
    assert "codeyhj/agent-router:latest" in workflow
    assert "cache-from: type=gha,scope=agent-router-dockerfile" in workflow
    assert "cache-to: type=gha,mode=max,scope=agent-router-dockerfile" in workflow
    assert "packaging/desktop" not in workflow
    assert {path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")} == {
        "ci.yml",
        "docker-build.yml",
    }


def test_release_workflow_is_removed_instead_of_disabled() -> None:
    assert not (ROOT / ".github" / "workflows" / "package.yml").exists()


def test_ci_does_not_contain_a_docker_runtime_smoke_job() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "build_docker_smoke:" not in ci
    assert "docker run" not in ci


def test_preview_entrypoint_does_not_bind_the_local_environment_layout() -> None:
    preview = (ROOT / "scripts" / "server" / "start-preview-18409.bat").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "LINROUTER_SERVER_PYTHON" in preview
    assert ".venvs" not in preview
    assert "uv run" not in preview.lower()
    assert "uv sync" not in preview.lower()
    assert ".venvs" not in readme

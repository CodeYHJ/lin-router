from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scripts_are_grouped_by_owner_without_desktop_compatibility_wrappers() -> None:
    scripts = ROOT / "scripts"
    assert {path.name for path in scripts.iterdir() if path.is_file()} == {"README.md"}
    assert {path.name for path in (scripts / "ci").iterdir() if path.is_file()} == {
        "verify_build_isolation.py",
    }
    assert {path.name for path in (scripts / "server").iterdir() if path.is_file()} == {
        "reasoning_ab_check.py",
        "start-preview-18409.bat",
    }
    for removed in ("build.sh", "generate_icon.py", "release_guard.py", "sign_windows_artifact.py"):
        assert not (scripts / removed).exists()


def test_documentation_separates_current_specs_from_archives() -> None:
    docs = ROOT / "docs"
    assert {path.name for path in docs.iterdir() if path.is_file()} == {
        "README.md",
        "docker-desktop-build-isolation.md",
    }
    assert (docs / "archive" / "backend-v0.6").is_dir()
    assert (docs / "archive" / "prd").is_dir()
    assert (docs / "archive" / "product" / "legacy-roadmap.md").is_file()
    assert (docs / "archive" / "release-checklists").is_dir()
    assert not (ROOT / "PRD").exists()
    assert not (ROOT / "ROADMAP.md").exists()


def test_current_component_docs_use_owner_entrypoints_and_resource_paths() -> None:
    frontend = (ROOT / "frontend" / "README.md").read_text(encoding="utf-8")
    assert "python -m linrouter_server" in frontend
    assert "python app.py" not in frontend
    assert "web/shared" in frontend
    assert "根目录 `static/`" not in frontend


def test_local_markdown_links_resolve() -> None:
    sources = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md"), ROOT / "frontend" / "README.md"]
    missing: list[str] = []
    for source in sources:
        text = source.read_text(encoding="utf-8-sig")
        for raw_target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (source.parent / target).resolve().exists():
                missing.append(f"{source.relative_to(ROOT)} -> {raw_target}")
    assert missing == []

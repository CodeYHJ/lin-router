from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable

SENSITIVE_NAME_PATTERNS = [
    re.compile(r"(^|[\\/])lin-router-config\.json$", re.I),
    re.compile(r"(^|[\\/])lin-router-settings\.json$", re.I),
    re.compile(r"(^|[\\/])lin-router-logs\.jsonl$", re.I),
    re.compile(r"(^|[\\/])\.env$", re.I),
    re.compile(r"\.bak($|-)", re.I),
    re.compile(r"\.backup$", re.I),
    re.compile(r"(^|[\\/])\.tmp([\\/]|$)", re.I),
]

SECRET_PATTERNS = [
    ("openai_style_key", re.compile(rb"sk-[A-Za-z0-9_\-]{12,}")),
    ("bearer_token", re.compile(rb"Bearer\s+[A-Za-z0-9._\-]{16,}", re.I)),
    ("group_route_key", re.compile(rb"lr-[A-Za-z0-9]{8,}")),
    ("aggregate_route_key", re.compile(rb"lr-ag-[A-Za-z0-9]{8,}")),
]

TEXT_SUFFIXES = {
    ".json", ".jsonl", ".txt", ".md", ".py", ".js", ".css", ".html", ".yml", ".yaml", ".env", ".ini", ".cfg", ".log"
}

MAX_SCAN_BYTES = 100 * 1024 * 1024


def iter_files(path: Path) -> Iterable[tuple[str, bytes | None]]:
    if path.is_file():
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename
                    data = None
                    if info.file_size <= MAX_SCAN_BYTES:
                        data = archive.read(info)
                    yield f"{path}!{name}", data
        else:
            data = None
            if path.stat().st_size <= MAX_SCAN_BYTES:
                data = path.read_bytes()
            yield str(path), data
        return

    for child in path.rglob("*"):
        if not child.is_file():
            continue
        rel = str(child.relative_to(path))
        data = None
        if child.stat().st_size <= MAX_SCAN_BYTES:
            data = child.read_bytes()
        yield rel, data


def scan(paths: list[Path]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for target in paths:
        if not target.exists():
            findings.append((str(target), "missing_target"))
            continue
        for display_name, data in iter_files(target):
            normalized = display_name.replace("\\", "/")
            for pattern in SENSITIVE_NAME_PATTERNS:
                if pattern.search(normalized):
                    findings.append((display_name, "sensitive_filename"))
                    break
            if data is None:
                continue
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(data):
                    findings.append((display_name, label))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan Lin Router release artifacts for accidental sensitive data")
    parser.add_argument("paths", nargs="+", help="dist files or directories to scan")
    args = parser.parse_args()
    findings = scan([Path(item).resolve() for item in args.paths])
    if findings:
        print("release guard failed:")
        for path, label in findings:
            print(f"- {path}: {label}")
        return 1
    print("release guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

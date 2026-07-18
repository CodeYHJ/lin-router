#!/usr/bin/env python3
"""Snapshot protected paths and fail if another build changes them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


SNAPSHOT_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_paths(root: Path, paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in paths:
        path = Path(value)
        if path.is_absolute():
            raise ValueError(f"受保护路径必须相对于仓库根目录：{value}")
        resolved = (root / path).resolve(strict=False)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"受保护路径不能离开仓库根目录：{value}") from error
        normalized.append(relative.as_posix())
    return sorted(set(normalized))


def _describe_path(root: Path, relative: str) -> dict[str, dict[str, Any]]:
    target = root / relative
    if target.is_symlink():
        return {".": {"type": "symlink", "target": os.readlink(target)}}
    if not target.exists():
        return {".": {"type": "missing"}}
    if target.is_file():
        return {".": {"type": "file", "sha256": _sha256(target), "size": target.stat().st_size}}

    entries: dict[str, dict[str, Any]] = {".": {"type": "directory"}}
    for directory, directory_names, file_names in os.walk(target, followlinks=False):
        directory_path = Path(directory)
        directory_names.sort()
        file_names.sort()
        for name in directory_names + file_names:
            child = directory_path / name
            child_relative = child.relative_to(target).as_posix()
            if child.is_symlink():
                entries[child_relative] = {"type": "symlink", "target": os.readlink(child)}
            elif child.is_dir():
                entries[child_relative] = {"type": "directory"}
            else:
                entries[child_relative] = {
                    "type": "file",
                    "sha256": _sha256(child),
                    "size": child.stat().st_size,
                }
    return entries


def _capture(root: Path, paths: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    return {relative: _describe_path(root, relative) for relative in paths}


def snapshot(output: Path, protected_paths: list[str]) -> None:
    root = Path.cwd().resolve()
    normalized = _normalize_paths(root, protected_paths)
    payload = {
        "version": SNAPSHOT_VERSION,
        "root": str(root),
        "paths": normalized,
        "entries": _capture(root, normalized),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(snapshot_path: Path) -> None:
    root = Path.cwd().resolve()
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if payload.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"不支持的快照版本：{payload.get('version')}")
    if payload.get("root") != str(root):
        raise ValueError(f"快照仓库根目录不匹配：{payload.get('root')} != {root}")

    paths = _normalize_paths(root, list(payload.get("paths", [])))
    before = payload.get("entries")
    after = _capture(root, paths)
    if before != after:
        changed = sorted(
            path
            for path in set(before or {}) | set(after)
            if (before or {}).get(path) != after.get(path)
        )
        raise RuntimeError("构建越过隔离边界，以下受保护路径发生变化：" + ", ".join(changed))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot", help="记录受保护路径当前内容")
    snapshot_parser.add_argument("--output", required=True, type=Path)
    snapshot_parser.add_argument("paths", nargs="+")

    verify_parser = subparsers.add_parser("verify", help="确认受保护路径未发生变化")
    verify_parser.add_argument("--snapshot", required=True, type=Path)

    arguments = parser.parse_args()
    try:
        if arguments.command == "snapshot":
            snapshot(arguments.output, arguments.paths)
        else:
            verify(arguments.snapshot)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

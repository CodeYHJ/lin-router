#!/usr/bin/env python3
"""Compatibility wrapper for the Desktop release guard."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_IMPLEMENTATION = Path(__file__).resolve().parents[1] / "packaging" / "desktop" / "tools" / "release_guard.py"
_SPEC = importlib.util.spec_from_file_location("_linrouter_release_guard", _IMPLEMENTATION)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"无法加载 Desktop release guard：{_IMPLEMENTATION}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
for _name, _value in vars(_MODULE).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

if __name__ == "__main__":
    raise SystemExit(_MODULE.main())

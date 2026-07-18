#!/usr/bin/env python3
"""Compatibility wrapper for the Desktop icon generator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_IMPLEMENTATION = Path(__file__).resolve().parents[1] / "packaging" / "desktop" / "tools" / "generate_icon.py"
_SPEC = importlib.util.spec_from_file_location("_linrouter_generate_icon", _IMPLEMENTATION)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"无法加载 Desktop icon generator：{_IMPLEMENTATION}")
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
for _name, _value in vars(_MODULE).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

if __name__ == "__main__":
    raise SystemExit(_MODULE.main())

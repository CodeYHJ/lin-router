"""Compatibility facade for the Desktop runtime."""
from __future__ import annotations

import sys

from linrouter_desktop import tray as _implementation

sys.modules[__name__] = _implementation

if __name__ == "__main__":
    _implementation.main()

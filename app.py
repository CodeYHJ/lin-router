"""Compatibility facade for the server implementation.

New code should import from ``linrouter_server``. This module remains so the
existing ``python app.py`` command and legacy integrations keep working.
"""
from __future__ import annotations

import sys

from linrouter_server import application as _implementation

# Keep monkeypatching and ``app.__file__`` based legacy contracts working by
# exposing the implementation module itself under the old module name.
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    _implementation.main()

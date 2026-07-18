"""Compatibility facade for ``linrouter_server.debug_capture``."""
from __future__ import annotations

import sys

from linrouter_server import debug_capture as _implementation

sys.modules[__name__] = _implementation

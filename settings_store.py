"""Compatibility facade for ``linrouter_server.settings_store``."""
from __future__ import annotations

import sys

from linrouter_server import settings_store as _implementation

sys.modules[__name__] = _implementation

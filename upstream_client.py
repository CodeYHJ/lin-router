"""Compatibility facade for ``linrouter_server.upstream_client``."""
from __future__ import annotations

import sys

from linrouter_server import upstream_client as _implementation

sys.modules[__name__] = _implementation

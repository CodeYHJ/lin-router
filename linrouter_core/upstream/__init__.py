"""Protocol-only upstream adaptation for Lin Router."""
from .adapter import UpstreamAdapter
from .errors import UpstreamAdapterError
from .request import (
    BROWSER_UA,
    build_model_fetch_headers,
    build_passthrough_headers,
    build_upstream_headers,
    build_waf_compatible_headers,
    can_forward_header,
)
from .url import resolve_endpoint

__all__ = [
    "BROWSER_UA", "UpstreamAdapter", "UpstreamAdapterError", "build_model_fetch_headers",
    "build_passthrough_headers", "build_upstream_headers", "build_waf_compatible_headers",
    "can_forward_header", "resolve_endpoint",
]

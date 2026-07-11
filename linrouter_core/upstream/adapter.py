"""Stable facade for existing upstream protocol adaptation."""
from __future__ import annotations

import ssl
from typing import Any, Dict, List, Tuple

from . import models
from .request import build_request_headers
from .url import resolve_endpoint


class UpstreamAdapter:
    """Protocol-only facade. It owns no routing, health, or HTTP API behavior."""

    def __init__(self, ssl_context: ssl.SSLContext | None = None) -> None:
        self._ssl_context = ssl_context

    @staticmethod
    def resolve_endpoint(base_url: str, path: str) -> str:
        return resolve_endpoint(base_url, path)

    @staticmethod
    def build_request(
        *, base_url: str, auth_key: str, incoming_headers: Dict[str, str], stream: bool,
        waf_compatible: bool, waf_accept_policy: str,
    ) -> Dict[str, str]:
        return build_request_headers(
            base_url=base_url,
            auth_key=auth_key,
            incoming_headers=incoming_headers,
            stream=stream,
            waf_compatible=waf_compatible,
            waf_accept_policy=waf_accept_policy,
        )

    def fetch_models(self, base_url: str, auth_key: str) -> Tuple[str, Dict[str, str], int, List[Dict[str, Any]]]:
        return models.fetch_models(base_url, auth_key, self._ssl_context)

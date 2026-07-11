"""Upstream model-list protocol operation without HTTP response mapping."""
from __future__ import annotations

import json
import ssl
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen

from .request import build_model_fetch_headers
from .url import resolve_endpoint


def fetch_models(base_url: str, auth_key: str, ssl_context: ssl.SSLContext | None) -> Tuple[str, Dict[str, str], int, List[Dict[str, Any]]]:
    """Fetch and parse an existing OpenAI-compatible model list.

    HTTP/network exceptions intentionally propagate unchanged so the existing
    handler remains the sole owner of logs and external error mapping.
    """
    target_url = resolve_endpoint(base_url, "/v1/models")
    headers = build_model_fetch_headers(auth_key)
    request = Request(target_url, headers=headers, method="GET")
    with urlopen(request, timeout=60, context=ssl_context) as resp:
        status = resp.status
        raw = resp.read()
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise RuntimeError("上游模型列表格式无效")
    return target_url, headers, status, [item for item in data if isinstance(item, dict)]

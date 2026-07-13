from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app import ArkProxyRouter, ConnectionGroup
from linrouter_core.upstream import UpstreamAdapter
from linrouter_core.upstream import models as upstream_models


class Store:
    groups = []
    models = []


def test_adapter_url_and_request_facades_preserve_existing_header_shapes(tmp_path: Path) -> None:
    router = ArkProxyRouter(Store(), None, tmp_path / "logs.jsonl")
    group = ConnectionGroup(
        id="g1", name="relay", provider_type="relay", base_url="https://relay.example/v1",
        waf_compatible=True, waf_accept_policy="passthrough",
    )
    incoming = {
        "Authorization": "Bearer client-key",
        "Accept": "application/custom",
        "X-Keep": "yes",
        "X-Stainless-Lang": "python",
        "User-Agent": "client",
    }

    assert router._resolve_url(group.base_url, "/v1/chat/completions") == "https://relay.example/v1/chat/completions"
    headers = router._headers_for(group, "upstream-key", incoming, stream=True)
    assert headers["authorization"] == "Bearer upstream-key"
    assert headers["host"] == "relay.example"
    assert headers["user-agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    assert headers["accept"] == "application/custom"
    assert headers["X-Keep"] == "yes"
    assert "Authorization" not in headers
    assert "X-Stainless-Lang" not in headers


def test_waf_default_forces_sse_accept_for_streaming_requests(tmp_path: Path) -> None:
    router = ArkProxyRouter(Store(), None, tmp_path / "logs.jsonl")
    group = ConnectionGroup(
        id="g1", name="relay", provider_type="relay", base_url="https://relay.example/v1",
        waf_compatible=True, waf_accept_policy="default",
    )

    headers = router._headers_for(
        group,
        "upstream-key",
        {"Accept": "application/json", "User-Agent": "Hermes/1.0"},
        stream=True,
    )

    assert headers["accept"] == "text/event-stream"


def test_waf_passthrough_accept_remains_explicit_override(tmp_path: Path) -> None:
    router = ArkProxyRouter(Store(), None, tmp_path / "logs.jsonl")
    group = ConnectionGroup(
        id="g1", name="relay", provider_type="relay", base_url="https://relay.example/v1",
        waf_compatible=True, waf_accept_policy="passthrough",
    )

    headers = router._headers_for(
        group,
        "upstream-key",
        {"Accept": "application/custom"},
        stream=True,
    )

    assert headers["accept"] == "application/custom"


def test_router_uses_explicit_injected_adapter_without_changing_waf_decision(tmp_path: Path) -> None:
    class Adapter:
        def __init__(self) -> None:
            self.calls = []

        @staticmethod
        def resolve_endpoint(base_url: str, path: str) -> str:
            return f"{base_url.rstrip('/')}/injected/{path.lstrip('/')}"

        def build_request(self, **kwargs):
            self.calls.append(kwargs)
            return {"X-Adapter": "ok"}

    adapter = Adapter()
    router = ArkProxyRouter(Store(), None, tmp_path / "logs.jsonl", upstream_adapter=adapter)
    group = ConnectionGroup(id="g1", name="relay", provider_type="relay", base_url="https://relay.example", waf_compatible=True)

    assert router._headers_for(group, "key", {"User-Agent": "Codex"}, stream=False) == {"X-Adapter": "ok"}
    assert adapter.calls[0]["waf_compatible"] is True
    assert router._resolve_url(group.base_url, "/v1/models") == "https://relay.example/injected/v1/models"


def test_model_fetch_parses_existing_shape_and_preserves_http_error() -> None:
    class Response:
        status = 200

        def read(self) -> bytes:
            return b'{"data":[{"id":"a"},"invalid"]}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    adapter = UpstreamAdapter(None)
    with patch.object(upstream_models, "urlopen", return_value=Response()) as opener:
        url, headers, status, data = adapter.fetch_models("https://relay.example/v1", "secret")

    assert url == "https://relay.example/v1/models"
    assert status == 200
    assert data == [{"id": "a"}]
    assert headers["authorization"] == "Bearer secret"
    assert opener.call_args.kwargs["timeout"] == 60

    error = RuntimeError("network failed")
    with patch.object(upstream_models, "urlopen", side_effect=error):
        with pytest.raises(RuntimeError) as raised:
            adapter.fetch_models("https://relay.example", "secret")
    assert raised.value is error

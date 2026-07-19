from __future__ import annotations

import json
import socket
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from linrouter_server.application import create_server


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(port: int, path: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def test_health_route_is_reachable_without_changing_existing_get_dispatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config.json"
        server, port, _ = create_server("127.0.0.1", _get_free_port(), config_path)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            health_status, health_headers, health_body = _get(port, "/health")
            assert health_status == 200
            assert health_headers["Content-Type"].startswith("application/json")
            assert json.loads(health_body.decode("utf-8"))["ok"] is True

            root_status, root_headers, _ = _get(port, "/")
            assert root_status == 200
            assert root_headers["Content-Type"].startswith("text/html")

            api_status, api_headers, api_body = _get(port, "/api/state")
            assert api_status == 200
            assert api_headers["Content-Type"].startswith("application/json")
            assert "settings" in json.loads(api_body.decode("utf-8"))

            v1_status, v1_headers, v1_body = _get(port, "/v1/models")
            assert v1_status == 401
            assert v1_headers["Content-Type"].startswith("application/json")
            assert "error" in json.loads(v1_body.decode("utf-8"))

            static_status, static_headers, static_body = _get(port, "/css/base.css")
            assert static_status == 200
            assert static_headers["Content-Type"].startswith("text/css")
            assert static_body
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

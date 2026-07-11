"""HTTP proxy-response execution behind the ``RouterHandler`` compatibility facade."""
from __future__ import annotations

from typing import Any, Dict


def handle_proxy_request(
    handler: Any,
    path: str,
    payload: Dict[str, Any],
    route: Any,
    raw_body: bytes,
) -> None:
    """Execute the existing ``/v1`` and ``/chat`` POST response path via a handler facade."""
    stream = bool(payload.get("stream"))
    try:
        if stream:
            status, headers, iterator, request_id = handler.router.stream(path, payload, route, dict(handler.headers.items()), raw_body)
            handler.send_response(status)
            for key, value in headers.items():
                if key.lower() in {"content-length", "connection", "transfer-encoding"}:
                    continue
                handler.send_header(key, value)
            handler.send_header("Content-Type", headers.get("Content-Type", "text/event-stream; charset=utf-8"))
            handler.end_headers()
            try:
                for chunk in iterator:
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
            finally:
                iterator.close()
                handler.router.finalize_stream_if_needed(request_id)
            return
        status, headers, data = handler.router.call(path, payload, route, dict(handler.headers.items()), raw_body)
        handler.send_response(status)
        for key, value in headers.items():
            if key.lower() in {"content-length", "connection", "transfer-encoding"}:
                continue
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except handler._all_models_failed_error_type as err:
        handler._send_all_models_failed_error(err)
    except Exception as err:
        handler._send_json({
            "error": {
                "message": f"服务器内部错误: {err}",
                "type": "internal_server_error",
                "code": "internal_error",
            }
        }, status=500)
    return

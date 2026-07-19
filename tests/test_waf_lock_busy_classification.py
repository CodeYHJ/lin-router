#!/usr/bin/env python3
"""验证显式串行保护等待超时被分类为候选忙，而不是上游 timeout cooldown。"""

import json
import socket
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from linrouter_server.application import ArkProxyRouter as Router, ConfigStore, RouteContext


class SlowStreamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"busy"}}]}\n\n')
        self.wfile.flush()
        time.sleep(0.2)
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(handler, port):
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def build_config(port):
    group_id = uuid.uuid4().hex
    model_id = uuid.uuid4().hex
    return {
        "groups": [
            {
                "id": group_id,
                "name": "relay-busy",
                "provider_type": "relay",
                "base_url": f"http://127.0.0.1:{port}/v1",
                "route_key": "lr-busy",
                "auto_model_name": "lin-router-auto",
                "waf_compatible": True,
                "serial_protection": True,
                "stream_idle_timeout": 20,
            }
        ],
        "models": [
            {
                "id": model_id,
                "name": "busy-model",
                "ep_id": "gpt-test",
                "group_id": group_id,
                "upstream_model": "gpt-test",
                "api_key": "sk-test",
                "usable": True,
            }
        ],
    }


def test_serial_protection_timeout_is_candidate_busy_not_cooldown():
    port = get_free_port()
    server = start_server(SlowStreamHandler, port)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        config_path = f.name
        json.dump(build_config(port), f, ensure_ascii=False, indent=2)

    try:
        store = ConfigStore(config_path)
        router = Router(store, settings_store=None)
        group = store.groups[0]
        ctx = RouteContext(
            client_key=group.route_key,
            group=group,
            group_id=group.id,
            provider_type=group.provider_type,
            base_url=group.base_url,
            display_name=group.name,
            passthrough=False,
        )
        payload = {"model": "busy-model", "messages": [{"role": "user", "content": "hi"}], "stream": True}

        status, _headers, iterator, request_id = router.stream("/v1/chat/completions", payload, ctx)
        assert status == 200
        first_chunk = next(iterator)
        assert b"busy" in first_chunk

        # 直接模拟等待失败，避免为验证显式串行保护分支等待十秒。
        router.runtime.concurrency._acquire = lambda _lock: (False, 7)
        status2, _headers2, body2, = router.call("/v1/chat/completions", {"model": "busy-model", "messages": [{"role": "user", "content": "second"}]}, ctx)
        assert status2 == 503
        assert "串行保护" in body2[0].decode("utf-8")
        busy_logs = [log for log in router.logs if log.event == "serial_protection_timeout"]
        assert busy_logs, "应记录 serial_protection_timeout 日志"
        log = busy_logs[0]
        assert log.failure_scope == "busy"
        assert log.cooldown_applied is False
        assert "fallback_reason=large_task_in_progress" in log.detail
        assert "request_concurrency=serial_protection" in log.detail
        assert store.models[0].cooldown_until == 0

        iterator.close()
        router.finalize_stream_if_needed(request_id)
    finally:
        server.shutdown()
        Path(config_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_serial_protection_timeout_is_candidate_busy_not_cooldown()

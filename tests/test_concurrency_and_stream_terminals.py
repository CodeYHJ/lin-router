from __future__ import annotations

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

from app import ArkProxyRouter, ConfigStore, RouteContext


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_config(port: int, *, serial_protection: bool = False, stream_idle_timeout: int = 5) -> dict:
    group_id = uuid.uuid4().hex
    return {
        "groups": [{
            "id": group_id,
            "name": "parallel-relay",
            "provider_type": "relay",
            "base_url": f"http://127.0.0.1:{port}/v1",
            "route_key": "lr-parallel",
            "waf_compatible": True,
            "serial_protection": serial_protection,
            "stream_idle_timeout": stream_idle_timeout,
        }],
        "models": [{
            "id": uuid.uuid4().hex,
            "name": "same-model",
            "ep_id": "gpt-test",
            "upstream_model": "gpt-test",
            "group_id": group_id,
            "api_key": "sk-test",
            "usable": True,
        }],
    }


def make_router(tmp_path: str, port: int, **kwargs: object) -> tuple[ArkProxyRouter, RouteContext]:
    config_path = Path(tmp_path) / "config.json"
    config_path.write_text(json.dumps(build_config(port, **kwargs), ensure_ascii=False), encoding="utf-8")
    store = ConfigStore(config_path)
    router = ArkProxyRouter(store, settings_store=None, log_file=Path(tmp_path) / "logs.jsonl")
    group = store.groups[0]
    return router, RouteContext(
        client_key=group.route_key,
        group=group,
        group_id=group.id,
        provider_type=group.provider_type,
        base_url=group.base_url,
        display_name=group.name,
        passthrough=False,
    )


class ConcurrentTerminalHandler(BaseHTTPRequestHandler):
    release = threading.Event()
    hold_open = threading.Event()
    started = threading.Event()
    lock = threading.Lock()
    request_count = 0

    @classmethod
    def reset(cls) -> None:
        cls.release = threading.Event()
        cls.hold_open = threading.Event()
        cls.started = threading.Event()
        cls.request_count = 0

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(content_length) or b"{}")
        content = str(((payload.get("messages") or [{}])[0] or {}).get("content") or "")
        terminal = b"data: [DONE]\n\n" if content == "done" else b'data: {"type":"response.completed","response":{"usage":{"input_tokens":3,"output_tokens":2}}}\n\n'
        with type(self).lock:
            type(self).request_count += 1
            if type(self).request_count >= 2:
                type(self).started.set()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'data: {"type":"response.output_text.delta","delta":"working"}\n\n')
            self.wfile.flush()
            type(self).release.wait(5)
            self.wfile.write(terminal)
            self.wfile.flush()
            type(self).hold_open.wait(5)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, _format: str, *_args: object) -> None:
        return


class ImmediateTerminalHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(content_length) or b"{}")
        signal = str(((payload.get("messages") or [{}])[0] or {}).get("content") or "response.completed")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'data: {"type":"response.output_text.delta","delta":"working"}\n\n')
        if signal != "eof":
            self.wfile.write(f'data: {{"type":"{signal}"}}\n\n'.encode("utf-8"))
        self.wfile.flush()

    def log_message(self, _format: str, *_args: object) -> None:
        return


class IdleAfterFirstChunkHandler(BaseHTTPRequestHandler):
    release = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.release = threading.Event()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'data: {"type":"response.output_text.delta","delta":"working"}\n\n')
            self.wfile.flush()
            type(self).release.wait(5)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, _format: str, *_args: object) -> None:
        return


def start_server(handler_type: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", get_free_port()), handler_type)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def stream_payload(content: str) -> dict:
    return {"model": "same-model", "messages": [{"role": "user", "content": content}], "stream": True}


def test_waf_compatible_same_candidate_streams_run_in_parallel_and_finalize_before_eof() -> None:
    ConcurrentTerminalHandler.reset()
    upstream = start_server(ConcurrentTerminalHandler)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            router, context = make_router(tmp, upstream.server_address[1])
            status_a, _headers_a, stream_a, request_a = router.stream("/v1/chat/completions", stream_payload("completed"), context)
            assert status_a == 200
            assert b"working" in next(stream_a)

            status_b, _headers_b, stream_b, request_b = router.stream("/v1/chat/completions", stream_payload("done"), context)
            assert status_b == 200
            assert b"working" in next(stream_b)
            assert ConcurrentTerminalHandler.started.wait(1)
            assert ConcurrentTerminalHandler.request_count == 2
            live = router.live_requests_payload()
            assert live["count"] == 2
            assert {item["request_id"] for item in live["requests"]} == {request_a, request_b}
            assert all(item["stage"] == "streaming" for item in live["requests"])

            ConcurrentTerminalHandler.release.set()
            started_at = time.perf_counter()
            assert b"response.completed" in b"".join(stream_a)
            assert time.perf_counter() - started_at < 1
            assert router.live_requests_payload()["count"] == 1

            assert b"[DONE]" in b"".join(stream_b)
            assert router.live_requests_payload()["count"] == 0

            logs_by_request = {item.request_id: item for item in router.logs if item.request_id in {request_a, request_b}}
            assert "completion_signal=response.completed" in logs_by_request[request_a].detail
            assert "completion_signal=[DONE]" in logs_by_request[request_b].detail
            assert all("lifecycle=stream_done" in item.detail for item in logs_by_request.values())
            assert all("request_concurrency=parallel" in item.detail for item in logs_by_request.values())
            assert not any(item.event in {"waf_lock_timeout", "serial_protection_timeout"} for item in router.logs)
    finally:
        ConcurrentTerminalHandler.release.set()
        ConcurrentTerminalHandler.hold_open.set()
        upstream.shutdown()
        upstream.server_close()


def test_response_failed_and_incomplete_have_distinct_stream_lifecycles() -> None:
    upstream = start_server(ImmediateTerminalHandler)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            router, context = make_router(tmp, upstream.server_address[1])
            for signal, lifecycle in (("response.failed", "stream_failed"), ("response.incomplete", "stream_incomplete")):
                status, _headers, stream, request_id = router.stream("/v1/responses", stream_payload(signal), context)
                assert status == 200
                assert signal.encode("utf-8") in b"".join(stream)
                log = next(item for item in router.logs if item.request_id == request_id)
                assert f"completion_signal={signal}" in log.detail
                assert f"lifecycle={lifecycle}" in log.detail
                assert log.failure_scope == "upstream"
                assert router.live_requests_payload()["count"] == 0
    finally:
        upstream.shutdown()
        upstream.server_close()


def test_stream_completion_signal_parses_done_and_structured_response_events() -> None:
    assert ArkProxyRouter._stream_completion_signal(b"data: [DONE]\n") == "[DONE]"
    assert ArkProxyRouter._stream_completion_signal(b'data: {"type":"response.completed"}\n') == "response.completed"
    assert ArkProxyRouter._stream_completion_signal(b'data: {"event":"response.failed"}\n') == "response.failed"
    assert ArkProxyRouter._stream_completion_signal(b'event: response.incomplete\n') == "event:response.incomplete"


def test_stream_eof_remains_a_compatible_completion_signal() -> None:
    upstream = start_server(ImmediateTerminalHandler)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            router, context = make_router(tmp, upstream.server_address[1])
            status, _headers, stream, request_id = router.stream("/v1/chat/completions", stream_payload("eof"), context)
            assert status == 200
            assert b"working" in b"".join(stream)
            log = next(item for item in router.logs if item.request_id == request_id)
            assert "lifecycle=stream_done" in log.detail
            assert "completion_signal=eof" in log.detail
    finally:
        upstream.shutdown()
        upstream.server_close()


def test_post_first_byte_idle_timeout_is_not_recorded_as_client_disconnect() -> None:
    IdleAfterFirstChunkHandler.reset()
    upstream = start_server(IdleAfterFirstChunkHandler)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            router, context = make_router(tmp, upstream.server_address[1], stream_idle_timeout=1)
            status, _headers, stream, request_id = router.stream("/v1/chat/completions", stream_payload("idle"), context)
            assert status == 200
            assert b"working" in next(stream)
            list(stream)
            log = next(item for item in router.logs if item.request_id == request_id)
            assert log.status == "timeout"
            assert "lifecycle=stream_idle_timeout" in log.detail
            assert "lifecycle=client_disconnected" not in log.detail
    finally:
        IdleAfterFirstChunkHandler.release.set()
        upstream.shutdown()
        upstream.server_close()

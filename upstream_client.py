from __future__ import annotations

import queue
import ssl
import threading
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class StreamIdleTimeoutError(TimeoutError):
    pass


class UpstreamResponse:
    """统一上游响应包装，兼容 urllib 与 httpx。

    提供 readline(timeout_seconds) 方法以支持流式空闲超时检测。
    """

    def __init__(
        self,
        status: int,
        headers: Dict[str, str],
        http_version: str,
        line_reader: Optional[Any] = None,
        body_bytes: Optional[bytes] = None,
        close_callback: Optional[Any] = None,
    ) -> None:
        self.status = status
        self.headers = headers
        self.http_version = http_version
        self._line_reader = line_reader
        self._body_bytes = body_bytes
        self._close_callback = close_callback
        self._closed = False
        self._body_consumed = False

    def readline(self, timeout_seconds: int = 0) -> bytes:
        """读取一行 SSE 数据；timeout_seconds <= 0 表示无限等待。"""
        if self._line_reader is not None:
            return self._line_reader.readline(timeout_seconds)
        if self._body_bytes is not None and not self._body_consumed:
            self._body_consumed = True
            return self._body_bytes
        return b""

    def read(self) -> bytes:
        if self._body_bytes is not None:
            return self._body_bytes
        if self._line_reader is not None:
            chunks = []
            while True:
                chunk = self.readline()
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        return b""

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._line_reader is not None:
            try:
                self._line_reader.close()
            except Exception:
                pass
        if self._close_callback is not None:
            try:
                self._close_callback()
            except Exception:
                pass

    def __enter__(self) -> "UpstreamResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class _LineReader:
    """把 urllib/httpx 原始响应包装成支持超时 readline 的迭代器。"""

    def __init__(self, raw: Any, is_httpx: bool = False) -> None:
        self._raw = raw
        self._is_httpx = is_httpx
        self._buffer: bytes = b""
        self._closed = False
        if is_httpx:
            self._iter = raw.iter_lines()
        else:
            self._iter = None

    def _read_once(self) -> bytes:
        if self._is_httpx:
            try:
                line = next(self._iter)
                return (line + b"\n") if line and not line.endswith(b"\n") else line
            except StopIteration:
                return b""
        return self._raw.readline()

    def readline(self, timeout_seconds: int = 0) -> bytes:
        if self._closed:
            return b""
        if timeout_seconds <= 0:
            return self._read_once()
        result: queue.Queue[Any] = queue.Queue(maxsize=1)

        def _read() -> None:
            try:
                result.put(self._read_once())
            except Exception as exc:
                result.put(exc)

        worker = threading.Thread(target=_read, daemon=True)
        worker.start()
        try:
            item = result.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise StreamIdleTimeoutError("stream_idle_timeout") from exc
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._raw.close()
        except Exception:
            pass


class UpstreamClient:
    """上游 HTTP 客户端抽象，支持 urllib 与 httpx，失败时自动降级。"""

    def __init__(
        self,
        client_type: str = "urllib",
        http2: bool = False,
        keepalive: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
    ) -> None:
        self.client_type = client_type if client_type in ("urllib", "httpx") else "urllib"
        self.http2 = bool(http2)
        self.keepalive = bool(keepalive)
        self.ssl_context = ssl_context
        self._httpx_client: Optional[Any] = None
        self._httpx_available: Optional[bool] = None
        self._init_error: Optional[str] = None
        if self.client_type == "httpx":
            self._ensure_httpx_client()

    def _ensure_httpx_client(self) -> bool:
        if self._httpx_client is not None:
            return True
        if self._httpx_available is False:
            return False
        try:
            import httpx
        except Exception as exc:
            self._httpx_available = False
            self._init_error = f"httpx import failed: {exc}"
            return False
        try:
            limits = None
            if self.keepalive:
                limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
            transport = None
            if self.ssl_context is not None:
                transport = httpx.HTTPTransport(verify=self.ssl_context)
            self._httpx_client = httpx.Client(
                http2=self.http2,
                limits=limits,
                transport=transport,
            )
            self._httpx_available = True
            return True
        except Exception as exc:
            self._httpx_available = False
            self._init_error = f"httpx client init failed: {exc}"
            return False

    def _detect_http_version(self, resp: Any, is_httpx: bool) -> str:
        version = getattr(resp, "http_version", None)
        if version:
            return str(version)
        if is_httpx and self.http2:
            return "HTTP/2"
        return "HTTP/1.1"

    def _urllib_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        stream: bool,
        timeout: float,
    ) -> UpstreamResponse:
        request = Request(url, data=body, headers=headers, method=method)
        kwargs: Dict[str, Any] = {"timeout": timeout}
        if self.ssl_context is not None:
            kwargs["context"] = self.ssl_context
        resp = urlopen(request, **kwargs)
        response_headers = dict(resp.headers.items())
        status = getattr(resp, "status", getattr(resp, "code", 200))
        http_version = self._detect_http_version(resp, is_httpx=False)
        if stream:
            return UpstreamResponse(
                status=status,
                headers=response_headers,
                http_version=http_version,
                line_reader=_LineReader(resp, is_httpx=False),
                close_callback=resp.close,
            )
        return UpstreamResponse(
            status=status,
            headers=response_headers,
            http_version=http_version,
            body_bytes=resp.read(),
            close_callback=resp.close,
        )

    def _httpx_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        stream: bool,
        timeout: float,
    ) -> UpstreamResponse:
        import httpx

        if not self._ensure_httpx_client():
            return self._urllib_request(method, url, headers, body, stream, timeout)
        client = self._httpx_client
        assert client is not None
        request = httpx.Request(method, url, headers=headers, content=body)
        if stream:
            resp = client.send(request, stream=True, timeout=timeout)
            resp.raise_for_status()
            response_headers = dict(resp.headers.items())
            status = resp.status_code
            http_version = self._detect_http_version(resp, is_httpx=True)
            return UpstreamResponse(
                status=status,
                headers=response_headers,
                http_version=http_version,
                line_reader=_LineReader(resp, is_httpx=True),
                close_callback=resp.close,
            )
        resp = client.send(request, timeout=timeout)
        resp.raise_for_status()
        response_headers = dict(resp.headers.items())
        status = resp.status_code
        http_version = self._detect_http_version(resp, is_httpx=True)
        return UpstreamResponse(
            status=status,
            headers=response_headers,
            http_version=http_version,
            body_bytes=resp.content,
            close_callback=resp.close,
        )

    def request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: bytes,
        stream: bool = False,
        timeout: float = 120.0,
    ) -> UpstreamResponse:
        if self.client_type == "httpx":
            try:
                return self._httpx_request(method, url, headers, body, stream, timeout)
            except HTTPError:
                raise
            except Exception as exc:
                # 将 httpx HTTP 错误归一化为 urllib HTTPError，保持 app.py 错误处理不变
                httpx_status_error = self._try_extract_httpx_status_error(exc)
                if httpx_status_error is not None:
                    raise httpx_status_error
                # 其他 httpx 失败回退 urllib
                return self._urllib_request(method, url, headers, body, stream, timeout)
        return self._urllib_request(method, url, headers, body, stream, timeout)

    @staticmethod
    def _try_extract_httpx_status_error(exc: Exception) -> Optional[HTTPError]:
        try:
            import httpx
        except Exception:
            return None
        if not isinstance(exc, httpx.HTTPStatusError):
            return None
        response = getattr(exc, "response", None)
        if response is None:
            return None
        from io import BytesIO

        code = int(response.status_code)
        body = (response.content or b"")
        if isinstance(body, str):
            body = body.encode("utf-8")
        fp = BytesIO(body)
        url = str(exc.request.url) if hasattr(exc, "request") and exc.request else ""
        return HTTPError(url, code, str(exc), dict(response.headers), fp)

    def close(self) -> None:
        if self._httpx_client is not None:
            try:
                self._httpx_client.close()
            except Exception:
                pass
            self._httpx_client = None

    def __del__(self) -> None:
        self.close()

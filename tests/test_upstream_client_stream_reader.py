from __future__ import annotations

from upstream_client import _LineReader


class _FakeHttpxResponse:
    def __init__(self, lines: list[object]) -> None:
        self._lines = iter(lines)
        self.closed = False

    def iter_lines(self):
        return self._lines

    def close(self) -> None:
        self.closed = True


def test_httpx_reader_normalizes_text_lines_and_preserves_sse_blank_lines() -> None:
    raw = _FakeHttpxResponse([
        'data: {"type":"response.completed"}',
        "",
        "data: [DONE]",
        "",
    ])
    reader = _LineReader(raw, is_httpx=True)

    assert reader.readline() == b'data: {"type":"response.completed"}\n'
    assert reader.readline() == b"\n"
    assert reader.readline() == b"data: [DONE]\n"
    assert reader.readline() == b"\n"
    assert reader.readline() == b""


def test_httpx_reader_accepts_bytes_lines_and_only_stop_iteration_is_eof() -> None:
    raw = _FakeHttpxResponse([b"data: first\n", b""])
    reader = _LineReader(raw, is_httpx=True)

    assert reader.readline() == b"data: first\n"
    assert reader.readline() == b"\n"
    assert reader.readline() == b""

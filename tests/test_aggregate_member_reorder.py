import json
import socket
import threading
import urllib.error
import urllib.request

from app import create_server
from linrouter_core.config.models import AggregateMember, AggregateModel
from linrouter_core.config.store import ConfigStore
from linrouter_core.runtime.http_api_runtime import handle_post


class _ReorderHandler:
    def __init__(self, store, payload):
        self.path = "/api/aggregates/agg-1/members/reorder"
        self.store = store
        self.payload = payload
        self.response = None
        self.status = 200

    def _read_json(self):
        return self.payload

    def _send_json(self, response, status=200):
        self.response = response
        self.status = status


def _store_with_members(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.aggregate_models = [AggregateModel(id="agg-1", name="aggregate")]
    store.aggregate_members = [
        AggregateMember(id="member-a", aggregate_id="agg-1", group_id="group", model_id="model-a", priority=1),
        AggregateMember(id="member-b", aggregate_id="agg-1", group_id="group", model_id="model-b", priority=2),
        AggregateMember(id="member-c", aggregate_id="agg-1", group_id="group", model_id="model-c", priority=3),
    ]
    return store


def test_reorder_aggregate_members_replaces_complete_order_and_increments_revision(tmp_path):
    store = _store_with_members(tmp_path)

    ok, message, code, revision = store.reorder_aggregate_members(
        "agg-1", ["member-c", "member-a", "member-b"], expected_revision=0
    )

    assert (ok, message, code, revision) == (True, "", "", 1)
    assert [(member.id, member.priority) for member in store.get_aggregate_members("agg-1")] == [
        ("member-a", 2),
        ("member-b", 3),
        ("member-c", 1),
    ]


def test_reorder_aggregate_members_rejects_missing_or_duplicate_member_ids(tmp_path):
    store = _store_with_members(tmp_path)

    ok, _, code, revision = store.reorder_aggregate_members(
        "agg-1", ["member-a", "member-a", "member-c"], expected_revision=0
    )

    assert not ok
    assert code == "invalid_member_order"
    assert revision == 0
    assert [member.priority for member in store.get_aggregate_members("agg-1")] == [1, 2, 3]


def test_reorder_aggregate_members_rejects_stale_revision_without_writing(tmp_path):
    store = _store_with_members(tmp_path)
    ok, _, _, revision = store.reorder_aggregate_members(
        "agg-1", ["member-c", "member-b", "member-a"], expected_revision=0
    )
    assert ok and revision == 1

    ok, _, code, current_revision = store.reorder_aggregate_members(
        "agg-1", ["member-b", "member-a", "member-c"], expected_revision=0
    )

    assert not ok
    assert code == "aggregate_member_revision_conflict"
    assert current_revision == 1
    assert [member.id for member in sorted(store.get_aggregate_members("agg-1"), key=lambda item: item.priority)] == [
        "member-c", "member-b", "member-a"
    ]


def test_reorder_endpoint_returns_persisted_member_order_and_revision(tmp_path):
    handler = _ReorderHandler(
        _store_with_members(tmp_path),
        {"member_ids": ["member-c", "member-b", "member-a"], "expected_revision": 0},
    )

    handle_post(handler)

    assert handler.status == 200
    assert handler.response["ok"] is True
    assert handler.response["revision"] == 1
    assert [member["id"] for member in handler.response["members"]] == ["member-c", "member-b", "member-a"]


def test_reorder_endpoint_reports_stale_revision_as_structured_conflict(tmp_path):
    store = _store_with_members(tmp_path)
    first = _ReorderHandler(store, {"member_ids": ["member-b", "member-a", "member-c"], "expected_revision": 0})
    handle_post(first)
    stale = _ReorderHandler(store, {"member_ids": ["member-c", "member-b", "member-a"], "expected_revision": 0})
    handle_post(stale)

    assert stale.status == 409
    assert stale.response["error"]["code"] == "aggregate_member_revision_conflict"
    assert stale.response["error"]["revision"] == 1


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(port, method, path, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_ord_02_http_contract_rejects_stale_client_and_preserves_first_order(tmp_path):
    """Two clients read revision 0; only the first full-order write may persist."""
    server, port, _ = create_server("127.0.0.1", _free_port(), tmp_path / "config.json")
    store = server.store
    store.aggregate_models = [AggregateModel(id="agg-1", name="aggregate")]
    store.aggregate_members = [
        AggregateMember(id="member-a", aggregate_id="agg-1", group_id="group", model_id="model-a", priority=1),
        AggregateMember(id="member-b", aggregate_id="agg-1", group_id="group", model_id="model-b", priority=2),
        AggregateMember(id="member-c", aggregate_id="agg-1", group_id="group", model_id="model-c", priority=3),
    ]
    store.aggregate_member_revisions = {"agg-1": 0}
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, client_a_read = _request_json(port, "GET", "/api/aggregates/agg-1/members")
        assert status == 200
        assert client_a_read["revision"] == 0
        assert [member["id"] for member in client_a_read["members"]] == ["member-a", "member-b", "member-c"]

        status, client_b_read = _request_json(port, "GET", "/api/aggregates/agg-1/members")
        assert status == 200
        assert client_b_read["revision"] == client_a_read["revision"]

        status, first = _request_json(
            port,
            "POST",
            "/api/aggregates/agg-1/members/reorder",
            {"member_ids": ["member-c", "member-a", "member-b"], "expected_revision": client_a_read["revision"]},
        )
        assert status == 200
        assert first["revision"] == 1
        assert [member["id"] for member in first["members"]] == ["member-c", "member-a", "member-b"]

        status, stale = _request_json(
            port,
            "POST",
            "/api/aggregates/agg-1/members/reorder",
            {"member_ids": ["member-b", "member-c", "member-a"], "expected_revision": client_b_read["revision"]},
        )
        assert status == 409
        assert stale["error"] == {
            "message": "成员顺序已被其他操作更新，请刷新后重试",
            "type": "conflict_error",
            "code": "aggregate_member_revision_conflict",
            "revision": 1,
        }

        status, final_read = _request_json(port, "GET", "/api/aggregates/agg-1/members")
        assert status == 200
        assert final_read["revision"] == 1
        assert [member["id"] for member in final_read["members"]] == ["member-c", "member-a", "member-b"]

        status, aggregates = _request_json(port, "GET", "/api/aggregates")
        assert status == 200
        assert aggregates["aggregate_member_revisions"] == {"agg-1": 1}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

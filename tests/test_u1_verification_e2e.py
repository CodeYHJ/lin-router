"""U1 持久化验证证据的 HTTP 保存回归。"""

import json
import socket
import threading
import urllib.request
from pathlib import Path

from app import create_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request_json(port: int, path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _mark_verified(server) -> None:
    model = server.store.find_model("m1")
    member = server.store.find_aggregate_member("am1")
    assert model is not None and member is not None
    model.last_success_at = "2026-07-14 12:00:00"
    model.last_checked_at = model.last_success_at
    member.last_success_at = model.last_success_at
    member.last_checked_at = model.last_success_at
    server.store.save()


def test_connectivity_saves_invalidate_persisted_verification_evidence(tmp_path: Path) -> None:
    """只在真实上游连通性字段改变后清除对应成功证据。"""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "groups": [{
            "id": "g1", "name": "中转组", "provider_type": "relay",
            "base_url": "https://relay.example/v1", "route_key": "lr-g1",
        }],
        "models": [{
            "id": "m1", "name": "local-model", "ep_id": "upstream-one", "group_id": "g1",
            "upstream_model": "upstream-one", "api_key": "sk-test", "usable": True,
        }],
        "aggregate_models": [{
            "id": "a1", "name": "aggregate", "description": "历史描述", "route_key": "lr-ag-1", "enabled": True,
        }],
        "aggregate_members": [{
            "id": "am1", "aggregate_id": "a1", "group_id": "g1", "model_id": "m1", "enabled": True,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    server, port, _ = create_server("127.0.0.1", _free_port(), config_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        _mark_verified(server)
        status, result = _request_json(port, "/api/groups/g1", {
            "name": "中转组", "provider_type": "relay",
            "base_url": "https://relay-new.example/v1", "route_key": "lr-g1",
        })
        assert status == 200 and result["ok"] is True
        assert server.store.find_model("m1").last_success_at == ""
        assert server.store.find_aggregate_member("am1").last_success_at == ""

        # 仅改展示名称不得让已验证连接重新回到待验证。
        _mark_verified(server)
        status, result = _request_json(port, "/api/groups/g1", {
            "name": "中转组（显示名已改）", "provider_type": "relay",
            "base_url": "https://relay-new.example/v1", "route_key": "lr-g1",
        })
        assert status == 200 and result["ok"] is True
        assert server.store.find_model("m1").last_success_at
        assert server.store.find_aggregate_member("am1").last_success_at

        _mark_verified(server)
        status, result = _request_json(port, "/api/models/m1", {
            "name": "local-model", "ep_id": "upstream-two", "group_id": "g1",
            "upstream_model": "upstream-two", "api_key": "sk-test", "usable": True,
        })
        assert status == 200 and result["ok"] is True
        assert server.store.find_model("m1").last_success_at == ""
        assert server.store.find_aggregate_member("am1").last_success_at == ""

        # 前端不再编辑 description，但保存其他字段时必须保留旧数据。
        status, result = _request_json(port, "/api/aggregates/a1", {
            "name": "aggregate", "display_name": "更新后的聚合名称",
            "enabled": True, "strategy": "priority", "cooldown_minutes": 5,
        })
        assert status == 200 and result["ok"] is True
        assert server.store.find_aggregate("a1").description == "历史描述"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

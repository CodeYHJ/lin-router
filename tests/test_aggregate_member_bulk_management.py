"""聚合成员勾选式批量管理的后端与静态前端契约。"""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app import ConfigStore, create_server


ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _post_json(port: int, path: str, payload: Any) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "groups": [
                    {
                        "id": "g-one",
                        "name": "中转一组",
                        "provider_type": "relay",
                        "base_url": "https://relay-one.example/v1",
                        "route_key": "lr-one",
                    },
                    {
                        "id": "g-two",
                        "name": "中转二组",
                        "provider_type": "relay",
                        "base_url": "https://relay-two.example/v1",
                        "route_key": "lr-two",
                    },
                ],
                "models": [
                    {
                        "id": "m-alpha",
                        "name": "Alpha",
                        "ep_id": "up-alpha",
                        "upstream_model": "up-alpha",
                        "group_id": "g-one",
                        "usable": True,
                    },
                    {
                        "id": "m-beta",
                        "name": "Beta",
                        "ep_id": "up-beta",
                        "upstream_model": "up-beta",
                        "group_id": "g-one",
                        "usable": True,
                    },
                    {
                        "id": "m-gamma",
                        "name": "Gamma",
                        "ep_id": "up-gamma",
                        "upstream_model": "up-gamma",
                        "group_id": "g-one",
                        "usable": True,
                    },
                    {
                        "id": "m-other",
                        "name": "Other",
                        "ep_id": "up-other",
                        "upstream_model": "up-other",
                        "group_id": "g-two",
                        "usable": True,
                    },
                ],
                "aggregate_models": [
                    {"id": "agg-one", "name": "aggregate-one", "route_key": "lr-ag-one"},
                    {"id": "agg-two", "name": "aggregate-two", "route_key": "lr-ag-two"},
                ],
                "aggregate_members": [
                    {
                        "id": "am-alpha",
                        "aggregate_id": "agg-one",
                        "group_id": "g-one",
                        "model_id": "m-alpha",
                        "priority": 1,
                        "enabled": True,
                        "cooldown_until": 9999999999,
                        "cooldown_reason": "temporary_failure",
                        "last_error": "timeout",
                    },
                    {
                        "id": "am-beta",
                        "aggregate_id": "agg-one",
                        "group_id": "g-one",
                        "model_id": "m-beta",
                        "priority": 2,
                        "enabled": False,
                    },
                    {
                        "id": "am-gamma",
                        "aggregate_id": "agg-one",
                        "group_id": "g-one",
                        "model_id": "m-gamma",
                        "priority": 3,
                        "enabled": True,
                    },
                    {
                        "id": "am-other",
                        "aggregate_id": "agg-two",
                        "group_id": "g-two",
                        "model_id": "m-other",
                        "priority": 1,
                        "enabled": True,
                    },
                ],
                "aggregate_member_revisions": {"agg-one": 4, "agg-two": 2},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_batch_update_is_one_save_atomic_and_clears_member_level_health(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    store = ConfigStore(path)
    original_save = store.save
    save_calls = 0

    def counted_save() -> None:
        nonlocal save_calls
        save_calls += 1
        original_save()

    store.save = counted_save  # type: ignore[method-assign]
    result = store.batch_update_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta"],
        enabled=True,
        expected_revision=4,
    )

    assert result["ok"] is True
    assert result["changed_count"] == 2
    assert result["skipped_count"] == 0
    assert result["revision"] == 5
    assert [member["id"] for member in result["members"]] == [
        "am-alpha",
        "am-beta",
        "am-gamma",
    ]
    assert save_calls == 1
    alpha = store.find_aggregate_member("am-alpha")
    beta = store.find_aggregate_member("am-beta")
    assert alpha is not None and beta is not None
    assert alpha.enabled is True and beta.enabled is True
    assert alpha.cooldown_until == 0
    assert alpha.cooldown_reason == ""
    assert alpha.last_error == ""
    persisted = ConfigStore(path)
    assert persisted.aggregate_member_revision("agg-one") == 5
    assert persisted.find_aggregate_member("am-beta").enabled is True  # type: ignore[union-attr]


def test_batch_update_rejects_stale_or_cross_aggregate_input_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    store = ConfigStore(path)
    before = path.read_text(encoding="utf-8")

    cross_aggregate = store.batch_update_aggregate_members(
        "agg-one",
        ["am-alpha", "am-other"],
        enabled=False,
        expected_revision=4,
    )
    assert cross_aggregate["ok"] is False
    assert cross_aggregate["code"] == "member_not_in_aggregate"
    assert store.aggregate_member_revision("agg-one") == 4
    assert path.read_text(encoding="utf-8") == before

    invalid_member = store.batch_update_aggregate_members(
        "agg-one",
        ["am-alpha", "missing-member"],
        enabled=False,
        expected_revision=4,
    )
    assert invalid_member["ok"] is False
    assert invalid_member["code"] == "invalid_member_ids"
    assert store.aggregate_member_revision("agg-one") == 4
    assert path.read_text(encoding="utf-8") == before

    stale = store.batch_update_aggregate_members(
        "agg-one",
        ["am-alpha"],
        enabled=False,
        expected_revision=3,
    )
    assert stale["ok"] is False
    assert stale["code"] == "aggregate_member_revision_conflict"
    assert stale["revision"] == 4
    assert path.read_text(encoding="utf-8") == before


def test_batch_delete_preview_is_read_only_and_delete_preserves_unselected_order(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    store = ConfigStore(path)
    before = path.read_text(encoding="utf-8")

    preview = store.preview_batch_delete_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta"],
        expected_revision=4,
    )

    assert preview["ok"] is True
    assert [item["member_id"] for item in preview["members"]] == ["am-alpha", "am-beta"]
    assert [item["member_id"] for item in preview["candidate_chain_before"]] == [
        "am-alpha",
        "am-beta",
        "am-gamma",
    ]
    assert [item["member_id"] for item in preview["candidate_chain_after"]] == ["am-gamma"]
    assert preview["has_routable_candidate"] is True
    assert store.aggregate_member_revision("agg-one") == 4
    assert path.read_text(encoding="utf-8") == before

    deleted = store.batch_delete_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta"],
        expected_revision=4,
    )
    assert deleted["ok"] is True
    assert deleted["deleted_count"] == 2
    assert deleted["revision"] == 5
    remaining = store.get_aggregate_members("agg-one")
    assert [(member.id, member.priority) for member in remaining] == [("am-gamma", 3)]


def test_batch_delete_preview_warns_when_no_routable_candidate_remains(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    store = ConfigStore(path)

    preview = store.preview_batch_delete_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta", "am-gamma"],
        expected_revision=4,
    )

    assert preview["ok"] is True
    assert preview["has_routable_candidate"] is False
    assert preview["warnings"]


def test_batch_update_and_delete_roll_back_members_and_revision_on_save_failure(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    store = ConfigStore(path)
    members_before = [(member.id, member.enabled) for member in store.aggregate_members]

    def fail_save() -> None:
        raise OSError("disk full")

    store.save = fail_save  # type: ignore[method-assign]
    update = store.batch_update_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta"],
        enabled=True,
        expected_revision=4,
    )
    assert update["ok"] is False
    assert update["code"] == "config_save_failed"
    assert store.aggregate_member_revision("agg-one") == 4
    assert [(member.id, member.enabled) for member in store.aggregate_members] == members_before
    assert [(member.id, member.enabled) for member in ConfigStore(path).aggregate_members] == members_before

    store = ConfigStore(path)
    store.save = fail_save  # type: ignore[method-assign]
    deleted = store.batch_delete_aggregate_members(
        "agg-one",
        ["am-alpha", "am-beta"],
        expected_revision=4,
    )
    assert deleted["ok"] is False
    assert deleted["code"] == "config_save_failed"
    assert store.aggregate_member_revision("agg-one") == 4
    assert [(member.id, member.enabled) for member in store.aggregate_members] == members_before
    assert [(member.id, member.enabled) for member in ConfigStore(path).aggregate_members] == members_before


def test_batch_member_http_contract_handles_revision_conflict_and_delete_preview(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    _write_config(path)
    server, port, _ = create_server("127.0.0.1", _free_port(), path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, updated = _post_json(
            port,
            "/api/aggregates/agg-one/members/batch-update",
            {
                "member_ids": ["am-alpha", "am-beta"],
                "enabled": True,
                "expected_revision": 4,
            },
        )
        assert status == 200
        assert updated["changed_count"] == 2
        assert updated["revision"] == 5

        status, stale = _post_json(
            port,
            "/api/aggregates/agg-one/members/batch-delete-preview",
            {"member_ids": ["am-alpha"], "expected_revision": 4},
        )
        assert status == 409
        assert stale["error"]["code"] == "aggregate_member_revision_conflict"

        status, preview = _post_json(
            port,
            "/api/aggregates/agg-one/members/batch-delete-preview",
            {"member_ids": ["am-alpha", "am-beta"], "expected_revision": 5},
        )
        assert status == 200
        assert preview["ok"] is True
        assert preview["revision"] == 5

        status, deleted = _post_json(
            port,
            "/api/aggregates/agg-one/members/batch-delete",
            {"member_ids": ["am-alpha", "am-beta"], "expected_revision": 5},
        )
        assert status == 200
        assert deleted["deleted_count"] == 2
        assert deleted["revision"] == 6

        status, cross_aggregate = _post_json(
            port,
            "/api/aggregates/agg-one/members/batch-update",
            {
                "member_ids": ["am-other"],
                "enabled": False,
                "expected_revision": 6,
            },
        )
        assert status == 400
        assert cross_aggregate["error"]["code"] == "member_not_in_aggregate"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _run_node(script: str) -> str:
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return completed.stdout.strip()


def test_frontend_bulk_selection_filter_add_payload_and_drag_handle_contract() -> None:
    api_js = (ROOT / "static/js/api.js").read_text(encoding="utf-8")
    config_js = (ROOT / "static/js/config-tab.js").read_text(encoding="utf-8")
    actions_js = (ROOT / "static/js/config-tab-actions.js").read_text(encoding="utf-8")
    css = (ROOT / "static/css/config-tab.css").read_text(encoding="utf-8")

    assert "batchUpdateAggregateMembers" in api_js
    assert "batchDeleteAggregateMembersPreview" in api_js
    assert "batchDeleteAggregateMembers" in api_js
    assert "model_ids: modelIds" in actions_js
    assert "onBatchUpdateAggregateMembers" in actions_js
    assert "onBatchDeleteAggregateMembers" in actions_js
    assert "aggregate-member-select-all" in config_js
    assert "aggregate-member-bulk-toolbar" in config_js
    assert "aggregate-drag-handle" in config_js
    assert "<tr data-member-id=\"${member.id}\" draggable=\"true\"" not in config_js
    assert "draggable=\"true\"" in config_js
    assert "handle.addEventListener('dragstart'" in actions_js
    assert "event.preventDefault();" in actions_js
    assert ".aggregate-member-bulk-toolbar" in css
    assert ".aggregate-drag-handle" in css
    assert "cursor: grab" in css

    script = r'''
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('static/js/config-tab.js', 'utf8') + '\nthis.config = ConfigTab;';
const members = [
  { id: 'am-alpha', aggregate_id: 'a1', group_id: 'g1', model_id: 'm-alpha', priority: 1, enabled: true },
  { id: 'am-beta', aggregate_id: 'a1', group_id: 'g1', model_id: 'm-beta', priority: 2, enabled: false },
  { id: 'am-other', aggregate_id: 'a1', group_id: 'g2', model_id: 'm-other', priority: 3, enabled: true },
];
const models = {
  'm-alpha': { id: 'm-alpha', name: 'Alpha', upstream_model: 'alpha-upstream', usable: true },
  'm-beta': { id: 'm-beta', name: 'Beta', upstream_model: 'beta-upstream', usable: true },
  'm-other': { id: 'm-other', name: 'Other', upstream_model: 'other-upstream', usable: false },
};
const Store = {
  state: { aggregate_members: members },
  getAggregateMembers() { return members; },
  getModel(id) { return models[id]; },
};
const context = { Store, Utils: { escapeHtml(value) { return String(value ?? ''); } }, Map, Set, Date, String };
vm.runInNewContext(source, context);
const state = context.config.getAggregateMemberUiState('a1');
state.filters = { groupId: 'g1', status: 'all', query: 'alpha-upstream' };
const filtered = context.config.getFilteredAggregateMembers('a1');
if (filtered.length !== 1 || filtered[0].id !== 'am-alpha') throw new Error('keyword/group filter mismatch');
state.filters = { groupId: '', status: 'manual_disabled', query: '' };
if (context.config.getFilteredAggregateMembers('a1')[0].id !== 'am-beta') throw new Error('manual disabled filter mismatch');
state.selectedIds.add('am-alpha');
context.config.clearAggregateMemberSelection('a1');
if (state.selectedIds.size !== 0) throw new Error('selection clear mismatch');
console.log('AGGREGATE_MEMBER_BULK_UI_STATE_OK');
'''
    assert _run_node(script) == "AGGREGATE_MEMBER_BULK_UI_STATE_OK"

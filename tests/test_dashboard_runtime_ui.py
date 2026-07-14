"""首页运行态差分渲染与可扩展接入区的静态/渲染契约。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run_dashboard(state: dict, access_filter: str = "") -> dict:
    """在无浏览器依赖的 Node VM 中执行首页纯渲染逻辑。"""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const state = JSON.parse(process.argv[1]);
const accessFilter = process.argv[2] || '';
const context = {
  Store: { state },
  URL,
  Date,
  window: { location: { origin: 'http://127.0.0.1:8748' } },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/utils.js', 'utf8') + '\nthis.ConnectionStatus = ConnectionStatus; this.Utils = Utils;', context);
vm.runInContext(fs.readFileSync('static/js/dashboard-tab.js', 'utf8') + '\nthis.DashboardTab = DashboardTab;', context);
context.DashboardTab._accessFilter = accessFilter;
const structureBefore = context.DashboardTab.structureSignature(state);
const runtimeBefore = context.DashboardTab.runtimeSignature(state);
const changedRuntime = JSON.parse(JSON.stringify(state));
changedRuntime.live_requests = [{ request_id: 'runtime-only', requested_model: 'runtime-model' }];
changedRuntime.logs = [{ request_id: 'runtime-only', status: '200', event: 'ok', detail: '' }];
const changedHealth = JSON.parse(JSON.stringify(state));
if (changedHealth.models && changedHealth.models[0]) {
  changedHealth.models[0].usable = false;
  changedHealth.models[0].cooldown_until = 9999999999;
  changedHealth.models[0].last_success_at = '';
}
console.log(JSON.stringify({
  html: context.DashboardTab.render(),
  structureBefore,
  structureAfterRuntimeOnly: context.DashboardTab.structureSignature(changedRuntime),
  structureAfterHealthOnly: context.DashboardTab.structureSignature(changedHealth),
  runtimeBefore,
  runtimeAfter: context.DashboardTab.runtimeSignature(changedRuntime),
  runtimeAfterHealthOnly: context.DashboardTab.runtimeSignature(changedHealth),
}));
"""
    completed = subprocess.run(
        ["node", "-e", script, json.dumps(state, ensure_ascii=False), access_filter],
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return json.loads(completed.stdout)


def group(group_id: str, name: str) -> dict:
    return {
        "id": group_id,
        "name": name,
        "provider_type": "relay",
        "base_url": "https://relay.example/v1",
        "route_key": f"lr-{group_id}",
    }


def model(model_id: str, group_id: str, *, verified: bool = False) -> dict:
    return {
        "id": model_id,
        "name": model_id,
        "group_id": group_id,
        "upstream_model": model_id,
        "api_key": "sk-test",
        "usable": True,
        "last_success_at": "2026-07-14 12:00:00" if verified else "",
    }


def primary_button_count(html: str) -> int:
    return html.count('class="btn-primary"')


def test_runtime_fields_do_not_change_dashboard_structure_signature():
    state = {
        "groups": [group("g1", "主连接组")],
        "models": [model("m1", "g1", verified=True)],
        "aggregate_models": [],
        "aggregate_members": [],
        "logs": [],
        "live_requests": [],
    }

    rendered = run_dashboard(state)

    assert rendered["structureBefore"] == rendered["structureAfterRuntimeOnly"]
    assert rendered["structureBefore"] == rendered["structureAfterHealthOnly"]
    assert rendered["runtimeBefore"] != rendered["runtimeAfter"]
    assert rendered["runtimeBefore"] != rendered["runtimeAfterHealthOnly"]


def test_s2_keeps_next_step_expanded_and_always_renders_live_requests():
    state = {
        "groups": [group("g1", "待验证连接组")],
        "models": [model("m1", "g1")],
        "aggregate_models": [],
        "aggregate_members": [],
        "logs": [],
        "live_requests": [{
            "request_id": "req-live",
            "request_id_short": "req-live",
            "requested_model": "m1",
            "group": "待验证连接组",
            "stage": "waiting_first_byte",
            "elapsed_ms": 1000,
        }],
    }

    html = run_dashboard(state)["html"]

    assert 'data-dashboard-live-requests' in html
    assert 'data-dashboard-live-request="req-live"' in html
    assert 'data-dashboard-flow-summary="S2"' not in html
    assert primary_button_count(html) == 1


def test_s0_s1_and_e1_keep_next_step_expanded_with_one_primary_action():
    cases = [
        {
            "groups": [],
            "models": [],
            "aggregate_models": [],
            "aggregate_members": [],
            "logs": [],
            "live_requests": [],
        },
        {
            "groups": [group("g1", "待添加模型")],
            "models": [],
            "aggregate_models": [],
            "aggregate_members": [],
            "logs": [],
            "live_requests": [],
        },
        {
            "groups": [group("g1", "需处理连接组")],
            "models": [{**model("m1", "g1"), "usable": False}],
            "aggregate_models": [],
            "aggregate_members": [],
            "logs": [],
            "live_requests": [],
        },
    ]

    for state in cases:
        html = run_dashboard(state)["html"]
        assert 'data-dashboard-flow-summary=' not in html
        assert primary_button_count(html) == 1
        assert 'data-dashboard-live-requests' in html


def test_s3_shows_all_aggregates_and_keeps_single_primary_action():
    aggregates = [
        {
            "id": f"a{index}",
            "name": f"aggregate-{index}",
            "display_name": f"聚合 {index}",
            "route_key": f"lr-ag-{index}",
            "enabled": index != 5,
        }
        for index in range(1, 6)
    ]
    state = {
        "groups": [group("g1", "主连接组")],
        "models": [model("m1", "g1", verified=True)],
        "aggregate_models": aggregates,
        "aggregate_members": [],
        "logs": [],
        "live_requests": [],
    }

    html = run_dashboard(state)["html"]

    assert 'data-dashboard-flow-summary="S3"' in html
    assert 'data-dashboard-access-filter' in html
    assert '中转站' in html
    assert '可用模型 1 / 1' in html
    assert 'data-dashboard-access-group="g1" open' in html
    assert html.count('class="dashboard-card dashboard-aggregate-card') == 5
    assert '聚合 5' in html
    assert '已停用' in html
    assert 'dashboard-aggregate-access-card is-disabled' not in html
    assert primary_button_count(html) == 1


def test_s4_filters_collapsible_direct_access_groups_without_hiding_live_region():
    state = {
        "groups": [group("g1", "主连接组"), group("g2", "备用连接组")],
        "models": [model("m1", "g1", verified=True), model("m2", "g2", verified=True)],
        "aggregate_models": [],
        "aggregate_members": [],
        "logs": [],
        "live_requests": [],
    }

    html = run_dashboard(state, "备用")["html"]

    assert 'data-dashboard-flow-summary="S4"' in html
    assert html.count('data-dashboard-access-group=') == 1
    assert '备用连接组' in html
    assert '主连接组' not in html
    assert 'data-dashboard-access-group="g2" open' not in html
    assert 'data-dashboard-live-requests' in html
    assert primary_button_count(html) == 1


def test_dashboard_runtime_source_uses_stable_slots_and_delegated_events():
    dashboard_js = (ROOT / "static/js/dashboard-tab.js").read_text(encoding="utf-8")
    dashboard_css = (ROOT / "static/css/dashboard-tab.css").read_text(encoding="utf-8")

    assert "patchRuntime(panel)" in dashboard_js
    assert "data-dashboard-live-requests" in dashboard_js
    assert "data-dashboard-metrics" in dashboard_js
    assert "data-dashboard-access-filter" in dashboard_js
    assert "panel.addEventListener('click'" in dashboard_js
    assert ".slice(0, 4)" not in dashboard_js
    assert "dashboard-access-group" in dashboard_css
    assert "dashboard-flow-details" in dashboard_css
    assert "dashboard-aggregate-card" in dashboard_css

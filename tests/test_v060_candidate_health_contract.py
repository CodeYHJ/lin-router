from __future__ import annotations

import json

from app import ArkProxyRouter, ConfigStore
from linrouter_core.runtime import CandidateHealthService


def _router(tmp_path):
    config = {
        "groups": [{"id": "g1", "name": "relay", "provider_type": "relay", "base_url": "https://relay.example/v1", "route_key": "key", "waf_compatible": True}],
        "models": [
            {"id": "m1", "name": "first", "ep_id": "model-1", "group_id": "g1", "api_key": "key-1", "usable": True},
            {"id": "m2", "name": "second", "ep_id": "model-2", "group_id": "g1", "api_key": "key-2", "usable": True},
        ],
        "aggregate_models": [{"id": "a1", "name": "aggregate", "route_key": "agg-key", "strategy": "priority"}],
        "aggregate_members": [
            {"id": "am1", "aggregate_id": "a1", "group_id": "g1", "model_id": "m2", "priority": 2, "enabled": True},
            {"id": "am2", "aggregate_id": "a1", "group_id": "g1", "model_id": "m1", "priority": 1, "enabled": False},
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return ArkProxyRouter(ConfigStore(path), None, tmp_path / "logs.jsonl"), path


def test_candidate_health_service_is_the_single_runtime_owner(tmp_path) -> None:
    router, _ = _router(tmp_path)

    assert isinstance(router.candidate_health, CandidateHealthService)
    assert router.runtime.candidate_health is router.candidate_health
    assert [candidate.label for candidate in router._iter_upstream_candidates(None, "g1")] == ["first", "second"]


def test_candidate_health_preserves_manual_member_disable_and_reload(tmp_path) -> None:
    router, path = _router(tmp_path)
    aggregate = router.store.find_aggregate("a1")
    assert aggregate is not None
    assert [candidate.label for candidate in router._iter_aggregate_candidates(aggregate)] == ["second"]

    router._set_aggregate_member_cooldown("am1", "network failure", 60, "network")
    router._mark_aggregate_member_success("am2")
    reloaded = ConfigStore(path)
    cooling = reloaded.find_aggregate_member("am1")
    disabled = reloaded.find_aggregate_member("am2")
    assert cooling is not None and cooling.cooldown_reason == "network"
    assert disabled is not None and disabled.enabled is False


def test_candidate_health_writes_model_states_without_second_copy(tmp_path) -> None:
    router, path = _router(tmp_path)

    router._set_cooldown(0, "network failure", 60, "network")
    router._set_success(1)
    router._set_unusable(1, "quota exhausted")
    reloaded = ConfigStore(path)
    assert reloaded.models[0].usable is False
    assert reloaded.models[0].cooldown_reason == "network"
    assert reloaded.models[1].usable is False
    assert reloaded.models[1].cooldown_until == 0

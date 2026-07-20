"""v0.6 I3 behavior contracts for execution-policy classification."""
from __future__ import annotations

from types import SimpleNamespace

from linrouter_core.contracts.execution_ports import CandidateErrorClassification, ExecutionPolicyPort
from linrouter_core.runtime import ExecutionPolicyService


def _policy() -> ExecutionPolicyService:
    return ExecutionPolicyService(
        is_rate_limited=lambda status, raw: "rate" in raw,
        is_quota_exhausted=lambda status, raw: "quota" in raw,
        is_waf_blocked_error=lambda status, raw: status == 403 and "blocked" in raw.lower(),
        is_request_level_error=lambda status, raw: status == 400 or status in (401, 403),
    )


def test_i3_policy_classification_preserves_all_five_fields() -> None:
    policy = _policy()
    expected = {
        (None, "network", "network"): (True, False, "network", "network", "upstream"),
        (None, "timeout", "stream_timeout"): (True, False, "stream_timeout", "stream_timeout", "upstream"),
        (503, "failure", "http"): (True, False, "server_error", "server_error_503", "upstream"),
        (429, "rate", "http"): (True, False, "rate_limit", "rate_limit", "upstream"),
        (429, "quota", "http"): (True, False, "quota_exhausted", "quota_exhausted", "upstream"),
        (403, "Your request was blocked", "http"): (False, True, "waf_blocked", "waf_blocked", "candidate"),
        (401, "unauthorized", "http"): (False, True, "auth_error", "auth_error", "candidate"),
        (400, "invalid request", "http"): (False, True, "request_level", "request_level", "request"),
    }

    for (status_code, raw, error_kind), fields in expected.items():
        classification = policy.classify_candidate_error(status_code, raw, error_kind)
        assert isinstance(classification, CandidateErrorClassification)
        assert (
            classification.should_cooldown,
            classification.is_request_level,
            classification.category,
            classification.log_reason,
            classification.failure_scope,
        ) == fields


def test_i3_policy_auto_cooldown_and_waf_text_preserve_contract() -> None:
    policy = _policy()
    assert isinstance(policy, ExecutionPolicyPort)
    relay = SimpleNamespace(provider_type="relay", waf_compatible=True, auto_model_name="group-auto", auto_model_cooldown_minutes="3")
    default_group = SimpleNamespace(provider_type="ark", waf_compatible=False, auto_model_name="", auto_model_cooldown_minutes="bad")

    assert policy.is_auto_model(None, relay)
    assert policy.is_auto_model("all-router-auto", relay)
    assert policy.is_auto_model("group-auto", relay)
    assert not policy.is_auto_model("specific", relay)
    assert policy.auto_cooldown_seconds(relay) == 180
    assert policy.auto_cooldown_seconds(default_group) == 300

    classification = policy.classify_candidate_error(403, "blocked")
    assert "该连接组已开启 WAF" in policy.waf_blocked_suffix(classification, relay)
    assert "检查中转站后台" in policy.waf_blocked_hint([{"category": "waf_blocked", "waf_compatible": True}])

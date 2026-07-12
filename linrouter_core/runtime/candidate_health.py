"""Candidate query and health-state ownership for the v0.6 I2 slice.

This service owns candidate construction/enumeration and candidate or aggregate-member
health writes. It depends on ConfigStore and explicit callbacks only; it does not import
the legacy facade, HTTP transport, execution services, or a broad router dependency.
"""
from __future__ import annotations

import time
from typing import Callable, Iterator, Tuple

from linrouter_core.config.constants import GLOBAL_ROUTE_GROUP_ID, PROVIDER_PROXY, PROVIDER_RELAY
from linrouter_core.config.models import AggregateMember, AggregateModel, ConnectionGroup, ModelConfig
from linrouter_core.config.store import ConfigStore
from linrouter_core.contracts.runtime_types import UpstreamCandidate


class CandidateHealthService:
    """Single business owner for candidate queries and health-state mutation."""

    def __init__(
        self,
        store: ConfigStore,
        *,
        now: Callable[[], str],
        is_auto_model: Callable[[str | None, ConnectionGroup | None], bool],
        mode_for: Callable[[ConnectionGroup | None], str],
        group_for: Callable[[ModelConfig], ConnectionGroup | None],
        auth_for: Callable[[ConnectionGroup, ModelConfig | None], str],
        candidate_type: type[UpstreamCandidate],
        log_aggregate_member_skip: Callable[..., None],
    ) -> None:
        self._store = store
        self._now = now
        self._is_auto_model = is_auto_model
        self._mode_for = mode_for
        self._group_for = group_for
        self._auth_for = auth_for
        self._candidate_type = candidate_type
        self._log_aggregate_member_skip = log_aggregate_member_skip

    def iter_candidates(
        self,
        requested_model: str | None,
        group_id: str | None = None,
    ) -> Iterator[Tuple[int, ModelConfig]]:
        group = self._store.find_group(group_id) if group_id else None
        if self._is_auto_model(requested_model, group):
            requested_model = None
        for idx, model in enumerate(self._store.models):
            if model.cooldown_until and model.cooldown_until <= int(time.time()):
                model.cooldown_until = 0
                model.cooldown_reason = ""
                if not model.disabled_by_user:
                    model.usable = True
                model.last_error = ""
                model.last_checked_at = self._now()
                self._store.save()
            if model.disabled_by_user or not model.usable:
                continue
            if group_id and model.group_id != group_id:
                continue
            if requested_model and requested_model not in {model.id, model.name, model.ep_id}:
                continue
            yield idx, model

    def candidate_from_model(
        self,
        idx: int | None,
        model: ModelConfig | None,
        group: ConnectionGroup,
    ) -> UpstreamCandidate:
        mode = self._mode_for(group)
        channel = model.price_group if model and mode == PROVIDER_RELAY and model.price_group else ("proxy" if mode == PROVIDER_PROXY else "")
        label = model.name if model else ""
        target_model = model.ep_id if model else ""
        return self._candidate_type(
            idx=idx,
            group=group,
            model=model,
            label=label,
            target_model=target_model,
            auth_key=self._auth_for(group, model),
            channel=channel,
        )

    def iter_upstream_candidates(
        self,
        requested_model: str | None,
        group_id: str | None = None,
    ) -> Iterator[UpstreamCandidate]:
        if group_id == GLOBAL_ROUTE_GROUP_ID:
            return
        if group_id:
            group = self._store.find_group(group_id)
            if not group:
                return
            matched = False
            for idx, model in self.iter_candidates(requested_model, group.id):
                matched = True
                yield self.candidate_from_model(idx, model, group)
            if self._mode_for(group) == PROVIDER_PROXY and not matched and requested_model and not self._is_auto_model(requested_model, group):
                yield self._candidate_type(
                    idx=None,
                    group=group,
                    model=None,
                    label=requested_model,
                    target_model=requested_model,
                    auth_key=self._auth_for(group, None),
                    channel="pass-through",
                )
            return
        for idx, model in self.iter_candidates(requested_model):
            group = self._group_for(model)
            if group:
                yield self.candidate_from_model(idx, model, group)

    def aggregate_member_skip_reason(
        self,
        member: AggregateMember,
    ) -> Tuple[str, str, ConnectionGroup | None, ModelConfig | None]:
        group = self._store.find_group(member.group_id)
        model = self._store.find_model(member.model_id)
        now_ts = int(time.time())
        if not member.enabled:
            return "member_disabled", "该聚合成员已手动停用，不参与本次调度。", group, model
        if member.cooldown_until and member.cooldown_until > now_ts:
            return "member_cooling", "该聚合成员正在冷却中，本次直接跳过。", group, model
        if not group:
            return "underlying_group_missing", "底层连接组不存在，请检查聚合成员配置。", group, model
        if not model:
            return "underlying_model_missing", "底层真实模型不存在，请检查聚合成员配置。", group, model
        if not model.usable or model.disabled_by_user:
            return "underlying_model_disabled", "底层真实模型已停用，请先启用真实模型。", group, model
        if model.cooldown_until and model.cooldown_until > now_ts:
            return "underlying_model_cooling", "底层真实模型冷却中，本次直接跳过。", group, model
        return "", "", group, model

    def iter_aggregate_candidates(self, aggregate: AggregateModel, **kwargs: object) -> Iterator[UpstreamCandidate]:
        self._store.refresh_expired_cooldowns()
        members = self._store.get_aggregate_members(aggregate.id)
        if aggregate.strategy == "price_first":
            members = sorted(members, key=lambda member: (member.manual_price is None, member.manual_price if member.manual_price is not None else 0, member.priority))
        else:
            members = sorted(members, key=lambda member: member.priority)
        for member in members:
            reason, message, group, model = self.aggregate_member_skip_reason(member)
            if reason:
                if kwargs.get("log_skips", False):
                    self._log_aggregate_member_skip(
                        str(kwargs.get("path", "")), aggregate, member, reason, message, group, model,
                        str(kwargs.get("requested_label", "")), str(kwargs.get("request_id", "")), str(kwargs.get("resolved_as", "")),
                    )
                continue
            if not group or not model:
                continue
            candidate = self.candidate_from_model(self._store.models.index(model), model, group)
            candidate.aggregate_id = aggregate.id
            candidate.aggregate_name = aggregate.name
            candidate.aggregate_member_id = member.id
            candidate.manual_price = member.manual_price
            yield candidate

    def set_cooldown(self, idx: int, error: str, cooldown_seconds: int, reason: str) -> None:
        model = self._store.models[idx]
        model.usable = False
        model.last_error = error[:500]
        model.last_checked_at = self._now()
        model.cooldown_until = int(time.time()) + max(0, cooldown_seconds)
        model.cooldown_reason = reason[:120]
        self._store.save()

    def set_success(self, idx: int) -> None:
        model = self._store.models[idx]
        model.last_error = ""
        model.last_success_at = self._now()
        model.last_checked_at = model.last_success_at
        self._store.save()

    def set_unusable(self, idx: int, error: str) -> None:
        model = self._store.models[idx]
        model.usable = False
        model.last_error = error[:500]
        model.last_checked_at = self._now()
        model.cooldown_until = 0
        model.cooldown_reason = ""
        self._store.save()

    def set_aggregate_member_cooldown(self, member_id: str, error: str, cooldown_seconds: int, reason: str) -> None:
        member = self._store.find_aggregate_member(member_id)
        if not member:
            return
        member.last_error = error[:500]
        member.last_checked_at = self._now()
        member.cooldown_until = int(time.time()) + max(0, cooldown_seconds)
        member.cooldown_reason = reason[:120]
        self._store.save()

    def mark_aggregate_member_success(self, member_id: str) -> None:
        member = self._store.find_aggregate_member(member_id)
        if not member:
            return
        member.last_error = ""
        member.last_success_at = self._now()
        member.last_checked_at = member.last_success_at
        self._store.save()

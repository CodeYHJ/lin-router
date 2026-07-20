"""v0.6 I1 behavior: execution types remain shared core contracts."""
from __future__ import annotations

from linrouter_server.application import AllModelsFailedError as AppAllModelsFailedError
from linrouter_server.application import RouteContext as AppRouteContext
from linrouter_server.application import StreamIdleTimeoutError as AppStreamIdleTimeoutError
from linrouter_server.application import UpstreamCandidate as AppUpstreamCandidate
from linrouter_core.contracts.runtime_types import (
    AllModelsFailedError,
    RouteContext,
    StreamIdleTimeoutError,
    UpstreamCandidate,
)


def test_v060_execution_types_are_core_contracts_reexported_by_legacy_facade() -> None:
    assert AppUpstreamCandidate is UpstreamCandidate
    assert AppRouteContext is RouteContext
    assert AppAllModelsFailedError is AllModelsFailedError
    assert AppStreamIdleTimeoutError is StreamIdleTimeoutError

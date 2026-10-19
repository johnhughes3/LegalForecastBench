"""Host-side use of the existing bounded Anthropic gateway for native LAB.

The pinned LAB checkout owns the solver and judge loops.  This module only
hosts the already-supported gateway next to those subprocesses and projects
its settled usage, so provider requests never receive the upstream key.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from legalforecast.multiharness.container_harness.model_gateway_protocol import (
    GatewaySpendController,
    ModelGatewayPolicy,
)
from legalforecast.multiharness.container_harness.model_gateway_server import (
    ModelGatewayHTTPServer,
    build_model_gateway_server,
)
from legalforecast.multiharness.container_harness.model_gateway_types import (
    GatewayUsageSnapshot,
)


class LabCoreGatewayError(RuntimeError):
    """The shared gateway could not provide settled native-LAB accounting."""


@dataclass(frozen=True, slots=True)
class LabCoreGateway:
    """Configuration for one host-local, Anthropic-compatible LAB gateway."""

    policy: ModelGatewayPolicy = field(repr=False)
    request_id: str
    spend_controller: GatewaySpendController | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise LabCoreGatewayError("native LAB gateway request ID is required")
        if "127.0.0.1" not in self.policy.allowed_ingress_hosts:
            raise LabCoreGatewayError(
                "native LAB gateway must allow its loopback ingress host"
            )

    @contextmanager
    def serve(self, private_root: Path) -> Generator[LabCoreGatewaySession]:
        """Serve one gateway for the solver and judge subprocesses."""

        gateway_root = private_root / "gateway"
        gateway_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        usage_path = gateway_root / "usage.json"
        server = build_model_gateway_server(
            self.policy,
            usage_evidence_path=usage_path,
            spend_controller=self.spend_controller,
            request_id=self.request_id,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            name="legalforecast-native-lab-gateway",
            daemon=True,
        )
        thread.start()
        session = LabCoreGatewaySession(
            gateway=self,
            server=server,
            thread=thread,
            usage_path=usage_path,
        )
        try:
            yield session
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
            if thread.is_alive():
                raise LabCoreGatewayError("native LAB gateway did not shut down")


@dataclass(frozen=True, slots=True)
class LabCoreGatewaySession:
    """Live gateway route and final accounting for one native LAB run."""

    gateway: LabCoreGateway = field(repr=False)
    server: ModelGatewayHTTPServer = field(repr=False)
    thread: threading.Thread = field(repr=False)
    usage_path: Path

    @property
    def environment(self) -> dict[str, str]:
        """Return only the synthetic key and loopback base URL for LAB."""

        return {
            "ANTHROPIC_API_KEY": self.gateway.policy.capability_token,
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{self.server.server_port}",
        }

    @property
    def secret_values(self) -> tuple[str, ...]:
        """Return values that must not appear in normalized public output."""

        return (
            self.gateway.policy.upstream_api_key,
            self.gateway.policy.capability_token,
        )

    def snapshot(self) -> GatewayUsageSnapshot:
        """Return the gateway's current aggregate usage."""

        return self.server.gateway.usage.snapshot()

    def require_settled(self) -> dict[str, int | None]:
        """Require both model phases to have complete gateway accounting."""

        snapshot = self.snapshot()
        if snapshot.request_count <= 0:
            raise LabCoreGatewayError("native LAB made no gateway requests")
        if snapshot.rejected_count:
            raise LabCoreGatewayError("native LAB gateway rejected a model request")
        if snapshot.reserved_input_tokens or snapshot.reserved_output_tokens:
            raise LabCoreGatewayError("native LAB gateway has unsettled usage")
        if (
            snapshot.observed_input_tokens is None
            or snapshot.observed_output_tokens is None
        ):
            raise LabCoreGatewayError(
                "native LAB gateway did not receive complete provider usage"
            )

        settled_requests: int | None = None
        settled_microusd: int | None = None
        if self.gateway.spend_controller is not None:
            totals = getattr(self.gateway.spend_controller, "settlement_totals", None)
            if not callable(totals):
                raise LabCoreGatewayError(
                    "native LAB spend controller has no settlement journal"
                )
            settled_requests, settled_microusd = totals()
            if (
                type(settled_requests) is not int
                or type(settled_microusd) is not int
                or settled_requests != snapshot.request_count
                or settled_microusd < 0
            ):
                raise LabCoreGatewayError(
                    "native LAB gateway and spend journal disagree"
                )

        return {
            "request_count": snapshot.request_count,
            "input_tokens": snapshot.observed_input_tokens,
            "output_tokens": snapshot.observed_output_tokens,
            "rejected_count": snapshot.rejected_count,
            "settled_requests": settled_requests,
            "settled_microusd": settled_microusd,
        }


__all__ = ["LabCoreGateway", "LabCoreGatewayError", "LabCoreGatewaySession"]

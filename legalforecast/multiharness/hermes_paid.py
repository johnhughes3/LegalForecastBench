"""Protected release Hermes route using the existing bounded Anthropic gateway.

This owns no agent loop or alternative spend authority. Hermes runs through the
command adapter; all provider requests use the shared gateway and controller.
"""

from __future__ import annotations

import secrets
import sys
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from legalforecast.immutable_io import ensure_private_directory
from legalforecast.multiharness.adapters import AdapterPreparation, ToolExecutor
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    ProtectedPaidGatewayConfig,
    build_paid_gateway_controller,
    load_paid_gateway_config,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
)
from legalforecast.multiharness.container_harness.model_gateway_protocol import (
    ModelGatewayPolicy,
)
from legalforecast.multiharness.container_harness.model_gateway_server import (
    build_model_gateway_server,
)
from legalforecast.multiharness.hermes_agent import capabilities, validate_checkout
from legalforecast.multiharness.protected_terminal_paid import (
    UPSTREAM_API_KEY_ENV,
    GitHubEnvironmentGatewayCredentialSource,
)
from legalforecast.multiharness.release_harness import is_release_task
from legalforecast.multiharness.release_runtime import (
    release_bytes_sha256,
    release_canonical_bytes,
    release_record_sha256,
    write_release_create_only,
    write_release_json_create_only,
)
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_no_secret_values


@dataclass(frozen=True, slots=True)
class ProtectedHermesAdapter:
    """An outcome-blinded LFB adapter with host-only credentials and settlement."""

    checkout: Path
    config: ProtectedPaidGatewayConfig
    timeout_seconds: int

    @property
    def manifest(self) -> AdapterManifest:
        return AdapterManifest(
            adapter_id="hermes-agent",
            adapter_version="1.0.0",
            display_name="Pinned Hermes Agent Protected Release",
            command=(
                "legalforecast",
                "multiharness",
                "release-execute",
                "--harness",
                "hermes-agent",
            ),
        )

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        del workspace
        return replace(
            capabilities(),
            capabilities_sha256=release_record_sha256(
                {
                    "bridge": capabilities().capabilities_sha256,
                    "protected_bridge": release_bytes_sha256(
                        Path(__file__).read_bytes()
                    ),
                    "paid_config": asdict(self.config.spend),
                    "registry": self.config.model_registry_sha256,
                    "entry": self.config.model_registry_entry_sha256,
                    "max_requests": self.config.max_requests,
                    "timeout_seconds": self.timeout_seconds,
                    "gateway": "anthropic-messages-host-only",
                    "reasoning_effort": self.config.registry_entry.reasoning_effort
                    or "high",
                }
            ),
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        if (
            request.adapter != self.manifest
            or request.model_key != self.config.model_key
            or not is_release_task(request)
            or request.task.family != "legalforecast_mtd"
            or request.task.scoring_mode != "lfb_brier"
            or request.sandbox_policy.allowed_provider_env_vars
        ):
            raise ValueError(
                "protected Hermes requires its exact blinded release contract"
            )
        validate_checkout(self.checkout)
        return AdapterPreparation(
            self.manifest, self.capabilities(workspace), workspace
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        raise ValueError("protected Hermes requires host-owned live tools")

    def run_with_tools(
        self, request: RunRequest, workspace: Path, tool_executor: ToolExecutor
    ) -> RunResult:
        self.prepare(request, workspace)
        # Construct the canonical spend authority before retrieving the real key.
        controller = build_paid_gateway_controller(self.config)
        upstream_key = (
            GitHubEnvironmentGatewayCredentialSource().upstream_environment()[
                UPSTREAM_API_KEY_ENV
            ]
        )
        capability = secrets.token_urlsafe(32)
        entry = self.config.registry_entry
        policy = ModelGatewayPolicy(
            upstream_base_url=MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
            upstream_api_key=upstream_key,
            capability_token=capability,
            allowed_models=frozenset({entry.model_id}),
            allowed_ingress_hosts=frozenset({"127.0.0.1"}),
            max_requests=self.config.max_requests,
            max_input_tokens=entry.context_limit,
            max_output_tokens=entry.max_output_tokens,
            max_total_input_tokens=entry.context_limit * self.config.max_requests,
            max_total_output_tokens=entry.max_output_tokens * self.config.max_requests,
            upstream_timeout_seconds=min(120, self.timeout_seconds),
        )
        private = ensure_private_directory(
            workspace.absolute() / "private-logs" / "gateway"
        )
        server = build_model_gateway_server(
            policy,
            usage_evidence_path=private / "usage.json",
            spend_controller=controller,
            request_id=f"paid-gateway:{self.config.spend.reservation_ledger_sha256}:{request.request_id}",
        )
        route = private / "route.json"
        write_release_json_create_only(
            route,
            {
                "request_sha256": request.request_sha256,
                "model_key": request.model_key,
                "base_url": f"http://127.0.0.1:{server.server_port}",
                "capability_token": capability,
                "max_output_tokens": entry.max_output_tokens,
                "reasoning_config": {"effort": entry.reasoning_effort or "high"},
            },
        )
        delegate = CommandAdapter(
            manifest=replace(
                self.manifest,
                command=(
                    sys.executable,
                    "-m",
                    "legalforecast.multiharness.hermes_agent",
                    "--hermes-checkout",
                    str(self.checkout),
                    "--gateway-route",
                    str(route),
                ),
            ),
            timeout_seconds=self.timeout_seconds,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = delegate.run_with_tools(request, workspace, tool_executor)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            route.unlink()
        usage = server.gateway.usage.snapshot()
        settled_requests, settled_microusd = controller.settlement_totals()
        if (
            usage.request_count < 1
            or settled_requests != usage.request_count
            or usage.observed_input_tokens is None
            or usage.observed_output_tokens is None
            or usage.reserved_input_tokens
            or usage.reserved_output_tokens
            or result.status != "succeeded"
        ):
            raise ValueError("Hermes provider usage did not fully settle")
        evidence = {
            "request_sha256": request.request_sha256,
            "capabilities_sha256": self.capabilities(workspace).capabilities_sha256,
            "model_key": request.model_key,
            "auth_profile": "published-api-key",
            "ceiling_microusd": self.config.spend.ceiling_microusd,
            "usage": asdict(usage),
            "settled_requests": settled_requests,
            "settled_microusd": settled_microusd,
        }
        payload = release_canonical_bytes(evidence)
        path = private / "settlement.json"
        write_release_create_only(path, payload, mode=0o600)
        digest = release_bytes_sha256(payload)
        summary = {
            **result.public_summary,
            "gateway_settlement_sha256": digest,
            "provider_requests": settled_requests,
            "cost_microusd": settled_microusd,
        }
        validate_no_secret_values(
            summary, (upstream_key, capability), "Hermes paid summary"
        )
        return replace(
            result,
            public_summary=summary,
            result_sha256=release_record_sha256(
                {"result": result.result_sha256, "settlement": digest}
            ),
            artifacts=(
                *result.artifacts,
                ArtifactRecord(
                    artifact_id="hermes-gateway-settlement-private",
                    path=path.relative_to(workspace.absolute()).as_posix(),
                    sha256=digest,
                    media_type="application/json",
                    public=False,
                    size_bytes=len(payload),
                ),
            ),
        )


def build_protected_hermes_adapter(
    *,
    checkout: Path,
    paid_config_path: Path,
    model_registry_path: Path,
    model_key: str,
    max_budget_usd: float,
    timeout_seconds: int,
) -> ProtectedHermesAdapter:
    """Validate frozen identity and the aggregate cap before credential access."""

    config = load_paid_gateway_config(
        paid_config_path, model_registry_path=model_registry_path
    )
    if config.harness_id != "hermes-agent":
        raise ValueError("protected paid gateway harness does not match Hermes")
    entry = config.registry_entry
    if (
        entry.tool_policy.value != "controlled_docket_tool_only"
        or entry.jev_input_mode is not None
        or entry.temperature is not None
        or entry.top_p is not None
        or entry.reasoning_effort not in {None, "low", "medium", "high", "max"}
    ):
        raise ValueError(
            "Hermes requires a full-document tool registry "
            "with supported reasoning settings"
        )
    if (
        config.model_key != model_key
        or round(max_budget_usd * 1_000_000) != config.spend.ceiling_microusd
    ):
        raise ValueError(
            "Hermes model and budget must match the paid gateway descriptor"
        )
    validate_checkout(checkout)
    return ProtectedHermesAdapter(checkout.resolve(), config, timeout_seconds)

"""Pinned OpenClaw forecast-release execution through the protected gateway.

The existing container harness owns networking, the gateway owns credentials
and per-request spend admission/settlement, and OpenClaw owns every model turn.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, replace
from pathlib import Path

from legalforecast.multiharness.adapters import AdapterPreparation
from legalforecast.multiharness.auth_profiles import PUBLISHED_API_KEY
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.container_harness import (
    ContainerHarnessSpec,
    ModelGatewayRequest,
    run_container_harness,
)
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    load_paid_gateway_config,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
)
from legalforecast.multiharness.openclaw import (
    GATEWAY_HARNESS_ID,
    OPENCLAW_COMMIT,
    OPENCLAW_VERSION,
    TOOL_NAME,
    OpenClawError,
    capabilities,
    record_digest,
    validate_request,
)
from legalforecast.multiharness.openclaw_worker import CAPABILITY_ENV
from legalforecast.multiharness.protected_terminal_paid import (
    PROTECTED_AUTHORITY_REGION_ENV,
)
from legalforecast.multiharness.release_harness import (
    RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
    RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
    read_release_object,
    read_release_regular_file,
    release_bytes_sha256,
    release_canonical_bytes,
    require_release_metadata_str,
    write_release_create_only,
)
from legalforecast.multiharness.release_runtime import write_release_json_create_only
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.terminal_release_cli import TerminalReleaseOptions


@dataclass(frozen=True, slots=True)
class OpenClawContainerAdapter:
    """Release-only adapter; local/unfunded fallback is deliberately absent."""

    options: TerminalReleaseOptions

    def __post_init__(self) -> None:
        options = self.options
        if (
            options.auth_profile != PUBLISHED_API_KEY
            or options.paid_config_path is None
            or options.model_registry_path is None
        ):
            raise OpenClawError(
                "OpenClaw container requires the protected paid descriptor and registry"
            )
        if (
            options.fixture_base_url is not None
            or options.fixture_egress_network is not None
            or options.approval_reference is not None
        ):
            raise OpenClawError(
                "OpenClaw protected execution cannot use fixture routing"
            )
        if (
            options.gateway_upstream_base_url
            != MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL
        ):
            raise OpenClawError(
                "OpenClaw protected gateway must use the fixed Anthropic origin"
            )
        if options.gateway_image_digest is None:
            raise OpenClawError("OpenClaw requires a pinned gateway image")
        require_digest_pinned_image(options.image, "OpenClaw image")
        require_digest_pinned_image(options.gateway_image_digest, "gateway image")
        config = load_paid_gateway_config(
            options.paid_config_path, model_registry_path=options.model_registry_path
        )
        if (
            config.harness_id != GATEWAY_HARNESS_ID
            or not config.forecast_release_digest
        ):
            raise OpenClawError(
                "paid descriptor must bind the exact pinned OpenClaw harness "
                "and forecast release"
            )
        if config.model_key != options.model_key or not options.model_key.startswith(
            "anthropic:"
        ):
            raise OpenClawError(
                "OpenClaw model must match the protected Anthropic registry"
            )
        if (
            options.max_budget_usd is None
            or round(options.max_budget_usd * 1_000_000)
            != config.spend.ceiling_microusd
        ):
            raise OpenClawError("OpenClaw ceiling must equal the protected descriptor")
        effort = config.registry_entry.reasoning_effort
        if effort is None or effort.value != "high":
            raise OpenClawError(
                "OpenClaw requires a registry with explicit high reasoning"
            )

    @property
    def manifest(self) -> AdapterManifest:
        path = (
            Path(__file__).resolve().parents[2]
            / "examples/adapters/openclaw-pinned/adapter-manifest.json"
        )
        return CommandAdapter.from_manifest_file(path).manifest

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        del workspace
        return capabilities()

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        validate_request(request)
        backend, env = resolve_rootless_backend(self.options.backend)
        resolve_local_image_id(backend, self.options.image, env)
        assert self.options.gateway_image_digest is not None
        resolve_local_image_id(backend, self.options.gateway_image_digest, env)
        return AdapterPreparation(
            manifest=self.manifest, capabilities=capabilities(), workspace=workspace
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        raise OpenClawError(
            "OpenClaw container requires authenticated forecast-release input"
        )

    def run_with_solver_input(
        self, request: RunRequest, workspace: Path, solver_input_root: Path
    ) -> RunResult:
        validate_request(request)
        if (
            request.model_key != self.options.model_key
            or request.sandbox_policy.allowed_provider_env_vars
            or request.sandbox_policy.timeout_seconds != self.options.timeout_seconds
        ):
            raise OpenClawError(
                "OpenClaw request model/grant/timeout differs from its protected route"
            )
        assert self.options.paid_config_path is not None
        assert self.options.model_registry_path is not None
        config = load_paid_gateway_config(
            self.options.paid_config_path,
            model_registry_path=self.options.model_registry_path,
        )
        if (
            require_release_metadata_str(
                request.task.metadata, "forecast_release_digest"
            )
            != config.forecast_release_digest
        ):
            raise OpenClawError(
                "OpenClaw task differs from the approved forecast release"
            )
        prompt = read_release_regular_file(solver_input_root / "prompt.txt")
        prompt_digest = require_release_metadata_str(
            request.task.metadata, "prompt_sha256"
        )
        if release_bytes_sha256(prompt) != prompt_digest:
            raise OpenClawError("OpenClaw staged prompt commitment mismatch")
        workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_release_create_only(workspace / "prompt.txt", prompt, mode=0o400)
        write_release_json_create_only(
            workspace / "openclaw-request.json", request.to_record()
        )
        write_release_json_create_only(
            workspace / "openclaw-model.json",
            {
                "context_limit": config.registry_entry.context_limit,
                "max_output_tokens": config.registry_entry.max_output_tokens,
                "reasoning_effort": "high",
            },
        )
        capability = secrets.token_urlsafe(32)
        region = os.environ.get(PROTECTED_AUTHORITY_REGION_ENV, "")
        if not region or any(
            c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in region
        ):
            raise OpenClawError("protected gateway region is missing or invalid")
        spec = ContainerHarnessSpec(
            run_id="openclaw-" + request.request_sha256.removeprefix("sha256:")[:16],
            image=self.options.image,
            proxy_image=self.options.gateway_image_digest,
            harness_argv=("run",),
            workspace=workspace,
            log_root=workspace / "private-logs/container",
            allow_hosts=("api.anthropic.com", f"dynamodb.{region}.amazonaws.com"),
            environment={CAPABILITY_ENV: capability},
            cli_name="openclaw",
            model_gateway=ModelGatewayRequest(
                upstream_base_url=MODEL_GATEWAY_PROTECTED_UPSTREAM_BASE_URL,
                model_key=request.model_key,
                run_capability=capability,
                paid_config_path=self.options.paid_config_path,
                model_registry_path=self.options.model_registry_path,
                request_id=request.request_id,
            ),
            container_user="0:0",
            read_only_workspace_paths=(
                "prompt.txt",
                "openclaw-request.json",
                "openclaw-model.json",
            ),
            timeout_seconds=self.options.timeout_seconds,
        )
        container = run_container_harness(
            spec,
            publication_directory=workspace / "private-logs/container-package",
            backend=self.options.backend,
        )
        if (
            container.exit_code != 0
            or container.timed_out
            or container.gateway_usage is None
        ):
            raise OpenClawError("contained OpenClaw or gateway accounting failed")
        if read_release_regular_file(workspace / "prompt.txt") != prompt:
            raise OpenClawError("OpenClaw changed the authenticated prompt")
        result = RunResult.from_record(
            read_release_object(workspace / "openclaw-result.json", "OpenClaw result")
        )
        summary = result.public_summary
        if (
            result.request_id != request.request_id
            or result.status != "succeeded"
            or summary.get("openclaw_version") != OPENCLAW_VERSION
            or summary.get("openclaw_commit") != OPENCLAW_COMMIT
            or summary.get("prompt_delivery_complete") is not True
            or summary.get("auth_mode") != "protected-gateway-capability"
            or summary.get("provider") != "anthropic"
            or summary.get("requested_model") != request.model_key.split(":", 1)[1]
            or summary.get("served_model") != summary.get("requested_model")
        ):
            raise OpenClawError("OpenClaw worker result/provenance mismatch")
        forecast = read_release_regular_file(
            workspace / "private-logs/openclaw-forecast.json"
        )
        transcript = release_canonical_bytes(
            {
                "request_sha256": request.request_sha256,
                "packet_sha256": require_release_metadata_str(
                    request.task.metadata, "packet_sha256"
                ),
                "prompt_sha256": prompt_digest,
                "response_sha256": release_bytes_sha256(forecast),
                "container": container.to_record(),
            }
        )
        transcript_path = "private-logs/release-harness-transcript.json"
        write_release_create_only(workspace / transcript_path, transcript, mode=0o600)
        output_artifact = ArtifactRecord(
            artifact_id=RELEASE_FORECAST_OUTPUT_ARTIFACT_ID,
            path="private-logs/openclaw-forecast.json",
            sha256=release_bytes_sha256(forecast),
            media_type="application/json",
            public=False,
            size_bytes=len(forecast),
        )
        transcript_artifact = ArtifactRecord(
            artifact_id=RELEASE_HARNESS_TRANSCRIPT_ARTIFACT_ID,
            path=transcript_path,
            sha256=release_bytes_sha256(transcript),
            media_type="application/json",
            public=False,
            size_bytes=len(transcript),
        )
        public = dict(
            summary,
            harness_track="native",
            allowed_tools=[TOOL_NAME],
            tool_policy="host-container-solver-prompt-only",
            transcript_sha256=transcript_artifact.sha256,
            gateway_usage=dict(container.gateway_usage),
        )
        return replace(
            result,
            artifacts=(output_artifact, transcript_artifact),
            public_summary=public,
            result_sha256=record_digest(
                {
                    "request": request.request_sha256,
                    "summary": public,
                    "forecast": output_artifact.sha256,
                }
            ),
        )

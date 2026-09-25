"""Fail-closed Claude Code container adapter configuration.

The image and CLI policy are useful only when Claude's native Linux sandbox can
create its child namespace and hide the parent process environment.  Rootless
Docker on the supported development host cannot currently create that nested
namespace.  This module keeps the release-facing adapter identity and factory
in one place, but refuses execution unless its production runtime preflight
succeeds.  It deliberately does not project an API key into a child
container as a workaround: a proxy that gives Bash the model route is not the
required boundary.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit

from legalforecast.multiharness.adapters import AdapterPreparation
from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
    require_auth_profile_id,
)
from legalforecast.multiharness.claude_code import (
    CLAUDE_CODE_ADAPTER_VERSION,
    ClaudeCodeCliAdapter,
    ClaudeCodeCliAdapterError,
    claude_code_local_manifest,
)
from legalforecast.multiharness.claude_code_container_inputs import (
    stage_visible_solver_input as _stage_visible_solver_input,
)
from legalforecast.multiharness.claude_code_container_inputs import (
    verify_staged_solver_input as _verify_staged_solver_input,
)
from legalforecast.multiharness.claude_code_container_runtime import (
    MODEL_GATEWAY_HOST,
    MODEL_GATEWAY_PORT,
    NATIVE_SANDBOX_MODE,
    OUTER_CONTAINER_ONLY_MODE,
    ClaudeCodeContainerExecutionService,
    ClaudeExecutionMode,
    probe_native_claude_sandbox,
)
from legalforecast.multiharness.claude_code_stream import (
    normalize_claude_stream,
    terminal_success,
)
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
    capability_digest_for,
)
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliExecutionService,
)
from legalforecast.multiharness.release_harness import (
    ReleaseHarnessError,
    read_release_regular_file,
    release_bytes_sha256,
    require_release_metadata_str,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

# Keep the historical private test/import seams while the implementations live
# in focused modules.
_normalize_claude_stream = normalize_claude_stream
_terminal_success = terminal_success

CLAUDE_CODE_CONTAINER_ADAPTER_ID: Final[str] = "claude-code-container"
CLAUDE_CODE_CONTAINER_DISPLAY_NAME: Final[str] = "Claude Code container"
CLAUDE_CODE_CONTAINER_ADAPTER_VERSION: Final[str] = CLAUDE_CODE_ADAPTER_VERSION
CLAUDE_CODE_IMAGE_VERSION: Final[str] = "2.1.282 (Claude Code)"
_STAGED_PROMPT_INSTRUCTION: Final[str] = (
    "Read the complete authenticated solver input from /workspace/prompt.txt "
    "with Bash before answering. Follow that input exactly, use only the "
    "workspace files it identifies, and return the requested structured answer."
)


class ClaudeCodeContainerAdapterError(ClaudeCodeCliAdapterError):
    """Raised when container execution cannot prove the required boundary."""


ApprovalVerifier = Callable[[str, float], None]


@dataclass(frozen=True, slots=True)
class ClaudeCodeContainerAdapter:
    """Release-facing adapter with fail-closed native and fixture-only modes."""

    delegate: ClaudeCodeCliAdapter
    image_digest: str
    model_key: str
    auth_profile: str
    max_budget_usd: float | None
    approval_reference: str | None
    output_root: Path
    backend: str
    timeout_seconds: int
    case_count: int | None
    per_case_budget_usd: float | None
    approval_verifier: ApprovalVerifier | None = None
    sandbox_verified: bool = False
    execution_mode: ClaudeExecutionMode = NATIVE_SANDBOX_MODE
    outer_container_verified: bool = False

    @property
    def manifest(self) -> AdapterManifest:
        return self.delegate.manifest

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        return self.delegate.capabilities(workspace)

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        self._preflight(request.model_key)
        return self.delegate.prepare(request, workspace)

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self._preflight(request.model_key)
        return self.delegate.run(request, workspace)

    def run_with_solver_input(
        self,
        request: RunRequest,
        workspace: Path,
        solver_input_root: Path,
    ) -> RunResult:
        """Expose the authenticated prompt only inside the run workspace.

        The release harness authenticates the solver-input tree before calling
        this method. We repeat the prompt commitment check at the execution
        boundary, create the prompt read-only, and give Claude a fixed
        instruction to read that file with its managed Bash tool. The prompt
        bytes are not copied into task metadata or the host-side CLI argv.
        """

        self._preflight(request.model_key)
        try:
            prompt = read_release_regular_file(
                solver_input_root / SOLVER_INPUT_ENTRY_PATH
            )
            prompt_sha256 = require_release_metadata_str(
                request.task.metadata, "prompt_sha256"
            )
            if release_bytes_sha256(prompt) != prompt_sha256:
                raise ReleaseHarnessError(
                    "container prompt commitment does not match authenticated input"
                )
            staged_files, staged_directories = _stage_visible_solver_input(
                solver_input_root,
                workspace,
            )
            try:
                result = self.delegate.run_with_prompt(
                    request,
                    workspace,
                    _STAGED_PROMPT_INSTRUCTION,
                )
                _verify_staged_solver_input(staged_files)
                return result
            finally:
                for path, _payload in reversed(staged_files):
                    path.unlink(missing_ok=True)
                for path in reversed(staged_directories):
                    path.rmdir()
        except ReleaseHarnessError as exc:
            raise ClaudeCodeContainerAdapterError(str(exc)) from exc

    def _preflight(self, requested_model_key: str) -> None:
        if requested_model_key != self.model_key:
            raise ClaudeCodeContainerAdapterError(
                "request model_key does not match the configured container adapter"
            )
        if self.execution_mode == NATIVE_SANDBOX_MODE and not self.sandbox_verified:
            raise ClaudeCodeContainerAdapterError(
                "native Claude Code sandbox is not verified for this container "
                "topology; refusing execution instead of retrying unsandboxed"
            )
        if self.execution_mode == OUTER_CONTAINER_ONLY_MODE and (
            not self.outer_container_verified
        ):
            raise ClaudeCodeContainerAdapterError(
                "outer-container-only fixture topology is not verified"
            )
        if self.execution_mode not in {NATIVE_SANDBOX_MODE, OUTER_CONTAINER_ONLY_MODE}:
            raise ClaudeCodeContainerAdapterError(
                f"unsupported Claude Code execution mode: {self.execution_mode}"
            )
        if self.auth_profile == PUBLISHED_API_KEY:
            verifier = self.approval_verifier
            if verifier is None or self.approval_reference is None:
                raise ClaudeCodeContainerAdapterError(
                    "published-api-key requires an authoritative spend approval "
                    "verifier and reference before credentials are resolved"
                )
            verifier(self.approval_reference, self.max_budget_usd or 0.0)


def build_claude_code_container_adapter(
    *,
    image_digest: str,
    auth_profile: str,
    model_key: str,
    max_budget_usd: float | None,
    approval_reference: str | None,
    output_root: Path,
    backend: str = "docker",
    timeout_seconds: int = 900,
    case_count: int | None = None,
    approval_verifier: ApprovalVerifier | None = None,
    fixture_base_url: str | None = None,
    fixture_egress_network: str | None = None,
    execution_mode: ClaudeExecutionMode = NATIVE_SANDBOX_MODE,
    gateway_base_url: str | None = None,
    gateway_upstream_base_url: str | None = None,
) -> ClaudeCodeContainerAdapter:
    """Build the ``claude-code-container`` adapter without starting a run.

    ``max_budget_usd`` is the aggregate release ceiling.  ``case_count`` is
    required for paid profiles so the factory can bind the per-case Claude
    ``--max-budget-usd`` value instead of silently treating a release total as
    a per-case cap.  A published-api-key adapter also needs a verifier for the
    repository's authoritative approval artifact before credentials are read.
    """

    if not image_digest.startswith("sha256:"):
        raise ClaudeCodeContainerAdapterError(
            "image_digest must be a sha256-pinned image identity"
        )
    if len(image_digest) != len("sha256:") + 64:
        raise ClaudeCodeContainerAdapterError("image_digest must be a full SHA-256")
    profile = require_auth_profile_id(auth_profile)
    if profile not in {FIXTURE_NONE, PUBLISHED_API_KEY}:
        raise ClaudeCodeContainerAdapterError(
            "Claude Code container supports fixture-none or published-api-key"
        )
    if not model_key.startswith("anthropic:") or len(model_key) == len("anthropic:"):
        raise ClaudeCodeContainerAdapterError(
            "model_key must use the anthropic:<model> namespace"
        )
    if max_budget_usd is not None and (
        not math.isfinite(max_budget_usd) or max_budget_usd <= 0
    ):
        raise ClaudeCodeContainerAdapterError("max_budget_usd must be positive")
    if profile == PUBLISHED_API_KEY and not approval_reference:
        raise ClaudeCodeContainerAdapterError(
            "published-api-key requires an approval_reference"
        )
    if profile == PUBLISHED_API_KEY and max_budget_usd is None:
        raise ClaudeCodeContainerAdapterError(
            "published-api-key requires max_budget_usd"
        )
    if profile == PUBLISHED_API_KEY and (case_count is None or case_count <= 0):
        raise ClaudeCodeContainerAdapterError(
            "published-api-key requires the selected case_count to derive a "
            "per-case Claude ceiling"
        )
    if not output_root.is_absolute():
        raise ClaudeCodeContainerAdapterError("output_root must be absolute")
    if backend != "docker":
        raise ClaudeCodeContainerAdapterError("backend must be docker")
    if timeout_seconds <= 0:
        raise ClaudeCodeContainerAdapterError("timeout_seconds must be positive")
    if execution_mode not in {NATIVE_SANDBOX_MODE, OUTER_CONTAINER_ONLY_MODE}:
        raise ClaudeCodeContainerAdapterError(
            "execution_mode must be native-sandbox or outer-container-only"
        )
    if (
        execution_mode != OUTER_CONTAINER_ONLY_MODE
        and gateway_base_url is not None
        and fixture_base_url is not None
    ):
        raise ClaudeCodeContainerAdapterError(
            "provide gateway_base_url or fixture_base_url, not both"
        )
    if execution_mode == OUTER_CONTAINER_ONLY_MODE:
        if profile != FIXTURE_NONE:
            raise ClaudeCodeContainerAdapterError(
                "outer-container-only is fixture-only until a credential broker "
                "is integrated"
            )
        if gateway_upstream_base_url is None and fixture_base_url is None:
            raise ClaudeCodeContainerAdapterError(
                "outer-container-only requires a fixture upstream endpoint"
            )
        if gateway_base_url is not None:
            parsed_gateway = urlsplit(gateway_base_url)
            if (
                parsed_gateway.scheme != "http"
                or parsed_gateway.hostname != MODEL_GATEWAY_HOST
                or (parsed_gateway.port or 80) != MODEL_GATEWAY_PORT
            ):
                raise ClaudeCodeContainerAdapterError(
                    "outer-container-only requires the internal fixture gateway"
                )
    elif gateway_upstream_base_url is not None:
        raise ClaudeCodeContainerAdapterError(
            "gateway_upstream_base_url requires outer-container-only"
        )

    per_case_budget_usd = (
        None
        if max_budget_usd is None or case_count is None
        else max_budget_usd / case_count
    )
    if execution_mode == OUTER_CONTAINER_ONLY_MODE:
        # Outer mode skips the native bwrap probe, but it must still fail at
        # adapter construction when the selected backend or pinned image is
        # unavailable. Otherwise release scoring can turn setup failure into a
        # misleading all-failed result.
        try:
            backend_path, backend_environment = resolve_rootless_backend(backend)
            resolve_local_image_id(backend_path, image_digest, backend_environment)
        except ContainerImageError as exc:
            raise ClaudeCodeContainerAdapterError(
                f"outer-container-only preflight failed: {exc}"
            ) from exc
    manifest = _container_manifest(image_digest)
    sandbox_verified = (
        probe_native_claude_sandbox(
            image_digest,
            backend=backend,
            timeout_seconds=min(timeout_seconds, 30),
        )
        if execution_mode == NATIVE_SANDBOX_MODE
        else False
    )
    service = ClaudeCodeContainerExecutionService(
        image_digest=image_digest,
        auth_profile=profile,
        model_key=model_key,
        output_root=output_root,
        backend=backend,
        fixture_base_url=fixture_base_url,
        gateway_base_url=gateway_base_url,
        gateway_upstream_base_url=gateway_upstream_base_url,
        fixture_egress_network=fixture_egress_network,
        execution_mode=execution_mode,
        sandbox_verified=sandbox_verified,
    )
    delegate = ClaudeCodeCliAdapter(
        execution_service=cast(LocalCliExecutionService, service),
        local_manifest=manifest,
        auth_profile=profile,
        adapter_id=CLAUDE_CODE_CONTAINER_ADAPTER_ID,
        max_budget_usd=(
            None if per_case_budget_usd is None else f"{per_case_budget_usd:.6f}"
        ),
        output_format="stream-json",
        verbose=True,
    )
    return ClaudeCodeContainerAdapter(
        delegate=delegate,
        image_digest=image_digest,
        model_key=model_key,
        auth_profile=profile,
        max_budget_usd=max_budget_usd,
        approval_reference=approval_reference,
        output_root=output_root,
        backend=backend,
        timeout_seconds=timeout_seconds,
        case_count=case_count,
        per_case_budget_usd=per_case_budget_usd,
        approval_verifier=approval_verifier,
        sandbox_verified=sandbox_verified,
        execution_mode=execution_mode,
        outer_container_verified=execution_mode == OUTER_CONTAINER_ONLY_MODE,
    )


def _container_manifest(image_digest: str) -> LocalCliAdapterManifest:
    base = claude_code_local_manifest()
    record = base.to_record()
    record["manifest_id"] = CLAUDE_CODE_CONTAINER_ADAPTER_ID
    record["display_name"] = CLAUDE_CODE_CONTAINER_DISPLAY_NAME
    executable = dict(record["executable"])
    # Local CLI manifests store the executable digest without the ``sha256:``
    # prefix; the adapter's separate image identity retains the full pin.
    executable["sha256"] = image_digest.removeprefix("sha256:")
    executable["version"] = CLAUDE_CODE_IMAGE_VERSION
    record["executable"] = executable
    binding = dict(record["harness_binding"])
    binding["adapter_id"] = CLAUDE_CODE_CONTAINER_ADAPTER_ID
    binding["adapter_version"] = CLAUDE_CODE_ADAPTER_VERSION
    record["harness_binding"] = binding
    record["capability_digest"] = capability_digest_for(record)
    manifest = LocalCliAdapterManifest.from_record(record)
    validate_public_record(manifest.to_record(), "Claude Code container manifest")
    return manifest


__all__ = [
    "CLAUDE_CODE_CONTAINER_ADAPTER_ID",
    "CLAUDE_CODE_CONTAINER_ADAPTER_VERSION",
    "NATIVE_SANDBOX_MODE",
    "OUTER_CONTAINER_ONLY_MODE",
    "ClaudeCodeContainerAdapter",
    "ClaudeCodeContainerAdapterError",
    "ClaudeCodeContainerExecutionService",
    "ClaudeExecutionMode",
    "build_claude_code_container_adapter",
    "probe_native_claude_sandbox",
]

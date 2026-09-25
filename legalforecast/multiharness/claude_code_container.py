"""Fail-closed Claude Code container adapter configuration.

The image and CLI policy are useful only when Claude's native Linux sandbox can
create its child namespace and hide the parent process environment.  Rootless
Docker on the supported development host cannot currently create that nested
namespace.  This module keeps the release-facing adapter identity and factory
in one place, but refuses execution until an independently verified runtime
probe is supplied.  It deliberately does not project an API key into a child
container as a workaround: a proxy that gives Bash the model route is not the
required boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
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
from legalforecast.multiharness.container_harness import (
    ContainerHarnessSpec,
    run_container_harness,
)
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
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
    write_release_create_only,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

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
class ClaudeCodeContainerExecutionService:
    """Run one CLI spec through the existing rootless container harness.

    The service deliberately supports only a local fixture endpoint. A live API
    key cannot be placed in this container until an external credential broker
    has proved the child boundary; ``published-api-key`` therefore returns a
    typed refusal before any credential lookup.
    """

    image_digest: str
    auth_profile: str
    output_root: Path
    backend: str = "docker"
    fixture_base_url: str | None = None
    fixture_egress_network: str | None = None
    profile_env_vars: tuple[tuple[str, tuple[str, ...]], ...] = (
        (FIXTURE_NONE, ()),
        (PUBLISHED_API_KEY, ("ANTHROPIC_API_KEY",)),
    )

    def env_vars_for_profile(self, profile_id: str) -> tuple[str, ...]:
        for declared, names in self.profile_env_vars:
            if declared == profile_id:
                return names
        return ()

    def execute(self, spec: RunSpec) -> ExecutionReceipt:
        if self.auth_profile == PUBLISHED_API_KEY:
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=(
                    "published-api-key requires a separate credential broker; "
                    "the container harness does not project provider keys"
                ),
                returncode=None,
                status="failed",
            )
        endpoint = self.fixture_base_url
        if endpoint is None:
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr="fixture_base_url is required for fixture-none execution",
                returncode=None,
                status="failed",
            )
        try:
            parsed = urlsplit(endpoint)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if parsed.scheme not in {"http", "https"} or host is None:
                raise ValueError("fixture_base_url must be an HTTP URL")
            require_digest_pinned_image(self.image_digest, "image_digest")
            run_key = hashlib.sha256(spec.spec_id.encode("utf-8")).hexdigest()[:16]
            run_root = self.output_root / run_key
            log_root = run_root / "logs"
            package_root = run_root / "package"
            log_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            package_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            environment = {
                "ANTHROPIC_BASE_URL": endpoint,
                "ANTHROPIC_API_KEY": "fixture-only-dummy-key",
            }
            if parsed.scheme == "https":
                # The local fixture uses an ephemeral self-signed certificate;
                # this branch never applies to a published provider profile.
                environment["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
            result = run_container_harness(
                ContainerHarnessSpec(
                    run_id=f"claude-{run_key}",
                    image=self.image_digest,
                    harness_argv=spec.argv[1:],
                    workspace=spec.working_directory,
                    log_root=log_root,
                    allow_hosts=(host,),
                    allow_ports=(port,),
                    # Claude requires an API-key-shaped value before it will
                    # send a request even when the endpoint is a local fixture.
                    # This is a public, non-provider dummy and is never used
                    # for the published-api-key profile.
                    environment=environment,
                    cli_name="claude",
                    egress_network=self.fixture_egress_network,
                    timeout_seconds=max(1, int(spec.timeout_seconds)),
                ),
                publication_directory=package_root,
                backend=self.backend,
            )
            stdout = result.stdout_path.read_text(encoding="utf-8", errors="replace")
            stderr = result.stderr_path.read_text(encoding="utf-8", errors="replace")
            envelope = _json_object(stdout)
            status = (
                "timeout"
                if result.timed_out
                else ("succeeded" if result.exit_code == 0 else "failed")
            )
            return ExecutionReceipt.from_transcript(
                spec,
                stdout=stdout,
                stderr=stderr,
                returncode=result.exit_code,
                status=status,
                served_model=_served_model(envelope),
                usage=_usage(envelope),
                cost_usd=_cost(envelope),
            )
        except Exception as exc:
            # Keep the receipt path-free and typed. The harness writes its
            # private refusal package whenever setup progressed that far.
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=f"container setup refused: {type(exc).__name__}",
                returncode=None,
                status="failed",
            )


@dataclass(frozen=True, slots=True)
class ClaudeCodeContainerAdapter:
    """Release-facing adapter that refuses an unproven native-tool boundary."""

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
        instruction to read that file with its sandboxed Bash tool. The prompt
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
        if not self.sandbox_verified:
            raise ClaudeCodeContainerAdapterError(
                "native Claude Code sandbox is not verified for this container "
                "topology; refusing execution instead of retrying unsandboxed"
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

    per_case_budget_usd = (
        None
        if max_budget_usd is None or case_count is None
        else max_budget_usd / case_count
    )
    manifest = _container_manifest(image_digest)
    service = ClaudeCodeContainerExecutionService(
        image_digest=image_digest,
        auth_profile=profile,
        output_root=output_root,
        backend=backend,
        fixture_base_url=fixture_base_url,
        fixture_egress_network=fixture_egress_network,
    )
    delegate = ClaudeCodeCliAdapter(
        execution_service=cast(LocalCliExecutionService, service),
        local_manifest=manifest,
        auth_profile=profile,
        adapter_id=CLAUDE_CODE_CONTAINER_ADAPTER_ID,
        max_budget_usd=(
            None if per_case_budget_usd is None else f"{per_case_budget_usd:.6f}"
        ),
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
        sandbox_verified=probe_native_claude_sandbox(
            image_digest,
            backend=backend,
            timeout_seconds=min(timeout_seconds, 30),
        ),
    )


def probe_native_claude_sandbox(
    image_digest: str,
    *,
    backend: str = "docker",
    timeout_seconds: int = 30,
) -> bool:
    """Probe the namespace half of Claude's required native sandbox.

    This is the production preflight used by the factory. It checks the
    namespace operation with the exact production capability restrictions; a
    false result keeps the adapter fail closed. It does not resolve a provider
    credential or use host networking. The stricter CLI settings in the image
    then deny credentials, web tools, unsandboxed commands, and child network
    access for a run whose preflight succeeds.
    """

    try:
        require_digest_pinned_image(image_digest, "image_digest")
        backend_path, environment = resolve_rootless_backend(backend)
        resolve_local_image_id(backend_path, image_digest, environment)
        completed = subprocess.run(
            (
                str(backend_path),
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "32",
                "--memory",
                "128m",
                "--cpus=0.25",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=16m",
                "--tmpfs",
                "/workspace:rw,nosuid,nodev,size=16m",
                "--entrypoint",
                "/usr/bin/bwrap",
                image_digest,
                "--unshare-user",
                "--unshare-pid",
                "--unshare-net",
                "--ro-bind",
                "/",
                "/",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "/bin/true",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
            env=dict(environment),
        )
        return completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError):
        return False


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


def _stage_visible_solver_input(
    solver_input_root: Path,
    workspace: Path,
) -> tuple[list[tuple[Path, bytes]], list[Path]]:
    """Copy only the authenticated prompt and visible documents into workspace."""

    if not solver_input_root.is_dir() or solver_input_root.is_symlink():
        raise ReleaseHarnessError("authenticated solver input root is unavailable")
    workspace.mkdir(parents=True, exist_ok=True)
    files: list[tuple[Path, bytes]] = []
    for source in sorted(solver_input_root.rglob("*")):
        if source.is_symlink():
            raise ReleaseHarnessError("authenticated solver input contains a symlink")
        if source.is_dir():
            continue
        relative = source.relative_to(solver_input_root).as_posix()
        if relative != SOLVER_INPUT_ENTRY_PATH and not relative.startswith(
            "documents/"
        ):
            raise ReleaseHarnessError(
                f"authenticated solver input contains a hidden file: {relative}"
            )
        files.append((workspace / relative, read_release_regular_file(source)))
    if not any(
        path.relative_to(workspace).as_posix() == SOLVER_INPUT_ENTRY_PATH
        for path, _ in files
    ):
        raise ReleaseHarnessError("authenticated solver input prompt is missing")
    directories: list[Path] = []
    for path, payload in files:
        parent = path.parent
        missing: list[Path] = []
        while parent != workspace and not parent.exists():
            missing.append(parent)
            parent = parent.parent
        if parent != workspace and (parent.is_symlink() or not parent.is_dir()):
            raise ReleaseHarnessError("solver workspace path is not a directory")
        for directory in reversed(missing):
            directory.mkdir(mode=0o700)
            directories.append(directory)
        # The image runs as UID 65532 while the host workspace belongs to the
        # operator. The workspace itself is private; 0444 is therefore the
        # narrow read-only mode that lets the container UID consume the bytes.
        write_release_create_only(path, payload, mode=0o444)
    return files, directories


def _verify_staged_solver_input(staged_files: list[tuple[Path, bytes]]) -> None:
    for path, expected in staged_files:
        observed = read_release_regular_file(path)
        if observed != expected:
            raise ReleaseHarnessError(
                f"staged solver input changed during execution: {path.name}"
            )


def _json_object(stdout: str) -> dict[str, object] | None:
    try:
        value: object = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _served_model(envelope: dict[str, object] | None) -> str | None:
    if envelope is None:
        return None
    model = envelope.get("model")
    if isinstance(model, str) and model.strip():
        return model
    model_usage = envelope.get("modelUsage")
    if isinstance(model_usage, dict):
        typed_model_usage = cast(dict[str, object], model_usage)
        if len(typed_model_usage) == 1:
            value = next(iter(typed_model_usage))
            return value if value.strip() else None
    return None


def _usage(envelope: dict[str, object] | None) -> dict[str, int]:
    if envelope is None or not isinstance(envelope.get("usage"), dict):
        return {}
    usage = cast(dict[object, object], envelope["usage"])
    return {
        key: value
        for key, value in usage.items()
        if isinstance(key, str) and type(value) is int and value >= 0
    }


def _cost(envelope: dict[str, object] | None) -> float | None:
    if envelope is None:
        return None
    value = envelope.get("total_cost_usd")
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


__all__ = [
    "CLAUDE_CODE_CONTAINER_ADAPTER_ID",
    "CLAUDE_CODE_CONTAINER_ADAPTER_VERSION",
    "ClaudeCodeContainerAdapter",
    "ClaudeCodeContainerAdapterError",
    "ClaudeCodeContainerExecutionService",
    "build_claude_code_container_adapter",
    "probe_native_claude_sandbox",
]

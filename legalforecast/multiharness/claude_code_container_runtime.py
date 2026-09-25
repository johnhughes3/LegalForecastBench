"""Contained Claude Code execution and native-sandbox preflight."""

from __future__ import annotations

import hashlib
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlsplit

from legalforecast.multiharness.auth_profiles import (
    FIXTURE_NONE,
    PUBLISHED_API_KEY,
)
from legalforecast.multiharness.claude_code_stream import (
    cost,
    normalize_claude_stream,
    served_model,
    terminal_success,
    usage,
)
from legalforecast.multiharness.container_harness import (
    MODEL_GATEWAY_HOST,
    MODEL_GATEWAY_PORT,
    ContainerHarnessSpec,
    ModelGatewayRequest,
    run_container_harness,
)
from legalforecast.multiharness.container_harness.fence import FenceObservation
from legalforecast.multiharness.container_harness.images import (
    require_digest_pinned_image,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)

ClaudeExecutionMode = Literal["native-sandbox", "outer-container-only"]
NATIVE_SANDBOX_MODE: Final[ClaudeExecutionMode] = "native-sandbox"
OUTER_CONTAINER_ONLY_MODE: Final[ClaudeExecutionMode] = "outer-container-only"
_EXECUTION_MODES = frozenset({NATIVE_SANDBOX_MODE, OUTER_CONTAINER_ONLY_MODE})


def _fence_allows_forecast(fence: FenceObservation) -> bool:
    """Accept only observed native tools with no provider-side web capability."""

    return (
        fence.observable
        and fence.native_tools_enabled is True
        and fence.server_side_web_tools_disabled is True
        and fence.web_request_count == 0
    )


def _gateway_upstream_origin(value: str) -> tuple[str, str, int]:
    """Return the fixed gateway origin and its network allowlist coordinates."""

    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("fixture upstream endpoint is malformed") from exc
    if parsed.scheme not in {"http", "https"} or host is None:
        raise ValueError("fixture upstream endpoint must be HTTP(S)")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("fixture upstream endpoint must not contain credentials")
    host_for_url = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{parsed.scheme}://{host_for_url}:{port}", host, port


@dataclass(frozen=True, slots=True)
class ClaudeCodeContainerExecutionService:
    """Run one CLI spec through the existing rootless container harness.

    The service deliberately supports only an HTTPS fixture or gateway
    endpoint. A live API key cannot be placed in this container until an
    external credential broker has proved the child boundary;
    ``published-api-key`` therefore returns a typed refusal before any
    credential lookup. ``outer-container-only`` uses the rootless harness's
    per-run internal network and bounded egress sidecar, and is fixture-only.
    """

    image_digest: str
    auth_profile: str
    model_key: str
    output_root: Path
    backend: str = "docker"
    fixture_base_url: str | None = None
    gateway_base_url: str | None = None
    gateway_upstream_base_url: str | None = None
    fixture_egress_network: str | None = None
    execution_mode: ClaudeExecutionMode = NATIVE_SANDBOX_MODE
    sandbox_verified: bool = False
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
        if self.execution_mode not in _EXECUTION_MODES:
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=f"unsupported Claude Code execution mode: {self.execution_mode}",
                returncode=None,
                status="failed",
            )
        if self.execution_mode == NATIVE_SANDBOX_MODE and not self.sandbox_verified:
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=(
                    "native Claude Code sandbox is not verified for this "
                    "container topology"
                ),
                returncode=None,
                status="failed",
            )
        if self.execution_mode == OUTER_CONTAINER_ONLY_MODE and (
            self.auth_profile != FIXTURE_NONE
        ):
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=(
                    "outer-container-only is fixture-only until a credential "
                    "broker is integrated"
                ),
                returncode=None,
                status="failed",
            )
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
        upstream_host: str | None = None
        upstream_port: int | None = None
        if self.execution_mode == OUTER_CONTAINER_ONLY_MODE:
            endpoint = self.gateway_base_url or (
                f"http://{MODEL_GATEWAY_HOST}:{MODEL_GATEWAY_PORT}"
            )
            upstream_endpoint = self.gateway_upstream_base_url or self.fixture_base_url
            if upstream_endpoint is None:
                return ExecutionReceipt.from_transcript(
                    spec,
                    stdout="",
                    stderr=(
                        "outer-container-only requires a fixture upstream endpoint"
                    ),
                    returncode=None,
                    status="failed",
                )
            upstream_origin, upstream_host, upstream_port = _gateway_upstream_origin(
                upstream_endpoint
            )
        else:
            endpoint = self.gateway_base_url or self.fixture_base_url
            upstream_endpoint = None
            upstream_origin = None
        if endpoint is None:
            return ExecutionReceipt.from_transcript(
                spec,
                stdout="",
                stderr=(
                    "gateway_base_url is required for outer-container-only "
                    "fixture execution"
                    if self.execution_mode == OUTER_CONTAINER_ONLY_MODE
                    else "fixture_base_url is required for fixture-none execution"
                ),
                returncode=None,
                status="failed",
            )
        try:
            parsed = urlsplit(endpoint)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if self.execution_mode == OUTER_CONTAINER_ONLY_MODE:
                if (
                    parsed.scheme != "http"
                    or host != MODEL_GATEWAY_HOST
                    or port != MODEL_GATEWAY_PORT
                    or parsed.path not in {"", "/"}
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(
                        "outer gateway endpoint must be the bare internal model "
                        "gateway origin"
                    )
                assert upstream_origin is not None
            else:
                if parsed.scheme != "https" or host is None:
                    raise ValueError("fixture_base_url must be an HTTPS URL")
                upstream_host = host
                upstream_port = port
            assert upstream_host is not None
            assert upstream_port is not None
            require_digest_pinned_image(self.image_digest, "image_digest")
            run_key = hashlib.sha256(spec.spec_id.encode("utf-8")).hexdigest()[:16]
            run_root = self.output_root / run_key
            log_root = run_root / "logs"
            package_root = run_root / "package"
            log_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.execution_mode == OUTER_CONTAINER_ONLY_MODE:
                assert upstream_origin is not None
                run_capability = secrets.token_urlsafe(32)
                environment = {
                    "ANTHROPIC_BASE_URL": endpoint,
                    # Claude requires an API-key-shaped value. This is a
                    # per-run gateway capability, never an upstream key.
                    "ANTHROPIC_API_KEY": run_capability,
                }
                model_gateway = ModelGatewayRequest(
                    upstream_base_url=upstream_origin,
                    model_key=self.model_key,
                    run_capability=run_capability,
                    # The fixture gateway requires a sidecar-only upstream key.
                    # It is a test capability, never a provider credential and
                    # never added to the harness environment or argv.
                    upstream_api_key="fixture-upstream-dummy-key",
                )
            else:
                environment = {
                    "ANTHROPIC_BASE_URL": endpoint,
                    "ANTHROPIC_API_KEY": "fixture-only-dummy-key",
                }
                # The local fixture uses an ephemeral self-signed certificate;
                # this branch never applies to a published provider profile.
                environment["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
                model_gateway = None
            read_only_workspace_paths = ["prompt.txt"]
            if (spec.working_directory / "documents").is_dir():
                read_only_workspace_paths.append("documents")
            result = run_container_harness(
                ContainerHarnessSpec(
                    run_id=f"claude-{run_key}",
                    image=self.image_digest,
                    harness_argv=spec.argv[1:],
                    workspace=spec.working_directory,
                    log_root=log_root,
                    allow_hosts=(upstream_host,),
                    allow_ports=(upstream_port,),
                    # Claude requires an API-key-shaped value before it will
                    # send a request even when the endpoint is a local fixture.
                    # This public dummy is never used for published-api-key.
                    environment=environment,
                    cli_name="claude",
                    egress_network=self.fixture_egress_network,
                    model_gateway=model_gateway,
                    # The row workspace is owner-only on the host. Rootless
                    # Docker maps container UID 0 to that owner while caps and
                    # no-new-privileges remain active.
                    container_user="0:0",
                    read_only_workspace_paths=tuple(read_only_workspace_paths),
                    timeout_seconds=max(1, int(spec.timeout_seconds)),
                ),
                publication_directory=package_root,
                backend=self.backend,
            )
            raw_stdout = result.stdout_path.read_text(
                encoding="utf-8", errors="replace"
            )
            stderr = result.stderr_path.read_text(encoding="utf-8", errors="replace")
            stdout, envelope, trace_ok = normalize_claude_stream(
                raw_stdout,
                spec.working_directory,
            )
            terminal_ok = terminal_success(envelope)
            fence_ok = _fence_allows_forecast(result.fence)
            run_success = (
                result.exit_code == 0 and trace_ok and terminal_ok and fence_ok
            )
            status = (
                "timeout"
                if result.timed_out
                else ("succeeded" if run_success else "failed")
            )
            if result.exit_code == 0 and not run_success:
                stderr = (
                    f"{stderr}\n" if stderr else ""
                ) + "missing valid Claude terminal, Bash, or web-fence evidence"
            return ExecutionReceipt.from_transcript(
                spec,
                stdout=stdout,
                stderr=stderr,
                returncode=result.exit_code,
                status=status,
                served_model=served_model(envelope),
                usage=usage(envelope),
                cost_usd=cost(envelope),
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


def probe_native_claude_sandbox(
    image_digest: str,
    *,
    backend: str = "docker",
    timeout_seconds: int = 30,
) -> bool:
    """Probe the namespace half of Claude's required native sandbox."""

    try:
        require_digest_pinned_image(image_digest, "image_digest")
        backend_path, environment = resolve_rootless_backend(backend)
        resolve_local_image_id(backend_path, image_digest, environment)
        completed = subprocess.run(
            (
                str(backend_path),
                "run",
                "--rm",
                "--user",
                "0:0",
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


__all__ = [
    "NATIVE_SANDBOX_MODE",
    "OUTER_CONTAINER_ONLY_MODE",
    "ClaudeCodeContainerExecutionService",
    "ClaudeExecutionMode",
    "probe_native_claude_sandbox",
]

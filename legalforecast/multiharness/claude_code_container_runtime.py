"""Contained Claude Code execution and native-sandbox preflight."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
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
        if not self.sandbox_verified:
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
            if parsed.scheme != "https" or host is None:
                raise ValueError("fixture_base_url must be an HTTPS URL")
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
            # The local fixture uses an ephemeral self-signed certificate; this
            # branch never applies to a published provider profile.
            environment["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
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
                    allow_hosts=(host,),
                    allow_ports=(port,),
                    # Claude requires an API-key-shaped value before it will
                    # send a request even when the endpoint is a local fixture.
                    # This public dummy is never used for published-api-key.
                    environment=environment,
                    cli_name="claude",
                    egress_network=self.fixture_egress_network,
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
            run_success = result.exit_code == 0 and trace_ok and terminal_ok
            status = (
                "timeout"
                if result.timed_out
                else ("succeeded" if run_success else "failed")
            )
            if result.exit_code == 0 and not run_success:
                stderr = (
                    f"{stderr}\n" if stderr else ""
                ) + "missing valid Claude terminal or Bash tool evidence"
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
    "ClaudeCodeContainerExecutionService",
    "probe_native_claude_sandbox",
]

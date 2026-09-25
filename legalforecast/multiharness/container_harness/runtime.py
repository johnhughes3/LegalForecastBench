"""Execute one containerized agentic-CLI harness run behind the egress fence.

The topology, measured on rootless Docker rather than assumed:

* a per-run ``--internal`` Docker network, which has no external route at all --
  from a container on it, direct egress fails and external DNS returns NXDOMAIN;
* standard runs start an egress sidecar attached to that network *and* to an
  ordinary network, so it is the only path off the internal one. It runs
  :mod:`~legalforecast.multiharness.container_harness.egress_proxy` and refuses
  anything outside the run allowlist;
* outer fixture runs start the bounded model gateway on the internal network
  and attach only that gateway to the selected fixture network. The harness
  uses the gateway's fixed HTTP endpoint and receives no generic proxy route.

The standard proxy environment variables are therefore the convenience, not
the fence: even a harness that ignored them has nowhere to go. The gateway
mode has no proxy variables at all. See
:mod:`legalforecast.multiharness.container_harness` for what the fence cannot
reach, and :mod:`.plan` for the argv and environment this module executes.
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from legalforecast.multiharness.container_harness.evidence import (
    AccountedEgress,
    EgressEvidenceError,
    parse_egress_evidence,
)
from legalforecast.multiharness.container_harness.fence import fence_from_cli_output
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_CAPABILITY_TOKEN_ENV,
    MODEL_GATEWAY_UPSTREAM_KEY_ENV,
    MODEL_GATEWAY_USAGE_EVIDENCE_TARGET,
    ModelGatewayLaunch,
    build_model_gateway_run_argv,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    model_gateway_source_path as _model_gateway_source_path,
)
from legalforecast.multiharness.container_harness.model_gateway_runtime import (
    preserve_model_gateway_evidence as _preserve_model_gateway_evidence,
)
from legalforecast.multiharness.container_harness.model_gateway_runtime import (
    read_model_gateway_evidence as _read_model_gateway_evidence,
)
from legalforecast.multiharness.container_harness.model_gateway_runtime import (
    stage_model_gateway as _stage_model_gateway_impl,
)
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessNames,
    ContainerHarnessResult,
    ContainerHarnessSpec,
    build_egress_network_create_argv,
    build_harness_run_argv,
    build_model_gateway_network_connect_argv,
    build_network_connect_argv,
    build_network_create_argv,
    build_proxy_run_argv,
    build_run_names,
    egress_proxy_source_path,
    fenced_cli_name,
    stage_cli_fence,
    stage_credential_home,
    stage_outer_container_marker,
)
from legalforecast.multiharness.container_harness.publication import (
    write_published_package,
)

# Kept as a module attribute for callers that previously patched the staging
# source resolver on ``container_harness.runtime``.
model_gateway_source_path = _model_gateway_source_path

STAGING_ROOT_NAME = "legalforecast-multiharness"
PROXY_READY_TIMEOUT_SECONDS = 30.0
EVIDENCE_FILE_NAME = "egress-evidence.json"


def _stage_model_gateway(staging: Path, request: object) -> ModelGatewayLaunch:
    """Preserve the historical runtime-level source-resolver seam."""

    return _stage_model_gateway_impl(
        staging, request, source_resolver=model_gateway_source_path
    )


def run_container_harness(
    spec: ContainerHarnessSpec,
    *,
    publication_directory: Path,
    backend: str = "docker",
) -> ContainerHarnessResult:
    """Execute one fenced run and write its sole public result representation."""

    spec.allowlist()
    backend_path, environment = resolve_rootless_backend(backend)
    try:
        image_id = resolve_local_image_id(backend_path, spec.image, environment)
        proxy_image = spec.resolved_proxy_image()
        proxy_image_id = (
            image_id
            if proxy_image == spec.image
            else resolve_local_image_id(backend_path, proxy_image, environment)
        )
    except ContainerImageError as exc:
        raise ContainerHarnessError(str(exc)) from exc
    token = secrets.token_hex(8)
    names = build_run_names(spec.run_id, token)
    staging = _staging_directory(environment, token)
    spec.log_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    stdout_path = spec.log_root / f"{names.harness_container}.stdout"
    stderr_path = spec.log_root / f"{names.harness_container}.stderr"
    started = time.monotonic()
    # Staging holds the credential copies, so every path out of here -- including
    # a failure while staging them -- has to go through the cleanup that deletes
    # it; nothing that touches `staging` may sit outside this try.
    evidence_directory = staging / "egress"
    try:
        evidence_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        credential_home = stage_credential_home(staging, spec)
        fence_binary = stage_cli_fence(staging)
        outer_container_marker = (
            stage_outer_container_marker(staging)
            if spec.model_gateway is not None
            else None
        )
        _run_backend(build_network_create_argv(backend_path, names), environment)
        if spec.egress_network is None:
            _run_backend(
                build_egress_network_create_argv(backend_path, names), environment
            )
        if spec.model_gateway is None:
            _run_backend(
                build_proxy_run_argv(
                    backend_path,
                    spec,
                    names,
                    proxy_source=egress_proxy_source_path(),
                    evidence_directory=evidence_directory,
                ),
                environment,
            )
            _run_backend(
                build_network_connect_argv(backend_path, spec, names), environment
            )
        else:
            gateway_launch = _stage_model_gateway(
                staging,
                spec.model_gateway,
            )
            gateway_environment = dict(environment)
            gateway_environment.update(
                {
                    MODEL_GATEWAY_CAPABILITY_TOKEN_ENV: (
                        spec.model_gateway.run_capability
                    ),
                    MODEL_GATEWAY_UPSTREAM_KEY_ENV: spec.model_gateway.upstream_api_key
                    or "",
                }
            )
            _run_backend(
                build_model_gateway_run_argv(
                    backend_path,
                    spec,
                    names,
                    gateway_launch,
                    evidence_directory=evidence_directory,
                ),
                gateway_environment,
            )
            _run_backend(
                build_model_gateway_network_connect_argv(backend_path, spec, names),
                environment,
            )
        _await_sidecar_ready(backend_path, names, spec, environment)
        exit_code, timed_out = _run_harness(
            build_harness_run_argv(
                backend_path,
                spec,
                names,
                credential_home=credential_home,
                cidfile=staging / "harness.cid",
                fence_binary=fence_binary,
                outer_container_marker=outer_container_marker,
            ),
            environment,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout_seconds=spec.timeout_seconds,
        )
        # Force-remove the harness first: on the timeout path `subprocess.run`
        # only killed the `docker run` client, and a container still holding the
        # proxy open could keep making requests while we collect the evidence.
        _run_backend(
            (str(backend_path), "rm", "--force", names.harness_container),
            environment,
            check=False,
        )
        _run_backend(
            (str(backend_path), "stop", "--time", "5", names.proxy_container),
            environment,
            check=False,
        )
        gateway_usage: Mapping[str, object] | None = None
        if spec.model_gateway is None:
            evidence = _read_evidence(evidence_directory / EVIDENCE_FILE_NAME)
        else:
            evidence, gateway_usage = _read_model_gateway_evidence(
                evidence_directory / Path(MODEL_GATEWAY_USAGE_EVIDENCE_TARGET).name,
                spec,
            )
    finally:
        if spec.model_gateway is not None:
            _preserve_model_gateway_evidence(
                evidence_directory / Path(MODEL_GATEWAY_USAGE_EVIDENCE_TARGET).name,
                spec.log_root / f"{names.proxy_container}.gateway-usage.json",
            )
        _cleanup(backend_path, names, environment, staging)
    try:
        stdout = stdout_path.read_bytes()
    except OSError as exc:
        raise ContainerHarnessError(
            "harness stdout is unreadable; fence evidence cannot be derived"
        ) from exc
    fence = fence_from_cli_output(fenced_cli_name(spec), stdout)
    result = ContainerHarnessResult(
        run_id=spec.run_id,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=time.monotonic() - started,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        image_id=image_id,
        proxy_image_id=proxy_image_id,
        allowed_hosts=evidence.allowed_hosts,
        refused=evidence.refused,
        allowlist=spec.allowlist().to_record(),
        fence=fence,
        gateway_usage=gateway_usage,
    )
    write_published_package(
        publication_directory,
        result_record=result.to_record(),
        egress_evidence={
            "allowed_hosts": list(evidence.allowed_hosts),
            "refused": [dict(record) for record in evidence.refused],
            "decision_count": evidence.decision_count,
        },
        fence=fence,
        allowlist=spec.allowlist().to_record(),
    )
    return result


def _staging_directory(environment: Mapping[str, str], token: str) -> Path:
    runtime_directory = environment.get("XDG_RUNTIME_DIR")
    if not runtime_directory:
        raise ContainerHarnessError(
            "XDG_RUNTIME_DIR is required: the per-run credential copy lives on the "
            "operator's runtime tmpfs, never beside the real credential file"
        )
    staging = Path(runtime_directory) / STAGING_ROOT_NAME / token
    staging.mkdir(mode=0o700, parents=True, exist_ok=False)
    return staging


def _run_backend(
    argv: Sequence[str], environment: Mapping[str, str], *, check: bool = True
) -> None:
    try:
        completed = subprocess.run(
            tuple(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
            env=dict(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContainerHarnessError(f"container command failed: {argv[1:3]}") from exc
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()[:512]
        raise ContainerHarnessError(
            f"container command {list(argv[1:3])} failed: {detail}"
        )


def _await_sidecar_ready(
    backend_path: Path,
    names: ContainerHarnessNames,
    spec: ContainerHarnessSpec,
    environment: Mapping[str, str],
) -> None:
    """Wait until the selected sidecar accepts a local TCP connection."""

    deadline = time.monotonic() + PROXY_READY_TIMEOUT_SECONDS
    if spec.model_gateway is not None:
        probe = (
            str(backend_path),
            "exec",
            names.proxy_container,
            "python3",
            "-c",
            (
                "import socket; s=socket.create_connection("
                "('lfb-model-gateway', 8080), 1); s.close()"
            ),
        )
    else:
        probe = None
    while time.monotonic() < deadline:
        if probe is None:
            completed = subprocess.run(
                (str(backend_path), "logs", names.proxy_container),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
                env=dict(environment),
            )
            ready = (
                completed.returncode == 0
                and str(spec.proxy_port).encode("ascii") in completed.stdout
            )
        else:
            completed = subprocess.run(
                probe,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
                env=dict(environment),
            )
            ready = completed.returncode == 0
        if ready:
            return
        time.sleep(0.25)
    raise ContainerHarnessError(
        "egress sidecar did not report a bound port within "
        f"{PROXY_READY_TIMEOUT_SECONDS:.0f}s; the run was not started"
    )


def _run_harness(
    argv: Sequence[str],
    environment: Mapping[str, str],
    *,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> tuple[int | None, bool]:
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            completed = subprocess.run(
                tuple(argv),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout_seconds,
                check=False,
                env=dict(environment),
            )
        except subprocess.TimeoutExpired:
            return None, True
        except OSError as exc:
            raise ContainerHarnessError("harness container failed to start") from exc
    return completed.returncode, False


def _read_evidence(path: Path) -> AccountedEgress:
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContainerHarnessError(
            "egress evidence is missing or unreadable; a run whose egress cannot be "
            "accounted for is not a usable benchmark row"
        ) from exc
    try:
        return parse_egress_evidence(decoded)
    except EgressEvidenceError as exc:
        raise ContainerHarnessError(
            "egress evidence is missing or unreadable; a run whose egress cannot be "
            "accounted for is not a usable benchmark row"
        ) from exc


def _cleanup(
    backend_path: Path,
    names: ContainerHarnessNames,
    environment: Mapping[str, str],
    staging: Path,
) -> None:
    try:
        for argv in (
            (str(backend_path), "rm", "--force", names.harness_container),
            (str(backend_path), "rm", "--force", names.proxy_container),
            (str(backend_path), "network", "rm", names.network),
            (str(backend_path), "network", "rm", names.egress_network),
        ):
            try:
                _run_backend(argv, environment, check=False)
            except ContainerHarnessError:
                continue
    finally:
        shutil.rmtree(staging, ignore_errors=True)

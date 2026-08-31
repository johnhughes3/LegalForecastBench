"""Execute one containerized agentic-CLI harness run behind the egress fence.

The topology, measured on rootless Docker rather than assumed:

* a per-run ``--internal`` Docker network, which has no external route at all --
  from a container on it, direct egress fails and external DNS returns NXDOMAIN;
* an egress sidecar attached to that network *and* to an ordinary network, so it
  is the only path off the internal one.  It runs
  :mod:`~legalforecast.multiharness.container_harness.egress_proxy`, bind-mounted
  in as a single stdlib file, and refuses anything outside the run allowlist;
* the harness container, attached to the internal network only and pointed at
  the sidecar by ``HTTPS_PROXY``/``HTTP_PROXY``.

The proxy environment variables are therefore the convenience, not the fence:
even a harness that ignored them has nowhere to go.  See
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
from typing import Any, cast

from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessNames,
    ContainerHarnessResult,
    ContainerHarnessSpec,
    build_egress_network_create_argv,
    build_harness_run_argv,
    build_network_connect_argv,
    build_network_create_argv,
    build_proxy_run_argv,
    build_run_names,
    egress_proxy_source_path,
    stage_credential_home,
)

STAGING_ROOT_NAME = "legalforecast-multiharness"
PROXY_READY_TIMEOUT_SECONDS = 30.0
EVIDENCE_FILE_NAME = "egress-evidence.json"


def run_container_harness(
    spec: ContainerHarnessSpec, *, backend: str = "docker"
) -> ContainerHarnessResult:
    """Execute one harness run in a container fenced by the allowlist proxy."""

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
    try:
        evidence_directory = staging / "egress"
        evidence_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        credential_home = stage_credential_home(staging, spec)
        _run_backend(build_network_create_argv(backend_path, names), environment)
        if spec.egress_network is None:
            _run_backend(
                build_egress_network_create_argv(backend_path, names), environment
            )
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
        _run_backend(build_network_connect_argv(backend_path, spec, names), environment)
        _await_proxy_ready(backend_path, names, spec, environment)
        exit_code, timed_out = _run_harness(
            build_harness_run_argv(
                backend_path,
                spec,
                names,
                credential_home=credential_home,
                cidfile=staging / "harness.cid",
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
        evidence = _read_evidence(evidence_directory / EVIDENCE_FILE_NAME)
    finally:
        _cleanup(backend_path, names, environment, staging)
    return ContainerHarnessResult(
        run_id=spec.run_id,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=time.monotonic() - started,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        image_id=image_id,
        proxy_image_id=proxy_image_id,
        allowed_hosts=tuple(evidence.get("allowed_hosts", ())),
        refused=tuple(evidence.get("refused", ())),
        allowlist=spec.allowlist().to_record(),
    )


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


def _await_proxy_ready(
    backend_path: Path,
    names: ContainerHarnessNames,
    spec: ContainerHarnessSpec,
    environment: Mapping[str, str],
) -> None:
    """Wait until the sidecar has printed the port it bound."""

    deadline = time.monotonic() + PROXY_READY_TIMEOUT_SECONDS
    expected = str(spec.proxy_port).encode("ascii")
    while time.monotonic() < deadline:
        completed = subprocess.run(
            (str(backend_path), "logs", names.proxy_container),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
            env=dict(environment),
        )
        if completed.returncode == 0 and expected in completed.stdout:
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


def _read_evidence(path: Path) -> Mapping[str, Any]:
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContainerHarnessError(
            "egress evidence is missing or unreadable; a run whose egress cannot be "
            "accounted for is not a usable benchmark row"
        ) from exc
    if not isinstance(decoded, dict):
        raise ContainerHarnessError("egress evidence must be a JSON object")
    return cast(dict[str, Any], decoded)


def _cleanup(
    backend_path: Path,
    names: ContainerHarnessNames,
    environment: Mapping[str, str],
    staging: Path,
) -> None:
    for argv in (
        (str(backend_path), "rm", "--force", names.harness_container),
        (str(backend_path), "rm", "--force", names.proxy_container),
        (str(backend_path), "network", "rm", names.network),
        (str(backend_path), "network", "rm", names.egress_network),
    ):
        _run_backend(argv, environment, check=False)
    shutil.rmtree(staging, ignore_errors=True)

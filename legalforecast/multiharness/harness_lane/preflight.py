"""No-spend readiness probe for one containerized, tools-on harness run.

Four things go wrong between "the manifest validates" and "the run produced a
number", and all four are cheap to find before the first token is bought: the
contributor is not logged in, the pinned image is not on the host, the egress
sidecar cannot bind, or the selection resolved to nothing.  Every check here
answers one of those and costs no provider call.

The probe reports; the operator decides.  It is not a gate wired into a run
(there is no live run path yet) and it writes no state -- the report is a
single JSON file plus a non-zero exit code, and it is deleted along with the
run's output directory.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from legalforecast.contracts import MULTIHARNESS_HARNESS_PREFLIGHT_V1
from legalforecast.multiharness.auth_profiles import (
    CONTRIBUTOR_SUBSCRIPTION,
    AuthProfileError,
)
from legalforecast.multiharness.container_harness import (
    AllowlistConnectProxy,
    EgressAllowlist,
    EgressPolicyError,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.images import ContainerImageError
from legalforecast.multiharness.harness_lane.adapter import ContainerCliAdapter
from legalforecast.multiharness.harness_lane.auth import prove_local_login

ImageResolver = Callable[[str, str], str]
ProxyProbe = Callable[[EgressAllowlist], int]


@dataclass(frozen=True, slots=True)
class PreflightCheck:
    """One readiness answer: what was checked, whether it passed, and why."""

    name: str
    ok: bool
    detail: str

    def to_record(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """The probe's whole output: the run's declared shape plus its checks."""

    harness: str
    manifest_id: str
    capability_digest: str
    container_image_digest: str
    auth_profile: str
    backend: str
    egress_allowlist: dict[str, Any]
    task_count: int
    checks: tuple[PreflightCheck, ...]

    @property
    def ok(self) -> bool:
        """Return whether every check passed."""

        return all(check.ok for check in self.checks)

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": str(MULTIHARNESS_HARNESS_PREFLIGHT_V1),
            "command": "harness preflight",
            "ok": self.ok,
            "harness": self.harness,
            "manifest_id": self.manifest_id,
            "capability_digest": self.capability_digest,
            "container_image_digest": self.container_image_digest,
            "auth_profile": self.auth_profile,
            "container_backend": self.backend,
            "egress_allowlist": self.egress_allowlist,
            "task_count": self.task_count,
            "native_tools_enabled": True,
            "server_side_web_tools_disabled": True,
            "checks": [check.to_record() for check in self.checks],
        }


def default_image_resolver(backend: str, image: str) -> str:
    """Resolve the rootless backend and read back the pinned image's local ID."""

    backend_path, environment = resolve_rootless_backend(backend)
    return resolve_local_image_id(backend_path, image, environment)


def default_proxy_probe(allowlist: EgressAllowlist) -> int:
    """Start the allowlist sidecar on an ephemeral port and return that port."""

    with AllowlistConnectProxy(allowlist, bind_port=0) as proxy:
        return proxy.port


def run_preflight(
    adapter: ContainerCliAdapter,
    *,
    selected_task_ids: Sequence[str],
    image_resolver: ImageResolver = default_image_resolver,
    proxy_probe: ProxyProbe = default_proxy_probe,
) -> PreflightReport:
    """Probe one harness's readiness without spending anything."""

    manifest = adapter.local_manifest
    allowlist, allowlist_check = _allowlist_check(adapter)
    checks = (
        _login_check(adapter),
        _image_check(adapter, image_resolver),
        allowlist_check,
        _proxy_check(allowlist, proxy_probe),
        _selection_check(selected_task_ids),
    )
    return PreflightReport(
        harness=adapter.identity.registry_name,
        manifest_id=manifest.manifest_id,
        capability_digest=manifest.capability_digest,
        container_image_digest=adapter.image,
        auth_profile=adapter.auth_profile,
        backend=adapter.backend,
        egress_allowlist={} if allowlist is None else allowlist.to_record(),
        task_count=len(selected_task_ids),
        checks=checks,
    )


def _login_check(adapter: ContainerCliAdapter) -> PreflightCheck:
    name = "local_login"
    if adapter.auth_profile != CONTRIBUTOR_SUBSCRIPTION:
        return PreflightCheck(
            name=name,
            ok=True,
            detail=f"{adapter.auth_profile} needs no local harness login",
        )
    try:
        prove_local_login(adapter.identity, adapter.auth_profile, adapter.environment())
    except AuthProfileError as exc:
        return PreflightCheck(name=name, ok=False, detail=str(exc))
    return PreflightCheck(
        name=name,
        ok=True,
        detail=(
            f"{adapter.identity.executable_basename} login artifacts are present "
            "and owned by this user"
        ),
    )


def _image_check(
    adapter: ContainerCliAdapter, image_resolver: ImageResolver
) -> PreflightCheck:
    name = "container_image"
    try:
        image_id = image_resolver(adapter.backend, adapter.image)
    except ContainerImageError as exc:
        return PreflightCheck(name=name, ok=False, detail=str(exc))
    if image_id != adapter.image:
        return PreflightCheck(
            name=name,
            ok=False,
            detail=(
                f"the local image resolved to {image_id}, not the manifest's "
                f"pinned {adapter.image}"
            ),
        )
    return PreflightCheck(
        name=name,
        ok=True,
        detail=f"pinned image {image_id} is present under rootless {adapter.backend}",
    )


def _allowlist_check(
    adapter: ContainerCliAdapter,
) -> tuple[EgressAllowlist | None, PreflightCheck]:
    name = "egress_allowlist"
    try:
        allowlist = EgressAllowlist.from_rules(
            hosts=adapter.allow_hosts,
            subdomains=adapter.allow_subdomains,
            ports=adapter.allow_ports,
        )
    except EgressPolicyError as exc:
        return None, PreflightCheck(name=name, ok=False, detail=str(exc))
    hosts = len(allowlist.hosts) + len(allowlist.subdomain_suffixes)
    return allowlist, PreflightCheck(
        name=name,
        ok=True,
        detail=f"{hosts} host rule(s) on port(s) {sorted(allowlist.ports)}",
    )


def _proxy_check(
    allowlist: EgressAllowlist | None, proxy_probe: ProxyProbe
) -> PreflightCheck:
    name = "egress_proxy"
    if allowlist is None:
        return PreflightCheck(
            name=name, ok=False, detail="no allowlist to start the sidecar with"
        )
    try:
        port = proxy_probe(allowlist)
    except OSError as exc:
        return PreflightCheck(
            name=name, ok=False, detail=f"sidecar did not bind: {exc}"
        )
    return PreflightCheck(
        name=name, ok=True, detail=f"allowlist sidecar bound and released port {port}"
    )


def _selection_check(selected_task_ids: Sequence[str]) -> PreflightCheck:
    count = len(selected_task_ids)
    return PreflightCheck(
        name="task_selection",
        ok=count > 0,
        detail=f"{count} task(s) selected",
    )

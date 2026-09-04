"""Containerized agentic-CLI harness execution behind an allowlist egress fence.

The multiharness lane asks whether an agentic CLI beats the bare provider API on
the same task, so every harness runs with its own tools ON.  That makes network
posture the integrity question: the harness must reach its own model and nothing
else, because these are real federal cases whose outcomes are one web search
away.  :mod:`.egress_proxy` is the allowlist, :mod:`.plan` is the container topology as
pure data, :mod:`.runtime` executes it, and :mod:`.images` is the digest-pinned
image and rootless-backend preflight they depend on.

This package does not overload
:mod:`legalforecast.multiharness.container_runtime`, which is the official
network-disabled tool-protocol session.

The web/search fence is the image-baked wrapper in :mod:`.cli_fence`: it is
the only ``PATH`` name for the CLI, always injects the vendor disable flags,
and ignores agent-writable HOME config for tool enablement.  Credential files
are bind-mounted read-only; HOME is a writable tmpfs so OAuth refresh can
still land.  CONNECT authorization is bound to the TLS SNI and HTTP Host the
client actually uses.

What the fence does not reach: a provider-side web tool that ignores the
vendor disable flag.  That is a parser-observation problem
(legalforecastbench-2ve1.4).  Redacting denied hostnames in published
evidence is also 2ve1.4.
"""

from legalforecast.multiharness.container_harness.cli_fence import (
    FENCED_CLIS,
    CliFenceError,
    fenced_argv,
    install_cli_fence,
)
from legalforecast.multiharness.container_harness.egress_proxy import (
    AllowlistConnectProxy,
    EgressAllowlist,
    EgressDecision,
    EgressEvidence,
    EgressPolicyError,
    normalize_host,
)
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    require_digest_pinned_image,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessNames,
    ContainerHarnessResult,
    ContainerHarnessSpec,
    HarnessCredential,
    build_egress_network_create_argv,
    build_harness_environment,
    build_harness_run_argv,
    build_network_connect_argv,
    build_network_create_argv,
    build_proxy_run_argv,
    build_run_names,
    cli_fence_source_path,
    egress_network_name,
    egress_proxy_source_path,
    fenced_cli_name,
    stage_cli_fence,
    stage_credential_home,
)
from legalforecast.multiharness.container_harness.runtime import (
    run_container_harness,
)

__all__ = [
    "FENCED_CLIS",
    "AllowlistConnectProxy",
    "CliFenceError",
    "ContainerHarnessError",
    "ContainerHarnessNames",
    "ContainerHarnessResult",
    "ContainerHarnessSpec",
    "ContainerImageError",
    "EgressAllowlist",
    "EgressDecision",
    "EgressEvidence",
    "EgressPolicyError",
    "HarnessCredential",
    "build_egress_network_create_argv",
    "build_harness_environment",
    "build_harness_run_argv",
    "build_network_connect_argv",
    "build_network_create_argv",
    "build_proxy_run_argv",
    "build_run_names",
    "cli_fence_source_path",
    "egress_network_name",
    "egress_proxy_source_path",
    "fenced_argv",
    "fenced_cli_name",
    "install_cli_fence",
    "normalize_host",
    "require_digest_pinned_image",
    "resolve_local_image_id",
    "resolve_rootless_backend",
    "run_container_harness",
    "stage_cli_fence",
    "stage_credential_home",
]

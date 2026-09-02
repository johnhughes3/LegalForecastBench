"""Containerized agentic-CLI harness execution behind an allowlist egress fence.

The multiharness lane asks whether an agentic CLI beats the bare provider API on
the same task, so every harness runs with its own tools ON.  That makes network
posture the integrity question: the harness must reach its own model and nothing
else, because these are real federal cases whose outcomes are one web search
away.  :mod:`.egress_proxy` is the allowlist, :mod:`.plan` is the container topology as
pure data, :mod:`.runtime` executes it, and :mod:`.images` is the digest-pinned
image and rootless-backend preflight they depend on.

What the fence does not reach: a provider-side web tool.  A server-executed
``web_search``/``web_fetch`` runs on the provider's own infrastructure,
downstream of every egress rule here, so it must be disabled per harness by
flag.  ``ContainerHarnessSpec.harness_argv`` is passed through verbatim so the
manifest, not this package, states that it was.
"""

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
    egress_network_name,
    egress_proxy_source_path,
    stage_credential_home,
)
from legalforecast.multiharness.container_harness.runtime import (
    run_container_harness,
)

__all__ = [
    "AllowlistConnectProxy",
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
    "egress_network_name",
    "egress_proxy_source_path",
    "normalize_host",
    "require_digest_pinned_image",
    "resolve_local_image_id",
    "resolve_rootless_backend",
    "run_container_harness",
    "stage_credential_home",
]

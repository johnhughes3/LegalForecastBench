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

The standard mode uses the generic HTTPS egress sidecar.  The outer fixture
mode instead starts the bounded model gateway on the internal network and
connects only that sidecar to the selected fixture network; its upstream key
never enters the harness environment.

The web/search fence is the image-baked wrapper in :mod:`.cli_fence`: it is
the only ``PATH`` name for the CLI, always injects the vendor disable flags,
and ignores agent-writable HOME config for tool enablement.  Credential files
are bind-mounted read-only; HOME is a writable tmpfs so OAuth refresh can
still land.  CONNECT authorization is bound to the TLS SNI and HTTP Host the
client actually uses.

What the fence does not reach: a provider-side web tool that ignores the
vendor disable flag.  :mod:`.fence` derives web-disable flags from parser
observations, never from a hardcoded True.  :mod:`.publication` redacts
denied hostnames before a results package or community tree is written.
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
from legalforecast.multiharness.container_harness.evidence import (
    AccountedEgress,
    EgressEvidenceError,
    is_clean_egress,
    parse_egress_evidence,
)
from legalforecast.multiharness.container_harness.fence import (
    FenceEvidenceError,
    FenceObservation,
    ParserFenceFields,
    fence_from_cli_output,
    fence_from_parser_fields,
    require_honest_fence_record,
)
from legalforecast.multiharness.container_harness.images import (
    ContainerImageError,
    require_digest_pinned_image,
    resolve_local_image_id,
    resolve_rootless_backend,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_CAPABILITY_TOKEN_ENV,
    MODEL_GATEWAY_CONFIG_TARGET,
    MODEL_GATEWAY_ENV_TARGET,
    MODEL_GATEWAY_EVIDENCE_TARGET,
    MODEL_GATEWAY_HOST,
    MODEL_GATEWAY_MODULE,
    MODEL_GATEWAY_PACKAGE_ROOT_TARGET,
    MODEL_GATEWAY_PACKAGE_TARGET,
    MODEL_GATEWAY_PORT,
    MODEL_GATEWAY_READY_MARKER,
    MODEL_GATEWAY_RUN_CAPABILITY_ENV,
    MODEL_GATEWAY_SOURCE_TARGET,
    MODEL_GATEWAY_UPSTREAM_KEY_ENV,
    MODEL_GATEWAY_USAGE_EVIDENCE_TARGET,
    ModelGatewayLaunch,
    ModelGatewayPlanError,
    ModelGatewayRequest,
    build_model_gateway_run_argv,
    model_gateway_environment_names,
    model_gateway_source_path,
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
    build_model_gateway_network_connect_argv,
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
from legalforecast.multiharness.container_harness.publication import (
    PublicationError,
    denied_host_token,
    write_published_package,
)
from legalforecast.multiharness.container_harness.runtime import (
    run_container_harness,
)

__all__ = [
    "FENCED_CLIS",
    "MODEL_GATEWAY_CAPABILITY_TOKEN_ENV",
    "MODEL_GATEWAY_CONFIG_TARGET",
    "MODEL_GATEWAY_ENV_TARGET",
    "MODEL_GATEWAY_EVIDENCE_TARGET",
    "MODEL_GATEWAY_HOST",
    "MODEL_GATEWAY_MODULE",
    "MODEL_GATEWAY_PACKAGE_ROOT_TARGET",
    "MODEL_GATEWAY_PACKAGE_TARGET",
    "MODEL_GATEWAY_PORT",
    "MODEL_GATEWAY_READY_MARKER",
    "MODEL_GATEWAY_RUN_CAPABILITY_ENV",
    "MODEL_GATEWAY_SOURCE_TARGET",
    "MODEL_GATEWAY_UPSTREAM_KEY_ENV",
    "MODEL_GATEWAY_USAGE_EVIDENCE_TARGET",
    "AccountedEgress",
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
    "EgressEvidenceError",
    "EgressPolicyError",
    "FenceEvidenceError",
    "FenceObservation",
    "HarnessCredential",
    "ModelGatewayLaunch",
    "ModelGatewayPlanError",
    "ModelGatewayRequest",
    "ParserFenceFields",
    "PublicationError",
    "build_egress_network_create_argv",
    "build_harness_environment",
    "build_harness_run_argv",
    "build_model_gateway_network_connect_argv",
    "build_model_gateway_run_argv",
    "build_network_connect_argv",
    "build_network_create_argv",
    "build_proxy_run_argv",
    "build_run_names",
    "cli_fence_source_path",
    "denied_host_token",
    "egress_network_name",
    "egress_proxy_source_path",
    "fence_from_cli_output",
    "fence_from_parser_fields",
    "fenced_argv",
    "fenced_cli_name",
    "install_cli_fence",
    "is_clean_egress",
    "model_gateway_environment_names",
    "model_gateway_source_path",
    "normalize_host",
    "parse_egress_evidence",
    "require_digest_pinned_image",
    "require_honest_fence_record",
    "resolve_local_image_id",
    "resolve_rootless_backend",
    "run_container_harness",
    "stage_cli_fence",
    "stage_credential_home",
    "write_published_package",
]

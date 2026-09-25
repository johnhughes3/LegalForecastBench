"""Stage and account one bounded model-gateway sidecar.

The Docker lifecycle remains in :mod:`.runtime`; this module owns the gateway
policy files and their evidence contract so the general container runner stays
small and the gateway-specific validation has one seam.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from legalforecast.multiharness.container_harness.evidence import AccountedEgress
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_CAPABILITY_TOKEN_ENV,
    MODEL_GATEWAY_UPSTREAM_KEY_ENV,
    MODEL_GATEWAY_USAGE_EVIDENCE_TARGET,
    ModelGatewayLaunch,
    ModelGatewayPlanError,
    ModelGatewayRequest,
    model_gateway_source_path,
)
from legalforecast.multiharness.container_harness.plan import (
    ContainerHarnessError,
    ContainerHarnessSpec,
)


def stage_model_gateway(
    staging: Path,
    request: object,
    *,
    source_resolver: Callable[[], Path] = model_gateway_source_path,
) -> ModelGatewayLaunch:
    """Stage a gateway policy and sidecar-only env file without logging secrets."""

    if not isinstance(request, ModelGatewayRequest):
        raise ContainerHarnessError("model_gateway has an invalid request type")
    gateway_root = staging / "model-gateway"
    gateway_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    config_path = gateway_root / "policy.json"
    environment_path = gateway_root / "gateway.env"
    source_path = source_resolver()
    package_path = (
        gateway_root
        / "package"
        / "legalforecast"
        / "multiharness"
        / "container_harness"
    )
    package_path.mkdir(mode=0o700, parents=True, exist_ok=False)
    for relative in (
        "model_gateway.py",
        "model_gateway_accounting.py",
        "model_gateway_protocol.py",
        "model_gateway_server.py",
        "model_gateway_types.py",
    ):
        shutil.copyfile(source_path.parent / relative, package_path / relative)
    for init_path in (
        package_path.parent.parent / "__init__.py",
        package_path.parent / "__init__.py",
        package_path / "__init__.py",
    ):
        init_path.write_text("", encoding="utf-8")
    if request.upstream_api_key is None:
        raise ContainerHarnessError(
            "model gateway request must provide a sidecar-only upstream key"
        )
    config = {
        "bind_host": "0.0.0.0",
        "bind_port": request.port,
        "upstream_base_url": request.upstream_base_url,
        "allowed_models": [request.model_key.removeprefix("anthropic:")],
        "allowed_ingress_hosts": [request.host],
        "usage_evidence_path": MODEL_GATEWAY_USAGE_EVIDENCE_TARGET,
        "max_requests": 64,
        "max_input_tokens": 1_000_000,
        # Claude Code 2.1.282 sends max_tokens=128000 even for the fixture
        # turn; the gateway still accounts observed usage after forwarding.
        "max_output_tokens": 128_000,
        "max_total_input_tokens": 1_000_000,
        "max_total_output_tokens": 256_000,
    }
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    config_path.chmod(0o400)
    environment_lines = [
        f"{MODEL_GATEWAY_CAPABILITY_TOKEN_ENV}={request.run_capability}",
        f"{MODEL_GATEWAY_UPSTREAM_KEY_ENV}={request.upstream_api_key}",
    ]
    environment_path.write_text("\n".join(environment_lines) + "\n", encoding="utf-8")
    environment_path.chmod(0o600)
    try:
        return ModelGatewayLaunch(
            source_path=source_path,
            config_path=config_path,
            environment_path=environment_path,
            package_path=package_path,
            host=request.host,
            port=request.port,
        )
    except ModelGatewayPlanError as exc:
        raise ContainerHarnessError(str(exc)) from exc


def read_model_gateway_evidence(
    path: Path,
    spec: ContainerHarnessSpec,
) -> tuple[AccountedEgress, Mapping[str, object]]:
    """Translate bounded gateway usage into the publication egress contract."""

    if spec.model_gateway is None:
        raise ContainerHarnessError("gateway evidence requires model_gateway")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContainerHarnessError(
            "model gateway usage evidence is missing or unreadable"
        ) from exc
    if not isinstance(payload, dict):
        raise ContainerHarnessError("model gateway usage evidence is not an object")
    payload = cast(dict[str, object], payload)
    required = {
        "schema_version",
        "request_count",
        "rejected_count",
        "accounted_input_tokens",
        "accounted_output_tokens",
        "reserved_input_tokens",
        "reserved_output_tokens",
        "observed_input_tokens",
        "observed_output_tokens",
    }
    if set(payload) != required or payload.get("schema_version") != 1:
        raise ContainerHarnessError("model gateway usage evidence schema is invalid")
    integer_fields = (
        "request_count",
        "rejected_count",
        "accounted_input_tokens",
        "accounted_output_tokens",
        "reserved_input_tokens",
        "reserved_output_tokens",
    )
    for field in integer_fields:
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ContainerHarnessError(
                f"model gateway usage evidence field {field} is invalid"
            )
    request_count = payload["request_count"]
    if not isinstance(request_count, int) or isinstance(request_count, bool):
        raise ContainerHarnessError("model gateway request_count is invalid")
    if request_count <= 0:
        raise ContainerHarnessError("model gateway recorded no accepted model request")
    if payload["reserved_input_tokens"] or payload["reserved_output_tokens"]:
        raise ContainerHarnessError(
            "model gateway retained an unsettled usage reservation"
        )
    for field in ("observed_input_tokens", "observed_output_tokens"):
        value = payload[field]
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ContainerHarnessError(
                f"model gateway usage evidence field {field} is invalid"
            )
    upstream_host = urlsplit(spec.model_gateway.upstream_base_url).hostname
    if upstream_host is None or upstream_host not in spec.allowlist().hosts:
        raise ContainerHarnessError(
            "model gateway upstream is outside the declared egress allowlist"
        )
    return (
        AccountedEgress(
            allowed_hosts=(upstream_host,),
            refused=(),
            decision_count=request_count,
        ),
        dict(payload),
    )


def preserve_model_gateway_evidence(source: Path, destination: Path) -> None:
    """Keep a private usage copy before staging cleanup on success or failure."""

    if not source.is_file():
        return
    try:
        with source.open("rb") as input_file, destination.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file)
        destination.chmod(0o600)
    except OSError as exc:
        raise ContainerHarnessError(
            "model gateway usage evidence could not be preserved"
        ) from exc


__all__ = [
    "preserve_model_gateway_evidence",
    "read_model_gateway_evidence",
    "stage_model_gateway",
]

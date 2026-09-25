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
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    ProtectedPaidGatewayConfig,
    load_paid_gateway_config,
    worst_case_request_microusd,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_PROXY_BASE_URL,
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
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
)


def stage_model_gateway(
    staging: Path,
    request: object,
    *,
    source_resolver: Callable[[], Path] = model_gateway_source_path,
    environment: Mapping[str, str] | None = None,
) -> ModelGatewayLaunch:
    """Stage a gateway policy without writing sidecar credentials to disk."""

    if not isinstance(request, ModelGatewayRequest):
        raise ContainerHarnessError("model_gateway has an invalid request type")
    gateway_root = staging / "model-gateway"
    gateway_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    config_path = gateway_root / "policy.json"
    if request.paid_config_path is None and request.upstream_api_key is None:
        raise ContainerHarnessError(
            "model gateway request must provide a sidecar-only upstream key"
        )
    wire_model = request.model_key.removeprefix("anthropic:")
    source_path: Path | None = None
    package_path: Path | None = None
    paid_config_path: Path | None = None
    model_registry_path: Path | None = None
    if request.paid_config_path is not None:
        assert request.model_registry_path is not None
        try:
            paid_config = load_paid_gateway_config(
                request.paid_config_path,
                model_registry_path=request.model_registry_path,
                environment=environment,
            )
        except ProtectedTerminalPaidError as exc:
            raise ContainerHarnessError(str(exc)) from exc
        _validate_paid_budget(paid_config)
        paid_config_path = gateway_root / "paid-gateway.json"
        model_registry_path = gateway_root / "model-registry.json"
        shutil.copyfile(request.paid_config_path, paid_config_path)
        shutil.copyfile(request.model_registry_path, model_registry_path)
        paid_config_path.chmod(0o444)
        model_registry_path.chmod(0o444)
        max_requests = paid_config.max_requests
        max_input_tokens = paid_config.registry_entry.context_limit
        max_output_tokens = paid_config.registry_entry.max_output_tokens
    else:
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
        max_requests = 64
        max_input_tokens = 1_000_000
        max_output_tokens = 128_000
    config = {
        "bind_host": "0.0.0.0",
        "bind_port": request.port,
        "upstream_base_url": request.upstream_base_url,
        # Claude Code may append its context-window tier to the wire model
        # (for example ``claude-opus-5-5[1m]``). Both values resolve to this
        # one requested model; no arbitrary model name is admitted.
        "allowed_models": [wire_model, f"{wire_model}[1m]"],
        "allowed_ingress_hosts": [request.host],
        # The gateway has no external interface.  Its fixed upstream request
        # must traverse the allowlisted CONNECT relay on the internal network.
        "proxy_base_url": MODEL_GATEWAY_PROXY_BASE_URL,
        "usage_evidence_path": MODEL_GATEWAY_USAGE_EVIDENCE_TARGET,
        "max_requests": max_requests,
        "max_input_tokens": max_input_tokens,
        # Claude Code 2.1.282 sends max_tokens=128000 even for the fixture
        # turn; the gateway still accounts observed usage after forwarding.
        "max_output_tokens": max_output_tokens,
        "max_total_input_tokens": max_requests * max_input_tokens,
        "max_total_output_tokens": max_requests * max_output_tokens,
    }
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    config_path.chmod(0o400)
    try:
        return ModelGatewayLaunch(
            source_path=source_path,
            config_path=config_path,
            package_path=package_path,
            paid_config_path=paid_config_path,
            model_registry_path=model_registry_path,
            host=request.host,
            port=request.port,
        )
    except ModelGatewayPlanError as exc:
        raise ContainerHarnessError(str(exc)) from exc


def _validate_paid_budget(config: ProtectedPaidGatewayConfig) -> None:
    """Prove the frozen request envelope fits the approved run ceiling."""

    # Keep this check independent of the controller constructor: staging must
    # reject an unbounded paid launch before Docker can start the sidecar.
    ceiling = config.spend.ceiling_microusd
    try:
        worst_case_microusd = worst_case_request_microusd(config.registry_entry)
    except ProtectedTerminalPaidError as exc:
        raise ContainerHarnessError(str(exc)) from exc
    if worst_case_microusd > ceiling:
        raise ContainerHarnessError(
            "paid gateway worst-case request cost exceeds the approved ceiling"
        )


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

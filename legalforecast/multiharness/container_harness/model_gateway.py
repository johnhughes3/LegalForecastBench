"""Sidecar entrypoint and public API for the bounded Anthropic gateway.

The sidecar reads public policy from an owner-only JSON file and receives the
provider key and per-run capability from sidecar-only environment variables.
It exposes the protocol gateway on an internal per-run network and writes
owner-only usage evidence to the configured path after every accounting event.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from .model_gateway_accounting import GatewayUsage
    from .model_gateway_protocol import (
        AnthropicModelGateway,
        GatewaySpendController,
        ModelGatewayPolicy,
    )
    from .model_gateway_server import ModelGatewayHTTPServer, build_model_gateway_server
    from .model_gateway_types import (
        GatewayAuthenticationError,
        GatewayBudgetExceeded,
        GatewayEvidenceError,
        GatewayResponse,
        GatewayUpstreamError,
        GatewayUsageSnapshot,
        ModelGatewayError,
        ObservedUsage,
        Reservation,
    )
elif __package__ in (None, ""):
    import sys
    from types import ModuleType

    _standalone_package_name = "_lfb_model_gateway"
    _standalone_package = ModuleType(_standalone_package_name)
    _standalone_package.__path__ = [str(Path(__file__).resolve().parent)]  # type: ignore[attr-defined]
    sys.modules.setdefault(_standalone_package_name, _standalone_package)
    from _lfb_model_gateway.model_gateway_accounting import (  # pyright: ignore[reportMissingImports]
        GatewayUsage,
    )
    from _lfb_model_gateway.model_gateway_protocol import (  # pyright: ignore[reportMissingImports]
        AnthropicModelGateway,
        GatewaySpendController,
        ModelGatewayPolicy,
    )
    from _lfb_model_gateway.model_gateway_server import (  # pyright: ignore[reportMissingImports]
        ModelGatewayHTTPServer,
        build_model_gateway_server,
    )
    from _lfb_model_gateway.model_gateway_types import (  # pyright: ignore[reportMissingImports]
        GatewayAuthenticationError,
        GatewayBudgetExceeded,
        GatewayEvidenceError,
        GatewayResponse,
        GatewayUpstreamError,
        GatewayUsageSnapshot,
        ModelGatewayError,
        ObservedUsage,
        Reservation,
    )
else:
    from .model_gateway_accounting import GatewayUsage
    from .model_gateway_protocol import (
        AnthropicModelGateway,
        GatewaySpendController,
        ModelGatewayPolicy,
    )
    from .model_gateway_server import (
        ModelGatewayHTTPServer,
        build_model_gateway_server,
    )
    from .model_gateway_types import (
        GatewayAuthenticationError,
        GatewayBudgetExceeded,
        GatewayEvidenceError,
        GatewayResponse,
        GatewayUpstreamError,
        GatewayUsageSnapshot,
        ModelGatewayError,
        ObservedUsage,
        Reservation,
    )

UPSTREAM_API_KEY_ENV: Final[str] = "LFB_MODEL_GATEWAY_UPSTREAM_API_KEY"
UPSTREAM_KEY_FILE_ENV: Final[str] = "LFB_MODEL_GATEWAY_UPSTREAM_KEY_FILE"
CAPABILITY_TOKEN_ENV: Final[str] = "LFB_MODEL_GATEWAY_CAPABILITY_TOKEN"
PAID_CONFIG_PATH_ENV: Final[str] = "LFB_MODEL_GATEWAY_PAID_CONFIG_PATH"
MODEL_REGISTRY_PATH_ENV: Final[str] = "LFB_MODEL_GATEWAY_MODEL_REGISTRY_PATH"
_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "bind_host",
        "bind_port",
        "upstream_base_url",
        "proxy_base_url",
        "allowed_models",
        "allowed_ingress_hosts",
        "max_request_bytes",
        "max_response_bytes",
        "max_requests",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_input_tokens",
        "max_total_output_tokens",
        "upstream_timeout_seconds",
        "usage_evidence_path",
    }
)


@dataclass(frozen=True, slots=True)
class ModelGatewayLaunchConfig:
    """Resolved sidecar configuration with secrets supplied out of band."""

    policy: ModelGatewayPolicy
    bind_host: str
    bind_port: int
    usage_evidence_path: Path
    spend_controller: GatewaySpendController | None = None
    request_id: str | None = None


def load_model_gateway_launch_config(
    config_path: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> ModelGatewayLaunchConfig:
    """Load public policy from an owner-only file and secrets from sidecar env.

    The JSON file intentionally has no credential fields. The upstream key is
    accepted only from one of the sidecar-only environment variables, and the
    per-run capability is accepted only from ``CAPABILITY_TOKEN_ENV``. Neither
    value is a command-line argument or a harness-controlled field.
    """

    _require_owner_only_file(config_path, "gateway policy")
    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ModelGatewayError("gateway policy is not valid JSON") from exc
    if not isinstance(raw_config, dict):
        raise ModelGatewayError("gateway policy must be a JSON object")
    config = cast(dict[str, object], raw_config)
    if "upstream_api_key" in config or "capability_token" in config:
        raise ModelGatewayError("gateway policy must not contain credentials")
    unknown_keys = set(config) - _POLICY_KEYS
    if unknown_keys:
        raise ModelGatewayError("gateway policy contains unknown fields")

    env = os.environ if environment is None else environment
    upstream_api_key = _load_upstream_api_key(env)
    capability_token = env.get(CAPABILITY_TOKEN_ENV)
    if not capability_token:
        raise ModelGatewayError(
            f"{CAPABILITY_TOKEN_ENV} must be set for the gateway sidecar"
        )

    policy_values: dict[str, Any] = {
        "upstream_base_url": _config_string(config, "upstream_base_url"),
        "upstream_api_key": upstream_api_key,
        "capability_token": capability_token,
        "allowed_models": frozenset(_config_string_list(config, "allowed_models")),
        "allowed_ingress_hosts": frozenset(
            _config_string_list(config, "allowed_ingress_hosts")
        ),
    }
    if "proxy_base_url" in config:
        policy_values["proxy_base_url"] = _config_string(config, "proxy_base_url")
    for name in (
        "max_request_bytes",
        "max_response_bytes",
        "max_requests",
        "max_input_tokens",
        "max_output_tokens",
        "max_total_input_tokens",
        "max_total_output_tokens",
    ):
        if name in config:
            policy_values[name] = _config_positive_int(config, name)
    if "upstream_timeout_seconds" in config:
        timeout = config["upstream_timeout_seconds"]
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ModelGatewayError(
                "gateway policy upstream_timeout_seconds must be positive"
            )
        policy_values["upstream_timeout_seconds"] = float(timeout)

    policy = ModelGatewayPolicy(**policy_values)
    bind_host = _config_string(config, "bind_host")
    bind_port = _config_positive_int(config, "bind_port")
    if bind_port > 65_535:
        raise ModelGatewayError("gateway policy bind_port is out of range")
    usage_evidence_path = _config_absolute_path(config, "usage_evidence_path")
    spend_controller: GatewaySpendController | None = None
    request_id: str | None = None
    paid_config_path = env.get(PAID_CONFIG_PATH_ENV)
    model_registry_path = env.get(MODEL_REGISTRY_PATH_ENV)
    if bool(paid_config_path) != bool(model_registry_path):
        raise ModelGatewayError(
            f"set both {PAID_CONFIG_PATH_ENV} and {MODEL_REGISTRY_PATH_ENV} "
            "for protected paid gateway mode"
        )
    if paid_config_path is not None and model_registry_path is not None:
        if (
            not Path(paid_config_path).is_absolute()
            or not Path(model_registry_path).is_absolute()
        ):
            raise ModelGatewayError("paid gateway config paths must be absolute")
        try:
            # Keep paid imports lazy: the provider-free fixture image contains
            # only the staged gateway package, while the paid image carries the
            # complete installed package and its protected spend primitives.
            from .model_gateway_paid import (  # type: ignore[import-not-found]
                build_paid_gateway_controller,
                load_paid_gateway_config,
            )
        except ImportError as exc:
            raise ModelGatewayError(
                "protected paid gateway support is unavailable in this image"
            ) from exc
        try:
            paid_config = load_paid_gateway_config(
                paid_config_path,
                model_registry_path=model_registry_path,
                environment=env,
            )
            wire_model = paid_config.model_key.removeprefix("anthropic:")
            expected_models = frozenset({wire_model, f"{wire_model}[1m]"})
            if policy.allowed_models != expected_models:
                raise ModelGatewayError(
                    "paid gateway policy model does not match the frozen registry"
                )
            if (
                policy.max_requests != paid_config.max_requests
                or policy.max_input_tokens != paid_config.registry_entry.context_limit
                or policy.max_output_tokens
                != paid_config.registry_entry.max_output_tokens
                or policy.max_total_input_tokens
                != paid_config.max_requests * paid_config.registry_entry.context_limit
                or policy.max_total_output_tokens
                != paid_config.max_requests
                * paid_config.registry_entry.max_output_tokens
            ):
                raise ModelGatewayError(
                    "paid gateway policy limits do not match the frozen registry"
                )
            spend_controller = build_paid_gateway_controller(paid_config)
        except Exception as exc:
            # The paid loader and authority constructor deliberately expose a
            # single protected error type. Avoid leaking paths or provider
            # details from the sidecar's command-line error.
            if isinstance(exc, ModelGatewayError):
                raise
            raise ModelGatewayError(f"protected paid gateway refused: {exc}") from exc
        request_id = f"paid-gateway:{paid_config.spend.reservation_ledger_sha256}"
    return ModelGatewayLaunchConfig(
        policy,
        bind_host,
        bind_port,
        usage_evidence_path,
        spend_controller,
        request_id,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the sidecar from an owner-only policy mount.

    Example deployment command::

        python -m legalforecast.multiharness.container_harness.model_gateway \
          --config /run/legalforecast/model-gateway/policy.json

    Credentials are absent from the command line. The sidecar environment
    supplies them through the ``*_ENV`` variables above.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="owner-only JSON policy file; it contains no credentials",
    )
    args = parser.parse_args(argv)
    try:
        launch = load_model_gateway_launch_config(args.config)
        server = build_model_gateway_server(
            launch.policy,
            bind_host=launch.bind_host,
            port=launch.bind_port,
            usage_evidence_path=launch.usage_evidence_path,
            spend_controller=launch.spend_controller,
            request_id=launch.request_id,
        )
    except (OSError, ModelGatewayError, GatewayEvidenceError) as exc:
        parser.error(f"invalid gateway configuration: {exc}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _load_upstream_api_key(environment: Mapping[str, str]) -> str:
    env_key = environment.get(UPSTREAM_API_KEY_ENV)
    key_file_name = environment.get(UPSTREAM_KEY_FILE_ENV)
    if bool(env_key) == bool(key_file_name):
        raise ModelGatewayError(
            "set exactly one sidecar upstream-key source: "
            f"{UPSTREAM_API_KEY_ENV} or {UPSTREAM_KEY_FILE_ENV}"
        )
    if env_key is not None:
        return env_key
    assert key_file_name is not None
    key_file = Path(key_file_name)
    _require_owner_only_file(key_file, "upstream key")
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise ModelGatewayError("upstream key file cannot be read") from exc
    if not key:
        raise ModelGatewayError("upstream key file is empty")
    return key


def _require_owner_only_file(path: Path, description: str) -> None:
    if path.is_symlink():
        raise ModelGatewayError(f"{description} file must not be a symlink")
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise ModelGatewayError(f"{description} file cannot be inspected") from exc
    if not path.is_file():
        raise ModelGatewayError(f"{description} file is not a regular file")
    if mode & 0o077:
        raise ModelGatewayError(f"{description} file must be owner-only")


def _config_string(config: Mapping[str, object], name: str) -> str:
    value = config.get(name)
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string")
    return value


def _config_string_list(config: Mapping[str, object], name: str) -> list[str]:
    value = config.get(name)
    if not isinstance(value, list):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string list")
    items = cast(list[object], value)
    if not items or any(
        not isinstance(item, str)
        or not item
        or any(character.isspace() for character in item)
        for item in items
    ):
        raise ModelGatewayError(f"gateway policy {name} must be a nonempty string list")
    return cast(list[str], value)


def _config_positive_int(config: Mapping[str, object], name: str) -> int:
    value = config.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelGatewayError(f"gateway policy {name} must be a positive integer")
    return value


def _config_absolute_path(config: Mapping[str, object], name: str) -> Path:
    value = config.get(name)
    if not isinstance(value, str) or not value:
        raise ModelGatewayError(f"gateway policy {name} must be an absolute path")
    path = Path(value)
    if not path.is_absolute():
        raise ModelGatewayError(f"gateway policy {name} must be an absolute path")
    return path


__all__ = [
    "CAPABILITY_TOKEN_ENV",
    "MODEL_REGISTRY_PATH_ENV",
    "PAID_CONFIG_PATH_ENV",
    "UPSTREAM_API_KEY_ENV",
    "UPSTREAM_KEY_FILE_ENV",
    "AnthropicModelGateway",
    "GatewayAuthenticationError",
    "GatewayBudgetExceeded",
    "GatewayEvidenceError",
    "GatewayResponse",
    "GatewaySpendController",
    "GatewayUpstreamError",
    "GatewayUsage",
    "GatewayUsageSnapshot",
    "ModelGatewayError",
    "ModelGatewayHTTPServer",
    "ModelGatewayLaunchConfig",
    "ModelGatewayPolicy",
    "ObservedUsage",
    "Reservation",
    "build_model_gateway_server",
    "load_model_gateway_launch_config",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())

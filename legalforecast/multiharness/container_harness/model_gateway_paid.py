"""Fail-closed construction of the protected paid model gateway.

The outer harness loads this small read-only JSON descriptor before starting a
paid gateway.  The descriptor binds the protected workflow marker, the frozen
Anthropic registry bytes and entry, and the existing DynamoDB authority
identity.  It contains no provider credential.  Construction delegates spend
accounting to :mod:`protected_terminal_paid`; this module only derives the
uniform request hold and selects the registry-aware charge extractor.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry,
    model_registry_entry_sha256,
)
from legalforecast.multiharness.protected_terminal_paid import (
    PROTECTED_WORKFLOW_MARKER,
    PROTECTED_WORKFLOW_MARKER_VALUE,
    ProtectedTerminalPaidError,
    ProtectedTerminalSpendConfig,
    ProviderGatewaySpendController,
    anthropic_registry_charge_extractor,
    build_protected_gateway_spend_controller,
    protected_authority_environment,
    uniform_case_reservation_microusd,
)

PAID_GATEWAY_CONFIG_SCHEMA: Final[int] = 1
PAID_GATEWAY_WORKFLOW_MARKER: Final[str] = (
    f"{PROTECTED_WORKFLOW_MARKER}={PROTECTED_WORKFLOW_MARKER_VALUE}"
)

_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "workflow_marker",
        "cycle_id",
        "account",
        "model_key",
        "ceiling_microusd",
        "max_requests",
        "authority_identity_sha256",
        "reservation_ledger_sha256",
        "provider_authority_table",
        "provider_authority_region",
        "provider_authority_resource_identity_sha256",
        "model_registry_sha256",
        "model_registry_entry_sha256",
    }
)
_OPTIONAL_FIELDS: Final[frozenset[str]] = frozenset(
    {"stage", "ablation", "repeat_index"}
)


@dataclass(frozen=True, slots=True)
class ProtectedPaidGatewayConfig:
    """Validated paid gateway inputs and its frozen pricing entry."""

    spend: ProtectedTerminalSpendConfig
    model_registry_sha256: str
    model_registry_entry_sha256: str
    registry_entry: ModelRegistryEntry
    max_requests: int
    reservation_microusd: int

    @property
    def model_key(self) -> str:
        """Return the frozen provider/model key used by the gateway."""

        return self.spend.model_key


def load_paid_gateway_config(
    config_path: str | Path,
    *,
    model_registry_path: str | Path,
    environment: Mapping[str, str] | None = None,
) -> ProtectedPaidGatewayConfig:
    """Load and validate a protected paid gateway descriptor.

    ``config_path`` and ``model_registry_path`` are caller-owned read-only
    inputs.  The loader performs no AWS or provider operation.  ``environment``
    is injectable only for tests; production callers leave it unset so the
    existing protected workflow environment is checked directly.
    """

    payload = _read_object(Path(config_path), "paid gateway config")
    _require_exact_fields(payload, _REQUIRED_FIELDS, _OPTIONAL_FIELDS)
    if _required_int(payload, "schema_version") != PAID_GATEWAY_CONFIG_SCHEMA:
        raise ProtectedTerminalPaidError(
            f"unsupported paid gateway config schema; expected "
            f"{PAID_GATEWAY_CONFIG_SCHEMA}"
        )
    if _required_str(payload, "workflow_marker") != PAID_GATEWAY_WORKFLOW_MARKER:
        raise ProtectedTerminalPaidError(
            "paid gateway config does not carry the official workflow marker"
        )

    authority_table, authority_region, authority_resource = (
        protected_authority_environment(environment)
    )
    config = ProtectedTerminalSpendConfig(
        cycle_id=_required_str(payload, "cycle_id"),
        account=_required_str(payload, "account"),
        model_key=_required_str(payload, "model_key"),
        ceiling_microusd=_required_int(payload, "ceiling_microusd"),
        authority_identity_sha256=_required_str(payload, "authority_identity_sha256"),
        reservation_ledger_sha256=_required_str(payload, "reservation_ledger_sha256"),
        provider_authority_table=_required_str(payload, "provider_authority_table"),
        provider_authority_region=_required_str(payload, "provider_authority_region"),
        provider_authority_resource_identity_sha256=_required_str(
            payload, "provider_authority_resource_identity_sha256"
        ),
        stage=_optional_str(payload, "stage", default="official"),
        ablation=_optional_str(payload, "ablation", default="none"),
        repeat_index=_optional_int(payload, "repeat_index", default=1),
    )
    if (
        config.provider_authority_table,
        config.provider_authority_region,
        config.provider_authority_resource_identity_sha256,
    ) != (authority_table, authority_region, authority_resource):
        raise ProtectedTerminalPaidError(
            "paid gateway config does not match the protected authority identity"
        )

    max_requests = _required_int(payload, "max_requests")
    registry_sha256 = _required_sha256(payload, "model_registry_sha256")
    entry_sha256 = _required_sha256(payload, "model_registry_entry_sha256")
    registry = load_model_registry(model_registry_path)
    if registry.source_sha256 != registry_sha256:
        raise ProtectedTerminalPaidError(
            "paid gateway model registry differs from its frozen SHA-256"
        )
    provider, model_id = _split_model_key(config.model_key)
    try:
        entry = registry.get(provider, model_id)
    except KeyError as exc:
        raise ProtectedTerminalPaidError(
            f"paid gateway model key is absent from the frozen registry: "
            f"{config.model_key}"
        ) from exc
    if model_registry_entry_sha256(entry) != entry_sha256:
        raise ProtectedTerminalPaidError(
            "paid gateway model registry entry differs from its frozen SHA-256"
        )
    if not entry.network_disabled or not entry.search_disabled:
        raise ProtectedTerminalPaidError(
            "paid gateway registry entry must disable network and search"
        )

    reservation = uniform_case_reservation_microusd(
        config.ceiling_microusd,
        max_requests,
    )
    return ProtectedPaidGatewayConfig(
        spend=config,
        model_registry_sha256=registry_sha256,
        model_registry_entry_sha256=entry_sha256,
        registry_entry=entry,
        max_requests=max_requests,
        reservation_microusd=reservation,
    )


def build_paid_gateway_controller(
    config: ProtectedPaidGatewayConfig,
) -> ProviderGatewaySpendController:
    """Construct the existing protected controller with frozen pricing."""

    return build_protected_gateway_spend_controller(
        config.spend,
        reservation_microusd=config.reservation_microusd,
        charge_extractor=anthropic_registry_charge_extractor(config.registry_entry),
    )


def _read_object(path: Path, description: str) -> Mapping[str, Any]:
    if not path.is_file():
        raise ProtectedTerminalPaidError(f"{description} must be a regular file")
    try:
        value: object = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtectedTerminalPaidError(f"{description} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ProtectedTerminalPaidError(f"{description} must contain a JSON object")
    return cast(Mapping[str, Any], value)


def _require_exact_fields(
    payload: Mapping[str, Any],
    required: frozenset[str],
    optional: frozenset[str],
) -> None:
    fields = frozenset(payload)
    missing = required - fields
    unknown = fields - required - optional
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if unknown:
            details.append(f"unknown={sorted(unknown)}")
        raise ProtectedTerminalPaidError(
            "paid gateway config fields are invalid: " + ", ".join(details)
        )


def _required_str(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ProtectedTerminalPaidError(f"paid gateway config {name} must be nonempty")
    return value


def _required_int(payload: Mapping[str, Any], name: str) -> int:
    value = payload.get(name)
    if type(value) is not int or value <= 0:
        raise ProtectedTerminalPaidError(
            f"paid gateway config {name} must be a positive integer"
        )
    return value


def _optional_str(payload: Mapping[str, Any], name: str, *, default: str) -> str:
    if name not in payload:
        return default
    return _required_str(payload, name)


def _optional_int(payload: Mapping[str, Any], name: str, *, default: int) -> int:
    if name not in payload:
        return default
    return _required_int(payload, name)


def _required_sha256(payload: Mapping[str, Any], name: str) -> str:
    value = _required_str(payload, name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ProtectedTerminalPaidError(
            f"paid gateway config {name} must be a lowercase SHA-256"
        )
    return value


def _split_model_key(model_key: str) -> tuple[str, str]:
    provider, separator, model_id = model_key.partition(":")
    if not separator or not provider.strip() or not model_id.strip():
        raise ProtectedTerminalPaidError(
            "paid gateway model_key must be provider:model_id"
        )
    return provider, model_id


__all__ = [
    "PAID_GATEWAY_CONFIG_SCHEMA",
    "PAID_GATEWAY_WORKFLOW_MARKER",
    "ProtectedPaidGatewayConfig",
    "build_paid_gateway_controller",
    "load_paid_gateway_config",
]

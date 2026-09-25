"""Protected paid gateway config loading without provider or AWS calls."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import legalforecast.multiharness.container_harness.model_gateway_paid as paid
import pytest
from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_entry_sha256,
)
from legalforecast.multiharness.protected_terminal_paid import (
    GatewayChargeExtractor,
    ProtectedTerminalPaidError,
    ProtectedTerminalSpendConfig,
    ProviderGatewaySpendController,
)

_ENVIRONMENT = {
    "GITHUB_ACTIONS": "true",
    "LFB_PROTECTED_TERMINAL_RELEASE": "1",
    "LFB_PROVIDER_AUTHORITY_TABLE": "provider-spend",
    "LFB_AWS_REGION": "us-east-1",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256": "c" * 64,
}


def _registry_record() -> dict[str, object]:
    return {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-5",
        "display_name": "Claude Sonnet",
        "model_version_or_snapshot": "claude-sonnet-4-5",
        "provider_training_cutoff_status": "unknown",
        "max_output_tokens": 128_000,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 1_000_000,
        "pricing_source": "fixture-pricing",
        "input_token_price": 5.0,
        "output_token_price": 25.0,
        "cache_read_token_price": 0.5,
        "cache_write_token_price": 6.25,
        "known_cutoff_publicity_caveats": [],
    }


def _files(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    registry_payload = (
        json.dumps([_registry_record()], sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    registry_path = tmp_path / "model-registry.json"
    registry_path.write_bytes(registry_payload)
    registry = load_model_registry_bytes(registry_payload)
    entry = registry.entries[0]
    config_record: dict[str, Any] = {
        "schema_version": paid.PAID_GATEWAY_CONFIG_SCHEMA,
        "workflow_marker": paid.PAID_GATEWAY_WORKFLOW_MARKER,
        "cycle_id": "cycle-1",
        "account": "official",
        "model_key": entry.registry_key,
        "ceiling_microusd": 101,
        "max_requests": 4,
        "authority_identity_sha256": "a" * 64,
        "reservation_ledger_sha256": "b" * 64,
        "provider_authority_table": "provider-spend",
        "provider_authority_region": "us-east-1",
        "provider_authority_resource_identity_sha256": "c" * 64,
        "model_registry_sha256": registry.source_sha256,
        "model_registry_entry_sha256": model_registry_entry_sha256(entry),
    }
    config_path = tmp_path / "paid-gateway.json"
    config_path.write_text(json.dumps(config_record), encoding="utf-8")
    return config_path, registry_path, config_record


def test_load_paid_gateway_config_binds_frozen_inputs_and_reservation(
    tmp_path: Path,
) -> None:
    config_path, registry_path, _ = _files(tmp_path)

    config = paid.load_paid_gateway_config(
        config_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )

    assert config.model_key == "anthropic:claude-sonnet-4-5"
    assert config.max_requests == 4
    assert config.reservation_microusd == 25
    assert config.registry_entry.registry_key == config.model_key


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("workflow_marker", "LFB_PROTECTED_TERMINAL_RELEASE=0", "workflow marker"),
        ("model_registry_sha256", "d" * 64, "registry differs"),
        (
            "provider_authority_resource_identity_sha256",
            "d" * 64,
            "authority identity",
        ),
    ],
)
def test_load_paid_gateway_config_rejects_changed_frozen_identity(
    tmp_path: Path,
    field: str,
    value: str,
    match: str,
) -> None:
    config_path, registry_path, record = _files(tmp_path)
    record[field] = value
    config_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ProtectedTerminalPaidError, match=match):
        paid.load_paid_gateway_config(
            config_path,
            model_registry_path=registry_path,
            environment=_ENVIRONMENT,
        )


def test_load_paid_gateway_config_rejects_request_budget_not_coverable(
    tmp_path: Path,
) -> None:
    config_path, registry_path, record = _files(tmp_path)
    record["max_requests"] = 102
    config_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ProtectedTerminalPaidError, match="at least one"):
        paid.load_paid_gateway_config(
            config_path,
            model_registry_path=registry_path,
            environment=_ENVIRONMENT,
        )


def test_build_paid_gateway_controller_uses_cache_aware_registry_pricing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, registry_path, _ = _files(tmp_path)
    config = paid.load_paid_gateway_config(
        config_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_builder(
        spend: ProtectedTerminalSpendConfig,
        *,
        reservation_microusd: int,
        charge_extractor: GatewayChargeExtractor,
    ) -> ProviderGatewaySpendController:
        captured["spend"] = spend
        captured["reservation"] = reservation_microusd
        captured["extractor"] = charge_extractor
        return cast(ProviderGatewaySpendController, sentinel)

    monkeypatch.setattr(paid, "build_protected_gateway_spend_controller", fake_builder)

    controller = paid.build_paid_gateway_controller(config)

    assert controller is sentinel
    assert captured["spend"] is config.spend
    assert captured["reservation"] == 25
    extractor = cast(
        Callable[[bytes, int, str | None], int | None], captured["extractor"]
    )
    body = json.dumps(
        {
            "usage": {
                "input_tokens": 1_000,
                "output_tokens": 100,
                "cache_read_input_tokens": 500,
                "cache_creation_input_tokens": 100,
            }
        },
        separators=(",", ":"),
    ).encode()
    assert extractor(body, 200, "application/json") == 5_375

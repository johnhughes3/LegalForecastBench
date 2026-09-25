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
from legalforecast.multiharness.container_harness.model_gateway import (
    CAPABILITY_TOKEN_ENV,
    MODEL_REGISTRY_PATH_ENV,
    PAID_CONFIG_PATH_ENV,
    REQUEST_ID_ENV,
    UPSTREAM_API_KEY_ENV,
    load_model_gateway_launch_config,
)
from legalforecast.multiharness.container_harness.model_gateway_plan import (
    MODEL_GATEWAY_AUTHORITY_ENV,
    MODEL_GATEWAY_MODEL_REGISTRY_TARGET,
    MODEL_GATEWAY_PACKAGE_ROOT_TARGET,
    MODEL_GATEWAY_PAID_CONFIG_TARGET,
    MODEL_GATEWAY_RELAY_ENV,
    MODEL_GATEWAY_SOURCE_TARGET,
    ModelGatewayRequest,
    build_model_gateway_run_argv,
)
from legalforecast.multiharness.container_harness.model_gateway_runtime import (
    stage_model_gateway,
)
from legalforecast.multiharness.container_harness.model_gateway_types import (
    ModelGatewayError,
)
from legalforecast.multiharness.container_harness.plan import ContainerHarnessNames
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
        "ceiling_microusd": 10_000_000,
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
    assert config.reservation_microusd == 9_450_000
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
    record["ceiling_microusd"] = 9_449_999
    config_path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ProtectedTerminalPaidError, match="worst-case request cost"):
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
    assert captured["reservation"] == 9_450_000
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


def test_paid_gateway_stages_installed_image_inputs_without_fixture_pythonpath(
    tmp_path: Path,
) -> None:
    config_path, registry_path, record = _files(tmp_path)
    record["ceiling_microusd"] = 40_000_000
    config_path.write_text(json.dumps(record), encoding="utf-8")
    request = ModelGatewayRequest(
        upstream_base_url="https://api.anthropic.com:443",
        model_key="anthropic:claude-sonnet-4-5",
        run_capability="run-capability",
        paid_config_path=config_path,
        model_registry_path=registry_path,
        request_id="case-" + "d" * 64,
    )
    launch = stage_model_gateway(
        tmp_path / "staging",
        request,
        environment=_ENVIRONMENT,
    )

    assert launch.source_path is None
    assert launch.package_path is None
    assert launch.paid_config_path is not None
    assert launch.model_registry_path is not None
    names = ContainerHarnessNames(
        network="run-net",
        egress_network="run-out",
        proxy_container="run-relay",
        model_gateway_container="run-gateway",
        harness_container="run-harness",
    )

    class Spec:
        def resolved_proxy_image(self) -> str:
            return "lfb-paid-gateway@sha256:" + "a" * 64

    argv = build_model_gateway_run_argv(
        Path("/usr/bin/docker"),
        Spec(),
        names,
        launch,
        evidence_directory=tmp_path / "evidence",
    )
    env_values = [argv[index + 1] for index, item in enumerate(argv) if item == "--env"]
    assert f"{PAID_CONFIG_PATH_ENV}={MODEL_GATEWAY_PAID_CONFIG_TARGET}" in env_values
    assert (
        f"{MODEL_REGISTRY_PATH_ENV}={MODEL_GATEWAY_MODEL_REGISTRY_TARGET}" in env_values
    )
    assert f"PYTHONPATH={MODEL_GATEWAY_PACKAGE_ROOT_TARGET}" not in env_values
    assert MODEL_GATEWAY_SOURCE_TARGET not in argv
    assert MODEL_GATEWAY_AUTHORITY_ENV[0] in env_values
    assert MODEL_GATEWAY_RELAY_ENV[1] in env_values
    assert "fixture-upstream-dummy-key" not in argv
    assert "run-capability" not in argv


def test_paid_gateway_loader_constructs_controller_before_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path, registry_path, record = _files(tmp_path)
    record["ceiling_microusd"] = 40_000_000
    config_path.write_text(json.dumps(record), encoding="utf-8")
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "bind_host": "0.0.0.0",
                "bind_port": 8080,
                "upstream_base_url": "https://api.anthropic.com:443",
                "proxy_base_url": "http://lfb-model-egress:3128",
                "allowed_models": ["claude-sonnet-4-5", "claude-sonnet-4-5[1m]"],
                "allowed_ingress_hosts": ["lfb-model-gateway"],
                "usage_evidence_path": "/var/legalforecast-egress/gateway-usage.json",
                "max_requests": 4,
                "max_input_tokens": 1_000_000,
                "max_output_tokens": 128_000,
                "max_total_input_tokens": 4_000_000,
                "max_total_output_tokens": 512_000,
            }
        ),
        encoding="utf-8",
    )
    policy_path.chmod(0o400)
    sentinel = object()
    monkeypatch.setattr(
        "legalforecast.multiharness.container_harness.model_gateway_paid.build_paid_gateway_controller",
        lambda config: cast(Any, sentinel),
    )
    environment = {
        **_ENVIRONMENT,
        CAPABILITY_TOKEN_ENV: "run-capability",
        UPSTREAM_API_KEY_ENV: "fixture-upstream-dummy-key",
        PAID_CONFIG_PATH_ENV: str(config_path),
        MODEL_REGISTRY_PATH_ENV: str(registry_path),
        REQUEST_ID_ENV: "case-" + "d" * 64,
    }

    loaded = load_model_gateway_launch_config(policy_path, environment=environment)

    assert loaded.spend_controller is sentinel
    assert loaded.request_id == "paid-gateway:" + "b" * 64 + ":case-" + "d" * 64
    missing_request_id = dict(environment)
    missing_request_id.pop(REQUEST_ID_ENV)
    monkeypatch.setattr(
        "legalforecast.multiharness.container_harness.model_gateway_paid.build_paid_gateway_controller",
        lambda _config: pytest.fail("controller must not build without case identity"),
    )
    with pytest.raises(ModelGatewayError, match=REQUEST_ID_ENV):
        load_model_gateway_launch_config(policy_path, environment=missing_request_id)


class _RecordingSpendAuthority:
    def __init__(self) -> None:
        self.keys: list[object] = []

    def authorize_attempt(self, key: object, *, reservation_microusd: int) -> object:
        del reservation_microusd
        self.keys.append(key)
        return object()


def test_fresh_paid_sidecars_bind_gateway_keys_to_outer_case_identity(
    tmp_path: Path,
) -> None:
    config_path, registry_path, record = _files(tmp_path)
    record["ceiling_microusd"] = 40_000_000
    config_path.write_text(json.dumps(record), encoding="utf-8")
    config = paid.load_paid_gateway_config(
        config_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )
    authorities = (_RecordingSpendAuthority(), _RecordingSpendAuthority())
    controllers = tuple(
        ProviderGatewaySpendController(
            authority=cast(Any, authority),
            config=config.spend,
            reservation_microusd=config.reservation_microusd,
            charge_extractor=lambda _body, _status, _content_type: 0,
        )
        for authority in authorities
    )

    controllers[0].authorize_request(
        request_id="case-alpha",
        body=b"{}",
        model="claude-sonnet-4-5",
        max_tokens=1,
    )
    controllers[1].authorize_request(
        request_id="case-beta",
        body=b"{}",
        model="claude-sonnet-4-5",
        max_tokens=1,
    )
    retry_authority = _RecordingSpendAuthority()
    retry_controller = ProviderGatewaySpendController(
        authority=cast(Any, retry_authority),
        config=config.spend,
        reservation_microusd=config.reservation_microusd,
        charge_extractor=lambda _body, _status, _content_type: 0,
    )
    retry_controller.authorize_request(
        request_id="case-alpha",
        body=b"{}",
        model="claude-sonnet-4-5",
        max_tokens=1,
    )

    assert authorities[0].keys[0] != authorities[1].keys[0]
    assert authorities[0].keys[0] == retry_authority.keys[0]

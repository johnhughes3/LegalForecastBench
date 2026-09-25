"""Provider-free issuance tests for the protected terminal descriptor."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from legalforecast.immutable_io import ImmutableIOError
from legalforecast.multiharness.container_harness.model_gateway_paid import (
    load_paid_gateway_config,
)
from legalforecast.multiharness.paid_gateway_descriptor import (
    PAID_GATEWAY_MAX_REQUESTS_PER_CASE,
    issue_paid_gateway_descriptor,
    write_paid_gateway_descriptor,
)
from legalforecast.multiharness.protected_terminal_paid import (
    ProtectedTerminalPaidError,
)
from legalforecast.release.run_manifest import (
    BenchmarkRunManifest,
    DocumentRole,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    SelectedCase,
    serialize_run_manifest,
)
from legalforecast.release.synthetic import issue_synthetic_release

_ENVIRONMENT = {
    "GITHUB_ACTIONS": "true",
    "LFB_PROTECTED_TERMINAL_RELEASE": "1",
    "LFB_PROVIDER_AUTHORITY_TABLE": "provider-spend",
    "LFB_AWS_REGION": "us-east-1",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256": "c" * 64,
}
_CEILING_MICROUSD = 300_000_000


def _registry_bytes() -> bytes:
    return (
        json.dumps(
            [
                {
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
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    manifest_path = release_root / "run-manifest.json"
    # The fixture release binds this exact canonical manifest commitment but
    # does not publish the manifest because ordinary fixture scoring does not
    # consume it.
    manifest_path.write_bytes(
        serialize_run_manifest(
            BenchmarkRunManifest(
                run_id=UUID("12345678-1234-5678-1234-567812345678"),
                selected_cases=tuple(
                    SelectedCase(
                        case_id=f"case-{index:03d}",
                        provider_id="corpus-store",
                        qc_status=QCStatus.ACCEPTED,
                        role_locators=tuple(
                            RoleObjectLocator(
                                role=role,
                                locator=OpaqueObjectLocator(
                                    provider_id="object-store",
                                    object_locator=f"cases/case-{index:03d}/{role.value}",
                                    version_id=f"version-case-{index:03d}-{role.value}",
                                ),
                            )
                            for role in (
                                DocumentRole.DECISION,
                                DocumentRole.MOTION,
                                DocumentRole.COMPLAINT,
                            )
                        ),
                        opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
                    )
                    for index in range(1, 4)
                ),
                policy_version="federal-mtd-v1",
                code_revision="a" * 40,
                created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
                locked_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
            )
        )
    )
    registry_path = tmp_path / "model-registry.json"
    registry_path.write_bytes(_registry_bytes())
    return (
        release_root / "run-manifest.json",
        release_root / "forecast-release.json",
        release_root,
        registry_path,
    )


def test_descriptor_is_derived_from_locked_inputs_and_loads_as_paid_config(
    tmp_path: Path,
) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)

    descriptor = issue_paid_gateway_descriptor(
        manifest_path=manifest_path,
        forecast_path=forecast_path,
        artifact_root=artifact_root,
        model_registry_path=registry_path,
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    output_path = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(output_path, descriptor)
    loaded = load_paid_gateway_config(
        output_path,
        model_registry_path=registry_path,
        environment=_ENVIRONMENT,
    )

    assert descriptor.cycle_id == "synthetic-three-case-v1"
    assert descriptor.max_requests == PAID_GATEWAY_MAX_REQUESTS_PER_CASE
    assert re.fullmatch(r"[0-9a-f]{64}", descriptor.reservation_ledger_sha256)
    assert loaded.model_key == "anthropic:claude-sonnet-4-5"
    assert loaded.max_requests == PAID_GATEWAY_MAX_REQUESTS_PER_CASE
    assert output_path.stat().st_mode & 0o777 == 0o400
    record = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(record, dict)
    assert "approval_reference" not in record
    assert "ANTHROPIC_API_KEY" not in output_path.read_text(encoding="utf-8")


def test_descriptor_binds_registry_bytes_for_later_loader_rechecks(
    tmp_path: Path,
) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)
    descriptor = issue_paid_gateway_descriptor(
        manifest_path=manifest_path,
        forecast_path=forecast_path,
        artifact_root=artifact_root,
        model_registry_path=registry_path,
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    output_path = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(output_path, descriptor)
    changed_registry_path = tmp_path / "changed-model-registry.json"
    changed_registry_path.write_bytes(
        _registry_bytes().replace(b"Claude Sonnet", b"Claude Changed")
    )

    with pytest.raises(ProtectedTerminalPaidError, match="differs from its frozen"):
        load_paid_gateway_config(
            output_path,
            model_registry_path=changed_registry_path,
            environment=_ENVIRONMENT,
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        (
            "LFB_PROTECTED_TERMINAL_RELEASE",
            "0",
            "official workflow marker",
        ),
        (
            "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
            "",
            "authority configuration",
        ),
    ],
)
def test_descriptor_requires_protected_workflow_authority(
    tmp_path: Path,
    field: str,
    value: str,
    match: str,
) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)
    environment = {**_ENVIRONMENT, field: value}

    with pytest.raises(ProtectedTerminalPaidError, match=match):
        issue_paid_gateway_descriptor(
            manifest_path=manifest_path,
            forecast_path=forecast_path,
            artifact_root=artifact_root,
            model_registry_path=registry_path,
            model_key="anthropic:claude-sonnet-4-5",
            ceiling_microusd=_CEILING_MICROUSD,
            account="official",
            environment=environment,
        )


def test_descriptor_rejects_registry_model_not_in_locked_registry(
    tmp_path: Path,
) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)

    with pytest.raises(ProtectedTerminalPaidError, match="absent"):
        issue_paid_gateway_descriptor(
            manifest_path=manifest_path,
            forecast_path=forecast_path,
            artifact_root=artifact_root,
            model_registry_path=registry_path,
            model_key="anthropic:claude-opus-5-5",
            ceiling_microusd=_CEILING_MICROUSD,
            account="official",
            environment=_ENVIRONMENT,
        )


def test_descriptor_refuses_release_wide_worst_case_over_ceiling(
    tmp_path: Path,
) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)

    with pytest.raises(ProtectedTerminalPaidError, match="worst-case release cost"):
        issue_paid_gateway_descriptor(
            manifest_path=manifest_path,
            forecast_path=forecast_path,
            artifact_root=artifact_root,
            model_registry_path=registry_path,
            model_key="anthropic:claude-sonnet-4-5",
            ceiling_microusd=226_800_000 - 1,
            account="official",
            environment=_ENVIRONMENT,
        )


def test_descriptor_output_is_create_only(tmp_path: Path) -> None:
    manifest_path, forecast_path, artifact_root, registry_path = _inputs(tmp_path)
    descriptor = issue_paid_gateway_descriptor(
        manifest_path=manifest_path,
        forecast_path=forecast_path,
        artifact_root=artifact_root,
        model_registry_path=registry_path,
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=_CEILING_MICROUSD,
        account="official",
        environment=_ENVIRONMENT,
    )
    output_path = tmp_path / "paid-gateway.json"
    write_paid_gateway_descriptor(output_path, descriptor)

    with pytest.raises(ImmutableIOError, match="already exists"):
        write_paid_gateway_descriptor(output_path, descriptor)

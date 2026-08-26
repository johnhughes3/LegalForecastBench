from __future__ import annotations

# pyright: reportPrivateUsage=false
import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.labeling.provider_cycle_caps_materializer import (
    ProviderCycleCapsMaterializationError,
    _materialize_provider_cycle_caps_successor,
    _ProviderCycleCapsSuccessorPolicy,
    _VerifiedAuthoritySmoke,
    canonical_successor_receipt_bytes,
    load_provider_cycle_caps_successor_policy,
)
from legalforecast.labeling.provider_journal import load_provider_cycle_caps_bytes

ROOT = Path(__file__).resolve().parents[1]
FORECAST_LEGACY_CAPS = (
    ROOT / "model_registries/cycle-1-forecast-provider-caps-base-2026-08-25.json"
)
FORECAST_SUCCESSOR_POLICY = (
    ROOT
    / "model_registries/cycle-1-forecast-provider-caps-successor-policy-2026-08-25.json"
)

ProviderCycleCapsSuccessorPolicy = _ProviderCycleCapsSuccessorPolicy
VerifiedAuthoritySmoke = _VerifiedAuthoritySmoke
materialize_provider_cycle_caps_successor = _materialize_provider_cycle_caps_successor


def _legacy_caps_bytes() -> bytes:
    return (
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "cycle-1",
                "providers": [
                    {
                        "provider": "openai",
                        "cycle_reservation_cap_usd": "50.00",
                    },
                    {
                        "provider": "anthropic",
                        "cycle_reservation_cap_usd": "100.00",
                    },
                    {
                        "provider": "google",
                        "cycle_reservation_cap_usd": "50.00",
                    },
                ],
            },
            indent=2,
        )
        + "\n"
    ).encode()


def _accounts() -> dict[str, str]:
    return {
        "anthropic": "cycle1-anthropic",
        "google": "cycle1-google",
        "openai": "cycle1-openai",
    }


def _verified_smoke(
    *, resource_identity_sha256: str = "a" * 64
) -> VerifiedAuthoritySmoke:
    return VerifiedAuthoritySmoke(
        byte_count=321,
        sha256="d" * 64,
        release_sha="e" * 40,
        resource_identity_sha256=resource_identity_sha256,
    )


def _policy(
    *,
    accounts: dict[str, str] | None = None,
    max_billable_attempts: int = 2,
    failure_threshold: int = 3,
    failure_window_seconds: int = 300,
) -> ProviderCycleCapsSuccessorPolicy:
    return ProviderCycleCapsSuccessorPolicy(
        byte_count=456,
        sha256="f" * 64,
        cycle_id="cycle-1",
        provider_accounts=accounts or _accounts(),
        max_billable_attempts=max_billable_attempts,
        failure_threshold=failure_threshold,
        failure_window_seconds=failure_window_seconds,
    )


@pytest.mark.parametrize("nonfinite_value", [float("nan"), float("inf")])
def test_policy_loader_rejects_nonfinite_values_with_domain_error(
    nonfinite_value: float,
) -> None:
    record = {
        "schema_version": "legalforecast.provider_cycle_caps_successor_policy.v1",
        "cycle_id": "cycle-1",
        "provider_accounts": [
            {"provider": provider, "account": account}
            for provider, account in _accounts().items()
        ],
        "spend_authority": {
            "backend": "dynamodb",
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "max_billable_attempts": 2,
            "failure_threshold": nonfinite_value,
            "failure_window_seconds": 300,
        },
    }
    payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()

    with pytest.raises(
        ProviderCycleCapsMaterializationError,
        match="must use canonical JSON bytes",
    ):
        load_provider_cycle_caps_successor_policy(
            payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )


def test_materializer_builds_deterministic_authority_enabled_successor() -> None:
    source = _legacy_caps_bytes()

    materialized = materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=hashlib.sha256(source).hexdigest(),
        authority_smoke=_verified_smoke(),
        policy=_policy(),
    )

    caps = load_provider_cycle_caps_bytes(
        materialized.caps_bytes,
        source="materialized successor",
    )
    assert caps.cycle_id == "cycle-1"
    assert caps.require_spend_authority().resource_identity_sha256 == "a" * 64
    assert caps.account("anthropic") == "cycle1-anthropic"
    assert caps.account("google") == "cycle1-google"
    assert caps.account("openai") == "cycle1-openai"
    assert caps.cap_usd("anthropic") == 100.0
    assert caps.cap_usd("google") == 50.0
    assert caps.cap_usd("openai") == 50.0

    successor = json.loads(materialized.caps_bytes)
    assert successor["providers"] == [
        {
            "account": "cycle1-anthropic",
            "cycle_reservation_cap_usd": "100.00",
            "provider": "anthropic",
        },
        {
            "account": "cycle1-google",
            "cycle_reservation_cap_usd": "50.00",
            "provider": "google",
        },
        {
            "account": "cycle1-openai",
            "cycle_reservation_cap_usd": "50.00",
            "provider": "openai",
        },
    ]
    assert (
        materialized.caps_sha256 == hashlib.sha256(materialized.caps_bytes).hexdigest()
    )
    assert materialized.receipt == {
        "schema_version": "legalforecast.provider_cycle_caps_successor_receipt.v1",
        "status": "complete",
        "cycle_id": "cycle-1",
        "source": {
            "bytes": len(source),
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "sha256": hashlib.sha256(source).hexdigest(),
        },
        "authority_smoke": {
            "bytes": 321,
            "release_sha": "e" * 40,
            "schema_version": "legalforecast.official_labeling_authority_smoke.v1",
            "sha256": "d" * 64,
        },
        "policy": {
            "bytes": 456,
            "schema_version": ("legalforecast.provider_cycle_caps_successor_policy.v1"),
            "sha256": "f" * 64,
        },
        "successor": {
            "bytes": len(materialized.caps_bytes),
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "sha256": materialized.caps_sha256,
        },
        "spend_authority": {
            "backend": "dynamodb",
            "failure_threshold": 3,
            "failure_window_seconds": 300,
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "max_billable_attempts": 2,
            "resource_identity_sha256": "a" * 64,
        },
        "provider_account_caps": successor["providers"],
    }
    receipt_bytes = canonical_successor_receipt_bytes(materialized.receipt)
    assert json.loads(receipt_bytes) == materialized.receipt
    assert b"arn:" not in materialized.caps_bytes + receipt_bytes
    assert b"123456789012" not in materialized.caps_bytes + receipt_bytes
    assert b"external_spend" not in materialized.caps_bytes + receipt_bytes


def test_materializer_accepts_forecast_only_successor_registry_provider_set() -> None:
    source = FORECAST_LEGACY_CAPS.read_bytes()
    policy_bytes = FORECAST_SUCCESSOR_POLICY.read_bytes()
    policy = load_provider_cycle_caps_successor_policy(
        policy_bytes,
        expected_sha256=hashlib.sha256(policy_bytes).hexdigest(),
    )

    materialized = materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=hashlib.sha256(source).hexdigest(),
        authority_smoke=_verified_smoke(),
        policy=policy,
    )

    caps = load_provider_cycle_caps_bytes(
        materialized.caps_bytes,
        source="forecast-only successor",
    )
    assert caps.cycle_id == "cycle-1"
    assert set(caps.providers) == {"anthropic", "openai"}
    assert caps.account("anthropic") == "cycle1-anthropic"
    assert caps.account("openai") == "cycle1-openai"
    assert caps.cap_microusd("anthropic") == 668_700_000
    assert caps.cap_microusd("openai") == 1_374_960_000
    assert sum(caps.cap_microusd(provider) for provider in caps.providers) == (
        2_043_660_000
    )
    authority = caps.require_spend_authority()
    assert authority.backend == "dynamodb"
    assert authority.ledger_scope_fields == ("cycle_id", "provider", "account")
    assert authority.max_billable_attempts == 2
    assert authority.failure_threshold == 3
    assert authority.failure_window_seconds == 300


def test_materializer_is_order_independent() -> None:
    source = _legacy_caps_bytes()
    expected = hashlib.sha256(source).hexdigest()
    accounts = _accounts()

    forward = materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=expected,
        authority_smoke=_verified_smoke(resource_identity_sha256="b" * 64),
        policy=_policy(accounts=accounts),
    )
    reverse = materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=expected,
        authority_smoke=_verified_smoke(resource_identity_sha256="b" * 64),
        policy=_policy(accounts=dict(reversed(tuple(accounts.items())))),
    )

    assert forward == reverse


@pytest.mark.parametrize(
    ("expected_source_sha256", "message"),
    [
        ("c" * 64, "source SHA-256 differs"),
        ("not-a-digest", "expected source SHA-256"),
    ],
)
def test_materializer_rejects_unbound_source_bytes(
    expected_source_sha256: str,
    message: str,
) -> None:
    with pytest.raises(ProviderCycleCapsMaterializationError, match=message):
        materialize_provider_cycle_caps_successor(
            _legacy_caps_bytes(),
            expected_source_sha256=expected_source_sha256,
            authority_smoke=_verified_smoke(),
            policy=_policy(),
        )


@pytest.mark.parametrize(
    ("accounts", "message"),
    [
        (
            {"anthropic": "cycle1-anthropic", "google": "cycle1-google"},
            "provider account aliases differ",
        ),
        (
            {
                **_accounts(),
                "cohere": "cycle1-cohere",
            },
            "provider account aliases differ",
        ),
        (
            {
                **_accounts(),
                "openai": "123456789012",
            },
            "public account alias",
        ),
    ],
)
def test_materializer_requires_exact_public_alias_map(
    accounts: dict[str, str],
    message: str,
) -> None:
    source = _legacy_caps_bytes()

    with pytest.raises(ProviderCycleCapsMaterializationError, match=message):
        materialize_provider_cycle_caps_successor(
            source,
            expected_source_sha256=hashlib.sha256(source).hexdigest(),
            authority_smoke=_verified_smoke(),
            policy=_policy(accounts=accounts),
        )


def test_materializer_rejects_already_authorized_or_annotated_source() -> None:
    source = json.loads(_legacy_caps_bytes())
    source["providers"][0]["external_spend_limit_usd"] = "215.00"
    payload = (json.dumps(source) + "\n").encode()

    with pytest.raises(
        ProviderCycleCapsMaterializationError,
        match="legacy caps source must omit authority, accounts, and annotations",
    ):
        materialize_provider_cycle_caps_successor(
            payload,
            expected_source_sha256=hashlib.sha256(payload).hexdigest(),
            authority_smoke=_verified_smoke(),
            policy=_policy(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_billable_attempts", 0),
        ("failure_threshold", 0),
        ("failure_window_seconds", 0),
    ],
)
def test_materializer_rejects_nonpositive_authority_policy(
    field: str,
    value: int,
) -> None:
    source = _legacy_caps_bytes()
    with pytest.raises(ProviderCycleCapsMaterializationError, match=field):
        materialize_provider_cycle_caps_successor(
            source,
            expected_source_sha256=hashlib.sha256(source).hexdigest(),
            authority_smoke=_verified_smoke(),
            policy=_policy(
                max_billable_attempts=(
                    value if field == "max_billable_attempts" else 2
                ),
                failure_threshold=value if field == "failure_threshold" else 3,
                failure_window_seconds=(
                    value if field == "failure_window_seconds" else 300
                ),
            ),
        )


def test_materializer_does_not_read_or_write_files(tmp_path: Path) -> None:
    source = _legacy_caps_bytes()
    marker = tmp_path / "unchanged"
    marker.write_text("before", encoding="utf-8")

    materialize_provider_cycle_caps_successor(
        source,
        expected_source_sha256=hashlib.sha256(source).hexdigest(),
        authority_smoke=_verified_smoke(),
        policy=_policy(),
    )

    assert marker.read_text(encoding="utf-8") == "before"
    assert tuple(tmp_path.iterdir()) == (marker,)

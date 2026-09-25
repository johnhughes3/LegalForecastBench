from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import legalforecast.multiharness.protected_terminal_paid as protected_terminal_paid
import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_control import AttemptLease, ProviderSpendKey
from legalforecast.multiharness.auth_profiles import (
    PUBLISHED_API_KEY,
    AuthProfileError,
    ResolvedAuthProfile,
)
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.protected_terminal_paid import (
    GitHubEnvironmentCredentialSource,
    GitHubEnvironmentGatewayCredentialSource,
    ProtectedSpendController,
    ProtectedTerminalPaidError,
    ProtectedTerminalSpendConfig,
    ProviderGatewaySpendController,
    anthropic_registry_charge_extractor,
    build_protected_gateway_spend_controller,
    protected_authority_environment,
    uniform_case_reservation_microusd,
)


class _FakeAuthority:
    def __init__(self) -> None:
        self.authorized: list[tuple[ProviderSpendKey, int]] = []
        self.responses: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        self.authorized.append((key, reservation_microusd))
        return AttemptLease(
            attempt_id="a" * 64,
            authority_identity_sha256="b" * 64,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=1,
            reservation_microusd=reservation_microusd,
        )

    def record_response(self, lease: AttemptLease, **kwargs: Any) -> None:
        self.responses.append({"lease": lease, **kwargs})

    def record_failure(self, lease: AttemptLease, **kwargs: Any) -> None:
        self.failures.append({"lease": lease, **kwargs})

    def adopt_attempt(self, *args: Any, **kwargs: Any) -> AttemptLease:
        raise NotImplementedError

    def reconcile_ambiguous(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError


def _profile() -> ResolvedAuthProfile:
    return ResolvedAuthProfile(
        profile_id=PUBLISHED_API_KEY,
        projected_env_vars=("ANTHROPIC_API_KEY",),
        infisical_path=None,
        infisical_env="dev",
    )


def _spec(tmp_path: Path) -> RunSpec:
    return RunSpec(
        spec_id="row-case-1",
        argv=("claude", "-p", "prompt"),
        working_directory=tmp_path,
    )


def _config() -> ProtectedTerminalSpendConfig:
    return ProtectedTerminalSpendConfig(
        cycle_id="cycle-1",
        account="official",
        model_key="anthropic:claude-sonnet-4-5",
        ceiling_microusd=100,
        authority_identity_sha256="a" * 64,
        reservation_ledger_sha256="b" * 64,
        provider_authority_table="provider-spend",
        provider_authority_region="us-east-1",
        provider_authority_resource_identity_sha256="c" * 64,
    )


def _registry_entry(
    model_id: str = "claude-opus-5",
    *,
    cache_read_price: float | None = 0.5,
    cache_write_price: float | None = 6.25,
) -> ModelRegistryEntry:
    record: dict[str, object] = {
        "provider": "anthropic",
        "model_id": model_id,
        "display_name": model_id,
        "model_version_or_snapshot": model_id,
        "provider_training_cutoff_status": "unknown",
        "max_output_tokens": 128000,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 1_000_000,
        "pricing_source": "fixture-pricing",
        "input_token_price": 5.0,
        "output_token_price": 25.0,
        "known_cutoff_publicity_caveats": [],
    }
    if cache_read_price is not None:
        record["cache_read_token_price"] = cache_read_price
    if cache_write_price is not None:
        record["cache_write_token_price"] = cache_write_price
    return ModelRegistryEntry.from_record(record)


def _usage_body(usage: dict[str, object]) -> bytes:
    return json.dumps({"usage": usage}, separators=(",", ":")).encode()


def _receipt(spec: RunSpec, *, status: str = "succeeded") -> ExecutionReceipt:
    return ExecutionReceipt.from_transcript(
        spec,
        stdout='{"type":"result"}',
        stderr="" if status == "succeeded" else "failed",
        returncode=0 if status == "succeeded" else 1,
        status=status,
        usage=(
            {"input_tokens": 12, "output_tokens": 4} if status == "succeeded" else {}
        ),
        cost_usd=0.000003 if status == "succeeded" else None,
    )


def test_github_environment_source_requires_protected_workflow() -> None:
    source = GitHubEnvironmentCredentialSource(
        {
            "GITHUB_ACTIONS": "true",
            "ANTHROPIC_API_KEY": "secret-value",
        }
    )
    with pytest.raises(AuthProfileError, match="official workflow marker"):
        source.fetch_projected_env(_profile())

    projected = source.__class__(
        {
            "GITHUB_ACTIONS": "true",
            "LFB_PROTECTED_TERMINAL_RELEASE": "1",
            "ANTHROPIC_API_KEY": "secret-value",
        }
    ).fetch_projected_env(_profile())
    assert projected == {"ANTHROPIC_API_KEY": "secret-value"}


def test_gateway_credential_source_keeps_provider_key_out_of_harness() -> None:
    source = GitHubEnvironmentGatewayCredentialSource(
        {
            "GITHUB_ACTIONS": "true",
            "LFB_PROTECTED_TERMINAL_RELEASE": "1",
            "ANTHROPIC_API_KEY": "secret-value",
        }
    )

    projected = source.upstream_environment()

    assert projected == {"LFB_MODEL_GATEWAY_UPSTREAM_API_KEY": "secret-value"}
    assert "ANTHROPIC_API_KEY" not in projected


def test_gateway_credential_source_refuses_ambient_key() -> None:
    source = GitHubEnvironmentGatewayCredentialSource(
        {"ANTHROPIC_API_KEY": "secret-value"}
    )

    with pytest.raises(ProtectedTerminalPaidError, match="GitHub Actions"):
        source.upstream_environment()


def test_protected_authority_environment_is_value_bound() -> None:
    values = protected_authority_environment(
        {
            "GITHUB_ACTIONS": "true",
            "LFB_PROTECTED_TERMINAL_RELEASE": "1",
            "LFB_PROVIDER_AUTHORITY_TABLE": "provider-spend",
            "LFB_AWS_REGION": "us-east-1",
            "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256": "a" * 64,
        }
    )
    assert values == ("provider-spend", "us-east-1", "a" * 64)


def test_uniform_reservation_leaves_remainder_in_shared_cap() -> None:
    assert uniform_case_reservation_microusd(101, 4) == 25
    with pytest.raises(ProtectedTerminalPaidError, match="at least one"):
        uniform_case_reservation_microusd(3, 4)


def test_protected_gateway_factory_uses_workflow_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _FakeAuthority()
    config = _config()
    captured: list[ProtectedTerminalSpendConfig] = []

    def fake_builder(
        received: ProtectedTerminalSpendConfig,
    ) -> _FakeAuthority:
        captured.append(received)
        return authority

    monkeypatch.setattr(
        protected_terminal_paid,
        "build_dynamodb_spend_authority",
        fake_builder,
    )

    controller = build_protected_gateway_spend_controller(
        config,
        reservation_microusd=25,
        charge_extractor=lambda _body, _status, _content_type: 7,
    )

    assert controller.authority is authority
    assert captured == [config]


def test_anthropic_registry_charge_extractor_prices_cache_buckets() -> None:
    extract = anthropic_registry_charge_extractor(_registry_entry())
    body = _usage_body(
        {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_input_tokens": 400,
            "cache_creation_input_tokens": 100,
        }
    )

    assert extract(body, 200, "application/json") == 10_825


def test_anthropic_registry_charge_extractor_accepts_explicit_zero_cache() -> None:
    extract = anthropic_registry_charge_extractor(
        _registry_entry(cache_read_price=None, cache_write_price=None)
    )
    body = _usage_body(
        {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
    )

    assert extract(body, 200, "application/json") == 10_000


def test_anthropic_registry_charge_extractor_prices_stream_usage() -> None:
    extract = anthropic_registry_charge_extractor(_registry_entry())
    body = (
        b"data: "
        + json.dumps(
            {
                "type": "message_start",
                "message": {
                    "usage": {
                        "input_tokens": 1000,
                        "output_tokens": 0,
                        "cache_read_input_tokens": 400,
                        "cache_creation_input_tokens": 100,
                    }
                },
            },
            separators=(",", ":"),
        ).encode()
        + b"\n\n"
        + b'data: {"type":"message_delta","usage":{"output_tokens":200}}\n\n'
        b"data: [DONE]\n\n"
    )

    assert extract(body, 200, "text/event-stream") == 10_825


def test_anthropic_registry_charge_extractor_accepts_cache_larger_than_raw() -> None:
    extract = anthropic_registry_charge_extractor(_registry_entry())
    body = _usage_body(
        {
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_read_input_tokens": 400,
            "cache_creation_input_tokens": 100,
        }
    )

    assert extract(body, 200, "application/json") == 6_325


@pytest.mark.parametrize(
    "body",
    (
        _usage_body(
            {
                "input_tokens": 1000,
                "output_tokens": 200,
                "cache_creation_input_tokens": 100,
            }
        ),
        _usage_body(
            {
                "input_tokens": 1000,
                "output_tokens": 200,
                "cache_read_input_tokens": 400,
                "cache_creation_input_tokens": "100",
            }
        ),
    ),
)
def test_anthropic_registry_charge_extractor_fails_closed_on_unknown_usage(
    body: bytes,
) -> None:
    extract = anthropic_registry_charge_extractor(_registry_entry())

    assert extract(body, 200, "application/json") is None


def test_anthropic_registry_charge_extractor_fails_closed_on_unknown_cache_rate() -> (
    None
):
    extract = anthropic_registry_charge_extractor(
        _registry_entry(cache_write_price=None)
    )
    body = _usage_body(
        {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 100,
        }
    )

    assert extract(body, 200, "application/json") is None


def test_anthropic_registry_charge_extractor_rejects_non_anthropic_entry() -> None:
    record = _registry_entry().to_record()
    record["provider"] = "openai"
    with pytest.raises(ProtectedTerminalPaidError, match="Anthropic registry"):
        anthropic_registry_charge_extractor(ModelRegistryEntry.from_record(record))


def test_controller_authorizes_and_settles_success(tmp_path: Path) -> None:
    authority = _FakeAuthority()
    config = _config()
    controller = ProtectedSpendController(authority, config, 25)
    spec = _spec(tmp_path)

    receipt = controller.execute(spec, lambda value: _receipt(value))

    assert receipt.status == "succeeded"
    assert authority.authorized[0][0].case_id == spec.spec_id
    assert authority.authorized[0][1] == 25
    assert len(authority.responses) == 1
    response = authority.responses[0]
    assert response["input_tokens"] == 12
    assert response["output_tokens"] == 4
    assert response["actual_microusd"] == 3
    assert (
        response["response_sha256"]
        == hashlib.sha256(receipt.stdout.encode()).hexdigest()
    )
    assert authority.failures == []


def test_controller_retains_reservation_for_failed_receipt(tmp_path: Path) -> None:
    authority = _FakeAuthority()
    controller = ProtectedSpendController(authority, _config(), 25)
    controller.execute(_spec(tmp_path), lambda value: _receipt(value, status="failed"))

    assert authority.responses == []
    assert len(authority.failures) == 1
    assert authority.failures[0]["failure_type"] == "terminal_receipt_failed"
    assert authority.failures[0]["ambiguous"] is True


def test_gateway_controller_allocates_and_settles_each_recursive_request() -> None:
    authority = _FakeAuthority()
    controller = ProviderGatewaySpendController(
        authority,
        _config(),
        25,
        lambda _body, _status, _content_type: 7,
    )

    first = controller.authorize_request(
        request_id="case-1",
        body=b"first",
        model="claude-sonnet-4-5",
        max_tokens=10,
    )
    second = controller.authorize_request(
        request_id="case-1",
        body=b"second",
        model="claude-sonnet-4-5",
        max_tokens=10,
    )

    assert (
        controller.settle_response(
            first,
            response_body=b"response-1",
            response_status=200,
            content_type="application/json",
            input_tokens=12,
            output_tokens=4,
        )
        is True
    )
    assert (
        controller.settle_response(
            second,
            response_body=b"response-2",
            response_status=502,
            content_type="application/json",
            input_tokens=None,
            output_tokens=None,
        )
        is False
    )

    assert [key.case_id for key, _ in authority.authorized] == [
        "case-1:gateway:1",
        "case-1:gateway:2",
    ]
    assert authority.responses[0]["actual_microusd"] == 7
    assert authority.failures[0]["failure_type"] == "gateway_upstream_error"
    assert authority.failures[0]["ambiguous"] is True


def test_gateway_controller_retains_unknown_charge() -> None:
    authority = _FakeAuthority()
    controller = ProviderGatewaySpendController(
        authority,
        _config(),
        25,
        lambda _body, _status, _content_type: None,
    )
    lease = controller.authorize_request(
        request_id="case-1",
        body=b"request",
        model="claude-sonnet-4-5",
        max_tokens=10,
    )

    assert (
        controller.settle_response(
            lease,
            response_body=b"response",
            response_status=200,
            content_type="application/json",
            input_tokens=12,
            output_tokens=4,
        )
        is False
    )
    assert authority.responses == []
    assert authority.failures[0]["failure_type"] == "gateway_charge_missing"
    assert authority.failures[0]["ambiguous"] is True


def test_gateway_controller_journals_normalized_anthropic_input() -> None:
    authority = _FakeAuthority()
    controller = ProviderGatewaySpendController(
        authority,
        _config(),
        25,
        anthropic_registry_charge_extractor(_registry_entry()),
    )
    lease = controller.authorize_request(
        request_id="case-1",
        body=b"request",
        model="claude-sonnet-4-5",
        max_tokens=10,
    )
    response_body = _usage_body(
        {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_read_input_tokens": 400,
            "cache_creation_input_tokens": 100,
        }
    )

    assert (
        controller.settle_response(
            lease,
            response_body=response_body,
            response_status=200,
            content_type="application/json",
            input_tokens=1000,
            output_tokens=200,
        )
        is True
    )

    assert authority.responses[0]["input_tokens"] == 1500
    assert authority.responses[0]["output_tokens"] == 200
    assert authority.responses[0]["actual_microusd"] == 10_825

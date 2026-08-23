from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import LongContextSurcharge
from legalforecast.evals.provider_spend_attempt_handler import (
    CompositeProviderAttemptHandler,
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
    max_output_tokens_for_reservation_cap,
)
from legalforecast.evals.provider_spend_control import AttemptLease, ProviderSpendKey
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)


@dataclass
class RecordingAuthority:
    events: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    attempt_count: int = 0
    authority_identity_sha256: str = "a" * 64
    leases: dict[int, AttemptLease] = field(default_factory=dict[int, AttemptLease])
    statuses: dict[int, str] = field(default_factory=dict[int, str])

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        self.attempt_count += 1
        lease = AttemptLease(
            attempt_id=f"{self.attempt_count:064x}",
            authority_identity_sha256=self.authority_identity_sha256,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=self.attempt_count,
            reservation_microusd=reservation_microusd,
        )
        self.leases[lease.attempt_ordinal] = lease
        self.statuses[lease.attempt_ordinal] = "reserved"
        self.events.append(("authorize", reservation_microusd))
        return lease

    def adopt_attempt(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int | None = None,
    ) -> AttemptLease:
        ordinal = self.attempt_count if attempt_ordinal is None else attempt_ordinal
        lease = self.leases[ordinal]
        assert lease.logical_call_key == key.logical_call_key
        if self.statuses[ordinal] not in {"reserved", "settled"}:
            raise RuntimeError("remote attempt is not replayable")
        self.events.append(("adopt", ordinal))
        return lease

    def record_response(
        self,
        lease: AttemptLease,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_microusd: int,
        response_sha256: str,
    ) -> None:
        self.statuses[lease.attempt_ordinal] = "settled"
        self.events.append(
            (
                "response",
                lease.attempt_ordinal,
                input_tokens,
                output_tokens,
                actual_microusd,
                response_sha256,
            )
        )

    def record_failure(
        self,
        lease: AttemptLease,
        *,
        failure_type: str,
        ambiguous: bool,
    ) -> None:
        self.statuses[lease.attempt_ordinal] = (
            "ambiguous" if ambiguous else "failed_nonbillable"
        )
        self.events.append(("failure", lease.attempt_ordinal, failure_type, ambiguous))


def test_handler_authorizes_immediately_before_each_transport_call() -> None:
    authority = RecordingAuthority()
    handler = _handler(authority)

    def provider_call() -> dict[str, object]:
        assert authority.events == [("authorize", 500_000)]
        return {"response": "ok"}

    assert handler.run_attempt(1, provider_call) == {"response": "ok"}
    assert handler.durable_attempt_ordinal(1) == 1


def test_transport_failure_is_ambiguous_and_retains_reservation() -> None:
    authority = RecordingAuthority()
    handler = _handler(authority)

    with pytest.raises(TimeoutError):
        handler.run_attempt(1, lambda: (_ for _ in ()).throw(TimeoutError()))

    assert authority.events == [
        ("authorize", 500_000),
        ("failure", 1, "TimeoutError", True),
    ]


def test_explicit_http_429_is_nonbillable_for_bounded_fallback() -> None:
    authority = RecordingAuthority()
    handler = _handler(authority)

    class RateLimitError(RuntimeError):
        status_code = 429

    with pytest.raises(RateLimitError):
        handler.run_attempt(1, lambda: (_ for _ in ()).throw(RateLimitError()))

    assert authority.events == [
        ("authorize", 500_000),
        ("failure", 1, "RateLimitError", False),
    ]


def test_post_response_validation_failure_is_recorded_as_ambiguous() -> None:
    authority = RecordingAuthority()
    handler = _handler(authority)
    handler.run_attempt(1, lambda: {"malformed": True})

    handler.record_post_response_failure(1, failure_type="LiveModelResponseError")

    assert authority.events[-1] == (
        "failure",
        1,
        "LiveModelResponseError",
        True,
    )


def test_settlement_uses_authority_ordinal_and_rounds_microdollars_up() -> None:
    authority = RecordingAuthority()
    handler = _handler(authority)
    handler.run_attempt(1, lambda: {"response": "ok"})

    handler.settle_attempt(
        1,
        input_tokens=3,
        output_tokens=2,
        actual_cost_usd=0.0000011,
        raw_output='{"ok":true}',
    )

    event = authority.events[-1]
    assert event[:5] == ("response", 1, 3, 2, 2)
    assert isinstance(event[5], str) and len(event[5]) == 64


def test_handler_adopts_authorization_after_crash_and_settles_idempotently() -> None:
    authority = RecordingAuthority()
    original = _handler(authority)
    original.run_attempt(7, lambda: {"response": "ok"})
    durable_ordinal = original.durable_attempt_ordinal(7)

    recovered = _handler(authority)
    recovered.adopt_attempt(7, durable_attempt_ordinal=durable_ordinal)
    for _ in range(2):
        recovered.settle_attempt(
            durable_ordinal,
            input_tokens=3,
            output_tokens=2,
            actual_cost_usd=0.0000011,
            raw_output='{"ok":true}',
        )

    assert authority.events == [
        ("authorize", 500_000),
        ("adopt", durable_ordinal),
        ("response", durable_ordinal, 3, 2, 2, authority.events[-1][5]),
        ("response", durable_ordinal, 3, 2, 2, authority.events[-1][5]),
    ]


def test_conservative_reservation_uses_remaining_input_context() -> None:
    assert (
        conservative_reservation_microusd(
            context_limit=200_000,
            max_output_tokens=4_096,
            input_token_price=2.5,
            output_token_price=10.0,
        )
        == 530_720
    )


def test_conservative_reservation_uses_base_rates_at_long_context_boundary() -> None:
    assert (
        conservative_reservation_microusd(
            context_limit=276_096,
            max_output_tokens=4_096,
            input_token_price=2.5,
            output_token_price=10.0,
            long_context_surcharge=LongContextSurcharge(
                threshold_input_tokens=272_000,
                input_price_multiplier=2.0,
                output_price_multiplier=1.5,
            ),
        )
        == 720_960
    )


def test_conservative_reservation_uses_surcharge_above_long_context_boundary() -> None:
    assert (
        conservative_reservation_microusd(
            context_limit=276_097,
            max_output_tokens=4_096,
            input_token_price=2.5,
            output_token_price=10.0,
            long_context_surcharge=LongContextSurcharge(
                threshold_input_tokens=272_000,
                input_price_multiplier=2.0,
                output_price_multiplier=1.5,
            ),
        )
        == 1_421_445
    )


def test_retry_output_bound_fits_reservation_cap() -> None:
    output_bound = max_output_tokens_for_reservation_cap(
        context_limit=40_000,
        max_output_tokens=20_000,
        input_tokens=100,
        input_token_price=0.75,
        output_token_price=4.5,
        reservation_cap_microusd=50_000,
    )

    assert output_bound == 11_094
    assert math.ceil(100 * 0.75 + output_bound * 4.5) <= 50_000
    assert math.ceil(100 * 0.75 + (output_bound + 1) * 4.5) > 50_000


def test_retry_output_bound_rejects_prompt_that_exhausts_cap() -> None:
    with pytest.raises(ValueError, match="cannot cover the conservative prompt"):
        max_output_tokens_for_reservation_cap(
            context_limit=40_000,
            max_output_tokens=20_000,
            input_tokens=100,
            input_token_price=0.75,
            output_token_price=4.5,
            reservation_cap_microusd=50,
        )


@pytest.mark.parametrize("max_output_tokens", [200_000, 200_001])
def test_conservative_reservation_requires_input_capacity(
    max_output_tokens: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="max_output_tokens must be less than context_limit",
    ):
        conservative_reservation_microusd(
            context_limit=200_000,
            max_output_tokens=max_output_tokens,
            input_token_price=2.5,
            output_token_price=10.0,
        )


def test_composite_adopts_remote_spend_when_local_replay_skips_transport() -> None:
    replay = RecordingHandler(replay_payload={"cached": True})
    spend = RecordingHandler()
    composite = CompositeProviderAttemptHandler(replay, spend)

    assert composite.run_attempt(1, lambda: {"network": True}) == {"cached": True}
    composite.settle_attempt(
        1,
        input_tokens=1,
        output_tokens=1,
        actual_cost_usd=0.1,
        raw_output="cached",
    )

    assert spend.events == [("adopt", 1, 11), ("settle", 11)]
    assert replay.events == [("run", 1), ("settle", 11)]


def test_composite_transport_failure_persists_exact_authority_ordinal(
    tmp_path: Path,
) -> None:
    authority = RecordingAuthority(attempt_count=6)
    journal_path = tmp_path / "provider-attempts.sqlite3"

    with _journal(journal_path) as journal:
        composite = CompositeProviderAttemptHandler(journal, _handler(authority))
        with pytest.raises(TimeoutError, match="provider timed out"):
            composite.run_attempt(
                1,
                lambda: (_ for _ in ()).throw(TimeoutError("provider timed out")),
            )

    assert authority.statuses == {7: "ambiguous"}
    with sqlite3.connect(journal_path) as connection:
        row = connection.execute(
            "SELECT status, failure_type, authority_attempt_ordinal "
            "FROM provider_attempts WHERE attempt_ordinal = 1"
        ).fetchone()
    assert row == ("ambiguous", "TimeoutError", 7)


def test_composite_authorization_failure_preserves_original_and_skips_spend() -> None:
    replay = RecordingHandler()
    spend = AuthorizationFailingHandler()
    composite = CompositeProviderAttemptHandler(replay, spend)
    provider_calls = 0

    def provider_call() -> Mapping[str, object]:
        nonlocal provider_calls
        provider_calls += 1
        return {"unexpected": True}

    with pytest.raises(
        AuthorizationFailure,
        match="spend authorization denied",
    ) as exc_info:
        composite.run_attempt(1, provider_call)

    composite.settle_attempt(
        1,
        input_tokens=1,
        output_tokens=1,
        actual_cost_usd=0.1,
        raw_output="not-called",
    )

    assert provider_calls == 0
    assert exc_info.value is spend.authorization_error
    assert replay.events == [("run", 1), ("settle", 11)]
    assert spend.events == [("run", 1)]


def test_composite_maps_each_store_ordinal_for_new_response_failure() -> None:
    replay = RecordingHandler()
    spend = RecordingHandler()
    composite = CompositeProviderAttemptHandler(replay, spend)
    composite.run_attempt(1, lambda: {"malformed": True})

    composite.record_post_response_failure(1, failure_type="ResponseError")

    assert replay.events == [("run", 1), ("failure", 11, "ResponseError")]
    assert spend.events == [("run", 1), ("failure", 11, "ResponseError")]


def test_composite_recovers_when_remote_settlement_fails_after_local_persist() -> None:
    replay = RecordingHandler()
    spend = RecordingHandler(settle_error=RuntimeError("remote unavailable"))
    first_process = CompositeProviderAttemptHandler(replay, spend)
    first_process.run_attempt(1, lambda: {"response": True})

    with pytest.raises(RuntimeError, match="remote unavailable"):
        first_process.settle_attempt(
            1,
            input_tokens=1,
            output_tokens=1,
            actual_cost_usd=0.1,
            raw_output="response",
        )

    # The local response is durable before the failed remote transition.
    assert replay.events == [("run", 1), ("settle", 11)]
    assert spend.events == [("run", 1), ("settle", 11)]

    replay.replay_payload = {"response": True}
    spend.settle_error = None
    second_process = CompositeProviderAttemptHandler(replay, spend)
    provider_calls = 0

    def provider_call() -> Mapping[str, object]:
        nonlocal provider_calls
        provider_calls += 1
        return {"unexpected": True}

    assert second_process.run_attempt(1, provider_call) == {"response": True}
    second_process.settle_attempt(
        1,
        input_tokens=1,
        output_tokens=1,
        actual_cost_usd=0.1,
        raw_output="response",
    )

    assert provider_calls == 0
    assert replay.events == [
        ("run", 1),
        ("settle", 11),
        ("run", 1),
        ("settle", 11),
    ]
    assert spend.events == [
        ("run", 1),
        ("settle", 11),
        ("adopt", 1, 11),
        ("settle", 11),
    ]


def test_composite_replay_adopts_exact_persisted_remote_attempt(
    tmp_path: Path,
) -> None:
    authority = RecordingAuthority()
    journal_path = tmp_path / "provider-attempts.sqlite3"

    with _journal(journal_path) as journal:
        first_process = CompositeProviderAttemptHandler(journal, _handler(authority))
        assert first_process.run_attempt(1, lambda: {"response": "attempt-1"}) == {
            "response": "attempt-1"
        }

    # A duplicate worker may have reserved a later attempt before recovery.
    later = authority.authorize_attempt(
        _handler(authority).key,
        reservation_microusd=500_000,
    )
    assert later.attempt_ordinal == 2

    with _journal(journal_path) as journal:
        recovered = CompositeProviderAttemptHandler(journal, _handler(authority))
        provider_calls = 0

        def provider_call() -> Mapping[str, object]:
            nonlocal provider_calls
            provider_calls += 1
            return {"unexpected": True}

        assert recovered.run_attempt(1, provider_call) == {"response": "attempt-1"}
        recovered.settle_attempt(
            1,
            input_tokens=3,
            output_tokens=2,
            actual_cost_usd=0.000001,
            raw_output='{"response":"attempt-1"}',
        )

    assert provider_calls == 0
    assert ("adopt", 1) in authority.events
    assert any(event[:2] == ("response", 1) for event in authority.events)
    assert not any(event[:2] == ("response", 2) for event in authority.events)


def test_composite_restart_skips_ambiguous_raw_response_and_settles_attempt_two(
    tmp_path: Path,
) -> None:
    authority = RecordingAuthority()
    journal_path = tmp_path / "provider-attempts.sqlite3"

    with _journal(journal_path) as journal:
        first_process = CompositeProviderAttemptHandler(journal, _handler(authority))
        first_process.run_attempt(1, lambda: {"malformed": True})
        first_process.record_post_response_failure(
            1,
            failure_type="LiveModelResponseError",
        )

    provider_calls = 0
    with _journal(journal_path) as journal:
        second_process = CompositeProviderAttemptHandler(journal, _handler(authority))

        def provider_call() -> Mapping[str, object]:
            nonlocal provider_calls
            provider_calls += 1
            return {"response": "attempt-2"}

        assert second_process.run_attempt(1, provider_call) == {"response": "attempt-2"}
        second_process.settle_attempt(
            1,
            input_tokens=3,
            output_tokens=2,
            actual_cost_usd=0.000001,
            raw_output='{"response":"attempt-2"}',
        )
        journal.commit_reconstruction({"labels": []})

    assert provider_calls == 1
    assert authority.statuses == {1: "ambiguous", 2: "settled"}
    with sqlite3.connect(journal_path) as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, raw_response_json, "
            "authority_attempt_ordinal FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows[0][0:2] == (1, "ambiguous")
    assert rows[0][2] is not None
    assert rows[0][3] == 1
    assert rows[1][0:2] == (2, "settled")
    assert rows[1][3] == 2


def test_composite_crash_after_local_failure_keeps_remote_reserved_and_retries(
    tmp_path: Path,
) -> None:
    authority = RecordingAuthority()
    journal_path = tmp_path / "provider-attempts.sqlite3"

    with _journal(journal_path, journal_type=CrashAfterLocalFailureJournal) as journal:
        first_process = CompositeProviderAttemptHandler(journal, _handler(authority))
        first_process.run_attempt(1, lambda: {"malformed": True})
        with pytest.raises(SimulatedProcessCrash):
            first_process.record_post_response_failure(
                1,
                failure_type="LiveModelResponseError",
            )

    assert authority.statuses == {1: "reserved"}

    provider_calls = 0
    with _journal(journal_path) as journal:
        recovered = CompositeProviderAttemptHandler(journal, _handler(authority))

        def provider_call() -> Mapping[str, object]:
            nonlocal provider_calls
            provider_calls += 1
            return {"response": "attempt-2"}

        assert recovered.run_attempt(1, provider_call) == {"response": "attempt-2"}
        recovered.settle_attempt(
            1,
            input_tokens=3,
            output_tokens=2,
            actual_cost_usd=0.000001,
            raw_output='{"response":"attempt-2"}',
        )

    assert provider_calls == 1
    assert authority.statuses == {1: "reserved", 2: "settled"}


def _handler(authority: RecordingAuthority) -> ProviderSpendAttemptHandler:
    return ProviderSpendAttemptHandler(
        authority=authority,
        key=ProviderSpendKey(
            cycle_id="cycle-1",
            provider="openai",
            account="primary",
            stage="official-eval",
            model_key="openai:gpt-test",
            case_id="case-1",
            ablation="full_packet",
            repeat_index=1,
        ),
        reservation_microusd=500_000,
    )


@dataclass
class RecordingHandler:
    replay_payload: dict[str, object] | None = None
    events: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    settle_error: Exception | None = None
    bound_remote_ordinals: dict[int, int] = field(default_factory=dict[int, int])

    def adopt_attempt(
        self,
        local_ordinal: int,
        *,
        durable_attempt_ordinal: int | None = None,
    ) -> None:
        if durable_attempt_ordinal is None:
            durable_attempt_ordinal = local_ordinal + 10
        self.events.append(("adopt", local_ordinal, durable_attempt_ordinal))

    def bind_authority_attempt(
        self,
        local_ordinal: int,
        authority_attempt_ordinal: int,
    ) -> None:
        self.bound_remote_ordinals[local_ordinal] = authority_attempt_ordinal

    def authority_attempt_ordinal(self, local_ordinal: int) -> int:
        return self.bound_remote_ordinals.get(local_ordinal, local_ordinal + 10)

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], Mapping[str, object]],
    ) -> Mapping[str, object]:
        self.events.append(("run", attempt_ordinal))
        if self.replay_payload is not None:
            return self.replay_payload
        return call()

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        return local_ordinal + 10

    def settle_attempt(self, attempt_ordinal: int, **_: object) -> None:
        self.events.append(("settle", attempt_ordinal))
        if self.settle_error is not None:
            raise self.settle_error

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        self.events.append(("failure", durable_attempt_ordinal, failure_type))


class SimulatedProcessCrash(RuntimeError):
    pass


class AuthorizationFailure(RuntimeError):
    pass


@dataclass
class AuthorizationFailingHandler(RecordingHandler):
    authorization_error: AuthorizationFailure = field(
        default_factory=lambda: AuthorizationFailure("spend authorization denied")
    )

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Callable[[], Mapping[str, object]],
    ) -> Mapping[str, object]:
        self.events.append(("run", attempt_ordinal))
        raise self.authorization_error

    def authority_attempt_ordinal(self, local_ordinal: int) -> int:
        raise RuntimeError("spend authorization did not reserve an attempt")


class CrashAfterLocalFailureJournal(ProviderAttemptJournal):
    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        super().record_post_response_failure(
            durable_attempt_ordinal,
            failure_type=failure_type,
        )
        raise SimulatedProcessCrash


def _journal(
    path: Path,
    *,
    journal_type: type[ProviderAttemptJournal] = ProviderAttemptJournal,
) -> ProviderAttemptJournal:
    return journal_type(
        path,
        identity=ProviderCallIdentity(
            stage="llm-label",
            candidate_id="case-1",
            model_key="openai:gpt-test",
            prompt="frozen prompt",
            model_registry_sha256="registry-sha256",
            account="primary",
        ),
        provider="openai",
        reservation_usd=0.5,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:frozen-caps",
    )

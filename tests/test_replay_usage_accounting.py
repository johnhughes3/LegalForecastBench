"""Replaying a settled attempt must reproduce the accounting rule it settled under.

Token counts are derived from a provider usage block, so the derivation rule is
itself evidence. `3a4fad75` (#1003) started billing Gemini `thoughtsTokenCount`
at the output rate; replaying a pre-#1003 settlement then recomputed a larger
output count over byte-identical response bytes and the durable spend authority
rejected it as changed evidence. These tests pin both halves: a superseded rule
reproduces its own settlement, and accounting no declared rule produces still
fails closed.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.evals.live_model_solver import (
    SettledProviderAccounting,
    ValidatedProviderResponseFields,
    complete_live_prompt,
    resolve_settled_provider_response_fields,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.evals.provider_spend_attempt_handler import (
    CompositeProviderAttemptHandler,
    ProviderSpendAttemptHandler,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SettlementError,
    SqliteProviderSpendAuthority,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)

# The exact usage shape that blocked Cycle 1 contract re-issue: thinking tokens
# are reported outside `candidatesTokenCount`, so the two accounting rules
# disagree by exactly `thoughtsTokenCount` over one unchanged response.
RAW_OUTPUT = '{"reviews":[]}'
THINKING_RESPONSE: dict[str, Any] = {
    "modelVersion": "gemini-thinking-2026-05-14",
    "candidates": [{"content": {"parts": [{"text": RAW_OUTPUT}]}}],
    "usageMetadata": {
        "promptTokenCount": 21345,
        "candidatesTokenCount": 3153,
        "thoughtsTokenCount": 4956,
        "totalTokenCount": 29454,
    },
}
SUPERSEDED_OUTPUT_TOKENS = 3153
SUPERSEDED_COST_USD = 0.0603945
CURRENT_OUTPUT_TOKENS = 8109
CURRENT_COST_USD = 0.1049985
RESERVATION_MICROUSD = 1_695_744
SPEND_KEY = ProviderSpendKey(
    cycle_id="cycle-1",
    provider="google",
    account="primary",
    stage="disclosure-model-review",
    model_key="google:gemini-thinking",
    case_id="cand-1",
    ablation="full_packet",
    repeat_index=1,
)


def test_replay_reproduces_the_rule_in_force_at_settlement() -> None:
    handler = _SettledReplayAttemptHandler(
        settled={
            "raw_output": RAW_OUTPUT,
            "input_tokens": 21345,
            "output_tokens": SUPERSEDED_OUTPUT_TOKENS,
            "actual_cost_usd": SUPERSEDED_COST_USD,
        }
    )

    response = _replay_with_handler(handler)

    assert response.output_tokens == SUPERSEDED_OUTPUT_TOKENS
    assert response.estimated_cost == SUPERSEDED_COST_USD
    assert handler.events == [
        ("run", 1),
        (
            "settle",
            1,
            21345,
            SUPERSEDED_OUTPUT_TOKENS,
            SUPERSEDED_COST_USD,
            RAW_OUTPUT,
        ),
    ]


def test_replay_keeps_the_current_rule_when_it_already_matches_settlement() -> None:
    response = _replay_with_handler(
        _SettledReplayAttemptHandler(
            settled={
                "raw_output": RAW_OUTPUT,
                "input_tokens": 21345,
                "output_tokens": CURRENT_OUTPUT_TOKENS,
                "actual_cost_usd": CURRENT_COST_USD,
            }
        )
    )

    assert response.output_tokens == CURRENT_OUTPUT_TOKENS
    assert response.estimated_cost == CURRENT_COST_USD


def test_replay_keeps_the_current_rule_when_no_declared_rule_reproduces_it() -> None:
    """Unreproducible settled accounting must reach the authority unchanged."""

    response = _replay_with_handler(
        _SettledReplayAttemptHandler(
            settled={
                "raw_output": RAW_OUTPUT,
                "input_tokens": 21345,
                "output_tokens": 5000,
                "actual_cost_usd": 0.0770175,
            }
        )
    )

    assert response.output_tokens == CURRENT_OUTPUT_TOKENS


def test_replay_ignores_a_settlement_recorded_for_different_response_bytes() -> None:
    response = _replay_with_handler(
        _SettledReplayAttemptHandler(
            settled={
                "raw_output": '{"reviews":[{"id":"other"}]}',
                "input_tokens": 21345,
                "output_tokens": SUPERSEDED_OUTPUT_TOKENS,
                "actual_cost_usd": SUPERSEDED_COST_USD,
            }
        )
    )

    assert response.output_tokens == CURRENT_OUTPUT_TOKENS


def test_fresh_attempt_without_prior_settlement_uses_the_current_rule() -> None:
    response = _replay_with_handler(_RecordingAttemptHandler())

    assert response.output_tokens == CURRENT_OUTPUT_TOKENS
    assert response.estimated_cost == CURRENT_COST_USD


def test_settled_replay_survives_the_rule_change_across_durable_stores(
    tmp_path: Path,
) -> None:
    """End-to-end reproduction: journal replay plus the real spend authority."""

    journal_path = tmp_path / "provider-attempts.sqlite3"
    authority_path = tmp_path / "provider-spend-authority.sqlite3"
    _settle_under_the_superseded_rule(journal_path, authority_path)

    with (
        _journal(journal_path) as journal,
        _authority(authority_path) as authority,
    ):
        response = complete_live_prompt(
            _registry_entry(),
            "frozen prompt",
            transport=_forbidden_transport,
            environ={"GEMINI_API_KEY": "gemini-secret"},
            max_attempts=1,
            attempt_handler=CompositeProviderAttemptHandler(
                journal,
                ProviderSpendAttemptHandler(
                    authority=authority,
                    key=SPEND_KEY,
                    reservation_microusd=RESERVATION_MICROUSD,
                ),
            ),
        )

    assert (response.input_tokens, response.output_tokens) == (
        21345,
        SUPERSEDED_OUTPUT_TOKENS,
    )
    assert response.estimated_cost == SUPERSEDED_COST_USD


def test_settled_replay_still_fails_closed_on_unreproducible_accounting(
    tmp_path: Path,
) -> None:
    """A journal claim no declared rule produces must not settle a replay."""

    journal_path = tmp_path / "provider-attempts.sqlite3"
    authority_path = tmp_path / "provider-spend-authority.sqlite3"
    _settle_under_the_superseded_rule(journal_path, authority_path)
    with sqlite3.connect(journal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET normalized_response_json = ?",
            (
                json.dumps(
                    {
                        "actual_cost_usd": 0.0770175,
                        "input_tokens": 21345,
                        "output_tokens": 5000,
                        "raw_output": RAW_OUTPUT,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ),
        )

    with (
        _journal(journal_path) as journal,
        _authority(authority_path) as authority,
        pytest.raises(SettlementError, match="settled provider response evidence"),
    ):
        complete_live_prompt(
            _registry_entry(),
            "frozen prompt",
            transport=_forbidden_transport,
            environ={"GEMINI_API_KEY": "gemini-secret"},
            max_attempts=1,
            attempt_handler=CompositeProviderAttemptHandler(
                journal,
                ProviderSpendAttemptHandler(
                    authority=authority,
                    key=SPEND_KEY,
                    reservation_microusd=RESERVATION_MICROUSD,
                ),
            ),
        )


@pytest.mark.parametrize(
    "settled",
    (
        {
            "raw_output": RAW_OUTPUT,
            "input_tokens": "21345",
            "output_tokens": SUPERSEDED_OUTPUT_TOKENS,
            "actual_cost_usd": SUPERSEDED_COST_USD,
        },
        {
            "raw_output": RAW_OUTPUT,
            "input_tokens": 21345,
            "output_tokens": SUPERSEDED_OUTPUT_TOKENS,
            "actual_cost_usd": "0.0603945",
        },
        {"input_tokens": 21345},
    ),
)
def test_a_malformed_settlement_record_is_ignored_rather_than_trusted(
    settled: dict[str, object],
) -> None:
    response = _replay_with_handler(_SettledReplayAttemptHandler(settled=settled))

    assert response.output_tokens == CURRENT_OUTPUT_TOKENS


def test_a_superseded_rule_that_cannot_parse_the_payload_is_skipped() -> None:
    """An unparsable payload must fall through, not raise out of the replay."""

    entry = _registry_entry()
    fields = ValidatedProviderResponseFields(
        raw_output=RAW_OUTPUT,
        input_tokens=21345,
        output_tokens=CURRENT_OUTPUT_TOKENS,
        served_model_version="gemini-thinking-2026-05-14",
    )

    resolved = resolve_settled_provider_response_fields(
        entry,
        {},
        fields,
        SettledProviderAccounting(
            raw_output=RAW_OUTPUT,
            input_tokens=21345,
            output_tokens=SUPERSEDED_OUTPUT_TOKENS,
            actual_cost_usd=SUPERSEDED_COST_USD,
        ),
    )

    assert resolved == fields


def test_a_handler_without_a_replay_store_reports_no_settlement() -> None:
    composite = CompositeProviderAttemptHandler(
        cast(Any, _RecordingAttemptHandler()),
        cast(Any, _RecordingAttemptHandler()),
    )

    assert composite.settled_response_accounting(1) is None


def test_the_journal_reports_no_settlement_before_one_is_recorded(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "provider-attempts.sqlite3"
    with _journal(journal_path) as journal:
        assert journal.settled_response_accounting(1) is None
        journal.run_attempt(1, lambda: THINKING_RESPONSE)
        # `response_received` holds the bytes but no accounting yet.
        assert journal.settled_response_accounting(1) is None


def test_the_journal_ignores_a_settlement_record_that_is_not_an_object(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "provider-attempts.sqlite3"
    authority_path = tmp_path / "provider-spend-authority.sqlite3"
    _settle_under_the_superseded_rule(journal_path, authority_path)
    with sqlite3.connect(journal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET normalized_response_json = ?",
            ("[]",),
        )

    with _journal(journal_path) as journal:
        assert journal.settled_response_accounting(1) is None


def _settle_under_the_superseded_rule(
    journal_path: Path,
    authority_path: Path,
) -> None:
    """Record the settlement a pre-#1003 process would have written."""

    with (
        _journal(journal_path) as journal,
        _authority(authority_path) as authority,
    ):
        handler = CompositeProviderAttemptHandler(
            journal,
            ProviderSpendAttemptHandler(
                authority=authority,
                key=SPEND_KEY,
                reservation_microusd=RESERVATION_MICROUSD,
            ),
        )
        handler.run_attempt(1, lambda: THINKING_RESPONSE)
        handler.settle_attempt(
            1,
            input_tokens=21345,
            output_tokens=SUPERSEDED_OUTPUT_TOKENS,
            actual_cost_usd=SUPERSEDED_COST_USD,
            raw_output=RAW_OUTPUT,
        )
        journal.commit_reconstruction({"reviews": 0})


def _replay_with_handler(handler: _RecordingAttemptHandler) -> Any:
    return complete_live_prompt(
        _registry_entry(),
        "frozen prompt",
        transport=_FixtureTransport(THINKING_RESPONSE),
        environ={"GEMINI_API_KEY": "gemini-secret"},
        attempt_handler=cast(Any, handler),
    )


@dataclass(slots=True)
class _FixtureTransport:
    payload: dict[str, Any]

    def __call__(
        self,
        request: urllib.request.Request,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        del request, timeout_seconds
        return self.payload


@dataclass(slots=True)
class _RecordingAttemptHandler:
    events: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])

    def run_attempt(
        self,
        attempt_ordinal: int,
        call: Any,
    ) -> Mapping[str, object]:
        self.events.append(("run", attempt_ordinal))
        return cast(Mapping[str, object], call())

    def settle_attempt(
        self,
        attempt_ordinal: int,
        *,
        input_tokens: int,
        output_tokens: int,
        actual_cost_usd: float,
        raw_output: str,
    ) -> None:
        self.events.append(
            (
                "settle",
                attempt_ordinal,
                input_tokens,
                output_tokens,
                actual_cost_usd,
                raw_output,
            )
        )

    def durable_attempt_ordinal(self, local_ordinal: int) -> int:
        return local_ordinal

    def record_post_response_failure(
        self,
        durable_attempt_ordinal: int,
        *,
        failure_type: str,
    ) -> None:
        self.events.append(
            ("post_response_failure", durable_attempt_ordinal, failure_type)
        )


@dataclass(slots=True)
class _SettledReplayAttemptHandler(_RecordingAttemptHandler):
    """Recording handler that also reports one durably settled prior attempt."""

    settled: Mapping[str, object] | None = None

    def settled_response_accounting(
        self,
        attempt_ordinal: int,
    ) -> Mapping[str, object] | None:
        del attempt_ordinal
        return self.settled


def _forbidden_transport(
    request: urllib.request.Request,
    timeout_seconds: float,
) -> dict[str, object]:
    del request, timeout_seconds
    raise AssertionError("replay must not reach provider transport")


def _journal(path: Path) -> ProviderAttemptJournal:
    return ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="disclosure-model-review",
            candidate_id="cand-1",
            model_key="google:gemini-thinking",
            prompt="frozen prompt",
            model_registry_sha256="registry-sha256",
        ),
        provider="google",
        reservation_usd=1.7,
        cycle_cap_usd=10.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:frozen-caps",
    )


def _authority(path: Path) -> SqliteProviderSpendAuthority:
    return SqliteProviderSpendAuthority(
        path,
        authority_identity_sha256="a" * 64,
        cycle_id="cycle-1",
        provider="google",
        account="primary",
        cap_microusd=10_000_000,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256="f" * 64,
            max_billable_attempts=3,
            failure_threshold=3,
            failure_window_seconds=300,
        ),
    )


def _registry_entry() -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        {
            "provider": "google",
            "model_id": "gemini-thinking",
            "display_name": "Gemini thinking test",
            "model_version_or_snapshot": "gemini-thinking-2026-05-14",
            "release_timestamp": "2026-05-14T09:00:00Z",
            "release_timestamp_source": "fixture release note",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-04-01",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "fixture price sheet",
            "input_token_price": 1.5,
            "output_token_price": 9.0,
            "known_cutoff_publicity_caveats": [],
        }
    )

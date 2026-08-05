from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict, cast

import legalforecast.cli as cli
import legalforecast.ingestion.ranked_reserve_replacement as ranked_reserve_module
import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseStatus,
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
    CourtListenerRecapFetchError,
)
from legalforecast.ingestion.docket_decision_text_source import (
    VerifiedTerminalPurchaseDispositionAuthority,
)
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.ranked_reserve_replacement import (
    RankedReserveReplacementError,
    bind_ranked_reserve_outputs,
    plan_ranked_reserve_replacements,
)
from legalforecast.ingestion.terminal_purchase_failure import (
    TerminalPurchaseFailureError,
    VerifiedTerminalPurchaseFailureAuthority,
    terminal_retrieval_exclusions_bytes,
    verify_terminal_purchase_failure_authority,
)
from legalforecast.ingestion.terminal_purchase_failure import (
    _issue as issue_terminal_purchase_failure_authority,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionStage,
    merge_exclusion_ledger_records,
)
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures


@pytest.fixture
def _historical_v1_algorithm_fixture(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


pytestmark = pytest.mark.usefixtures("_historical_v1_algorithm_fixture")


def test_exact_100_plus_five_promotes_first_reserve_and_reconciles(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=_terminal_bytes("case-050"),
            expected_terminal_exclusions_sha256=_sha(_terminal_bytes("case-050")),
            purchase_journal=journal,
        )

    assert len(plan.active_selection) == 100
    assert plan.active_candidate_ids[50] == "case-100"
    assert [row["candidate_id"] for row in plan.replacement_selection] == ["case-100"]
    assert [row.candidate_id for row in plan.replacement_plan.case_plans] == [
        "case-100"
    ]
    assert plan.successor_approval_required is True
    assert plan.replacement_plan.dry_run is False
    selected = set(plan.active_candidate_ids)
    excluded = {str(row["candidate_id"]) for row in plan.successor_exclusions}
    assert selected.isdisjoint(excluded)
    assert selected | excluded == {f"case-{index:03d}" for index in range(105)}
    assert "case-100" not in excluded
    assert "case-050" in excluded
    terminal_exclusion = next(
        row for row in plan.successor_exclusions if row["candidate_id"] == "case-050"
    )
    assert terminal_exclusion["stage"] == "unitization"
    assert terminal_exclusion["source_stage"] == "apply-unitization-review"
    round_tripped = merge_exclusion_ledger_records((terminal_exclusion,))
    assert round_tripped.entries[0].stage is ExclusionStage.UNITIZATION
    assert plan.committed_spend_usd == "3.05"
    assert plan.reserved_replacement_spend_usd == "3.05"
    assert plan.remaining_headroom_usd == "0.00"
    assert plan.paid_activity_requested is False
    assert plan.paid_activity_executed is False


@pytest.mark.parametrize(
    ("terminal", "retryable"),
    ((False, False), (True, True)),
)
def test_retryable_or_nonterminal_evidence_never_consumes_a_reserve(
    tmp_path: Path,
    terminal: bool,
    retryable: bool,
) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_record("case-050")
    evidence["terminal"] = terminal
    evidence["retryable"] = retryable
    payload = _jsonl((evidence,))

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="explicit terminal nonretryable",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=payload,
                expected_terminal_exclusions_sha256=_sha(payload),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_unknown_terminal_stage_fails_before_journal_mutation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_record("case-050")
    evidence["source_stage"] = "unsupported-downstream-stage"
    payload = _jsonl((evidence,))

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="terminal exclusion source stage is unsupported",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=payload,
                expected_terminal_exclusions_sha256=_sha(payload),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


@pytest.mark.parametrize("queue_status", (3, 6, 7))
def test_verified_terminal_purchase_failure_consumes_ranked_reserve(
    tmp_path: Path,
    queue_status: int,
) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=queue_status,
            result_path=result_path,
        )
        authority = verify_terminal_purchase_failure_authority(
            purchase_result_path=_write_purchase_artifacts(
                result_path, result=result, run_card=run_card
            ),
            purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
            purchase_journal=journal,
        )
        terminal_bytes = terminal_retrieval_exclusions_bytes(authority)
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=terminal_bytes,
            expected_terminal_exclusions_sha256=_sha(terminal_bytes),
            purchase_journal=journal,
            terminal_purchase_failure_authority=authority,
        )

    evidence = authority.evidence_records[0]
    failure = evidence["failures"][0]
    assert evidence["candidate_id"] == "case-050"
    assert evidence["terminal"] is True
    assert evidence["retryable"] is False
    assert failure["source_document_id"] == "doc-050"
    assert failure["queue_status"] == queue_status
    assert failure["ledger_status"] == "failed"
    assert failure["reservation_usd"] == "3.05"
    assert failure["cap_counted"] is True
    assert failure["cap_counted_usd"] == "3.05"
    assert failure["operation_key"]
    assert failure["ledger_operation_sha256"].startswith("sha256:")
    assert plan.active_candidate_ids[50] == "case-100"
    terminal_exclusion = next(
        row for row in plan.successor_exclusions if row["candidate_id"] == "case-050"
    )
    assert terminal_exclusion["stage"] == "retrieval"
    assert terminal_exclusion["source_stage"] == "purchase-missing-recap-fetch"
    assert terminal_exclusion["terminal_evidence_sha256"].startswith("sha256:")


def test_verified_mixed_disposition_emits_cap_bounded_99_case_precursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(
        tmp_path,
        hard_cap_usd="24.40",
        reserve_document_counts=(3, 4, 4, 4, 4),
    )
    terminal_records = {
        candidate_id: {
            **_terminal_record(candidate_id),
            "reason": "terminal_courtlistener_recap_fetch_provider_error",
            "source_stage": "purchase-missing-recap-fetch",
        }
        for candidate_id in ("case-050", "case-051", "case-052")
    }
    terminal_bytes = _jsonl(tuple(terminal_records.values()))
    disposition = object.__new__(VerifiedTerminalPurchaseDispositionAuthority)
    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_residual_terminal_records",
        lambda authority, *, purchase_journal: terminal_records,
    )
    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_terminal_purchase_disposition_record",
        lambda authority, *, purchase_journal: _disposition_record(
            residual_sha256=_sha(terminal_bytes)
        ),
    )

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=terminal_bytes,
            expected_terminal_exclusions_sha256=_sha(terminal_bytes),
            purchase_journal=journal,
            terminal_purchase_disposition_authority=disposition,
            precommit_revalidator=lambda: None,
        )
        replayed = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=terminal_bytes,
            expected_terminal_exclusions_sha256=_sha(terminal_bytes),
            purchase_journal=journal,
            terminal_purchase_disposition_authority=disposition,
            precommit_revalidator=lambda: None,
        )

    assert len(plan.active_selection) == 99
    assert [row["candidate_id"] for row in plan.replacement_selection] == [
        "case-100",
        "case-101",
    ]
    assert [row.candidate_id for row in plan.replacement_plan.case_plans] == [
        "case-100",
        "case-101",
    ]
    assert "case-052" not in plan.active_candidate_ids
    assert {row["candidate_id"] for row in plan.successor_exclusions} >= {
        "case-050",
        "case-051",
        "case-052",
    }
    assert plan.reserved_replacement_spend_usd == "21.35"
    assert plan.remaining_headroom_usd == "0.00"
    assert len(plan.tranche_event_record_sha256s) == 2
    assert replayed.active_selection == plan.active_selection
    assert replayed.replacement_selection == plan.replacement_selection
    assert replayed.replacement_plan.to_record() == plan.replacement_plan.to_record()
    assert replayed.tranche_event_record_sha256s == plan.tranche_event_record_sha256s


def test_raw_retrieval_terminal_record_cannot_bypass_verified_authority(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    record = _terminal_record("case-050")
    record.update(
        {
            "reason": "terminal_courtlistener_recap_fetch_provider_error",
            "source_stage": "purchase-missing-recap-fetch",
        }
    )
    terminal_bytes = _jsonl((record,))

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="verified terminal purchase-failure authority",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=terminal_bytes,
                expected_terminal_exclusions_sha256=_sha(terminal_bytes),
                purchase_journal=journal,
            )


def test_fabricated_terminal_purchase_authority_is_rejected_by_planner(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    record = _terminal_record("case-050")
    record.update(
        {
            "reason": "terminal_courtlistener_recap_fetch_provider_error",
            "source_stage": "purchase-missing-recap-fetch",
        }
    )
    terminal_bytes = _jsonl((record,))
    fabricated = object.__new__(VerifiedTerminalPurchaseFailureAuthority)
    object.__setattr__(fabricated, "_issuer", object())

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(
            RankedReserveReplacementError,
            match="not verifier-issued",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=terminal_bytes,
                expected_terminal_exclusions_sha256=_sha(terminal_bytes),
                purchase_journal=journal,
                terminal_purchase_failure_authority=fabricated,
            )


def test_importable_issuer_cannot_forge_planner_authority(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    forged_terminal_bytes = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        _write_purchase_artifacts(result_path, result=result, run_card=run_card)
        result_bytes = result_path.read_bytes()
        run_card_bytes = result_path.with_name("purchase-run-card.json").read_bytes()
        budget_plan_path = result_path.with_name("purchase-budget-plan.json")
        budget_plan_bytes = budget_plan_path.read_bytes()
        forged = issue_terminal_purchase_failure_authority(  # pyright: ignore[reportPrivateUsage]
            evidence_bytes=b'{"forged":true}\n',
            terminal_exclusions_bytes=forged_terminal_bytes,
            purchase_result_sha256=_sha(result_bytes),
            purchase_run_card_sha256=_sha(run_card_bytes),
            purchase_journal_state_sha256=("sha256:" + journal.purchase_state_sha256()),
            purchase_budget_plan_bytes=budget_plan_bytes,
            purchase_budget_plan_path=str(budget_plan_path.resolve()),
            purchase_result_bytes=result_bytes,
            purchase_result_locator=str(result_path),
            purchase_result_path=str(result_path.resolve()),
            purchase_run_card_bytes=run_card_bytes,
            purchase_run_card_path=str(
                result_path.with_name("purchase-run-card.json").resolve()
            ),
        )
        with pytest.raises(
            RankedReserveReplacementError,
            match="differs from verified source evidence",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=forged_terminal_bytes,
                expected_terminal_exclusions_sha256=_sha(forged_terminal_bytes),
                purchase_journal=journal,
                terminal_purchase_failure_authority=forged,
            )


def test_result_cannot_differ_from_committed_budget_tranche(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        _terminal_purchase_artifacts(
            journal,
            candidate_id="case-051",
            document_id="doc-051",
            queue_status=6,
            result_path=tmp_path / "other-result.json",
        )
        assert (
            json.loads((tmp_path / "purchase-budget-plan.json").read_bytes())[
                "case_plans"
            ][0]["candidate_id"]
            == "case-051"
        )
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="committed budget-plan tranche exactly once",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


def test_later_tranche_may_exclude_historical_terminal_failure(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    first_result_path = tmp_path / "first-result.json"
    second_result_path = tmp_path / "second-result.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=first_result_path,
        )
        second_result, second_run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-100",
            document_id="doc-100",
            queue_status=6,
            result_path=second_result_path,
        )
        authority = verify_terminal_purchase_failure_authority(
            purchase_result_path=_write_purchase_artifacts(
                second_result_path,
                result=second_result,
                run_card=second_run_card,
            ),
            purchase_run_card_path=second_result_path.with_name(
                "purchase-run-card.json"
            ),
            purchase_journal=journal,
        )

    assert [record["candidate_id"] for record in authority.evidence_records] == [
        "case-100"
    ]


@pytest.mark.parametrize("laundered_status", ("purchased", "quarantined"))
def test_terminal_failure_cannot_be_laundered_as_completed_status(
    tmp_path: Path,
    laundered_status: str,
) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        second_result, _ = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-051",
            document_id="doc-051",
            queue_status=6,
            result_path=tmp_path / "other-result.json",
        )
        attempts = result["attempts"]
        second_attempts = second_result["attempts"]
        assert isinstance(attempts, list)
        assert isinstance(second_attempts, list)
        typed_attempts = cast(list[dict[str, object]], attempts)
        typed_second_attempts = cast(list[dict[str, object]], second_attempts)
        laundered_attempt = dict(typed_second_attempts[0])
        laundered_attempt["status"] = laundered_status
        laundered_attempt["reason"] = "fabricated_completed_status"
        typed_attempts.append(laundered_attempt)
        result.update(
            {
                "projected_cost_usd": "6.10",
                "max_projected_budget_usd": "6.10",
                "intended_purchase_count": 2,
                "executed_purchase_count": int(laundered_status == "purchased"),
                "quarantined_material_count": int(laundered_status == "quarantined"),
                "completed_purchase_count": 1,
            }
        )
        run_card.update(
            {
                "record_count": 2,
                "executed_purchase_count": int(laundered_status == "purchased"),
                "quarantined_material_count": int(laundered_status == "quarantined"),
                "completed_purchase_count": 1,
            }
        )
        combined_plan = MissingCoreBudgetPlan(
            case_plans=(
                _case_purchase_plan("case-050", "doc-050", journal),
                _case_purchase_plan("case-051", "doc-051", journal),
            ),
            cost_per_document=journal.policy.per_document_reservation_usd,
            max_projected_budget=journal.policy.per_document_reservation_usd * 2,
            max_missing_core_documents_per_case=1,
            dry_run=False,
            target_case_count=2,
        )
        result_path.with_name("purchase-budget-plan.json").write_bytes(
            _canonical_json(combined_plan.to_record())
        )
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="statuses differ from terminal operations",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


@pytest.mark.parametrize("queue_status", (1, 4, 5))
def test_retryable_queue_status_cannot_issue_terminal_authority(
    tmp_path: Path,
    queue_status: int,
) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=queue_status,
            result_path=result_path,
            terminal=False,
        )
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="retryable or unresolved purchase attempt",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


def test_unbounded_queue_status_digits_raise_domain_error(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        attempts = cast(list[dict[str, object]], result["attempts"])
        attempts[0]["reason"] = "recap_fetch_status_" + "9" * 5000
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="lacks a nonretryable CourtListener queue status",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


@pytest.mark.parametrize("ledger_state", ("submitted", "queued", "unknown"))
def test_ambiguous_ledger_state_cannot_issue_terminal_authority(
    tmp_path: Path,
    ledger_state: str,
) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        if ledger_state == "submitted":
            journal._connection.execute(  # pyright: ignore[reportPrivateUsage]
                "UPDATE purchase_operations SET status='submitted'"
            )
        elif ledger_state == "queued":
            journal._connection.execute(  # pyright: ignore[reportPrivateUsage]
                "UPDATE purchase_operations SET status='queued'"
            )
        else:
            journal._connection.execute(  # pyright: ignore[reportPrivateUsage]
                "UPDATE purchase_operations SET status='unknown'"
            )
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="submitted, queued, or unknown",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


@pytest.mark.parametrize(
    ("tamper_target", "field", "value", "match"),
    (
        ("result", "candidate_id", "case-051", "budget-plan tranche"),
        ("result", "source_document_id", "doc-051", "budget-plan tranche"),
        ("result", "reason", "recap_fetch_status_5", "nonretryable"),
        ("run_card", "record_count", 2, "record count"),
        ("run_card", "status", "failed", "completed purchase run card"),
    ),
)
def test_mismatched_result_or_run_card_cannot_issue_terminal_authority(
    tmp_path: Path,
    tamper_target: str,
    field: str,
    value: object,
    match: str,
) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        if tamper_target == "result":
            attempts = result["attempts"]
            assert isinstance(attempts, list)
            attempts[0][field] = value
        else:
            run_card[field] = value
        with pytest.raises(TerminalPurchaseFailureError, match=match):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


def test_result_path_must_match_run_card_and_use_canonical_bytes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        other_result_path = tmp_path / "synthetic-purchase-result.json"
        _write_purchase_artifacts(other_result_path, result=result, run_card=run_card)
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="bind the result and canonical ledger",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=other_result_path,
                purchase_run_card_path=other_result_path.with_name(
                    "purchase-run-card.json"
                ),
                purchase_journal=journal,
            )
        result_path.write_text(json.dumps(result), encoding="utf-8")
        (tmp_path / "purchase-run-card.json").write_bytes(_canonical_json(run_card))
        with pytest.raises(TerminalPurchaseFailureError, match="exact canonical JSON"):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=result_path,
                purchase_run_card_path=tmp_path / "purchase-run-card.json",
                purchase_journal=journal,
            )


def test_purchase_artifact_symlink_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    real_result_path = tmp_path / "real-purchase-result.json"
    linked_result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=linked_result_path,
        )
        _write_purchase_artifacts(
            real_result_path,
            result=result,
            run_card=run_card,
        )
        linked_result_path.symlink_to(real_result_path)
        with pytest.raises(
            TerminalPurchaseFailureError,
            match="cannot be safely captured",
        ):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=linked_result_path,
                purchase_run_card_path=real_result_path.with_name(
                    "purchase-run-card.json"
                ),
                purchase_journal=journal,
            )


def test_relative_producer_paths_authenticate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    result_path = Path("courtlistener-recap-fetch-purchases.json")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        authority = verify_terminal_purchase_failure_authority(
            purchase_result_path=_write_purchase_artifacts(
                result_path, result=result, run_card=run_card
            ),
            purchase_run_card_path=Path("purchase-run-card.json"),
            purchase_journal=journal,
        )

    assert authority.evidence_records[0]["candidate_id"] == "case-050"


@pytest.mark.parametrize(
    ("sql", "match"),
    (
        (
            "UPDATE purchase_operations SET reservation_usd='4.00'",
            "reservation differs",
        ),
        (
            "UPDATE purchase_operations SET operation_key='not-a-uuid'",
            "canonical UUID",
        ),
        (
            "UPDATE purchase_operations SET response_json=NULL",
            "statuses differ from terminal operations",
        ),
    ),
)
def test_mismatched_or_non_cap_counted_operation_cannot_issue_authority(
    tmp_path: Path,
    sql: str,
    match: str,
) -> None:
    fixture = _fixture(tmp_path)
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        journal._connection.execute(sql)  # pyright: ignore[reportPrivateUsage]
        with pytest.raises(TerminalPurchaseFailureError, match=match):
            verify_terminal_purchase_failure_authority(
                purchase_result_path=_write_purchase_artifacts(
                    result_path, result=result, run_card=run_card
                ),
                purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
                purchase_journal=journal,
            )


def test_planner_rejects_authority_after_canonical_journal_drift(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="12.20")
    result_path = tmp_path / "courtlistener-recap-fetch-purchases.json"
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        result, run_card = _terminal_purchase_artifacts(
            journal,
            candidate_id="case-050",
            document_id="doc-050",
            queue_status=3,
            result_path=result_path,
        )
        authority = verify_terminal_purchase_failure_authority(
            purchase_result_path=_write_purchase_artifacts(
                result_path, result=result, run_card=run_card
            ),
            purchase_run_card_path=result_path.with_name("purchase-run-card.json"),
            purchase_journal=journal,
        )
        journal.plan(
            MissingCoreBudgetPlan(
                case_plans=(
                    CaseMissingCorePurchasePlan(
                        candidate_id="case-051",
                        purchase_document_ids=("doc-051",),
                        missing_core_document_count=1,
                        estimated_cost=fixture["policy"].per_document_reservation_usd,
                        audit_only_document_count=0,
                        dry_run=False,
                        missing_core_roles=("complaint",),
                    ),
                ),
                cost_per_document=fixture["policy"].per_document_reservation_usd,
                max_projected_budget=fixture["policy"].per_document_reservation_usd,
                max_missing_core_documents_per_case=1,
                dry_run=False,
                target_case_count=1,
            )
        )
        terminal_bytes = terminal_retrieval_exclusions_bytes(authority)
        with pytest.raises(
            RankedReserveReplacementError,
            match="another journal state",
        ):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=terminal_bytes,
                expected_terminal_exclusions_sha256=_sha(terminal_bytes),
                purchase_journal=journal,
                terminal_purchase_failure_authority=authority,
            )


def test_reserve_commitment_tamper_fails_before_journal_mutation(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    tampered = fixture["reserve_bytes"].replace(
        b'"reserve_rank":1', b'"reserve_rank":9'
    )

    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="reserve bytes"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=tampered,
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=_terminal_bytes("case-050"),
                expected_terminal_exclusions_sha256=_sha(_terminal_bytes("case-050")),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_result_binds_exact_successor_and_tranche_bytes(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        plan = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=evidence,
            expected_terminal_exclusions_sha256=_sha(evidence),
            purchase_journal=journal,
        )

    active = _jsonl(plan.active_selection)
    replacements = _jsonl(plan.replacement_selection)
    exclusions = _jsonl(plan.successor_exclusions)
    result = bind_ranked_reserve_outputs(
        plan,
        active_selection_bytes=active,
        replacement_selection_bytes=replacements,
        successor_exclusions_bytes=exclusions,
        replacement_budget_plan_bytes=_canonical_json(
            plan.replacement_plan.to_record()
        ),
    )

    assert result["active_selection_sha256"] == _sha(active)
    assert result["replacement_selection_sha256"] == _sha(replacements)
    assert result["successor_exclusions_sha256"] == _sha(exclusions)
    assert result["replacement_budget_plan_sha256"] == _sha(
        _canonical_json(plan.replacement_plan.to_record())
    )
    assert result["purchase_policy_sha256"] == (
        "sha256:" + fixture["policy"].policy_sha256
    )
    assert result["purchase_journal_state_sha256"].startswith("sha256:")
    assert result["successor_approval_required"] is True
    assert result["provider_activity_requested"] is False
    assert result["evaluation_authorized"] is False
    assert result["freeze_authorized"] is False
    assert result["dispatch_authorized"] is False


def test_replay_is_idempotent_and_later_terminal_reserve_uses_next_rank(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    first_evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        first = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        replay = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        second_evidence = _terminal_bytes("case-100")
        second = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=second_evidence,
            expected_terminal_exclusions_sha256=_sha(second_evidence),
            purchase_journal=journal,
        )
        replacement_event_count = len(journal.replacement_events())

    assert [row["candidate_id"] for row in first.replacement_selection] == ["case-100"]
    assert replay.replacement_selection == ()
    assert replay.active_selection == first.active_selection
    assert replay.active_candidate_ids == first.active_candidate_ids
    assert replay.successor_exclusions == first.successor_exclusions
    assert replay.successor_approval_required is False
    assert [row["candidate_id"] for row in second.replacement_selection] == ["case-101"]
    assert second.active_candidate_ids[50] == "case-101"
    assert {row["candidate_id"] for row in second.successor_exclusions} >= {
        "case-050",
        "case-100",
    }
    assert replacement_event_count == 2


def test_failed_purchase_with_response_is_not_double_reserved(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.15")
    first_evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        first = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=first_evidence,
            expected_terminal_exclusions_sha256=_sha(first_evidence),
            purchase_journal=journal,
        )
        journal.plan(first.replacement_plan)
        assert journal.submit("doc-100") is True
        journal.queue("doc-100", response={"queue_id": "queue-100"})
        journal.fail("doc-100", RuntimeError("provider failed after response"))
        operation = journal.operation_records()[0]
        assert operation["status"] == "failed"
        assert operation["response"] is not None
        assert operation["reconciliation"] is None
        assert journal.committed_amount_usd == "6.10"

        second_evidence = _terminal_bytes("case-100")
        second = plan_ranked_reserve_replacements(
            projection=fixture["projection"],
            selected_bytes=fixture["selected_bytes"],
            reserve_bytes=fixture["reserve_bytes"],
            source_pool_bytes=fixture["source_pool_bytes"],
            original_exclusions_bytes=fixture["exclusions_bytes"],
            terminal_exclusions_bytes=second_evidence,
            expected_terminal_exclusions_sha256=_sha(second_evidence),
            purchase_journal=journal,
        )

    assert [row["candidate_id"] for row in second.replacement_selection] == ["case-101"]
    assert second.committed_spend_usd == "6.10"
    assert second.reserved_replacement_spend_usd == "3.05"
    assert second.remaining_headroom_usd == "0.00"


def test_hard_cap_blocks_next_rank_before_journal_mutation(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="6.09")
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="headroom"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_multi_exclusion_cap_failure_appends_no_partial_event(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, hard_cap_usd="9.14")
    evidence = _jsonl((_terminal_record("case-050"), _terminal_record("case-051")))
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        with pytest.raises(RankedReserveReplacementError, match="headroom"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert journal.replacement_events() == ()


def test_incompatible_replacement_history_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    evidence = _terminal_bytes("case-050")
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ) as journal:
        journal.append_replacement_event(
            "legacy-clearance-event",
            {"schema_version": "legalforecast.clearance_replacement_event.v1"},
        )
        with pytest.raises(RankedReserveReplacementError, match="incompatible"):
            plan_ranked_reserve_replacements(
                projection=fixture["projection"],
                selected_bytes=fixture["selected_bytes"],
                reserve_bytes=fixture["reserve_bytes"],
                source_pool_bytes=fixture["source_pool_bytes"],
                original_exclusions_bytes=fixture["exclusions_bytes"],
                terminal_exclusions_bytes=evidence,
                expected_terminal_exclusions_sha256=_sha(evidence),
                purchase_journal=journal,
            )
        assert len(journal.replacement_events()) == 1


def test_cli_replays_full_projection_and_emits_provider_free_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    target_root = tmp_path / "target"
    summary_path = target_root / "target-cohort-projection.json"
    selection_path = target_root / "target-cohort-selection.jsonl"
    reserve_path = target_root / "target-cohort-ranked-reserve.jsonl"
    exclusions_path = target_root / "target-cohort-exclusions.jsonl"
    source_path = Path("/frozen/public-packet-selection-reconciled.jsonl")
    verified_bytes = {
        str(summary_path.resolve()): _canonical_json(fixture["projection"]),
        str(selection_path.resolve()): fixture["selected_bytes"],
        str(reserve_path.resolve()): fixture["reserve_bytes"],
        str(exclusions_path.resolve()): fixture["exclusions_bytes"],
        str(source_path): fixture["source_pool_bytes"],
    }

    def verified_projection(_root: Path) -> dict[str, object]:
        return {
            "summary": fixture["projection"],
            "summary_path": summary_path,
            "selection_path": selection_path,
            "verified_artifact_bytes": verified_bytes,
        }

    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        verified_projection,
    )
    terminal = _terminal_bytes("case-050")
    terminal_path = tmp_path / "terminal.jsonl"
    terminal_path.write_bytes(terminal)
    digest_path = tmp_path / "terminal.sha256"
    digest_path.write_text(_sha(terminal) + "\n")
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_canonical_json(dict(fixture["policy"].artifact)))
    receipt_path = tmp_path / "initialization.json"
    receipt_path.write_text("{}\n")
    controlled_private_root = tmp_path / "private"
    controlled_private_root.mkdir()
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ):
        pass
    outputs = {
        "result": tmp_path / "result.json",
        "active": tmp_path / "active.jsonl",
        "replacement": tmp_path / "replacement.jsonl",
        "exclusions": tmp_path / "successor-exclusions.jsonl",
        "budget": tmp_path / "budget.json",
    }

    command = [
        "acquisition",
        "plan-ranked-reserve-replacements",
        "--target-cohort-root",
        str(target_root),
        "--purchase-policy",
        str(policy_path),
        "--controlled-private-root",
        str(controlled_private_root),
        "--purchase-ledger",
        str(fixture["policy"].canonical_ledger_path),
        "--purchase-ledger-initialization-receipt",
        str(receipt_path),
        "--terminal-exclusions",
        str(terminal_path),
        "--terminal-exclusions-sha256-file",
        str(digest_path),
        "--output",
        str(outputs["result"]),
        "--active-selection-output",
        str(outputs["active"]),
        "--replacement-selection-output",
        str(outputs["replacement"]),
        "--successor-exclusions-output",
        str(outputs["exclusions"]),
        "--replacement-budget-plan-output",
        str(outputs["budget"]),
    ]
    status = cli.main(command)

    assert status == 0
    result = json.loads(outputs["result"].read_bytes())
    artifact_commitments = (
        ("active", "active_selection_sha256"),
        ("replacement", "replacement_selection_sha256"),
        ("exclusions", "successor_exclusions_sha256"),
        ("budget", "replacement_budget_plan_sha256"),
    )
    for artifact_name, commitment_name in artifact_commitments:
        assert _sha(outputs[artifact_name].read_bytes()) == result[commitment_name]
    assert result["active_case_count"] == 100
    assert result["successor_approval_required"] is True
    assert result["provider_activity_requested"] is False
    assert json.loads(capsys.readouterr().out)["paid_activity_executed"] is False

    original_outputs = {name: path.read_bytes() for name, path in outputs.items()}
    replay_status = cli.main(command)
    replay_console = capsys.readouterr()

    assert replay_status == 2
    assert "immutable output differs" in replay_console.err
    replayed_outputs = {name: path.read_bytes() for name, path in outputs.items()}
    assert replayed_outputs == original_outputs


def test_cli_derives_mixed_terminal_partition_and_publishes_99_case_precursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(
        tmp_path,
        hard_cap_usd="24.40",
        reserve_document_counts=(3, 4, 4, 4, 4),
    )
    target_root = tmp_path / "target"
    summary_path = target_root / "target-cohort-projection.json"
    selection_path = target_root / "target-cohort-selection.jsonl"
    reserve_path = target_root / "target-cohort-ranked-reserve.jsonl"
    exclusions_path = target_root / "target-cohort-exclusions.jsonl"
    source_path = Path("/frozen/public-packet-selection-reconciled.jsonl")
    verified_bytes = {
        str(summary_path.resolve()): _canonical_json(fixture["projection"]),
        str(selection_path.resolve()): fixture["selected_bytes"],
        str(reserve_path.resolve()): fixture["reserve_bytes"],
        str(exclusions_path.resolve()): fixture["exclusions_bytes"],
        str(source_path): fixture["source_pool_bytes"],
    }
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "summary": fixture["projection"],
            "summary_path": summary_path,
            "selection_path": selection_path,
            "verified_artifact_bytes": verified_bytes,
        },
    )
    terminal_records = {
        candidate_id: {
            **_terminal_record(candidate_id),
            "reason": "terminal_courtlistener_recap_fetch_provider_error",
            "source_stage": "purchase-missing-recap-fetch",
        }
        for candidate_id in ("case-050", "case-051", "case-052")
    }
    terminal_bytes = _jsonl(tuple(terminal_records.values()))
    disposition = object.__new__(VerifiedTerminalPurchaseDispositionAuthority)
    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_residual_terminal_records",
        lambda authority, *, purchase_journal: terminal_records,
    )
    monkeypatch.setattr(
        ranked_reserve_module,
        "verified_terminal_purchase_disposition_record",
        lambda authority, *, purchase_journal: _disposition_record(
            residual_sha256=_sha(terminal_bytes)
        ),
    )
    monkeypatch.setattr(
        cli,
        "_verify_materializer_docket_decision_authority",
        lambda **_kwargs: SimpleNamespace(
            authority=disposition,
            source_snapshots={},
        ),
    )
    monkeypatch.setattr(
        cli,
        "residual_terminal_exclusions_bytes",
        lambda authority, *, purchase_journal: terminal_bytes,
    )
    monkeypatch.setattr(
        cli,
        "_replay_materialized_docket_decision_authority",
        lambda descriptor: (descriptor.authority, ()),
    )

    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_bytes(_canonical_json(dict(fixture["policy"].artifact)))
    receipt_path = tmp_path / "initialization.json"
    receipt_path.write_text("{}\n")
    controlled_private_root = tmp_path / "private"
    controlled_private_root.mkdir()
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
        allow_create=True,
    ):
        pass
    freshness_checks = 0
    reject_stale = True
    mutate_during_planning = False

    def require_fresh_before_mutation(
        snapshots: Mapping[Path, bytes], *, label: str
    ) -> None:
        nonlocal freshness_checks, reject_stale
        freshness_checks += 1
        if reject_stale:
            raise RankedReserveReplacementError("simulated stale terminal evidence")
        for path, expected in snapshots.items():
            if path.read_bytes() != expected:
                raise RankedReserveReplacementError(
                    "simulated concurrent terminal evidence mutation"
                )

    monkeypatch.setattr(
        cli, "_require_snapshot_unchanged", require_fresh_before_mutation
    )
    original_planner = cli.plan_ranked_reserve_replacements

    def assert_freshness_precedes_planner(**kwargs: object) -> object:
        assert freshness_checks == 1
        journal = cast(CaseDevPurchaseJournal, kwargs["purchase_journal"])
        assert journal.replacement_events() == ()
        if mutate_during_planning:
            purchase_result.write_text('{"tampered":true}\n')
        return original_planner(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        cli, "plan_ranked_reserve_replacements", assert_freshness_precedes_planner
    )
    purchase_result = tmp_path / "purchase-result.json"
    purchase_run_card = tmp_path / "purchase-run-card.json"
    snapshot_manifest = tmp_path / "snapshot" / "manifest.json"
    snapshot_manifest.parent.mkdir()
    for path in (purchase_result, purchase_run_card, snapshot_manifest):
        path.write_text("{}\n")
    outputs = {
        "result": tmp_path / "result.json",
        "active": tmp_path / "active.jsonl",
        "replacement": tmp_path / "replacement.jsonl",
        "exclusions": tmp_path / "successor-exclusions.jsonl",
        "budget": tmp_path / "budget.json",
    }
    command = [
        "acquisition",
        "plan-ranked-reserve-replacements",
        "--target-cohort-root",
        str(target_root),
        "--purchase-policy",
        str(policy_path),
        "--controlled-private-root",
        str(controlled_private_root),
        "--purchase-ledger",
        str(fixture["policy"].canonical_ledger_path),
        "--purchase-ledger-initialization-receipt",
        str(receipt_path),
        "--purchase-result",
        str(purchase_result),
        "--purchase-run-card",
        str(purchase_run_card),
        "--screening-snapshot-manifest",
        str(snapshot_manifest),
        "--output",
        str(outputs["result"]),
        "--active-selection-output",
        str(outputs["active"]),
        "--replacement-selection-output",
        str(outputs["replacement"]),
        "--successor-exclusions-output",
        str(outputs["exclusions"]),
        "--replacement-budget-plan-output",
        str(outputs["budget"]),
    ]
    assert cli.main(command) == 2
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
    ) as observer:
        assert observer.replacement_events() == ()
    assert not any(path.exists() for path in outputs.values())

    reject_stale = False
    freshness_checks = 0
    mutate_during_planning = True
    assert cli.main(command) == 2
    with CaseDevPurchaseJournal(
        fixture["policy"].canonical_ledger_path,
        policy=fixture["policy"],
    ) as observer:
        assert observer.replacement_events() == ()
    assert not any(path.exists() for path in outputs.values())

    purchase_result.write_text("{}\n")
    freshness_checks = 0
    mutate_during_planning = False
    status = cli.main(command)

    assert status == 0
    result = json.loads(outputs["result"].read_bytes())
    assert result["active_case_count"] == 99
    assert result["replacement_case_count"] == 2
    assert result["reserved_replacement_spend_usd"] == "21.35"
    assert result["remaining_headroom_usd"] == "0.00"
    assert result["schema_version"] == (
        "legalforecast.ranked_reserve_replacement_result.v2"
    )
    assert result["terminal_disposition"]["partition_exhaustive"] is True
    assert result["terminal_disposition_sha256"].startswith("sha256:")
    assert freshness_checks == 3
    assert [
        json.loads(line)["candidate_id"]
        for line in outputs["replacement"].read_text().splitlines()
    ] == ["case-100", "case-101"]


def test_cli_requires_one_complete_terminal_evidence_mode(tmp_path: Path) -> None:
    status = cli.main(
        [
            "acquisition",
            "plan-ranked-reserve-replacements",
            "--target-cohort-root",
            str(tmp_path / "target"),
            "--purchase-policy",
            str(tmp_path / "policy.json"),
            "--controlled-private-root",
            str(tmp_path / "private"),
            "--purchase-ledger",
            str(tmp_path / "ledger.sqlite3"),
            "--purchase-ledger-initialization-receipt",
            str(tmp_path / "receipt.json"),
            "--purchase-result",
            str(tmp_path / "result.json"),
            "--output",
            str(tmp_path / "output.json"),
            "--active-selection-output",
            str(tmp_path / "active.jsonl"),
            "--replacement-selection-output",
            str(tmp_path / "replacement.jsonl"),
            "--successor-exclusions-output",
            str(tmp_path / "exclusions.jsonl"),
            "--replacement-budget-plan-output",
            str(tmp_path / "budget.json"),
        ]
    )

    assert status == 2


def test_v4_continuation_template_has_no_paid_or_downstream_stage() -> None:
    template_path = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.v4-ranked-reserve-replacement-plan.template.json"
    )
    template = json.loads(template_path.read_bytes())

    assert template["schema_version"] == (
        "legalforecast.ranked_reserve_replacement_plan_template.v1"
    )
    assert template["command"]["name"] == "plan-ranked-reserve-replacements"
    assert template["command"]["boundary"] == "provider_free"
    arguments = template["command"]["arguments"]
    assert "--purchase-result" in arguments
    assert "--purchase-run-card" in arguments
    assert "--screening-snapshot-manifest" in arguments
    assert "--terminal-exclusions" not in arguments
    assert template["authority"] == {
        "dispatch_authorized": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "paid_activity_executed": False,
        "paid_activity_requested": False,
        "paid_replacement_requires_separate_successor_approval": True,
        "provider_activity_requested": False,
    }


class _Fixture(TypedDict):
    policy: CaseDevPurchasePolicy
    projection: dict[str, object]
    selected_bytes: bytes
    reserve_bytes: bytes
    source_pool_bytes: bytes
    exclusions_bytes: bytes


def _fixture(
    tmp_path: Path,
    *,
    hard_cap_usd: str = "6.10",
    reserve_document_counts: tuple[int, int, int, int, int] = (1, 1, 1, 1, 1),
) -> _Fixture:
    selected = tuple(_selection(index) for index in range(100))
    reserves = tuple(
        _reserve(index, document_count=document_count)
        for index, document_count in zip(
            range(100, 105), reserve_document_counts, strict=True
        )
    )
    source_pool = tuple(_selection(index) for index in range(105))
    exclusions = tuple(_omission(index) for index in range(100, 105))
    selected_bytes = _jsonl(selected)
    reserve_bytes = _jsonl(reserves)
    source_pool_bytes = _jsonl(source_pool)
    exclusions_bytes = _jsonl(exclusions)
    policy_artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "cycle-v4-ranked-reserve-test",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str((tmp_path / "purchase.sqlite3").resolve()),
            "hard_cap_usd": hard_cap_usd,
            "opening_committed_spend_usd": "3.05",
            "opening_case_committed_spend_usd": {"historical": "3.05"},
            "max_per_case_usd": hard_cap_usd,
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-08-04T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    policy = verify_case_dev_purchase_policy(policy_artifact)
    projection: dict[str, object] = {
        "schema_version": "legalforecast.target_cohort_projection.v1",
        "projection_sha256": "sha256:" + "1" * 64,
        "resolved_pool_case_count": 105,
        "post_clearance_case_count": 105,
        "selected_case_count": 100,
        "ranked_reserve_case_count": 5,
        "selected_candidate_ids_sha256": _canonical_sha(
            [row["candidate_id"] for row in selected]
        ),
        "ranked_reserve_candidate_ids_sha256": _canonical_sha(
            [row["candidate_id"] for row in reserves]
        ),
        "ranked_reserve_sha256": _canonical_sha(reserves),
        "output_commitments": {
            "target-cohort-selection.jsonl": _sha(selected_bytes),
            "target-cohort-ranked-reserve.jsonl": _sha(reserve_bytes),
            "target-cohort-exclusions.jsonl": _sha(exclusions_bytes),
        },
        "input_commitments": {
            "/frozen/public-packet-selection-reconciled.jsonl": _sha(source_pool_bytes)
        },
    }
    return {
        "policy": policy,
        "projection": projection,
        "selected_bytes": selected_bytes,
        "reserve_bytes": reserve_bytes,
        "source_pool_bytes": source_pool_bytes,
        "exclusions_bytes": exclusions_bytes,
    }


def _selection(index: int) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": "2026-07-01",
        "documents": [],
    }


def _reserve(index: int, *, document_count: int = 1) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    rank = index - 99
    document_ids = (
        [f"doc-{index:03d}"]
        if document_count == 1
        else [f"doc-{index:03d}-{offset}" for offset in range(document_count)]
    )
    estimated_cost = f"{document_count * 3.05:.2f}"
    return {
        "schema_version": "legalforecast.target_cohort_ranked_reserve.v1",
        "reserve_rank": rank,
        "frontier_rank": 100 + rank,
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": "2026-07-01",
        "missing_core_document_count": document_count,
        "missing_core_roles": ["complaint"],
        "purchase_document_ids": document_ids,
        "estimated_cost_usd": estimated_cost,
        "ranking_key": [document_count, estimated_cost, candidate_id],
    }


def _omission(index: int) -> dict[str, object]:
    candidate_id = f"case-{index:03d}"
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": "court-a",
        "decision_date": None,
        "notes": (
            "Candidate was outside the deterministic cheapest exact-cohort prefix."
        ),
        "primary_exclusion_reason": "target_cohort_frontier_omitted",
        "reason": "target_cohort_frontier_omitted",
        "related_family_id": None,
        "secondary_exclusion_reasons": [],
        "source_document_ids": [],
        "source_entry_ids": [],
        "stage": "extraction",
    }


def _disposition_record(
    *,
    residual_sha256: str,
    purchase_journal_state_sha256: str = "sha256:" + "3" * 64,
) -> dict[str, object]:
    terminal_pairs = [
        {"candidate_id": f"case-{index:03d}", "source_document_id": f"doc-{index:03d}"}
        for index in range(50, 53)
    ]
    return {
        "schema_version": "legalforecast.terminal_purchase_disposition.v1",
        "purchase_result_sha256": "sha256:" + "1" * 64,
        "purchase_run_card_sha256": "sha256:" + "2" * 64,
        "purchase_journal_state_sha256": purchase_journal_state_sha256,
        "selection_payload_sha256": "sha256:" + "4" * 64,
        "snapshot_manifest_sha256": "sha256:" + "5" * 64,
        "terminal_candidate_count": 3,
        "terminal_failure_pair_count": 3,
        "terminal_failure_pairs": terminal_pairs,
        "docket_retained_candidate_count": 0,
        "docket_retained_failure_pair_count": 0,
        "docket_retained_failure_pairs": [],
        "docket_decision_sources_sha256": "sha256:" + "6" * 64,
        "residual_candidate_count": 3,
        "residual_failure_pair_count": 3,
        "residual_failure_pairs": terminal_pairs,
        "residual_terminal_exclusions_sha256": residual_sha256,
        "partition_disjoint": True,
        "partition_exhaustive": True,
        "model_visible": False,
        "audit_only": True,
    }


def _terminal_record(candidate_id: str) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.ranked_reserve_terminal_exclusion.v1",
        "candidate_id": candidate_id,
        "reason": "stage_a_boundary_unresolvable",
        "source_stage": "apply-unitization-review",
        "source_artifact_sha256": "sha256:" + "2" * 64,
        "source_record_sha256": "sha256:" + "3" * 64,
        "terminal": True,
        "retryable": False,
    }


def _terminal_bytes(candidate_id: str) -> bytes:
    return _jsonl((_terminal_record(candidate_id),))


def _terminal_purchase_artifacts(
    journal: CaseDevPurchaseJournal,
    *,
    candidate_id: str,
    document_id: str,
    queue_status: int,
    result_path: Path,
    terminal: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    plan = MissingCoreBudgetPlan(
        case_plans=(_case_purchase_plan(candidate_id, document_id, journal),),
        cost_per_document=journal.policy.per_document_reservation_usd,
        max_projected_budget=journal.policy.per_document_reservation_usd,
        max_missing_core_documents_per_case=1,
        dry_run=False,
        target_case_count=1,
    )
    budget_plan_path = result_path.with_name("purchase-budget-plan.json")
    budget_plan_path.write_bytes(_canonical_json(plan.to_record()))
    journal.plan(plan)
    assert journal.submit(document_id)
    journal.queue(
        document_id,
        response={
            "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            "reservation_usd": (f"{journal.policy.per_document_reservation_usd:.2f}"),
            "queue_id": "77",
            "reservation_id": "reservation-1",
        },
    )
    if terminal:
        journal.fail(
            document_id,
            CourtListenerRecapFetchError(
                f"RECAP Fetch terminal queue status {queue_status}"
            ),
        )
        attempt_status = CaseDevPacerPurchaseStatus.PROVIDER_ERROR.value
        attempt_reason = f"recap_fetch_status_{queue_status}"
    else:
        attempt_status = CaseDevPacerPurchaseStatus.NOT_ATTEMPTED.value
        attempt_reason = f"recap_fetch_queued_status_{queue_status}"
    result: dict[str, object] = {
        "live": True,
        "acknowledge_pacer_fees": True,
        "capability": "document_level_purchase",
        "dry_run": False,
        "projected_cost_usd": "3.05",
        "max_projected_budget_usd": "3.05",
        "intended_purchase_count": 1,
        "executed_purchase_count": 0,
        "quarantined_material_count": 0,
        "completed_purchase_count": 0,
        "attempts": [
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": attempt_status,
                "reason": attempt_reason,
                "fee_acknowledged": None,
                "pacer_fees": None,
                "download_url": None,
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            }
        ],
    }
    run_card: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "purchase-missing-recap-fetch",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "resume": False,
        "record_count": 1,
        "input_paths": [str(budget_plan_path), "/frozen/selection.jsonl"],
        "output_paths": [
            str(result_path),
            str(journal.policy.canonical_ledger_path),
        ],
        "paid_activity_requested": True,
        "paid_activity_executed": True,
        "generated_at": "2026-08-05T00:00:00Z",
        "executed_purchase_count": 0,
        "quarantined_material_count": 0,
        "completed_purchase_count": 0,
        "courtlistener_live": True,
        "courtlistener_physical_requests": 2,
        "courtlistener_rate_profile": "authenticated",
        "courtlistener_request_budget_max_wait_seconds": 3700.0,
        "courtlistener_request_ledger": "/private/request-ledger.sqlite3",
        "courtlistener_reservations_this_phase": 2,
        "courtlistener_reservations_total": 2,
        "courtlistener_limits": {
            "per_minute": 50,
            "per_hour": 500,
            "per_day": 1400,
        },
    }
    return result, run_card


def _case_purchase_plan(
    candidate_id: str,
    document_id: str,
    journal: CaseDevPurchaseJournal,
) -> CaseMissingCorePurchasePlan:
    return CaseMissingCorePurchasePlan(
        candidate_id=candidate_id,
        purchase_document_ids=(document_id,),
        missing_core_document_count=1,
        estimated_cost=journal.policy.per_document_reservation_usd,
        audit_only_document_count=0,
        dry_run=False,
        missing_core_roles=("complaint",),
    )


def _write_purchase_artifacts(
    result_path: Path,
    *,
    result: Mapping[str, object],
    run_card: Mapping[str, object],
) -> Path:
    result_path.write_bytes(_canonical_json(result))
    result_path.with_name("purchase-run-card.json").write_bytes(
        _canonical_json(run_card)
    )
    return result_path


def _jsonl(records: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(
        json.dumps(
            record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
        + b"\n"
        for record in records
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return _sha(payload)


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode() + b"\n"
    )

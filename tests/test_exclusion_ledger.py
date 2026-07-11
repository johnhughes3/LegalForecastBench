from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from legalforecast.selection.contamination_filters import (
    LeakageSource,
    LeakageSourceKind,
    detect_outcome_leakage,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedger,
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
    merge_exclusion_ledger_records,
)


def test_exclusion_entry_records_primary_reason_and_auditable_context() -> None:
    entry = ExclusionLedgerEntry(
        candidate_id="cand-1",
        case_id="case-1",
        court="S.D.N.Y.",
        decision_date=date(2026, 5, 14),
        stage=ExclusionStage.RETRIEVAL,
        reason=ExclusionReason.MISSING_CORE_FILING.value,
        secondary_reasons=(ExclusionReason.INSUFFICIENT_TEXT_QUALITY.value,),
        source_entry_ids=("entry-12",),
        source_document_ids=("doc-12",),
        notes="Missing opposition and motion text is below quality threshold.",
    )

    record = entry.to_record()

    assert record["primary_exclusion_reason"] == "missing_core_filing"
    assert record["secondary_exclusion_reasons"] == ["insufficient_text_quality"]
    assert record["court"] == "S.D.N.Y."
    assert record["decision_date"] == "2026-05-14"
    assert record["source_entry_ids"] == ["entry-12"]
    assert record["source_document_ids"] == ["doc-12"]
    json.dumps(record)


def test_ledger_enforces_one_primary_entry_per_excluded_candidate() -> None:
    entry = _entry("cand-duplicate", ExclusionReason.AMBIGUOUS_ORDER)

    with pytest.raises(ValueError, match="exactly one primary"):
        ExclusionLedger((entry, entry))


def test_ledger_exports_jsonl_records(tmp_path) -> None:
    ledger = ExclusionLedger(
        (
            _entry("cand-missing", ExclusionReason.MISSING_CORE_FILING),
            _entry(
                "cand-related",
                ExclusionReason.DUPLICATE_RELATED_CASE_INFLATION,
                related_family_id="family-1",
            ),
        )
    )

    output_path = ledger.write_jsonl(tmp_path / "exclusion-ledger.jsonl")
    lines = output_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]

    assert [record["candidate_id"] for record in records] == [
        "cand-missing",
        "cand-related",
    ]
    assert records[1]["related_family_id"] == "family-1"


@pytest.mark.parametrize(
    "reason",
    [
        ExclusionReason.AMBIGUOUS_MOTION_TO_ORDER_LINKAGE,
        ExclusionReason.MISSING_CORE_FILING,
        ExclusionReason.AMBIGUOUS_ORDER,
        ExclusionReason.OUTCOME_LEAKAGE,
        ExclusionReason.DUPLICATE_RELATED_CASE_INFLATION,
        ExclusionReason.INSUFFICIENT_TEXT_QUALITY,
        ExclusionReason.CONFLICT_OF_INTEREST,
    ],
)
def test_required_exclusion_reasons_are_first_class(reason: ExclusionReason) -> None:
    entry = _entry(f"cand-{reason.value}", reason)

    assert entry.primary_exclusion_reason == reason.value


def test_outcome_leakage_filter_converts_to_primary_ledger_entry() -> None:
    leakage = detect_outcome_leakage(
        (
            LeakageSource(
                source_id="entry-44",
                source_kind=LeakageSourceKind.DOCKET_ENTRY,
                text="Minute order granting the motion to dismiss.",
                observed_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
                related_family_id="family-1",
            ),
        ),
        evaluation_timestamp=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )

    entry = ExclusionLedgerEntry.from_outcome_leakage(
        candidate_id="cand-leak",
        case_id="case-leak",
        court="D. Del.",
        decision_date=date(2026, 5, 13),
        leakage_result=leakage,
    )

    assert entry.reason == ExclusionReason.OUTCOME_LEAKAGE.value
    assert entry.stage is ExclusionStage.LEAKAGE
    assert entry.source_entry_ids == ("entry-44",)
    assert entry.related_family_id == "family-1"
    assert entry.secondary_reasons == ("minute_order_resolving_target",)


def test_conflict_of_interest_exclusion_is_auditable_without_private_detail() -> None:
    entry = ExclusionLedgerEntry(
        candidate_id="cand-recusal",
        case_id="case-recusal",
        court="D.D.C.",
        stage=ExclusionStage.ELIGIBILITY,
        reason=ExclusionReason.CONFLICT_OF_INTEREST.value,
        source_entry_ids=("entry-1",),
        notes="Maintainer recusal or conflict policy exclusion; no merits detail.",
    )

    record = entry.to_record()

    assert record["primary_exclusion_reason"] == "conflict_of_interest"
    assert record["stage"] == "eligibility"
    assert "recusal" in record["notes"]


def test_merge_exclusion_ledger_records_consolidates_split_stage_artifacts() -> None:
    ledger = merge_exclusion_ledger_records(
        (
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "selected": False,
                "exclusion_reasons": ["no_free_decision_document"],
            },
        ),
        (
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "stage": "llm-label",
                "status": "failed",
                "error_type": "FrozenUnitWorkflowRequiredError",
                "error_message": "decision contains a material missing unit",
                "exclusion_ledger_entries": [
                    {
                        "candidate_id": "cand-1",
                        "case_id": "case-1",
                        "stage": "labeling",
                        "reason": "unit_missing_from_stage_a",
                        "source_entry_ids": ["entry-9"],
                        "source_document_ids": ["decision-1"],
                        "notes": "Stage B found a material unit absent from Stage A.",
                    }
                ],
            },
        ),
    )

    assert len(ledger.entries) == 1
    record = ledger.entries[0].to_record()
    assert record["primary_exclusion_reason"] == "no_free_decision_document"
    assert record["secondary_exclusion_reasons"] == ["unit_missing_from_stage_a"]
    assert record["source_entry_ids"] == ["entry-9"]
    assert record["source_document_ids"] == ["decision-1"]
    assert "material unit absent" in record["notes"]


def test_merge_exclusion_ledger_records_records_unselected_overflow() -> None:
    ledger = merge_exclusion_ledger_records(
        (
            {
                "candidate_id": "cand-overflow",
                "case_id": "case-overflow",
                "selected": False,
                "exclusion_reasons": [],
            },
        )
    )

    assert ledger.entries[0].reason == "target_clean_case_cap_reached"


def test_merge_exclusion_ledger_records_normalizes_parser_failures() -> None:
    ledger = merge_exclusion_ledger_records(
        (
            {
                "candidate_id": "cand-parse",
                "source_document_id": "doc-bad",
                "status": "timed_out",
                "error_message": "parser timed out",
            },
        )
    )

    entry = ledger.entries[0]
    assert entry.stage is ExclusionStage.EXTRACTION
    assert entry.reason == ExclusionReason.PARSE_ERROR.value
    assert entry.source_document_ids == ("doc-bad",)


def test_merge_exclusion_ledger_records_normalizes_pending_adjudication() -> None:
    ledger = merge_exclusion_ledger_records(
        (
            {
                "candidate_id": "cand-review",
                "status": "pending_adjudication",
            },
        )
    )

    entry = ledger.entries[0]
    assert entry.stage is ExclusionStage.LABELING
    assert entry.reason == ExclusionReason.ADJUDICATION_PENDING.value


def test_merge_exclusion_ledger_records_falls_back_after_empty_nested_entries() -> None:
    ledger = merge_exclusion_ledger_records(
        (
            {
                "candidate_id": "cand-label-failure",
                "case_id": "case-label-failure",
                "stage": "llm-label",
                "status": "failed",
                "error_type": "TimeoutError",
                "error_message": "judge response timed out",
                "exclusion_ledger_entries": [],
            },
        )
    )

    entry = ledger.entries[0]
    assert entry.stage is ExclusionStage.LABELING
    assert entry.reason == "timeout_error"
    assert entry.notes == "judge response timed out"


def _entry(
    candidate_id: str,
    reason: ExclusionReason,
    *,
    related_family_id: str | None = None,
) -> ExclusionLedgerEntry:
    return ExclusionLedgerEntry(
        candidate_id=candidate_id,
        case_id=f"case-{candidate_id}",
        stage=ExclusionStage.ELIGIBILITY,
        reason=reason.value,
        source_entry_ids=(f"entry-{candidate_id}",),
        notes=f"Excluded for {reason.value}.",
        related_family_id=related_family_id,
    )

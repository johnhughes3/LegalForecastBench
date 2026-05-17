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

from __future__ import annotations

from legalforecast.ingestion.case_dev_scheduling import (
    case_dev_enrichment_schedule_key,
)


def _record(
    *matched_terms: str,
    decision_evidence: object | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {"matched_terms": list(matched_terms)}
    if decision_evidence is not None:
        record["source_lineage"] = {
            "lead_commitment": {"decision_entry_evidence": decision_evidence}
        }
    return record


def test_case_dev_schedule_prioritizes_exact_and_decision_signals() -> None:
    generic_mtd = _record('"motion to dismiss"')
    generic_rule_12 = _record('("Rule 12(b)(6)" OR "12(b)(6)")')
    order = _record('"order on motion to dismiss"')
    resolution = _record('"motion to dismiss" AND granted')
    exact = _record(
        '"motion to dismiss"',
        decision_evidence={
            "description": "ORDER granting motion to dismiss",
            "entry_date_filed": "2026-07-15",
        },
    )
    exact_generic = _record(
        '"motion to dismiss"',
        decision_evidence={
            "description": "Motion to Dismiss Case, Notice of Hearing",
            "entry_date_filed": "2026-07-15",
        },
    )

    scheduled = sorted(
        enumerate(
            (
                generic_mtd,
                generic_rule_12,
                order,
                resolution,
                exact_generic,
                exact,
            )
        ),
        key=lambda item: case_dev_enrichment_schedule_key(
            input_index=item[0], record=item[1]
        ),
    )

    assert [input_index for input_index, _record in scheduled] == [5, 4, 2, 3, 0, 1]


def test_case_dev_schedule_uses_source_hit_terms_and_stable_input_tie_break() -> None:
    first = {
        "matched_terms": [],
        "source_lineage": {
            "lead_commitment": {"decision_entry_evidence": None},
            "source_hits": [
                {
                    "query_term": '"dismissing amended complaint" AND order',
                }
            ],
        },
    }
    second = _record('"dismissing adversary complaint" AND order')

    assert case_dev_enrichment_schedule_key(
        input_index=7, record=first
    ) < case_dev_enrichment_schedule_key(input_index=8, record=second)

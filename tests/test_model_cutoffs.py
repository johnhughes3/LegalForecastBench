from __future__ import annotations

from datetime import date

import pytest
from legalforecast.reporting.model_cutoffs import (
    CutoffEvidence,
    cutoff_eligibility,
    evidence_for,
    load_cutoffs,
)

FIRST_DECISION = date(2026, 6, 30)


def _evidence(cutoff: str | None) -> CutoffEvidence:
    return CutoffEvidence(slug="m", model_ids=("m",), cutoff=cutoff, kind="knowledge")


def test_month_cutoff_in_or_before_the_decision_month_is_eligible() -> None:
    assert _evidence("2026-05").comparison_date == date(2026, 5, 1)
    assert (
        cutoff_eligibility(_evidence("2026-05"), first_decision=FIRST_DECISION)[0]
        == "eligible"
    )
    # Same month as the first decision (June 30): treated as preceding it.
    assert (
        cutoff_eligibility(_evidence("2026-06"), first_decision=FIRST_DECISION)[0]
        == "eligible"
    )
    assert cutoff_eligibility(_evidence("2026-07"), first_decision=FIRST_DECISION) == (
        "qualified",
        "reported_cutoff_overlaps_decisions",
    )


def test_exact_cutoff_must_strictly_precede_the_first_decision() -> None:
    assert (
        cutoff_eligibility(_evidence("2026-06-29"), first_decision=FIRST_DECISION)[0]
        == "eligible"
    )
    assert (
        cutoff_eligibility(_evidence("2026-06-30"), first_decision=FIRST_DECISION)[0]
        == "qualified"
    )


def test_missing_cutoff_is_qualified() -> None:
    assert cutoff_eligibility(_evidence(None), first_decision=FIRST_DECISION) == (
        "qualified",
        "cutoff_not_published",
    )


def test_table_loads_and_resolves_model_ids() -> None:
    entries = load_cutoffs()
    assert len({entry.slug for entry in entries}) == len(entries)
    grok = evidence_for("spacexai/grok-4.6")
    assert grok is not None and grok.slug == "grok-4-6"
    assert evidence_for("not-a-model") is None


def test_malformed_cutoff_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported cutoff format"):
        _ = _evidence("2026").comparison_date


def test_month_only_cutoff_exports_without_a_date_field() -> None:
    evidence = evidence_for("spacexai/grok-4.7")
    assert evidence is not None and evidence.cutoff == "2026-05"
    # Month precision is kept in the table; only exact days fit the date field.
    assert evidence.exact_date is None

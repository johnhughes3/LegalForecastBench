from __future__ import annotations

from datetime import date

import pytest
from legalforecast.publication.model_cutoffs import (
    CutoffEvidence,
    cutoff_eligibility,
    evidence_for,
    load_cutoffs,
)

FIRST_DECISION = date(2026, 6, 30)


def _evidence(cutoff: str | None) -> CutoffEvidence:
    return CutoffEvidence(slug="m", model_ids=("m",), cutoff=cutoff, kind="knowledge")


def test_month_cutoff_counts_as_its_last_day() -> None:
    assert _evidence("2026-05").last_day == date(2026, 5, 31)
    assert cutoff_eligibility(_evidence("2026-05"), first_decision=FIRST_DECISION) == (
        "eligible",
        "reported_cutoff_predates_decisions",
    )
    # June 2026 could be June 30, the first decision date, so it is qualified.
    assert cutoff_eligibility(_evidence("2026-06"), first_decision=FIRST_DECISION) == (
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
        _ = _evidence("2026").last_day

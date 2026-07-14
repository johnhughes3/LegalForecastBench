"""Frozen decision-first RECAP vocabulary shared by transport implementations."""

from __future__ import annotations

DECISION_FIRST_RECAP_SEARCH_TERMS: tuple[str, ...] = (
    'order AND granting AND "motion to dismiss"',
    'order AND denying AND "motion to dismiss"',
    '"motion to dismiss" AND "granted in part"',
    '"order on motion to dismiss"',
    '"memorandum opinion" AND "motion to dismiss"',
    '"report and recommendation" AND "motion to dismiss"',
    'order AND (granting OR denying) AND "judgment on the pleadings"',
    'order AND (granting OR denying) AND "12(b)(6)"',
)

"""Maintained provider cutoff evidence for comparison eligibility.

Frozen model registries record a training cutoff only when a provider states an
exact training-data date, so knowledge cutoffs and month-only statements stay
"unknown" there. The owner's rule (2026-09-28): a model is eligible when its
provider-reported training-data or knowledge cutoff falls before the earliest
scored decision. A month-only cutoff is compared as the first day of that
month, because ingesting a decision on the day it issued is implausible. The
maintained table, ``legalforecast/data/model_cutoffs.json``, is read here and by
the website; frozen registries are not rewritten.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib import resources
from typing import Literal

Eligibility = Literal["eligible", "qualified"]


@dataclass(frozen=True, slots=True)
class CutoffEvidence:
    """One model's reported cutoff; ``cutoff`` is YYYY-MM-DD, YYYY-MM, or None."""

    slug: str
    model_ids: tuple[str, ...]
    cutoff: str | None
    kind: str | None

    @property
    def comparison_date(self) -> date | None:
        """The date compared with the first decision (a month is its first day)."""
        if self.cutoff is None:
            return None
        parts = [int(part) for part in self.cutoff.split("-")]
        if len(parts) == 3:
            return date(parts[0], parts[1], parts[2])
        if len(parts) == 2:
            return date(parts[0], parts[1], 1)
        raise ValueError(f"unsupported cutoff format {self.cutoff!r} for {self.slug}")

    @property
    def exact_date(self) -> date | None:
        """The cutoff when the provider states a day; None for month precision."""
        return self.comparison_date if self.cutoff and len(self.cutoff) == 10 else None


@cache
def load_cutoffs() -> tuple[CutoffEvidence, ...]:
    """Load and validate the maintained cutoff table."""
    raw = json.loads(
        resources.files("legalforecast.data")
        .joinpath("model_cutoffs.json")
        .read_text(encoding="utf-8")
    )
    entries = tuple(
        CutoffEvidence(
            slug=item["slug"],
            model_ids=tuple(item["model_ids"]),
            cutoff=item["cutoff"],
            kind=item["kind"],
        )
        for item in raw["models"]
    )
    ids = [model_id for entry in entries for model_id in entry.model_ids]
    if len(ids) != len(set(ids)) or len({e.slug for e in entries}) != len(entries):
        raise ValueError("model_cutoffs.json repeats a slug or model id")
    for entry in entries:
        entry.comparison_date  # noqa: B018 - validates the date format eagerly
    return entries


def evidence_for(*model_ids: str) -> CutoffEvidence | None:
    """Return the table entry matching any of the given model identifiers."""
    for entry in load_cutoffs():
        if any(model_id in entry.model_ids for model_id in model_ids):
            return entry
    return None


def cutoff_eligibility(
    evidence: CutoffEvidence, *, first_decision: date
) -> tuple[Eligibility, str]:
    """Apply the owner's rule to one model against the earliest scored decision."""
    compared = evidence.comparison_date
    if compared is None:
        return "qualified", "cutoff_not_published"
    if compared < first_decision:
        return "eligible", "reported_cutoff_predates_decisions"
    return "qualified", "reported_cutoff_overlaps_decisions"

"""Maintained provider cutoff evidence for comparison eligibility.

Frozen model registries record a training cutoff only when a provider states
an exact training-data date, so knowledge cutoffs and month-only statements
stay "unknown" there. The owner's rule (2026-09-28) is broader: a model is
eligible when its provider-reported training-data or knowledge cutoff falls
before the earliest scored decision. This module applies that rule from one
maintained table, ``legalforecast/data/model_cutoffs.json``, which the website
reads too, without rewriting any frozen registry.
"""

from __future__ import annotations

import calendar
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
    def last_day(self) -> date | None:
        """The latest date the cutoff could mean (a month counts as its last day)."""
        if self.cutoff is None:
            return None
        parts = [int(part) for part in self.cutoff.split("-")]
        if len(parts) == 3:
            return date(parts[0], parts[1], parts[2])
        if len(parts) == 2:
            year, month = parts
            return date(year, month, calendar.monthrange(year, month)[1])
        raise ValueError(f"unsupported cutoff format {self.cutoff!r} for {self.slug}")


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
        entry.last_day  # noqa: B018 - validates the date format eagerly
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
    last_day = evidence.last_day
    if last_day is None:
        return "qualified", "cutoff_not_published"
    if last_day < first_decision:
        return "eligible", "reported_cutoff_predates_decisions"
    return "qualified", "reported_cutoff_overlaps_decisions"

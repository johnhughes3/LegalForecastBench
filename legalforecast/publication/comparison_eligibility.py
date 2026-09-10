"""Cutoff-aware ordering for official comparison rows."""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from legalforecast.reporting.contamination_tiers import ContaminationTier
from legalforecast.reporting.result_class import (
    ResultClass,
    result_class_marker,
    supplementary_caveat_if_needed,
)


class _ComparisonEntry(Protocol):
    @property
    def row(self) -> Mapping[str, Any]: ...

    @property
    def comparison_eligible(self) -> bool | None: ...

    @property
    def result_class(self) -> ResultClass: ...


def _first_str(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _optional_number(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def arm_rank_key(row: Mapping[str, Any]) -> tuple[float, str]:
    score = _optional_number(row, "micro_brier")
    return (
        score if score is not None else float("inf"),
        _first_str(row, ("model_id", "model_key", "solver_id")),
    )


def comparison_eligibility(
    row: Mapping[str, Any],
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> bool | None:
    """Return cutoff eligibility, preserving an unannotated legacy state."""

    if contamination_tiers is None or _first_str(row, ("row_type",)) == "baseline":
        return None
    model_id = _first_str(row, ("model_id", "model_key", "solver_id"))
    # Missing sidecar evidence is qualified by default. A renderer must never
    # infer eligibility from release timing or from a missing map entry.
    return contamination_tiers.get(model_id) is ContaminationTier.RESISTANT


def comparison_badge(eligible: bool | None) -> str:
    if eligible is True:
        return " <span class='comparison-badge eligible'>Eligible comparison</span>"
    if eligible is False:
        return " <span class='comparison-badge qualified'>Qualified comparison</span>"
    return ""


def supplementary_note(
    entries: Sequence[_ComparisonEntry],
    *,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> str:
    """Explain the retained release marker beside supplementary rows."""

    post_anchor_entries = tuple(
        entry for entry in entries if entry.result_class is ResultClass.POST_ANCHOR
    )
    if not post_anchor_entries:
        return ""
    marker = result_class_marker(ResultClass.POST_ANCHOR)
    if contamination_tiers is not None and all(
        entry.comparison_eligible is True for entry in post_anchor_entries
    ):
        return (
            "<p class='notice post-anchor-notice'>"
            f"{html.escape(marker, quote=False)} Historical post-anchor marker: "
            "release timing is retained for provenance; comparison eligibility is "
            "determined by documented training-cutoff evidence.</p>"
        )
    caveat = supplementary_caveat_if_needed(
        entry.result_class for entry in post_anchor_entries
    )
    if caveat is None:
        return ""
    return (
        "<p class='notice post-anchor-notice'>"
        f"{html.escape(marker, quote=False)} {html.escape(caveat, quote=False)}</p>"
    )


def ordered_model_entries[EntryT: _ComparisonEntry](
    entries: Sequence[EntryT],
    *,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> tuple[EntryT, ...]:
    """Rank one eligible comparison, then its qualified rows."""

    if contamination_tiers is None:
        return tuple(entries)
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                0 if entry.comparison_eligible is True else 1,
                *arm_rank_key(entry.row),
            ),
        )
    )


def best_model_entry[EntryT: _ComparisonEntry](
    official_entries: Sequence[EntryT],
    supplementary_entries: Sequence[EntryT],
    *,
    contamination_tiers: Mapping[str, ContaminationTier] | None,
) -> EntryT | None:
    entries = (
        tuple(official_entries)
        if contamination_tiers is None
        else (*official_entries, *supplementary_entries)
    )
    if contamination_tiers is not None:
        entries = tuple(entry for entry in entries if entry.comparison_eligible is True)
    scored = [
        entry
        for entry in entries
        if _optional_number(entry.row, "micro_brier") is not None
    ]
    if not scored:
        return entries[0] if entries else None
    return min(scored, key=lambda entry: arm_rank_key(entry.row))

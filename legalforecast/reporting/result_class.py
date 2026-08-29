"""Official versus post-anchor supplementary classification for result rows.

A cycle's *corpus anchor* is the latest first-deployment date among the models
the cycle froze.  Every corpus decision the cycle scores predates that anchor,
which is what lets an official row claim the model could not have trained on the
outcome.  A model released after the anchor cannot make that claim, so its rows
are published as supplementary and are refused inside the official set.

The classification is mechanical and has no override: it compares the model's
``release_timestamp`` against an anchor supplied by the caller.  The anchor must
come from the *official* frozen registry binding, never from the entries being
classified -- a supplementary registry's self-derived anchor is its own release
date, which would make every post-anchor model trivially "official".

This module is a classification overlay in the same spirit as
``contamination_tiers``, and the two dimensions are independent.  A model can be
official yet contamination-preliminary (its cutoff is simply undisclosed), and a
supplementary model normally carries both markers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum

from legalforecast.evals.model_registry import ModelRegistryEntry

SUPPLEMENTARY_MARKER = "†"
"""Dagger, deliberately distinct from the contamination-tier asterisk.

``contamination_tiers.PRELIMINARY_MARKER`` already marks official models whose
training cutoff is undisclosed, so reusing it here would stop the marker from
separating official rows from unofficial ones.
"""

SUPPLEMENTARY_CAVEAT = (
    "Unofficial (supplementary): model released after the corpus decision "
    "window closed; training-data contamination cannot be ruled out."
)


class ResultClass(StrEnum):
    """Whether a published row belongs to the official set."""

    OFFICIAL = "official"
    SUPPLEMENTARY_POST_ANCHOR = "supplementary_post_anchor"


class ResultClassError(ValueError):
    """Raised when a post-anchor model is presented as an official result."""


def classify_result_class(
    *,
    release_timestamp: datetime | None,
    corpus_anchor: date,
) -> ResultClass:
    """Classify one model against a cycle's corpus anchor.

    Fails closed: a missing ``release_timestamp`` cannot demonstrate that the
    model predates the anchor, so it classifies as supplementary rather than
    inheriting official status by omission.
    """

    if release_timestamp is None:
        return ResultClass.SUPPLEMENTARY_POST_ANCHOR
    if release_timestamp.tzinfo is None:
        raise ResultClassError("release_timestamp must be timezone-aware")
    if release_timestamp.astimezone(UTC).date() > corpus_anchor:
        return ResultClass.SUPPLEMENTARY_POST_ANCHOR
    return ResultClass.OFFICIAL


def classify_registry_entry(
    entry: ModelRegistryEntry,
    *,
    corpus_anchor: date,
) -> ResultClass:
    """Classify one frozen registry entry against a cycle's corpus anchor."""

    return classify_result_class(
        release_timestamp=entry.release_timestamp,
        corpus_anchor=corpus_anchor,
    )


def official_corpus_anchor(entries: Sequence[ModelRegistryEntry]) -> date:
    """Derive the corpus anchor from the *official* frozen registry entries.

    Callers must pass the official registry.  Passing the registry under
    evaluation would make the comparison self-referential and therefore vacuous.
    """

    from legalforecast.evals.model_registry import earliest_eligible_decision_date

    return earliest_eligible_decision_date(entries)


def supplementary_model_ids(
    entries: Iterable[ModelRegistryEntry],
    *,
    corpus_anchor: date,
) -> tuple[str, ...]:
    """Return the registry keys that classify as supplementary, sorted."""

    return tuple(
        sorted(
            entry.registry_key
            for entry in entries
            if classify_registry_entry(entry, corpus_anchor=corpus_anchor)
            is ResultClass.SUPPLEMENTARY_POST_ANCHOR
        )
    )


def require_official_result_classes(
    entries: Sequence[ModelRegistryEntry],
    *,
    corpus_anchor: date,
) -> None:
    """Fail closed unless every entry may be published as an official result.

    This is the one integrity property the supplementary lane must never be able
    to defeat: a model released after the corpus anchor cannot appear in the
    official set, whatever a run card, receipt, or sidecar claims about it.
    """

    supplementary = supplementary_model_ids(entries, corpus_anchor=corpus_anchor)
    if supplementary:
        raise ResultClassError(
            "official results refuse models released after the corpus anchor "
            f"{corpus_anchor.isoformat()}: {list(supplementary)}"
        )


def result_class_marker(result_class: ResultClass) -> str:
    """Return the public row marker for a result class."""

    if result_class is ResultClass.SUPPLEMENTARY_POST_ANCHOR:
        return SUPPLEMENTARY_MARKER
    return ""


def supplementary_caveat_if_needed(
    result_classes: Iterable[ResultClass],
) -> str | None:
    """Return the published caveat when any row is supplementary."""

    if any(
        result_class is ResultClass.SUPPLEMENTARY_POST_ANCHOR
        for result_class in result_classes
    ):
        return SUPPLEMENTARY_CAVEAT
    return None

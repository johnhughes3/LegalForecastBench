"""Pre-anchor versus post-anchor classification for result rows.

A cycle's *corpus anchor* is the **earliest decision date the cycle scores**.

A pre-anchor row claims the model already existed when the court decided the
case, so every scored decision must *postdate* the evaluated model's release.
Turned around, a model may join the pre-anchor set only if it was released on
or before the earliest decision in the corpus -- that date is the anchor.  A
model released after it publishes as post-anchor: still an official, viable
result, but it cannot claim contamination resistance on this corpus.

The classification is mechanical and has no override: it compares the model's
``release_timestamp`` against that corpus-derived anchor.  Deriving the anchor
from the corpus rather than from the registry under evaluation is what keeps the
check non-vacuous -- a registry containing only post-anchor models would
otherwise supply its own anchor and trivially certify itself as pre-anchor.

For Cycle 1 the corpus decision window closed 2026-06-30 and the frozen
registry's latest release is 2026-06-26, so the two candidate definitions
happen to bracket a narrow range; the implementation uses the corpus-derived
date throughout, and only that date can be trusted when the registry varies.

This module is a classification overlay in the same spirit as
``contamination_tiers``, and the two dimensions are independent.  A model can be
pre-anchor yet contamination-preliminary (its cutoff is simply undisclosed), and
a post-anchor model normally carries both markers.  Classification is a tracked
property of a result, never a permission to publish.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_sha256_digest
from legalforecast._record_validation import require_non_empty
from legalforecast.evals.model_registry import ModelRegistry, ModelRegistryEntry

SIDECAR_KIND = "result_class_sidecar"
_SHA256_PREFIX = "sha256:"
SUPPLEMENTARY_MARKER = "†"
"""Dagger, deliberately distinct from the contamination-tier asterisk.

``contamination_tiers.PRELIMINARY_MARKER`` already marks models whose training
cutoff is undisclosed, so reusing it here would stop the marker from separating
the two result-class arms.
"""

SUPPLEMENTARY_CAVEAT = (
    "Post-anchor result: the model was released after the corpus decision "
    "window closed, so this result is not contamination-resistant on this corpus."
)

_LEGACY_RESULT_CLASS_VALUES = {
    "official": "pre_anchor",
    "supplementary_post_anchor": "post_anchor",
}


class ResultClass(StrEnum):
    """Whether a published row predates the cycle's corpus anchor."""

    PRE_ANCHOR = "pre_anchor"
    POST_ANCHOR = "post_anchor"


class ResultClassError(ValueError):
    """Raised when a result class is mislabeled or a model is in the wrong lane."""


def classify_result_class(
    *,
    release_timestamp: datetime | None,
    corpus_anchor: date,
) -> ResultClass:
    """Classify one model against a cycle's corpus anchor.

    Fails closed: a missing ``release_timestamp`` cannot demonstrate that the
    model predates the anchor, so it classifies as post-anchor rather than
    inheriting pre-anchor status by omission.
    """

    if release_timestamp is None:
        return ResultClass.POST_ANCHOR
    if release_timestamp.tzinfo is None:
        raise ResultClassError("release_timestamp must be timezone-aware")
    if release_timestamp.astimezone(UTC).date() > corpus_anchor:
        return ResultClass.POST_ANCHOR
    return ResultClass.PRE_ANCHOR


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


def classify_decision_against_anchor(
    *,
    decision_date: date,
    release_anchor: date,
) -> ResultClass:
    """Classify one scored decision against the evaluated registry's anchor.

    A pre-anchor row claims the model already existed when the court decided the
    case, which is exactly ``decision_date >= release_anchor``. A decision that
    predates the model's release cannot support that claim, and is therefore
    post-anchor.

    This is the same comparison the aggregate performs, expressed per decision so
    the corpus-build and per-case gates can share it. Both directions are
    refusals: a pre-anchor run rejects a decision that predates the anchor, and a
    post-anchor run rejects one that does not, so a pre-anchor model cannot be
    smuggled through the post-anchor lane to dodge the pre-anchor gates.
    """

    if decision_date >= release_anchor:
        return ResultClass.PRE_ANCHOR
    return ResultClass.POST_ANCHOR


def expected_result_class(*, supplementary: bool) -> ResultClass:
    """Return the only result class the named execution mode may produce."""

    if supplementary:
        return ResultClass.POST_ANCHOR
    return ResultClass.PRE_ANCHOR


def corpus_anchor_from_decision_dates(decision_dates: Iterable[date]) -> date:
    """Derive a cycle's corpus anchor from the decision dates it scores.

    Every pre-anchor row rests on the claim that the model already existed when
    the court decided the case, which the per-packet gate enforces as
    ``decision_date >= release_anchor``.  Turned around, a model may join the
    pre-anchor set only if it was released on or before the *earliest* decision
    in the corpus.  That earliest decision date is the corpus anchor.

    Deriving the anchor from the corpus rather than from the models under
    evaluation is what makes the classification non-vacuous: a registry
    containing only post-anchor models would otherwise supply its own anchor and
    trivially certify itself as pre-anchor.
    """

    dates = sorted(decision_dates)
    if not dates:
        raise ResultClassError("corpus anchor requires at least one decision date")
    return dates[0]


def supplementary_model_ids(
    entries: Iterable[ModelRegistryEntry],
    *,
    corpus_anchor: date,
) -> tuple[str, ...]:
    """Return the registry keys that classify as post-anchor, sorted."""

    return tuple(
        sorted(
            entry.registry_key
            for entry in entries
            if classify_registry_entry(entry, corpus_anchor=corpus_anchor)
            is ResultClass.POST_ANCHOR
        )
    )


def require_official_result_classes(
    entries: Sequence[ModelRegistryEntry],
    *,
    corpus_anchor: date,
    claimed_classes: Mapping[str, ResultClass] | None = None,
) -> None:
    """Allow post-anchor models on an official surface; refuse a mismatched label.

    Classification is a tracked property of a result, not a permission to
    publish. A post-anchor model may appear as an official, viable result. What
    this function refuses is a claimed pre-anchor label on a mechanically
    post-anchor model.
    """

    if claimed_classes is None:
        return
    by_id = {entry.model_id: entry for entry in entries}
    by_key = {entry.registry_key: entry for entry in entries}
    mislabeled: list[str] = []
    for model_id, claimed in claimed_classes.items():
        if claimed is not ResultClass.PRE_ANCHOR:
            continue
        entry = by_key.get(model_id) or by_id.get(model_id)
        if entry is None:
            continue
        if (
            classify_registry_entry(entry, corpus_anchor=corpus_anchor)
            is ResultClass.POST_ANCHOR
        ):
            mislabeled.append(model_id)
    if mislabeled:
        raise ResultClassError(
            f"post-anchor rows cannot be labeled pre-anchor: {sorted(mislabeled)}"
        )


def require_lane_result_classes(
    entries: Sequence[ModelRegistryEntry],
    *,
    corpus_anchor: date,
    supplementary: bool,
) -> None:
    """Refuse a registry that does not belong to the lane being executed.

    Both directions refuse, from one place, so the pre-dispatch authorization
    chain and the aggregate cannot drift into disagreeing about which set a model
    belongs to.  A caller declares which bundle or dispatch it is building; it
    never gets to declare how a model classifies.  Publication of a post-anchor
    row as an official result is a separate question, handled by
    ``require_official_result_classes``.
    """

    if supplementary and not entries:
        # Checked before anything else: without it an empty registry would make a
        # post-anchor lane skip the separation entirely rather than refuse.
        raise ResultClassError(
            "a supplementary result set requires a model registry to classify"
        )
    post_anchor_keys = set(
        supplementary_model_ids(entries, corpus_anchor=corpus_anchor)
    )
    if not supplementary:
        if post_anchor_keys:
            raise ResultClassError(
                "a pre-anchor result set refuses models released after the "
                f"corpus anchor {corpus_anchor.isoformat()}: "
                f"{sorted(post_anchor_keys)}"
            )
        return
    pre_anchor = sorted(
        entry.registry_key
        for entry in entries
        if entry.registry_key not in post_anchor_keys
    )
    if pre_anchor:
        raise ResultClassError(
            "a supplementary result set refuses models released on or before the "
            f"corpus anchor {corpus_anchor.isoformat()}: {pre_anchor}"
        )


def corpus_anchor_from_decision_rows(
    rows: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    required: bool,
) -> date | None:
    """Derive the corpus anchor from labelled run-input rows, or refuse.

    ``rows`` are ``(label, record)`` pairs in the caller's own deterministic
    order; the label appears only in the partial-dating refusal.

    Rows carrying no ``decision_date`` are collected rather than skipped so a
    manifest with no dates at all -- older fixtures, where the anchor is simply
    unavailable -- stays distinguishable from a partially dated one.  A partial
    set is always refused: an anchor taken from the dated rows alone can only be
    later than the true earliest decision, and a later anchor can only
    under-report post-anchor models.  ``required`` makes the all-absent case a
    refusal too, which is what any post-anchor lane passes.
    """

    dates: list[date] = []
    undated: list[str] = []
    for label, record in rows:
        raw = record.get("decision_date")
        if raw is None:
            undated.append(label)
            continue
        if not isinstance(raw, str) or not raw.strip():
            raise ResultClassError("run-input decision_date must be an ISO date string")
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError as exc:
            raise ResultClassError(
                f"run-input decision_date is not an ISO date: {raw}"
            ) from exc
    if undated and dates:
        raise ResultClassError(
            "run-input rows disagree on decision_date presence; the corpus anchor "
            f"cannot be derived from a partial set: {undated}"
        )
    if not dates:
        if required:
            raise ResultClassError(
                "a supplementary result set requires run-input decision dates to "
                "derive the corpus anchor"
            )
        return None
    return corpus_anchor_from_decision_dates(dates)


@dataclass(frozen=True, slots=True)
class ResultClassRow:
    """One sidecar row: the non-authoritative result class for a model."""

    model_id: str
    result_class: ResultClass

    def __post_init__(self) -> None:
        require_non_empty(self.model_id, "model_id")

    def to_record(self) -> dict[str, Any]:
        return {"model_id": self.model_id, "result_class": self.result_class.value}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ResultClassRow:
        return cls(
            model_id=_required_str(record, "model_id"),
            result_class=_parse_result_class(_required_str(record, "result_class")),
        )


@dataclass(frozen=True, slots=True)
class ResultClassSidecar:
    """Non-authoritative result-class overlay keyed by a frozen result digest.

    Cycle 1 change control keeps published whole-card bytes frozen, so this
    presentation flag lives in a sidecar rather than as a new field on
    ``legalforecast-official-aggregate-v1``. The sidecar is a rendering
    convenience: the authoritative properties are the lane-separation gate and
    the arm-membership assertion that a post-anchor row cannot be labeled
    pre-anchor.
    """

    result_digest: str
    corpus_anchor: date
    rows: tuple[ResultClassRow, ...]
    kind: str = SIDECAR_KIND
    authoritative: bool = False

    def __post_init__(self) -> None:
        if self.kind != SIDECAR_KIND:
            raise ValueError(f"unsupported result-class sidecar kind: {self.kind}")
        if self.authoritative:
            raise ValueError("result-class sidecar must not be authoritative")
        if not is_sha256_digest(self.result_digest, allow_prefix=True):
            raise ValueError("result_digest must be a sha256: hex digest")
        if not self.result_digest.startswith(_SHA256_PREFIX):
            raise ValueError("result_digest must use the sha256: prefix")
        if not self.rows:
            raise ValueError("result-class sidecar requires at least one row")
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in self.rows:
            if row.model_id in seen:
                duplicates.add(row.model_id)
            seen.add(row.model_id)
        if duplicates:
            raise ValueError(
                f"duplicate result-class sidecar model_id values: {sorted(duplicates)}"
            )

    def result_class_by_model_id(self) -> dict[str, ResultClass]:
        return {row.model_id: row.result_class for row in self.rows}

    def to_record(self) -> dict[str, Any]:
        return {
            "authoritative": False,
            "corpus_anchor": self.corpus_anchor.isoformat(),
            "kind": SIDECAR_KIND,
            "result_digest": self.result_digest,
            "rows": [row.to_record() for row in self.rows],
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> ResultClassSidecar:
        if "schema_version" in record:
            raise ValueError(
                "result-class sidecar must not declare a schema_version family"
            )
        raw_rows = record.get("rows")
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, str | bytes):
            raise ValueError("result-class sidecar rows must be an array")
        row_values = cast(Sequence[object], raw_rows)
        rows = tuple(
            ResultClassRow.from_record(_mapping_record(item, index))
            for index, item in enumerate(row_values)
        )
        return cls(
            result_digest=_required_str(record, "result_digest"),
            corpus_anchor=date.fromisoformat(_required_str(record, "corpus_anchor")),
            rows=rows,
            kind=_required_str(record, "kind"),
            authoritative=_required_false(record, "authoritative"),
        )


def build_result_class_sidecar(
    model_rows: Sequence[tuple[str, str]],
    *,
    result_digest: str,
    registry: ModelRegistry,
    corpus_anchor: date,
) -> ResultClassSidecar:
    """Derive a sidecar for the named leaderboard models from registry bytes.

    Each entry of ``model_rows`` is ``(model_id, lookup_key)``: the leaderboard
    label to key the row by, and the identifier to resolve against the registry.
    A published ``model_id`` is a display label chosen by the solver run and need
    not match any registry field, so the caller supplies the ``solver_id`` --
    which is the registry key -- as the lookup rather than letting this function
    guess from the label.
    """

    by_model_id = {entry.model_id: entry for entry in registry.entries}
    by_registry_key = {entry.registry_key: entry for entry in registry.entries}
    rows: list[ResultClassRow] = []
    for model_id, lookup_key in model_rows:
        require_non_empty(model_id, "model_id")
        # Two deliberate lookups, in order of trust: solver_id is the registry
        # key on the production path, and a caller with no solver_id passes the
        # model_id through as the lookup, which resolves against model_id.
        entry = by_registry_key.get(lookup_key) or by_model_id.get(lookup_key)
        if entry is None:
            raise ValueError(f"no registry entry for leaderboard model_id {model_id}")
        rows.append(
            ResultClassRow(
                model_id=model_id,
                result_class=classify_registry_entry(
                    entry, corpus_anchor=corpus_anchor
                ),
            )
        )
    return ResultClassSidecar(
        result_digest=result_digest,
        corpus_anchor=corpus_anchor,
        rows=tuple(sorted(rows, key=lambda row: row.model_id)),
    )


def write_result_class_sidecar(path: Path, sidecar: ResultClassSidecar) -> None:
    """Write the sidecar as non-canonical reporting JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sidecar.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_result_class_sidecar(
    path: Path,
    *,
    expected_digest: str,
) -> ResultClassSidecar:
    """Load a sidecar and fail closed unless it matches the frozen result digest."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("result-class sidecar must be a JSON object")
    sidecar = ResultClassSidecar.from_record(cast(Mapping[str, Any], payload))
    if sidecar.result_digest != expected_digest:
        raise ValueError("result-class sidecar result_digest does not match")
    return sidecar


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_false(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if value is not False:
        raise ValueError(f"{field_name} must be false")
    return False


def _mapping_record(value: object, index: int) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"result-class sidecar row {index} must be an object")
    return cast(Mapping[str, Any], value)


def _parse_result_class(raw: str) -> ResultClass:
    """Parse a sidecar result_class, accepting the pre-rename wire values."""

    return ResultClass(_LEGACY_RESULT_CLASS_VALUES.get(raw, raw))


def result_class_marker(result_class: ResultClass) -> str:
    """Return the public row marker for a result class."""

    if result_class is ResultClass.POST_ANCHOR:
        return SUPPLEMENTARY_MARKER
    return ""


def result_class_tier_label(result_class: ResultClass) -> str:
    """Return the compact table badge for a result class."""

    if result_class is ResultClass.POST_ANCHOR:
        return f"Official (post-anchor){result_class_marker(result_class)}"
    return "Official"


def supplementary_caveat_if_needed(
    result_classes: Iterable[ResultClass],
) -> str | None:
    """Return the published caveat when any row is post-anchor."""

    if any(result_class is ResultClass.POST_ANCHOR for result_class in result_classes):
        return SUPPLEMENTARY_CAVEAT
    return None

"""Official versus post-anchor supplementary classification for result rows.

A cycle's *corpus anchor* is the **earliest decision date the cycle scores**.

An official row claims the model already existed when the court decided the
case, so every scored decision must *postdate* the evaluated models' release.
Turned around, a model may join the official set only if it was released on or
before the earliest decision in the corpus -- that date is the anchor.  A model
released after it cannot support the claim for every scored case, so its rows
publish as supplementary and are refused inside the official set.

The classification is mechanical and has no override: it compares the model's
``release_timestamp`` against that corpus-derived anchor.  Deriving the anchor
from the corpus rather than from the registry under evaluation is what keeps the
check non-vacuous -- a registry containing only post-anchor models would
otherwise supply its own anchor and trivially certify itself as official.

For Cycle 1 the corpus decision window closed 2026-06-30 and the frozen
registry's latest release is 2026-06-26, so the two candidate definitions
happen to bracket a narrow range; the implementation uses the corpus-derived
date throughout, and only that date can be trusted when the registry varies.

This module is a classification overlay in the same spirit as
``contamination_tiers``, and the two dimensions are independent.  A model can be
official yet contamination-preliminary (its cutoff is simply undisclosed), and a
supplementary model normally carries both markers.
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


def classify_decision_against_anchor(
    *,
    decision_date: date,
    release_anchor: date,
) -> ResultClass:
    """Classify one scored decision against the evaluated registry's anchor.

    An official row claims the model already existed when the court decided the
    case, which is exactly ``decision_date >= release_anchor``. A decision that
    predates the model's release cannot support that claim, and is therefore
    supplementary.

    This is the same comparison the aggregate performs, expressed per decision so
    the corpus-build and per-case gates can share it. Both directions are
    refusals: an official run rejects a decision that predates the anchor, and a
    supplementary run rejects one that does not, so a pre-anchor model cannot be
    smuggled through the supplementary lane to dodge the official gates.
    """

    if decision_date >= release_anchor:
        return ResultClass.OFFICIAL
    return ResultClass.SUPPLEMENTARY_POST_ANCHOR


def expected_result_class(*, supplementary: bool) -> ResultClass:
    """Return the only result class the named execution mode may produce."""

    if supplementary:
        return ResultClass.SUPPLEMENTARY_POST_ANCHOR
    return ResultClass.OFFICIAL


def corpus_anchor_from_decision_dates(decision_dates: Iterable[date]) -> date:
    """Derive a cycle's corpus anchor from the decision dates it scores.

    Every official row rests on the claim that the model already existed when the
    court decided the case, which the per-packet gate enforces as
    ``decision_date >= release_anchor``.  Turned around, a model may join the
    official set only if it was released on or before the *earliest* decision in
    the corpus.  That earliest decision date is the corpus anchor.

    Deriving the anchor from the corpus rather than from the models under
    evaluation is what makes the classification non-vacuous: a registry
    containing only post-anchor models would otherwise supply its own anchor and
    trivially certify itself as official.
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
            result_class=ResultClass(_required_str(record, "result_class")),
        )


@dataclass(frozen=True, slots=True)
class ResultClassSidecar:
    """Non-authoritative result-class overlay keyed by a frozen result digest.

    Cycle 1 change control keeps published whole-card bytes frozen, so this
    presentation flag lives in a sidecar rather than as a new field on
    ``legalforecast-official-aggregate-v1``. The sidecar is a rendering
    convenience: the authoritative property is the aggregate gate that refuses a
    post-anchor model inside an official bundle, which no sidecar can relax.
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

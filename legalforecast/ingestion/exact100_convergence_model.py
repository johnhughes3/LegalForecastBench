"""Result, disposition, and input types for the exact-100 convergence gate.

The gate's vocabulary lives here so the nine invariants themselves stay
readable in :mod:`legalforecast.ingestion.exact100_convergence_invariants`:
what a failure and a result look like, how an owner disposition and its
independent execution state are read, and how the artifacts a run needs are
assembled into one input bundle.

Nothing here evaluates anything. It parses untyped JSON defensively -- these
artifacts are hand-assembled overlays, not authenticated contracts -- and
routes every byte-role verdict through
:mod:`legalforecast.ingestion.adjudication_validation_view` so the whole gate
has a single definition of "validated".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, cast

from legalforecast.ingestion.adjudication_validation_view import (
    CandidateValidationView,
    build_validation_views,
)

__all__ = [
    "BRIEFING_ROLES",
    "COMPLETE",
    "EXECUTION_STATES",
    "PLEADING_ROLES",
    "REQUIRED_CASE_COUNT",
    "TARGET_MOTION_ROLES",
    "ConvergenceInputs",
    "ConvergenceReport",
    "Disposition",
    "InvariantFailure",
    "InvariantResult",
    "entries_of",
    "mapping_of",
    "parse_disposition",
    "rows_of",
    "sequence_of",
    "text_of",
]

#: The corpus is exactly this many eligible unique cases when converged.
REQUIRED_CASE_COUNT: Final = 100

#: Roles that identify the case's target motion.
TARGET_MOTION_ROLES: Final = frozenset({"target_motion"})

#: Roles that identify the pleading the target motion attacks.
PLEADING_ROLES: Final = frozenset(
    {
        "amended_complaint",
        "complaint",
        "counterclaim",
        "crossclaim",
        "interpleader_complaint",
        "operative_pleading",
        "second_amended_complaint",
    }
)

#: Roles that identify docketed briefing on the target motion.
BRIEFING_ROLES: Final = frozenset(
    {
        "motion_memorandum",
        "opposition",
        "reply",
        "response",
        "surreply",
    }
)

#: Execution state meaning the disposition has been carried out in full.
COMPLETE: Final = "complete"

EXECUTION_STATES: Final = frozenset({"ready", "blocked", COMPLETE})


@dataclass(frozen=True, slots=True)
class InvariantFailure:
    """One named blocker: which invariant, which case, which document."""

    invariant: str
    detail: str
    candidate_id: str | None = None
    entry_number: int | None = None
    source_document_id: str | None = None

    def describe(self) -> str:
        location = self.candidate_id or "corpus"
        if self.entry_number is not None:
            location = f"{location} E{self.entry_number}"
        if self.source_document_id:
            location = f"{location} (document {self.source_document_id})"
        return f"{location}: {self.detail}"

    def to_json(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "detail": self.detail,
            "entry_number": self.entry_number,
            "invariant": self.invariant,
            "source_document_id": self.source_document_id,
        }


@dataclass(frozen=True, slots=True)
class InvariantResult:
    """Outcome of one invariant, with every blocker it found."""

    key: str
    statement: str
    checked: int
    failures: tuple[InvariantFailure, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def blocking_candidate_ids(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for failure in self.failures:
            if failure.candidate_id:
                seen.setdefault(failure.candidate_id, None)
        return tuple(seen)

    def to_json(self) -> dict[str, Any]:
        return {
            "blocking_candidate_ids": list(self.blocking_candidate_ids),
            "checked": self.checked,
            "failure_count": len(self.failures),
            "failures": [failure.to_json() for failure in self.failures],
            "key": self.key,
            "passed": self.passed,
            "statement": self.statement,
        }


@dataclass(frozen=True, slots=True)
class ConvergenceReport:
    """The suite's whole result: nine invariants, each pass or blocked."""

    results: tuple[InvariantResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failing(self) -> tuple[InvariantResult, ...]:
        return tuple(result for result in self.results if not result.passed)

    def to_json(self) -> dict[str, Any]:
        return {
            "converged": self.passed,
            "failing_invariant_count": len(self.failing),
            "invariant_count": len(self.results),
            "invariants": [result.to_json() for result in self.results],
            "schema_version": "legalforecast.exact100_convergence_invariants.v1",
        }

    def render_text(self) -> str:
        lines: list[str] = []
        status = "CONVERGED" if self.passed else "BLOCKED"
        passing = len(self.results) - len(self.failing)
        lines.append(
            f"exact-100 convergence: {status} "
            f"({passing}/{len(self.results)} invariants pass)"
        )
        for result in self.results:
            mark = "PASS" if result.passed else "FAIL"
            lines.append("")
            lines.append(f"[{mark}] {result.key} — {result.statement}")
            lines.append(f"       checked {result.checked}")
            for failure in result.failures:
                lines.append(f"       - {failure.describe()}")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Disposition:
    """One owner legal decision plus its independent execution state."""

    candidate_id: str
    decision: str
    execution_state: str
    execution_blocked_on: str | None = None
    final_packet: tuple[Mapping[str, Any], ...] = ()
    drops: tuple[Mapping[str, Any], ...] = ()
    collateral: tuple[Mapping[str, Any], ...] = ()
    relabels: tuple[Mapping[str, Any], ...] = ()
    superseded: tuple[Mapping[str, Any], ...] = ()
    exclusion: Mapping[str, Any] | None = None
    in_corpus: bool = True
    #: True when the record carried a ``final_packet`` key at all, so a
    #: deliberately empty packet is distinguishable from an absent one.
    final_packet_declared: bool = False

    @property
    def excluded(self) -> bool:
        return self.exclusion is not None

    @property
    def replacement_candidate_id(self) -> str | None:
        """The owner-approved successor for this slot, if one exists."""

        return self._exclusion_text("replacement_candidate_id")

    @property
    def proposed_replacement_candidate_id(self) -> str | None:
        """A sourced successor still awaiting owner approval.

        Distinguishing this from an approved replacement keeps the convergence
        report honest in both directions: a slot with a posted proposal is not
        unsourced, and a posted proposal is not an approval.
        """

        return self._exclusion_text("proposed_replacement_candidate_id")

    def _exclusion_text(self, field_name: str) -> str | None:
        if self.exclusion is None:
            return None
        value = self.exclusion.get(field_name)
        return value if isinstance(value, str) and value.strip() else None

    def unsourced_detail(self) -> str:
        """Explain why an excluded slot is still unfilled."""

        proposed = self.proposed_replacement_candidate_id
        if proposed:
            return (
                f"owner-excluded; successor {proposed} is sourced and posted but not "
                "yet owner-approved, so the slot is unfilled"
            )
        return "owner-excluded and its slot has no sourced replacement candidate"

    @property
    def dropped_entries(self) -> frozenset[int]:
        return frozenset(entries_of(self.drops))

    @property
    def collateral_entries(self) -> frozenset[int]:
        return frozenset(entries_of(self.collateral))

    @property
    def superseded_entries(self) -> frozenset[int]:
        return frozenset(entries_of(self.superseded))

    @property
    def final_packet_entries(self) -> frozenset[int]:
        return frozenset(entries_of(self.final_packet))


def entries_of(rows: Iterable[Mapping[str, Any]]) -> list[int]:
    numbers: list[int] = []
    for row in rows:
        value = row.get("entry")
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            numbers.append(value)
        elif isinstance(value, str) and value.strip().isdigit():
            numbers.append(int(value.strip()))
    return numbers


def mapping_of(value: Any) -> Mapping[str, Any] | None:
    """Narrow untyped JSON to a string-keyed mapping, or ``None``."""

    if isinstance(value, Mapping):
        return cast("Mapping[str, Any]", value)
    return None


def sequence_of(value: Any) -> tuple[Any, ...]:
    """Narrow untyped JSON to a tuple of items, treating text as scalar."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(cast("Sequence[Any]", value))


def rows_of(value: Any) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for item in sequence_of(value):
        row = mapping_of(item)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def text_of(source: Mapping[str, Any], field_name: str) -> str | None:
    value = source.get(field_name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def parse_disposition(record: Mapping[str, Any]) -> Disposition:
    """Read one owner disposition overlay record."""

    state = text_of(record, "execution_state") or "ready"
    return Disposition(
        candidate_id=text_of(record, "candidate_id") or "",
        decision=text_of(record, "decision") or "",
        execution_state=state,
        execution_blocked_on=text_of(record, "execution_blocked_on"),
        final_packet=rows_of(record.get("final_packet")),
        drops=rows_of(record.get("drops")),
        collateral=rows_of(record.get("collateral")),
        relabels=rows_of(record.get("relabels")),
        superseded=rows_of(record.get("superseded")),
        exclusion=mapping_of(record.get("exclusion")),
        in_corpus=record.get("in_corpus", True) is not False,
        final_packet_declared="final_packet" in record,
    )


@dataclass(frozen=True, slots=True)
class ConvergenceInputs:
    """Every artifact the suite reads, already parsed."""

    corpus: tuple[Mapping[str, Any], ...]
    adjudication: tuple[Mapping[str, Any], ...]
    dispositions: tuple[Disposition, ...]
    parse_quality: Mapping[str, Any] | None = None
    replacements: tuple[Mapping[str, Any], ...] | None = None
    validation_views: Mapping[str, CandidateValidationView] = field(
        default_factory=lambda: cast("dict[str, CandidateValidationView]", {})
    )

    @classmethod
    def build(
        cls,
        *,
        corpus: Iterable[Mapping[str, Any]],
        adjudication: Iterable[Mapping[str, Any]],
        dispositions: Iterable[Mapping[str, Any]],
        parse_quality: Mapping[str, Any] | None = None,
        replacements: Iterable[Mapping[str, Any]] | None = None,
        acquisitions: Iterable[Mapping[str, Any]] | None = None,
    ) -> ConvergenceInputs:
        adjudication_rows = tuple(adjudication)
        return cls(
            corpus=tuple(corpus),
            adjudication=adjudication_rows,
            dispositions=tuple(parse_disposition(row) for row in dispositions),
            parse_quality=parse_quality,
            replacements=None if replacements is None else tuple(replacements),
            validation_views=build_validation_views(
                _merge_acquisitions(adjudication_rows, acquisitions)
            ),
        )

    @property
    def disposition_by_candidate(self) -> dict[str, Disposition]:
        return {
            disposition.candidate_id: disposition
            for disposition in self.dispositions
            if disposition.candidate_id
        }


def _acquisition_status_row(record: Mapping[str, Any]) -> dict[str, Any]:
    """Reshape one held-document record into a document-status row.

    Reusing the document-status shape means the acquisition evidence flows
    through exactly the same canonical validation view as the adjudication
    overlay, so there is still only one place that decides what "validated"
    means.
    """

    entry = record.get("entry")
    role = text_of(record, "role")
    validation: dict[str, Any] = {
        "expected_role": role,
        "source_document_id": text_of(record, "source_document_id"),
    }
    for field_name in ("byte_role_verdict", "verdict", "validation_basis"):
        value = text_of(record, field_name)
        if value:
            validation[field_name] = value
    return {
        "acquired_document_role": role,
        "acquired_evidence": {
            "docket_entry_number": entry,
            "source_document_id": text_of(record, "source_document_id"),
        },
        "acquisition_status": text_of(record, "acquisition_status") or "acquired",
        "byte_role_validation": validation,
        "entry": entry,
        "role": role,
    }


def _merge_acquisitions(
    adjudication: tuple[Mapping[str, Any], ...],
    acquisitions: Iterable[Mapping[str, Any]] | None,
) -> tuple[Mapping[str, Any], ...]:
    """Fold corpus-wide held-document evidence into the adjudication rows.

    The adjudication overlay only covers the cases that needed human review.
    Without the rest of the corpus's acquisition evidence the suite cannot tell
    "this document was never acquired" from "nobody handed me the record", and
    the second dressed as the first makes the failure list useless as a work
    list. The merged rows are used only to build validation views; the
    adjudication rows themselves stay untouched for owner-state reconciliation.
    """

    if acquisitions is None:
        return adjudication
    extra: dict[str, list[dict[str, Any]]] = {}
    for record in acquisitions:
        candidate_id = text_of(record, "candidate_id")
        if not candidate_id:
            continue
        extra.setdefault(candidate_id, []).append(_acquisition_status_row(record))
    if not extra:
        return adjudication

    merged: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for row in adjudication:
        candidate_id = text_of(row, "candidate_id") or ""
        seen.add(candidate_id)
        additions = extra.get(candidate_id)
        if not additions:
            merged.append(row)
            continue
        combined = dict(row)
        existing = rows_of(row.get("missing_document_status"))
        # Compare NORMALIZED entry numbers. The two artifacts come from
        # different pipeline stages and nothing guarantees they serialize an
        # entry number the same way; comparing raw values would let an
        # acquisition record slip in beside the overlay's own row for the same
        # entry, where its verdict could override the overlay's own finding.
        # That is the exact opposite of this function's contract.
        known = {entry for status in existing for entry in entries_of([status])}
        combined["missing_document_status"] = list(existing) + [
            status for status in additions if not (set(entries_of([status])) & known)
        ]
        merged.append(combined)
    for candidate_id, additions in extra.items():
        if candidate_id in seen:
            continue
        merged.append(
            {
                "byte_mismatches": [],
                "candidate_id": candidate_id,
                "missing_document_status": additions,
            }
        )
    return tuple(merged)

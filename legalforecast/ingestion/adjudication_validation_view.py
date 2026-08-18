"""One canonical current byte-role validation verdict for adjudication records.

Byte-role validation records in the needs-human adjudication corpus carry two
different spellings of the same field. The original heuristic validator wrote
``verdict`` alongside ``heuristic_verdict``/``matched_pattern``/``title_excerpt``;
the later exact-role validator writes ``byte_role_verdict`` alongside
``observed_heading``/``text_sha256``/``validation_basis``. Both spellings occur
in the same overlay file, sometimes for the same case.

Reading only one spelling makes a validated document render as unvalidated. It
also leaves stale ``byte_mismatches`` -- pass-level role findings recorded
*before* the later validation ran -- looking unresolved when a subsequent
validation already resolved the same docket entry to ``match``.

This module is the single read-side view every renderer and executor uses so
that a document's *current* verdict is derived in exactly one place. It is
deliberately read-only: it re-derives nothing, validates no bytes, and changes
no authenticated contract. It only answers "what does the newest validation
record on file say about this document, and does it supersede an older
mismatch finding?"

Join key
--------
Validation records and mismatch findings are joined on **candidate id plus
docket entry number**, never on role. A stale mismatch records the role the
selector had assigned at the time (``selected_role``), while the resolving
validation records the role the document was finally validated against
(``expected_role``); for the same document these frequently differ, so a
role-based join silently fails to match. ``source_document_id`` is carried as a
secondary identity check.

Entry numbers come from the enclosing document-status row, because the newer
validation records do not carry ``docket_entry_number`` themselves.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

__all__ = [
    "NOT_VALIDATED",
    "VERDICT_FIELDS",
    "CandidateValidationView",
    "DocumentValidation",
    "MismatchResolution",
    "build_candidate_validation_view",
    "build_validation_views",
    "current_validation_verdict",
]

#: Verdict reported when no byte-role validation record exists for a document.
NOT_VALIDATED: Final = "not_validated"

#: Verdict field spellings, newest schema first. The first present, non-empty
#: string wins, so a record carrying both spellings resolves to the newer one.
VERDICT_FIELDS: Final = ("byte_role_verdict", "verdict")

#: Verdict meaning "the bytes carry the role they were selected for".
MATCH_VERDICT: Final = "match"


def current_validation_verdict(validation: Mapping[str, Any] | None) -> str:
    """Return the canonical verdict for one byte-role validation record.

    Accepts either schema spelling and returns :data:`NOT_VALIDATED` when the
    record is absent or carries no verdict at all. Never returns ``None``, so
    callers cannot accidentally render a missing verdict as an empty string.
    """

    if not validation:
        return NOT_VALIDATED
    for field in VERDICT_FIELDS:
        value = validation.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return NOT_VALIDATED


@dataclass(frozen=True, slots=True)
class DocumentValidation:
    """Current validation state of one selected or acquired document."""

    candidate_id: str
    entry_number: int | None
    source_document_id: str | None
    expected_role: str | None
    acquisition_status: str | None
    verdict: str
    validation_basis: str | None

    @property
    def validated(self) -> bool:
        """True when any byte-role validation record exists for the document."""

        return self.verdict != NOT_VALIDATED

    @property
    def matched(self) -> bool:
        """True when the current validation resolves the document to its role."""

        return self.verdict == MATCH_VERDICT

    def describe(self) -> str:
        entry = "E?" if self.entry_number is None else f"E{self.entry_number}"
        role = self.expected_role or "role unrecorded"
        return f"{self.candidate_id} {entry} {role}: {self.verdict}"


@dataclass(frozen=True, slots=True)
class MismatchResolution:
    """A recorded ``byte_mismatches`` finding read against current validation.

    ``superseded`` is the whole point: a pass-level finding that a later
    validation resolved to ``match`` is history, not an open defect, and must
    not be ranked as an unknown/unverifiable role.
    """

    candidate_id: str
    entry_number: int | None
    selected_role: str | None
    observed_role: str | None
    recorded_verdict: str | None
    current_verdict: str
    evidence: str | None

    @property
    def superseded(self) -> bool:
        """True when a later validation resolved this entry to ``match``."""

        return self.current_verdict == MATCH_VERDICT

    @property
    def open(self) -> bool:
        """True when nothing later resolved the finding."""

        return not self.superseded

    @property
    def unresolved_role(self) -> bool:
        """True for an open finding whose observed role is unknown/empty.

        This is the condition worth ranking as owner-attention cost. A finding
        superseded by a later ``match`` is not, however the observed role reads.
        """

        if self.superseded:
            return False
        observed = (self.observed_role or "").strip().lower()
        return observed in {"", "none", "unknown"}

    def describe(self) -> str:
        entry = "E?" if self.entry_number is None else f"E{self.entry_number}"
        selected = self.selected_role or "role unrecorded"
        observed = self.observed_role or "unknown"
        state = (
            f"superseded by later validation ({self.current_verdict})"
            if self.superseded
            else f"open ({self.recorded_verdict or 'verdict unrecorded'})"
        )
        return f"{self.candidate_id} {entry} {selected} -> {observed}: {state}"


@dataclass(frozen=True, slots=True)
class CandidateValidationView:
    """Canonical current validation state for one adjudication row."""

    candidate_id: str
    documents: tuple[DocumentValidation, ...]
    mismatches: tuple[MismatchResolution, ...]

    def verdict_for_entry(self, entry_number: int) -> str:
        """Current verdict for a docket entry, or :data:`NOT_VALIDATED`.

        When several documents share an entry number (a main document plus an
        attachment), a ``match`` on any of them reports as ``match``; otherwise
        the first recorded verdict is reported.
        """

        verdicts = [
            document.verdict
            for document in self.documents
            if document.entry_number == entry_number
        ]
        if not verdicts:
            return NOT_VALIDATED
        if MATCH_VERDICT in verdicts:
            return MATCH_VERDICT
        for verdict in verdicts:
            if verdict != NOT_VALIDATED:
                return verdict
        return NOT_VALIDATED

    @property
    def unvalidated_documents(self) -> tuple[DocumentValidation, ...]:
        """Acquired documents carrying no byte-role validation record."""

        return tuple(
            document
            for document in self.documents
            if document.acquisition_status == "acquired" and not document.validated
        )

    @property
    def open_mismatches(self) -> tuple[MismatchResolution, ...]:
        """Recorded mismatches that no later validation resolved."""

        return tuple(mismatch for mismatch in self.mismatches if mismatch.open)

    @property
    def superseded_mismatches(self) -> tuple[MismatchResolution, ...]:
        """Recorded mismatches a later validation resolved to ``match``."""

        return tuple(mismatch for mismatch in self.mismatches if mismatch.superseded)

    @property
    def unresolved_role_mismatches(self) -> tuple[MismatchResolution, ...]:
        """Open mismatches whose observed role is unknown or empty."""

        return tuple(
            mismatch for mismatch in self.mismatches if mismatch.unresolved_role
        )


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    """Narrow untyped JSON to a string-keyed mapping, or ``None``."""

    if isinstance(value, Mapping):
        return cast("Mapping[str, Any]", value)
    return None


def _as_rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    """Narrow untyped JSON to a tuple of string-keyed mappings."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    rows: list[Mapping[str, Any]] = []
    for item in cast("Sequence[Any]", value):
        row = _as_mapping(item)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _entry_number(status: Mapping[str, Any]) -> int | None:
    """Resolve a document-status row to its docket entry number.

    Prefers the status row's own ``entry``; falls back to the acquired
    evidence's ``docket_entry_number`` and then to the status row's
    ``docket_entry_number`` so that both worksheet spellings resolve.
    """

    candidates: list[Any] = [status.get("entry")]
    evidence = _as_mapping(status.get("acquired_evidence"))
    if evidence is not None:
        candidates.append(evidence.get("docket_entry_number"))
    candidates.append(status.get("docket_entry_number"))
    validation = _as_mapping(status.get("byte_role_validation"))
    if validation is not None:
        candidates.append(validation.get("docket_entry_number"))
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _text_field(source: Mapping[str, Any], field: str) -> str | None:
    value = source.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _document_validation(
    candidate_id: str, status: Mapping[str, Any]
) -> DocumentValidation:
    validation_map = _as_mapping(status.get("byte_role_validation"))
    evidence_map = _as_mapping(status.get("acquired_evidence")) or {}
    source_document_id = None
    for candidate_source in (validation_map or {}, evidence_map, status):
        source_document_id = _text_field(candidate_source, "source_document_id")
        if source_document_id:
            break
    expected_role = None
    if validation_map is not None:
        expected_role = _text_field(validation_map, "expected_role")
    if expected_role is None:
        for field in ("acquired_document_role", "document_role", "role"):
            expected_role = _text_field(status, field)
            if expected_role:
                break
    return DocumentValidation(
        candidate_id=candidate_id,
        entry_number=_entry_number(status),
        source_document_id=source_document_id,
        expected_role=expected_role,
        acquisition_status=_text_field(status, "acquisition_status"),
        verdict=current_validation_verdict(validation_map),
        validation_basis=(
            _text_field(validation_map, "validation_basis")
            if validation_map is not None
            else None
        ),
    )


def _mismatch_entry_number(mismatch: Mapping[str, Any]) -> int | None:
    value = mismatch.get("entry")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def build_candidate_validation_view(row: Mapping[str, Any]) -> CandidateValidationView:
    """Build the canonical validation view for one adjudication worksheet row.

    ``row`` is a worksheet/overlay record carrying ``candidate_id``,
    ``missing_document_status`` and ``byte_mismatches``.
    """

    candidate_id = _text_field(row, "candidate_id") or ""
    documents = tuple(
        _document_validation(candidate_id, status)
        for status in _as_rows(row.get("missing_document_status"))
    )
    verdict_by_entry: dict[int, list[str]] = {}
    for document in documents:
        if document.entry_number is not None:
            verdict_by_entry.setdefault(document.entry_number, []).append(
                document.verdict
            )

    mismatches: list[MismatchResolution] = []
    for mismatch in _as_rows(row.get("byte_mismatches")):
        entry_number = _mismatch_entry_number(mismatch)
        verdicts = verdict_by_entry.get(entry_number or -1, [])
        if MATCH_VERDICT in verdicts:
            current = MATCH_VERDICT
        else:
            current = next(
                (verdict for verdict in verdicts if verdict != NOT_VALIDATED),
                NOT_VALIDATED,
            )
        mismatches.append(
            MismatchResolution(
                candidate_id=candidate_id,
                entry_number=entry_number,
                selected_role=_text_field(mismatch, "selected_role"),
                observed_role=_text_field(mismatch, "observed_role"),
                recorded_verdict=_text_field(mismatch, "verdict"),
                current_verdict=current,
                evidence=_text_field(mismatch, "evidence"),
            )
        )
    return CandidateValidationView(
        candidate_id=candidate_id,
        documents=documents,
        mismatches=tuple(mismatches),
    )


def build_validation_views(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, CandidateValidationView]:
    """Build canonical validation views keyed by candidate id.

    Later rows for the same candidate replace earlier ones, matching how the
    overlay files are read (last record wins).
    """

    views: dict[str, CandidateValidationView] = {}
    for row in rows:
        view = build_candidate_validation_view(row)
        if view.candidate_id:
            views[view.candidate_id] = view
    return views

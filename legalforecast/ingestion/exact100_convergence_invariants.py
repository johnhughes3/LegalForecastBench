"""The deterministic final invariant suite for the exact-100 corpus.

This is the convergence gate that ends broad review: nine invariants that,
taken together, say the corpus is finished. It is expected to FAIL while
acquisitions and replacements are outstanding -- that is the point. Every
failure names the case, and where applicable the docket entry or document, that
blocks it, so the failure list is a work list rather than a verdict.

The suite performs no acquisition, no provider call, no model selection and no
byte re-derivation. It joins artifacts that already exist:

* the exact-100 normalized manifest projection (corpus membership, per-case
  required entries, outstanding documents),
* the needs-human adjudication overlay (acquisition and byte-role validation
  evidence),
* the owner disposition overlay (the legal decisions, each with an independent
  execution state),
* optionally corpus-wide held-document evidence, a parse-quality rejection
  artifact, and a replacement-validation artifact.

Verdicts are read through
:mod:`legalforecast.ingestion.adjudication_validation_view` so that the suite
and every renderer agree on what "validated" means. The vocabulary the
invariants speak -- failures, results, dispositions, inputs -- lives in
:mod:`legalforecast.ingestion.exact100_convergence_model`.

Where the evidence an invariant needs was not supplied, the invariant fails
with an ``evidence_gap`` rather than passing by default. A convergence gate
that passes for lack of looking is worse than no gate.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Final

from legalforecast.ingestion.adjudication_validation_view import (
    MATCH_VERDICT,
    NOT_VALIDATED,
    CandidateValidationView,
)
from legalforecast.ingestion.exact100_convergence_model import (
    BRIEFING_ROLES,
    COMPLETE,
    EXECUTION_STATES,
    PLEADING_ROLES,
    REQUIRED_CASE_COUNT,
    TARGET_MOTION_ROLES,
    ConvergenceInputs,
    ConvergenceReport,
    Disposition,
    InvariantFailure,
    InvariantResult,
    entries_of,
    mapping_of,
    rows_of,
    sequence_of,
    text_of,
)

__all__ = [
    "BRIEFING_ROLES",
    "PLEADING_ROLES",
    "REQUIRED_CASE_COUNT",
    "TARGET_MOTION_ROLES",
    "ConvergenceInputs",
    "ConvergenceReport",
    "Disposition",
    "InvariantFailure",
    "InvariantResult",
    "evaluate_convergence",
    "load_inputs",
]


def _candidate_id(row: Mapping[str, Any]) -> str:
    return text_of(row, "candidate_id") or ""


def _required_entries(row: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return rows_of(row.get("required_entries"))


def _outstanding_entries(row: Mapping[str, Any]) -> frozenset[int]:
    """Docket entries the audit recorded as not yet held."""

    return frozenset(entries_of(rows_of(row.get("missing_docs"))))


def _acquired_entries(view: CandidateValidationView | None) -> frozenset[int]:
    if view is None:
        return frozenset()
    return frozenset(
        document.entry_number
        for document in view.documents
        if document.entry_number is not None
        and document.acquisition_status == "acquired"
    )


def _effective_entries(
    row: Mapping[str, Any], disposition: Disposition | None
) -> tuple[tuple[int, str], ...]:
    """The case's final packet as (entry, role) pairs.

    Starts from the audit's required entries, applies the owner's relabels and
    drops, and removes anything the owner classified collateral or superseded.
    A disposition that states an explicit ``final_packet`` overrides entirely.
    """

    if disposition is not None and disposition.final_packet:
        declared: list[tuple[int, str]] = []
        for document in disposition.final_packet:
            role = text_of(document, "role") or ""
            for entry in entries_of([document]):
                declared.append((entry, role))
        return tuple(sorted(set(declared)))

    relabelled: dict[int, str] = {}
    if disposition is not None:
        for relabel in disposition.relabels:
            for entry in entries_of([relabel]):
                to_role = text_of(relabel, "to_role") or text_of(relabel, "to")
                if to_role:
                    relabelled[entry] = to_role

    removed: set[int] = set()
    if disposition is not None:
        removed |= set(disposition.dropped_entries)
        removed |= set(disposition.collateral_entries)
        removed |= set(disposition.superseded_entries)

    pairs: list[tuple[int, str]] = []
    for required in _required_entries(row):
        for entry in entries_of([required]):
            if entry in removed:
                continue
            role = relabelled.get(entry) or text_of(required, "role") or ""
            pairs.append((entry, role))
    return tuple(sorted(set(pairs)))


def _invariant_1(inputs: ConvergenceInputs) -> InvariantResult:
    key = "exactly_100_eligible_unique_cases"
    statement = "exactly 100 eligible unique cases"
    failures: list[InvariantFailure] = []
    ids = [_candidate_id(row) for row in inputs.corpus]
    seen: dict[str, int] = {}
    for candidate_id in ids:
        seen[candidate_id] = seen.get(candidate_id, 0) + 1
    for candidate_id, count in sorted(seen.items()):
        if count > 1:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail=f"appears {count} times in the corpus",
                )
            )
    dispositions = inputs.disposition_by_candidate
    excluded = sorted(
        candidate_id
        for candidate_id in seen
        if (disposition := dispositions.get(candidate_id)) is not None
        and disposition.excluded
    )
    validated_replacements = _validated_replacement_ids(inputs)
    eligible = len(seen) - len(
        [
            candidate_id
            for candidate_id in excluded
            if (dispositions[candidate_id].replacement_candidate_id or "")
            not in validated_replacements
        ]
    )
    for candidate_id in excluded:
        replacement = dispositions[candidate_id].replacement_candidate_id
        if replacement is None:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail=dispositions[candidate_id].unsourced_detail(),
                )
            )
        elif replacement not in validated_replacements:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail=(
                        f"owner-excluded; replacement {replacement} is not yet "
                        "fully validated, so the slot is unfilled"
                    ),
                )
            )
    if eligible != REQUIRED_CASE_COUNT:
        failures.append(
            InvariantFailure(
                invariant=key,
                detail=(
                    f"{eligible} eligible unique cases; the corpus requires "
                    f"exactly {REQUIRED_CASE_COUNT}"
                ),
            )
        )
    return InvariantResult(
        key=key, statement=statement, checked=len(ids), failures=tuple(failures)
    )


def _invariant_2(inputs: ConvergenceInputs) -> InvariantResult:
    key = "one_eligible_target_motion_per_case"
    statement = "one eligible target motion per case"
    failures: list[InvariantFailure] = []
    dispositions = inputs.disposition_by_candidate
    for row in inputs.corpus:
        candidate_id = _candidate_id(row)
        disposition = dispositions.get(candidate_id)
        if disposition is not None and disposition.excluded:
            continue
        targets = [
            entry
            for entry, role in _effective_entries(row, disposition)
            if role in TARGET_MOTION_ROLES
        ]
        if len(targets) != 1:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail=(
                        f"{len(targets)} target motions in the final packet"
                        + (f" (entries {sorted(targets)})" if targets else "")
                    ),
                )
            )
    return InvariantResult(
        key=key,
        statement=statement,
        checked=len(inputs.corpus),
        failures=tuple(failures),
    )


def _invariant_3(inputs: ConvergenceInputs) -> InvariantResult:
    key = "attacked_pleading_and_target_motion_present"
    statement = "attacked pleading + target motion present"
    failures: list[InvariantFailure] = []
    dispositions = inputs.disposition_by_candidate
    for row in inputs.corpus:
        candidate_id = _candidate_id(row)
        disposition = dispositions.get(candidate_id)
        if disposition is not None and disposition.excluded:
            continue
        view = inputs.validation_views.get(candidate_id)
        outstanding = _outstanding_entries(row) - _acquired_entries(view)
        effective = _effective_entries(row, disposition)
        for label, roles in (
            ("attacked pleading", PLEADING_ROLES),
            ("target motion", TARGET_MOTION_ROLES),
        ):
            present = [entry for entry, role in effective if role in roles]
            if not present:
                failures.append(
                    InvariantFailure(
                        invariant=key,
                        candidate_id=candidate_id,
                        detail=f"no {label} in the final packet",
                    )
                )
                continue
            for entry in present:
                if entry in outstanding:
                    failures.append(
                        InvariantFailure(
                            invariant=key,
                            candidate_id=candidate_id,
                            entry_number=entry,
                            detail=f"{label} is selected but not yet held",
                        )
                    )
    return InvariantResult(
        key=key,
        statement=statement,
        checked=len(inputs.corpus),
        failures=tuple(failures),
    )


def _invariant_4(inputs: ConvergenceInputs) -> InvariantResult:
    key = "docketed_target_motion_briefs_included_and_linked"
    statement = "every docketed target-motion brief included and linked"
    failures: list[InvariantFailure] = []
    dispositions = inputs.disposition_by_candidate
    for row in inputs.corpus:
        candidate_id = _candidate_id(row)
        disposition = dispositions.get(candidate_id)
        if disposition is not None and disposition.excluded:
            continue
        view = inputs.validation_views.get(candidate_id)
        held = _acquired_entries(view)
        outstanding = _outstanding_entries(row) - held
        excused: set[int] = set()
        if disposition is not None:
            excused = (
                set(disposition.dropped_entries)
                | set(disposition.collateral_entries)
                | set(disposition.superseded_entries)
            )
        target_entries = {
            entry
            for entry, role in _effective_entries(row, disposition)
            if role in TARGET_MOTION_ROLES
        }
        for required in _required_entries(row):
            role = text_of(required, "role") or ""
            if role not in BRIEFING_ROLES:
                continue
            for entry in entries_of([required]):
                if entry in excused:
                    continue
                if entry in outstanding:
                    failures.append(
                        InvariantFailure(
                            invariant=key,
                            candidate_id=candidate_id,
                            entry_number=entry,
                            detail=(f"docketed {role} is required but not yet held"),
                        )
                    )
                    continue
                linked = set(_link_targets(required))
                if target_entries and linked and not (linked & target_entries):
                    failures.append(
                        InvariantFailure(
                            invariant=key,
                            candidate_id=candidate_id,
                            entry_number=entry,
                            detail=(
                                f"{role} links to entries {sorted(linked)}, none of "
                                f"which is the target motion {sorted(target_entries)}"
                            ),
                        )
                    )
    return InvariantResult(
        key=key,
        statement=statement,
        checked=len(inputs.corpus),
        failures=tuple(failures),
    )


def _link_targets(required: Mapping[str, Any]) -> list[int]:
    entries: list[int] = []
    for item in sequence_of(required.get("linked_motion_entries")):
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            entries.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            entries.append(int(item.strip()))
    return entries


def _invariant_5(inputs: ConvergenceInputs) -> InvariantResult:
    key = "superseded_filings_removed"
    statement = "superseded filings removed"
    failures: list[InvariantFailure] = []
    checked = 0
    dispositions = inputs.disposition_by_candidate
    for row in inputs.corpus:
        candidate_id = _candidate_id(row)
        disposition = dispositions.get(candidate_id)
        if disposition is None:
            continue
        effective = {entry for entry, _ in _effective_entries(row, disposition)}
        for superseded in disposition.superseded:
            for entry in entries_of([superseded]):
                checked += 1
                if entry in effective:
                    failures.append(
                        InvariantFailure(
                            invariant=key,
                            candidate_id=candidate_id,
                            entry_number=entry,
                            detail=(
                                "recorded as superseded by "
                                f"E{superseded.get('superseded_by_entry')} but still "
                                "in the final packet"
                            ),
                        )
                    )
    return InvariantResult(
        key=key, statement=statement, checked=checked, failures=tuple(failures)
    )


def _invariant_6(inputs: ConvergenceInputs) -> InvariantResult:
    key = "no_collateral_filing_linked_as_target_briefing"
    statement = "no collateral filing linked as target briefing"
    failures: list[InvariantFailure] = []
    checked = 0
    corpus_by_id = {_candidate_id(row): row for row in inputs.corpus}
    for disposition in inputs.dispositions:
        row = corpus_by_id.get(disposition.candidate_id)
        if row is None:
            continue
        effective = {entry for entry, _ in _effective_entries(row, disposition)}
        for entry in sorted(disposition.collateral_entries):
            checked += 1
            if entry in effective:
                failures.append(
                    InvariantFailure(
                        invariant=key,
                        candidate_id=disposition.candidate_id,
                        entry_number=entry,
                        detail=(
                            "classified collateral by the owner but still linked as "
                            "target briefing"
                        ),
                    )
                )
        for entry in sorted(disposition.dropped_entries):
            checked += 1
            if entry in effective:
                failures.append(
                    InvariantFailure(
                        invariant=key,
                        candidate_id=disposition.candidate_id,
                        entry_number=entry,
                        detail="dropped by the owner but still in the final packet",
                    )
                )
    return InvariantResult(
        key=key, statement=statement, checked=checked, failures=tuple(failures)
    )


def _parse_rejections(inputs: ConvergenceInputs) -> dict[tuple[str, str], str]:
    """Map (candidate_id, source_document_id) -> rejection reason."""

    rejections: dict[tuple[str, str], str] = {}
    payload = inputs.parse_quality
    if payload is None:
        return rejections
    raw = payload.get("rejected") or payload.get("records") or payload.get("flags")
    for record in rows_of(raw):
        candidate_id = text_of(record, "candidate_id")
        document_id = text_of(record, "source_document_id")
        if candidate_id and document_id:
            rejections[(candidate_id, document_id)] = (
                text_of(record, "reason") or "rejected by the parse-quality sweep"
            )
    return rejections


def _invariant_7(inputs: ConvergenceInputs) -> InvariantResult:
    key = "selected_documents_parseable_and_byte_role_validated"
    statement = "every selected document parseable and byte-role validated"
    failures: list[InvariantFailure] = []
    checked = 0
    dispositions = inputs.disposition_by_candidate
    if inputs.parse_quality is None:
        failures.append(
            InvariantFailure(
                invariant=key,
                detail=(
                    "evidence_gap: no parse-quality artifact supplied, so document "
                    "parseability cannot be asserted"
                ),
            )
        )
    rejections = _parse_rejections(inputs)
    for row in inputs.corpus:
        candidate_id = _candidate_id(row)
        disposition = dispositions.get(candidate_id)
        if disposition is not None and disposition.excluded:
            continue
        view = inputs.validation_views.get(candidate_id)
        effective = _effective_entries(row, disposition)
        if view is None:
            # Cases outside the needs-human set carry no per-document validation
            # evidence in this artifact set; the gap is named, not assumed away.
            checked += len(effective)
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail=(
                        "evidence_gap: no byte-role validation evidence supplied "
                        "for this case"
                    ),
                )
            )
            continue
        for entry, role in effective:
            checked += 1
            verdict = view.verdict_for_entry(entry)
            if verdict == NOT_VALIDATED:
                failures.append(
                    InvariantFailure(
                        invariant=key,
                        candidate_id=candidate_id,
                        entry_number=entry,
                        detail=f"selected {role} carries no byte-role validation",
                    )
                )
            elif verdict != MATCH_VERDICT:
                failures.append(
                    InvariantFailure(
                        invariant=key,
                        candidate_id=candidate_id,
                        entry_number=entry,
                        detail=(
                            f"byte-role verdict for the selected {role} is {verdict}"
                        ),
                    )
                )
            for document in view.documents:
                if document.entry_number != entry or not document.source_document_id:
                    continue
                reason = rejections.get((candidate_id, document.source_document_id))
                if reason:
                    failures.append(
                        InvariantFailure(
                            invariant=key,
                            candidate_id=candidate_id,
                            entry_number=entry,
                            source_document_id=document.source_document_id,
                            detail=f"parse-quality rejection: {reason}",
                        )
                    )
    return InvariantResult(
        key=key, statement=statement, checked=checked, failures=tuple(failures)
    )


def _validated_replacement_ids(inputs: ConvergenceInputs) -> frozenset[str]:
    if not inputs.replacements:
        return frozenset()
    validated: set[str] = set()
    for record in inputs.replacements:
        candidate_id = text_of(record, "candidate_id")
        if candidate_id and record.get("fully_validated") is True:
            validated.add(candidate_id)
    return frozenset(validated)


def _invariant_8(inputs: ConvergenceInputs) -> InvariantResult:
    key = "replacements_fully_validated"
    statement = "every replacement fully validated"
    failures: list[InvariantFailure] = []
    excluded = [
        disposition for disposition in inputs.dispositions if disposition.excluded
    ]
    by_replacement = {
        text_of(record, "candidate_id"): record
        for record in (inputs.replacements or ())
    }
    for disposition in excluded:
        replacement = disposition.replacement_candidate_id
        if replacement is None:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=disposition.candidate_id,
                    detail=disposition.unsourced_detail(),
                )
            )
            continue
        record = by_replacement.get(replacement)
        if record is None:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=replacement,
                    detail=(
                        "evidence_gap: no replacement-validation record for the "
                        f"successor to {disposition.candidate_id}"
                    ),
                )
            )
            continue
        if record.get("fully_validated") is not True:
            outstanding = sequence_of(record.get("outstanding_documents"))
            detail = "replacement is not fully validated"
            if outstanding:
                detail = f"{detail}; outstanding {list(outstanding)}"
            failures.append(
                InvariantFailure(invariant=key, candidate_id=replacement, detail=detail)
            )
    return InvariantResult(
        key=key, statement=statement, checked=len(excluded), failures=tuple(failures)
    )


def _invariant_9(inputs: ConvergenceInputs) -> InvariantResult:
    key = "owner_and_corpus_state_reconciled"
    statement = "owner/corpus state reconciled"
    failures: list[InvariantFailure] = []
    dispositions = inputs.disposition_by_candidate
    corpus_ids = {_candidate_id(row) for row in inputs.corpus}
    checked = 0
    for row in inputs.adjudication:
        candidate_id = _candidate_id(row)
        if text_of(row, "decision_status") != "pending_human_adjudication":
            continue
        checked += 1
        if candidate_id not in dispositions:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=candidate_id,
                    detail="pending adjudication row carries no owner disposition",
                )
            )
    for disposition in inputs.dispositions:
        checked += 1
        if disposition.execution_state not in EXECUTION_STATES:
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=disposition.candidate_id,
                    detail=(
                        f"execution state {disposition.execution_state!r} is not one "
                        "of ready/blocked/complete"
                    ),
                )
            )
            continue
        if disposition.execution_state != COMPLETE:
            blocked_on = disposition.execution_blocked_on or "not yet executed"
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=disposition.candidate_id,
                    detail=(
                        f"disposition {disposition.decision!r} is "
                        f"{disposition.execution_state} ({blocked_on})"
                    ),
                )
            )
        if (
            disposition.in_corpus
            and disposition.candidate_id
            and disposition.candidate_id not in corpus_ids
        ):
            failures.append(
                InvariantFailure(
                    invariant=key,
                    candidate_id=disposition.candidate_id,
                    detail="disposition references a case absent from the corpus",
                )
            )
    return InvariantResult(
        key=key, statement=statement, checked=checked, failures=tuple(failures)
    )


_INVARIANTS: Final = (
    _invariant_1,
    _invariant_2,
    _invariant_3,
    _invariant_4,
    _invariant_5,
    _invariant_6,
    _invariant_7,
    _invariant_8,
    _invariant_9,
)


def evaluate_convergence(inputs: ConvergenceInputs) -> ConvergenceReport:
    """Run all nine invariants in their declared order."""

    return ConvergenceReport(
        results=tuple(invariant(inputs) for invariant in _INVARIANTS)
    )


def load_jsonl(payload: str) -> tuple[Mapping[str, Any], ...]:
    """Parse JSON Lines text into mapping records, ignoring blank lines."""

    records: list[Mapping[str, Any]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        row = mapping_of(json.loads(line))
        if row is not None:
            records.append(row)
    return tuple(records)


def load_inputs(
    *,
    corpus_text: str,
    adjudication_text: str,
    dispositions_text: str,
    parse_quality_text: str | None = None,
    replacements_text: str | None = None,
    acquisitions_text: str | None = None,
) -> ConvergenceInputs:
    """Build :class:`ConvergenceInputs` from raw artifact text."""

    parse_quality: Mapping[str, Any] | None = None
    if parse_quality_text is not None:
        parse_quality = mapping_of(json.loads(parse_quality_text))
    replacements: tuple[Mapping[str, Any], ...] | None = None
    if replacements_text is not None:
        replacements = load_jsonl(replacements_text)
    return ConvergenceInputs.build(
        corpus=load_jsonl(corpus_text),
        adjudication=load_jsonl(adjudication_text),
        dispositions=load_jsonl(dispositions_text),
        parse_quality=parse_quality,
        replacements=replacements,
        acquisitions=(
            None if acquisitions_text is None else load_jsonl(acquisitions_text)
        ),
    )

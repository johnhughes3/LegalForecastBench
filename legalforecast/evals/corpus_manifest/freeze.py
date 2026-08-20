"""Freeze the current corpus state into one owner-signable manifest.

Every hash in the emitted manifest is computed fresh from the bytes on disk at
freeze time.  The freeze fails closed, and it collects **every** violation
before refusing, so one run enumerates the complete cure list rather than
surfacing blockers one at a time.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import read_jsonl_objects
from legalforecast.contracts.commitments import RAW_BYTES_RAW_SHA256_V1
from legalforecast.contracts.schemas import OWNER_SIGNED_CORPUS_MANIFEST_V1
from legalforecast.evals.corpus_manifest.schema import (
    AUDIT_ONLY_DOCUMENT_ROLES,
    MODEL_VISIBLE_DOCUMENT_ROLES,
    REQUIRED_CLAIM_BEARING_ROLES,
    REQUIRED_TARGET_MOTION_ROLES,
    BoundSource,
    CorpusManifest,
    CorpusManifestError,
    ManifestCase,
    ManifestDocument,
)
from legalforecast.evals.corpus_manifest.stores import (
    StoredDocument,
    VerdictRecord,
    index_document_store,
    index_verdicts,
)
from legalforecast.ingestion.provenance import DocumentRole

# The verdict stores speak a repair vocabulary that is deliberately not the
# packet DocumentRole vocabulary.  Each spelling is mapped positively to the
# packet roles it may certify; an unmapped spelling is a hard refusal, and a
# spelling that certifies no packet role at all (a cover sheet is not a
# pleading) maps to the empty set and therefore always refuses.
VERDICT_ROLE_COMPATIBILITY: Final[Mapping[str, frozenset[DocumentRole]]] = {
    "amended_complaint": frozenset({DocumentRole.AMENDED_COMPLAINT}),
    "amended_reply": frozenset({DocumentRole.REPLY}),
    "complaint": frozenset({DocumentRole.COMPLAINT}),
    "counterclaim": frozenset({DocumentRole.COUNTERCLAIM}),
    "cover_sheet": frozenset(),
    "crossclaim": frozenset({DocumentRole.CROSSCLAIM}),
    "decision": frozenset({DocumentRole.DECISION}),
    "docket_history": frozenset({DocumentRole.DOCKET_HISTORY}),
    "interpleader_complaint": frozenset({DocumentRole.INTERPLEADER_COMPLAINT}),
    "motion_memorandum": frozenset({DocumentRole.MTD_MEMORANDUM}),
    "motion_to_dismiss_memorandum": frozenset({DocumentRole.MTD_MEMORANDUM}),
    "motion_to_dismiss_notice": frozenset({DocumentRole.MTD_NOTICE}),
    "opening_memorandum": frozenset({DocumentRole.MTD_MEMORANDUM}),
    "operative_pleading": frozenset(
        {DocumentRole.COMPLAINT, DocumentRole.AMENDED_COMPLAINT}
    ),
    "opposition": frozenset({DocumentRole.OPPOSITION}),
    "other_claim_bearing_filing": frozenset({DocumentRole.OTHER_CLAIM_BEARING}),
    "reply": frozenset({DocumentRole.REPLY}),
    "response": frozenset({DocumentRole.OPPOSITION}),
    "supplemental_brief": frozenset({DocumentRole.SUPPLEMENTAL_BRIEF}),
    "surreply": frozenset({DocumentRole.SURREPLY}),
    "third_party_complaint": frozenset({DocumentRole.THIRD_PARTY_COMPLAINT}),
    "target_motion": frozenset({DocumentRole.MTD_MEMORANDUM, DocumentRole.MTD_NOTICE}),
}


class CorpusFreezeRefused(CorpusManifestError):
    """Raised when the corpus cannot be frozen, carrying every blocker found."""

    def __init__(self, violations: Sequence[str]) -> None:
        self.violations = tuple(violations)
        super().__init__(
            f"corpus freeze refused with {len(self.violations)} blocker(s):\n"
            + "\n".join(f"  - {violation}" for violation in self.violations)
        )


@dataclass(frozen=True, slots=True)
class FreezeInputs:
    """Every input the freeze reads, named explicitly."""

    selection_path: Path
    prediction_units_path: Path
    document_store_roots: tuple[Path, ...]
    verdict_sources: tuple[Path, ...]
    cycle_id: str
    generated_at: str


def freeze_corpus_manifest(inputs: FreezeInputs) -> CorpusManifest:
    """Freeze the selected corpus into a manifest, or refuse with every blocker."""

    selection = _selection_records(inputs.selection_path)
    unit_candidates = _prediction_unit_candidates(inputs.prediction_units_path)
    documents = index_document_store(inputs.document_store_roots)
    verdicts = index_verdicts(inputs.verdict_sources)

    violations: list[str] = []
    cases: list[ManifestCase] = []
    for record in selection:
        case = _manifest_case(
            record,
            documents=documents,
            verdicts=verdicts,
            violations=violations,
        )
        if case is not None:
            cases.append(case)
        candidate_id = _text(record.get("candidate_id"))
        if candidate_id and candidate_id not in unit_candidates:
            violations.append(
                f"{candidate_id}: no scorable prediction units in "
                f"{inputs.prediction_units_path.name}"
            )
    if violations:
        raise CorpusFreezeRefused(violations)
    return CorpusManifest(
        cycle_id=inputs.cycle_id,
        generated_at=inputs.generated_at,
        selection_source=_bound_source(inputs.selection_path),
        prediction_units_source=_bound_source(inputs.prediction_units_path),
        cases=tuple(cases),
    )


def _manifest_case(
    record: Mapping[str, Any],
    *,
    documents: Mapping[str, StoredDocument],
    verdicts: Mapping[str, tuple[VerdictRecord, ...]],
    violations: list[str],
) -> ManifestCase | None:
    candidate_id = _text(record.get("candidate_id"))
    if not candidate_id:
        violations.append("selection row has no candidate_id")
        return None
    rows = record.get("documents")
    if not isinstance(rows, list) or not rows:
        violations.append(f"{candidate_id}: selection row has no documents")
        return None

    manifest_documents: list[ManifestDocument] = []
    unresolved_audit_only: list[str] = []
    for row in cast("list[object]", rows):
        if not isinstance(row, Mapping):
            violations.append(f"{candidate_id}: malformed document row")
            continue
        document = _manifest_document(
            cast("Mapping[str, Any]", row),
            candidate_id=candidate_id,
            documents=documents,
            verdicts=verdicts,
            violations=violations,
            unresolved_audit_only=unresolved_audit_only,
        )
        if document is not None:
            manifest_documents.append(document)
    if not manifest_documents:
        return None

    visible_roles = {
        document.document_role
        for document in manifest_documents
        if document.model_visible
    }
    if not visible_roles & REQUIRED_CLAIM_BEARING_ROLES:
        violations.append(
            f"{candidate_id}: no model-visible claim-bearing pleading "
            "(complaint family) survives the freeze"
        )
    if not visible_roles & REQUIRED_TARGET_MOTION_ROLES:
        violations.append(
            f"{candidate_id}: no model-visible target motion-to-dismiss paper "
            "survives the freeze"
        )
    try:
        return ManifestCase(
            candidate_id=candidate_id,
            case_id=_text(record.get("case_id")) or candidate_id,
            court=_text(record.get("court")) or "unknown",
            docket_number=_text(record.get("docket_number")) or "unknown",
            documents=tuple(manifest_documents),
            decision_date=_text(record.get("decision_date")) or None,
            target_motion_entry_numbers=_int_tuple(
                record.get("target_motion_entry_numbers")
            ),
            unresolved_audit_only_document_ids=tuple(sorted(unresolved_audit_only)),
        )
    except CorpusManifestError as exc:
        violations.append(f"{candidate_id}: {exc}")
        return None


def _manifest_document(
    row: Mapping[str, Any],
    *,
    candidate_id: str,
    documents: Mapping[str, StoredDocument],
    verdicts: Mapping[str, tuple[VerdictRecord, ...]],
    violations: list[str],
    unresolved_audit_only: list[str],
) -> ManifestDocument | None:
    document_id = _text(row.get("source_document_id"))
    if not document_id:
        violations.append(f"{candidate_id}: document row has no source_document_id")
        return None
    label = f"{candidate_id}/{document_id}"

    raw_role = _text(row.get("document_role"))
    try:
        role = DocumentRole(raw_role)
    except ValueError:
        violations.append(f"{label}: unknown document_role '{raw_role}'")
        return None

    model_visible = bool(row.get("model_visible"))
    if model_visible and role in AUDIT_ONLY_DOCUMENT_ROLES:
        violations.append(
            f"{label}: role '{role.value}' is audit-only and may never be model-visible"
        )
        return None
    if model_visible and role not in MODEL_VISIBLE_DOCUMENT_ROLES:
        violations.append(
            f"{label}: role '{role.value}' is not classified model-visible"
        )
        return None

    stored = documents.get(document_id)
    if stored is None:
        if model_visible:
            violations.append(
                f"{label}: role '{role.value}' has no parsed document in any store"
            )
            return None
        # Audit-only bytes the forecast never reads.  Record the gap on the
        # case instead of blocking a run that does not depend on them.
        unresolved_audit_only.append(document_id)
        return None

    pdf_sha256 = _file_digest(stored.pdf_path, label=label, violations=violations)
    if pdf_sha256 is None:
        return None
    markdown_sha256 = _file_digest(
        stored.markdown_path,
        label=label,
        violations=violations,
    )
    if markdown_sha256 is None and model_visible:
        return None

    verdict = None
    if model_visible:
        verdict = _accepted_verdict(
            document_id,
            role=role,
            label=label,
            verdicts=verdicts,
            violations=violations,
        )
        if verdict is None:
            return None

    try:
        return ManifestDocument(
            source_document_id=document_id,
            document_role=role,
            model_visible=model_visible,
            pdf_path=str(stored.pdf_path),
            pdf_sha256=pdf_sha256,
            source_url=_text(row.get("source_url"))
            or _text(row.get("source_url_or_reference"))
            or "unrecorded",
            markdown_path=str(stored.markdown_path)
            if markdown_sha256 is not None
            else None,
            markdown_sha256=markdown_sha256,
            docket_entry_number=_positive_int(row.get("docket_entry_number")),
            byte_role_verdict=verdict.verdict if verdict is not None else None,
            validation_basis=verdict.validation_basis if verdict is not None else None,
        )
    except CorpusManifestError as exc:
        violations.append(f"{label}: {exc}")
        return None


def _accepted_verdict(
    document_id: str,
    *,
    role: DocumentRole,
    label: str,
    verdicts: Mapping[str, tuple[VerdictRecord, ...]],
    violations: list[str],
) -> VerdictRecord | None:
    """Return the accepting verdict for a model-visible document, or refuse.

    A verdict certifies what the BYTES are, so the selection's role must be
    compatible with the role the verdict CERTIFIED — never with the role the
    corpus claimed when the act ran.  Trusting the claim would compare the
    corpus against its own earlier belief, and would let a stale claim rescue
    a mislabel the bytes contradict.  This is the check that catches a document
    whose role was adjudicated away from the one the corpus still names.
    """

    records = verdicts.get(document_id)
    if not records:
        violations.append(
            f"{label}: model-visible with no byte-role validation verdict"
        )
        return None
    refusals = [record for record in records if record.is_refusal]
    if refusals:
        violations.append(
            f"{label}: byte-role verdict refuses this document "
            f"({refusals[0].verdict} in {refusals[0].source})"
        )
        return None
    accepted = [record for record in records if record.is_accepted]
    if not accepted:
        violations.append(
            f"{label}: no byte-role verdict of match or adjudicated "
            f"(found {', '.join(sorted({record.verdict for record in records}))})"
        )
        return None
    roleless = [record for record in accepted if record.certified_role is None]
    if roleless:
        # C1: the verdict field fails closed but the role field used to fail
        # open here.  A verdict with no readable role certifies nothing about
        # WHICH role the bytes carry, so it cannot clear a document the model
        # will read: the visibility partition only checks the role the corpus
        # CLAIMS, and this cross-check is the only thing that checks the role
        # the bytes actually have.  Audit-only documents are exempt because
        # they never enter a packet under any role.
        violations.append(
            f"{label}: byte-role verdict in {roleless[0].source} carries no "
            "readable role, so it cannot certify a model-visible document; "
            "record the role it validated"
        )
        return None
    for record in accepted:
        if record.certified_role is None:  # pragma: no cover - refused above
            continue
        compatible = VERDICT_ROLE_COMPATIBILITY.get(record.certified_role)
        if compatible is None:
            violations.append(
                f"{label}: verdict store role '{record.certified_role}' is "
                "unclassified; "
                "map it before it can certify a packet role"
            )
            return None
        if role not in compatible:
            violations.append(
                f"{label}: selection claims role '{role.value}' but the "
                f"byte-role verdict certifies '{record.certified_role}'"
                + (
                    ""
                    if record.claimed_role in (None, record.certified_role)
                    else (
                        f" (the validation act recorded the corpus claim as "
                        f"'{record.claimed_role}' at the time; correct the "
                        "selection, not the verdict)"
                    )
                )
            )
            return None
    return accepted[0]


def _file_digest(
    path: Path,
    *,
    label: str,
    violations: list[str],
) -> str | None:
    try:
        payload = path.read_bytes()
    except OSError:
        violations.append(f"{label}: file missing or unreadable: {path.name}")
        return None
    commitment = RAW_BYTES_RAW_SHA256_V1.commit(
        payload,
        domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
    )
    return str(commitment.digest)


def _bound_source(path: Path) -> BoundSource:
    commitment = RAW_BYTES_RAW_SHA256_V1.commit(
        path.read_bytes(),
        domain=OWNER_SIGNED_CORPUS_MANIFEST_V1,
    )
    return BoundSource(path=str(path), sha256=str(commitment.digest))


def _selection_records(path: Path) -> tuple[Mapping[str, Any], ...]:
    records = read_jsonl_objects(
        path,
        error_factory=CorpusManifestError,
        missing_message=lambda missing: f"selection not found: {missing}",
        non_object_message=lambda bad, line: (
            f"selection row {line} in {bad} is not an object"
        ),
    )
    selected = tuple(
        record for record in records if record.get("selected", True) is not False
    )
    if not selected:
        raise CorpusManifestError(f"selection has no selected rows: {path}")
    return selected


def _prediction_unit_candidates(path: Path) -> frozenset[str]:
    records = read_jsonl_objects(
        path,
        error_factory=CorpusManifestError,
        missing_message=lambda missing: f"prediction units not found: {missing}",
        non_object_message=lambda bad, line: (
            f"prediction unit row {line} in {bad} is not an object"
        ),
    )
    return frozenset(
        candidate_id
        for record in records
        if (candidate_id := _text(record.get("candidate_id")))
        and _has_scorable_units(record.get("prediction_units"))
    )


def _has_scorable_units(value: object) -> bool:
    """Return whether a case has a unit the prompt can actually ask about.

    ``render_model_prompt`` refuses a packet whose units are all unscorable, so
    a case with only unscorable units is a freeze-time blocker rather than a
    surprise at build time.
    """

    if not isinstance(value, list):
        return False
    return any(
        isinstance(unit, Mapping)
        and cast("Mapping[str, Any]", unit).get("should_score", True) is not False
        for unit in cast("list[object]", value)
    )


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _int_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return ()
    return tuple(
        item
        for item in cast("Iterable[object]", value)
        if isinstance(item, int) and not isinstance(item, bool) and item > 0
    )

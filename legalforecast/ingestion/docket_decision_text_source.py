"""Authenticated lineage for audit-only CourtListener docket decision text.

This module deliberately separates source replay from downstream authority.  A
screening snapshot can prove that public docket-entry text is the first written
MTD disposition, but that fact alone does not authorize omitting a selected PDF.
The terminal-purchase verifier supplies that second authority in the composed
entry point added by the acquisition pipeline.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from types import MappingProxyType
from typing import Any, Final, cast

from legalforecast.ingestion.case_dev_purchase import CaseDevPurchaseJournal
from legalforecast.ingestion.courtlistener_dates import parse_courtlistener_filed_date
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.docket_sync import NormalizedDocketEntry
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.screening_snapshot_union import (
    UnionRawArtifact,
    VerifiedScreeningSnapshot,
)
from legalforecast.ingestion.screening_union_policy_rebind import (
    POLICY_DELTA_NAME,
    POLICY_PROOF_SCHEMA,
)
from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)
from legalforecast.ingestion.terminal_purchase_failure import (
    TerminalPurchaseFailureError,
    VerifiedTerminalPurchaseFailureAuthority,
    verified_terminal_retrieval_records,
)
from legalforecast.selection.motion_linkage import link_mtd_dispositions

JsonRecord = dict[str, Any]

DOCKET_DECISION_TEXT_SOURCE_SCHEMA: Final = (
    "legalforecast.docket_decision_text_source.v1"
)
TERMINAL_PURCHASE_DISPOSITION_SCHEMA: Final = (
    "legalforecast.terminal_purchase_disposition.v1"
)
RAW_COURTLISTENER_HTML_BASIS: Final = "raw_courtlistener_html"
MANIFEST_BOUND_REST_BASIS: Final = "manifest_bound_canonical_rest_screen"
_SOURCE_KIND: Final = "authenticated_docket_entry_text"
_LINEAGE_ISSUER = object()
_DISPOSITION_ISSUER = object()

_ROLE_MAP: Final = {
    CourtListenerEntryRole.MTD_NOTICE: DocumentRole.MTD_NOTICE,
    CourtListenerEntryRole.MTD_MEMORANDUM: DocumentRole.MTD_MEMORANDUM,
    CourtListenerEntryRole.OPPOSITION: DocumentRole.OPPOSITION,
    CourtListenerEntryRole.REPLY: DocumentRole.REPLY,
    CourtListenerEntryRole.EXHIBIT: DocumentRole.OTHER,
    CourtListenerEntryRole.DECISION: DocumentRole.DECISION,
    CourtListenerEntryRole.OTHER: DocumentRole.OTHER,
}


class DocketDecisionTextSourceError(ValueError):
    """Raised when docket text cannot be authenticated as the selected decision."""


class ReplayedDocketDecisionLineage:
    """Opaque source replay; it is not omission or materialization authority."""

    __slots__ = (
        "_issuer",
        "_record_bytes",
        "selection_payload_sha256",
        "snapshot_manifest_sha256",
    )

    def __init__(self) -> None:
        raise TypeError("docket decision lineage is issued only by its verifier")


class VerifiedDocketDecisionTextSources:
    """Opaque verified source set before downstream omission authority is exposed."""

    __slots__ = ("_authority", "_issuer")

    def __init__(self) -> None:
        raise TypeError("docket decision sources are issued only by their verifier")

    def terminal_purchase_disposition_authority(
        self,
        *,
        purchase_journal: CaseDevPurchaseJournal,
    ) -> VerifiedTerminalPurchaseDispositionAuthority:
        """Return the shared omission/residual authority after fresh replay."""

        if getattr(self, "_issuer", None) is not _DISPOSITION_ISSUER or not isinstance(
            getattr(self, "_authority", None),
            VerifiedTerminalPurchaseDispositionAuthority,
        ):
            raise DocketDecisionTextSourceError(
                "docket decision source set was not issued by its verifier"
            )
        _replay_terminal_disposition(self._authority, purchase_journal)
        return self._authority


class VerifiedTerminalPurchaseDispositionAuthority:
    """Opaque exhaustive partition of fresh terminal purchase failures."""

    __slots__ = (
        "_disposition_bytes",
        "_docket_lineages",
        "_issuer",
        "_residual_exclusions_bytes",
        "_terminal_failure_authority",
        "purchase_journal_state_sha256",
        "selection_payload_sha256",
        "snapshot_manifest_sha256",
    )

    def __init__(self) -> None:
        raise TypeError(
            "terminal purchase disposition authority is issued only by its verifier"
        )


def replay_docket_decision_source_lineage(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    selection_payload_sha256: str,
    screening_snapshot: VerifiedScreeningSnapshot,
    candidate_id: str,
    unavailable_recap_document_id: str,
) -> ReplayedDocketDecisionLineage:
    """Replay one source from already authenticated selection/snapshot inputs.

    This private seam exists so the eventual public verifier can compose it
    with ``VerifiedTerminalPurchaseFailureAuthority``.  It intentionally
    returns no capability accepted by a materializer or packet planner.
    """

    selection_sha256 = _sha256(selection_payload_sha256, "selection payload")
    selections = _selection_index(selection_records)
    selection = selections.get(candidate_id)
    if selection is None:
        raise DocketDecisionTextSourceError(
            "docket decision candidate is absent from the frozen selection: "
            f"{candidate_id}"
        )
    _require_selection_identity(selection, candidate_id)

    snapshot_candidate_id = f"courtlistener-docket-{candidate_id}"
    screens = _screen_index(screening_snapshot.screened)
    evidence = screens.get(snapshot_candidate_id)
    if evidence is None:
        raise DocketDecisionTextSourceError(
            "selected candidate is absent from the authenticated screening snapshot"
        )
    try:
        validate_strict_screen_evidence(
            evidence,
            expected_candidate_id=snapshot_candidate_id,
        )
    except StrictScreenEvidenceError as exc:
        raise DocketDecisionTextSourceError(
            "screening snapshot does not contain valid strict MTD evidence"
        ) from exc

    decision_document = _selected_decision_document(
        selection,
        unavailable_recap_document_id=unavailable_recap_document_id,
    )
    decision_entry_number = str(
        _positive_int(decision_document.get("docket_entry_number"), "decision entry")
    )
    selected_decision_numbers = _positive_int_list(
        selection.get("decision_entry_numbers"),
        "selection decision entry numbers",
    )
    if selected_decision_numbers != (int(decision_entry_number),):
        raise DocketDecisionTextSourceError(
            "selection does not identify exactly the unavailable decision entry"
        )
    target_motion_numbers = tuple(
        str(value)
        for value in _positive_int_list(
            selection.get("target_motion_entry_numbers"),
            "selection target motion entry numbers",
        )
    )
    screen_ai = _mapping(evidence.get("ai"), "screen AI selection evidence")
    authenticated_target_motion_numbers = tuple(
        str(value)
        for value in _positive_intish_list(
            screen_ai.get("target_motion_entry_numbers"),
            "screen target motion entry numbers",
        )
    )
    authenticated_decision_numbers = _positive_intish_list(
        screen_ai.get("decision_entry_numbers"),
        "screen decision entry numbers",
    )
    if target_motion_numbers != authenticated_target_motion_numbers:
        raise DocketDecisionTextSourceError(
            "selection target motions differ from authenticated screening evidence"
        )
    if selected_decision_numbers != authenticated_decision_numbers:
        raise DocketDecisionTextSourceError(
            "selection decisions differ from authenticated screening evidence"
        )
    selected_entries = _selected_entries(evidence)
    decision_entry = _unique_entry(
        selected_entries,
        entry_number=decision_entry_number,
    )
    text = _required_string(decision_entry.get("text"), "decision entry text")
    if not _selection_description_matches_entry(decision_document, decision_entry):
        raise DocketDecisionTextSourceError(
            "selected decision description differs from its authenticated docket entry"
        )
    entered_date = _canonical_date(
        evidence.get("first_written_mtd_disposition_date"),
        "first written disposition date",
    )
    anchor_date = _canonical_date(
        evidence.get("eligibility_anchor_date"),
        "eligibility anchor date",
    )
    if entered_date < anchor_date:
        raise DocketDecisionTextSourceError(
            "docket decision text predates the eligibility anchor"
        )
    if selection.get("decision_date") != entered_date.isoformat():
        raise DocketDecisionTextSourceError(
            "selection and screening disposition dates differ"
        )

    _verify_decision_entry_is_public(decision_entry)
    page, basis, source_evidence = _reconstruct_source_page(
        screening_snapshot=screening_snapshot,
        evidence=evidence,
        snapshot_candidate_id=snapshot_candidate_id,
        docket_id=candidate_id,
    )
    _verify_source_identity(
        basis=basis,
        source_evidence=source_evidence,
        decision_document=decision_document,
        decision_entry=decision_entry,
        entered_date=entered_date,
        unavailable_recap_document_id=unavailable_recap_document_id,
    )
    _rerun_semantic_screen_and_linkage(
        page=page,
        evidence=evidence,
        docket_id=candidate_id,
        anchor_date=anchor_date,
    )

    manifest = screening_snapshot.manifest
    manifest_files = _mapping(manifest.get("files"), "snapshot manifest files")
    record: JsonRecord = {
        "schema_version": DOCKET_DECISION_TEXT_SOURCE_SCHEMA,
        "candidate_id": candidate_id,
        "case_id": _required_string(selection.get("case_id"), "selection case ID"),
        "docket_id": candidate_id,
        "source_kind": _SOURCE_KIND,
        "source_basis": basis,
        "decision_source_id": f"docket-entry:{candidate_id}:{decision_entry_number}",
        "decision_entry_row_id": _required_string(
            decision_entry.get("row_id"), "decision row ID"
        ),
        "decision_entry_number": int(decision_entry_number),
        "decision_docket_entry_id": _positive_intish(
            decision_document.get("courtlistener_docket_entry_id"),
            "CourtListener docket entry ID",
        ),
        "unavailable_recap_document_id": unavailable_recap_document_id,
        "entered_date": entered_date.isoformat(),
        "target_motion_entry_numbers": [int(value) for value in target_motion_numbers],
        "text": text,
        "text_sha256": _bytes_sha256(text.encode()),
        "text_byte_count": len(text.encode()),
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "audit_only": True,
        "materialization_required": False,
        "selection_sha256": selection_sha256,
        "selection_record_sha256": _canonical_sha256(selection),
        "snapshot_manifest_sha256": _sha256(
            screening_snapshot.manifest_sha256,
            "snapshot manifest",
        ),
        "snapshot_cycle_hash": _sha256(
            manifest.get("cycle_hash"), "snapshot cycle hash"
        ),
        "snapshot_batch_id": _required_string(
            manifest.get("batch_id"), "snapshot batch ID"
        ),
        "snapshot_batch_digest": _sha256(
            manifest.get("batch_digest"), "snapshot batch digest"
        ),
        "snapshot_candidates_sha256": _manifest_file_sha256(
            manifest_files, "candidates.jsonl"
        ),
        "snapshot_screened_sha256": _manifest_file_sha256(
            manifest_files, "screened-cases.jsonl"
        ),
        "snapshot_raw_manifest_sha256": _manifest_file_sha256(
            manifest_files, "raw-artifacts.jsonl"
        ),
        "screen_record_sha256": _canonical_sha256(evidence),
        "strict_screen_sha256": _canonical_sha256(
            _mapping(evidence.get("mtd_decision_screen"), "strict screen")
        ),
        "motion_linkage_sha256": _canonical_sha256(
            _mapping(evidence.get("motion_linkage"), "motion linkage")
        ),
        "restriction_evidence": list(
            _string_list(
                decision_document.get("restriction_evidence"),
                "decision restriction evidence",
            )
        ),
        "source_evidence": source_evidence,
    }
    _validate_closed_source_record(record)
    return _issue_replayed_lineage(
        record=record,
        selection_payload_sha256=selection_sha256,
        snapshot_manifest_sha256=cast(str, record["snapshot_manifest_sha256"]),
    )


def verify_docket_decision_text_sources(
    *,
    selection_records: Sequence[Mapping[str, Any]],
    selection_payload_sha256: str,
    screening_snapshot: VerifiedScreeningSnapshot,
    expected_snapshot_manifest_sha256: str,
    terminal_purchase_failure_authority: VerifiedTerminalPurchaseFailureAuthority,
    purchase_journal: CaseDevPurchaseJournal,
) -> VerifiedDocketDecisionTextSources:
    """Derive one exhaustive retained-versus-residual terminal partition.

    Candidate identities are never supplied as a disposition list.  The full
    fresh terminal universe comes from the purchase-failure verifier.  A
    candidate is retained only when every failed obligation is a selected
    audit-only decision document and every such docket lineage replays.  All
    other terminal candidates remain exact verifier-owned reserve exclusions.
    """

    selection_sha256 = _sha256(selection_payload_sha256, "selection payload")
    captured_selection_records, captured_selection_bytes = _capture_selection_records(
        selection_records
    )
    if _bytes_sha256(captured_selection_bytes) != selection_sha256:
        raise DocketDecisionTextSourceError(
            "selection records differ from the frozen selection payload"
        )
    captured_snapshot = _capture_screening_snapshot(
        screening_snapshot,
        expected_manifest_sha256=expected_snapshot_manifest_sha256,
    )
    terminal_records, evidence_by_candidate = _fresh_terminal_universe(
        terminal_purchase_failure_authority,
        purchase_journal=purchase_journal,
    )
    selections = _selection_index(captured_selection_records)
    docket_lineages: list[ReplayedDocketDecisionLineage] = []
    residual_records: list[JsonRecord] = []
    for candidate_id in sorted(evidence_by_candidate):
        evidence = evidence_by_candidate[candidate_id]
        failure_ids = _terminal_failure_document_ids(evidence)
        selection = selections.get(candidate_id)
        decision_failure_ids = (
            ()
            if selection is None
            else _selected_terminal_decision_failure_ids(
                selection,
                terminal_document_ids=failure_ids,
            )
        )
        if decision_failure_ids != failure_ids:
            residual_records.append(dict(terminal_records[candidate_id]))
            continue
        # Once the frozen selection represents every failure as a decision,
        # any replay defect is ambiguity, not authority to silently replace it.
        for document_id in failure_ids:
            docket_lineages.append(
                replay_docket_decision_source_lineage(
                    selection_records=captured_selection_records,
                    selection_payload_sha256=selection_sha256,
                    screening_snapshot=captured_snapshot,
                    candidate_id=candidate_id,
                    unavailable_recap_document_id=document_id,
                )
            )

    residual_bytes = _canonical_jsonl(residual_records)
    disposition = _build_disposition_record(
        terminal_failure_authority=terminal_purchase_failure_authority,
        selection_payload_sha256=selection_sha256,
        snapshot_manifest_sha256=_sha256(
            captured_snapshot.manifest_sha256,
            "snapshot manifest",
        ),
        evidence_by_candidate=evidence_by_candidate,
        docket_lineages=tuple(docket_lineages),
        residual_records=tuple(residual_records),
        residual_bytes=residual_bytes,
    )
    authority = _issue_terminal_disposition(
        terminal_failure_authority=terminal_purchase_failure_authority,
        docket_lineages=tuple(docket_lineages),
        residual_exclusions_bytes=residual_bytes,
        disposition_bytes=_canonical_json_bytes(disposition),
        purchase_journal_state_sha256=(
            terminal_purchase_failure_authority.purchase_journal_state_sha256
        ),
        selection_payload_sha256=selection_sha256,
        snapshot_manifest_sha256=_sha256(
            captured_snapshot.manifest_sha256,
            "snapshot manifest",
        ),
    )
    _replay_terminal_disposition(authority, purchase_journal)
    sources = object.__new__(VerifiedDocketDecisionTextSources)
    sources._issuer = _DISPOSITION_ISSUER  # pyright: ignore[reportPrivateUsage]
    sources._authority = authority  # pyright: ignore[reportPrivateUsage]
    return sources


def verified_docket_decision_source_records(
    authority: VerifiedTerminalPurchaseDispositionAuthority,
    *,
    purchase_journal: CaseDevPurchaseJournal,
) -> tuple[Mapping[str, Any], ...]:
    """Freshly replay terminal authority and return retained audit-only sources."""

    sources, _residual = _replay_terminal_disposition(authority, purchase_journal)
    return sources


def verified_residual_terminal_records(
    authority: VerifiedTerminalPurchaseDispositionAuthority,
    *,
    purchase_journal: CaseDevPurchaseJournal,
) -> dict[str, JsonRecord]:
    """Freshly replay terminal authority and return exact residual exclusions."""

    _sources, residual = _replay_terminal_disposition(authority, purchase_journal)
    return {
        _required_string(record.get("candidate_id"), "residual candidate ID"): dict(
            record
        )
        for record in residual
    }


def residual_terminal_exclusions_bytes(
    authority: VerifiedTerminalPurchaseDispositionAuthority,
    *,
    purchase_journal: CaseDevPurchaseJournal,
) -> bytes:
    """Return only verifier-owned residual bytes after fresh substantive replay."""

    _replay_terminal_disposition(authority, purchase_journal)
    return authority._residual_exclusions_bytes  # pyright: ignore[reportPrivateUsage]


def _fresh_terminal_universe(
    authority: VerifiedTerminalPurchaseFailureAuthority,
    *,
    purchase_journal: CaseDevPurchaseJournal,
) -> tuple[dict[str, JsonRecord], dict[str, JsonRecord]]:
    try:
        terminal_records = verified_terminal_retrieval_records(
            authority,
            purchase_journal=purchase_journal,
        )
    except TerminalPurchaseFailureError as exc:
        raise DocketDecisionTextSourceError(str(exc)) from exc
    evidence_by_candidate: dict[str, JsonRecord] = {}
    for value in authority.evidence_records:
        candidate_id = _required_string(
            value.get("candidate_id"), "terminal evidence candidate ID"
        )
        if candidate_id in evidence_by_candidate:
            raise DocketDecisionTextSourceError(
                "terminal purchase evidence repeats a candidate"
            )
        _terminal_failure_document_ids(value)
        evidence_by_candidate[candidate_id] = value
    if set(evidence_by_candidate) != set(terminal_records):
        raise DocketDecisionTextSourceError(
            "terminal evidence and exclusion candidate universes differ"
        )
    return terminal_records, evidence_by_candidate


def _terminal_failure_document_ids(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    failures_value = evidence.get("failures")
    if not isinstance(failures_value, list) or not failures_value:
        raise DocketDecisionTextSourceError(
            "terminal candidate must contain at least one failed document"
        )
    document_ids = tuple(
        _required_string(
            _mapping(value, "terminal failure").get("source_document_id"),
            "terminal failure document ID",
        )
        for value in cast(list[object], failures_value)
    )
    if len(document_ids) != len(set(document_ids)):
        raise DocketDecisionTextSourceError(
            "terminal candidate repeats a failed document"
        )
    if document_ids != tuple(sorted(document_ids)):
        raise DocketDecisionTextSourceError(
            "terminal failed documents are not canonically ordered"
        )
    return document_ids


def _selected_terminal_decision_failure_ids(
    selection: Mapping[str, Any],
    *,
    terminal_document_ids: tuple[str, ...],
) -> tuple[str, ...]:
    documents_value = selection.get("documents")
    if not isinstance(documents_value, list):
        return ()
    documents_by_id: dict[str, Mapping[str, Any]] = {}
    for value in cast(list[object], documents_value):
        document = _mapping(value, "selection document")
        document_id = document.get("source_document_id")
        if not isinstance(document_id, str) or not document_id:
            continue
        if document_id in documents_by_id:
            raise DocketDecisionTextSourceError(
                "selection repeats a source document identity"
            )
        documents_by_id[document_id] = document
    matched: list[str] = []
    for document_id in terminal_document_ids:
        document = documents_by_id.get(document_id)
        if document is None or document.get("document_role") != "decision":
            continue
        required = {
            "candidate_id": selection.get("candidate_id"),
            "contains_target_outcome": True,
            "model_visible": False,
            "is_predecision_material": False,
            "availability_status": "unavailable",
            "is_available": False,
            "requires_paid_recovery": True,
        }
        if any(document.get(key) != expected for key, expected in required.items()):
            continue
        if document.get("is_sealed") is True or document.get("is_private") is True:
            continue
        if document.get("redaction_or_seal_status") in {
            "sealed",
            "restricted",
            "private",
        }:
            continue
        matched.append(document_id)
    return tuple(matched)


def _build_disposition_record(
    *,
    terminal_failure_authority: VerifiedTerminalPurchaseFailureAuthority,
    selection_payload_sha256: str,
    snapshot_manifest_sha256: str,
    evidence_by_candidate: Mapping[str, JsonRecord],
    docket_lineages: tuple[ReplayedDocketDecisionLineage, ...],
    residual_records: tuple[JsonRecord, ...],
    residual_bytes: bytes,
) -> JsonRecord:
    source_records = tuple(
        require_replayed_docket_decision_lineage(lineage) for lineage in docket_lineages
    )
    terminal_pairs = _terminal_pairs(evidence_by_candidate)
    retained_pairs = tuple(
        sorted(
            (
                _required_string(source.get("candidate_id"), "source candidate ID"),
                _required_string(
                    source.get("unavailable_recap_document_id"),
                    "source terminal document ID",
                ),
            )
            for source in source_records
        )
    )
    residual_candidate_ids = tuple(
        _required_string(record.get("candidate_id"), "residual candidate ID")
        for record in residual_records
    )
    if residual_candidate_ids != tuple(sorted(residual_candidate_ids)) or len(
        residual_candidate_ids
    ) != len(set(residual_candidate_ids)):
        raise DocketDecisionTextSourceError(
            "residual terminal exclusions are duplicated or unordered"
        )
    residual_pairs = tuple(
        pair for pair in terminal_pairs if pair[0] in set(residual_candidate_ids)
    )
    if (
        set(retained_pairs) & set(residual_pairs)
        or set(retained_pairs) | set(residual_pairs) != set(terminal_pairs)
        or len(retained_pairs) + len(residual_pairs) != len(terminal_pairs)
    ):
        raise DocketDecisionTextSourceError(
            "terminal retained and residual pairs are not a disjoint exhaustive union"
        )
    retained_candidate_ids = {candidate_id for candidate_id, _ in retained_pairs}
    if retained_candidate_ids & set(residual_candidate_ids) or (
        retained_candidate_ids | set(residual_candidate_ids)
        != set(evidence_by_candidate)
    ):
        raise DocketDecisionTextSourceError(
            "terminal retained and residual candidates are not exhaustive"
        )
    source_bytes = _canonical_jsonl(source_records)
    return {
        "schema_version": TERMINAL_PURCHASE_DISPOSITION_SCHEMA,
        "purchase_result_sha256": terminal_failure_authority.purchase_result_sha256,
        "purchase_run_card_sha256": (
            terminal_failure_authority.purchase_run_card_sha256
        ),
        "purchase_journal_state_sha256": (
            terminal_failure_authority.purchase_journal_state_sha256
        ),
        "selection_payload_sha256": selection_payload_sha256,
        "snapshot_manifest_sha256": snapshot_manifest_sha256,
        "terminal_candidate_count": len(evidence_by_candidate),
        "terminal_failure_pair_count": len(terminal_pairs),
        "terminal_failure_pairs": _pair_records(terminal_pairs),
        "docket_retained_candidate_count": len(retained_candidate_ids),
        "docket_retained_failure_pair_count": len(retained_pairs),
        "docket_retained_failure_pairs": _pair_records(retained_pairs),
        "docket_decision_sources_sha256": _bytes_sha256(source_bytes),
        "residual_candidate_count": len(residual_candidate_ids),
        "residual_failure_pair_count": len(residual_pairs),
        "residual_failure_pairs": _pair_records(residual_pairs),
        "residual_terminal_exclusions_sha256": _bytes_sha256(residual_bytes),
        "partition_disjoint": True,
        "partition_exhaustive": True,
        "model_visible": False,
        "audit_only": True,
    }


def _terminal_pairs(
    evidence_by_candidate: Mapping[str, JsonRecord],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (candidate_id, document_id)
            for candidate_id, evidence in evidence_by_candidate.items()
            for document_id in _terminal_failure_document_ids(evidence)
        )
    )


def _pair_records(pairs: tuple[tuple[str, str], ...]) -> list[JsonRecord]:
    return [
        {"candidate_id": candidate_id, "source_document_id": document_id}
        for candidate_id, document_id in pairs
    ]


def _issue_terminal_disposition(
    *,
    terminal_failure_authority: VerifiedTerminalPurchaseFailureAuthority,
    docket_lineages: tuple[ReplayedDocketDecisionLineage, ...],
    residual_exclusions_bytes: bytes,
    disposition_bytes: bytes,
    purchase_journal_state_sha256: str,
    selection_payload_sha256: str,
    snapshot_manifest_sha256: str,
) -> VerifiedTerminalPurchaseDispositionAuthority:
    authority = object.__new__(VerifiedTerminalPurchaseDispositionAuthority)
    authority._issuer = _DISPOSITION_ISSUER  # pyright: ignore[reportPrivateUsage]
    authority._terminal_failure_authority = (  # pyright: ignore[reportPrivateUsage]
        terminal_failure_authority
    )
    authority._docket_lineages = docket_lineages  # pyright: ignore[reportPrivateUsage]
    authority._residual_exclusions_bytes = (  # pyright: ignore[reportPrivateUsage]
        residual_exclusions_bytes
    )
    authority._disposition_bytes = disposition_bytes  # pyright: ignore[reportPrivateUsage]
    authority.purchase_journal_state_sha256 = purchase_journal_state_sha256
    authority.selection_payload_sha256 = selection_payload_sha256
    authority.snapshot_manifest_sha256 = snapshot_manifest_sha256
    return authority


def _replay_terminal_disposition(
    authority: object,
    purchase_journal: CaseDevPurchaseJournal,
) -> tuple[tuple[Mapping[str, Any], ...], tuple[JsonRecord, ...]]:
    if (
        not isinstance(authority, VerifiedTerminalPurchaseDispositionAuthority)
        or getattr(authority, "_issuer", None) is not _DISPOSITION_ISSUER
    ):
        raise DocketDecisionTextSourceError(
            "terminal purchase disposition authority was not verifier-issued"
        )
    verified = authority
    terminal_records, evidence_by_candidate = _fresh_terminal_universe(
        verified._terminal_failure_authority,  # pyright: ignore[reportPrivateUsage]
        purchase_journal=purchase_journal,
    )
    if verified.purchase_journal_state_sha256 != (
        verified._terminal_failure_authority.purchase_journal_state_sha256  # pyright: ignore[reportPrivateUsage]
    ):
        raise DocketDecisionTextSourceError(
            "terminal disposition targets another purchase journal state"
        )
    source_records = tuple(
        require_replayed_docket_decision_lineage(lineage)
        for lineage in verified._docket_lineages  # pyright: ignore[reportPrivateUsage]
    )
    residual_payload = (
        verified._residual_exclusions_bytes  # pyright: ignore[reportPrivateUsage]
    )
    residual_records = (
        ()
        if residual_payload == b""
        else tuple(
            _jsonl_records(
                residual_payload,
                "residual terminal exclusions",
            )
        )
    )
    for residual in residual_records:
        candidate_id = _required_string(
            residual.get("candidate_id"), "residual candidate ID"
        )
        if terminal_records.get(candidate_id) != residual:
            raise DocketDecisionTextSourceError(
                "residual exclusion differs from fresh terminal authority"
            )
    rebuilt = _build_disposition_record(
        terminal_failure_authority=verified._terminal_failure_authority,  # pyright: ignore[reportPrivateUsage]
        selection_payload_sha256=verified.selection_payload_sha256,
        snapshot_manifest_sha256=verified.snapshot_manifest_sha256,
        evidence_by_candidate=evidence_by_candidate,
        docket_lineages=verified._docket_lineages,  # pyright: ignore[reportPrivateUsage]
        residual_records=residual_records,
        residual_bytes=verified._residual_exclusions_bytes,  # pyright: ignore[reportPrivateUsage]
    )
    if _canonical_json_bytes(rebuilt) != verified._disposition_bytes:  # pyright: ignore[reportPrivateUsage]
        raise DocketDecisionTextSourceError(
            "terminal disposition differs from its verified partition"
        )
    return source_records, residual_records


def require_replayed_docket_decision_lineage(
    lineage: object,
) -> Mapping[str, Any]:
    """Return a replayed record only to the composed terminal-authority verifier."""

    if (
        not isinstance(lineage, ReplayedDocketDecisionLineage)
        or lineage._issuer  # pyright: ignore[reportPrivateUsage]
        is not _LINEAGE_ISSUER
    ):
        raise DocketDecisionTextSourceError(
            "docket decision lineage was not issued by the semantic replay verifier"
        )
    record = _json_record_bytes(
        lineage._record_bytes,  # pyright: ignore[reportPrivateUsage]
        "docket decision lineage",
    )
    _validate_closed_source_record(record)
    return MappingProxyType(record)


def _issue_replayed_lineage(
    *,
    record: JsonRecord,
    selection_payload_sha256: str,
    snapshot_manifest_sha256: str,
) -> ReplayedDocketDecisionLineage:
    lineage = object.__new__(ReplayedDocketDecisionLineage)
    lineage._issuer = _LINEAGE_ISSUER  # pyright: ignore[reportPrivateUsage]
    lineage._record_bytes = _canonical_json_bytes(record)  # pyright: ignore[reportPrivateUsage]
    lineage.selection_payload_sha256 = selection_payload_sha256
    lineage.snapshot_manifest_sha256 = snapshot_manifest_sha256
    return lineage


def _reconstruct_source_page(
    *,
    screening_snapshot: VerifiedScreeningSnapshot,
    evidence: Mapping[str, Any],
    snapshot_candidate_id: str,
    docket_id: str,
) -> tuple[CourtListenerWebDocketPage, str, JsonRecord]:
    raw_matches = tuple(
        artifact
        for artifact in screening_snapshot.raw_artifacts
        if artifact.candidate_id == snapshot_candidate_id
    )
    if raw_matches:
        if len(raw_matches) != 1:
            raise DocketDecisionTextSourceError(
                "docket decision source has duplicate raw artifacts"
            )
        return _raw_html_source_page(
            raw=raw_matches[0],
            evidence=evidence,
            docket_id=docket_id,
            expected_target_cycle_hash=_sha256(
                screening_snapshot.manifest.get("cycle_hash"),
                "screening snapshot cycle hash",
            ),
        )
    return _canonical_rest_source_page(evidence=evidence, docket_id=docket_id)


def _raw_html_source_page(
    *,
    raw: UnionRawArtifact,
    evidence: Mapping[str, Any],
    docket_id: str,
    expected_target_cycle_hash: str,
) -> tuple[CourtListenerWebDocketPage, str, JsonRecord]:
    if not raw.content_authenticated or raw.content is None:
        raise DocketDecisionTextSourceError(
            "raw CourtListener HTML bytes are not authenticated"
        )
    if (
        hashlib.sha256(raw.content).hexdigest() != raw.sha256
        or len(raw.content) != raw.byte_count
    ):
        raise DocketDecisionTextSourceError(
            "raw CourtListener HTML differs from its snapshot commitment"
        )
    try:
        raw_html = raw.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocketDecisionTextSourceError(
            "raw CourtListener HTML is not UTF-8"
        ) from exc
    strict_screen = _mapping(evidence.get("mtd_decision_screen"), "strict screen")
    page = parse_courtlistener_docket_html(
        raw_html,
        source_url=_required_string(strict_screen.get("source_url"), "source URL"),
        docket_id=docket_id,
    )
    if not _raw_entries_equivalent(
        cast(list[object], page.to_record()["entries"]),
        evidence.get("selected_entries"),
    ):
        raise DocketDecisionTextSourceError(
            "raw CourtListener HTML does not reproduce selected docket entries"
        )
    if (
        evidence.get("canonical_rest_screen_complete") is not None
        or evidence.get("decision_entry_evidence") is not None
    ):
        raise DocketDecisionTextSourceError(
            "raw-backed decision source contains contradictory REST-only evidence"
        )
    rebind = _mapping(
        evidence.get("screening_union_policy_rebind"),
        "screening policy-rebind proof",
    )
    expected_rebind_keys = {
        "schema_version",
        "source_cycle_hash",
        "source_snapshot_manifest_sha256",
        "source_terminal_sha256",
        "target_cycle_hash",
        "policy_delta",
        "current_policy_proof_available",
        "paid_activity_requested",
        "paid_activity_executed",
        "provider_activity_requested",
        "provider_activity_executed",
    }
    if set(rebind) != expected_rebind_keys or any(
        rebind.get(key) is not expected
        for key, expected in {
            "current_policy_proof_available": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
        }.items()
    ):
        raise DocketDecisionTextSourceError(
            "raw source policy-rebind proof is open or permits provider activity"
        )
    if (
        rebind.get("schema_version") != POLICY_PROOF_SCHEMA
        or rebind.get("policy_delta") != POLICY_DELTA_NAME
        or rebind.get("target_cycle_hash") != expected_target_cycle_hash
    ):
        raise DocketDecisionTextSourceError(
            "raw source policy-rebind proof targets another policy or cycle"
        )
    for key in (
        "source_cycle_hash",
        "source_snapshot_manifest_sha256",
        "source_terminal_sha256",
        "target_cycle_hash",
    ):
        _sha256(rebind.get(key), f"policy rebind {key}")
    return (
        page,
        RAW_COURTLISTENER_HTML_BASIS,
        {
            "schema_version": "legalforecast.docket_decision_raw_html_evidence.v1",
            "raw_artifact_path": str(raw.path),
            "raw_artifact_sha256": raw.sha256,
            "raw_artifact_byte_count": raw.byte_count,
            "raw_artifact_retrieved_at": raw.retrieved_at,
            "policy_rebind": dict(rebind),
        },
    )


def _raw_entries_equivalent(parsed: object, selected: object) -> bool:
    """Ignore only the known synthetic blank document on unnumbered rows.

    Some REST-to-HTML rebind snapshots preserve a structurally empty document
    placeholder that the HTML parser intentionally omits.  The placeholder has
    no text, link, availability, restriction, or PACER semantics.  Normalizing
    precisely that shape keeps the raw bytes authoritative without permitting
    substantive entry drift.
    """

    if not isinstance(parsed, list) or not isinstance(selected, list):
        return False

    def normalize(value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        record = dict(cast(Mapping[str, Any], value))
        documents = record.get("documents")
        if record.get("entry_number") is not None or not isinstance(documents, list):
            return record
        record["documents"] = [
            document
            for document in cast(list[object], documents)
            if not _is_synthetic_blank_document(document)
        ]
        return record

    return [normalize(value) for value in cast(list[object], parsed)] == [
        normalize(value) for value in cast(list[object], selected)
    ]


def _is_synthetic_blank_document(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    return dict(cast(Mapping[str, Any], value)) == {
        "action_label": None,
        "description": "",
        "freely_available": False,
        "href": None,
        "kind": "",
        "pacer_only": False,
        "restriction_markers": [],
    }


def _canonical_rest_source_page(
    *,
    evidence: Mapping[str, Any],
    docket_id: str,
) -> tuple[CourtListenerWebDocketPage, str, JsonRecord]:
    if (
        evidence.get("provider") != "courtlistener-recap-rest-v4"
        or evidence.get("canonical_rest_screen_complete") is not True
    ):
        raise DocketDecisionTextSourceError(
            "rawless decision source is not a complete canonical REST screen"
        )
    proof = _mapping(evidence.get("reconstruction_proof"), "REST reconstruction proof")
    if set(proof) != {
        "complete",
        "cursor_exhausted",
        "docket_id",
        "duplicate_entry_ids",
        "entry_count",
        "entry_numbers_monotonic",
        "pages_fetched",
    }:
        raise DocketDecisionTextSourceError(
            "REST reconstruction proof has an open or incomplete schema"
        )
    selected_entries = _selected_entries(evidence)
    if (
        proof.get("complete") is not True
        or proof.get("cursor_exhausted") is not True
        or proof.get("entry_numbers_monotonic") is not True
        or proof.get("docket_id") != docket_id
        or proof.get("duplicate_entry_ids") != []
        or proof.get("entry_count") != len(selected_entries)
        or _positive_int(proof.get("pages_fetched"), "REST pages fetched") < 1
    ):
        raise DocketDecisionTextSourceError(
            "REST reconstruction does not prove complete cursor exhaustion"
        )
    entries = tuple(_entry_from_record(record) for record in selected_entries)
    if [entry.to_record() for entry in entries] != list(selected_entries):
        raise DocketDecisionTextSourceError(
            "REST entries do not round-trip under the production parser model"
        )
    strict_screen = _mapping(evidence.get("mtd_decision_screen"), "strict screen")
    page = CourtListenerWebDocketPage(
        docket_id=docket_id,
        source_url=_required_string(strict_screen.get("source_url"), "source URL"),
        title=_required_string(strict_screen.get("title"), "screen title"),
        entries=entries,
        has_next_page=False,
    )
    decision_evidence = _mapping(
        evidence.get("decision_entry_evidence"),
        "REST decision-entry evidence",
    )
    if set(decision_evidence) != {
        "absolute_url",
        "description",
        "docket_entry_id",
        "document_number",
        "entry_date_filed",
        "entry_number",
        "id",
    }:
        raise DocketDecisionTextSourceError(
            "REST decision-entry evidence has an open or incomplete schema"
        )
    evidence_entry_number = str(
        _positive_intish(
            decision_evidence.get("entry_number"),
            "REST evidence entry number",
        )
    )
    evidence_entry = _unique_entry(
        selected_entries,
        entry_number=evidence_entry_number,
    )
    if decision_evidence.get("description") != evidence_entry.get("text"):
        raise DocketDecisionTextSourceError(
            "REST evidence description differs from its complete docket entry"
        )
    evidence_filed_date = parse_courtlistener_filed_date(
        _required_string(evidence_entry.get("filed_at"), "REST evidence entry date")
    )
    if (
        evidence_filed_date is None
        or decision_evidence.get("entry_date_filed") != evidence_filed_date.isoformat()
    ):
        raise DocketDecisionTextSourceError(
            "REST evidence date differs from its complete docket entry"
        )
    return (
        page,
        MANIFEST_BOUND_REST_BASIS,
        {
            "schema_version": "legalforecast.docket_decision_rest_evidence.v1",
            "canonical_rest_screen_complete": True,
            "reconstruction_proof": dict(proof),
            "decision_entry_evidence": dict(decision_evidence),
        },
    )


def _rerun_semantic_screen_and_linkage(
    *,
    page: CourtListenerWebDocketPage,
    evidence: Mapping[str, Any],
    docket_id: str,
    anchor_date: date,
) -> None:
    candidate = _mapping(evidence.get("candidate"), "screen candidate")
    metadata = _mapping(candidate.get("metadata"), "screen candidate metadata")
    replayed_screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text=_required_string(metadata.get("case_name"), "case name"),
        court_id=_required_string(metadata.get("court"), "court"),
        decision_filed_on_or_after=anchor_date,
    ).to_record()
    if replayed_screen != evidence.get("mtd_decision_screen"):
        raise DocketDecisionTextSourceError(
            "production MTD screen does not reproduce the frozen strict decision"
        )
    normalized = tuple(
        NormalizedDocketEntry(
            source_provider="courtlistener",
            source_case_id=docket_id,
            docket_entry_id=entry.row_id,
            entry_number=entry.entry_number,
            entry_text=entry.text,
            filed_at=entry.filed_at,
            document_role=_ROLE_MAP[entry.role],
            source_document_ids=tuple(
                document.href
                for document in entry.documents
                if document.href is not None
            ),
            source_url=page.source_url,
        )
        for entry in page.entries
    )
    expected_linkage = _mapping(evidence.get("motion_linkage"), "motion linkage")
    replayed_linkage = link_mtd_dispositions(
        normalized,
        candidate_id=docket_id,
        case_id=_required_string(expected_linkage.get("case_id"), "linkage case ID"),
    ).to_record()
    actual_decision_ids = _strict_actual_decision_row_ids(evidence)
    if (
        _linkage_actual_decision_projection(
            expected_linkage,
            actual_decision_ids=actual_decision_ids,
            require_already_projected=True,
        )
        != expected_linkage
        or _linkage_actual_decision_projection(
            replayed_linkage,
            actual_decision_ids=actual_decision_ids,
            require_already_projected=False,
        )
        != expected_linkage
    ):
        raise DocketDecisionTextSourceError(
            "production motion linkage does not reproduce the selected MTD decision"
        )


def _strict_actual_decision_row_ids(
    evidence: Mapping[str, Any],
) -> frozenset[str]:
    screen = _mapping(evidence.get("mtd_decision_screen"), "strict screen")
    values = screen.get("decision_entries")
    if not isinstance(values, list) or not values:
        raise DocketDecisionTextSourceError(
            "strict screen has no actual decision entries"
        )
    decision_entries = cast(list[object], values)
    result = frozenset(
        _required_string(
            _mapping(value, "strict decision entry").get("row_id"),
            "strict decision row ID",
        )
        for value in decision_entries
    )
    if len(result) != len(decision_entries):
        raise DocketDecisionTextSourceError(
            "strict screen repeats an actual decision entry"
        )
    return result


def _linkage_actual_decision_projection(
    linkage: Mapping[str, Any],
    *,
    actual_decision_ids: frozenset[str],
    require_already_projected: bool,
) -> JsonRecord:
    links_value = linkage.get("links")
    if not isinstance(links_value, list):
        raise DocketDecisionTextSourceError("motion linkage links must be a list")
    projected_links: list[JsonRecord] = []
    for value in cast(list[object], links_value):
        link = dict(_mapping(value, "motion linkage link"))
        disposition_ids = _string_list(
            link.get("disposition_entry_ids"), "linked disposition entry IDs"
        )
        projected_ids = [
            entry_id for entry_id in disposition_ids if entry_id in actual_decision_ids
        ]
        if require_already_projected and len(projected_ids) != len(disposition_ids):
            raise DocketDecisionTextSourceError(
                "frozen motion linkage includes a nonactual decision entry"
            )
        if not projected_ids:
            continue
        link["disposition_entry_ids"] = projected_ids
        projected_links.append(link)
    projected = dict(linkage)
    projected["links"] = projected_links
    projected["is_clean"] = bool(projected_links) and not projected.get(
        "exclusion_entries"
    )
    return projected


def _verify_source_identity(
    *,
    basis: str,
    source_evidence: Mapping[str, Any],
    decision_document: Mapping[str, Any],
    decision_entry: Mapping[str, Any],
    entered_date: date,
    unavailable_recap_document_id: str,
) -> None:
    if basis == RAW_COURTLISTENER_HTML_BASIS:
        return
    if basis != MANIFEST_BOUND_REST_BASIS:
        raise DocketDecisionTextSourceError("unsupported docket source basis")
    rest = _mapping(
        source_evidence.get("decision_entry_evidence"),
        "REST decision-entry evidence",
    )
    entry_number = _positive_intish(
        decision_entry.get("entry_number"), "decision entry"
    )
    docket_id = _required_string(
        decision_document.get("candidate_id"), "decision candidate ID"
    )
    rest_entry_number = _positive_intish(
        rest.get("entry_number"), "REST evidence entry number"
    )
    rest_document_number = _positive_intish(
        rest.get("document_number"), "REST evidence document number"
    )
    absolute_url = _required_string(rest.get("absolute_url"), "REST absolute URL")
    if rest_entry_number != rest_document_number or not absolute_url.startswith(
        f"/docket/{docket_id}/{rest_entry_number}/"
    ):
        raise DocketDecisionTextSourceError(
            "REST evidence URL differs from its docket and entry identity"
        )
    _positive_intish(rest.get("id"), "REST evidence document ID")
    _positive_intish(rest.get("docket_entry_id"), "REST evidence docket entry ID")
    _canonical_date(rest.get("entry_date_filed"), "REST evidence entry date")
    if rest_entry_number == entry_number:
        expected = {
            "description": decision_entry.get("text"),
            "docket_entry_id": _positive_intish(
                decision_document.get("courtlistener_docket_entry_id"),
                "CourtListener docket entry ID",
            ),
            "entry_date_filed": entered_date.isoformat(),
            "id": _positive_intish(
                unavailable_recap_document_id,
                "unavailable RECAP document ID",
            ),
        }
        if any(rest.get(key) != value for key, value in expected.items()):
            raise DocketDecisionTextSourceError(
                "REST decision-entry evidence differs from the frozen selection"
            )
        return
    _verify_rest_selection_document_identity(
        decision_document,
        docket_id=docket_id,
        unavailable_recap_document_id=unavailable_recap_document_id,
    )


def _selection_description_matches_entry(
    decision_document: Mapping[str, Any],
    decision_entry: Mapping[str, Any],
) -> bool:
    description = _required_string(
        decision_document.get("description"), "selected decision description"
    )
    if description == decision_entry.get("text"):
        return True
    documents = decision_entry.get("documents")
    if not isinstance(documents, list):
        return False
    return any(
        _mapping(value, "decision docket document").get("description") == description
        for value in cast(list[object], documents)
    )


def _verify_rest_selection_document_identity(
    decision_document: Mapping[str, Any],
    *,
    docket_id: str,
    unavailable_recap_document_id: str,
) -> None:
    _positive_intish(
        decision_document.get("courtlistener_docket_entry_id"),
        "CourtListener docket entry ID",
    )
    if decision_document.get("source_document_id") != unavailable_recap_document_id:
        raise DocketDecisionTextSourceError(
            "REST selection differs from the terminal document identity"
        )
    expected_url = (
        "https://www.courtlistener.com/api/rest/v4/recap-documents/"
        f"{unavailable_recap_document_id}/"
    )
    if (
        decision_document.get("source_url") != expected_url
        or decision_document.get("source_url_or_reference") != expected_url
    ):
        raise DocketDecisionTextSourceError(
            "REST selection does not bind the terminal document URL"
        )
    if decision_document.get("source_provider") != "courtlistener+recap-fetch":
        raise DocketDecisionTextSourceError(
            "REST selection has an unsupported terminal document provider"
        )
    restriction_evidence = set(
        _string_list(
            decision_document.get("restriction_evidence"),
            "decision restriction evidence",
        )
    )
    required = {
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_false",
        "courtlistener_rest_recap_document_seal_status_unknown",
        "courtlistener_rest_no_positive_restriction_marker",
    }
    if (
        required != restriction_evidence
        or decision_document.get("candidate_id") != docket_id
    ):
        raise DocketDecisionTextSourceError(
            "REST selection lacks exact public terminal-document lineage"
        )


def _entry_from_record(record: Mapping[str, Any]) -> CourtListenerWebDocketEntry:
    if set(record) != {
        "documents",
        "entry_number",
        "filed_at",
        "restriction_markers",
        "role",
        "row_id",
        "text",
    }:
        raise DocketDecisionTextSourceError(
            "selected docket entry has an open or incomplete schema"
        )
    documents_value = record.get("documents")
    if not isinstance(documents_value, list):
        raise DocketDecisionTextSourceError("selected entry documents must be a list")
    documents = tuple(
        _document_from_record(_mapping(value, "selected entry document"))
        for value in cast(list[object], documents_value)
    )
    entry_number_value = record.get("entry_number")
    if entry_number_value is not None and not isinstance(entry_number_value, str):
        raise DocketDecisionTextSourceError(
            "selected entry number must be text or null"
        )
    filed_at_value = record.get("filed_at")
    if filed_at_value is not None and not isinstance(filed_at_value, str):
        raise DocketDecisionTextSourceError("selected entry date must be text or null")
    return CourtListenerWebDocketEntry(
        row_id=_required_string(record.get("row_id"), "selected row ID"),
        entry_number=entry_number_value,
        filed_at=filed_at_value,
        text=_string(record.get("text"), "selected entry text"),
        documents=documents,
        restriction_markers=_string_list(
            record.get("restriction_markers"), "entry restriction markers"
        ),
    )


def _document_from_record(record: Mapping[str, Any]) -> CourtListenerWebDocument:
    if set(record) != {
        "action_label",
        "description",
        "freely_available",
        "href",
        "kind",
        "pacer_only",
        "restriction_markers",
    }:
        raise DocketDecisionTextSourceError(
            "selected docket document has an open or incomplete schema"
        )
    action_label = _optional_string(record.get("action_label"), "document action label")
    href = _optional_string(record.get("href"), "document href")
    pacer_only = _boolean(record.get("pacer_only"), "document PACER-only flag")
    document = CourtListenerWebDocument(
        kind=_required_string(record.get("kind"), "document kind"),
        description=_string(record.get("description"), "document description"),
        href=href,
        action_label=action_label,
        pacer_only=pacer_only,
        restriction_markers=_string_list(
            record.get("restriction_markers"), "document restriction markers"
        ),
    )
    if document.freely_available is not record.get("freely_available"):
        raise DocketDecisionTextSourceError(
            "selected document availability is not derived from its public link"
        )
    return document


def _verify_decision_entry_is_public(entry: Mapping[str, Any]) -> None:
    if _string_list(entry.get("restriction_markers"), "entry restriction markers"):
        raise DocketDecisionTextSourceError("decision docket entry is restricted")
    documents = entry.get("documents")
    if not isinstance(documents, list):
        raise DocketDecisionTextSourceError(
            "decision docket entry documents are invalid"
        )
    for value in cast(list[object], documents):
        document = _mapping(value, "decision docket document")
        if _string_list(
            document.get("restriction_markers"), "document restriction markers"
        ):
            raise DocketDecisionTextSourceError(
                "decision docket document is restricted"
            )


def _selected_decision_document(
    selection: Mapping[str, Any], *, unavailable_recap_document_id: str
) -> Mapping[str, Any]:
    documents_value = selection.get("documents")
    if not isinstance(documents_value, list):
        raise DocketDecisionTextSourceError("selection documents must be a list")
    matches: list[Mapping[str, Any]] = []
    for value in cast(list[object], documents_value):
        document_record = _mapping(value, "selection document")
        if document_record.get("source_document_id") == unavailable_recap_document_id:
            matches.append(document_record)
    if len(matches) != 1:
        raise DocketDecisionTextSourceError(
            "terminal decision document is absent or duplicated in the selection"
        )
    document = matches[0]
    required = {
        "candidate_id": selection.get("candidate_id"),
        "document_role": "decision",
        "contains_target_outcome": True,
        "model_visible": False,
        "is_predecision_material": False,
        "availability_status": "unavailable",
        "is_available": False,
        "requires_paid_recovery": True,
    }
    if any(document.get(key) != value for key, value in required.items()):
        raise DocketDecisionTextSourceError(
            "selected terminal document is not the unavailable audit-only decision"
        )
    if document.get("is_sealed") is True or document.get("is_private") is True:
        raise DocketDecisionTextSourceError("selected decision document is restricted")
    if document.get("redaction_or_seal_status") in {"sealed", "restricted", "private"}:
        raise DocketDecisionTextSourceError("selected decision document is restricted")
    return document


def _validate_closed_source_record(record: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "candidate_id",
        "case_id",
        "docket_id",
        "source_kind",
        "source_basis",
        "decision_source_id",
        "decision_entry_row_id",
        "decision_entry_number",
        "decision_docket_entry_id",
        "unavailable_recap_document_id",
        "entered_date",
        "target_motion_entry_numbers",
        "text",
        "text_sha256",
        "text_byte_count",
        "is_first_written_disposition",
        "contains_target_outcome",
        "model_visible",
        "audit_only",
        "materialization_required",
        "selection_sha256",
        "selection_record_sha256",
        "snapshot_manifest_sha256",
        "snapshot_cycle_hash",
        "snapshot_batch_id",
        "snapshot_batch_digest",
        "snapshot_candidates_sha256",
        "snapshot_screened_sha256",
        "snapshot_raw_manifest_sha256",
        "screen_record_sha256",
        "strict_screen_sha256",
        "motion_linkage_sha256",
        "restriction_evidence",
        "source_evidence",
    }
    if set(record) != expected:
        raise DocketDecisionTextSourceError(
            "docket decision text source has an open or incomplete schema"
        )
    required = {
        "schema_version": DOCKET_DECISION_TEXT_SOURCE_SCHEMA,
        "source_kind": _SOURCE_KIND,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "audit_only": True,
        "materialization_required": False,
    }
    if any(record.get(key) != value for key, value in required.items()):
        raise DocketDecisionTextSourceError(
            "docket decision text visibility or outcome contract is invalid"
        )
    text = _required_string(record.get("text"), "docket decision text")
    if record.get("text_sha256") != _bytes_sha256(text.encode()) or record.get(
        "text_byte_count"
    ) != len(text.encode()):
        raise DocketDecisionTextSourceError(
            "docket decision text commitment is invalid"
        )
    basis = record.get("source_basis")
    source_evidence = _mapping(record.get("source_evidence"), "source evidence")
    expected_source_keys = (
        {
            "schema_version",
            "raw_artifact_path",
            "raw_artifact_sha256",
            "raw_artifact_byte_count",
            "raw_artifact_retrieved_at",
            "policy_rebind",
        }
        if basis == RAW_COURTLISTENER_HTML_BASIS
        else {
            "schema_version",
            "canonical_rest_screen_complete",
            "reconstruction_proof",
            "decision_entry_evidence",
        }
        if basis == MANIFEST_BOUND_REST_BASIS
        else None
    )
    if expected_source_keys is None or set(source_evidence) != expected_source_keys:
        raise DocketDecisionTextSourceError(
            "docket decision source basis or evidence schema is invalid"
        )


def _selection_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_string(record.get("candidate_id"), "candidate ID")
        if candidate_id in result:
            raise DocketDecisionTextSourceError("selection repeats a candidate")
        result[candidate_id] = record
    return result


def _screen_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = _required_string(
            record.get("candidate_id"), "screen candidate ID"
        )
        if candidate_id in result:
            raise DocketDecisionTextSourceError(
                "screening snapshot repeats a candidate"
            )
        result[candidate_id] = record
    return result


def _require_selection_identity(
    selection: Mapping[str, Any], candidate_id: str
) -> None:
    if (
        selection.get("candidate_id") != candidate_id
        or selection.get("case_id") != candidate_id
        or selection.get("selected") is not True
    ):
        raise DocketDecisionTextSourceError(
            "frozen selection candidate, case, or selected identity is invalid"
        )


def _selected_entries(evidence: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    value = evidence.get("selected_entries")
    if not isinstance(value, list) or not value:
        raise DocketDecisionTextSourceError("selected docket entries must be non-empty")
    return tuple(
        _mapping(record, "selected docket entry")
        for record in cast(list[object], value)
    )


def _unique_entry(
    entries: Sequence[Mapping[str, Any]], *, entry_number: str
) -> Mapping[str, Any]:
    matches = [entry for entry in entries if entry.get("entry_number") == entry_number]
    if len(matches) != 1:
        raise DocketDecisionTextSourceError(
            "selected decision entry is absent or duplicated"
        )
    entry = matches[0]
    if entry.get("row_id") != f"entry-{entry_number}":
        raise DocketDecisionTextSourceError(
            "selected decision entry row identity is invalid"
        )
    return entry


def _manifest_file_sha256(files: Mapping[str, Any], filename: str) -> str:
    record = _mapping(files.get(filename), f"snapshot {filename} commitment")
    return _sha256(record.get("sha256"), f"snapshot {filename}")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DocketDecisionTextSourceError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise DocketDecisionTextSourceError(f"{label} must be text")
    return value


def _required_string(value: object, label: str) -> str:
    rendered = _string(value, label)
    if not rendered.strip():
        raise DocketDecisionTextSourceError(f"{label} must be non-empty")
    return rendered


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise DocketDecisionTextSourceError(f"{label} must be a string list")
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        raise DocketDecisionTextSourceError(f"{label} must be a string list")
    rendered = tuple(cast(list[str], values))
    if len(rendered) != len(set(rendered)):
        raise DocketDecisionTextSourceError(f"{label} must not contain duplicates")
    return rendered


def _positive_int_list(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise DocketDecisionTextSourceError(f"{label} must be a non-empty integer list")
    rendered = tuple(_positive_int(item, label) for item in cast(list[object], value))
    if len(rendered) != len(set(rendered)):
        raise DocketDecisionTextSourceError(f"{label} must not contain duplicates")
    return rendered


def _positive_intish_list(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise DocketDecisionTextSourceError(f"{label} must be a non-empty list")
    rendered = tuple(
        _positive_intish(item, label) for item in cast(list[object], value)
    )
    if len(rendered) != len(set(rendered)):
        raise DocketDecisionTextSourceError(f"{label} contains duplicates")
    return rendered


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DocketDecisionTextSourceError(f"{label} must be a positive integer")
    return value


def _positive_intish(value: object, label: str) -> int:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    return _positive_int(value, label)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise DocketDecisionTextSourceError(f"{label} must be boolean")
    return value


def _canonical_date(value: object, label: str) -> date:
    rendered = _required_string(value, label)
    try:
        parsed = date.fromisoformat(rendered)
    except ValueError as exc:
        raise DocketDecisionTextSourceError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != rendered:
        raise DocketDecisionTextSourceError(f"{label} must be a canonical ISO date")
    return parsed


def _sha256(value: object, label: str) -> str:
    rendered = _required_string(value, label)
    normalized = rendered.removeprefix("sha256:")
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise DocketDecisionTextSourceError(f"{label} must be a lowercase SHA-256")
    return normalized


def _bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _capture_selection_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[tuple[JsonRecord, ...], bytes]:
    """Capture the canonical frozen-selection JSONL represented by records."""

    try:
        payload = b"".join(
            (
                json.dumps(
                    dict(record),
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
            for record in records
        )
        captured = tuple(
            cast(JsonRecord, json.loads(line)) for line in payload.splitlines()
        )
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocketDecisionTextSourceError(
            "selection records are not canonical JSONL values"
        ) from exc
    if not captured:
        raise DocketDecisionTextSourceError("selection records must not be empty")
    return captured, payload


def _capture_screening_snapshot(
    snapshot: VerifiedScreeningSnapshot,
    *,
    expected_manifest_sha256: str,
) -> VerifiedScreeningSnapshot:
    """Re-authenticate the exact manifest, screen, and raw-artifact metadata."""

    expected_manifest = _sha256(
        expected_manifest_sha256,
        "expected snapshot manifest",
    )
    manifest_bytes = snapshot.payloads.get("manifest.json")
    screened_bytes = snapshot.payloads.get("screened-cases.jsonl")
    raw_manifest_bytes = snapshot.payloads.get("raw-artifacts.jsonl")
    if not isinstance(manifest_bytes, bytes) or not isinstance(screened_bytes, bytes):
        raise DocketDecisionTextSourceError(
            "screening snapshot lacks captured manifest or screened-case bytes"
        )
    if not isinstance(raw_manifest_bytes, bytes):
        raise DocketDecisionTextSourceError(
            "screening snapshot lacks captured raw-artifact metadata"
        )
    if (
        _bytes_sha256(manifest_bytes) != expected_manifest
        or snapshot.manifest_sha256 != expected_manifest
    ):
        raise DocketDecisionTextSourceError(
            "screening snapshot differs from the frozen manifest pin"
        )
    manifest = _json_record_bytes(manifest_bytes, "screening snapshot manifest")
    if manifest != dict(snapshot.manifest):
        raise DocketDecisionTextSourceError(
            "screening snapshot manifest differs from its captured bytes"
        )
    files = _mapping(manifest.get("files"), "screening snapshot file commitments")
    for name, payload in (
        ("screened-cases.jsonl", screened_bytes),
        ("raw-artifacts.jsonl", raw_manifest_bytes),
    ):
        commitment = _mapping(files.get(name), f"{name} commitment")
        if commitment.get("sha256") != _bytes_sha256(payload):
            raise DocketDecisionTextSourceError(
                f"screening snapshot {name} differs from its manifest commitment"
            )
    screened = tuple(_jsonl_records(screened_bytes, "screened cases"))
    if screened != tuple(snapshot.screened):
        raise DocketDecisionTextSourceError(
            "screening snapshot records differ from captured screened-case bytes"
        )
    raw_records = (
        ()
        if raw_manifest_bytes == b""
        else tuple(_jsonl_records(raw_manifest_bytes, "raw artifact metadata"))
    )
    raw_by_identity = {
        (
            _required_string(record.get("candidate_id"), "raw candidate ID"),
            _required_string(record.get("path"), "raw artifact path"),
        ): record
        for record in raw_records
    }
    if len(raw_by_identity) != len(raw_records):
        raise DocketDecisionTextSourceError(
            "screening snapshot repeats raw-artifact metadata"
        )
    if len(raw_by_identity) != len(snapshot.raw_artifacts):
        raise DocketDecisionTextSourceError(
            "screening snapshot raw artifacts differ from captured metadata"
        )
    for artifact in snapshot.raw_artifacts:
        record = raw_by_identity.get((artifact.candidate_id, str(artifact.path)))
        if record is None or any(
            record.get(key) != expected
            for key, expected in {
                "sha256": artifact.sha256,
                "byte_count": artifact.byte_count,
                "retrieved_at": artifact.retrieved_at,
            }.items()
        ):
            raise DocketDecisionTextSourceError(
                "screening snapshot raw artifact differs from captured metadata"
            )
    return VerifiedScreeningSnapshot(
        manifest=manifest,
        manifest_sha256=expected_manifest,
        candidates=snapshot.candidates,
        screened=screened,
        exclusions=snapshot.exclusions,
        payloads=dict(snapshot.payloads),
        raw_artifacts=snapshot.raw_artifacts,
    )


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _canonical_jsonl(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_json_bytes(dict(record)) for record in records)


def _json_record_bytes(payload: bytes, label: str) -> JsonRecord:
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocketDecisionTextSourceError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, dict):
        raise DocketDecisionTextSourceError(f"{label} is not a canonical object")
    record = cast(JsonRecord, value)
    if _canonical_json_bytes(record) != payload:
        raise DocketDecisionTextSourceError(f"{label} is not a canonical object")
    return record


def _jsonl_records(payload: bytes, label: str) -> list[JsonRecord]:
    if not payload or not payload.endswith(b"\n"):
        raise DocketDecisionTextSourceError(
            f"{label} must be nonempty newline-terminated JSONL"
        )
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(keepends=True), start=1):
        record = _json_record_bytes(line, f"{label} line {line_number}")
        records.append(record)
    return records


def _canonical_sha256(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _bytes_sha256(payload)

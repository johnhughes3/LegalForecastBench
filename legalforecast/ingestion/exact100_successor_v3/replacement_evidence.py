"""Sealed replacement evidence for owner-adjudicated exact-100 promotions.

Successor promotions have until now been *derived*: the v2 executor picks the
next candidate from the sealed wider-rank horizon, and an operator cannot name
one.  Owner decision B4:A admits a second, narrower source — a replacement the
owner adjudicated after that horizon was exhausted — on the condition that it
carries full provenance and fully validated documents.

This module is the capability that condition turns into code.  It mints one
sealed :class:`VerifiedOwnerAdjudicatedReplacement` per candidate, and it mints
it only when every one of these holds:

* every document's bytes hash to the digest its acquisition receipt recorded,
* every document has a byte-role validation record, keyed by that same digest,
  whose verdict is an exact role match with no structural defect,
* the mapped semantic roles cover every required packet role,
* the owner disposition names this candidate as the replacement for this slot,
* every synthesized selection-row field names the artifact it came from.

Nothing here is trusted because a caller passed it.  A manifest of pointers is
an input; authority comes from re-deriving each claim against the artifact the
pointer names.  A replacement missing any leg of that refuses rather than
degrading, which is the fail-closed half of B4:A.

The module is deliberately free of paths and of provider, retrieval, paid,
model, evaluation, freeze and dispatch capability: it receives bytes and
records, and returns a sealed value or raises.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from legalforecast.contracts import OWNER_ADJUDICATED_REPLACEMENT_EVIDENCE_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.provenance import DocumentRole

JsonRecord = dict[str, Any]

EVIDENCE_SCHEMA_VERSION = str(OWNER_ADJUDICATED_REPLACEMENT_EVIDENCE_V1)

_SEAL = object()
_REQUIRED_BASE_ROLES = frozenset(
    {
        DocumentRole.COMPLAINT.value,
        DocumentRole.MTD_MEMORANDUM.value,
        DocumentRole.DECISION.value,
    }
)

# Acquisition receipts across the repair tranches label documents with tranche
# vocabulary ("operative_pleading", "target_motion_opening_brief"), not with the
# corpus DocumentRole vocabulary.  The map is closed on purpose: an unmapped
# receipt role refuses, so a new tranche label can never silently enter a packet
# as some adjacent role.
_RECEIPT_ROLE_TO_DOCUMENT_ROLE: Mapping[str, str] = MappingProxyType(
    {
        "operative_pleading": DocumentRole.COMPLAINT.value,
        "amended_operative_pleading": DocumentRole.AMENDED_COMPLAINT.value,
        "complaint": DocumentRole.COMPLAINT.value,
        "amended_complaint": DocumentRole.AMENDED_COMPLAINT.value,
        "target_motion": DocumentRole.MTD_MEMORANDUM.value,
        "target_motion_opening_brief": DocumentRole.MTD_MEMORANDUM.value,
        "opening_memorandum": DocumentRole.MTD_MEMORANDUM.value,
        "motion_to_dismiss_memorandum": DocumentRole.MTD_MEMORANDUM.value,
        "motion_to_dismiss_notice": DocumentRole.MTD_NOTICE.value,
        "opposition": DocumentRole.OPPOSITION.value,
        "reply": DocumentRole.REPLY.value,
        "amended_reply": DocumentRole.REPLY.value,
        "surreply": DocumentRole.SURREPLY.value,
        "decision": DocumentRole.DECISION.value,
        "decision_audit_only": DocumentRole.DECISION.value,
    }
)
# Which validation regime cleared a document.  The paid tranche carries a
# quote-verified byte-role verdict; the free tranches carry strict PDF parsing
# plus recorded role findings and a visual render check.
_VALIDATION_CLASSES = frozenset(
    {
        "document_repair_byte_role_verdict",
        "free_tranche_strict_pdf_and_role_findings",
    }
)
_DOCUMENT_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {
        DocumentRole.COMPLAINT.value: "Operative Complaint",
        DocumentRole.AMENDED_COMPLAINT.value: "Amended Complaint",
        DocumentRole.MTD_NOTICE.value: "Motion to Dismiss Notice",
        DocumentRole.MTD_MEMORANDUM.value: "Motion to Dismiss and Memorandum",
        DocumentRole.OPPOSITION.value: "Opposition to Motion to Dismiss",
        DocumentRole.REPLY.value: "Reply in Support of Motion to Dismiss",
        DocumentRole.SURREPLY.value: "Surreply",
        DocumentRole.DECISION.value: "Written MTD Disposition",
    }
)


class OwnerAdjudicatedReplacementError(ValueError):
    """Raised when replacement evidence is not complete and byte-authenticated."""


class ReplacementAcquisitionRoute(StrEnum):
    """How a replacement document was obtained, in the corpus vocabulary."""

    FREE = "free"
    PURCHASED = "purchased"


@dataclass(frozen=True, slots=True, init=False)
class VerifiedOwnerAdjudicatedReplacement:
    """One owner-adjudicated replacement, sealed after byte re-derivation."""

    candidate_id: str
    replaces_candidate_id: str
    selection_row: JsonRecord
    case_relevance_row: JsonRecord
    download_manifest: tuple[JsonRecord, ...]
    disclosure_clearance: tuple[JsonRecord, ...]
    restriction_evidence: tuple[JsonRecord, ...]
    document_bytes: Mapping[str, bytes]
    required_document_sha256: Mapping[str, str]
    field_provenance: Mapping[str, str]
    source_commitments: Mapping[str, str]
    commitment_sha256: str
    _verification_seal: object = field(repr=False, compare=False)


def mint_verified_owner_adjudicated_replacement(
    *,
    candidate_id: str,
    replaces_candidate_id: str,
    documents: Sequence[Mapping[str, Any]],
    document_bytes_by_id: Mapping[str, bytes],
    byte_role_validation_by_id: Mapping[str, Mapping[str, Any]],
    docket_entries_by_number: Mapping[int, Mapping[str, Any]],
    case_identity: Mapping[str, Any],
    owner_disposition: Mapping[str, Any],
    field_provenance: Mapping[str, Any],
    source_commitments: Mapping[str, str],
) -> VerifiedOwnerAdjudicatedReplacement:
    """Seal a replacement only when every claim re-derives from its evidence.

    ``documents`` carries the receipt rows; it is a manifest of pointers, never
    authority.  Each row is checked against the bytes it names, the byte-role
    validation record keyed by the same digest, and the authenticated docket
    entry it claims -- so a manifest cannot assert a role, a digest, or a docket
    position that the underlying evidence does not already support.
    """

    if not candidate_id or not replaces_candidate_id:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement requires both candidate identities"
        )
    if candidate_id == replaces_candidate_id:
        raise OwnerAdjudicatedReplacementError(
            "an owner-adjudicated replacement cannot replace itself"
        )
    _require_owner_disposition(
        owner_disposition,
        candidate_id=candidate_id,
        replaces_candidate_id=replaces_candidate_id,
    )
    if not documents:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement has no documents"
        )

    manifest: list[JsonRecord] = []
    clearance: list[JsonRecord] = []
    restriction: list[JsonRecord] = []
    selection_documents: list[JsonRecord] = []
    required_document_sha256: dict[str, str] = {}
    present_roles: set[str] = set()
    seen: set[str] = set()
    decision_entry_numbers: list[int] = []
    target_motion_entry_numbers: list[int] = []

    for row in _ordered(documents):
        source_document_id = _text(row, "source_document_id")
        if source_document_id in seen:
            raise OwnerAdjudicatedReplacementError(
                f"replacement document repeats: {source_document_id}"
            )
        seen.add(source_document_id)
        if _text(row, "candidate_id") != candidate_id:
            raise OwnerAdjudicatedReplacementError(
                "replacement manifest contains another candidate"
            )
        payload = document_bytes_by_id.get(source_document_id)
        if not isinstance(payload, bytes) or not payload:
            raise OwnerAdjudicatedReplacementError(
                f"replacement document bytes are missing: {source_document_id}"
            )
        digest = hashlib.sha256(payload).hexdigest()
        if _hex(row, "sha256") != digest:
            raise OwnerAdjudicatedReplacementError(
                f"replacement document bytes differ from the receipt digest: "
                f"{source_document_id}"
            )
        byte_count = row.get("byte_count")
        if byte_count != len(payload):
            raise OwnerAdjudicatedReplacementError(
                f"replacement document byte count differs: {source_document_id}"
            )
        role = _mapped_role(_text(row, "document_role"))
        entry_number = _entry_number(row)
        _require_docket_entry(
            docket_entries_by_number,
            entry_number=entry_number,
            source_document_id=source_document_id,
        )
        validation_class = _require_byte_role_validation(
            byte_role_validation_by_id.get(source_document_id),
            source_document_id=source_document_id,
            digest=digest,
            byte_count=len(payload),
            receipt_role=_text(row, "document_role"),
        )
        route = _route(row)
        is_decision = role == DocumentRole.DECISION.value
        if is_decision:
            decision_entry_numbers.append(entry_number)
        if role in {DocumentRole.MTD_MEMORANDUM.value, DocumentRole.MTD_NOTICE.value}:
            target_motion_entry_numbers.append(entry_number)
        present_roles.add(_required_role(role))
        if _required_role(role) in _REQUIRED_BASE_ROLES or role == (
            DocumentRole.OPPOSITION.value
        ):
            required_document_sha256[source_document_id] = digest
        source_url = row.get("source_url")
        if source_url is not None and not isinstance(source_url, str):
            raise OwnerAdjudicatedReplacementError(
                f"replacement document source URL is invalid: {source_document_id}"
            )
        # ``local_path`` is resolved by downstream materialisation against the
        # successor root's sidecar documents tree, so it must be the path
        # relative to that tree, not the path inside this evidence root.  Root
        # 46 set the precedent: its newly promoted candidate's merged-manifest
        # rows are candidate-structured for exactly this reason.
        local_path = f"{candidate_id}/{source_document_id}.pdf"
        manifest.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "docket_entry_number": entry_number,
                "document_role": role,
                "free_or_purchased": route.value,
                "local_path": local_path,
                "sha256": digest,
                "source_document_id": source_document_id,
                "source_url": source_url,
                "validation_class": validation_class,
            }
        )
        clearance.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "clearance_basis": (
                    "paid_delivery"
                    if route is ReplacementAcquisitionRoute.PURCHASED
                    else "courtlistener_public_download"
                ),
                "free_or_purchased": route.value,
                "sha256": digest,
                "source_document_id": source_document_id,
                "status": "cleared",
            }
        )
        restriction.append(
            {
                "candidate_id": candidate_id,
                "is_private": False,
                "is_sealed": False,
                "restriction_evidence": _restriction_evidence(route),
                "restriction_status": "public",
                "source_document_id": source_document_id,
            }
        )
        selection_documents.append(
            {
                "candidate_id": candidate_id,
                # Outcome leakage: only the disposition carries the target
                # outcome, and only it is withheld from the model.
                "contains_target_outcome": is_decision,
                "description": _DOCUMENT_DESCRIPTIONS.get(role, role),
                "docket_entry_number": entry_number,
                "document_role": role,
                "is_private": False,
                "is_sealed": False,
                "model_visible": not is_decision,
                "redaction_or_seal_status": "public",
                "restriction_evidence": _restriction_evidence(route),
                "setup_runner_label": (
                    "other_substantive" if is_decision else "core_mtd"
                ),
                "source_document_id": source_document_id,
                "source_url": source_url,
            }
        )

    required_roles = set(_REQUIRED_BASE_ROLES)
    if DocumentRole.OPPOSITION.value in present_roles:
        required_roles.add(DocumentRole.OPPOSITION.value)
    if not required_roles <= present_roles:
        missing = ", ".join(sorted(required_roles - present_roles))
        raise OwnerAdjudicatedReplacementError(
            f"owner-adjudicated replacement packet is incomplete: missing {missing}"
        )
    if len(decision_entry_numbers) != 1:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement needs exactly one disposition document"
        )
    if not target_motion_entry_numbers:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement needs a target motion document"
        )

    provenance = _validated_field_provenance(field_provenance)
    commitments = _validated_commitments(source_commitments)
    selection_row = _selection_row(
        candidate_id=candidate_id,
        case_identity=case_identity,
        documents=selection_documents,
        free_document_count=sum(
            1 for row in manifest if row["free_or_purchased"] == "free"
        ),
        required_role_count=len(required_roles),
        decision_entry_numbers=sorted(decision_entry_numbers),
        target_motion_entry_numbers=sorted(target_motion_entry_numbers),
    )
    document_tree = {
        f"documents/{candidate_id}/{key}.pdf": value
        for key, value in sorted(document_bytes_by_id.items())
        if key in seen
    }
    commitment = _replacement_commitment_sha256(
        candidate_id=candidate_id,
        replaces_candidate_id=replaces_candidate_id,
        selection_row=selection_row,
        manifest=manifest,
        clearance=clearance,
        restriction=restriction,
        document_tree=document_tree,
        field_provenance=provenance,
        source_commitments=commitments,
    )
    value = object.__new__(VerifiedOwnerAdjudicatedReplacement)
    for name, item in (
        ("candidate_id", candidate_id),
        ("replaces_candidate_id", replaces_candidate_id),
        ("selection_row", selection_row),
        ("case_relevance_row", dict(selection_row)),
        ("download_manifest", tuple(manifest)),
        ("disclosure_clearance", tuple(clearance)),
        ("restriction_evidence", tuple(restriction)),
        ("document_bytes", MappingProxyType(document_tree)),
        (
            "required_document_sha256",
            MappingProxyType(dict(sorted(required_document_sha256.items()))),
        ),
        ("field_provenance", MappingProxyType(provenance)),
        ("source_commitments", MappingProxyType(commitments)),
        ("commitment_sha256", commitment),
        ("_verification_seal", _SEAL),
    ):
        object.__setattr__(value, name, item)
    return value


# contract-ratchet: allow in-process capability seal, never a persisted artifact
def _replacement_commitment_sha256(
    *,
    candidate_id: str,
    replaces_candidate_id: str,
    selection_row: Mapping[str, Any],
    manifest: Sequence[Mapping[str, Any]],
    clearance: Sequence[Mapping[str, Any]],
    restriction: Sequence[Mapping[str, Any]],
    document_tree: Mapping[str, bytes],
    field_provenance: Mapping[str, str],
    source_commitments: Mapping[str, str],
) -> str:
    """Commit every field a consumer relies on, so mutation is detectable."""

    return _sha(
        _canonical_bytes(
            {
                "candidate_id": candidate_id,
                "replaces_candidate_id": replaces_candidate_id,
                "selection_row": _sha(_canonical_bytes(dict(selection_row))),
                "download_manifest": _sha(_jsonl_bytes(manifest)),
                "disclosure_clearance": _sha(_jsonl_bytes(clearance)),
                "restriction_evidence": _sha(_jsonl_bytes(restriction)),
                "document_tree": _sha(
                    _canonical_bytes(
                        {
                            name: hashlib.sha256(payload).hexdigest()
                            for name, payload in sorted(document_tree.items())
                        }
                    )
                ),
                "field_provenance": dict(field_provenance),
                "source_commitments": dict(source_commitments),
            }
        )
    )


def require_verified_owner_adjudicated_replacement(
    replacement: VerifiedOwnerAdjudicatedReplacement,
) -> None:
    """Reject a caller-constructed or mutated replacement capability.

    Checking the seal alone is not enough.  The dataclass is frozen but its
    records are ordinary dicts and lists, so a minted replacement can still be
    reached into -- flipping a disposition to ``model_visible``, say -- without
    the seal noticing.  Recomputing the commitment over every field a consumer
    relies on is what makes that mutation detectable.
    """

    if (
        type(replacement) is not VerifiedOwnerAdjudicatedReplacement
        or getattr(replacement, "_verification_seal", None) is not _SEAL
    ):
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement was not produced by verified minting"
        )
    if replacement.case_relevance_row != replacement.selection_row:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement changed after verified minting"
        )
    if replacement.commitment_sha256 != _replacement_commitment_sha256(
        candidate_id=replacement.candidate_id,
        replaces_candidate_id=replacement.replaces_candidate_id,
        selection_row=replacement.selection_row,
        manifest=replacement.download_manifest,
        clearance=replacement.disclosure_clearance,
        restriction=replacement.restriction_evidence,
        document_tree=replacement.document_bytes,
        field_provenance=replacement.field_provenance,
        source_commitments=replacement.source_commitments,
    ):
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement changed after verified minting"
        )


def _require_owner_disposition(
    disposition: Mapping[str, Any],
    *,
    candidate_id: str,
    replaces_candidate_id: str,
) -> None:
    """Require the owner record to name exactly this slot and replacement."""

    if disposition.get("excluded_candidate_id") != replaces_candidate_id:
        raise OwnerAdjudicatedReplacementError(
            "owner disposition does not name the excluded slot"
        )
    if disposition.get("replacement_candidate_id") != candidate_id:
        raise OwnerAdjudicatedReplacementError(
            "owner disposition does not name this replacement candidate"
        )
    verbatim = disposition.get("owner_verbatim")
    if not isinstance(verbatim, str) or not verbatim.strip():
        raise OwnerAdjudicatedReplacementError(
            "owner disposition carries no recorded owner text"
        )
    source = disposition.get("signoff_source")
    if not isinstance(source, str) or not source.strip():
        raise OwnerAdjudicatedReplacementError(
            "owner disposition does not name the source of its owner text"
        )


def _require_byte_role_validation(
    record: Mapping[str, Any] | None,
    *,
    source_document_id: str,
    digest: str,
    byte_count: int,
    receipt_role: str,
) -> str:
    """Require an exact-role verdict bound to these exact bytes and this role.

    A verdict of "match" only means something once you know *which* role it
    matched.  The tranches label the same document differently ("target_motion"
    on the receipt, "target_motion_opening_brief" in the validation), so the
    comparison is on the mapped corpus role rather than on the raw label.
    """

    if record is None:
        raise OwnerAdjudicatedReplacementError(
            f"replacement document has no byte-role validation: {source_document_id}"
        )
    if _hex(record, "pdf_sha256") != digest or record.get("pdf_byte_count") != (
        byte_count
    ):
        raise OwnerAdjudicatedReplacementError(
            f"byte-role validation binds different bytes: {source_document_id}"
        )
    if record.get("role_verdict") != "match":
        raise OwnerAdjudicatedReplacementError(
            f"replacement document role is not an exact match: {source_document_id}"
        )
    if record.get("strict_parse") != "pass":
        raise OwnerAdjudicatedReplacementError(
            f"replacement document failed strict parsing: {source_document_id}"
        )
    defects = record.get("structural_defects")
    if defects not in ([], ()):
        raise OwnerAdjudicatedReplacementError(
            f"replacement document has structural defects: {source_document_id}"
        )
    if record.get("encrypted") is not False:
        raise OwnerAdjudicatedReplacementError(
            f"replacement document is encrypted: {source_document_id}"
        )
    # The repair tranches validated paid and free documents under different
    # regimes.  Both are accepted, but which one applied is recorded per
    # document rather than flattened away, so a reader of the promotion can see
    # exactly what was checked.
    validated_role = record.get("requested_role")
    if not isinstance(validated_role, str) or _mapped_role(validated_role) != (
        _mapped_role(receipt_role)
    ):
        raise OwnerAdjudicatedReplacementError(
            f"byte-role validation is for a different role: {source_document_id}"
        )
    validation_class = record.get("validation_class")
    if validation_class not in _VALIDATION_CLASSES:
        raise OwnerAdjudicatedReplacementError(
            f"replacement document validation regime is unrecorded: "
            f"{source_document_id}"
        )
    return cast(str, validation_class)


def _require_docket_entry(
    entries: Mapping[int, Mapping[str, Any]],
    *,
    entry_number: int,
    source_document_id: str,
) -> None:
    """Require the authenticated docket snapshot to place this document."""

    entry = entries.get(entry_number)
    if entry is None:
        raise OwnerAdjudicatedReplacementError(
            f"docket snapshot lacks entry {entry_number} for {source_document_id}"
        )
    documents = entry.get("recap_documents")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise OwnerAdjudicatedReplacementError(
            f"docket entry {entry_number} carries no documents"
        )
    identifiers = {
        str(cast(Mapping[str, Any], item).get("id"))
        for item in cast(Sequence[object], documents)
        if isinstance(item, Mapping)
    }
    if source_document_id not in identifiers:
        raise OwnerAdjudicatedReplacementError(
            f"docket entry {entry_number} does not carry {source_document_id}"
        )


def _selection_row(
    *,
    candidate_id: str,
    case_identity: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    free_document_count: int,
    required_role_count: int,
    decision_entry_numbers: Sequence[int],
    target_motion_entry_numbers: Sequence[int],
) -> JsonRecord:
    """Assemble the corpus selection row from verified identity and documents."""

    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "case_name": _text(case_identity, "case_name"),
        "case_type_stratum": "district_civil",
        "cost_rank": None,
        "court": _text(case_identity, "court"),
        "decision_date": _text(case_identity, "decision_date"),
        "decision_entry_numbers": list(decision_entry_numbers),
        "docket_number": _text(case_identity, "docket_number"),
        "documents": [dict(document) for document in documents],
        "exclusion_reasons": [],
        "free_required_document_count": free_document_count,
        "mdl_family_id": None,
        "missing_required_document_count": 0,
        "nature_of_suit": case_identity.get("nature_of_suit"),
        "nos_macro_category": case_identity.get("nos_macro_category"),
        "paid_gap_reasons": [],
        "paid_recovery_required": False,
        "planning_status": "owner_adjudicated_packet_complete",
        "projected_paid_cost_usd": "0.00",
        "related_family_id": None,
        "required_document_count": required_role_count,
        "selected": True,
        "source_url": _text(case_identity, "source_url"),
        "target_motion_entry_numbers": list(target_motion_entry_numbers),
    }


def _restriction_evidence(route: ReplacementAcquisitionRoute) -> list[str]:
    """Name the evidence that makes each acquisition route publicly usable.

    A purchased document's public status is proven by its post-delivery repair
    receipt, not by CourtListener's ``is_private`` field, which REST v4 no
    longer serializes.  A free document keeps the public-download evidence.
    """

    if route is ReplacementAcquisitionRoute.PURCHASED:
        return [
            "document_repair_paid_delivery_clearance",
            "document_repair_byte_role_validation_match",
        ]
    return [
        "courtlistener_public_download_record_checked",
        "document_repair_byte_role_validation_match",
    ]


def _ordered(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (_entry_number(row), _text(row, "source_document_id")),
    )


def _entry_number(row: Mapping[str, Any]) -> int:
    value = row.get("docket_entry_number")
    if type(value) is not int or value < 0:
        raise OwnerAdjudicatedReplacementError(
            "replacement document lacks a docket entry number"
        )
    return value


def _route(row: Mapping[str, Any]) -> ReplacementAcquisitionRoute:
    value = row.get("free_or_purchased")
    try:
        return ReplacementAcquisitionRoute(value)
    except ValueError as exc:
        raise OwnerAdjudicatedReplacementError(
            "replacement document has an unknown acquisition route"
        ) from exc


def _mapped_role(receipt_role: str) -> str:
    role = _RECEIPT_ROLE_TO_DOCUMENT_ROLE.get(receipt_role)
    if role is None:
        raise OwnerAdjudicatedReplacementError(
            f"replacement document role is outside the closed map: {receipt_role}"
        )
    return role


def _required_role(role: str) -> str:
    return (
        DocumentRole.COMPLAINT.value
        if role == DocumentRole.AMENDED_COMPLAINT.value
        else role
    )


def _validated_field_provenance(values: Mapping[str, Any]) -> dict[str, str]:
    """Require every synthesized identity field to name its source artifact."""

    required = {"case_name", "court", "docket_number", "decision_date", "source_url"}
    result = {
        str(name): value
        for name, value in cast(Mapping[object, object], values).items()
        if isinstance(name, str) and isinstance(value, str) and value.strip()
    }
    if not required <= set(result):
        missing = ", ".join(sorted(required - set(result)))
        raise OwnerAdjudicatedReplacementError(
            f"replacement identity fields lack recorded provenance: {missing}"
        )
    return dict(sorted(result.items()))


def _validated_commitments(values: Mapping[str, str]) -> dict[str, str]:
    if not values:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement requires source commitments"
        )
    result: dict[str, str] = {}
    for name, value in values.items():
        raw = value.removeprefix("sha256:")
        if (
            not name
            or len(raw) != 64
            or any(ch not in "0123456789abcdef" for ch in raw)
        ):
            raise OwnerAdjudicatedReplacementError(
                "owner-adjudicated replacement source commitment is invalid"
            )
        result[name] = "sha256:" + raw
    return dict(sorted(result.items()))


def _text(row: Mapping[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise OwnerAdjudicatedReplacementError(f"record lacks {field_name}")
    return value


def _hex(row: Mapping[str, Any], field_name: str) -> str:
    value = _text(row, field_name).removeprefix("sha256:")
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise OwnerAdjudicatedReplacementError(f"record has invalid {field_name}")
    return value


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=OwnerAdjudicatedReplacementError,
        error_message="owner-adjudicated replacement serialization failed",
    )


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(dict(row)) for row in rows)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()

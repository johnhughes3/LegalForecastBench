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
import re
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
        # A brief in support, docketed separately from the motion it supports.
        # The corpus already holds this shape: where the motion and its
        # supporting brief sit on two entries, the case carries two
        # ``motion_to_dismiss_memorandum`` documents, and the byte-role
        # validator whose verdicts this mint consumes already normalises the
        # receipt spelling ``motion_memorandum`` onto that same corpus role.
        # Mapping it anywhere else would drop the document from the model
        # packet: only the complaint family, the notice, and the three brief
        # roles mount, and Stage A unitization refuses every other spelling.
        "motion_memorandum": DocumentRole.MTD_MEMORANDUM.value,
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
# Receipt roles naming briefing filed in support of the target motion rather
# than the motion itself.  Both carry the corpus memorandum role, so the packet
# holds two of them, but only the motion's own entry is the target motion: the
# corpus records that single entry, and the packet planner reaches the
# supporting brief on its own by unioning in every memorandum-role entry.  The
# convergence model draws the same line, listing this spelling under briefing
# and never under the target-motion roles.  Selecting on the receipt spelling
# rather than the mapped role is deliberate -- the mapped role cannot tell the
# two apart, and tranches spell the motion itself several ways.
_SUPPORTING_BRIEF_RECEIPT_ROLES: frozenset[str] = frozenset({"motion_memorandum"})
# Receipt spellings that name EITHER the motion or a brief in support of it,
# depending on the tranche that produced them.  One tranche's document with this
# spelling is its case's only motion; another's is the brief supporting a
# separate ``target_motion`` entry.  The spelling cannot decide, and deciding it
# wrongly damages evidence in both directions -- reading it as a brief empties
# the first case's target list, and reading it as a motion gives the second case
# two motions.  So the authenticated validation record decides: a record naming
# the entries its document supports is a brief, and a record naming none is the
# motion.  Absence is the compatible reading on purpose, because every root
# minted before linkage existed is replayed under this code.
_AMBIGUOUS_BRIEF_RECEIPT_ROLES: frozenset[str] = frozenset({"opening_memorandum"})
# A linkage claim is the one fact this validator consumes that is NOT derived
# from the bytes it hashes: it is a reading of the docket, asserted by whoever
# produced the validation.  So a record making the claim must disclose exactly
# that, in these words, or the claim would read as though the digest vouched
# for it.  The basis says how the reading was reached, and the schema status
# says the field's shape was agreed with this parser rather than guessed at --
# a record still declaring itself pending is refused, because consuming one
# would make the status decorative.
# A replacement may be sourced by a deterministic walk of the ranked reserve
# rather than by the owner picking it after the reserve horizon was exhausted.
# The two stories are published differently, and the methods disclosure is
# generated from the promotion record, so the sourcing has to be recorded where
# it is decided -- on the owner's own disposition -- rather than inferred.
# Absence is "owner adjudicated", which is what every root minted before this
# claim existed carries and what its replay depends on.
_RESERVE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_RESERVE_DERIVATION_FIELDS = frozenset(
    {"artifact_sha256", "reserve_rank", "selection_basis"}
)
_LINKAGE_AUTHORITY = "validator_asserted_docket_reading_not_byte_derived"
_LINKAGE_BASES: frozenset[str] = frozenset(
    {"explicit_entry_reference", "title", "party_posture"}
)
_LINKAGE_SCHEMA_STATUSES: frozenset[str] = frozenset({"coordinated"})
# Only one regime can clear a document's role: a per-document, quote-verified
# byte-role verdict.  The free tranches' role findings are keyed by finding
# topic and cite several documents per topic -- a disposition is quoted under
# the pleading finding -- so they can never establish a single document's own
# role, and _require_byte_role_validation refuses them as "unverified".
_VALIDATION_CLASSES = frozenset(
    {
        "document_repair_byte_role_verdict",
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
    reserve_derivation: Mapping[str, Any] | None
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
    reserve_derivation = _reserve_derivation_claim(owner_disposition)
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
    linked_briefs: list[tuple[str, frozenset[int]]] = []

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
        receipt_role = _text(row, "document_role")
        role = _mapped_role(receipt_role)
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
            receipt_role=receipt_role,
        )
        linked_entries = _supporting_brief_linkage(
            byte_role_validation_by_id.get(source_document_id),
            source_document_id=source_document_id,
        )
        if linked_entries is not None:
            linked_briefs.append((source_document_id, linked_entries))
        route = _route(row)
        is_decision = role == DocumentRole.DECISION.value
        if is_decision:
            decision_entry_numbers.append(entry_number)
        # An unconditional brief spelling is briefing whatever its record says.
        # An ambiguous one is briefing only where the record declares what it
        # supports; without that declaration it is the motion itself.
        is_supporting_brief = receipt_role in _SUPPORTING_BRIEF_RECEIPT_ROLES or (
            receipt_role in _AMBIGUOUS_BRIEF_RECEIPT_ROLES
            and linked_entries is not None
        )
        if (
            role in {DocumentRole.MTD_MEMORANDUM.value, DocumentRole.MTD_NOTICE.value}
            and not is_supporting_brief
        ):
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
    # A packet carrying only a brief in support reaches here with the memorandum
    # role present but no motion behind it, so the required-role check passes and
    # this one has to refuse.  More than one target motion is refused for the
    # opposite reason: the corpus counts exactly one per case, and emitting two
    # would strand the promotion at the readiness gate instead of here.
    #
    # The count is over distinct ENTRIES, not documents: one docket entry can
    # carry a main document and its attachments, which are separate documents
    # naming one motion.  Deduplicating here rather than only in the refusal is
    # what keeps that shape from minting a row with a repeated entry, which the
    # readiness gate counts as two target motions.
    target_entries = sorted(set(target_motion_entry_numbers))
    if not target_entries:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement needs a target motion document"
        )
    if len(target_entries) > 1:
        raise OwnerAdjudicatedReplacementError(
            "owner-adjudicated replacement names more than one target motion: "
            f"entries {target_entries}"
        )
    # A brief that declared what it supports has to have declared *this* motion.
    # The check runs only where a claim was made: silence is what every root
    # minted before linkage existed carries, and demanding linkage of those
    # would make them unusable at the first projection that included them.
    target_entry_set = frozenset(target_entries)
    for source_document_id, linked in linked_briefs:
        if linked != target_entry_set:
            raise OwnerAdjudicatedReplacementError(
                "supporting brief linkage does not name the target motion: "
                f"{source_document_id}"
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
        target_motion_entry_numbers=target_entries,
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
        # Sourcing, not evidence: deliberately outside the commitment, so
        # recording it cannot move an already-minted root's digest.
        ("reserve_derivation", reserve_derivation),
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


def _reserve_derivation_claim(
    disposition: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """The ranked-reserve sourcing claim an owner disposition may carry.

    ``None`` means no claim, which reads as owner adjudication.  A claim that is
    present but incomplete refuses rather than degrading to ``None``: the
    published methods statement repeats whatever this returns, so a half-formed
    sourcing claim is worse than none at all.
    """

    raw = disposition.get("reserve_derivation")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise OwnerAdjudicatedReplacementError(
            "owner disposition reserve derivation is not a record"
        )
    claim = cast(Mapping[str, Any], raw)
    if frozenset(claim) != _RESERVE_DERIVATION_FIELDS:
        raise OwnerAdjudicatedReplacementError(
            "owner disposition reserve derivation fields differ from "
            f"{sorted(_RESERVE_DERIVATION_FIELDS)}"
        )
    digest = claim.get("artifact_sha256")
    if not isinstance(digest, str) or _RESERVE_DIGEST.fullmatch(digest) is None:
        raise OwnerAdjudicatedReplacementError(
            "owner disposition reserve derivation names no ranked reserve digest"
        )
    rank = claim.get("reserve_rank")
    if type(rank) is not int or rank < 1:
        raise OwnerAdjudicatedReplacementError(
            "owner disposition reserve derivation carries no positive reserve rank"
        )
    basis = claim.get("selection_basis")
    if not isinstance(basis, str) or not basis.strip():
        raise OwnerAdjudicatedReplacementError(
            "owner disposition reserve derivation states no selection basis"
        )
    return MappingProxyType(
        {
            "artifact_sha256": digest,
            "reserve_rank": rank,
            "selection_basis": basis,
        }
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


def _supporting_brief_linkage(
    record: Mapping[str, Any] | None, *, source_document_id: str
) -> frozenset[int] | None:
    """The docket entries a validation record declares its document supports.

    ``None`` means the record made no linkage claim, which is the reading every
    root minted before linkage existed depends on.  A claim that is present but
    unreadable refuses instead of degrading to ``None``: degrading would resolve
    an ambiguous spelling to "target motion" and hand the packet a second motion,
    which is precisely the confusion this field exists to settle.
    """

    if record is None:
        return None
    raw = record.get("linked_motion_entries")
    if raw is None:
        return None
    entries = (
        list(cast(Sequence[object], raw))
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes))
        else None
    )
    if not entries or any(type(entry) is not int or entry < 0 for entry in entries):
        raise OwnerAdjudicatedReplacementError(
            "supporting brief linkage is not a list of docket entry numbers: "
            f"{source_document_id}"
        )
    if record.get("linkage_authority") != _LINKAGE_AUTHORITY:
        raise OwnerAdjudicatedReplacementError(
            f"supporting brief linkage authority is not disclosed: {source_document_id}"
        )
    if record.get("linkage_basis") not in _LINKAGE_BASES:
        raise OwnerAdjudicatedReplacementError(
            f"supporting brief linkage basis is not recognised: {source_document_id}"
        )
    if record.get("linkage_schema_status") not in _LINKAGE_SCHEMA_STATUSES:
        raise OwnerAdjudicatedReplacementError(
            "supporting brief linkage schema status is not recognised: "
            f"{source_document_id}"
        )
    return frozenset(cast(list[int], entries))


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
    if record.get("role_verdict") == "unverified":
        raise OwnerAdjudicatedReplacementError(
            "replacement document has no per-document byte-role verdict, only "
            f"strict-PDF validation: {source_document_id}. Run the supported "
            "byte-role validator over it and pass that artifact."
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
    # Only the byte-role verdict regime clears a role.  The regime is still
    # recorded per document rather than flattened away, so a reader of the
    # promotion can see exactly what was checked rather than inferring it.
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

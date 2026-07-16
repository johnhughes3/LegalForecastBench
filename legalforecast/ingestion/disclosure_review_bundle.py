"""Deterministic, externally signed disclosure-review bundles.

The signer is deliberately outside this module.  This code prepares the exact
bytes to review and sign, then independently verifies an SSHSIG produced by a
hardware-backed human key or a separately controlled service identity.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from legalforecast.ingestion.disclosure_clearance import build_clearance_records
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthority,
)

WORKSHEET_SCHEMA_VERSION = "legalforecast.disclosure_review_worksheet.v1"
POLICY_SCHEMA_VERSION = "legalforecast.disclosure_reviewer_policy.v1"
STATEMENT_SCHEMA_VERSION = "legalforecast.disclosure_review_statement.v1"
RECEIPT_SCHEMA_VERSION = "legalforecast.disclosure_review_receipt.v2"
SIGNATURE_NAMESPACE = "legalforecast-disclosure-review-v1"
HARDWARE_SIGNER_BEAD = "LegalForecastBench-5qd6.39.7.1"
SSH_KEYGEN = Path("/usr/bin/ssh-keygen")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_PUBLIC_RESTRICTIONS = frozenset({"public", "redacted"})
_HUMAN_KEY_TYPES = frozenset(
    {
        "sk-ssh-ed25519@openssh.com",
        "sk-ecdsa-sha2-nistp256@openssh.com",
    }
)
_SERVICE_KEY_TYPES = frozenset({"ssh-ed25519", "ecdsa-sha2-nistp256"})
_STATEMENT_FIELDS = frozenset(
    {
        "schema_version",
        "review_artifact_sha256",
        "decision_artifact_sha256",
        "decision_confirmation_sha256",
        "worksheet_sha256",
        "review_requests_sha256",
        "download_manifest_sha256",
        "restriction_evidence_sha256",
        "document_set_sha256",
        "document_count",
        "cleared_count",
        "quarantined_count",
        "decision_summary",
        "cycle_id",
        "cohort_policy_sha256",
        "eligibility_anchor",
        "disclosure_authority_sha256",
        "ssh_public_key_fingerprint",
        "authenticated_reviewer_id",
        "controlled_store_uri",
        "authentication_method",
        "authenticated_at",
        "reviewer_policy_sha256",
        "signature_namespace",
    }
)
_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "statement",
        "sshsig_base64",
        "decision_artifact_base64",
    }
)


class ReviewBundleError(ValueError):
    """Raised when review preparation or authentication fails closed."""


def read_unique_regular_file(path: Path) -> bytes:
    """Read one unique regular file through a no-follow, race-checked fd.

    Every parent component is opened relative to the preceding directory fd so
    neither an attacker-controlled parent symlink nor a last-component symlink
    can redirect the read. ``O_NONBLOCK`` makes special files fail validation
    without allowing a FIFO to stall the review process.
    """

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ReviewBundleError("safe private-file reads require O_NOFOLLOW")
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow | os.O_CLOEXEC
    file_flags = os.O_RDONLY | os.O_NONBLOCK | nofollow | os.O_CLOEXEC
    directory_fd: int | None = None
    file_fd: int | None = None
    try:
        directory_fd = os.open(parts[0], directory_flags)
        for component in parts[1:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(parts[-1], file_flags, dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ReviewBundleError(f"path is not a unique regular file: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(file_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(getattr(before, name) != getattr(after, name) for name in stable_fields):
            raise ReviewBundleError(f"file changed while it was read: {path}")
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise ReviewBundleError(f"file changed while it was read: {path}")
        return payload
    except ReviewBundleError:
        raise
    except OSError as exc:
        raise ReviewBundleError(f"path cannot be safely read: {path}") from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


@dataclass(frozen=True, slots=True)
class VerifiedReviewAuthority:
    """Identity and provenance recovered from a verified signed statement."""

    reviewer_id: str
    controlled_store_uri: str
    authentication_method: str
    authenticated_at: str
    review_artifact_sha256: str
    reviewer_policy_sha256: str


@dataclass(frozen=True, slots=True)
class ReviewerPolicy:
    """Strict, externally pinned reviewer-verification policy."""

    reviewer_id: str
    ssh_principal: str
    ssh_key_type: str
    ssh_key_data: str
    identity_kind: str
    controlled_store_uri_prefix: str
    signature_namespace: str
    sha256: str

    @property
    def authentication_method(self) -> str:
        """Return the receipt method implied by this key's custody class."""

        if self.identity_kind == "human_hardware":
            return "human_hardware_ssh_signature"
        return "controlled_store_service_ssh_signature"


def canonical_json_bytes(value: object) -> bytes:
    """Return the one canonical byte representation used for signatures."""

    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def prepare_review_worksheet(
    review_requests: Sequence[Mapping[str, object]],
    download_manifest: Sequence[Mapping[str, object]],
    restriction_evidence: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
) -> dict[str, object]:
    """Hash exact inputs and emit a deterministic, value-redacted worksheet."""

    _require_jsonl_records_match(
        review_requests, review_requests_bytes, "review requests"
    )
    _require_jsonl_records_match(
        download_manifest, download_manifest_bytes, "download manifest"
    )
    _require_jsonl_records_match(
        restriction_evidence,
        restriction_evidence_bytes,
        "restriction evidence",
    )
    request_index = _unique_index(review_requests, "review request")
    manifest_index = _unique_index(download_manifest, "download manifest")
    restriction_keys = {_key(row) for row in restriction_evidence}
    if set(request_index) != set(manifest_index) or restriction_keys != set(
        manifest_index
    ):
        raise ReviewBundleError(
            "review worksheet input coverage mismatch across requests, manifest, "
            "and restriction evidence"
        )
    try:
        scanned = build_clearance_records(
            download_manifest,
            document_root=document_root,
            reviews=(),
            restriction_records=restriction_evidence,
        )
    except ValueError as exc:
        raise ReviewBundleError(str(exc)) from exc
    scanned_index = {
        (record.candidate_id, record.source_document_id): record for record in scanned
    }
    documents: list[dict[str, object]] = []
    for key in sorted(manifest_index):
        request = request_index[key]
        manifest = manifest_index[key]
        record = scanned_index[key]
        if (
            request.get("schema_version")
            != "legalforecast.disclosure_review_request.v1"
        ):
            raise ReviewBundleError(f"unsupported disclosure review request: {key}")
        if request.get("required_human_decision") != "cleared_or_quarantined":
            raise ReviewBundleError(
                f"review request lacks explicit decision gate: {key}"
            )
        for field in ("sha256", "byte_count", "free_or_purchased"):
            if request.get(field) != manifest.get(field):
                raise ReviewBundleError(f"review request {field} mismatch: {key}")
        relevant_restrictions = [
            row for row in restriction_evidence if _key(row) == key
        ]
        documents.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "sha256": record.sha256,
                "byte_count": record.byte_count,
                "free_or_purchased": record.free_or_purchased,
                "restriction_status": record.restriction_status,
                "restriction_evidence_count": len(relevant_restrictions),
                "restriction_evidence_sha256": hashlib.sha256(
                    canonical_json_bytes(relevant_restrictions)
                ).hexdigest(),
                "restriction_evidence": list(record.restriction_evidence),
                "automated_markers": list(record.automated_markers),
                "required_human_decision": "cleared_or_quarantined",
            }
        )
    document_set_sha256 = hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    return {
        "schema_version": WORKSHEET_SCHEMA_VERSION,
        "disclosure_authority": _disclosure_authority_binding(disclosure_authority),
        "source_sha256": {
            "review_requests": hashlib.sha256(review_requests_bytes).hexdigest(),
            "download_manifest": hashlib.sha256(download_manifest_bytes).hexdigest(),
            "restriction_evidence": hashlib.sha256(
                restriction_evidence_bytes
            ).hexdigest(),
        },
        "document_set_sha256": document_set_sha256,
        "document_count": len(documents),
        "documents": documents,
    }


def build_review_artifact(
    worksheet: Mapping[str, object],
    decisions: Sequence[Mapping[str, object]],
    *,
    reviewer_id: str,
    controlled_store_uri: str,
) -> bytes:
    """Turn complete explicit decisions into exact clear-disclosures JSONL."""

    documents = _worksheet_documents(worksheet)
    decision_index = _unique_index(decisions, "review decision")
    document_keys = {_key(row) for row in documents}
    if set(decision_index) != document_keys:
        missing = sorted(document_keys - set(decision_index))
        extra = sorted(set(decision_index) - document_keys)
        raise ReviewBundleError(
            f"review decision coverage mismatch; missing={missing}; extra={extra}"
        )
    reviewer_id = _nonempty(reviewer_id, "reviewer_id")
    _require_private_store_uri(controlled_store_uri)
    rows: list[dict[str, object]] = []
    for document in documents:
        key = _key(document)
        decision = decision_index[key]
        if _required_string(decision, "intended_reviewer_id") != reviewer_id:
            raise ReviewBundleError(f"review decision has the wrong reviewer: {key}")
        status = _required_string(decision, "status")
        if status not in {"cleared", "quarantined"}:
            raise ReviewBundleError(f"invalid explicit review decision: {key}")
        reviewed_at = _required_string(decision, "reviewed_at")
        _parse_timestamp(reviewed_at, "reviewed_at")
        inspected_at = _required_string(decision, "inspected_at")
        _parse_timestamp(inspected_at, "inspected_at")
        if _digest(decision, "inspected_sha256") != _digest(document, "sha256"):
            raise ReviewBundleError(f"review decision inspected the wrong bytes: {key}")
        raw_markers = document.get("automated_markers")
        if not isinstance(raw_markers, list):
            raise ReviewBundleError(f"worksheet has invalid marker categories: {key}")
        markers = cast(list[object], raw_markers)
        if not all(isinstance(item, str) and item for item in markers):
            raise ReviewBundleError(f"worksheet has invalid marker categories: {key}")
        restriction_status = _required_string(document, "restriction_status")
        if status == "cleared" and (
            markers or restriction_status not in _PUBLIC_RESTRICTIONS
        ):
            raise ReviewBundleError(
                f"flagged or non-public document cannot be cleared: {key}"
            )
        rows.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "sha256": _digest(document, "sha256"),
                "status": status,
                "reviewer_id": reviewer_id,
                "controlled_store_provenance": controlled_store_uri,
                "reviewed_at": reviewed_at,
                "inspected_at": inspected_at,
                "inspected_sha256": _digest(document, "sha256"),
            }
        )
    return b"".join(canonical_json_bytes(row) for row in rows)


def build_private_inspection_map(
    worksheet: Mapping[str, object],
    download_manifest: Sequence[Mapping[str, object]],
    *,
    document_root: Path,
) -> bytes:
    """Map signed document hashes to exact local bytes for private human review.

    This artifact contains paths and therefore belongs only in the controlled
    private review store.  Neither it nor its paths are embedded in the signed
    receipt, packet inputs, or public run cards.
    """

    documents = _worksheet_documents(worksheet)
    manifest = _unique_index(download_manifest, "download manifest")
    if set(manifest) != {_key(row) for row in documents}:
        raise ReviewBundleError("private inspection map manifest coverage mismatch")
    root = document_root.resolve()
    rows: list[dict[str, object]] = []
    for document in documents:
        key = _key(document)
        raw_path = _required_string(manifest[key], "local_path")
        relative = Path(raw_path)
        if relative.is_absolute():
            raise ReviewBundleError(f"inspection path must be relative: {key}")
        path = root / relative
        if ".." in relative.parts:
            raise ReviewBundleError(f"inspection path is unsafe: {key}")
        try:
            data = read_unique_regular_file(path)
        except ReviewBundleError as exc:
            raise ReviewBundleError(f"inspection path cannot be read: {key}") from exc
        if hashlib.sha256(data).hexdigest() != _digest(document, "sha256"):
            raise ReviewBundleError(f"inspection bytes changed: {key}")
        rows.append(
            {
                "candidate_id": key[0],
                "source_document_id": key[1],
                "inspection_path": str(path.absolute()),
                "sha256": _digest(document, "sha256"),
                "byte_count": len(data),
            }
        )
    return b"".join(canonical_json_bytes(row) for row in rows)


def build_signing_statement(
    review_artifact: bytes,
    decision_artifact: bytes,
    worksheet_bytes: bytes,
    worksheet: Mapping[str, object],
    *,
    reviewer_policy: Mapping[str, object],
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    controlled_store_uri: str,
    authenticated_at: str,
) -> dict[str, object]:
    """Build the canonical statement an external reviewer identity must sign."""

    policy = _parse_policy(reviewer_policy, reviewer_policy_bytes)
    _validate_disclosure_authority(disclosure_authority, policy)
    _validate_worksheet_disclosure_authority(worksheet, disclosure_authority)
    _validate_store_uri(controlled_store_uri, policy)
    _parse_timestamp(authenticated_at, "authenticated_at")
    documents = _worksheet_documents(worksheet)
    sources = _mapping(worksheet.get("source_sha256"), "worksheet source_sha256")
    decision_summary = _decision_artifact_summary(
        decision_artifact, review_artifact=review_artifact, policy=policy
    )
    statement: dict[str, object] = {
        "schema_version": STATEMENT_SCHEMA_VERSION,
        "review_artifact_sha256": hashlib.sha256(review_artifact).hexdigest(),
        "decision_artifact_sha256": hashlib.sha256(decision_artifact).hexdigest(),
        "decision_confirmation_sha256": decision_summary["confirmation_sha256"],
        "worksheet_sha256": hashlib.sha256(worksheet_bytes).hexdigest(),
        "review_requests_sha256": _digest(sources, "review_requests"),
        "download_manifest_sha256": _digest(sources, "download_manifest"),
        "restriction_evidence_sha256": _digest(sources, "restriction_evidence"),
        "document_set_sha256": _digest(worksheet, "document_set_sha256"),
        "document_count": len(documents),
        "cleared_count": decision_summary["cleared_count"],
        "quarantined_count": decision_summary["quarantined_count"],
        "decision_summary": _review_decision_summary(review_artifact),
        "cycle_id": disclosure_authority.identity.cycle_id,
        "cohort_policy_sha256": disclosure_authority.identity.cohort_policy_sha256,
        "eligibility_anchor": (
            disclosure_authority.identity.eligibility_anchor.isoformat()
        ),
        "disclosure_authority_sha256": disclosure_authority.authority_sha256,
        "ssh_public_key_fingerprint": (disclosure_authority.ssh_public_key_fingerprint),
        "authenticated_reviewer_id": policy.reviewer_id,
        "controlled_store_uri": controlled_store_uri,
        "authentication_method": policy.authentication_method,
        "authenticated_at": authenticated_at,
        "reviewer_policy_sha256": policy.sha256,
        "signature_namespace": policy.signature_namespace,
    }
    _validate_review_artifact_semantics(
        review_artifact,
        worksheet,
        policy=policy,
        authenticated_at=authenticated_at,
    )
    return statement


def reviewer_policy_preflight(
    reviewer_policy_bytes: bytes,
    *,
    expected_reviewer_policy_sha256: str,
    allow_test_service_identity: bool = False,
) -> ReviewerPolicy:
    """Validate the policy pin and report absent human hardware without key data."""

    policy = _parse_policy_bytes(
        reviewer_policy_bytes,
        expected_reviewer_policy_sha256=expected_reviewer_policy_sha256,
    )
    if policy.identity_kind == "human_hardware" and (
        policy.ssh_key_type not in _HUMAN_KEY_TYPES
    ):
        raise ReviewBundleError(
            "human disclosure review requires an allowlisted hardware-backed sk-* "
            f"SSH signer; none is configured (see {HARDWARE_SIGNER_BEAD})"
        )
    if policy.identity_kind == "controlled_store_service" and not (
        allow_test_service_identity
    ):
        raise ReviewBundleError(
            "controlled-store service signing is not production-authorized until an "
            "external precommitted authority is deployed; use the human hardware "
            f"signer tracked by {HARDWARE_SIGNER_BEAD}"
        )
    return policy


def _validate_disclosure_authority(
    authority: DisclosureReviewAuthority, policy: ReviewerPolicy
) -> None:
    if (
        authority.reviewer_id != policy.reviewer_id
        or authority.reviewer_policy_sha256 != policy.sha256
        or authority.signature_namespace != policy.signature_namespace
        or authority.controlled_store_uri_prefix != policy.controlled_store_uri_prefix
        or authority.ssh_key_type != policy.ssh_key_type
        or authority.ssh_public_key != f"{policy.ssh_key_type} {policy.ssh_key_data}"
    ):
        raise ReviewBundleError("reviewer policy differs from disclosure authority")


def _disclosure_authority_binding(
    authority: DisclosureReviewAuthority,
) -> dict[str, str]:
    return {
        "cycle_id": authority.identity.cycle_id,
        "cohort_policy_sha256": authority.identity.cohort_policy_sha256,
        "eligibility_anchor": authority.identity.eligibility_anchor.isoformat(),
        "disclosure_authority_sha256": authority.authority_sha256,
        "reviewer_id": authority.reviewer_id,
        "reviewer_policy_sha256": authority.reviewer_policy_sha256,
        "ssh_public_key_fingerprint": authority.ssh_public_key_fingerprint,
    }


def _validate_worksheet_disclosure_authority(
    worksheet: Mapping[str, object], authority: DisclosureReviewAuthority
) -> None:
    binding = worksheet.get("disclosure_authority")
    if not isinstance(binding, Mapping) or dict(
        cast(Mapping[str, object], binding)
    ) != _disclosure_authority_binding(authority):
        raise ReviewBundleError("review worksheet disclosure authority mismatch")


def seal_review_receipt(
    review_artifact: bytes,
    decision_artifact: bytes,
    worksheet_bytes: bytes,
    worksheet: Mapping[str, object],
    statement: Mapping[str, object],
    signature: bytes,
    *,
    reviewer_policy: Mapping[str, object],
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> dict[str, object]:
    """Verify an external SSHSIG and emit a self-contained signed receipt."""

    policy = reviewer_policy_preflight(
        reviewer_policy_bytes,
        expected_reviewer_policy_sha256=disclosure_authority.reviewer_policy_sha256,
        allow_test_service_identity=allow_test_service_identity,
    )
    parsed_policy = _parse_policy(reviewer_policy, reviewer_policy_bytes)
    if parsed_policy != policy:
        raise ReviewBundleError("reviewer policy bytes do not match parsed policy")
    _validate_statement(
        statement,
        review_artifact=review_artifact,
        decision_artifact=decision_artifact,
        worksheet_bytes=worksheet_bytes,
        worksheet=worksheet,
        policy=policy,
        disclosure_authority=disclosure_authority,
    )
    _validate_worksheet_disclosure_authority(worksheet, disclosure_authority)
    _require_json_object_bytes_match(worksheet, worksheet_bytes, "review worksheet")
    _validate_review_artifact_semantics(
        review_artifact,
        worksheet,
        policy=policy,
        authenticated_at=_required_string(statement, "authenticated_at"),
    )
    _validate_source_bytes(
        statement,
        review_requests_bytes=review_requests_bytes,
        download_manifest_bytes=download_manifest_bytes,
        restriction_evidence_bytes=restriction_evidence_bytes,
    )
    _verify_sshsig(canonical_json_bytes(dict(statement)), signature, policy)
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "statement": dict(statement),
        "sshsig_base64": base64.b64encode(signature).decode("ascii"),
        "decision_artifact_base64": base64.b64encode(decision_artifact).decode("ascii"),
    }


def verify_review_receipt(
    review_artifact: bytes,
    receipt: Mapping[str, object],
    *,
    reviewer_policy_bytes: bytes,
    disclosure_authority: DisclosureReviewAuthority,
    worksheet_bytes: bytes,
    worksheet: Mapping[str, object],
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
    allow_test_service_identity: bool = False,
) -> VerifiedReviewAuthority:
    """Independently verify a receipt against an explicit external policy pin."""

    if frozenset(receipt) != _RECEIPT_FIELDS:
        raise ReviewBundleError("signed disclosure review receipt has extra fields")
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise ReviewBundleError("unsupported signed disclosure review receipt schema")
    policy = reviewer_policy_preflight(
        reviewer_policy_bytes,
        expected_reviewer_policy_sha256=disclosure_authority.reviewer_policy_sha256,
        allow_test_service_identity=allow_test_service_identity,
    )
    statement = _mapping(receipt.get("statement"), "receipt statement")
    decision_artifact = _receipt_decision_artifact(receipt)
    _validate_statement(
        statement,
        review_artifact=review_artifact,
        decision_artifact=decision_artifact,
        worksheet_bytes=worksheet_bytes,
        worksheet=worksheet,
        policy=policy,
        disclosure_authority=disclosure_authority,
    )
    _validate_worksheet_disclosure_authority(worksheet, disclosure_authority)
    _require_json_object_bytes_match(worksheet, worksheet_bytes, "review worksheet")
    _validate_review_artifact_semantics(
        review_artifact,
        worksheet,
        policy=policy,
        authenticated_at=_required_string(statement, "authenticated_at"),
    )
    _validate_source_bytes(
        statement,
        review_requests_bytes=review_requests_bytes,
        download_manifest_bytes=download_manifest_bytes,
        restriction_evidence_bytes=restriction_evidence_bytes,
    )
    _verify_sshsig(
        canonical_json_bytes(dict(statement)), _receipt_signature(receipt), policy
    )
    return _verified_authority(review_artifact, statement, policy)


def _validate_source_bytes(
    statement: Mapping[str, object],
    *,
    review_requests_bytes: bytes,
    download_manifest_bytes: bytes,
    restriction_evidence_bytes: bytes,
) -> None:
    exact_sources = {
        "review_requests_sha256": hashlib.sha256(review_requests_bytes).hexdigest(),
        "download_manifest_sha256": hashlib.sha256(download_manifest_bytes).hexdigest(),
        "restriction_evidence_sha256": hashlib.sha256(
            restriction_evidence_bytes
        ).hexdigest(),
    }
    for field, expected in exact_sources.items():
        if _digest(statement, field) != expected:
            raise ReviewBundleError(f"signed review input lineage mismatch: {field}")


def _validate_review_artifact_semantics(
    review_artifact: bytes,
    worksheet: Mapping[str, object],
    *,
    policy: ReviewerPolicy,
    authenticated_at: str,
) -> None:
    rows = _parse_canonical_jsonl(review_artifact, "review artifact")
    documents = _worksheet_documents(worksheet)
    review_index = _unique_index(rows, "review artifact")
    document_index = {_key(row): row for row in documents}
    if set(review_index) != set(document_index):
        raise ReviewBundleError("review artifact coverage differs from worksheet")
    authenticated = _parse_timestamp(authenticated_at, "authenticated_at")
    if authenticated > datetime.now(UTC) + timedelta(minutes=5):
        raise ReviewBundleError("authenticated_at is implausibly in the future")
    allowed_fields = {
        "candidate_id",
        "source_document_id",
        "sha256",
        "status",
        "reviewer_id",
        "controlled_store_provenance",
        "reviewed_at",
        "inspected_at",
        "inspected_sha256",
    }
    for key in sorted(document_index):
        row = review_index[key]
        document = document_index[key]
        if set(row) != allowed_fields:
            raise ReviewBundleError(f"review artifact has non-canonical fields: {key}")
        digest = _digest(document, "sha256")
        if (
            _digest(row, "sha256") != digest
            or _digest(row, "inspected_sha256") != digest
        ):
            raise ReviewBundleError(f"review artifact document hash mismatch: {key}")
        if _required_string(row, "reviewer_id") != policy.reviewer_id:
            raise ReviewBundleError(f"review artifact has the wrong reviewer: {key}")
        provenance = _required_string(row, "controlled_store_provenance")
        _validate_store_uri(provenance, policy)
        status = _required_string(row, "status")
        if status not in {"cleared", "quarantined"}:
            raise ReviewBundleError(f"review artifact has invalid decision: {key}")
        markers = cast(list[object], document.get("automated_markers"))
        restriction = _required_string(document, "restriction_status")
        if status == "cleared" and (markers or restriction not in _PUBLIC_RESTRICTIONS):
            raise ReviewBundleError(f"review artifact clears a flagged document: {key}")
        inspected = _parse_timestamp(
            _required_string(row, "inspected_at"), "inspected_at"
        )
        reviewed = _parse_timestamp(_required_string(row, "reviewed_at"), "reviewed_at")
        if inspected > reviewed or reviewed > authenticated:
            raise ReviewBundleError(
                "review timestamps must satisfy inspected <= reviewed <= "
                f"authenticated: {key}"
            )


def _receipt_signature(receipt: Mapping[str, object]) -> bytes:
    raw_signature = receipt.get("sshsig_base64")
    if not isinstance(raw_signature, str) or not raw_signature:
        raise ReviewBundleError("receipt lacks SSHSIG authentication evidence")
    try:
        return base64.b64decode(raw_signature, validate=True)
    except (ValueError, TypeError) as exc:
        raise ReviewBundleError("receipt has malformed SSHSIG evidence") from exc


def _receipt_decision_artifact(receipt: Mapping[str, object]) -> bytes:
    raw_artifact = receipt.get("decision_artifact_base64")
    if not isinstance(raw_artifact, str) or not raw_artifact:
        raise ReviewBundleError("receipt lacks canonical decision artifact")
    try:
        return base64.b64decode(raw_artifact, validate=True)
    except (ValueError, TypeError) as exc:
        raise ReviewBundleError("receipt has malformed decision artifact") from exc


def _verified_authority(
    review_artifact: bytes,
    statement: Mapping[str, object],
    policy: ReviewerPolicy,
) -> VerifiedReviewAuthority:
    return VerifiedReviewAuthority(
        reviewer_id=policy.reviewer_id,
        controlled_store_uri=_required_string(statement, "controlled_store_uri"),
        authentication_method=policy.authentication_method,
        authenticated_at=_required_string(statement, "authenticated_at"),
        review_artifact_sha256=hashlib.sha256(review_artifact).hexdigest(),
        reviewer_policy_sha256=policy.sha256,
    )


def _validate_statement(
    statement: Mapping[str, object],
    *,
    review_artifact: bytes,
    decision_artifact: bytes,
    worksheet_bytes: bytes | None,
    worksheet: Mapping[str, object] | None,
    policy: ReviewerPolicy,
    disclosure_authority: DisclosureReviewAuthority,
) -> None:
    if frozenset(statement) != _STATEMENT_FIELDS:
        raise ReviewBundleError("signed disclosure review statement has extra fields")
    if statement.get("schema_version") != STATEMENT_SCHEMA_VERSION:
        raise ReviewBundleError("unsupported disclosure review statement schema")
    if (
        _digest(statement, "review_artifact_sha256")
        != hashlib.sha256(review_artifact).hexdigest()
    ):
        raise ReviewBundleError("review receipt artifact hash mismatch")
    if (
        _digest(statement, "decision_artifact_sha256")
        != hashlib.sha256(decision_artifact).hexdigest()
    ):
        raise ReviewBundleError("review receipt decision artifact hash mismatch")
    if (
        worksheet_bytes is not None
        and _digest(statement, "worksheet_sha256")
        != hashlib.sha256(worksheet_bytes).hexdigest()
    ):
        raise ReviewBundleError("review statement worksheet hash mismatch")
    for field in (
        "worksheet_sha256",
        "review_requests_sha256",
        "download_manifest_sha256",
        "restriction_evidence_sha256",
        "document_set_sha256",
        "reviewer_policy_sha256",
        "decision_artifact_sha256",
        "decision_confirmation_sha256",
        "cohort_policy_sha256",
        "disclosure_authority_sha256",
    ):
        _digest(statement, field)
    if _digest(statement, "reviewer_policy_sha256") != policy.sha256:
        raise ReviewBundleError("review statement policy pin mismatch")
    _validate_disclosure_authority(disclosure_authority, policy)
    if (
        _required_string(statement, "cycle_id")
        != disclosure_authority.identity.cycle_id
        or _digest(statement, "cohort_policy_sha256")
        != disclosure_authority.identity.cohort_policy_sha256
        or _required_string(statement, "eligibility_anchor")
        != disclosure_authority.identity.eligibility_anchor.isoformat()
        or _digest(statement, "disclosure_authority_sha256")
        != disclosure_authority.authority_sha256
        or _required_string(statement, "ssh_public_key_fingerprint")
        != disclosure_authority.ssh_public_key_fingerprint
    ):
        raise ReviewBundleError("signed statement disclosure authority mismatch")
    if _required_string(statement, "authenticated_reviewer_id") != policy.reviewer_id:
        raise ReviewBundleError("signed statement has the wrong reviewer")
    if (
        _required_string(statement, "authentication_method")
        != policy.authentication_method
    ):
        raise ReviewBundleError("signed statement has the wrong authentication method")
    if _required_string(statement, "signature_namespace") != policy.signature_namespace:
        raise ReviewBundleError("signed statement has the wrong signature namespace")
    _validate_store_uri(_required_string(statement, "controlled_store_uri"), policy)
    _parse_timestamp(
        _required_string(statement, "authenticated_at"), "authenticated_at"
    )
    count = statement.get("document_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ReviewBundleError("signed statement has invalid document_count")
    if worksheet is not None:
        documents = _worksheet_documents(worksheet)
        if count != len(documents):
            raise ReviewBundleError("signed statement document_count mismatch")
        if _digest(statement, "document_set_sha256") != _digest(
            worksheet, "document_set_sha256"
        ):
            raise ReviewBundleError("signed statement document set mismatch")
    if statement.get("decision_summary") != _review_decision_summary(review_artifact):
        raise ReviewBundleError("signed statement decision summary mismatch")
    decision_summary = _decision_artifact_summary(
        decision_artifact, review_artifact=review_artifact, policy=policy
    )
    if (
        statement.get("decision_confirmation_sha256")
        != decision_summary["confirmation_sha256"]
        or statement.get("cleared_count") != decision_summary["cleared_count"]
        or statement.get("quarantined_count") != decision_summary["quarantined_count"]
    ):
        raise ReviewBundleError("signed statement decision commitment mismatch")


def _review_decision_summary(review_artifact: bytes) -> dict[str, object]:
    rows = _parse_canonical_jsonl(review_artifact, "review artifact")
    decisions = [
        {
            "candidate_id": _required_string(row, "candidate_id"),
            "source_document_id": _required_string(row, "source_document_id"),
            "sha256": _digest(row, "sha256"),
            "status": _required_string(row, "status"),
        }
        for row in rows
    ]
    cleared = sum(row["status"] == "cleared" for row in decisions)
    return {
        "document_count": len(decisions),
        "cleared_count": cleared,
        "quarantined_count": len(decisions) - cleared,
        "decisions": decisions,
    }


def _decision_artifact_summary(
    decision_artifact: bytes,
    *,
    review_artifact: bytes,
    policy: ReviewerPolicy,
) -> dict[str, object]:
    decisions = _parse_canonical_jsonl(decision_artifact, "decision artifact")
    reviews = _parse_canonical_jsonl(review_artifact, "review artifact")
    decision_index = _unique_index(decisions, "decision artifact")
    review_index = _unique_index(reviews, "review artifact")
    if list(decision_index) != list(review_index):
        raise ReviewBundleError("decision artifact order or coverage differs")
    fields = {
        "candidate_id",
        "source_document_id",
        "status",
        "reviewed_at",
        "inspected_at",
        "inspected_sha256",
        "recording_method",
        "intended_reviewer_id",
        "batch_confirmation_sha256",
    }
    base_rows: list[dict[str, object]] = []
    pins: set[str] = set()
    for key, decision in decision_index.items():
        review = review_index[key]
        if set(decision) != fields:
            raise ReviewBundleError(f"decision artifact has extra fields: {key}")
        if (
            _required_string(decision, "recording_method") != "interactive_review_cli"
            or _required_string(decision, "intended_reviewer_id") != policy.reviewer_id
            or _required_string(decision, "status")
            != _required_string(review, "status")
            or _required_string(decision, "reviewed_at")
            != _required_string(review, "reviewed_at")
            or _required_string(decision, "inspected_at")
            != _required_string(review, "inspected_at")
            or _digest(decision, "inspected_sha256")
            != _digest(review, "inspected_sha256")
        ):
            raise ReviewBundleError(f"decision artifact differs from review: {key}")
        pin = _digest(decision, "batch_confirmation_sha256")
        pins.add(pin)
        base_rows.append(
            {
                name: value
                for name, value in decision.items()
                if name != "batch_confirmation_sha256"
            }
        )
    expected = hashlib.sha256(
        b"".join(canonical_json_bytes(row) for row in base_rows)
    ).hexdigest()
    if pins != {expected}:
        raise ReviewBundleError("decision artifact confirmation hash mismatch")
    cleared = sum(row.get("status") == "cleared" for row in decisions)
    return {
        "document_count": len(decisions),
        "cleared_count": cleared,
        "quarantined_count": len(decisions) - cleared,
        "confirmation_sha256": expected,
    }


def _verify_sshsig(payload: bytes, signature: bytes, policy: ReviewerPolicy) -> None:
    if (
        not signature.startswith(b"-----BEGIN SSH SIGNATURE-----\n")
        or len(signature) > 16_384
    ):
        raise ReviewBundleError("receipt has malformed SSHSIG evidence")
    with tempfile.TemporaryDirectory(prefix="legalforecast-review-verify-") as tmp:
        root = Path(tmp)
        allowed = root / "allowed_signers"
        signature_path = root / "review.sig"
        allowed.write_text(
            f"{policy.ssh_principal} {policy.ssh_key_type} {policy.ssh_key_data}\n",
            encoding="utf-8",
        )
        signature_path.write_bytes(signature)
        try:
            result = subprocess.run(
                [
                    str(SSH_KEYGEN),
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed),
                    "-I",
                    policy.ssh_principal,
                    "-n",
                    policy.signature_namespace,
                    "-s",
                    str(signature_path),
                ],
                input=payload,
                capture_output=True,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReviewBundleError("SSHSIG verifier is unavailable") from exc
    if result.returncode != 0:
        raise ReviewBundleError("disclosure review SSHSIG verification failed")


def _parse_policy_bytes(
    policy_bytes: bytes, *, expected_reviewer_policy_sha256: str
) -> ReviewerPolicy:
    expected = _strict_digest(
        expected_reviewer_policy_sha256, "expected reviewer policy pin"
    )
    actual = hashlib.sha256(policy_bytes).hexdigest()
    if expected != actual:
        raise ReviewBundleError("reviewer policy pin mismatch")
    try:
        raw = json.loads(policy_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewBundleError("reviewer policy is not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise ReviewBundleError("reviewer policy must be a JSON object")
    return _parse_policy(cast(dict[str, object], raw), policy_bytes)


def _parse_policy(policy: Mapping[str, object], policy_bytes: bytes) -> ReviewerPolicy:
    required = {
        "schema_version",
        "reviewer_id",
        "ssh_principal",
        "ssh_public_key",
        "identity_kind",
        "controlled_store_uri_prefix",
        "signature_namespace",
    }
    if set(policy) != required or policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ReviewBundleError("unsupported or non-canonical reviewer policy")
    public_key = _required_string(policy, "ssh_public_key").split()
    if len(public_key) < 2:
        raise ReviewBundleError("reviewer policy has malformed SSH public key")
    key_type, key_data = public_key[:2]
    identity_kind = _required_string(policy, "identity_kind")
    if identity_kind == "human_hardware":
        allowed_types = _HUMAN_KEY_TYPES
    elif identity_kind == "controlled_store_service":
        allowed_types = _SERVICE_KEY_TYPES
    else:
        raise ReviewBundleError("reviewer policy has unsupported identity kind")
    if key_type not in allowed_types:
        if identity_kind == "human_hardware":
            raise ReviewBundleError(
                "human disclosure review requires an allowlisted hardware-backed sk-* "
                f"SSH signer; none is configured (see {HARDWARE_SIGNER_BEAD})"
            )
        raise ReviewBundleError("controlled-store policy has unsupported SSH key type")
    try:
        base64.b64decode(key_data, validate=True)
    except ValueError as exc:
        raise ReviewBundleError("reviewer policy has malformed SSH public key") from exc
    namespace = _required_string(policy, "signature_namespace")
    if namespace != SIGNATURE_NAMESPACE:
        raise ReviewBundleError("reviewer policy has unsupported signature namespace")
    prefix = _required_string(policy, "controlled_store_uri_prefix")
    _require_private_store_uri(prefix)
    principal = _required_string(policy, "ssh_principal")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}", principal) is None:
        raise ReviewBundleError("reviewer policy has invalid SSH principal")
    return ReviewerPolicy(
        reviewer_id=_required_string(policy, "reviewer_id"),
        ssh_principal=principal,
        ssh_key_type=key_type,
        ssh_key_data=key_data,
        identity_kind=identity_kind,
        controlled_store_uri_prefix=prefix,
        signature_namespace=namespace,
        sha256=hashlib.sha256(policy_bytes).hexdigest(),
    )


def _worksheet_documents(worksheet: Mapping[str, object]) -> list[Mapping[str, object]]:
    if worksheet.get("schema_version") != WORKSHEET_SCHEMA_VERSION:
        raise ReviewBundleError("unsupported disclosure review worksheet schema")
    raw = worksheet.get("documents")
    if not isinstance(raw, list) or not raw:
        raise ReviewBundleError("review worksheet has no documents")
    documents: list[Mapping[str, object]] = []
    for item in cast(list[object], raw):
        if not isinstance(item, Mapping):
            raise ReviewBundleError("review worksheet contains an invalid document")
        documents.append(cast(Mapping[str, object], item))
    count = worksheet.get("document_count")
    if count != len(documents):
        raise ReviewBundleError("review worksheet document count mismatch")
    if (
        _digest(worksheet, "document_set_sha256")
        != hashlib.sha256(canonical_json_bytes(documents)).hexdigest()
    ):
        raise ReviewBundleError("review worksheet document-set hash mismatch")
    _unique_index(documents, "worksheet document")
    return documents


def _unique_index(
    records: Sequence[Mapping[str, object]], label: str
) -> dict[tuple[str, str], Mapping[str, object]]:
    output: dict[tuple[str, str], Mapping[str, object]] = {}
    for record in records:
        key = _key(record)
        if key in output:
            raise ReviewBundleError(f"duplicate {label} key: {key}")
        output[key] = record
    return output


def _key(record: Mapping[str, object]) -> tuple[str, str]:
    return (
        _required_string(record, "candidate_id"),
        _required_string(record, "source_document_id"),
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ReviewBundleError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _required_string(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ReviewBundleError(f"{field} must be a non-empty string")
    return value.strip()


def _nonempty(value: str, field: str) -> str:
    if not value.strip():
        raise ReviewBundleError(f"{field} must be a non-empty string")
    return value.strip()


def _strict_digest(value: str, label: str) -> str:
    value = value.removeprefix("sha256:")
    if _SHA256.fullmatch(value) is None:
        raise ReviewBundleError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _digest(record: Mapping[str, object], field: str) -> str:
    return _strict_digest(_required_string(record, field), field)


def _require_private_store_uri(value: str) -> None:
    parsed = urlsplit(value)
    segments = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if (
        parsed.scheme != "private-store"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or "//" in parsed.path
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ReviewBundleError(
            "review bundle requires controlled private-store provenance"
        )


def _validate_store_uri(value: str, policy: ReviewerPolicy) -> None:
    _require_private_store_uri(value)
    prefix = policy.controlled_store_uri_prefix.rstrip("/")
    if value != prefix and not value.startswith(prefix + "/"):
        raise ReviewBundleError(
            "review bundle URI is outside the controlled store policy"
        )


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewBundleError(f"{label} must be an RFC 3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReviewBundleError(f"{label} must include a UTC offset")
    return parsed.astimezone(UTC)


def _require_jsonl_records_match(
    records: Sequence[Mapping[str, object]], raw_bytes: bytes, label: str
) -> None:
    try:
        text = raw_bytes.decode("utf-8")
        parsed: list[object] = [
            json.loads(line) for line in text.splitlines() if line.strip()
        ]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewBundleError(f"{label} bytes are not valid UTF-8 JSONL") from exc
    expected = [dict(row) for row in records]
    if parsed != expected:
        raise ReviewBundleError(
            f"{label} records do not exactly match the supplied JSONL bytes/order"
        )


def _parse_canonical_jsonl(raw_bytes: bytes, label: str) -> list[Mapping[str, object]]:
    if not raw_bytes or not raw_bytes.endswith(b"\n"):
        raise ReviewBundleError(f"{label} must be newline-terminated canonical JSONL")
    rows: list[Mapping[str, object]] = []
    for raw_line in raw_bytes.splitlines(keepends=True):
        if not raw_line.strip():
            raise ReviewBundleError(f"{label} contains a blank line")
        try:
            parsed = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReviewBundleError(f"{label} is not valid UTF-8 JSONL") from exc
        if not isinstance(parsed, dict):
            raise ReviewBundleError(f"{label} row must be an object")
        row = cast(dict[str, object], parsed)
        if canonical_json_bytes(row) != raw_line:
            raise ReviewBundleError(f"{label} is not canonical JSONL")
        rows.append(row)
    return rows


def _require_json_object_bytes_match(
    parsed: Mapping[str, object], raw_bytes: bytes, label: str
) -> None:
    try:
        raw = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewBundleError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or raw != dict(parsed):
        raise ReviewBundleError(f"{label} bytes differ from parsed artifact")
    if canonical_json_bytes(dict(parsed)) != raw_bytes:
        raise ReviewBundleError(f"{label} is not canonical JSON")


__all__ = [
    "HARDWARE_SIGNER_BEAD",
    "POLICY_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_VERSION",
    "SIGNATURE_NAMESPACE",
    "WORKSHEET_SCHEMA_VERSION",
    "ReviewBundleError",
    "VerifiedReviewAuthority",
    "build_private_inspection_map",
    "build_review_artifact",
    "build_signing_statement",
    "canonical_json_bytes",
    "prepare_review_worksheet",
    "reviewer_policy_preflight",
    "seal_review_receipt",
    "verify_review_receipt",
]

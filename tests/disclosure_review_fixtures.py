from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import TypedDict, cast

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthority,
    DisclosureReviewAuthorityIdentity,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    build_signing_statement,
    canonical_json_bytes,
    seal_review_receipt,
)


class SignedReviewLineage(TypedDict):
    reviews: list[dict[str, object]]
    reviews_bytes: bytes
    decision_artifact_bytes: bytes
    review_receipt: dict[str, object]
    review_receipt_bytes: bytes
    review_requests_bytes: bytes
    review_worksheet: dict[str, object]
    review_worksheet_bytes: bytes
    reviewer_policy_bytes: bytes
    reviewer_policy_sha256: str
    download_manifest_bytes: bytes
    disclosure_authority: DisclosureReviewAuthority


class ServiceReviewSigner(TypedDict):
    """Test-only signing identity split from review artifact construction."""

    private_key: Ed25519PrivateKey
    reviewer_policy: dict[str, object]
    reviewer_policy_bytes: bytes
    disclosure_authority: DisclosureReviewAuthority


def service_review_signer(
    *,
    reviewer_id: str,
    controlled_store_uri: str,
    identity: DisclosureReviewAuthorityIdentity | None = None,
) -> ServiceReviewSigner:
    """Create a cryptographically real test signer before worksheet preparation."""

    private_key = Ed25519PrivateKey.generate()
    public_key = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        )
        .decode()
    )
    uri_parts = controlled_store_uri.split("/")
    controlled_prefix = "/".join(uri_parts[:-1]) + "/"
    policy: dict[str, object] = {
        "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
        "reviewer_id": reviewer_id,
        "ssh_principal": "legalforecast-test-controlled-store",
        "ssh_public_key": public_key,
        "identity_kind": "controlled_store_service",
        "controlled_store_uri_prefix": controlled_prefix,
        "signature_namespace": "legalforecast-disclosure-review-v1",
    }
    policy_bytes = canonical_json_bytes(policy)
    disclosure_authority = service_disclosure_authority_from_policy_bytes(
        policy_bytes, identity=identity
    )
    return {
        "private_key": private_key,
        "reviewer_policy": policy,
        "reviewer_policy_bytes": policy_bytes,
        "disclosure_authority": disclosure_authority,
    }


def service_disclosure_authority_from_policy_bytes(
    policy_bytes: bytes,
    *,
    identity: DisclosureReviewAuthorityIdentity | None = None,
) -> DisclosureReviewAuthority:
    """Reconstruct the deterministic typed authority for test policy bytes."""

    raw_policy = json.loads(policy_bytes)
    if not isinstance(raw_policy, dict):
        raise AssertionError("fixture reviewer policy must be an object")
    policy = cast(dict[str, object], raw_policy)
    public_key = str(policy["ssh_public_key"])
    authority = DisclosureReviewAuthority(
        identity=DisclosureReviewAuthorityIdentity(
            cycle_id="test-cycle",
            cohort_policy_sha256="a" * 64,
            eligibility_anchor=date(2026, 6, 30),
        ),
        reviewer_id=str(policy["reviewer_id"]),
        identity_kind="human_hardware",
        ssh_key_type=public_key.split(" ", 1)[0],
        ssh_public_key=public_key,
        ssh_public_key_fingerprint="SHA256:test-fixture",
        reviewer_policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        signature_namespace="legalforecast-disclosure-review-v1",
        controlled_store_uri_prefix=str(policy["controlled_store_uri_prefix"]),
        authority_sha256="b" * 64,
    )
    return authority if identity is None else replace(authority, identity=identity)


def signed_service_review_lineage(
    reviews: Sequence[Mapping[str, object]],
    *,
    restriction_evidence_bytes: bytes,
    download_manifest_bytes: bytes | None = None,
    review_requests_bytes: bytes | None = None,
    worksheet: Mapping[str, object] | None = None,
    signer: ServiceReviewSigner | None = None,
    authenticated_at: str,
) -> SignedReviewLineage:
    """Build a cryptographically real service receipt for test fixtures only."""

    normalized_reviews: list[dict[str, object]] = []
    documents: list[dict[str, object]] = []
    for review in reviews:
        digest = str(review["sha256"])
        reviewed_at = str(review["reviewed_at"])
        normalized_reviews.append(
            {
                "candidate_id": review["candidate_id"],
                "source_document_id": review["source_document_id"],
                "sha256": digest,
                "status": review["status"],
                "reviewer_id": review["reviewer_id"],
                "controlled_store_provenance": review["controlled_store_provenance"],
                "reviewed_at": reviewed_at,
                "inspected_at": review.get("inspected_at", reviewed_at),
                "inspected_sha256": digest,
            }
        )
        raw_byte_count = review.get("byte_count", 100)
        if isinstance(raw_byte_count, bool) or not isinstance(raw_byte_count, int):
            raise AssertionError("fixture byte_count must be an integer")
        raw_markers = review.get("automated_markers", [])
        if not isinstance(raw_markers, Sequence) or isinstance(
            raw_markers, (str, bytes)
        ):
            raise AssertionError("fixture automated_markers must be a sequence")
        documents.append(
            {
                "candidate_id": review["candidate_id"],
                "source_document_id": review["source_document_id"],
                "sha256": digest,
                "byte_count": raw_byte_count,
                "free_or_purchased": str(review.get("free_or_purchased", "purchased")),
                "restriction_status": str(review.get("restriction_status", "public")),
                "restriction_evidence_count": 1,
                "restriction_evidence_sha256": hashlib.sha256(
                    restriction_evidence_bytes
                ).hexdigest(),
                "restriction_evidence": list(
                    cast(
                        Sequence[object],
                        review.get(
                            "restriction_evidence",
                            ["fresh_post_recovery_public_detail"],
                        ),
                    )
                ),
                "automated_markers": list(cast(Sequence[object], raw_markers)),
                "required_human_decision": "cleared_or_quarantined",
            }
        )
    normalized_reviews.sort(
        key=lambda row: (str(row["candidate_id"]), str(row["source_document_id"]))
    )
    documents.sort(
        key=lambda row: (str(row["candidate_id"]), str(row["source_document_id"]))
    )
    if download_manifest_bytes is None:
        download_manifest_bytes = _jsonl_bytes(
            [
                {
                    "candidate_id": row["candidate_id"],
                    "source_document_id": row["source_document_id"],
                    "sha256": row["sha256"],
                    "byte_count": row["byte_count"],
                    "free_or_purchased": row["free_or_purchased"],
                    "local_path": (
                        f"{row['candidate_id']}/{row['source_document_id']}.pdf"
                    ),
                }
                for row in documents
            ]
        )
    if review_requests_bytes is None:
        review_requests_bytes = _jsonl_bytes(
            [
                {
                    "schema_version": "legalforecast.disclosure_review_request.v1",
                    "candidate_id": row["candidate_id"],
                    "source_document_id": row["source_document_id"],
                    "sha256": row["sha256"],
                    "byte_count": row["byte_count"],
                    "free_or_purchased": row["free_or_purchased"],
                    "required_human_decision": "cleared_or_quarantined",
                }
                for row in documents
            ]
        )
    review_bytes = _jsonl_bytes(normalized_reviews)
    decision_bases = [
        {
            "candidate_id": row["candidate_id"],
            "source_document_id": row["source_document_id"],
            "status": row["status"],
            "reviewed_at": row["reviewed_at"],
            "inspected_at": row["inspected_at"],
            "inspected_sha256": row["inspected_sha256"],
            "recording_method": "interactive_review_cli",
            "intended_reviewer_id": row["reviewer_id"],
        }
        for row in normalized_reviews
    ]
    confirmation = hashlib.sha256(_jsonl_bytes(decision_bases)).hexdigest()
    decision_bytes = _jsonl_bytes(
        [{**row, "batch_confirmation_sha256": confirmation} for row in decision_bases]
    )
    reviewer_id = str(normalized_reviews[0]["reviewer_id"])
    controlled_store_uri = str(normalized_reviews[0]["controlled_store_provenance"])
    if signer is None:
        signer = service_review_signer(
            reviewer_id=reviewer_id,
            controlled_store_uri=controlled_store_uri,
        )
    policy = signer["reviewer_policy"]
    policy_bytes = signer["reviewer_policy_bytes"]
    policy_pin = hashlib.sha256(policy_bytes).hexdigest()
    disclosure_authority = signer["disclosure_authority"]
    if (
        disclosure_authority.reviewer_id != reviewer_id
        or not controlled_store_uri.startswith(
            disclosure_authority.controlled_store_uri_prefix
        )
    ):
        raise AssertionError("fixture signer differs from review identity")
    authority_binding = {
        "cycle_id": disclosure_authority.identity.cycle_id,
        "cohort_policy_sha256": (disclosure_authority.identity.cohort_policy_sha256),
        "eligibility_anchor": (
            disclosure_authority.identity.eligibility_anchor.isoformat()
        ),
        "disclosure_authority_sha256": disclosure_authority.authority_sha256,
        "reviewer_id": disclosure_authority.reviewer_id,
        "reviewer_policy_sha256": disclosure_authority.reviewer_policy_sha256,
        "ssh_public_key_fingerprint": (disclosure_authority.ssh_public_key_fingerprint),
    }
    if worksheet is None:
        worksheet_record: dict[str, object] = {
            "schema_version": "legalforecast.disclosure_review_worksheet.v1",
            "disclosure_authority": authority_binding,
            "source_sha256": {
                "review_requests": hashlib.sha256(review_requests_bytes).hexdigest(),
                "download_manifest": hashlib.sha256(
                    download_manifest_bytes
                ).hexdigest(),
                "restriction_evidence": hashlib.sha256(
                    restriction_evidence_bytes
                ).hexdigest(),
            },
            "document_set_sha256": hashlib.sha256(
                canonical_json_bytes(documents)
            ).hexdigest(),
            "document_count": len(documents),
            "documents": documents,
        }
    else:
        worksheet_record = dict(worksheet)
        existing_binding = worksheet_record.get("disclosure_authority")
        if existing_binding is not None and existing_binding != authority_binding:
            raise AssertionError("fixture worksheet disclosure authority differs")
        worksheet_record["disclosure_authority"] = authority_binding
    worksheet_bytes = canonical_json_bytes(worksheet_record)
    statement = build_signing_statement(
        review_bytes,
        decision_bytes,
        worksheet_bytes,
        worksheet_record,
        reviewer_policy=policy,
        reviewer_policy_bytes=policy_bytes,
        disclosure_authority=disclosure_authority,
        controlled_store_uri=controlled_store_uri,
        authenticated_at=authenticated_at,
    )
    with tempfile.TemporaryDirectory(prefix="legalforecast-test-review-") as tmp:
        root = Path(tmp)
        key_path = root / "review-key"
        statement_path = root / "statement.json"
        key_path.write_bytes(
            signer["private_key"].private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.OpenSSH,
                serialization.NoEncryption(),
            )
        )
        key_path.chmod(0o600)
        statement_path.write_bytes(canonical_json_bytes(statement))
        subprocess.run(
            [
                "/usr/bin/ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(key_path),
                "-n",
                "legalforecast-disclosure-review-v1",
                str(statement_path),
            ],
            check=True,
            capture_output=True,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
        signature = statement_path.with_suffix(".json.sig").read_bytes()
    receipt = seal_review_receipt(
        review_bytes,
        decision_bytes,
        worksheet_bytes,
        worksheet_record,
        statement,
        signature,
        reviewer_policy=policy,
        reviewer_policy_bytes=policy_bytes,
        disclosure_authority=disclosure_authority,
        review_requests_bytes=review_requests_bytes,
        download_manifest_bytes=download_manifest_bytes,
        restriction_evidence_bytes=restriction_evidence_bytes,
        allow_test_service_identity=True,
    )
    return {
        "reviews": normalized_reviews,
        "reviews_bytes": review_bytes,
        "decision_artifact_bytes": decision_bytes,
        "review_receipt": receipt,
        "review_receipt_bytes": canonical_json_bytes(receipt),
        "review_requests_bytes": review_requests_bytes,
        "review_worksheet": worksheet_record,
        "review_worksheet_bytes": worksheet_bytes,
        "reviewer_policy_bytes": policy_bytes,
        "reviewer_policy_sha256": policy_pin,
        "download_manifest_bytes": download_manifest_bytes,
        "disclosure_authority": disclosure_authority,
    }


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_json_bytes(dict(record)) for record in records)

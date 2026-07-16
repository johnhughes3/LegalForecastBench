from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from legalforecast.ingestion.disclosure_review_authority import (
    DisclosureReviewAuthority,
    DisclosureReviewAuthorityIdentity,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    build_review_artifact,
    build_signing_statement,
    canonical_json_bytes,
    prepare_review_worksheet,
    reviewer_policy_preflight,
    seal_review_receipt,
    verify_review_receipt,
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _fixture_inputs(
    tmp_path: Path,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    Path,
]:
    root = tmp_path / "documents"
    path = root / "cand-1" / "doc-1.pdf"
    path.parent.mkdir(parents=True)
    content = (
        b"%PDF-1.4\n/Type /Page\n<< >>\nstream\n"
        b"BT (Public motion memorandum) Tj ET\nendstream"
    )
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    manifest = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "doc-1",
            "local_path": "cand-1/doc-1.pdf",
            "sha256": digest,
            "byte_count": len(content),
            "free_or_purchased": "free",
        }
    ]
    restrictions = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "doc-1",
            "restriction_status": "public",
            "restriction_evidence": "courtlistener-public-docket",
        }
    ]
    requests = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": "cand-1",
            "source_document_id": "doc-1",
            "sha256": digest,
            "byte_count": len(content),
            "free_or_purchased": "free",
            "restriction_status": "public",
            "restriction_evidence": "courtlistener-public-docket",
            "required_human_decision": "cleared_or_quarantined",
        }
    ]
    return requests, manifest, restrictions, root


def _service_policy(tmp_path: Path) -> tuple[dict[str, object], bytes, Path]:
    key = tmp_path / "review-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        check=True,
    )
    public_key = key.with_suffix(".pub").read_text().strip()
    policy = {
        "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
        "reviewer_id": "reviewer:controlled-store-test",
        "ssh_principal": "legalforecast-controlled-store-test",
        "ssh_public_key": public_key,
        "identity_kind": "controlled_store_service",
        "controlled_store_uri_prefix": "private-store://cycle-1/reviews/",
        "signature_namespace": "legalforecast-disclosure-review-v1",
    }
    return policy, _json_bytes(policy), key


def _authority(
    policy: dict[str, object], policy_bytes: bytes
) -> DisclosureReviewAuthority:
    public_key = " ".join(str(policy["ssh_public_key"]).split()[:2])
    return DisclosureReviewAuthority(
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
        signature_namespace=str(policy["signature_namespace"]),
        controlled_store_uri_prefix=str(policy["controlled_store_uri_prefix"]),
        authority_sha256="b" * 64,
    )


def _signed_bundle(
    tmp_path: Path,
) -> tuple[bytes, dict[str, object], bytes, bytes, tuple[bytes, bytes, bytes]]:
    requests, manifest, restrictions, root = _fixture_inputs(tmp_path)
    request_bytes = _json_bytes(requests[0])
    manifest_bytes = _json_bytes(manifest[0])
    restriction_bytes = _json_bytes(restrictions[0])
    policy, policy_bytes, key = _service_policy(tmp_path)
    disclosure_authority = _authority(policy, policy_bytes)
    worksheet = prepare_review_worksheet(
        requests,
        manifest,
        restrictions,
        document_root=root,
        review_requests_bytes=request_bytes,
        download_manifest_bytes=manifest_bytes,
        restriction_evidence_bytes=restriction_bytes,
        disclosure_authority=disclosure_authority,
    )
    worksheet_bytes = _json_bytes(worksheet)
    decisions = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "doc-1",
            "status": "cleared",
            "reviewed_at": "2026-07-16T02:00:00Z",
            "inspected_at": "2026-07-16T01:59:00Z",
            "inspected_sha256": worksheet["documents"][0]["sha256"],
            "recording_method": "interactive_review_cli",
            "intended_reviewer_id": policy["reviewer_id"],
        }
    ]
    decision_base_bytes = _json_bytes(decisions[0])
    confirmation = hashlib.sha256(decision_base_bytes).hexdigest()
    decisions[0]["batch_confirmation_sha256"] = confirmation
    decision_bytes = _json_bytes(decisions[0])
    review_bytes = build_review_artifact(
        worksheet,
        decisions,
        reviewer_id=str(policy["reviewer_id"]),
        controlled_store_uri="private-store://cycle-1/reviews/batch-001",
    )
    statement = build_signing_statement(
        review_bytes,
        decision_bytes,
        worksheet_bytes,
        worksheet,
        reviewer_policy=policy,
        reviewer_policy_bytes=policy_bytes,
        disclosure_authority=disclosure_authority,
        controlled_store_uri="private-store://cycle-1/reviews/batch-001",
        authenticated_at="2026-07-16T02:05:00Z",
    )
    statement_path = tmp_path / "statement.json"
    statement_path.write_bytes(_json_bytes(statement))
    subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(key),
            "-n",
            str(policy["signature_namespace"]),
            str(statement_path),
        ],
        check=True,
        capture_output=True,
    )
    signature = statement_path.with_suffix(".json.sig").read_bytes()
    receipt = seal_review_receipt(
        review_bytes,
        decision_bytes,
        worksheet_bytes,
        worksheet,
        statement,
        signature,
        reviewer_policy=policy,
        reviewer_policy_bytes=policy_bytes,
        disclosure_authority=disclosure_authority,
        review_requests_bytes=request_bytes,
        download_manifest_bytes=manifest_bytes,
        restriction_evidence_bytes=restriction_bytes,
        allow_test_service_identity=True,
    )
    return (
        review_bytes,
        receipt,
        policy_bytes,
        worksheet_bytes,
        (request_bytes, manifest_bytes, restriction_bytes),
    )


def test_prepare_is_deterministic_and_never_emits_matched_values(
    tmp_path: Path,
) -> None:
    requests, manifest, restrictions, root = _fixture_inputs(tmp_path)
    policy, policy_bytes, _key_path = _service_policy(tmp_path)
    kwargs = {
        "document_root": root,
        "review_requests_bytes": _json_bytes(requests[0]),
        "download_manifest_bytes": _json_bytes(manifest[0]),
        "restriction_evidence_bytes": _json_bytes(restrictions[0]),
        "disclosure_authority": _authority(policy, policy_bytes),
    }
    first = prepare_review_worksheet(requests, manifest, restrictions, **kwargs)
    second = prepare_review_worksheet(requests, manifest, restrictions, **kwargs)
    assert first == second
    rendered = json.dumps(first)
    assert "Public motion memorandum" not in rendered
    assert first["documents"][0]["automated_markers"] == []


def test_partial_and_flagged_clear_decisions_fail_closed(tmp_path: Path) -> None:
    requests, manifest, restrictions, root = _fixture_inputs(tmp_path)
    policy, policy_bytes, _key_path = _service_policy(tmp_path)
    worksheet = prepare_review_worksheet(
        requests,
        manifest,
        restrictions,
        document_root=root,
        review_requests_bytes=_json_bytes(requests[0]),
        download_manifest_bytes=_json_bytes(manifest[0]),
        restriction_evidence_bytes=_json_bytes(restrictions[0]),
        disclosure_authority=_authority(policy, policy_bytes),
    )
    with pytest.raises(ReviewBundleError, match="coverage"):
        build_review_artifact(
            worksheet,
            [],
            reviewer_id="reviewer:john",
            controlled_store_uri="private-store://cycle-1/reviews/batch-001",
        )
    worksheet["documents"][0]["automated_markers"] = ["ssn"]
    worksheet["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes(worksheet["documents"])
    ).hexdigest()
    with pytest.raises(ReviewBundleError, match="flagged"):
        build_review_artifact(
            worksheet,
            [
                {
                    "candidate_id": "cand-1",
                    "source_document_id": "doc-1",
                    "status": "cleared",
                    "reviewed_at": "2026-07-16T02:00:00Z",
                    "inspected_at": "2026-07-16T01:59:00Z",
                    "inspected_sha256": worksheet["documents"][0]["sha256"],
                    "intended_reviewer_id": "reviewer:john",
                }
            ],
            reviewer_id="reviewer:john",
            controlled_store_uri="private-store://cycle-1/reviews/batch-001",
        )


def test_receipt_verification_rejects_tamper_substitution_and_wrong_pin(
    tmp_path: Path,
) -> None:
    (
        review_bytes,
        receipt,
        policy_bytes,
        worksheet_bytes,
        source_bytes,
    ) = _signed_bundle(tmp_path)
    request_bytes, manifest_bytes, restriction_bytes = source_bytes
    authority = verify_review_receipt(
        review_bytes,
        receipt,
        reviewer_policy_bytes=policy_bytes,
        disclosure_authority=_authority(json.loads(policy_bytes), policy_bytes),
        worksheet_bytes=worksheet_bytes,
        worksheet=json.loads(worksheet_bytes),
        review_requests_bytes=request_bytes,
        download_manifest_bytes=manifest_bytes,
        restriction_evidence_bytes=restriction_bytes,
        allow_test_service_identity=True,
    )
    assert authority.reviewer_id == "reviewer:controlled-store-test"
    signed_statement = receipt["statement"]
    assert isinstance(signed_statement, dict)
    assert signed_statement["cleared_count"] == 1
    assert signed_statement["quarantined_count"] == 0
    assert len(signed_statement["decision_artifact_sha256"]) == 64
    with pytest.raises(ReviewBundleError, match="artifact hash"):
        verify_review_receipt(
            review_bytes + b"tampered",
            receipt,
            reviewer_policy_bytes=policy_bytes,
            disclosure_authority=_authority(json.loads(policy_bytes), policy_bytes),
            worksheet_bytes=worksheet_bytes,
            worksheet=json.loads(worksheet_bytes),
            review_requests_bytes=request_bytes,
            download_manifest_bytes=manifest_bytes,
            restriction_evidence_bytes=restriction_bytes,
            allow_test_service_identity=True,
        )
    forged = json.loads(json.dumps(receipt))
    forged["statement"]["authenticated_reviewer_id"] = "reviewer:john"
    with pytest.raises(ReviewBundleError, match=r"signature|reviewer"):
        verify_review_receipt(
            review_bytes,
            forged,
            reviewer_policy_bytes=policy_bytes,
            disclosure_authority=_authority(json.loads(policy_bytes), policy_bytes),
            worksheet_bytes=worksheet_bytes,
            worksheet=json.loads(worksheet_bytes),
            review_requests_bytes=request_bytes,
            download_manifest_bytes=manifest_bytes,
            restriction_evidence_bytes=restriction_bytes,
            allow_test_service_identity=True,
        )
    decision_tamper = json.loads(json.dumps(receipt))
    decision_tamper["decision_artifact_base64"] = "AAAA"
    with pytest.raises(ReviewBundleError, match="decision artifact hash"):
        verify_review_receipt(
            review_bytes,
            decision_tamper,
            reviewer_policy_bytes=policy_bytes,
            disclosure_authority=_authority(json.loads(policy_bytes), policy_bytes),
            worksheet_bytes=worksheet_bytes,
            worksheet=json.loads(worksheet_bytes),
            review_requests_bytes=request_bytes,
            download_manifest_bytes=manifest_bytes,
            restriction_evidence_bytes=restriction_bytes,
            allow_test_service_identity=True,
        )
    wrong_authority = replace(
        _authority(json.loads(policy_bytes), policy_bytes),
        reviewer_policy_sha256="0" * 64,
    )
    with pytest.raises(ReviewBundleError, match="policy pin"):
        verify_review_receipt(
            review_bytes,
            receipt,
            reviewer_policy_bytes=policy_bytes,
            disclosure_authority=wrong_authority,
            worksheet_bytes=worksheet_bytes,
            worksheet=json.loads(worksheet_bytes),
            review_requests_bytes=request_bytes,
            download_manifest_bytes=manifest_bytes,
            restriction_evidence_bytes=restriction_bytes,
            allow_test_service_identity=True,
        )


def test_human_policy_requires_hardware_backed_key_without_exposing_key() -> None:
    policy = {
        "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
        "reviewer_id": "reviewer:john",
        "ssh_principal": "john",
        "ssh_public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture",
        "identity_kind": "human_hardware",
        "controlled_store_uri_prefix": "private-store://cycle-1/reviews/",
        "signature_namespace": "legalforecast-disclosure-review-v1",
    }
    policy_bytes = _json_bytes(policy)
    with pytest.raises(ReviewBundleError, match=r"5qd6\.39\.7\.1") as exc:
        reviewer_policy_preflight(
            policy_bytes,
            expected_reviewer_policy_sha256=hashlib.sha256(policy_bytes).hexdigest(),
        )
    assert "AAAAC3" not in str(exc.value)

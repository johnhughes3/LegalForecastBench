from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.disclosure_clearance import (
    PDF_SCAN_SCHEMA_VERSION_V1,
    DisclosurePdfScan,
    require_clearance_policy,
)
from legalforecast.ingestion.disclosure_model_review import DECISION_SCHEMA_VERSION
from legalforecast.ingestion.provenance_clearance import (
    ProvenanceClearanceError,
    build_authenticated_model_provenance_clearance_records_v3,
    build_provenance_clearance_plan,
    build_provenance_clearance_plan_v3,
    build_provenance_clearance_records,
    build_provider_free_quarantine_records_v3,
    canonical_json_bytes,
    exception_review_worksheet_v3,
    validate_exception_review_worksheet_v3,
)
from tests.recovered_public_capability_helpers import (
    issue_recovered_public_capability,
)

PUBLIC_EVIDENCE = ["courtlistener_public_download_record_checked"]


def _jsonl(rows: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_json_bytes(row) for row in rows)


def _fixture(
    tmp_path: Path,
) -> tuple[
    Path,
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    root = tmp_path / "documents"
    root.mkdir()
    data = b"exact model-review fixture bytes"
    relative = "case-a/entry-1.pdf"
    (root / "case-a").mkdir()
    (root / relative).write_bytes(data)
    manifest: list[dict[str, object]] = [
        {
            "candidate_id": "case-a",
            "source_document_id": "entry-1",
            "local_path": relative,
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_count": len(data),
            "free_or_purchased": "free",
            "source_provider": "courtlistener",
            "source_url": "https://storage.courtlistener.com/recap/a.pdf",
        }
    ]
    restrictions: list[dict[str, object]] = [
        {
            "candidate_id": "case-a",
            "source_document_id": "entry-1",
            "restriction_status": "public",
            "restriction_evidence": PUBLIC_EVIDENCE,
            "is_sealed": None,
            "is_private": None,
        }
    ]
    requests: list[dict[str, object]] = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": "case-a",
            "source_document_id": "entry-1",
            "sha256": manifest[0]["sha256"],
            "byte_count": len(data),
            "free_or_purchased": "free",
            "restriction_status": "public",
            "restriction_evidence": PUBLIC_EVIDENCE,
            "required_human_decision": "cleared_or_quarantined",
        }
    ]
    relevance: list[dict[str, object]] = [
        {
            "candidate_id": "case-a",
            "documents": [
                {
                    "source_document_id": "entry-1",
                    "source_url_or_reference": manifest[0]["source_url"],
                    "model_visible": False,
                    "contains_target_outcome": True,
                }
            ],
        }
    ]
    return root, requests, manifest, restrictions, relevance


def _plan(tmp_path: Path) -> dict[str, object]:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    scan = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=("medical",),
    )
    return build_provenance_clearance_plan_v3(
        requests,
        manifest,
        restrictions,
        relevance,
        document_root=root,
        review_requests_bytes=_jsonl(requests),
        download_manifest_bytes=_jsonl(manifest),
        restriction_evidence_bytes=_jsonl(restrictions),
        case_relevance_bytes=_jsonl(relevance),
        document_scanner=lambda _: scan,
    )


def test_v3_plan_rejects_mixed_scanner_versions(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    documents = cast(list[dict[str, object]], plan["documents"])
    second = deepcopy(documents[0])
    second["candidate_id"] = "case-b"
    second["source_document_id"] = "entry-2"
    second["local_path"] = "case-b/entry-2.pdf"
    scan = cast(dict[str, object], second["disclosure_pdf_scan"])
    scan["schema_version"] = PDF_SCAN_SCHEMA_VERSION_V1
    scan["method"] = "pypdf_page_text_v1"
    documents.append(second)
    plan["document_count"] = 2
    plan["exception_review_count"] = 2
    plan["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes(documents)
    ).hexdigest()

    with pytest.raises(ProvenanceClearanceError, match="mixed PDF scanner versions"):
        exception_review_worksheet_v3(plan)


def test_empty_v3_plan_builds_empty_worksheet(tmp_path: Path) -> None:
    plan = build_provenance_clearance_plan_v3(
        [],
        [],
        [],
        [],
        document_root=tmp_path,
        review_requests_bytes=b"",
        download_manifest_bytes=b"",
        restriction_evidence_bytes=b"",
        case_relevance_bytes=b"",
    )

    assert exception_review_worksheet_v3(plan)["documents"] == []


def test_v3_plan_and_worksheet_use_generic_vocabulary_and_exact_binding(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)

    rows = validate_exception_review_worksheet_v3(
        worksheet,
        routing_plan=plan,
        routing_plan_bytes=canonical_json_bytes(plan),
        worksheet_bytes=canonical_json_bytes(worksheet),
    )

    assert plan["exception_review_count"] == 1
    assert "john_review_count" not in plan
    assert rows[0]["route"] == "exception_review"
    assert rows[0]["exception_clearance_permitted"] is True
    assert "human_clearance_permitted" not in rows[0]


def test_v3_provider_free_finalizer_quarantines_every_exception(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    routing_sha256 = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()

    records = build_provider_free_quarantine_records_v3(
        plan, routing_plan_sha256=routing_sha256
    )

    assert [record.status for record in records] == ["quarantined"]
    assert [record.clearance_basis for record in records] == [
        "provider_free_exception_quarantine"
    ]
    assert records[0].reviewer_id is None
    assert records[0].reviewed_at is None
    assert records[0].controlled_store_provenance is None
    assert records[0].routing_plan_sha256 == routing_sha256


def test_v3_provider_free_finalizer_rejects_v2_and_wrong_hash(
    tmp_path: Path,
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    v3_root = tmp_path / "v3"
    v3_root.mkdir()
    plan_v3 = _plan(v3_root)
    plan_v2 = build_provenance_clearance_plan(
        requests,
        manifest,
        restrictions,
        relevance,
        document_root=root,
        review_requests_bytes=_jsonl(requests),
        download_manifest_bytes=_jsonl(manifest),
        restriction_evidence_bytes=_jsonl(restrictions),
        case_relevance_bytes=_jsonl(relevance),
        document_scanner=lambda _: DisclosurePdfScan(
            parsed_page_count=1,
            text_scanned_page_numbers=(1,),
            ocr_scanned_page_numbers=(),
            unscanned_page_numbers=(),
            coverage_status="complete",
            diagnostics=(),
            automated_markers=("medical",),
        ),
    )

    with pytest.raises(ProvenanceClearanceError, match="unsupported"):
        build_provider_free_quarantine_records_v3(
            plan_v2,
            routing_plan_sha256=hashlib.sha256(
                canonical_json_bytes(plan_v2)
            ).hexdigest(),
        )
    with pytest.raises(ProvenanceClearanceError, match="routing plan hash"):
        build_provider_free_quarantine_records_v3(plan_v3, routing_plan_sha256="0" * 64)


def test_v3_recovered_public_requires_verifier_capability_and_exact_closed_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    fresh_sha = "2" * 64
    operation_key = "00000000-0000-4000-8000-000000000000"
    manifest[0].update(
        {
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
            "purchase_operation_key": operation_key,
            "fresh_recap_detail_sha256": fresh_sha,
        }
    )
    manifest[0].pop("source_url")
    requests[0]["free_or_purchased"] = "purchased"
    restrictions[0].update(
        {
            "schema_version": "legalforecast.post_recovery_restriction_evidence.v1",
            "source_provider": "courtlistener_recap_fetch_fresh_detail",
            "fresh_recap_detail_sha256": fresh_sha,
            "is_available": True,
            "is_sealed": False,
            "is_private": None,
            "redaction_or_seal_status": "public",
            "restriction_status": "public",
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_false",
                "courtlistener_recap_fetch_no_positive_private_marker",
            ],
        }
    )
    requests[0]["restriction_status"] = "public"
    requests[0]["restriction_evidence"] = restrictions[0]["restriction_evidence"]
    relevance[0]["documents"][0]["source_url_or_reference"] = "recap-document:entry-1"
    scan = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=(),
    )
    kwargs = {
        "document_root": root,
        "review_requests_bytes": _jsonl(requests),
        "download_manifest_bytes": _jsonl(manifest),
        "restriction_evidence_bytes": _jsonl(restrictions),
        "case_relevance_bytes": _jsonl(relevance),
        "document_scanner": lambda _: scan,
    }
    with pytest.raises(ProvenanceClearanceError, match="verifier-issued"):
        build_provenance_clearance_plan_v3(
            requests, manifest, restrictions, relevance, **kwargs
        )
    explicit_null_manifest = deepcopy(manifest)
    explicit_null_manifest[0]["source_url"] = None
    with pytest.raises(ProvenanceClearanceError, match="must omit source_url"):
        build_provenance_clearance_plan_v3(
            requests,
            explicit_null_manifest,
            restrictions,
            relevance,
            **{
                **kwargs,
                "download_manifest_bytes": _jsonl(explicit_null_manifest),
            },
        )
    empty_capability = issue_recovered_public_capability(monkeypatch, [])
    with pytest.raises(ProvenanceClearanceError, match="must omit source_url"):
        build_provenance_clearance_plan_v3(
            requests,
            explicit_null_manifest,
            restrictions,
            relevance,
            **{
                **kwargs,
                "download_manifest_bytes": _jsonl(explicit_null_manifest),
            },
            verified_recovery_capability=empty_capability,
        )
    with pytest.raises(ProvenanceClearanceError, match="verifier-issued capability"):
        build_provenance_clearance_plan_v3(
            requests,
            manifest,
            restrictions,
            relevance,
            **kwargs,
            verified_recovery_capability=object(),
        )

    lineage = {
        "candidate_id": "case-a",
        "source_document_id": "entry-1",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": hashlib.sha256(_jsonl(manifest)).hexdigest(),
        "recovery_restriction_evidence_sha256": hashlib.sha256(
            _jsonl(restrictions)
        ).hexdigest(),
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": "7" * 64,
        "purchase_operation_key": operation_key,
        "fresh_recap_detail_sha256": fresh_sha,
    }
    capability = issue_recovered_public_capability(monkeypatch, [lineage])
    plan = build_provenance_clearance_plan_v3(
        requests,
        manifest,
        restrictions,
        relevance,
        **kwargs,
        verified_recovery_capability=capability,
    )
    document = cast(list[dict[str, object]], plan["documents"])[0]
    assert document["route"] == "auto_clear"
    assert document["recovered_public_lineage"] == lineage
    records = build_provider_free_quarantine_records_v3(
        plan,
        routing_plan_sha256=hashlib.sha256(canonical_json_bytes(plan)).hexdigest(),
    )
    assert records[0].clearance_basis == "provider_free_recovered_public"
    assert records[0].reviewer_id is None
    assert records[0].controlled_store_provenance == (
        "courtlistener-rest://recap-documents/entry-1"
    )

    for field, value, expected in (
        ("source_provider", "courtlistener_recap_fetch", "does not prove"),
        ("source_provider", "other", "does not prove"),
        ("source_url", None, "must omit source_url"),
        (
            "source_url",
            "https://storage.courtlistener.com/recap/a.pdf",
            "coverage",
        ),
        (
            "purchase_operation_key",
            "11111111-1111-4111-8111-111111111111",
            "does not prove",
        ),
        ("fresh_recap_detail_sha256", "9" * 64, "does not prove"),
    ):
        changed_manifest = deepcopy(manifest)
        changed_manifest[0][field] = value
        changed_kwargs = {
            **kwargs,
            "download_manifest_bytes": _jsonl(changed_manifest),
        }
        with pytest.raises(ProvenanceClearanceError, match=expected):
            build_provenance_clearance_plan_v3(
                requests,
                changed_manifest,
                restrictions,
                relevance,
                **changed_kwargs,
                verified_recovery_capability=capability,
            )

    document_path = root / cast(str, manifest[0]["local_path"])
    original_document_bytes = document_path.read_bytes()
    changed_data = b"different authenticated document bytes"
    document_path.write_bytes(changed_data)
    changed_manifest = deepcopy(manifest)
    changed_manifest[0]["sha256"] = hashlib.sha256(changed_data).hexdigest()
    changed_manifest[0]["byte_count"] = len(changed_data)
    changed_requests = deepcopy(requests)
    changed_requests[0]["sha256"] = changed_manifest[0]["sha256"]
    changed_requests[0]["byte_count"] = changed_manifest[0]["byte_count"]
    with pytest.raises(ProvenanceClearanceError, match="does not prove"):
        build_provenance_clearance_plan_v3(
            changed_requests,
            changed_manifest,
            restrictions,
            relevance,
            **{
                **kwargs,
                "review_requests_bytes": _jsonl(changed_requests),
                "download_manifest_bytes": _jsonl(changed_manifest),
            },
            verified_recovery_capability=capability,
        )
    document_path.write_bytes(original_document_bytes)

    changed_restrictions = deepcopy(restrictions)
    changed_restrictions[0]["schema_version"] = "tampered"
    with pytest.raises(ProvenanceClearanceError, match="does not prove"):
        build_provenance_clearance_plan_v3(
            requests,
            manifest,
            changed_restrictions,
            relevance,
            **{
                **kwargs,
                "restriction_evidence_bytes": _jsonl(changed_restrictions),
            },
            verified_recovery_capability=capability,
        )


def test_v3_recovered_public_requires_exact_capability_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    manifest[0].update(
        {
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
        }
    )
    manifest[0].pop("source_url")
    capability = issue_recovered_public_capability(monkeypatch, [])

    with pytest.raises(ProvenanceClearanceError, match="coverage"):
        build_provenance_clearance_plan_v3(
            requests,
            manifest,
            restrictions,
            relevance,
            document_root=root,
            review_requests_bytes=_jsonl(requests),
            download_manifest_bytes=_jsonl(manifest),
            restriction_evidence_bytes=_jsonl(restrictions),
            case_relevance_bytes=_jsonl(relevance),
            verified_recovery_capability=capability,
        )


def test_v3_mixed_manifest_preserves_legacy_row_and_scopes_recovery_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    recovered_data = b"recovered document bytes"
    recovered_relative = "case-a/entry-2.pdf"
    (root / recovered_relative).write_bytes(recovered_data)
    fresh_sha = "2" * 64
    operation_key = "00000000-0000-4000-8000-000000000000"
    manifest.append(
        {
            "candidate_id": "case-a",
            "source_document_id": "entry-2",
            "local_path": recovered_relative,
            "sha256": hashlib.sha256(recovered_data).hexdigest(),
            "byte_count": len(recovered_data),
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
            "purchase_operation_key": operation_key,
            "fresh_recap_detail_sha256": fresh_sha,
        }
    )
    recovered_evidence = [
        "courtlistener_recap_fetch_fresh_detail_exact_match",
        "courtlistener_recap_fetch_is_available_true",
        "courtlistener_recap_fetch_is_sealed_false",
        "courtlistener_recap_fetch_no_positive_private_marker",
    ]
    restrictions.append(
        {
            "candidate_id": "case-a",
            "source_document_id": "entry-2",
            "source_provider": "courtlistener_recap_fetch_fresh_detail",
            "fresh_recap_detail_sha256": fresh_sha,
            "is_available": True,
            "is_sealed": False,
            "is_private": None,
            "redaction_or_seal_status": "public",
            "restriction_status": "public",
            "restriction_evidence": recovered_evidence,
        }
    )
    requests.append(
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": "case-a",
            "source_document_id": "entry-2",
            "sha256": manifest[1]["sha256"],
            "byte_count": len(recovered_data),
            "free_or_purchased": "purchased",
            "restriction_status": "public",
            "restriction_evidence": recovered_evidence,
            "required_human_decision": "cleared_or_quarantined",
        }
    )
    cast(list[dict[str, object]], relevance[0]["documents"]).append(
        {
            "source_document_id": "entry-2",
            "source_url_or_reference": (
                "https://www.courtlistener.com/api/rest/v4/recap-documents/entry-2/"
            ),
            "model_visible": False,
            "contains_target_outcome": True,
        }
    )
    lineage = {
        "candidate_id": "case-a",
        "source_document_id": "entry-2",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": hashlib.sha256(_jsonl(manifest)).hexdigest(),
        "recovery_restriction_evidence_sha256": hashlib.sha256(
            _jsonl(restrictions)
        ).hexdigest(),
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": "7" * 64,
        "purchase_operation_key": operation_key,
        "fresh_recap_detail_sha256": fresh_sha,
    }
    capability = issue_recovered_public_capability(monkeypatch, [lineage])
    scan = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=(),
    )
    kwargs = {
        "document_root": root,
        "review_requests_bytes": _jsonl(requests),
        "download_manifest_bytes": _jsonl(manifest),
        "restriction_evidence_bytes": _jsonl(restrictions),
        "case_relevance_bytes": _jsonl(relevance),
        "document_scanner": lambda _: scan,
    }
    plan = build_provenance_clearance_plan_v3(
        requests,
        manifest,
        restrictions,
        relevance,
        **kwargs,
        verified_recovery_capability=capability,
    )
    legacy, recovered = cast(list[dict[str, object]], plan["documents"])
    assert legacy["route"] == "auto_clear"
    assert legacy["source_url"] == manifest[0]["source_url"]
    assert "recovered_public_lineage" not in legacy
    assert recovered["route"] == "auto_clear"
    assert recovered["recovered_public_lineage"] == lineage

    extra_lineage = {**lineage, "source_document_id": "entry-extra"}
    extra_capability = issue_recovered_public_capability(
        monkeypatch, [lineage, extra_lineage]
    )
    with pytest.raises(ProvenanceClearanceError, match="coverage"):
        build_provenance_clearance_plan_v3(
            requests,
            manifest,
            restrictions,
            relevance,
            **kwargs,
            verified_recovery_capability=extra_capability,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("is_available", False),
        ("is_available", None),
        ("is_sealed", True),
        ("is_sealed", None),
        ("is_private", True),
        ("visibility_model_visible", True),
        ("visibility_contains_target_outcome", False),
        ("scan_coverage_status", "incomplete"),
        ("scan_markers", ("medical",)),
        ("manifest_purchase_operation_key", "11111111-1111-4111-8111-111111111111"),
        ("manifest_fresh_recap_detail_sha256", "9" * 64),
    ),
)
def test_v3_recovered_public_rejects_contradictions_and_routes_scan_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    manifest[0].update(
        {
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
            "purchase_operation_key": "00000000-0000-4000-8000-000000000000",
            "fresh_recap_detail_sha256": "2" * 64,
        }
    )
    manifest[0].pop("source_url")
    requests[0]["free_or_purchased"] = "purchased"
    evidence = [
        "courtlistener_recap_fetch_fresh_detail_exact_match",
        "courtlistener_recap_fetch_is_available_true",
        "courtlistener_recap_fetch_is_sealed_false",
        "courtlistener_recap_fetch_no_positive_private_marker",
    ]
    restrictions[0].update(
        {
            "source_provider": "courtlistener_recap_fetch_fresh_detail",
            "fresh_recap_detail_sha256": "2" * 64,
            "is_available": True,
            "is_sealed": False,
            "is_private": None,
            "redaction_or_seal_status": "public",
            "restriction_evidence": evidence,
            **(
                {field: value}
                if not field.startswith(("visibility_", "scan_", "manifest_"))
                else {}
            ),
        }
    )
    if field.startswith("visibility_"):
        relevance[0]["documents"][0][field.removeprefix("visibility_")] = value
    elif field.startswith("manifest_"):
        manifest[0][field.removeprefix("manifest_")] = value
    requests[0]["restriction_evidence"] = evidence
    lineage = {
        "candidate_id": "case-a",
        "source_document_id": "entry-1",
        "recovery_run_card_sha256": "3" * 64,
        "recovery_manifest_sha256": hashlib.sha256(_jsonl(manifest)).hexdigest(),
        "recovery_restriction_evidence_sha256": hashlib.sha256(
            _jsonl(restrictions)
        ).hexdigest(),
        "purchase_state_sha256": "6" * 64,
        "purchase_operation_sha256": "7" * 64,
        "purchase_operation_key": "00000000-0000-4000-8000-000000000000",
        "fresh_recap_detail_sha256": "2" * 64,
    }
    capability = issue_recovered_public_capability(monkeypatch, [lineage])

    def build() -> dict[str, object]:
        return build_provenance_clearance_plan_v3(
            requests,
            manifest,
            restrictions,
            relevance,
            document_root=root,
            review_requests_bytes=_jsonl(requests),
            download_manifest_bytes=_jsonl(manifest),
            restriction_evidence_bytes=_jsonl(restrictions),
            case_relevance_bytes=_jsonl(relevance),
            document_scanner=lambda _: DisclosurePdfScan(
                parsed_page_count=1,
                text_scanned_page_numbers=(
                    () if field == "scan_coverage_status" else (1,)
                ),
                ocr_scanned_page_numbers=(),
                unscanned_page_numbers=(
                    (1,) if field == "scan_coverage_status" else ()
                ),
                coverage_status=(
                    cast(str, value) if field == "scan_coverage_status" else "complete"
                ),
                diagnostics=(),
                automated_markers=(
                    cast(tuple[str, ...], value) if field == "scan_markers" else ()
                ),
            ),
            verified_recovery_capability=capability,
        )

    if field not in {"scan_coverage_status", "scan_markers"}:
        with pytest.raises(ProvenanceClearanceError, match="does not prove"):
            build()
        return
    plan = build()
    document = cast(list[dict[str, object]], plan["documents"])[0]
    assert document["route"] == "exception_review"
    if field in {"scan_coverage_status", "scan_markers"}:
        assert document["recovered_public_lineage"] == lineage
        assert exception_review_worksheet_v3(plan)["documents"] == [document]
        if field == "scan_markers":
            routing_sha256 = hashlib.sha256(canonical_json_bytes(plan)).hexdigest()
            monkeypatch.setattr(
                "legalforecast.ingestion.disclosure_model_review_authority.public_disclosure_model_review_record",
                lambda _capability: {
                    "routing_plan_sha256": routing_sha256,
                    "reviewer_registry_key": "gemini-3.5-flash",
                    "decision_count": 1,
                    "decisions": [
                        {
                            "schema_version": DECISION_SCHEMA_VERSION,
                            "candidate_id": "case-a",
                            "source_document_id": "entry-1",
                            "document_sha256": document["sha256"],
                            "prompt_sha256": "8" * 64,
                            "batch_prompt_sha256": "9" * 64,
                            "response_sha256": "a" * 64,
                            "batch_response_sha256": "b" * 64,
                            "reviewer_registry_entry_sha256": "c" * 64,
                            "status": "cleared",
                        }
                    ],
                },
            )
            records = build_authenticated_model_provenance_clearance_records_v3(
                plan,
                model_review_capability=object(),
                routing_plan_sha256=routing_sha256,
            )
            record = records[0].to_record()
            assert record["clearance_basis"] == ("authenticated_model_exception_review")
            assert record["recovered_public_lineage"] == lineage
            assert record["controlled_store_provenance"] == (
                "courtlistener-rest://recap-documents/entry-1"
            )
            require_clearance_policy(
                record, key=("case-a", "entry-1"), label="resolved document"
            )


def test_v3_worksheet_does_not_alias_plan_documents(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    plan_before = deepcopy(plan)
    rows = cast(list[dict[str, object]], worksheet["documents"])
    scan = cast(dict[str, object], rows[0]["disclosure_pdf_scan"])

    scan["coverage_status"] = "mutated"

    assert plan == plan_before


def test_v3_worksheet_rejects_cross_plan_replay(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    changed = dict(plan)
    changed["source_sha256"] = {
        **dict(plan["source_sha256"]),  # type: ignore[arg-type]
        "review_requests": "b" * 64,
    }

    with pytest.raises(ProvenanceClearanceError, match="routing plan hash"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=changed,
            routing_plan_bytes=canonical_json_bytes(changed),
            worksheet_bytes=canonical_json_bytes(worksheet),
        )


@pytest.mark.parametrize("artifact", ["routing_plan", "worksheet"])
def test_v3_worksheet_rejects_noncanonical_json_bytes(
    tmp_path: Path, artifact: str
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    plan_bytes = json.dumps(plan, indent=2).encode()
    worksheet_bytes = json.dumps(worksheet, indent=2).encode()

    with pytest.raises(ProvenanceClearanceError, match="differs from exact bytes"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=plan,
            routing_plan_bytes=(
                plan_bytes if artifact == "routing_plan" else canonical_json_bytes(plan)
            ),
            worksheet_bytes=(
                worksheet_bytes
                if artifact == "worksheet"
                else canonical_json_bytes(worksheet)
            ),
        )


@pytest.mark.parametrize(
    ("artifact", "nested"),
    [
        ("routing_plan", False),
        ("routing_plan", True),
        ("worksheet", False),
        ("worksheet", True),
    ],
)
def test_v3_worksheet_rejects_duplicate_json_keys(
    tmp_path: Path, artifact: str, nested: bool
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    target = canonical_json_bytes(plan if artifact == "routing_plan" else worksheet)
    if nested:
        target = target.replace(
            b'"candidate_id":"case-a"',
            b'"candidate_id":"case-a","candidate_id":"case-a"',
            1,
        )
    else:
        target = target.replace(
            b'{"',
            b'{"schema_version":"duplicate","',
            1,
        )

    with pytest.raises(ProvenanceClearanceError, match="duplicate key"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=plan,
            routing_plan_bytes=(
                target if artifact == "routing_plan" else canonical_json_bytes(plan)
            ),
            worksheet_bytes=(
                target if artifact == "worksheet" else canonical_json_bytes(worksheet)
            ),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"extra": True},
        {"source_sha256": {"review_requests": "a" * 64}},
        {
            "source_sha256": {
                "review_requests": "not-a-digest",
                "download_manifest": "a" * 64,
                "restriction_evidence": "a" * 64,
                "case_relevance": "a" * 64,
            }
        },
    ],
)
def test_v3_plan_rejects_open_or_invalid_top_level(
    tmp_path: Path, mutation: dict[str, object]
) -> None:
    plan = {**_plan(tmp_path), **mutation}

    with pytest.raises(ProvenanceClearanceError):
        exception_review_worksheet_v3(plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("document_count", True),
        ("document_count", 1.0),
        ("auto_clear_count", False),
        ("auto_clear_count", "0"),
        ("exception_review_count", True),
        ("exception_review_count", -1),
    ],
)
def test_v3_plan_rejects_non_integer_summary_counts(
    tmp_path: Path, field: str, value: object
) -> None:
    plan = _plan(tmp_path)
    plan[field] = value

    with pytest.raises(ProvenanceClearanceError, match="non-negative integer"):
        exception_review_worksheet_v3(plan)


@pytest.mark.parametrize("document_count", [True, 1.0, "1", -1])
def test_v3_worksheet_rejects_non_integer_document_count(
    tmp_path: Path, document_count: object
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    worksheet["document_count"] = document_count

    with pytest.raises(ProvenanceClearanceError, match="non-negative integer"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=plan,
            routing_plan_bytes=canonical_json_bytes(plan),
            worksheet_bytes=canonical_json_bytes(worksheet),
        )


@pytest.mark.parametrize("artifact", ["routing_plan", "worksheet"])
@pytest.mark.parametrize("field", ["text_scanned_page_count", "ocr_scanned_page_count"])
@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
def test_v3_nested_scan_rejects_non_integer_page_counts(
    tmp_path: Path, artifact: str, field: str, value: object
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    target = deepcopy(plan if artifact == "routing_plan" else worksheet)
    documents = cast(list[dict[str, object]], target["documents"])
    scan = cast(dict[str, object], documents[0]["disclosure_pdf_scan"])
    scan[field] = value

    with pytest.raises(ProvenanceClearanceError, match="non-negative integer"):
        if artifact == "routing_plan":
            exception_review_worksheet_v3(target)
        else:
            validate_exception_review_worksheet_v3(
                target,
                routing_plan=plan,
                routing_plan_bytes=canonical_json_bytes(plan),
                worksheet_bytes=canonical_json_bytes(target),
            )


@pytest.mark.parametrize("artifact", ["routing_plan", "worksheet"])
@pytest.mark.parametrize("value", [True, 1.0, "1", -1])
def test_v3_document_rejects_non_integer_byte_count(
    tmp_path: Path, artifact: str, value: object
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    target = deepcopy(plan if artifact == "routing_plan" else worksheet)
    documents = cast(list[dict[str, object]], target["documents"])
    documents[0]["byte_count"] = value

    with pytest.raises(ProvenanceClearanceError, match="non-negative integer"):
        if artifact == "routing_plan":
            exception_review_worksheet_v3(target)
        else:
            validate_exception_review_worksheet_v3(
                target,
                routing_plan=plan,
                routing_plan_bytes=canonical_json_bytes(plan),
                worksheet_bytes=canonical_json_bytes(target),
            )


@pytest.mark.parametrize("artifact", ["routing_plan", "worksheet"])
@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("sha256", "bad", "lowercase SHA-256"),
        ("local_path", "", "local_path must be a non-empty string"),
        ("local_path", "../escape.pdf", "safe relative POSIX path.*case-a"),
        ("free_or_purchased", "borrowed", "must be free or purchased"),
        ("source_provider", "", "source_provider must be a non-empty string"),
        ("source_url", 0, "source_url must be a non-empty string"),
        (
            "source_url_or_reference",
            "",
            "source_url_or_reference must be a non-empty string",
        ),
        ("restriction_status", 0, "restriction_status must be a non-empty string"),
        ("is_sealed", "false", "restriction is_sealed must be bool or null"),
        ("is_sealed", 0, "restriction is_sealed must be bool or null"),
        ("is_sealed", 1, "restriction is_sealed must be bool or null"),
        ("is_private", 0, "restriction is_private must be bool or null"),
        ("is_private", 1, "restriction is_private must be bool or null"),
        ("is_private", "false", "restriction is_private must be bool or null"),
        ("model_visible", 1, "visibility model_visible must be bool"),
        (
            "contains_target_outcome",
            "false",
            "visibility contains_target_outcome must be bool",
        ),
    ],
)
def test_v3_document_rejects_invalid_identity_and_safety_domains(
    tmp_path: Path, artifact: str, field: str, value: object, match: str
) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)
    target = deepcopy(plan if artifact == "routing_plan" else worksheet)
    documents = cast(list[dict[str, object]], target["documents"])
    documents[0][field] = value
    target["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes(documents)
    ).hexdigest()

    with pytest.raises(ProvenanceClearanceError, match=match):
        if artifact == "routing_plan":
            exception_review_worksheet_v3(target)
        else:
            validate_exception_review_worksheet_v3(
                target,
                routing_plan=plan,
                routing_plan_bytes=canonical_json_bytes(plan),
                worksheet_bytes=canonical_json_bytes(target),
            )


def test_v3_preserves_non_courtlistener_source_as_exception_routed(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    documents = cast(list[dict[str, object]], plan["documents"])
    documents[0]["source_provider"] = "other-public-source"
    documents[0]["route_reasons"] = [
        "affirmative_public_provenance_unproven",
        "automated_marker_present",
    ]
    plan["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes(documents)
    ).hexdigest()

    worksheet = exception_review_worksheet_v3(plan)

    assert worksheet["document_count"] == 1
    rows = cast(list[dict[str, object]], worksheet["documents"])
    assert rows[0]["route"] == "exception_review"


@pytest.mark.parametrize(
    "source_url",
    [
        "https://storage.courtlistener.com:443/recap/a.pdf",
        "https://storage.courtlistener.com:8443/recap/a.pdf",
        "https://storage.courtlistener.com:bad/recap/a.pdf",
        "https://storage.courtlistener.com[/recap/a.pdf",
    ],
)
def test_v2_and_v3_reject_noncanonical_courtlistener_port_as_public(
    tmp_path: Path, source_url: str
) -> None:
    root, requests, manifest, restrictions, relevance = _fixture(tmp_path)
    manifest[0]["source_url"] = source_url
    relevance_documents = cast(list[dict[str, object]], relevance[0]["documents"])
    relevance_documents[0]["source_url_or_reference"] = source_url
    scan = DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=(),
    )
    kwargs = {
        "document_root": root,
        "review_requests_bytes": _jsonl(requests),
        "download_manifest_bytes": _jsonl(manifest),
        "restriction_evidence_bytes": _jsonl(restrictions),
        "case_relevance_bytes": _jsonl(relevance),
        "document_scanner": lambda _: scan,
    }

    v2 = build_provenance_clearance_plan(
        requests,
        manifest,
        restrictions,
        relevance,
        **kwargs,
    )
    v3 = build_provenance_clearance_plan_v3(
        requests,
        manifest,
        restrictions,
        relevance,
        **kwargs,
    )

    v2_document = cast(list[dict[str, object]], v2["documents"])[0]
    v3_document = cast(list[dict[str, object]], v3["documents"])[0]
    assert v2_document["route"] == "john_exception_review"
    assert v3_document["route"] == "exception_review"
    assert v2_document["route_reasons"] == ["affirmative_public_provenance_unproven"]
    assert v3_document["route_reasons"] == ["affirmative_public_provenance_unproven"]


def test_v3_worksheet_rejects_substituted_bytes(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    worksheet = exception_review_worksheet_v3(plan)

    with pytest.raises(ProvenanceClearanceError, match="differs from exact bytes"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=plan,
            routing_plan_bytes=canonical_json_bytes({**plan, "document_count": 0}),
            worksheet_bytes=canonical_json_bytes(worksheet),
        )


def test_v2_constructor_rejects_v3_plan(tmp_path: Path) -> None:
    plan = _plan(tmp_path)

    with pytest.raises(
        ProvenanceClearanceError, match="unsupported provenance routing plan"
    ):
        build_provenance_clearance_records(
            plan,
            [],
            routing_plan_sha256=hashlib.sha256(canonical_json_bytes(plan)).hexdigest(),
        )


def test_v3_worksheet_rejects_valid_auto_clear_document(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan_document = cast(list[dict[str, object]], plan["documents"])[0]
    scan = cast(dict[str, object], plan_document["disclosure_pdf_scan"])
    scan["automated_markers"] = []
    plan_document["automated_markers"] = []
    plan_document["route"] = "auto_clear"
    plan_document["route_reasons"] = []
    plan["auto_clear_count"] = 1
    plan["exception_review_count"] = 0
    plan["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes([plan_document])
    ).hexdigest()
    worksheet = exception_review_worksheet_v3(plan)
    worksheet["documents"] = [deepcopy(plan_document)]
    worksheet["document_count"] = 1
    worksheet["document_set_sha256"] = hashlib.sha256(
        canonical_json_bytes(worksheet["documents"])
    ).hexdigest()

    with pytest.raises(ProvenanceClearanceError, match="auto-clear row"):
        validate_exception_review_worksheet_v3(
            worksheet,
            routing_plan=plan,
            routing_plan_bytes=canonical_json_bytes(plan),
            worksheet_bytes=canonical_json_bytes(worksheet),
        )

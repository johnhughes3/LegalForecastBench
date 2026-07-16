from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
from legalforecast.cli import main
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.packet_input_planner import plan_packet_build_inputs
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.purchased_document_recovery import (
    PurchasedDocumentRecoveryRequest,
    purchased_document_download_manifest_records,
    recover_purchased_documents,
)
from legalforecast.unitization.review import apply_unitization_reviews

JsonRecord = dict[str, Any]


def test_paid_audit_only_decision_reaches_stage_b_but_not_model_packet(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_root = tmp_path / "acquisition"
    document_root = output_root / "documents"
    decision_url = "https://case.dev/download/decision.pdf"
    [recovery] = recover_purchased_documents(
        (
            PurchasedDocumentRecoveryRequest(
                purchase_attempt=CaseDevPacerPurchaseAttempt(
                    candidate_id="cand-1",
                    source_document_id="decision",
                    status=CaseDevPacerPurchaseStatus.PURCHASED,
                    fee_acknowledged=True,
                    pacer_fees={
                        "pacer_fee_usd": "0.00",
                        "service_fee_usd": "3.05",
                        "total_usd": "3.05",
                    },
                    download_url=decision_url,
                ),
                source_case_id="case-1",
                court="S.D.N.Y.",
                docket_number="1:26-cv-00001",
                document_role=DocumentRole.DECISION,
                docket_entry_number=16,
                pre_purchase_evidence={"reason": "first_written_disposition"},
                is_predecision_material=False,
                contains_target_outcome=True,
            ),
        ),
        output_root=document_root,
        source=FixtureFreeDocumentSource({decision_url: b"%PDF paid decision"}),
        retrieved_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    [decision_download] = purchased_document_download_manifest_records((recovery,))
    assert decision_download["recovery_status"] == "recovered_audit_only"
    assert decision_download["parse_purpose"] == "stage_b_labeling"
    assert decision_download["model_visible"] is False
    assert decision_download["packet_membership"] == "not_mounted"

    free_downloads = [
        _free_download(document_root, "complaint", "complaint", 1),
        _free_download(
            document_root,
            "mtd",
            "motion_to_dismiss_notice",
            5,
        ),
    ]
    downloads = [*free_downloads, decision_download]
    download_manifest = tmp_path / "downloads.jsonl"
    _write_jsonl(download_manifest, downloads)
    clearance = tmp_path / "clearance.jsonl"
    _write_jsonl(
        clearance,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "byte_count": row["byte_count"],
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for row in downloads
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(download_manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parse_requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert {record["source_document_id"] for record in parse_requests} == {
        "complaint",
        "mtd",
        "decision",
    }

    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "complaint.md").write_text(
        "Count I alleges a Section 10(b) claim.",
        encoding="utf-8",
    )
    (fixture_markdown / "mtd.md").write_text(
        "Defendant moves to dismiss Count I.",
        encoding="utf-8",
    )
    decision_text = "The motion to dismiss Count I is granted without leave to amend."
    (fixture_markdown / "decision.md").write_text(decision_text, encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(output_root / "parse-document-requests.jsonl"),
                "--disclosure-clearance",
                str(clearance),
                "--output-root",
                str(output_root),
                "--fixture-markdown-dir",
                str(fixture_markdown),
                "--execute",
            ]
        )
        == 0
    )
    parser_manifest = output_root / "mistral-markdown-conversions.jsonl"
    conversions = _read_jsonl(parser_manifest)
    assert any(
        record["source_document_id"] == "decision" and record["status"] == "succeeded"
        for record in conversions
    )

    selection = _selection()
    selection_path = tmp_path / "selection.jsonl"
    units = _prediction_units()
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    evaluated_registry_path = tmp_path / "evaluated-registry.json"
    provider_caps_path = tmp_path / "provider-caps.json"
    _write_jsonl(selection_path, [selection])
    finalized_units = apply_unitization_reviews(
        prediction_unit_records=[units],
        review_records=(),
        adjudication_records=(),
    )
    _write_jsonl(units_path, list(finalized_units))
    registry_path.write_text(json.dumps([_registry_record()]), encoding="utf-8")
    evaluated_record = _registry_record()
    evaluated_record["model_id"] = "gpt-evaluated"
    evaluated_record["model_version_or_snapshot"] = "gpt-evaluated-2026-06-30"
    evaluated_registry_path.write_text(json.dumps([evaluated_record]), encoding="utf-8")
    provider_caps_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "test-cycle",
                "providers": [
                    {
                        "provider": "openai",
                        "cycle_reservation_cap_usd": "10.00",
                        "external_spend_limit_usd": "20.00",
                        "external_limit_scope": "test account",
                        "external_limit_source": "test fixture",
                        "verified_at": "2026-07-12T16:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_manifest=parser_manifest,
        markdown_root=output_root / "markdown",
        decision_text=decision_text,
    )
    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", _stage_b_completion)
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_manifest),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(evaluated_registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(provider_caps_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [label] = _read_jsonl(output_root / "labels.jsonl")
    assert label["supporting_citations"] == [
        {
            "document_id": "decision",
            "excerpt": decision_text,
            "page": None,
            "paragraph": None,
        }
    ]

    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / "cand-1.html").write_text(_docket_html(), encoding="utf-8")
    plan = plan_packet_build_inputs(
        selection_records=(selection,),
        download_records=downloads,
        parser_records=conversions,
        prediction_unit_records=finalized_units,
        raw_html_dir=raw_html_dir,
        document_root=document_root,
        markdown_root=output_root / "markdown",
        source_dir=output_root,
        generated_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    [packet_input] = plan.packet_build_records
    decision_packet_id = "cand-1-decision"
    decision_provenance = next(
        document
        for document in packet_input["documents"]
        if document["source_document_id"] == decision_packet_id
    )
    assert decision_provenance["is_mounted_for_model"] is False
    assert decision_provenance["contains_target_outcome"] is True
    packet_input_path = output_root / "packet-build-input.jsonl"
    _write_jsonl(packet_input_path, [packet_input])
    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [packet] = _read_jsonl(output_root / "packets.jsonl")
    mounted_ids = {document["source_document_id"] for document in packet["documents"]}
    assert decision_packet_id not in mounted_ids
    assert decision_packet_id in packet["excluded_document_ids"]


def _free_download(
    document_root: Path,
    source_document_id: str,
    role: str,
    docket_entry_number: int,
) -> JsonRecord:
    local_path = f"cand-1/courtlistener/{source_document_id}.pdf"
    content = f"%PDF {source_document_id}".encode()
    path = document_root / local_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "candidate_id": "cand-1",
        "source_provider": "courtlistener",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "local_path": local_path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "byte_count": len(content),
        "free_or_purchased": "free",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def _selection() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "decision_date": "2026-07-01",
        "case_name": "Example v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-00001",
        "source_url": "https://www.courtlistener.com/docket/cand-1/",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "selected": True,
        "documents": [
            _selection_document("complaint", "complaint", 1, True, False),
            _selection_document("mtd", "motion_to_dismiss_notice", 5, True, False),
            _selection_document("decision", "decision", 16, False, True),
        ],
    }


def _selection_document(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    model_visible: bool,
    contains_target_outcome: bool,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "description": role,
        "model_visible": model_visible,
        "contains_target_outcome": contains_target_outcome,
        "redaction_or_seal_status": "public",
        "restriction_evidence": ["fixture-public-docket"],
    }


def _prediction_units() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "prediction_units": [
            {
                "unit_id": "unit-1",
                "count": "Count I",
                "claim_name": "Section 10(b)",
                "defendant_group": "Issuer",
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 0.9,
                "source_citations": [
                    {
                        "document_id": "mtd",
                        "docket_entry_number": 5,
                        "excerpt": "Defendant moves to dismiss Count I.",
                    }
                ],
                "grouping": "individual",
                "grouping_rationale": None,
                "separable_subclaim": None,
                "uncertainty_notes": None,
            }
        ],
    }


def _stage_b_completion(*args: Any, **kwargs: Any) -> SolverResponse:
    del kwargs
    prompt = cast(str, args[1])
    assert "Create Stage B outcome labels" in prompt
    return SolverResponse(
        raw_output=json.dumps(
            {
                "unit_findings": [
                    {
                        "unit_id": "unit-1",
                        "resolution": "fully_dismissed",
                        "amendment_signal": "express_denial_of_leave",
                        "supporting_excerpt": (
                            "The motion to dismiss Count I is granted without leave "
                            "to amend."
                        ),
                        "labeler_confidence": 0.95,
                    }
                ],
                "missing_unit_flags": [],
            }
        ),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": "openai", "model_id": "gpt-test"},
    )


def _write_authenticated_stage_b_inputs(
    *,
    root: Path,
    selection_path: Path,
    parser_manifest: Path,
    markdown_root: Path,
    decision_text: str,
) -> list[str]:
    conversions = _read_jsonl(parser_manifest)
    [decision_parser] = [
        record for record in conversions if record["source_document_id"] == "decision"
    ]
    text_sha256 = hashlib.sha256(decision_text.encode()).hexdigest()
    decision_parser["parser_config"] = {
        "engine": "mistral",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "expected_parser_revision": EXPECTED_PARSER_REVISION,
        "fixture_markdown": False,
    }
    decision_parser["extracted_text"] = {
        "source_document_id": "decision",
        "extraction_method": "mistral_parser_markdown",
        "text_sha256": text_sha256,
    }
    _write_jsonl(parser_manifest, conversions)
    commitments = {
        "clearance_run_card_sha256": "sha256:" + "b" * 64,
        "disclosure_clearance_sha256": "sha256:" + "c" * 64,
        "download_manifest_sha256": "sha256:" + "d" * 64,
        "parser_manifest_sha256": _sha256(parser_manifest),
        "parser_run_card_sha256": "sha256:" + "e" * 64,
        "restriction_evidence_sha256": "sha256:" + "f" * 64,
        "selection_sha256": _sha256(selection_path),
        "selection_run_card_sha256": "sha256:" + "1" * 64,
    }
    record = {
        "schema_version": "legalforecast.decision_text.v1",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "document_id": "decision",
        "entered_date": "2026-07-01",
        "text": decision_text,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "document_role": "decision",
        "docket_entry_number": 16,
        "source_sha256": decision_parser["source_sha256"],
        "source_byte_count": decision_parser["source_byte_count"],
        "text_sha256": text_sha256,
        "markdown_sha256": text_sha256,
        "extraction_method": "mistral_parser_markdown",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "clearance": {
            "status": "cleared",
            "restriction_status": "public",
            "reviewer_id": "reviewer:test",
            "controlled_store_provenance": "private-store://test/decision",
            "reviewed_at": "2026-07-15T12:00:00Z",
        },
        "input_commitments": commitments,
    }
    decision_texts = root / "decision-texts.jsonl"
    manifest_path = root / "decision-texts-manifest.json"
    run_card_path = root / "build-decision-texts.json"
    _write_jsonl(decision_texts, [record])
    manifest = {
        "schema_version": "legalforecast.decision_text_manifest.v1",
        "eligibility_anchor": "2026-06-30",
        "record_count": 1,
        "candidate_ids_sha256": _canonical_sha256(["cand-1"]),
        "decision_texts_sha256": _sha256(decision_texts),
        "input_commitments": commitments,
        "outcome_material_model_visible": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    _write_json(manifest_path, manifest)
    _write_json(
        run_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "build-decision-texts",
            "status": "completed",
            "execute": True,
            "dry_run": False,
            "record_count": 1,
            "eligibility_anchor": "2026-06-30",
            "decision_texts_sha256": _sha256(decision_texts),
            "decision_texts_manifest_sha256": _sha256(manifest_path),
            "input_commitments": commitments,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
        },
    )
    return [
        "--decision-texts",
        str(decision_texts),
        "--decision-texts-manifest",
        str(manifest_path),
        "--decision-texts-run-card",
        str(run_card_path),
        "--markdown-root",
        str(markdown_root),
    ]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _registry_record() -> JsonRecord:
    return {
        "provider": "openai",
        "model_id": "gpt-test",
        "display_name": "GPT Test",
        "model_version_or_snapshot": "gpt-test-2026-06-26",
        "release_timestamp": "2026-06-26T00:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-06-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "fixture",
        "input_token_price": 1.0,
        "output_token_price": 2.0,
        "known_cutoff_publicity_caveats": [],
    }


def _docket_html() -> str:
    return """
    <html><body><div id="docket-entry-table">
      <div class="row odd" id="entry-1">
        <div class="col-xs-1"><p>1</p></div>
        <div class="col-xs-3"><p>Jan 1, 2026</p></div>
        <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
      </div>
      <div class="row even" id="entry-5">
        <div class="col-xs-1"><p>5</p></div>
        <div class="col-xs-3"><p>Feb 1, 2026</p></div>
        <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
      </div>
      <div class="row odd" id="entry-16">
        <div class="col-xs-1"><p>16</p></div>
        <div class="col-xs-3"><p>Jul 1, 2026</p></div>
        <div class="col-xs-8"><p>ORDER on Motion to Dismiss.</p></div>
      </div>
    </div></body></html>
    """


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

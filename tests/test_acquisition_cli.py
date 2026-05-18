from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
from legalforecast.cli import main
from legalforecast.ingestion.free_document_downloader import FreeDocumentFetch
from pytest import CaptureFixture, MonkeyPatch

JsonRecord = dict[str, Any]
_GENERATED_AT = "2026-05-17T12:00:00Z"


def test_acquisition_plan_defaults_to_dry_run_with_log_and_run_card(
    tmp_path: Path,
) -> None:
    core_results = tmp_path / "core-filter-results.jsonl"
    output_root = tmp_path / "acquisition"
    _write_jsonl(core_results, [_core_filter_result()])

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert plan["dry_run"] is True
    assert plan["total_missing_core_documents"] == 1
    assert plan["total_estimated_cost_usd"] == "3.05"

    log = _read_jsonl(output_root / "logs" / "acquisition-plan.jsonl")[0]
    assert log["event"] == "stage_completed"
    assert log["dry_run"] is True
    assert log["paid_activity_executed"] is False
    assert log["record_count"] == 1
    run_card = _read_json(output_root / "run-cards" / "acquisition-plan.json")
    assert run_card["schema_version"] == "legalforecast.acquisition_run_card.v1"
    assert run_card["stage"] == "acquisition-plan"


def test_purchase_missing_requires_non_dry_run_plan_and_paid_activity_flags(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path = _write_execute_budget_plan(tmp_path, output_root)

    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(plan_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert "--live-purchase" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "purchase-missing.json")
    assert failure["status"] == "failed"
    assert failure["paid_activity_executed"] is False
    assert failure["failure_reason"] == (
        "live_purchase_and_fee_acknowledgment_required"
    )
    assert not (output_root / "case-dev-pacer-purchases.json").exists()


def test_purchase_missing_uses_fixture_only_after_explicit_fee_flags(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path = _write_execute_budget_plan(tmp_path, output_root)
    fixture_path = tmp_path / "case-dev-purchase.jsonl"
    _write_jsonl(
        fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/mtd-memo/pacer",
                "params": {"acknowledgePacerFees": True, "live": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": "https://case.dev/download/mtd-memo.pdf",
                    "pacerFees": {
                        "pacerFee": 0,
                        "serviceFee": 3.05,
                        "total": 3.05,
                    },
                },
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(plan_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--case-dev-fixture",
                str(fixture_path),
            ]
        )
        == 0
    )

    purchase = _read_json(output_root / "case-dev-pacer-purchases.json")
    assert purchase["executed_purchase_count"] == 1
    assert purchase["attempts"][0]["status"] == "purchased"
    assert purchase["attempts"][0]["pacer_fees"]["total_usd"] == "3.05"
    run_card = _read_json(output_root / "run-cards" / "purchase-missing.json")
    assert run_card["paid_activity_requested"] is True
    assert run_card["paid_activity_executed"] is True


def test_download_free_fixture_stage_is_idempotent(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "Complaint fixture bytes"})

    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]
    assert main(command) == 0
    assert main(command) == 0

    records = _read_jsonl(output_root / "free-document-downloads.jsonl")
    assert records[0]["reused_existing"] is True
    assert (
        records[0]["sha256"] == hashlib.sha256(b"Complaint fixture bytes").hexdigest()
    )
    log_records = _read_jsonl(output_root / "logs" / "download-free.jsonl")
    assert len(log_records) == 2
    assert all(record["paid_activity_executed"] is False for record in log_records)


def test_download_free_no_resume_rejects_existing_artifacts(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "Complaint fixture bytes"})

    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]
    assert main(command) == 0

    assert main([*command, "--no-resume"]) == 2

    assert "resume is disabled" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "download-free.json")
    assert failure["status"] == "failed"
    assert failure["paid_activity_executed"] is False
    assert failure["failure_reason"].startswith("existing document artifact")


def test_download_free_live_public_source_requires_explicit_flag(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    source_url = "https://storage.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    requested_urls: list[str] = []

    class _FakeLiveSource:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            requested_urls.append(source_url)
            return FreeDocumentFetch(content=b"%PDF live free document")

    monkeypatch.setattr(cli, "UrlLibFreeDocumentSource", _FakeLiveSource)
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(requests_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-public-download",
            ]
        )
        == 0
    )

    assert requested_urls == [source_url]
    records = _read_jsonl(output_root / "free-document-downloads.jsonl")
    assert records[0]["byte_count"] == len(b"%PDF live free document")
    assert records[0]["reused_existing"] is False


def test_plan_parse_documents_derives_parser_requests_from_download_manifest(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    manifest_path = tmp_path / "free-document-downloads.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "entry-1-complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": "https://storage.courtlistener.com/recap/doc-1.pdf",
                "local_path": "cand-1/courtlistener/entry-1_doc-1.pdf",
                "sha256": "0" * 64,
                "byte_count": 10,
                "free_or_purchased": "free",
                "retry_count": 0,
                "rate_limited": False,
                "reused_existing": False,
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert requests == [
        {
            "candidate_id": "cand-1",
            "source_document_id": "entry-1-complaint",
            "input_path": str(
                output_root
                / "documents"
                / "free"
                / "cand-1"
                / "courtlistener"
                / "entry-1_doc-1.pdf"
            ),
            "markdown_output_path": "markdown/cand-1/entry-1-complaint.md",
        }
    ]


def test_parse_and_build_packet_acquisition_fixture_flow(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "complaint.md").write_text(
        "Complaint markdown", encoding="utf-8"
    )
    (fixture_markdown / "mtd-memo.md").write_text("MTD markdown", encoding="utf-8")
    parse_requests = tmp_path / "parse-requests.jsonl"
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fixture")
    _write_jsonl(
        parse_requests,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "input_path": str(source_pdf),
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "mtd-memo",
                "input_path": str(source_pdf),
            },
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(parse_requests),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-markdown-dir",
                str(fixture_markdown),
            ]
        )
        == 0
    )

    conversions = _read_jsonl(output_root / "mistral-markdown-conversions.jsonl")
    packet_input = tmp_path / "packet-input.jsonl"
    _write_jsonl(
        packet_input,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "docket_number": "1:26-cv-1",
                "generated_at": _GENERATED_AT,
                "docket_markdown": {
                    "model_visible_markdown": "# Model docket\n\nMTD filed.",
                    "audit_markdown": "# Audit docket\n\nOrder excluded.",
                },
                "documents": [
                    _provenance("complaint", "complaint", 1),
                    _provenance("mtd-memo", "motion_to_dismiss_memorandum", 34),
                ],
                "parsed_documents": [
                    {
                        "source_document_id": conversion["source_document_id"],
                        "markdown_path": conversion["markdown_path"],
                        "extraction_method": "fixture_markdown",
                    }
                    for conversion in conversions
                ],
                "prediction_units": [_prediction_unit()],
                "target_docket_entry_numbers": [34],
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    packet = _read_jsonl(output_root / "packets.jsonl")[0]
    assert [document["source_document_id"] for document in packet["documents"]] == [
        "cand-1:controlled-docket",
        "complaint",
        "mtd-memo",
    ]
    assert (output_root / "case-packets.jsonl").exists()
    audit = _read_jsonl(output_root / "packet-audit.jsonl")[0]
    assert (
        audit["controlled_docket"]["audit_markdown"]
        == "# Audit docket\n\nOrder excluded."
    )


def test_plan_packet_inputs_bridges_acquisition_outputs_to_build_packets(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "cand-1.html").write_text(
        _packet_input_docket_html(),
        encoding="utf-8",
    )
    selection_path = tmp_path / "selection.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    markdown_root = output_root / "markdown"
    for source_document_id, markdown in {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "decision": "Decision markdown",
    }.items():
        markdown_path = markdown_root / "cand-1" / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    _write_jsonl(selection_path, [_packet_selection_record()])
    _write_jsonl(
        downloads_path,
        [
            _download_record("complaint", "complaint", 1),
            _download_record("mtd-memo", "motion_to_dismiss_memorandum", 34),
            _download_record("decision", "decision", 50),
        ],
    )
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint"),
            _parser_record("mtd-memo"),
            _parser_record("decision"),
        ],
    )
    _write_jsonl(
        units_path,
        [{"candidate_id": "cand-1", "prediction_units": [_prediction_unit()]}],
    )

    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--output-root",
                str(output_root),
                "--generated-at",
                _GENERATED_AT,
                "--search-window",
                "2026-04-24..2026-05-18",
                "--execute",
            ]
        )
        == 0
    )

    packet_input = _read_jsonl(output_root / "packet-build-input.jsonl")[0]
    assert packet_input["documents"][0]["source_document_id"] == "cand-1-complaint"
    assert packet_input["prediction_units"][0]["source_citations"] == [
        {"document_id": "cand-1-complaint", "page": 1}
    ]
    assert len(_read_jsonl(output_root / "document-manifest.jsonl")) == 3
    candidate_manifest = _read_jsonl(output_root / "candidate-manifest.jsonl")[0]
    assert candidate_manifest["manifest_record_hash"]

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(output_root / "packet-build-input.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    packet = _read_jsonl(output_root / "packets.jsonl")[0]
    assert "cand-1-decision" in packet["excluded_document_ids"]
    assert packet["prediction_units"][0]["unit_id"] == "count-i-issuer"


def test_build_packets_rejects_mounted_outcome_leakage(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    packet_input = tmp_path / "packet-input.jsonl"
    _write_jsonl(
        packet_input,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "docket_number": "1:26-cv-1",
                "generated_at": _GENERATED_AT,
                "docket_markdown": {
                    "model_visible_markdown": "# Model docket",
                    "audit_markdown": "# Audit docket",
                },
                "documents": [
                    _provenance("complaint", "complaint", 1),
                    _provenance("mtd-memo", "motion_to_dismiss_memorandum", 34),
                    {
                        **_provenance("decision", "decision", 50),
                        "contains_target_outcome": True,
                    },
                ],
                "parsed_documents": [
                    {
                        "source_document_id": "complaint",
                        "markdown": "Complaint markdown",
                    },
                    {"source_document_id": "mtd-memo", "markdown": "MTD markdown"},
                    {
                        "source_document_id": "decision",
                        "markdown": "Decision grants the motion",
                    },
                ],
                "prediction_units": [_prediction_unit()],
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert "must not expose target outcomes" in capsys.readouterr().err
    assert not (output_root / "packets.jsonl").exists()


def _write_execute_budget_plan(tmp_path: Path, output_root: Path) -> Path:
    core_results = tmp_path / "core-filter-results.jsonl"
    _write_jsonl(core_results, [_core_filter_result()])
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    return output_root / "missing-core-budget-plan.json"


def _core_filter_result() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "purchase_document_ids": ["mtd-memo"],
        "core_mtd_documents": ["mtd-memo"],
        "core_exhibit_documents": [],
        "model_visible_document_ids": ["complaint", "mtd-memo"],
        "operative_complaint_document_id": "complaint",
        "operative_complaint_documents": ["complaint"],
        "audit_only_document_ids": [],
        "core_missing_documents": ["mtd-memo"],
        "exclusion_reasons": [],
    }


def _packet_selection_record() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Example v. Defendant",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "source_url": "https://www.courtlistener.com/docket/cand-1/example/",
        "selected": True,
        "exclusion_reasons": [],
        "target_motion_entry_numbers": [34],
        "decision_entry_numbers": [50],
        "documents": [
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": "https://storage.courtlistener.com/complaint.pdf",
                "description": "Complaint",
                "model_visible": True,
                "contains_target_outcome": False,
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "mtd-memo",
                "docket_entry_number": 34,
                "document_role": "motion_to_dismiss_memorandum",
                "source_url": "https://storage.courtlistener.com/mtd.pdf",
                "description": "Memorandum",
                "model_visible": True,
                "contains_target_outcome": False,
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "decision",
                "docket_entry_number": 50,
                "document_role": "decision",
                "source_url": "https://storage.courtlistener.com/decision.pdf",
                "description": "Decision",
                "model_visible": False,
                "contains_target_outcome": True,
            },
        ],
    }


def _download_record(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_provider": "courtlistener",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "local_path": f"cand-1/courtlistener/{source_document_id}.pdf",
        "sha256": hashlib.sha256(source_document_id.encode()).hexdigest(),
        "byte_count": 10,
        "free_or_purchased": "free",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def _parser_record(source_document_id: str) -> JsonRecord:
    markdown_path = f"cand-1/{source_document_id}.md"
    markdown = {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "decision": "Decision markdown",
    }[source_document_id]
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "input_path": f"/tmp/{source_document_id}.pdf",
        "markdown_path": markdown_path,
        "metadata_path": f"{markdown_path}.metadata.json",
        "parser_config": {"engine": "fixture"},
        "quality_flags": [],
        "extracted_text": {
            "source_document_id": source_document_id,
            "extracted_at": _GENERATED_AT,
            "extraction_method": "fixture_markdown",
            "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "quality_flags": [],
        },
    }


def _packet_input_docket_html() -> str:
    return """
    <html>
      <body>
        <div id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1"><p>1</p></div>
            <div class="col-xs-3"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
          </div>
          <div class="row even" id="entry-34">
            <div class="col-xs-1"><p>34</p></div>
            <div class="col-xs-3"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
          </div>
          <div class="row odd" id="entry-50">
            <div class="col-xs-1"><p>50</p></div>
            <div class="col-xs-3"><p>May 8, 2026</p></div>
            <div class="col-xs-8"><p>ORDER on Motion to Dismiss.</p></div>
          </div>
        </div>
      </body>
    </html>
    """


def _provenance(document_id: str, role: str, docket_entry_number: int) -> JsonRecord:
    return {
        "source_provider": "fixture",
        "source_case_id": "case-1",
        "source_document_id": document_id,
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "document_role": role,
        "retrieved_at": _GENERATED_AT,
        "source_url_or_reference": f"fixture://{document_id}",
        "sha256": hashlib.sha256(f"{document_id} source".encode()).hexdigest(),
        "is_predecision_material": True,
        "is_mounted_for_model": True,
        "availability_status": "available",
        "docket_entry_number": docket_entry_number,
        "contains_target_outcome": False,
        "packet_section": "filings",
    }


def _prediction_unit() -> JsonRecord:
    return {
        "unit_id": "count-i-issuer",
        "count": "I",
        "claim_name": "Section 10(b)",
        "defendant_group": "Issuer",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.95,
        "source_citations": [{"document_id": "complaint", "page": 1}],
    }


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: JsonRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> JsonRecord:
    return cast(JsonRecord, json.loads(path.read_text(encoding="utf-8")))


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

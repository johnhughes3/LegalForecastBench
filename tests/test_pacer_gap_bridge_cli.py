from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main


def test_bridge_pacer_gaps_help_documents_identity_and_free_first_flags(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "bridge-pacer-gaps", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--screened-cases" in output
    assert "--live-case-dev" in output
    assert "never invokes a PACER purchase endpoint" in normalized
    assert "--case-relevance-output" in output
    assert "Run download-free" in output


def test_fixture_pacer_gap_flow_reaches_merged_parser_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    common_document_root = output_root / "documents"
    screened_path = tmp_path / "screened.jsonl"
    case_dev_fixture_path = tmp_path / "case-dev-bridge.jsonl"
    _write_jsonl(screened_path, [_screened_case()])
    _write_jsonl(
        case_dev_fixture_path,
        [
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00001",
                    "limit": 20,
                },
                payload={"dockets": [_case_dev_docket()]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-777",
                    "includeEntries": True,
                    "limit": 500,
                },
                payload={
                    "docket": {
                        **_case_dev_docket(),
                        "entries": [
                            _case_dev_entry(1, "Complaint", "case-dev-complaint"),
                            _case_dev_entry(5, "Motion to Dismiss", "case-dev-mtd"),
                            _case_dev_entry(
                                16,
                                "Order on Motion to Dismiss",
                                "case-dev-decision",
                            ),
                        ],
                    }
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(case_dev_fixture_path),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    free_requests = _read_jsonl(output_root / "free-document-requests.jsonl")
    assert [record["source_document_id"] for record in free_requests] == [
        "case-dev-complaint",
        "case-dev-decision",
    ]
    [selection] = _read_jsonl(output_root / "public-packet-selection.jsonl")
    assert selection["case_id"] == "case-dev-777"
    assert selection["identity_resolution"]["courtlistener_candidate_id"] == ("cl-123")

    free_fixture_path = tmp_path / "free-documents.json"
    _write_json(
        free_fixture_path,
        {
            "https://storage.courtlistener.com/complaint.pdf": "%PDF complaint",
            "https://storage.courtlistener.com/decision.pdf": "%PDF decision",
        },
    )
    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(output_root / "free-document-requests.jsonl"),
                "--fixture-documents",
                str(free_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "filter-core-documents",
                "--case-relevance",
                str(output_root / "case-relevance.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(output_root / "core-filter-results.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    budget = _read_json(output_root / "missing-core-budget-plan.json")
    assert budget["max_projected_budget_usd"] == "2250.00"
    assert budget["max_missing_core_documents_per_case"] == 24
    assert budget["case_plans"][0]["purchase_document_ids"] == ["case-dev-mtd"]

    purchase_fixture_path = tmp_path / "purchase.jsonl"
    download_url = "https://case.dev/download/case-dev-mtd.pdf"
    _write_jsonl(
        purchase_fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/case-dev-mtd/pacer",
                "params": {"live": True, "acknowledgePacerFees": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": download_url,
                    "pacerFees": {"pacerFee": 0, "serviceFee": 3.05, "total": 3.05},
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
                str(output_root / "missing-core-budget-plan.json"),
                "--case-dev-fixture",
                str(purchase_fixture_path),
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    purchased_fixture_path = tmp_path / "purchased.json"
    _write_json(purchased_fixture_path, {download_url: "%PDF purchased motion"})
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(output_root / "case-dev-pacer-purchases.json"),
                "--selection",
                str(output_root / "public-packet-selection.jsonl"),
                "--fixture-documents",
                str(purchased_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "merge-download-manifests",
                "--download-manifest",
                str(output_root / "free-document-downloads.jsonl"),
                "--download-manifest",
                str(output_root / "purchased-document-downloads.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(output_root / "document-downloads-merged.jsonl"),
                "--document-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parser_requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert {record["source_document_id"] for record in parser_requests} == {
        "case-dev-complaint",
        "case-dev-mtd",
        "case-dev-decision",
    }


def _response(
    *,
    params: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": params,
        "status_code": 200,
        "payload": payload,
    }


def _case_dev_docket() -> dict[str, object]:
    return {
        "id": "case-dev-777",
        "courtId": "nysd",
        "docketNumber": "1:26-cv-00001",
        "caseName": "Fixture v. Example",
    }


def _case_dev_entry(
    entry_number: int,
    description: str,
    document_id: str,
) -> dict[str, object]:
    return {
        "id": f"case-dev-entry-{entry_number}",
        "entryNumber": entry_number,
        "description": description,
        "documents": [
            {
                "id": document_id,
                "description": description,
                "type": "main_document",
            }
        ],
    }


def _screened_case() -> dict[str, object]:
    return {
        "candidate": {
            "docket_id": "cl-123",
            "candidate_key": "cl-123",
            "metadata": {
                "case_id": "cl-123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _courtlistener_entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _courtlistener_entry(
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _courtlistener_entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _courtlistener_entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

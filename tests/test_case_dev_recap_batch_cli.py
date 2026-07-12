from __future__ import annotations

import json
from pathlib import Path

from legalforecast.cli import main


def test_enrich_recap_case_dev_ranks_free_lookups_without_fee_flags(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        json.dumps(
            {
                "candidate_id": "courtlistener-docket-101",
                "docket_id": "101",
                "docket_url": "https://www.courtlistener.com/docket/101/example/",
                "entry_keys": ["entry-10"],
                "matched_terms": ["motion to dismiss"],
                "eligibility_status": "potential_unverified",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "method": "POST",
                "path": "/legal/v1/docket",
                "params": {
                    "type": "lookup",
                    "docketId": "101",
                    "includeEntries": True,
                    "limit": 100,
                },
                "status_code": 200,
                "payload": {
                    "docket": {
                        "id": "101",
                        "url": (
                            "https://www.courtlistener.com/api/rest/v4/dockets/101/"
                        ),
                        "entries": [
                            {
                                "id": "entry-10",
                                "entryNumber": 10,
                                "date": "2026-07-01",
                                "description": "Order denying Motion to Dismiss",
                                "documents": [
                                    {
                                        "id": "doc-10",
                                        "description": "Decision",
                                        "type": "main_document",
                                        "pdfUrl": (
                                            "https://storage.courtlistener.com/"
                                            "decision.pdf"
                                        ),
                                        "isAvailable": True,
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "output"

    assert (
        main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )

    [ranked] = _read_jsonl(output_root / "checkpoints" / "case-dev-recap-ranked.jsonl")
    assert ranked["identity"]["courtlistener_docket_id"] == "101"
    assert ranked["actual_free_required_document_count"] == 1
    assert ranked["missing_required_document_count"] == 2
    summary = json.loads(
        (output_root / "checkpoints" / "case-dev-recap-summary.json").read_text()
    )
    assert summary["case_dev_request_count"] == 1
    assert summary["successful_docket_count"] == 1
    assert summary["reconciled"] is True
    assert summary["free_lookup_only"] is True
    assert summary["pacer_fee_acknowledgment_allowed"] is False
    assert summary["pacer_spend_usd"] == "0.00"
    assert (
        output_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    ).read_text() == ""


def test_enrich_recap_case_dev_resumes_after_transient_provider_abort(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102")
        )
    )
    first_fixture = tmp_path / "first.jsonl"
    first_fixture.write_text(
        json.dumps(_case_dev_response("101"))
        + "\n"
        + "\n".join(json.dumps(_timeout_response("102")) for _ in range(3))
        + "\n"
    )
    output_root = tmp_path / "output"

    assert (
        main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(first_fixture),
                "--execute",
                "--resume",
            ]
        )
        == 2
    )
    progress = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-progress.jsonl"
    )
    assert [record["input_index"] for record in progress] == [0]

    second_fixture = tmp_path / "second.jsonl"
    second_fixture.write_text(json.dumps(_case_dev_response("102")) + "\n")
    assert (
        main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(second_fixture),
                "--execute",
                "--resume",
            ]
        )
        == 0
    )
    ranked = _read_jsonl(output_root / "checkpoints" / "case-dev-recap-ranked.jsonl")
    assert {record["identity"]["courtlistener_docket_id"] for record in ranked} == {
        "101",
        "102",
    }


def _case_dev_response(docket_id: str) -> dict[str, object]:
    return {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {
            "type": "lookup",
            "docketId": docket_id,
            "includeEntries": True,
            "limit": 100,
        },
        "status_code": 200,
        "payload": {
            "docket": {
                "id": docket_id,
                "url": f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/",
                "entries": [],
            }
        },
    }


def _timeout_response(docket_id: str) -> dict[str, object]:
    response = _case_dev_response(docket_id)
    response["status_code"] = 504
    response["payload"] = {"error": "case.dev request timed out"}
    return response


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]

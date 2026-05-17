from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_client import (
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_smoke import (
    CaseDevSmokeConfig,
    render_case_dev_smoke_markdown,
    run_case_dev_smoke,
)

JsonRecord = dict[str, Any]


def test_case_dev_smoke_runner_summarizes_fixture_results() -> None:
    client = CaseDevClient(
        config=CaseDevConfig(
            api_key=None,
            base_url="https://api.case.dev",
            estimated_cost_per_request_usd=0.25,
        ),
        transport=CaseDevFixtureTransport(_smoke_responses()),
    )
    config = CaseDevSmokeConfig(
        query_terms=("motion to dismiss", "Rule 12"),
        date_window_start="2026-01-01",
        date_window_end="2026-03-31",
        per_query_limit=3,
        candidate_retrieval_limit=2,
        retrieved_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
    )

    result = run_case_dev_smoke(client, config=config)

    assert [summary.hit_count for summary in result.query_summaries] == [2, 1]
    assert [summary.candidate_case_count for summary in result.query_summaries] == [
        2,
        1,
    ]
    assert result.total_hit_count == 3
    assert result.unique_candidate_count == 2
    assert result.retrieved_candidate_count == 2
    assert result.clean_mtd_candidate_count == 1
    assert result.missing_document_reasons == {"no_source_document_id": 1}
    assert result.usage.request_count == 9
    assert result.usage.estimated_cost_usd == 2.25

    markdown = render_case_dev_smoke_markdown(result)
    assert "# Phase 0 case.dev Smoke Report" in markdown
    assert "2026-01-01 to 2026-03-31" in markdown
    assert "| motion to dismiss | 2 | 2 |" in markdown
    assert "- Clean MTD candidates: 1" in markdown
    assert "- no_source_document_id: 1" in markdown
    assert "- case.dev request count: 9" in markdown
    assert "targeted fallback should be evaluated" in markdown


def test_case_dev_smoke_filters_search_hits_to_date_window() -> None:
    client = CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=CaseDevFixtureTransport(
            (
                RecordedCaseDevResponse.from_record(
                    {
                        "method": "POST",
                        "path": "/legal/v1/docket",
                        "params": {
                            "type": "search",
                            "query": "motion to dismiss",
                            "limit": 5,
                        },
                        "status_code": 200,
                        "payload": {
                            "dockets": [
                                _search_docket(
                                    "case-old",
                                    "Old v. Example",
                                    filed_at="2025-12-31",
                                ),
                                _search_docket(
                                    "case-window",
                                    "Window v. Example",
                                    filed_at="2026-02-15",
                                ),
                                _search_docket(
                                    "case-undated",
                                    "Undated v. Example",
                                    filed_at=None,
                                ),
                            ]
                        },
                    }
                ),
            )
        ),
    )
    config = CaseDevSmokeConfig(
        query_terms=("motion to dismiss",),
        date_window_start="2026-01-01",
        date_window_end="2026-03-31",
        per_query_limit=5,
        candidate_retrieval_limit=0,
    )

    result = run_case_dev_smoke(client, config=config)

    assert result.query_summaries[0].hit_count == 1
    assert result.query_summaries[0].candidate_case_count == 1
    assert result.unique_candidate_count == 1
    assert result.retrieved_candidate_count == 0


def test_case_dev_smoke_reports_unavailable_docket_entries() -> None:
    client = CaseDevClient(
        config=CaseDevConfig(api_key=None, base_url="https://api.case.dev"),
        transport=CaseDevFixtureTransport(
            (
                RecordedCaseDevResponse.from_record(
                    {
                        "method": "POST",
                        "path": "/legal/v1/docket",
                        "params": {
                            "type": "search",
                            "query": "motion to dismiss",
                            "limit": 1,
                        },
                        "status_code": 200,
                        "payload": {
                            "dockets": [
                                _search_docket("case-entries", "Entries v. Example")
                            ]
                        },
                    }
                ),
                RecordedCaseDevResponse.from_record(
                    {
                        "method": "POST",
                        "path": "/legal/v1/docket",
                        "params": {"type": "lookup", "docketId": "case-entries"},
                        "status_code": 200,
                        "payload": {
                            "docket": {
                                "id": "case-entries",
                                "caseName": "Entries v. Example",
                                "court": "S.D.N.Y.",
                                "docketNumber": "1:26-cv-00003",
                            }
                        },
                    }
                ),
                RecordedCaseDevResponse.from_record(
                    {
                        "method": "POST",
                        "path": "/legal/v1/docket",
                        "params": {
                            "type": "lookup",
                            "docketId": "case-entries",
                            "includeEntries": True,
                        },
                        "status_code": 501,
                        "payload": {
                            "message": "Docket entry listing is coming soon",
                        },
                    }
                ),
            )
        ),
    )
    config = CaseDevSmokeConfig(
        query_terms=("motion to dismiss",),
        per_query_limit=1,
        candidate_retrieval_limit=1,
    )

    result = run_case_dev_smoke(client, config=config)

    assert result.retrieved_candidate_count == 0
    assert result.clean_mtd_candidate_count == 0
    assert result.missing_document_reasons == {"docket_entry_listing_unavailable": 1}
    assert result.candidates[0].retrieval_error == "Docket entry listing is coming soon"


def test_case_dev_smoke_rejects_invalid_date_window() -> None:
    with pytest.raises(ValueError, match="date_window_start must use YYYY-MM-DD"):
        CaseDevSmokeConfig(date_window_start="01/01/2026")

    with pytest.raises(ValueError, match="on or before"):
        CaseDevSmokeConfig(
            date_window_start="2026-04-01",
            date_window_end="2026-03-31",
        )


def test_case_dev_smoke_cli_writes_fixture_backed_report(tmp_path: Path) -> None:
    fixture_path = tmp_path / "case-dev-smoke.jsonl"
    _write_jsonl(fixture_path, _smoke_response_records())
    output_path = tmp_path / "phase0_case_dev_smoke.md"

    assert (
        main(
            [
                "case-dev-smoke",
                "--output",
                str(output_path),
                "--case-dev-fixture",
                str(fixture_path),
                "--query-term",
                "motion to dismiss",
                "--query-term",
                "Rule 12",
                "--date-window-start",
                "2026-01-01",
                "--date-window-end",
                "2026-03-31",
                "--per-query-limit",
                "3",
                "--candidate-retrieval-limit",
                "2",
            ]
        )
        == 0
    )

    report = output_path.read_text(encoding="utf-8")
    assert "| Rule 12 | 1 | 1 |" in report
    assert "- Unique candidate cases: 2" in report
    assert "| case-dev-smoke-case-1 | case-1 | yes | none | none |" in report


def test_case_dev_smoke_cli_dry_run_needs_no_credentials(tmp_path: Path) -> None:
    output_path = tmp_path / "phase0_case_dev_smoke.md"

    assert (
        main(
            [
                "case-dev-smoke",
                "--output",
                str(output_path),
                "--dry-run",
                "--query-term",
                "motion to dismiss",
                "--date-window-start",
                "2026-01-01",
                "--date-window-end",
                "2026-03-31",
            ]
        )
        == 0
    )

    report = output_path.read_text(encoding="utf-8")
    assert "- Dry run: yes" in report
    assert "| motion to dismiss | 0 | 0 |" in report
    assert "- case.dev request count: 0" in report
    assert "run with a fixture or CASE_DEV_API_KEY" in report


def test_case_dev_smoke_cli_requires_fixture_or_live_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "case-dev-smoke",
                "--output",
                str(tmp_path / "phase0_case_dev_smoke.md"),
                "--query-term",
                "motion to dismiss",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert "case-dev-smoke requires --case-dev-fixture" in captured.err


def _smoke_responses() -> tuple[RecordedCaseDevResponse, ...]:
    return tuple(
        RecordedCaseDevResponse.from_record(record)
        for record in _smoke_response_records()
    )


def _smoke_response_records() -> tuple[JsonRecord, ...]:
    return (
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "search", "query": "motion to dismiss", "limit": 3},
            "status_code": 200,
            "payload": {
                "dockets": [
                    _search_docket("case-1", "Motion To Dismiss v. One"),
                    _search_docket("case-2", "Motion To Dismiss v. Two"),
                ]
            },
        },
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "search", "query": "Rule 12", "limit": 3},
            "status_code": 200,
            "payload": {
                "dockets": [
                    _search_docket(
                        "case-1",
                        "Rule 12 v. Fixture",
                    )
                ]
            },
        },
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "lookup", "docketId": "case-1"},
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-1",
                    "caseName": "Fixture v. Example",
                    "court": "S.D.N.Y.",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        },
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {
                "type": "lookup",
                "docketId": "case-1",
                "includeEntries": True,
            },
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-1",
                    "entries": [
                        _docket_hit("case-1", 1, "Complaint", "doc-1"),
                        _docket_hit(
                            "case-1",
                            12,
                            "Memorandum in support of motion to dismiss",
                            "doc-12",
                        ),
                        _docket_hit(
                            "case-1",
                            99,
                            "Opinion and order denying motion to dismiss",
                            "doc-99",
                        ),
                    ],
                }
            },
        },
        _document_response("doc-1", "case-1", "Complaint text"),
        _document_response("doc-12", "case-1", "Motion to dismiss text"),
        _document_response("doc-99", "case-1", "Decision text"),
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "lookup", "docketId": "case-2"},
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-2",
                    "caseName": "Missing Docs v. Example",
                    "court": "D. Del.",
                    "docketNumber": "1:26-cv-00002",
                },
            },
        },
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {
                "type": "lookup",
                "docketId": "case-2",
                "includeEntries": True,
            },
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-2",
                    "entries": [
                        _docket_hit(
                            "case-2",
                            8,
                            "Motion to dismiss amended complaint",
                            "",
                        )
                    ],
                }
            },
        },
    )


def _search_docket(
    case_id: str,
    case_name: str,
    *,
    filed_at: str | None = "2026-02-01",
) -> JsonRecord:
    record = {
        "id": case_id,
        "caseName": case_name,
        "docketNumber": f"{case_id}-number",
        "court": "S.D.N.Y.",
    }
    if filed_at is not None:
        record["dateFiled"] = filed_at
    return record


def _docket_hit(
    case_id: str,
    entry_number: int,
    text: str,
    document_id: str,
) -> JsonRecord:
    record: JsonRecord = {
        "entryNumber": entry_number,
        "description": text,
        "date": "2026-02-01",
    }
    if document_id:
        record["documents"] = [{"id": document_id}]
    return record


def _document_response(document_id: str, case_id: str, text: str) -> JsonRecord:
    return {
        "method": "GET",
        "path": f"/v1/documents/{document_id}",
        "params": {},
        "status_code": 200,
        "payload": {
            "document_id": document_id,
            "case_id": case_id,
            "text": text,
        },
    }


def _write_jsonl(path: Path, records: tuple[JsonRecord, ...]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record)}\n" for record in records),
        encoding="utf-8",
    )

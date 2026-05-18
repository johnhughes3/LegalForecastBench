from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from legalforecast.cli import main
from legalforecast.ingestion import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.reporting.fallback_pilot import (
    FallbackAttemptStatus,
    FallbackCredentialStatus,
    build_fallback_reconstruction_pilot_report,
    parse_case_dev_fallback_candidates,
    render_fallback_reconstruction_pilot_markdown,
    run_courtlistener_fallback_attempts,
)


def test_fallback_pilot_blocks_truthfully_when_tokens_are_absent() -> None:
    report = build_fallback_reconstruction_pilot_report(
        _blocked_smoke_report(),
        credentials=FallbackCredentialStatus.from_env({"CASE_DEV_API_KEY": "present"}),
        generated_at=datetime(2026, 5, 14, 12, 30, tzinfo=UTC),
    )

    markdown = render_fallback_reconstruction_pilot_markdown(report)

    assert report.clean_packet_count == 0
    assert report.credentials.case_dev_key_present is True
    assert report.credentials.courtlistener_token_present is False
    assert report.status_counts == {
        FallbackAttemptStatus.BLOCKED_MISSING_COURTLISTENER_TOKEN: 2
    }
    assert "| CourtListener token available | no |" in markdown
    assert "| Clean packets produced | 0 |" in markdown
    assert "`COURTLISTENER_API_TOKEN`" in markdown
    assert "not a basis to fabricate packets" in markdown


def test_fallback_pilot_reconstructs_docket_with_courtlistener_fixture() -> None:
    candidates = parse_case_dev_fallback_candidates(_blocked_smoke_report())
    client = CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(
            (
                _courtlistener_response(
                    path="/dockets/123/",
                    payload={"id": 123, "case_name": "Fixture v. Example"},
                ),
                _courtlistener_response(
                    path="/docket-entries/",
                    params={"docket": "123", "page_size": 100},
                    payload={
                        "results": [
                            {
                                "id": 7001,
                                "docket": 123,
                                "entry_number": 12,
                                "description": "Motion to dismiss complaint",
                                "recap_documents": [{"id": 9001}],
                            }
                        ],
                        "next": None,
                    },
                ),
            )
        ),
    )

    attempts = run_courtlistener_fallback_attempts(
        candidates,
        client=client,
        attempt_limit=1,
    )

    assert attempts[0].status is FallbackAttemptStatus.DOCKET_RECONSTRUCTED
    assert attempts[0].docket_entry_count == 1
    assert attempts[0].recap_document_handle_count == 1
    assert attempts[0].request_count == 2


def test_fallback_reconstruction_cli_writes_fixture_backed_report(
    tmp_path: Path,
) -> None:
    smoke_report = tmp_path / "phase0_case_dev_smoke.md"
    smoke_report.write_text(_blocked_smoke_report(), encoding="utf-8")
    fixture_path = tmp_path / "courtlistener.jsonl"
    _write_jsonl(
        fixture_path,
        (
            {
                "method": "GET",
                "path": "/dockets/123/",
                "params": {},
                "status_code": 200,
                "payload": {"id": 123, "case_name": "Fixture v. Example"},
            },
            {
                "method": "GET",
                "path": "/docket-entries/",
                "params": {"docket": "123", "page_size": 100},
                "status_code": 200,
                "payload": {
                    "results": [
                        {
                            "id": 7001,
                            "docket": 123,
                            "description": "Motion to dismiss complaint",
                        }
                    ],
                    "next": None,
                },
            },
        ),
    )
    output = tmp_path / "fallback.md"

    assert (
        main(
            [
                "pilot",
                "fallback-reconstruction",
                "--smoke-report",
                str(smoke_report),
                "--courtlistener-fixture",
                str(fixture_path),
                "--attempt-limit",
                "1",
                "--output",
                str(output),
                "--generated-at",
                "2026-05-14T12:30:00Z",
            ]
        )
        == 0
    )

    report = output.read_text(encoding="utf-8")
    assert "`docket_reconstructed`" in report
    assert "| `case.dev-plus-fallback` | 1 |" in report
    assert "| Clean packets produced | 0 |" in report


def _blocked_smoke_report() -> str:
    return """# Phase 0 case.dev Smoke Report

## Run Configuration

- Generated at: 2026-05-14T19:05:37.526562Z

## Candidate Yield

- Total hit count: 144
- Unique candidate cases: 82
- Retrieved candidate cases: 0
- Clean MTD candidates: 0

## Missing Document Reasons

- docket_entry_listing_unavailable: 2

## Request And Cost Counts

- case.dev request count: 42
- Estimated case.dev cost: not configured

## Candidate Ledger

| Candidate ID | Case ID | Clean proxy | Missing reasons | Retrieval error |
| --- | --- | --- | --- | --- |
| case-dev-smoke-123 | 123 | no | docket_entry_listing_unavailable | unavailable |
| case-dev-smoke-456 | 456 | no | docket_entry_listing_unavailable | unavailable |
"""


def _courtlistener_response(
    *,
    path: str,
    payload: dict[str, object],
    params: dict[str, object] | None = None,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path=path,
        params={} if params is None else params,
        status_code=200,
        payload=payload,
    )


def _write_jsonl(path: Path, records: tuple[dict[str, object], ...]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

from __future__ import annotations

import json
from pathlib import Path

from legalforecast.cli import main


def test_discover_firecrawl_recap_uses_shared_budget_and_reports_potentials(
    tmp_path: Path,
) -> None:
    raw_html = (
        "<!doctype html><html><head><title>0 Results — CourtListener.com</title>"
        "</head><body></body></html>"
    )
    fixture = tmp_path / "firecrawl.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": 200,
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                        },
                    },
                },
                "headers": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "output"

    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(output_root),
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "recap-search-001",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--decision-filed-on-or-before",
                "2026-07-12",
                "--query-term",
                "motion to dismiss",
                "--firecrawl-fixture",
                str(fixture),
                "--proxy",
                "auto",
                "--execute",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "checkpoints" / "batch-001-recap-summary.json").read_text()
    )
    assert summary["potential_candidate_count"] == 0
    assert summary["clean_corpus_count"] == 0
    assert summary["complete"] is True
    assert summary["saturated"] is True
    assert summary["pages_fetched"] == 1
    assert summary["credit_cap"] == 45_000
    assert summary["reserved_credits"] == 5
    assert summary["reported_credits"] == 1
    assert summary["remaining_authorization"] == 44_995
    assert summary["query_terms"] == ["motion to dismiss"]
    assert (
        output_root / "checkpoints" / "batch-001-recap-entries.jsonl"
    ).read_text() == ""
    assert (
        output_root / "checkpoints" / "batch-001-recap-dockets.jsonl"
    ).read_text() == ""


def test_discover_firecrawl_recap_rejects_judgment_on_pleadings_terms(
    tmp_path: Path,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-firecrawl-recap",
                "--output-root",
                str(tmp_path / "output"),
                "--batch-id",
                "batch-001",
                "--run-id",
                "recap-search-001",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--decision-filed-on-or-before",
                "2026-07-12",
                "--query-term",
                "order on motion for judgment on the pleadings",
                "--live-firecrawl",
            ]
        )
        == 2
    )

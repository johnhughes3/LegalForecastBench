from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from legalforecast.cli import _firecrawl_metered_activity_executed, main
from legalforecast.ingestion.firecrawl_recap_decision_discovery import (
    DECISION_FIRST_RECAP_MAX_AUTHORIZED_CREDITS,
    DECISION_FIRST_RECAP_SEARCH_TERMS,
    FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS,
    FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS,
    build_decision_recap_search_url,
)


def _fixture(path: Path, *, include_hit: bool = False) -> Path:
    records = []
    for index, term in enumerate(DECISION_FIRST_RECAP_SEARCH_TERMS):
        source_url = build_decision_recap_search_url(
            term=term,
            entry_date_filed_after=date(2026, 6, 30),
            entry_date_filed_before=date(2026, 7, 13),
        )
        raw_html = (
            "<!doctype html><html><head><title>0 Results — "
            "CourtListener.com</title></head><body></body></html>"
        )
        if include_hit and index == 0:
            raw_html = (
                "<!doctype html><html><head><title>1 Result — "
                'CourtListener.com</title></head><body><main id="search-results">'
                '<article><h3><a href="/docket/12345/alpha-v-beta/">'
                'Alpha v. Beta</a></h3><div class="col-md-offset-half"><h4>'
                '<a href="/docket/12345/27/alpha-v-beta/">ORDER granting motion '
                'to dismiss — Document #27</a></h4><time datetime="2026-07-02">'
                "2026-07-02</time></div></article></main></body></html>"
            )
        records.append(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": 200,
                            "proxyUsed": "basic",
                            "creditsUsed": 1,
                            "sourceURL": source_url,
                        },
                    },
                },
                "headers": {},
            }
        )
    path.write_text("".join(f"{json.dumps(record)}\n" for record in records))
    return path


def test_metered_activity_uses_current_run_not_prior_cycle_reservations() -> None:
    assert not _firecrawl_metered_activity_executed(
        live=True,
        summary={"reserved_credits": 7_320, "run_reserved_credits": 0},
    )
    assert _firecrawl_metered_activity_executed(
        live=True,
        summary={"reserved_credits": 7_325, "run_reserved_credits": 5},
    )


def _args(tmp_path: Path, fixture: Path) -> list[str]:
    return [
        "acquisition",
        "discover-firecrawl-recap-decisions",
        "--output-root",
        str(tmp_path / "output"),
        "--cycle-store",
        str(tmp_path / "cycle.sqlite3"),
        "--batch-id",
        "decision-rescue-001",
        "--run-id",
        "decision-search-001",
        "--eligibility-anchor",
        "2026-06-30",
        "--search-window-start",
        "2026-06-30",
        "--search-window-end",
        "2026-07-13",
        "--firecrawl-fixture",
        str(fixture),
        "--execute",
    ]


def test_cli_runs_eight_term_type_rd_rescue_with_bounded_credit_accounting(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "firecrawl.jsonl")
    assert main(_args(tmp_path, fixture)) == 0
    summary_path = (
        tmp_path / "output/checkpoints/decision-rescue-001-recap-summary.json"
    )
    summary = json.loads(summary_path.read_text())
    assert summary["query_terms"] == list(DECISION_FIRST_RECAP_SEARCH_TERMS)
    assert summary["courtlistener_search_type"] == "r"
    assert summary["max_pages_per_term"] == 100
    assert summary["worst_case_authorized_credits"] == 12_000
    assert summary["frozen_combined_worst_case_credits"] == 28_320
    assert summary["frozen_combined_worst_case_credits"] < 45_000
    assert summary["reserved_credits"] == 40
    assert summary["reported_credits"] == 8
    assert summary["pages_fetched"] == 8
    assert summary["complete"] is True
    assert summary["potential_candidate_count"] == 0
    assert summary["next_stage"] == "acquisition enrich-recap-case-dev"
    assert summary["downstream_stages"][-1] == ("acquisition screen-firecrawl-dockets")
    assert "COURTLISTENER_API_TOKEN" not in json.dumps(summary)


def test_cli_resume_reuses_verified_pages_without_additional_credits(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path / "firecrawl.jsonl")
    args = _args(tmp_path, fixture)
    assert main(args) == 0
    assert main(args) == 0
    summary_path = (
        tmp_path / "output/checkpoints/decision-rescue-001-recap-summary.json"
    )
    summary = json.loads(summary_path.read_text())
    assert summary["reserved_credits"] == 40
    assert summary["reported_credits"] == 8


def test_decision_docket_output_hands_off_to_free_case_dev_enrichment(
    tmp_path: Path,
) -> None:
    firecrawl_fixture = _fixture(tmp_path / "firecrawl.jsonl", include_hit=True)
    assert main(_args(tmp_path, firecrawl_fixture)) == 0
    dockets_path = (
        tmp_path / "output/checkpoints/decision-rescue-001-recap-dockets.jsonl"
    )
    [docket] = [json.loads(line) for line in dockets_path.read_text().splitlines()]
    assert docket["docket_id"] == "12345"
    assert docket["candidate_id"] == "courtlistener-docket-12345"

    case_dev_fixture = tmp_path / "case-dev.jsonl"
    case_dev_fixture.write_text(
        json.dumps(
            {
                "method": "POST",
                "path": "/legal/v1/docket",
                "params": {
                    "type": "lookup",
                    "docketId": "12345",
                    "includeEntries": True,
                    "limit": 100,
                },
                "status_code": 200,
                "payload": {
                    "docket": {
                        "id": "12345",
                        "url": (
                            "https://www.courtlistener.com/api/rest/v4/dockets/12345/"
                        ),
                        "entries": [],
                    }
                },
            }
        )
        + "\n"
    )
    enrichment_root = tmp_path / "enrichment"
    assert (
        main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(enrichment_root),
                "--dockets",
                str(dockets_path),
                "--case-dev-fixture",
                str(case_dev_fixture),
                "--execute",
            ]
        )
        == 0
    )
    enrichment_summary = json.loads(
        (enrichment_root / "checkpoints/case-dev-recap-summary.json").read_text()
    )
    assert enrichment_summary["successful_docket_count"] == 1
    assert enrichment_summary["free_lookup_only"] is True
    assert enrichment_summary["pacer_fee_acknowledgment_allowed"] is False
    assert enrichment_summary["pacer_spend_usd"] == "0.00"


def test_cli_rejects_any_decision_plan_above_the_frozen_twelve_thousand_bound(
    tmp_path: Path,
    capsys: object,
) -> None:
    fixture = _fixture(tmp_path / "firecrawl.jsonl")
    args = _args(tmp_path, fixture)
    args[args.index("--execute") : args.index("--execute")] = [
        "--query-term",
        DECISION_FIRST_RECAP_SEARCH_TERMS[0],
        "--max-pages-per-term",
        "101",
    ]
    assert main(args) == 2
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "12000-credit decision-rescue bound" in captured.err


def test_frozen_credit_constants_include_both_other_cycle_commitments() -> None:
    assert DECISION_FIRST_RECAP_MAX_AUTHORIZED_CREDITS == 12_000
    assert FROZEN_EXISTING_FIRECRAWL_COMMITMENT_CREDITS == 7_320
    assert FROZEN_OTHER_RESCUE_COMMITMENT_CREDITS == 9_000
    assert 12_000 + 7_320 + 9_000 == 28_320 < 45_000


def test_canonical_help_names_firecrawl_case_dev_and_no_courtlistener_token(
    capsys: object,
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "discover-firecrawl-recap-decisions", "--help"])
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    normalized_output = output.replace("-\n", "-")
    assert "type=r" in output
    assert "enrich-recap-case-dev" in normalized_output
    assert "--max-pages-per-term" in output
    assert "--live-firecrawl" in output
    assert "CourtListener API token" in output
    assert "COURTLISTENER_API_TOKEN" not in output

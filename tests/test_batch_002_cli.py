"""CLI tests for the batch-002 RECAP API acquisition driver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_client import COURTLISTENER_API_TOKEN_ENV
from legalforecast.ingestion.recap_api_discovery import (
    DECISION_FIRST_RECAP_API_SEARCH_TERMS,
)


def _search_record(*, term: str, results: list[dict[str, object]]) -> dict[str, object]:
    return {
        "method": "GET",
        "path": "/search/",
        "params": {
            "type": "rd",
            "description": term,
            "entry_date_filed_after": "2026-06-30",
            "entry_date_filed_before": "2026-07-12",
            "order_by": "entry_date_filed desc",
            "page_size": 100,
        },
        "status_code": 200,
        "payload": {"results": results, "next": None},
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def _discover_fixture(
    path: Path, *, first_term_results: list[dict[str, object]]
) -> None:
    records: list[dict[str, object]] = []
    for index, term in enumerate(DECISION_FIRST_RECAP_API_SEARCH_TERMS):
        results = first_term_results if index == 0 else []
        records.append(_search_record(term=term, results=results))
    _write_jsonl(path, records)


def _run_discover(
    tmp_path: Path,
    store: Path,
    *,
    first_term_results: list[dict[str, object]] | None = None,
) -> None:
    fixture = tmp_path / "discover-fixture.jsonl"
    _discover_fixture(fixture, first_term_results=first_term_results or [])
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(store),
                "--courtlistener-fixture",
                str(fixture),
            ]
        )
        == 0
    )


# ---------------------------------------------------------------------------
# discover.
# ---------------------------------------------------------------------------


def test_cli_discover_reports_funnel(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "cycle.sqlite3"
    summary = tmp_path / "discover-summary.json"
    fixture = tmp_path / "fixture.jsonl"
    _discover_fixture(
        fixture,
        first_term_results=[
            {
                "id": 9001,
                "docket_id": 555,
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            }
        ],
    )
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(store),
                "--courtlistener-fixture",
                str(fixture),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["batch_id"] == "batch-002"
    assert out["terms_total"] == 8
    assert out["terms_terminal"] == 8
    assert out["distinct_candidates"] == 1
    assert out["total_hits"] == 1
    assert out["complete"] is True
    written = json.loads(summary.read_text(encoding="utf-8"))
    assert written == out


def test_cli_discover_rejects_inverted_window(tmp_path: Path) -> None:
    store = tmp_path / "cycle.sqlite3"
    fixture = tmp_path / "fixture.jsonl"
    _discover_fixture(fixture, first_term_results=[])
    # A window-order error is a fail-closed CommandError (exit 2), not an argparse
    # usage error.
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(store),
                "--decision-window-start",
                "2026-07-12",
                "--decision-window-end",
                "2026-06-30",
                "--courtlistener-fixture",
                str(fixture),
            ]
        )
        == 2
    )


def test_cli_discover_rejects_negative_min_interval(tmp_path: Path) -> None:
    store = tmp_path / "cycle.sqlite3"
    fixture = tmp_path / "fixture.jsonl"
    _discover_fixture(fixture, first_term_results=[])
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(store),
                "--min-interval-seconds",
                "-0.1",
                "--courtlistener-fixture",
                str(fixture),
            ]
        )
        == 2
    )


def test_cli_discover_requires_a_source(tmp_path: Path) -> None:
    store = tmp_path / "cycle.sqlite3"
    with pytest.raises(SystemExit):
        main(["batch-002", "discover", "--cycle-store", str(store)])


# ---------------------------------------------------------------------------
# observe.
# ---------------------------------------------------------------------------


def test_cli_observe_fails_closed_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(COURTLISTENER_API_TOKEN_ENV, raising=False)
    store = tmp_path / "cycle.sqlite3"
    _run_discover(
        tmp_path,
        store,
        first_term_results=[
            {
                "id": 9001,
                "docket_id": 555,
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            }
        ],
    )
    empty_fixture = tmp_path / "observe-fixture.jsonl"
    empty_fixture.write_text("", encoding="utf-8")
    # Fails closed before any network call: exit 2 with a token-required message.
    assert (
        main(
            [
                "batch-002",
                "observe",
                "--cycle-store",
                str(store),
                "--courtlistener-fixture",
                str(empty_fixture),
                "--min-interval-seconds",
                "0",
                "--jitter-seconds",
                "0",
            ]
        )
        == 2
    )


def test_cli_observe_accepts_with_token_fixture(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(COURTLISTENER_API_TOKEN_ENV, "test-token")
    store = tmp_path / "cycle.sqlite3"
    _run_discover(
        tmp_path,
        store,
        first_term_results=[
            {
                "id": 9001,
                "docket_id": 555,
                "description": "ORDER granting motion to dismiss",
                "entry_date_filed": "2026-07-05",
                "court_id": "nysd",
                "docketNumber": "1:26-cv-00001",
                "caseName": "Acme Corp v. Roe",
            }
        ],
    )
    capsys.readouterr()
    fixture = tmp_path / "observe-fixture.jsonl"
    _write_jsonl(
        fixture,
        [
            {
                "method": "GET",
                "path": "/dockets/555/",
                "params": {},
                "status_code": 200,
                "payload": {
                    "id": 555,
                    "court": "nysd",
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Acme Corp v. Roe",
                    "date_filed": "2026-05-01",
                    "absolute_url": "https://www.courtlistener.com/docket/555/",
                },
            },
            {
                "method": "GET",
                "path": "/docket-entries/",
                "params": {"docket": "555", "page_size": 100},
                "status_code": 200,
                "payload": {
                    "results": [
                        {
                            "id": 7002,
                            "docket": (
                                "https://www.courtlistener.com/api/rest/v4/dockets/555/"
                            ),
                            "entry_number": 40,
                            "description": (
                                "ORDER granting defendant's motion to dismiss the "
                                "complaint"
                            ),
                            "date_filed": "2026-07-05",
                        }
                    ],
                    "next": None,
                },
            },
        ],
    )
    assert (
        main(
            [
                "batch-002",
                "observe",
                "--cycle-store",
                str(store),
                "--courtlistener-fixture",
                str(fixture),
                "--min-interval-seconds",
                "0",
                "--jitter-seconds",
                "0",
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["observed"] == 1
    assert out["eligible"] == 1


# ---------------------------------------------------------------------------
# seed-batch-001-leads.
# ---------------------------------------------------------------------------


def _build_batch_001_store(path: Path) -> None:
    from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore

    store = CycleAcquisitionStore(path)
    store.ensure_cycle({"schema_version": "test"})
    store.ensure_batch("batch-001", {"provider": "firecrawl"})
    term = "motion to dismiss"
    store.ensure_terms("batch-001", (term,))
    store.commit_search_page(
        "batch-001",
        term,
        None,
        [
            {
                "provider_hit_id": "hit-ok",
                "candidate_id": "courtlistener-docket-100",
                "payload": {"docket_id": "100", "case_name": "Ok v. Enriched"},
            },
            {
                "provider_hit_id": "hit-fail",
                "candidate_id": "courtlistener-docket-200",
                "payload": {"docket_id": "200", "case_name": "Fail v. Enrichment"},
            },
        ],
        next_cursor=None,
        terminal_status="exhausted",
    )
    store.record_observation(
        "courtlistener-docket-100",
        batch_id="batch-001",
        state="excluded",
        reason_code="strict_clean_screen_failed",
        evidence={"note": "enriched"},
    )
    store.close()


def test_cli_seed_is_idempotent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "batch-001.sqlite3"
    _build_batch_001_store(source)
    store = tmp_path / "cycle.sqlite3"
    _run_discover(tmp_path, store)
    capsys.readouterr()

    assert (
        main(
            [
                "batch-002",
                "seed-batch-001-leads",
                "--source-store",
                str(source),
                "--cycle-store",
                str(store),
            ]
        )
        == 0
    )
    first = json.loads(capsys.readouterr().out)
    assert first["leads_seeded"] == 1
    assert first["already_seeded"] is False

    assert (
        main(
            [
                "batch-002",
                "seed-batch-001-leads",
                "--source-store",
                str(source),
                "--cycle-store",
                str(store),
            ]
        )
        == 0
    )
    second = json.loads(capsys.readouterr().out)
    assert second["leads_seeded"] == 0
    assert second["already_seeded"] is True


def test_cli_seed_requires_attached_batch(tmp_path: Path) -> None:
    source = tmp_path / "batch-001.sqlite3"
    _build_batch_001_store(source)
    store = tmp_path / "empty.sqlite3"
    from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore

    with CycleAcquisitionStore(store) as opened:
        opened.ensure_cycle(
            {
                "schema_version": "legalforecast.cycle_acquisition_policy.v1",
                "eligibility_anchor": "2026-06-30",
            }
        )
    # The batch was never attached (discover not run), so seeding fails closed.
    assert (
        main(
            [
                "batch-002",
                "seed-batch-001-leads",
                "--source-store",
                str(source),
                "--cycle-store",
                str(store),
            ]
        )
        == 2
    )

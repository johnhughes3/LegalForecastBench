"""CLI tests for the batch-002 RECAP API acquisition driver."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from legalforecast.cli import _batch_002_default_live_interval, main
from legalforecast.ingestion.courtlistener_client import COURTLISTENER_API_TOKEN_ENV
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
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
            "entry_date_filed_before": "2026-07-14",
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


def test_default_live_pacing_matches_selected_hourly_budget() -> None:
    assert (
        _batch_002_default_live_interval(Namespace(courtlistener_rate_profile="base"))
        == 12.5
    )
    assert (
        _batch_002_default_live_interval(
            Namespace(courtlistener_rate_profile="temporary-doubled")
        )
        == 6.25
    )


def test_cli_discover_requires_a_source(tmp_path: Path) -> None:
    store = tmp_path / "cycle.sqlite3"
    with pytest.raises(SystemExit):
        main(["batch-002", "discover", "--cycle-store", str(store)])


def test_cli_live_discover_requires_durable_request_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(COURTLISTENER_API_TOKEN_ENV, "test-token")
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--live",
            ]
        )
        == 2
    )


def test_cli_temporary_doubled_profile_requires_authenticated_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(COURTLISTENER_API_TOKEN_ENV, raising=False)
    assert (
        main(
            [
                "batch-002",
                "discover",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--live",
                "--request-ledger",
                str(tmp_path / "requests.sqlite3"),
                "--courtlistener-rate-profile",
                "temporary-doubled",
            ]
        )
        == 2
    )


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
                            "id": 7001,
                            "docket": (
                                "https://www.courtlistener.com/api/rest/v4/dockets/555/"
                            ),
                            "entry_number": 20,
                            "description": "Motion to dismiss the complaint",
                            "date_filed": "2026-06-20",
                            "recap_documents": [
                                {
                                    "id": 8001,
                                    "document_number": "20",
                                    "attachment_number": None,
                                    "description": "Motion to dismiss",
                                    "filepath_local": (
                                        "https://storage.courtlistener.com/"
                                        "recap/motion.pdf"
                                    ),
                                    "is_available": True,
                                    "is_sealed": False,
                                    "is_private": False,
                                    "redaction_or_seal_status": "public",
                                    "pacer_doc_id": "02004678901",
                                }
                            ],
                        },
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
                        },
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


def test_cli_snapshot_publishes_verified_rest_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(COURTLISTENER_API_TOKEN_ENV, "test-token")
    store = tmp_path / "cycle.sqlite3"
    test_cli_observe_accepts_with_token_fixture(tmp_path, capsys, monkeypatch)
    capsys.readouterr()

    assert (
        main(
            [
                "batch-002",
                "snapshot",
                "--cycle-store",
                str(store),
                "--batch-id",
                "batch-002",
                "--snapshot-id",
                "batch-002-rest-v1",
                "--output-root",
                str(tmp_path / "snapshots"),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    snapshot = Path(summary["snapshot_path"])
    assert summary["verified"] is True
    screened = [
        json.loads(line)
        for line in (snapshot / "screened-cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert screened[0]["ai"]["target_motion_entry_numbers"] == ["20"]
    assert (
        screened[0]["selected_entries"][0]["documents"][0]["freely_available"] is True
    )

    plan_root = tmp_path / "public-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(plan_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                summary["cycle_hash"],
                "--use-embedded-entries",
                "--target-clean-cases",
                "1",
            ]
        )
        == 0
    )
    plan_summary = json.loads(
        (plan_root / "public-packet-plan-summary.json").read_text(encoding="utf-8")
    )
    assert plan_summary["screened_case_count"] == 1
    assert plan_summary["use_embedded_entries"] is True


@pytest.mark.parametrize(
    "rest_evidence",
    (
        {
            "candidate_id": "courtlistener-docket-555",
            "provider": "courtlistener-recap-rest-v4",
            "screen": {"strict_clean": True},
        },
        {
            "candidate_id": "courtlistener-docket-555",
            "provider": "courtlistener-recap-rest-v4",
            "canonical_rest_screen_complete": True,
            "selected_entries": [],
            "screen": {"strict_clean": True},
        },
    ),
    ids=("preliminary", "empty-selected-entries"),
)
def test_cli_snapshot_rejects_incomplete_rest_accept(
    tmp_path: Path, rest_evidence: dict[str, object]
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch("batch-002", {"provider": "courtlistener-recap-rest-v4"})
        store.ensure_terms("batch-002", ("term",))
        store.commit_search_page(
            "batch-002",
            "term",
            None,
            [
                {
                    "provider_hit_id": "hit-1",
                    "candidate_id": "courtlistener-docket-555",
                    "payload": {"docket_id": "555"},
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            "courtlistener-docket-555",
            batch_id="batch-002",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence=rest_evidence,
        )

    assert (
        main(
            [
                "batch-002",
                "snapshot",
                "--cycle-store",
                str(store_path),
                "--snapshot-id",
                "preliminary-rest",
                "--output-root",
                str(tmp_path / "snapshots"),
            ]
        )
        == 2
    )


def test_cli_snapshot_preflights_saturation_without_poisoning_id(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    output_root = tmp_path / "snapshots"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch("batch-002", {"provider": "courtlistener-recap-rest-v4"})
        store.ensure_terms("batch-002", ("term",))
        store.commit_search_page(
            "batch-002",
            "term",
            None,
            [],
            next_cursor=None,
            terminal_status="limit_bound",
        )

    assert (
        main(
            [
                "batch-002",
                "snapshot",
                "--cycle-store",
                str(store_path),
                "--snapshot-id",
                "not-yet-saturated",
                "--output-root",
                str(output_root),
            ]
        )
        == 2
    )
    assert not (output_root / "not-yet-saturated").exists()
    with CycleAcquisitionStore(store_path) as store:
        assert store.published_snapshots() == ()


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


# ---------------------------------------------------------------------------
# seed-direct-search.
# ---------------------------------------------------------------------------


_DIRECT_SEARCH_SOURCE_BATCH_ID = "direct-search-source"
_DIRECT_SEARCH_TARGET_BATCH_ID = "direct-search-rest-screen"


def _build_direct_search_store(path: Path, *, exhausted: bool = True) -> None:
    """Create the smallest realistic direct CourtListener search source."""

    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            {
                "schema_version": "legalforecast.cycle_acquisition_policy.v1",
                "eligibility_anchor": "2026-06-30",
            }
        )
        term = "motion to dismiss"
        store.ensure_batch(
            _DIRECT_SEARCH_SOURCE_BATCH_ID,
            {
                "provider": "courtlistener",
                "query_terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-15",
            },
        )
        store.ensure_terms(_DIRECT_SEARCH_SOURCE_BATCH_ID, (term,))
        store.commit_search_page(
            _DIRECT_SEARCH_SOURCE_BATCH_ID,
            term,
            None,
            [
                {
                    "provider_hit_id": "search-hit-555",
                    "candidate_id": "555",
                    "payload": {
                        "docket_id": "555",
                        "court_id": "nysd",
                        "docket_number": "1:26-cv-00001",
                        "case_name": "Acme Corp v. Roe",
                        "recap_documents": [
                            {
                                "id": 9001,
                                "docket_entry_id": 7001,
                                "entry_number": 40,
                                "document_number": "40",
                                "description": "Order granting motion to dismiss",
                                "entry_date_filed": "2026-07-05",
                            }
                        ],
                    },
                },
                {
                    "provider_hit_id": "search-hit-777",
                    "candidate_id": "777",
                    "payload": {
                        "docket_id": "777",
                        "court_id": "cand",
                        "docket_number": "3:26-cv-00002",
                        "case_name": "Example LLC v. Smith",
                    },
                },
            ],
            next_cursor=None,
            terminal_status="exhausted" if exhausted else "limit_bound",
        )


def _direct_seed_args(store: Path) -> list[str]:
    return [
        "batch-002",
        "seed-direct-search",
        "--source-store",
        str(store),
        "--source-batch-id",
        _DIRECT_SEARCH_SOURCE_BATCH_ID,
        "--cycle-store",
        str(store),
        "--batch-id",
        _DIRECT_SEARCH_TARGET_BATCH_ID,
    ]


@pytest.mark.parametrize(
    "missing_flag",
    ("--source-store", "--source-batch-id", "--cycle-store", "--batch-id"),
)
def test_cli_direct_seed_requires_source_and_target_identity_flags(
    tmp_path: Path, missing_flag: str
) -> None:
    args = _direct_seed_args(tmp_path / "unused.sqlite3")
    index = args.index(missing_flag)
    del args[index : index + 2]

    with pytest.raises(SystemExit) as exc_info:
        main(args)

    assert exc_info.value.code == 2


def test_cli_direct_seed_same_store_is_idempotent_and_writes_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    summary_path = tmp_path / "direct-seed-summary.json"
    _build_direct_search_store(store_path)
    args = [*_direct_seed_args(store_path), "--summary-output", str(summary_path)]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["batch_id"] == _DIRECT_SEARCH_TARGET_BATCH_ID
    assert first["source_batch_id"] == _DIRECT_SEARCH_SOURCE_BATCH_ID
    assert first["leads_selected"] == 2
    assert first["leads_seeded"] == 2
    assert first["already_seeded"] is False
    assert json.loads(summary_path.read_text(encoding="utf-8")) == first
    with CycleAcquisitionStore(store_path) as store:
        target_config = store.batch_config(_DIRECT_SEARCH_TARGET_BATCH_ID)
        assert target_config["page_size"] == 100
        assert (
            store.term_progress(
                _DIRECT_SEARCH_TARGET_BATCH_ID,
                "courtlistener-direct-search-transfer-v1",
            ).terminal_status
            == "exhausted"
        )
        assert store.candidate_ids(_DIRECT_SEARCH_TARGET_BATCH_ID) == (
            "courtlistener-docket-555",
            "courtlistener-docket-777",
        )

    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["leads_selected"] == 2
    assert second["leads_seeded"] == 0
    assert second["already_seeded"] is True
    assert json.loads(summary_path.read_text(encoding="utf-8")) == second


def test_cli_direct_seed_rejects_incomplete_source(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    _build_direct_search_store(store_path, exhausted=False)

    assert main(_direct_seed_args(store_path)) == 2


def test_cli_direct_seed_rejects_same_source_and_target_batch(tmp_path: Path) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    _build_direct_search_store(store_path)
    args = _direct_seed_args(store_path)
    args[args.index("--batch-id") + 1] = _DIRECT_SEARCH_SOURCE_BATCH_ID

    assert main(args) == 2


def test_cli_batch_002_live_help_distinguishes_discover_and_observe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as discover_exit:
        main(["batch-002", "discover", "--help"])
    assert discover_exit.value.code == 0
    discover_help = capsys.readouterr().out
    assert "Disabled for discovery" in discover_help
    assert "seed-direct-search" in discover_help

    with pytest.raises(SystemExit) as observe_exit:
        main(["batch-002", "observe", "--help"])
    assert observe_exit.value.code == 0
    observe_help = capsys.readouterr().out
    normalized_observe_help = " ".join(observe_help.split())
    assert "authenticated CourtListener REST" in normalized_observe_help
    assert "COURTLISTENER_API_TOKEN" in observe_help
    assert "Disabled for discovery" not in observe_help

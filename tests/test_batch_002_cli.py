"""CLI tests for the batch-002 RECAP API acquisition driver."""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from pathlib import Path

import pytest
from legalforecast.cli import _batch_002_default_live_interval, main
from legalforecast.ingestion.courtlistener_client import COURTLISTENER_API_TOKEN_ENV
from legalforecast.ingestion.courtlistener_opinion_discovery import (
    FEDERAL_TRIAL_COURT_IDS,
    OPINION_STATUS_FILTERS,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.firecrawl_screening_identity import (
    snapshot_firecrawl_screening_source_count,
)
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


def _opinion_search_record(
    *, term: str, results: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "method": "GET",
        "path": "/search/",
        "params": {
            "type": "o",
            "q": term,
            "filed_after": "2026-06-30",
            "filed_before": "2026-07-14",
            "order_by": "dateFiled desc",
            "court": " ".join(FEDERAL_TRIAL_COURT_IDS),
            **{name: "on" for name in OPINION_STATUS_FILTERS},
        },
        "status_code": 200,
        "payload": {"count": len(results), "results": results, "next": None},
    }


def _unrestricted_recap_record(
    *, term: str, results: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "method": "GET",
        "path": "/search/",
        "params": {
            "q": (f"{term} AND entry_date_filed:[2026-06-30 TO 2026-07-15]"),
            "type": "r",
            "order_by": "score desc",
            "page_size": 20,
        },
        "status_code": 200,
        "payload": {"results": results, "next": None},
    }


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


def test_cli_discover_opinions_reports_metadata_only_funnel(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(COURTLISTENER_API_TOKEN_ENV, "test-token")
    store = tmp_path / "cycle.sqlite3"
    fixture = tmp_path / "opinion-fixture.jsonl"
    term = '"motion to dismiss"'
    _write_jsonl(
        fixture,
        [
            _opinion_search_record(
                term=term,
                results=[
                    {
                        "cluster_id": 10026367,
                        "docket_id": 70649963,
                        "absolute_url": "/opinion/10026367/example-v-example/",
                        "court_id": "txsd",
                        "docketNumber": "4:26-cv-01234",
                        "caseName": "Example v. Example",
                        "dateFiled": "2026-07-10",
                        "status": "Unpublished",
                        "snippet": "ORDER granting motion to dismiss",
                    }
                ],
            )
        ],
    )

    assert (
        main(
            [
                "batch-002",
                "discover-opinions",
                "--cycle-store",
                str(store),
                "--batch-id",
                "opinion-source-v1",
                "--query-term",
                term,
                "--courtlistener-fixture",
                str(fixture),
                "--summary-output",
                str(tmp_path / "summary.json"),
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["batch_id"] == "opinion-source-v1"
    assert out["terms_total"] == 1
    assert out["terms_terminal"] == 1
    assert out["distinct_candidates"] == 1
    assert out["complete"] is True
    with CycleAcquisitionStore(store) as acquisition_store:
        hit = acquisition_store.candidate_discovery_hits("opinion-source-v1")[0]
        assert hit.candidate_id == "70649963"
        assert "snippet" not in hit.payload

    assert (
        main(
            [
                "batch-002",
                "seed-direct-search",
                "--source-store",
                str(store),
                "--source-batch-id",
                "opinion-source-v1",
                "--cycle-store",
                str(store),
                "--batch-id",
                "opinion-rest-screen-v1",
            ]
        )
        == 0
    )
    transfer = json.loads(capsys.readouterr().out)
    assert transfer["leads_selected"] == 1
    with CycleAcquisitionStore(store) as acquisition_store:
        transferred = acquisition_store.candidate_discovery_hits(
            "opinion-rest-screen-v1"
        )[0]
        assert transferred.candidate_id == "courtlistener-docket-70649963"
        assert "decision_entry_evidence" not in transferred.payload


def test_cli_discover_unrestricted_recap_omits_availability_filter_and_transfers(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(COURTLISTENER_API_TOKEN_ENV, "test-token")
    store = tmp_path / "cycle.sqlite3"
    fixture = tmp_path / "unrestricted-fixture.jsonl"
    term = '"motion to dismiss" AND granted'
    _write_jsonl(
        fixture,
        [
            _unrestricted_recap_record(
                term=term,
                results=[
                    {
                        "docket_id": 71234567,
                        "court_id": "nysd",
                        "docketNumber": "1:26-cv-00123",
                        "caseName": "Alpha LLC v. Beta Inc.",
                        "recap_documents": [
                            {
                                "id": 998,
                                "entry_number": 22,
                                "description": "ORDER granting motion to dismiss",
                                "is_available": False,
                            }
                        ],
                    }
                ],
            )
        ],
    )
    assert (
        main(
            [
                "batch-002",
                "discover-unrestricted-recap",
                "--cycle-store",
                str(store),
                "--batch-id",
                "unrestricted-source-v1",
                "--decision-window-end",
                "2026-07-15",
                "--query-term",
                term,
                "--courtlistener-fixture",
                str(fixture),
            ]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["distinct_candidates"] == 1
    assert out["saturated"] is True
    with CycleAcquisitionStore(store) as acquisition_store:
        config = acquisition_store.batch_config("unrestricted-source-v1")
        assert config["available_only"] == "omitted"

    assert (
        main(
            [
                "batch-002",
                "seed-direct-search",
                "--source-store",
                str(store),
                "--source-batch-id",
                "unrestricted-source-v1",
                "--cycle-store",
                str(store),
                "--batch-id",
                "unrestricted-rest-screen-v1",
            ]
        )
        == 0
    )
    transfer = json.loads(capsys.readouterr().out)
    assert transfer["leads_selected"] == 1
    with CycleAcquisitionStore(store) as acquisition_store:
        assert acquisition_store.candidate_ids("unrestricted-rest-screen-v1") == (
            "courtlistener-docket-71234567",
        )


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


def test_cli_observe_rejects_stale_screening_sources_before_fixture_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(COURTLISTENER_API_TOKEN_ENV, raising=False)
    store_path = tmp_path / "stale-cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "legalforecast.cycle_acquisition_policy.v1",
                "eligibility_anchor": "2026-06-30",
                "screening_source_sha256": {"stale": "0" * 64},
            }
        )
        store.ensure_batch(
            "batch-002",
            {
                "provider": "courtlistener",
                "decision_window_start": "2026-06-30",
                "decision_window_end": "2026-07-15",
            },
        )
        store.ensure_terms("batch-002", ("term",))
        store.commit_search_page(
            "batch-002",
            "term",
            None,
            [
                {
                    "provider_hit_id": "hit-555",
                    "candidate_id": "courtlistener-docket-555",
                    "payload": {
                        "candidate_id": "courtlistener-docket-555",
                        "docket_id": "555",
                    },
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
    unused_fixture = tmp_path / "must-not-be-read.jsonl"
    unused_fixture.write_text("", encoding="utf-8")

    def provider_client_must_not_be_constructed(
        *_args: object, **_kwargs: object
    ) -> None:
        raise AssertionError("provider client constructed before provenance preflight")

    monkeypatch.setattr(
        "legalforecast.cli._batch_002_client",
        provider_client_must_not_be_constructed,
    )

    assert (
        main(
            [
                "batch-002",
                "observe",
                "--cycle-store",
                str(store_path),
                "--courtlistener-fixture",
                str(unused_fixture),
            ]
        )
        == 2
    )
    with CycleAcquisitionStore(store_path) as store:
        assert store.current_observation("courtlistener-docket-555") is None


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
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stage_commitments"] == {
        "courtlistener_rest_screen_inputs": {
            "schema_version": "legalforecast.courtlistener_rest_screen_inputs.v1"
        }
    }
    assert (
        snapshot_firecrawl_screening_source_count(manifest, require_current=True) == 0
    )
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


def _build_cli_prior_snapshot(tmp_path: Path, *, candidate_id: str) -> tuple[Path, str]:
    store_path = tmp_path / "prior.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "schema_version": "legalforecast.cycle_acquisition_policy.v1",
                "eligibility_anchor": "2026-06-30",
            }
        )
        store.ensure_batch("prior", {"provider": "courtlistener"})
        store.ensure_terms("prior", ("screen",))
        store.commit_search_page(
            "prior",
            "screen",
            None,
            [
                {
                    "provider_hit_id": "prior-hit",
                    "candidate_id": candidate_id,
                    "payload": {"candidate_id": candidate_id},
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        store.record_observation(
            candidate_id,
            batch_id="prior",
            state="excluded",
            reason_code="decision_before_release_anchor",
            evidence={
                "candidate_id": candidate_id,
                "decision_date": "2026-06-29",
            },
        )
        snapshot = store.export_snapshot(
            tmp_path / "prior-snapshots",
            snapshot_id="prior-snapshot",
            batch_id="prior",
            complete=True,
        )
    digest = hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()
    return snapshot, digest


def _novel_direct_seed_args(
    store: Path, snapshot: Path, manifest_sha256: str
) -> list[str]:
    return [
        "batch-002",
        "seed-novel-direct-search",
        "--source-store",
        str(store),
        "--source-batch-id",
        _DIRECT_SEARCH_SOURCE_BATCH_ID,
        "--prior-snapshot",
        str(snapshot),
        "--prior-snapshot-manifest-sha256",
        manifest_sha256,
        "--cycle-store",
        str(store),
        "--batch-id",
        "novel-direct-search-rest-screen",
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


def test_cli_rebind_direct_search_initializes_current_cycle_without_network(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "old-cycle.sqlite3"
    target_path = tmp_path / "current-cycle.sqlite3"
    summary_path = tmp_path / "rebind-summary.json"
    _build_direct_search_store(source_path)
    with CycleAcquisitionStore(source_path) as source_store:
        old_cycle_hash = source_store.cycle_hash

    args = [
        "batch-002",
        "rebind-direct-search",
        "--source-store",
        str(source_path),
        "--source-batch-id",
        _DIRECT_SEARCH_SOURCE_BATCH_ID,
        "--cycle-store",
        str(target_path),
        "--batch-id",
        _DIRECT_SEARCH_TARGET_BATCH_ID,
        "--eligibility-anchor",
        "2026-06-30",
        "--summary-output",
        str(summary_path),
    ]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["source_cycle_hash"] == old_cycle_hash
    assert first["target_cycle_hash"] != old_cycle_hash
    assert first["leads_selected"] == 2
    assert first["leads_seeded"] == 2
    assert first["provider_activity_requested"] is False
    assert first["provider_activity_executed"] is False
    assert json.loads(summary_path.read_text(encoding="utf-8")) == first

    with CycleAcquisitionStore(target_path) as target_store:
        assert target_store.cycle_hash == first["target_cycle_hash"]
        assert target_store.cycle_policy["screening_source_sha256"]
        assert target_store.candidate_ids(_DIRECT_SEARCH_TARGET_BATCH_ID) == (
            "courtlistener-docket-555",
            "courtlistener-docket-777",
        )
    with CycleAcquisitionStore(source_path) as source_store:
        with pytest.raises(KeyError):
            source_store.batch_config(_DIRECT_SEARCH_TARGET_BATCH_ID)

    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["leads_seeded"] == 0
    assert second["already_seeded"] is True


def test_cli_rebind_direct_search_help_freezes_provider_free_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch-002", "rebind-direct-search", "--help"])
    assert exc_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "complete saturated" in help_text
    assert "old and current cycle hashes" in help_text
    assert "no provider" in help_text


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


def test_cli_novel_direct_seed_is_zero_network_idempotent_and_auditable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    summary_path = tmp_path / "novel-seed-summary.json"
    _build_direct_search_store(store_path)
    snapshot, manifest_hash = _build_cli_prior_snapshot(
        tmp_path, candidate_id="courtlistener-docket-555"
    )
    args = [
        *_novel_direct_seed_args(store_path, snapshot, manifest_hash),
        "--summary-output",
        str(summary_path),
    ]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["selection_semantics"] == "priority_dedupe_only"
    assert first["prior_outcomes_authoritative"] is False
    assert first["leads_selected"] == 1
    assert first["leads_excluded_from_target"] == 1
    assert first["leads_seeded"] == 1
    assert json.loads(summary_path.read_text(encoding="utf-8")) == first
    with CycleAcquisitionStore(store_path) as store:
        assert store.candidate_ids("novel-direct-search-rest-screen") == (
            "courtlistener-docket-777",
        )
        config = store.batch_config("novel-direct-search-rest-screen")
        assert config["source_candidate_count"] == 2
        assert config["selected_candidate_count"] == 1
        assert config["excluded_from_target_candidate_count"] == 1
        assert config["prior_outcomes_authoritative"] is False

    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["leads_seeded"] == 0
    assert second["already_seeded"] is True


def test_cli_novel_direct_seed_rejects_manifest_mismatch_before_target_write(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    _build_direct_search_store(store_path)
    snapshot, _manifest_hash = _build_cli_prior_snapshot(
        tmp_path, candidate_id="courtlistener-docket-555"
    )

    assert main(_novel_direct_seed_args(store_path, snapshot, "0" * 64)) == 2
    with CycleAcquisitionStore(store_path) as store:
        with pytest.raises(KeyError):
            store.batch_config("novel-direct-search-rest-screen")


def test_cli_novel_direct_seed_help_states_priority_only_cross_cycle_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["batch-002", "seed-novel-direct-search", "--help"])
    assert exc_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "no provider or PACER requests" in help_text
    assert "cross-cycle snapshots are candidate-ID priority dedupe only" in help_text
    assert "--prior-snapshot-manifest-sha256" in help_text


def test_cli_priority_tranche_writes_exact_deferred_frontier_and_resumes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    frontier_path = tmp_path / "priority-1-frontier.json"
    summary_path = tmp_path / "priority-1-summary.json"
    _build_direct_search_store(store_path)
    snapshot, manifest_hash = _build_cli_prior_snapshot(
        tmp_path, candidate_id="courtlistener-docket-999"
    )
    assert main(_novel_direct_seed_args(store_path, snapshot, manifest_hash)) == 0
    capsys.readouterr()
    args = [
        "batch-002",
        "materialize-direct-search-priority-tranche",
        "--source-store",
        str(store_path),
        "--source-batch-id",
        "novel-direct-search-rest-screen",
        "--cycle-store",
        str(store_path),
        "--batch-id",
        "priority-1",
        "--tranche-size",
        "1",
        "--deferred-frontier-output",
        str(frontier_path),
        "--summary-output",
        str(summary_path),
    ]

    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    frontier = json.loads(frontier_path.read_text(encoding="utf-8"))
    assert first["selected_candidate_ids"] == ["courtlistener-docket-555"]
    assert first["deferred_candidate_ids"] == ["courtlistener-docket-777"]
    assert first["provider_activity_executed"] is False
    assert frontier["deferred_disposition"] == "unscreened_not_excluded"
    assert (
        first["deferred_frontier_file_sha256"]
        == hashlib.sha256(frontier_path.read_bytes()).hexdigest()
    )
    assert json.loads(summary_path.read_text(encoding="utf-8")) == first

    assert main(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["already_seeded"] is True
    assert second["leads_seeded"] == 0


def test_cli_priority_tranche_help_is_explicitly_rank_only_and_provider_free(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "batch-002",
                "materialize-direct-search-priority-tranche",
                "--help",
            ]
        )
    assert exc_info.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "rank-only scheduling" in help_text
    assert "Deferred candidates remain unscreened, never excluded" in help_text
    assert "cannot call providers" in help_text
    assert "--expected-predecessor-frontier-sha256" in help_text


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

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionError,
    materialize_selected_slice_batch,
    ranked_docket_targets,
    verify_authenticated_ranked_firecrawl_handoff,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
)
from legalforecast.protocol.freeze import sha256_file


def test_authenticated_ranked_firecrawl_handoff_accepts_exact_type_r_selection(
    tmp_path: Path,
) -> None:
    store_path, ranked_path, run_card_path, run_card_sha256 = (
        _authenticated_type_r_handoff(tmp_path)
    )

    with CycleAcquisitionStore(store_path) as store:
        records = verify_authenticated_ranked_firecrawl_handoff(
            store=store,
            parent_batch_id="ranked-parent",
            ranked_path=ranked_path,
            selection_run_card_path=run_card_path,
            expected_selection_run_card_sha256=run_card_sha256,
            max_candidates=1,
        )

    assert len(records) == 1
    assert records[0]["identity"]["courtlistener_docket_id"] == "123"
    assert records[0]["identity"]["case_dev_url"] == (
        "https://www.courtlistener.com/api/rest/v4/dockets/123/"
    )
    assert records[0]["identity"]["courtlistener_url"] == (
        "https://www.courtlistener.com/docket/123/fixture-v-example/"
    )
    assert ranked_docket_targets(records, limit=1)[0].docket_url == (
        "https://www.courtlistener.com/docket/123/fixture-v-example/"
    )


def test_authenticated_ranked_firecrawl_handoff_rejects_source_type_substitution(
    tmp_path: Path,
) -> None:
    store_path, ranked_path, run_card_path, _run_card_sha256 = (
        _authenticated_type_r_handoff(tmp_path)
    )
    run_card = json.loads(run_card_path.read_text())
    run_card["source_search_type"] = "o"
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()

    with CycleAcquisitionStore(store_path) as store:
        with pytest.raises(
            BudgetedDocketAcquisitionError,
            match="schema/type substitution",
        ):
            verify_authenticated_ranked_firecrawl_handoff(
                store=store,
                parent_batch_id="ranked-parent",
                ranked_path=ranked_path,
                selection_run_card_path=run_card_path,
                expected_selection_run_card_sha256=expected_sha256,
                max_candidates=1,
            )


def test_ranked_budgeted_cli_feeds_strict_selected_slice_snapshot(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    ranked_path = tmp_path / "ranked.jsonl"
    fixture_path = tmp_path / "firecrawl.jsonl"
    output = tmp_path / "output"
    raw_html = _docket_html()
    ranked = {
        "identity": {
            "courtlistener_docket_id": "123",
            "courtlistener_url": (
                "https://www.courtlistener.com/docket/123/fixture-v-example/"
            ),
        },
        "screening_metadata": {
            "case_id": "123",
            "court_id": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Fixture v. Example",
            "nature_of_suit": "Civil Rights",
            "nos_macro_category": "civil_rights",
        },
        "ranking_key": [0, 3, "123"],
    }
    _write_jsonl(ranked_path, [ranked])
    source_url = (
        "https://www.courtlistener.com/docket/123/fixture-v-example/"
        "?order_by=desc&page=1"
    )
    _write_jsonl(
        fixture_path,
        [
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": 200,
                            "sourceURL": source_url,
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                        },
                    },
                },
            }
        ],
    )
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(_policy())
        store.ensure_batch("partial-parent", {"source": "partial-recap"})
        store.ensure_terms("partial-parent", ("motion to dismiss",))
        store.commit_search_page(
            "partial-parent",
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="hit-123",
                    candidate_id="courtlistener-docket-123",
                    payload={"docket_id": "123"},
                ),
            ),
            next_cursor="page-2",
            terminal_status=None,
        )

    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "dockets-001",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--workers",
                "1",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--firecrawl-fixture",
                str(fixture_path),
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 0
    )
    fetch_exclusions = output / "firecrawl-docket-exclusions.jsonl"
    snapshot_root = output / "snapshots"
    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--batch-id",
                "selected-001",
                "--successes",
                str(output / "firecrawl-docket-successes.jsonl"),
                "--fetch-exclusions",
                str(fetch_exclusions),
                "--raw-html-dir",
                str(output / "raw-docket-html"),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--snapshot-root",
                str(snapshot_root),
                "--snapshot-id",
                "selected-001-complete",
                "--output-root",
                str(output / "screen"),
                "--execute",
            ]
        )
        == 0
    )
    manifest = json.loads(
        (snapshot_root / "selected-001-complete" / "manifest.json").read_text()
    )
    assert manifest["complete"] is True
    assert manifest["saturated"] is True
    screened_path = snapshot_root / "selected-001-complete" / "screened-cases.jsonl"
    screened = [json.loads(line) for line in screened_path.read_text().splitlines()]
    assert len(screened) == 1
    assert screened[0]["candidate"]["docket_id"] == "123"
    assert screened[0]["ai"] == {
        "target_motion_entry_numbers": ["5"],
        "decision_entry_numbers": ["16"],
    }
    planner_root = output / "planner"
    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot_root / "selected-001-complete"),
                "--expected-cycle-hash",
                manifest["cycle_hash"],
                "--screened-cases",
                str(screened_path),
                "--raw-html-dir",
                str(output / "raw-docket-html"),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(planner_root),
                "--execute",
            ]
        )
        == 0
    )
    planned_cases = [
        json.loads(line)
        for line in (planner_root / "public-packet-selection.jsonl")
        .read_text()
        .splitlines()
    ]
    assert len(planned_cases) == 1
    assert planned_cases[0]["target_motion_entry_numbers"] == [5]
    with CycleAcquisitionStore(store_path) as store:
        assert (
            store.term_progress("partial-parent", "motion to dismiss").terminal_status
            is None
        )
        run_config = store.firecrawl_run_config("dockets-001")
        assert run_config["workers"] == 1
        assert run_config["max_attempts_per_page"] == 3
        assert run_config["provider_breaker_threshold"] == 5
        assert run_config["target_http_pressure_policy_version"] == (
            "courtlistener-target-http-202-aimd-v1"
        )


def test_ranked_budgeted_cli_dry_run_does_not_mutate_cycle_store(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    ranked_path = tmp_path / "ranked.jsonl"
    fixture_path = tmp_path / "firecrawl.jsonl"
    output = tmp_path / "output"
    _write_jsonl(
        ranked_path,
        [
            {
                "identity": {"courtlistener_docket_id": "123"},
                "screening_metadata": {"case_id": "123"},
                "ranking_key": [0, 1, "123"],
            }
        ],
    )
    _write_jsonl(fixture_path, [])

    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "dockets-001",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--firecrawl-fixture",
                str(fixture_path),
                "--proxy",
                "enhanced",
                "--force-browser",
                "--output-root",
                str(output),
            ]
        )
        == 0
    )

    assert not store_path.exists()
    assert (output / "firecrawl-docket-successes.jsonl").read_text() == ""
    summary = json.loads((output / "firecrawl-docket-summary.json").read_text())
    assert summary["dry_run"] is True
    assert summary["firecrawl_proxy"] == "enhanced"
    assert summary["firecrawl_force_browser"] is True
    assert summary["workers"] == 10
    assert summary["reserved_credits"] == 0


def test_ranked_budgeted_cli_rejects_source_bound_input_without_authenticated_card(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_path, ranked_path, _run_card_path, _run_card_sha256 = (
        _authenticated_type_r_handoff(tmp_path)
    )
    fixture_path = tmp_path / "unused.jsonl"
    _write_jsonl(fixture_path, [])

    result = main(
        [
            "acquisition",
            "acquire-ranked-firecrawl-dockets",
            "--cycle-store",
            str(store_path),
            "--parent-batch-id",
            "ranked-parent",
            "--selected-batch-id",
            "firecrawl-selection",
            "--run-id",
            "firecrawl-run",
            "--ranked",
            str(ranked_path),
            "--max-candidates",
            "1",
            "--decision-filed-on-or-after",
            "2026-06-30",
            "--firecrawl-fixture",
            str(fixture_path),
            "--output-root",
            str(tmp_path / "output"),
        ]
    )

    assert result == 2
    assert "source-bound parent batch requires an authenticated ranked-selection" in (
        capsys.readouterr().err
    )


def test_ranked_budgeted_cli_cannot_bypass_card_by_stripping_source_lineage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_path, ranked_path, _run_card_path, _run_card_sha256 = (
        _authenticated_type_r_handoff(tmp_path)
    )
    [ranked] = [json.loads(line) for line in ranked_path.read_text().splitlines()]
    ranked.pop("source_lineage")
    _write_jsonl(ranked_path, [ranked])
    fixture_path = tmp_path / "unused.jsonl"
    _write_jsonl(fixture_path, [])

    result = main(
        [
            "acquisition",
            "acquire-ranked-firecrawl-dockets",
            "--cycle-store",
            str(store_path),
            "--parent-batch-id",
            "ranked-parent",
            "--selected-batch-id",
            "firecrawl-selection",
            "--run-id",
            "firecrawl-run",
            "--ranked",
            str(ranked_path),
            "--max-candidates",
            "1",
            "--decision-filed-on-or-after",
            "2026-06-30",
            "--firecrawl-fixture",
            str(fixture_path),
            "--output-root",
            str(tmp_path / "output"),
        ]
    )

    assert result == 2
    assert "source-bound parent batch requires an authenticated ranked-selection" in (
        capsys.readouterr().err
    )


def test_ranked_budgeted_cli_rejects_concurrent_fixture_workers(
    tmp_path: Path,
) -> None:
    ranked_path = tmp_path / "ranked.jsonl"
    fixture_path = tmp_path / "firecrawl.jsonl"
    _write_jsonl(ranked_path, [])
    _write_jsonl(fixture_path, [])

    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "dockets-001",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--workers",
                "2",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--firecrawl-fixture",
                str(fixture_path),
                "--output-root",
                str(tmp_path / "output"),
                "--execute",
            ]
        )
        == 2
    )


def test_seal_ranked_firecrawl_cli_projects_exact_unresolved_without_source_write(
    tmp_path: Path,
) -> None:
    store_path, ranked_path, selection_card, selection_card_sha256 = (
        _authenticated_type_r_handoff(tmp_path)
    )
    source_raw_root = tmp_path / "source-raw"
    source_raw_root.mkdir()
    with CycleAcquisitionStore(store_path) as store:
        run_config = {
            "purpose": "ranked-complete-docket-acquisition",
            "decision_anchor": "2026-06-30",
            "max_pages_per_docket": 2,
            "raw_artifact_root": str(source_raw_root.resolve()),
            "firecrawl_proxy": "enhanced",
            "firecrawl_force_browser": False,
            "firecrawl_max_credits_per_scrape": 5,
            "workers": 10,
            "max_attempts_per_page": 3,
            "provider_breaker_threshold": 5,
            "target_http_pressure_policy_version": (
                "courtlistener-target-http-202-aimd-v1"
            ),
        }
        run_digest = store.ensure_firecrawl_run(
            "exhausted-run",
            batch_id="ranked-parent",
            config=run_config,
            credit_cap=5,
            reserved_credits_per_attempt=5,
        )
        source_url = (
            "https://www.courtlistener.com/docket/123/fixture-v-example/"
            "?order_by=desc&page=1"
        )
        target_id = "docket-" + hashlib.sha256(b"123:1").hexdigest()[:24]
        store.ensure_firecrawl_target(
            "exhausted-run",
            target_id=target_id,
            target_kind="docket",
            source_url=source_url,
            ordinal=0,
        )
        attempt = store.authorize_firecrawl_attempt(
            "exhausted-run",
            target_id=target_id,
            page_number=1,
            request_url=source_url,
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="provider_error",
            provider_http_status=500,
            failure_code="provider_server_error",
            failure_message="provider unavailable",
            failure_transient=True,
            failure_response_sha256="a" * 64,
        )
        store.set_firecrawl_target_status("exhausted-run", target_id, "in_progress")
        cycle_hash = store.cycle_hash
    source_namespace = {
        path.name: path.read_bytes()
        for path in tmp_path.iterdir()
        if path.name.startswith(store_path.name)
    }
    output = tmp_path / "sealed"
    seal_args = [
        "acquisition",
        "seal-ranked-firecrawl-run",
        "--source-cycle-store",
        str(store_path),
        "--run-id",
        "exhausted-run",
        "--ranked",
        str(ranked_path),
        "--ranked-selection-run-card",
        str(selection_card),
        "--expected-ranked-selection-run-card-sha256",
        selection_card_sha256,
        "--max-candidates",
        "1",
        "--max-pages-per-docket",
        "2",
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-run-config-sha256",
        run_digest,
        "--expected-credit-cap",
        "5",
        "--expected-total-prior-authorized-firecrawl-credits",
        "5",
        "--authorized-fresh-recovery-credit-cap",
        "0",
        "--output-root",
        str(output),
        "--execute",
    ]

    assert main(seal_args) == 0

    assert (output / "firecrawl-docket-successes.jsonl").read_bytes() == b""
    assert (output / "firecrawl-docket-exclusions.jsonl").read_bytes() == b""
    unresolved = [
        json.loads(line)
        for line in (output / "firecrawl-unresolved-partition.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [record["docket_id"] for record in unresolved] == ["123"]
    assert unresolved[0]["reason"] == "provider_or_interrupted_page_incomplete"
    assert (output / "firecrawl-terminal-partition.jsonl").read_bytes() == b""
    run_card = json.loads(
        (output / "run-cards" / "seal-ranked-firecrawl-run.json").read_text()
    )
    assert run_card["status"] == "completed"
    assert run_card["unresolved_count"] == 1
    assert run_card["authorized_fresh_recovery_credit_cap"] == 0
    assert run_card["provider_activity_executed"] is False
    assert {
        path.name: path.read_bytes()
        for path in tmp_path.iterdir()
        if path.name.startswith(store_path.name)
    } == source_namespace
    assert list(source_raw_root.rglob("*")) == []

    rejected_output = tmp_path / "rejected-seal"
    overlap_args = list(seal_args)
    overlap_args[overlap_args.index(str(output))] = str(rejected_output)
    overlap_args.extend(
        ["--successes-output", str(source_raw_root / "forbidden.jsonl")]
    )
    assert main(overlap_args) == 2
    assert list(source_raw_root.rglob("*")) == []
    assert not rejected_output.exists()


def test_seal_immutable_publication_does_not_clobber_concurrent_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "sealed.jsonl"

    def race_link(
        _source: Path,
        target: Path,
        *,
        follow_symlinks: bool,
    ) -> None:
        assert follow_symlinks is False
        Path(target).write_bytes(b"concurrent publisher\n")
        raise FileExistsError

    monkeypatch.setattr(cli_module.os, "link", race_link)

    with pytest.raises(cli_module.CommandError, match="appeared concurrently"):
        cli_module._write_immutable_bytes(
            destination,
            b"sealed payload\n",
            resume=False,
        )

    assert destination.read_bytes() == b"concurrent publisher\n"
    assert list(tmp_path.glob(".sealed.jsonl.*.tmp")) == []


def test_ranked_budgeted_cli_requires_sequential_resume_for_legacy_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    ranked_path = tmp_path / "ranked.jsonl"
    output = tmp_path / "output"
    ranked = {
        "identity": {
            "courtlistener_docket_id": "123",
            "courtlistener_url": (
                "https://www.courtlistener.com/docket/123/fixture-v-example/"
            ),
        },
        "screening_metadata": {"case_id": "123"},
        "ranking_key": [0, 1, "123"],
    }
    _write_jsonl(ranked_path, [ranked])
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(_policy())
        store.ensure_batch("partial-parent", {"source": "partial-recap"})
        store.ensure_terms("partial-parent", ("motion to dismiss",))
        store.commit_search_page(
            "partial-parent",
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="hit-123",
                    candidate_id="courtlistener-docket-123",
                    payload={"docket_id": "123"},
                ),
            ),
            next_cursor="page-2",
            terminal_status=None,
        )
        materialize_selected_slice_batch(
            store=store,
            parent_batch_id="partial-parent",
            selected_batch_id="selected-001",
            records=[ranked],
            limit=1,
        )
        store.ensure_firecrawl_run(
            "legacy-dockets",
            batch_id="selected-001",
            config={
                "purpose": "ranked-complete-docket-acquisition",
                "decision_anchor": "2026-06-30",
                "max_pages_per_docket": 1000,
                "raw_artifact_root": str((output / "raw-docket-html").resolve()),
                "firecrawl_proxy": "auto",
                "firecrawl_force_browser": False,
                "firecrawl_max_credits_per_scrape": 5,
            },
            credit_cap=45_000,
            reserved_credits_per_attempt=5,
        )

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fixture-key")
    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "legacy-dockets",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--workers",
                "10",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--live-firecrawl",
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "legacy-dockets",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--workers",
                "1",
                "--max-attempts-per-page",
                "4",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--live-firecrawl",
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(store_path),
                "--parent-batch-id",
                "partial-parent",
                "--selected-batch-id",
                "selected-001",
                "--run-id",
                "legacy-dockets",
                "--ranked",
                str(ranked_path),
                "--max-candidates",
                "1",
                "--workers",
                "1",
                "--provider-breaker-threshold",
                "6",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--live-firecrawl",
                "--output-root",
                str(output),
                "--execute",
            ]
        )
        == 2
    )


def _authenticated_type_r_handoff(
    tmp_path: Path,
) -> tuple[Path, Path, Path, str]:
    store_path = tmp_path / "cycle.sqlite3"
    ranked_path = tmp_path / "ranked.jsonl"
    run_card_path = tmp_path / "ranked-selection.json"
    ranked = {
        "identity": {
            "courtlistener_docket_id": "123",
            "case_dev_url": ("https://www.courtlistener.com/api/rest/v4/dockets/123/"),
            "courtlistener_url": (
                "https://www.courtlistener.com/api/rest/v4/dockets/123/"
            ),
        },
        "screening_metadata": {
            "case_id": "123",
            "court_id": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Fixture v. Example",
        },
        "source_lineage": {"source_search_type": "r"},
        "ranking_key": [0, 0, 0, 0, "123"],
    }
    _write_jsonl(ranked_path, [ranked])
    ranked_sha256 = hashlib.sha256(ranked_path.read_bytes()).hexdigest()
    ranked_record_sha256 = hashlib.sha256(
        json.dumps(ranked, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    selected = [
        {
            "docket_id": "123",
            "rank": 1,
            "ranking_key": [0, 0, 0, 0, "123"],
            "returned_courtlistener_url": (
                "https://www.courtlistener.com/api/rest/v4/dockets/123/"
            ),
            "ranked_record_sha256": ranked_record_sha256,
        }
    ]
    selected_sha256 = hashlib.sha256(
        json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    query_commitment = {
        "source_schema_version": ("legalforecast.courtlistener_unrestricted_recap.v1"),
        "source_search_type": "r",
        "source_available_only": "omitted",
        "source_query_expression": ("{term} AND entry_date_filed:[{start} TO {end}]"),
        "source_query_terms": ['"motion to dismiss"'],
        "source_search_window_start": "2026-07-13",
        "source_search_window_end": "2026-07-16",
    }
    commitments: dict[str, object] = {
        "source_batch_id": "unrestricted-source",
        "source_batch_digest": "1" * 64,
        "source_cycle_hash": "2" * 64,
        **query_commitment,
        "source_query_commitment_sha256": hashlib.sha256(
            json.dumps(
                query_commitment,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "source_candidate_set_sha256": "4" * 64,
        "source_hit_set_sha256": "5" * 64,
        "source_projection_sha256": "6" * 64,
        "ranked_output_sha256": ranked_sha256,
        "enrichment_run_card_sha256": "7" * 64,
        "selected_candidate_set_sha256": selected_sha256,
    }
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(_policy())
        target_cycle_hash = store.cycle_hash
        target_config = {
            "selection_semantics": "exact_case_dev_ranked_prefix",
            "query_terms": ["case-dev-ranked-opinion-transfer-v1"],
            "selected_candidate_count": 1,
            **commitments,
        }
        target_digest = store.ensure_batch("ranked-parent", target_config)
        store.ensure_terms(
            "ranked-parent",
            ("case-dev-ranked-opinion-transfer-v1",),
        )
        store.commit_search_page(
            "ranked-parent",
            "case-dev-ranked-opinion-transfer-v1",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="selected-123",
                    candidate_id="courtlistener-docket-123",
                    payload={"docket_id": "123"},
                ),
            ),
            next_cursor=None,
            terminal_status="exhausted",
        )
    run_card = {
        "schema_version": "legalforecast.case_dev_ranked_rest_selection_run.v1",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "batch_id": "ranked-parent",
        "target_cycle_hash": target_cycle_hash,
        "target_batch_digest": target_digest,
        "ranked_candidate_count": 1,
        "leads_selected": 1,
        "top_n": 1,
        "selected": selected,
        **commitments,
    }
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    return (
        store_path,
        ranked_path,
        run_card_path,
        hashlib.sha256(run_card_path.read_bytes()).hexdigest(),
    )


def _policy() -> dict[str, object]:
    package_root = Path(__file__).parents[1] / "legalforecast"
    sources = {
        "mtd_acquisition_screen": package_root / "ingestion/mtd_acquisition_screen.py",
        "courtlistener_acquisition": package_root
        / "ingestion/courtlistener_acquisition.py",
        "restricted_material": package_root / "ingestion/restricted_material.py",
        "contamination_filters": package_root / "selection/contamination_filters.py",
        "motion_linkage": package_root / "selection/motion_linkage.py",
    }
    return {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": "2026-06-30",
        "screening_source_sha256": {
            name: sha256_file(path) for name, path in sorted(sources.items())
        },
    }


def _docket_html() -> str:
    def entry(number: int, filed: str, text: str, description: str) -> str:
        return (
            f'<div class="row" id="entry-{number}">'
            f'<div class="col-xs-1">{number}</div>'
            f'<div class="col-xs-3"><span title="{filed}">{filed}</span></div>'
            f'<div class="col-xs-8">{text}'
            f'<div class="recap-documents"><div>Main Document</div>'
            f'<div>{description}</div><a href="https://storage.courtlistener.com/'
            f'{number}.pdf">Download PDF</a></div></div></div>'
        )

    return (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + entry(1, "January 2, 2026", "COMPLAINT filed", "Complaint")
        + entry(
            5,
            "February 2, 2026",
            "MOTION to Dismiss and Memorandum in Support",
            "Motion to Dismiss and Memorandum in Support",
        )
        + entry(
            16,
            "June 30, 2026",
            "ORDER granting Motion to Dismiss",
            "Order on Motion to Dismiss",
        )
        + "</div></body></html>"
    )


def _write_jsonl(path: Path, records: list[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )

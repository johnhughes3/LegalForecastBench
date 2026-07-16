from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest
from legalforecast.cli import _cycle_acquisition_policy, main
from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionError,
    ranked_parent_requires_authenticated_handoff,
    verify_authenticated_ranked_firecrawl_handoff,
)
from legalforecast.ingestion.case_dev_provisional_frontier import (
    CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA,
    CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore


def test_provisional_frontier_reconciles_success_exclusion_and_pending(
    tmp_path: Path,
) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    checkpoints = enrichment_root / "checkpoints"
    progress_path = checkpoints / "case-dev-recap-progress.jsonl"
    completed = _read_jsonl(progress_path)
    partial = [
        completed[0],
        {
            "input_index": 1,
            "outcome": "failure",
            "payload": {
                "input_index": 1,
                "reason": "case_dev_server_error_retries_exhausted",
                "detail": "provider attempts exhausted",
            },
        },
        {
            "input_index": 2,
            "outcome": "transient",
            "payload": {
                "reason": "case_dev_server_error",
                "detail": "temporary timeout",
            },
        },
    ]
    _write_jsonl(progress_path, partial)
    target_store = _target_store(tmp_path)
    ranked_path = tmp_path / "provisional-ranked.jsonl"
    run_card_path = tmp_path / "provisional-run-card.json"
    summary_path = tmp_path / "provisional-summary.json"
    args = _provisional_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=target_store,
        ranked_path=ranked_path,
        run_card_path=run_card_path,
        summary_path=summary_path,
    )

    assert main(args) == 0
    run_card = json.loads(run_card_path.read_text())
    assert run_card["schema_version"] == CASE_DEV_PROVISIONAL_FRONTIER_RUN_SCHEMA
    assert run_card["provisional_frontier"] is True
    assert run_card["final_cohort_eligible"] is False
    assert run_card["full_source_terminal"] is False
    assert run_card["source_candidate_count"] == 4
    assert run_card["success_count"] == 1
    assert run_card["terminal_exclusion_count"] == 1
    assert run_card["pending_count"] == 2
    assert [item["pending_state"] for item in run_card["pending"]] == [
        "retryable_transient",
        "unprocessed",
    ]
    assert run_card["paid_activity_executed"] is False
    assert len(_read_jsonl(ranked_path)) == 1
    with CycleAcquisitionStore(target_store) as store:
        config = store.batch_config("provisional-rest")
        assert config["selection_semantics"] == (
            CASE_DEV_PROVISIONAL_FRONTIER_SEMANTICS
        )
        assert ranked_parent_requires_authenticated_handoff(store, "provisional-rest")
        assert store.candidate_ids("provisional-rest") == ("courtlistener-docket-101",)
        verified = verify_authenticated_ranked_firecrawl_handoff(
            store=store,
            parent_batch_id="provisional-rest",
            ranked_path=ranked_path,
            selection_run_card_path=run_card_path,
            expected_selection_run_card_sha256=hashlib.sha256(
                run_card_path.read_bytes()
            ).hexdigest(),
            max_candidates=1,
        )
    assert [record["identity"]["courtlistener_docket_id"] for record in verified] == [
        "101"
    ]

    firecrawl_fixture = tmp_path / "firecrawl.jsonl"
    source_url = "https://www.courtlistener.com/docket/101/example-101-v-example/"
    _write_jsonl(
        firecrawl_fixture,
        [
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": _docket_html(),
                        "metadata": {
                            "statusCode": 200,
                            "sourceURL": source_url + "?order_by=desc&page=1",
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                        },
                    },
                },
            }
        ],
    )
    firecrawl_output = tmp_path / "firecrawl-output"
    assert (
        main(
            [
                "acquisition",
                "acquire-ranked-firecrawl-dockets",
                "--cycle-store",
                str(target_store),
                "--parent-batch-id",
                "provisional-rest",
                "--selected-batch-id",
                "provisional-selected",
                "--run-id",
                "provisional-firecrawl",
                "--ranked",
                str(ranked_path),
                "--ranked-selection-run-card",
                str(run_card_path),
                "--expected-ranked-selection-run-card-sha256",
                hashlib.sha256(run_card_path.read_bytes()).hexdigest(),
                "--max-candidates",
                "1",
                "--workers",
                "1",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--firecrawl-fixture",
                str(firecrawl_fixture),
                "--output-root",
                str(firecrawl_output),
                "--execute",
            ]
        )
        == 0
    )
    [firecrawl_success] = _read_jsonl(
        firecrawl_output / "firecrawl-docket-successes.jsonl"
    )
    assert firecrawl_success["provisional_frontier"] is True
    assert firecrawl_success["final_cohort_eligible"] is False
    firecrawl_summary = json.loads(
        (firecrawl_output / "firecrawl-docket-summary.json").read_text()
    )
    assert firecrawl_summary["pending_count"] == 2
    firecrawl_run_card = json.loads(
        (
            firecrawl_output / "run-cards" / "acquire-ranked-firecrawl-dockets.json"
        ).read_text()
    )
    assert firecrawl_run_card["provisional_frontier"] is True
    assert firecrawl_run_card["final_cohort_eligible"] is False
    assert (
        firecrawl_run_card["pending_candidate_set_sha256"]
        == run_card["pending_candidate_set_sha256"]
    )
    with CycleAcquisitionStore(target_store) as store:
        child_config = store.batch_config("provisional-selected")
        assert child_config["provisional_frontier"] is True
        assert child_config["final_cohort_eligible"] is False
        assert (
            child_config["pending_candidate_set_sha256"]
            == (run_card["pending_candidate_set_sha256"])
        )

    screen_output = tmp_path / "screen-output"
    snapshot_root = tmp_path / "snapshots"
    screen_args = [
        "acquisition",
        "screen-firecrawl-dockets",
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "provisional-selected",
        "--successes",
        str(firecrawl_output / "firecrawl-docket-successes.jsonl"),
        "--fetch-exclusions",
        str(firecrawl_output / "firecrawl-docket-exclusions.jsonl"),
        "--raw-html-dir",
        str(firecrawl_output / "raw-docket-html"),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "provisional-screened",
        "--output-root",
        str(screen_output),
        "--execute",
    ]
    assert main(screen_args) == 0
    snapshot = snapshot_root / "provisional-screened"
    manifest = json.loads((snapshot / "manifest.json").read_text())
    assert manifest["complete"] is True
    assert manifest["saturated"] is True
    assert manifest["provisional_frontier"] is True
    assert manifest["final_cohort_eligible"] is False
    assert (
        manifest["stage_commitments"]["provisional_lineage"][
            "pending_candidate_set_sha256"
        ]
        == run_card["pending_candidate_set_sha256"]
    )
    screen_summary = json.loads(
        (screen_output / "firecrawl-screening-summary.json").read_text()
    )
    assert screen_summary["provisional_frontier"] is True
    assert screen_summary["final_cohort_eligible"] is False
    assert (
        screen_summary["pending_candidate_set_sha256"]
        == run_card["pending_candidate_set_sha256"]
    )

    stripped = dict(firecrawl_success)
    stripped.pop("pending_candidate_set_sha256")
    _write_jsonl(firecrawl_output / "firecrawl-docket-successes.jsonl", [stripped])
    assert main(screen_args) == 2
    _write_jsonl(
        firecrawl_output / "firecrawl-docket-successes.jsonl", [firecrawl_success]
    )

    fixture_documents = tmp_path / "documents.jsonl"
    courtlistener_fixture = tmp_path / "courtlistener.jsonl"
    _write_jsonl(fixture_documents, [])
    _write_jsonl(courtlistener_fixture, [])
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(tmp_path / "target-preparation"),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                manifest["cycle_hash"],
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
            ]
        )
        == 2
    )

    assert main(args) == 0
    summary = json.loads(summary_path.read_text())
    assert summary["already_seeded"] is True
    assert "pending" not in summary
    assert "selected" not in summary


@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("pending_count", 1),
        ("success_count", 2),
        ("provisional_frontier", False),
    ],
)
def test_firecrawl_rejects_rehashed_provisional_partition_tamper(
    tmp_path: Path,
    field: str,
    forged: object,
) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    progress_path = enrichment_root / "checkpoints/case-dev-recap-progress.jsonl"
    completed = _read_jsonl(progress_path)
    _write_jsonl(
        progress_path,
        [
            completed[0],
            {
                "input_index": 1,
                "outcome": "transient",
                "payload": {
                    "reason": "case_dev_server_error",
                    "detail": "timeout",
                },
            },
        ],
    )
    target_store = _target_store(tmp_path)
    ranked_path = tmp_path / "ranked.jsonl"
    run_card_path = tmp_path / "run-card.json"
    args = _provisional_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=target_store,
        ranked_path=ranked_path,
        run_card_path=run_card_path,
        summary_path=tmp_path / "summary.json",
    )
    assert main(args) == 0
    run_card = json.loads(run_card_path.read_text())
    run_card[field] = forged
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")

    with CycleAcquisitionStore(target_store) as store:
        with pytest.raises(BudgetedDocketAcquisitionError):
            verify_authenticated_ranked_firecrawl_handoff(
                store=store,
                parent_batch_id="provisional-rest",
                ranked_path=ranked_path,
                selection_run_card_path=run_card_path,
                expected_selection_run_card_sha256=hashlib.sha256(
                    run_card_path.read_bytes()
                ).hexdigest(),
                max_candidates=1,
            )


def test_provisional_frontier_rejects_repeated_terminal_success(tmp_path: Path) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    progress_path = enrichment_root / "checkpoints/case-dev-recap-progress.jsonl"
    completed = _read_jsonl(progress_path)
    _write_jsonl(progress_path, [completed[0], completed[0]])

    assert (
        main(
            _provisional_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=_target_store(tmp_path),
                ranked_path=tmp_path / "ranked.jsonl",
                run_card_path=tmp_path / "run-card.json",
                summary_path=tmp_path / "summary.json",
            )
        )
        == 2
    )


def test_provisional_frontier_rejects_rehashed_success_identity_tamper(
    tmp_path: Path,
) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    progress_path = enrichment_root / "checkpoints/case-dev-recap-progress.jsonl"
    [success, *_] = _read_jsonl(progress_path)
    payload = success["payload"]
    assert isinstance(payload, dict)
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity["courtlistener_docket_id"] = "999"
    _write_jsonl(progress_path, [success])

    assert (
        main(
            _provisional_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=_target_store(tmp_path),
                ranked_path=tmp_path / "ranked.jsonl",
                run_card_path=tmp_path / "run-card.json",
                summary_path=tmp_path / "summary.json",
            )
        )
        == 2
    )


def test_provisional_frontier_keeps_retryable_integrity_failure_pending(
    tmp_path: Path,
) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    progress_path = enrichment_root / "checkpoints/case-dev-recap-progress.jsonl"
    completed = _read_jsonl(progress_path)
    _write_jsonl(
        progress_path,
        [
            completed[0],
            {
                "input_index": 1,
                "outcome": "failure",
                "payload": {"reason": "case_dev_duplicate_entry_conflict"},
            },
        ],
    )

    assert (
        main(
            _provisional_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=_target_store(tmp_path),
                ranked_path=tmp_path / "ranked.jsonl",
                run_card_path=tmp_path / "run-card.json",
                summary_path=tmp_path / "summary.json",
            )
        )
        == 0
    )
    run_card = json.loads((tmp_path / "run-card.json").read_text())
    assert run_card["pending_count"] == 3
    assert run_card["terminal_exclusion_count"] == 0


def test_provisional_frontier_rejects_unauthorized_terminal_drop(
    tmp_path: Path,
) -> None:
    source_store = _source_store(tmp_path)
    enrichment_root = _completed_enrichment(tmp_path, source_store)
    progress_path = enrichment_root / "checkpoints/case-dev-recap-progress.jsonl"
    completed = _read_jsonl(progress_path)
    _write_jsonl(
        progress_path,
        [
            completed[0],
            {
                "input_index": 1,
                "outcome": "failure",
                "payload": {
                    "reason": "case_dev_unclassified_failure",
                    "detail": "must not become an exclusion",
                },
            },
        ],
    )

    assert (
        main(
            _provisional_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=_target_store(tmp_path),
                ranked_path=tmp_path / "ranked.jsonl",
                run_card_path=tmp_path / "run-card.json",
                summary_path=tmp_path / "summary.json",
            )
        )
        == 2
    )


def _provisional_args(
    *,
    source_store: Path,
    enrichment_root: Path,
    target_store: Path,
    ranked_path: Path,
    run_card_path: Path,
    summary_path: Path,
) -> list[str]:
    checkpoints = enrichment_root / "checkpoints"
    progress_path = checkpoints / "case-dev-recap-progress.jsonl"
    return [
        "batch-002",
        "select-case-dev-provisional-frontier",
        "--source-store",
        str(source_store),
        "--source-batch-id",
        "source",
        "--source-projection",
        str(checkpoints / "case-dev-recap-source-projection.jsonl"),
        "--progress-config",
        str(checkpoints / "case-dev-recap-progress-config.json"),
        "--progress",
        str(progress_path),
        "--expected-progress-sha256",
        hashlib.sha256(progress_path.read_bytes()).hexdigest(),
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "provisional-rest",
        "--ranked-output",
        str(ranked_path),
        "--run-card-output",
        str(run_card_path),
        "--summary-output",
        str(summary_path),
    ]


def _completed_enrichment(tmp_path: Path, source_store: Path) -> Path:
    fixture = tmp_path / "case-dev.jsonl"
    _write_jsonl(
        fixture,
        [_case_dev_response(str(docket_id)) for docket_id in range(101, 105)],
    )
    output_root = tmp_path / "enrichment"
    assert (
        main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )
    return output_root


def _source_store(tmp_path: Path) -> Path:
    path = tmp_path / "source.sqlite3"
    term = '"motion to dismiss"'
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch(
            "source",
            {
                "schema_version": "legalforecast.courtlistener_unrestricted_recap.v1",
                "provider": "courtlistener",
                "search_type": "r",
                "query_terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-15",
                "available_only": "omitted",
                "query_expression": "{term} AND entry_date_filed:[{start} TO {end}]",
                "search_page_size": 20,
            },
        )
        store.ensure_terms("source", (term,))
        store.commit_search_page(
            "source",
            term,
            None,
            [_source_hit(str(docket_id)) for docket_id in range(101, 105)],
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _target_store(tmp_path: Path) -> Path:
    path = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(_cycle_acquisition_policy(anchor=date(2026, 6, 30)))
    return path


def _source_hit(docket_id: str) -> dict[str, object]:
    return {
        "provider_hit_id": f"entry-{docket_id}",
        "candidate_id": docket_id,
        "payload": {
            "docket_id": docket_id,
            "court_id": "dcd",
            "docket_number": f"1:25-cv-{int(docket_id):05d}",
            "case_name": f"Example {docket_id} v. Example",
            "decision_entry_evidence": {
                "entry_number": "10",
                "date_filed": "2026-07-14",
                "description": "Order denying motion to dismiss",
            },
        },
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
                "caseName": f"Example {docket_id} v. Example",
                "courtId": "dcd",
                "docketNumber": f"1:25-cv-{int(docket_id):05d}",
                "entries": [],
            }
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
        "<html><head><title>Example 101 v. Example</title></head><body>"
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


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_jsonl(path: Path, records: list[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

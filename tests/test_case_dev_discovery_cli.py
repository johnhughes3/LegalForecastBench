from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import TermTerminalStatus


def test_discover_case_dev_writes_resumable_self_contained_checkpoint(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "method": "POST",
                "path": "/legal/v1/docket",
                "params": {
                    "type": "search",
                    "query": "order on motion to dismiss",
                    "limit": 2,
                },
                "status_code": 200,
                "payload": {
                    "dockets": [
                        {
                            "id": "case-dev-abc",
                            "caseName": "Fixture v. Example",
                            "courtId": "nysd",
                            "docketNumber": "1:26-cv-00001",
                            "url": (
                                "https://www.courtlistener.com/api/rest/v4/dockets/123/"
                            ),
                        }
                    ]
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "acquisition"

    command = [
        "acquisition",
        "discover-case-dev",
        "--output-root",
        str(output_root),
        "--batch-id",
        "batch-001",
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--decision-filed-on-or-before",
        "2026-07-12",
        "--query-term",
        "order on motion to dismiss",
        "--per-term-limit",
        "5",
        "--search-page-size",
        "2",
        "--case-dev-fixture",
        str(fixture),
        "--execute",
    ]
    assert main(command) == 0

    checkpoint = _read_jsonl(
        output_root / "checkpoints" / "batch-001-case-dev-candidates.partial.jsonl"
    )
    assert checkpoint == [
        {
            **checkpoint[0],
            "candidate_id": "case-dev-abc",
            "case_id": "case-dev-abc",
            "case_dev_case_id": "case-dev-abc",
            "courtlistener_docket_id": "123",
            "courtlistener_url": (
                "https://www.courtlistener.com/docket/123/fixture-v-example/"
            ),
        }
    ]
    assert checkpoint[0]["case_metadata"]["id"] == "case-dev-abc"
    summary = _read_json(
        output_root / "checkpoints" / "batch-001-case-dev-summary.partial.json"
    )
    assert summary["complete"] is False
    assert summary["saturated"] is False
    assert summary["provider_pagination_end_observed"] is True
    assert summary["provider_completeness_status"] == "unknown"
    assert summary["provider_saturation_status"] == "unproven"
    assert summary["anchored_disposition_discovery"] is False
    assert "exploratory" in summary["candidate_count_semantics"]
    assert summary["checkpoint_only"] is True
    assert summary["terminal_status_by_term"] == {
        "order on motion to dismiss": "exhausted"
    }
    assert isinstance(summary["cycle_hash"], str)

    with CycleAcquisitionStore(output_root / "cycle-acquisition.sqlite3") as store:
        progress = store.term_progress("batch-001", "order on motion to dismiss")
        assert progress.terminal_status is TermTerminalStatus.EXHAUSTED
        assert store.candidate_ids("batch-001") == ("case-dev-abc",)
        partial_snapshot = store.export_snapshot(
            tmp_path / "snapshots",
            snapshot_id="checkpoint",
            batch_id="batch-001",
            complete=False,
        )

    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(tmp_path / "planner"),
                "--snapshot",
                str(partial_snapshot),
                "--expected-cycle-hash",
                summary["cycle_hash"],
                "--execute",
            ]
        )
        == 2
    )


def test_discover_case_dev_full_cursorless_page_is_not_claimed_exhausted(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "case-dev.jsonl"
    records: list[dict[str, Any]] = [
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "search", "query": "MTD", "limit": 1},
            "status_code": 200,
            "payload": {
                "dockets": [
                    {
                        "id": "case-dev-abc",
                        "caseName": "Fixture v. Example",
                        "courtId": "nysd",
                        "docketNumber": "1:26-cv-00001",
                        "url": (
                            "https://www.courtlistener.com/api/rest/v4/dockets/123/"
                        ),
                    }
                ]
            },
        }
    ]
    fixture.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    output_root = tmp_path / "acquisition"

    assert (
        main(
            [
                "acquisition",
                "discover-case-dev",
                "--output-root",
                str(output_root),
                "--batch-id",
                "batch-001",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--decision-filed-on-or-before",
                "2026-07-12",
                "--query-term",
                "MTD",
                "--per-term-limit",
                "5",
                "--search-page-size",
                "1",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )

    summary = _read_json(
        output_root / "checkpoints" / "batch-001-case-dev-summary.partial.json"
    )
    assert summary["complete"] is False
    assert summary["saturated"] is False
    assert summary["terminal_status_by_term"] == {"MTD": "limit_bound_unpageable"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
)
from legalforecast.protocol.freeze import sha256_file


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
    with CycleAcquisitionStore(store_path) as store:
        assert (
            store.term_progress("partial-parent", "motion to dismiss").terminal_status
            is None
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
            f'<div class="row" id="entry-{number}"><div>{number}</div>'
            f'<span title="{filed}">{filed}</span><div>{text}'
            f'<div class="recap-documents"><div>Main Document</div>'
            f'<div>{description}</div><a href="https://storage.courtlistener.com/'
            f'{number}.pdf">Download PDF</a></div></div></div>'
        )

    return (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + entry(1, "January 2, 2026", "COMPLAINT filed", "Complaint")
        + entry(5, "February 2, 2026", "MOTION to Dismiss", "Motion to Dismiss")
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

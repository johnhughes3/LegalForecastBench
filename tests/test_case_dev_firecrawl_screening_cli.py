from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.protocol.freeze import sha256_file


@dataclass(frozen=True, slots=True)
class _CycleState:
    cli_args: tuple[str, ...]
    snapshot: Path
    cycle_hash: str
    batch_digest: str


@pytest.fixture
def cycle_state(tmp_path: Path) -> _CycleState:
    return _create_cycle_state(
        tmp_path,
        policy=_test_cycle_policy(anchor=date(2026, 6, 30)),
    )


def _create_cycle_state(
    tmp_path: Path,
    *,
    policy: dict[str, object],
) -> _CycleState:
    store_path = tmp_path / "cycle-acquisition.sqlite3"
    batch_id = "fixture-batch"
    fetch_exclusions = tmp_path / "fetch-exclusions.jsonl"
    snapshot_root = tmp_path / "snapshots"
    snapshot_id = "fixture-complete"
    _write_jsonl(fetch_exclusions, [])
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle(policy)
        batch_digest = store.ensure_batch(batch_id, {"fixture": True})
        store.ensure_terms(batch_id, ("motion to dismiss",))
        store.commit_search_page(
            batch_id,
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="fixture-provider-hit-123",
                    candidate_id="case-dev-123",
                    payload={"case_id": "case-dev-123"},
                ),
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    return _CycleState(
        cli_args=(
            "--cycle-store",
            str(store_path),
            "--batch-id",
            batch_id,
            "--fetch-exclusions",
            str(fetch_exclusions),
            "--snapshot-root",
            str(snapshot_root),
            "--snapshot-id",
            snapshot_id,
        ),
        snapshot=snapshot_root / snapshot_id,
        cycle_hash=cycle_hash,
        batch_digest=batch_digest,
    )


def test_screen_firecrawl_dockets_emits_direct_public_planner_input(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    success = _success_record(raw_html)
    success.update(
        {
            "candidate_id": "search-hit-123",
            "source_url": (
                "https://www.courtlistener.com/docket/123/fixture-v-example/"
            ),
            "raw_html_path": "/untrusted/path/ignored.html",
            "case_metadata": {
                "case_id": "case-dev-123",
                "court_id": "nysd",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
                "case_name": "Fixture v. Example",
                "nature_of_suit": "Civil Rights",
                "nos_macro_category": "civil_rights",
            },
        }
    )
    _write_jsonl(
        successes,
        [success],
    )

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [screened] = _read_jsonl(output_root / "firecrawl-screened-cases.jsonl")
    assert screened["candidate"]["docket_id"] == "123"
    assert screened["candidate"]["metadata"]["case_id"] == "case-dev-123"
    assert screened["ai"] == {
        "target_motion_entry_numbers": ["5"],
        "decision_entry_numbers": ["16"],
    }
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []
    assert _read_json(output_root / "firecrawl-screening-summary.json") == {
        "accepted_case_count": 1,
        "anchor_date": "2026-06-30",
        "batch_digest": cycle_state.batch_digest,
        "cycle_hash": cycle_state.cycle_hash,
        "dry_run": False,
        "excluded_case_count": 0,
        "input_fetch_exclusion_count": 0,
        "input_success_count": 1,
        "paid_activity_requested": False,
        "reconciled": True,
        "schema_version": "legalforecast.firecrawl_screening_summary.v1",
        "snapshot_complete": True,
        "snapshot_path": str(cycle_state.snapshot),
        "snapshot_saturated": True,
    }

    planner_root = tmp_path / "planner"
    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(cycle_state.snapshot),
                "--expected-cycle-hash",
                cycle_state.cycle_hash,
                "--screened-cases",
                str(cycle_state.snapshot / "screened-cases.jsonl"),
                "--raw-html-dir",
                str(raw_html_dir),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(planner_root),
                "--execute",
            ]
        )
        == 0
    )
    [selection] = _read_jsonl(planner_root / "public-packet-selection.jsonl")
    assert selection["candidate_id"] == "123"
    assert selection["case_id"] == "case-dev-123"

    screened_before_dry_run = (
        output_root / "firecrawl-screened-cases.jsonl"
    ).read_bytes()
    exclusions_before_dry_run = (
        output_root / "firecrawl-screening-exclusions.jsonl"
    ).read_bytes()
    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
    assert (
        output_root / "firecrawl-screened-cases.jsonl"
    ).read_bytes() == screened_before_dry_run
    assert (
        output_root / "firecrawl-screening-exclusions.jsonl"
    ).read_bytes() == exclusions_before_dry_run


def test_screen_firecrawl_dockets_fail_closed_on_first_preanchor_disposition(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 29, 2026", "July 1, 2026"))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "firecrawl-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["reason"] == "decision_before_release_anchor"
    assert exclusion["case_id"] == "case-dev-123"


def test_screen_firecrawl_dockets_rejects_changed_html_commitment(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    raw_path = raw_html_dir / "123.html"
    raw_path.write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    success = _success_record(raw_html)
    success["raw_html_bytes"] = len(raw_html.encode())
    success["raw_html_sha256"] = f"sha256:{sha256(b'different').hexdigest()}"
    _write_jsonl(successes, [success])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert not cycle_state.snapshot.exists()


@pytest.mark.parametrize(
    "missing_field",
    ("raw_html_sha256", "raw_html_bytes", "retrieved_at"),
)
def test_screen_firecrawl_dockets_requires_raw_artifact_commitments(
    tmp_path: Path,
    cycle_state: _CycleState,
    missing_field: str,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    success = _success_record(raw_html)
    success.pop(missing_field)
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [success])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert not cycle_state.snapshot.exists()


def test_screen_firecrawl_dockets_rejects_anchor_drift_from_frozen_cycle(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("July 1, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-07-01",
                "--output-root",
                str(tmp_path / "screening"),
                "--execute",
            ]
        )
        == 2
    )
    assert not cycle_state.snapshot.exists()


def test_screen_firecrawl_dockets_rejects_screening_source_drift(
    tmp_path: Path,
) -> None:
    policy = _test_cycle_policy(anchor=date(2026, 6, 30))
    frozen_hashes = cast(dict[str, object], policy["screening_source_sha256"])
    frozen_hashes["motion_linkage"] = "0" * 64
    cycle_state = _create_cycle_state(tmp_path, policy=policy)
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(tmp_path / "screening"),
                "--execute",
            ]
        )
        == 2
    )
    assert not cycle_state.snapshot.exists()


def test_screen_firecrawl_dockets_rejects_existing_snapshot_target(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    cycle_state.snapshot.mkdir(parents=True)
    marker = cycle_state.snapshot / "do-not-reuse"
    marker.write_text("stale", encoding="utf-8")
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(tmp_path / "screening"),
                "--execute",
            ]
        )
        == 2
    )
    assert marker.read_text(encoding="utf-8") == "stale"


def test_screen_firecrawl_dockets_excludes_predecision_outcome_leakage(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = _docket_html(decision_dates=("June 30, 2026",)).replace(
        _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        ),
        _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        )
        + _entry_html(
            number=10,
            filed_at="June 20, 2026",
            text=(
                "REPORT AND RECOMMENDATION recommends granting the Motion to Dismiss"
            ),
            description="Report and Recommendation",
        ),
    )
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["stage"] == "leakage"
    assert exclusion["reason"] == "outcome_leakage"
    assert exclusion["source_entry_ids"] == ["entry-10"]


def test_screen_firecrawl_dockets_rechecks_persisted_privacy_metadata(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    successes = tmp_path / "successes.jsonl"
    record = _success_record()
    case_metadata = cast(dict[str, object], record["case_metadata"])
    case_metadata["is_sealed"] = True
    _write_jsonl(successes, [record])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(tmp_path / "missing-html"),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["stage"] == "discovery"
    assert exclusion["reason"] == "restricted_case_metadata"


def test_screen_firecrawl_dockets_scopes_leakage_to_linked_target_motion(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        _docket_html(decision_dates=("June 30, 2026",))
        .replace(
            "ORDER granting in part and denying in part Motion to Dismiss",
            "ORDER granting Motion to Dismiss at Docket 5",
        )
        .replace(
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
            ),
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
            )
            + _entry_html(
                number=8,
                filed_at="March 2, 2026",
                text="MOTION to Dismiss filed by Other Defendant",
                description="Motion to Dismiss",
            )
            + _entry_html(
                number=10,
                filed_at="June 20, 2026",
                text=(
                    "REPORT AND RECOMMENDATION recommends granting the Motion to "
                    "Dismiss at Docket 8"
                ),
                description="Report and Recommendation",
            ),
        )
    )
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [screened] = _read_jsonl(output_root / "firecrawl-screened-cases.jsonl")
    assert screened["ai"]["target_motion_entry_numbers"] == ["5"]
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []


def test_screen_firecrawl_dockets_excludes_ambiguous_unscoped_multi_mtd_leakage(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        _docket_html(decision_dates=("June 30, 2026",))
        .replace(
            "ORDER granting in part and denying in part Motion to Dismiss",
            "ORDER granting Motion to Dismiss at Docket 5",
        )
        .replace(
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
            ),
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
            )
            + _entry_html(
                number=8,
                filed_at="March 2, 2026",
                text="MOTION to Dismiss filed by Other Defendant",
                description="Motion to Dismiss",
            )
            + _entry_html(
                number=10,
                filed_at="June 20, 2026",
                text=(
                    "REPORT AND RECOMMENDATION recommends granting the Motion to "
                    "Dismiss"
                ),
                description="Report and Recommendation",
            ),
        )
    )
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(html)])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["stage"] == "leakage"
    assert exclusion["reason"] == "outcome_leakage"


def test_screen_firecrawl_dockets_namespaces_invalid_manifest_ledger_ids(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    invalid = _success_record(raw_html)
    invalid["candidate_id"] = "123"
    invalid["docket_id"] = "not-numeric"
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html), invalid])

    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(raw_html_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [screened] = _read_jsonl(output_root / "firecrawl-screened-cases.jsonl")
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert screened["candidate"]["docket_id"] == "123"
    assert exclusion["candidate_id"] == "firecrawl-manifest-row-2"


def _success_record(raw_html: str | None = None) -> dict[str, object]:
    content = raw_html or _docket_html(decision_dates=("June 30, 2026",))
    raw_bytes = content.encode()
    return {
        "case_id": "case-dev-123",
        "source_url": "https://www.courtlistener.com/docket/123/fixture/",
        "docket_id": "123",
        "raw_html_path": "ignored",
        "raw_html_sha256": f"sha256:{sha256(raw_bytes).hexdigest()}",
        "raw_html_bytes": len(raw_bytes),
        "retrieved_at": "2026-07-12T12:00:00+00:00",
        "case_metadata": {
            "case_id": "case-dev-123",
            "court_id": "nysd",
            "docket_number": "1:26-cv-00001",
            "case_name": "Fixture v. Example",
        },
    }


def _test_cycle_policy(*, anchor: date) -> dict[str, object]:
    package_root = Path(__file__).parents[1] / "legalforecast"
    screening_sources = {
        "mtd_acquisition_screen": package_root
        / "ingestion"
        / "mtd_acquisition_screen.py",
        "courtlistener_acquisition": package_root
        / "ingestion"
        / "courtlistener_acquisition.py",
        "restricted_material": package_root / "ingestion" / "restricted_material.py",
        "contamination_filters": package_root
        / "selection"
        / "contamination_filters.py",
        "motion_linkage": package_root / "selection" / "motion_linkage.py",
    }
    return {
        "schema_version": "legalforecast.case_dev_discovery_policy.v1",
        "eligibility_anchor": anchor.isoformat(),
        "query_terms": ["motion to dismiss"],
        "query_term_order_is_frozen": True,
        "screening_source_sha256": {
            name: sha256_file(path) for name, path in sorted(screening_sources.items())
        },
    }


def _docket_html(*, decision_dates: tuple[str, ...]) -> str:
    decisions = "".join(
        _entry_html(
            number=16 + index,
            filed_at=filed_at,
            text="ORDER granting in part and denying in part Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
        for index, filed_at in enumerate(decision_dates)
    )
    return (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=1,
            filed_at="January 2, 2026",
            text="COMPLAINT filed by Plaintiff",
            description="Complaint",
        )
        + _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        )
        + decisions
        + "</div></body></html>"
    )


def _entry_html(
    *,
    number: int,
    filed_at: str,
    text: str,
    description: str,
) -> str:
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents"><div>Main Document</div>'
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">'
        "Download PDF</a></div></div></div>"
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

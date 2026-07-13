from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_acquisition import _parse_filed_date
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


@pytest.mark.parametrize(
    "decision_text",
    (
        "ORDER granting 5 Motion to Dismiss",
        "ORDER granting Motion to Dismiss 5",
    ),
)
@pytest.mark.parametrize(
    "motion_description",
    (
        "Dismiss",
        "Dismiss AND Dismiss for Failure to State a Claim",
    ),
)
def test_screen_recovers_generic_dismiss_row_from_explicit_disposition_reference(
    tmp_path: Path,
    cycle_state: _CycleState,
    decision_text: str,
    motion_description: str,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
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
            text="Main Document",
            description=motion_description,
        )
        + _entry_html(
            number=16,
            filed_at="June 30, 2026",
            text=decision_text,
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
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
    assert screened["motion_linkage"]["links"][0]["linkage_basis"] == [
        "explicit_docket_entry_reference",
        "deterministic_earliest_eligible_target_motion",
    ]
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []


def test_screen_does_not_promote_unreferenced_generic_dismiss_row(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=6,
            filed_at="February 2, 2026",
            text="Main Document",
            description="Dismiss",
        )
        + _entry_html(
            number=16,
            filed_at="June 30, 2026",
            text="ORDER granting 5 Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
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

    assert _read_jsonl(output_root / "firecrawl-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["reason"] == "no_target_motion"


def test_screen_does_not_treat_case_number_as_mtd_entry_reference(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=24,
            filed_at="February 2, 2026",
            text="Main Document",
            description="Dismiss",
        )
        + _entry_html(
            number=30,
            filed_at="June 30, 2026",
            text="ORDER granting motion to dismiss in Civil Action No. 24-1234",
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
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

    assert _read_jsonl(output_root / "firecrawl-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["reason"] == "no_target_motion"


@pytest.mark.parametrize(
    "description",
    (
        "Dismiss/Joint or Voluntary",
        "Dismiss Appeal",
        "Dismiss Counterclaim",
        "Notice of Dismissal",
        "Dismiss AND Notice of Dismissal",
    ),
)
def test_screen_does_not_promote_explicitly_referenced_non_mtd_dismissal(
    tmp_path: Path,
    cycle_state: _CycleState,
    description: str,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="Main Document",
            description=description,
        )
        + _entry_html(
            number=16,
            filed_at="June 30, 2026",
            text="ORDER granting 5 Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
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

    assert _read_jsonl(output_root / "firecrawl-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["reason"] == "no_target_motion"


def test_screen_does_not_count_notice_of_compliance_as_second_mtd(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=26,
            filed_at="June 24, 2026",
            text="MOTION to Dismiss for Failure to State a Claim by Defendant",
            description="Dismiss for Failure to State a Claim",
        )
        + _entry_html(
            number=27,
            filed_at="June 25, 2026",
            text="NOTICE of compliance re 26 MOTION to Dismiss",
            description="Compliance notice",
        )
        + _entry_html(
            number=30,
            filed_at="June 30, 2026",
            text="Order on Motion to Dismiss for Failure to State a Claim",
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
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
    assert screened["ai"]["target_motion_entry_numbers"] == ["26"]
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []


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


def test_screen_counts_preanchor_report_as_first_written_disposition(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        )
        + _entry_html(
            number=15,
            filed_at="June 29, 2026",
            text=(
                "REPORT AND RECOMMENDATION re 5 Motion to Dismiss. The Court "
                "recommends that the motion be granted."
            ),
            description="Report and Recommendation",
        )
        + _entry_html(
            number=16,
            filed_at="July 1, 2026",
            text="ORDER adopting Report and Recommendation re 5 Motion to Dismiss",
            description="Order Adopting Report and Recommendation",
        )
        + "</div></body></html>"
    )
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
    assert exclusion["decision_date"] == "2026-06-29"
    assert exclusion["source_entry_ids"] == ["entry-15", "entry-16"]


@pytest.mark.parametrize(
    ("filed_at", "expected"),
    (
        ("July 10, 2026, noon", date(2026, 7, 10)),
        ("July 10, 2026, midnight", date(2026, 7, 10)),
        ("July 10, 2026, 1:48 p.m.", date(2026, 7, 10)),
        ("July 10, 2026, 8 a.m.", date(2026, 7, 10)),
        ("Feb. 26, 2026, 10:21 a.m.", date(2026, 2, 26)),
    ),
)
def test_courtlistener_timestamp_dates_preserve_calendar_date(
    filed_at: str, expected: date
) -> None:
    assert _parse_filed_date(filed_at) == expected


@pytest.mark.parametrize(
    "filed_at",
    (
        "July 10, 2026, breakfast",
        "July 10, 2026, 25:00 p.m.",
        "not a date",
        "",
    ),
)
def test_courtlistener_invalid_timestamp_dates_remain_unparseable(
    filed_at: str,
) -> None:
    assert _parse_filed_date(filed_at) is None


def test_screen_firecrawl_dockets_preserves_fetch_exclusions_in_public_ledger(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [])
    fetch_exclusions = Path(
        cycle_state.cli_args[cycle_state.cli_args.index("--fetch-exclusions") + 1]
    )
    fetch_exclusion = {
        "case_id": "case-dev-123",
        "docket_id": "123",
        "reason": "provider_circuit_open",
    }
    _write_jsonl(fetch_exclusions, [fetch_exclusion])

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

    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == [
        fetch_exclusion
    ]
    summary = _read_json(output_root / "firecrawl-screening-summary.json")
    assert summary["input_fetch_exclusion_count"] == 1
    assert summary["excluded_case_count"] == 1
    assert summary["reconciled"] is True


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
    (
        "raw_html_sha256",
        "raw_html_bytes",
        "retrieved_at",
        "pagination_complete_for_anchor_window",
    ),
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


def test_screen_excludes_preanchor_report_before_leakage_screening(
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
            extra_document_description="Memorandum in Support of Motion to Dismiss",
        ),
        _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
            extra_document_description="Memorandum in Support of Motion to Dismiss",
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
    assert exclusion["stage"] == "eligibility"
    assert exclusion["reason"] == "decision_before_release_anchor"
    assert exclusion["decision_date"] == "2026-06-20"


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


def test_screen_applies_case_anchor_before_target_scoped_leakage(
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
                extra_document_description="Memorandum in Support of Motion to Dismiss",
            ),
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
                extra_document_description="Memorandum in Support of Motion to Dismiss",
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

    assert _read_jsonl(output_root / "firecrawl-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl")
    assert exclusion["stage"] == "eligibility"
    assert exclusion["reason"] == "decision_before_release_anchor"
    assert exclusion["decision_date"] == "2026-06-20"


def test_screen_excludes_preanchor_unscoped_report_for_eligibility(
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
                extra_document_description="Memorandum in Support of Motion to Dismiss",
            ),
            _entry_html(
                number=5,
                filed_at="February 2, 2026",
                text="MOTION to Dismiss filed by Defendant",
                description="Motion to Dismiss",
                extra_document_description="Memorandum in Support of Motion to Dismiss",
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
    assert exclusion["stage"] == "eligibility"
    assert exclusion["reason"] == "decision_before_release_anchor"
    assert exclusion["decision_date"] == "2026-06-20"


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
        "pagination_complete_for_anchor_window": True,
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
            extra_document_description="Memorandum in Support of Motion to Dismiss",
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
    extra_document_description: str | None = None,
) -> str:
    extra_document = (
        ""
        if extra_document_description is None
        else (
            '<div class="row recap-documents"><div>Attachment 1</div>'
            f"<div>{extra_document_description}</div>"
            f'<a href="https://storage.courtlistener.com/{number}-memo.pdf">'
            "Download PDF</a></div>"
        )
    )
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents"><div>Main Document</div>'
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">'
        f"Download PDF</a></div>{extra_document}</div></div>"
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

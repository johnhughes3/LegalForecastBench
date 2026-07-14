from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import (
    CommandError,
    _verified_snapshot_raw_html_sources,
    main,
)
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
    store_path: Path
    batch_id: str
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
        store_path=store_path,
        batch_id=batch_id,
        snapshot=snapshot_root / snapshot_id,
        cycle_hash=cycle_hash,
        batch_digest=batch_digest,
    )


def test_verified_snapshot_raw_html_sources_maps_multiple_directories(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    first = tmp_path / "first" / "123.html"
    second = tmp_path / "second" / "456.html"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("<html>first</html>", encoding="utf-8")
    second.write_text("<html>second</html>", encoding="utf-8")
    _write_jsonl(
        snapshot / "raw-artifacts.jsonl",
        [
            {"candidate_id": "courtlistener-docket-123", "path": str(first)},
            {"candidate_id": "courtlistener-docket-456", "path": str(second)},
        ],
    )

    directory, paths = _verified_snapshot_raw_html_sources(
        snapshot,
        requested=None,
        use_embedded_entries=False,
    )

    assert directory is None
    assert paths == {"123": first.resolve(), "456": second.resolve()}


def test_verified_snapshot_raw_html_sources_rejects_duplicate_candidate_paths(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    first = tmp_path / "first" / "123.html"
    second = tmp_path / "second" / "123.html"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("<html>first</html>", encoding="utf-8")
    second.write_text("<html>second</html>", encoding="utf-8")
    _write_jsonl(
        snapshot / "raw-artifacts.jsonl",
        [
            {"candidate_id": "case-dev-first", "path": str(first)},
            {"candidate_id": "case-dev-second", "path": str(second)},
        ],
    )

    with pytest.raises(CommandError, match="conflict for candidate 123"):
        _verified_snapshot_raw_html_sources(
            snapshot,
            requested=None,
            use_embedded_entries=False,
        )


def test_verified_snapshot_raw_html_sources_selects_requested_refresh_directory(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    first = tmp_path / "first-refresh" / "123.html"
    second = tmp_path / "second-refresh" / "123.html"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("<html>first</html>", encoding="utf-8")
    second.write_text("<html>second</html>", encoding="utf-8")
    _write_jsonl(
        snapshot / "raw-artifacts.jsonl",
        [
            {"candidate_id": "courtlistener-docket-123", "path": str(first)},
            {"candidate_id": "courtlistener-docket-123", "path": str(second)},
        ],
    )

    directory, paths = _verified_snapshot_raw_html_sources(
        snapshot,
        requested=second.parent,
        use_embedded_entries=False,
    )

    assert directory is None
    assert paths == {"123": second.resolve()}


def test_verified_snapshot_raw_html_sources_preserves_other_committed_directories(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    old_duplicate = tmp_path / "old-refresh" / "123.html"
    new_duplicate = tmp_path / "new-refresh" / "123.html"
    old_only = tmp_path / "old-refresh" / "456.html"
    old_duplicate.parent.mkdir()
    new_duplicate.parent.mkdir()
    old_duplicate.write_text("<html>old 123</html>", encoding="utf-8")
    new_duplicate.write_text("<html>new 123</html>", encoding="utf-8")
    old_only.write_text("<html>old 456</html>", encoding="utf-8")
    _write_jsonl(
        snapshot / "raw-artifacts.jsonl",
        [
            {"candidate_id": "courtlistener-docket-123", "path": str(old_duplicate)},
            {"candidate_id": "courtlistener-docket-123", "path": str(new_duplicate)},
            {"candidate_id": "courtlistener-docket-456", "path": str(old_only)},
        ],
    )

    directory, paths = _verified_snapshot_raw_html_sources(
        snapshot,
        requested=new_duplicate.parent,
        use_embedded_entries=False,
    )

    assert directory is None
    assert paths == {"123": new_duplicate.resolve(), "456": old_only.resolve()}


def test_verified_snapshot_raw_html_sources_rejects_uncommitted_requested_directory(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    committed = tmp_path / "committed" / "123.html"
    committed.parent.mkdir()
    committed.write_text("<html>committed</html>", encoding="utf-8")
    _write_jsonl(
        snapshot / "raw-artifacts.jsonl",
        [{"candidate_id": "courtlistener-docket-123", "path": str(committed)}],
    )

    with pytest.raises(CommandError, match="exactly match a committed"):
        _verified_snapshot_raw_html_sources(
            snapshot,
            requested=tmp_path / "uncommitted",
            use_embedded_entries=False,
        )


def test_metadata_rich_firecrawl_rescreen_replaces_absent_metadata_snapshot_state(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        store.record_observation(
            "case-dev-123",
            batch_id=cycle_state.batch_id,
            state="excluded",
            reason_code="not_federal_district_court",
            evidence={
                "candidate_id": "case-dev-123",
                "case_id": "case-dev-123",
                "court": None,
                "decision_date": None,
                "primary_exclusion_reason": "not_federal_district_court",
                "reason": "not_federal_district_court",
                "secondary_exclusion_reasons": ["missing_docket_number"],
                "source_document_ids": [],
                "source_entry_ids": [],
                "stage": "discovery",
            },
        )

    output_root = tmp_path / "screening"
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
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [snapshot_case] = _read_jsonl(cycle_state.snapshot / "screened-cases.jsonl")
    assert snapshot_case["candidate_id"] == "case-dev-123"
    assert _read_jsonl(cycle_state.snapshot / "exclusions.jsonl") == []
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observations = store.observations("case-dev-123")
        assert [observation.state for observation in observations] == [
            "excluded",
            "accepted",
        ]
        assert store.current_observation("case-dev-123") == observations[-1]


def test_metadata_repair_proof_mismatch_remains_reconciled_parse_exclusion(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    successes = tmp_path / "successes.jsonl"
    success = _success_record()
    metadata = cast(dict[str, object], success["case_metadata"])
    metadata["case_id"] = "different-case"
    _write_jsonl(successes, [success])

    output_root = tmp_path / "screening"
    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                *cycle_state.cli_args,
                "--successes",
                str(successes),
                "--raw-html-dir",
                str(tmp_path / "unused-html"),
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
    assert exclusion["case_id"] == "case-dev-123"
    assert exclusion["reason"] == "parse_error"
    assert _read_jsonl(cycle_state.snapshot / "screened-cases.jsonl") == []
    [snapshot_exclusion] = _read_jsonl(cycle_state.snapshot / "exclusions.jsonl")
    assert snapshot_exclusion["candidate_id"] == "case-dev-123"


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
            text="ORDER granting 26 Motion to Dismiss for Failure to State a Claim",
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


def test_generic_order_event_does_not_precede_explicit_disposition_anchor(
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
            text="Main Document Order on Motion to Dismiss Buy on PACER",
            description="Order on Motion to Dismiss",
        )
        + _entry_html(
            number=16,
            filed_at="July 1, 2026",
            text="ORDER denying 5 Motion to Dismiss",
            description="Order on Motion to Dismiss",
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

    [screened] = _read_jsonl(output_root / "firecrawl-screened-cases.jsonl")
    assert screened["first_written_mtd_disposition_date"] == "2026-07-01"
    assert screened["ai"]["decision_entry_numbers"] == ["16"]
    assert screened["ai"]["target_motion_entry_numbers"] == ["5"]
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []


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
    assert exclusion["source_entry_ids"] == ["entry-15"]


@pytest.mark.parametrize(
    ("docket_id", "procedural_date", "procedural_text", "decision_date"),
    (
        (
            "71280017",
            "November 19, 2025",
            (
                "ORDER: Plaintiffs' Unopposed Motion [Doc. 23] is GRANTED. "
                "Plaintiffs' deadline to respond to the pending Motion to "
                "Dismiss is extended through December 1, 2025."
            ),
            "July 1, 2026",
        ),
        (
            "72283240",
            "April 21, 2026",
            (
                "ORDER Granting 17 Motion to Stay Discovery. The parties shall "
                "file a discovery plan after entry of an order adjudicating "
                "defendant's 5 Motion to Dismiss."
            ),
            "July 7, 2026",
        ),
    ),
)
def test_screen_does_not_make_preanchor_procedural_relief_first_disposition(
    tmp_path: Path,
    cycle_state: _CycleState,
    docket_id: str,
    procedural_date: str,
    procedural_text: str,
    decision_date: str,
) -> None:
    output_root = tmp_path / "screening"
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=5,
            filed_at="October 1, 2025",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        )
        + _entry_html(
            number=17,
            filed_at=procedural_date,
            text=procedural_text,
            description="Order",
        )
        + _entry_html(
            number=22,
            filed_at=decision_date,
            text="ORDER granting in part and denying in part 5 Motion to Dismiss",
            description="Order on Motion to Dismiss",
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
    ), docket_id

    [screened] = _read_jsonl(output_root / "firecrawl-screened-cases.jsonl")
    expected_decision_date = _parse_filed_date(decision_date)
    assert expected_decision_date is not None
    assert screened["first_written_mtd_disposition_date"] == (
        expected_decision_date.isoformat()
    )
    assert screened["ai"]["decision_entry_numbers"] == ["22"]
    assert _read_jsonl(output_root / "firecrawl-screening-exclusions.jsonl") == []


def test_screen_rejects_court_order_event_without_outcome_text(
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
            filed_at="November 6, 2025",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
        )
        + _entry_html(
            number=17,
            filed_at="November 7, 2025",
            text=(
                "ORDER Response/Briefing Schedule re 5 Motion to Dismiss. "
                "Plaintiff's response is due November 26, 2025."
            ),
            description="Order",
        )
        + _entry_html(
            number=26,
            filed_at="July 9, 2026",
            text="Order on Motion to Dismiss for Failure to State a Claim",
            description="Order on Motion to Dismiss",
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
    assert exclusion["reason"] == "motion_filing_only"
    assert exclusion["secondary_exclusion_reasons"] == [
        "procedural_or_standing_order",
        "mtd_disposition_unproven",
    ]


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


def test_screen_firecrawl_dockets_resume_reuses_exact_complete_snapshot(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]

    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    snapshot_before = {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    }
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observation_ids_before = tuple(
            observation.observation_id
            for observation in store.observations("case-dev-123")
        )

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 0

    assert {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    } == snapshot_before
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        assert (
            tuple(
                observation.observation_id
                for observation in store.observations("case-dev-123")
            )
            == observation_ids_before
        )
    [screened] = _read_jsonl(resumed_output / "firecrawl-screened-cases.jsonl")
    assert screened["candidate_id"] == "case-dev-123"
    summary = json.loads(
        (resumed_output / "firecrawl-screening-summary.json").read_text()
    )
    assert summary["resumed_existing_snapshot"] is True
    assert summary["accepted_case_count"] == 1


def test_screen_resume_run_card_records_committed_snapshot_path(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    snapshot_root_link = tmp_path / "snapshot-root-link"
    snapshot_root_link.symlink_to(cycle_state.snapshot.parent, target_is_directory=True)
    resumed_output = tmp_path / "resumed"

    assert (
        main(
            [
                *base_command,
                "--snapshot-root",
                str(snapshot_root_link),
                "--output-root",
                str(resumed_output),
            ]
        )
        == 0
    )

    run_card = _read_json(resumed_output / "run-cards/screen-firecrawl-dockets.json")
    assert run_card["output_paths"][-1] == str(cycle_state.snapshot.resolve())


def test_screen_resume_rejects_snapshot_manifest_mismatch_before_store_writes(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    manifest_path = cycle_state.snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["created_at"] = "2026-07-13T23:59:59Z"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    snapshot_before = {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    }
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observation_ids_before = tuple(
            observation.observation_id
            for observation in store.observations("case-dev-123")
        )

    assert main([*base_command, "--output-root", str(tmp_path / "resumed")]) == 2

    assert {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    } == snapshot_before
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        assert (
            tuple(
                observation.observation_id
                for observation in store.observations("case-dev-123")
            )
            == observation_ids_before
        )


def test_screen_resume_rejects_committed_id_at_different_path_before_writes(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    canonical_before = {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    }
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observation_ids_before = tuple(
            observation.observation_id
            for observation in store.observations("case-dev-123")
        )

    wrong_root = tmp_path / "wrong-snapshot-root"
    assert (
        main(
            [
                *base_command,
                "--snapshot-root",
                str(wrong_root),
                "--output-root",
                str(tmp_path / "resumed"),
            ]
        )
        == 2
    )

    assert not wrong_root.exists()
    assert {
        path.name: path.read_bytes()
        for path in cycle_state.snapshot.iterdir()
        if path.is_file()
    } == canonical_before
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        assert (
            tuple(
                observation.observation_id
                for observation in store.observations("case-dev-123")
            )
            == observation_ids_before
        )


def test_screen_resume_rejects_malformed_success_commitment_before_output_writes(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    malformed = _success_record(raw_html)
    malformed["raw_html_sha256"] = "not-a-commitment"
    _write_jsonl(successes, [malformed])
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observation_ids_before = tuple(
            observation.observation_id
            for observation in store.observations("case-dev-123")
        )

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 2

    assert not (resumed_output / "firecrawl-screened-cases.jsonl").exists()
    assert not (resumed_output / "firecrawl-screening-summary.json").exists()
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        assert (
            tuple(
                observation.observation_id
                for observation in store.observations("case-dev-123")
            )
            == observation_ids_before
        )


def test_screen_resume_rejects_changed_input_candidate_set_before_output_writes(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    unrelated = _success_record(raw_html)
    unrelated["case_id"] = "case-dev-unrelated"
    _write_jsonl(successes, [unrelated])
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        observation_ids_before = tuple(
            observation.observation_id
            for observation in store.observations("case-dev-123")
        )

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 2

    assert not (resumed_output / "firecrawl-screened-cases.jsonl").exists()
    assert not (resumed_output / "firecrawl-screening-summary.json").exists()
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        assert (
            tuple(
                observation.observation_id
                for observation in store.observations("case-dev-123")
            )
            == observation_ids_before
        )


def test_screen_resume_rejects_success_changed_to_fetch_exclusion(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    fetch_exclusions = tmp_path / "fetch-exclusions.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    _write_jsonl(fetch_exclusions, [])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--fetch-exclusions",
        str(fetch_exclusions),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    _write_jsonl(successes, [])
    _write_jsonl(
        fetch_exclusions,
        [{"case_id": "case-dev-123", "reason": "criminal_posture"}],
    )

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 2

    assert not (resumed_output / "firecrawl-screened-cases.jsonl").exists()
    assert not (resumed_output / "firecrawl-screening-summary.json").exists()


def test_screen_resume_rejects_changed_fetch_exclusion_reason_or_evidence(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    successes = tmp_path / "successes.jsonl"
    fetch_exclusions = tmp_path / "fetch-exclusions.jsonl"
    _write_jsonl(successes, [])
    exclusion = {
        "case_id": "case-dev-123",
        "reason": "criminal_posture",
        "provider_evidence": {"status": "initial"},
    }
    _write_jsonl(fetch_exclusions, [exclusion])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--fetch-exclusions",
        str(fetch_exclusions),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    exclusion["reason"] = "bankruptcy_posture"
    exclusion["provider_evidence"] = {"status": "changed"}
    _write_jsonl(fetch_exclusions, [exclusion])

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 2

    assert not (resumed_output / "firecrawl-screening-exclusions.jsonl").exists()
    assert not (resumed_output / "firecrawl-screening-summary.json").exists()


def test_screen_resume_rejects_changed_success_metadata(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    success = _success_record(raw_html)
    _write_jsonl(successes, [success])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    success["source_url"] = "https://www.courtlistener.com/docket/123/changed/"
    _write_jsonl(successes, [success])

    resumed_output = tmp_path / "resumed"
    assert main([*base_command, "--output-root", str(resumed_output)]) == 2

    assert not (resumed_output / "firecrawl-screened-cases.jsonl").exists()
    assert not (resumed_output / "firecrawl-screening-summary.json").exists()


@pytest.mark.parametrize(
    "output_flag",
    [
        "--screened-cases-output",
        "--exclusions-output",
        "--summary-output",
        "--run-card-output",
        "--log-output",
    ],
)
def test_screen_resume_rejects_every_writable_output_inside_snapshot(
    tmp_path: Path,
    cycle_state: _CycleState,
    output_flag: str,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    snapshot_before = {
        path.relative_to(cycle_state.snapshot): path.read_bytes()
        for path in cycle_state.snapshot.rglob("*")
        if path.is_file()
    }
    unsafe_output = cycle_state.snapshot / "unsafe" / "output.json"

    assert (
        main(
            [
                *base_command,
                output_flag,
                str(unsafe_output),
                "--output-root",
                str(tmp_path / "resumed"),
            ]
        )
        == 2
    )

    assert not unsafe_output.exists()
    assert {
        path.relative_to(cycle_state.snapshot): path.read_bytes()
        for path in cycle_state.snapshot.rglob("*")
        if path.is_file()
    } == snapshot_before


def test_screen_resume_rejects_output_root_inside_snapshot_before_creation(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    unsafe_root = cycle_state.snapshot / "unsafe-output-root"

    assert main([*base_command, "--output-root", str(unsafe_root)]) == 2

    assert not unsafe_root.exists()


def test_screen_resume_rejects_output_root_inside_snapshot_with_redirected_outputs(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]
    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    snapshot_before = {
        path.relative_to(cycle_state.snapshot): path.read_bytes()
        for path in cycle_state.snapshot.rglob("*")
        if path.is_file()
    }
    unsafe_root = cycle_state.snapshot / "redirected-output-root"
    redirected_root = tmp_path / "redirected"

    assert (
        main(
            [
                *base_command,
                "--output-root",
                str(unsafe_root),
                "--screened-cases-output",
                str(redirected_root / "screened.jsonl"),
                "--exclusions-output",
                str(redirected_root / "exclusions.jsonl"),
                "--summary-output",
                str(redirected_root / "summary.json"),
                "--run-card-output",
                str(redirected_root / "run-card.json"),
                "--log-output",
                str(redirected_root / "log.jsonl"),
            ]
        )
        == 2
    )

    assert not unsafe_root.exists()
    assert not redirected_root.exists()
    assert {
        path.relative_to(cycle_state.snapshot): path.read_bytes()
        for path in cycle_state.snapshot.rglob("*")
        if path.is_file()
    } == snapshot_before


def test_screen_resume_uses_snapshot_level_commitment_when_observation_is_immutable(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    with CycleAcquisitionStore(cycle_state.store_path) as store:
        store.record_observation(
            "case-dev-123",
            batch_id=cycle_state.batch_id,
            state="excluded",
            reason_code="criminal_case",
            evidence={"candidate_id": "case-dev-123", "source": "frozen"},
        )
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    success = _success_record(raw_html)
    _write_jsonl(successes, [success])
    base_command = [
        "acquisition",
        "screen-firecrawl-dockets",
        *cycle_state.cli_args,
        "--successes",
        str(successes),
        "--raw-html-dir",
        str(raw_html_dir),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--execute",
    ]

    assert main([*base_command, "--output-root", str(tmp_path / "first")]) == 0
    manifest = json.loads((cycle_state.snapshot / "manifest.json").read_text())
    assert "firecrawl_screen_inputs" in manifest["stage_commitments"]
    assert main([*base_command, "--output-root", str(tmp_path / "resume")]) == 0

    success["source_url"] = "https://www.courtlistener.com/docket/123/drifted/"
    _write_jsonl(successes, [success])
    assert main([*base_command, "--output-root", str(tmp_path / "drift")]) == 2


def test_fresh_screen_rejects_prospective_output_root_inside_snapshot(
    tmp_path: Path,
    cycle_state: _CycleState,
) -> None:
    raw_html_dir = tmp_path / "html"
    raw_html_dir.mkdir()
    raw_html = _docket_html(decision_dates=("June 30, 2026",))
    (raw_html_dir / "123.html").write_text(raw_html, encoding="utf-8")
    successes = tmp_path / "successes.jsonl"
    _write_jsonl(successes, [_success_record(raw_html)])
    unsafe_root = cycle_state.snapshot / "prospective-output"

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
                str(unsafe_root),
                "--execute",
            ]
        )
        == 2
    )

    assert not cycle_state.snapshot.exists()


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

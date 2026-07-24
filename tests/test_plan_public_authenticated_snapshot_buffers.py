"""TOCTOU regressions for direct public-download snapshot consumption."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import pytest
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads
from tests.test_courtlistener_acquisition_cli import _docket_html
from tests.test_rest_priority_subset_promotion import _strict_screen_evidence


def _snapshot(
    root: Path,
    *,
    store_path: Path,
    batch_id: str,
    candidate_id: str,
) -> tuple[Path, str]:
    term = f"fixture-{batch_id}"
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle(
            {"eligibility_anchor": "2026-06-30", "fixture": True}
        )
        store.ensure_batch(batch_id, {"provider": "courtlistener"})
        store.ensure_terms(batch_id, (term,))
        store.commit_search_page(
            batch_id,
            term,
            None,
            (
                DiscoveryHit(
                    provider_hit_id=f"hit-{candidate_id}",
                    candidate_id=candidate_id,
                    payload={"candidate_id": candidate_id},
                ),
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        store.record_observation(
            candidate_id,
            batch_id=batch_id,
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence=_strict_screen_evidence(candidate_id),
            observed_at="2026-07-24T12:00:00+00:00",
        )
        snapshot = store.export_snapshot(
            root,
            snapshot_id=f"{batch_id}-snapshot",
            batch_id=batch_id,
            complete=True,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )
    return snapshot, cycle_hash


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _swap_snapshot_files(*, source: Path, target: Path) -> None:
    filenames = (
        "screened-cases.jsonl",
        "exclusions.jsonl",
        "summary.json",
        "candidates.jsonl",
        "observations.jsonl",
        "raw-artifacts.jsonl",
        "manifest.json",
    )
    for filename in filenames:
        shutil.copyfile(source / filename, target / filename)


def _command(
    *,
    snapshot: Path,
    manifest_sha256: str,
    cycle_hash: str,
    output_root: Path,
) -> list[str]:
    return [
        "acquisition",
        "plan-public-downloads",
        "--snapshot",
        str(snapshot),
        "--expected-snapshot-manifest-sha256",
        manifest_sha256,
        "--expected-cycle-hash",
        cycle_hash,
        "--target-clean-cases",
        "1",
        "--use-embedded-entries",
        "--output-root",
        str(output_root),
        "--execute",
    ]


def test_plan_public_rejects_swap_after_external_pin_before_buffered_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    original, cycle_hash = _snapshot(
        tmp_path / "original",
        store_path=store_path,
        batch_id="original",
        candidate_id="courtlistener-docket-101",
    )
    replacement, _ = _snapshot(
        tmp_path / "replacement",
        store_path=store_path,
        batch_id="replacement",
        candidate_id="courtlistener-docket-202",
    )
    expected_manifest_sha256 = _manifest_sha256(original)
    validate_pin = cli_module._validate_external_snapshot_manifest_pin

    def validate_then_swap(snapshot: Path, expected_sha256: str) -> str:
        result = validate_pin(snapshot, expected_sha256)
        _swap_snapshot_files(source=replacement, target=original)
        return result

    monkeypatch.setattr(
        cli_module,
        "_validate_external_snapshot_manifest_pin",
        validate_then_swap,
    )

    assert (
        cli_module.main(
            _command(
                snapshot=original,
                manifest_sha256=expected_manifest_sha256,
                cycle_hash=cycle_hash,
                output_root=tmp_path / "rejected",
            )
        )
        == 2
    )
    assert not (tmp_path / "rejected/public-packet-selection.jsonl").exists()


def test_public_planner_consumes_authenticated_raw_html_bytes_without_paths() -> None:
    candidate_id = "courtlistener-docket-101"

    plan = plan_public_packet_downloads(
        (_strict_screen_evidence(candidate_id),),
        raw_html_bytes_by_candidate={
            "101": _docket_html(decision_dates=("June 30, 2026",)).encode("utf-8")
        },
        target_clean_cases=1,
    )

    assert plan.screened_case_count == 1
    assert [row.case_id for row in plan.planned_cases] == [candidate_id]


def test_plan_public_consumes_buffers_when_paths_swap_after_verify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    original_id = "courtlistener-docket-101"
    replacement_id = "courtlistener-docket-202"
    original, cycle_hash = _snapshot(
        tmp_path / "original",
        store_path=store_path,
        batch_id="original",
        candidate_id=original_id,
    )
    replacement, _ = _snapshot(
        tmp_path / "replacement",
        store_path=store_path,
        batch_id="replacement",
        candidate_id=replacement_id,
    )
    expected_manifest_sha256 = _manifest_sha256(original)
    load_snapshot = cli_module.load_verified_screening_snapshot

    def load_then_swap(*args: Any, **kwargs: Any) -> Any:
        result = load_snapshot(*args, **kwargs)
        _swap_snapshot_files(source=replacement, target=original)
        return result

    monkeypatch.setattr(
        cli_module,
        "load_verified_screening_snapshot",
        load_then_swap,
    )
    output_root = tmp_path / "accepted"

    assert (
        cli_module.main(
            _command(
                snapshot=original,
                manifest_sha256=expected_manifest_sha256,
                cycle_hash=cycle_hash,
                output_root=output_root,
            )
        )
        == 0
    )
    planned = [
        json.loads(line)
        for line in (output_root / "public-packet-paid-gaps.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["case_id"] for row in planned] == [original_id]
    assert replacement_id not in (
        output_root / "public-packet-paid-gaps.jsonl"
    ).read_text(encoding="utf-8")

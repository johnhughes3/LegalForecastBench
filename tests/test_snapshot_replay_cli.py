from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.protocol.freeze import sha256_file

ANCHOR = "2026-06-30"


def test_replay_screening_snapshots_is_provider_free_and_globally_plannable(
    tmp_path: Path,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("101",),
        fetch_exclusions=("102",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("101", "103"),
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"

    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    output_root = tmp_path / "replay"
    snapshot_id = "global-replay"
    command = _replay_command(
        output_root=output_root,
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=source_cycle_hash,
        assembly_run_card=assembly_run_card,
        snapshot_id=snapshot_id,
    )

    assert main(command) == 0

    snapshot = output_root / "snapshots" / snapshot_id
    manifest = verify_snapshot(
        snapshot,
        expected_cycle_hash=target_cycle_hash,
        require_saturated=True,
    )
    assert (
        manifest["stage_commitments"]["source_bound_replay"]["source_candidate_count"]
        == 3
    )
    summary = _read_json(snapshot / "summary.json")
    assert summary == {
        "accepted_count": 2,
        "batch_id": "superseding-replay",
        "excluded_count": 1,
        "processed_count": 3,
        "reconciliation_complete": True,
    }
    assert {
        row["candidate_id"] for row in _read_jsonl(snapshot / "screened-cases.jsonl")
    } == {"case-dev-101", "case-dev-103"}
    [excluded] = _read_jsonl(snapshot / "exclusions.jsonl")
    assert excluded["candidate_id"] == "case-dev-102"
    assert excluded["primary_exclusion_reason"] == "decision_before_release_anchor"
    run_card = _read_json(output_root / "run-cards/replay-screening-snapshots.json")
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False

    public_plan = tmp_path / "public-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--output-root",
                str(public_plan),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                target_cycle_hash,
                "--target-clean-cases",
                "2",
                "--execute",
            ]
        )
        == 0
    )
    assert (
        _read_json(public_plan / "public-packet-plan-summary.json")[
            "screened_case_count"
        ]
        == 2
    )


def test_replay_screening_snapshots_combines_explicit_target_cycle_snapshot(
    tmp_path: Path,
) -> None:
    old_policy = _cycle_policy(extra={"fixture_generation": "old"})
    old_snapshot = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "old.sqlite3",
        policy=old_policy,
        batch_id="old-source",
        successes=("151",),
    )
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                str(verify_snapshot(old_snapshot)["cycle_hash"]),
                "--batch-root",
                str(old_snapshot),
                "--execute",
            ]
        )
        == 0
    )
    current_policy = _cycle_policy()
    current_snapshot = _source_snapshot(
        tmp_path,
        store_path=tmp_path / "current-source.sqlite3",
        policy=current_policy,
        batch_id="current-source",
        successes=("152",),
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(current_policy)
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=target_cycle_hash,
        source_cycle_hash=str(verify_snapshot(old_snapshot)["cycle_hash"]),
        assembly_run_card=assembly_run_card,
        snapshot_id="combined-replay",
    )
    command.extend(("--source-snapshot", str(current_snapshot)))

    assert main(command) == 0

    manifest = verify_snapshot(
        tmp_path / "replay/snapshots/combined-replay",
        expected_cycle_hash=target_cycle_hash,
        require_saturated=True,
    )
    stage_commitments = cast(dict[str, Any], manifest["stage_commitments"])
    replay_commitment = cast(dict[str, Any], stage_commitments["source_bound_replay"])
    assert replay_commitment["source_snapshot_count"] == 2


@pytest.mark.parametrize(
    ("mutation", "error_pattern"),
    (
        ("assembly_hash", "source assembly SHA-256 mismatch"),
        ("source_cycle", "source snapshot cycle hash mismatch"),
        ("target_cycle", "target cycle hash mismatch"),
        ("raw_html", "raw artifact"),
        ("missing_raw", "raw artifact"),
        ("symlink_raw", "symlink"),
    ),
)
def test_replay_screening_snapshots_rejects_unbound_or_unsafe_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    error_pattern: str,
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    source = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source",
        successes=("201",),
    )
    source_cycle_hash = str(verify_snapshot(source)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(source),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())
    command = _replay_command(
        output_root=tmp_path / "replay",
        target_store=target_store,
        target_cycle_hash=(
            "0" * 64 if mutation == "target_cycle" else target_cycle_hash
        ),
        source_cycle_hash=(
            "1" * 64 if mutation == "source_cycle" else source_cycle_hash
        ),
        assembly_run_card=assembly_run_card,
        snapshot_id="rejected-replay",
        expected_assembly_sha256=(
            "2" * 64 if mutation == "assembly_hash" else sha256_file(assembly_run_card)
        ),
    )
    if mutation == "raw_html":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        raw_path.write_text("tampered", encoding="utf-8")
    elif mutation == "missing_raw":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        raw_path.unlink()
    elif mutation == "symlink_raw":
        raw_path = Path(_read_jsonl(source / "raw-artifacts.jsonl")[0]["path"])
        original = raw_path.with_suffix(".original")
        raw_path.rename(original)
        raw_path.symlink_to(original)

    assert main(command) == 2
    assert error_pattern in capsys.readouterr().err
    assert not (tmp_path / "replay/snapshots/rejected-replay").exists()


def test_replay_screening_snapshots_rejects_conflicting_overlap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("301",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("301",),
        decision_text="ORDER denying Motion to Dismiss",
    )
    source_cycle_hash = str(verify_snapshot(first)["cycle_hash"])
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                source_cycle_hash,
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    assembly_run_card = assembly_root / "run-cards/assemble-cycle-acquisition.json"
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=source_cycle_hash,
                assembly_run_card=assembly_run_card,
                snapshot_id="conflicting-replay",
            )
        )
        == 2
    )
    assert (
        "conflicting raw artifacts for candidate case-dev-301"
        in capsys.readouterr().err
    )


def test_replay_screening_snapshots_rejects_docket_identity_collision(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_store = tmp_path / "source.sqlite3"
    source_policy = _cycle_policy(extra={"fixture_generation": "old"})
    first = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-one",
        successes=("401",),
    )
    second = _source_snapshot(
        tmp_path,
        store_path=source_store,
        policy=source_policy,
        batch_id="source-two",
        successes=("401",),
        candidate_ids={"401": "case-dev-collision"},
    )
    assembly_root = tmp_path / "source-assembly"
    assert (
        main(
            [
                "acquisition",
                "assemble-cycle-acquisition",
                "--output-root",
                str(assembly_root),
                "--expected-cycle-hash",
                str(verify_snapshot(first)["cycle_hash"]),
                "--batch-root",
                str(first),
                "--batch-root",
                str(second),
                "--execute",
            ]
        )
        == 0
    )
    target_store = tmp_path / "target.sqlite3"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.ensure_cycle(_cycle_policy())

    assert (
        main(
            _replay_command(
                output_root=tmp_path / "replay",
                target_store=target_store,
                target_cycle_hash=target_cycle_hash,
                source_cycle_hash=str(verify_snapshot(first)["cycle_hash"]),
                assembly_run_card=(
                    assembly_root / "run-cards/assemble-cycle-acquisition.json"
                ),
                snapshot_id="colliding-replay",
            )
        )
        == 2
    )
    assert "docket ID collision" in capsys.readouterr().err


def test_replay_screening_snapshots_help_states_no_provider_semantics(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "replay-screening-snapshots", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "never contacts a provider" in output
    assert "--expected-source-assembly-sha256" in output
    assert "--expected-target-cycle-hash" in output
    assert "--source-snapshot" in output


def _source_snapshot(
    tmp_path: Path,
    *,
    store_path: Path,
    policy: dict[str, object],
    batch_id: str,
    successes: tuple[str, ...],
    fetch_exclusions: tuple[str, ...] = (),
    decision_text: str = "ORDER granting Motion to Dismiss",
    candidate_ids: dict[str, str] | None = None,
) -> Path:
    batch_root = tmp_path / batch_id
    raw_dir = batch_root / "raw-docket-html"
    raw_dir.mkdir(parents=True)
    success_records: list[dict[str, object]] = []
    hits: list[DiscoveryHit] = []
    for docket_id in successes:
        case_id = (candidate_ids or {}).get(docket_id, f"case-dev-{docket_id}")
        raw_html = _docket_html(docket_id=docket_id, decision_text=decision_text)
        raw_path = raw_dir / f"{docket_id}.html"
        raw_path.write_text(raw_html, encoding="utf-8")
        success_records.append(_success_record(docket_id, raw_html, case_id=case_id))
        hits.append(
            DiscoveryHit(
                provider_hit_id=f"success-{docket_id}",
                candidate_id=case_id,
                payload={"case_id": case_id},
            )
        )
    exclusion_records: list[dict[str, object]] = []
    for docket_id in fetch_exclusions:
        case_id = f"case-dev-{docket_id}"
        hits.append(
            DiscoveryHit(
                provider_hit_id=f"excluded-{docket_id}",
                candidate_id=case_id,
                payload={"case_id": case_id},
            )
        )
        exclusion_records.append(
            {
                "case_id": case_id,
                "candidate_id": docket_id,
                "reason": "decision_before_release_anchor",
                "primary_exclusion_reason": "decision_before_release_anchor",
                "stage": "eligibility",
            }
        )
    successes_path = batch_root / "firecrawl-docket-successes.jsonl"
    exclusions_path = batch_root / "firecrawl-docket-exclusions.jsonl"
    _write_jsonl(successes_path, success_records)
    _write_jsonl(exclusions_path, exclusion_records)
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(policy)
        store.ensure_batch(batch_id, {"fixture_batch": batch_id})
        store.ensure_terms(batch_id, ("fixture",))
        store.commit_search_page(
            batch_id,
            "fixture",
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    snapshot_id = f"{batch_id}-complete"
    assert (
        main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--output-root",
                str(batch_root / "screening"),
                "--cycle-store",
                str(store_path),
                "--batch-id",
                batch_id,
                "--successes",
                str(successes_path),
                "--fetch-exclusions",
                str(exclusions_path),
                "--raw-html-dir",
                str(raw_dir),
                "--decision-filed-on-or-after",
                ANCHOR,
                "--snapshot-id",
                snapshot_id,
                "--execute",
            ]
        )
        == 0
    )
    return batch_root / "screening/snapshots" / snapshot_id


def _replay_command(
    *,
    output_root: Path,
    target_store: Path,
    target_cycle_hash: str,
    source_cycle_hash: str,
    assembly_run_card: Path,
    snapshot_id: str,
    expected_assembly_sha256: str | None = None,
) -> list[str]:
    return [
        "acquisition",
        "replay-screening-snapshots",
        "--output-root",
        str(output_root),
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "superseding-replay",
        "--source-assembly-run-card",
        str(assembly_run_card),
        "--expected-source-assembly-sha256",
        expected_assembly_sha256 or sha256_file(assembly_run_card),
        "--expected-source-cycle-hash",
        source_cycle_hash,
        "--expected-target-cycle-hash",
        target_cycle_hash,
        "--decision-filed-on-or-after",
        ANCHOR,
        "--snapshot-id",
        snapshot_id,
        "--execute",
    ]


def _cycle_policy(*, extra: dict[str, object] | None = None) -> dict[str, object]:
    package_root = Path(__file__).parents[1] / "legalforecast"
    sources = {
        "mtd_acquisition_screen": package_root / "ingestion/mtd_acquisition_screen.py",
        "courtlistener_acquisition": package_root
        / "ingestion/courtlistener_acquisition.py",
        "restricted_material": package_root / "ingestion/restricted_material.py",
        "contamination_filters": package_root / "selection/contamination_filters.py",
        "motion_linkage": package_root / "selection/motion_linkage.py",
    }
    policy: dict[str, object] = {
        "schema_version": "legalforecast.cycle_acquisition_policy.v1",
        "eligibility_anchor": date(2026, 6, 30).isoformat(),
        "screening_source_sha256": {
            name: sha256_file(path) for name, path in sorted(sources.items())
        },
    }
    if extra:
        policy.update(extra)
    return policy


def _success_record(
    docket_id: str,
    raw_html: str,
    *,
    case_id: str | None = None,
) -> dict[str, object]:
    raw_bytes = raw_html.encode()
    case_id = case_id or f"case-dev-{docket_id}"
    return {
        "case_id": case_id,
        "source_url": f"https://www.courtlistener.com/docket/{docket_id}/fixture/",
        "docket_id": docket_id,
        "raw_html_path": "ignored",
        "raw_html_sha256": f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}",
        "raw_html_bytes": len(raw_bytes),
        "retrieved_at": "2026-07-14T12:00:00+00:00",
        "pagination_complete_for_anchor_window": True,
        "case_metadata": {
            "case_id": case_id,
            "court_id": "nysd",
            "docket_number": f"1:26-cv-{int(docket_id):05d}",
            "case_name": f"Fixture {docket_id} v. Example",
        },
    }


def _docket_html(*, docket_id: str, decision_text: str) -> str:
    def entry(number: int, filed_at: str, text: str, description: str) -> str:
        return (
            f'<div class="row" id="entry-{number}">'
            f'<div class="col-xs-1">{number}</div>'
            f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
            f'<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>Main Document</div>'
            f"<div>{description}</div>"
            f'<a href="https://storage.courtlistener.com/{docket_id}-{number}.pdf">'
            f"Download PDF</a></div></div></div>"
        )

    return (
        f"<html><head><title>Fixture {docket_id} v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + entry(1, "January 2, 2026", "COMPLAINT filed", "Complaint")
        + entry(5, "February 2, 2026", "MOTION to Dismiss", "Motion to Dismiss")
        + entry(16, "July 1, 2026", decision_text, "Order on Motion to Dismiss")
        + "</div></body></html>"
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]

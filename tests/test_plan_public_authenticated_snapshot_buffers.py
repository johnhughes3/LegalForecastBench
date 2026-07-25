"""TOCTOU regressions for direct public-download snapshot consumption."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import legalforecast.ingestion.screening_snapshot_union as snapshot_union_module
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
    raw_html: bytes | None = None,
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
        if raw_html is not None:
            docket_id = candidate_id.removeprefix("courtlistener-docket-")
            store.write_raw_artifact(
                candidate_id,
                root / "raw" / f"{docket_id}.html",
                raw_html,
                retrieved_at="2026-07-24T11:00:00+00:00",
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


def _repin_snapshot_file(snapshot: Path, filename: str) -> str:
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = (snapshot / filename).read_bytes()
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": payload.count(b"\n"),
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return _manifest_sha256(snapshot)


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


def test_plan_public_rejects_repinned_candidate_evidence_identity_swap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot, cycle_hash = _snapshot(
        tmp_path / "snapshot",
        store_path=tmp_path / "cycle.sqlite3",
        batch_id="identity-swap",
        candidate_id="courtlistener-docket-101",
    )
    candidates_path = snapshot / "candidates.jsonl"
    candidates = [
        json.loads(line)
        for line in candidates_path.read_text(encoding="utf-8").splitlines()
    ]
    candidates[0]["evidence"]["candidate_id"] = "courtlistener-docket-202"
    candidates_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in candidates
        ),
        encoding="utf-8",
    )
    manifest_sha256 = _repin_snapshot_file(snapshot, "candidates.jsonl")

    assert (
        cli_module.main(
            _command(
                snapshot=snapshot,
                manifest_sha256=manifest_sha256,
                cycle_hash=cycle_hash,
                output_root=tmp_path / "rejected-evidence",
            )
        )
        == 2
    )
    assert "evidence identity mismatch" in capsys.readouterr().err


def test_plan_public_rejects_repinned_raw_candidate_path_swap(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_html = _docket_html(decision_dates=("June 30, 2026",)).encode("utf-8")
    snapshot, cycle_hash = _snapshot(
        tmp_path / "snapshot",
        store_path=tmp_path / "cycle.sqlite3",
        batch_id="raw-path-swap",
        candidate_id="courtlistener-docket-101",
        raw_html=raw_html,
    )
    replacement = tmp_path / "snapshot/raw/202.html"
    replacement.write_bytes(raw_html)
    raw_path = snapshot / "raw-artifacts.jsonl"
    raw_records = [
        json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()
    ]
    raw_records[0]["path"] = str(replacement.resolve())
    raw_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in raw_records
        ),
        encoding="utf-8",
    )
    manifest_sha256 = _repin_snapshot_file(snapshot, "raw-artifacts.jsonl")

    assert (
        cli_module.main(
            _command(
                snapshot=snapshot,
                manifest_sha256=manifest_sha256,
                cycle_hash=cycle_hash,
                output_root=tmp_path / "rejected-raw-path",
            )
        )
        == 2
    )
    assert "candidate/path ownership mismatch" in capsys.readouterr().err


def test_plan_public_rejects_owned_raw_identity_not_in_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_html = _docket_html(decision_dates=("June 30, 2026",)).encode("utf-8")
    snapshot, cycle_hash = _snapshot(
        tmp_path / "snapshot",
        store_path=tmp_path / "cycle.sqlite3",
        batch_id="owned-identity-mismatch",
        candidate_id="courtlistener-docket-101",
        raw_html=raw_html,
    )
    screened_payload = (snapshot / "screened-cases.jsonl").read_bytes()
    owned_screened = tmp_path / "owned/screened-cases.jsonl"
    owned_screened.parent.mkdir(parents=True)
    owned_screened.write_bytes(screened_payload)
    owned_raw_dir = tmp_path / "owned/raw"
    owned_raw_dir.mkdir()
    owned_raw_path = owned_raw_dir / "202.html"
    owned_raw_path.write_bytes(raw_html)
    manifest_payload = (
        json.dumps(
            {
                "candidate_id": "202",
                "relative_path": "202.html",
                "sha256": "sha256:" + hashlib.sha256(raw_html).hexdigest(),
                "byte_count": len(raw_html),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    owned_manifest = tmp_path / "owned/raw-html-manifest.jsonl"
    owned_manifest.write_bytes(manifest_payload)

    assert (
        cli_module.main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot),
                "--expected-snapshot-manifest-sha256",
                _manifest_sha256(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--screened-cases",
                str(owned_screened),
                "--expected-screened-cases-sha256",
                hashlib.sha256(screened_payload).hexdigest(),
                "--raw-html-dir",
                str(owned_raw_dir),
                "--authenticated-raw-html-manifest",
                str(owned_manifest),
                "--expected-authenticated-raw-html-manifest-sha256",
                hashlib.sha256(manifest_payload).hexdigest(),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(tmp_path / "rejected-owned-identity"),
                "--execute",
            ]
        )
        == 2
    )
    assert "does not bind exactly once" in capsys.readouterr().err


def test_plan_public_rejects_empty_owned_raw_manifest_without_placeholder_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw_html = _docket_html(decision_dates=("June 30, 2026",)).encode("utf-8")
    snapshot, cycle_hash = _snapshot(
        tmp_path / "snapshot",
        store_path=tmp_path / "cycle.sqlite3",
        batch_id="empty-owned-raw",
        candidate_id="courtlistener-docket-101",
        raw_html=raw_html,
    )
    verified = cli_module.load_verified_screening_snapshot(
        snapshot,
        expected_manifest_sha256=_manifest_sha256(snapshot),
        expected_cycle_hash=cycle_hash,
        authenticated_raw_html_bytes_by_candidate={},
    )
    [artifact] = verified.raw_artifacts
    assert artifact.content is None
    assert artifact.content_authenticated is False

    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    owned_screened = owned_root / "screened-cases.jsonl"
    screened_payload = (snapshot / "screened-cases.jsonl").read_bytes()
    owned_screened.write_bytes(screened_payload)
    owned_raw_dir = owned_root / "raw"
    owned_raw_dir.mkdir()
    owned_manifest = owned_root / "raw-html-manifest.jsonl"
    owned_manifest.write_bytes(b"")

    assert (
        cli_module.main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot),
                "--expected-snapshot-manifest-sha256",
                _manifest_sha256(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--screened-cases",
                str(owned_screened),
                "--expected-screened-cases-sha256",
                hashlib.sha256(screened_payload).hexdigest(),
                "--raw-html-dir",
                str(owned_raw_dir),
                "--authenticated-raw-html-manifest",
                str(owned_manifest),
                "--expected-authenticated-raw-html-manifest-sha256",
                hashlib.sha256(b"").hexdigest(),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(tmp_path / "rejected-empty-owned-raw"),
                "--execute",
            ]
        )
        == 2
    )
    assert "does not match the canonical snapshot projection" in capsys.readouterr().err
    assert not (
        tmp_path / "rejected-empty-owned-raw/public-packet-selection.jsonl"
    ).exists()


def test_partial_owned_raw_mapping_never_synthesizes_placeholder_bytes(
    tmp_path: Path,
) -> None:
    first = b"<html>first</html>"
    second = b"<html>second</html>"
    first_path = tmp_path / "101.html"
    second_path = tmp_path / "202.html"
    first_path.write_bytes(first)
    second_path.write_bytes(second)
    rows = (
        {
            "candidate_id": "courtlistener-docket-101",
            "path": str(first_path.resolve()),
            "sha256": hashlib.sha256(first).hexdigest(),
            "byte_count": len(first),
            "retrieved_at": "2026-07-24T11:00:00+00:00",
        },
        {
            "candidate_id": "courtlistener-docket-202",
            "path": str(second_path.resolve()),
            "sha256": hashlib.sha256(second).hexdigest(),
            "byte_count": len(second),
            "retrieved_at": "2026-07-24T11:00:00+00:00",
        },
    )

    first_artifact, second_artifact = snapshot_union_module._raw_records(
        rows,
        authenticated_raw_html_bytes_by_candidate={"101": first},
    )

    assert first_artifact.content == first
    assert first_artifact.content_authenticated is True
    assert second_artifact.content is None
    assert second_artifact.content_authenticated is False


def test_plan_public_raw_admission_failure_writes_nonpaid_run_card(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash = _snapshot(
        tmp_path / "snapshot",
        store_path=tmp_path / "cycle.sqlite3",
        batch_id="raw-admission-failure",
        candidate_id="courtlistener-docket-101",
    )
    output_root = tmp_path / "failed-admission"
    command = _command(
        snapshot=snapshot,
        manifest_sha256=_manifest_sha256(snapshot),
        cycle_hash=cycle_hash,
        output_root=output_root,
    )
    command.remove("--use-embedded-entries")

    assert cli_module.main(command) == 2

    failure = json.loads(
        (output_root / "run-cards/plan-public-downloads.json").read_text(
            encoding="utf-8"
        )
    )
    assert failure["status"] == "failed"
    assert "no raw docket artifacts" in failure["failure_reason"]
    assert failure["paid_activity_requested"] is False
    assert failure["paid_activity_executed"] is False
    assert not (output_root / "public-packet-selection.jsonl").exists()

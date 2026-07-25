from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from legalforecast import cli as cli_module
from legalforecast.cli import (
    CommandError,
    _validate_rest_priority_promotion_paths,  # pyright: ignore[reportPrivateUsage]
)
from tests.test_rest_priority_subset_promotion import (
    _build_promotion_fixture,  # pyright: ignore[reportPrivateUsage]
    _PromotionFixture,  # pyright: ignore[reportPrivateUsage]
)


def _args(
    tmp_path: Path,
    *,
    cycle_store: Path,
    parent_source_store: Path | None = None,
    resume: bool = True,
) -> argparse.Namespace:
    return argparse.Namespace(
        output_root=tmp_path / "output",
        cycle_store=cycle_store,
        parent_source_store=parent_source_store or cycle_store,
        run_card_output=None,
        log_output=None,
        resume=resume,
    )


def _validate(
    tmp_path: Path,
    *,
    args: argparse.Namespace,
    snapshot_path: Path | None = None,
    omission_inventory_path: Path | None = None,
    summary_path: Path | None = None,
) -> None:
    frontier = tmp_path / "frontier.json"
    source_snapshot = tmp_path / "source-snapshot"
    policy = tmp_path / "policy.json"
    _validate_rest_priority_promotion_paths(
        args=args,
        immutable_inputs=(frontier, source_snapshot, policy),
        snapshot_path=snapshot_path or tmp_path / "output" / "snapshots" / "promoted",
        omission_inventory_path=(
            omission_inventory_path
            or tmp_path / "output" / "unscreened-not-excluded.jsonl"
        ),
        summary_path=(summary_path or tmp_path / "output" / "promotion-summary.json"),
    )


def _promotion_cli_args(
    fixture: _PromotionFixture,
    *,
    output_root: Path,
    target_batch_id: str,
    snapshot_id: str,
) -> list[str]:
    return [
        "acquisition",
        "promote-terminal-rest-priority-subset",
        "--output-root",
        str(output_root),
        "--execute",
        "--cycle-store",
        str(fixture.store_path),
        "--parent-source-store",
        str(fixture.store_path),
        "--parent-source-batch-id",
        "novel-direct-search",
        "--expected-parent-source-batch-digest",
        fixture.source_batch_digest,
        "--priority-batch-id",
        "priority-tranche-1",
        "--expected-priority-batch-digest",
        fixture.priority_batch_digest,
        "--priority-frontier",
        str(fixture.frontier_path),
        "--expected-priority-frontier-sha256",
        fixture.frontier_file_sha256,
        "--source-snapshot",
        str(fixture.source_snapshot),
        "--expected-source-snapshot-manifest-sha256",
        fixture.source_snapshot_manifest_sha256,
        "--selection-policy",
        str(fixture.policy_path),
        "--expected-selection-policy-sha256",
        fixture.policy_sha256,
        "--expected-cycle-hash",
        fixture.cycle_hash,
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--batch-id",
        target_batch_id,
        "--snapshot-id",
        snapshot_id,
    ]


@pytest.mark.parametrize("store_suffix", ("", ".lock", "-wal", "-shm", "-journal"))
def test_rejects_writable_output_that_aliases_cycle_store_or_sidecar(
    tmp_path: Path,
    store_suffix: str,
) -> None:
    cycle_store = tmp_path / "cycle.sqlite3"
    args = _args(tmp_path, cycle_store=cycle_store)

    with pytest.raises(CommandError, match=r"protected input"):
        _validate(
            tmp_path,
            args=args,
            summary_path=Path(f"{cycle_store}{store_suffix}"),
        )


def test_rejects_summary_and_omission_inventory_alias(
    tmp_path: Path,
) -> None:
    cycle_store = tmp_path / "cycle.sqlite3"
    args = _args(tmp_path, cycle_store=cycle_store)
    shared = tmp_path / "output" / "shared.json"

    with pytest.raises(CommandError, match=r"(alias|overlap)"):
        _validate(
            tmp_path,
            args=args,
            omission_inventory_path=shared,
            summary_path=shared,
        )


def test_rejects_writable_file_containing_snapshot_tree(
    tmp_path: Path,
) -> None:
    cycle_store = tmp_path / "cycle.sqlite3"
    args = _args(tmp_path, cycle_store=cycle_store)
    shared = tmp_path / "output" / "shared"

    with pytest.raises(CommandError, match=r"overlap"):
        _validate(
            tmp_path,
            args=args,
            snapshot_path=shared / "snapshot",
            summary_path=shared,
        )


def test_no_resume_rejects_existing_external_output_before_mutation(
    tmp_path: Path,
) -> None:
    cycle_store = tmp_path / "cycle.sqlite3"
    args = _args(tmp_path, cycle_store=cycle_store, resume=False)
    summary = tmp_path / "output" / "promotion-summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text("{}\n")

    with pytest.raises(CommandError, match=r"--no-resume"):
        _validate(
            tmp_path,
            args=args,
            summary_path=summary,
        )


def test_cli_rejects_untracked_resume_snapshot_before_target_batch_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    output_root = tmp_path / "cli-output"
    snapshot_id = "promoted-collision"
    (output_root / "snapshots" / snapshot_id).mkdir(parents=True)
    target_batch_id = "cli-target-must-not-exist"

    exit_code = cli_module.main(
        _promotion_cli_args(
            fixture,
            output_root=output_root,
            target_batch_id=target_batch_id,
            snapshot_id=snapshot_id,
        )
    )
    assert exit_code == 2
    assert "untracked snapshot target" in capsys.readouterr().err

    with sqlite3.connect(fixture.store_path) as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM batches WHERE batch_id = ?",
                (target_batch_id,),
            ).fetchone()
            is None
        )


@pytest.mark.parametrize(
    "malformed_value",
    (None, "not-a-list", [1], ["duplicate", "duplicate"]),
)
def test_cli_dry_run_rejects_malformed_frontier_ids_with_failure_card(
    tmp_path: Path,
    malformed_value: object,
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    frontier = json.loads(fixture.frontier_path.read_text(encoding="utf-8"))
    frontier["selected_candidate_ids"] = malformed_value
    fixture.frontier_path.write_text(
        json.dumps(frontier, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    frontier_sha256 = hashlib.sha256(fixture.frontier_path.read_bytes()).hexdigest()
    output_root = tmp_path / "dry-run-malformed"
    args = _promotion_cli_args(
        fixture,
        output_root=output_root,
        target_batch_id="dry-run-target",
        snapshot_id="dry-run-snapshot",
    )
    args.remove("--execute")
    args[args.index("--expected-priority-frontier-sha256") + 1] = frontier_sha256

    assert cli_module.main(args) == 2

    failure = json.loads(
        (
            output_root / "run-cards/promote-terminal-rest-priority-subset.json"
        ).read_text(encoding="utf-8")
    )
    assert failure["status"] == "failed"
    assert "unique string list" in failure["failure_reason"]
    assert failure["paid_activity_executed"] is False


def test_cli_executes_and_resumes_exact_immutable_publication(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _build_promotion_fixture(tmp_path)
    output_root = tmp_path / "cli-output"
    target_batch_id = "cli-promoted-terminal-subset"
    snapshot_id = "cli-promoted-snapshot"
    args = _promotion_cli_args(
        fixture,
        output_root=output_root,
        target_batch_id=target_batch_id,
        snapshot_id=snapshot_id,
    )

    assert cli_module.main(args) == 0
    capsys.readouterr()
    summary_path = output_root / "rest-priority-subset-promotion-summary.json"
    omission_path = output_root / "unscreened-not-excluded.jsonl"
    summary_before = summary_path.read_bytes()
    omission_before = omission_path.read_bytes()
    assert summary_before
    assert omission_before

    assert cli_module.main(args) == 0
    capsys.readouterr()
    assert summary_path.read_bytes() == summary_before
    assert omission_path.read_bytes() == omission_before
    with sqlite3.connect(fixture.store_path) as connection:
        [snapshot_count] = connection.execute(
            "SELECT COUNT(*) FROM snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
    assert snapshot_count == 1

    tampered_summary = b'{"tampered":true}\n'
    summary_path.write_bytes(tampered_summary)
    assert cli_module.main(args) == 2
    assert "immutable output differs" in capsys.readouterr().err
    assert summary_path.read_bytes() == tampered_summary

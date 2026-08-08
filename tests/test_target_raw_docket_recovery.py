from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast import cli
from legalforecast.ingestion import target_raw_docket_recovery as recovery
from legalforecast.ingestion.budgeted_firecrawl import FirecrawlTargetSpec
from legalforecast.ingestion.case_dev_firecrawl import (
    screen_case_dev_firecrawl_successes,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.target_raw_docket_recovery import (
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
    TargetRawDocketRecoveryError,
    build_target_raw_docket_recovery_plan,
    load_target_raw_docket_recovery_plan,
    target_raw_docket_recovery_receipt_bytes,
    verify_target_raw_docket_recovery_receipt,
    write_target_raw_docket_recovery_plan,
)
from legalforecast.protocol.freeze import sha256_file


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> str:
    payload = b"".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for row in rows
    )
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _recovery_provenance(
    *, plan_sha: str, batch_id: str, run_id: str
) -> dict[str, object]:
    return {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA,
        "plan_sha256": plan_sha,
        "batch_id": batch_id,
        "run_id": run_id,
    }


def _plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    selection = tmp_path / "selection.jsonl"
    selection_sha = _write_jsonl(
        selection,
        [
            {
                "candidate_id": "100",
                "case_id": "100",
                "case_name": "Example One v. Defendant",
                "court": "txwd",
                "docket_number": "1:26-cv-00100",
                "selected": True,
                "source_url": "https://www.courtlistener.com/docket/100/example/",
            },
            {
                "candidate_id": "200",
                "case_id": "200",
                "case_name": "Example Two v. Defendant",
                "court": "txwd",
                "docket_number": "1:26-cv-00200",
                "selected": True,
                "source_url": "https://www.courtlistener.com/docket/200/example/",
            },
        ],
    )
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text('{"fixture":true}\n')
    _write_jsonl(
        snapshot / "screened-cases.jsonl",
        [
            {
                "candidate_id": "courtlistener-docket-100",
                "candidate": {
                    "url": "https://www.courtlistener.com/docket/100/example/"
                },
            },
            {
                "candidate_id": "courtlistener-docket-200",
                "candidate": {
                    "url": "https://www.courtlistener.com/docket/200/example/"
                },
            },
        ],
    )
    card = tmp_path / "source-card.json"
    card.write_text(
        json.dumps({"status": "completed", "snapshot_path": str(snapshot)}) + "\n"
    )
    raw = snapshot / "raw-artifacts.jsonl"
    raw_sha = _write_jsonl(
        raw,
        [
            {
                "candidate_id": "courtlistener-docket-100",
                "sha256": "a" * 64,
                "byte_count": 1,
            }
        ],
    )

    def verify_snapshot(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "cycle_hash": "a" * 64,
            "batch_id": "source-batch",
            "batch_digest": "b" * 64,
        }

    monkeypatch.setattr(recovery, "verify_snapshot", verify_snapshot)

    def screening_source_count(
        manifest: Mapping[str, Any], *, require_current: bool
    ) -> int:
        assert require_current is True
        return 1

    monkeypatch.setattr(
        recovery, "snapshot_firecrawl_screening_source_count", screening_source_count
    )
    return build_target_raw_docket_recovery_plan(
        selection_path=selection,
        expected_selection_sha256=selection_sha,
        source_snapshot_path=snapshot,
        expected_source_snapshot_manifest_sha256=hashlib.sha256(
            (snapshot / "manifest.json").read_bytes()
        ).hexdigest(),
        expected_cycle_hash="a" * 64,
        source_snapshot_run_card_path=card,
        expected_source_snapshot_run_card_sha256=hashlib.sha256(
            card.read_bytes()
        ).hexdigest(),
        source_raw_manifest_path=raw,
        expected_source_raw_manifest_sha256=raw_sha,
        cycle_store_path=tmp_path / "cycle.sqlite3",
        batch_id="raw-recovery",
        run_id="raw-recovery-run",
        credit_cap=45,
        workers=1,
        max_pages_per_docket=10,
        max_attempts_per_page=3,
        provider_breaker_threshold=5,
        proxy="basic",
        force_browser=False,
    )


def _rebuild(plan: recovery.TargetRawDocketRecoveryPlan, **overrides: object):
    values: dict[str, object] = {
        "selection_path": Path(plan.selection_path),
        "expected_selection_sha256": plan.selection_sha256,
        "source_snapshot_path": Path(plan.source_snapshot_path),
        "expected_source_snapshot_manifest_sha256": (
            plan.source_snapshot_manifest_sha256
        ),
        "expected_cycle_hash": plan.cycle_hash,
        "source_snapshot_run_card_path": Path(plan.source_snapshot_run_card_path),
        "expected_source_snapshot_run_card_sha256": (
            plan.source_snapshot_run_card_sha256
        ),
        "source_raw_manifest_path": Path(plan.source_raw_manifest_path),
        "expected_source_raw_manifest_sha256": plan.source_raw_manifest_sha256,
        "cycle_store_path": Path(plan.cycle_store_path),
        "batch_id": plan.batch_id,
        "run_id": plan.run_id,
        "credit_cap": plan.credit_cap,
        "workers": plan.workers,
        "max_pages_per_docket": plan.max_pages_per_docket,
        "max_attempts_per_page": plan.max_attempts_per_page,
        "provider_breaker_threshold": plan.provider_breaker_threshold,
        "proxy": plan.proxy,
        "force_browser": plan.force_browser,
    }
    values.update(overrides)
    return build_target_raw_docket_recovery_plan(**values)  # type: ignore[arg-type]


def _command_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> recovery.TargetRawDocketRecoveryPlan:
    """Create the exact store/snapshot authority that the CLI replays."""

    preliminary = _plan(tmp_path, monkeypatch)
    store_path = Path(preliminary.cycle_store_path)
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle({"fixture": True})
        source_batch_digest = store.ensure_batch(
            preliminary.source_batch_id, {"fixture": True}
        )
        store.ensure_terms(preliminary.source_batch_id, ("motion to dismiss",))
        store.commit_search_page(
            preliminary.source_batch_id,
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="fixture-hit-200",
                    candidate_id="courtlistener-docket-200",
                    payload={"case_id": "courtlistener-docket-200"},
                ),
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )

    monkeypatch.setattr(
        recovery,
        "verify_snapshot",
        lambda *args, **kwargs: {
            "cycle_hash": cycle_hash,
            "batch_id": preliminary.source_batch_id,
            "batch_digest": source_batch_digest,
        },
    )
    return _rebuild(preliminary, expected_cycle_hash=cycle_hash)


def _command_args(
    plan: recovery.TargetRawDocketRecoveryPlan,
    *,
    output_root: Path,
    execute: bool,
    plan_output: Path,
    firecrawl_fixture: Path | None = None,
) -> Namespace:
    return Namespace(
        output_root=output_root,
        run_card_output=None,
        log_output=None,
        resume=True,
        execute=execute,
        selection=Path(plan.selection_path),
        expected_selection_sha256=plan.selection_sha256,
        source_snapshot=Path(plan.source_snapshot_path),
        expected_source_snapshot_manifest_sha256=(plan.source_snapshot_manifest_sha256),
        expected_cycle_hash=plan.cycle_hash,
        source_snapshot_run_card=Path(plan.source_snapshot_run_card_path),
        expected_source_snapshot_run_card_sha256=(plan.source_snapshot_run_card_sha256),
        source_raw_manifest=Path(plan.source_raw_manifest_path),
        expected_source_raw_manifest_sha256=plan.source_raw_manifest_sha256,
        cycle_store=Path(plan.cycle_store_path),
        batch_id=plan.batch_id,
        run_id=plan.run_id,
        credit_cap=plan.credit_cap,
        workers=plan.workers,
        max_pages_per_docket=plan.max_pages_per_docket,
        max_attempts_per_page=plan.max_attempts_per_page,
        provider_breaker_threshold=plan.provider_breaker_threshold,
        proxy=plan.proxy,
        force_browser=plan.force_browser,
        plan_output=plan_output,
        plan=plan_output,
        expected_plan_sha256=None,
        raw_html_dir=output_root / "raw-html",
        successes_output=output_root / "successes.jsonl",
        exclusions_output=output_root / "exclusions.jsonl",
        summary_output=output_root / "summary.json",
        receipt_output=output_root / "receipt.json",
        live_firecrawl=False,
        firecrawl_fixture=firecrawl_fixture,
    )


def _fixture_docket_html() -> str:
    return """
    <html><head><title>Fixture 200</title></head><body>
      <div id="docket-entry-table">
        <div id="entry-1" class="row">
          <div class="col-xs-1">1</div>
          <div class="col-xs-3"><span title="June 1, 2026">June 1, 2026</span></div>
          <div class="col-xs-8">Motion to Dismiss for Failure to State a Claim.</div>
        </div>
        <div id="entry-2" class="row">
          <div class="col-xs-1">2</div>
          <div class="col-xs-3"><span title="July 1, 2026">July 1, 2026</span></div>
          <div class="col-xs-8">ORDER granting 1 Motion to Dismiss for Failure to
            State a Claim.</div>
        </div>
      </div>
    </body></html>
    """


def test_plan_command_writes_authenticated_plan_and_stage_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    output_root = tmp_path / "plan-output"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=False,
        plan_output=output_root / "recovery-plan.json",
    )

    assert cli._cmd_acquisition_plan_target_raw_docket_recovery(args) == 0  # pyright: ignore[reportPrivateUsage]

    plan_sha = sha256_file(args.plan_output)
    assert load_target_raw_docket_recovery_plan(args.plan_output, plan_sha) == plan
    run_card = json.loads(
        (output_root / "run-cards/plan-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["dry_run"] is True
    assert run_card["paid_activity_requested"] is False
    assert run_card["record_count"] == 1
    assert run_card["plan_sha256"] == plan_sha


def test_execute_command_dry_run_writes_empty_terminal_quartet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
    output_root = tmp_path / "dry-execute"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=False,
        plan_output=plan_output,
    )
    args.expected_plan_sha256 = plan_sha

    assert cli._cmd_acquisition_execute_target_raw_docket_recovery(args) == 0  # pyright: ignore[reportPrivateUsage]

    assert args.successes_output.read_bytes() == b""
    assert args.exclusions_output.read_bytes() == b""
    summary = json.loads(args.summary_output.read_text())
    assert summary == {
        "schema_version": recovery.TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA,
        "dry_run": True,
        "target_count": 1,
        "provider_activity_requested": False,
    }
    receipt = json.loads(args.receipt_output.read_text())
    assert receipt == {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
        "dry_run": True,
        "plan_sha256": plan_sha,
    }
    run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["dry_run"] is True
    assert run_card["record_count"] == 0
    assert run_card["provider_activity_requested"] is False


def test_execute_command_rejects_partial_or_ambiguous_execution_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
    output_root = tmp_path / "invalid-execute"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=True,
        plan_output=plan_output,
    )
    args.expected_plan_sha256 = plan_sha
    args.successes_output.parent.mkdir()
    args.successes_output.write_bytes(b"partial\n")

    with pytest.raises(
        cli.CommandError,
        match="either no terminal outputs or the complete terminal set",
    ):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]

    args.successes_output.unlink()
    with pytest.raises(
        cli.CommandError, match="exactly one of --live-firecrawl or --firecrawl-fixture"
    ):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]

    args.firecrawl_fixture = tmp_path / "empty-fixture.jsonl"
    args.firecrawl_fixture.write_bytes(b"")
    args.workers = 2
    with pytest.raises(
        cli.CommandError, match="Firecrawl fixture execution requires --workers 1"
    ):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]


def test_execute_command_records_pinned_plan_mismatch_as_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
    output_root = tmp_path / "mismatched-execute"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=False,
        plan_output=plan_output,
    )
    args.expected_plan_sha256 = plan_sha
    args.batch_id = "changed-batch"

    with pytest.raises(cli.CommandError, match="pinned plan differs from current"):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]

    run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["status"] == "failed"
    assert run_card["failure_reason"] == "pinned plan differs from current inputs"


def test_execute_command_replays_offline_fixture_and_authenticates_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
    source_url = "https://www.courtlistener.com/docket/200/example/"
    fixture = tmp_path / "firecrawl.jsonl"
    _write_jsonl(
        fixture,
        [
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": _fixture_docket_html(),
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
    output_root = tmp_path / "fixture-execute"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=True,
        plan_output=plan_output,
        firecrawl_fixture=fixture,
    )
    args.expected_plan_sha256 = plan_sha

    assert cli._cmd_acquisition_execute_target_raw_docket_recovery(args) == 0  # pyright: ignore[reportPrivateUsage]

    [success] = [
        json.loads(line) for line in args.successes_output.read_text().splitlines()
    ]
    assert success["candidate_id"] == "courtlistener-docket-200"
    assert success["target_raw_docket_recovery"] == _recovery_provenance(
        plan_sha=plan_sha, batch_id=plan.batch_id, run_id=plan.run_id
    )
    summary = json.loads(args.summary_output.read_text())
    assert summary["success_count"] == 1
    assert summary["exclusion_count"] == 0
    assert summary["raw_artifacts"][0]["candidate_id"] == "courtlistener-docket-200"
    receipt = verify_target_raw_docket_recovery_receipt(
        receipt_path=args.receipt_output,
        expected_receipt_sha256=sha256_file(args.receipt_output),
        expected_plan_sha256=plan_sha,
        successes_path=args.successes_output,
        exclusions_path=args.exclusions_output,
        summary_path=args.summary_output,
        raw_html_dir=args.raw_html_dir,
    )
    assert receipt["batch_id"] == plan.batch_id
    assert receipt["run_id"] == plan.run_id
    run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["dry_run"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False
    assert run_card["record_count"] == 1

    assert cli._cmd_acquisition_execute_target_raw_docket_recovery(args) == 0  # pyright: ignore[reportPrivateUsage]
    resumed_run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert resumed_run_card["resumed_complete_receipt"] is True


def test_plan_derives_only_selected_minus_pinned_raw_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)

    assert [target["candidate_id"] for target in plan.targets] == [
        "courtlistener-docket-200"
    ]
    assert plan.targets[0]["identity"] == {
        "courtlistener_docket_id": "200",
        "courtlistener_url": "https://www.courtlistener.com/docket/200/example/",
    }
    output = tmp_path / "plan.json"
    digest = write_target_raw_docket_recovery_plan(output, plan)
    assert load_target_raw_docket_recovery_plan(output, digest) == plan


def test_plan_rejects_rebound_pinned_source_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw = Path(plan.source_raw_manifest_path)
    raw.write_text("{}\n")

    with pytest.raises(
        TargetRawDocketRecoveryError, match="source raw manifest SHA-256 mismatch"
    ):
        build_target_raw_docket_recovery_plan(
            selection_path=Path(plan.selection_path),
            expected_selection_sha256=plan.selection_sha256,
            source_snapshot_path=Path(plan.source_snapshot_path),
            expected_source_snapshot_manifest_sha256=(
                plan.source_snapshot_manifest_sha256
            ),
            expected_cycle_hash=plan.cycle_hash,
            source_snapshot_run_card_path=Path(plan.source_snapshot_run_card_path),
            expected_source_snapshot_run_card_sha256=plan.source_snapshot_run_card_sha256,
            source_raw_manifest_path=raw,
            expected_source_raw_manifest_sha256=plan.source_raw_manifest_sha256,
            cycle_store_path=Path(plan.cycle_store_path),
            batch_id=plan.batch_id,
            run_id=plan.run_id,
            credit_cap=plan.credit_cap,
            workers=plan.workers,
            max_pages_per_docket=plan.max_pages_per_docket,
            max_attempts_per_page=plan.max_attempts_per_page,
            provider_breaker_threshold=plan.provider_breaker_threshold,
            proxy=plan.proxy,
            force_browser=plan.force_browser,
        )


def test_plan_rejects_completed_card_for_a_different_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    card = Path(plan.source_snapshot_run_card_path)
    other_snapshot = tmp_path / "other-snapshot"
    other_snapshot.mkdir()
    card.write_text(
        json.dumps({"status": "completed", "snapshot_path": str(other_snapshot)}) + "\n"
    )

    with pytest.raises(
        TargetRawDocketRecoveryError,
        match="source snapshot run card does not bind source snapshot",
    ):
        build_target_raw_docket_recovery_plan(
            selection_path=Path(plan.selection_path),
            expected_selection_sha256=plan.selection_sha256,
            source_snapshot_path=Path(plan.source_snapshot_path),
            expected_source_snapshot_manifest_sha256=(
                plan.source_snapshot_manifest_sha256
            ),
            expected_cycle_hash=plan.cycle_hash,
            source_snapshot_run_card_path=card,
            expected_source_snapshot_run_card_sha256=(
                hashlib.sha256(card.read_bytes()).hexdigest()
            ),
            source_raw_manifest_path=Path(plan.source_raw_manifest_path),
            expected_source_raw_manifest_sha256=plan.source_raw_manifest_sha256,
            cycle_store_path=Path(plan.cycle_store_path),
            batch_id=plan.batch_id,
            run_id=plan.run_id,
            credit_cap=plan.credit_cap,
            workers=plan.workers,
            max_pages_per_docket=plan.max_pages_per_docket,
            max_attempts_per_page=plan.max_attempts_per_page,
            provider_breaker_threshold=plan.provider_breaker_threshold,
            proxy=plan.proxy,
            force_browser=plan.force_browser,
        )


def test_plan_rejects_raw_manifest_not_owned_by_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    unrelated = tmp_path / "unrelated-raw.jsonl"
    unrelated.write_bytes(Path(plan.source_raw_manifest_path).read_bytes())

    with pytest.raises(
        TargetRawDocketRecoveryError,
        match="not the authenticated snapshot raw-artifacts",
    ):
        build_target_raw_docket_recovery_plan(
            selection_path=Path(plan.selection_path),
            expected_selection_sha256=plan.selection_sha256,
            source_snapshot_path=Path(plan.source_snapshot_path),
            expected_source_snapshot_manifest_sha256=(
                plan.source_snapshot_manifest_sha256
            ),
            expected_cycle_hash=plan.cycle_hash,
            source_snapshot_run_card_path=Path(plan.source_snapshot_run_card_path),
            expected_source_snapshot_run_card_sha256=(
                plan.source_snapshot_run_card_sha256
            ),
            source_raw_manifest_path=unrelated,
            expected_source_raw_manifest_sha256=hashlib.sha256(
                unrelated.read_bytes()
            ).hexdigest(),
            cycle_store_path=Path(plan.cycle_store_path),
            batch_id=plan.batch_id,
            run_id=plan.run_id,
            credit_cap=plan.credit_cap,
            workers=plan.workers,
            max_pages_per_docket=plan.max_pages_per_docket,
            max_attempts_per_page=plan.max_attempts_per_page,
            provider_breaker_threshold=plan.provider_breaker_threshold,
            proxy=plan.proxy,
            force_browser=plan.force_browser,
        )


def test_plan_rejects_incomplete_or_unsaturated_source_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)

    def incomplete(*args: object, **kwargs: object) -> dict[str, object]:
        raise recovery.SnapshotVerificationError("snapshot is not complete")

    monkeypatch.setattr(recovery, "verify_snapshot", incomplete)
    with pytest.raises(TargetRawDocketRecoveryError, match="not current complete"):
        _rebuild(plan)


def test_plan_rejects_duplicate_selected_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    selection = Path(plan.selection_path)
    duplicate = json.loads(selection.read_text().splitlines()[0])
    selection.write_text(selection.read_text() + json.dumps(duplicate) + "\n")
    with pytest.raises(TargetRawDocketRecoveryError, match="repeats"):
        _rebuild(
            plan,
            expected_selection_sha256=hashlib.sha256(
                selection.read_bytes()
            ).hexdigest(),
        )


def test_plan_accepts_authenticated_raw_history_for_one_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw = Path(plan.source_raw_manifest_path)
    rows = [json.loads(line) for line in raw.read_text().splitlines()]
    rows.append(
        {
            "candidate_id": "courtlistener-docket-100",
            "sha256": "b" * 64,
            "byte_count": 2,
        }
    )
    raw_sha = _write_jsonl(raw, rows)

    rebuilt = _rebuild(plan, expected_source_raw_manifest_sha256=raw_sha)

    assert [target["candidate_id"] for target in rebuilt.targets] == [
        "courtlistener-docket-200"
    ]


def test_plan_rejects_selected_url_for_a_different_docket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    selection = Path(plan.selection_path)
    rows = [json.loads(line) for line in selection.read_text().splitlines()]
    rows[1]["source_url"] = "https://www.courtlistener.com/docket/100/example/"
    selection_sha = _write_jsonl(selection, rows)

    with pytest.raises(TargetRawDocketRecoveryError, match="does not match"):
        _rebuild(plan, expected_selection_sha256=selection_sha)


def test_plan_rejects_url_not_bound_by_source_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    screened = Path(plan.source_snapshot_path) / "screened-cases.jsonl"
    rows = [json.loads(line) for line in screened.read_text().splitlines()]
    rows[1]["candidate"]["url"] = (  # type: ignore[index]
        "https://www.courtlistener.com/docket/200/changed/"
    )
    _write_jsonl(screened, rows)

    with pytest.raises(TargetRawDocketRecoveryError, match="not authenticated"):
        _rebuild(plan)


def test_plan_rejects_duplicate_screened_candidate_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    screened = Path(plan.source_snapshot_path) / "screened-cases.jsonl"
    rows = [json.loads(line) for line in screened.read_text().splitlines()]
    rows.append(rows[1])
    _write_jsonl(screened, rows)

    with pytest.raises(TargetRawDocketRecoveryError, match="repeats screened"):
        _rebuild(plan)


def _path_args(tmp_path: Path, *, resume: bool = True) -> Namespace:
    return Namespace(
        output_root=tmp_path / "output",
        run_card_output=None,
        log_output=None,
        cycle_store=tmp_path / "cycle.sqlite3",
        resume=resume,
    )


def test_output_preflight_rejects_protected_input_as_output(tmp_path: Path) -> None:
    args = _path_args(tmp_path)
    selection = tmp_path / "selection.jsonl"
    selection.write_text("{}\n")

    with pytest.raises(cli.CommandError, match="below --output-root"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(selection,),
            writable_paths=(selection,),
        )


def test_output_preflight_rejects_dotdot_escape(tmp_path: Path) -> None:
    args = _path_args(tmp_path)
    escaped = args.output_root / ".." / "escaped.jsonl"

    with pytest.raises(cli.CommandError, match="below --output-root"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(escaped,),
        )


def test_output_preflight_rejects_symlinked_raw_tree(tmp_path: Path) -> None:
    args = _path_args(tmp_path)
    output_root = args.output_root
    output_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    raw_dir = output_root / "raw"
    raw_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(cli.CommandError, match="symlink"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(output_root / "success.jsonl",),
            raw_html_dir=raw_dir,
        )


def test_output_preflight_honors_no_resume(tmp_path: Path) -> None:
    args = _path_args(tmp_path, resume=False)
    output = args.output_root / "success.jsonl"
    output.parent.mkdir()
    output.write_text("existing\n")

    with pytest.raises(cli.CommandError, match="--no-resume"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(output,),
        )


def test_output_preflight_rejects_terminal_raw_residue_without_receipt(
    tmp_path: Path,
) -> None:
    args = _path_args(tmp_path)
    raw_dir = args.output_root / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "200.html").write_text("stale")

    with pytest.raises(cli.CommandError, match="terminal residue"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(args.output_root / "success.jsonl",),
            raw_html_dir=raw_dir,
        )


def test_output_preflight_allows_safe_terminal_raw_residue_for_resume(
    tmp_path: Path,
) -> None:
    args = _path_args(tmp_path)
    raw_dir = args.output_root / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "200.html").write_text("durably reconstructed")

    cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
        args,
        stage="fixture",
        protected_paths=(tmp_path / "selection.jsonl",),
        writable_paths=(args.output_root / "success.jsonl",),
        raw_html_dir=raw_dir,
        allow_completed_raw_files=True,
    )


def test_terminal_raw_residue_must_match_durable_page_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    terminal = raw_dir / "200.html"
    terminal.write_bytes(b"durably reconstructed")

    def replay(**kwargs: object) -> SimpleNamespace:
        records = cast(Sequence[Mapping[str, object]], kwargs["records"])
        assert tuple(records) == plan.targets
        return SimpleNamespace(bundles=(SimpleNamespace(docket_id="200"),))

    def render(bundle: object) -> str:
        return "durably reconstructed"

    monkeypatch.setattr(cli, "acquire_ranked_dockets", replay)
    monkeypatch.setattr(cli, "render_complete_docket_html", render)
    with CycleAcquisitionStore(Path(plan.cycle_store_path)) as store:
        store.ensure_cycle({"fixture": True})
        cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
            store=store,
            plan=plan,
            raw_html_dir=raw_dir,
        )
        terminal.write_bytes(b"changed")
        with pytest.raises(
            TargetRawDocketRecoveryError, match="differs from durable pages"
        ):
            cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
                store=store,
                plan=plan,
                raw_html_dir=raw_dir,
            )


def test_terminal_raw_residue_accepts_absent_or_page_only_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    with CycleAcquisitionStore(Path(plan.cycle_store_path)) as store:
        store.ensure_cycle({"fixture": True})
        raw_dir = tmp_path / "raw"
        cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
            store=store,
            plan=plan,
            raw_html_dir=raw_dir,
        )
        (raw_dir / "pages").mkdir(parents=True)
        cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
            store=store,
            plan=plan,
            raw_html_dir=raw_dir,
        )


def test_terminal_raw_residue_rejects_unrecognized_or_unplanned_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    with CycleAcquisitionStore(Path(plan.cycle_store_path)) as store:
        store.ensure_cycle({"fixture": True})
        junk = raw_dir / "junk.txt"
        junk.write_text("junk")
        with pytest.raises(TargetRawDocketRecoveryError, match="unrecognized entry"):
            cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
                store=store,
                plan=plan,
                raw_html_dir=raw_dir,
            )
        junk.unlink()
        (raw_dir / "999.html").write_text("not selected")
        with pytest.raises(TargetRawDocketRecoveryError, match=r"outside.*plan"):
            cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
                store=store,
                plan=plan,
                raw_html_dir=raw_dir,
            )


def test_terminal_raw_residue_rejects_incomplete_durable_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "200.html").write_text("partial")

    def fail_replay(**kwargs: object) -> SimpleNamespace:
        raise AssertionError("provider requested")

    monkeypatch.setattr(cli, "acquire_ranked_dockets", fail_replay)
    with CycleAcquisitionStore(Path(plan.cycle_store_path)) as store:
        store.ensure_cycle({"fixture": True})
        with pytest.raises(TargetRawDocketRecoveryError, match="complete durable run"):
            cli._verify_target_raw_recovery_terminal_residue(  # pyright: ignore[reportPrivateUsage]
                store=store,
                plan=plan,
                raw_html_dir=raw_dir,
            )


def test_output_preflight_rejects_pages_root_file(tmp_path: Path) -> None:
    args = _path_args(tmp_path)
    raw_dir = args.output_root / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "pages").write_text("not a directory")

    with pytest.raises(cli.CommandError, match="pages root is not a directory"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(args.output_root / "success.jsonl",),
            raw_html_dir=raw_dir,
        )


def test_page_residue_requires_matching_durable_run(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    pages = raw_dir / "pages"
    pages.mkdir(parents=True)
    (pages / "stale.html").write_text("stale")
    store_path = tmp_path / "cycle.sqlite3"

    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"fixture": True})
        with pytest.raises(TargetRawDocketRecoveryError, match="no matching durable"):
            cli._verify_target_raw_recovery_page_residue(  # pyright: ignore[reportPrivateUsage]
                store=store,
                run_id="missing-run",
                raw_html_dir=raw_dir,
            )


class _OnePageScheduler:
    run_id = "fixture-run"

    def __init__(self) -> None:
        self.store = self

    def firecrawl_attempts(self, run_id: str) -> tuple[SimpleNamespace, ...]:
        assert run_id == self.run_id
        return (
            SimpleNamespace(
                request_url=(
                    "https://www.courtlistener.com/docket/200/example/"
                    "?order_by=desc&page=1"
                ),
                status="succeeded",
                completed_at="2026-08-08T10:00:00+00:00",
            ),
        )

    def run(self, targets: Sequence[FirecrawlTargetSpec]) -> SimpleNamespace:
        pages: list[SimpleNamespace] = []
        for target in targets:
            docket_id = target.source_url.split("/docket/", 1)[1].split("/", 1)[0]
            pages.append(
                SimpleNamespace(
                    target_id=target.target_id,
                    source_url=target.source_url,
                    raw_html=f"""
                    <html><head><title>Fixture {docket_id}</title></head><body>
                      <div id="docket-entry-table">
                        <div id="entry-1" class="row">
                          <div class="col-xs-1">1</div>
                          <div class="col-xs-3"><span title="June 1, 2026">
                            June 1, 2026</span></div>
                          <div class="col-xs-8">
                            Motion to Dismiss for Failure to State a Claim.</div>
                        </div>
                        <div id="entry-2" class="row">
                          <div class="col-xs-1">2</div>
                          <div class="col-xs-3"><span title="July 1, 2026">
                            July 1, 2026</span></div>
                          <div class="col-xs-8">ORDER granting 1 Motion to Dismiss
                            for Failure to State a Claim.</div>
                        </div>
                      </div>
                    </body></html>
                    """,
                )
            )
        return SimpleNamespace(
            pages=tuple(pages),
            summary={"reserved_credits": len(pages), "reported_credits": len(pages)},
        )


def test_execution_emits_screen_compatible_prefixed_candidate_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"

    successes, exclusions, summary = recovery.execute_target_raw_docket_recovery(
        plan=plan,
        scheduler=_OnePageScheduler(),  # type: ignore[arg-type]
        raw_html_dir=raw_dir,
    )
    screened = screen_case_dev_firecrawl_successes(
        successes=successes,
        raw_html_directory=raw_dir,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert exclusions == []
    assert summary["pagination_complete_before_screening"] is True
    assert successes[0]["case_id"] == "courtlistener-docket-200"
    assert successes[0]["retrieved_at"] == "2026-08-08T10:00:00+00:00"
    assert successes[0]["case_metadata"]["case_id"] == "courtlistener-docket-200"  # type: ignore[index]
    assert len(screened.screened_cases) == 1
    assert screened.exclusions == ()


def test_receipt_authenticates_exact_recovery_to_screen_handoff(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_path = raw_dir / "200.html"
    raw = b"<html>complete docket</html>"
    raw_path.write_bytes(raw)
    raw_artifact = {
        "candidate_id": "courtlistener-docket-200",
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw),
        "retrieved_at": "2026-08-08T10:00:00+00:00",
    }
    plan_sha = "a" * 64
    batch_id = "raw-recovery"
    run_id = "raw-recovery-run"
    successes = tmp_path / "successes.jsonl"
    successes_sha = _write_jsonl(
        successes,
        [
            {
                **raw_artifact,
                "case_id": "courtlistener-docket-200",
                "docket_id": "200",
                "raw_html_path": str(raw_path.resolve()),
                "raw_html_sha256": raw_artifact["sha256"],
                "raw_html_bytes": raw_artifact["byte_count"],
                "target_raw_docket_recovery": _recovery_provenance(
                    plan_sha=plan_sha, batch_id=batch_id, run_id=run_id
                ),
            }
        ],
    )
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions.write_bytes(b"")
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps({"raw_artifacts": [raw_artifact]}, indent=2, sort_keys=True) + "\n"
    )
    receipt_record: dict[str, object] = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
        "dry_run": False,
        "plan_sha256": plan_sha,
        "batch_id": batch_id,
        "run_id": run_id,
        "successes_path": str(successes.resolve()),
        "exclusions_path": str(exclusions.resolve()),
        "summary_path": str(summary.resolve()),
        "raw_html_dir": str(raw_dir.resolve()),
        "successes_sha256": successes_sha,
        "exclusions_sha256": hashlib.sha256(b"").hexdigest(),
        "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
        "raw_artifacts": [raw_artifact],
    }
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(target_raw_docket_recovery_receipt_bytes(receipt_record))
    receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()

    verified = verify_target_raw_docket_recovery_receipt(
        receipt_path=receipt,
        expected_receipt_sha256=receipt_sha,
        expected_plan_sha256=plan_sha,
        successes_path=successes,
        exclusions_path=exclusions,
        summary_path=summary,
        raw_html_dir=raw_dir,
    )
    assert verified["plan_sha256"] == plan_sha

    raw_path.write_bytes(b"changed")
    with pytest.raises(TargetRawDocketRecoveryError, match="raw HTML commitment"):
        verify_target_raw_docket_recovery_receipt(
            receipt_path=receipt,
            expected_receipt_sha256=receipt_sha,
            expected_plan_sha256=plan_sha,
            successes_path=successes,
            exclusions_path=exclusions,
            summary_path=summary,
            raw_html_dir=raw_dir,
        )


def test_receipt_accepts_terminal_all_excluded_recovery(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    successes = tmp_path / "successes.jsonl"
    successes.write_bytes(b"")
    plan_sha = "a" * 64
    batch_id = "raw-recovery"
    run_id = "raw-recovery-run"
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions_sha = _write_jsonl(
        exclusions,
        [
            {
                "candidate_id": "courtlistener-docket-200",
                "reason": "terminal",
                "target_raw_docket_recovery": _recovery_provenance(
                    plan_sha=plan_sha, batch_id=batch_id, run_id=run_id
                ),
            }
        ],
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps({"raw_artifacts": []}, indent=2, sort_keys=True) + "\n"
    )
    receipt_record: dict[str, object] = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
        "dry_run": False,
        "plan_sha256": plan_sha,
        "batch_id": batch_id,
        "run_id": run_id,
        "successes_path": str(successes.resolve()),
        "exclusions_path": str(exclusions.resolve()),
        "summary_path": str(summary.resolve()),
        "raw_html_dir": str(raw_dir.resolve()),
        "successes_sha256": hashlib.sha256(b"").hexdigest(),
        "exclusions_sha256": exclusions_sha,
        "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
        "raw_artifacts": [],
    }
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(target_raw_docket_recovery_receipt_bytes(receipt_record))

    verified = verify_target_raw_docket_recovery_receipt(
        receipt_path=receipt,
        expected_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
        expected_plan_sha256=plan_sha,
        successes_path=successes,
        exclusions_path=exclusions,
        summary_path=summary,
        raw_html_dir=raw_dir,
    )
    assert verified["raw_artifacts"] == []


def test_screen_cli_authenticates_recovery_receipt_handoff(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_path = raw_dir / "200.html"
    raw = b"""
    <html><head><title>Fixture v. Example</title></head><body>
      <div id="docket-entry-table">
        <div id="entry-1" class="row"><div class="col-xs-1">1</div>
          <div class="col-xs-3"><span title="June 1, 2026">June 1, 2026</span></div>
          <div class="col-xs-8">Motion to Dismiss.</div></div>
        <div id="entry-2" class="row"><div class="col-xs-1">2</div>
          <div class="col-xs-3"><span title="July 1, 2026">July 1, 2026</span></div>
          <div class="col-xs-8">ORDER granting 1 Motion to Dismiss.</div></div>
      </div>
    </body></html>
    """
    raw_path.write_bytes(raw)
    candidate_id = "courtlistener-docket-200"
    plan_sha = "a" * 64
    batch_id = "raw-recovery"
    run_id = "raw-recovery-run"
    retrieved_at = "2026-08-08T10:00:00+00:00"
    raw_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
    success: dict[str, object] = {
        "case_id": candidate_id,
        "candidate_id": candidate_id,
        "source_url": "https://www.courtlistener.com/docket/200/example/",
        "docket_id": "200",
        "raw_html_path": str(raw_path.resolve()),
        "raw_html_sha256": raw_sha,
        "raw_html_bytes": len(raw),
        "retrieved_at": retrieved_at,
        "pagination_complete_for_anchor_window": True,
        "page_count": 1,
        "target_raw_docket_recovery": _recovery_provenance(
            plan_sha=plan_sha, batch_id=batch_id, run_id=run_id
        ),
        "case_metadata": {
            "case_id": candidate_id,
            "court_id": "txwd",
            "docket_number": "1:26-cv-00200",
            "case_name": "Fixture v. Example",
        },
    }
    successes = tmp_path / "successes.jsonl"
    successes_sha = _write_jsonl(successes, [success])
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions.write_bytes(b"")
    raw_artifact = {
        "candidate_id": candidate_id,
        "sha256": raw_sha,
        "byte_count": len(raw),
        "retrieved_at": retrieved_at,
    }
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps({"raw_artifacts": [raw_artifact]}, indent=2, sort_keys=True) + "\n"
    )
    store_path = tmp_path / "cycle.sqlite3"
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
    with CycleAcquisitionStore(store_path) as store:
        cycle_hash = store.ensure_cycle(
            {
                "schema_version": "legalforecast.case_dev_discovery_policy.v1",
                "eligibility_anchor": "2026-06-30",
                "query_terms": ["motion to dismiss"],
                "query_term_order_is_frozen": True,
                "screening_source_sha256": {
                    name: sha256_file(path)
                    for name, path in sorted(screening_sources.items())
                },
            }
        )
        batch_digest = store.ensure_batch(
            batch_id, {"purpose": "target-raw-docket-recovery"}
        )
        store.ensure_terms(batch_id, ("motion to dismiss",))
        store.commit_search_page(
            batch_id,
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="fixture-hit-200",
                    candidate_id=candidate_id,
                    payload={"case_id": candidate_id},
                ),
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        run_config = {
            "purpose": "target-raw-docket-recovery",
            "fixture": True,
        }
        store.ensure_firecrawl_run(
            run_id,
            batch_id=batch_id,
            config=run_config,
            credit_cap=9,
            reserved_credits_per_attempt=1,
        )
        store.ensure_batch("ordinary-batch", {"fixture": True})
        store.ensure_terms("ordinary-batch", ("motion to dismiss",))
        store.commit_search_page(
            "ordinary-batch",
            "motion to dismiss",
            None,
            (
                DiscoveryHit(
                    provider_hit_id="ordinary-hit-200",
                    candidate_id=candidate_id,
                    payload={"case_id": candidate_id},
                ),
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
    receipt_record = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
        "dry_run": False,
        "plan_sha256": plan_sha,
        "cycle_hash": cycle_hash,
        "cycle_store_path": str(store_path.resolve()),
        "batch_id": batch_id,
        "batch_digest": batch_digest,
        "run_id": run_id,
        "run_config": run_config,
        "credit_cap": 9,
        "reserved_credits_per_attempt": 1,
        "successes_path": str(successes.resolve()),
        "exclusions_path": str(exclusions.resolve()),
        "summary_path": str(summary.resolve()),
        "raw_html_dir": str(raw_dir.resolve()),
        "successes_sha256": successes_sha,
        "exclusions_sha256": hashlib.sha256(b"").hexdigest(),
        "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
        "raw_artifacts": [raw_artifact],
    }
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(target_raw_docket_recovery_receipt_bytes(receipt_record))
    receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
    output = tmp_path / "screen"

    assert (
        cli.main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--execute",
                "--no-resume",
                "--output-root",
                str(tmp_path / "unbound-screen"),
                "--cycle-store",
                str(store_path),
                "--batch-id",
                "ordinary-batch",
                "--successes",
                str(successes),
                "--fetch-exclusions",
                str(exclusions),
                "--raw-html-dir",
                str(raw_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--snapshot-id",
                "unbound-recovery-screen",
            ]
        )
        == 2
    )
    assert (
        cli.main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--execute",
                "--no-resume",
                "--output-root",
                str(output),
                "--cycle-store",
                str(store_path),
                "--batch-id",
                batch_id,
                "--successes",
                str(successes),
                "--fetch-exclusions",
                str(exclusions),
                "--raw-html-dir",
                str(raw_dir),
                "--target-raw-docket-recovery-receipt",
                str(receipt),
                "--target-raw-docket-recovery-summary",
                str(summary),
                "--expected-target-raw-docket-recovery-receipt-sha256",
                receipt_sha,
                "--expected-target-raw-docket-recovery-plan-sha256",
                plan_sha,
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--snapshot-id",
                "raw-recovery-screen",
            ]
        )
        == 0
    )
    snapshot_manifest = json.loads(
        (output / "snapshots/raw-recovery-screen/manifest.json").read_text()
    )
    assert (
        snapshot_manifest["stage_commitments"]["target_raw_docket_recovery"][
            "receipt_sha256"
        ]
        == receipt_sha
    )

from __future__ import annotations

import hashlib
import json
import os
from argparse import Namespace
from collections.abc import Mapping, Sequence
from dataclasses import replace
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
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
)
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


def _snapshot_commitment(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": payload.count(b"\n"),
    }


def _recovery_provenance(
    *, plan_sha: str, batch_id: str, run_id: str
) -> dict[str, object]:
    return {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA,
        "plan_sha256": plan_sha,
        "batch_id": batch_id,
        "run_id": run_id,
    }


def _write_recovery_summary(
    path: Path,
    *,
    raw_artifacts: list[dict[str, object]],
    success_count: int,
    exclusion_count: int,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": recovery.TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA,
                "success_count": success_count,
                "exclusion_count": exclusion_count,
                "raw_artifacts": raw_artifacts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


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
    manifest_record: dict[str, object] = {
        "cycle_hash": "a" * 64,
        "batch_id": "source-batch",
        "batch_digest": "b" * 64,
        "files": {
            "screened-cases.jsonl": _snapshot_commitment(
                snapshot / "screened-cases.jsonl"
            ),
            "raw-artifacts.jsonl": _snapshot_commitment(raw),
        },
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest_record) + "\n")

    def verify_snapshot(*args: object, **kwargs: object) -> dict[str, object]:
        return manifest_record

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


def _reauthenticate_snapshot_file(
    plan: recovery.TargetRawDocketRecoveryPlan,
    filename: str,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    snapshot = Path(plan.source_snapshot_path)
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][filename] = _snapshot_commitment(snapshot / filename)
    manifest_path.write_text(json.dumps(manifest) + "\n")
    monkeypatch.setattr(recovery, "verify_snapshot", lambda *args, **kwargs: manifest)
    return sha256_file(manifest_path)


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

    manifest_path = Path(preliminary.source_snapshot_path) / "manifest.json"
    manifest_record = json.loads(manifest_path.read_text())
    manifest_record.update(
        {
            "cycle_hash": cycle_hash,
            "batch_id": preliminary.source_batch_id,
            "batch_digest": source_batch_digest,
        }
    )
    manifest_path.write_text(json.dumps(manifest_record) + "\n")
    manifest_sha = sha256_file(manifest_path)
    monkeypatch.setattr(
        recovery,
        "verify_snapshot",
        lambda *args, **kwargs: manifest_record,
    )
    return _rebuild(
        preliminary,
        expected_cycle_hash=cycle_hash,
        expected_source_snapshot_manifest_sha256=manifest_sha,
    )


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
        expected_receipt_sha256=None,
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


def test_execute_command_records_all_inputs_for_value_error_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
    output_root = tmp_path / "failure"
    args = _command_args(
        plan,
        output_root=output_root,
        execute=False,
        plan_output=plan_output,
    )
    args.expected_plan_sha256 = plan_sha

    def fail_reconstruction(args: Namespace) -> recovery.TargetRawDocketRecoveryPlan:
        raise ValueError("fixture store boundary")

    monkeypatch.setattr(
        cli, "_target_raw_docket_recovery_plan_from_args", fail_reconstruction
    )

    with pytest.raises(cli.CommandError, match="fixture store boundary"):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]

    run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["input_paths"] == [
        str(args.plan),
        str(args.selection),
        str(args.source_snapshot / "manifest.json"),
        str(args.source_snapshot_run_card),
        str(args.source_raw_manifest),
    ]


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
    assert receipt["run_config"]["recovery_of_run_id"] == (
        plan.source_snapshot_manifest_sha256
    )
    run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert run_card["dry_run"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False
    assert run_card["record_count"] == 1

    args.expected_receipt_sha256 = sha256_file(args.receipt_output)

    def forbid_store_mutation(*args: object, **kwargs: object) -> None:
        raise AssertionError("completed receipt verification must be read-only")

    monkeypatch.setattr(
        CycleAcquisitionStore, "ensure_firecrawl_run", forbid_store_mutation
    )
    assert cli._cmd_acquisition_execute_target_raw_docket_recovery(args) == 0  # pyright: ignore[reportPrivateUsage]
    resumed_run_card = json.loads(
        (output_root / "run-cards/execute-target-raw-docket-recovery.json").read_text()
    )
    assert resumed_run_card["resumed_complete_receipt"] is True


def test_execute_command_completed_resume_requires_external_receipt_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _command_plan(tmp_path, monkeypatch)
    plan_output = tmp_path / "plan-stage" / "recovery-plan.json"
    plan_output.parent.mkdir()
    plan_sha = write_target_raw_docket_recovery_plan(plan_output, plan)
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
                            "sourceURL": (
                                "https://www.courtlistener.com/docket/200/example/"
                                "?order_by=desc&page=1"
                            ),
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

    with pytest.raises(cli.CommandError, match="external lowercase SHA-256 anchor"):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]

    args.expected_receipt_sha256 = "0" * 64
    with pytest.raises(cli.CommandError, match="SHA-256 mismatch"):
        cli._cmd_acquisition_execute_target_raw_docket_recovery(args)  # pyright: ignore[reportPrivateUsage]


def test_cycle_store_rejects_second_recovery_for_same_source_snapshot(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "cycle.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle({"fixture": True})
        store.ensure_batch("recovery-one", {"fixture": 1})
        store.ensure_batch("recovery-two", {"fixture": 2})
        parent = "a" * 64
        store.ensure_firecrawl_run(
            "run-one",
            batch_id="recovery-one",
            config={"recovery_of_run_id": parent},
            credit_cap=9,
            reserved_credits_per_attempt=1,
        )
        with pytest.raises(ConfigMismatchError, match="already exists"):
            store.ensure_firecrawl_run(
                "run-two",
                batch_id="recovery-two",
                config={"recovery_of_run_id": parent},
                credit_cap=9,
                reserved_credits_per_attempt=1,
            )


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


def test_plan_uses_the_same_selection_bytes_for_pin_and_derivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    selection = Path(plan.selection_path)
    original_reader = recovery._read_unique_regular_file  # pyright: ignore[reportPrivateUsage]
    replaced = False

    def replacing_reader(path: Path, label: str) -> bytes:
        nonlocal replaced
        payload = original_reader(path, label)
        if path == selection and not replaced:
            selection.write_text('{"selected":false}\n')
            replaced = True
        return payload

    monkeypatch.setattr(recovery, "_read_unique_regular_file", replacing_reader)
    assert _rebuild(plan) == plan
    assert replaced is True


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

    manifest_sha = _reauthenticate_snapshot_file(
        plan, "raw-artifacts.jsonl", monkeypatch
    )
    rebuilt = _rebuild(
        plan,
        expected_source_raw_manifest_sha256=raw_sha,
        expected_source_snapshot_manifest_sha256=manifest_sha,
    )

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
    manifest_sha = _reauthenticate_snapshot_file(
        plan, "screened-cases.jsonl", monkeypatch
    )

    with pytest.raises(TargetRawDocketRecoveryError, match="not authenticated"):
        _rebuild(plan, expected_source_snapshot_manifest_sha256=manifest_sha)


def test_plan_rejects_duplicate_screened_candidate_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    screened = Path(plan.source_snapshot_path) / "screened-cases.jsonl"
    rows = [json.loads(line) for line in screened.read_text().splitlines()]
    rows.append(rows[1])
    _write_jsonl(screened, rows)
    manifest_sha = _reauthenticate_snapshot_file(
        plan, "screened-cases.jsonl", monkeypatch
    )

    with pytest.raises(TargetRawDocketRecoveryError, match="repeats screened"):
        _rebuild(plan, expected_source_snapshot_manifest_sha256=manifest_sha)


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


def test_output_preflight_rejects_output_nested_in_protected_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    args = _path_args(tmp_path)
    args.output_root = snapshot / "output"

    with pytest.raises(cli.CommandError, match="overlaps authenticated input"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(snapshot,),
            writable_paths=(args.output_root / "success.jsonl",),
        )


def test_output_preflight_wraps_stat_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _path_args(tmp_path)
    output = args.output_root / "success.jsonl"
    output.parent.mkdir()
    output.write_text("existing\n")
    original_stat = Path.stat

    def failing_stat(path: Path, *args: object, **kwargs: object):
        if path == output:
            raise PermissionError("fixture denial")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", failing_stat)
    with pytest.raises(cli.CommandError, match="cannot inspect writable output"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(output,),
        )


def test_output_preflight_wraps_resume_entry_lstat_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _path_args(tmp_path)
    raw_dir = args.output_root / "raw"
    page = raw_dir / "pages" / "200" / "page-000001.html"
    page.parent.mkdir(parents=True)
    page.write_text("existing\n")
    original_lstat = Path.lstat

    def failing_lstat(path: Path, *args: object, **kwargs: object):
        if path == page:
            raise FileNotFoundError("fixture race")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", failing_lstat)
    with pytest.raises(cli.CommandError, match="cannot inspect raw HTML resume entry"):
        cli._preflight_target_raw_docket_recovery_paths(  # pyright: ignore[reportPrivateUsage]
            args,
            stage="fixture",
            protected_paths=(tmp_path / "selection.jsonl",),
            writable_paths=(args.output_root / "success.jsonl",),
            raw_html_dir=raw_dir,
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
    _write_recovery_summary(
        summary,
        raw_artifacts=[raw_artifact],
        success_count=1,
        exclusion_count=0,
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
    _write_recovery_summary(
        summary,
        raw_artifacts=[],
        success_count=0,
        exclusion_count=1,
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

    summary.write_text(json.dumps({"raw_artifacts": []}) + "\n")
    receipt_record["summary_sha256"] = sha256_file(summary)
    receipt.write_bytes(target_raw_docket_recovery_receipt_bytes(receipt_record))
    with pytest.raises(TargetRawDocketRecoveryError, match="summary contract"):
        verify_target_raw_docket_recovery_receipt(
            receipt_path=receipt,
            expected_receipt_sha256=sha256_file(receipt),
            expected_plan_sha256=plan_sha,
            successes_path=successes,
            exclusions_path=exclusions,
            summary_path=summary,
            raw_html_dir=raw_dir,
        )


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
    _write_recovery_summary(
        summary,
        raw_artifacts=[raw_artifact],
        success_count=1,
        exclusion_count=0,
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


@pytest.mark.parametrize("suffix", ("?page=1", "#docket"))
def test_plan_rejects_selected_courtlistener_url_query_or_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    selection = Path(plan.selection_path)
    rows = [json.loads(line) for line in selection.read_text().splitlines()]
    rows[1]["source_url"] += suffix
    selection_sha = _write_jsonl(selection, rows)

    with pytest.raises(
        TargetRawDocketRecoveryError, match="selected URL docket does not match"
    ):
        _rebuild(plan, expected_selection_sha256=selection_sha)


@pytest.mark.parametrize(
    ("targets", "message"),
    (
        (({},), "plan target is malformed"),
        ((cast(Mapping[str, object], "not-a-mapping"),), "plan target is malformed"),
    ),
)
def test_execute_rejects_malformed_target_before_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    targets: tuple[Mapping[str, object], ...],
    message: str,
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    called: list[bool] = []

    def unexpected_scheduler(*args: object, **kwargs: object) -> object:
        called.append(True)
        raise AssertionError("invalid plan must fail before scheduler use")

    monkeypatch.setattr(recovery, "acquire_ranked_dockets", unexpected_scheduler)
    with pytest.raises(TargetRawDocketRecoveryError, match=message):
        recovery.execute_target_raw_docket_recovery(
            plan=replace(plan, targets=targets),
            scheduler=cast(Any, SimpleNamespace()),
            raw_html_dir=tmp_path / "raw",
        )

    assert called == []


def test_execute_rejects_duplicate_target_before_scheduler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    called: list[bool] = []

    def unexpected_scheduler(*args: object, **kwargs: object) -> object:
        called.append(True)
        raise AssertionError("invalid plan must fail before scheduler use")

    monkeypatch.setattr(recovery, "acquire_ranked_dockets", unexpected_scheduler)
    with pytest.raises(TargetRawDocketRecoveryError, match="metadata is malformed"):
        recovery.execute_target_raw_docket_recovery(
            plan=replace(plan, targets=plan.targets * 2),
            scheduler=cast(Any, SimpleNamespace()),
            raw_html_dir=tmp_path / "raw",
        )

    assert called == []


def test_execute_rejects_unplanned_bundle_before_publishing_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr(
        recovery,
        "acquire_ranked_dockets",
        lambda **kwargs: SimpleNamespace(
            bundles=(SimpleNamespace(docket_id="999", pages=(), base_url=""),),
            failures=(),
            credit_summary={},
        ),
    )

    with pytest.raises(TargetRawDocketRecoveryError, match="not a planned target"):
        recovery.execute_target_raw_docket_recovery(
            plan=plan,
            scheduler=cast(
                Any,
                SimpleNamespace(
                    run_id="fixture-run",
                    store=SimpleNamespace(firecrawl_attempts=lambda run_id: ()),
                ),
            ),
            raw_html_dir=raw_dir,
        )

    assert not (raw_dir / "999.html").exists()


def test_execute_wraps_ranked_acquisition_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)

    def fail_acquisition(**kwargs: object) -> object:
        raise recovery.BudgetedDocketAcquisitionError("fixture invalid target")

    monkeypatch.setattr(recovery, "acquire_ranked_dockets", fail_acquisition)
    with pytest.raises(
        TargetRawDocketRecoveryError, match="target raw docket acquisition is invalid"
    ):
        recovery.execute_target_raw_docket_recovery(
            plan=plan,
            scheduler=cast(Any, SimpleNamespace()),
            raw_html_dir=tmp_path / "raw",
        )
    assert list((tmp_path / "raw").glob("*.html")) == []


def test_execute_orders_retrieval_timestamps_by_instant_and_owns_summary_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path, monkeypatch)
    first_url = "https://www.courtlistener.com/docket/200/example/?page=1"
    second_url = "https://www.courtlistener.com/docket/200/example/?page=2"
    bundle = SimpleNamespace(
        docket_id="200",
        base_url="https://www.courtlistener.com/docket/200/example/",
        pages=(
            SimpleNamespace(source_url=first_url),
            SimpleNamespace(source_url=second_url),
        ),
    )
    monkeypatch.setattr(
        recovery,
        "acquire_ranked_dockets",
        lambda **kwargs: SimpleNamespace(
            bundles=(bundle,), failures=(), credit_summary={"schema_version": "wrong"}
        ),
    )
    monkeypatch.setattr(recovery, "render_complete_docket_html", lambda bundle: "raw")
    scheduler = SimpleNamespace(
        run_id="fixture-run",
        store=SimpleNamespace(
            firecrawl_attempts=lambda run_id: (
                SimpleNamespace(
                    request_url=first_url,
                    status="succeeded",
                    completed_at="2026-08-08T10:00:00+02:00",
                ),
                SimpleNamespace(
                    request_url=second_url,
                    status="succeeded",
                    completed_at="2026-08-08T09:00:00Z",
                ),
            )
        ),
    )

    successes, exclusions, summary = recovery.execute_target_raw_docket_recovery(
        plan=plan,
        scheduler=cast(Any, scheduler),
        raw_html_dir=tmp_path / "raw",
    )

    assert exclusions == []
    assert successes[0]["retrieved_at"] == "2026-08-08T09:00:00Z"
    assert (
        summary["schema_version"] == recovery.TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA
    )


def test_receipt_rejects_non_numeric_docket_id_before_path_projection(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    successes = tmp_path / "successes.jsonl"
    docket_id = "200/../../outside"
    candidate_id = "courtlistener-docket-" + docket_id
    plan_sha = "a" * 64
    success = {
        "candidate_id": candidate_id,
        "docket_id": docket_id,
        "raw_html_path": str(raw_dir / "outside.html"),
        "raw_html_sha256": "sha256:" + "a" * 64,
        "raw_html_bytes": 0,
        "retrieved_at": "2026-08-08T10:00:00Z",
        "target_raw_docket_recovery": _recovery_provenance(
            plan_sha=plan_sha, batch_id="raw-recovery", run_id="fixture-run"
        ),
    }
    successes_sha = _write_jsonl(successes, [success])
    exclusions = tmp_path / "exclusions.jsonl"
    exclusions.write_bytes(b"")
    summary = tmp_path / "summary.json"
    _write_recovery_summary(
        summary,
        raw_artifacts=[],
        success_count=1,
        exclusion_count=0,
    )
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(
        target_raw_docket_recovery_receipt_bytes(
            {
                "schema_version": TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA,
                "dry_run": False,
                "plan_sha256": plan_sha,
                "batch_id": "raw-recovery",
                "run_id": "fixture-run",
                "successes_path": str(successes.resolve()),
                "exclusions_path": str(exclusions.resolve()),
                "summary_path": str(summary.resolve()),
                "raw_html_dir": str(raw_dir.resolve()),
                "successes_sha256": successes_sha,
                "exclusions_sha256": hashlib.sha256(b"").hexdigest(),
                "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
                "raw_artifacts": [],
            }
        )
    )

    with pytest.raises(TargetRawDocketRecoveryError, match="malformed raw-artifact"):
        verify_target_raw_docket_recovery_receipt(
            receipt_path=receipt,
            expected_receipt_sha256=sha256_file(receipt),
            expected_plan_sha256=plan_sha,
            successes_path=successes,
            exclusions_path=exclusions,
            summary_path=summary,
            raw_html_dir=raw_dir,
        )


def test_open_raw_html_directory_rejects_symlink_and_regular_file(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(outside, target_is_directory=True)
    descriptor: int | None = None
    try:
        with pytest.raises(TargetRawDocketRecoveryError, match="not a real directory"):
            descriptor = recovery._open_raw_html_directory(symlink)  # pyright: ignore[reportPrivateUsage]
    finally:
        if descriptor is not None:
            os.close(descriptor)

    regular_file = tmp_path / "regular-file"
    regular_file.write_text("not a directory")
    descriptor = None
    try:
        with pytest.raises(
            TargetRawDocketRecoveryError,
            match=r"cannot create recovery raw HTML directory|not a real directory",
        ):
            descriptor = recovery._open_raw_html_directory(regular_file)  # pyright: ignore[reportPrivateUsage]
    finally:
        if descriptor is not None:
            os.close(descriptor)


def test_unique_reader_rejects_fifo_and_symlinked_parent(tmp_path: Path) -> None:
    fifo = tmp_path / "input.fifo"
    os.mkfifo(fifo)
    with pytest.raises(TargetRawDocketRecoveryError, match="singly linked"):
        recovery._read_unique_regular_file(  # pyright: ignore[reportPrivateUsage]
            fifo, "fixture FIFO"
        )

    outside = tmp_path / "outside-parent"
    outside.mkdir()
    (outside / "input.json").write_text("{}\n")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(TargetRawDocketRecoveryError, match="singly linked"):
        recovery._read_unique_regular_file(  # pyright: ignore[reportPrivateUsage]
            linked_parent / "input.json", "fixture linked parent"
        )


def test_raw_html_publisher_rejects_linked_and_racing_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"immutable"
    raw_dir = tmp_path / "raw"
    descriptor = recovery._open_raw_html_directory(raw_dir)  # pyright: ignore[reportPrivateUsage]
    outside = tmp_path / "outside"
    outside.write_bytes(payload)
    try:
        (raw_dir / "symlink.html").symlink_to(outside)
        with pytest.raises(TargetRawDocketRecoveryError, match="singly linked"):
            recovery._publish_unique_raw_html(  # pyright: ignore[reportPrivateUsage]
                descriptor, "symlink.html", payload, label="fixture symlink"
            )

        os.link(outside, raw_dir / "hardlink.html")
        with pytest.raises(TargetRawDocketRecoveryError, match="singly linked"):
            recovery._publish_unique_raw_html(  # pyright: ignore[reportPrivateUsage]
                descriptor, "hardlink.html", payload, label="fixture hardlink"
            )

        original_link = recovery.os.link

        def racing_link(source: object, destination: object, **kwargs: object) -> None:
            destination_fd = cast(int, kwargs["dst_dir_fd"])
            racing_fd = os.open(
                cast(str, destination),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=destination_fd,
            )
            try:
                os.write(racing_fd, b"racer")
            finally:
                os.close(racing_fd)
            original_link(source, destination, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(recovery.os, "link", racing_link)
        with pytest.raises(TargetRawDocketRecoveryError, match="different bytes"):
            recovery._publish_unique_raw_html(  # pyright: ignore[reportPrivateUsage]
                descriptor, "racing.html", payload, label="fixture race"
            )
        assert (raw_dir / "racing.html").read_bytes() == b"racer"
    finally:
        os.close(descriptor)

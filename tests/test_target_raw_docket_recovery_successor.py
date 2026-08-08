from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast import cli
from legalforecast.ingestion import target_raw_docket_recovery as recovery
from legalforecast.ingestion.budgeted_docket_acquisition import (
    materialize_selected_slice_batch,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    ConfigMismatchError,
    CycleAcquisitionStore,
)
from legalforecast.ingestion.target_raw_docket_recovery import (
    TargetRawDocketRecoveryError,
    TargetRawDocketRecoveryPlan,
    TargetRawDocketRecoverySuccessorPlan,
    build_target_raw_docket_recovery_successor_plan,
    load_target_raw_docket_recovery_successor_plan,
    resolve_target_raw_docket_recovery_successor,
    write_target_raw_docket_recovery_plan,
    write_target_raw_docket_recovery_successor_plan,
)
from tests import test_target_raw_docket_recovery as raw_recovery_tests


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _subcommand_parser(
    parser: argparse.ArgumentParser, command: str
) -> argparse.ArgumentParser:
    subparsers = next(
        action
        for action in cast(list[Any], parser._actions)
        if type(action).__name__ == "_SubParsersAction"
    )
    return cast(
        argparse.ArgumentParser,
        cast(dict[str, object], subparsers.choices)[command],
    )


def _long_options(parser: argparse.ArgumentParser) -> set[str]:
    return {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }


def _prepare_circuit_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    attempt_status: str = "provider_error",
    provider_http_status: int = 500,
) -> tuple[TargetRawDocketRecoveryPlan, Path]:
    """Materialize the same accepted parent authority the production CLI uses."""

    command_plan = cast(Any, raw_recovery_tests._command_plan)  # pyright: ignore[reportPrivateUsage]
    parent = cast(TargetRawDocketRecoveryPlan, command_plan(tmp_path, monkeypatch))
    raw_html_dir = tmp_path / "parent-raw-html"
    raw_html_dir.mkdir()
    with CycleAcquisitionStore(Path(parent.cycle_store_path)) as store:
        materialize_selected_slice_batch(
            store=store,
            parent_batch_id=parent.source_batch_id,
            selected_batch_id=parent.batch_id,
            records=parent.targets,
            limit=len(parent.targets),
            purpose="target-raw-docket-recovery",
        )
        root_config = {
            "purpose": "target-raw-docket-recovery",
            "recovery_of_run_id": parent.source_snapshot_manifest_sha256,
            "max_pages_per_docket": parent.max_pages_per_docket,
            "raw_artifact_root": str((raw_html_dir / "pages").resolve()),
            "firecrawl_proxy": parent.proxy,
            "firecrawl_force_browser": parent.force_browser,
            "workers": parent.workers,
            "max_attempts_per_page": parent.max_attempts_per_page,
            "provider_breaker_threshold": parent.provider_breaker_threshold,
        }
        store.ensure_firecrawl_run(
            parent.run_id,
            batch_id=parent.batch_id,
            config=root_config,
            credit_cap=parent.credit_cap,
            reserved_credits_per_attempt=1,
        )
        for ordinal, target in enumerate(parent.targets):
            identity = cast(dict[str, str], target["identity"])
            candidate_id = cast(str, target["candidate_id"])
            request_url = f"{identity['courtlistener_url']}?order_by=desc&page=1"
            store.ensure_firecrawl_target(
                parent.run_id,
                target_id=candidate_id,
                target_kind="docket",
                source_url=request_url,
                ordinal=ordinal,
            )
            attempt = store.authorize_firecrawl_attempt(
                parent.run_id,
                target_id=candidate_id,
                page_number=1,
                request_url=request_url,
            )
            if attempt_status == "succeeded":
                store.finalize_firecrawl_attempt(
                    attempt.attempt_id,
                    status="succeeded",
                    reported_credits=1,
                )
            else:
                store.finalize_firecrawl_attempt(
                    attempt.attempt_id,
                    status="provider_error",
                    provider_http_status=provider_http_status,
                    failure_code="provider_server_error",
                    failure_message="Fixture Firecrawl server failure",
                    failure_transient=True,
                )
        store.set_firecrawl_run_status(parent.run_id, "circuit_open")
    return parent, raw_html_dir


def _failure_run_card(
    plan_path: Path,
    parent: TargetRawDocketRecoveryPlan,
    *,
    raw_html_dir: Path,
) -> Path:
    """Produce the exact card shape the failure recorder leaves for a circuit."""

    terminal_root = plan_path.parent / "terminal"
    terminal_outputs = tuple(
        terminal_root / name
        for name in (
            "successes.jsonl",
            "exclusions.jsonl",
            "summary.json",
            "receipt.json",
        )
    )
    with CycleAcquisitionStore(Path(parent.cycle_store_path)) as store:
        summary = dict(store.firecrawl_run_summary(parent.run_id))
    path = plan_path.parent / "execute-parent-failure.json"
    path.write_text(
        json.dumps(
            {
                **summary,
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "execute-target-raw-docket-recovery",
                "status": "failed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "record_count": 0,
                "input_paths": [
                    str(plan_path),
                    parent.selection_path,
                    str(Path(parent.source_snapshot_path) / "manifest.json"),
                    parent.source_snapshot_run_card_path,
                    parent.source_raw_manifest_path,
                ],
                "output_paths": [str(path) for path in terminal_outputs],
                "paid_activity_requested": True,
                "paid_activity_executed": True,
                "firecrawl_metered_activity_requested": True,
                "firecrawl_metered_activity_executed": True,
                "failure_reason": "target raw docket acquisition provider circuit open",
                "firecrawl_run_status": "circuit_open",
            },
            sort_keys=True,
        )
        + "\n"
    )
    assert raw_html_dir.is_dir()
    return path


def _successor_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    TargetRawDocketRecoveryPlan,
    Path,
    str,
    Path,
    str,
    TargetRawDocketRecoverySuccessorPlan,
]:
    parent, raw_html_dir = _prepare_circuit_parent(tmp_path, monkeypatch)
    parent_plan_path = tmp_path / "parent-plan.json"
    parent_sha = write_target_raw_docket_recovery_plan(parent_plan_path, parent)
    failure_card = _failure_run_card(
        parent_plan_path, parent, raw_html_dir=raw_html_dir
    )
    failure_card_sha = _sha256(failure_card)
    successor = build_target_raw_docket_recovery_successor_plan(
        parent_plan_path=parent_plan_path,
        expected_parent_plan_sha256=parent_sha,
        parent_failure_run_card_path=failure_card,
        expected_parent_failure_run_card_sha256=failure_card_sha,
        parent_raw_html_dir=raw_html_dir,
        batch_id="successor-batch",
        run_id="successor-run",
    )
    return (
        parent,
        parent_plan_path,
        parent_sha,
        failure_card,
        failure_card_sha,
        successor,
    )


def test_successor_plan_is_externally_pinned_and_derives_every_effective_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, parent_path, parent_sha, failure_card, failure_card_sha, successor = (
        _successor_plan(tmp_path, monkeypatch)
    )
    successor_path = tmp_path / "successor-plan.json"
    successor_sha = write_target_raw_docket_recovery_successor_plan(
        successor_path, successor
    )

    loaded = load_target_raw_docket_recovery_successor_plan(
        successor_path, successor_sha
    )
    resolved_parent, child = resolve_target_raw_docket_recovery_successor(loaded)

    assert resolved_parent == parent
    assert child.batch_id == "successor-batch"
    assert child.run_id == "successor-run"
    assert child.targets == parent.targets
    for field in TargetRawDocketRecoveryPlan.__dataclass_fields__:
        if field not in {"batch_id", "run_id"}:
            assert getattr(child, field) == getattr(parent, field)
    assert successor_path.exists()
    assert parent_path.exists()
    assert parent_sha == _sha256(parent_path)
    assert failure_card_sha == _sha256(failure_card)


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("status", "completed"),
        ("firecrawl_run_status", "active"),
        ("stage", "plan-target-raw-docket-recovery"),
    ],
)
def test_successor_plan_rejects_unpinned_or_ineligible_parent_failure_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    value: str,
) -> None:
    parent, parent_path, parent_sha, failure_card, _, _ = _successor_plan(
        tmp_path, monkeypatch
    )
    record = json.loads(failure_card.read_text())
    record[mutation] = value
    failure_card.write_text(json.dumps(record, sort_keys=True) + "\n")
    raw_html_dir = tmp_path / "parent-raw-html"

    with pytest.raises(TargetRawDocketRecoveryError, match="circuit failure"):
        build_target_raw_docket_recovery_successor_plan(
            parent_plan_path=parent_path,
            expected_parent_plan_sha256=parent_sha,
            parent_failure_run_card_path=failure_card,
            expected_parent_failure_run_card_sha256=_sha256(failure_card),
            parent_raw_html_dir=raw_html_dir,
            batch_id="successor-batch",
            run_id="successor-run",
        )
    with pytest.raises(TargetRawDocketRecoveryError, match="SHA-256 mismatch"):
        build_target_raw_docket_recovery_successor_plan(
            parent_plan_path=parent_path,
            expected_parent_plan_sha256=parent_sha,
            parent_failure_run_card_path=failure_card,
            expected_parent_failure_run_card_sha256="f" * 64,
            parent_raw_html_dir=raw_html_dir,
            batch_id="successor-batch-2",
            run_id="successor-run-2",
        )
    assert parent.run_id


@pytest.mark.parametrize(
    ("attempt_status", "provider_http_status"),
    [("succeeded", 500), ("provider_error", 429)],
)
def test_successor_plan_rejects_nonzero_success_or_non_5xx_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attempt_status: str,
    provider_http_status: int,
) -> None:
    parent, raw_html_dir = _prepare_circuit_parent(
        tmp_path,
        monkeypatch,
        attempt_status=attempt_status,
        provider_http_status=provider_http_status,
    )
    parent_plan_path = tmp_path / "parent-plan.json"
    parent_sha = write_target_raw_docket_recovery_plan(parent_plan_path, parent)
    failure_card = _failure_run_card(
        parent_plan_path, parent, raw_html_dir=raw_html_dir
    )

    with pytest.raises(
        TargetRawDocketRecoveryError, match="zero-success all-provider-error"
    ):
        build_target_raw_docket_recovery_successor_plan(
            parent_plan_path=parent_plan_path,
            expected_parent_plan_sha256=parent_sha,
            parent_failure_run_card_path=failure_card,
            expected_parent_failure_run_card_sha256=_sha256(failure_card),
            parent_raw_html_dir=raw_html_dir,
            batch_id="successor-batch",
            run_id="successor-run",
        )


def test_successor_child_uses_parent_run_identity_and_store_rejects_duplicate_or_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, _, _, _, _, successor = _successor_plan(tmp_path, monkeypatch)
    _, child = resolve_target_raw_docket_recovery_successor(successor)
    child_config = {
        "purpose": "target-raw-docket-recovery",
        "recovery_of_run_id": parent.run_id,
    }

    with CycleAcquisitionStore(Path(parent.cycle_store_path)) as store:
        store.ensure_batch(child.batch_id, {"purpose": "target-raw-docket-recovery"})
        store.ensure_firecrawl_run(
            child.run_id,
            batch_id=child.batch_id,
            config=child_config,
            credit_cap=child.credit_cap,
            reserved_credits_per_attempt=1,
        )
        assert (
            store.firecrawl_run_config(child.run_id)["recovery_of_run_id"]
            == parent.run_id
        )

        store.ensure_batch("duplicate-batch", {"purpose": "target-raw-docket-recovery"})
        with pytest.raises(
            ConfigMismatchError, match="terminal target recovery already exists"
        ):
            store.ensure_firecrawl_run(
                "duplicate-child-run",
                batch_id="duplicate-batch",
                config={**child_config, "recovery_of_run_id": parent.run_id},
                credit_cap=child.credit_cap,
                reserved_credits_per_attempt=1,
            )

        child_plan_path = tmp_path / "child-plan.json"
        child_plan_sha = write_target_raw_docket_recovery_plan(child_plan_path, child)
        store.set_firecrawl_run_status(child.run_id, "circuit_open")
    child_failure_card = _failure_run_card(
        child_plan_path, child, raw_html_dir=tmp_path / "parent-raw-html"
    )
    with pytest.raises(
        TargetRawDocketRecoveryError, match="durable cycle-store authority"
    ):
        build_target_raw_docket_recovery_successor_plan(
            parent_plan_path=child_plan_path,
            expected_parent_plan_sha256=child_plan_sha,
            parent_failure_run_card_path=child_failure_card,
            expected_parent_failure_run_card_sha256=_sha256(child_failure_card),
            parent_raw_html_dir=tmp_path / "parent-raw-html",
            batch_id="would-be-grandchild-batch",
            run_id="would-be-grandchild-run",
        )


def test_successor_accepts_retried_zero_success_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, parent_path, parent_sha, _, _, _ = _successor_plan(tmp_path, monkeypatch)
    with CycleAcquisitionStore(Path(parent.cycle_store_path)) as store:
        store.set_firecrawl_run_status(parent.run_id, "active")
        target = store.firecrawl_targets(parent.run_id)[0]
        attempt = store.authorize_firecrawl_attempt(
            parent.run_id,
            target_id=target.target_id,
            page_number=1,
            request_url=target.source_url,
        )
        store.finalize_firecrawl_attempt(
            attempt.attempt_id,
            status="provider_error",
            provider_http_status=503,
            failure_code="provider_server_error",
            failure_message="Fixture retry also failed",
            failure_transient=True,
        )
        store.set_firecrawl_run_status(parent.run_id, "circuit_open")
    raw_html_dir = tmp_path / "parent-raw-html"
    failure_card = _failure_run_card(parent_path, parent, raw_html_dir=raw_html_dir)

    successor = build_target_raw_docket_recovery_successor_plan(
        parent_plan_path=parent_path,
        expected_parent_plan_sha256=parent_sha,
        parent_failure_run_card_path=failure_card,
        expected_parent_failure_run_card_sha256=_sha256(failure_card),
        parent_raw_html_dir=raw_html_dir,
        batch_id="retried-successor-batch",
        run_id="retried-successor-run",
    )

    assert successor.run_id == "retried-successor-run"


def test_successor_mirrors_provisional_source_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, _, _, _, _, _ = _successor_plan(tmp_path, monkeypatch)
    source_config: dict[str, object] = {
        "provisional_frontier": True,
        "final_cohort_eligible": False,
        "full_source_terminal": False,
        "source_candidate_count": 1,
        "success_count": 0,
        "terminal_exclusion_count": 0,
        "pending_count": 1,
    }
    for field in (
        "source_candidate_set_sha256",
        "source_projection_sha256",
        "progress_config_sha256",
        "progress_sha256",
        "success_candidate_set_sha256",
        "terminal_excluded_candidate_set_sha256",
        "pending_candidate_set_sha256",
    ):
        source_config[field] = "a" * 64

    config = recovery._expected_selected_slice_config(  # pyright: ignore[reportPrivateUsage]
        parent, source_batch_config=source_config
    )

    for field, value in source_config.items():
        assert config[field] == value


def test_successor_normalizes_child_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, parent_path, parent_sha, failure_card, failure_card_sha, _ = (
        _successor_plan(tmp_path, monkeypatch)
    )

    successor = build_target_raw_docket_recovery_successor_plan(
        parent_plan_path=parent_path,
        expected_parent_plan_sha256=parent_sha,
        parent_failure_run_card_path=failure_card,
        expected_parent_failure_run_card_sha256=failure_card_sha,
        parent_raw_html_dir=tmp_path / "parent-raw-html",
        batch_id=" child-batch ",
        run_id=" child-run ",
    )

    assert successor.batch_id == "child-batch"
    assert successor.run_id == "child-run"
    assert parent.run_id != successor.run_id


def test_successor_planning_cli_declares_parent_raw_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, parent_path, parent_sha, failure_card, failure_card_sha, _ = _successor_plan(
        tmp_path, monkeypatch
    )
    raw_html_dir = tmp_path / "parent-raw-html"
    output_root = tmp_path / "planning-cli"
    args = cli.build_parser().parse_args(
        [
            "acquisition",
            "plan-target-raw-docket-recovery-successor",
            "--output-root",
            str(output_root),
            "--execute",
            "--no-resume",
            "--parent-plan",
            str(parent_path),
            "--expected-parent-plan-sha256",
            parent_sha,
            "--parent-failure-run-card",
            str(failure_card),
            "--expected-parent-failure-run-card-sha256",
            failure_card_sha,
            "--parent-raw-html-dir",
            str(raw_html_dir),
            "--batch-id",
            "planning-cli-batch",
            "--run-id",
            "planning-cli-run",
            "--plan-output",
            str(output_root / "successor-plan.json"),
        ]
    )

    assert args.handler(args) == 0
    card = json.loads(
        (
            output_root / "run-cards/plan-target-raw-docket-recovery-successor.json"
        ).read_text()
    )
    assert card["input_paths"] == [
        str(parent_path),
        str(failure_card),
        str(raw_html_dir),
    ]


def test_successor_executor_replays_fixture_with_parent_bound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, parent_path, parent_sha, failure_card, failure_card_sha, successor = (
        _successor_plan(tmp_path, monkeypatch)
    )
    successor_path = tmp_path / "successor-plan.json"
    successor_sha = write_target_raw_docket_recovery_successor_plan(
        successor_path, successor
    )
    fixture = tmp_path / "firecrawl.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_recovery_tests._fixture_docket_html(),  # pyright: ignore[reportPrivateUsage]
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
            },
            sort_keys=True,
        )
        + "\n"
    )
    command_args = cast(Any, raw_recovery_tests._command_args)  # pyright: ignore[reportPrivateUsage]
    output_root = tmp_path / "successor-execute"
    args = command_args(
        parent,
        output_root=output_root,
        execute=True,
        plan_output=parent_path,
        firecrawl_fixture=fixture,
    )
    args.successor_plan = successor_path
    args.expected_successor_plan_sha256 = successor_sha

    assert cli._cmd_acquisition_execute_target_raw_docket_recovery_successor(args) == 0  # pyright: ignore[reportPrivateUsage]

    [success] = [
        json.loads(line) for line in args.successes_output.read_text().splitlines()
    ]
    receipt = json.loads(args.receipt_output.read_text())
    assert success["candidate_id"] == "courtlistener-docket-200"
    assert success["target_raw_docket_recovery"]["plan_sha256"] == successor_sha
    assert receipt["plan_sha256"] == successor_sha
    assert receipt["run_id"] == successor.run_id
    assert receipt["batch_id"] == successor.batch_id
    assert receipt["credit_cap"] == parent.credit_cap
    assert receipt["run_config"]["recovery_of_run_id"] == parent.run_id
    assert receipt["run_config"]["parent_plan_sha256"] == parent_sha
    assert receipt["run_config"]["parent_failure_run_card_sha256"] == failure_card_sha
    assert json.loads(args.summary_output.read_text())["success_count"] == 1
    assert failure_card.exists()


def test_successor_cli_exposes_only_parent_pins_and_execution_outputs() -> None:
    acquisition = _subcommand_parser(cli.build_parser(), "acquisition")
    planning = _subcommand_parser(
        acquisition, "plan-target-raw-docket-recovery-successor"
    )
    execution = _subcommand_parser(
        acquisition, "execute-target-raw-docket-recovery-successor"
    )

    planning_options = _long_options(planning)
    assert {
        "--parent-plan",
        "--expected-parent-plan-sha256",
        "--parent-failure-run-card",
        "--expected-parent-failure-run-card-sha256",
        "--parent-raw-html-dir",
        "--batch-id",
        "--run-id",
        "--plan-output",
    } <= planning_options
    execution_options = _long_options(execution)
    assert {
        "--successor-plan",
        "--expected-successor-plan-sha256",
        "--raw-html-dir",
        "--successes-output",
        "--exclusions-output",
        "--summary-output",
        "--receipt-output",
        "--expected-receipt-sha256",
    } <= execution_options

    drift_prone = {
        "--selection",
        "--expected-selection-sha256",
        "--source-snapshot",
        "--expected-source-snapshot-manifest-sha256",
        "--expected-cycle-hash",
        "--source-snapshot-run-card",
        "--expected-source-snapshot-run-card-sha256",
        "--source-raw-manifest",
        "--expected-source-raw-manifest-sha256",
        "--cycle-store",
        "--credit-cap",
        "--workers",
        "--max-pages-per-docket",
        "--max-attempts-per-page",
        "--provider-breaker-threshold",
        "--proxy",
        "--force-browser",
    }
    assert not (planning_options & drift_prone)
    assert not (execution_options & drift_prone)

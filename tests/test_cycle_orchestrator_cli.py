from __future__ import annotations

import fcntl
import json
from pathlib import Path

import pytest
from legalforecast.cli import build_parser, main
from legalforecast.ingestion.cycle_orchestrator import (
    COMMAND_BOUNDARIES,
    BoundaryPermissions,
    CycleOrchestratorError,
    run_acquisition_cycle,
)
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes


def _write_config(
    path: Path,
    *,
    stages: list[dict[str, object]],
) -> Path:
    payload: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_cycle_config.v1",
        "cycle_id": "cycle-next",
        "eligibility_anchor": "2026-06-30",
        "target_case_count": 100,
        "stages": stages,
    }
    path.write_bytes(canonical_json_bytes(payload))
    return path


def _stage(
    *,
    stage_id: str,
    command: str,
    boundary: str,
    arguments: list[str],
    run_card: Path,
    run_card_stage: str | None = None,
) -> dict[str, object]:
    return {
        "id": stage_id,
        "command": command,
        "boundary": boundary,
        "arguments": arguments,
        "run_card": str(run_card),
        "run_card_stage": run_card_stage or command,
    }


def test_run_cycle_help_describes_safe_resume_boundaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "run-cycle", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for expected in (
        "--config",
        "--state-root",
        "--execute",
        "--allow-network",
        "--allow-human",
        "--allow-model-provider",
        "--allow-paid",
        "--json",
    ):
        assert expected in help_text
    assert "evaluation" in help_text
    assert "freeze" in help_text
    assert "dispatch" in help_text


def test_run_cycle_allowlist_contains_only_receipted_acquisition_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for command in COMMAND_BOUNDARIES:
        with pytest.raises(SystemExit) as exc_info:
            main(["acquisition", command, "--help"])
        assert exc_info.value.code == 0, command
        command_help = capsys.readouterr().out
        assert "--execute" in command_help, command
        assert "--run-card-output" in command_help, command
        assert "--resume" in command_help, command


def test_run_cycle_status_reports_provider_free_stage_as_ready(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 0
    )

    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "ready"
    assert status["completed_stage_count"] == 0
    assert status["next_stage"]["id"] == "initialize"
    assert status["next_stage"]["boundary"] == "provider_free"
    assert not (tmp_path / "state").exists()


def test_run_cycle_treats_bare_delegated_system_exit_as_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )
    args = build_parser().parse_args(
        [
            "acquisition",
            "run-cycle",
            "--config",
            str(config),
            "--state-root",
            str(tmp_path / "state"),
            "--execute",
            "--json",
        ]
    )

    def delegated_main(_arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        raise SystemExit

    monkeypatch.setattr("legalforecast.cli.main", delegated_main)

    assert args.handler(args) == 0


def test_run_cycle_executes_provider_free_stage_and_resumes_from_receipt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    command = [
        "acquisition",
        "run-cycle",
        "--config",
        str(config),
        "--state-root",
        str(state_root),
        "--execute",
        "--json",
    ]
    assert main(command) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "completed"
    assert first["completed_stage_count"] == 1
    assert first["plan_completed"] is True
    assert first["corpus_finalization_planned"] is False
    assert first["corpus_target_verified"] is False
    assert first["clean_case_count"] is None
    receipt = state_root / "receipts" / "0000-initialize.json"
    assert receipt.is_file()

    run_card_before = run_card.read_bytes()
    receipt_before = receipt.read_bytes()
    assert main(command) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "completed"
    assert second["stages"][0]["status"] == "completed"
    assert run_card.read_bytes() == run_card_before
    assert receipt.read_bytes() == receipt_before


def test_run_cycle_stops_before_network_without_provider_activity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_root = tmp_path / "init"
    init_run_card = init_root / "run-cards" / "init-cycle.json"
    run_card = tmp_path / "network" / "run-cards" / "discover-courtlistener.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(init_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_run_card),
                    "--execute",
                ],
                run_card=init_run_card,
            ),
            _stage(
                stage_id="discover",
                command="discover-courtlistener",
                boundary="network",
                arguments=[
                    "--output-root",
                    str(tmp_path / "network"),
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--execute",
                "--json",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "blocked"
    assert status["completed_stage_count"] == 1
    assert status["stop_reason"] == "network_boundary_not_authorized"
    assert status["next_stage"]["command"] == "discover-courtlistener"
    assert status["next_stage"]["status"] == "blocked"
    assert not run_card.exists()
    assert not (tmp_path / "state" / "receipts" / "0001-discover.json").exists()


def test_run_cycle_rejects_boundary_downgrade_for_paid_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_card = tmp_path / "paid" / "run-cards" / "purchase.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="purchase",
                command="purchase-missing-recap-fetch",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "paid"),
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
                run_card_stage="purchase-missing-recap-fetch",
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "boundary must be paid" in capsys.readouterr().err


def test_run_cycle_requires_network_authority_before_paid_authority(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _write_config(tmp_path / "cycle.json", stages=[])

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--execute",
                "--allow-paid",
                "--json",
            ]
        )
        == 2
    )
    assert "--allow-paid requires --allow-network" in capsys.readouterr().err


def test_run_cycle_binds_target_count_to_prepare_stage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    prepare_card = tmp_path / "prepare" / "run-cards" / "prepare-target-cohort.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="prepare",
                command="prepare-target-cohort",
                boundary="network",
                arguments=[
                    "--output-root",
                    str(tmp_path / "prepare"),
                    "--target-case-count",
                    "150",
                    "--run-card-output",
                    str(prepare_card),
                    "--execute",
                ],
                run_card=prepare_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "target count differs" in capsys.readouterr().err


def test_run_cycle_rejects_equals_form_identity_override(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--eligibility-anchor=2027-01-01",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "must not use or repeat equals form" in capsys.readouterr().err


def test_run_cycle_binds_target_count_to_finalization_stage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_card = tmp_path / "init" / "run-cards" / "init-cycle.json"
    final_card = tmp_path / "final" / "run-cards" / "finalize-corpus.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "init"),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize",
                command="finalize-corpus",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(tmp_path / "final"),
                    "--target-clean-cases",
                    "150",
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(config),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "finalize-corpus target count differs" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("clean_count", "meets_target", "should_succeed"),
    [(100, True, True), (99, True, False), (100, False, False)],
)
def test_run_cycle_verifies_completed_corpus_target(
    tmp_path: Path,
    clean_count: int,
    meets_target: bool,
    should_succeed: bool,
) -> None:
    init_card = tmp_path / "init-cycle.json"
    final_card = tmp_path / "finalize-corpus.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize",
                command="finalize-corpus",
                boundary="provider_free",
                arguments=[
                    "--target-clean-cases",
                    "100",
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    def write_cards(command: str, _arguments: tuple[str, ...]) -> int:
        card_path = init_card if command == "init-cycle" else final_card
        card: dict[str, object] = {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": command,
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "resume": True,
            "paid_activity_executed": False,
            "output_paths": [],
        }
        if command == "finalize-corpus":
            card.update(
                {
                    "target_clean_cases": 100,
                    "clean_count": clean_count,
                    "meets_target": meets_target,
                }
            )
        card_path.write_bytes(canonical_json_bytes(card))
        return 0

    state_root = tmp_path / "state"
    if should_succeed:
        status = run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_cards,
        )
        assert status["corpus_target_verified"] is True
        assert status["clean_case_count"] == 100
    else:
        with pytest.raises(
            CycleOrchestratorError,
            match="does not verify the configured target",
        ):
            run_acquisition_cycle(
                config_path=config,
                state_root=state_root,
                execute=True,
                permissions=BoundaryPermissions(),
                executor=write_cards,
            )
        assert not (state_root / "receipts" / "0001-finalize.json").exists()


def test_run_cycle_refuses_concurrent_owner_before_stage_execution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )
    state_root.mkdir()
    lock_path = state_root / ".run-cycle.lock"
    with lock_path.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (
            main(
                [
                    "acquisition",
                    "run-cycle",
                    "--config",
                    str(config),
                    "--state-root",
                    str(state_root),
                    "--execute",
                    "--json",
                ]
            )
            == 2
        )

    assert "already owns this state root" in capsys.readouterr().err
    assert not run_card.exists()


def test_run_cycle_refuses_config_change_during_stage(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def mutate_config(_command: str, _arguments: tuple[str, ...]) -> int:
        record = json.loads(config.read_text(encoding="utf-8"))
        record["target_case_count"] = 101
        config.write_bytes(canonical_json_bytes(record))
        return 0

    with pytest.raises(CycleOrchestratorError, match="changed during execution"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=mutate_config,
        )
    assert not (tmp_path / "state" / "receipts" / "0000-initialize.json").exists()


def test_run_cycle_fails_closed_when_receipted_run_card_changes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    state_root = tmp_path / "state"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )
    command = [
        "acquisition",
        "run-cycle",
        "--config",
        str(config),
        "--state-root",
        str(state_root),
        "--execute",
        "--json",
    ]
    assert main(command) == 0
    capsys.readouterr()

    card = json.loads(run_card.read_text(encoding="utf-8"))
    card["record_count"] = 999
    run_card.write_text(json.dumps(card) + "\n", encoding="utf-8")

    assert main(command) == 2
    assert "receipted run card changed" in capsys.readouterr().err


def test_run_cycle_fails_closed_when_receipted_output_changes(
    tmp_path: Path,
) -> None:
    stage_root = tmp_path / "stage"
    run_card = stage_root / "run-cards" / "init-cycle.json"
    output = stage_root / "cycle-identity.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--output-root",
                    str(stage_root),
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("original\n", encoding="utf-8")
        run_card.parent.mkdir(parents=True, exist_ok=True)
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [str(output)],
                }
            )
        )
        return 0

    state_root = tmp_path / "state"
    first = run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_stage,
    )
    assert first["status"] == "completed"

    output.write_text("changed\n", encoding="utf-8")
    with pytest.raises(
        CycleOrchestratorError,
        match="stage receipt no longer matches cycle config",
    ):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_rejects_relative_output_path(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": ["relative-output.json"],
                }
            )
        )
        return 0

    with pytest.raises(CycleOrchestratorError, match="must be absolute"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_rejects_symlink_inside_output_directory(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    output_directory = tmp_path / "output"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "document.txt").write_text("outside\n", encoding="utf-8")
    output_directory.mkdir()
    (output_directory / "escape").symlink_to(outside, target_is_directory=True)
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [str(output_directory)],
                }
            )
        )
        return 0

    with pytest.raises(CycleOrchestratorError, match="contains a symlink"):
        run_acquisition_cycle(
            config_path=config,
            state_root=tmp_path / "state",
            execute=True,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_rejects_symlinked_receipts_directory(
    tmp_path: Path,
) -> None:
    run_card = tmp_path / "init-cycle.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(run_card),
                    "--execute",
                ],
                run_card=run_card,
            )
        ],
    )

    def write_stage(_command: str, _arguments: tuple[str, ...]) -> int:
        run_card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "init-cycle",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "resume": True,
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    state_root = tmp_path / "state"
    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_stage,
    )
    receipts = state_root / "receipts"
    relocated = state_root / "receipts-relocated"
    receipts.rename(relocated)
    receipts.symlink_to(relocated, target_is_directory=True)

    with pytest.raises(CycleOrchestratorError, match="must not contain symlinks"):
        run_acquisition_cycle(
            config_path=config,
            state_root=state_root,
            execute=False,
            permissions=BoundaryPermissions(),
            executor=write_stage,
        )


def test_run_cycle_accepts_known_specialized_resume_card_without_resume_field(
    tmp_path: Path,
) -> None:
    init_card = tmp_path / "init-cycle.json"
    final_card = tmp_path / "finalize-provenance-quarantine.json"
    config = _write_config(
        tmp_path / "cycle.json",
        stages=[
            _stage(
                stage_id="initialize",
                command="init-cycle",
                boundary="provider_free",
                arguments=[
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--run-card-output",
                    str(init_card),
                    "--execute",
                ],
                run_card=init_card,
            ),
            _stage(
                stage_id="finalize-disclosure",
                command="finalize-provenance-quarantine",
                boundary="provider_free",
                arguments=[
                    "--run-card-output",
                    str(final_card),
                    "--execute",
                ],
                run_card=final_card,
            ),
        ],
    )

    def write_cards(command: str, _arguments: tuple[str, ...]) -> int:
        card_path = init_card if command == "init-cycle" else final_card
        card_path.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": (
                        "legalforecast.acquisition_run_card.v1"
                        if command == "init-cycle"
                        else (
                            "legalforecast.provenance_quarantine_clearance_run_card.v1"
                        )
                    ),
                    "stage": command,
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    **({"resume": True} if command == "init-cycle" else {}),
                    "paid_activity_executed": False,
                    "output_paths": [],
                }
            )
        )
        return 0

    status = run_acquisition_cycle(
        config_path=config,
        state_root=tmp_path / "state",
        execute=True,
        permissions=BoundaryPermissions(),
        executor=write_cards,
    )

    assert status["status"] == "completed"
    assert status["completed_stage_count"] == 2


def test_run_cycle_rejects_noncanonical_or_linked_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_cycle_config.v1",
        "cycle_id": "cycle-next",
        "eligibility_anchor": "2026-06-30",
        "target_case_count": 100,
        "stages": [],
    }
    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(noncanonical),
                "--state-root",
                str(tmp_path / "state"),
                "--json",
            ]
        )
        == 2
    )
    assert "canonical JSON" in capsys.readouterr().err

    canonical = _write_config(tmp_path / "canonical.json", stages=[])
    linked = tmp_path / "linked.json"
    linked.hardlink_to(canonical)
    assert (
        main(
            [
                "acquisition",
                "run-cycle",
                "--config",
                str(linked),
                "--state-root",
                str(tmp_path / "state-2"),
                "--json",
            ]
        )
        == 2
    )
    assert "unique regular file" in capsys.readouterr().err

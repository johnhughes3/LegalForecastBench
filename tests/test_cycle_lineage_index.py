from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_lineage_index import (
    CycleLineageIndexError,
    locate_cycle_lineage,
    register_cycle_lineage,
    register_cycle_stage_head,
)
from legalforecast.ingestion.cycle_orchestrator import (
    BoundaryPermissions,
    run_acquisition_cycle,
)
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


def _write_cycle(
    root: Path,
    *,
    cycle_id: str = "cycle-1",
    human_stage: bool = False,
    complete_human: bool = True,
) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True)
    output = root / "output.json"
    output.write_text("completed\n", encoding="utf-8")
    init_card = root / "run-cards/init.json"
    human_card = root / "run-cards/review.json"
    stages: list[dict[str, object]] = [
        {
            "id": "initialize",
            "command": "init-cycle",
            "boundary": "provider_free",
            "arguments": [
                "--eligibility-anchor",
                "2026-06-30",
                "--output-root",
                str(root),
                "--run-card-output",
                str(init_card),
                "--execute",
            ],
            "run_card": str(init_card),
            "run_card_stage": "init-cycle",
        }
    ]
    if human_stage:
        stages.append(
            {
                "id": "record-review",
                "command": "record-disclosure-review-decisions",
                "boundary": "human",
                "arguments": [
                    "--run-card-output",
                    str(human_card),
                    "--execute",
                ],
                "run_card": str(human_card),
                "run_card_stage": "record-disclosure-review-decisions",
            }
        )
    config = root / "cycle.json"
    config.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_cycle_config.v1",
                "cycle_id": cycle_id,
                "eligibility_anchor": "2026-06-30",
                "target_case_count": 100,
                "stages": stages,
            }
        )
    )
    state_root = root / "state"

    def execute(command: str, _arguments: tuple[str, ...]) -> int:
        card = init_card if command == "init-cycle" else human_card
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_bytes(
            canonical_json_bytes(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": command,
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

    run_acquisition_cycle(
        config_path=config,
        state_root=state_root,
        execute=True,
        permissions=BoundaryPermissions(human=human_stage and complete_human),
        executor=execute,
    )
    return config, state_root, human_card


def test_register_and_locate_reauthenticates_without_exposing_local_paths(
    tmp_path: Path,
) -> None:
    config, state_root, _ = _write_cycle(tmp_path / "cycle")
    index = tmp_path / "lineage-index.json"

    registered = register_cycle_lineage(
        index_path=index,
        config_path=config,
        state_root=state_root,
        code_commit=COMMIT_A,
    )
    assert registered["cycle_id"] == "cycle-1"

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["verification"] == "VERIFIED"
    assert status["code_commit"] == COMMIT_A
    assert status["stage"] == "initialize"
    assert status["stage_status"] == "completed"
    assert status["config_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    card = cast(Mapping[str, object], status["card"])
    assert (
        card["sha256"]
        == hashlib.sha256(
            (tmp_path / "cycle/run-cards/init.json").read_bytes()
        ).hexdigest()
    )
    assert status["artifact_hashes"] == [
        {
            "byte_count": len(b"completed\n"),
            "kind": "file",
            "sha256": hashlib.sha256(b"completed\n").hexdigest(),
        }
    ]
    rendered = json.dumps(status, sort_keys=True)
    assert str(tmp_path) not in rendered
    assert status["authority"] == {
        "dispatch": False,
        "evaluation": False,
        "freeze": False,
        "publication": False,
        "purchase": False,
    }

    (tmp_path / "cycle/output.json").write_text("changed\n", encoding="utf-8")
    with pytest.raises(CycleLineageIndexError, match="receipt no longer matches"):
        locate_cycle_lineage(index_path=index, cycle_id="cycle-1")


def test_successor_is_current_and_completed_human_decision_is_visible(
    tmp_path: Path,
) -> None:
    old_config, old_state, _ = _write_cycle(tmp_path / "old")
    new_config, new_state, _ = _write_cycle(tmp_path / "new", human_stage=True)
    index = tmp_path / "lineage-index.json"
    old = register_cycle_lineage(
        index_path=index,
        config_path=old_config,
        state_root=old_state,
        code_commit=COMMIT_A,
    )
    register_cycle_lineage(
        index_path=index,
        config_path=new_config,
        state_root=new_state,
        code_commit=COMMIT_B,
        supersedes_config_sha256=str(old["config_sha256"]),
    )

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["code_commit"] == COMMIT_B
    assert status["supersedes_config_sha256"] == old["config_sha256"]
    card = cast(Mapping[str, object], status["card"])
    assert status["human_decisions"] == [
        {
            "card_sha256": card["sha256"],
            "stage": "record-review",
            "status": "recorded",
            "verification": "VERIFIED",
        }
    ]


def test_missing_corrupt_and_ambiguous_index_fail_closed(tmp_path: Path) -> None:
    index = tmp_path / "lineage-index.json"
    with pytest.raises(CycleLineageIndexError, match="does not exist"):
        locate_cycle_lineage(index_path=index, cycle_id="cycle-1")

    index.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(CycleLineageIndexError, match="valid UTF-8 JSON"):
        locate_cycle_lineage(index_path=index, cycle_id="cycle-1")

    first_config, first_state, _ = _write_cycle(tmp_path / "first")
    second_config, second_state, _ = _write_cycle(tmp_path / "second")
    index.unlink()
    register_cycle_lineage(
        index_path=index,
        config_path=first_config,
        state_root=first_state,
        code_commit=COMMIT_A,
    )
    register_cycle_lineage(
        index_path=index,
        config_path=second_config,
        state_root=second_state,
        code_commit=COMMIT_B,
    )
    with pytest.raises(CycleLineageIndexError, match="ambiguous active lineages"):
        locate_cycle_lineage(index_path=index, cycle_id="cycle-1")


def test_late_unreceipted_human_decision_is_visible_but_never_verified(
    tmp_path: Path,
) -> None:
    config, state_root, human_card = _write_cycle(
        tmp_path / "cycle", human_stage=True, complete_human=False
    )
    human_card.parent.mkdir(parents=True, exist_ok=True)
    human_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "record-disclosure-review-decisions",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "paid_activity_executed": False,
                "output_paths": [str(tmp_path / "cycle/output.json")],
            }
        )
    )
    index = tmp_path / "lineage-index.json"
    register_cycle_lineage(
        index_path=index,
        config_path=config,
        state_root=state_root,
        code_commit=COMMIT_A,
    )

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["human_decisions"] == [
        {
            "card_sha256": hashlib.sha256(human_card.read_bytes()).hexdigest(),
            "stage": "record-review",
            "status": "recorded_unreceipted",
            "verification": "UNVERIFIED",
        }
    ]


def test_direct_stage_continuation_supersedes_decision_and_keeps_it_visible(
    tmp_path: Path,
) -> None:
    index = tmp_path / "lineage-index.json"
    decision_output = tmp_path / "decision.jsonl"
    decision_output.write_text("decision\n", encoding="utf-8")
    decision_card = tmp_path / "cards/decision.json"
    decision_card.parent.mkdir()
    decision_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "record-disclosure-review-decisions",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": True,
                "paid_activity_executed": False,
                "output_paths": [str(decision_output)],
            }
        )
    )
    decision = register_cycle_stage_head(
        index_path=index,
        cycle_id="cycle-1",
        command="record-disclosure-review-decisions",
        run_card_path=decision_card,
        code_commit=COMMIT_A,
    )

    parse_output = tmp_path / "parse.jsonl"
    parse_output.write_text("parsed\n", encoding="utf-8")
    parse_card = tmp_path / "cards/parse.json"
    parse_card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "parse-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "resume": False,
                "paid_activity_executed": False,
                "output_paths": [str(parse_output)],
            }
        )
    )
    register_cycle_stage_head(
        index_path=index,
        cycle_id="cycle-1",
        command="parse-documents",
        run_card_path=parse_card,
        code_commit=COMMIT_B,
        supersedes_root_identity_sha256=str(decision["root_identity_sha256"]),
    )

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["stage"] == "parse-documents"
    assert status["code_commit"] == COMMIT_B
    assert status["human_decisions"] == [
        {
            "card_sha256": hashlib.sha256(decision_card.read_bytes()).hexdigest(),
            "stage": "record-disclosure-review-decisions",
            "status": "recorded",
            "verification": "VERIFIED",
        }
    ]


def test_nested_replacement_approval_card_is_authenticated(tmp_path: Path) -> None:
    body: dict[str, object] = {
        "stage": "record-replacement-purchase-approval",
        "status": "completed",
        "decision": "approve",
        "request_sha256": "1" * 64,
        "checkpoint_sha256": "2" * 64,
        "reviewer_id": "reviewer",
        "recorded_at_utc": "2026-08-07T00:00:00Z",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_fee_acknowledged": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    body_sha256 = hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    card = tmp_path / "approval.json"
    card.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": (
                    "legalforecast.replacement_purchase_approval_run_card.v2"
                ),
                "run_card": body,
                "run_card_sha256": body_sha256,
            }
        )
    )
    index = tmp_path / "lineage-index.json"
    register_cycle_stage_head(
        index_path=index,
        cycle_id="cycle-1",
        command="record-replacement-purchase-approval",
        run_card_path=card,
        code_commit=COMMIT_A,
    )

    status = locate_cycle_lineage(index_path=index, cycle_id="cycle-1")
    assert status["stage"] == "record-replacement-purchase-approval"
    assert status["human_decisions"] == [
        {
            "card_sha256": hashlib.sha256(card.read_bytes()).hexdigest(),
            "stage": "record-replacement-purchase-approval",
            "status": "recorded",
            "verification": "VERIFIED",
        }
    ]


def test_empty_cache_rebuild_and_cli_environment_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, state_root, _ = _write_cycle(tmp_path / "cycle")
    index = tmp_path / "lineage-index.json"
    monkeypatch.setenv("LEGALFORECAST_CYCLE_LINEAGE_INDEX", str(index))

    assert (
        main(
            [
                "acquisition",
                "register-cycle-lineage",
                "--config",
                str(config),
                "--state-root",
                str(state_root),
                "--code-commit",
                COMMIT_A,
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "acquisition",
                "locate-cycle-lineage",
                "--cycle-id",
                "cycle-1",
                "--json",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["verification"] == "VERIFIED"

    index.unlink()
    assert main(["acquisition", "locate-cycle-lineage", "--cycle-id", "cycle-1"]) == 2
    assert "register-cycle-lineage" in capsys.readouterr().err

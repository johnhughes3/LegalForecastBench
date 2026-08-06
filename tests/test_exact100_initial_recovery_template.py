from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_manifest_template import (
    CycleManifestTemplateError,
    render_cycle_config,
)
from legalforecast.ingestion.cycle_orchestrator import load_cycle_config

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    ROOT / "manifests" / "cycle-1-target-100.exact100-initial-recovery.template.json"
)
DISCLOSURE_TEMPLATES = (
    ROOT / "manifests" / "cycle-1-target-100.initial-recovery-disclosure.template.json",
    ROOT
    / "manifests"
    / "cycle-1-target-100.initial-recovery-disclosure-no-review.template.json",
)


def _assignments(tmp_path: Path) -> dict[str, Path]:
    return {
        "CYCLE_ROOT": tmp_path / "cycle",
        "INITIAL_APPROVED_ROOT": tmp_path / "initial-approved",
        "PURCHASE_AUTHORITY_ROOT": tmp_path / "purchase-authority",
        "PURCHASE_PRIVATE_ROOT": tmp_path / "purchase-private",
        "RECOVERY_ROOT": tmp_path / "recovery",
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
    }


def _render(tmp_path: Path) -> tuple[dict[str, Path], Path, dict[str, object]]:
    assignments = _assignments(tmp_path)
    output = tmp_path / "rendered" / "cycle.json"
    output.parent.mkdir()
    receipt = render_cycle_config(
        template_path=TEMPLATE,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    return assignments, output, receipt


def test_exact100_initial_recovery_template_binds_noncharging_inputs(
    tmp_path: Path,
) -> None:
    assignments, output, receipt = _render(tmp_path)
    config = load_cycle_config(output)

    assert receipt["completion_mode"] == "partial"
    assert receipt["stage_count"] == 2
    assert receipt["provider_activity_requested"] is False
    assert receipt["paid_activity_requested"] is False
    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "recover-recap-fetch-quarantine",
    ]
    assert [stage.boundary.value for stage in config.stages] == [
        "provider_free",
        "network",
    ]

    recovery = config.stages[1]
    expected_bindings = {
        "--selection": assignments["INITIAL_APPROVED_ROOT"]
        / "target-cohort-selection.jsonl",
        "--case-relevance": assignments["INITIAL_APPROVED_ROOT"]
        / "case-relevance.jsonl",
        "--target-projection-run-card": assignments["INITIAL_APPROVED_ROOT"]
        / "run-cards"
        / "project-target-cohort.json",
        "--purchase-policy": assignments["PURCHASE_AUTHORITY_ROOT"]
        / "purchase-policy-v2.json",
        "--cohort-policy": assignments["REPO_ROOT"]
        / "docs"
        / "cohort-policy-cycle-1-target-100-2026-07-25.json",
        "--budget-plan": assignments["INITIAL_APPROVED_ROOT"]
        / "missing-core-budget-plan.json",
        "--purchase-ledger": assignments["PURCHASE_AUTHORITY_ROOT"]
        / "cycle-1-target100-recap-fetch-purchase-ledger.sqlite3",
        "--controlled-private-root": assignments["PURCHASE_PRIVATE_ROOT"],
        "--purchase-ledger-initialization-receipt": assignments[
            "PURCHASE_AUTHORITY_ROOT"
        ]
        / "purchase-ledger-initialization.json",
        "--attempt-policy": assignments["PURCHASE_AUTHORITY_ROOT"]
        / "recap-fetch-attempt-policy.json",
        "--manifest-output": assignments["RECOVERY_ROOT"]
        / "recap-fetch-quarantine-downloads.jsonl",
        "--case-relevance-output": assignments["RECOVERY_ROOT"]
        / "purchased-case-relevance.jsonl",
        "--restriction-evidence-output": assignments["RECOVERY_ROOT"]
        / "post-recovery-restriction-evidence.jsonl",
        "--terminal-unavailable-output": assignments["RECOVERY_ROOT"]
        / "terminal-unavailable-operations.jsonl",
        "--review-requests-output": assignments["RECOVERY_ROOT"]
        / "disclosure-review-requests.jsonl",
        "--document-output-root": assignments["RECOVERY_ROOT"]
        / "documents"
        / "recap-fetch-quarantine",
        "--request-ledger": assignments["SOURCE_ROOT"]
        / "courtlistener-request-ledger-base-v1.sqlite3",
    }
    for flag, expected in expected_bindings.items():
        index = recovery.arguments.index(flag)
        assert recovery.arguments[index + 1] == str(expected)

    assert "--live-courtlistener-recovery" in recovery.arguments
    assert "--execute" in recovery.arguments
    assert "--resume" in recovery.arguments
    forbidden = {
        "--acknowledge-pacer-fees",
        "--broker-policy",
        "--direct-courtlistener-purchase",
        "--live-purchase",
        "--replacement-purchase-authority",
    }
    assert forbidden.isdisjoint(recovery.arguments)
    forbidden_commands = {
        "build-packets",
        "clear-provenance-disclosures",
        "dispatch",
        "evaluate",
        "finalize-corpus",
        "freeze",
        "llm-label",
        "llm-unitize",
        "parse-documents",
        "purchase-missing-recap-fetch",
    }
    assert forbidden_commands.isdisjoint(stage.command for stage in config.stages)


@pytest.mark.parametrize("disclosure_template", DISCLOSURE_TEMPLATES)
def test_exact100_recovery_outputs_feed_disclosure_continuations_exactly(
    tmp_path: Path,
    disclosure_template: Path,
) -> None:
    assignments, output, _receipt = _render(tmp_path)
    recovery = load_cycle_config(output).stages[1]
    output_to_input_flag = {
        "--manifest-output": "--download-manifest",
        "--case-relevance-output": "--case-relevance",
        "--restriction-evidence-output": "--restriction-evidence",
        "--terminal-unavailable-output": None,
        "--review-requests-output": "--review-requests",
        "--document-output-root": "--document-root",
    }
    disclosure = json.loads(disclosure_template.read_bytes())
    disclosure_stages = disclosure["config"]["stages"]
    unconsumed_outputs: set[str] = set()

    for output_flag, input_flag in output_to_input_flag.items():
        recovery_output = recovery.arguments[recovery.arguments.index(output_flag) + 1]
        if input_flag is None:
            unconsumed_outputs.add(recovery_output)
            assert all(
                recovery_output
                not in {
                    argument.replace(
                        "${RECOVERY_ROOT}", str(assignments["RECOVERY_ROOT"])
                    )
                    for argument in stage["arguments"]
                    if isinstance(argument, str)
                }
                for stage in disclosure_stages
            )
            continue

        continuation_inputs = {
            stage["arguments"][stage["arguments"].index(input_flag) + 1].replace(
                "${RECOVERY_ROOT}", str(assignments["RECOVERY_ROOT"])
            )
            for stage in disclosure_stages
            if input_flag in stage["arguments"]
        }
        assert continuation_inputs == {recovery_output}

    assert unconsumed_outputs == {
        str(assignments["RECOVERY_ROOT"] / "terminal-unavailable-operations.jsonl")
    }


def test_exact100_initial_recovery_cycle_stops_before_network(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assignments, config, _receipt = _render(tmp_path)
    state_root = assignments["CYCLE_ROOT"] / "orchestrator"

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
        == 0
    )
    status = json.loads(capsys.readouterr().out)

    assert status["status"] == "blocked"
    assert status["completed_stage_count"] == 1
    assert status["stop_reason"] == "network_boundary_not_authorized"
    assert status["next_stage"]["command"] == "recover-recap-fetch-quarantine"
    assert status["next_stage"]["status"] == "blocked"
    assert not assignments["RECOVERY_ROOT"].exists()
    assert not (
        state_root / "receipts" / "0001-recover-purchased-documents.json"
    ).exists()


def test_exact100_initial_recovery_template_rejects_successor_root_alias(
    tmp_path: Path,
) -> None:
    assignments = _assignments(tmp_path)
    assignments.pop("INITIAL_APPROVED_ROOT")
    assignments["EXACT100_ROOT"] = tmp_path / "later-successor"

    with pytest.raises(
        CycleManifestTemplateError,
        match=(
            "missing variables: INITIAL_APPROVED_ROOT; "
            "unexpected variables: EXACT100_ROOT"
        ),
    ):
        render_cycle_config(
            template_path=TEMPLATE,
            output_path=tmp_path / "must-not-exist.json",
            variable_assignments=[
                f"{name}={path}" for name, path in assignments.items()
            ],
        )

    assert not (tmp_path / "must-not-exist.json").exists()

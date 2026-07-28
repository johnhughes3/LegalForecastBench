from __future__ import annotations

import json
from pathlib import Path

from legalforecast.ingestion.cycle_manifest_template import render_cycle_config
from legalforecast.ingestion.cycle_orchestrator import (
    AcquisitionCycleConfig,
    CycleStage,
    load_cycle_config,
)

_MANIFESTS = Path(__file__).parents[1] / "manifests"
_SUCCESSOR_TEMPLATE = (
    _MANIFESTS / "cycle-1-target-100.quarantine-successor.template.json"
)
_V2_TEMPLATE = _MANIFESTS / "cycle-1-target-100.acquisition-cycle.template.json"


def _render_successor(
    tmp_path: Path,
) -> tuple[dict[str, object], AcquisitionCycleConfig]:
    output = tmp_path / "rendered" / "acquisition-cycle.json"
    output.parent.mkdir()
    assignments = {
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
        "FROZEN_ARTIFACT_ROOT": tmp_path / "frozen-v2",
        "SUCCESSOR_ARTIFACT_ROOT": tmp_path / "successor-v3",
        "SUCCESSOR_PRIVATE_ROOT": tmp_path / "private-v3",
        "PARSER_ROOT": tmp_path / "parser",
    }
    receipt = render_cycle_config(
        template_path=_SUCCESSOR_TEMPLATE,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    return receipt, load_cycle_config(output)


def _argument_value(stage: CycleStage, option: str) -> str:
    arguments = stage.arguments
    return arguments[arguments.index(option) + 1]


def test_v3_quarantine_successor_renders_complete_exact_100_plan(
    tmp_path: Path,
) -> None:
    receipt, config = _render_successor(tmp_path)
    commands = [stage.command for stage in config.stages]

    assert receipt["completion_mode"] == "corpus"
    assert receipt["corpus_finalization_planned"] is True
    assert receipt["stage_count"] == 25
    assert config.cycle_id == "cycle-1-target-100-2026-07-25-v3-quarantine"
    assert config.target_case_count == 100
    assert commands[:4] == [
        "init-cycle",
        "plan-disclosure-provenance",
        "finalize-provenance-quarantine",
        "project-target-cohort",
    ]
    assert commands[-1] == "finalize-corpus"
    assert "record-disclosure-review-decisions" not in commands[:4]
    assert not {"evaluate", "freeze", "dispatch"} & set(commands)

    initialize, plan, quarantine, projection = config.stages[:4]
    assert _argument_value(initialize, "--cycle-store") == str(
        tmp_path / "successor-v3" / "00-cycle" / "cycle-acquisition.sqlite3"
    )
    assert _argument_value(plan, "--schema-version") == "v3"
    assert plan.boundary.value == "provider_free"
    assert quarantine.boundary.value == "provider_free"
    assert projection.boundary.value == "provider_free"
    assert _argument_value(projection, "--target-case-count") == "100"
    assert _argument_value(projection, "--max-projected-budget-usd") == "567.30"
    assert _argument_value(projection, "--cost-per-document-usd") == "3.05"


def test_v3_quarantine_successor_never_writes_frozen_v2_root(
    tmp_path: Path,
) -> None:
    _, config = _render_successor(tmp_path)
    frozen_root = tmp_path / "frozen-v2"
    successor_root = tmp_path / "successor-v3"
    output_options = {
        "--output-root",
        "--identity-output",
        "--log-output",
        "--run-card-output",
        "--routing-plan-output",
        "--exception-worksheet-output",
        "--clearance-output",
        "--quarantine-output",
        "--authority-output",
        "--attempt-policy-output",
        "--initialization-receipt-output",
        "--purchase-output",
        "--manifest-output",
        "--case-relevance-output",
        "--restriction-evidence-output",
        "--review-requests-output",
        "--document-output-root",
        "--resolved-output",
        "--requests-output",
        "--markdown-output-root",
        "--prediction-units-output",
        "--audit-output",
        "--unitization-review-queue-output",
        "--structural-flags-output",
        "--review-queue-output",
        "--finalized-prediction-units-output",
        "--decision-texts-output",
        "--decision-texts-manifest-output",
        "--labels-output",
        "--lawyer-review-queue-output",
        "--cycle-label-audit-summary-output",
        "--adjudication-routing-summary-output",
        "--planned-llm-label-audit-output",
        "--packet-build-input-output",
        "--document-manifest-output",
        "--candidate-manifest-output",
        "--extracted-texts-output",
        "--exclusion-ledger-output",
        "--packets-output",
        "--case-packets-output",
        "--complete-exclusion-ledger-output",
        "--readiness-output",
    }

    for stage in config.stages:
        assert stage.run_card.is_relative_to(
            successor_root
        ) or stage.run_card.is_relative_to(tmp_path / "private-v3")
        for index, argument in enumerate(stage.arguments[:-1]):
            if argument in output_options:
                output = Path(stage.arguments[index + 1])
                assert not output.is_relative_to(frozen_root)

    frozen_inputs = {
        _argument_value(config.stages[1], "--review-requests"),
        _argument_value(config.stages[1], "--download-manifest"),
        _argument_value(config.stages[1], "--case-relevance"),
        _argument_value(config.stages[1], "--document-root"),
        _argument_value(config.stages[1], "--restriction-evidence"),
        _argument_value(config.stages[3], "--preparation-summary"),
        _argument_value(config.stages[3], "--preparation-config"),
    }
    assert frozen_inputs
    assert all(Path(path).is_relative_to(frozen_root) for path in frozen_inputs)


def test_v3_quarantine_successor_has_no_human_or_model_clearance_substitution(
    tmp_path: Path,
) -> None:
    _, config = _render_successor(tmp_path)
    quarantine = config.stages[2]

    assert quarantine.command == "finalize-provenance-quarantine"
    assert not {
        "--exception-decisions",
        "--exception-review-run-card",
        "--reviewer-id",
        "--model-key",
        "--model-registry",
        "--provider-cycle-caps",
        "--provider-journal",
    } & set(quarantine.arguments)
    assert _argument_value(quarantine, "--routing-plan").endswith(
        "/03-free-disclosure-plan-v3/disclosure-provenance-plan.json"
    )
    assert _argument_value(quarantine, "--exception-worksheet").endswith(
        "/03-free-disclosure-plan-v3/disclosure-exception-worksheet.json"
    )


def test_v3_quarantine_successor_preserves_unchanged_downstream_tail() -> None:
    successor = json.loads(_SUCCESSOR_TEMPLATE.read_bytes())
    v2 = json.loads(_V2_TEMPLATE.read_bytes())
    expected_tail = json.loads(
        json.dumps(v2["config"]["stages"][6:])
        .replace(
            "${ARTIFACT_ROOT}/02-preparation",
            "${FROZEN_ARTIFACT_ROOT}/02-preparation",
        )
        .replace(
            "${ARTIFACT_ROOT}/05-target-cohort",
            "${SUCCESSOR_ARTIFACT_ROOT}/05-target-cohort-v3",
        )
        .replace("${ARTIFACT_ROOT}", "${SUCCESSOR_ARTIFACT_ROOT}")
        .replace("${PRIVATE_ROOT}", "${SUCCESSOR_PRIVATE_ROOT}")
    )

    assert successor["config"]["stages"][4:] == expected_tail

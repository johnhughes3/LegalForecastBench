from __future__ import annotations

from pathlib import Path

from legalforecast.ingestion.cycle_manifest_template import render_cycle_config
from legalforecast.ingestion.cycle_orchestrator import (
    AcquisitionCycleConfig,
    CycleStage,
    load_cycle_config,
)

_TEMPLATE = (
    Path(__file__).parents[1]
    / "manifests"
    / "cycle-1-target-100.v4-ranked-reserve.template.json"
)


def _render(tmp_path: Path) -> tuple[dict[str, object], AcquisitionCycleConfig]:
    output = tmp_path / "rendered" / "acquisition-cycle.json"
    output.parent.mkdir()
    assignments = {
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
        "FROZEN_ARTIFACT_ROOT": tmp_path / "frozen-preparation",
        "FROZEN_V4_ROOT": tmp_path / "frozen-v4",
        "APPROVAL_ROOT": tmp_path / "private-approval",
        "SUCCESSOR_ARTIFACT_ROOT": tmp_path / "successor-v4",
        "SUCCESSOR_PRIVATE_ROOT": tmp_path / "private-v4",
        "PARSER_ROOT": tmp_path / "parser",
    }
    receipt = render_cycle_config(
        template_path=_TEMPLATE,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    return receipt, load_cycle_config(output)


def _argument_value(stage: CycleStage, option: str) -> str:
    return stage.arguments[stage.arguments.index(option) + 1]


def test_v4_ranked_reserve_template_binds_existing_approved_projection(
    tmp_path: Path,
) -> None:
    receipt, config = _render(tmp_path)
    commands = [stage.command for stage in config.stages]
    frozen_v4 = tmp_path / "frozen-v4"
    approval_root = tmp_path / "private-approval"
    authority_root = tmp_path / "successor-v4" / "06-purchase-authority"

    assert receipt["completion_mode"] == "corpus"
    assert receipt["corpus_finalization_planned"] is True
    assert config.cycle_id == "cycle-1-target-100-2026-07-25-v4-ranked-reserve"
    assert config.target_case_count == 100
    assert commands[:4] == [
        "init-cycle",
        "generate-recap-fetch-broker-policy",
        "init-purchase-ledger",
        "purchase-missing-recap-fetch",
    ]
    assert commands[-1] == "finalize-corpus"
    assert "record-purchase-approval" not in commands
    assert "project-target-cohort" not in commands
    assert not {"evaluate", "freeze", "dispatch"} & set(commands)

    broker, ledger, purchase = config.stages[1:4]
    assert broker.boundary.value == "provider_free"
    assert _argument_value(broker, "--budget-plan") == str(
        frozen_v4 / "missing-core-budget-plan.json"
    )
    assert _argument_value(broker, "--selection") == str(
        frozen_v4 / "target-cohort-selection.jsonl"
    )
    assert _argument_value(broker, "--purchase-policy") == str(
        authority_root / "purchase-policy-v2.json"
    )
    assert _argument_value(broker, "--attempt-policy") == str(
        authority_root / "recap-fetch-attempt-policy.json"
    )
    assert _argument_value(broker, "--controlled-private-root") == str(approval_root)
    assert _argument_value(ledger, "--initialization-receipt-output") == str(
        authority_root / "purchase-ledger-initialization.json"
    )
    assert _argument_value(purchase, "--broker-policy") == str(
        authority_root / "recap-fetch-broker-policy.json"
    )
    assert _argument_value(purchase, "--purchase-ledger-initialization-receipt") == (
        str(authority_root / "purchase-ledger-initialization.json")
    )


def test_v4_ranked_reserve_template_never_writes_frozen_evidence(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    frozen_v4 = tmp_path / "frozen-v4"
    approval_root = tmp_path / "private-approval"
    successor_root = tmp_path / "successor-v4"
    successor_private = tmp_path / "private-v4"
    output_options = {
        "--output-root",
        "--identity-output",
        "--log-output",
        "--run-card-output",
        "--output",
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
        ) or stage.run_card.is_relative_to(successor_private)
        for index, argument in enumerate(stage.arguments[:-1]):
            if argument in output_options:
                output = Path(stage.arguments[index + 1])
                assert not output.is_relative_to(frozen_v4)
                assert not output.is_relative_to(approval_root)


def test_v4_ranked_reserve_template_binds_provider_caps_successor(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    expected_caps = (
        tmp_path / "successor-v4" / "01-provider-authority" / "provider-cycle-caps.json"
    )
    consumers = [
        stage for stage in config.stages if "--provider-cycle-caps" in stage.arguments
    ]

    assert consumers
    assert all(
        _argument_value(stage, "--provider-cycle-caps") == str(expected_caps)
        for stage in consumers
    )

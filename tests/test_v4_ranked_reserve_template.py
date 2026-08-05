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
    authority_root = tmp_path / "successor-v4" / "06-purchase-authority"

    assert receipt["completion_mode"] == "corpus"
    assert receipt["corpus_finalization_planned"] is True
    assert config.cycle_id == "cycle-1-target-100-2026-07-25-v4-ranked-reserve"
    assert config.target_case_count == 100
    assert commands[:3] == [
        "init-cycle",
        "init-purchase-ledger",
        "purchase-missing-recap-fetch",
    ]
    assert commands[-1] == "finalize-corpus"
    assert "record-purchase-approval" not in commands
    assert "project-target-cohort" not in commands
    assert not {"evaluate", "freeze", "dispatch"} & set(commands)

    ledger, purchase = config.stages[1:3]
    assert _argument_value(config.stages[0], "--cycle-store") == str(
        tmp_path / "successor-v4" / "00-cycle" / "cycle-acquisition.sqlite3"
    )
    assert _argument_value(ledger, "--initialization-receipt-output") == str(
        authority_root / "purchase-ledger-initialization.json"
    )
    expected_ledger = str(
        authority_root / "cycle-1-target100-recap-fetch-purchase-ledger.sqlite3"
    )
    assert _argument_value(ledger, "--purchase-ledger") == expected_ledger
    assert "--direct-courtlistener-purchase" in purchase.arguments
    assert "--broker-policy" not in purchase.arguments
    assert _argument_value(purchase, "--request-budget-max-wait-seconds") == "3700"
    assert all(
        "--controlled-private-root" not in stage.arguments for stage in config.stages
    )
    assert _argument_value(purchase, "--purchase-ledger-initialization-receipt") == (
        str(authority_root / "purchase-ledger-initialization.json")
    )
    assert _argument_value(purchase, "--purchase-ledger") == expected_ledger


def test_v4_ranked_reserve_template_never_writes_frozen_evidence(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    frozen_v4 = tmp_path / "frozen-v4"
    successor_root = tmp_path / "successor-v4"
    successor_private = tmp_path / "private-v4"
    successor_roots = tuple(
        root.resolve() for root in (successor_root, successor_private)
    )
    frozen_v4 = frozen_v4.resolve()
    stateful_options = {"--cycle-store", "--provider-journal", "--purchase-ledger"}

    for stage in config.stages:
        run_card = stage.run_card.resolve()
        assert any(run_card.is_relative_to(root) for root in successor_roots)
        for index, argument in enumerate(stage.arguments[:-1]):
            if (
                argument == "--output"
                or argument.endswith("-output")
                or argument.endswith("-output-root")
                or argument in stateful_options
            ):
                output = Path(stage.arguments[index + 1]).resolve()
                assert not output.is_relative_to(frozen_v4)
                assert any(output.is_relative_to(root) for root in successor_roots)

        assert "--allow-paid" not in stage.arguments
        assert "--allow-network" not in stage.arguments


def test_v4_ranked_reserve_template_merges_protected_stage_b_shards(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    label_stage = next(stage for stage in config.stages if stage.command == "llm-label")

    shard_root = tmp_path / "successor-v4" / "19-stage-b-shards"
    assert label_stage.stage_id == "merge-stage-b-provider-shards"
    assert label_stage.boundary.value == "model_provider"
    assert "--execution-provider" not in label_stage.arguments
    assert "--provider-authority-table" not in label_stage.arguments
    assert "--provider-authority-region" not in label_stage.arguments
    assert [
        label_stage.arguments[index + 1]
        for index, argument in enumerate(label_stage.arguments)
        if argument == "--provider-shard-audit"
    ] == [
        str(shard_root / "openai-audit.jsonl"),
        str(shard_root / "google-audit.jsonl"),
    ]
    assert [
        label_stage.arguments[index + 1]
        for index, argument in enumerate(label_stage.arguments)
        if argument == "--provider-shard-run-card"
    ] == [
        str(shard_root / "openai-run-card.json"),
        str(shard_root / "google-run-card.json"),
    ]


def test_v4_ranked_reserve_runbook_requires_provider_free_merge_then_adoption() -> None:
    runbook = (
        Path(__file__).parents[1]
        / "docs"
        / "cycle-1-target-100-v4-ranked-reserve-materialization.md"
    ).read_text(encoding="utf-8")

    assert "## Merge and adopt protected Stage B shards" in runbook
    assert "19-stage-b-shards/openai-audit.jsonl" in runbook
    assert "19-stage-b-shards/openai-run-card.json" in runbook
    assert "19-stage-b-shards/google-audit.jsonl" in runbook
    assert "19-stage-b-shards/google-run-card.json" in runbook
    assert "uv run legalforecast acquisition llm-label" in runbook
    assert "--execute --allow-network --allow-paid --json" in runbook
    assert "COURTLISTENER_API_TOKEN" in runbook
    assert "PACER_USERNAME" in runbook
    assert "PACER_PASSWORD" in runbook
    assert "--adopt-next-completed --json" in runbook
    assert "Do not combine `--adopt-next-completed` with `--execute`" in runbook


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

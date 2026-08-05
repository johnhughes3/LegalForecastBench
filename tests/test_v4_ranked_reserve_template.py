from __future__ import annotations

import hashlib
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


def test_v4_ranked_reserve_template_runs_ordered_local_stage_b_shards(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    label_stages = [stage for stage in config.stages if stage.command == "llm-label"]

    shard_root = tmp_path / "successor-v4" / "19-stage-b-shards"
    assert [stage.stage_id for stage in label_stages] == [
        "label-stage-b-openai-shard",
        "label-stage-b-google-shard",
        "merge-stage-b-provider-shards",
    ]
    openai_stage, google_stage, merge_stage = label_stages
    for stage, provider in (
        (openai_stage, "openai"),
        (google_stage, "google"),
    ):
        assert stage.boundary.value == "model_provider"
        assert stage.run_card_stage == "llm-label-provider-shard"
        assert _argument_value(stage, "--execution-provider") == provider
        assert "--local-provider-journal-only" in stage.arguments
        assert "--provider-authority-table" not in stage.arguments
        assert "--provider-authority-region" not in stage.arguments
        assert _argument_value(stage, "--audit-output") == str(
            shard_root / f"{provider}-audit.jsonl"
        )
        assert _argument_value(stage, "--labels-output") == str(
            shard_root / f"{provider}-labels.jsonl"
        )
        assert _argument_value(stage, "--lawyer-review-queue-output") == str(
            shard_root / f"{provider}-lawyer-review-queue.jsonl"
        )
        assert _argument_value(stage, "--run-card-output") == str(
            shard_root / f"{provider}-run-card.json"
        )

    assert merge_stage.boundary.value == "provider_free"
    assert merge_stage.run_card_stage == "llm-label"
    assert "--execution-provider" not in merge_stage.arguments
    assert "--local-provider-journal-only" not in merge_stage.arguments
    assert "--provider-authority-table" not in merge_stage.arguments
    assert "--provider-authority-region" not in merge_stage.arguments
    assert [
        merge_stage.arguments[index + 1]
        for index, argument in enumerate(merge_stage.arguments)
        if argument == "--provider-shard-audit"
    ] == [
        str(shard_root / "openai-audit.jsonl"),
        str(shard_root / "google-audit.jsonl"),
    ]
    assert [
        merge_stage.arguments[index + 1]
        for index, argument in enumerate(merge_stage.arguments)
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

    assert "## Execute, merge, and adopt local Stage B shards" in runbook
    assert "19-stage-b-shards/openai-audit.jsonl" in runbook
    assert "19-stage-b-shards/openai-run-card.json" in runbook
    assert "19-stage-b-shards/google-audit.jsonl" in runbook
    assert "19-stage-b-shards/google-run-card.json" in runbook
    assert "--local-provider-journal-only" in runbook
    assert "71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74" in runbook
    assert "--execute --allow-network --allow-paid --json" in runbook
    assert "COURTLISTENER_API_TOKEN" in runbook
    assert "PACER_USERNAME" in runbook
    assert "PACER_PASSWORD" in runbook
    assert "--adopt-next-completed --json" in runbook
    assert "Do not combine `--adopt-next-completed` with `--execute`" in runbook


def test_v4_ranked_reserve_template_binds_checked_in_local_provider_caps(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    expected_caps = (
        tmp_path
        / "repo"
        / "model_registries"
        / "cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )
    consumers = [
        stage for stage in config.stages if "--provider-cycle-caps" in stage.arguments
    ]

    assert consumers
    assert all(
        _argument_value(stage, "--provider-cycle-caps") == str(expected_caps)
        for stage in consumers
    )

    checked_in_caps = (
        Path(__file__).parents[1]
        / "model_registries"
        / "cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )
    assert hashlib.sha256(checked_in_caps.read_bytes()).hexdigest() == (
        "71a0919b7e23a1b0dab7bca7233c9036f2e678f35760f78f98b4f2c37330eb74"
    )


def test_v4_ranked_reserve_provider_calls_share_one_local_journal(
    tmp_path: Path,
) -> None:
    _, config = _render(tmp_path)
    provider_stages = [
        stage
        for stage in config.stages
        if stage.command in {"llm-unitize", "llm-review-stage-a"}
        or "--execution-provider" in stage.arguments
    ]
    expected_journal = str(
        tmp_path / "private-v4" / "paid-labeling" / "provider-attempts.sqlite3"
    )

    assert [stage.stage_id for stage in provider_stages] == [
        "unitize-stage-a",
        "review-stage-a-structure",
        "label-stage-b-openai-shard",
        "label-stage-b-google-shard",
    ]
    assert all(
        "--local-provider-journal-only" in stage.arguments for stage in provider_stages
    )
    assert all(
        _argument_value(stage, "--provider-journal") == expected_journal
        for stage in provider_stages
    )

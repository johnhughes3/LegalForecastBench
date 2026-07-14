from __future__ import annotations

import json
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.target_100_acquisition import (
    Target100PreparationConfig,
    build_target_100_stage_commands,
)
from pytest import CaptureFixture, MonkeyPatch


def test_target_100_commands_are_resumable_noncharging_and_exactly_capped(
    tmp_path: Path,
) -> None:
    config = Target100PreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        candidate_pool_size=165,
        target_case_count=100,
        live_public_download=True,
        live_case_dev=True,
        use_embedded_entries=True,
        resume=True,
    )

    commands = build_target_100_stage_commands(config)

    assert [command.stage for command in commands] == [
        "plan-public-downloads",
        "download-free",
        "bridge-pacer-gaps",
        "filter-core-documents",
        "plan",
    ]
    flattened = [argument for command in commands for argument in command.argv]
    assert "purchase-missing" not in flattened
    assert "purchase-missing-recap-fetch" not in flattened
    assert "--acknowledge-pacer-fees" not in flattened
    assert "--live-purchase" not in flattened
    assert "--resume" in flattened
    assert commands[-1].argv[-2:] == ("--target-case-count", "100")
    assert "--live-case-dev" in commands[2].argv
    assert "--live-public-download" in commands[1].argv


def test_target_100_cli_help_explains_provider_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "prepare-target-100", "--help"])
    output = capsys.readouterr().out
    assert "complete saturated screened snapshot" in output
    assert "never purchases" in output
    assert "CourtListener" in output
    assert "Case.dev" in output


def test_target_100_dry_run_writes_a_nonpurchase_stage_plan(tmp_path: Path) -> None:
    output_root = tmp_path / "run"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(tmp_path / "snapshot"),
                "--expected-cycle-hash",
                "a" * 64,
                "--live-public-download",
                "--live-case-dev",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["dry_run"] is True
    assert summary["target_case_count"] == 100
    assert summary["paid_activity_requested"] is False
    assert summary["paid_activity_executed"] is False
    assert all(
        row["stage"] != "purchase-missing-recap-fetch"
        for row in summary["stage_commands"]
    )


def test_target_100_execute_composes_stages_and_requires_exact_100(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "run"
    invoked: list[tuple[str, ...]] = []

    def fake_stage_main(argv: tuple[str, ...]) -> int:
        invoked.append(argv)
        stage = argv[1]
        if stage == "bridge-pacer-gaps":
            path = output_root / "03-gap-bridge" / "pacer-gap-bridge-exclusions.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        elif stage == "plan":
            path = output_root / "05-budget" / "missing-core-budget-plan.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            case_plans = [
                {
                    "candidate_id": f"candidate-{index:03d}",
                    "purchase_document_ids": [],
                    "missing_core_document_count": 0,
                    "estimated_purchase_count": 0,
                    "missing_core_roles": [],
                    "estimated_cost_usd": "0.00",
                    "audit_only_document_count": 0,
                    "dry_run": False,
                    "exclusion_reasons": [],
                }
                for index in range(100)
            ]
            path.write_text(
                json.dumps(
                    {
                        "dry_run": False,
                        "cost_per_document_usd": "3.05",
                        "max_projected_budget_usd": "2250.00",
                        "max_missing_core_documents_per_case": 24,
                        "target_case_count": 100,
                        "target_case_count_met": True,
                        "case_plans": case_plans,
                        "frontier_rows": [],
                        "omitted_candidate_ids": [],
                        "excluded_case_plans": [],
                    }
                )
            )
        return 0

    monkeypatch.setattr(cli, "main", fake_stage_main)
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(tmp_path / "snapshot"),
                "--expected-cycle-hash",
                "a" * 64,
                "--live-public-download",
                "--live-case-dev",
                "--execute",
            ]
        )
        == 0
    )

    assert [argv[1] for argv in invoked] == [
        "plan-public-downloads",
        "download-free",
        "bridge-pacer-gaps",
        "filter-core-documents",
        "plan",
    ]
    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["selected_case_count"] == 100
    assert summary["next_stage"] == "purchase-missing-recap-fetch"
    assert summary["paid_activity_executed"] is False

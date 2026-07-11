from __future__ import annotations

import importlib.util
import json
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from legalforecast.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_publication_docs_match_current_cli_and_workflow_contract() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    reproduce = (ROOT / "docs" / "reproduce-or-audit.md").read_text(encoding="utf-8")
    methods = (ROOT / "docs" / "METHODS.md").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "run-benchmark.yaml").read_text(
        encoding="utf-8"
    )

    for command in (
        "uv run scripts/release_check.py",
        "uv run legalforecast publish aggregate",
        "uv run legalforecast publish site",
    ):
        assert command in runbook
    for workflow_input in (
        "ablations",
        "resume_existing_results",
        "max_projected_model_cost_usd",
    ):
        assert workflow_input in runbook
        assert workflow_input in workflow

    for option in (
        "--model-registry",
        "--allow-no-baselines",
        "--baseline-training-examples",
    ):
        assert option in runbook
        assert option in reproduce

    assert "--profile official-cycle" not in reproduce
    assert "does not implement an `official-cycle` profile" in reproduce
    combined = "\n".join((runbook, reproduce, methods)).lower()
    for deprecated in (
        "verified-community",
        "community-unverified",
        "alpha-non-canonical",
        "preregistration",
    ):
        assert deprecated not in combined


def test_documented_aggregate_command_accepts_downloaded_workflow_tree(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    helpers = cast(Any, _official_aggregate_helpers())
    manifest_path = helpers._write_run_input_manifest(
        tmp_path,
        ablations=("full_packet", "metadata_only"),
    )
    labels_path = helpers._write_labels(tmp_path)
    per_case_dir = tmp_path / "downloaded-artifacts"
    for ablation, probability in (("full_packet", 0.9), ("metadata_only", 0.55)):
        helpers._write_case_artifacts(
            per_case_dir,
            case_dir_name=f"official-eval-case-1-{ablation}-model-a",
            solver_id="fixture:model-a",
            model_id="model-a",
            ablation=ablation,
            dismissed_probability=probability,
        )
    output_dir = tmp_path / "official-aggregate"

    assert (
        main(
            [
                "publish",
                "aggregate",
                "--per-case-dir",
                str(per_case_dir),
                "--run-input-manifest",
                str(manifest_path),
                "--labels",
                str(labels_path),
                "--output-dir",
                str(output_dir),
                "--cycle-id",
                "cycle-1",
                "--cycle-series",
                "pilot",
                "--clean-motion-count",
                "25",
                "--prediction-unit-count",
                "1",
                "--model-key",
                "fixture:model-a",
                "--allow-no-baselines",
            ]
        )
        == 0
    )

    summary = json.loads(capsys.readouterr().out)
    assert summary["expected_matrix_row_count"] == 2
    assert summary["aggregated_matrix_row_count"] == 2
    ablation_report = json.loads(
        (output_dir / "public" / "ablation-deltas.json").read_text(encoding="utf-8")
    )
    assert len(ablation_report["rows"]) == 1

    site_dir = tmp_path / "official-site"
    assert (
        main(
            [
                "publish",
                "site",
                "--official-artifacts-dir",
                str(output_dir / "public"),
                "--output-dir",
                str(site_dir),
            ]
        )
        == 0
    )
    site_summary = json.loads(capsys.readouterr().out)
    rendered = Path(site_summary["index"]).read_text(encoding="utf-8")
    assert "model-a" in rendered
    assert "No official score rows" not in rendered


@cache
def _official_aggregate_helpers() -> ModuleType:
    module_path = ROOT / "tests" / "test_official_aggregate.py"
    spec = importlib.util.spec_from_file_location(
        "_lfb_official_aggregate_helpers",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load aggregate helpers from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

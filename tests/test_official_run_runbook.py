from __future__ import annotations

import hashlib
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
        "--dispatch-provenance",
        "--allow-no-baselines",
        "--baseline-training-examples",
    ):
        assert option in runbook
        assert option in reproduce

    for amendment_contract in (
        "legalforecast freeze amend",
        "freeze_bundle_path",
        "prior_dispatches_json",
        "additive_supersession",
        "byte-identity assertion",
    ):
        assert amendment_contract in runbook

    batch_002_section = runbook.split(
        "## Cycle 1 Batch-002 CourtListener-First Acquisition", maxsplit=1
    )[1]
    ordered_acquisition_steps = (
        "### Step 1: Discover",
        "### First-Run Observation Smoke Step (required)",
        "### Step 2: Seed Optional Leads, Then Observe",
        "### Step 3: Freeze The Complete Saturated Snapshot",
        "### Step 4: Prepare The Resolved Pool And Provisional Budget",
        "### Step 5: Clear Every Free Document And Freeze The Exact Cohort",
        "### Step 6: Generate The Broker Allowlist, Then Purchase Explicitly",
    )
    assert [
        batch_002_section.index(step) for step in ordered_acquisition_steps
    ] == sorted(batch_002_section.index(step) for step in ordered_acquisition_steps)
    for command in (
        "legalforecast batch-002 discover",
        "legalforecast batch-002 observe",
        "legalforecast batch-002 snapshot",
        "legalforecast acquisition prepare-target-100",
        "legalforecast acquisition clear-disclosures",
        "legalforecast acquisition project-target-cohort",
        "legalforecast acquisition generate-recap-fetch-broker-policy",
        "legalforecast acquisition purchase-missing-recap-fetch",
    ):
        assert command in batch_002_section
    for hierarchy_contract in (
        "CourtListener REST v4 is the primary",
        "Case.dev is permitted only as an optional free equivalent",
        "Firecrawl is a compatibility fallback only",
        "It never purchases a document",
        "only fee-bearing happy path",
        "legacy paid-unknown evidence is never purchase authority",
    ):
        assert hierarchy_contract in batch_002_section

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


def test_staged_rollout_rehearsal_preserves_model_a_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    helpers = cast(Any, _official_aggregate_helpers())
    manifest_path = helpers._write_run_input_manifest(tmp_path)
    labels_path = helpers._write_labels(tmp_path)
    registry_path = helpers._write_model_registry(tmp_path, ("fixture:model-a",))
    union_dir = tmp_path / "union"
    model_a_dir = helpers._write_case_artifacts(
        union_dir / "dispatch-1001",
        case_dir_name="official-eval-case-1-full_packet-model-a",
        solver_id="fixture:model-a",
        model_id="model-a",
        dismissed_probability=0.9,
    )

    assert (
        main(
            [
                "publish",
                "aggregate",
                "--per-case-dir",
                str(union_dir),
                "--run-input-manifest",
                str(manifest_path),
                "--model-registry",
                str(registry_path),
                "--labels",
                str(labels_path),
                "--output-dir",
                str(tmp_path / "model-a-aggregate"),
                "--cycle-id",
                "cycle-1",
                "--cycle-series",
                "pilot",
                "--clean-motion-count",
                "25",
                "--prediction-unit-count",
                "1",
                "--allow-no-baselines",
                "--ablation",
                "full_packet",
            ]
        )
        == 0
    )
    capsys.readouterr()
    model_a_hashes_before = _tree_hashes(model_a_dir)

    registry_path = helpers._write_model_registry(
        tmp_path,
        ("fixture:model-a", "fixture:model-b"),
    )
    helpers._write_case_artifacts(
        union_dir / "dispatch-1002",
        case_dir_name="official-eval-case-1-full_packet-model-b",
        solver_id="fixture:model-b",
        model_id="model-b",
        dismissed_probability=0.6,
    )
    root_sha = "1" * 64
    amendment_sha = "2" * 64
    provenance_path = tmp_path / "lfb-dispatch-provenance.json"
    helpers._write_json(
        provenance_path,
        {
            "schema_version": "legalforecast.dispatch_provenance.v1",
            "cycle_id": "cycle-1",
            "current_freeze_bundle_sha256": amendment_sha,
            "freeze_chain": [
                {
                    "bundle_sha256": root_sha,
                    "amends_bundle_sha256": None,
                    "cycle_id": "cycle-1",
                    "freeze_timestamp": "2026-05-16T12:00:00Z",
                    "introduced_model_keys": ["fixture:model-a"],
                },
                {
                    "bundle_sha256": amendment_sha,
                    "amends_bundle_sha256": root_sha,
                    "cycle_id": "cycle-1",
                    "freeze_timestamp": "2026-05-17T12:00:00Z",
                    "introduced_model_keys": ["fixture:model-b"],
                },
            ],
            "dispatches": [
                {
                    "workflow_run_id": "1001",
                    "workflow_run_attempt": 1,
                    "freeze_bundle_sha256": root_sha,
                    "model_keys": ["fixture:model-a"],
                },
                {
                    "workflow_run_id": "1002",
                    "workflow_run_attempt": 1,
                    "freeze_bundle_sha256": amendment_sha,
                    "model_keys": ["fixture:model-b"],
                },
            ],
            "model_entry_freezes": [
                {
                    "model_key": "fixture:model-a",
                    "freeze_bundle_sha256": root_sha,
                },
                {
                    "model_key": "fixture:model-b",
                    "freeze_bundle_sha256": amendment_sha,
                },
            ],
            "publication": {
                "mode": "additive_supersession",
                "supersedes_report_uri": (
                    "s3://results/reports/cycle-1/multi-ablation/"
                ),
            },
        },
    )
    amended_output = tmp_path / "amended-aggregate"

    assert (
        main(
            [
                "publish",
                "aggregate",
                "--per-case-dir",
                str(union_dir),
                "--run-input-manifest",
                str(manifest_path),
                "--model-registry",
                str(registry_path),
                "--dispatch-provenance",
                str(provenance_path),
                "--labels",
                str(labels_path),
                "--output-dir",
                str(amended_output),
                "--cycle-id",
                "cycle-1",
                "--cycle-series",
                "pilot",
                "--clean-motion-count",
                "25",
                "--prediction-unit-count",
                "1",
                "--allow-no-baselines",
                "--ablation",
                "full_packet",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["expected_matrix_row_count"] == 2
    assert summary["aggregated_matrix_row_count"] == 2
    assert _tree_hashes(model_a_dir) == model_a_hashes_before
    leaderboard = json.loads(
        (amended_output / "public" / "report" / "leaderboard.json").read_text(
            encoding="utf-8"
        )
    )
    assert {row["model_id"] for row in leaderboard["rows"]} == {
        "model-a",
        "model-b",
    }


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


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

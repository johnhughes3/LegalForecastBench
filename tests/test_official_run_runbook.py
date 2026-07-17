from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
from legalforecast.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]


def _documented_command_block(runbook: str, command: str) -> str:
    marker = f"uv run legalforecast acquisition {command}"
    blocks = runbook.split(marker)
    assert len(blocks) > 1, f"{command} is not documented"
    remainder = blocks[1]
    assert "```" in remainder, f"{command} command block is not closed"
    return remainder.split("```", maxsplit=1)[0]


def _documented_acquisition_commands(runbook: str) -> list[tuple[str, str]]:
    commands: list[tuple[str, str]] = []
    for fenced_block in re.findall(r"```[^\n]*\n(.*?)```", runbook, flags=re.DOTALL):
        lines = fenced_block.splitlines()
        line_index = 0
        while line_index < len(lines):
            match = re.search(
                r"\buv run legalforecast acquisition ([a-z0-9-]+)",
                lines[line_index],
            )
            if match is None:
                line_index += 1
                continue
            invocation = [lines[line_index]]
            while invocation[-1].rstrip().endswith("\\"):
                line_index += 1
                assert line_index < len(lines), "unterminated acquisition command"
                invocation.append(lines[line_index])
            commands.append((match.group(1), "\n".join(invocation)))
            line_index += 1
    return commands


def test_documented_command_extraction_keeps_invocations_separate() -> None:
    runbook = """```zsh
if uv run legalforecast acquisition example --first one \\
  --second two; then
  uv run legalforecast acquisition example --third three
fi
```"""

    assert _documented_acquisition_commands(runbook) == [
        (
            "example",
            "if uv run legalforecast acquisition example --first one \\\n"
            "  --second two; then",
        ),
        (
            "example",
            "  uv run legalforecast acquisition example --third three",
        ),
    ]


def _subcommand_parser(
    parser: argparse.ArgumentParser,
    command: str,
) -> argparse.ArgumentParser:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return subparsers.choices[command]


def _long_options(parser: argparse.ArgumentParser) -> set[str]:
    return {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--")
    }


def _required_long_options(parser: argparse.ArgumentParser) -> set[str]:
    return {
        option
        for action in parser._actions
        if action.required
        for option in action.option_strings
        if option.startswith("--")
    }


def test_every_documented_acquisition_command_matches_current_cli_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    acquisition_parser = _subcommand_parser(build_parser(), "acquisition")

    for command, command_block in _documented_acquisition_commands(runbook):
        command_parser = _subcommand_parser(acquisition_parser, command)
        documented_options = set(re.findall(r"--[a-z0-9][a-z0-9-]*", command_block))

        with pytest.raises(SystemExit) as exc:
            main(["acquisition", command, "--help"])
        assert exc.value.code == 0
        help_text = capsys.readouterr().out

        assert documented_options <= _long_options(command_parser)
        assert documented_options <= set(re.findall(r"--[a-z0-9][a-z0-9-]*", help_text))
        assert _required_long_options(command_parser) <= documented_options, (
            f"{command} example omits a required current CLI option"
        )


def test_downstream_runbook_preserves_materialization_and_lineage() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")

    required_options = {
        "materialize-cohort-documents": (
            "--target-cohort-root",
            "--free-disclosure-clearance",
            "--purchased-recovery-root",
            "--purchased-disclosure-clearance",
            "--purchased-clearance-run-card",
            "--purchase-policy",
            "--cohort-policy",
            "--purchase-ledger",
        ),
        "plan-parse-documents": (
            "--materialization-run-card",
            "--document-root",
            "--requests-output",
        ),
        "parse-documents": (
            "--selection",
            "--materialization-run-card",
            "--purchase-policy",
            "--purchase-ledger",
        ),
        "llm-label": (
            "--llm-unitization-run-card",
            "--llm-review-stage-a-run-card",
            "--unitization-review-run-card",
        ),
        "plan-packet-inputs": (
            "--materialization-run-card",
            "--document-root",
            "--markdown-root",
        ),
        "build-packets": (
            "--llm-unitize-run-card",
            "--llm-unitize-provider-journal",
            "--stage-a-review-run-card",
            "--stage-a-review-provider-journal",
            "--apply-unitization-review-run-card",
            "--parse-plan-run-card",
        ),
        "finalize-corpus": (
            "--output-root",
            "--disclosure-clearance",
            "--download-manifest",
            "--materialization-run-card",
            "--document-root",
            "--llm-unitization-audit",
            "--llm-unitize-run-card",
            "--llm-unitize-provider-journal",
            "--stage-a-review-run-card",
            "--stage-a-review-provider-journal",
            "--apply-unitization-review-run-card",
            "--labels",
            "--llm-label-audit",
            "--llm-label-run-card",
            "--stage-b-judge-registry",
            "--labeling-policy",
            "--lawyer-review-queue",
            "--lawyer-review-audit",
            "--packet-input-run-card",
            "--packet-build-run-card",
        ),
    }
    for command, options in required_options.items():
        command_block = _documented_command_block(runbook, command)
        for option in options:
            assert option in command_block, f"{command} is missing {option}"

    assert "--llm-label-run-card" not in _documented_command_block(runbook, "llm-label")


def test_runbook_documents_isolated_provider_free_exact_cohort_rehearsal() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    block = _documented_command_block(runbook, "rehearse-downstream")
    for option in (
        "--selection-run-card",
        "--materialization-run-card",
        "--parse-plan-run-card",
        "--parse-requests",
        "--parser-run-card",
        "--response-fixtures",
        "--target-case-count",
        "--evaluated-model-registry",
    ):
        assert option in block
    rehearsal_section = runbook.split(
        "### Provider-free exact-cohort downstream rehearsal", maxsplit=1
    )[1].split("Unitize Stage A only", maxsplit=1)[0]
    for required_claim in (
        "official_eligible=false",
        "provider_journal_created=false",
        'provider_billing_usd="0.00"',
        "cannot freeze, evaluate, or dispatch",
        "never self-adjudicates",
    ):
        assert required_claim in rehearsal_section
    assert "--acknowledge-pacer-fees" not in block


def test_runbook_closes_unknown_status_purchase_to_materialization_chain() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    commands = _documented_acquisition_commands(runbook)

    recovery_blocks = [
        block
        for command, block in commands
        if command == "recover-recap-fetch-quarantine"
    ]
    assert len(recovery_blocks) == 1
    for option in (
        "--attempt-policy",
        "--manifest-output",
        "--restriction-evidence-output",
        "--review-requests-output",
        "--document-output-root",
        "--live-courtlistener-recovery",
    ):
        assert option in recovery_blocks[0]

    purchased_prepare = next(
        block
        for command, block in commands
        if command == "prepare-disclosure-review"
        and "$purchased_review_requests" in block
    )
    for option in (
        "--review-requests",
        "--download-manifest",
        "--document-root",
        "--restriction-evidence",
        "--controlled-private-store-root",
    ):
        assert option in purchased_prepare

    purchased_clearance = next(
        block
        for command, block in commands
        if command == "clear-disclosures" and "$purchased_review_requests" in block
    )
    for option in (
        "--review-receipt",
        "--reviewer-policy",
        "--cohort-policy",
        "--restriction-evidence",
    ):
        assert option in purchased_clearance

    resolution = _documented_command_block(runbook, "resolve-post-recovery-documents")
    for option in (
        "--attempt-policy",
        "--download-manifest",
        "--disclosure-clearance",
        "--clearance-run-card",
        "--reviews",
        "--review-receipt",
        "--restriction-evidence",
        "--resolved-output",
    ):
        assert option in resolution

    materializer = _documented_command_block(runbook, "materialize-cohort-documents")
    assert "<recover-recap-fetch-quarantine-root>" in materializer
    assert "$quarantine_recovery_root" in runbook
    assert "$resolved_post_recovery" in runbook


def test_release_dates_match_frozen_two_judge_stage_b_registry() -> None:
    release_dates = (ROOT / "MODEL_RELEASE_DATES.md").read_text(encoding="utf-8")
    stage_b_registry = json.loads(
        (
            ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
        ).read_text(encoding="utf-8")
    )
    stage_b_section = release_dates.split(
        "## Cycle 1 Label-Generation Models", maxsplit=1
    )[1]

    assert "exactly the two voting entries" in stage_b_section
    assert "Claude Haiku" not in stage_b_section
    assert {
        f"{entry['provider']}:{entry['model_id']}" for entry in stage_b_registry
    } == {
        "google:gemini-3.5-flash",
        "openai:gpt-5.4-mini-2026-03-17",
    }
    for entry in stage_b_registry:
        assert f"`{entry['model_id']}`" in stage_b_section


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
        "### Step 1: Search CourtListener Decisions Through Firecrawl",
        "### Step 2: Enrich And Rank With Free Case.dev Lookup",
        "### Step 3: Acquire And Screen Complete CourtListener Dockets",
        "### Step 4: Prepare The Resolved Pool And Provisional Budget",
        "### Step 5: Clear Every Free Document And Freeze The Exact Cohort",
        "### Step 6: Generate Allowlist, Initialize Ledger, Then Purchase",
    )
    assert [
        batch_002_section.index(step) for step in ordered_acquisition_steps
    ] == sorted(batch_002_section.index(step) for step in ordered_acquisition_steps)
    for command in (
        "legalforecast acquisition discover-firecrawl-recap-decisions",
        "legalforecast acquisition enrich-recap-case-dev",
        "legalforecast acquisition acquire-ranked-firecrawl-dockets",
        "legalforecast acquisition screen-firecrawl-dockets",
        "legalforecast acquisition prepare-target-100",
        "legalforecast acquisition clear-disclosures",
        "legalforecast acquisition project-target-cohort",
        "legalforecast acquisition generate-recap-fetch-broker-policy",
        "legalforecast acquisition init-purchase-ledger",
        "legalforecast acquisition purchase-missing-recap-fetch",
        "legalforecast batch-002 seed-direct-search",
        "legalforecast batch-002 observe",
        "legalforecast batch-002 snapshot",
    ):
        assert command in batch_002_section
    assert batch_002_section.index(
        "legalforecast acquisition init-purchase-ledger"
    ) < batch_002_section.index(
        "legalforecast acquisition purchase-missing-recap-fetch"
    )
    for disabled_command in ("legalforecast batch-002 discover \\",):
        assert disabled_command not in batch_002_section
    assert "--max-projected-budget-usd 567.30" in batch_002_section
    for hierarchy_contract in (
        "CourtListener remains the source",
        "Case.dev is used only for equivalent free lookup and prioritization",
        (
            "Firecrawl is used only for the demonstrated CourtListener search and "
            "docket-HTML surface gap"
        ),
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


def test_disclosure_review_runbook_uses_main_pinned_authority_contract() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    section = runbook.split(
        "### Step 5: Clear Every Free Document And Freeze The Exact Cohort",
        maxsplit=1,
    )[1].split("### Step 6:", maxsplit=1)[0]

    assert "cohort_policy=<frozen-cohort-policy.json>" in section
    assert "--expected-reviewer-policy-sha256" not in section

    required_options = {
        "prepare-disclosure-review": ("--reviewer-policy", "--cohort-policy"),
        "preflight-disclosure-review-signer": (
            "--reviewer-policy",
            "--cohort-policy",
        ),
        "build-disclosure-review-bundle": (
            "--reviewer-policy",
            "--cohort-policy",
        ),
        "seal-disclosure-review-bundle": (
            "--reviewer-policy",
            "--cohort-policy",
        ),
        "clear-disclosures": ("--reviewer-policy", "--cohort-policy"),
    }
    for command, options in required_options.items():
        marker = f"uv run legalforecast acquisition {command}"
        command_blocks = [
            remainder.split("```", maxsplit=1)[0]
            for remainder in section.split(marker)[1:]
        ]
        assert command_blocks, f"{command} is not documented"
        for command_block in command_blocks:
            for option in options:
                assert option in command_block, f"{command} is missing {option}"


def test_paid_recap_fetch_runbook_freezes_and_consumes_attempt_authority() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    section = runbook.split(
        "### Step 6: Generate Allowlist, Initialize Ledger, Then Purchase",
        maxsplit=1,
    )[1].split("### Expected Volumes", maxsplit=1)[0]

    ordered_commands = (
        "generate-recap-fetch-attempt-policy",
        "generate-recap-fetch-broker-policy",
        "init-purchase-ledger",
        "purchase-missing-recap-fetch",
    )
    command_markers = [
        f"uv run legalforecast acquisition {command}" for command in ordered_commands
    ]
    assert [section.index(marker) for marker in command_markers] == sorted(
        section.index(marker) for marker in command_markers
    )
    assert "--attempt-policy" in _documented_command_block(
        section, "generate-recap-fetch-broker-policy"
    )
    assert "--attempt-policy" in _documented_command_block(
        section, "purchase-missing-recap-fetch"
    )


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
    registry_path = helpers._write_model_registry(tmp_path, ("fixture:model-a",))
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
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cycle_id"] = "runbook-shape-smoke"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    for metrics_path in per_case_dir.glob("*/metrics.json"):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["cycle_id"] = "runbook-shape-smoke"
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
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
                "runbook-shape-smoke",
                "--cycle-series",
                "official",
                "--clean-motion-count",
                "1",
                "--prediction-unit-count",
                "2",
                "--model-registry",
                str(registry_path),
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

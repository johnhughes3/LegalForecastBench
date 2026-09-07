"""Mechanical checks for the retained public release boundary."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
RETAINED_WORKFLOWS = ("run-benchmark.yaml", "fan-in-publish.yaml")
BOUNDARY_DOCS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / ".agents" / "AGENTS.md",
    ROOT / "docs" / "official-run-runbook.md",
    ROOT / "docs" / "reproduce-or-audit.md",
    ROOT / "scripts" / "AGENTS.md",
    ROOT / "infra" / "official-eval" / "README.md",
)
STALE_BOUNDARY_TOKENS = (
    "corpus acquisition CLI",
    "budget approve",
    "budget set",
    "resume_existing_results",
    "repeat_sample_case_ids",
    "official_infra_contract.py",
    "stage-manifest-run.yaml",
    "stage-official-manifest-run.yaml",
    "official-s3-access-validation.yaml",
    "publish aggregate",
    "official-provider-cell",
    "acquisition is core pipeline",
    "legalforecast acquisition",
)
LOCAL_ACTION_REFERENCE = re.compile(
    r"uses:\s+\./\.github/actions/(?P<name>[A-Za-z0-9._-]+)"
)


def test_retained_workflows_are_present() -> None:
    for workflow in RETAINED_WORKFLOWS:
        assert (WORKFLOW_ROOT / workflow).is_file(), workflow


def test_workflow_local_actions_resolve() -> None:
    for workflow in WORKFLOW_ROOT.glob("*.y*ml"):
        text = workflow.read_text(encoding="utf-8")
        for match in LOCAL_ACTION_REFERENCE.finditer(text):
            action = ROOT / ".github" / "actions" / match.group("name") / "action.yml"
            assert action.is_file(), f"{workflow}: missing local action {action}"


def test_boundary_docs_have_no_removed_runtime_references() -> None:
    for path in BOUNDARY_DOCS:
        text = path.read_text(encoding="utf-8")
        for token in STALE_BOUNDARY_TOKENS:
            assert token not in text, f"{path}: stale boundary token {token!r}"


def test_boundary_docs_name_the_strict_release_contract() -> None:
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    for workflow in RETAINED_WORKFLOWS:
        assert workflow in runbook
    for option in (
        "--labels-release",
        "--forecast-release",
        "--manifest",
        "--model-registry",
        "--ledger",
    ):
        assert option in runbook


def test_docs_index_describes_the_retained_corpus_handoff() -> None:
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "## Corpus Handoff Boundary" in docs_index
    for stale in (
        "## Acquisition Operations",
        "[Attachment-menu acquisition]",
        "[Acquisition systemd launcher]",
        "cycle-acquisition-config.md",
        "acquisition-cycle-config-v1.md",
        "acquisition-cycle-template-v1.md",
        "legalforecast acquisition replay-stage-a",
    ):
        assert stale not in docs_index, stale


def test_public_tree_does_not_keep_retired_cycle_acquisition_templates() -> None:
    manifests = ROOT / "manifests"
    leftover = (
        sorted(
            path.relative_to(ROOT).as_posix()
            for path in manifests.glob("cycle-1-target-100*.template.json")
        )
        if manifests.is_dir()
        else []
    )
    recap_policies = manifests / "recap-fetch-policies"
    assert leftover == []
    assert not recap_policies.exists()
    assert not (ROOT / "docs" / "labeling-policy.json").exists()
    assert not (
        ROOT / "docs" / "cohort-policy-cycle-1-target-100-2026-07-25.json"
    ).exists()


def test_tracked_manifest_templates_resolve_repo_root_inputs() -> None:
    manifests = ROOT / "manifests"
    if not manifests.is_dir():
        return

    missing: list[str] = []
    local_paths: list[str] = []
    for path in manifests.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        if "/work/" in text or "/Users/" in text:
            local_paths.append(relative)
        if path.suffix != ".json" or ".template." not in path.name:
            continue
        json.loads(text)
        for match in re.findall(r"\$\{REPO_ROOT\}/([^\"\s]+)", text):
            if not (ROOT / match).exists():
                missing.append(f"{relative} -> {match}")

    assert local_paths == []
    assert missing == []

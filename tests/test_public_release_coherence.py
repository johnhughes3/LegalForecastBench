"""Mechanical checks for the retained public release boundary."""

from __future__ import annotations

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
    ROOT / "docs" / "official-run-gate-pack.md",
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
    gate_pack = (ROOT / "docs" / "official-run-gate-pack.md").read_text(
        encoding="utf-8"
    )
    for workflow in RETAINED_WORKFLOWS:
        assert workflow in runbook
        assert workflow in gate_pack
    for option in (
        "--labels-release",
        "--forecast-release",
        "--manifest",
        "--model-registry",
        "--ledger",
    ):
        assert option in runbook
        assert option in gate_pack


def test_gate_pack_dispatch_examples_match_workflow_inputs() -> None:
    gate_pack = (ROOT / "docs" / "official-run-gate-pack.md").read_text(
        encoding="utf-8"
    )
    run_workflow = (WORKFLOW_ROOT / "run-benchmark.yaml").read_text(encoding="utf-8")
    fan_in_workflow = (WORKFLOW_ROOT / "fan-in-publish.yaml").read_text(
        encoding="utf-8"
    )
    run_fields = _dispatch_input_names(run_workflow)
    fan_in_fields = _dispatch_input_names(fan_in_workflow)
    assert set(_gate_pack_fields(gate_pack, "run-benchmark.yaml")) == set(run_fields)
    assert set(_gate_pack_fields(gate_pack, "fan-in-publish.yaml")) == set(
        fan_in_fields
    )


def test_docs_index_describes_the_retained_corpus_handoff() -> None:
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "## Corpus Handoff Boundary" in docs_index
    active_index = docs_index.split("## Historical and Migration Records", 1)[0]
    for stale in (
        "## Acquisition Operations",
        "[Attachment-menu acquisition]",
        "[Acquisition systemd launcher]",
        "cycle-acquisition-config.md",
        "acquisition-cycle-config-v1.md",
        "acquisition-cycle-template-v1.md",
        "legalforecast acquisition replay-stage-a",
    ):
        assert stale not in active_index, stale


def test_private_labeling_and_freeze_records_are_historical_only() -> None:
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    active_index = docs_index.split("## Historical and Migration Records", 1)[0]
    for document in (
        "labeling-protocol.md",
        "cycle-1-manifest-provider-free-freeze-v2.md",
    ):
        assert document not in active_index
        text = (ROOT / "docs" / document).read_text(encoding="utf-8")
        assert "Historical Corpus record" in text
        assert "non-executable" in text
    assert (
        "## Historical private-corpus and migration schemas (non-executable)"
        in docs_index
    )


def _dispatch_input_names(workflow: str) -> tuple[str, ...]:
    """Extract the workflow-dispatch input names from a checked-in workflow."""

    dispatch = workflow.split("workflow_dispatch:\n", maxsplit=1)[1]
    inputs = dispatch.split("\n\npermissions:", maxsplit=1)[0]
    return tuple(re.findall(r"^      ([a-z][a-z0-9_]*)\s*:\s*$", inputs, re.M))


def _gate_pack_fields(document: str, workflow_name: str) -> tuple[str, ...]:
    """Extract ``-f`` fields from one workflow command in the gate pack."""

    blocks = re.findall(r"```bash\n(.*?)\n```", document, re.DOTALL)
    command = next(
        block for block in blocks if f"gh workflow run {workflow_name}" in block
    )
    return tuple(re.findall(r"^\s*-f ([a-z][a-z0-9_]*)=", command, re.M))

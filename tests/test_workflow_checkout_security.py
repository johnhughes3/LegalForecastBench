from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
GITHUB_ROOT = ROOT / ".github"

# GitHub refuses to parse a workflow that declares more than this many
# workflow_dispatch inputs, with
#   HTTP 422: you may only define up to 25 'inputs' for a 'workflow_dispatch'
# The refusal happens at dispatch time against the file on the default branch,
# so nothing in CI -- which never dispatches -- observes it. run-benchmark.yaml
# shipped 27 inputs and was undispatchable for both the official and the
# supplementary lane until a count check existed.
WORKFLOW_DISPATCH_INPUT_LIMIT = 25

# Headroom below the platform limit. Landing exactly at 25 leaves the next
# input addition to fail in production rather than in CI, so the budget is the
# gate and the limit above is only the explanation.
WORKFLOW_DISPATCH_INPUT_BUDGET = 24

_INPUT_NAME = re.compile(r"^      ([A-Za-z_][A-Za-z0-9_-]*):\s*$")


def _workflow_dispatch_input_names(text: str) -> list[str] | None:
    """Return the declared workflow_dispatch input names, or None if undispatchable.

    The repository parses workflows as text everywhere else and has no YAML
    dependency, so this reads the fixed two-space-per-level layout the workflows
    all use: ``  workflow_dispatch:`` under ``on:``, ``    inputs:`` under it,
    and one input name per line at six spaces. Anything deeper belongs to an
    input's body.
    """

    lines = text.splitlines()
    try:
        start = lines.index("  workflow_dispatch:")
    except ValueError:
        return None
    names: list[str] = []
    inside_inputs = False
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith("   "):
            break  # back out to another top-level `on:` trigger or block
        if line.strip() == "inputs:" and line.startswith("    ") and line[4] != " ":
            inside_inputs = True
            continue
        if not inside_inputs:
            continue
        if line.strip() and not line.startswith("      "):
            break
        match = _INPUT_NAME.match(line)
        if match is not None:
            names.append(match.group(1))
    if inside_inputs and not names:
        # A workflow that declares inputs but parses to zero would silently
        # exempt itself from the limit below, which is the one failure mode a
        # text parser must never have.
        raise AssertionError(
            "workflow_dispatch declares an inputs: block but no input names "
            "were parsed; the layout this parser assumes has changed"
        )
    return names


def test_dispatchable_workflows_stay_under_the_github_input_limit() -> None:
    counts: dict[str, int] = {}
    for workflow_path in sorted(WORKFLOW_ROOT.glob("*.y*ml")):
        names = _workflow_dispatch_input_names(
            workflow_path.read_text(encoding="utf-8")
        )
        if names is None:
            continue
        assert len(names) == len(set(names)), (
            f"{workflow_path.name} declares duplicate workflow_dispatch inputs"
        )
        counts[workflow_path.name] = len(names)

    assert "run-benchmark.yaml" in counts, (
        "run-benchmark.yaml must remain a workflow_dispatch workflow"
    )

    over_limit = {
        name: count
        for name, count in counts.items()
        if count > WORKFLOW_DISPATCH_INPUT_LIMIT
    }
    assert not over_limit, (
        "GitHub refuses to parse a workflow_dispatch event with more than "
        f"{WORKFLOW_DISPATCH_INPUT_LIMIT} inputs (HTTP 422), so these workflows "
        f"cannot be dispatched at all: {over_limit}"
    )

    over_budget = {
        name: count
        for name, count in counts.items()
        if count > WORKFLOW_DISPATCH_INPUT_BUDGET
    }
    assert not over_budget, (
        f"{over_budget} exceeds the {WORKFLOW_DISPATCH_INPUT_BUDGET}-input budget "
        f"kept below GitHub's hard cap of {WORKFLOW_DISPATCH_INPUT_LIMIT}. Free a "
        "slot before adding one: in run-benchmark.yaml, cycle_series, "
        "clean_motion_count, prediction_unit_count, allow_no_baselines, and "
        "baseline_training_examples_uri feed only the aggregate-results job, "
        "which cannot run because validation refuses the "
        "dry_run=false/shard_only=false combination it requires."
    )


def test_workflow_dispatch_input_parser_sees_the_real_declarations() -> None:
    """Guard the parser itself: a silent zero would make the fence vacuous."""

    counts = {
        path.name: _workflow_dispatch_input_names(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOW_ROOT.glob("*.y*ml"))
    }
    run_benchmark = counts["run-benchmark.yaml"]
    assert run_benchmark is not None
    # Spot-check both ends of the block and a choice-typed input in the middle,
    # so a parser that stops early or swallows nested keys fails here.
    assert run_benchmark[0] == "release_sha"
    assert run_benchmark[-1] == "execution_scope_uri"
    assert "cycle_series" in run_benchmark
    assert "options" not in run_benchmark
    assert "supplementary" not in run_benchmark, (
        "the official/supplementary lane is derived from freeze_bundle_path"
    )
    assert counts["ci.yaml"] == []
    assert counts["fan-in-publish.yaml"] is not None


def test_checkout_steps_disable_credential_persistence() -> None:
    checkout_steps: list[tuple[Path, int]] = []
    unsecured_steps: list[str] = []

    for workflow_path in sorted(WORKFLOW_ROOT.glob("*.y*ml")):
        lines = workflow_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/checkout@" not in line:
                continue
            checkout_steps.append((workflow_path, index + 1))
            step_indent = len(line) - len(line.lstrip()) - 2
            step_block: list[str] = []
            for candidate in lines[index + 1 :]:
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if (
                    candidate.lstrip().startswith("- ")
                    and candidate_indent <= step_indent
                ):
                    break
                step_block.append(candidate)
            if not any(
                candidate.strip() == "persist-credentials: false"
                for candidate in step_block
            ):
                unsecured_steps.append(f"{workflow_path.name}:{index + 1}")

    assert checkout_steps, "expected at least one actions/checkout step"
    assert not unsecured_steps, (
        "actions/checkout steps must set persist-credentials: false: "
        + ", ".join(unsecured_steps)
    )


def test_external_actions_use_immutable_commit_pins() -> None:
    mutable_uses: list[str] = []
    uses_pattern = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)

    for action_path in sorted(GITHUB_ROOT.rglob("*.y*ml")):
        for use in uses_pattern.findall(action_path.read_text(encoding="utf-8")):
            if use.startswith(("./", "docker://")):
                continue
            _, separator, revision = use.rpartition("@")
            if separator != "@" or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
                mutable_uses.append(f"{action_path.relative_to(ROOT)}: {use}")

    assert not mutable_uses, (
        "external GitHub Actions must use immutable 40-character commit pins: "
        + ", ".join(mutable_uses)
    )


def test_official_fan_in_keeps_hf_publication_gated_and_short_lived() -> None:
    workflow = (WORKFLOW_ROOT / "fan-in-publish.yaml").read_text(encoding="utf-8")

    assert "hugging_face_release_version:" in workflow
    assert (
        workflow.count(
            "if: ${{ !inputs.verify_only && "
            "inputs.hugging_face_release_version != '' }}"
        )
        == 2
    )
    assert (
        "HF_OIDC_RESOURCE: datasets/${{ vars.LFB_HF_OFFICIAL_DATASET_REPO }}"
        in workflow
    )
    assert "huggingface_hub==1.28.0" in workflow
    assert 'if info.gated != "manual":' in workflow
    assert "api.list_repo_files(" in workflow
    assert "immutable release already exists" in workflow
    assert "api.upload_folder(" in workflow
    assert "parent_commit=info.sha" in workflow
    assert "HF_TOKEN" not in workflow


def test_hf_runbook_records_revision_and_registration_boundaries() -> None:
    runbook = (ROOT / "docs" / "hugging-face-publication.md").read_text(
        encoding="utf-8"
    )

    assert "dataset.revision" in runbook
    assert "full Hugging Face commit SHA" in runbook
    assert "Manual approval" in runbook
    assert "allow-list" in runbook
    assert "not a reproducible benchmark identity" in runbook

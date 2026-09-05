from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(encoding="utf-8")
LEGACY = ROOT / ".github/workflows/run-benchmark-manifest.yaml"


def _job(name: str, next_name: str | None = None) -> str:
    start = WORKFLOW.index(f"  {name}:")
    end = WORKFLOW.index(f"  {next_name}:", start) if next_name else len(WORKFLOW)
    return WORKFLOW[start:end]


def test_canonical_dispatcher_partitions_dynamic_provider_lanes() -> None:
    assert not LEGACY.exists()
    assert "run-openai:" in WORKFLOW
    assert "run-anthropic:" in WORKFLOW
    assert "run-gemini:" in WORKFLOW
    for provider, next_name in (
        ("openai", "run-anthropic"),
        ("anthropic", "run-gemini"),
        ("gemini", None),
    ):
        job = _job(f"run-{provider}", next_name)
        assert "environment: legalforecastbench-official-eval" in job
        assert "Download outcome-blinded inputs" in job
        assert "fromJSON(needs.prepare-inputs.outputs." + provider + "_matrix)" in job


def test_provider_credentials_are_step_scoped_and_never_inherited() -> None:
    jobs = {
        "run-openai": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"),
        "run-anthropic": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"),
        "run-gemini": ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    }
    next_names = {
        "run-openai": "run-anthropic",
        "run-anthropic": "run-gemini",
        "run-gemini": None,
    }
    for name, (own, other_a, other_b) in jobs.items():
        block = _job(name, next_names[name])
        assert block.count(f"secrets.{own}") == 1
        assert f"secrets.{other_a}" not in block
        assert f"secrets.{other_b}" not in block
        assert "secrets: inherit" not in block
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in block


def test_provider_cells_have_no_label_input_or_scoring_authority() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        block = _job(name, next_name)
        assert "labels_release_uri" not in block
        assert "LABELS" not in block
        assert "--labels" not in block
        assert "score" not in block.lower()
        assert "report" not in block.lower()
        assert "GITHUB_EVENT_PATH" not in block


def test_provider_cells_use_durable_resume_state_and_exact_source_checks() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", None),
    ):
        block = _job(name, next_name)
        # origin/main must be resolvable by the time the source check runs, but
        # NOT via a separate `git fetch`: the checkout step sets
        # persist-credentials: false, so no later step holds a token, and a
        # bare fetch against this repository dies with
        # "could not read Username for 'https://github.com'"
        # (legalforecastbench-2x9o). fetch-depth: 0 makes the checkout action
        # itself fetch full history and refs (including origin/main) under its
        # own short-lived credentials instead.
        assert "fetch-depth: 0" in block
        assert "persist-credentials: false" in block
        assert "git fetch --no-tags --depth=1 origin main" not in block
        assert "git merge-base --is-ancestor HEAD origin/main" in block
        assert "Restore newest prior valid attempt" in block
        assert "Persist" in block
        assert "if: ${{ always() }}" in block
        assert "ledger.sqlite3" in block
        assert "receipts" in block
        assert "failure-summary.json" in block
        assert "if-no-files-found: error" in block
        assert "--cell-id" in block
        assert "--unit-id" in block


def test_workflow_action_references_are_full_sha_pinned() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    for action, revision in references:
        assert re.fullmatch(r"[0-9a-f]{40}", revision), (action, revision)

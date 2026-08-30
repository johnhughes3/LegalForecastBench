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


def test_canonical_dispatcher_partitions_provider_lanes_without_legacy_action() -> None:
    assert not LEGACY.exists()
    for provider, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        job = _job(provider, next_name)
        assert (
            f"startsWith(inputs.model_key, '{provider.removeprefix('run-')}:')" in job
        )
        assert "environment: legalforecastbench-official-eval" in job
        assert "uses: ./.github/actions/official-provider-cell" not in job
        assert "Download outcome-blinded inputs" in job


def test_provider_credentials_are_step_scoped_and_never_inherited() -> None:
    jobs = {
        "run-openai": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"),
        "run-anthropic": ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"),
        "run-gemini": ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
    }
    for name, (own, other_a, other_b) in jobs.items():
        block = _job(
            name,
            {
                "run-openai": "run-anthropic",
                "run-anthropic": "run-gemini",
                "run-gemini": "score-and-report",
            }[name],
        )
        assert block.count(f"secrets.{own}") == 1
        assert f"secrets.{other_a}" not in block
        assert f"secrets.{other_b}" not in block
        assert "secrets: inherit" not in block
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in block


def test_provider_cells_have_no_label_input_or_label_storage_authority() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        block = _job(name, next_name)
        assert "labels_release_uri" not in block
        assert "labels-release" not in block
        assert "LABELS" not in block
        assert "--labels" not in block
        assert "LFB_GITHUB_FAN_IN_ROLE_ARN" not in block


def test_provider_cells_use_durable_resume_state_and_exact_source_checks() -> None:
    for name, next_name in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        block = _job(name, next_name)
        assert "git fetch --no-tags --depth=1 origin main" in block
        assert "git merge-base --is-ancestor origin/main HEAD" in block
        assert "Restore resumable" in block
        assert "Persist" in block
        assert "if: ${{ always() }}" in block
        assert "ledger.sqlite3" in block
        assert "receipts" in block


def test_workflow_action_references_are_full_sha_pinned() -> None:
    references = re.findall(
        r"^\s*uses:\s+([^@\s]+)@([^\s#]+)", WORKFLOW, flags=re.MULTILINE
    )
    assert references
    for action, revision in references:
        assert re.fullmatch(r"[0-9a-f]{40}", revision), (action, revision)

"""Fences for the restored legacy fan-in boundary.

PR #1019 (397ccf3e) replaced ``.github/workflows/fan-in-publish.yaml`` with the
per-model locked-manifest boundary. That boundary consumes a single
``official-forecast-results-<run>-<attempt>`` Actions artifact, which the
restored legacy dispatch lane (``run-benchmark-legacy.yaml``, PR #1029) never
emits, and it has no path to the immutable S3 shard receipts the legacy provider
cells write. The owner-approved Cycle 1 r4 repair (bead
``legalforecastbench-y7hk``) fans in through those shard receipts, so
``fan-in-publish-legacy.yaml`` restores the pre-#1019 boundary beside it.

These tests hold the restored file to the same provider-free, protected-boundary
guarantees as the locked-manifest fan-in, and pin the one behavioural delta from
289ebac9: the source-dispatch workflow-path allowlist.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
LEGACY_FAN_IN_PATH = WORKFLOW_ROOT / "fan-in-publish-legacy.yaml"
LOCKED_FAN_IN_PATH = WORKFLOW_ROOT / "fan-in-publish.yaml"
LEGACY_DISPATCH_PATH = WORKFLOW_ROOT / "run-benchmark-legacy.yaml"

LEGACY_FAN_IN = LEGACY_FAN_IN_PATH.read_text(encoding="utf-8")

RUN_BENCHMARK_WORKFLOW_PATH = ".github/workflows/run-benchmark.yaml"
RUN_BENCHMARK_LEGACY_WORKFLOW_PATH = ".github/workflows/run-benchmark-legacy.yaml"

_ALLOWLIST = re.compile(
    r'if run\["path"\] not in (\{[^}]*\}):',
    re.DOTALL,
)


def _source_dispatch_path_allowlist() -> frozenset[str]:
    """Return the workflow paths the legacy fan-in accepts as a source dispatch.

    The check lives inside a heredoc, so it is read as text and the set literal
    is parsed rather than executed. A literal that stops parsing -- or that grows
    a computed element -- fails here instead of silently widening the boundary.
    """

    matches = _ALLOWLIST.findall(LEGACY_FAN_IN)
    assert len(matches) == 1, (
        "expected exactly one source-dispatch workflow-path allowlist; "
        f"found {len(matches)}"
    )
    literal = ast.literal_eval(matches[0])
    assert isinstance(literal, set)
    assert all(isinstance(item, str) for item in literal)
    return frozenset(literal)


def test_legacy_fan_in_exists_only_while_the_legacy_dispatch_lane_does() -> None:
    """Both halves of the legacy chain retire together when y7hk closes."""

    assert LEGACY_DISPATCH_PATH.exists(), (
        "fan-in-publish-legacy.yaml exists only to fan in dispatches from "
        "run-benchmark-legacy.yaml; delete both together when "
        "legalforecastbench-y7hk closes"
    )
    assert "legalforecastbench-y7hk" in LEGACY_FAN_IN
    assert "Retire this file when legalforecastbench-y7hk closes" in LEGACY_FAN_IN


def test_legacy_fan_in_keeps_the_provider_free_protected_boundary() -> None:
    assert "name: Fan In Official Shards (Legacy)" in LEGACY_FAN_IN
    assert "workflow_dispatch:" in LEGACY_FAN_IN
    assert "workflow_run:" not in LEGACY_FAN_IN
    assert "fan-in-results:" in LEGACY_FAN_IN
    assert "environment: legalforecastbench-official-eval-fan-in" in LEGACY_FAN_IN
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in LEGACY_FAN_IN
    assert "id-token: write" in LEGACY_FAN_IN
    assert "run-case:" not in LEGACY_FAN_IN
    assert "finalize-shard:" not in LEGACY_FAN_IN
    for provider_secret in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "MISTRAL_API_KEY",
    ):
        assert provider_secret not in LEGACY_FAN_IN


def test_legacy_fan_in_keeps_the_shard_receipt_dispatch_contract() -> None:
    """The inputs #1019 retired are exactly what the r4 repair fan-in needs."""

    for input_name in (
        "release_sha:",
        "cycle_id:",
        "freeze_bundle_path:",
        "source_dispatch_run_id:",
        "source_dispatch_run_attempt:",
        "source_dispatch_runs_json:",
        "accepted_attempt_map_path:",
        "verify_only:",
        "supplementary_artifacts_dir:",
        "hugging_face_release_version:",
    ):
        assert input_name in LEGACY_FAN_IN
    assert "python -m legalforecast.publication.shard_fan_in" in LEGACY_FAN_IN
    assert "python -m legalforecast.publication.shard_fan_in_publish" in LEGACY_FAN_IN
    assert '--receipt-root "s3://${LFB_RESULTS_BUCKET}"' in LEGACY_FAN_IN
    # The locked-manifest boundary's artifact contract must not leak in here:
    # run-benchmark-legacy.yaml does not emit that artifact. (The header comment
    # names it in prose, so this pins the executable forms.)
    assert "official-forecast-results-{run_id}-{attempt}" not in LEGACY_FAN_IN
    assert "Download exact durable forecast result artifact" not in LEGACY_FAN_IN
    assert "labels_release_uri:" not in LEGACY_FAN_IN


def test_source_dispatch_allowlist_accepts_both_dispatch_lanes() -> None:
    allowlist = _source_dispatch_path_allowlist()
    assert allowlist == {
        RUN_BENCHMARK_WORKFLOW_PATH,
        RUN_BENCHMARK_LEGACY_WORKFLOW_PATH,
    }
    # Pre-#1019 dispatches (the 2026-08-29/30 supplementary shards) carry the
    # first; the Cycle 1 r4 repair dispatches carry the second.
    assert RUN_BENCHMARK_WORKFLOW_PATH in allowlist
    assert RUN_BENCHMARK_LEGACY_WORKFLOW_PATH in allowlist


def test_source_dispatch_allowlist_refuses_any_other_workflow() -> None:
    allowlist = _source_dispatch_path_allowlist()
    for refused in (
        ".github/workflows/fan-in-publish.yaml",
        ".github/workflows/fan-in-publish-legacy.yaml",
        ".github/workflows/official-provider-cell.yaml",
        ".github/workflows/run-benchmark-manifest.yaml",
        ".github/workflows/attacker-supplied.yaml",
        "run-benchmark-legacy.yaml",
        ".github/workflows/run-benchmark-legacy.yml",
    ):
        assert refused not in allowlist, (
            f"the source-dispatch allowlist must be exactly two entries; {refused} "
            "would let an unrelated workflow's run supply fan-in provenance"
        )
    # An allowlist, never a prefix or substring match.
    assert 'run["path"].startswith' not in LEGACY_FAN_IN
    assert 'run["path"] !=' not in LEGACY_FAN_IN


def test_locked_manifest_fan_in_boundary_is_untouched() -> None:
    """The legacy entry is added beside Sol's boundary, never inside it."""

    locked = LOCKED_FAN_IN_PATH.read_text(encoding="utf-8")
    assert "name: Protected Labels Fan In" in locked
    assert RUN_BENCHMARK_LEGACY_WORKFLOW_PATH not in locked
    assert f'run.get("path") == "{RUN_BENCHMARK_WORKFLOW_PATH}"' in locked, (
        "the locked-manifest fan-in stays pinned to the single locked dispatch "
        "lane: it consumes a durable forecast artifact the legacy lane never "
        "emits, so widening it would admit a run it cannot score"
    )

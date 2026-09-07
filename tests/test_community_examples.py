from __future__ import annotations

from pathlib import Path

from legalforecast.multiharness.community import validate_submission_file
from legalforecast.publication.community_aggregate import (
    CommunityAggregateConfig,
    build_community_aggregate,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EXAMPLES_ROOT = ROOT / "tests" / "fixtures" / "community_submissions" / "2026"
EXPECTED_FIXTURE_EXAMPLES = {
    "lq-ai-fixture-bridge": "lq-ai-fixture-bridge",
    "hermes-agent-fixture-bridge": "hermes-agent-fixture-bridge",
    "openclaw-fixture-bridge": "openclaw-fixture-bridge",
    "openai-responses-fixture-baseline": "openai-responses-fixture-baseline",
    "claude-agent-sdk-fixture-baseline": "claude-agent-sdk-fixture-baseline",
}
EXPECTED_HISTORICAL_SMOKE_ADAPTERS = {
    "claude-agent-sdk-baseline",
    "openai-responses-baseline",
}
EXPECTED_HISTORICAL_SMOKE_SUBMISSIONS = {
    "claude-agent-sdk-community-smoke-20260809",
    "openai-responses-community-smoke-20260805",
}


def test_first_class_adapter_fixture_examples_validate() -> None:
    for submission_id, adapter_id in EXPECTED_FIXTURE_EXAMPLES.items():
        root = FIXTURE_EXAMPLES_ROOT / submission_id
        manifest = validate_submission_file(root / "submission.json")

        assert manifest.submission_id == submission_id
        assert manifest.run_summary.adapter_ids == (adapter_id,)
        assert manifest.run_summary.families == ("legalforecast_mtd",)
        assert manifest.run_summary.scoring_modes == ("lfb_brier",)
        assert manifest.run_summary.row_count == 1
        assert manifest.shards[0].adapter_id == adapter_id
        assert manifest.shards[0].compatible_shard_group_id.startswith(
            "legalforecast_mtd:lfb_brier:"
        )
        assert (root / "conformance-report.json").is_file()
        assert (root / "selection-manifest.json").is_file()
        assert (root / "artifact-manifest.json").is_file()
        assert (root / "hf-upload-plan.json").is_file()


def test_community_aggregate_contains_only_historical_provider_smokes(
    tmp_path: Path,
) -> None:
    submissions_root = ROOT / "community" / "submissions"
    submission_ids = {
        path.parent.name for path in submissions_root.rglob("submission.json")
    }
    assert submission_ids == EXPECTED_HISTORICAL_SMOKE_SUBMISSIONS

    result = build_community_aggregate(
        CommunityAggregateConfig(
            submissions_dir=submissions_root,
            output_dir=tmp_path / "aggregate",
        )
    )

    adapter_ids = {row.adapter_id for row in result.rows}
    assert adapter_ids == EXPECTED_HISTORICAL_SMOKE_ADAPTERS
    assert all(row.row_type == "single-shard" for row in result.rows)
    assert (result.output_dir / "reports" / "community-comparison.json").is_file()
    assert (result.output_dir / "registry" / "site-summary.json").is_file()

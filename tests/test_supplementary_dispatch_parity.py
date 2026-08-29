"""The supplementary lane is the official pipeline, not a parallel one.

The owner directive is that a post-anchor model runs through the same GitHub
Actions pipeline as the frozen four -- same docket tool, same output cap, same
reasoning posture -- rather than through a custom implementation. These tests
pin that as a property of the real dispatch issuer rather than as prose: the
supplementary registry is fed to the unmodified ``execution_scope`` plan issuer
and the resulting policy is asserted to carry official-identical harness
settings and the standard two-ablation shard schedule.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest.cost_projector import provider_lane
from legalforecast.evals.corpus_manifest.execution_scope import issue_execution_plan_v4
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.protocol.policy_artifacts import OFFICIAL_SHARD_ABLATIONS

REPO_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_REGISTRY = (
    REPO_ROOT
    / "model_registries"
    / "cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json"
)
SUPPLEMENTARY_REGISTRY = (
    REPO_ROOT
    / "model_registries"
    / "cycle-1-supplementary-gemini-3.7-flash-2026-08-29.json"
)
SUPPLEMENTARY_KEY = "google:gemini-3.7-flash"


def _common_frozen_inputs(registry_path: Path) -> dict[str, str]:
    return {
        "manifest_sha256": "b" * 64,
        "run_input_manifest_sha256": "b" * 64,
        "run_card_sha256": "b" * 64,
        "model_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
    }


def _supplementary_plan() -> dict[str, Any]:
    return issue_execution_plan_v4(
        cycle_id="cycle-1-target-100-2026-07-25",
        model_registry=SUPPLEMENTARY_REGISTRY,
        common_frozen_inputs=_common_frozen_inputs(SUPPLEMENTARY_REGISTRY),
    )


def test_supplementary_registry_issues_a_standard_execution_policy() -> None:
    """The unmodified issuer accepts a one-model supplementary registry."""

    plan = _supplementary_plan()
    policy = plan["policy"]

    assert plan["schema_version"] == "legalforecast.execution_policy.v4"
    assert list(policy["model_registry_entries"]) == [SUPPLEMENTARY_KEY]
    assert policy["cycle_series"] == "official"
    shards = {
        (shard["model_key"], shard["ablation"])
        for shard in policy["shard_schedule"]["shards"]
    }
    assert shards == {
        (SUPPLEMENTARY_KEY, ablation) for ablation in OFFICIAL_SHARD_ABLATIONS
    }


@pytest.mark.parametrize(
    "field",
    ["tool_policy", "max_output_tokens", "network_disabled", "search_disabled"],
)
def test_supplementary_entry_matches_official_harness_settings(field: str) -> None:
    """Every execution setting the official four share is shared here too."""

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    official_values = {getattr(entry, field) for entry in official}
    assert len(official_values) == 1, f"official four disagree on {field}"

    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]
    assert getattr(supplementary, field) == official_values.pop()


def test_supplementary_entry_requests_reasoning_explicitly() -> None:
    """No silent provider-default reasoning: the knob is set, not inherited.

    The official OpenAI entries pin reasoning_effort=high. Google exposes the
    equivalent as thinking_level, so parity means an explicit maximum there
    rather than an omitted field that would silently take Gemini's default.
    """

    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]
    assert supplementary.thinking_level is not None
    assert supplementary.thinking_level.value == "high"

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    openai_efforts = {
        entry.reasoning_effort.value
        for entry in official
        if entry.reasoning_effort is not None
    }
    assert openai_efforts == {"high"}


def test_supplementary_model_routes_to_the_existing_gemini_lane() -> None:
    """The workflow's gemini lane already serves provider google, unchanged."""

    assert provider_lane(SUPPLEMENTARY_KEY) == "gemini"


def test_supplementary_entry_is_the_only_post_anchor_model() -> None:
    """Parity does not extend to the anchor: this entry stays classified apart."""

    from legalforecast.evals.model_registry import earliest_eligible_decision_date
    from legalforecast.reporting.result_class import (
        ResultClass,
        classify_registry_entry,
    )

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    anchor = earliest_eligible_decision_date(official)
    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]

    assert classify_registry_entry(supplementary, corpus_anchor=anchor) is (
        ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )
    for entry in official:
        assert (
            classify_registry_entry(entry, corpus_anchor=anchor) is ResultClass.OFFICIAL
        )

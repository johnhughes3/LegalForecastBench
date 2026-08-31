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
from datetime import date
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
    / "cycle-1-2026-06-30-claude-fable-5-successor-2026-08-31.json"
)
SUPPLEMENTARY_REGISTRY = (
    REPO_ROOT
    / "model_registries"
    / "cycle-1-supplementary-gemini-3.7-flash-2026-08-29.json"
)
SUPPLEMENTARY_KEY = "google:gemini-3.7-flash"
# The earliest decision the Cycle 1 corpus scores. The corpus decision window
# closed 2026-06-30; the frozen registry's latest release is 2026-06-26.
CYCLE_1_CORPUS_ANCHOR = date(2026, 6, 30)


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
    ["tool_policy", "network_disabled", "search_disabled"],
)
def test_supplementary_entry_matches_official_harness_settings(field: str) -> None:
    """Every execution setting the official four share is shared here too."""

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    official_values = {getattr(entry, field) for entry in official}
    assert len(official_values) == 1, f"official four disagree on {field}"

    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]
    assert getattr(supplementary, field) == official_values.pop()


# Gemini 3.7 Flash's provider output-token limit, from
# https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash (checked
# 2026-08-29). A registry value above this is unreachable, so parity with the
# official 128000 cap is not available and the deviation is documented instead.
GEMINI_37_FLASH_PROVIDER_OUTPUT_LIMIT = 65_536


def test_supplementary_output_cap_is_official_parity_or_the_provider_maximum() -> None:
    """Match the official cap, or the provider ceiling where that is lower.

    Parity is the rule, but a registry cannot request more output than the
    provider will emit. Where the provider caps lower, the entry must sit
    exactly at that ceiling -- not at some intermediate value chosen by hand --
    and must say so in its caveats with a source.
    """

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    official_caps = {entry.max_output_tokens for entry in official}
    assert len(official_caps) == 1, "official four disagree on max_output_tokens"
    official_cap = official_caps.pop()

    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]
    expected = min(official_cap, GEMINI_37_FLASH_PROVIDER_OUTPUT_LIMIT)
    assert supplementary.max_output_tokens == expected

    if expected != official_cap:
        caveats = " ".join(supplementary.known_cutoff_publicity_caveats)
        assert str(GEMINI_37_FLASH_PROVIDER_OUTPUT_LIMIT) in caveats.replace(",", "")
        assert "https://" in caveats


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
    """Parity does not extend to the anchor: this entry stays classified apart.

    The anchor here is the CORPUS-derived one -- the earliest decision the cycle
    scores -- which is the definition the implementation uses everywhere. The
    Cycle 1 corpus decision window closed 2026-06-30, so 2026-06-30 stands in
    for the earliest scored decision; the frozen registry's own latest release
    is 2026-06-26. Both classify the four official models as official and
    Gemini 3.7 Flash (2026-08-13) as supplementary, but only the corpus-derived
    date is trustworthy when the registry varies.
    """

    from legalforecast.reporting.result_class import (
        ResultClass,
        classify_registry_entry,
    )

    official = load_model_registry(OFFICIAL_REGISTRY).entries
    anchor = CYCLE_1_CORPUS_ANCHOR
    supplementary = load_model_registry(SUPPLEMENTARY_REGISTRY).entries[0]

    assert classify_registry_entry(supplementary, corpus_anchor=anchor) is (
        ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )
    for entry in official:
        assert (
            classify_registry_entry(entry, corpus_anchor=anchor) is ResultClass.OFFICIAL
        )


def test_run_case_cli_flag_reaches_the_runner_config() -> None:
    """The dispatch flag must actually land on the config the gate reads.

    The provider cell reaches the runner through ``eval run-case``, so an
    unwired flag would leave supplementary mode unreachable from Actions even
    though the Python API supports it. Parsing the real argv guards that seam.
    """

    from legalforecast.cli import build_parser

    parser = build_parser()
    base = [
        "eval",
        "run-case",
        "--manifest",
        "run-inputs.json",
        "--case-id",
        "case-1",
        "--ablation",
        "full_packet",
        "--output-dir",
        "out",
    ]
    assert parser.parse_args([*base, "--supplementary"]).supplementary is True
    assert parser.parse_args(base).supplementary is False

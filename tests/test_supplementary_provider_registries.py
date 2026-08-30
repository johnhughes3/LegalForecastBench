"""Gates on the shipped supplementary provider registries.

These registries are the only place a model's frozen identity, price and
execution settings live, so the checks here are about identity and eligibility
rather than about code paths: does each entry classify into the lane it claims,
does it fail closed when a required field is missing, and does every published
value carry a source and a checked-on date.

The corpus anchor is hard-coded to the value Cycle 1 actually froze rather than
derived, so that a change to either the anchor or a release timestamp shows up
here as a failure instead of silently reclassifying a published row.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    load_model_registry,
)
from legalforecast.reporting.result_class import (
    ResultClass,
    ResultClassError,
    classify_registry_entry,
    require_lane_result_classes,
)

REGISTRY_DIR = Path(__file__).resolve().parents[1] / "model_registries"

CYCLE_1_CORPUS_ANCHOR = date(2026, 6, 30)
"""The anchor Cycle 1 froze.

Recorded in the Gemini supplementary receipt's ``supplementary_binding`` and
consistent with the frozen official registry, whose latest release
(claude-sonnet-5, 2026-06-30) classifies official and therefore cannot postdate
the anchor.
"""

SUPPLEMENTARY_REGISTRIES = (
    "cycle-1-supplementary-grok-4.6-2026-08-30.json",
    "cycle-1-supplementary-kimi-k3-2026-08-30.json",
)

EXPECTED_IDENTITY = {
    "xai:grok-4.6": {
        "model_version_or_snapshot": "grok-4.6",
        "release": "2026-08-12",
        "input_price": 2.0,
        "output_price": 6.0,
    },
    "deepinfra:moonshotai/Kimi-K3": {
        "model_version_or_snapshot": "moonshotai/Kimi-K3",
        "release": "2026-07-17",
        "input_price": 2.85,
        "output_price": 14.25,
    },
}

# Parity targets taken from the frozen official successor registry
# cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json.
OFFICIAL_PARITY_MAX_OUTPUT_TOKENS = 128000
OFFICIAL_PARITY_REASONING_EFFORT = "high"
OFFICIAL_PARITY_TOOL_POLICY = "controlled_docket_tool_only"


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_every_shipped_entry_classifies_supplementary(filename: str) -> None:
    """A supplementary registry must contain only post-anchor models.

    Both directions are enforced by ``require_lane_result_classes``: a
    pre-anchor model cannot be smuggled into the supplementary lane, which is
    what excluded GLM 5.2 (2026-06-16) and MiniMax M3 (2026-06-01) from this
    work entirely.
    """

    registry = load_model_registry(REGISTRY_DIR / filename)
    assert registry.entries

    for entry in registry.entries:
        assert (
            classify_registry_entry(entry, corpus_anchor=CYCLE_1_CORPUS_ANCHOR)
            is ResultClass.SUPPLEMENTARY_POST_ANCHOR
        )

    require_lane_result_classes(
        list(registry.entries),
        corpus_anchor=CYCLE_1_CORPUS_ANCHOR,
        supplementary=True,
    )


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_shipped_entries_refuse_the_official_lane(filename: str) -> None:
    """The same registry must be refused if presented as an official result set."""

    registry = load_model_registry(REGISTRY_DIR / filename)
    with pytest.raises(ResultClassError, match="refuse models released after"):
        require_lane_result_classes(
            list(registry.entries),
            corpus_anchor=CYCLE_1_CORPUS_ANCHOR,
            supplementary=False,
        )


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_shipped_entries_pin_their_verified_identity_and_price(filename: str) -> None:
    """Freeze the researched values so a later edit cannot drift them quietly."""

    registry = load_model_registry(REGISTRY_DIR / filename)
    for entry in registry.entries:
        expected = EXPECTED_IDENTITY[entry.registry_key]
        assert entry.model_version_or_snapshot == expected["model_version_or_snapshot"]
        assert entry.release_timestamp is not None
        assert entry.release_timestamp.date().isoformat() == expected["release"]
        assert entry.input_token_price == expected["input_price"]
        assert entry.output_token_price == expected["output_price"]


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_shipped_entries_match_official_execution_parity(filename: str) -> None:
    """Execution settings mirror the frozen official successor registry.

    Neither model needed a provider-imposed deviation from the official output
    cap, and both carry an explicit reasoning setting rather than relying on a
    provider default -- the owner directive on bead legalforecastbench-1xko.
    """

    registry = load_model_registry(REGISTRY_DIR / filename)
    for entry in registry.entries:
        assert entry.max_output_tokens == OFFICIAL_PARITY_MAX_OUTPUT_TOKENS
        assert entry.tool_policy.value == OFFICIAL_PARITY_TOOL_POLICY
        assert entry.reasoning_effort is not None, (
            "an explicit reasoning setting is required; a silent provider "
            "default is never acceptable"
        )
        assert entry.reasoning_effort.value == OFFICIAL_PARITY_REASONING_EFFORT
        assert entry.network_disabled is True
        assert entry.search_disabled is True
        # The prompt budget must leave room for the docket-tool transcript.
        assert entry.context_limit > entry.max_output_tokens


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_every_shipped_entry_documents_sources_and_check_dates(filename: str) -> None:
    """Every published value must be traceable to a source read on a stated date.

    These model versions postdate the training data of anyone likely to review
    this file, so an unsourced value is indistinguishable from an invented one.
    """

    registry = load_model_registry(REGISTRY_DIR / filename)
    for entry in registry.entries:
        assert "http" in entry.pricing_source
        assert "2026-08-30" in entry.pricing_source
        assert entry.release_timestamp_source is not None
        assert "http" in entry.release_timestamp_source
        assert "2026-08-30" in entry.release_timestamp_source
        assert entry.known_cutoff_publicity_caveats
        caveats = " ".join(entry.known_cutoff_publicity_caveats)
        # An undisclosed cutoff must be stated as undisclosed, never inferred
        # from the release date.
        assert entry.provider_training_cutoff is None
        assert entry.provider_training_cutoff_status.value == "unknown"
        assert "supplementary" in caveats
        assert "2026-06-30" in caveats


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
@pytest.mark.parametrize(
    "required_field",
    (
        "provider",
        "model_id",
        "display_name",
        "model_version_or_snapshot",
        "max_output_tokens",
        "context_limit",
        "pricing_source",
        "input_token_price",
        "output_token_price",
        "tool_policy",
        "network_disabled",
        "search_disabled",
        "provider_training_cutoff_status",
    ),
)
def test_registry_entry_refuses_a_missing_required_field(
    filename: str,
    required_field: str,
) -> None:
    """Dropping any required field must refuse, never default."""

    record = _first_record(REGISTRY_DIR / filename)
    del record[required_field]

    with pytest.raises((TypeError, ValueError, KeyError)):
        ModelRegistryEntry.from_record(record)


@pytest.mark.parametrize("filename", SUPPLEMENTARY_REGISTRIES)
def test_entry_without_a_release_timestamp_fails_closed_to_supplementary(
    filename: str,
) -> None:
    """A model that cannot prove it predates the anchor is never official.

    Fail-closed by omission: the absence of evidence classifies as
    supplementary rather than inheriting official status.
    """

    record = _first_record(REGISTRY_DIR / filename)
    record["release_timestamp"] = None
    record["release_timestamp_source"] = None
    entry = ModelRegistryEntry.from_record(record)

    assert entry.release_timestamp is None
    assert (
        classify_registry_entry(entry, corpus_anchor=CYCLE_1_CORPUS_ANCHOR)
        is ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )


def _first_record(path: Path) -> dict[str, Any]:
    payload: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    record = payload[0]
    assert isinstance(record, dict)
    return dict(record)

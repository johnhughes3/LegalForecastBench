from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.publication.run_cards import (
    RUN_CARD_SCHEMA_VERSION,
    RunCardArtifacts,
    build_run_card_record,
    validate_run_card_record,
    write_run_card,
)


def test_model_and_run_card_templates_cover_required_publication_fields() -> None:
    model_template = _read_text("docs/model_card_template.md")
    run_template = _read_text("docs/run_card_template.md")
    schema = json.loads(_read_text("docs/run_card_schema.json"))

    assert "Provider training cutoff status" in model_template
    assert "Network disabled confirmed" in model_template
    assert "95th percentile tool calls per case" in model_template
    assert "Run cards are machine-readable JSON artifacts" in run_template
    assert schema["properties"]["schema_version"]["const"] == RUN_CARD_SCHEMA_VERSION
    assert "accounting_summary" in schema["required"]
    assert "prompt_sha256" in schema["properties"]["hashes"]["required"]


def test_build_run_card_record_emits_complete_valid_official_card(tmp_path) -> None:
    record = _run_card_record(run_type="official")

    result = validate_run_card_record(record)

    assert result.ok
    assert record["run"]["run_type"] == "official"
    assert record["model"]["provider"] == "example-provider"
    assert record["policy"]["network_disabled"] is True
    assert record["accounting_summary"]["cost_per_case"] == 0.02

    output_path = write_run_card(record, tmp_path / "run-card.json")
    assert json.loads(output_path.read_text(encoding="utf-8")) == record


def test_build_run_card_record_emits_complete_valid_rapid_card() -> None:
    record = _run_card_record(run_type="rapid")

    assert validate_run_card_record(record).ok
    assert record["run"]["run_type"] == "rapid"


def test_run_card_validation_fails_when_required_fields_are_missing() -> None:
    record = _run_card_record(run_type="rapid")
    del record["hashes"]["prompt_sha256"]
    del record["accounting_summary"]["cost_per_prediction_unit"]

    result = validate_run_card_record(record)

    assert not result.ok
    issue_paths = {issue.path for issue in result.issues}
    assert "hashes.prompt_sha256" in issue_paths
    assert "accounting_summary.cost_per_prediction_unit" in issue_paths


def test_run_card_validation_requires_known_cutoff_date() -> None:
    record = _run_card_record(run_type="rapid")
    record["model"]["provider_training_cutoff"] = None

    result = validate_run_card_record(record)

    assert not result.ok
    assert any(
        issue.path == "model.provider_training_cutoff" and "required" in issue.message
        for issue in result.issues
    )


def test_run_card_validation_requires_disabled_network_and_search() -> None:
    record = _run_card_record(run_type="rapid")
    record["policy"]["network_disabled"] = False
    record["model"]["search_disabled"] = False

    result = validate_run_card_record(record)

    assert not result.ok
    issue_paths = {issue.path for issue in result.issues}
    assert "policy.network_disabled" in issue_paths
    assert "model.search_disabled" in issue_paths


def test_run_card_validation_rejects_invalid_token_totals_and_rates() -> None:
    record = _run_card_record(run_type="rapid")
    record["accounting_summary"]["total_tokens"] = 10
    record["accounting_summary"]["refusal_rate"] = 1.5

    result = validate_run_card_record(record)

    assert not result.ok
    issue_paths = {issue.path for issue in result.issues}
    assert "accounting_summary.total_tokens" in issue_paths
    assert "accounting_summary.refusal_rate" in issue_paths


@pytest.mark.parametrize(
    ("section", "field_name", "value", "expected_path", "expected_message"),
    (
        (
            "model",
            "provider_training_cutoff_status",
            "pretraining",
            "model.provider_training_cutoff_status",
            "must be known, unknown, or not_disclosed",
        ),
        (
            "model",
            "provider_training_cutoff_status",
            "unknown",
            "model.provider_training_cutoff",
            "must be null unless cutoff status is known",
        ),
        (
            "model",
            "provider_training_cutoff_status",
            "not_disclosed",
            "model.provider_training_cutoff",
            "must be null unless cutoff status is known",
        ),
        (
            "model",
            "provider_training_cutoff",
            "April 2026",
            "model.provider_training_cutoff",
            "must be an ISO date",
        ),
        (
            "run",
            "run_type",
            "ad_hoc",
            "run.run_type",
            "must be one of",
        ),
        (
            "model",
            "tool_policy",
            "browser_access",
            "model.tool_policy",
            "must be no_tools or controlled_docket_tool_only",
        ),
        (
            "policy",
            "tool_policy",
            "browser_access",
            "policy.tool_policy",
            "must be no_tools or controlled_docket_tool_only",
        ),
        (
            "hashes",
            "prompt_sha256",
            "sha256:ABC",
            "hashes.prompt_sha256",
            "must match sha256:<64 lowercase hex characters>",
        ),
        (
            "run",
            "generated_at",
            "May 14, 2026",
            "run.generated_at",
            "must be an ISO timestamp",
        ),
        (
            "model",
            "release_timestamp",
            "May 14, 2026",
            "model.release_timestamp",
            "must be an ISO timestamp",
        ),
        (
            "run",
            "limitations",
            "fixture-only",
            "run.limitations",
            "must be an array",
        ),
        (
            "model",
            "known_cutoff_publicity_caveats",
            ("documented", ""),
            "model.known_cutoff_publicity_caveats[1]",
            "must be a non-empty string",
        ),
    ),
)
def test_run_card_validation_rejects_public_schema_edge_cases(
    section: str,
    field_name: str,
    value: object,
    expected_path: str,
    expected_message: str,
) -> None:
    record = _run_card_record(run_type="rapid")
    _section(record, section)[field_name] = value

    result = validate_run_card_record(record)

    assert not result.ok
    assert any(
        issue.path == expected_path and expected_message in issue.message
        for issue in result.issues
    )


def test_build_run_card_record_surfaces_accounting_summary_validation_errors() -> None:
    accounting_summary = _accounting_summary()
    del accounting_summary["cost_per_prediction_unit"]
    accounting_summary["refusal_rate"] = 1.5

    with pytest.raises(ValueError) as exc_info:
        _run_card_record(run_type="rapid", accounting_summary=accounting_summary)

    assert str(exc_info.value) == (
        "run card validation failed: "
        "accounting_summary.cost_per_prediction_unit: must be a number; "
        "accounting_summary.refusal_rate: must be at most 1"
    )


def _run_card_record(
    *,
    run_type: str,
    accounting_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_run_card_record(
        run_id=f"cycle-2026-rapid-001/example-provider:example-model/{run_type}",
        run_type=run_type,
        generated_at=datetime(2026, 5, 14, 18, 45, tzinfo=UTC),
        registry_entry=ModelRegistryEntry.from_record(_registry_record()),
        artifacts=RunCardArtifacts(
            cycle_id="cycle-2026-rapid-001",
            evaluation_timestamp=datetime(2026, 5, 14, 18, 30, tzinfo=UTC),
            harness_version=_hash("harness"),
            prompt_sha256=_hash("prompt"),
            scorer_sha256=_hash("scorer"),
            model_registry_sha256=_hash("registry"),
            manifest_sha256=_hash("manifest"),
            prediction_unit_sha256=_hash("units"),
            label_sha256=_hash("labels"),
            tool_call_cap=10,
            run_label="full_packet",
        ),
        accounting_summary=(
            accounting_summary
            if accounting_summary is not None
            else _accounting_summary()
        ),
        limitations=("fixture-only values for validation tests",),
        notes=("generated by unit test",),
    )


def _accounting_summary() -> dict[str, object]:
    return {
        "case_count": 3,
        "prediction_unit_count": 6,
        "request_count": 3,
        "prompt_tokens": 1_000,
        "completion_tokens": 200,
        "total_tokens": 1_200,
        "mean_tool_calls_per_case": 2.3,
        "median_tool_calls_per_case": 2,
        "p95_tool_calls_per_case": 5,
        "cost_per_case": 0.02,
        "cost_per_prediction_unit": 0.01,
        "mean_latency_ms": 200,
        "p95_latency_ms": 300,
        "invalid_output_rate": 0,
        "refusal_rate": 0,
        "content_filter_rate": 0,
    }


def _section(record: dict[str, object], section_name: str) -> dict[str, object]:
    section = record[section_name]
    assert isinstance(section, dict)
    return section


def _registry_record() -> dict[str, object]:
    return {
        "provider": "example-provider",
        "model_id": "example-model",
        "display_name": "Example Model",
        "model_version_or_snapshot": "2026-05-14",
        "release_timestamp": "2026-05-14T09:00:00Z",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "provider-price-sheet-2026-05-14",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": ["no stable public cutoff"],
    }


def _hash(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('utf-8')).hexdigest()}"


def _read_text(path: str) -> str:
    return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from legalforecast.evals import (
    ModelRegistry,
    ToolPolicy,
    dump_model_registry,
    load_model_registry,
)
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.selection import TrainingCutoffStatus


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


def test_model_registry_entry_round_trips_plan_fields() -> None:
    entry = ModelRegistryEntry.from_record(_registry_record())

    assert entry.provider == "example-provider"
    assert entry.model_id == "example-model"
    assert entry.tool_policy is ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY
    assert entry.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN
    assert entry.release_timestamp == datetime(2026, 5, 14, 9, 0, tzinfo=UTC)

    record = entry.to_record()
    assert record["release_timestamp"] == "2026-05-14T09:00:00Z"
    assert record["provider_training_cutoff"] == "2026-04-01"
    assert record["temperature"] == 0.0
    json.dumps(record)


def test_registry_exports_model_run_metadata_for_eligibility_schema() -> None:
    entry = ModelRegistryEntry.from_record(_registry_record())

    run_metadata = entry.to_model_run_metadata(datetime(2026, 5, 14, 12, 0, tzinfo=UTC))

    assert run_metadata.provider == entry.provider
    assert run_metadata.model_name == entry.model_id
    assert run_metadata.network_disabled is True
    assert run_metadata.search_disabled is True
    assert run_metadata.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN


def test_registry_rejects_missing_required_fields() -> None:
    record = _registry_record()
    del record["pricing_source"]

    with pytest.raises(ValueError, match="pricing_source is required"):
        ModelRegistryEntry.from_record(record)


def test_registry_rejects_unknown_cutoff_date() -> None:
    record = _registry_record()
    record["provider_training_cutoff_status"] = "unknown"

    with pytest.raises(ValueError, match="must be omitted"):
        ModelRegistryEntry.from_record(record)


def test_registry_rejects_duplicate_provider_model_ids() -> None:
    record = _registry_record()

    with pytest.raises(ValueError, match="duplicate model registry entries"):
        ModelRegistry.from_records([record, record])


def test_registry_file_load_and_dump(tmp_path) -> None:
    path = tmp_path / "models.json"
    path.write_text(json.dumps([_registry_record()]), encoding="utf-8")

    registry = load_model_registry(path)
    assert registry.get("example-provider", "example-model").display_name == (
        "Example Model"
    )

    output_path = tmp_path / "models.out.json"
    dump_model_registry(registry, output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == [
        registry.entries[0].to_record()
    ]

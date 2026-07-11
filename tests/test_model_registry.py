from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from legalforecast.evals import (
    ModelRegistry,
    ToolPolicy,
    dump_model_registry,
    load_model_registry,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    earliest_eligible_decision_date,
    latest_release_timestamp,
    model_registry_entry_sha256,
    require_official_registry_entries,
)
from legalforecast.selection import TrainingCutoffStatus

ROOT = Path(__file__).resolve().parents[1]
PILOT_REGISTRY = ROOT / "model_registries" / "pilot-2026-04-24_to_2026-05-18.json"


def _registry_record() -> dict[str, object]:
    return {
        "provider": "example-provider",
        "model_id": "example-model",
        "display_name": "Example Model",
        "model_version_or_snapshot": "2026-05-14",
        "release_timestamp": "2026-05-14T09:00:00Z",
        "release_timestamp_source": "fixture release note",
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


def _entry(**overrides: object) -> ModelRegistryEntry:
    record = _registry_record()
    record.update(overrides)
    return ModelRegistryEntry.from_record(record)


def test_model_registry_entry_round_trips_plan_fields() -> None:
    entry = ModelRegistryEntry.from_record(_registry_record())

    assert entry.provider == "example-provider"
    assert entry.model_id == "example-model"
    assert entry.tool_policy is ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY
    assert entry.provider_training_cutoff_status is TrainingCutoffStatus.KNOWN
    assert entry.release_timestamp == datetime(2026, 5, 14, 9, 0, tzinfo=UTC)

    record = entry.to_record()
    assert record["release_timestamp"] == "2026-05-14T09:00:00Z"
    assert record["release_timestamp_source"] == "fixture release note"
    assert record["provider_training_cutoff"] == "2026-04-01"
    assert record["temperature"] == 0.0
    json.dumps(record)


def test_model_registry_entry_hash_is_canonical() -> None:
    entry = _entry()

    assert model_registry_entry_sha256(entry) == model_registry_entry_sha256(
        ModelRegistryEntry.from_record(dict(reversed(tuple(entry.to_record().items()))))
    )
    assert model_registry_entry_sha256(entry) != model_registry_entry_sha256(
        _entry(input_token_price=entry.input_token_price + 0.01)
    )


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


def test_registry_rejects_release_timestamp_without_source() -> None:
    record = _registry_record()
    del record["release_timestamp_source"]

    with pytest.raises(ValueError, match="release_timestamp_source is required"):
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


def test_pilot_registry_contains_requested_model_matrix() -> None:
    registry = load_model_registry(PILOT_REGISTRY)

    assert {entry.registry_key for entry in registry.entries} == {
        "openai:gpt-5.4-mini",
        "anthropic:claude-sonnet-4-6",
    }
    for entry in registry.entries:
        assert entry.release_timestamp_source
        assert entry.network_disabled is True
        assert entry.search_disabled is True
        assert entry.tool_policy is ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY
        assert entry.input_token_price > 0
        assert entry.output_token_price > 0


def test_latest_release_timestamp_uses_latest_official_model_release() -> None:
    older = _entry(
        provider="older-provider",
        model_id="older-model",
        release_timestamp="2026-05-14T09:00:00Z",
    )
    newer = _entry(
        provider="newer-provider",
        model_id="newer-model",
        release_timestamp="2026-05-16T03:30:00Z",
    )

    assert latest_release_timestamp((older, newer)) == datetime(
        2026,
        5,
        16,
        3,
        30,
        tzinfo=UTC,
    )


def test_latest_release_timestamp_rejects_missing_release_anchor() -> None:
    missing = _entry(
        provider="missing-provider",
        model_id="missing-model",
        release_timestamp=None,
    )

    with pytest.raises(ValueError, match="missing-provider:missing-model"):
        latest_release_timestamp((missing,))


def test_earliest_eligible_decision_date_uses_first_deployment_date() -> None:
    late_utc_release = _entry(release_timestamp="2026-05-14T23:59:59Z")

    assert earliest_eligible_decision_date((late_utc_release,)) == date(2026, 5, 14)


def test_official_registry_rejects_mutable_preview_or_latest_aliases() -> None:
    preview = _entry(
        provider="preview-provider",
        model_id="model-preview",
        model_version_or_snapshot="model-preview",
    )
    latest = _entry(
        provider="latest-provider",
        model_id="model-latest",
        model_version_or_snapshot="model-latest",
    )

    with pytest.raises(ValueError, match="preview-provider:model-preview"):
        require_official_registry_entries((preview,))
    with pytest.raises(ValueError, match="latest-provider:model-latest"):
        require_official_registry_entries((latest,))


def test_official_registry_accepts_dated_preview_snapshot() -> None:
    dated_preview = _entry(
        provider="preview-provider",
        model_id="model-preview",
        model_version_or_snapshot="model-preview-2026-05-14",
    )

    assert require_official_registry_entries((dated_preview,)) == (dated_preview,)

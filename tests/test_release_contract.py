from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    FORECAST_RELEASE_V1,
    LABELS_RELEASE_V1,
)
from legalforecast.release import (
    BRIEFING_ROLES,
    PLEADING_ROLES,
    ForecastRelease,
    LabelsRelease,
    ReleaseValidationError,
    issue_synthetic_release,
    load_forecast_execution,
    publish_release,
    validate_release,
)
from pydantic import ValidationError


def test_synthetic_issuer_is_deterministic_complete_and_blinded(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    issue_synthetic_release(first)
    issue_synthetic_release(second)

    first_payloads = _tree_payloads(first)
    assert first_payloads == _tree_payloads(second)
    assert all(payload.endswith(b"\n") for payload in first_payloads.values())

    forecast, labels = validate_release(
        first / "forecast-release.json",
        first / "labels-release.json",
        artifact_root=first,
    )
    assert forecast.schema_version == str(FORECAST_RELEASE_V1)
    assert labels.schema_version == str(LABELS_RELEASE_V1)
    assert forecast.case_count == 3
    assert forecast.unit_count == 3
    assert labels.unit_count == 3
    full_packet_roles = {
        document.role
        for document in forecast.cases[0].documents
        if document.document_id.startswith("full-")
    }
    assert full_packet_roles == PLEADING_ROLES | BRIEFING_ROLES

    execution = load_forecast_execution(
        first / "forecast-release.json", artifact_root=first
    )
    assert execution.release == forecast
    assert "labels" not in dir(execution)
    assert "labels" not in inspect.signature(load_forecast_execution).parameters
    assert execution.packet_bytes("unit-001").startswith(b"{")
    assert execution.prompt_bytes("unit-001").startswith(b"Forecast whether")
    assert execution.document_bytes("unit-001", 0).startswith(
        b"Synthetic predecision material"
    )


def test_execution_rereads_committed_bytes_at_use_time(tmp_path: Path) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    execution = load_forecast_execution(
        root / "forecast-release.json", artifact_root=root
    )
    packet = root / execution.release.prediction_units[0].packet_path
    original = packet.read_bytes()
    packet.write_bytes(bytes([original[0] ^ 1]) + original[1:])

    with pytest.raises(ReleaseValidationError, match="packet SHA-256 mismatch"):
        execution.packet_bytes("unit-001")


def test_publication_rechecks_committed_bytes_at_publish_time(tmp_path: Path) -> None:
    source = tmp_path / "source"
    issued = issue_synthetic_release(source)
    packet = source / issued.forecast.prediction_units[0].packet_path
    original = packet.read_bytes()
    packet.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    output = tmp_path / "published"

    with pytest.raises(ReleaseValidationError, match="packet SHA-256 mismatch"):
        publish_release(output, issued, artifact_root=source)

    assert not output.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(case_count=4), "case_count"),
        (
            lambda value: (
                value["prediction_units"].append(dict(value["prediction_units"][0]))
                or value.update(unit_count=4)
            ),
            "duplicate prediction unit",
        ),
        (
            lambda value: value["prediction_units"].reverse(),
            "canonical unit order",
        ),
        (
            lambda value: value["cases"][0]["documents"][0].update(
                path="../private.pdf"
            ),
            "relative POSIX path",
        ),
        (
            lambda value: value["prediction_units"][0].update(outcome=1),
            "extra_forbidden",
        ),
        (
            lambda value: value["cases"][0]["documents"][0].update(role="decision"),
            "Input should be",
        ),
    ],
)
def test_forecast_contract_rejects_structural_mutations(
    tmp_path: Path,
    mutation: Any,
    message: str,
) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    value = json.loads((root / "forecast-release.json").read_bytes())
    mutation(value)
    value["release_digest"] = _digest_placeholder()

    with pytest.raises((ValidationError, ReleaseValidationError), match=message):
        ForecastRelease.model_validate_json(ARTIFACT_CANONICAL_JSON_V1.encode(value))


def test_release_validation_rejects_hash_mutation_and_unit_set_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    forecast_value = json.loads((root / "forecast-release.json").read_bytes())
    labels_value = json.loads((root / "labels-release.json").read_bytes())

    forecast_value["release_digest"] = _digest_placeholder()
    mutated_forecast = tmp_path / "mutated-forecast.json"
    mutated_forecast.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(forecast_value))
    with pytest.raises(ReleaseValidationError, match="forecast release digest"):
        validate_release(
            mutated_forecast,
            root / "labels-release.json",
            artifact_root=root,
        )

    labels_value["unit_outcomes"][-1]["unit_id"] = "unknown-unit"
    labels_value["release_digest"] = _labels_digest(labels_value)
    mutated_labels = tmp_path / "mutated-labels.json"
    mutated_labels.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(labels_value))
    with pytest.raises(ReleaseValidationError, match="labels unit set"):
        validate_release(
            root / "forecast-release.json",
            mutated_labels,
            artifact_root=root,
        )


def test_release_validation_rejects_changed_artifact_bytes(tmp_path: Path) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    forecast = ForecastRelease.model_validate_json(
        (root / "forecast-release.json").read_bytes()
    )
    packet = root / forecast.prediction_units[0].packet_path
    original = packet.read_bytes()
    packet.write_bytes(bytes([original[0] ^ 1]) + original[1:])

    with pytest.raises(ReleaseValidationError, match="packet SHA-256 mismatch"):
        validate_release(
            root / "forecast-release.json",
            root / "labels-release.json",
            artifact_root=root,
        )


def test_release_artifacts_are_canonical_json(tmp_path: Path) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)

    forecast_bytes = (root / "forecast-release.json").read_bytes()
    labels_bytes = (root / "labels-release.json").read_bytes()
    forecast = ForecastRelease.model_validate_json(forecast_bytes)
    labels = LabelsRelease.model_validate_json(labels_bytes)

    assert forecast_bytes == ARTIFACT_CANONICAL_JSON_V1.encode(
        forecast.model_dump(mode="json")
    )
    assert labels_bytes == ARTIFACT_CANONICAL_JSON_V1.encode(
        labels.model_dump(mode="json")
    )


def test_validator_rejects_noncanonical_release_bytes(tmp_path: Path) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    value = json.loads((root / "forecast-release.json").read_bytes())
    noncanonical = tmp_path / "forecast-pretty.json"
    noncanonical.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReleaseValidationError, match="not canonical artifact JSON"):
        validate_release(
            noncanonical,
            root / "labels-release.json",
            artifact_root=root,
        )


def _tree_payloads(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _digest_placeholder() -> str:
    return "0" * 64


def _labels_digest(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "release_digest"}
    return str(ARTIFACT_RAW_SHA256_V1.commit(payload, domain=LABELS_RELEASE_V1).digest)

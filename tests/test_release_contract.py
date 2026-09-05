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
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    ForecastRelease,
    LabelsDraft,
    LabelsRelease,
    PredictionUnitDraft,
    ReleaseCase,
    ReleaseValidationError,
    ScoringPolicy,
    UnitOutcome,
    enumerate_forecast_worker_inputs,
    issue_release,
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
    legacy_forecast = json.loads((first / "forecast-release.json").read_bytes())
    assert all(
        all(
            field not in document
            for field in (
                "supporting_side",
                "supporting_kind",
                "target_motion_document_id",
            )
        )
        for case in legacy_forecast["cases"]
        for document in case["documents"]
    )

    forecast, labels = validate_release(
        first / "forecast-release.json",
        first / "labels-release.json",
        artifact_root=first,
    )
    assert forecast.schema_version == str(FORECAST_RELEASE_V1)
    assert labels.schema_version == str(LABELS_RELEASE_V1)
    assert forecast.case_count == 3
    assert forecast.unit_count == 3
    assert labels.unit_count == 2
    assert [unit.count for unit in forecast.prediction_units] == [
        "Count I",
        "Count II",
        "Count III",
    ]
    assert [
        unit.unit_id for unit in forecast.prediction_units if unit.should_score
    ] == [
        "unit-001",
        "unit-002",
    ]
    assert [outcome.unit_id for outcome in labels.unit_outcomes] == [
        "unit-001",
        "unit-002",
    ]
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


def test_issue_release_preserves_multiple_supporting_documents_and_metadata(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    documents = (
        DocumentDraft(
            document_id="complaint",
            role="complaint",
            path="documents/complaint.txt",
        ),
        DocumentDraft(
            document_id="motion",
            role="motion_to_dismiss_memorandum",
            path="documents/motion.txt",
        ),
        DocumentDraft(
            document_id="opposition",
            role="opposition",
            path="documents/opposition.txt",
        ),
        DocumentDraft(
            document_id="opening-declaration",
            role="supporting_document",
            path="documents/opening-declaration.txt",
            supporting_side="opening",
            supporting_kind="declaration",
            target_motion_document_id="motion",
        ),
        DocumentDraft(
            document_id="opposition-exhibit",
            role="supporting_document",
            path="documents/opposition-exhibit.txt",
            supporting_side="opposition",
            supporting_kind="exhibit",
            target_motion_document_id="motion",
        ),
    )
    payloads = {
        document.path: f"payload for {document.document_id}".encode()
        for document in documents
    }
    packet_path = "packets/unit-001.json"
    prompt_path = "prompts/unit-001.txt"
    payloads[packet_path] = b'{"case_id":"case-001"}'
    payloads[prompt_path] = b"Forecast all units together."
    for path, payload in payloads.items():
        path_on_disk = artifact_root / path
        path_on_disk.parent.mkdir(parents=True, exist_ok=True)
        path_on_disk.write_bytes(payload)

    issued = issue_release(
        ForecastDraft(
            release_id="supporting-documents-test",
            policy_digest="0" * 64,
            code_version="test-code",
            packet_builder_version="test-packet-builder",
            cases=(CaseDraft(case_id="case-001", documents=documents),),
            prediction_units=(
                PredictionUnitDraft(
                    unit_id="unit-001",
                    case_id="case-001",
                    claim_name="Count I",
                    defendant_group="all defendants",
                    count="Count I",
                    should_score=True,
                    model_visible_document_ids=tuple(
                        document.document_id for document in documents
                    ),
                    packet_path=packet_path,
                    prompt_path=prompt_path,
                ),
            ),
        ),
        LabelsDraft(
            release_id="supporting-documents-test",
            scoring_policy=ScoringPolicy(policy_id="test-policy"),
            unit_outcomes=(UnitOutcome(unit_id="unit-001", outcome=1),),
        ),
        artifact_root=artifact_root,
    )

    support = [
        document
        for document in issued.forecast.cases[0].documents
        if document.role == "supporting_document"
    ]
    assert [
        (document.document_id, document.supporting_side, document.supporting_kind)
        for document in support
    ] == [
        ("opening-declaration", "opening", "declaration"),
        ("opposition-exhibit", "opposition", "exhibit"),
    ]
    assert all(document.target_motion_document_id == "motion" for document in support)
    worker_document_paths = {
        item.relative_path
        for item in enumerate_forecast_worker_inputs(issued.forecast)
        if item.kind == "document"
    }
    assert {document.path for document in support} <= worker_document_paths
    forecast_path = artifact_root / "forecast-release.json"
    forecast_path.write_bytes(
        ARTIFACT_CANONICAL_JSON_V1.encode(issued.forecast.model_dump(mode="json"))
    )
    execution = load_forecast_execution(forecast_path, artifact_root=artifact_root)
    assert (
        execution.document_bytes(
            "unit-001",
            next(
                index
                for index, document in enumerate(issued.forecast.cases[0].documents)
                if document.document_id == "opposition-exhibit"
            ),
        )
        == b"payload for opposition-exhibit"
    )


def test_release_rejects_invalid_supporting_document_linkage(tmp_path: Path) -> None:
    root = tmp_path / "release"
    issue_synthetic_release(root)
    forecast_value = json.loads((root / "forecast-release.json").read_bytes())
    case_value = forecast_value["cases"][0]
    complaint_id = next(
        document["document_id"]
        for document in case_value["documents"]
        if document["role"] == "complaint"
    )
    support_value = {
        "document_id": "support",
        "role": "supporting_document",
        "path": "support.txt",
        "sha256": "0" * 64,
        "byte_count": 1,
    }
    case_value["documents"] = tuple(
        sorted(
            [*case_value["documents"], support_value],
            key=lambda document: document["document_id"],
        )
    )

    with pytest.raises(ValidationError, match="require side, kind"):
        ReleaseCase.model_validate(case_value)

    support_value.update(
        {
            "supporting_side": "opening",
            "supporting_kind": "declaration",
            "target_motion_document_id": "missing-motion",
        }
    )
    with pytest.raises(ValidationError, match="must name a motion document"):
        ReleaseCase.model_validate(case_value)

    support_value["target_motion_document_id"] = complaint_id
    with pytest.raises(ValidationError, match="must name a motion document"):
        ReleaseCase.model_validate(case_value)


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
            lambda value: value["cases"][0]["documents"][1].update(
                path=value["cases"][0]["documents"][0]["path"]
            ),
            "artifact path is reused",
        ),
        (
            lambda value: value["prediction_units"][0].update(
                prompt_path=value["prediction_units"][0]["packet_path"]
            ),
            "artifact path is reused",
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

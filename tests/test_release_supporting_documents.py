from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.release import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    LabelsDraft,
    PredictionUnitDraft,
    ReleaseCase,
    ReleaseDocument,
    ScoringPolicy,
    UnitOutcome,
    enumerate_forecast_worker_inputs,
    issue_release,
    issue_synthetic_release,
    load_forecast_execution,
)
from pydantic import ValidationError


def test_supporting_document_metadata_is_required() -> None:
    for missing in ("supporting_side", "supporting_kind", "target_motion_document_id"):
        metadata = {
            "supporting_side": "opening",
            "supporting_kind": "declaration",
            "target_motion_document_id": "motion",
        }
        metadata.pop(missing)

        with pytest.raises(ValidationError, match="require side, kind"):
            DocumentDraft(
                document_id="support",
                role="supporting_document",
                path="documents/support.txt",
                **metadata,
            )


def test_supporting_metadata_is_rejected_for_other_roles() -> None:
    with pytest.raises(ValidationError, match="only valid for supporting_document"):
        DocumentDraft(
            document_id="complaint",
            role="complaint",
            path="documents/complaint.txt",
            supporting_side="opening",
        )

    with pytest.raises(ValidationError, match="only valid for supporting_document"):
        ReleaseDocument(
            document_id="complaint",
            role="complaint",
            path="documents/complaint.txt",
            sha256="0" * 64,
            byte_count=1,
            supporting_kind="exhibit",
        )


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

    cross_case_motion_id = next(
        document["document_id"]
        for document in forecast_value["cases"][1]["documents"]
        if document["role"] == "motion_to_dismiss_memorandum"
    )
    support_value["target_motion_document_id"] = cross_case_motion_id
    with pytest.raises(ValidationError, match="must name a motion document"):
        ReleaseCase.model_validate(case_value)

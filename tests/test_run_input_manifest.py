from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from legalforecast.publication.run_input_manifest import (
    RunInputManifestError,
    freeze_run_input_labels,
    main,
)
from legalforecast.release import (
    BenchmarkRunManifest,
    DocumentRole,
    ManifestLockedError,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    RunManifestError,
    serialize_run_manifest,
    validate_run_manifest_structure,
)


def test_freeze_run_input_labels_records_hash_in_produced_manifest(
    tmp_path: Path,
) -> None:
    source_manifest = tmp_path / "cycle.run-inputs.json"
    frozen_manifest = tmp_path / "cycle.run-inputs.frozen.json"
    labels_path = tmp_path / "cycle.labels.jsonl"
    source_record = {
        "schema_version": "legalforecast-private-store-export-v1",
        "cycle_id": "cycle-fixture",
        "generated_at": "2026-05-18T00:00:00Z",
        "model_packets": [
            {
                "case_id": "case-1",
                "packet_object_key": "model-packets/cycle-fixture/case-1/full.json",
            }
        ],
    }
    source_manifest.write_text(
        json.dumps(source_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")

    result = freeze_run_input_labels(
        source_manifest,
        labels_path=labels_path,
        output_path=frozen_manifest,
    )

    expected_sha256 = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    produced = json.loads(frozen_manifest.read_text(encoding="utf-8"))
    original = json.loads(source_manifest.read_text(encoding="utf-8"))
    assert result.labels_sha256 == expected_sha256
    assert result.output_path == frozen_manifest
    assert produced == {**source_record, "labels_sha256": expected_sha256}
    assert "labels_sha256" not in original


def test_freeze_run_input_labels_is_idempotent_for_same_labels(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    labels_sha256 = hashlib.sha256(labels_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": labels_sha256,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = freeze_run_input_labels(
        manifest_path,
        labels_path=labels_path,
        output_path=manifest_path,
    )

    assert result.labels_sha256 == labels_sha256
    assert (
        json.loads(manifest_path.read_text(encoding="utf-8"))["labels_sha256"]
        == labels_sha256
    )


def test_freeze_run_input_labels_refuses_to_replace_existing_commitment(
    tmp_path: Path,
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": "0" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="refusing to replace"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=tmp_path / "frozen.json",
        )


def test_freeze_run_input_labels_rejects_invalid_existing_commitment(
    tmp_path: Path,
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-fixture",
                "model_packets": [],
                "labels_sha256": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="lowercase SHA-256"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=tmp_path / "frozen.json",
        )


def test_freeze_run_input_labels_refuses_to_overwrite_labels(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps({"cycle_id": "cycle-fixture", "model_packets": []}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RunInputManifestError, match="must not overwrite"):
        freeze_run_input_labels(
            manifest_path,
            labels_path=labels_path,
            output_path=labels_path,
        )

    assert labels_path.read_text(encoding="utf-8") == '{"unit_id":"unit-1"}\n'


def test_freeze_labels_cli_writes_manifest_and_reports_hash(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    labels_path = tmp_path / "labels.jsonl"
    labels_path.write_text('{"unit_id":"unit-1"}\n', encoding="utf-8")
    manifest_path = tmp_path / "run-inputs.json"
    manifest_path.write_text(
        json.dumps({"cycle_id": "cycle-fixture", "model_packets": []}) + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "run-inputs.frozen.json"

    status = main(
        (
            "freeze-labels",
            "--manifest",
            str(manifest_path),
            "--labels",
            str(labels_path),
            "--output",
            str(output_path),
        )
    )

    stdout = json.loads(capsys.readouterr().out)
    produced = json.loads(output_path.read_text(encoding="utf-8"))
    assert status == 0
    assert stdout == {
        "labels_sha256": produced["labels_sha256"],
        "output": str(output_path),
    }


RUN_ID = UUID("12345678-1234-5678-1234-567812345678")
COMMIT = "a" * 40


def _locator(role: str, suffix: str = "1") -> RoleObjectLocator:
    return RoleObjectLocator(
        role=DocumentRole(role),
        locator=OpaqueObjectLocator(
            provider_id="corpus-store",
            object_locator=f"cases/case-1/{role}",
            version_id=f"provider-version-{suffix}",
        ),
    )


def _case(
    case_id: str = "case-1",
    *,
    opposition_status: OppositionStatus = OppositionStatus.DOCKETED,
    roles: tuple[str, ...] = ("decision", "motion", "complaint", "opposition", "reply"),
    qc_status: QCStatus = QCStatus.ACCEPTED,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "provider_id": "courtlistener",
        "qc_status": qc_status,
        "role_locators": tuple(_locator(role) for role in roles),
        "opposition_status": opposition_status,
    }


def _manifest(*cases: dict[str, Any], **changes: Any) -> BenchmarkRunManifest:
    values: dict[str, Any] = {
        "run_id": RUN_ID,
        "selected_cases": tuple(cases or (_case(),)),
        "policy_version": "federal-mtd-v1",
        "code_revision": COMMIT,
        "created_at": datetime(2026, 8, 30, 12, tzinfo=UTC),
        "locked_at": datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    }
    values.update(changes)
    return BenchmarkRunManifest(**values)


def _case_with_roles(*roles: str, **changes: Any) -> dict[str, Any]:
    value = _case(roles=roles)
    value.update(changes)
    return value


def _selected_case(*roles: str, **changes: Any) -> dict[str, Any]:
    return {"selected_cases": (_case_with_roles(*roles, **changes),)}


def _bad_locator_case(value: str) -> dict[str, Any]:
    case = _case()
    case["role_locators"] = (
        {
            "role": "decision",
            "locator": {
                "provider_id": "corpus-store",
                "object_locator": value,
                "version_id": "v1",
            },
        },
        *_case()["role_locators"][1:],
    )
    return case


def _case_with_extra(key: str) -> dict[str, Any]:
    case = _case()
    case[key] = False
    return case


def _conflicting_case() -> dict[str, Any]:
    case = _case()
    case["role_locators"] = (
        {
            "role": "decision",
            "locator": {
                "provider_id": "corpus-store",
                "object_locator": "cases/case-1/decision",
                "version_id": "v1",
            },
            "object_locator": "cases/case-1/conflicting",
        },
        *_case()["role_locators"][1:],
    )
    return case


def test_valid_locked_manifest_requires_roles_but_keeps_locators_opaque() -> None:
    manifest = _manifest()

    assert manifest.run_id == RUN_ID
    assert manifest.selected_cases[0].role_locators[-1].role.value == "reply"
    payload = serialize_run_manifest(manifest)
    assert b"sha256" not in payload.lower()
    assert b"private" not in payload.lower()
    assert validate_run_manifest_structure(payload) == manifest
    assert (
        _manifest(_case(roles=("decision", "motion", "complaint", "opposition")))
        .selected_cases[0]
        .role_locators[-1]
        .role.value
        == "opposition"
    )


def test_confirmed_unopposed_case_does_not_need_an_opposition() -> None:
    manifest = _manifest(
        _case_with_roles(
            "decision",
            "motion",
            "complaint",
            opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
        )
    )
    assert (
        manifest.selected_cases[0].opposition_status
        is OppositionStatus.CONFIRMED_UNOPPOSED
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"selected_cases": (_case(), _case("case-1"))}, "unique stable IDs"),
        (_selected_case("decision", "motion", "complaint"), "docketed opposition"),
        (_selected_case("decision", "motion", "opposition"), "complaint locator"),
        (
            _selected_case("decision", "complaint", "opposition"),
            "motion or opening memorandum",
        ),
        (_selected_case("motion", "complaint", "opposition"), "decision locator"),
        (
            _selected_case(
                "decision",
                "motion_to_dismiss_notice",
                "complaint",
                opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
            ),
            "motion or opening memorandum",
        ),
        (
            {"selected_cases": (_case(qc_status=QCStatus.REJECTED),)},
            "completeness-accepted",
        ),
        (
            {"selected_cases": (_case(qc_status=QCStatus.NEEDS_REVIEW),)},
            "completeness-accepted",
        ),
        ({"locked_at": None}, "valid datetime"),
        (
            {
                "created_at": datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
                "locked_at": datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
            },
            "at or after",
        ),
        ({"created_at": datetime(2026, 8, 30, 12, 0)}, "timezone-aware"),
        ({"run_id": "not-a-uuid"}, "UUID"),
        ({"code_revision": "main"}, "full lowercase 40-character commit SHA"),
        ({"code_revision": "a" * 39}, "full lowercase 40-character commit SHA"),
    ],
)
def test_invalid_locked_manifest_is_rejected(
    changes: dict[str, Any], message: str
) -> None:
    with pytest.raises((RunManifestError, ValueError), match=message):
        _manifest(**changes)


@pytest.mark.parametrize(
    "value",
    [
        "/work/private/decision.pdf",
        "//server/private/decision.pdf",
        "\\\\server\\private\\decision.pdf",
        "C:/private/decision.pdf",
        "cases/../private/decision.pdf",
        "cases/./private/decision.pdf",
        "cases/%2e%2e/private/decision.pdf",
        "%2Fwork%2Fprivate%2Fdecision.pdf",
        "https://user:password@example.test/document.pdf",
        "https://example.test/document.pdf?X-Amz-Signature=secret",
        "s3://bucket/private/decision.pdf",
        "file:///work/private/decision.pdf",
        "opaque+scheme:private-document",
        "cases/private/decision.pdf#secret",
        "cases/private/decision.pdf?token=secret",
        "cases/private/decision\x00.pdf",
    ],
)
def test_opaque_locator_rejects_private_paths_urls_and_encoded_forms(
    value: str,
) -> None:
    with pytest.raises((RunManifestError, ValueError), match="opaque locators"):
        _manifest(_bad_locator_case(value))


def test_public_shape_has_no_label_or_policy_bypass_and_rejects_aliases() -> None:
    with pytest.raises((RunManifestError, ValueError), match="extra_forbidden"):
        _manifest(labels=b"outcome=grant")
    with pytest.raises((RunManifestError, ValueError), match="extra_forbidden"):
        _manifest(manifest_id=str(RUN_ID))
    for key in ("complaint_required", "policy_requires_complaint"):
        with pytest.raises((RunManifestError, ValueError), match="extra_forbidden"):
            _manifest(_case_with_extra(key))
    with pytest.raises((RunManifestError, ValueError), match="extra_forbidden"):
        _manifest(_conflicting_case())


def test_not_docketed_is_not_a_runnable_opposition_state() -> None:
    unresolved = _case()
    unresolved["opposition_status"] = "not_docketed"
    with pytest.raises((RunManifestError, ValueError), match="opposition_status"):
        _manifest(unresolved)


def test_manifest_is_locked_and_cannot_be_replaced() -> None:
    manifest = _manifest()
    with pytest.raises(ManifestLockedError, match="locked"):
        manifest.model_copy(
            update={"run_id": UUID("87654321-4321-8765-4321-876543218765")}
        )
    payload = json.loads(serialize_run_manifest(manifest))
    assert payload["run_id"] == str(RUN_ID)
    assert payload["code_revision"] == COMMIT

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.immutable_io import ImmutableIOError
from legalforecast.release import (
    BenchmarkRunManifest,
    DocumentRole,
    ManifestLockedError,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    RunManifestError,
    load_run_manifest,
    serialize_run_manifest,
    validate_run_manifest_structure,
    write_run_manifest,
)


def _locator(role: str, suffix: str = "1") -> RoleObjectLocator:
    return RoleObjectLocator(
        role=role,
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
    include_opposition: bool = True,
    include_reply: bool = True,
    complaint_required: bool = True,
    qc_status: QCStatus = QCStatus.ACCEPTED,
) -> dict[str, Any]:
    roles: list[RoleObjectLocator] = [
        _locator("decision"),
        _locator("motion"),
    ]
    if complaint_required:
        roles.append(_locator("complaint"))
    if include_opposition:
        roles.append(_locator("opposition"))
    if include_reply:
        roles.append(_locator("reply"))
    return {
        "case_id": case_id,
        "provider_id": "courtlistener",
        "qc_status": qc_status,
        "role_locators": tuple(roles),
        "complaint_required": complaint_required,
        "opposition_status": opposition_status,
    }


def _manifest(*cases: dict[str, Any], **changes: Any) -> BenchmarkRunManifest:
    values: dict[str, Any] = {
        "run_id": "run-1",
        "selected_cases": tuple(cases or (_case(),)),
        "policy_version": "federal-mtd-v1",
        "code_revision": "bench-revision-1",
        "created_at": datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
        "locked_at": datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    }
    values.update(changes)
    return BenchmarkRunManifest(**values)


def test_valid_locked_manifest_requires_roles_but_keeps_locators_opaque() -> None:
    manifest = _manifest()

    assert manifest.is_locked
    assert manifest.selected_cases[0].role_locators[-1].role is DocumentRole.REPLY
    payload = serialize_run_manifest(manifest)
    assert b"sha256" not in payload.lower()
    assert b"private" not in payload.lower()


def test_confirmed_unopposed_case_does_not_need_an_opposition() -> None:
    manifest = _manifest(
        _case(
            opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
            include_opposition=False,
        )
    )

    assert (
        manifest.selected_cases[0].opposition_status
        is OppositionStatus.CONFIRMED_UNOPPOSED
    )


def test_reply_is_optional() -> None:
    manifest = _manifest(_case(include_reply=False))

    assert all(
        item.role is not DocumentRole.REPLY
        for item in manifest.selected_cases[0].role_locators
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"selected_cases": (_case(), _case("case-1"))}, "unique stable IDs"),
        (
            {
                "selected_cases": (
                    _case(
                        opposition_status=OppositionStatus.DOCKETED,
                        include_opposition=False,
                    ),
                )
            },
            "docketed opposition",
        ),
        (
            {
                "selected_cases": (
                    {
                        **_case(),
                        "role_locators": (
                            _locator("decision"),
                            _locator("motion"),
                            _locator("opposition"),
                        ),
                    },
                )
            },
            "complaint locator",
        ),
        (
            {
                "selected_cases": (
                    {
                        **_case(),
                        "role_locators": (_locator("decision"), _locator("complaint")),
                    },
                )
            },
            "motion or opening memorandum",
        ),
        (
            {
                "selected_cases": (
                    {
                        **_case(),
                        "role_locators": (_locator("motion"), _locator("complaint")),
                    },
                )
            },
            "decision locator",
        ),
        (
            {"selected_cases": (_case(qc_status=QCStatus.REJECTED),)},
            "completeness-accepted",
        ),
        ({"locked_at": None}, "locked before execution"),
        (
            {
                "created_at": datetime(2026, 8, 30, 12, 2, tzinfo=UTC),
                "locked_at": datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
            },
            "at or after",
        ),
        (
            {
                "created_at": datetime(2026, 8, 30, 12, 0),
            },
            "timezone-aware",
        ),
    ],
)
def test_invalid_locked_manifest_is_rejected(
    changes: dict[str, Any], message: str
) -> None:
    with pytest.raises((RunManifestError, ValueError), match=message):
        _manifest(**changes)


def test_private_paths_and_label_bytes_are_not_public_contract_fields() -> None:
    private = _case()
    private["role_locators"] = (
        {
            "role": "decision",
            "locator": {
                "provider_id": "corpus-store",
                "object_locator": "/work/private/decision.pdf",
                "version_id": "v1",
            },
        },
        *_case()["role_locators"][1:],
    )
    with pytest.raises(
        (RunManifestError, ValueError), match="private filesystem paths"
    ):
        _manifest(private)

    with pytest.raises(
        (RunManifestError, ValueError), match=r"extra_forbidden|Extra inputs"
    ):
        _manifest(labels=b"outcome=grant")


def test_locked_manifest_cannot_be_replaced_and_file_load_is_canonical(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    with pytest.raises(ManifestLockedError, match="locked"):
        manifest.model_copy(update={"run_id": "different"})

    output = tmp_path / "run-manifest.json"
    write_run_manifest(manifest, output)
    assert load_run_manifest(output) == manifest
    assert validate_run_manifest_structure(output.read_bytes()) == manifest
    with pytest.raises(ImmutableIOError):
        write_run_manifest(manifest, output)

    noncanonical = tmp_path / "noncanonical.json"
    noncanonical.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RunManifestError, match="canonical"):
        load_run_manifest(noncanonical)

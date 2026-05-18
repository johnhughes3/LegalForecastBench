from __future__ import annotations

import json

import pytest
from legalforecast.ingestion import (
    AcquisitionPacketRole,
    SetupRunnerDocumentLabel,
    contract_for_setup_runner_label,
    normalize_setup_runner_label,
    setup_runner_label_contract_records,
)


@pytest.mark.parametrize(
    ("label", "role", "model_visible", "packet_section"),
    [
        (
            "core_mtd",
            AcquisitionPacketRole.MODEL_VISIBLE_CORE,
            True,
            "filings",
        ),
        (
            "core_exhibit",
            AcquisitionPacketRole.MODEL_VISIBLE_SUPPORTING,
            True,
            "exhibits",
        ),
        (
            "other_substantive",
            AcquisitionPacketRole.AUDIT_ONLY_SUBSTANTIVE,
            False,
            None,
        ),
        (
            "procedural_minor",
            AcquisitionPacketRole.AUDIT_ONLY_PROCEDURAL,
            False,
            None,
        ),
    ],
)
def test_setup_runner_labels_map_to_deterministic_acquisition_roles(
    label: str,
    role: AcquisitionPacketRole,
    model_visible: bool,
    packet_section: str | None,
) -> None:
    contract = contract_for_setup_runner_label(label)

    assert contract.label.value == label
    assert contract.acquisition_role is role
    assert contract.model_visible_by_default is model_visible
    assert contract.packet_section == packet_section
    assert contract.audit_bundle_required is True


def test_label_normalization_accepts_enum_and_rejects_unknown_values() -> None:
    assert (
        normalize_setup_runner_label(SetupRunnerDocumentLabel.CORE_MTD)
        is SetupRunnerDocumentLabel.CORE_MTD
    )
    assert (
        normalize_setup_runner_label(" CORE_MTD ") is SetupRunnerDocumentLabel.CORE_MTD
    )

    with pytest.raises(ValueError, match="unknown setup-runner document label"):
        normalize_setup_runner_label("nice_to_have")


def test_setup_runner_contract_records_are_stable_jsonl_fixtures() -> None:
    records = setup_runner_label_contract_records()

    assert [record["label"] for record in records] == [
        "core_mtd",
        "core_exhibit",
        "other_substantive",
        "procedural_minor",
    ]
    assert {record["acquisition_role"] for record in records} == {
        "model_visible_core",
        "model_visible_supporting",
        "audit_only_substantive",
        "audit_only_procedural",
    }
    assert all(record["audit_bundle_required"] is True for record in records)
    for record in records:
        json.dumps(record, sort_keys=True)

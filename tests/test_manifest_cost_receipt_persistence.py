from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.evals.corpus_manifest.cost_projector import (
    issue_manifest_cost_projection,
    verify_manifest_cost_projection_receipt,
)
from legalforecast.evals.model_registry import load_model_registry_bytes
from tests.test_manifest_cost_projector import SUCCESSOR_REGISTRY, _authenticated_chain


def test_persisted_canonical_receipt_verifies_with_long_context_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, _packet_paths = _authenticated_chain(
        tmp_path, monkeypatch, packet_input_tokens=272_001
    )

    issued = issue_manifest_cost_projection(request)
    persisted = cast(dict[str, Any], json.loads(request.output.read_bytes()))
    assert issued["long_context_surcharge_packet_count"] == 200
    assert persisted["long_context_surcharge_packet_count"] == 200

    registry_entry = next(
        entry
        for entry in load_model_registry_bytes(SUCCESSOR_REGISTRY.read_bytes()).entries
        if entry.registry_key == "openai:gpt-5.6-terra"
    )
    commitments = cast(dict[str, Any], persisted["input_commitments"])
    expected_common = {
        expected_name: commitments[commitment_name]["sha256"]
        for expected_name, commitment_name in (
            ("freeze_bundle_sha256", "freeze_bundle"),
            ("manifest_sha256", "owner_manifest"),
            ("run_input_manifest_sha256", "run_input_manifest"),
            ("model_registry_sha256", "model_registry"),
        )
    }

    for receipt in (issued, persisted):
        assert (
            verify_manifest_cost_projection_receipt(
                receipt,
                expected_cycle_id="cycle-1",
                expected_model_key="openai:gpt-5.6-terra",
                expected_common_frozen_inputs=expected_common,
                expected_registry_entry=registry_entry.to_record(),
            )
            == receipt["receipt_sha256"]
        )

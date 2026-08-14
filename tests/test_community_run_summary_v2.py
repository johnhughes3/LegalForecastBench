"""v2 community run summaries bind canonical artifact hashes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.community import (
    COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2,
    BoundIdentityKeys,
    CanonicalArtifactBindings,
    CommunityRunSummary,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError

FIXTURE = (
    Path(__file__).parent
    / "fixtures/multiharness-artifact-characterization/community-run-summary.v2.json"
)
DIGEST = "sha256:" + "4" * 64


def test_v2_characterization_fixture_round_trips() -> None:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    summary = CommunityRunSummary.from_record(record)
    assert summary.schema_version == COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2
    assert summary.to_record() == record
    assert summary.artifact_bindings is not None
    assert summary.artifact_bindings.execution_receipt_sha256 is not None
    assert summary.identity_bindings is not None


def test_v2_summary_requires_artifact_bindings() -> None:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del record["artifact_bindings"]
    with pytest.raises(MultiHarnessValidationError, match="artifact_bindings"):
        CommunityRunSummary.from_record(record)


def test_identity_keys_require_an_execution_receipt_binding() -> None:
    with pytest.raises(MultiHarnessValidationError, match="execution-receipt"):
        CommunityRunSummary(
            run_id="fixture-run",
            run_manifest_sha256="sha256:" + "1" * 64,
            selection_sha256="sha256:" + "2" * 64,
            selection_label="scoped:fixture-selection",
            run_config_sha256="sha256:" + "3" * 64,
            row_count=1,
            result_status_counts={"succeeded": 1},
            families=("harvey_lab",),
            scoring_modes=("lab_native",),
            adapter_ids=("fixture-cli",),
            model_keys=("fixture-model",),
            schema_version=COMMUNITY_RUN_SUMMARY_SCHEMA_VERSION_V2,
            artifact_bindings=CanonicalArtifactBindings(
                score_artifact_sha256=DIGEST,
            ),
            identity_bindings=BoundIdentityKeys(
                task_identity_key="sha256:" + "c" * 64,
                solver_identity_key="sha256:" + "b" * 64,
                run_identity_key="sha256:" + "a" * 64,
            ),
            coverage_kind="scoped",
            claim_kind="scoped",
        )


def test_v1_summaries_cannot_carry_v2_bindings() -> None:
    with pytest.raises(MultiHarnessValidationError, match="v1"):
        CommunityRunSummary(
            run_id="fixture-run",
            run_manifest_sha256="sha256:" + "1" * 64,
            selection_sha256="sha256:" + "2" * 64,
            selection_label="fixture selection",
            run_config_sha256="sha256:" + "3" * 64,
            row_count=1,
            result_status_counts={"succeeded": 1},
            families=("harvey_lab",),
            scoring_modes=("lab_native",),
            adapter_ids=("fixture-cli",),
            model_keys=("fixture-model",),
            artifact_bindings=CanonicalArtifactBindings(
                execution_receipt_sha256=DIGEST,
            ),
        )

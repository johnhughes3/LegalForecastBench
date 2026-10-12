"""Protected scoring inputs and exact completed-run output validation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from legalforecast.runner.completion_artifacts import read_record, unpack_artifact
from legalforecast.runner.recovery import RecoveryPlan
from legalforecast.runner.recovery_client import RecoveryError, recovery_object


def scoring_inputs(
    plan: RecoveryPlan, cycle_id: str, labels_uri: str, publish: bool
) -> dict[str, str]:
    frozen = plan.frozen_identity
    return {
        "release_sha": frozen.release_sha,
        "cycle_id": cycle_id,
        "forecast_run_id": str(plan.source_run_id),
        "forecast_run_attempt": str(plan.source_run_attempt),
        "manifest_uri": frozen.manifest_uri,
        "forecast_release_uri": frozen.forecast_release_uri,
        "artifact_root_uri": frozen.artifact_root_uri,
        "model_registry_uri": frozen.model_registry_uri,
        "labels_release_uri": labels_uri,
        "model_key": frozen.model_key,
        "publish": "true" if publish else "false",
        "artifact_retention_days": "90",
    }


def save_scored_artifact(
    payload: bytes, output: Path, plan: RecoveryPlan
) -> tuple[int, int]:
    with TemporaryDirectory() as directory:
        root = Path(directory) / "artifact"
        unpack_artifact(payload, root)
        export = read_record(root / "lfb-site-export.json")
        source = recovery_object(export.get("source"), "site export source")
        if (
            source.get("run_identity_sha256")
            != plan.frozen_identity.run_identity_sha256
            or source.get("model_registry_sha256")
            != plan.frozen_identity.model_registry_sha256
        ):
            raise RecoveryError("scored artifact differs from frozen forecast identity")
        results = export.get("results")
        if not isinstance(results, list) or len(cast(list[object], results)) != 1:
            raise RecoveryError(
                "scored artifact must contain exactly the selected model"
            )
        model = recovery_object(cast(list[object], results)[0], "scored model")
        cases, units = model.get("case_count"), model.get("unit_count")
        if (
            model.get("model_id") != plan.frozen_identity.model_key
            or type(cases) is not int
            or type(units) is not int
            or units <= 0
            or cases
            != plan.census.declared_state_count // plan.frozen_identity.repeat_count
        ):
            raise RecoveryError("score is not the complete original case census")
        runtime = read_record(root / "lfb-report/scoring-runtime.json")
        if (
            str(runtime.get("forecast_run_id")) != str(plan.source_run_id)
            or str(runtime.get("forecast_run_attempt")) != str(plan.source_run_attempt)
            or runtime.get("forecast_revision") != plan.frozen_identity.release_sha
        ):
            raise RecoveryError(
                "score provenance differs from exact completed forecast"
            )
        # Shared extraction refuses an output created by another writer.
        unpack_artifact(payload, output)
        return cases, units

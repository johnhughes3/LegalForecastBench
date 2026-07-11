from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.protocol.manifest import hash_payload
from legalforecast.publication.dispatch_provenance import (
    DispatchProvenanceError,
    build_dispatch_provenance,
    load_dispatch_provenance,
)


def test_amendment_provenance_maps_models_to_introducing_freeze(
    tmp_path: Path,
) -> None:
    root_bundle, root_sha = _write_bundle(
        tmp_path,
        name="root",
        registry_records=[_registry_entry("model-a")],
    )
    amendment_bundle, amendment_sha = _write_bundle(
        tmp_path,
        name="amendment",
        registry_records=[_registry_entry("model-a"), _registry_entry("model-b")],
        amends_bundle_sha256=root_sha,
    )

    record = build_dispatch_provenance(
        current_freeze_bundle_path=amendment_bundle,
        candidate_freeze_bundle_paths=(root_bundle, amendment_bundle),
        root_path=tmp_path,
        current_model_registry_path=tmp_path / "amendment-registry.json",
        prior_dispatches=(
            {
                "workflow_run_id": "1001",
                "workflow_run_attempt": 1,
                "freeze_bundle_sha256": root_sha,
                "model_keys": ["fixture:model-a"],
            },
        ),
        current_workflow_run_id="1002",
        current_workflow_run_attempt=1,
        requested_model_keys=("fixture:model-b",),
        supersedes_report_uri="s3://results/reports/cycle-1/multi-ablation/",
    )

    assert record["freeze_chain"] == [
        {
            "bundle_sha256": root_sha,
            "amends_bundle_sha256": None,
            "cycle_id": "cycle-1",
            "freeze_timestamp": "2026-07-10T12:00:00Z",
            "introduced_model_keys": ["fixture:model-a"],
        },
        {
            "bundle_sha256": amendment_sha,
            "amends_bundle_sha256": root_sha,
            "cycle_id": "cycle-1",
            "freeze_timestamp": "2026-07-11T12:00:00Z",
            "introduced_model_keys": ["fixture:model-b"],
        },
    ]
    assert record["model_entry_freezes"] == [
        {"model_key": "fixture:model-a", "freeze_bundle_sha256": root_sha},
        {"model_key": "fixture:model-b", "freeze_bundle_sha256": amendment_sha},
    ]
    assert record["dispatches"][-1] == {
        "workflow_run_id": "1002",
        "workflow_run_attempt": 1,
        "freeze_bundle_sha256": amendment_sha,
        "model_keys": ["fixture:model-b"],
    }
    assert record["publication"] == {
        "mode": "additive_supersession",
        "supersedes_report_uri": ("s3://results/reports/cycle-1/multi-ablation/"),
    }

    provenance_path = tmp_path / "dispatch-provenance.json"
    provenance_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert (
        load_dispatch_provenance(
            provenance_path,
            expected_cycle_id="cycle-1",
            expected_model_keys=("fixture:model-a", "fixture:model-b"),
        )
        == record
    )


def test_amendment_dispatch_rejects_existing_model_key(tmp_path: Path) -> None:
    root_bundle, root_sha = _write_bundle(
        tmp_path,
        name="root",
        registry_records=[_registry_entry("model-a")],
    )
    amendment_bundle, _ = _write_bundle(
        tmp_path,
        name="amendment",
        registry_records=[_registry_entry("model-a"), _registry_entry("model-b")],
        amends_bundle_sha256=root_sha,
    )

    with pytest.raises(
        DispatchProvenanceError,
        match="requested model keys must exactly equal models introduced",
    ):
        build_dispatch_provenance(
            current_freeze_bundle_path=amendment_bundle,
            candidate_freeze_bundle_paths=(root_bundle, amendment_bundle),
            root_path=tmp_path,
            current_model_registry_path=tmp_path / "amendment-registry.json",
            prior_dispatches=(
                {
                    "workflow_run_id": "1001",
                    "workflow_run_attempt": 1,
                    "freeze_bundle_sha256": root_sha,
                    "model_keys": ["fixture:model-a"],
                },
            ),
            current_workflow_run_id="1002",
            current_workflow_run_attempt=1,
            requested_model_keys=("fixture:model-a", "fixture:model-b"),
        )


def test_provenance_requires_dispatch_coverage_for_every_model(tmp_path: Path) -> None:
    bundle_path, _ = _write_bundle(
        tmp_path,
        name="root",
        registry_records=[_registry_entry("model-a")],
    )

    with pytest.raises(
        DispatchProvenanceError,
        match="requested model keys must exactly equal models introduced",
    ):
        build_dispatch_provenance(
            current_freeze_bundle_path=bundle_path,
            candidate_freeze_bundle_paths=(bundle_path,),
            root_path=tmp_path,
            current_model_registry_path=tmp_path / "root-registry.json",
            prior_dispatches=(),
            current_workflow_run_id="1001",
            current_workflow_run_attempt=1,
            requested_model_keys=(),
        )


def _write_bundle(
    tmp_path: Path,
    *,
    name: str,
    registry_records: list[dict[str, object]],
    amends_bundle_sha256: str | None = None,
) -> tuple[Path, str]:
    registry_path = tmp_path / f"{name}-registry.json"
    registry_bytes = (
        json.dumps(registry_records, indent=2, sort_keys=True) + "\n"
    ).encode()
    registry_path.write_bytes(registry_bytes)
    record: dict[str, object] = {
        "cycle_id": "cycle-1",
        "freeze_timestamp": (
            "2026-07-10T12:00:00Z"
            if amends_bundle_sha256 is None
            else "2026-07-11T12:00:00Z"
        ),
        "model_registry": {
            "path": registry_path.name,
            "sha256": hashlib.sha256(registry_bytes).hexdigest(),
        },
    }
    if amends_bundle_sha256 is not None:
        record["amends_bundle_sha256"] = amends_bundle_sha256
    bundle_sha = hash_payload(record)
    record["hash_bundle_sha256"] = bundle_sha
    bundle_path = tmp_path / f"{name}.freeze.json"
    bundle_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return bundle_path, bundle_sha


def _registry_entry(model_id: str) -> dict[str, object]:
    return {"provider": "fixture", "model_id": model_id}

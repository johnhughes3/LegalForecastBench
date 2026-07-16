from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.protocol.manifest import hash_payload
from legalforecast.protocol.policy_artifacts import generate_execution_policy
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


def test_declared_shard_dispatch_records_frozen_pair_and_remaining_schedule(
    tmp_path: Path,
) -> None:
    bundle_path, bundle_sha = _write_sharded_bundle(tmp_path)

    record = build_dispatch_provenance(
        current_freeze_bundle_path=bundle_path,
        candidate_freeze_bundle_paths=(bundle_path,),
        root_path=tmp_path,
        current_model_registry_path=tmp_path / "root-registry.json",
        prior_dispatches=(),
        current_workflow_run_id="1001",
        current_workflow_run_attempt=1,
        requested_model_keys=("fixture:model-a",),
        requested_ablations=("full_packet",),
        shard_only=True,
    )

    assert record["dispatch_mode"] == "shard_only"
    assert record["dispatches"] == [
        {
            "workflow_run_id": "1001",
            "workflow_run_attempt": 1,
            "freeze_bundle_sha256": bundle_sha,
            "model_keys": ["fixture:model-a"],
            "ablations": ["full_packet"],
        }
    ]
    assert record["requested_shard"] == {
        "model_key": "fixture:model-a",
        "ablation": "full_packet",
    }
    assert record["remaining_shards"] == [
        {"model_key": f"fixture:model-{model}", "ablation": ablation}
        for model in ("a", "b", "c", "d")
        for ablation in ("full_packet", "metadata_only")
        if (model, ablation) != ("a", "full_packet")
    ]
    provenance_path = tmp_path / "shard-dispatch-provenance.json"
    provenance_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert load_dispatch_provenance(
        provenance_path,
        expected_cycle_id="cycle-1",
        expected_model_keys=tuple(
            f"fixture:model-{model}" for model in ("a", "b", "c", "d")
        ),
    ) == record


@pytest.mark.parametrize(
    ("model_keys", "ablations", "message"),
    (
        (("fixture:model-a",), ("judge_removed",), "not declared"),
        (
            ("fixture:model-a", "fixture:model-b"),
            ("full_packet", "metadata_only"),
            "exactly one",
        ),
    ),
)
def test_shard_dispatch_rejects_undeclared_or_full_set_request(
    tmp_path: Path,
    model_keys: tuple[str, ...],
    ablations: tuple[str, ...],
    message: str,
) -> None:
    bundle_path, _ = _write_sharded_bundle(tmp_path)

    with pytest.raises(DispatchProvenanceError, match=message):
        build_dispatch_provenance(
            current_freeze_bundle_path=bundle_path,
            candidate_freeze_bundle_paths=(bundle_path,),
            root_path=tmp_path,
            current_model_registry_path=tmp_path / "root-registry.json",
            prior_dispatches=(),
            current_workflow_run_id="1001",
            current_workflow_run_attempt=1,
            requested_model_keys=model_keys,
            requested_ablations=ablations,
            shard_only=True,
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


def _write_sharded_bundle(tmp_path: Path) -> tuple[Path, str]:
    registry_records = [_registry_entry(f"model-{model}") for model in "abcd"]
    registry_path = tmp_path / "root-registry.json"
    registry_bytes = (
        json.dumps(registry_records, indent=2, sort_keys=True) + "\n"
    ).encode()
    registry_path.write_bytes(registry_bytes)
    execution_policy = generate_execution_policy(
        {
            "cycle_id": "cycle-1",
            "cycle_series": "official",
            "allow_no_baselines": True,
            "labeling_policy_sha256": "a" * 64,
            "cohort_policy_sha256": "b" * 64,
            "cohort_observation_manifest_sha256": "c" * 64,
            "lifecycle": {
                "labeling_policy_published_at": "2026-07-12T20:00:00Z",
                "production_labeling_started_at": "2026-07-13T00:00:00Z",
                "cohort_policy_published_at": "2026-07-12T19:00:00Z",
                "batch_002_started_at": "2026-07-12T21:00:00Z",
            },
            "shard_schedule": {
                "shard_count": 8,
                "dispatch_unit": "model_key_ablation",
                "shards": [
                    {"model_key": f"fixture:model-{model}", "ablation": ablation}
                    for model in "abcd"
                    for ablation in ("full_packet", "metadata_only")
                ],
            },
            "concurrency_policy": {
                "mode": "shard_identity",
                "identity_fields": ["cycle_id", "model_key", "ablation"],
            },
            "receipt_policy": {
                "write_once_per_attempt": True,
                "identity_fields": ["workflow_run_id", "workflow_run_attempt"],
                "result_commitment_required": True,
            },
            "attempt_policy": {
                "reservation_ledger_sha256": "d" * 64,
                "max_billable_attempts": 2,
            },
            "repeat_policy": {"case_ids": ["case-1", "case-2"], "count": 2},
            "cadence_counts": {
                "clean_motion_count_source": "frozen_manifest",
                "prediction_unit_count_source": "frozen_units",
                "reject_operator_mismatch": True,
            },
        }
    )
    execution_path = tmp_path / "execution-policy.json"
    execution_bytes = (
        json.dumps(execution_policy, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    execution_path.write_bytes(execution_bytes)
    record: dict[str, object] = {
        "cycle_id": "cycle-1",
        "freeze_timestamp": "2026-07-10T12:00:00Z",
        "model_registry": {
            "path": registry_path.name,
            "sha256": hashlib.sha256(registry_bytes).hexdigest(),
        },
        "artifacts": [
            {
                "name": "execution_policy",
                "path": execution_path.name,
                "sha256": hashlib.sha256(execution_bytes).hexdigest(),
                "size_bytes": len(execution_bytes),
            }
        ],
    }
    bundle_sha = hash_payload(record)
    record["hash_bundle_sha256"] = bundle_sha
    bundle_path = tmp_path / "root.freeze.json"
    bundle_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return bundle_path, bundle_sha


def _registry_entry(model_id: str) -> dict[str, object]:
    return {"provider": "fixture", "model_id": model_id}

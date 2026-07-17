from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.protocol.manifest import hash_payload
from legalforecast.publication import shard_fan_in, shard_fan_in_publish
from legalforecast.publication.shard_receipt import build_shard_receipt, receipt_key


def test_single_receipt_per_declared_shard_auto_accepts() -> None:
    receipts = [_receipt("fixture:model-a", ablation) for ablation in _ABLATIONS]

    selection = shard_fan_in.select_accepted_receipts(
        receipts,
        declared_shards=_DECLARED_SHARDS,
        cycle_id="cycle-1",
        freeze_bundle_sha256="a" * 64,
        execution_policy_sha256="b" * 64,
        shard_schedule_sha256=_SCHEDULE_SHA256,
    )

    assert [(item["model_key"], item["ablation"]) for item in selection.receipts] == [
        ("fixture:model-a", "full_packet"),
        ("fixture:model-a", "metadata_only"),
    ]
    assert selection.accepted_attempt_map_sha256 is None


def test_missing_or_undeclared_shard_receipts_fail_closed() -> None:
    with pytest.raises(shard_fan_in.FanInError, match="missing shard receipts"):
        shard_fan_in.select_accepted_receipts(
            [_receipt("fixture:model-a", "full_packet")],
            declared_shards=_DECLARED_SHARDS,
            cycle_id="cycle-1",
            freeze_bundle_sha256="a" * 64,
            execution_policy_sha256="b" * 64,
            shard_schedule_sha256=_SCHEDULE_SHA256,
        )

    with pytest.raises(shard_fan_in.FanInError, match="undeclared shard receipts"):
        shard_fan_in.select_accepted_receipts(
            [
                *[_receipt("fixture:model-a", value) for value in _ABLATIONS],
                _receipt("fixture:model-b", "full_packet"),
            ],
            declared_shards=_DECLARED_SHARDS,
            cycle_id="cycle-1",
            freeze_bundle_sha256="a" * 64,
            execution_policy_sha256="b" * 64,
            shard_schedule_sha256=_SCHEDULE_SHA256,
        )


def test_multiple_receipts_require_hash_bound_accepted_attempt_map() -> None:
    receipts = [
        _receipt("fixture:model-a", "full_packet", run_id="1001", attempt=1),
        _receipt("fixture:model-a", "full_packet", run_id="1001", attempt=2),
        _receipt("fixture:model-a", "metadata_only"),
    ]

    with pytest.raises(
        shard_fan_in.FanInError,
        match=r"accepted-attempt map.*fixture:model-a.*full_packet",
    ):
        shard_fan_in.select_accepted_receipts(
            receipts,
            declared_shards=_DECLARED_SHARDS,
            cycle_id="cycle-1",
            freeze_bundle_sha256="a" * 64,
            execution_policy_sha256="b" * 64,
            shard_schedule_sha256=_SCHEDULE_SHA256,
        )

    accepted_map = _accepted_map(receipts[1])
    selection = shard_fan_in.select_accepted_receipts(
        receipts,
        declared_shards=_DECLARED_SHARDS,
        cycle_id="cycle-1",
        freeze_bundle_sha256="a" * 64,
        execution_policy_sha256="b" * 64,
        shard_schedule_sha256=_SCHEDULE_SHA256,
        accepted_attempt_map=accepted_map,
    )

    assert selection.receipts[0]["workflow_run_attempt"] == 2
    assert (
        selection.accepted_attempt_map_sha256
        == accepted_map["accepted_attempt_map_sha256"]
    )


def test_accepted_attempt_map_rejects_wrong_freeze_and_singleton_entries() -> None:
    receipts = [
        _receipt("fixture:model-a", "full_packet", attempt=1),
        _receipt("fixture:model-a", "full_packet", attempt=2),
        _receipt("fixture:model-a", "metadata_only"),
    ]
    wrong_freeze = _accepted_map(receipts[1], freeze_bundle_sha256="b" * 64)
    with pytest.raises(shard_fan_in.FanInError, match="freeze_bundle_sha256"):
        shard_fan_in.select_accepted_receipts(
            receipts,
            declared_shards=_DECLARED_SHARDS,
            cycle_id="cycle-1",
            freeze_bundle_sha256="a" * 64,
            execution_policy_sha256="b" * 64,
            shard_schedule_sha256=_SCHEDULE_SHA256,
            accepted_attempt_map=wrong_freeze,
        )

    extra = _accepted_map(receipts[1])
    selections = list(extra["selections"])
    selections.append(_selection(receipts[2]))
    extra["selections"] = selections
    extra["accepted_attempt_map_sha256"] = _map_hash(extra)
    with pytest.raises(shard_fan_in.FanInError, match="only ambiguous shards"):
        shard_fan_in.select_accepted_receipts(
            receipts,
            declared_shards=_DECLARED_SHARDS,
            cycle_id="cycle-1",
            freeze_bundle_sha256="a" * 64,
            execution_policy_sha256="b" * 64,
            shard_schedule_sha256=_SCHEDULE_SHA256,
            accepted_attempt_map=extra,
        )


def test_receipt_hashes_and_cells_are_reverified_against_frozen_inputs() -> None:
    run_manifest, receipt, repeat_policy = _strict_receipt()

    verified = shard_fan_in.validate_receipt_against_freeze(
        receipt,
        context=_context(),
        run_input_manifest=run_manifest,
        repeat_policy=repeat_policy,
        actual_receipt_key=str(receipt["receipt_key"]),
    )
    assert verified["receipt_sha256"] == receipt["receipt_sha256"]

    receipt["labels_sha256"] = "0" * 64
    _rehash_receipt(receipt)
    with pytest.raises(shard_fan_in.FanInError, match="labels_sha256"):
        shard_fan_in.validate_receipt_against_freeze(
            receipt,
            context=_context(),
            run_input_manifest=run_manifest,
            repeat_policy=repeat_policy,
        )


def test_mapped_rerun_validates_only_the_selected_receipt() -> None:
    run_manifest, valid, repeat_policy = _strict_receipt()
    invalid = deepcopy(valid)
    invalid["workflow_run_attempt"] = 2
    invalid["labels_sha256"] = "0" * 64
    invalid["receipt_key"] = receipt_key(invalid)
    _rehash_receipt(invalid)
    artifacts = (
        shard_fan_in.ReceiptArtifact(
            actual_key=str(invalid["receipt_key"]),
            raw_sha256="8" * 64,
            record=invalid,
        ),
        shard_fan_in.ReceiptArtifact(
            actual_key=str(valid["receipt_key"]),
            raw_sha256="9" * 64,
            record=valid,
        ),
    )

    selection = shard_fan_in.select_and_validate_receipts(
        artifacts,
        declared_shards=(("fixture:model-a", "full_packet"),),
        context=_context(),
        run_input_manifest=run_manifest,
        repeat_policy=repeat_policy,
        shard_schedule_sha256=hash_payload(
            {"shards": [{"model_key": "fixture:model-a", "ablation": "full_packet"}]}
        ),
        accepted_attempt_map=_accepted_map_for_schedule(
            valid, (("fixture:model-a", "full_packet"),)
        ),
    )

    assert selection.receipts == (valid,)


def test_materialized_union_rejects_uncommitted_and_stale_objects(
    tmp_path: Path,
) -> None:
    root = tmp_path / "result-store"
    commitments = _write_committed_cell(root)
    receipt = _receipt("fixture:model-a", "full_packet")
    receipt["cells"] = [
        {
            "case_id": "case-1",
            "model_key": "fixture:model-a",
            "ablation": "full_packet",
            "run_id": "run-1",
            "objects": commitments,
        }
    ]
    _rehash_receipt(receipt)

    output = tmp_path / "materialized"
    shard_fan_in.verify_and_materialize_union(
        (receipt,), result_store_root=str(root), output_dir=output
    )
    assert (
        output / "case-1" / "full_packet" / "fixture-model-a" / "runs.jsonl"
    ).is_file()

    extra = root / "per-case" / "cycle-1" / "stale.metrics.json"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(shard_fan_in.FanInError, match="uncommitted union objects"):
        shard_fan_in.verify_and_materialize_union(
            (receipt,), result_store_root=str(root), output_dir=tmp_path / "extra"
        )

    extra.unlink()
    committed_path = Path(str(commitments[0]["uri"]))
    committed_path.write_text("drift\n", encoding="utf-8")
    with pytest.raises(shard_fan_in.FanInError, match="object version"):
        shard_fan_in.verify_and_materialize_union(
            (receipt,), result_store_root=str(root), output_dir=tmp_path / "drift"
        )


def test_cadence_counts_derive_from_frozen_manifest_and_units(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.jsonl"
    units = tmp_path / "units.jsonl"
    run_input = tmp_path / "run-input.json"
    _write_jsonl(
        manifest,
        [
            _manifest_record("case-1", prediction_units=2),
            _manifest_record("case-2", prediction_units=1),
            _manifest_record("excluded", prediction_units=4, included=False),
        ],
    )
    _write_jsonl(
        units,
        [
            _finalized_envelope("case-1", (True, True)),
            _finalized_envelope("case-2", (True, False)),
            _finalized_envelope("excluded", (), excluded=True),
        ],
    )
    _write_json(
        run_input,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {"case_id": case_id, "ablation": ablation}
                for case_id in ("case-1", "case-2")
                for ablation in _ABLATIONS
            ],
        },
    )

    counts = shard_fan_in.derive_cadence_counts(
        manifest,
        units,
        run_input,
        operator_clean_motion_count=2,
        operator_prediction_unit_count=3,
    )
    assert counts.clean_motion_count == 2
    assert counts.prediction_unit_count == 3

    with pytest.raises(shard_fan_in.FanInError, match="clean_motion_count mismatch"):
        shard_fan_in.derive_cadence_counts(
            manifest,
            units,
            run_input,
            operator_clean_motion_count=99,
            operator_prediction_unit_count=3,
        )


def test_verify_only_accepts_smoke_and_has_no_publication_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []
    report = shard_fan_in.FanInReport(
        cycle_id="smoke-cycle-1",
        mode="verify_only",
        freeze_bundle_sha256="a" * 64,
        accepted_attempt_map_sha256=None,
        accepted_attempt_map=None,
        accepted_receipts=(),
        receipt_inventory_sha256="b" * 64,
        union_inventory_sha256="e" * 64,
        union_commitment_sha256="c" * 64,
        frozen_artifact_sha256={"manifest": "d" * 64},
        clean_motion_count=1,
        prediction_unit_count=1,
        aggregate_output_dir=tmp_path / "aggregate",
    )

    monkeypatch.setattr(
        shard_fan_in,
        "verify_fan_in",
        lambda _config: called.append("verify") or report,
    )
    monkeypatch.setattr(
        shard_fan_in,
        "config_from_args",
        lambda _args, *, verify_only: SimpleNamespace(
            output_dir=tmp_path,
            verify_only=verify_only,
        ),
    )

    assert shard_fan_in.verify_only_main(["--verify-only", *_required_cli_args()]) == 0
    assert called == ["verify"]
    source = Path(str(shard_fan_in.__file__)).read_text(encoding="utf-8")
    assert "shard_fan_in_publish" not in source
    assert "publish_verified_fan_in" not in source
    assert '["aws", "s3", "sync"' not in source


def test_full_fan_in_refuses_nonofficial_policy() -> None:
    with pytest.raises(shard_fan_in.FanInError, match="official cycle"):
        shard_fan_in.require_publishable_cycle(cycle_id="cycle-1", cycle_series="rapid")
    with pytest.raises(shard_fan_in.FanInError, match="non-smoke"):
        shard_fan_in.require_publishable_cycle(
            cycle_id="cycle-1-smoke", cycle_series="official"
        )
    shard_fan_in.require_publishable_cycle(cycle_id="cycle-1", cycle_series="official")


def test_cli_preserves_the_complete_freeze_amendment_chain() -> None:
    args = shard_fan_in.build_parser().parse_args(
        [
            "--freeze-bundle",
            "manifests/current.freeze.json",
            "--amendment-bundle",
            "manifests/root.freeze.json",
            "--amendment-bundle",
            "manifests/amendment-1.freeze.json",
            "--run-input-manifest",
            "manifests/run-input.json",
            "--receipt-root",
            "s3://results",
            "--output-dir",
            "tmp/fan-in",
            "--verify-only",
        ]
    )

    config = shard_fan_in.config_from_args(args, verify_only=True)

    assert config.amendment_bundle_paths == (
        Path("manifests/root.freeze.json"),
        Path("manifests/amendment-1.freeze.json"),
    )


def test_publisher_rechecks_inventory_before_canonical_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aggregate = tmp_path / "aggregate"
    public = aggregate / "public"
    public.mkdir(parents=True)
    (public / "report.json").write_text("{}\n", encoding="utf-8")
    report = _report(aggregate_output_dir=aggregate)
    config = shard_fan_in.FanInConfig(
        freeze_bundle_path=tmp_path / "freeze.json",
        run_input_manifest_path=tmp_path / "run-input.json",
        receipt_root=str(tmp_path / "store"),
        output_dir=tmp_path / "output",
    )
    monkeypatch.setattr(shard_fan_in_publish, "verify_fan_in", lambda _config: report)
    monkeypatch.setattr(
        shard_fan_in_publish,
        "current_receipt_inventory_sha256",
        lambda _root, _cycle: "0" * 64,
    )
    monkeypatch.setattr(
        shard_fan_in_publish,
        "current_union_inventory_sha256",
        lambda _root, _cycle: report.union_inventory_sha256,
    )

    with pytest.raises(shard_fan_in.FanInError, match="inventory changed"):
        shard_fan_in_publish.publish_fan_in(
            config, publish_root=str(tmp_path / "published")
        )
    assert not (tmp_path / "published").exists()

    monkeypatch.setattr(
        shard_fan_in_publish,
        "current_receipt_inventory_sha256",
        lambda _root, _cycle: report.receipt_inventory_sha256,
    )
    monkeypatch.setattr(
        shard_fan_in_publish,
        "current_union_inventory_sha256",
        lambda _root, _cycle: "0" * 64,
    )
    with pytest.raises(shard_fan_in.FanInError, match="object versions changed"):
        shard_fan_in_publish.publish_fan_in(
            config, publish_root=str(tmp_path / "published")
        )

    monkeypatch.setattr(
        shard_fan_in_publish,
        "current_union_inventory_sha256",
        lambda _root, _cycle: report.union_inventory_sha256,
    )
    shard_fan_in_publish.publish_fan_in(
        config, publish_root=str(tmp_path / "published")
    )
    assert (tmp_path / "published" / "report.json").is_file()


def test_s3_publication_refuses_a_nonempty_canonical_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout='{"KeyCount": 1}', stderr="")

    monkeypatch.setattr(shard_fan_in_publish.subprocess, "run", fake_run)

    with pytest.raises(shard_fan_in.FanInError, match="prefix is not empty"):
        shard_fan_in_publish._require_empty_s3_prefix(
            "s3://results/reports/cycle-1/multi-ablation/"
        )
    assert commands[0][:3] == ["aws", "s3api", "list-objects-v2"]


def test_s3_version_lookup_uses_one_s3api_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(
            returncode=0, stdout='{"VersionId": "version-1"}', stderr=""
        )

    monkeypatch.setattr(shard_fan_in.subprocess, "run", fake_run)

    assert (
        shard_fan_in._head_s3_version("s3://results/per-case/cycle-1/x") == "version-1"
    )
    assert commands == [
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            "results",
            "--key",
            "per-case/cycle-1/x",
            "--output",
            "json",
        ]
    ]


def test_verified_materialization_delegates_to_official_cartesian_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[Any] = []
    aggregate_result = SimpleNamespace(
        expected_matrix_row_count=4,
        aggregated_matrix_row_count=4,
        expected_case_count=2,
        aggregated_case_count=2,
        model_count=1,
    )
    monkeypatch.setattr(
        shard_fan_in,
        "verify_and_materialize_union",
        lambda *_args, **_kwargs: "e" * 64,
    )
    monkeypatch.setattr(
        shard_fan_in,
        "aggregate_official_results",
        lambda config: captured.append(config) or aggregate_result,
    )
    frozen = SimpleNamespace(
        context=SimpleNamespace(cycle_id="cycle-1"),
        labels_path=tmp_path / "labels.jsonl",
        model_registry_path=tmp_path / "registry.json",
        baselines_path=tmp_path / "baselines.jsonl",
        execution_policy={"allow_no_baselines": True},
    )
    config = shard_fan_in.FanInConfig(
        freeze_bundle_path=tmp_path / "freeze.json",
        run_input_manifest_path=tmp_path / "run-input.json",
        receipt_root=str(tmp_path / "store"),
        output_dir=tmp_path / "output",
    )

    result, union_inventory_sha256 = shard_fan_in._validate_aggregate(
        config,
        frozen=frozen,
        receipts=(),
        counts=shard_fan_in.CadenceCounts(2, 3),
        materialized_dir=tmp_path / "materialized",
        aggregate_dir=tmp_path / "aggregate",
        cycle_series="official",
        public_fan_in_record={"cycle_id": "cycle-1"},
    )

    assert result is aggregate_result
    assert union_inventory_sha256 == "e" * 64
    assert len(captured) == 1
    assert captured[0].clean_motion_count == 2
    assert captured[0].prediction_unit_count == 3
    assert captured[0].per_case_dir == tmp_path / "materialized"


_ABLATIONS = ("full_packet", "metadata_only")
_DECLARED_SHARDS = tuple(("fixture:model-a", value) for value in _ABLATIONS)
_SCHEDULE_SHA256 = hash_payload(
    {
        "shards": [
            {"model_key": model_key, "ablation": ablation}
            for model_key, ablation in sorted(_DECLARED_SHARDS)
        ]
    }
)


def _receipt(
    model_key: str,
    ablation: str,
    *,
    run_id: str = "1001",
    attempt: int = 1,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "legalforecast.shard_receipt.v1",
        "cycle_id": "cycle-1",
        "model_key": model_key,
        "ablation": ablation,
        "workflow_run_id": run_id,
        "workflow_run_attempt": attempt,
        "freeze_bundle_sha256": "a" * 64,
        "execution_policy_sha256": "b" * 64,
        "execution_policy_artifact_sha256": "c" * 64,
        "repeat_policy_sha256": "d" * 64,
        "attempt_policy_sha256": "e" * 64,
        "receipt_policy_sha256": "f" * 64,
        "frozen_manifest_sha256": "1" * 64,
        "run_input_manifest_sha256": "4" * 64,
        "labels_sha256": "2" * 64,
        "model_registry_sha256": "3" * 64,
        "expected_cell_count": 0,
        "cells": [],
        "result_commitment_sha256": hash_payload({"objects": []}),
    }
    receipt["receipt_key"] = receipt_key(receipt)
    receipt["receipt_sha256"] = hash_payload(receipt)
    return receipt


def _rehash_receipt(receipt: dict[str, Any]) -> None:
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hash_payload(receipt)


def _context() -> shard_fan_in.FrozenFanInContext:
    return shard_fan_in.FrozenFanInContext(
        cycle_id="cycle-1",
        freeze_bundle_sha256="a" * 64,
        execution_policy_sha256="b" * 64,
        execution_policy_artifact_sha256="c" * 64,
        repeat_policy_sha256=hash_payload({"case_ids": [], "count": 1}),
        attempt_policy_sha256="e" * 64,
        receipt_policy_sha256="f" * 64,
        frozen_manifest_sha256="1" * 64,
        run_input_manifest_sha256="4" * 64,
        labels_sha256="2" * 64,
        model_registry_sha256="3" * 64,
    )


def _strict_receipt() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = {
        "cycle_id": "cycle-1",
        "model_packets": [
            {
                "case_id": "case-1",
                "ablation": "full_packet",
                "object_key": "model-packets/cycle-1/case-1/full_packet.json",
                "sha256": "f" * 64,
            }
        ],
    }
    repeat_policy = {"case_ids": [], "count": 1}
    objects = [
        {
            "name": name,
            "uri": f"s3://results/per-case/cycle-1/run-1.{suffix}",
            "version_id": f"version-{name}",
            "sha256": digest * 64,
            "size_bytes": 1,
        }
        for name, suffix, digest in (
            ("runs", "runs.jsonl", "6"),
            ("accounting", "accounting.jsonl", "7"),
            ("metrics", "metrics.json", "8"),
        )
    ]
    completion = {
        "schema_version": "legalforecast.shard_cell_completion.v1",
        "status": "success",
        "origin": "fresh",
        "workflow_run_id": "1001",
        "workflow_run_attempt": 1,
        "cycle_id": "cycle-1",
        "model_key": "fixture:model-a",
        "case_id": "case-1",
        "ablation": "full_packet",
        "run_id": "run-1",
        "packet_object_key": "model-packets/cycle-1/case-1/full_packet.json",
        "packet_sha256": "f" * 64,
        "repeat_count": 1,
        "repeat_policy_sha256": hash_payload(repeat_policy),
        "execution_policy_sha256": "b" * 64,
        "objects": objects,
        "result_commitment_sha256": hash_payload(
            {"objects": sorted(objects, key=lambda value: value["name"])}
        ),
    }
    provenance = {
        "dispatch_mode": "shard_only",
        "cycle_id": "cycle-1",
        "current_freeze_bundle_sha256": "a" * 64,
        "execution_policy_sha256": "b" * 64,
        "execution_policy_artifact_sha256": "c" * 64,
        "repeat_policy": repeat_policy,
        "repeat_policy_sha256": hash_payload(repeat_policy),
        "attempt_policy_sha256": "e" * 64,
        "receipt_policy_sha256": "f" * 64,
        "frozen_result_inputs": {
            "frozen_manifest_sha256": "1" * 64,
            "labels_sha256": "2" * 64,
            "model_registry_sha256": "3" * 64,
        },
        "requested_shard": {
            "model_key": "fixture:model-a",
            "ablation": "full_packet",
        },
        "dispatches": [{"workflow_run_id": "1001", "workflow_run_attempt": 1}],
    }
    receipt = build_shard_receipt(
        provenance=provenance,
        manifest=manifest,
        completions=(completion,),
        run_input_manifest_sha256="4" * 64,
        labels_sha256="2" * 64,
        model_registry_sha256="3" * 64,
    )
    return manifest, receipt, repeat_policy


def _selection(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_key": receipt["model_key"],
        "ablation": receipt["ablation"],
        "workflow_run_id": receipt["workflow_run_id"],
        "workflow_run_attempt": receipt["workflow_run_attempt"],
        "receipt_key": receipt["receipt_key"],
        "receipt_sha256": receipt["receipt_sha256"],
    }


def _accepted_map(
    receipt: dict[str, Any], *, freeze_bundle_sha256: str = "a" * 64
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": "legalforecast.accepted_attempt_map.v1",
        "cycle_id": "cycle-1",
        "parent_freeze_bundle_sha256": freeze_bundle_sha256,
        "execution_policy_sha256": "b" * 64,
        "shard_schedule_sha256": _SCHEDULE_SHA256,
        "selections": [_selection(receipt)],
    }
    record["accepted_attempt_map_sha256"] = _map_hash(record)
    return record


def _accepted_map_for_schedule(
    receipt: dict[str, Any], schedule: tuple[tuple[str, str], ...]
) -> dict[str, Any]:
    record = _accepted_map(receipt)
    record["shard_schedule_sha256"] = hash_payload(
        {
            "shards": [
                {"model_key": model_key, "ablation": ablation}
                for model_key, ablation in sorted(schedule)
            ]
        }
    )
    record["accepted_attempt_map_sha256"] = _map_hash(record)
    return record


def _map_hash(record: dict[str, Any]) -> str:
    without_hash = dict(record)
    without_hash.pop("accepted_attempt_map_sha256", None)
    return hash_payload(without_hash)


def _write_committed_cell(root: Path) -> list[dict[str, Any]]:
    base = root / "per-case" / "cycle-1"
    payloads = {
        "runs": b'{"case_id":"case-1"}\n',
        "accounting": b'{"case_id":"case-1"}\n',
        "metrics": json.dumps(
            {
                "run_id": "run-1",
                "case_id": "case-1",
                "model_key": "fixture:model-a",
                "ablation": "full_packet",
            },
            sort_keys=True,
        ).encode(),
    }
    commitments: list[dict[str, Any]] = []
    for name, payload in payloads.items():
        path = base / f"run-1.{name}.{'json' if name == 'metrics' else 'jsonl'}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        commitments.append(
            {
                "name": name,
                "uri": str(path),
                "version_id": digest,
                "sha256": digest,
                "size_bytes": len(payload),
            }
        )
    return commitments


def _manifest_record(
    case_id: str, *, prediction_units: int, included: bool = True
) -> dict[str, Any]:
    return {
        "candidate_id": f"candidate-{case_id}",
        "case_id": case_id,
        "eligibility_status": "eligible",
        "exclusion_status": "included" if included else "excluded",
        "case_mix_fields": {"prediction_unit_count": prediction_units},
    }


def _finalized_envelope(
    case_id: str,
    scoreable: tuple[bool, ...],
    *,
    excluded: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": "legalforecast.finalized_prediction_units.v1",
        "candidate_id": f"candidate-{case_id}",
        "case_id": case_id,
        "unitization_review_queue_sha256": "9" * 64,
        "status": "candidate_excluded" if excluded else "finalized",
        "prediction_units": [
            {
                "unit_id": f"unit-{case_id}-{index}",
                "should_score": should_score,
                "source_unit_sha256s": [str(index) * 64],
                "adjudication_id": f"adj-{case_id}-{index}",
                "disposition": "ACCEPT",
            }
            for index, should_score in enumerate(scoreable, start=1)
        ],
    }
    if excluded:
        record["exclusion"] = {"reason": "fixture exclusion"}
    return record


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _required_cli_args() -> list[str]:
    return [
        "--freeze-bundle",
        "freeze.json",
        "--run-input-manifest",
        "run-inputs.json",
        "--receipt-root",
        "receipts",
        "--output-dir",
        "output",
    ]


def _report(*, aggregate_output_dir: Path) -> shard_fan_in.FanInReport:
    return shard_fan_in.FanInReport(
        cycle_id="cycle-1",
        mode="publish",
        freeze_bundle_sha256="a" * 64,
        accepted_attempt_map_sha256=None,
        accepted_attempt_map=None,
        accepted_receipts=(),
        receipt_inventory_sha256="b" * 64,
        union_inventory_sha256="e" * 64,
        union_commitment_sha256="c" * 64,
        frozen_artifact_sha256={"manifest": "d" * 64},
        clean_motion_count=1,
        prediction_unit_count=1,
        aggregate_output_dir=aggregate_output_dir,
    )

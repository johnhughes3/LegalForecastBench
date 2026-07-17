from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import legalforecast.publication.shard_receipt as shard_receipt_module
import pytest
from legalforecast.protocol.manifest import hash_payload

_S3_OBJECTS: dict[tuple[str, str], bytes] = {}
_REAL_READ_EXACT_OBJECT = shard_receipt_module._read_exact_object


@pytest.fixture(autouse=True)
def _clear_s3_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    _S3_OBJECTS.clear()
    monkeypatch.setattr(
        shard_receipt_module,
        "_read_exact_object",
        lambda commitment: _S3_OBJECTS[
            (str(commitment["uri"]), str(commitment["version_id"]))
        ],
    )


def test_finalize_shard_builds_exact_mixed_origin_receipt(tmp_path: Path) -> None:
    completions = (
        _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
        _completion(tmp_path, case_id="case-2", repeat_count=1, origin="resumed"),
    )

    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=completions,
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )

    assert receipt["expected_cell_count"] == 2
    assert [cell["origin"] for cell in receipt["cells"]] == ["fresh", "resumed"]
    assert receipt["workflow_run_id"] == "1001"
    assert receipt["workflow_run_attempt"] == 1
    assert receipt["receipt_key"].endswith("/1001/1.json")
    assert len(receipt["result_commitment_sha256"]) == 64
    shard_receipt_module.verify_committed_objects(receipt)


@pytest.mark.parametrize("mutation", ("missing", "failed", "extra"))
def test_finalize_shard_rejects_incomplete_or_nonexact_cells(
    tmp_path: Path, mutation: str
) -> None:
    first = _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh")
    second = _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh")
    completions = [first, second]
    if mutation == "missing":
        completions.pop()
    elif mutation == "failed":
        completions[1]["status"] = "failed"
    elif mutation == "extra":
        completions.append(
            _completion(tmp_path, case_id="case-3", repeat_count=1, origin="fresh")
        )
    with pytest.raises(shard_receipt_module.ShardReceiptError):
        shard_receipt_module.build_shard_receipt(
            provenance=_provenance(),
            manifest=_manifest(),
            completions=completions,
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
        )


def test_finalize_shard_rejects_missing_frozen_repeat_case(tmp_path: Path) -> None:
    provenance = _provenance()
    repeat_policy = {"case_ids": ["case-missing"], "count": 3}
    provenance["repeat_policy"] = repeat_policy
    provenance["repeat_policy_sha256"] = hash_payload(repeat_policy)

    with pytest.raises(shard_receipt_module.ShardReceiptError, match="case-missing"):
        shard_receipt_module.build_shard_receipt(
            provenance=provenance,
            manifest=_manifest(),
            completions=(
                _completion(tmp_path, case_id="case-1", repeat_count=1, origin="fresh"),
                _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
            ),
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
        )


def test_rerun_receipt_adopts_prior_cells_and_uses_current_attempt(
    tmp_path: Path,
) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(
                tmp_path,
                case_id="case-1",
                repeat_count=3,
                origin="fresh",
                workflow_run_attempt=1,
            ),
            _completion(
                tmp_path,
                case_id="case-2",
                repeat_count=1,
                origin="fresh",
                workflow_run_attempt=2,
            ),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
        current_workflow_run_id="1001",
        current_workflow_run_attempt=2,
    )

    assert receipt["workflow_run_attempt"] == 2
    assert receipt["receipt_key"].endswith("/1001/2.json")
    first, second = receipt["cells"]
    assert first["producer_workflow_run_attempt"] == 1
    assert first["receipt_adoption_state"] == "adopted_prior_attempt"
    assert second["producer_workflow_run_attempt"] == 2
    assert second["receipt_adoption_state"] == "current_attempt"


def test_rerun_receipt_selects_highest_valid_duplicate_attempt(
    tmp_path: Path,
) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(
                tmp_path,
                case_id="case-1",
                repeat_count=3,
                origin="resumed",
                workflow_run_attempt=1,
            ),
            _completion(
                tmp_path,
                case_id="case-1",
                repeat_count=3,
                origin="fresh",
                workflow_run_attempt=2,
            ),
            _completion(
                tmp_path,
                case_id="case-2",
                repeat_count=1,
                origin="fresh",
                workflow_run_attempt=1,
            ),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
        current_workflow_run_id="1001",
        current_workflow_run_attempt=2,
    )

    first = receipt["cells"][0]
    assert first["origin"] == "fresh"
    assert first["producer_workflow_run_attempt"] == 2
    assert first["receipt_adoption_state"] == "current_attempt"


def test_rerun_receipt_rejects_conflicting_highest_attempt_duplicates(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        shard_receipt_module.ShardReceiptError, match="ambiguous completion cells"
    ):
        shard_receipt_module.build_shard_receipt(
            provenance=_provenance(),
            manifest=_manifest(),
            completions=(
                _completion(
                    tmp_path,
                    case_id="case-1",
                    repeat_count=3,
                    origin="fresh",
                    workflow_run_attempt=2,
                ),
                _completion(
                    tmp_path,
                    case_id="case-1",
                    repeat_count=3,
                    origin="resumed",
                    workflow_run_attempt=2,
                ),
                _completion(
                    tmp_path,
                    case_id="case-2",
                    repeat_count=1,
                    origin="fresh",
                    workflow_run_attempt=2,
                ),
            ),
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
            current_workflow_run_id="1001",
            current_workflow_run_attempt=2,
        )


def test_rerun_receipt_rejects_future_completion(tmp_path: Path) -> None:
    with pytest.raises(
        shard_receipt_module.ShardReceiptError, match="future workflow attempt"
    ):
        shard_receipt_module.build_shard_receipt(
            provenance=_provenance(),
            manifest=_manifest(),
            completions=(
                _completion(
                    tmp_path,
                    case_id="case-1",
                    repeat_count=3,
                    origin="fresh",
                    workflow_run_attempt=3,
                ),
                _completion(
                    tmp_path,
                    case_id="case-2",
                    repeat_count=1,
                    origin="fresh",
                    workflow_run_attempt=2,
                ),
            ),
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
            current_workflow_run_id="1001",
            current_workflow_run_attempt=2,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("cycle_id", "wrong-cycle", "cycle_id mismatch"),
        ("execution_policy_sha256", "0" * 64, "execution policy mismatch"),
    ),
)
def test_completion_rejects_frozen_identity_mismatch(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    completion = _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh")
    completion[field] = value

    with pytest.raises(shard_receipt_module.ShardReceiptError, match=message):
        shard_receipt_module.build_shard_receipt(
            provenance=_provenance(),
            manifest=_manifest(),
            completions=(
                completion,
                _completion(
                    tmp_path,
                    case_id="case-2",
                    repeat_count=1,
                    origin="fresh",
                ),
            ),
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
        )


def test_receipt_write_is_exclusive_but_new_attempt_has_new_key(
    tmp_path: Path,
) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
            _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )

    first_path = shard_receipt_module.write_receipt_once(
        str(tmp_path / "receipts"), receipt
    )
    assert Path(first_path).is_file()
    with pytest.raises(shard_receipt_module.ReceiptAlreadyExistsError):
        shard_receipt_module.write_receipt_once(str(tmp_path / "receipts"), receipt)

    attempt_two = dict(receipt)
    attempt_two["workflow_run_attempt"] = 2
    attempt_two["receipt_key"] = shard_receipt_module.receipt_key(attempt_two)
    attempt_two_without_hash = dict(attempt_two)
    attempt_two_without_hash.pop("receipt_sha256")
    attempt_two["receipt_sha256"] = hash_payload(attempt_two_without_hash)
    assert attempt_two["receipt_key"] != receipt["receipt_key"]
    assert Path(
        shard_receipt_module.write_receipt_once(str(tmp_path / "receipts"), attempt_two)
    ).is_file()


def test_exact_version_verification_rejects_content_drift(tmp_path: Path) -> None:
    completions = (
        _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
        _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
    )
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=completions,
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )
    commitment = receipt["cells"][0]["objects"][0]
    identity = (str(commitment["uri"]), str(commitment["version_id"]))
    _S3_OBJECTS[identity] = b"drift"

    with pytest.raises(
        shard_receipt_module.ShardReceiptError, match="commitment mismatch"
    ):
        shard_receipt_module.verify_committed_objects(receipt)


def test_receipt_write_rejects_tampered_receipt_content(tmp_path: Path) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
            _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )
    receipt["labels_sha256"] = "0" * 64

    with pytest.raises(shard_receipt_module.ShardReceiptError, match="receipt_sha256"):
        shard_receipt_module.write_receipt_once(str(tmp_path / "receipts"), receipt)


def test_strict_receipt_verifier_reconstructs_frozen_cells(tmp_path: Path) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
            _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )

    verified = shard_receipt_module.verify_shard_receipt(
        receipt,
        manifest=_manifest(),
        repeat_policy={"case_ids": ["case-1"], "count": 3},
        expected_identity=_receipt_identity(),
        expected_shard=("fixture:model-a", "full_packet"),
        actual_receipt_key=str(receipt["receipt_key"]),
    )

    assert verified == receipt


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("unknown_top_level", "receipt fields mismatch"),
        ("wrong_key", "actual receipt key"),
        ("wrong_frozen_identity", "labels_sha256 does not match"),
        ("wrong_expected_count", "expected_cell_count"),
        ("wrong_global_commitment", "result commitment"),
        ("wrong_adoption_state", "receipt_adoption_state"),
    ),
)
def test_strict_receipt_verifier_rejects_rehashed_invalid_receipt(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
            _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )
    actual_key = str(receipt["receipt_key"])
    if mutation == "unknown_top_level":
        receipt["unexpected"] = True
    elif mutation == "wrong_key":
        actual_key = "shard-receipts/cycle-1/not-the-receipt.json"
    elif mutation == "wrong_frozen_identity":
        receipt["labels_sha256"] = "0" * 64
    elif mutation == "wrong_expected_count":
        receipt["expected_cell_count"] = 1
    elif mutation == "wrong_global_commitment":
        receipt["result_commitment_sha256"] = "0" * 64
    elif mutation == "wrong_adoption_state":
        receipt["cells"][0]["receipt_adoption_state"] = "adopted_prior_attempt"
    receipt_without_hash = dict(receipt)
    receipt_without_hash.pop("receipt_sha256")
    receipt["receipt_sha256"] = hash_payload(receipt_without_hash)

    with pytest.raises(shard_receipt_module.ShardReceiptError, match=message):
        shard_receipt_module.verify_shard_receipt(
            receipt,
            manifest=_manifest(),
            repeat_policy={"case_ids": ["case-1"], "count": 3},
            expected_identity=_receipt_identity(),
            expected_shard=("fixture:model-a", "full_packet"),
            actual_receipt_key=actual_key,
        )


def test_completion_rejects_null_s3_version(tmp_path: Path) -> None:
    completion = _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh")
    completion["objects"][0]["version_id"] = "null"
    completion["result_commitment_sha256"] = hash_payload(
        {"objects": sorted(completion["objects"], key=lambda value: value["name"])}
    )

    with pytest.raises(shard_receipt_module.ShardReceiptError, match="VersionId"):
        shard_receipt_module.build_shard_receipt(
            provenance=_provenance(),
            manifest=_manifest(),
            completions=(
                completion,
                _completion(
                    tmp_path,
                    case_id="case-2",
                    repeat_count=1,
                    origin="fresh",
                ),
            ),
            frozen_manifest_sha256="6" * 64,
            labels_sha256="7" * 64,
            model_registry_sha256="8" * 64,
        )


def test_exact_s3_reader_pins_recorded_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        Path(command[-1]).write_bytes(b"payload")
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(shard_receipt_module.subprocess, "run", fake_run)

    payload = _REAL_READ_EXACT_OBJECT(
        {
            "uri": "s3://results/metrics/run.metrics.json",
            "version_id": "version-123",
        }
    )

    assert payload == b"payload"
    assert commands[0][commands[0].index("--version-id") + 1] == "version-123"


def test_s3_receipt_writer_uses_atomic_if_none_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = shard_receipt_module.build_shard_receipt(
        provenance=_provenance(),
        manifest=_manifest(),
        completions=(
            _completion(tmp_path, case_id="case-1", repeat_count=3, origin="fresh"),
            _completion(tmp_path, case_id="case-2", repeat_count=1, origin="fresh"),
        ),
        frozen_manifest_sha256="6" * 64,
        labels_sha256="7" * 64,
        model_registry_sha256="8" * 64,
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(shard_receipt_module.subprocess, "run", fake_run)

    destination = shard_receipt_module.write_receipt_once("s3://results", receipt)

    assert destination.startswith("s3://results/shard-receipts/")
    assert commands[0][commands[0].index("--if-none-match") + 1] == "*"


def _manifest() -> dict[str, object]:
    return {
        "model_packets": [
            {
                "case_id": case_id,
                "ablation": "full_packet",
                "packet_object_key": f"model-packets/cycle-1/{case_id}.json",
                "sha256": digest * 64,
            }
            for case_id, digest in (("case-1", "a"), ("case-2", "b"))
        ]
    }


def _provenance() -> dict[str, object]:
    repeat_policy = {"case_ids": ["case-1"], "count": 3}
    return {
        "dispatch_mode": "shard_only",
        "cycle_id": "cycle-1",
        "current_freeze_bundle_sha256": "1" * 64,
        "execution_policy_sha256": "2" * 64,
        "execution_policy_artifact_sha256": "9" * 64,
        "repeat_policy": repeat_policy,
        "repeat_policy_sha256": hash_payload(repeat_policy),
        "attempt_policy_sha256": "3" * 64,
        "receipt_policy_sha256": "4" * 64,
        "frozen_result_inputs": {
            "frozen_manifest_sha256": "6" * 64,
            "labels_sha256": "7" * 64,
            "model_registry_sha256": "8" * 64,
        },
        "requested_shard": {
            "model_key": "fixture:model-a",
            "ablation": "full_packet",
        },
        "dispatches": [{"workflow_run_id": "1001", "workflow_run_attempt": 1}],
    }


def _receipt_identity() -> dict[str, str]:
    return {
        "freeze_bundle_sha256": "1" * 64,
        "execution_policy_sha256": "2" * 64,
        "execution_policy_artifact_sha256": "9" * 64,
        "repeat_policy_sha256": hash_payload({"case_ids": ["case-1"], "count": 3}),
        "attempt_policy_sha256": "3" * 64,
        "receipt_policy_sha256": "4" * 64,
        "frozen_manifest_sha256": "6" * 64,
        "labels_sha256": "7" * 64,
        "model_registry_sha256": "8" * 64,
    }


def _completion(
    tmp_path: Path,
    *,
    case_id: str,
    repeat_count: int,
    origin: str,
    workflow_run_attempt: int = 1,
) -> dict[str, object]:
    objects: list[dict[str, object]] = []
    for name in ("runs", "accounting", "metrics"):
        run_id = f"run-{case_id}"
        payload = (
            json.dumps(
                {
                    "run_id": run_id,
                    "cycle_id": "cycle-1",
                    "case_id": case_id,
                    "model_key": "fixture:model-a",
                    "ablation": "full_packet",
                    "packet_object_key": f"model-packets/cycle-1/{case_id}.json",
                    "packet_sha256": ("a" if case_id == "case-1" else "b") * 64,
                    "repeat_count": repeat_count,
                    "repeat_policy_sha256": hash_payload(
                        {"case_ids": ["case-1"], "count": 3}
                    ),
                    "execution_policy_sha256": "2" * 64,
                },
                sort_keys=True,
            ).encode()
            if name == "metrics"
            else f"{case_id}-{name}".encode()
        )
        digest = hashlib.sha256(payload).hexdigest()
        suffix = {
            "runs": "runs.jsonl",
            "accounting": "accounting.jsonl",
            "metrics": "metrics.json",
        }[name]
        uri = f"s3://results/per-case/cycle-1/metrics/cycle-1/{run_id}.{suffix}"
        _S3_OBJECTS[(uri, digest)] = payload
        objects.append(
            {
                "name": name,
                "uri": uri,
                "version_id": digest,
                "sha256": digest,
                "size_bytes": len(payload),
            }
        )
    return {
        "schema_version": "legalforecast.shard_cell_completion.v1",
        "status": "success",
        "origin": origin,
        "workflow_run_id": "1001",
        "workflow_run_attempt": workflow_run_attempt,
        "cycle_id": "cycle-1",
        "model_key": "fixture:model-a",
        "case_id": case_id,
        "ablation": "full_packet",
        "run_id": run_id,
        "packet_object_key": f"model-packets/cycle-1/{case_id}.json",
        "packet_sha256": ("a" if case_id == "case-1" else "b") * 64,
        "repeat_count": repeat_count,
        "repeat_policy_sha256": hash_payload({"case_ids": ["case-1"], "count": 3}),
        "execution_policy_sha256": "2" * 64,
        "objects": objects,
        "result_commitment_sha256": hash_payload(
            {"objects": sorted(objects, key=lambda value: str(value["name"]))}
        ),
    }

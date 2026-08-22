from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import deferred_bundle as module
from legalforecast.evals.corpus_manifest.deferred_bundle import (
    DeferredReceiptError,
    ManifestForecastBundleError,
    attach_labels,
    issue_bundle,
    verify_bundle,
    write_deferred_receipts,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, value: object) -> bytes:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> bytes:
    payload = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    # Keep these unit tests small; production uses the fixed 100x2 matrix and
    # the real loaders are covered by the adversarial tests.
    monkeypatch.setattr(module, "_OFFICIAL_CASE_COUNT", 1)
    monkeypatch.setattr(module, "_OFFICIAL_MODEL_COUNT", 1)
    monkeypatch.setattr(module, "OFFICIAL_SHARD_ABLATIONS", ("full_packet",))
    freeze = tmp_path / "freeze-inputs"
    freeze_card_outputs: dict[str, str] = {}
    for name, value in (
        ("prompt-contract.json", {"role": "prompt"}),
        ("scorer-contract.json", {"role": "scorer"}),
        ("harness-contract.json", {"role": "harness"}),
        (
            "no-baselines.json",
            {
                "schema_version": "legalforecast.no_baselines.v1",
                "cycle_id": "cycle-1",
                "status": "unavailable",
            },
        ),
        ("complete-exclusion-ledger.jsonl", {"candidate_id": "excluded"}),
    ):
        payload = _write(freeze / name, value)
        freeze_card_outputs[name] = _sha(payload)
    _write(
        freeze / "run-cards/issue-manifest-freeze-inputs.json",
        {
            "status": "completed",
            "cycle_id": "cycle-1",
            "provider_calls_made": 0,
            "output_commitments": freeze_card_outputs,
        },
    )

    units = tmp_path / "finalized-units.jsonl"
    _write_jsonl(
        units,
        [
            {
                "candidate_id": "case-1",
                "prediction_units": [{"unit_id": "unit-1", "claim_name": "Count I"}],
            }
        ],
    )
    manifest = tmp_path / "owner-manifest.json"
    _write(manifest, {"cycle_id": "cycle-1", "manifest_sha256": "a" * 64})
    prediction_units_source = {
        "path": str(units),
        "sha256": _sha(units.read_bytes()),
    }
    monkeypatch.setattr(
        module,
        "_load_manifest",
        lambda _payload, _digest: type(
            "Manifest",
            (),
            {
                "cycle_id": "cycle-1",
                "cases": (type("Case", (), {"candidate_id": "case-1"})(),),
                "prediction_units_source": type(
                    "Source",
                    (),
                    {"to_record": lambda self: prediction_units_source},
                )(),
            },
        )(),
    )
    packet = tmp_path / "forecast/model-packets/case-1-full.json"
    packet_payload = _write(
        packet, {"candidate_id": "case-1", "ablation": "full_packet"}
    )
    forecast = packet.parent.parent
    _write(
        forecast / "manifest-mode-run-record.json",
        {
            "cycle_id": "cycle-1",
            "manifest_sha256": "a" * 64,
            "docket_tool_enabled": False,
            "required_eval_run_case_flags": ["--no-docket-tool"],
            "schema_version": "legalforecast.manifest_mode_forecast_run_record.v1",
            "entry_mode": "owner_signed_manifest",
            "case_count": 1,
            "packet_count": 1,
            "packet_ablations": ["full_packet"],
            "provider_calls_made": 0,
            "prediction_units_source": prediction_units_source,
            "owner_signature_reference": {
                "bead_id": "legalforecastbench-test",
                "approval_line": (
                    "I approve corpus manifest "
                    + "a" * 64
                    + " as the frozen Cycle 1 forecast corpus."
                ),
            },
        },
    )
    _write(
        forecast / "run-inputs.json",
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "candidate_id": "case-1",
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "packet_object_key": "model-packets/case-1-full.json",
                    "packet_sha256": _sha(packet_payload),
                    "prompt_sha256": "b" * 64,
                }
            ],
        },
    )
    registry = tmp_path / "successor-registry.json"
    _write(registry, [{"provider": "fixture", "model_id": "model-1"}])
    caps = tmp_path / "provider-caps.json"
    _write(caps, {"cycle_id": "cycle-1", "status": "authorized"})
    policy = tmp_path / "execution-policy.json"
    _write(policy, {"cycle_id": "cycle-1", "allow_no_baselines": True})
    monkeypatch.setattr(
        module,
        "_authenticate_runtime_inputs",
        lambda *_args, **_kwargs: (
            [{"provider": "fixture", "model_id": "model-1"}],
            {
                "repeat_policy": {"count": 1, "case_ids": ["case-1"]},
                "shard_schedule": {
                    "shards": [
                        {"model_key": "fixture:model-1", "ablation": "full_packet"}
                    ]
                },
            },
        ),
    )
    return {
        "freeze": freeze,
        "manifest": manifest,
        "forecast": forecast,
        "registry": registry,
        "caps": caps,
        "policy": policy,
        "units": units,
        "output": tmp_path / "bundle",
    }


def _issue(fixture: dict[str, Any]) -> dict[str, Any]:
    build = issue_bundle(
        cycle_id="cycle-1",
        freeze_inputs_root=fixture["freeze"],  # type: ignore[arg-type]
        owner_manifest=fixture["manifest"],  # type: ignore[arg-type]
        forecast_output_dir=fixture["forecast"],  # type: ignore[arg-type]
        model_registry=fixture["registry"],  # type: ignore[arg-type]
        provider_cycle_caps=fixture["caps"],  # type: ignore[arg-type]
        execution_policy=fixture["policy"],  # type: ignore[arg-type]
        repeat_policy={"count": 1, "case_ids": ["case-1"]},
        shard_schedule=[{"model_key": "fixture:model-1", "ablation": "full_packet"}],
        journal_namespace="cycle-1/manifest/a" + "a" * 20,
        output_root=fixture["output"],  # type: ignore[arg-type]
    )
    return dict(build.bundle)


def test_issue_verify_and_toctou(fixture: dict[str, Any]) -> None:
    bundle = _issue(fixture)
    assert bundle["labels_state"] == "deferred"
    assert bundle["scoreable"] is False
    assert verify_bundle(fixture["output"]) == bundle  # type: ignore[arg-type]
    fixture["policy"].write_bytes(b'{"cycle_id":"cycle-1","changed":true}\n')  # type: ignore[union-attr]
    with pytest.raises(ManifestForecastBundleError, match="bytes changed"):
        verify_bundle(fixture["output"])  # type: ignore[arg-type]


def test_deferred_receipt_cannot_contain_labels(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    bundle = _issue(fixture)
    receipts = [
        {
            "bundle_sha256": bundle["bundle_sha256"],
            "candidate_id": "case-1",
            "ablation": "full_packet",
            "packet_sha256": next(
                iter(bundle["forecast_inputs"]["packet_sha256"].values())
            ),  # type: ignore[index]
            "actual_provider_prompt_sha256": "b" * 64,
            "repeat_index": 0,
            "labels_state": "deferred",
            "scoreable": False,
            "publishable": False,
            "label": "leak",
        }
    ]
    with pytest.raises(DeferredReceiptError, match="outcome or label"):
        write_deferred_receipts(
            bundle=fixture["output"],  # type: ignore[arg-type]
            receipts=receipts,
            output=tmp_path / "receipts.jsonl",
        )


def test_deferred_receipt_mapping_cannot_bypass_bundle_replay(
    tmp_path: Path,
) -> None:
    with pytest.raises(DeferredReceiptError, match="bundle path"):
        write_deferred_receipts(
            bundle={
                "schema_version": "legalforecast.manifest_forecast_bundle.v1",
                "labels_state": "deferred",
                "bundle_sha256": "a" * 64,
            },
            receipts=[],
            output=tmp_path / "receipts.jsonl",
        )


def test_attach_labels_derives_fresh_bound_receipts(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    bundle = _issue(fixture)
    deferred = tmp_path / "deferred.jsonl"
    write_deferred_receipts(
        bundle=fixture["output"],  # type: ignore[arg-type]
        receipts=[
            {
                "bundle_sha256": bundle["bundle_sha256"],
                "candidate_id": "case-1",
                "ablation": "full_packet",
                "packet_sha256": next(
                    iter(bundle["forecast_inputs"]["packet_sha256"].values())
                ),  # type: ignore[index]
                "actual_provider_prompt_sha256": "b" * 64,
                "repeat_index": 0,
                "labels_state": "deferred",
                "scoreable": False,
                "publishable": False,
                "provider_response_sha256": "d" * 64,
            }
        ],
        output=deferred,
    )
    labels = tmp_path / "labels.jsonl"
    label_bytes = _write_jsonl(
        labels,
        [
            {
                "candidate_id": "case-1",
                "unit_id": "unit-1",
                "disposition": "DENY",
                "disposition_evidence": {
                    "disposition_excerpt": "The motion is denied."
                },
            }
        ],
    )
    decisions = tmp_path / "decision-texts.jsonl"
    _write_jsonl(
        decisions,
        [
            {
                "candidate_id": "case-1",
                "text": "The motion is denied.",
                "is_first_written_disposition": True,
            }
        ],
    )
    card = tmp_path / "llm-label-card.json"
    _write(
        card,
        {
            "stage": "llm-label",
            "status": "completed",
            "output_commitments": {"labels": _sha(label_bytes)},
        },
    )
    result = attach_labels(
        bundle=fixture["output"],  # type: ignore[arg-type]
        deferred_receipts=deferred,
        labels=labels,
        decision_texts=decisions,
        finalized_units=fixture["units"],  # type: ignore[arg-type]
        label_run_card=card,
        output_root=tmp_path / "attached",
    )
    assert result.attachment["labels_sha256"] == _sha(label_bytes)
    assert result.bound_receipts[0]["labels_state"] == "bound"
    assert result.bound_receipts[0]["scoreable"] is True
    assert (
        result.bound_receipts[0]["provider_evidence"]["provider_response_sha256"]
        == "d" * 64
    )


def test_attach_rejects_nonverbatim_or_incomplete_labels(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    _issue(fixture)
    labels = tmp_path / "labels.jsonl"
    label_bytes = _write_jsonl(
        labels,
        [
            {
                "candidate_id": "case-1",
                "unit_id": "unit-1",
                "disposition_evidence": {"disposition_excerpt": "not present"},
            }
        ],
    )
    decisions = tmp_path / "decision-texts.jsonl"
    _write_jsonl(
        decisions,
        [
            {
                "candidate_id": "case-1",
                "text": "The motion is denied.",
                "is_first_written_disposition": True,
            }
        ],
    )
    card = tmp_path / "card.json"
    _write(
        card,
        {
            "stage": "llm-label",
            "status": "completed",
            "output_commitments": {"labels": _sha(label_bytes)},
        },
    )
    deferred = tmp_path / "deferred.jsonl"
    _write_jsonl(deferred, [])
    with pytest.raises(DeferredReceiptError, match="coverage differs"):
        attach_labels(
            bundle=fixture["output"],  # type: ignore[arg-type]
            deferred_receipts=deferred,
            labels=labels,
            decision_texts=decisions,
            finalized_units=fixture["units"],  # type: ignore[arg-type]
            label_run_card=card,
            output_root=tmp_path / "attached",
        )

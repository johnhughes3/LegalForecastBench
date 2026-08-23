from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.cli_commands import corpus_manifest as cli_module
from legalforecast.evals.corpus_manifest import deferred_bundle as module
from legalforecast.evals.corpus_manifest.deferred_bundle import (
    ManifestForecastBundleError,
    issue_bundle,
    verify_bundle,
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
            "generated_at": "2026-01-03T00:00:00Z",
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
            "generated_at": "2026-01-03T00:00:00Z",
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
                "cycle_series": "official",
                "allow_no_baselines": True,
                "repeat_policy": {"count": 1, "case_ids": []},
                "shard_schedule": {
                    "shard_count": 1,
                    "dispatch_unit": "model_key_ablation",
                    "shards": [
                        {"model_key": "fixture:model-1", "ablation": "full_packet"}
                    ],
                },
                "attempt_policy": {"authority_backend": "fixture"},
            },
        ),
    )
    freeze_payloads = {
        str(path.relative_to(freeze)): path.read_bytes()
        for path in freeze.rglob("*")
        if path.is_file()
    }
    prompt_replay = {
        "owner_manifest_bytes_sha256": _sha(manifest.read_bytes()),
        "model_registry_sha256": _sha(registry.read_bytes()),
        "run_record_sha256": _sha(
            (forecast / "manifest-mode-run-record.json").read_bytes()
        ),
        "run_inputs_sha256": _sha((forecast / "run-inputs.json").read_bytes()),
        "packet_count": 1,
        "candidate_count": 1,
        "prompt_commitments": {"case-1:full_packet": "b" * 64},
    }
    freeze_payloads["prompt-contract.json"] = _write(
        freeze / "prompt-contract.json", {"prompt_replay": prompt_replay}
    )
    freeze_card = json.loads(
        (freeze / "run-cards/issue-manifest-freeze-inputs.json").read_text()
    )
    freeze_card["input_paths"] = {
        "owner_manifest": str(manifest),
        "model_registry": str(registry),
        "forecast_output_dir": str(forecast),
    }
    _write(freeze / "run-cards/issue-manifest-freeze-inputs.json", freeze_card)
    freeze_payloads["run-cards/issue-manifest-freeze-inputs.json"] = (
        freeze / "run-cards/issue-manifest-freeze-inputs.json"
    ).read_bytes()

    def freeze_verifier(_root: Path) -> SimpleNamespace:
        return SimpleNamespace(
            payloads=freeze_payloads,
            run_card=freeze_card,
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
        "freeze_verifier": freeze_verifier,
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
        output_root=fixture["output"],  # type: ignore[arg-type]
        verify_freeze_inputs=fixture["freeze_verifier"],
    )
    return dict(build.bundle)


def test_issue_verify_and_toctou(fixture: dict[str, Any]) -> None:
    bundle = _issue(fixture)
    assert bundle["labels_state"] == "deferred"
    assert bundle["scoreable"] is False
    assert not hasattr(module, "write_deferred_receipts")
    assert not hasattr(module, "attach_labels")
    assert (
        verify_bundle(
            fixture["output"],  # type: ignore[arg-type]
            verify_freeze_inputs=fixture["freeze_verifier"],
        )
        == bundle
    )
    fixture["policy"].write_bytes(b'{"cycle_id":"cycle-1","changed":true}\n')  # type: ignore[union-attr]
    with pytest.raises(ManifestForecastBundleError, match="bytes changed"):
        verify_bundle(
            fixture["output"],  # type: ignore[arg-type]
            verify_freeze_inputs=fixture["freeze_verifier"],
        )


def _rewrite_rehashed_bundle(
    fixture: dict[str, Any], mutation: dict[str, object]
) -> None:
    bundle_path = fixture["output"] / "bundle-v2.json"
    bundle = json.loads(bundle_path.read_bytes())
    bundle.update(mutation)
    without_digest = dict(bundle)
    without_digest.pop("bundle_sha256", None)
    bundle["bundle_sha256"] = _sha(
        (
            json.dumps(without_digest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    )
    _write(bundle_path, bundle)
    card_path = fixture["output"] / "run-cards/manifest-forecast-bundle-v2.json"
    card = json.loads(card_path.read_bytes())
    card["bundle_sha256"] = bundle["bundle_sha256"]
    _write(card_path, card)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"scoreable": True}, "labels-deferred"),
        ({"publishable": True}, "labels-deferred"),
        ({"provider_calls_made": 1}, "labels-deferred"),
        ({"labels_state": "attached"}, "labels-deferred"),
        ({"labels_sha256": "c" * 64}, "labels-deferred"),
        ({"unexpected": "field"}, "fields are not exact"),
    ],
)
def test_rehashed_semantic_bundle_mutations_are_rejected(
    fixture: dict[str, Any], mutation: dict[str, object], message: str
) -> None:
    _issue(fixture)
    _rewrite_rehashed_bundle(fixture, mutation)

    with pytest.raises(ManifestForecastBundleError, match=message):
        verify_bundle(
            fixture["output"],
            verify_freeze_inputs=fixture["freeze_verifier"],
        )


@pytest.mark.parametrize(
    "packet_mutation",
    [
        {"nested": {"labels": [1]}},
        {"nested": [{"contains_target_outcome": True}]},
        {"outcome_label": "granted"},
    ],
)
def test_nested_outcome_material_is_rejected(
    fixture: dict[str, Any], packet_mutation: dict[str, object]
) -> None:
    packet = next(fixture["forecast"].glob("model-packets/*.json"))
    value = json.loads(packet.read_bytes())
    value.update(packet_mutation)
    _write(packet, value)

    with pytest.raises(ManifestForecastBundleError, match="outcome"):
        _issue(fixture)


def test_bundle_issue_is_create_only(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    with pytest.raises(ManifestForecastBundleError, match="already exists"):
        _issue(fixture)


def test_bundle_issue_rejects_symlink_input(fixture: dict[str, Any]) -> None:
    policy = fixture["policy"]
    target = policy.with_name("policy-target.json")
    policy.rename(target)
    policy.symlink_to(target)

    with pytest.raises(
        ManifestForecastBundleError, match="cannot read execution policy"
    ):
        _issue(fixture)


@pytest.mark.parametrize("verify_existing", [False, True])
def test_bundle_rejects_symlink_packet_for_issue_and_verification(
    fixture: dict[str, Any], verify_existing: bool
) -> None:
    if verify_existing:
        _issue(fixture)
    packet = next(fixture["forecast"].glob("model-packets/*.json"))
    target = packet.with_name("packet-target.json")
    packet.rename(target)
    packet.symlink_to(target.name)

    with pytest.raises(ManifestForecastBundleError, match="cannot read packet"):
        if verify_existing:
            verify_bundle(
                fixture["output"],
                verify_freeze_inputs=fixture["freeze_verifier"],
            )
        else:
            _issue(fixture)


def test_bundle_verifier_rejects_hardlinked_output(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    bundle = fixture["output"] / "bundle-v2.json"
    hardlink = fixture["output"] / "bundle-hardlink.json"
    os.link(bundle, hardlink)

    with pytest.raises(ManifestForecastBundleError, match="one link"):
        verify_bundle(
            fixture["output"],
            verify_freeze_inputs=fixture["freeze_verifier"],
        )


def test_verify_bundle_cli_passes_one_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_root = tmp_path / "bundle"
    calls: list[Path] = []

    def verify(root: Path, *, verify_freeze_inputs: object) -> dict[str, object]:
        calls.append(root)
        assert verify_freeze_inputs is cli_module._verify_freeze_inputs_complete
        return {"verified": True}

    monkeypatch.setattr(
        cli_module, "_VERIFY_BUNDLE", SimpleNamespace(load=lambda: verify)
    )

    assert cli_module.run_verify_bundle(SimpleNamespace(output_root=output_root)) == 0
    assert calls == [output_root]
    assert json.loads(capsys.readouterr().out) == {"verified": True}

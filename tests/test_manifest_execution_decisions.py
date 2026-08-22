# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import execution_decisions as module


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, value: object) -> bytes:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    cycle_id = "cycle-1"
    manifest_digest = "a" * 64
    cases = tuple(SimpleNamespace(candidate_id=f"case-{i}") for i in range(100))
    prediction_units_source = {
        "path": str(tmp_path / "finalized-units.jsonl"),
        "sha256": "d" * 64,
    }
    entries = tuple(
        SimpleNamespace(
            provider="provider",
            model_id=f"model-{i}",
            registry_key=f"provider:model-{i}",
        )
        for i in range(4)
    )
    monkeypatch.setattr(
        module,
        "load_signed_manifest_bytes",
        lambda _payload, expected_digest: SimpleNamespace(
            cycle_id=cycle_id,
            cases=cases,
            prediction_units_source=SimpleNamespace(
                to_record=lambda: prediction_units_source
            ),
        ),
    )
    monkeypatch.setattr(
        module,
        "load_model_registry_bytes",
        lambda _payload: SimpleNamespace(entries=entries),
    )
    monkeypatch.setattr(
        module, "require_official_registry_entries", lambda value: value
    )
    monkeypatch.setattr(
        module,
        "registry_record",
        lambda value: [
            {"provider": entry.provider, "model_id": entry.model_id} for entry in value
        ],
    )
    monkeypatch.setattr(module, "verify_labeling_policy", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(module, "verify_cohort_policy", lambda *args, **kwargs: "ok")
    monkeypatch.setattr(
        module, "verify_observation_manifest", lambda *args, **kwargs: "last"
    )
    monkeypatch.setattr(
        module,
        "load_provider_cycle_caps_bytes",
        lambda *_args, **_kwargs: SimpleNamespace(
            cycle_id=cycle_id,
            execution_attempt_policy=lambda ledger: {
                "authority_backend": "dynamodb",
                "authority_resource_identity_sha256": "b" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "provider_account_caps": [
                    {"provider": "provider", "account": "acct", "cap_microusd": 1}
                ],
                "reservation_ledger_sha256": ledger,
                "max_billable_attempts": 1,
                "failure_threshold": 1,
                "failure_window_seconds": 1,
            },
        ),
    )

    owner = tmp_path / "owner-manifest.json"
    _write(owner, {"cycle_id": cycle_id, "manifest_sha256": manifest_digest})
    registry = tmp_path / "model-registry.json"
    _write(registry, [])
    caps = tmp_path / "provider-caps.json"
    _write(caps, {})
    labeling = tmp_path / "labeling-policy.json"
    _write(labeling, {"policy": {"published_at": "2026-01-01T00:00:00Z"}})
    cohort = tmp_path / "cohort-policy.json"
    _write(cohort, {"policy": {"cycle_id": cycle_id}})
    observation = tmp_path / "cohort-observation.jsonl"
    observation.write_bytes(b"{}\n")

    forecast = tmp_path / "forecast"
    packets: list[dict[str, Any]] = []
    prompt_commitments: dict[str, str] = {}
    for case in cases:
        for ablation in module._ABLATIONS:
            packet = forecast / "model-packets" / f"{case.candidate_id}-{ablation}.json"
            packet_bytes = _write(packet, {"candidate_id": case.candidate_id})
            prompt_sha = "c" * 64
            packets.append(
                {
                    "candidate_id": case.candidate_id,
                    "case_id": case.candidate_id,
                    "ablation": ablation,
                    "packet_object_key": str(packet.relative_to(forecast)),
                    "packet_sha256": _sha(packet_bytes),
                    "prompt_sha256": prompt_sha,
                }
            )
            prompt_commitments[f"{case.candidate_id}:{ablation}"] = prompt_sha
    run_record = {
        "schema_version": "legalforecast.manifest_mode_forecast_run_record.v1",
        "manifest_sha256": manifest_digest,
        "cycle_id": cycle_id,
        "entry_mode": "owner_signed_manifest",
        "case_count": len(cases),
        "packet_count": len(packets),
        "packet_ablations": list(module._ABLATIONS),
        "provider_calls_made": 0,
        "docket_tool_enabled": False,
        "required_eval_run_case_flags": ["--no-docket-tool"],
        "evaluation_models": [
            {"provider": entry.provider, "model_id": entry.model_id}
            for entry in entries
        ],
        "prompt_commitments": prompt_commitments,
        "owner_signature_reference": {
            "bead_id": "legalforecastbench-test",
            "approval_line": (
                "I approve corpus manifest "
                + manifest_digest
                + " as the frozen Cycle 1 forecast corpus."
            ),
        },
        "prediction_units_source": prediction_units_source,
    }
    _write(forecast / "manifest-mode-run-record.json", run_record)
    _write(
        forecast / "run-inputs.json", {"cycle_id": cycle_id, "model_packets": packets}
    )

    beads = tmp_path / "beads-observation.json"
    _write(
        beads,
        {
            "schema_version": module._BEADS_SCHEMA,
            "cycle_id": cycle_id,
            "observed_at": "2026-01-03T00:00:00Z",
            "bead_id": "legalforecastbench-test",
            "manifest_sha256": manifest_digest,
            "model_registry_path": str(registry),
            "raw_observation_sha256": "d" * 64,
            "spend": {"ceiling_usd": 10, "estimate_usd": 1},
            "lines": {
                name: {"text": name, "sha256": _sha(name.encode())}
                for name in ("manifest", "contamination", "final_provider_spend")
            },
            "lifecycle": {
                "production_labeling_started_at": "2026-01-02T00:00:00Z",
                "cohort_policy_published_at": "2026-01-01T00:00:00Z",
                "batch_002_started_at": "2026-01-02T00:00:00Z",
            },
        },
    )
    freeze = tmp_path / "freeze-inputs"
    no_baselines = _write(
        freeze / "no-baselines.json",
        {
            "schema_version": "legalforecast.no_baselines.v1",
            "cycle_id": cycle_id,
            "status": "unavailable",
        },
    )
    _write(
        freeze / "run-cards/issue-manifest-freeze-inputs.json",
        {
            "status": "completed",
            "cycle_id": cycle_id,
            "provider_calls_made": 0,
            "output_commitments": {"no-baselines.json": _sha(no_baselines)},
        },
    )
    return {
        "owner": owner,
        "forecast": forecast,
        "registry": registry,
        "caps": caps,
        "labeling": labeling,
        "cohort": cohort,
        "observation": observation,
        "beads": beads,
        "freeze": freeze,
        "output": tmp_path / "execution-decisions",
    }


def _issue(fixture: dict[str, Any]) -> module.ExecutionDecisionsBuild:
    return module.issue_execution_decisions(
        owner_manifest=fixture["owner"],
        forecast_output_dir=fixture["forecast"],
        model_registry=fixture["registry"],
        provider_cycle_caps=fixture["caps"],
        labeling_policy=fixture["labeling"],
        cohort_policy=fixture["cohort"],
        cohort_observation_manifest=fixture["observation"],
        beads_observation=fixture["beads"],
        freeze_inputs_root=fixture["freeze"],
        output_root=fixture["output"],
    )


def test_issue_and_verify_derives_four_by_two_policy(fixture: dict[str, Any]) -> None:
    build = _issue(fixture)
    assert build.decisions["allow_no_baselines"] is True
    policy = build.execution_policy["policy"]
    assert policy["labeling_policy_sha256"] == _sha(fixture["labeling"].read_bytes())
    assert len(policy["shard_schedule"]["shards"]) == 8
    assert policy["repeat_policy"] == {"case_ids": [], "count": 1}
    verified = module.verify_execution_decisions(fixture["output"])
    assert verified.decisions == build.decisions


def test_issue_is_create_only(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    with pytest.raises(module.ExecutionDecisionsError, match="already exists"):
        _issue(fixture)


def test_packet_drift_is_rejected(fixture: dict[str, Any]) -> None:
    _issue(fixture)
    packet = next(fixture["forecast"].glob("model-packets/*.json"))
    packet.write_bytes(b"changed\n")
    with pytest.raises(module.ExecutionDecisionsError, match="packet changed"):
        module.verify_execution_decisions(fixture["output"])


def test_observation_extra_line_is_rejected(fixture: dict[str, Any]) -> None:
    value = json.loads(fixture["beads"].read_text())
    value["lines"]["extra"] = {"text": "x", "sha256": _sha(b"x")}
    _write(fixture["beads"], value)
    with pytest.raises(module.ExecutionDecisionsError, match="lines are not exact"):
        _issue(fixture)


def test_raw_beads_observation_issuer_binds_exact_lines(
    fixture: dict[str, Any], tmp_path: Path
) -> None:
    raw = tmp_path / "bd-show.json"
    raw_bytes = _write(
        raw,
        {
            "comments": [
                "manifest approval",
                "contamination approval",
                "provider spend approval",
            ]
        },
    )
    output = tmp_path / "beads-wrapper.json"
    wrapper = module.issue_beads_observation(
        raw_observation=raw,
        raw_sha256=_sha(raw_bytes),
        cycle_id="cycle-1",
        manifest_digest="a" * 64,
        model_registry=fixture["registry"],
        bead_id="legalforecastbench-test",
        required_lines={
            "manifest": "manifest approval",
            "contamination": "contamination approval",
            "final_provider_spend": "provider spend approval",
        },
        lifecycle={
            "production_labeling_started_at": "2026-01-02T00:00:00Z",
            "cohort_policy_published_at": "2026-01-01T00:00:00Z",
            "batch_002_started_at": "2026-01-02T00:00:00Z",
        },
        ceiling_usd=10,
        estimate_usd=1,
        output=output,
    )
    assert wrapper["raw_observation_sha256"] == _sha(raw_bytes)
    assert output.exists()

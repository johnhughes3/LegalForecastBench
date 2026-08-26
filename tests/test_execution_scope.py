from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest import execution_decisions, execution_scope
from legalforecast.evals.corpus_manifest.cost_projector import safe_case_id_slug
from legalforecast.evals.corpus_manifest.execution_scope import (
    ExecutionScopeError,
    issue_execution_plan,
    issue_model_execution_scope,
    verify_execution_policy_v3,
    verify_execution_scope,
    verify_execution_scope_runtime,
)
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.per_case_runner import _scope_provider_authority
from legalforecast.protocol.manifest import hash_payload


@pytest.fixture(autouse=True)
def _capture_live_owner_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make every issuer call use the test's live Beads capture seam."""

    monkeypatch.setattr(
        execution_decisions,
        "capture_beads_comments",
        lambda _bead_id: (tmp_path / "owner-evidence.json").read_bytes(),
    )


def _registry_record(model_id: str) -> dict[str, object]:
    return {
        "provider": "openai",
        "model_id": model_id,
        "display_name": "Test model",
        "model_version_or_snapshot": "2026-08-20",
        "release_timestamp": "2026-08-20T09:00:00Z",
        "release_timestamp_source": "test fixture",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-01-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "test fixture",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }


def _write_registry(path: Path, model_id: str = "test-2026") -> str:
    payload = (json.dumps([_registry_record(model_id)], sort_keys=True) + "\n").encode()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _write_cost(
    path: Path,
    *,
    cycle_id: str,
    model_key: str,
    registry_sha256: str,
    run_input_manifest: Path,
) -> None:
    run_inputs = json.loads(run_input_manifest.read_text(encoding="utf-8"))
    packets = run_inputs["model_packets"]
    case_ids = [f"case-{index:03d}" for index in range(100)]
    packet_commitments: list[dict[str, object]] = []
    matrix_rows: list[dict[str, object]] = []
    for packet in packets:
        packet_key = packet["packet_object_key"]
        packet_sha256 = packet["packet_sha256"]
        packet_size_bytes = packet["packet_size_bytes"]
        packet_commitments.append(
            {
                "packet_object_key": packet_key,
                "sha256": packet_sha256,
                "size_bytes": packet_size_bytes,
                "input_tokens": (packet_size_bytes + 3) // 4,
            }
        )
        case_id = packet["case_id"]
        ablation = packet["ablation"]
        matrix_rows.append(
            {
                "case_id": case_id,
                "case_id_slug": safe_case_id_slug(case_id),
                "ablation": ablation,
                "packet_object_key": packet_key,
                "packet_sha256": packet_sha256,
                "model_key": model_key,
                "model_key_slug": model_key.replace(":", "-"),
                "repeat_count": 1,
            }
        )
    provider_matrices = {
        "openai": {"include": matrix_rows},
        "anthropic": {"include": []},
        "gemini": {"include": []},
    }
    record: dict[str, object] = {
        "schema_version": "legalforecast.manifest_cost_projection_receipt.v1",
        "cycle_id": cycle_id,
        "input_commitments": {
            "freeze_bundle": {"sha256": "1" * 64, "size_bytes": 1},
            "freeze_amendment_bundles": [],
            "owner_manifest": {"sha256": "2" * 64, "size_bytes": 1},
            "manifest_run_record": {"sha256": "5" * 64, "size_bytes": 1},
            "run_input_manifest": {
                "sha256": hashlib.sha256(run_input_manifest.read_bytes()).hexdigest(),
                "size_bytes": run_input_manifest.stat().st_size,
            },
            "model_registry": {
                "sha256": registry_sha256,
                "size_bytes": 1,
            },
            "prompt_contract": {"sha256": "6" * 64, "size_bytes": 1},
            "packets": packet_commitments,
        },
        "requested_model_keys": [model_key],
        "requested_ablations": ["full_packet", "metadata_only"],
        "case_ids": case_ids,
        "repeat_sample_case_ids": [],
        "repeat_count": 1,
        "matrix_limit": 800,
        "shard_only": False,
        "max_projected_model_cost_usd": None,
        "matrix": {"include": matrix_rows},
        "provider_counts": {"openai": 200, "anthropic": 0, "gemini": 0},
        "provider_matrices": provider_matrices,
        "case_count": 100,
        "packet_count": 200,
        "request_count": 200,
        "attempt_count": 200,
        "cell_count": 2,
        "matrix_row_count": 200,
        "shard_matrix_row_count": 100,
        "model_count": 1,
        "long_context_surcharge_packet_count": 0,
        "long_context_surcharge_packets": [],
        "long_context_surcharge_packets_json": "[]",
        "projected_model_cost_usd": "0.819250",
        "recommended_max_projected_model_cost_usd": "1.638500",
        "provider_calls_made": 0,
        "aws_activity_executed": False,
        "packet_mutations_made": 0,
        "openai_count": 200,
        "openai_matrix": provider_matrices["openai"],
        "anthropic_count": 0,
        "anthropic_matrix": provider_matrices["anthropic"],
        "gemini_count": 0,
        "gemini_matrix": provider_matrices["gemini"],
    }
    record["receipt_sha256"] = hash_payload(record)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _write_scope_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, str]:
    registry_path = tmp_path / "registry.json"
    registry_sha = _write_registry(registry_path)
    model_key = "openai:test-2026"
    run_input_path = tmp_path / "run-inputs.json"
    run_input_path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-scope-test",
                "model_packets": [
                    {
                        "ablation": ablation,
                        "case_id": case_id,
                        "packet_object_key": (
                            f"model-packets/{case_id}-{ablation}.json"
                        ),
                        "packet_sha256": hashlib.sha256(
                            f"{case_id}:{ablation}".encode()
                        ).hexdigest(),
                        "packet_size_bytes": 4,
                    }
                    for case_id in (f"case-{index:03d}" for index in range(100))
                    for ablation in ("full_packet", "metadata_only")
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    common_inputs = {
        "freeze_bundle_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
        "run_input_manifest_sha256": hashlib.sha256(
            run_input_path.read_bytes()
        ).hexdigest(),
        "model_registry_sha256": registry_sha,
        "run_card_sha256": "4" * 64,
    }
    plan = issue_execution_plan(
        cycle_id="cycle-scope-test",
        model_registry=registry_path,
        common_frozen_inputs=common_inputs,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, sort_keys=True) + "\n", encoding="utf-8")
    cost_path = tmp_path / "cost.json"
    _write_cost(
        cost_path,
        cycle_id="cycle-scope-test",
        model_key=model_key,
        registry_sha256=registry_sha,
        run_input_manifest=run_input_path,
    )
    evidence_path = tmp_path / "owner-evidence.json"
    evidence_path.write_text(
        json.dumps(
            [
                {
                    "id": "owner-1",
                    "issue_id": "scope-test",
                    "author": "John Hughes",
                    "text": (
                        "I approve up to USD 1.50 of provider spend for model "
                        "openai:test-2026 in the Cycle 1 forecast run, estimated "
                        "USD 1.00."
                    ),
                    "created_at": "2026-08-26T09:00:00Z",
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return plan_path, registry_path, run_input_path, cost_path, evidence_path, model_key


def _authority() -> dict[str, object]:
    return {
        "backend": "dynamodb",
        "resource_identity_sha256": "a" * 64,
        "provider": "openai",
        "account": "test-account",
        "cap_microusd": 1_500_000,
    }


def _provider_cycle_caps(
    path: Path,
    *,
    cycle_id: str = "cycle-scope-test",
    cap_usd: str = "1.50",
) -> bytes:
    payload = (
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": cycle_id,
                "spend_authority": {
                    "backend": "dynamodb",
                    "resource_identity_sha256": "a" * 64,
                    "ledger_scope_fields": ["cycle_id", "provider", "account"],
                    "max_billable_attempts": 2,
                    "failure_threshold": 3,
                    "failure_window_seconds": 300,
                },
                "providers": [
                    {
                        "provider": "openai",
                        "account": "test-account",
                        "cycle_reservation_cap_usd": cap_usd,
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    path.write_bytes(payload)
    return payload


def test_issue_execution_plan_supports_provider_free_pre_freeze_mode(
    tmp_path: Path,
) -> None:
    plan_path, registry_path, run_input_path, _cost_path, _evidence_path, _model_key = (
        _write_scope_inputs(tmp_path)
    )
    complete_inputs = json.loads(plan_path.read_text(encoding="utf-8"))["policy"][
        "common_frozen_inputs"
    ]
    pre_freeze_inputs = dict(complete_inputs)
    pre_freeze_inputs.pop("freeze_bundle_sha256")

    plan = issue_execution_plan(
        cycle_id="cycle-scope-test",
        model_registry=registry_path,
        common_frozen_inputs=pre_freeze_inputs,
    )

    assert "freeze_bundle_sha256" not in plan["policy"]["common_frozen_inputs"]
    assert verify_execution_policy_v3(plan) == plan["policy_sha256"]
    assert plan["policy"]["common_frozen_inputs"]["run_input_manifest_sha256"] == (
        hashlib.sha256(run_input_path.read_bytes()).hexdigest()
    )


def test_scope_issuance_fills_freeze_and_derives_authority_from_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    complete_inputs = json.loads(plan_path.read_text(encoding="utf-8"))["policy"][
        "common_frozen_inputs"
    ]
    pre_freeze_plan = issue_execution_plan(
        cycle_id="cycle-scope-test",
        model_registry=registry_path,
        common_frozen_inputs={
            key: value
            for key, value in complete_inputs.items()
            if key != "freeze_bundle_sha256"
        },
    )
    pre_freeze_path = tmp_path / "pre-freeze-plan.json"
    pre_freeze_path.write_text(json.dumps(pre_freeze_plan) + "\n", encoding="utf-8")

    freeze_path = tmp_path / "freeze.json"
    freeze_bytes = b"authenticated final freeze\n"
    freeze_path.write_bytes(freeze_bytes)
    freeze_sha256 = hashlib.sha256(freeze_bytes).hexdigest()
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost["input_commitments"]["freeze_bundle"] = {
        "sha256": freeze_sha256,
        "size_bytes": len(freeze_bytes),
    }
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    caps_path = tmp_path / "provider-cycle-caps.json"
    caps_bytes = _provider_cycle_caps(caps_path)

    class _Artifact:
        sha256 = hashlib.sha256(caps_bytes).hexdigest()
        size_bytes = len(caps_bytes)

    class _Bundle:
        cycle_id = "cycle-scope-test"

        @staticmethod
        def artifact(_name: object) -> _Artifact:
            return _Artifact()

    monkeypatch.setattr(
        execution_scope,
        "verify_freeze_bundle",
        lambda *_args, **_kwargs: _Bundle(),
    )
    scope = issue_model_execution_scope(
        common_plan=pre_freeze_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        freeze_bundle=freeze_path,
        provider_cycle_caps=caps_path,
    )

    assert scope["scope"]["common_frozen_inputs"]["freeze_bundle_sha256"] == (
        freeze_sha256
    )
    assert scope["scope"]["provider_authority"]["cap_microusd"] == 1_500_000
    assert scope["scope"]["provider_authority"]["account"] == "test-account"

    caps_path.write_bytes(caps_bytes + b"tampered")
    with pytest.raises(ExecutionScopeError, match="caps bytes do not match"):
        issue_model_execution_scope(
            common_plan=pre_freeze_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            freeze_bundle=freeze_path,
            provider_cycle_caps=caps_path,
        )

    too_large_caps = _provider_cycle_caps(caps_path, cap_usd="2.00")
    _Artifact.sha256 = hashlib.sha256(too_large_caps).hexdigest()
    _Artifact.size_bytes = len(too_large_caps)
    with pytest.raises(ExecutionScopeError, match="exceeds the model owner ceiling"):
        issue_model_execution_scope(
            common_plan=pre_freeze_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            freeze_bundle=freeze_path,
            provider_cycle_caps=caps_path,
        )


def test_scope_binds_one_model_and_authorizes_both_ablations(tmp_path: Path) -> None:
    (
        plan_path,
        registry_path,
        run_input_path,
        cost_path,
        evidence_path,
        model_key,
    ) = _write_scope_inputs(tmp_path)
    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )

    assert scope["scope"]["selected_ablations"] == ["full_packet", "metadata_only"]
    assert (
        json.loads(plan_path.read_text(encoding="utf-8"))["policy"][
            "allow_no_baselines"
        ]
        is True
    )
    verify_execution_scope(
        scope,
        common_plan=plan_path,
        model_registry=registry_path,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_evidence=evidence_path,
        provider_authority=_authority(),
        expected_model_key=model_key,
        expected_ablation="metadata_only",
    )
    runtime_digest = verify_execution_scope_runtime(
        scope,
        common_plan=json.loads(plan_path.read_text(encoding="utf-8")),
        model_registry=load_model_registry(registry_path),
        model_registry_sha256=hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        expected_model_key=model_key,
        expected_ablation="full_packet",
        expected_scope_sha256=scope["scope_sha256"],
    )
    assert runtime_digest == scope["scope_sha256"]

    with pytest.raises(ExecutionScopeError, match="does not match the current freeze"):
        verify_execution_scope_runtime(
            scope,
            common_plan=json.loads(plan_path.read_text(encoding="utf-8")),
            model_registry=load_model_registry(registry_path),
            model_registry_sha256=hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest(),
            expected_model_key=model_key,
            expected_ablation="full_packet",
            expected_freeze_bundle_sha256="2" * 64,
        )

    with pytest.raises(ExecutionScopeError, match="selected model"):
        verify_execution_scope_runtime(
            scope,
            common_plan=json.loads(plan_path.read_text(encoding="utf-8")),
            model_registry=load_model_registry(registry_path),
            model_registry_sha256=hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest(),
            expected_model_key="openai:other-model",
            expected_ablation="full_packet",
        )
    with pytest.raises(ExecutionScopeError, match="selected ablation"):
        verify_execution_scope_runtime(
            scope,
            common_plan=json.loads(plan_path.read_text(encoding="utf-8")),
            model_registry=load_model_registry(registry_path),
            model_registry_sha256=hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest(),
            expected_model_key=model_key,
            expected_ablation="unsupported",
        )


def test_scope_rejects_cost_and_owner_evidence_drift(tmp_path: Path) -> None:
    (
        plan_path,
        registry_path,
        run_input_path,
        cost_path,
        evidence_path,
        model_key,
    ) = _write_scope_inputs(tmp_path)
    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost["projected_model_cost_usd"] = "1.01"
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ExecutionScopeError, match="cost projection receipt hash"):
        verify_execution_scope(
            scope,
            common_plan=plan_path,
            model_registry=registry_path,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_evidence=evidence_path,
            provider_authority=_authority(),
        )


def test_scope_rejects_run_input_manifest_hash_drift(tmp_path: Path) -> None:
    (
        plan_path,
        registry_path,
        run_input_path,
        cost_path,
        evidence_path,
        model_key,
    ) = _write_scope_inputs(tmp_path)
    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )
    run_input_path.write_bytes(run_input_path.read_bytes() + b" ")

    with pytest.raises(ExecutionScopeError, match="run-input manifest bytes"):
        verify_execution_scope(
            scope,
            common_plan=plan_path,
            model_registry=registry_path,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_evidence=evidence_path,
            provider_authority=_authority(),
        )


def test_scope_rejects_self_authored_packet_token_basis(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost["input_commitments"]["packets"][0]["input_tokens"] += 1
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ExecutionScopeError, match="differs from authenticated"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_rejects_legacy_packet_commitments(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    for packet in cost["input_commitments"]["packets"]:
        packet.pop("input_tokens")
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ExecutionScopeError, match="input_tokens"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_rejects_minimal_self_hashed_cost_receipt(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost.pop("input_commitments")
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(
        ExecutionScopeError, match=r"fields mismatch.*input_commitments"
    ):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_rejects_cost_commitment_drift_from_common_plan(
    tmp_path: Path,
) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost["input_commitments"]["run_input_manifest"]["sha256"] = "0" * 64
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ExecutionScopeError, match="does not match common plan"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_rejects_cost_matrix_row_for_wrong_model(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    cost["matrix"]["include"][0]["model_key"] = "openai:other-model"
    cost["receipt_sha256"] = hash_payload(
        {key: value for key, value in cost.items() if key != "receipt_sha256"}
    )
    cost_path.write_text(json.dumps(cost, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ExecutionScopeError, match="row model_key differs"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_preserves_six_decimal_cost_projection(tmp_path: Path) -> None:
    (
        plan_path,
        registry_path,
        run_input_path,
        cost_path,
        evidence_path,
        model_key,
    ) = _write_scope_inputs(tmp_path)

    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )

    assert scope["scope"]["projected_cost_usd"] == "0.819250"
    verify_execution_scope(
        scope,
        common_plan=plan_path,
        model_registry=registry_path,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_evidence=evidence_path,
        provider_authority=_authority(),
        expected_model_key=model_key,
    )


def test_scope_issuance_captures_live_owner_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        plan_path,
        registry_path,
        run_input_path,
        cost_path,
        evidence_path,
        model_key,
    ) = _write_scope_inputs(tmp_path)
    captured: list[str] = []

    def capture(bead_id: str) -> bytes:
        captured.append(bead_id)
        return evidence_path.read_bytes()

    monkeypatch.setattr(execution_decisions, "capture_beads_comments", capture)
    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )

    assert captured == ["scope-test"]
    assert scope["scope"]["owner_evidence"]["bead_id"] == "scope-test"
    verify_execution_scope(
        scope,
        common_plan=plan_path,
        model_registry=registry_path,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        provider_authority=_authority(),
        expected_model_key=model_key,
    )


def test_scope_issuance_rejects_caller_authored_owner_wrapper(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    with pytest.raises(TypeError, match="unexpected keyword argument 'owner_evidence'"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_evidence={},
            owner_bead_id="scope-test",
            provider_authority=_authority(),
        )


def test_scope_issuance_rejects_wrong_owner_issue_identity(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    with pytest.raises(ExecutionScopeError, match="issue differs from scope"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="wrong-issue",
            provider_authority=_authority(),
        )


def test_scope_rejects_provider_cap_above_owner_ceiling(tmp_path: Path) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    authority = _authority()
    authority["cap_microusd"] = 1_500_001
    with pytest.raises(ExecutionScopeError, match="exceeds the model owner ceiling"):
        issue_model_execution_scope(
            common_plan=plan_path,
            model_registry=registry_path,
            model_key=model_key,
            cost_projection=cost_path,
            run_input_manifest=run_input_path,
            owner_ceiling_usd="1.50",
            owner_bead_id="scope-test",
            provider_authority=authority,
        )


def test_runtime_provider_authority_rejects_scope_identity_drift(
    tmp_path: Path,
) -> None:
    plan_path, registry_path, run_input_path, cost_path, _evidence_path, model_key = (
        _write_scope_inputs(tmp_path)
    )
    scope = issue_model_execution_scope(
        common_plan=plan_path,
        model_registry=registry_path,
        model_key=model_key,
        cost_projection=cost_path,
        run_input_manifest=run_input_path,
        owner_ceiling_usd="1.50",
        owner_bead_id="scope-test",
        provider_authority=_authority(),
    )
    authority = dict(scope["scope"]["provider_authority"])
    authority["scope_identity_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="scope identity is invalid"):
        _scope_provider_authority(
            authority,
            provider="openai",
            model_key=model_key,
            cycle_id="cycle-scope-test",
            projected_cost_usd="1.00",
            owner_ceiling_usd="1.50",
        )

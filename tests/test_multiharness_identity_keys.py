from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.multiharness.identity import (
    HarnessTreatment,
    IdentityError,
    MatchedHarnessIdentity,
    RunIdentity,
    SolverIdentity,
    TaskIdentity,
    derive_matched_harness_identity,
    derive_run_identity,
    derive_solver_identity,
    derive_system_bundle_label,
    derive_task_identity,
    validate_resume_binding,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    LocalCliContractError,
    RunSpec,
    validate_public_execution_receipt,
)

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64
DIGEST_E = "sha256:" + "e" * 64
RAW_DIGEST = "a" * 64


def _task(
    *,
    task_id: str = "lfb.case-1",
    family: str = "legalforecast_mtd",
    scoring_mode: str = "lfb_brier",
    suite_version: str = "cycle-1.fixture",
    task_sha256: str = DIGEST_A,
) -> TaskIdentity:
    return derive_task_identity(
        task_id=task_id,
        family=family,
        scoring_mode=scoring_mode,
        suite_version=suite_version,
        task_sha256=task_sha256,
    )


def _solver(
    *,
    provider: str = "anthropic",
    requested_model: str = "claude-opus-4",
    settings_sha256: str = DIGEST_B,
    served_model: str | None = "claude-opus-4",
) -> SolverIdentity:
    return derive_solver_identity(
        provider=provider,
        requested_model=requested_model,
        settings_sha256=settings_sha256,
        served_model=served_model,
    )


def _run(
    *,
    task: TaskIdentity | None = None,
    solver: SolverIdentity | None = None,
    runtime_policy_sha256: str = DIGEST_C,
    config_sha256: str = DIGEST_D,
    temporal_block: str = "cycle-1",
    order: int = 0,
    repeat_index: int = 0,
) -> RunIdentity:
    return derive_run_identity(
        task=task or _task(),
        solver=solver or _solver(),
        runtime_policy_sha256=runtime_policy_sha256,
        config_sha256=config_sha256,
        temporal_block=temporal_block,
        order=order,
        repeat_index=repeat_index,
    )


def _matched(
    *,
    task: TaskIdentity | None = None,
    solver: SolverIdentity | None = None,
    evaluator_identity: str = "official/lfb-brier",
    temporal_block: str = "cycle-1",
    outer_envelope: str = "clean-native",
    order: int = 0,
    repeat_index: int = 0,
    treatment: HarnessTreatment | None = None,
) -> MatchedHarnessIdentity:
    return derive_matched_harness_identity(
        task=task or _task(),
        solver=solver or _solver(),
        evaluator_identity=evaluator_identity,
        temporal_block=temporal_block,
        outer_envelope=outer_envelope,
        order=order,
        repeat_index=repeat_index,
        treatment=treatment,
    )


def test_identity_records_round_trip() -> None:
    task = _task()
    solver = _solver()
    run = _run(task=task, solver=solver)
    matched = _matched(task=task, solver=solver)
    bundle = derive_system_bundle_label(
        adapter_id="claude-code-clean-native",
        adapter_version="1.0.0",
        requested_model="claude-opus-4",
        family="legalforecast_mtd",
    )

    assert type(task).from_record(task.to_record()) == task
    assert type(solver).from_record(solver.to_record()) == solver
    assert type(run).from_record(run.to_record()) == run
    assert type(matched).from_record(matched.to_record()) == matched
    assert type(bundle).from_record(bundle.to_record()) == bundle


@pytest.mark.parametrize(
    "field",
    ("task_id", "family", "scoring_mode", "suite_version", "task_sha256"),
)
def test_perturbing_one_task_input_changes_key_and_fails_round_trip(field: str) -> None:
    original = _task()
    mutated_values = {
        "task_id": "lfb.case-2",
        "family": "harvey_lab",
        "scoring_mode": "lab_native",
        "suite_version": "cycle-1.other",
        "task_sha256": DIGEST_E,
    }
    mutated = _task(**{field: mutated_values[field]})
    assert mutated.key != original.key

    tampered = original.to_record()
    tampered[field] = mutated_values[field]
    with pytest.raises(IdentityError, match="key does not match"):
        type(original).from_record(tampered)


def test_unresolved_served_model_blocks_matched_harness_not_system_bundle() -> None:
    unresolved = _solver(served_model=None)
    bundle = derive_system_bundle_label(
        adapter_id="claude-code-clean-native",
        adapter_version="1.0.0",
        requested_model="claude-opus-4",
        family="legalforecast_mtd",
    )
    assert bundle.label == (
        "claude-code-clean-native/1.0.0/legalforecast_mtd/claude-opus-4"
    )
    with pytest.raises(IdentityError, match="unresolved served_model"):
        _matched(solver=unresolved)


@pytest.mark.parametrize("sentinel", ("unknown", "unresolved", "*", " none "))
def test_served_model_sentinels_are_ambiguous(sentinel: str) -> None:
    with pytest.raises(IdentityError, match="served_model"):
        _solver(served_model=sentinel)


def test_treatment_does_not_enter_matched_harness_key() -> None:
    left = _matched(
        treatment=HarnessTreatment(prompt_sha256=DIGEST_A, loop_sha256=DIGEST_B)
    )
    right = _matched(
        treatment=HarnessTreatment(
            prompt_sha256=DIGEST_C,
            tool_api_sha256=DIGEST_D,
            tool_implementation_sha256=DIGEST_E,
        )
    )
    assert left.key == right.key


def test_clean_native_and_mcp_mediated_are_distinct() -> None:
    native = _matched(outer_envelope="clean-native")
    mediated = _matched(outer_envelope="mcp-mediated")
    assert native.key != mediated.key
    with pytest.raises(IdentityError, match="outer_envelope"):
        _matched(outer_envelope="clean_native")


def test_alias_fields_are_rejected_as_ambiguous() -> None:
    record = _task().to_record()
    record["task_hash"] = DIGEST_E
    with pytest.raises(IdentityError, match="ambiguous alias"):
        type(_task()).from_record(record)


def test_missing_identity_field_is_named() -> None:
    record = _task().to_record()
    del record["task_sha256"]
    with pytest.raises(IdentityError, match="task_sha256"):
        type(_task()).from_record(record)


def test_raw_digest_without_prefix_is_rejected() -> None:
    with pytest.raises(IdentityError, match="sha256:"):
        _task(task_sha256=RAW_DIGEST)


def test_resume_cannot_cross_task_config_or_policy() -> None:
    prior = _run()
    validate_resume_binding(requested=prior, prior=prior)
    with pytest.raises(IdentityError, match="task identity"):
        validate_resume_binding(
            requested=_run(task=_task(task_sha256=DIGEST_E)), prior=prior
        )
    with pytest.raises(IdentityError, match="config_sha256"):
        validate_resume_binding(requested=_run(config_sha256=DIGEST_E), prior=prior)
    with pytest.raises(IdentityError, match="runtime_policy_sha256"):
        validate_resume_binding(
            requested=_run(runtime_policy_sha256=DIGEST_E), prior=prior
        )


def _run_spec(tmp_path: Path) -> RunSpec:
    return RunSpec(
        spec_id="fixture-spec",
        argv=("claude", "--print"),
        working_directory=tmp_path,
        timeout_seconds=30,
    )


def test_run_spec_and_execution_receipt_round_trip(tmp_path: Path) -> None:
    spec = _run_spec(tmp_path)
    assert RunSpec.from_record(spec.to_record()) == spec
    receipt = ExecutionReceipt.from_transcript(
        spec,
        stdout='{"type":"result"}',
        served_model="claude-opus-4",
        duration_ms=12,
        usage={"output_tokens": 4},
    )
    bound = receipt.with_identity_keys(task=_task(), solver=_solver(), run=_run())
    assert ExecutionReceipt.from_record(bound.to_record()) == bound
    assert bound.task_identity_key == _task().key
    validate_public_execution_receipt(bound.to_public_record())


def test_missing_public_receipt_field_is_named(tmp_path: Path) -> None:
    receipt = ExecutionReceipt.from_transcript(
        _run_spec(tmp_path),
        stdout="ok",
    )
    fixture = receipt.to_public_record()
    del fixture["spec_sha256"]
    with pytest.raises(LocalCliContractError, match="spec_sha256"):
        validate_public_execution_receipt(fixture)


def test_partial_identity_keys_on_receipt_are_rejected(tmp_path: Path) -> None:
    receipt = ExecutionReceipt.from_transcript(_run_spec(tmp_path), stdout="ok")
    with pytest.raises(LocalCliContractError, match="must be set together"):
        ExecutionReceipt(
            receipt_id=receipt.receipt_id,
            spec_sha256=receipt.spec_sha256,
            status=receipt.status,
            returncode=receipt.returncode,
            executable_name=receipt.executable_name,
            stdout=receipt.stdout,
            stderr=receipt.stderr,
            stdout_sha256=receipt.stdout_sha256,
            stderr_sha256=receipt.stderr_sha256,
            task_identity_key=_task().key,
        )

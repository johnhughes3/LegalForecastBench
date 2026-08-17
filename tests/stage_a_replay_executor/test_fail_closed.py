# pyright: reportPrivateUsage=false

"""Fail-closed and durable-receipt coverage for the Stage A executor."""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor import executor as executor_module
from legalforecast.ingestion.stage_a_replay_executor import lineage as lineage_module
from legalforecast.ingestion.stage_a_replay_executor import provider as provider_module
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    StageAReplayExecutorError,
    execute_canonical_stage_a_replay,
    execute_stage_a_replay,
    load_replay_spec,
)
from legalforecast.ingestion.stage_a_replay_executor.journal import (
    terminal_route_available,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from tests.stage_a_replay_executor.authorization_fixtures import (
    refresh_authorization_descriptor,
    rewrite_authorization_artifact,
)
from tests.stage_a_replay_executor.fixtures import (
    FakeSpendMeter,
    read_spec,
    settled_reviewer,
    settled_unitizer,
    terminal_outcome,
    write_spec,
)


def test_runtime_commit_is_resolved_from_the_executor_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> SimpleNamespace:
        observed["cwd"] = kwargs.get("cwd")
        command = cast(list[str], _args[0])
        if command[1] == "status":
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout="a" * 40)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(executor_module.subprocess, "run", fake_run)

    assert executor_module.current_code_commit() == "a" * 40
    assert observed["cwd"] == executor_module.repository_root()


def test_runtime_commit_rejects_dirty_checkout_despite_clean_git_env_decoy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_checkout = tmp_path / "runtime-checkout"
    decoy_checkout = tmp_path / "decoy-checkout"
    runtime_checkout.mkdir()
    subprocess.run(["git", "init", "-q", str(runtime_checkout)], check=True)
    tracked = runtime_checkout / "executor.py"
    tracked.write_text("trusted bytes\n")
    subprocess.run(
        ["git", "-C", str(runtime_checkout), "add", "executor.py"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(runtime_checkout),
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=Stage A test",
            "-c",
            "user.email=stage-a@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "clone", "-q", str(runtime_checkout), str(decoy_checkout)], check=True
    )
    tracked.write_text("modified runtime bytes\n")
    monkeypatch.setenv("GIT_DIR", str(decoy_checkout / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy_checkout))
    monkeypatch.setenv("GIT_INDEX_FILE", str(decoy_checkout / ".git" / "index"))

    with pytest.raises(StageAReplayExecutorError, match="runtime checkout is dirty"):
        executor_module.current_code_commit(cwd=runtime_checkout)


def test_runtime_commit_mismatch_halts_before_provider_access(tmp_path: Path) -> None:
    touched = False

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        nonlocal touched
        touched = True
        raise AssertionError("provider callback must remain closed")

    result = execute_stage_a_replay(
        write_spec(tmp_path, candidate_ids=("cand-a",)),
        unitizer=forbidden,
        reviewer=forbidden,
        spend_meter=cast(Any, forbidden),
        code_commit="1" * 40,
    )

    assert result.halted is True
    assert touched is False
    assert result.to_record()["halt_evidence"] == {
        "status": "halted_on_preflight_failure",
        "reason": "runtime code commit differs from the code commit in replay-spec",
        "failure_type": "RuntimeCommitMismatch",
        "provider_accessed": False,
    }


def test_signed_candidate_set_must_equal_exact_planned_rerun_set(
    tmp_path: Path,
) -> None:
    calls = 0

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("provider must remain closed")

    result = execute_stage_a_replay(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.40",
            candidate_ids=("cand-a", "cand-b"),
            changed_candidate_ids=("cand-a",),
        ),
        unitizer=forbidden,
        reviewer=forbidden,
        spend_meter=cast(Any, forbidden),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert calls == 0
    assert result.plan is None
    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["reason"] == "planned rerun candidates differ from signed authorization"
    assert halt["provider_accessed"] is False


@pytest.mark.parametrize(
    "drift_reason",
    [
        "predecessor Stage A verifier inputs changed",
        "successor Stage A verifier inputs changed",
    ],
)
def test_lineage_toctou_drift_halts_before_provider_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    drift_reason: str,
) -> None:
    parsed = load_replay_spec(write_spec(tmp_path, candidate_ids=("cand-a",)))
    lineage = lineage_module.verify_replay_lineage(parsed)

    def drifted() -> None:
        raise StageAReplayExecutorError(drift_reason)

    def drifted_lineage(_spec: object) -> object:
        return replace(lineage, require_unchanged=drifted)

    monkeypatch.setattr(executor_module, "verify_replay_lineage", drifted_lineage)
    result = execute_stage_a_replay(
        parsed,
        unitizer=settled_unitizer,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(),
        code_commit="0" * 40,
    )

    assert result.halted is True
    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["reason"] == drift_reason
    assert halt["provider_accessed"] is False


def test_unknown_provider_outcome_halts_with_terminal_evidence(tmp_path: Path) -> None:
    def unknown(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        outcome = settled_unitizer(request)
        return replace(outcome, status=cast(Any, "unknown"))

    result = execute_stage_a_replay(
        write_spec(tmp_path, aggregate_ceiling="1.00", candidate_ids=("cand-a",)),
        unitizer=unknown,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(),
        code_commit="0" * 40,
    )

    assert result.halted is True
    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["status"] == "halted_on_provider_outcome"
    assert halt["reason"] == "unitizer candidate cand-a returned an unknown outcome"
    assert halt["provider_accessed"] is True


def test_canonical_provider_mapper_refuses_unknown_audit_status() -> None:
    request = cast(
        CandidateScopedStageARerunRequest,
        SimpleNamespace(candidate_id="cand-a", request_sha256="1" * 64),
    )
    result = SimpleNamespace(audit_records=({"status": "mystery"},), records=())

    with pytest.raises(StageAReplayExecutorError, match="unknown status 'mystery'"):
        provider_module._outcome(request, cast(Any, result))


def test_forbidden_fourth_attempt_halts_and_never_opens_reviewer(
    tmp_path: Path,
) -> None:
    reviewer_calls = 0

    def reviewer(
        request: CandidateScopedStageARerunRequest,
        unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return settled_reviewer(request, unitize)

    result = execute_stage_a_replay(
        write_spec(tmp_path, aggregate_ceiling="1.00", candidate_ids=("cand-a",)),
        unitizer=settled_unitizer,
        reviewer=reviewer,
        spend_meter=FakeSpendMeter(attempts_by_call={("cand-a", "unitizer"): 4}),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert reviewer_calls == 0
    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["reason"] == (
        "unitizer candidate cand-a exceeded its reserved provider attempt authority"
    )
    row = json.loads((tmp_path / "invocations.json").read_text())["invocations"][0]
    assert row["attempt_count"] == 4
    assert row["status"] == "halted"


def test_post_call_per_candidate_overage_halts_with_actual_spend(
    tmp_path: Path,
) -> None:
    result = execute_stage_a_replay(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.50",
            per_candidate_ceiling="0.15",
            candidate_ids=("cand-a",),
        ),
        unitizer=settled_unitizer,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(actual_usd="0.16"),
        code_commit="0" * 40,
    )

    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["status"] == "halted_at_ceiling"
    assert "per-candidate ceiling" in str(halt["reason"])
    assert halt["actual_cost_usd"] == "0.16"
    assert halt["aggregate_spent_usd"] == "0.16"


def test_post_call_aggregate_overage_halts_across_candidates(tmp_path: Path) -> None:
    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        if request.candidate_id == "cand-a":
            outcome = settled_unitizer(request)
            return replace(
                outcome,
                audit={
                    **outcome.audit,
                    "status": "terminal_escalation",
                    "attempt_count": 3,
                },
                status="terminal_escalation",
            )
        return settled_unitizer(request)

    result = execute_stage_a_replay(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.25",
            per_candidate_ceiling="0.20",
            candidate_ids=("cand-a", "cand-b"),
        ),
        unitizer=unitizer,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(
            actual_usd="0.15",
        ),
        code_commit="0" * 40,
    )

    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["status"] == "halted_at_ceiling"
    assert halt["reason"] == "unitizer outcome exceeded the signed aggregate ceiling"
    assert halt["candidate_id"] == "cand-b"
    assert halt["aggregate_spent_usd"] == "0.30"


def test_spend_evidence_failure_preserves_simultaneous_provider_failure(
    tmp_path: Path,
) -> None:
    def provider_failure(
        _request: CandidateScopedStageARerunRequest,
    ) -> StageAStageOutcome:
        raise RuntimeError("provider transport failed")

    result = execute_stage_a_replay(
        write_spec(tmp_path, aggregate_ceiling="1.00", candidate_ids=("cand-a",)),
        unitizer=provider_failure,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(after_error=ValueError("journal snapshot failed")),
        code_commit="0" * 40,
    )

    halt = cast(dict[str, object], result.to_record()["halt_evidence"])
    assert halt["status"] == "halted_on_spend_evidence_failure"
    assert "journal snapshot failed" in str(halt["reason"])
    assert (
        "provider callback also failed: RuntimeError: provider transport failed"
        in str(halt["reason"])
    )
    assert halt["provider_accessed"] is True


def test_reviewer_two_attempt_terminal_route_is_receipted_without_a_third_call(
    tmp_path: Path,
) -> None:
    reviewer_calls = 0

    def reviewer(
        request: CandidateScopedStageARerunRequest,
        _unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        nonlocal reviewer_calls
        reviewer_calls += 1
        return terminal_outcome(request, attempt_count=2)

    result = execute_stage_a_replay(
        write_spec(tmp_path, aggregate_ceiling="0.50", candidate_ids=("cand-a",)),
        unitizer=settled_unitizer,
        reviewer=reviewer,
        spend_meter=FakeSpendMeter(
            attempts_by_call={("cand-a", "reviewer"): 2},
            maximum_new_attempts_by_call={("cand-a", "reviewer"): 2},
        ),
        code_commit="0" * 40,
    )

    assert result.halted is False
    assert reviewer_calls == 1
    rows = json.loads((tmp_path / "invocations.json").read_text())["invocations"]
    reviewer_row = rows[1]
    assert reviewer_row["attempt_count"] == 2
    assert reviewer_row["terminal_route"] == "qsp.attorney_adjudication"
    assert reviewer_row["terminal_evidence"] == {"terminal_escalation_sha256": "9" * 64}


def test_reviewer_two_identical_failures_qualify_without_a_third_attempt(
    tmp_path: Path,
) -> None:
    path = tmp_path / "provider.sqlite3"
    identity = ProviderCallIdentity(
        stage="llm-review-stage-a",
        candidate_id="cand-a",
        model_key="openai:reviewer",
        prompt="frozen reviewer prompt",
        model_registry_sha256="registry-sha256",
        prompt_contract="claim-ontology-v4",
    )
    with ProviderAttemptJournal(
        path,
        identity=identity,
        provider="openai",
        reservation_usd=0.1,
        cycle_cap_usd=1.0,
        cycle_id="cycle-1",
        provider_cycle_caps_sha256="sha256:frozen-caps",
    ) as journal:
        for ordinal in (1, 2):
            if ordinal == 2:
                assert journal.prepare_reconstruction_retry(max_attempts=3) == 2
            journal.run_attempt(1, lambda: {"output": "identical-invalid"})
            journal.settle_attempt(
                journal.durable_attempt_ordinal(1),
                input_tokens=10,
                output_tokens=2,
                actual_cost_usd=0.01,
                raw_output="identical-invalid",
            )
            journal.record_reconstruction_failure(ValueError("same rejection"))

    assert terminal_route_available(
        path,
        identity=identity,
        provider="openai",
        account="default",
        stage="reviewer",
    )
    assert not terminal_route_available(
        path,
        identity=identity,
        provider="openai",
        account="default",
        stage="unitizer",
    )


def test_production_command_rejects_synthetic_inline_packet_authority(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        StageAReplayExecutorError,
        match="production replay-stage-a refuses synthetic fixture authority",
    ):
        execute_canonical_stage_a_replay(write_spec(tmp_path))
    assert not (tmp_path / "plan.json").exists()
    assert not (tmp_path / "receipt.json").exists()


def test_expired_authorization_refuses_before_output_or_provider_access(
    tmp_path: Path,
) -> None:
    path = write_spec(tmp_path)
    rewrite_authorization_artifact(
        path,
        {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
    )

    with pytest.raises(StageAReplayExecutorError, match="authorization has expired"):
        load_replay_spec(path)
    assert not (tmp_path / "receipt.json").exists()


def test_request_artifact_pin_mismatch_refuses_before_lineage(tmp_path: Path) -> None:
    path = write_spec(tmp_path)
    rewrite_authorization_artifact(path, {"request_artifact_sha256": "0" * 64})

    with pytest.raises(StageAReplayExecutorError, match="request artifact differs"):
        load_replay_spec(path)


def test_output_path_may_not_descend_from_an_authenticated_input(
    tmp_path: Path,
) -> None:
    path = write_spec(tmp_path)
    record = read_spec(path)
    authorization = cast(dict[str, object], record["authorization"])
    authorization_artifact = json.loads(
        Path(cast(str, authorization["artifact_path"])).read_text()
    )
    request_path = Path(cast(str, authorization_artifact["request_artifact_path"]))
    cast(dict[str, object], record["outputs"])["plan_path"] = str(
        request_path / "plan.json"
    )
    refresh_authorization_descriptor(path, record, validate=False)

    with pytest.raises(
        StageAReplayExecutorError, match=r"output parent|output overlaps"
    ):
        load_replay_spec(path)


def test_output_paths_may_not_nest_and_fail_after_provider_access(
    tmp_path: Path,
) -> None:
    path = write_spec(tmp_path)
    record = read_spec(path)
    outputs = cast(dict[str, object], record["outputs"])
    nested_root = tmp_path / "nested-output"
    outputs["plan_path"] = str(nested_root)
    outputs["execution_path"] = str(nested_root / "execution.json")
    refresh_authorization_descriptor(path, record, validate=False)

    with pytest.raises(StageAReplayExecutorError, match="must not overlap each other"):
        load_replay_spec(path)

"""Provider-free Codex dispatch through the supported paired runner.

Fake executables prove composition and refusal behavior, not live readiness.
"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.multiharness.codex_cli import CodexCliAdapter, CodexCliAdapterError
from legalforecast.multiharness.codex_cli_harvey_lab import (
    run_codex_cli_clean_native_harvey_lab,
)
from legalforecast.multiharness.harvey_lab_projection import ISSUE_196_LAB_TASK_ID
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.tier0_runner import (
    RecordedOwnerApproval,
    Tier0ExecutableSpec,
    Tier0RunnerError,
    Tier0SpendApproval,
    load_executable_spec,
    load_spend_artifacts,
    run_tier0,
)
from tests.test_harvey_lab_projection import _issue_196_source
from tests.test_multiharness_codex_clean_native_lab_e2e import (
    KEY,
    _hosts,
    _install_codex_wrapper,
)
from tests.test_multiharness_tier0_runner import (
    LAB_BASENAME,
    _approval_object,
    _file_hash,
    _FixtureApprovalAuthority,
    _FixtureEvaluatorAuthority,
    _install_fixture_binaries,
    _install_tier0_caller_roots,
    _patch_fixture_authority,
    _read_json,
    _run_args,
    _signed_approval_record,
    _spec_record,
)


def _codex_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], dict[str, str]]:
    _issue_196_source(tmp_path / "lab")
    env = _install_fixture_binaries(tmp_path)
    _install_codex_wrapper(tmp_path / "bin" / "codex", outcome="success")
    monkeypatch.setenv("PATH", env["PATH"])
    record = _spec_record(env)
    arms = record["arms"]
    assert isinstance(arms, list)
    arms[0].update(
        adapter="codex-cli-offline",
        requested_model="gpt-5.1",
        solver_executable="codex",
        solver_executable_sha256=_file_hash(tmp_path / "bin" / "codex"),
        settings={"reasoning_effort": "high"},
    )
    return record, env


def test_canonical_cli_dispatches_codex_lab_and_retains_private_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record, _env = _codex_fixture(tmp_path, monkeypatch)
    calls = _capture_launches(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-private-canary")
    # Exercise the same spec loader and CLI dispatch as the production command.
    Tier0ExecutableSpec.from_record(record)
    spec_path = tmp_path / "spec.json"
    write_json_object(spec_path, record)
    spec_digest = _file_hash(spec_path)
    approval_path = tmp_path / "approval.json"
    write_json_object(approval_path, _signed_approval_record(spec_digest))
    _patch_fixture_authority(monkeypatch)
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    # Exercise the canonical command's parser/handler seam without coupling
    # another test module to the root CLI compatibility facade.
    parser = ArgumentParser()
    add_multiharness_parser(parser.add_subparsers())
    args = parser.parse_args(
        _run_args(spec_path, approval_path, spec_sha256=spec_digest)
    )
    assert args.handler(args) == 0
    archive_root = tmp_path / "archive"
    archive = _read_json(archive_root / "archive-manifest.json")
    assert archive["spec_sha256"] == spec_digest
    assert [call.argv[0] for call in calls] == [
        "codex",
        "harvey-lab-eval",
        "native-thin",
        "harvey-lab-eval",
    ]
    solver = calls[0]
    assert solver.argv[solver.argv.index("--model") + 1] == "gpt-5.1"
    assert 'model_reasoning_effort="high"' in solver.argv
    assert solver.timeout_seconds == 120  # existing manifest bound wins
    assert solver.argv[solver.argv.index("--sandbox") + 1] == "workspace-write"
    for arm in ("arm-opaque-01", "arm-opaque-02"):
        assert (tmp_path / "private" / arm / "sealed" / LAB_BASENAME).is_file()
        score = _read_json(archive_root / "private" / arm / "score.json")
        assert score["n_criteria"] == score["n_passed"] == 23
    private = archive_root / "private" / "arm-opaque-01"
    metadata = _read_json(private / "run-metadata.json")
    binding = _read_json(private / "receipt-metadata-binding.json")
    execution = _read_json(private / "solver-execution.json")
    assert metadata["run_spec_sha256"] == solver.spec_sha256
    assert metadata["metadata_sha256"] == binding["run_metadata_sha256"]
    assert execution["config_sha256"] == binding["config_sha256"]
    assert metadata["binary_identities"][0]["executable_sha256"] == _file_hash(
        tmp_path / "bin" / "codex"
    )
    public = (archive_root / "public" / "summary.json").read_text()
    assert "gpt-5.1" not in public
    assert str(tmp_path) not in public
    assert "ambient-private-canary" not in public
    assert "thread.started" not in public
    assert not list(
        (tmp_path / "private" / "arm-opaque-01" / "solver").rglob("gold-answers.json")
    )


def _capture_launches(monkeypatch: pytest.MonkeyPatch) -> list[RunSpec]:
    calls: list[RunSpec] = []
    execute = LocalCliExecutionService.execute

    def capture(service: LocalCliExecutionService, spec: RunSpec) -> ExecutionReceipt:
        calls.append(spec)
        return execute(service, spec)

    monkeypatch.setattr(LocalCliExecutionService, "execute", capture)
    return calls


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("adapter", "unknown", "unsupported adapter"),
        ("auth_profile", "published-api-key", "paid spend enforcement"),
        ("auth_profile", "contributor-subscription", "contributor login"),
        ("solver_executable", "claude", "pin the Codex executable"),
        ("command", ["codex", "exec"], "registered adapter"),
        ("settings", {"reasoning_effort": "invalid"}, "reasoning_effort"),
        ("settings", {"max_budget_usd": "1"}, "unsupported Codex arm settings"),
    ],
)
def test_spec_refuses_unsupported_codex_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    error: str,
) -> None:
    record, _env = _codex_fixture(tmp_path, monkeypatch)
    record["arms"][0][field] = value
    calls = _capture_launches(monkeypatch)
    with pytest.raises(Tier0RunnerError, match=error):
        Tier0ExecutableSpec.from_record(record)
    assert calls == []


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("solver_digest", "solver executable identity"),
        ("missing_evaluator", "not on PATH"),
        ("evaluator_digest", "evaluator wrapper hash"),
        ("missing_task", "task.json"),
    ],
)
def test_codex_prerequisites_refuse_before_solver_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    error: str,
) -> None:
    record, env = _codex_fixture(tmp_path, monkeypatch)
    if mutation == "solver_digest":
        record["arms"][0]["solver_executable_sha256"] = "sha256:" + "0" * 64
    elif mutation == "evaluator_digest":
        record["evaluator_wrapper_sha256"] = "sha256:" + "0" * 64
    elif mutation == "missing_evaluator":
        (tmp_path / "bin" / "harvey-lab-eval").unlink()
    else:
        (tmp_path / "lab" / "tasks" / ISSUE_196_LAB_TASK_ID / "task.json").unlink()
    spec, digest = _load_spec(tmp_path, record)
    calls = _capture_launches(monkeypatch)
    with pytest.raises((Tier0RunnerError, ValueError), match=error):
        _run(tmp_path, spec, digest, env)
    assert calls == []
    assert not (tmp_path / "private" / "arm-opaque-01" / "sealed").exists()


def test_paid_codex_refuses_even_with_spend_bindings_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, env = _codex_fixture(tmp_path, monkeypatch)
    record["pricing_snapshot_sha256"] = "sha256:" + "1" * 64
    record["spend_policy_sha256"] = "sha256:" + "2" * 64
    spec, digest = _load_spec(tmp_path, record)
    calls = _capture_launches(monkeypatch)
    with pytest.raises(Tier0RunnerError, match="no supported enforced spend control"):
        _run(tmp_path, spec, digest, env)
    # CLI loads spend artifacts before constructing its paid evaluator factory.
    with pytest.raises(Tier0RunnerError, match="no supported enforced spend control"):
        load_spend_artifacts(tmp_path / "spec.json", spec)
    assert calls == []
    assert not (tmp_path / "private").exists()


def test_paid_codex_cannot_omit_spend_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, env = _codex_fixture(tmp_path, monkeypatch)
    spec, digest = _load_spec(tmp_path, record)
    calls = _capture_launches(monkeypatch)
    approval = Tier0SpendApproval.from_record(
        _signed_approval_record(digest, status="approved")
    )
    with pytest.raises(Tier0RunnerError, match="no supported enforced spend control"):
        _run(tmp_path, spec, digest, env, approval=approval)
    assert calls == []


def test_recorded_owner_approval_does_not_bypass_paid_codex_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_multiharness_spend import _policy

    record, env = _codex_fixture(tmp_path, monkeypatch)
    spec, digest = _load_spec(tmp_path, record)
    calls = _capture_launches(monkeypatch)
    policy = _policy()
    approval = RecordedOwnerApproval(
        spec_sha256=digest,
        owner_approval="Proceed with this bounded run",
        max_cost_usd=policy.experiment.max_cost_usd,
    )
    with pytest.raises(Tier0RunnerError, match="no supported enforced spend control"):
        run_tier0(
            spec=spec,
            spec_sha256=digest,
            approval=approval,
            source_root=tmp_path / "lab",
            private_root=tmp_path / "private",
            archive_root=tmp_path / "archive",
            parent_env=env,
            approval_authority=None,
            evaluator_authority=_FixtureEvaluatorAuthority(),
            spend_policy=policy,
        )
    assert calls == []
    assert not (tmp_path / "private").exists()
    assert not (tmp_path / "archive").exists()


@pytest.mark.parametrize("outcome", ["refusal", "timeout", "crash"])
def test_codex_failure_is_not_retried_or_evaluated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    record, env = _codex_fixture(tmp_path, monkeypatch)
    binary = tmp_path / "bin" / "codex"
    _install_codex_wrapper(binary, outcome=outcome)
    record["arms"][0]["solver_executable_sha256"] = _file_hash(binary)
    # Only the hanging fixture needs deadline injection. Refusal/crash must
    # finish the Python wrapper and fake CLI startup, even under CI contention.
    if outcome == "timeout":
        record["arms"][0]["timeout_seconds"] = 0.2
    spec, digest = _load_spec(tmp_path, record)
    calls = _capture_launches(monkeypatch)
    with pytest.raises(Tier0RunnerError) as raised:
        _run(tmp_path, spec, digest, env)
    assert isinstance(raised.value.__cause__, CodexCliAdapterError)
    assert raised.value.__cause__.failure_class.value == outcome
    assert [call.argv[0] for call in calls] == ["codex"]
    assert not (tmp_path / "private" / "arm-opaque-01" / "sealed").exists()
    assert (tmp_path / "archive" / "private" / "terminal-denial.json").is_file()


def test_codex_executable_swap_after_preflight_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record, env = _codex_fixture(tmp_path, monkeypatch)
    spec, digest = _load_spec(tmp_path, record)
    execute = LocalCliExecutionService.execute
    calls: list[str] = []

    def swap(service: LocalCliExecutionService, run_spec: RunSpec) -> ExecutionReceipt:
        calls.append(run_spec.argv[0])
        binary = tmp_path / "bin" / "codex"
        binary.write_text(binary.read_text() + "\n# changed after preflight\n")
        assert service.executable_pin is not None
        assert service.executable_pin.sha256 != _file_hash(binary).removeprefix(
            "sha256:"
        )
        return execute(service, run_spec)

    monkeypatch.setattr(LocalCliExecutionService, "execute", swap)
    with pytest.raises((Tier0RunnerError, CodexCliAdapterError)):
        _run(tmp_path, spec, digest, env)
    assert calls == ["codex"]
    assert not (tmp_path / "private" / "arm-opaque-01" / "sandbox" / "output").exists()


def test_codex_service_auth_cannot_differ_from_adapter(tmp_path: Path) -> None:
    hosts = _hosts(tmp_path)
    adapter = CodexCliAdapter(
        execution_service=LocalCliExecutionService(auth_profile="published-api-key"),
    )
    with pytest.raises(CodexCliAdapterError, match="auth_profile does not match"):
        run_codex_cli_clean_native_harvey_lab(
            adapter=adapter,
            signer=KEY.sign,
            issuer_public_key=KEY.public_key(),
            **hosts,
        )
    assert not (tmp_path / "sandbox").exists()


def _load_spec(
    tmp_path: Path, record: dict[str, object]
) -> tuple[Tier0ExecutableSpec, str]:
    path = tmp_path / "spec.json"
    write_json_object(path, record)
    return load_executable_spec(path, _file_hash(path))


def _run(
    tmp_path: Path,
    spec: Tier0ExecutableSpec,
    digest: str,
    env: dict[str, str],
    *,
    approval: Tier0SpendApproval | None = None,
) -> object:
    return run_tier0(
        spec=spec,
        spec_sha256=digest,
        approval=approval or _approval_object(digest),
        source_root=tmp_path / "lab",
        private_root=tmp_path / "private",
        archive_root=tmp_path / "archive",
        parent_env=env,
        approval_authority=_FixtureApprovalAuthority(),
        evaluator_authority=_FixtureEvaluatorAuthority(),
    )

"""Provider-free acceptance of the frozen paired Tier-0 command composition."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
import tomllib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from legalforecast._json_io import write_json_object
from legalforecast.cli import main
from legalforecast.multiharness.harvey_lab_authorized_scoring import (
    harvey_lab_issuer_policy_sha256,
)
from legalforecast.multiharness.harvey_lab_evaluator import EVALUATOR_COMMAND_NAME
from legalforecast.multiharness.harvey_lab_projection import project_harvey_lab_suite
from legalforecast.multiharness.local_cli_contracts import ExecutionReceipt, RunSpec
from legalforecast.multiharness.tier0_operator_contract import (
    TIER0_ARCHIVE_ROOT_ENV,
    TIER0_PRIVATE_ROOT_ENV,
    TIER0_SOURCE_ROOT_ENV,
    infisical_evaluator_issuer_secret_loader,
)
from legalforecast.multiharness.tier0_production_factory import (
    REQUIRED_ANTHROPIC_SDK_VERSION,
)
from legalforecast.multiharness.tier0_runner import (
    TIER0_SPEND_APPROVAL_SCHEMA_VERSION,
    Tier0ArmSpec,
    Tier0EvaluatorConfiguration,
    Tier0EvaluatorProvenanceFactory,
    Tier0ExecutableSpec,
    Tier0RunnerError,
    Tier0SpendApproval,
    _identities_match,
    load_approved_tier0_approval_authority,
    load_detached_approval,
    load_executable_spec,
    run_tier0,
    tier0_approval_issuer_policy_sha256,
)
from tests.test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from tests.test_multiharness_claude_clean_native_lab_e2e import (
    FAKE_EVALUATOR,
    FAKE_LAB_CLI,
    _install_script,
    _install_trampoline,
)

APPROVAL_KEY = Ed25519PrivateKey.from_private_bytes(b"A" * 32)
EVALUATOR_KEY = Ed25519PrivateKey.from_private_bytes(b"L" * 32)
LAB_BASENAME = "issue-identification-memo.docx"


def test_tier0_optional_extra_matches_the_frozen_anthropic_sdk_version() -> None:
    """Keep the installable Tier-0 extra aligned with the paid-path freeze."""

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["optional-dependencies"]["tier0-judge-adapter"] == [
        f"anthropic=={REQUIRED_ANTHROPIC_SDK_VERSION}"
    ]


class _FixtureApprovalAuthority:
    public_key = APPROVAL_KEY.public_key()
    issuer_id = "fixture-tier0-approval-authority"
    key_id = "fixture-tier0-approver-v1"
    issuer_policy_sha256 = tier0_approval_issuer_policy_sha256()

    @classmethod
    def to_record(cls) -> dict[str, object]:
        return {
            "issuer_id": cls.issuer_id,
            "key_id": cls.key_id,
            "issuer_policy_sha256": cls.issuer_policy_sha256,
        }


class _FixtureEvaluatorAuthority:
    public_key = EVALUATOR_KEY.public_key()
    issuer_id = "fixture-evaluator-authority"
    key_id = "fixture-evaluator-v1"
    issuer_policy_sha256 = harvey_lab_issuer_policy_sha256()

    @staticmethod
    def sign(payload: bytes) -> bytes:
        return EVALUATOR_KEY.sign(payload)

    @classmethod
    def to_record(cls) -> dict[str, object]:
        return {
            "issuer_id": cls.issuer_id,
            "key_id": cls.key_id,
            "issuer_policy_sha256": cls.issuer_policy_sha256,
        }


def test_cli_full_paired_tier0_fake_binary_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The supported command runs both arms and emits archive receipts."""

    _issue_196_source(tmp_path / "lab")
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_record = _spec_record(env)
    spec_path = tmp_path / "executable-spec.json"
    write_json_object(spec_path, spec_record)
    spec_sha256 = _file_hash(spec_path)
    approval_path = tmp_path / "detached-approval.json"
    write_json_object(approval_path, _signed_approval_record(spec_sha256))

    import legalforecast.multiharness.tier0_runner as runner

    monkeypatch.setattr(
        runner,
        "load_approved_tier0_approval_authority",
        lambda: _FixtureApprovalAuthority(),
    )
    monkeypatch.setattr(
        runner,
        "load_approved_issuer_authority",
        lambda **_kwargs: _FixtureEvaluatorAuthority(),
    )
    import legalforecast.multiharness.cli as multiharness_cli

    monkeypatch.setattr(
        multiharness_cli,
        "load_approved_tier0_approval_authority",
        lambda: _FixtureApprovalAuthority(),
    )
    seen_loader: dict[str, object] = {}

    def _capture_authority(**kwargs: object) -> _FixtureEvaluatorAuthority:
        seen_loader.update(kwargs)
        return _FixtureEvaluatorAuthority()

    monkeypatch.setattr(
        multiharness_cli,
        "load_approved_issuer_authority",
        _capture_authority,
    )
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    assert (
        main(
            [
                "multiharness",
                "tier0",
                "run",
                "--spec",
                str(spec_path),
                "--spec-sha256",
                spec_sha256,
                "--approval",
                str(approval_path),
            ]
        )
        == 0
    )
    assert seen_loader.get("secret_loader") is infisical_evaluator_issuer_secret_loader
    assert not (tmp_path / ".tier0-runtime").exists()
    private_root = tmp_path / "private"
    archive_root = tmp_path / "archive"
    archive = _read_json(archive_root / "archive-manifest.json")
    summary = _read_json(archive_root / "public" / "summary.json")
    assert archive["spec_sha256"] == spec_sha256
    assert archive["matched"] is False
    assert (archive_root / "public" / "summary.json").is_file()
    assert (
        "Preliminary — one task pair, operator-run, not independently reproducible"
        in summary["claim_language"]
    )
    assert all("adapter" not in arm and "arm_id" not in arm for arm in summary["arms"])
    manifest_paths = {entry["path"] for entry in archive["files"]}
    assert "private/review-mapping.json" in manifest_paths
    assert "private/evaluator-issuer-authority.json" in manifest_paths
    assert "private/tier0-approval-authority.json" in manifest_paths
    evaluator_authority = _read_json(
        archive_root / "private" / "evaluator-issuer-authority.json"
    )
    approval_authority = _read_json(
        archive_root / "private" / "tier0-approval-authority.json"
    )
    assert evaluator_authority["issuer_id"] == _FixtureEvaluatorAuthority.issuer_id
    assert approval_authority["issuer_id"] == _FixtureApprovalAuthority.issuer_id
    assert any(path.endswith("/evaluation-raw-result.json") for path in manifest_paths)
    assert any(
        "/retained-artifacts/arm-opaque-01/sealed/" in path for path in manifest_paths
    )
    assert any(
        "/retained-artifacts/evaluator/overlay/arm-opaque-01/" in path
        for path in manifest_paths
    )
    for arm_id in ("arm-opaque-01", "arm-opaque-02"):
        assert (archive_root / "private" / arm_id / "score.json").is_file()
    assert (private_root / "arm-opaque-01" / "sealed" / LAB_BASENAME).is_file()
    assert (private_root / "arm-opaque-02" / "sealed" / LAB_BASENAME).is_file()


def test_tier0_cli_requires_caller_supplied_empty_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _issue_196_source(tmp_path / "lab")
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path, approval_path, spec_sha256 = _write_spec_and_approval(tmp_path, env)
    _patch_fixture_authority(monkeypatch)
    monkeypatch.delenv(TIER0_SOURCE_ROOT_ENV, raising=False)
    monkeypatch.delenv(TIER0_PRIVATE_ROOT_ENV, raising=False)
    monkeypatch.delenv(TIER0_ARCHIVE_ROOT_ENV, raising=False)
    assert main(_run_args(spec_path, approval_path, spec_sha256=spec_sha256)) == 2
    assert not (tmp_path / ".tier0-runtime").exists()


def test_tier0_cli_refuses_nonempty_private_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _issue_196_source(tmp_path / "lab")
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path, approval_path, spec_sha256 = _write_spec_and_approval(tmp_path, env)
    _patch_fixture_authority(monkeypatch)
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "stale.txt").write_text("occupied", encoding="utf-8")
    assert main(_run_args(spec_path, approval_path, spec_sha256=spec_sha256)) == 2


def test_tier0_cli_pending_authority_fails_before_infisical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _issue_196_source(tmp_path / "lab")
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path, approval_path, spec_sha256 = _write_spec_and_approval(tmp_path, env)
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    import legalforecast.multiharness.cli as multiharness_cli

    monkeypatch.setattr(
        multiharness_cli,
        "load_approved_tier0_approval_authority",
        lambda: _FixtureApprovalAuthority(),
    )
    called = False

    def _forbidden_loader(_environment: str, _path: str, _name: str) -> str:
        nonlocal called
        called = True
        raise AssertionError("Infisical must not be contacted")

    monkeypatch.setattr(
        multiharness_cli,
        "infisical_evaluator_issuer_secret_loader",
        _forbidden_loader,
    )
    assert main(_run_args(spec_path, approval_path, spec_sha256=spec_sha256)) == 2
    assert called is False


def test_tier0_spec_hash_and_approval_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path = tmp_path / "spec.json"
    write_json_object(spec_path, _spec_record(env))
    spec_sha256 = _file_hash(spec_path)
    spec, loaded_hash = load_executable_spec(spec_path, spec_sha256)
    assert loaded_hash == spec_sha256
    approval_path = tmp_path / "approval.json"
    write_json_object(
        approval_path,
        _signed_approval_record("sha256:" + "0" * 64),
    )
    try:
        load_detached_approval(
            approval_path,
            spec_sha256=spec_sha256,
            authority=_FixtureApprovalAuthority(),
        )
    except ValueError as exc:
        assert "different executable spec" in str(exc)
    else:
        raise AssertionError("mismatched detached approval unexpectedly loaded")
    assert spec.experiment_id == "tier0-fixture"


def test_tier0_detached_approval_rejects_tampering_and_unknown_issuer(
    tmp_path: Path,
) -> None:
    spec_sha256 = "sha256:" + "1" * 64
    tampered = _signed_approval_record(spec_sha256)
    tampered["status"] = "approved"
    tampered_path = tmp_path / "tampered.json"
    write_json_object(tampered_path, tampered)
    with pytest.raises(Tier0RunnerError, match="signature is invalid"):
        load_detached_approval(
            tampered_path,
            spec_sha256=spec_sha256,
            authority=_FixtureApprovalAuthority(),
        )

    unknown = _signed_approval_record(spec_sha256)
    unknown["authority"] = "unapproved-issuer"
    unknown_path = tmp_path / "unknown.json"
    write_json_object(unknown_path, unknown)
    with pytest.raises(Tier0RunnerError, match="issuer is not approved"):
        load_detached_approval(
            unknown_path,
            spec_sha256=spec_sha256,
            authority=_FixtureApprovalAuthority(),
        )


def test_tier0_detached_approval_rejects_evaluator_key_signature(
    tmp_path: Path,
) -> None:
    spec_sha256 = "sha256:" + "1" * 64
    forged = _signed_approval_record(spec_sha256, signing_key=EVALUATOR_KEY)
    forged_path = tmp_path / "evaluator-signed-approval.json"
    write_json_object(forged_path, forged)
    with pytest.raises(Tier0RunnerError, match="signature is invalid"):
        load_detached_approval(
            forged_path,
            spec_sha256=spec_sha256,
            authority=_FixtureApprovalAuthority(),
        )


def test_default_tier0_approval_authority_fails_closed_until_provisioned() -> None:
    """The public default cannot authorize a run before human key provisioning."""

    with pytest.raises(Tier0RunnerError, match="pending human provisioning"):
        load_approved_tier0_approval_authority()


def test_tier0_rejects_a_signing_authority_as_approval_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path = tmp_path / "spec.json"
    write_json_object(spec_path, _spec_record(env))
    spec, spec_sha256 = load_executable_spec(spec_path, _file_hash(spec_path))
    with pytest.raises(Tier0RunnerError, match="public-only"):
        run_tier0(
            spec=spec,
            spec_sha256=spec_sha256,
            approval=_approval_object(spec_sha256),
            source_root=tmp_path / "lab",
            private_root=tmp_path / "private",
            archive_root=tmp_path / "archive",
            approval_authority=_FixtureEvaluatorAuthority(),
            evaluator_authority=_FixtureEvaluatorAuthority(),
        )


def test_tier0_wrong_spec_hash_fails_before_any_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path, approval_path, _spec_sha256 = _write_spec_and_approval(tmp_path, env)
    assert (
        main(
            _run_args(
                spec_path,
                approval_path,
                spec_sha256="sha256:" + "0" * 64,
            )
        )
        == 2
    )
    assert not (tmp_path / "private").exists()
    assert not (tmp_path / "archive").exists()


def test_tier0_wrong_solver_hash_fails_before_any_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    record = _spec_record(env)
    arms = record["arms"]
    assert isinstance(arms, list)
    first_arm = arms[0]
    assert isinstance(first_arm, dict)
    first_arm["solver_executable_sha256"] = "sha256:" + "0" * 64
    spec_path, approval_path, spec_sha256 = _write_spec_and_approval(
        tmp_path, env, record=record
    )
    _patch_fixture_authority(monkeypatch)
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    assert (
        main(
            _run_args(
                spec_path,
                approval_path,
                spec_sha256=spec_sha256,
            )
        )
        == 2
    )
    assert not (tmp_path / "private").exists()
    assert not (tmp_path / "archive").exists()


def test_tier0_wrong_wrapper_hash_fails_before_any_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    record = _spec_record(env)
    record["evaluator_wrapper_sha256"] = "sha256:" + "0" * 64
    spec_path, approval_path, spec_sha256 = _write_spec_and_approval(
        tmp_path, env, record=record
    )
    _patch_fixture_authority(monkeypatch)
    _install_tier0_caller_roots(monkeypatch, tmp_path)
    assert (
        main(
            _run_args(
                spec_path,
                approval_path,
                spec_sha256=spec_sha256,
            )
        )
        == 2
    )
    assert not (tmp_path / "private").exists()
    assert not (tmp_path / "archive").exists()


def test_tier0_mutated_loaded_spec_is_rejected_before_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _install_fixture_binaries(tmp_path)
    monkeypatch.setenv("PATH", env["PATH"])
    spec_path = tmp_path / "spec.json"
    write_json_object(spec_path, _spec_record(env))
    spec, spec_sha256 = load_executable_spec(spec_path, _file_hash(spec_path))
    mutated = replace(spec, experiment_id="mutated-after-load")
    approval = _approval_object(spec_sha256)
    with pytest.raises(Tier0RunnerError, match="mutated after loading"):
        run_tier0(
            spec=mutated,
            spec_sha256=spec_sha256,
            approval=approval,
            source_root=tmp_path / "lab",
            private_root=tmp_path / "private",
            archive_root=tmp_path / "archive",
            approval_authority=_FixtureApprovalAuthority(),
            evaluator_authority=_FixtureEvaluatorAuthority(),
        )
    assert not (tmp_path / "private").exists()
    assert not (tmp_path / "archive").exists()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--model", "anything"],
        ["--source-root", "/tmp/source"],
        ["--private-root", "/tmp/private"],
        ["--archive-root", "/tmp/archive"],
        ["--dry-run"],
    ],
)
def test_tier0_cli_rejects_run_varying_flags(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["multiharness", "tier0", "run", *arguments])
    assert exc_info.value.code == 2


def test_tier0_matched_identity_requires_byte_identical_projection(
    tmp_path: Path,
) -> None:
    source_root = _issue_196_source(tmp_path / "lab")
    first = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=tmp_path / "solver-a",
        evaluator_private_root=tmp_path / "private-a",
        pin=FIXTURE_PIN,
        lab_task_ids=("employment-labor/identify-issues-in-counterparty-motion-brief",),
    )
    second = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=tmp_path / "solver-b",
        evaluator_private_root=tmp_path / "private-b",
        pin=FIXTURE_PIN,
        lab_task_ids=("employment-labor/identify-issues-in-counterparty-motion-brief",),
    )
    result_one = _identity_result(first, "claude")
    result_two = _identity_result(second, "native-thin")
    spec = _identity_spec()
    assert _identities_match((result_one, result_two), spec)
    document = next(
        path
        for path in second.solver_root.rglob("*")
        if path.name == "briggs-declaration.docx"
    )
    document.chmod(document.stat().st_mode | stat.S_IWUSR)
    document.write_bytes(document.read_bytes() + b"drift")
    assert not _identities_match((result_one, result_two), spec)


def test_tier0_matching_ignores_arm_specific_evaluation_hashes(
    tmp_path: Path,
) -> None:
    source_root = _issue_196_source(tmp_path / "lab")
    first = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=tmp_path / "solver-a",
        evaluator_private_root=tmp_path / "private-a",
        pin=FIXTURE_PIN,
        lab_task_ids=("employment-labor/identify-issues-in-counterparty-motion-brief",),
    )
    second = project_harvey_lab_suite(
        source_root=source_root,
        solver_root=tmp_path / "solver-b",
        evaluator_private_root=tmp_path / "private-b",
        pin=FIXTURE_PIN,
        lab_task_ids=("employment-labor/identify-issues-in-counterparty-motion-brief",),
    )
    result_one = _identity_result(first, "claude")
    result_two = _identity_result(second, "native-thin")
    result_two.evaluation.spec.deliverable_manifest_sha256 = "sha256:" + "1" * 64
    result_two.evaluation.spec.deliverable_tree_sha256 = "sha256:" + "2" * 64
    result_two.evaluation.spec.run_sha256 = "sha256:" + "3" * 64
    spec = _identity_spec()

    assert _identities_match((result_one, result_two), spec)

    result_two.evaluation.spec.config_sha256 = "sha256:" + "4" * 64
    assert not _identities_match((result_one, result_two), spec)


def test_tier0_provenance_factory_uses_each_arm_execution_accounting(
    tmp_path: Path,
) -> None:
    digest = "sha256:" + "a" * 64
    configuration = Tier0EvaluatorConfiguration(
        evaluator_repository="https://example.com/evaluator",
        evaluator_commit="b" * 40,
        evaluator_tree="c" * 40,
        evaluator_file_manifest_sha256=digest,
        evaluator_image_digest=digest,
        judge_requested_identity="provider/judge@v1",
        judge_settings_sha256=digest,
        judge_prompt_sha256=digest,
        judge_output_schema_sha256=digest,
        runtime_policy_sha256=digest,
        egress_policy_sha256=digest,
        resource_policy_sha256=digest,
        token_accounting_policy_sha256=digest,
        cost_basis="provider_reported",
    )
    factory = Tier0EvaluatorProvenanceFactory(configuration)
    run_spec = RunSpec(
        spec_id="provenance-fixture",
        argv=("judge",),
        working_directory=tmp_path,
    )
    first_execution = ExecutionReceipt.from_transcript(
        run_spec,
        stdout="first",
        served_model="provider/judge@v1",
        usage={"input_tokens": 10, "output_tokens": 5},
        cost_usd=0.000012,
    )
    second_execution = ExecutionReceipt.from_transcript(
        run_spec,
        stdout="second",
        served_model="provider/judge@v1",
        usage={"input_tokens": 20, "output_tokens": 7},
        cost_usd=0.000034,
    )

    first = factory("arm-opaque-01", first_execution)
    second = factory("arm-opaque-02", second_execution)

    assert first.evaluator_repository == second.evaluator_repository
    assert first.token_usage.input_tokens.value == 10
    assert first.token_usage.output_tokens.value == 5
    assert first.cost.amount_microusd == 12
    assert second.token_usage.input_tokens.value == 20
    assert second.token_usage.output_tokens.value == 7
    assert second.cost.amount_microusd == 34


def _install_tier0_caller_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "lab"
    private_root = tmp_path / "private"
    archive_root = tmp_path / "archive"
    source_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(TIER0_SOURCE_ROOT_ENV, str(source_root))
    monkeypatch.setenv(TIER0_PRIVATE_ROOT_ENV, str(private_root))
    monkeypatch.setenv(TIER0_ARCHIVE_ROOT_ENV, str(archive_root))
    return source_root, private_root, archive_root


def _write_spec_and_approval(
    tmp_path: Path,
    env: dict[str, str],
    *,
    record: dict[str, object] | None = None,
) -> tuple[Path, Path, str]:
    spec_path = tmp_path / "executable-spec.json"
    write_json_object(spec_path, _spec_record(env) if record is None else record)
    spec_sha256 = _file_hash(spec_path)
    approval_path = tmp_path / "detached-approval.json"
    write_json_object(approval_path, _signed_approval_record(spec_sha256))
    return spec_path, approval_path, spec_sha256


def _run_args(
    spec_path: Path,
    approval_path: Path,
    *,
    spec_sha256: str,
) -> list[str]:
    return [
        "multiharness",
        "tier0",
        "run",
        "--spec",
        str(spec_path),
        "--spec-sha256",
        spec_sha256,
        "--approval",
        str(approval_path),
    ]


def _patch_fixture_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    import legalforecast.multiharness.cli as multiharness_cli
    import legalforecast.multiharness.tier0_runner as runner

    monkeypatch.setattr(
        runner,
        "load_approved_tier0_approval_authority",
        _FixtureApprovalAuthority,
    )
    monkeypatch.setattr(
        runner,
        "load_approved_issuer_authority",
        lambda **_kwargs: _FixtureEvaluatorAuthority(),
    )
    monkeypatch.setattr(
        multiharness_cli,
        "load_approved_tier0_approval_authority",
        _FixtureApprovalAuthority,
    )
    monkeypatch.setattr(
        multiharness_cli,
        "load_approved_issuer_authority",
        lambda **_kwargs: _FixtureEvaluatorAuthority(),
    )


def _identity_result(projection: object, executable_name: str) -> object:
    digest = "sha256:" + "0" * 64
    return SimpleNamespace(
        projection=projection,
        auth_profile="fixture-none",
        solver_execution=SimpleNamespace(
            served_model="claude-sonnet-4-6",
            config_sha256=digest,
            runtime_policy_sha256=digest,
            task_identity_key=digest,
            solver_identity_key=digest,
            run_identity_key=digest,
            temporal_block="tier0",
            order=0,
            repeat_index=0,
            executable_name=executable_name,
            executable_version="fixture-v1",
        ),
        evaluation=SimpleNamespace(
            spec=SimpleNamespace(
                schema_version="evaluation-v1",
                evaluation_id="harvey-lab-employment-v1",
                deliverable_manifest_sha256=digest,
                deliverable_tree_sha256=digest,
                task_sha256=digest,
                run_sha256=digest,
                config_sha256=digest,
                evaluator_repository="https://example.com/lab",
                evaluator_commit="a" * 40,
                evaluator_tree="b" * 40,
                evaluator_file_manifest_sha256="sha256:" + "1" * 64,
                evaluator_image_digest="sha256:" + "2" * 64,
                wrapper_sha256="sha256:" + "3" * 64,
                rubric_sha256="sha256:" + "4" * 64,
                criteria_sha256="sha256:" + "5" * 64,
                aggregation_sha256="sha256:" + "6" * 64,
                judge_requested_identity="fixture-judge",
                judge_settings_sha256="sha256:" + "7" * 64,
                judge_prompt_sha256="sha256:" + "8" * 64,
                judge_output_schema_sha256="sha256:" + "9" * 64,
                runtime_policy_sha256="sha256:" + "a" * 64,
                egress_policy_sha256="sha256:" + "b" * 64,
                resource_policy_sha256="sha256:" + "c" * 64,
                token_accounting_policy_sha256="sha256:" + "d" * 64,
            ),
            receipt=SimpleNamespace(judge_resolved_identity="judge/provider@v1"),
        ),
    )


def _identity_spec() -> Tier0ExecutableSpec:
    digest = "sha256:" + "0" * 64
    return Tier0ExecutableSpec(
        experiment_id="identity-fixture",
        source_pin=FIXTURE_PIN,
        evaluator_command="evaluator",
        evaluator_wrapper_sha256=digest,
        issuer_key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        arms=(
            Tier0ArmSpec(
                arm_id="arm-opaque-01",
                adapter="claude-code-clean-native",
                auth_profile="fixture-none",
                requested_model="claude-sonnet-4-6",
                solver_executable="claude",
                solver_executable_sha256=digest,
                settings={},
            ),
            Tier0ArmSpec(
                arm_id="arm-opaque-02",
                adapter="harvey-lab",
                auth_profile="fixture-none",
                requested_model="claude-sonnet-4-6",
                solver_executable="native-thin",
                solver_executable_sha256=digest,
                command=("native-thin", "{sandbox_root}"),
                settings={},
            ),
        ),
    )


def _spec_record(env: dict[str, str]) -> dict[str, object]:
    del env
    spec = Tier0ExecutableSpec(
        experiment_id="tier0-fixture",
        source_pin=FIXTURE_PIN,
        evaluator_command=EVALUATOR_COMMAND_NAME,
        evaluator_wrapper_sha256=_path_hash_for_name("harvey-lab-eval"),
        issuer_key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=harvey_lab_issuer_policy_sha256(),
        arms=(
            Tier0ArmSpec(
                arm_id="arm-opaque-01",
                adapter="claude-code-clean-native",
                auth_profile="fixture-none",
                requested_model="claude-sonnet-4-6",
                solver_executable="claude",
                solver_executable_sha256=_path_hash_for_name("claude"),
                settings={"sandbox": "fixture"},
            ),
            Tier0ArmSpec(
                arm_id="arm-opaque-02",
                adapter="harvey-lab",
                auth_profile="fixture-none",
                requested_model="claude-sonnet-4-6",
                solver_executable="native-thin",
                solver_executable_sha256=_path_hash_for_name("native-thin"),
                command=("native-thin", "{sandbox_root}"),
                settings={"sandbox": "fixture"},
            ),
        ),
    )
    return spec.to_record()


def _install_fixture_binaries(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_trampoline(bin_dir / "claude", FAKE_LAB_CLI)
    _install_script(bin_dir / EVALUATOR_COMMAND_NAME, FAKE_EVALUATOR)
    native = bin_dir / "native-thin"
    native.write_text(
        "#!" + sys.executable + "\n"
        "import io, sys, zipfile\n"
        "from pathlib import Path\n"
        "output = Path(sys.argv[1]) / 'output'\n"
        "output.mkdir(parents=True, exist_ok=True)\n"
        "payload = io.BytesIO()\n"
        "with zipfile.ZipFile(payload, 'w') as archive:\n"
        "    archive.writestr('[Content_Types].xml', '<Types></Types>')\n"
        "    archive.writestr('word/document.xml', '<w:document></w:document>')\n"
        f"(output / {LAB_BASENAME!r}).write_bytes(payload.getvalue())\n",
        encoding="utf-8",
    )
    native.chmod(native.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}"}


def _path_hash_for_name(name: str) -> str:
    # The fixture spec is written after the test installs these names. The
    # helper is patched by the test through the current PATH.
    import shutil

    path = shutil.which(name)
    if path is None:
        raise AssertionError(f"fixture executable missing: {name}")
    return _file_hash(Path(path))


def _file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _approval_object(spec_sha256: str) -> Tier0SpendApproval:
    record = _signed_approval_record(spec_sha256)
    return Tier0SpendApproval.from_record(record)


def _signed_approval_record(
    spec_sha256: str,
    *,
    status: str = "provider_free",
    signing_key: Ed25519PrivateKey = APPROVAL_KEY,
) -> dict[str, object]:
    signing = {
        "schema_version": TIER0_SPEND_APPROVAL_SCHEMA_VERSION,
        "approval_id": "fixture-approval",
        "spec_sha256": spec_sha256,
        "status": status,
        "authority": _FixtureApprovalAuthority.issuer_id,
        "issuer_key_id": _FixtureApprovalAuthority.key_id,
        "issuer_policy_sha256": _FixtureApprovalAuthority.issuer_policy_sha256,
    }
    payload = json.dumps(
        signing, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        **signing,
        "signature": base64.b64encode(signing_key.sign(payload)).decode("ascii"),
    }


def _read_json(path: Path) -> dict[str, object]:
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value

"""Provider-free acceptance of the frozen paired Tier-0 command composition."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
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
from legalforecast.multiharness.tier0_runner import (
    TIER0_SPEND_APPROVAL_SCHEMA_VERSION,
    Tier0ArmSpec,
    Tier0ExecutableSpec,
    Tier0RunnerError,
    Tier0SpendApproval,
    _identities_match,
    load_detached_approval,
    load_executable_spec,
    run_tier0,
)
from tests.test_harvey_lab_projection import FIXTURE_PIN, _issue_196_source
from tests.test_multiharness_claude_clean_native_lab_e2e import (
    FAKE_EVALUATOR,
    FAKE_LAB_CLI,
    _install_script,
    _install_trampoline,
)

KEY = Ed25519PrivateKey.from_private_bytes(b"L" * 32)
LAB_BASENAME = "issue-identification-memo.docx"


class _FixtureAuthority:
    public_key = KEY.public_key()
    issuer_id = "fixture-test-authority"
    key_id = "harvey-lab-evaluator-v1"
    issuer_policy_sha256 = harvey_lab_issuer_policy_sha256()

    @staticmethod
    def sign(payload: bytes) -> bytes:
        return KEY.sign(payload)


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
        runner, "load_approved_issuer_authority", lambda: _FixtureAuthority()
    )
    import legalforecast.multiharness.cli as multiharness_cli

    monkeypatch.setattr(
        multiharness_cli, "load_approved_issuer_authority", lambda: _FixtureAuthority()
    )
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
    run_root = tmp_path / ".tier0-runtime" / spec_sha256.removeprefix("sha256:")
    private_root = run_root / "private"
    archive_root = run_root / "archive"
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
            approval_path, spec_sha256=spec_sha256, authority=_FixtureAuthority()
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
            authority=_FixtureAuthority(),
        )

    unknown = _signed_approval_record(spec_sha256)
    unknown["authority"] = "unapproved-issuer"
    unknown_path = tmp_path / "unknown.json"
    write_json_object(unknown_path, unknown)
    with pytest.raises(Tier0RunnerError, match="issuer is not approved"):
        load_detached_approval(
            unknown_path,
            spec_sha256=spec_sha256,
            authority=_FixtureAuthority(),
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
            authority=_FixtureAuthority(),
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

    monkeypatch.setattr(runner, "load_approved_issuer_authority", _FixtureAuthority)
    monkeypatch.setattr(
        multiharness_cli, "load_approved_issuer_authority", _FixtureAuthority
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
    spec_sha256: str, *, status: str = "provider_free"
) -> dict[str, object]:
    signing = {
        "schema_version": TIER0_SPEND_APPROVAL_SCHEMA_VERSION,
        "approval_id": "fixture-approval",
        "spec_sha256": spec_sha256,
        "status": status,
        "authority": _FixtureAuthority.issuer_id,
        "issuer_key_id": _FixtureAuthority.key_id,
        "issuer_policy_sha256": _FixtureAuthority.issuer_policy_sha256,
    }
    payload = json.dumps(
        signing, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        **signing,
        "signature": base64.b64encode(KEY.sign(payload)).decode("ascii"),
    }


def _read_json(path: Path) -> dict[str, object]:
    import json

    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value

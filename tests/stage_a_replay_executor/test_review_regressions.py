# pyright: reportPrivateUsage=false

"""Exact-head review regressions for Stage A replay authority boundaries."""

from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor import contract as contract_module
from legalforecast.ingestion.stage_a_replay_executor import executor as executor_module
from legalforecast.ingestion.stage_a_replay_executor import lineage as lineage_module
from legalforecast.ingestion.stage_a_replay_executor import provider as provider_module
from legalforecast.ingestion.stage_a_replay_executor import repair as repair_module
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    AUTHORIZATION_SIGNATURE_NAMESPACE,
    ReplayOutputClaimError,
    verify_authorization_signature,
)
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    StageAReplayExecutorError,
    execute_stage_a_replay,
    load_replay_spec,
)
from tests.stage_a_replay_executor.authorization_fixtures import (
    refresh_authorization_descriptor,
)
from tests.stage_a_replay_executor.fixtures import (
    FakeSpendMeter,
    read_spec,
    settled_reviewer,
    settled_unitizer,
    write_spec,
)


def _accept_authorization_signature(
    _artifact_payload: bytes,
    *,
    signature_path: Path,
    signer_principal: str,
    namespace: str,
) -> None:
    del signature_path, signer_principal, namespace


def _canonical_provider_alias(_provider: str) -> str:
    return "canonical-alias"


def _verified_cycle_root(**_kwargs: object) -> dict[str, object]:
    return {"verification": "VERIFIED", "root_identity_sha256": "8" * 64}


def test_production_code_commit_override_refuses_before_lineage_or_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        contract_module,
        "verify_authorization_signature",
        _accept_authorization_signature,
    )
    parsed = load_replay_spec(
        write_spec(tmp_path, production=True, candidate_ids=("cand-a",))
    )
    touched = False

    def forbidden(*_args: object, **_kwargs: object) -> Any:
        nonlocal touched
        touched = True
        raise AssertionError("production override must refuse before lineage")

    monkeypatch.setattr(executor_module, "verify_replay_lineage", forbidden)
    result = execute_stage_a_replay(parsed, code_commit="0" * 40)

    assert result.halted is True
    assert touched is False
    assert result.to_record()["halt_evidence"] == {
        "status": "halted_on_preflight_failure",
        "reason": "production execution forbids a caller-supplied code commit",
        "failure_type": "ProductionCodeCommitOverride",
        "provider_accessed": False,
    }


def test_dirty_checkout_refuses_code_identity() -> None:
    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        assert command[1] == "status"
        return SimpleNamespace(stdout="?? untracked-provider-wrapper.py\n")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(executor_module.subprocess, "run", fake_run)
        with pytest.raises(StageAReplayExecutorError, match="checkout is dirty"):
            executor_module.current_code_commit()


def test_worst_case_internal_retries_are_reserved_before_callback(
    tmp_path: Path,
) -> None:
    calls = 0

    def forbidden(_request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        nonlocal calls
        calls += 1
        raise AssertionError("callback opened without worst-case authority")

    result = execute_stage_a_replay(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.25",
            per_candidate_ceiling="0.25",
            candidate_ids=("cand-a",),
        ),
        unitizer=forbidden,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(
            maximum_new_attempts_by_call={("cand-a", "unitizer"): 3}
        ),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert calls == 0
    row = json.loads((tmp_path / "invocations.json").read_text())["invocations"][0]
    assert row["maximum_new_attempts"] == 3
    assert row["reservation_usd"] == "0.10"
    assert row["reserved_authority_usd"] == "0.30"
    assert row["new_attempt_count"] is None


def test_preexisting_journal_commitment_counts_against_signed_ceiling(
    tmp_path: Path,
) -> None:
    calls = 0

    def forbidden(_request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        nonlocal calls
        calls += 1
        raise AssertionError("callback opened after authority was already committed")

    result = execute_stage_a_replay(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.25",
            per_candidate_ceiling="0.25",
            candidate_ids=("cand-a",),
        ),
        unitizer=forbidden,
        reviewer=settled_reviewer,
        spend_meter=FakeSpendMeter(
            preexisting_attempts_by_call={("cand-a", "unitizer"): 1},
            preexisting_committed_by_call={("cand-a", "unitizer"): "0.10"},
            maximum_new_attempts_by_call={("cand-a", "unitizer"): 2},
        ),
        code_commit="0" * 40,
    )

    assert result.halted is True
    assert calls == 0
    summary = cast(dict[str, object], result.to_record()["spend_summary"])
    assert summary["aggregate_prior_committed_usd"] == "0.10"
    assert summary["aggregate_actual_cost_usd"] == "0"
    assert summary["aggregate_authorization_accounted_usd"] == "0.10"


def test_output_parent_beneath_regular_file_refuses_during_preflight(
    tmp_path: Path,
) -> None:
    path = write_spec(tmp_path)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied\n")
    record = read_spec(path)
    cast(dict[str, object], record["outputs"])["plan_path"] = str(blocker / "plan.json")
    refresh_authorization_descriptor(path, record, validate=False)

    with pytest.raises(StageAReplayExecutorError, match="not a real directory"):
        load_replay_spec(path)


def test_independent_repair_receipt_pin_is_mandatory_and_well_formed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_spec(tmp_path, production=True, candidate_ids=("cand-a",))
    record = read_spec(path)
    lineage = cast(dict[str, object], record["lineage"])
    cast(dict[str, object], lineage["repair_receipt"])["expected_receipt_sha256"] = (
        "self-pinned"
    )
    refresh_authorization_descriptor(path, record, validate=False)
    monkeypatch.setattr(
        contract_module,
        "verify_authorization_signature",
        _accept_authorization_signature,
    )

    with pytest.raises(
        StageAReplayExecutorError,
        match="expected_receipt_sha256 must be a lowercase SHA-256 digest",
    ):
        load_replay_spec(path)


def test_stale_cycle_root_identity_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        contract_module,
        "verify_authorization_signature",
        _accept_authorization_signature,
    )
    parsed = load_replay_spec(
        write_spec(tmp_path, production=True, candidate_ids=("cand-a",))
    )
    monkeypatch.setattr(
        "legalforecast.ingestion.cycle_lineage_index.locate_cycle_lineage",
        _verified_cycle_root,
    )

    with pytest.raises(StageAReplayExecutorError, match="root identity differs"):
        lineage_module._verify_cycle_root(parsed)


def test_detached_sshsig_verifies_exact_authorization_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key = tmp_path / "owner-key"
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-f",
            str(private_key),
        ],
        check=True,
    )
    artifact = tmp_path / "authorization.json"
    artifact.write_bytes(b'{"authorized":true}\n')
    subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(private_key),
            "-n",
            AUTHORIZATION_SIGNATURE_NAMESPACE,
            str(artifact),
        ],
        check=True,
        capture_output=True,
    )
    allowed_signers = tmp_path / "allowed_signers"
    allowed_signers.write_text(
        "owner@example.invalid " + (tmp_path / "owner-key.pub").read_text()
    )
    trusted_checkout = tmp_path / "trusted-checkout"
    trusted_checkout.mkdir()
    subprocess.run(["git", "init", "-q", str(trusted_checkout)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(trusted_checkout),
            "config",
            "--local",
            "gpg.ssh.allowedSignersFile",
            str(allowed_signers),
        ],
        check=True,
    )
    monkeypatch.setattr(contract_module, "repository_root", lambda: trusted_checkout)
    signature = Path(f"{artifact}.sig")

    verify_authorization_signature(
        artifact.read_bytes(),
        signature_path=signature,
        signer_principal="owner@example.invalid",
        namespace=AUTHORIZATION_SIGNATURE_NAMESPACE,
    )
    with pytest.raises(StageAReplayExecutorError, match="signature is invalid"):
        verify_authorization_signature(
            b'{"authorized":false}\n',
            signature_path=signature,
            signer_principal="owner@example.invalid",
            namespace=AUTHORIZATION_SIGNATURE_NAMESPACE,
        )


def test_authorization_signer_lookup_uses_runtime_checkout_not_caller_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_checkout = tmp_path / "trusted-checkout"
    caller_checkout = tmp_path / "caller-checkout"
    trusted_checkout.mkdir()
    caller_checkout.mkdir()
    subprocess.run(["git", "init", "-q", str(trusted_checkout)], check=True)
    subprocess.run(["git", "init", "-q", str(caller_checkout)], check=True)

    owner_key = tmp_path / "owner-key"
    attacker_key = tmp_path / "attacker-key"
    for key in (owner_key, attacker_key):
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            check=True,
        )

    trusted_signers = trusted_checkout / ".git-trust" / "allowed_signers"
    trusted_signers.parent.mkdir()
    trusted_signers.write_text(
        "owner@example.invalid " + owner_key.with_suffix(".pub").read_text()
    )
    caller_signers = tmp_path / "caller-signers"
    caller_signers.write_text(
        "owner@example.invalid " + attacker_key.with_suffix(".pub").read_text()
    )
    git_home = tmp_path / "git-home"
    git_home.mkdir()
    monkeypatch.setenv("HOME", str(git_home))
    subprocess.run(
        [
            "git",
            "config",
            "--global",
            "gpg.ssh.allowedSignersFile",
            ".git-trust/allowed_signers",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(caller_checkout),
            "config",
            "--local",
            "gpg.ssh.allowedSignersFile",
            str(caller_signers),
        ],
        check=True,
    )
    attacker_config = tmp_path / "attacker-config"
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(attacker_config),
            "gpg.ssh.allowedSignersFile",
            str(caller_signers),
        ],
        check=True,
    )

    artifact = tmp_path / "authorization.json"
    artifact.write_bytes(b'{"authorized":true}\n')
    subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(owner_key),
            "-n",
            AUTHORIZATION_SIGNATURE_NAMESPACE,
            str(artifact),
        ],
        check=True,
        capture_output=True,
    )

    monkeypatch.chdir(caller_checkout)
    monkeypatch.setenv("GIT_DIR", str(caller_checkout / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(caller_checkout))
    monkeypatch.setenv("GIT_CONFIG", str(attacker_config))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "gpg.ssh.allowedSignersFile")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(caller_signers))
    monkeypatch.setattr(
        contract_module,
        "repository_root",
        lambda: trusted_checkout,
        raising=False,
    )
    verify_authorization_signature(
        artifact.read_bytes(),
        signature_path=Path(f"{artifact}.sig"),
        signer_principal="owner@example.invalid",
        namespace=AUTHORIZATION_SIGNATURE_NAMESPACE,
    )


def test_plan_publication_is_an_exclusive_provider_access_claim(
    tmp_path: Path,
) -> None:
    parsed = load_replay_spec(
        write_spec(
            tmp_path,
            aggregate_ceiling="0.30",
            per_candidate_ceiling="0.30",
            candidate_ids=("cand-a",),
        )
    )
    calls: list[str] = []

    def unitizer(request: CandidateScopedStageARerunRequest) -> StageAStageOutcome:
        calls.append(f"unitizer:{request.candidate_id}")
        return settled_unitizer(request)

    def reviewer(
        request: CandidateScopedStageARerunRequest,
        unitize: StageAStageOutcome,
    ) -> StageAStageOutcome:
        calls.append(f"reviewer:{request.candidate_id}")
        return settled_reviewer(request, unitize)

    def execute() -> object:
        return execute_stage_a_replay(
            parsed,
            unitizer=unitizer,
            reviewer=reviewer,
            spend_meter=FakeSpendMeter(),
            code_commit="0" * 40,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(execute) for _ in range(2)]
    results: list[object] = []
    errors: list[Exception] = []
    for future in futures:
        try:
            results.append(future.result())
        except Exception as exc:
            errors.append(exc)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ReplayOutputClaimError)
    assert "replay plan output already exists" in str(errors[0])
    assert calls == ["unitizer:cand-a", "reviewer:cand-a"]
    assert (tmp_path / "receipt.json").is_file()


def test_provider_account_alias_must_equal_pinned_caps() -> None:
    entries = cast(
        Any,
        (
            SimpleNamespace(provider="openai"),
            SimpleNamespace(provider="openai"),
        ),
    )

    with pytest.raises(StageAReplayExecutorError, match="differs from pinned caps"):
        provider_module._validated_provider_accounts(
            {"openai": "untrusted-alias"},
            entries,
            _canonical_provider_alias,
        )
    with pytest.raises(StageAReplayExecutorError, match="exactly cover"):
        provider_module._validated_provider_accounts(
            {"openai": "canonical-alias", "unused": "extra"},
            entries,
            _canonical_provider_alias,
        )


def test_repair_receipt_scope_and_documents_bind_authorized_candidates(
    tmp_path: Path,
) -> None:
    parsed = load_replay_spec(write_spec(tmp_path, candidate_ids=("cand-a",)))
    successor = lineage_module.verify_replay_lineage(parsed).successor
    wrong_scope = {
        "manifest_candidate_ids": ["cand-b"],
        "execution_candidate_ids": ["cand-b"],
        "receipt_candidate_ids": ["cand-b"],
        "included_operations": [
            {
                "candidate_id": "cand-b",
                "source_document_id": "doc-cand-b",
                "document_role": "complaint",
            }
        ],
        "nonincluded_operations": [],
    }
    with pytest.raises(StageAReplayExecutorError, match="outside verified repair"):
        repair_module.verify_repair_scope(parsed, wrong_scope, successor)

    wrong_document = {
        "manifest_candidate_ids": ["cand-a"],
        "execution_candidate_ids": ["cand-a"],
        "receipt_candidate_ids": ["cand-a"],
        "included_operations": [
            {
                "candidate_id": "cand-a",
                "source_document_id": "different-document",
                "document_role": "complaint",
            }
        ],
        "nonincluded_operations": [],
    }
    with pytest.raises(StageAReplayExecutorError, match="differs from authenticated"):
        repair_module.verify_repair_scope(parsed, wrong_document, successor)

    excluded_operation = {
        "manifest_candidate_ids": ["cand-a"],
        "execution_candidate_ids": ["cand-a"],
        "receipt_candidate_ids": ["cand-a"],
        "included_operations": [
            {
                "candidate_id": "cand-a",
                "source_document_id": "doc-cand-a",
                "document_role": "complaint",
            }
        ],
        "nonincluded_operations": [
            {
                "candidate_id": "cand-a",
                "source_document_id": "sealed-document",
                "document_role": "order",
                "disposition": "excluded",
            }
        ],
    }
    with pytest.raises(StageAReplayExecutorError, match="nonincluded repair"):
        repair_module.verify_repair_scope(parsed, excluded_operation, successor)

"""Provider-free tests for the Tier-0 identity and receipt-authority seams.

All key material and binaries in this file are synthetic fixtures.  No test
resolves credentials or invokes a provider.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from legalforecast.multiharness.identity import (
    derive_run_identity,
    derive_solver_identity,
    derive_task_identity,
)
from legalforecast.multiharness.local_cli_contracts import (
    ExecutionReceipt,
    RunSpec,
)
from legalforecast.multiharness.local_cli_identity import (
    executable_pin_for,
)
from legalforecast.multiharness.local_cli_probe import (
    LocalCliProbeError,
    probe_installed_cli,
)
from legalforecast.multiharness.receipt_authority import (
    EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT,
    EVALUATOR_ISSUER_INFISICAL_PATH,
    EVALUATOR_ISSUER_PRIVATE_KEY_NAME,
    ReceiptAuthorityError,
    authority_from_synthetic_fixture_key,
    pending_evaluator_issuer_authority,
)
from legalforecast.multiharness.run_metadata import (
    BinaryRunIdentity,
    RunMetadataError,
    bind_execution_receipt,
    build_private_run_metadata,
    verify_receipt_metadata_binding,
    write_private_run_metadata,
)

POLICY = "sha256:" + "a" * 64


def test_pending_authority_refuses_before_any_secret_loader_call() -> None:
    authority = pending_evaluator_issuer_authority(
        issuer_id="legalforecast.harvey-lab-evaluator-issuer.v1",
        key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=POLICY,
    )
    called = False

    def loader(_environment: str, _path: str, _name: str) -> str:
        nonlocal called
        called = True
        return "should-not-be-read"

    with pytest.raises(ReceiptAuthorityError, match="pending"):
        authority.with_signing_secret_loader(loader).signer()
    assert not called


def test_synthetic_fixture_signer_is_bound_to_public_key_and_exact_loader_scope() -> (
    None
):
    authority = authority_from_synthetic_fixture_key(
        issuer_id="legalforecast.harvey-lab-evaluator-issuer.v1",
        key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=POLICY,
        private_key_bytes=b"K" * 32,
    )
    observed_scope: list[tuple[str, str, str]] = []

    def loader(environment: str, path: str, name: str) -> bytes:
        observed_scope.append((environment, path, name))
        return base64.b64encode(b"K" * 32)

    authority = authority.with_signing_secret_loader(loader)
    signer = authority.signer()
    payload = b"synthetic evaluator receipt payload"
    signature = signer(payload)
    authority.public_key.verify(signature, payload)
    assert observed_scope == [
        (
            EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT,
            EVALUATOR_ISSUER_INFISICAL_PATH,
            EVALUATOR_ISSUER_PRIVATE_KEY_NAME,
        )
    ]

    other = authority_from_synthetic_fixture_key(
        issuer_id="legalforecast.harvey-lab-evaluator-issuer.v1",
        key_id="harvey-lab-evaluator-v1",
        issuer_policy_sha256=POLICY,
        private_key_bytes=b"L" * 32,
    )
    with pytest.raises(InvalidSignature):
        other.public_key.verify(signature, payload)

    mutated_signature = bytearray(signature)
    mutated_signature[-1] ^= 1
    with pytest.raises(InvalidSignature):
        authority.public_key.verify(bytes(mutated_signature), payload)


def test_committed_authority_config_is_pending_and_loads_fail_closed() -> None:
    config = (
        Path(__file__).parents[1]
        / "examples"
        / "adapters"
        / "harvey-lab"
        / "evaluator-issuer-authority.json"
    )
    from legalforecast.multiharness.receipt_authority import (
        EvaluatorIssuerAuthority,
    )

    authority = EvaluatorIssuerAuthority.from_json_file(config)
    assert authority.status == "pending_human_provisioning"
    with pytest.raises(ReceiptAuthorityError, match="pending"):
        _ = authority.public_key


def test_credential_free_probe_reports_drift_instead_of_asserting_pin(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "synthetic-cli"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('codex-cli 0.147.0')\n"
        "else:\n"
        "    print('Usage: synthetic-cli --model MODEL --json --help')\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    pin = executable_pin_for(executable, version="codex-cli 0.146.0")
    parent_env = {
        "PATH": str(tmp_path) + os.pathsep + "/usr/bin",
        "LC_CTYPE": "C.UTF-8",
    }
    observed = probe_installed_cli(
        pin,
        scratch_root=tmp_path / "probe-scratch",
        parent_env=parent_env,
    )
    assert observed.observed_version == "codex-cli 0.147.0"
    assert observed.observed_sha256 == pin.sha256
    assert observed.pin_digest_match is True
    assert observed.pin_version_match is False
    assert "--model" in observed.observed_flags
    assert observed.provider_free is True


def test_probe_refuses_missing_installed_executable(tmp_path: Path) -> None:
    pin = executable_pin_for(
        Path(__file__).parent / "fixtures" / "local_cli_fake_cli.py",
        version="fixture-1.0.0",
    )
    with pytest.raises(LocalCliProbeError, match="not found"):
        probe_installed_cli(
            pin,
            scratch_root=tmp_path / "probe-scratch",
            parent_env={"PATH": str(tmp_path), "LC_CTYPE": "C.UTF-8"},
        )


def test_private_run_metadata_hash_binds_existing_receipt_config(
    tmp_path: Path,
) -> None:
    spec = RunSpec(
        spec_id="metadata-spec",
        argv=("synthetic-cli", "--print"),
        working_directory=tmp_path,
    )
    observed = BinaryRunIdentity(
        executable_name="synthetic-cli",
        executable_version="0.1.0",
        executable_sha256="sha256:" + "b" * 64,
    )
    metadata = build_private_run_metadata(
        run_id="run-metadata-1",
        run_spec=spec,
        executable_identities=(observed,),
        boundary_identity={
            "containment": "posix_process_group.v1",
            "auth_profile": "fixture-none",
        },
        config_records={
            "runtime": {"network": "none", "timeout_seconds": 30},
            "solver": {"requested_model": "synthetic/model"},
        },
        started_at_utc="2026-08-17T12:00:00Z",
    )
    task = derive_task_identity(
        task_id="lfb.synthetic-1",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture",
        task_sha256="sha256:" + "c" * 64,
    )
    solver = derive_solver_identity(
        provider="synthetic",
        requested_model="synthetic/model",
        served_model="synthetic/model",
        settings_sha256="sha256:" + "d" * 64,
    )
    identity = derive_run_identity(
        task=task,
        solver=solver,
        runtime_policy_sha256="sha256:" + "e" * 64,
        config_sha256=metadata.config_sha256,
        temporal_block="fixture",
        order=0,
        repeat_index=0,
    )
    receipt = ExecutionReceipt.from_transcript(spec, stdout="synthetic")
    bound = receipt.with_identity_keys(task=task, solver=solver, run=identity)
    binding = bind_execution_receipt(bound, metadata)
    verify_receipt_metadata_binding(bound, metadata, binding)
    assert metadata.config_sha256 == bound.config_sha256
    assert binding.run_metadata_sha256 == metadata.metadata_sha256
    assert (
        json.loads(json.dumps(metadata.to_record()))["binary_identities"][0][
            "executable_sha256"
        ]
        == observed.executable_sha256
    )

    tampered = dict(metadata.to_record())
    tampered["boundary_identity"] = {"containment": "changed"}
    with pytest.raises(RunMetadataError, match="metadata_sha256"):
        type(metadata).from_record(tampered)

    tampered_binary = json.loads(json.dumps(metadata.to_record()))
    tampered_binary["binary_identities"][0]["executable_sha256"] = "sha256:" + "a" * 64
    with pytest.raises(RunMetadataError, match="metadata_sha256"):
        type(metadata).from_record(tampered_binary)

    tampered_binding = dict(binding.to_record())
    tampered_binding["config_sha256"] = "sha256:" + "a" * 64
    with pytest.raises(RunMetadataError, match="binding"):
        verify_receipt_metadata_binding(
            bound,
            metadata,
            type(binding).from_record(tampered_binding),
        )

    write_private_run_metadata(tmp_path / "private" / "run-metadata.json", metadata)
    assert (tmp_path / "private" / "run-metadata.json").stat().st_mode & 0o777 == 0o600


def test_receipt_metadata_binding_refuses_spec_drift(tmp_path: Path) -> None:
    spec = RunSpec(
        spec_id="metadata-spec",
        argv=("synthetic-cli",),
        working_directory=tmp_path,
    )
    metadata = build_private_run_metadata(
        run_id="run-metadata-2",
        run_spec=spec,
        executable_identities=(
            BinaryRunIdentity(
                executable_name="synthetic-cli",
                executable_version="0.1.0",
                executable_sha256="sha256:" + "f" * 64,
            ),
        ),
        boundary_identity={"containment": "fixture"},
        config_records={"runtime": {"fixture": True}},
    )
    receipt = ExecutionReceipt.from_transcript(spec, stdout="other")
    with pytest.raises(RunMetadataError, match="config_sha256"):
        bind_execution_receipt(receipt, metadata)

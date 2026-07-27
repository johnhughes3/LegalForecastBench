from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.labeling.official_paid_baton import load_baton_receipt


@pytest.fixture
def age_material(tmp_path: Path) -> tuple[Path, Path, str]:
    age = Path(shutil.which("age") or pytest.skip("age is not installed"))
    keygen = Path(shutil.which("age-keygen") or pytest.skip("age-keygen missing"))
    identity = tmp_path / "identity.txt"
    subprocess.run(
        [str(keygen), "-o", str(identity)],
        check=True,
        capture_output=True,
        text=True,
    )
    recipient = subprocess.run(
        [str(keygen), "-y", str(identity)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return age, identity, recipient


def _source_tree(root: Path, *, release_sha: str) -> Path:
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    for name in (
        "disclosure-clearance.jsonl",
        "download-manifest.jsonl",
        "materialization-card.json",
        "model-registry.json",
        "parse-requests.jsonl",
        "parser-card.json",
        "parser-manifest.json",
        "selection-card.json",
        "selection.jsonl",
    ):
        (inputs / name).write_text("{}\n", encoding="utf-8")
    for name in ("documents", "markdown"):
        directory = inputs / name
        directory.mkdir()
        (directory / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    (inputs / "provider-caps.json").write_text(
        '{"cycle_id":"cycle-1"}\n', encoding="utf-8"
    )
    job_manifest = root / "official-paid-labeling-job.json"
    job_manifest.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.official_paid_labeling_job.v1",
                "release_sha": release_sha,
                "stage": "llm-unitize",
                "provider": "anthropic",
                "arguments": {
                    "disclosure-clearance": "inputs/disclosure-clearance.jsonl",
                    "document-root": "inputs/documents",
                    "download-manifest": "inputs/download-manifest.jsonl",
                    "markdown-root": "inputs/markdown",
                    "materialization-run-card": "inputs/materialization-card.json",
                    "model-key": ["anthropic:fixture-model"],
                    "model-registry": "inputs/model-registry.json",
                    "output-root": "state",
                    "parse-requests": "inputs/parse-requests.jsonl",
                    "parser-manifest": "inputs/parser-manifest.json",
                    "parser-run-card": "inputs/parser-card.json",
                    "provider-cycle-caps": "inputs/provider-caps.json",
                    "provider-journal": "state/provider-journal.sqlite3",
                    "selection": "inputs/selection.jsonl",
                    "selection-run-card": "inputs/selection-card.json",
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return job_manifest


def _identity_args(release_sha: str) -> list[str]:
    return [
        "--release-sha",
        release_sha,
        "--stage",
        "llm-unitize",
        "--provider",
        "anthropic",
        "--sequence-ordinal",
        "1",
    ]


def test_baton_cli_builds_assembles_opens_and_seals_failure_recovery(
    tmp_path: Path,
    age_material: tuple[Path, Path, str],
) -> None:
    age, age_identity, recipient = age_material
    release_sha = "a" * 40
    source_root = tmp_path / "source"
    job_manifest = _source_tree(source_root, release_sha=release_sha)
    source_ciphertext = tmp_path / "source.age"
    source_receipt_path = tmp_path / "source-receipt.json"

    assert (
        main(
            [
                "acquisition",
                "build-paid-labeling-source",
                "--source-root",
                str(source_root),
                *_identity_args(release_sha),
                "--age-executable",
                str(age),
                "--age-recipient",
                recipient,
                "--output-ciphertext",
                str(source_ciphertext),
                "--receipt-output",
                str(source_receipt_path),
                "--execute",
            ]
        )
        == 0
    )
    source_receipt = load_baton_receipt(source_receipt_path)

    assembly_root = tmp_path / "assembly-private"
    baton_ciphertext = tmp_path / "baton.age"
    baton_receipt_path = tmp_path / "baton-receipt.json"
    assert (
        main(
            [
                "acquisition",
                "assemble-paid-labeling-baton",
                "--source-ciphertext",
                str(source_ciphertext),
                "--source-ciphertext-sha256",
                "sha256:" + source_receipt.ciphertext_sha256,
                "--source-package-manifest-sha256",
                source_receipt.package_manifest_sha256,
                *_identity_args(release_sha),
                "--age-executable",
                str(age),
                "--age-identity-file",
                str(age_identity),
                "--age-recipient",
                recipient,
                "--job-root",
                str(assembly_root),
                "--output-ciphertext",
                str(baton_ciphertext),
                "--receipt-output",
                str(baton_receipt_path),
                "--execute",
            ]
        )
        == 0
    )
    baton_receipt = load_baton_receipt(baton_receipt_path)

    artifact_root = tmp_path / "downloaded-artifact"
    artifact_root.mkdir()
    shutil.copyfile(
        baton_ciphertext, artifact_root / "official-paid-labeling-baton.age"
    )
    shutil.copyfile(baton_receipt_path, artifact_root / "baton-receipt.json")
    opened_root = tmp_path / "opened-private"
    job_manifest_sha256 = hashlib.sha256(job_manifest.read_bytes()).hexdigest()
    assert (
        main(
            [
                "acquisition",
                "open-paid-labeling-baton",
                "--artifact-root",
                str(artifact_root),
                "--expected-package-manifest-sha256",
                baton_receipt.package_manifest_sha256,
                "--expected-job-manifest-sha256",
                job_manifest_sha256,
                *_identity_args(release_sha),
                "--age-executable",
                str(age),
                "--age-identity-file",
                str(age_identity),
                "--job-root",
                str(opened_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (opened_root / "official-paid-labeling-job.json").read_bytes() == (
        job_manifest.read_bytes()
    )

    result_ciphertext = tmp_path / "result.age"
    result_receipt_path = tmp_path / "result-receipt.json"
    assert (
        main(
            [
                "acquisition",
                "seal-paid-labeling-result",
                "--job-root",
                str(opened_root),
                "--input-package-manifest",
                str(opened_root / "official-paid-labeling-package.json"),
                "--expected-input-package-manifest-sha256",
                baton_receipt.package_manifest_sha256,
                *_identity_args(release_sha),
                "--provider-stage-outcome",
                "failure",
                "--age-executable",
                str(age),
                "--age-recipient",
                recipient,
                "--output-ciphertext",
                str(result_ciphertext),
                "--receipt-output",
                str(result_receipt_path),
                "--execute",
            ]
        )
        == 0
    )
    assert load_baton_receipt(result_receipt_path).identity.outcome == "failure"


def test_baton_cli_requires_execute_and_rejects_artifact_residue(
    tmp_path: Path,
) -> None:
    release_sha = "b" * 40
    source_root = tmp_path / "source"
    _source_tree(source_root, release_sha=release_sha)
    output = tmp_path / "source.age"
    receipt = tmp_path / "receipt.json"
    assert (
        main(
            [
                "acquisition",
                "build-paid-labeling-source",
                "--source-root",
                str(source_root),
                *_identity_args(release_sha),
                "--age-executable",
                "/does/not/matter",
                "--age-recipient",
                "age1" + "q" * 58,
                "--output-ciphertext",
                str(output),
                "--receipt-output",
                str(receipt),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert not receipt.exists()

    artifact_root = tmp_path / "artifact"
    artifact_root.mkdir()
    for name in (
        "official-paid-labeling-baton.age",
        "baton-receipt.json",
        "unexpected.txt",
    ):
        (artifact_root / name).write_text("x", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "open-paid-labeling-baton",
                "--artifact-root",
                str(artifact_root),
                "--expected-package-manifest-sha256",
                "c" * 64,
                "--expected-job-manifest-sha256",
                "d" * 64,
                *_identity_args(release_sha),
                "--age-executable",
                "/does/not/matter",
                "--age-identity-file",
                "/does/not/matter",
                "--job-root",
                str(tmp_path / "job"),
                "--execute",
            ]
        )
        == 2
    )
    assert not (tmp_path / "job").exists()

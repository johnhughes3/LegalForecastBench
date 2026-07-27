from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest
from legalforecast.labeling.official_paid_baton import (
    BatonIdentity,
    OfficialPaidBatonError,
    PredecessorBinding,
    _canonical,
    assemble_paid_labeling_baton,
    build_source_baton,
    open_paid_labeling_baton,
    seal_paid_labeling_baton,
)
from legalforecast.labeling.provider_journal import PROVIDER_JOURNAL_SCHEMA_VERSION


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_canonical_commitment_rejects_non_finite_numbers(non_finite: float) -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        _canonical({"value": non_finite})


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


def _job(root: Path, identity: BatonIdentity) -> None:
    root.mkdir(parents=True)
    (root / "inputs").mkdir()
    arguments: dict[str, object] = {
        "markdown-root": "inputs/markdown",
        "model-key": [f"{identity.provider}:fixture-model"],
        "model-registry": "inputs/model-registry.json",
        "output-root": "state",
        "parser-manifest": "inputs/parser-manifest.json",
        "provider-cycle-caps": "inputs/provider-caps.json",
        "provider-journal": "state/provider-journal.sqlite3",
        "selection": "inputs/selection.json",
    }
    if identity.stage == "llm-unitize":
        arguments.update(
            {
                "disclosure-clearance": "inputs/disclosure-clearance.jsonl",
                "document-root": "inputs/documents",
                "download-manifest": "inputs/download-manifest.jsonl",
                "materialization-run-card": "inputs/materialization-card.json",
                "parse-requests": "inputs/parse-requests.jsonl",
                "parser-run-card": "inputs/parser-card.json",
                "selection-run-card": "inputs/selection-card.json",
            }
        )
    elif identity.stage == "llm-review-stage-a":
        arguments.update(
            {
                "llm-unitization-run-card": "inputs/unitization-card.json",
                "prediction-units": "inputs/prediction-units.jsonl",
                "unitization-review-queue": "inputs/unitization-queue.jsonl",
            }
        )
    else:
        arguments.update(
            {
                "decision-texts": "inputs/decision-texts.jsonl",
                "decision-texts-manifest": "inputs/decision-texts-manifest.json",
                "decision-texts-run-card": "inputs/decision-texts-card.json",
                "evaluated-model-registry": "inputs/evaluated-registry.json",
                "llm-review-stage-a-run-card": "inputs/review-card.json",
                "llm-unitization-run-card": "inputs/unitization-card.json",
                "prediction-units": "inputs/finalized-units.jsonl",
                "unitization-review-run-card": "inputs/apply-card.json",
            }
        )
    directory_inputs = {"document-root", "markdown-root"}
    output_paths = {"output-root", "provider-journal"}
    for name, raw_path in arguments.items():
        if name not in directory_inputs | output_paths and isinstance(raw_path, str):
            path = root / raw_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
    for name in directory_inputs & arguments.keys():
        directory = root / str(arguments[name])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "fixture.txt").write_text("fixture\n", encoding="utf-8")
    (root / "official-paid-labeling-job.json").write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.official_paid_labeling_job.v1",
                "release_sha": identity.release_sha,
                "stage": identity.stage,
                "provider": identity.provider,
                "arguments": arguments,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "inputs" / "provider-caps.json").write_text(
        json.dumps({"cycle_id": "cycle-1"}) + "\n", encoding="utf-8"
    )


def _binding(receipt: object) -> PredecessorBinding:
    return PredecessorBinding.from_receipt(receipt)  # type: ignore[arg-type]


def test_source_build_and_consumer_open_are_closed_and_encrypted(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, age_identity, recipient = age_material
    identity = BatonIdentity(
        release_sha="a" * 40,
        stage="llm-unitize",
        provider="anthropic",
        sequence=1,
        outcome="ready",
    )
    source = tmp_path / "source"
    _job(source, identity)

    receipt = build_source_baton(
        source_root=source,
        identity=identity,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source.age",
        receipt_output=tmp_path / "source-receipt.json",
    )

    assert b"selection.json" not in (tmp_path / "source.age").read_bytes()
    assert (
        receipt.ciphertext_sha256
        == hashlib.sha256((tmp_path / "source.age").read_bytes()).hexdigest()
    )
    with pytest.raises(OfficialPaidBatonError, match="job manifest commitment"):
        open_paid_labeling_baton(
            ciphertext=tmp_path / "source.age",
            expected_ciphertext_sha256=receipt.ciphertext_sha256,
            expected_package_manifest_sha256=receipt.package_manifest_sha256,
            expected_job_manifest_sha256="0" * 64,
            expected_identity=identity,
            expected_predecessor=None,
            age_executable=age,
            age_identity_file=age_identity,
            job_root=tmp_path / "rejected",
            expected_kind="source",
        )
    assert not (tmp_path / "rejected").exists()

    opened = open_paid_labeling_baton(
        ciphertext=tmp_path / "source.age",
        expected_ciphertext_sha256=receipt.ciphertext_sha256,
        expected_package_manifest_sha256=receipt.package_manifest_sha256,
        expected_job_manifest_sha256=receipt.job_manifest_sha256,
        expected_identity=identity,
        expected_predecessor=None,
        age_executable=age,
        age_identity_file=age_identity,
        job_root=tmp_path / "opened",
        expected_kind="source",
    )
    assert opened.package_manifest_sha256 == receipt.package_manifest_sha256
    assert (tmp_path / "opened/inputs/selection.json").read_text() == "{}\n"
    assert (
        hashlib.sha256(
            (tmp_path / "opened/official-paid-labeling-package.json").read_bytes()
        ).hexdigest()
        == receipt.package_manifest_sha256
    )
    public_receipt = (tmp_path / "source-receipt.json").read_text()
    assert str(source) not in public_receipt
    assert "selection.json" not in public_receipt


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "fifo"])
def test_source_rejects_non_unique_or_special_files(
    tmp_path: Path,
    age_material: tuple[Path, Path, str],
    attack: str,
) -> None:
    age, _, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    target = source / "attack"
    if attack == "symlink":
        target.symlink_to(source / "inputs/selection.json")
    elif attack == "hardlink":
        os.link(source / "inputs/selection.json", target)
    else:
        os.mkfifo(target)

    with pytest.raises(OfficialPaidBatonError, match="unique regular"):
        build_source_baton(
            source_root=source,
            identity=identity,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "bad.age",
            receipt_output=tmp_path / "bad.json",
        )


def test_source_rejects_case_insensitive_path_collisions(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, _, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    (source / "inputs/markdown/Fixture.txt").write_text(
        "case collision\n",
        encoding="utf-8",
    )

    with pytest.raises(OfficialPaidBatonError, match="package path collision"):
        build_source_baton(
            source_root=source,
            identity=identity,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "bad.age",
            receipt_output=tmp_path / "bad.json",
        )


def test_source_rejects_provider_journal_and_sidecars(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, _, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    (source / "state").mkdir()
    (source / "state/provider-journal.sqlite3-wal").write_bytes(b"not allowed")

    with pytest.raises(OfficialPaidBatonError, match="journal"):
        build_source_baton(
            source_root=source,
            identity=identity,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "bad.age",
            receipt_output=tmp_path / "bad.json",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_argument", "required arguments are absent"),
        ("unknown_argument", "not allowlisted"),
        ("missing_input", "required input is absent"),
        ("residue", "undeclared residue"),
    ],
)
def test_source_rejects_semantically_invalid_job_before_encrypting(
    tmp_path: Path,
    age_material: tuple[Path, Path, str],
    mutation: str,
    message: str,
) -> None:
    age, _, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    manifest_path = source / "official-paid-labeling-job.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "missing_argument":
        del manifest["arguments"]["selection"]
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    elif mutation == "unknown_argument":
        manifest["arguments"]["shell"] = "rm -rf /"
        manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    elif mutation == "missing_input":
        (source / "inputs/selection.json").unlink()
    else:
        (source / "unexpected.txt").write_text("residue\n", encoding="utf-8")

    ciphertext = tmp_path / "must-not-exist.age"
    receipt = tmp_path / "must-not-exist.json"
    with pytest.raises(OfficialPaidBatonError, match=message):
        build_source_baton(
            source_root=source,
            identity=identity,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=ciphertext,
            receipt_output=receipt,
        )
    assert not ciphertext.exists()
    assert not receipt.exists()


def test_open_rejects_zip_traversal_before_creating_job_root(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, age_identity, recipient = age_material
    plain = tmp_path / "bad.zip"
    with zipfile.ZipFile(plain, "w") as archive:
        archive.writestr("../escape", b"bad")
        archive.writestr("official-paid-labeling-package.json", b"{}")
    ciphertext = tmp_path / "bad.age"
    subprocess.run(
        [str(age), "-r", recipient, "-o", str(ciphertext), str(plain)], check=True
    )

    with pytest.raises(OfficialPaidBatonError, match="archive path"):
        open_paid_labeling_baton(
            ciphertext=ciphertext,
            expected_ciphertext_sha256=hashlib.sha256(
                ciphertext.read_bytes()
            ).hexdigest(),
            expected_package_manifest_sha256="0" * 64,
            expected_job_manifest_sha256="0" * 64,
            expected_identity=BatonIdentity(
                "a" * 40, "llm-unitize", "anthropic", 1, "ready"
            ),
            expected_predecessor=None,
            age_executable=age,
            age_identity_file=age_identity,
            job_root=tmp_path / "must-not-exist",
        )
    assert not (tmp_path / "must-not-exist").exists()
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "package files differ"),
        ("extra", "package files differ"),
        ("changed", "package file commitment differs"),
        ("prefix", "archive path prefix collision"),
    ],
)
def test_open_rejects_manifest_and_prefix_closure_attacks(
    tmp_path: Path,
    age_material: tuple[Path, Path, str],
    mutation: str,
    message: str,
) -> None:
    age, age_identity, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    receipt = build_source_baton(
        source_root=source,
        identity=identity,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source.age",
        receipt_output=tmp_path / "source.json",
    )
    plain = tmp_path / "plain.zip"
    subprocess.run(
        [
            str(age),
            "-d",
            "-i",
            str(age_identity),
            "-o",
            str(plain),
            str(tmp_path / "source.age"),
        ],
        check=True,
    )
    with zipfile.ZipFile(plain) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    if mutation == "missing":
        members.pop("inputs/selection.json")
    elif mutation == "extra":
        members["unexpected.txt"] = b"unexpected"
    elif mutation == "changed":
        members["inputs/selection.json"] = b"changed"
    else:
        members["inputs/selection.json/child"] = b"collision"
    mutated = tmp_path / "mutated.zip"
    with zipfile.ZipFile(mutated, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    ciphertext = tmp_path / "mutated.age"
    subprocess.run(
        [str(age), "-r", recipient, "-o", str(ciphertext), str(mutated)], check=True
    )

    with pytest.raises(OfficialPaidBatonError, match=message):
        open_paid_labeling_baton(
            ciphertext=ciphertext,
            expected_ciphertext_sha256=hashlib.sha256(
                ciphertext.read_bytes()
            ).hexdigest(),
            expected_package_manifest_sha256=receipt.package_manifest_sha256,
            expected_job_manifest_sha256=receipt.job_manifest_sha256,
            expected_identity=identity,
            expected_predecessor=None,
            age_executable=age,
            age_identity_file=age_identity,
            job_root=tmp_path / "opened",
            expected_kind="source",
        )
    assert not (tmp_path / "opened").exists()


def test_open_rejects_archive_over_configured_total_limit(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, age_identity, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    receipt = build_source_baton(
        source_root=source,
        identity=identity,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source.age",
        receipt_output=tmp_path / "source.json",
    )
    with pytest.raises(OfficialPaidBatonError, match="total size limit"):
        open_paid_labeling_baton(
            ciphertext=tmp_path / "source.age",
            expected_ciphertext_sha256=receipt.ciphertext_sha256,
            expected_package_manifest_sha256=receipt.package_manifest_sha256,
            expected_job_manifest_sha256=receipt.job_manifest_sha256,
            expected_identity=identity,
            expected_predecessor=None,
            age_executable=age,
            age_identity_file=age_identity,
            job_root=tmp_path / "opened",
            expected_kind="source",
            max_total_bytes=1,
        )


def _create_journal(path: Path, *, caps_sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            "CREATE TABLE provider_journal_metadata (singleton INTEGER PRIMARY KEY, "
            "schema_version TEXT, cycle_id TEXT, provider_cycle_caps_sha256 TEXT, "
            "canonical_path TEXT)"
        )
        connection.execute(
            "INSERT INTO provider_journal_metadata VALUES (1, ?, ?, ?, ?)",
            (PROVIDER_JOURNAL_SCHEMA_VERSION, "cycle-1", caps_sha256, str(path)),
        )
        connection.execute("CREATE TABLE results (value TEXT)")
        connection.execute("INSERT INTO results VALUES ('durable')")
        connection.commit()
    finally:
        connection.close()


def test_successful_result_advances_and_failed_result_only_resumes_same_stage(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, age_identity, recipient = age_material
    first = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source_root = tmp_path / "source-1"
    _job(source_root, first)
    source_receipt = build_source_baton(
        source_root=source_root,
        identity=first,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source-1.age",
        receipt_output=tmp_path / "source-1.json",
    )
    assembled = assemble_paid_labeling_baton(
        source_ciphertext=tmp_path / "source-1.age",
        expected_source_ciphertext_sha256=source_receipt.ciphertext_sha256,
        expected_source_package_manifest_sha256=source_receipt.package_manifest_sha256,
        expected_identity=first,
        predecessor_ciphertext=None,
        predecessor=None,
        age_executable=age,
        age_identity_file=age_identity,
        age_recipient=recipient,
        job_root=tmp_path / "job-1",
        ciphertext_output=tmp_path / "ready-1.age",
        receipt_output=tmp_path / "ready-1.json",
    )
    caps = (tmp_path / "job-1/inputs/provider-caps.json").read_bytes()
    _create_journal(
        tmp_path / "job-1/state/provider-journal.sqlite3",
        caps_sha256=hashlib.sha256(caps).hexdigest(),
    )
    success = seal_paid_labeling_baton(
        job_root=tmp_path / "job-1",
        expected_input_package_manifest_sha256=assembled.package_manifest_sha256,
        outcome="success",
        predecessor=None,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "success.age",
        receipt_output=tmp_path / "success.json",
    )
    assert not (tmp_path / "job-1/state/provider-journal.sqlite3-wal").exists()
    assert success.identity.outcome == "success"

    second = BatonIdentity("a" * 40, "llm-review-stage-a", "google", 2, "ready")
    second_root = tmp_path / "source-2"
    _job(second_root, second)
    second_source = build_source_baton(
        source_root=second_root,
        identity=second,
        predecessor=_binding(success),
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source-2.age",
        receipt_output=tmp_path / "source-2.json",
    )
    # Hosted jobs rematerialize the same canonical JOB_ROOT on each runner.
    shutil.rmtree(tmp_path / "job-1")
    next_ready = assemble_paid_labeling_baton(
        source_ciphertext=tmp_path / "source-2.age",
        expected_source_ciphertext_sha256=second_source.ciphertext_sha256,
        expected_source_package_manifest_sha256=second_source.package_manifest_sha256,
        expected_identity=second,
        predecessor_ciphertext=tmp_path / "success.age",
        predecessor=_binding(success),
        age_executable=age,
        age_identity_file=age_identity,
        age_recipient=recipient,
        job_root=tmp_path / "job-1",
        ciphertext_output=tmp_path / "ready-2.age",
        receipt_output=tmp_path / "ready-2.json",
    )
    assert next_ready.identity == second

    failed = seal_paid_labeling_baton(
        job_root=tmp_path / "job-1",
        expected_input_package_manifest_sha256=next_ready.package_manifest_sha256,
        outcome="failure",
        predecessor=_binding(success),
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "failed.age",
        receipt_output=tmp_path / "failed.json",
    )
    wrong_advance = BatonIdentity(
        "a" * 40, "llm-label-provider-shard", "openai", 3, "ready"
    )
    wrong_root = tmp_path / "source-3"
    _job(wrong_root, wrong_advance)
    with pytest.raises(OfficialPaidBatonError, match="failed predecessor"):
        build_source_baton(
            source_root=wrong_root,
            identity=wrong_advance,
            predecessor=_binding(failed),
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "wrong.age",
            receipt_output=tmp_path / "wrong.json",
        )

    retry_root = tmp_path / "retry-source"
    _job(retry_root, second)
    retry_source = build_source_baton(
        source_root=retry_root,
        identity=second,
        predecessor=_binding(failed),
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "retry.age",
        receipt_output=tmp_path / "retry.json",
    )
    assert retry_source.predecessor == _binding(failed)
    shutil.rmtree(tmp_path / "job-1")
    resumed = assemble_paid_labeling_baton(
        source_ciphertext=tmp_path / "retry.age",
        expected_source_ciphertext_sha256=retry_source.ciphertext_sha256,
        expected_source_package_manifest_sha256=retry_source.package_manifest_sha256,
        expected_identity=second,
        predecessor_ciphertext=tmp_path / "failed.age",
        predecessor=_binding(failed),
        age_executable=age,
        age_identity_file=age_identity,
        age_recipient=recipient,
        job_root=tmp_path / "job-1",
        ciphertext_output=tmp_path / "resumed.age",
        receipt_output=tmp_path / "resumed.json",
    )
    assert resumed.identity == second
    assert resumed.predecessor == _binding(failed)


def test_seal_rejects_source_package_kind(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, age_identity, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    source_receipt = build_source_baton(
        source_root=source,
        identity=identity,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source.age",
        receipt_output=tmp_path / "source.json",
    )
    assemble_paid_labeling_baton(
        source_ciphertext=tmp_path / "source.age",
        expected_source_ciphertext_sha256=source_receipt.ciphertext_sha256,
        expected_source_package_manifest_sha256=(
            source_receipt.package_manifest_sha256
        ),
        expected_identity=identity,
        predecessor_ciphertext=None,
        predecessor=None,
        age_executable=age,
        age_identity_file=age_identity,
        age_recipient=recipient,
        job_root=tmp_path / "job",
        ciphertext_output=tmp_path / "ready.age",
        receipt_output=tmp_path / "ready.json",
    )
    manifest_path = tmp_path / "job/official-paid-labeling-package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["kind"] = "source"
    manifest_bytes = _canonical(manifest)
    manifest_path.write_bytes(manifest_bytes)

    with pytest.raises(OfficialPaidBatonError, match="assembled baton"):
        seal_paid_labeling_baton(
            job_root=tmp_path / "job",
            expected_input_package_manifest_sha256=hashlib.sha256(
                manifest_bytes
            ).hexdigest(),
            outcome="failure",
            predecessor=None,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "result.age",
            receipt_output=tmp_path / "result.json",
        )


def test_seal_rejects_changed_input_and_journal_identity(
    tmp_path: Path, age_material: tuple[Path, Path, str]
) -> None:
    age, identity_file, recipient = age_material
    identity = BatonIdentity("a" * 40, "llm-unitize", "anthropic", 1, "ready")
    source = tmp_path / "source"
    _job(source, identity)
    built = build_source_baton(
        source_root=source,
        identity=identity,
        age_executable=age,
        age_recipient=recipient,
        ciphertext_output=tmp_path / "source.age",
        receipt_output=tmp_path / "source.json",
    )
    ready = assemble_paid_labeling_baton(
        source_ciphertext=tmp_path / "source.age",
        expected_source_ciphertext_sha256=built.ciphertext_sha256,
        expected_source_package_manifest_sha256=built.package_manifest_sha256,
        expected_identity=identity,
        predecessor_ciphertext=None,
        predecessor=None,
        age_executable=age,
        age_identity_file=identity_file,
        age_recipient=recipient,
        job_root=tmp_path / "job",
        ciphertext_output=tmp_path / "ready.age",
        receipt_output=tmp_path / "ready.json",
    )
    (tmp_path / "job/inputs/selection.json").write_text("tampered\n")
    with pytest.raises(OfficialPaidBatonError, match="input package file changed"):
        seal_paid_labeling_baton(
            job_root=tmp_path / "job",
            expected_input_package_manifest_sha256=ready.package_manifest_sha256,
            outcome="success",
            predecessor=None,
            age_executable=age,
            age_recipient=recipient,
            ciphertext_output=tmp_path / "result.age",
            receipt_output=tmp_path / "result.json",
        )

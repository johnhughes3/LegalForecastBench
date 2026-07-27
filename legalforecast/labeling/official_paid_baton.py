"""Encrypted, closed handoffs for official paid-labeling stages.

This module deliberately has no provider, OIDC, AWS, evaluation, freeze, or
dispatch authority.  It only closes a local filesystem tree, encrypts it with
an explicitly supplied ``age`` executable, and verifies/decrypts exact bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import cast

from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)
from legalforecast.labeling.official_paid_job import (
    OfficialPaidLabelingJobError,
    validate_official_paid_labeling_job_package,
)
from legalforecast.labeling.provider_journal import PROVIDER_JOURNAL_SCHEMA_VERSION

PACKAGE_SCHEMA_VERSION = "legalforecast.official_paid_labeling_package.v1"
RECEIPT_SCHEMA_VERSION = "legalforecast.official_paid_labeling_baton_receipt.v1"
PACKAGE_MANIFEST = "official-paid-labeling-package.json"
JOB_MANIFEST = "official-paid-labeling-job.json"
DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STAGE_PROVIDERS = {
    "llm-unitize": frozenset({"anthropic"}),
    "llm-review-stage-a": frozenset({"google"}),
    "llm-label-provider-shard": frozenset({"google", "openai"}),
}
_OUTCOMES = frozenset({"ready", "success", "failure", "cancelled"})
_RESULT_OUTCOMES = frozenset({"success", "failure", "cancelled"})
_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


class OfficialPaidBatonError(ValueError):
    """Raised before an unverified baton can cross a paid-stage boundary."""


@dataclass(frozen=True, slots=True)
class BatonIdentity:
    """Identity asserted by the protected workflow before any provider secret."""

    release_sha: str
    stage: str
    provider: str
    sequence: int
    outcome: str

    def __post_init__(self) -> None:
        if _SHA40.fullmatch(self.release_sha) is None:
            raise OfficialPaidBatonError("release_sha must be a lowercase SHA-1")
        providers = _STAGE_PROVIDERS.get(self.stage)
        if providers is None or self.provider not in providers:
            raise OfficialPaidBatonError("stage/provider identity is not allowlisted")
        if type(self.sequence) is not int:
            raise OfficialPaidBatonError("sequence must be an integer")
        if self.sequence < 1 or self.sequence > 4:
            raise OfficialPaidBatonError("sequence is outside the Cycle 1 chain")
        if self.outcome not in _OUTCOMES:
            raise OfficialPaidBatonError("outcome is not recognized")
        _validate_sequence_stage(self)

    def to_record(self) -> dict[str, object]:
        return {
            "release_sha": self.release_sha,
            "stage": self.stage,
            "provider": self.provider,
            "sequence": self.sequence,
            "outcome": self.outcome,
        }

    @classmethod
    def from_record(cls, value: object) -> BatonIdentity:
        record = _exact_object(
            value,
            {"release_sha", "stage", "provider", "sequence", "outcome"},
            "identity",
        )
        return cls(
            release_sha=_string(record, "release_sha"),
            stage=_string(record, "stage"),
            provider=_string(record, "provider"),
            sequence=_integer(record, "sequence"),
            outcome=_string(record, "outcome"),
        )


@dataclass(frozen=True, slots=True)
class PredecessorBinding:
    """Exact ciphertext and closed-manifest identity of one prior result."""

    ciphertext_sha256: str
    package_manifest_sha256: str
    identity: BatonIdentity

    def __post_init__(self) -> None:
        _digest(self.ciphertext_sha256, "predecessor ciphertext")
        _digest(self.package_manifest_sha256, "predecessor package manifest")
        if self.identity.outcome == "ready":
            raise OfficialPaidBatonError("a ready baton cannot be a predecessor")

    def to_record(self) -> dict[str, object]:
        return {
            "ciphertext_sha256": self.ciphertext_sha256,
            "package_manifest_sha256": self.package_manifest_sha256,
            "identity": self.identity.to_record(),
        }

    @classmethod
    def from_record(cls, value: object) -> PredecessorBinding:
        record = _exact_object(
            value,
            {"ciphertext_sha256", "package_manifest_sha256", "identity"},
            "predecessor",
        )
        return cls(
            ciphertext_sha256=_string(record, "ciphertext_sha256"),
            package_manifest_sha256=_string(record, "package_manifest_sha256"),
            identity=BatonIdentity.from_record(record["identity"]),
        )

    @classmethod
    def from_receipt(cls, receipt: BatonReceipt) -> PredecessorBinding:
        if receipt.identity.outcome == "ready":
            raise OfficialPaidBatonError("a ready receipt cannot bind a predecessor")
        return cls(
            ciphertext_sha256=receipt.ciphertext_sha256,
            package_manifest_sha256=receipt.package_manifest_sha256,
            identity=receipt.identity,
        )


@dataclass(frozen=True, slots=True)
class BatonReceipt:
    """Public commitments for one encrypted package; never contains plaintext."""

    identity: BatonIdentity
    predecessor: PredecessorBinding | None
    ciphertext_sha256: str
    ciphertext_size_bytes: int
    package_manifest_sha256: str
    job_manifest_sha256: str
    input_package_manifest_sha256: str | None
    file_count: int
    total_size_bytes: int

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "identity": self.identity.to_record(),
            "predecessor": (
                None if self.predecessor is None else self.predecessor.to_record()
            ),
            "ciphertext_sha256": self.ciphertext_sha256,
            "ciphertext_size_bytes": self.ciphertext_size_bytes,
            "package_manifest_sha256": self.package_manifest_sha256,
            "job_manifest_sha256": self.job_manifest_sha256,
            "input_package_manifest_sha256": self.input_package_manifest_sha256,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
        }

    @classmethod
    def from_record(cls, value: object) -> BatonReceipt:
        record = _exact_object(
            value,
            {
                "schema_version",
                "identity",
                "predecessor",
                "ciphertext_sha256",
                "ciphertext_size_bytes",
                "package_manifest_sha256",
                "job_manifest_sha256",
                "input_package_manifest_sha256",
                "file_count",
                "total_size_bytes",
            },
            "baton receipt",
        )
        if record["schema_version"] != RECEIPT_SCHEMA_VERSION:
            raise OfficialPaidBatonError("baton receipt schema differs")
        input_sha = record["input_package_manifest_sha256"]
        return cls(
            identity=BatonIdentity.from_record(record["identity"]),
            predecessor=_optional_predecessor(record["predecessor"]),
            ciphertext_sha256=_digest(record["ciphertext_sha256"], "ciphertext"),
            ciphertext_size_bytes=_integer(record, "ciphertext_size_bytes"),
            package_manifest_sha256=_digest(
                record["package_manifest_sha256"], "package manifest"
            ),
            job_manifest_sha256=_digest(record["job_manifest_sha256"], "job manifest"),
            input_package_manifest_sha256=(
                None
                if input_sha is None
                else _digest(input_sha, "input package manifest")
            ),
            file_count=_integer(record, "file_count"),
            total_size_bytes=_integer(record, "total_size_bytes"),
        )


@dataclass(frozen=True, slots=True)
class _VerifiedPackage:
    identity: BatonIdentity
    predecessor: PredecessorBinding | None
    manifest: Mapping[str, object]
    manifest_bytes: bytes
    manifest_sha256: str
    files: Mapping[str, bytes]
    ciphertext_sha256: str
    ciphertext_size_bytes: int


def build_source_baton(
    *,
    source_root: Path,
    identity: BatonIdentity,
    age_executable: Path,
    age_recipient: str,
    ciphertext_output: Path,
    receipt_output: Path,
    predecessor: PredecessorBinding | None = None,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> BatonReceipt:
    """Close and encrypt provider-free inputs for one exact paid stage."""

    if identity.outcome != "ready":
        raise OfficialPaidBatonError("a source baton must have ready outcome")
    _validate_transition(identity, predecessor)
    files = _scan_tree(source_root, max_file_bytes, max_total_bytes)
    _validate_job_package(
        files,
        identity,
        require_inputs=identity.sequence == 1,
        enforce_source_closure=True,
    )
    journal = _journal_relative(files)
    if journal in files or any(
        f"{journal}{suffix}" in files for suffix in _SIDECAR_SUFFIXES
    ):
        raise OfficialPaidBatonError("source package must not contain provider journal")
    return _seal_files(
        files=files,
        kind="source",
        identity=identity,
        predecessor=predecessor,
        input_package_manifest_sha256=None,
        age_executable=age_executable,
        age_recipient=age_recipient,
        ciphertext_output=ciphertext_output,
        receipt_output=receipt_output,
    )


def open_paid_labeling_baton(
    *,
    ciphertext: Path,
    expected_ciphertext_sha256: str,
    expected_package_manifest_sha256: str,
    expected_job_manifest_sha256: str,
    expected_identity: BatonIdentity,
    expected_predecessor: PredecessorBinding | None,
    age_executable: Path,
    age_identity_file: Path,
    job_root: Path,
    expected_kind: str = "baton",
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> BatonReceipt:
    """Verify and decrypt an exact baton before provider/OIDC secret access."""

    package = _decrypt_package(
        ciphertext=ciphertext,
        expected_ciphertext_sha256=expected_ciphertext_sha256,
        expected_package_manifest_sha256=expected_package_manifest_sha256,
        age_executable=age_executable,
        age_identity_file=age_identity_file,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if package.identity != expected_identity:
        raise OfficialPaidBatonError("package identity differs from protected inputs")
    if package.manifest.get("kind") != expected_kind:
        raise OfficialPaidBatonError("package kind differs from protected inputs")
    if package.predecessor != expected_predecessor:
        raise OfficialPaidBatonError(
            "package predecessor differs from protected inputs"
        )
    _validate_job_package(
        package.files,
        package.identity,
        require_inputs=True,
        enforce_source_closure=False,
    )
    if _sha256(package.files[JOB_MANIFEST]) != _digest(
        expected_job_manifest_sha256, "job manifest"
    ):
        raise OfficialPaidBatonError("job manifest commitment differs")
    _install_package(package, job_root)
    return _receipt_for_open(package)


def assemble_paid_labeling_baton(
    *,
    source_ciphertext: Path,
    expected_source_ciphertext_sha256: str,
    expected_source_package_manifest_sha256: str,
    expected_identity: BatonIdentity,
    predecessor_ciphertext: Path | None,
    predecessor: PredecessorBinding | None,
    age_executable: Path,
    age_identity_file: Path,
    age_recipient: str,
    job_root: Path,
    ciphertext_output: Path,
    receipt_output: Path,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> BatonReceipt:
    """Overlay a provider-free source on its exact predecessor and reseal it."""

    if (predecessor is None) != (predecessor_ciphertext is None):
        raise OfficialPaidBatonError("predecessor ciphertext and binding are atomic")
    _validate_transition(expected_identity, predecessor)
    source = _decrypt_package(
        ciphertext=source_ciphertext,
        expected_ciphertext_sha256=expected_source_ciphertext_sha256,
        expected_package_manifest_sha256=expected_source_package_manifest_sha256,
        age_executable=age_executable,
        age_identity_file=age_identity_file,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if source.identity != expected_identity or source.predecessor != predecessor:
        raise OfficialPaidBatonError("source package identity or predecessor differs")
    if source.manifest.get("kind") != "source":
        raise OfficialPaidBatonError("assembly requires a source package")
    _validate_job_package(
        source.files,
        source.identity,
        require_inputs=False,
        enforce_source_closure=True,
    )
    journal = _journal_relative(source.files)
    if journal in source.files or any(
        f"{journal}{suffix}" in source.files for suffix in _SIDECAR_SUFFIXES
    ):
        raise OfficialPaidBatonError("source package must not contain provider journal")

    merged: dict[str, bytes] = {}
    if predecessor is not None:
        assert predecessor_ciphertext is not None
        prior = _decrypt_package(
            ciphertext=predecessor_ciphertext,
            expected_ciphertext_sha256=predecessor.ciphertext_sha256,
            expected_package_manifest_sha256=predecessor.package_manifest_sha256,
            age_executable=age_executable,
            age_identity_file=age_identity_file,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        if prior.identity != predecessor.identity:
            raise OfficialPaidBatonError("predecessor identity differs from binding")
        if prior.manifest.get("kind") != "result":
            raise OfficialPaidBatonError("predecessor is not a sealed provider result")
        merged.update(prior.files)
    for path, payload in source.files.items():
        existing = merged.get(path)
        if existing is not None and existing != payload and path != JOB_MANIFEST:
            raise OfficialPaidBatonError(
                f"source overlay changes predecessor file: {path}"
            )
        merged[path] = payload

    _validate_job_package(
        merged,
        expected_identity,
        require_inputs=True,
        enforce_source_closure=False,
    )
    _install_files(merged, job_root)
    if predecessor is not None:
        _checkpoint_provider_journal(job_root, required=True)
    return _seal_root(
        root=job_root,
        kind="baton",
        identity=expected_identity,
        predecessor=predecessor,
        input_package_manifest_sha256=source.manifest_sha256,
        age_executable=age_executable,
        age_recipient=age_recipient,
        ciphertext_output=ciphertext_output,
        receipt_output=receipt_output,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )


def seal_paid_labeling_baton(
    *,
    job_root: Path,
    expected_input_package_manifest_sha256: str,
    outcome: str,
    predecessor: PredecessorBinding | None,
    age_executable: Path,
    age_recipient: str,
    ciphertext_output: Path,
    receipt_output: Path,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> BatonReceipt:
    """Seal success or recovery bytes after provider credentials are cleared."""

    if outcome not in _RESULT_OUTCOMES:
        raise OfficialPaidBatonError("sealed provider outcome is not recognized")
    manifest_path = job_root / PACKAGE_MANIFEST
    manifest_bytes = _safe_read(manifest_path)
    if _sha256(manifest_bytes) != _digest(
        expected_input_package_manifest_sha256, "input package manifest"
    ):
        raise OfficialPaidBatonError("input package manifest commitment differs")
    manifest = _load_manifest(manifest_bytes)
    identity = BatonIdentity.from_record(manifest["identity"])
    if identity.outcome != "ready":
        raise OfficialPaidBatonError("provider input package is not ready")
    manifest_predecessor = _optional_predecessor(manifest["predecessor"])
    if manifest_predecessor != predecessor:
        raise OfficialPaidBatonError("provider input predecessor differs")
    _verify_input_files(job_root, manifest)
    _checkpoint_provider_journal(job_root, required=outcome == "success")
    return _seal_root(
        root=job_root,
        kind="result",
        identity=replace(identity, outcome=outcome),
        predecessor=predecessor,
        input_package_manifest_sha256=expected_input_package_manifest_sha256,
        age_executable=age_executable,
        age_recipient=age_recipient,
        ciphertext_output=ciphertext_output,
        receipt_output=receipt_output,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )


def _validate_sequence_stage(identity: BatonIdentity) -> None:
    expected = {
        1: "llm-unitize",
        2: "llm-review-stage-a",
        3: "llm-label-provider-shard",
        4: "llm-label-provider-shard",
    }[identity.sequence]
    if identity.stage != expected:
        raise OfficialPaidBatonError("stage does not match the frozen sequence")


def _validate_transition(
    identity: BatonIdentity, predecessor: PredecessorBinding | None
) -> None:
    if predecessor is None:
        if identity.sequence != 1:
            raise OfficialPaidBatonError("noninitial source requires predecessor")
        return
    prior = predecessor.identity
    if prior.release_sha != identity.release_sha:
        raise OfficialPaidBatonError("predecessor release differs")
    if prior.outcome in {"failure", "cancelled"}:
        if (
            identity.stage,
            identity.provider,
            identity.sequence,
        ) != (prior.stage, prior.provider, prior.sequence):
            raise OfficialPaidBatonError(
                "failed predecessor permits only an explicitly bound same-stage resume"
            )
        return
    if prior.outcome != "success" or identity.sequence != prior.sequence + 1:
        raise OfficialPaidBatonError("predecessor is not a successful prior sequence")
    if identity.sequence == 2 and (
        prior.stage,
        prior.provider,
        identity.stage,
        identity.provider,
    ) != ("llm-unitize", "anthropic", "llm-review-stage-a", "google"):
        raise OfficialPaidBatonError("invalid unitization-to-review transition")
    if identity.sequence == 3 and (
        prior.stage,
        prior.provider,
        identity.stage,
    ) != ("llm-review-stage-a", "google", "llm-label-provider-shard"):
        raise OfficialPaidBatonError("invalid review-to-label transition")
    if identity.sequence == 4 and (
        prior.stage != "llm-label-provider-shard"
        or identity.stage != "llm-label-provider-shard"
        or prior.provider == identity.provider
    ):
        raise OfficialPaidBatonError("final label shard requires the other provider")


def _seal_root(
    *,
    root: Path,
    kind: str,
    identity: BatonIdentity,
    predecessor: PredecessorBinding | None,
    input_package_manifest_sha256: str | None,
    age_executable: Path,
    age_recipient: str,
    ciphertext_output: Path,
    receipt_output: Path,
    max_file_bytes: int,
    max_total_bytes: int,
) -> BatonReceipt:
    files = _scan_tree(root, max_file_bytes, max_total_bytes, exclude_manifest=True)
    receipt = _seal_files(
        files=files,
        kind=kind,
        identity=identity,
        predecessor=predecessor,
        input_package_manifest_sha256=input_package_manifest_sha256,
        age_executable=age_executable,
        age_recipient=age_recipient,
        ciphertext_output=ciphertext_output,
        receipt_output=receipt_output,
    )
    _write_new_or_replace_manifest(
        root / PACKAGE_MANIFEST,
        _manifest_bytes(
            files, kind, identity, predecessor, input_package_manifest_sha256
        ),
    )
    return receipt


def _seal_files(
    *,
    files: Mapping[str, bytes],
    kind: str,
    identity: BatonIdentity,
    predecessor: PredecessorBinding | None,
    input_package_manifest_sha256: str | None,
    age_executable: Path,
    age_recipient: str,
    ciphertext_output: Path,
    receipt_output: Path,
) -> BatonReceipt:
    _new_output(ciphertext_output)
    _new_output(receipt_output)
    manifest_bytes = _manifest_bytes(
        files, kind, identity, predecessor, input_package_manifest_sha256
    )
    manifest_sha = _sha256(manifest_bytes)
    with tempfile.TemporaryDirectory(prefix="lfb-paid-baton-") as temporary:
        archive_path = Path(temporary) / "package.zip"
        with zipfile.ZipFile(
            archive_path, "w", compression=zipfile.ZIP_STORED
        ) as archive:
            for name, payload in sorted(files.items()):
                _zip_write(archive, name, payload)
            _zip_write(archive, PACKAGE_MANIFEST, manifest_bytes)
        encrypted = Path(temporary) / "package.age"
        _run_age_encrypt(age_executable, age_recipient, archive_path, encrypted)
        ciphertext_bytes = _safe_read(encrypted)
    receipt = BatonReceipt(
        identity=identity,
        predecessor=predecessor,
        ciphertext_sha256=_sha256(ciphertext_bytes),
        ciphertext_size_bytes=len(ciphertext_bytes),
        package_manifest_sha256=manifest_sha,
        job_manifest_sha256=_sha256(files[JOB_MANIFEST]),
        input_package_manifest_sha256=input_package_manifest_sha256,
        file_count=len(files),
        total_size_bytes=sum(map(len, files.values())),
    )
    try:
        _write_new(ciphertext_output, ciphertext_bytes)
        _write_new(receipt_output, _canonical(receipt.to_record()))
    except Exception:
        _unlink_owned_output(ciphertext_output)
        _unlink_owned_output(receipt_output)
        raise
    return receipt


def _manifest_bytes(
    files: Mapping[str, bytes],
    kind: str,
    identity: BatonIdentity,
    predecessor: PredecessorBinding | None,
    input_manifest_sha: str | None,
) -> bytes:
    rows: list[dict[str, object]] = [
        {"path": path, "size_bytes": len(payload), "sha256": _sha256(payload)}
        for path, payload in sorted(files.items())
    ]
    return _canonical(
        {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "kind": kind,
            "identity": identity.to_record(),
            "predecessor": None if predecessor is None else predecessor.to_record(),
            "input_package_manifest_sha256": input_manifest_sha,
            "files": rows,
            "file_count": len(rows),
            "total_size_bytes": sum(len(payload) for payload in files.values()),
        }
    )


def _decrypt_package(
    *,
    ciphertext: Path,
    expected_ciphertext_sha256: str,
    expected_package_manifest_sha256: str,
    age_executable: Path,
    age_identity_file: Path,
    max_file_bytes: int,
    max_total_bytes: int,
) -> _VerifiedPackage:
    ciphertext_bytes = _safe_read(ciphertext)
    if _sha256(ciphertext_bytes) != _digest(expected_ciphertext_sha256, "ciphertext"):
        raise OfficialPaidBatonError("ciphertext commitment differs")
    with tempfile.TemporaryDirectory(prefix="lfb-open-baton-") as temporary:
        temporary_root = Path(temporary)
        controlled_ciphertext = temporary_root / "input.age"
        controlled_ciphertext.write_bytes(ciphertext_bytes)
        controlled_identity = temporary_root / "identity.txt"
        controlled_identity.write_bytes(_safe_read(age_identity_file))
        controlled_identity.chmod(0o600)
        archive = temporary_root / "package.zip"
        _run_age_decrypt(
            age_executable, controlled_identity, controlled_ciphertext, archive
        )
        files, manifest_bytes = _read_zip_closed(
            archive, max_file_bytes=max_file_bytes, max_total_bytes=max_total_bytes
        )
    manifest_sha = _sha256(manifest_bytes)
    if manifest_sha != _digest(expected_package_manifest_sha256, "package manifest"):
        raise OfficialPaidBatonError("package manifest commitment differs")
    manifest = _load_manifest(manifest_bytes)
    _verify_manifest_files(manifest, files)
    identity = BatonIdentity.from_record(manifest["identity"])
    predecessor = _optional_predecessor(manifest["predecessor"])
    return _VerifiedPackage(
        identity=identity,
        predecessor=predecessor,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_sha256=manifest_sha,
        files=files,
        ciphertext_sha256=_sha256(ciphertext_bytes),
        ciphertext_size_bytes=len(ciphertext_bytes),
    )


def _load_manifest(payload: bytes) -> Mapping[str, object]:
    if len(payload) > _MAX_MANIFEST_BYTES:
        raise OfficialPaidBatonError("package manifest exceeds size limit")
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialPaidBatonError("package manifest is not valid JSON") from exc
    record = _exact_object(
        value,
        {
            "schema_version",
            "kind",
            "identity",
            "predecessor",
            "input_package_manifest_sha256",
            "files",
            "file_count",
            "total_size_bytes",
        },
        "package manifest",
    )
    if record["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise OfficialPaidBatonError("package manifest schema differs")
    if record["kind"] not in {"source", "baton", "result"}:
        raise OfficialPaidBatonError("package kind differs")
    optional_digest = record["input_package_manifest_sha256"]
    if optional_digest is not None:
        _digest(optional_digest, "input package manifest")
    return record


def _verify_manifest_files(
    manifest: Mapping[str, object], files: Mapping[str, bytes]
) -> None:
    raw_rows = manifest["files"]
    if not isinstance(raw_rows, list):
        raise OfficialPaidBatonError("package file manifest must be an array")
    rows = cast(list[object], raw_rows)
    expected: dict[str, tuple[int, str]] = {}
    for raw in rows:
        row = _exact_object(raw, {"path", "size_bytes", "sha256"}, "file row")
        path = _safe_relative(_string(row, "path"))
        if path in expected:
            raise OfficialPaidBatonError("package manifest has duplicate paths")
        expected[path] = (
            _integer(row, "size_bytes"),
            _digest(row["sha256"], "file"),
        )
    if set(expected) != set(files):
        raise OfficialPaidBatonError("package files differ from closed manifest")
    for path, payload in files.items():
        if expected[path] != (len(payload), _sha256(payload)):
            raise OfficialPaidBatonError("package file commitment differs")
    if manifest["file_count"] != len(files) or manifest["total_size_bytes"] != sum(
        map(len, files.values())
    ):
        raise OfficialPaidBatonError("package aggregate commitment differs")
    if JOB_MANIFEST not in files:
        raise OfficialPaidBatonError("package lacks official job manifest")


def _read_zip_closed(
    archive_path: Path, *, max_file_bytes: int, max_total_bytes: int
) -> tuple[dict[str, bytes], bytes]:
    files: dict[str, bytes] = {}
    folded: set[str] = set()
    declared_total = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                name = _safe_relative(info.filename)
                if info.is_dir():
                    raise OfficialPaidBatonError("archive contains directory entries")
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type not in {0, stat.S_IFREG}:
                    raise OfficialPaidBatonError("archive member is not a regular file")
                if info.flag_bits & 1:
                    raise OfficialPaidBatonError("nested encrypted ZIP is forbidden")
                if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise OfficialPaidBatonError(
                        "archive compression method is forbidden"
                    )
                if name.casefold() in folded:
                    raise OfficialPaidBatonError("archive path collision")
                folded.add(name.casefold())
                if info.file_size > max_file_bytes:
                    raise OfficialPaidBatonError("archive member exceeds size limit")
                declared_total += info.file_size
                if declared_total > max_total_bytes:
                    raise OfficialPaidBatonError("archive exceeds total size limit")
                with archive.open(info) as handle:
                    chunks: list[bytes] = []
                    remaining = info.file_size
                    while remaining:
                        chunk = handle.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise OfficialPaidBatonError("archive member is truncated")
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    if handle.read(1):
                        raise OfficialPaidBatonError(
                            "archive member exceeds declared size"
                        )
                payload = b"".join(chunks)
                if name in files:
                    raise OfficialPaidBatonError("archive has duplicate paths")
                files[name] = payload
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise OfficialPaidBatonError(
            "decrypted baton is not a safe ZIP archive"
        ) from exc
    try:
        manifest = files.pop(PACKAGE_MANIFEST)
    except KeyError as exc:
        raise OfficialPaidBatonError("archive lacks package manifest") from exc
    names = set(files)
    for name in names:
        for parent in PurePosixPath(name).parents:
            rendered = parent.as_posix()
            if rendered != "." and rendered in names:
                raise OfficialPaidBatonError("archive path prefix collision")
    return files, manifest


def _scan_tree(
    root: Path,
    max_file_bytes: int,
    max_total_bytes: int,
    *,
    exclude_manifest: bool = False,
) -> dict[str, bytes]:
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise OfficialPaidBatonError("package root is unavailable") from exc
    if not stat.S_ISDIR(root_stat.st_mode) or root.is_symlink():
        raise OfficialPaidBatonError("package root must be a real directory")
    files: dict[str, bytes] = {}
    total = 0
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in list(dirnames):
            child = directory_path / name
            mode = child.lstat().st_mode
            if not stat.S_ISDIR(mode) or child.is_symlink():
                raise OfficialPaidBatonError(
                    "package tree contains non-unique regular path"
                )
        for name in filenames:
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            _safe_relative(relative)
            if relative == PACKAGE_MANIFEST and exclude_manifest:
                continue
            if relative == PACKAGE_MANIFEST:
                raise OfficialPaidBatonError(
                    "source uses reserved package manifest path"
                )
            payload = _safe_read(path)
            if len(payload) > max_file_bytes:
                raise OfficialPaidBatonError("package file exceeds size limit")
            total += len(payload)
            if total > max_total_bytes:
                raise OfficialPaidBatonError("package exceeds total size limit")
            files[relative] = payload
    return files


def _validate_job_package(
    files: Mapping[str, bytes],
    identity: BatonIdentity,
    *,
    require_inputs: bool,
    enforce_source_closure: bool,
) -> None:
    try:
        manifest = files[JOB_MANIFEST]
    except KeyError as exc:
        raise OfficialPaidBatonError("package lacks official job manifest") from exc
    try:
        validate_official_paid_labeling_job_package(
            manifest_bytes=manifest,
            files=files,
            release_sha=identity.release_sha,
            stage=identity.stage,
            provider=identity.provider,
            sequence=identity.sequence,
            require_inputs=require_inputs,
            enforce_source_closure=enforce_source_closure,
        )
    except OfficialPaidLabelingJobError as exc:
        raise OfficialPaidBatonError(str(exc)) from exc


def _journal_relative(files: Mapping[str, bytes]) -> str:
    try:
        value: object = json.loads(files[JOB_MANIFEST])
        arguments = cast(
            Mapping[str, object], cast(Mapping[str, object], value)["arguments"]
        )
        journal = arguments["provider-journal"]
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OfficialPaidBatonError(
            "job manifest lacks provider journal path"
        ) from exc
    if not isinstance(journal, str):
        raise OfficialPaidBatonError("provider journal path must be a string")
    return _safe_relative(journal)


def _checkpoint_provider_journal(root: Path, *, required: bool) -> None:
    files = _scan_tree(
        root, DEFAULT_MAX_FILE_BYTES, DEFAULT_MAX_TOTAL_BYTES, exclude_manifest=True
    )
    relative = _journal_relative(files)
    journal = root / relative
    if not journal.exists():
        if required:
            raise OfficialPaidBatonError("provider journal is required")
        return
    _safe_read(journal)
    for suffix in _SIDECAR_SUFFIXES:
        sidecar = Path(f"{journal}{suffix}")
        if sidecar.exists() or sidecar.is_symlink():
            _safe_read(sidecar)
    try:
        connection = sqlite3.connect(journal, timeout=0.0, isolation_level=None)
        try:
            rows = connection.execute(
                "SELECT schema_version, cycle_id, provider_cycle_caps_sha256, "
                "canonical_path FROM provider_journal_metadata"
            ).fetchall()
            if len(rows) != 1:
                raise OfficialPaidBatonError(
                    "provider journal identity is not singular"
                )
            schema, cycle_id, caps_sha, canonical_path = map(str, rows[0])
            if schema != PROVIDER_JOURNAL_SCHEMA_VERSION:
                raise OfficialPaidBatonError("provider journal schema differs")
            if Path(canonical_path) != journal.absolute():
                raise OfficialPaidBatonError("provider journal canonical path differs")
            caps_relative = _job_argument(files, "provider-cycle-caps")
            caps = _safe_read(root / caps_relative)
            try:
                caps_value: object = json.loads(caps)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise OfficialPaidBatonError("provider caps are invalid") from exc
            if not isinstance(caps_value, dict):
                raise OfficialPaidBatonError("provider caps are invalid")
            caps_record = cast(Mapping[str, object], caps_value)
            if caps_record.get("cycle_id") != cycle_id:
                raise OfficialPaidBatonError("provider journal cycle differs")
            if _sha256(caps) != caps_sha:
                raise OfficialPaidBatonError("provider journal caps identity differs")
            checkpoint = connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            if checkpoint is None or int(checkpoint[0]) != 0:
                raise OfficialPaidBatonError("provider journal WAL is busy")
            integrity = connection.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise OfficialPaidBatonError("provider journal integrity check failed")
        finally:
            connection.close()
        connection = sqlite3.connect(journal, timeout=0.0, isolation_level=None)
        try:
            mode = connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            if mode is None or str(mode[0]).lower() != "delete":
                raise OfficialPaidBatonError("provider journal cannot leave WAL mode")
        finally:
            connection.close()
    except OfficialPaidBatonError:
        raise
    except sqlite3.Error as exc:
        raise OfficialPaidBatonError("provider journal cannot be checkpointed") from exc
    for suffix in _SIDECAR_SUFFIXES:
        sidecar = Path(f"{journal}{suffix}")
        if sidecar.exists() or sidecar.is_symlink():
            raise OfficialPaidBatonError(
                "provider journal sidecar remains after checkpoint"
            )
    _safe_read(journal)


def _job_argument(files: Mapping[str, bytes], name: str) -> str:
    try:
        value = json.loads(files[JOB_MANIFEST])
        argument = value["arguments"][name]
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialPaidBatonError(f"job manifest lacks {name}") from exc
    if not isinstance(argument, str):
        raise OfficialPaidBatonError(f"job manifest {name} must be a string")
    return _safe_relative(argument)


def _verify_input_files(root: Path, manifest: Mapping[str, object]) -> None:
    rows = cast(list[object], manifest["files"])
    for raw in rows:
        row = cast(Mapping[str, object], raw)
        path = _safe_relative(_string(row, "path"))
        payload = _safe_read(root / path)
        if len(payload) != _integer(row, "size_bytes") or _sha256(payload) != _digest(
            row["sha256"], "input file"
        ):
            raise OfficialPaidBatonError(f"input package file changed: {path}")


def _install_package(package: _VerifiedPackage, destination: Path) -> None:
    _install_files(package.files, destination)
    _write_new(destination / PACKAGE_MANIFEST, package.manifest_bytes)


def _install_files(files: Mapping[str, bytes], destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise OfficialPaidBatonError("job root must not already exist")
    parent = destination.parent
    _assert_real_parent(parent)
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=parent))
    try:
        for relative, payload in sorted(files.items()):
            target = temporary / _safe_relative(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_new(target, payload)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _write_new_or_replace_manifest(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink():
        _safe_read(path)
        path.unlink()
    _write_new(path, payload)


def _write_new(path: Path, payload: bytes) -> None:
    _assert_real_parent(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags | nofollow, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OfficialPaidBatonError("output is not a unique regular file")
    finally:
        os.close(descriptor)


def _new_output(path: Path) -> None:
    _assert_real_parent(path.parent)
    if path.exists() or path.is_symlink():
        raise OfficialPaidBatonError("output path already exists")


def _unlink_owned_output(path: Path) -> None:
    try:
        if path.is_file() and not path.is_symlink():
            path.unlink()
    except OSError:
        # Cleanup is best-effort after the primary baton operation has failed.
        pass


def _run_age_encrypt(
    executable: Path, recipient: str, plaintext: Path, output: Path
) -> None:
    if not recipient.strip():
        raise OfficialPaidBatonError("age recipient is required")
    _run_age(
        executable,
        [
            "--encrypt",
            "--recipient",
            recipient,
            "--output",
            str(output),
            str(plaintext),
        ],
    )


def _run_age_decrypt(
    executable: Path, identity: Path, ciphertext: Path, output: Path
) -> None:
    _run_age(
        executable,
        [
            "--decrypt",
            "--identity",
            str(identity),
            "--output",
            str(output),
            str(ciphertext),
        ],
    )


def _run_age(executable: Path, arguments: list[str]) -> None:
    if not executable.is_absolute():
        raise OfficialPaidBatonError("age executable path must be absolute")
    try:
        resolved = executable.resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        raise OfficialPaidBatonError("age executable is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or not os.access(resolved, os.X_OK):
        raise OfficialPaidBatonError("age executable is not executable")
    try:
        completed = subprocess.run(
            [str(resolved), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=600,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OfficialPaidBatonError("age process could not complete") from exc
    if completed.returncode != 0:
        raise OfficialPaidBatonError("age process rejected the baton")


def _zip_write(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(_safe_relative(name), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    archive.writestr(info, payload)


def _safe_relative(value: str) -> str:
    if not value or "\\" in value or "\x00" in value or value.startswith("/"):
        raise OfficialPaidBatonError("unsafe archive path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts) or path.as_posix() != value:
        raise OfficialPaidBatonError("unsafe archive path")
    return value


def _safe_read(path: Path) -> bytes:
    try:
        return read_unique_regular_file(path)
    except ReviewBundleError as exc:
        raise OfficialPaidBatonError(
            f"path is not a unique regular file: {path}"
        ) from exc


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise OfficialPaidBatonError(f"{label} SHA-256 is invalid")
    return value


def _exact_object(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise OfficialPaidBatonError(f"{label} keys differ from exact schema")
    record = cast(dict[str, object], value)
    if set(record) != keys:
        raise OfficialPaidBatonError(f"{label} keys differ from exact schema")
    return record


def _string(record: Mapping[str, object], key: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value:
        raise OfficialPaidBatonError(f"{key} must be a nonempty string")
    return value


def _integer(record: Mapping[str, object], key: str) -> int:
    value = record[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OfficialPaidBatonError(f"{key} must be a nonnegative integer")
    return value


def _optional_predecessor(value: object) -> PredecessorBinding | None:
    return None if value is None else PredecessorBinding.from_record(value)


def _receipt_for_open(package: _VerifiedPackage) -> BatonReceipt:
    manifest = package.manifest
    input_sha = manifest["input_package_manifest_sha256"]
    return BatonReceipt(
        identity=package.identity,
        predecessor=package.predecessor,
        ciphertext_sha256=package.ciphertext_sha256,
        ciphertext_size_bytes=package.ciphertext_size_bytes,
        package_manifest_sha256=package.manifest_sha256,
        job_manifest_sha256=_sha256(package.files[JOB_MANIFEST]),
        input_package_manifest_sha256=(
            None if input_sha is None else _digest(input_sha, "input package manifest")
        ),
        file_count=_integer(manifest, "file_count"),
        total_size_bytes=_integer(manifest, "total_size_bytes"),
    )


def load_baton_receipt(path: Path) -> BatonReceipt:
    """Load one exact, unique, regular receipt emitted by this module."""

    payload = _safe_read(path)
    try:
        value: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficialPaidBatonError("baton receipt is not valid JSON") from exc
    return BatonReceipt.from_record(value)


def _assert_real_parent(parent: Path) -> None:
    absolute = Path(os.path.abspath(parent))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if not current.exists() and not current.is_symlink():
            continue
        try:
            info = current.lstat()
        except OSError as exc:
            raise OfficialPaidBatonError("output parent cannot be inspected") from exc
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise OfficialPaidBatonError(
                "output parent contains a symlink or special path"
            )

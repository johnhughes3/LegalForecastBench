from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cycle_path_metadata import (
    CyclePathMetadataError,
    _read_fd,
    materialize_cycle_path_metadata,
)


def _canonical(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=ValueError,
        error_message="test JSON is not canonical",
    )


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _parser_checkout(root: Path) -> str:
    root.mkdir()
    _git(root, "init", "--quiet")
    _git(root, "config", "user.name", "Cycle Test")
    _git(root, "config", "user.email", "cycle@example.test")
    (root / "parser.py").write_text("print('parser')\n", encoding="utf-8")
    _git(root, "add", "parser.py")
    _git(root, "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "parser")
    return _git(root, "rev-parse", "HEAD")


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, Path]:
    public_root = tmp_path / "public-cycle"
    target_root = public_root / "05-target-cohort-v4"
    target_root.mkdir(parents=True)
    private_root = tmp_path / "private-cycle"
    approval_root = private_root / "purchase-approval"
    approval_root.mkdir(parents=True)
    checkpoint = approval_root / "purchase-approval-checkpoint.json"
    checkpoint.write_bytes(
        _canonical(
            {
                "checkpoint": {
                    "verification_inputs": {
                        "target_cohort_root": str(target_root.resolve())
                    }
                },
                "checkpoint_sha256": "0" * 64,
                "schema_version": "legalforecast.purchase_approval_checkpoint.v1",
            }
        )
    )
    parser_root = tmp_path / "parser"
    parser_commit = _parser_checkout(parser_root)
    return checkpoint, parser_root, parser_commit, private_root


def _checkpoint_sha256(checkpoint: Path) -> str:
    return hashlib.sha256(checkpoint.read_bytes()).hexdigest()


def test_read_fd_rejects_ctime_only_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b"{}\n")
    descriptor = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    real_fstat = os.fstat
    calls = 0

    def changed_ctime(fd: int) -> os.stat_result:
        nonlocal calls
        metadata = real_fstat(fd)
        if fd != descriptor:
            return metadata
        calls += 1
        if calls == 1:
            return metadata
        values = list(metadata)
        values[9] = metadata.st_ctime + 1
        return os.stat_result(values)

    monkeypatch.setattr(os, "fstat", changed_ctime)
    try:
        with pytest.raises(CyclePathMetadataError, match="changed while reading"):
            _read_fd(descriptor, "cycle path metadata")
    finally:
        os.close(descriptor)


def test_materialize_cycle_path_metadata_derives_exact_successor_roots(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"

    record = materialize_cycle_path_metadata(
        approval_checkpoint=checkpoint,
        expected_approval_checkpoint_sha256=_checkpoint_sha256(checkpoint),
        parser_root=parser_root,
        expected_parser_commit=parser_commit,
        output=output,
    )

    assert record["schema_version"] == "legalforecast.cycle_path_metadata.v1"
    assert record["approval_checkpoint"] == str(checkpoint.resolve())
    assert record["successor_artifact_root"] == str(
        (tmp_path / "public-cycle").resolve()
    )
    assert record["successor_private_root"] == str(private_root.resolve())
    assert record["parser_root"] == str(parser_root.resolve())
    assert record["parser_commit"] == parser_commit
    assert (
        record["approval_checkpoint_sha256"]
        == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    )
    assert record["provider_activity_requested"] is False
    assert record["paid_activity_requested"] is False
    assert output.read_bytes() == _canonical(record)
    assert (
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=_checkpoint_sha256(checkpoint),
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
        == record
    )


def test_materialize_cycle_path_metadata_rejects_noncanonical_output_location(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)

    with pytest.raises(
        CyclePathMetadataError,
        match="output must be the canonical private cycle metadata path",
    ):
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=_checkpoint_sha256(checkpoint),
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=private_root / "other.json",
        )


def test_materialize_cycle_path_metadata_rejects_dirty_parser_checkout(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    (parser_root / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(CyclePathMetadataError, match="parser checkout must be clean"):
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=_checkpoint_sha256(checkpoint),
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=private_root / "cycle-path-metadata.json",
        )


def test_materialize_cycle_path_metadata_rejects_wrong_parser_commit(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, _, private_root = _fixture(tmp_path)

    with pytest.raises(CyclePathMetadataError, match="parser HEAD differs"):
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=_checkpoint_sha256(checkpoint),
            parser_root=parser_root,
            expected_parser_commit="f" * 40,
            output=private_root / "cycle-path-metadata.json",
        )


def test_materialize_cycle_path_metadata_cli_publishes_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"

    status = main(
        [
            "acquisition",
            "materialize-cycle-path-metadata",
            "--approval-checkpoint",
            str(checkpoint),
            "--expected-approval-checkpoint-sha256",
            _checkpoint_sha256(checkpoint),
            "--parser-root",
            str(parser_root),
            "--expected-parser-commit",
            parser_commit,
            "--output",
            str(output),
        ]
    )

    assert status == 0
    assert json.loads(capsys.readouterr().out) == json.loads(output.read_bytes())


def test_materialize_cycle_path_metadata_rejects_wrong_checkpoint_digest(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)

    with pytest.raises(CyclePathMetadataError, match="checkpoint SHA-256 differs"):
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256="f" * 64,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=private_root / "cycle-path-metadata.json",
        )


@pytest.mark.parametrize("stage_kind", ["empty", "truncated"])
def test_materialize_cycle_path_metadata_recovers_incomplete_stage(
    tmp_path: Path,
    stage_kind: str,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"
    checkpoint_sha256 = _checkpoint_sha256(checkpoint)
    expected = materialize_cycle_path_metadata(
        approval_checkpoint=checkpoint,
        expected_approval_checkpoint_sha256=checkpoint_sha256,
        parser_root=parser_root,
        expected_parser_commit=parser_commit,
        output=output,
    )
    payload = output.read_bytes()
    output.unlink()
    stage = private_root / (
        f".{output.name}.{hashlib.sha256(payload).hexdigest()}.partial"
    )
    residue = b"" if stage_kind == "empty" else payload[: len(payload) // 2]
    stage.write_bytes(residue)

    assert (
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=checkpoint_sha256,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
        == expected
    )
    assert output.read_bytes() == payload
    assert not stage.exists()


def test_materialize_cycle_path_metadata_syncs_recovered_stage_before_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"
    checkpoint_sha256 = _checkpoint_sha256(checkpoint)
    expected = materialize_cycle_path_metadata(
        approval_checkpoint=checkpoint,
        expected_approval_checkpoint_sha256=checkpoint_sha256,
        parser_root=parser_root,
        expected_parser_commit=parser_commit,
        output=output,
    )
    payload = output.read_bytes()
    output.unlink()
    stage = private_root / (
        f".{output.name}.{hashlib.sha256(payload).hexdigest()}.partial"
    )
    stage.write_bytes(payload)
    stage_metadata = stage.stat()
    stage_identity = (stage_metadata.st_dev, stage_metadata.st_ino)
    real_fsync = os.fsync
    real_link = os.link

    def is_stage(descriptor: int) -> bool:
        metadata = os.fstat(descriptor)
        return (metadata.st_dev, metadata.st_ino) == stage_identity

    def fail_stage_sync(descriptor: int) -> None:
        if is_stage(descriptor):
            raise OSError("simulated stage fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_stage_sync)
    with pytest.raises(CyclePathMetadataError, match="simulated stage fsync failure"):
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=checkpoint_sha256,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
    assert not output.exists()
    assert stage.read_bytes() == payload

    events: list[str] = []

    def record_fsync(descriptor: int) -> None:
        if is_stage(descriptor):
            events.append("stage fsync")
        real_fsync(descriptor)

    def record_link(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        events.append("link")
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setattr(os, "link", record_link)
    assert (
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=checkpoint_sha256,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
        == expected
    )
    assert events.index("stage fsync") < events.index("link")
    assert output.read_bytes() == payload
    assert not stage.exists()


def test_materialize_cycle_path_metadata_recovers_vanished_concurrent_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"
    checkpoint_sha256 = _checkpoint_sha256(checkpoint)
    expected = materialize_cycle_path_metadata(
        approval_checkpoint=checkpoint,
        expected_approval_checkpoint_sha256=checkpoint_sha256,
        parser_root=parser_root,
        expected_parser_commit=parser_commit,
        output=output,
    )
    payload = output.read_bytes()
    stage = private_root / (
        f".{output.name}.{hashlib.sha256(payload).hexdigest()}.partial"
    )
    stage.write_bytes(payload)

    def peer_removes_stage(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del destination, dst_dir_fd, follow_symlinks
        assert source == stage.name
        os.unlink(source, dir_fd=src_dir_fd)
        raise FileNotFoundError

    monkeypatch.setattr(os, "link", peer_removes_stage)
    assert (
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=checkpoint_sha256,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
        == expected
    )
    assert not stage.exists()


def test_materialize_cycle_path_metadata_recovers_linked_stage_residue(
    tmp_path: Path,
) -> None:
    checkpoint, parser_root, parser_commit, private_root = _fixture(tmp_path)
    output = private_root / "cycle-path-metadata.json"
    checkpoint_sha256 = _checkpoint_sha256(checkpoint)
    expected = materialize_cycle_path_metadata(
        approval_checkpoint=checkpoint,
        expected_approval_checkpoint_sha256=checkpoint_sha256,
        parser_root=parser_root,
        expected_parser_commit=parser_commit,
        output=output,
    )
    payload = output.read_bytes()
    stage = private_root / (
        f".{output.name}.{hashlib.sha256(payload).hexdigest()}.partial"
    )
    os.link(output, stage)

    assert output.stat().st_ino == stage.stat().st_ino
    assert output.stat().st_nlink == 2
    assert (
        materialize_cycle_path_metadata(
            approval_checkpoint=checkpoint,
            expected_approval_checkpoint_sha256=checkpoint_sha256,
            parser_root=parser_root,
            expected_parser_commit=parser_commit,
            output=output,
        )
        == expected
    )
    assert not stage.exists()
    assert output.read_bytes() == payload
    assert output.stat().st_nlink == 1

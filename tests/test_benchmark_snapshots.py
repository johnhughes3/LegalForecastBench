"""Archived benchmark snapshots match the audit pins; the verifier catches tampering."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tarfile
import zlib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MANIFEST = ROOT / "site" / "src" / "data" / "benchmark-snapshots.json"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = _load("verify_benchmark_snapshot")


def test_manifest_and_verifier_cite_the_commits_the_audits_pin() -> None:
    from legalforecast.multiharness.harvey_lab.core_runtime import UPSTREAM_COMMIT

    lab_pin = _load("harvey_dual_audit_core").PINNED
    lrb_pin = _load("legalreasonbench_extract").REVISION
    assert lab_pin == UPSTREAM_COMMIT
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cited = {s["archive"]: s["commit"] for s in manifest["snapshots"]}
    assert cited == {
        "harvey-labs-1dd81403.git.tar": lab_pin,
        "legalreasonbench-1bfa904c.git.tar": lrb_pin,
    }
    assert {f"{name}.tar": c for name, c in verifier.SNAPSHOTS.items()} == cited
    for snapshot in manifest["snapshots"]:
        assert snapshot["commit"].startswith(snapshot["archive"].split("-")[-1][:8])
        assert len(snapshot["sha256"]) == 64
    assert manifest["record_url"].endswith(manifest["doi"].rsplit(".", 1)[1])


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _snapshot(tmp_path: Path, files: dict[str, bytes]) -> tuple[Path, Path, str]:
    """A bare single-commit repo named like a real snapshot, plus its tar."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q")
    for name, data in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_bytes(data)
    _git(work, "add", ".")
    _git(
        work,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-qm",
        "snapshot",
    )
    bare = tmp_path / "demo.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(bare))
    return bare, tmp_path / "demo.git.tar", _git(bare, "rev-parse", "HEAD")


def _tar(bare: Path, archive: Path) -> Path:
    with tarfile.open(archive, "w") as tar:
        tar.add(bare, arcname=bare.name)
    return archive


def _expect(monkeypatch: pytest.MonkeyPatch, commit: str) -> None:
    monkeypatch.setattr(verifier, "SNAPSHOTS", {"demo.git": commit})


def test_verifier_accepts_an_intact_snapshot_and_extracts_lfs_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"real file bytes\n"
    digest = hashlib.sha256(content).hexdigest()
    pointer = (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\n"
        f"size {len(content)}\n"
    ).encode()
    bare, archive, head = _snapshot(tmp_path, {"a.txt": b"a\n", "big.bin": pointer})
    obj = bare / "lfs" / "objects" / digest[:2] / digest[2:4] / digest
    obj.parent.mkdir(parents=True)
    obj.write_bytes(content)
    _expect(monkeypatch, head)
    _tar(bare, archive)
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{verifier.sha256_file(archive)}  {archive.name}\n")
    out = tmp_path / "out"
    assert (
        verifier.main(["--sums", str(sums), "--extract", str(out), str(archive)]) == 0
    )
    assert (out / "demo" / "big.bin").read_bytes() == content


def test_verifier_rejects_wrong_commit_tampered_objects_and_lfs_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare, archive, head = _snapshot(tmp_path, {"a.txt": b"a\n"})
    _expect(monkeypatch, "0" * 40)
    with pytest.raises(verifier.VerificationError, match="HEAD is"):
        verifier.verify(_tar(bare, archive), None)

    _expect(monkeypatch, head)
    # Swap a.txt's content while keeping the object's name: a well-formed forgery.
    blob = _git(bare, "rev-parse", "HEAD:a.txt")
    loose = bare / "objects" / blob[:2] / blob[2:]
    loose.unlink()
    loose.write_bytes(zlib.compress(b"blob 2\0b\n"))
    with pytest.raises(verifier.VerificationError, match="fsck"):
        verifier.verify(_tar(bare, archive), None)


def test_verifier_rejects_a_missing_or_altered_lfs_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = hashlib.sha256(b"original").hexdigest()
    pointer = (
        f"version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize 8\n"
    ).encode()
    bare, archive, head = _snapshot(tmp_path, {"big.bin": pointer})
    _expect(monkeypatch, head)
    with pytest.raises(verifier.VerificationError, match="missing LFS object"):
        verifier.verify(_tar(bare, archive), None)
    obj = bare / "lfs" / "objects" / digest[:2] / digest[2:4] / digest
    obj.parent.mkdir(parents=True)
    obj.write_bytes(b"altered!")
    with pytest.raises(verifier.VerificationError, match="does not match its pointer"):
        verifier.verify(_tar(bare, archive), None)


def test_verifier_rejects_an_archive_that_fails_its_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare, archive, head = _snapshot(tmp_path, {"a.txt": b"a\n"})
    _expect(monkeypatch, head)
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{'0' * 64}  {_tar(bare, archive).name}\n")
    assert verifier.main(["--sums", str(sums), str(archive)]) == 1


def test_repository_verifier_is_the_copy_deposited_with_the_snapshots() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    deposited = manifest["verifier"]["sha256"]
    assert (
        verifier.sha256_file(SCRIPTS / "verify_benchmark_snapshot.py") == deposited
    ), (
        "scripts/verify_benchmark_snapshot.py differs from the copy in the Zenodo "
        "record; publish a new record version before changing it."
    )

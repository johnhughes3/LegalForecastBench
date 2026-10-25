"""Verify an archived benchmark snapshot against the commit the audits cite.

LegalForecastBench audited two third-party benchmarks at fixed commits: Harvey's
Legal Agent Benchmark (LAB) on GitHub and micro1's LegalReasonBench on Hugging Face.
Each audit snapshot is a tar of a bare, single-commit git repository. Git names every
object by a hash of its contents, so if ``git fsck --full`` passes and ``HEAD`` is the
cited commit, the files are exactly the files at that commit. A changed byte changes
the commit SHA. Hugging Face stores large files with Git LFS: the commit holds a
pointer recording each file's SHA-256 and size, and the snapshot carries the objects
under ``lfs/objects``, which this script hashes against the pointers.

This file has no dependencies beyond Python 3.10+ and ``git``, so a researcher can run
it on a downloaded snapshot without installing this repository::

    python3 verify_benchmark_snapshot.py harvey-labs-1dd81403.git.tar
    python3 verify_benchmark_snapshot.py --sums SHA256SUMS *.tar

It exits nonzero, naming the failed check, unless every snapshot verifies. Add
``--extract DIR`` to also write the snapshot's files to ``DIR/<snapshot name>``.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

# The commits the audits cite, keyed by the snapshot directory inside each tar.
SNAPSHOTS = {
    "harvey-labs-1dd81403.git": "1dd81403b2fbb60596f7aea3fcecafad7bf73143",
    "legalreasonbench-1bfa904c.git": "1bfa904c8f255925baf2610c0f86aa7c05d94ed9",
}

LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"


class VerificationError(Exception):
    """A snapshot failed one of the checks."""


# contract-ratchet: allow standalone verifier for researchers; must not import this repo
def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> bytes:
    """Run git against a bare repository, raising with git's stderr on failure."""
    result = subprocess.run(
        ["git", "--git-dir", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        raise VerificationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def check_sums(archives: list[Path], sums: Path) -> None:
    """Compare each archive's SHA-256 with its line in a SHA256SUMS file."""
    expected = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            expected[name.lstrip("*")] = digest
    for archive in archives:
        if archive.name not in expected:
            raise VerificationError(f"{archive.name} is not listed in {sums.name}")
        if sha256_file(archive) != expected[archive.name]:
            raise VerificationError(f"{archive.name} does not match {sums.name}")


def safe_extract(archive: Path, dest: Path) -> str:
    """Extract a snapshot tar, refusing links and paths outside ``dest``."""
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        roots = {Path(m.name).parts[0] for m in members}
        if len(roots) != 1:
            raise VerificationError(f"{archive.name} must hold one top-level directory")
        for member in members:
            target = (dest / member.name).resolve()
            if not (member.isfile() or member.isdir()):
                raise VerificationError(
                    f"{archive.name} holds a non-file: {member.name}"
                )
            if dest.resolve() not in target.parents and target != dest.resolve():
                raise VerificationError(f"{archive.name} escapes its directory")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, members=members, filter="data")
        else:
            tar.extractall(dest, members=members)
    return roots.pop()


def check_lfs(repo: Path) -> dict[str, Path]:
    """Hash every LFS object the commit points to; map each file path to its object."""
    objects: dict[str, Path] = {}
    for entry in git(repo, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        blob = git(repo, "cat-file", "blob", meta.split()[2].decode())
        if not blob.startswith(LFS_POINTER):
            continue
        fields = dict(
            line.split(" ", 1) for line in blob.decode().splitlines() if " " in line
        )
        digest, size = fields["oid"].removeprefix("sha256:"), int(fields["size"])
        obj = repo / "lfs" / "objects" / digest[:2] / digest[2:4] / digest
        name = path.decode(errors="replace")
        if not obj.is_file():
            raise VerificationError(f"missing LFS object for {name}")
        if obj.stat().st_size != size or sha256_file(obj) != digest:
            raise VerificationError(f"LFS object for {name} does not match its pointer")
        objects[name] = obj
    return objects


def verify(archive: Path, extract: Path | None) -> str:
    """Run every check on one snapshot and return a one-line summary."""
    with tempfile.TemporaryDirectory() as tmp:
        root = safe_extract(archive, Path(tmp))
        if root not in SNAPSHOTS:
            raise VerificationError(f"{archive.name}: unknown snapshot {root}")
        repo = Path(tmp) / root
        git(repo, "fsck", "--full", "--no-dangling")
        head = git(repo, "rev-parse", "HEAD").decode().strip()
        if head != SNAPSHOTS[root]:
            raise VerificationError(f"{root}: HEAD is {head}, cited {SNAPSHOTS[root]}")
        files = (
            len(git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD").split(b"\0"))
            - 1
        )
        lfs = check_lfs(repo)
        if extract is not None:
            out = extract / root.removesuffix(".git")
            out.mkdir(parents=True, exist_ok=False)
            git(repo, f"--work-tree={out}", "checkout", "-f", "HEAD", "--", ".")
            for name, obj in lfs.items():  # replace pointer files with their content
                (out / name).write_bytes(obj.read_bytes())
    lfs_note = f", {len(lfs)} LFS objects hashed" if lfs else ""
    return f"OK {archive.name}: HEAD {head}, git fsck passed, {files} files{lfs_note}"


def main(argv: list[str] | None = None) -> int:
    """Verify each snapshot named on the command line."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("archives", nargs="+", type=Path, help="snapshot .tar files")
    parser.add_argument("--sums", type=Path, help="SHA256SUMS file to check first")
    parser.add_argument(
        "--extract",
        type=Path,
        help="also write each snapshot's files under this directory",
    )
    args = parser.parse_args(argv)
    try:
        if args.sums:
            check_sums(args.archives, args.sums)
        for archive in args.archives:
            print(verify(archive, args.extract))
    except VerificationError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

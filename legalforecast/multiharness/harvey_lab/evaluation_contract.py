"""Fail-closed private-material commitments for Harvey LAB evaluation."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from legalforecast.contracts import RAW_BYTES_PREFIXED_SHA256_V1
from legalforecast.contracts.schemas import HARVEY_LAB_EVALUATION_INPUT_V2
from legalforecast.ingestion.canonical_json import canonical_json_value_bytes


class HarveyLabEvaluationError(ValueError):
    """Raised when isolated LAB evaluation cannot proceed fail-closed."""


def read_regular_file(path: Path) -> bytes:
    """Read one evaluator file without following a final symlink."""

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HarveyLabEvaluationError(
            f"evaluation path must be a regular file: {path.name}"
        ) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise HarveyLabEvaluationError(
                f"evaluation path must be a regular file: {path.name}"
            )
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)


def directory_digest(root: Path, field_name: str) -> str:
    """Return the commitment for one evaluator-private directory."""

    digest, _ = directory_snapshot(root, field_name)
    return digest


def directory_snapshot(root: Path, field_name: str) -> tuple[str, Mapping[str, bytes]]:
    """Return one directory commitment and the exact bytes it covers."""

    if root.is_symlink() or not root.is_dir():
        raise HarveyLabEvaluationError(f"{field_name} root must be a real directory")
    entries: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for path in _walk_regular_files(root, field_name):
        relative = path.relative_to(root).as_posix()
        payload = read_regular_file(path)
        payloads[relative] = payload
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    encoded = canonical_json_value_bytes(
        {"files": entries},
        error_type=HarveyLabEvaluationError,
        error_message=f"{field_name} is not canonically serializable",
    )
    commitment = RAW_BYTES_PREFIXED_SHA256_V1.commit(
        encoded, domain=HARVEY_LAB_EVALUATION_INPUT_V2
    )
    return str(commitment.digest), payloads


def harvey_lab_private_material_sha256(root: Path) -> str:
    """Hash the exact evaluator-private directory supplied to the judge."""

    return directory_digest(root, "private_material_sha256")


def harvey_lab_private_material_snapshot(
    root: Path,
) -> tuple[str, Mapping[str, bytes]]:
    """Return one digest and the exact private bytes used to compute it."""

    return directory_snapshot(root, "private_material_sha256")


def _walk_regular_files(root: Path, field_name: str) -> list[Path]:
    files: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError as exc:
            raise HarveyLabEvaluationError(f"{field_name} is unreadable") from exc
        for child in children:
            if child.is_symlink():
                raise HarveyLabEvaluationError(
                    f"{field_name} must not contain symlinks"
                )
            if child.is_dir():
                stack.append(child)
            elif child.is_file():
                files.append(child)
            else:
                raise HarveyLabEvaluationError(
                    f"{field_name} contains an unsupported entry"
                )
    return sorted(files)

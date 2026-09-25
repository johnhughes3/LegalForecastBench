"""Authenticated solver-input staging for the Claude Code container adapter."""

from __future__ import annotations

from pathlib import Path

from legalforecast.multiharness.release_harness import (
    ReleaseHarnessError,
    read_release_regular_file,
    write_release_create_only,
)
from legalforecast.multiharness.solver_inputs import SOLVER_INPUT_ENTRY_PATH


def stage_visible_solver_input(
    solver_input_root: Path,
    workspace: Path,
) -> tuple[list[tuple[Path, bytes]], list[Path]]:
    """Copy only the authenticated prompt and visible documents into workspace."""

    if not solver_input_root.is_dir() or solver_input_root.is_symlink():
        raise ReleaseHarnessError("authenticated solver input root is unavailable")
    workspace.mkdir(parents=True, exist_ok=True)
    files: list[tuple[Path, bytes]] = []
    for source in sorted(solver_input_root.rglob("*")):
        if source.is_symlink():
            raise ReleaseHarnessError("authenticated solver input contains a symlink")
        if source.is_dir():
            continue
        relative = source.relative_to(solver_input_root).as_posix()
        if relative != SOLVER_INPUT_ENTRY_PATH and not relative.startswith(
            "documents/"
        ):
            raise ReleaseHarnessError(
                f"authenticated solver input contains a hidden file: {relative}"
            )
        files.append((workspace / relative, read_release_regular_file(source)))
    if not any(
        path.relative_to(workspace).as_posix() == SOLVER_INPUT_ENTRY_PATH
        for path, _ in files
    ):
        raise ReleaseHarnessError("authenticated solver input prompt is missing")
    directories: list[Path] = []
    for path, payload in files:
        parent = path.parent
        missing: list[Path] = []
        while parent != workspace and not parent.exists():
            missing.append(parent)
            parent = parent.parent
        if parent != workspace and (parent.is_symlink() or not parent.is_dir()):
            raise ReleaseHarnessError("solver workspace path is not a directory")
        for directory in reversed(missing):
            directory.mkdir(mode=0o755)
            directories.append(directory)
        # The workspace itself is private. The staged files are 0444 so the
        # image's default UID can read them; production also mounts these paths
        # read-only when it runs as the rootless host owner.
        write_release_create_only(path, payload, mode=0o444)
    return files, directories


def verify_staged_solver_input(staged_files: list[tuple[Path, bytes]]) -> None:
    """Verify that staged authenticated bytes were unchanged by the run."""

    for path, expected in staged_files:
        observed = read_release_regular_file(path)
        if observed != expected:
            raise ReleaseHarnessError(
                f"staged solver input changed during execution: {path.name}"
            )


__all__ = ["stage_visible_solver_input", "verify_staged_solver_input"]

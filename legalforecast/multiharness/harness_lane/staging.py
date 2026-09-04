"""Stage the graded case packet into a tools-on container workspace.

Official ``SolverInputStore.materialize`` copies only ``solver_visible``
files. That is correct for the clean API/native lane, where the inspect
prompt already carries the case record. It is not permission to omit
``source/model-packet.json`` from a tools-on container: the agent has to
Read the packet at the path the prompt names. The halted stack measured
the prompt alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from legalforecast.immutable_io import (
    ImmutableIOError,
    read_single_link_file,
    write_file_create_only,
)
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SolverInputEntry,
    SolverInputFile,
    SolverInputStore,
)
from legalforecast.multiharness.spec import CanonicalTask
from legalforecast.multiharness.validation import validate_safe_relative_path

CONTAINER_WORKSPACE_ROOT = "/workspace"
GRADED_PACKET_RELATIVE_PATH = "source/model-packet.json"
# Bind-mounted workspaces keep host ownership; the live sandbox runs as
# 65532:65532, so other-execute/other-read bits are what that UID uses.
GRADED_DIRECTORY_MODE = 0o755
GRADED_FILE_MODE = 0o644


class HarnessLaneStagingError(ValueError):
    """Raised when a graded container workspace is missing the case packet."""


@dataclass(frozen=True, slots=True)
class StagedHarnessWorkspace:
    """Host tree plus the container paths a planned Read would use."""

    host_root: Path
    container_root: str
    packet_relative_path: str
    packet_sha256: str
    invoke_prompt: str
    planned_read_path: str
    planned_command: tuple[str, ...]


def default_invoke_prompt(packet_relative_path: str) -> str:
    """Return the tools-on prompt that names the packet the agent must Read."""

    validate_safe_relative_path(packet_relative_path, "packet path")
    return (
        "Read the case packet at "
        f"{packet_relative_path} "
        "and return only a valid forecast JSON object."
    )


def packet_path_named_by_prompt(prompt: str) -> str:
    """Return the relative packet path the invoke prompt names."""

    if GRADED_PACKET_RELATIVE_PATH not in prompt:
        raise HarnessLaneStagingError(
            "invoke prompt does not name source/model-packet.json"
        )
    return GRADED_PACKET_RELATIVE_PATH


def workspace_relative_files(root: Path) -> tuple[str, ...]:
    """Return the relative POSIX files currently in a workspace tree."""

    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )


def require_packet_staged(root: Path, *, invoke_prompt: str) -> str:
    """Refuse a prompt-only workspace before a graded invoke."""

    files = workspace_relative_files(root)
    named = packet_path_named_by_prompt(invoke_prompt)
    if set(files) <= {SOLVER_INPUT_ENTRY_PATH}:
        raise HarnessLaneStagingError(
            "graded container workspace contains only prompt.txt; "
            "the case packet is missing"
        )
    if named not in files:
        raise HarnessLaneStagingError(f"graded container workspace is missing {named}")
    return named


def stage_graded_container_workspace(
    store: SolverInputStore,
    task: CanonicalTask,
    *,
    destination_root: Path,
    invoke_prompt: str | None = None,
) -> StagedHarnessWorkspace:
    """Copy every solver-input file, including the not-visible packet."""

    if destination_root.exists():
        raise HarnessLaneStagingError("graded workspace destination must be fresh")
    entry = store.entry_for(task)
    packet = _packet_file(entry)
    prompt = invoke_prompt or default_invoke_prompt(packet.destination_path)
    named = packet_path_named_by_prompt(prompt)
    if named != packet.destination_path:
        raise HarnessLaneStagingError(
            "invoke prompt names a packet path that is not in the solver input"
        )
    try:
        destination_root.mkdir(parents=True)
        for item in entry.files:
            payload = read_single_link_file(
                store.root / item.source_path,
                label="solver input source",
            )
            destination = destination_root / item.destination_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_file_create_only(destination, payload, mode=GRADED_FILE_MODE)
        _apply_sandbox_readable_modes(destination_root)
    except (ImmutableIOError, OSError) as exc:
        raise HarnessLaneStagingError("graded workspace could not be staged") from exc
    require_packet_staged(destination_root, invoke_prompt=prompt)
    planned_read_path = f"{CONTAINER_WORKSPACE_ROOT}/{packet.destination_path}"
    return StagedHarnessWorkspace(
        host_root=destination_root,
        container_root=CONTAINER_WORKSPACE_ROOT,
        packet_relative_path=packet.destination_path,
        packet_sha256=packet.sha256,
        invoke_prompt=prompt,
        planned_read_path=planned_read_path,
        planned_command=("Read", planned_read_path),
    )


def read_container_workspace_file(
    staged: StagedHarnessWorkspace,
    container_path: str,
) -> bytes:
    """Read one staged file the way the planned container command would."""

    prefix = f"{staged.container_root.rstrip('/')}/"
    if not container_path.startswith(prefix):
        raise HarnessLaneStagingError("path is outside the planned container workspace")
    relative = validate_safe_relative_path(
        container_path[len(prefix) :],
        "container path",
    )
    try:
        return read_single_link_file(
            staged.host_root / relative,
            label="container workspace file",
        )
    except ImmutableIOError as exc:
        raise HarnessLaneStagingError(
            "planned container read path is unreadable"
        ) from exc


def _apply_sandbox_readable_modes(root: Path) -> None:
    """chmod after create so umask cannot leave a 0700 owner-only tree."""

    root.chmod(GRADED_DIRECTORY_MODE)
    for path in root.rglob("*"):
        if path.is_symlink():
            raise HarnessLaneStagingError("graded workspace contains a symlink")
        if path.is_dir():
            path.chmod(GRADED_DIRECTORY_MODE)
        elif path.is_file():
            path.chmod(GRADED_FILE_MODE)


def _packet_file(entry: SolverInputEntry) -> SolverInputFile:
    hidden = tuple(item for item in entry.files if not item.solver_visible)
    if len(hidden) != 1:
        raise HarnessLaneStagingError("solver input packet file is missing")
    packet = hidden[0]
    if packet.destination_path != GRADED_PACKET_RELATIVE_PATH:
        raise HarnessLaneStagingError("solver input packet path is unexpected")
    return packet

"""Harvey LAB CLI bridge adapter."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import (
    read_json_object,
    write_json_object,
    write_jsonl_objects,
)
from legalforecast.multiharness.adapters import AdapterError, AdapterPreparation
from legalforecast.multiharness.spec import (
    AdapterCapabilities,
    AdapterManifest,
    ArtifactRecord,
    RunRequest,
    RunResult,
)
from legalforecast.multiharness.validation import validate_public_record

HARVEY_LAB_ADAPTER_ID = "harvey-lab-cli"
HARVEY_LAB_ADAPTER_VERSION = "0.1.0"
_REQUIRED_FLAGS = ("--lab-root", "--output-dir")


class HarveyLabCliAdapterError(AdapterError):
    """Raised when the Harvey LAB CLI bridge cannot run safely."""


def harvey_lab_manifest() -> AdapterManifest:
    """Return the built-in Harvey LAB CLI adapter manifest."""

    return AdapterManifest(
        adapter_id=HARVEY_LAB_ADAPTER_ID,
        display_name="Harvey LAB CLI Adapter",
        adapter_version=HARVEY_LAB_ADAPTER_VERSION,
        command=("harness.run",),
    )


@dataclass(frozen=True, slots=True)
class HarveyLabCommandCapabilities:
    """Private probe record for a LAB CLI command."""

    lab_root: str
    lab_commit: str
    lab_source_sha256: str
    harness_run_help_sha256: str
    supported_flags: tuple[str, ...]
    evaluation_command: tuple[str, ...]
    evaluation_command_sha256: str
    sandbox_expectation: str
    blockers: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "lab_root": self.lab_root,
            "lab_commit": self.lab_commit,
            "lab_source_sha256": self.lab_source_sha256,
            "harness_run_help_sha256": self.harness_run_help_sha256,
            "supported_flags": list(self.supported_flags),
            "evaluation_command": list(self.evaluation_command),
            "evaluation_command_sha256": self.evaluation_command_sha256,
            "sandbox_expectation": self.sandbox_expectation,
            "blockers": list(self.blockers),
        }

    def to_compatibility_record(self) -> dict[str, Any]:
        """Return path-independent capability semantics for public hashing."""

        return {
            "identity_version": 1,
            "lab_commit": self.lab_commit,
            "lab_source_sha256": self.lab_source_sha256,
            "evaluation_command_sha256": self.evaluation_command_sha256,
            "supported_flags": list(self.supported_flags),
            "sandbox_expectation": self.sandbox_expectation,
            "blockers": list(self.blockers),
        }


@dataclass(slots=True)
class HarveyLabCliAdapter:
    """Run selected Harvey LAB tasks through a LAB-compatible CLI command."""

    lab_command: tuple[str, ...]
    lab_root: Path | None = None
    manifest: AdapterManifest = field(default_factory=harvey_lab_manifest)
    timeout_seconds: float = 300
    _planned_capabilities_sha256: str | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _cached_command_capabilities: HarveyLabCommandCapabilities | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        command_capabilities = self._cached_command_capabilities
        if command_capabilities is None:
            command_capabilities = self.command_capabilities(workspace)
            capabilities = self._record_capabilities(workspace, command_capabilities)
            self._cached_command_capabilities = command_capabilities
            return capabilities
        return self._record_capabilities(workspace, command_capabilities)

    def _record_capabilities(
        self,
        workspace: Path,
        command_capabilities: HarveyLabCommandCapabilities,
    ) -> AdapterCapabilities:
        write_json_object(
            workspace / "private-logs" / "lab-command-capabilities.json",
            command_capabilities.to_record(),
        )
        capabilities = AdapterCapabilities(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            supported_families=("harvey_lab",),
            supported_scoring_modes=("lab_native",),
            supports_sandbox_policy=True,
            capabilities_sha256=_record_sha256(
                command_capabilities.to_compatibility_record()
            ),
        )
        expected_sha256 = self._planned_capabilities_sha256
        if expected_sha256 is None:
            self._planned_capabilities_sha256 = capabilities.capabilities_sha256
        elif capabilities.capabilities_sha256 != expected_sha256:
            raise HarveyLabCliAdapterError(
                "LAB capabilities changed after run planning; start a new run"
            )
        return capabilities

    def command_capabilities(self, workspace: Path) -> HarveyLabCommandCapabilities:
        lab_root = self._resolved_lab_root()
        _validate_lab_root(lab_root)
        help_text = self._run_help_probe(workspace)
        supported_flags = _supported_flags(help_text)
        blockers = tuple(
            f"missing required LAB command flag {flag}"
            for flag in _REQUIRED_FLAGS
            if flag not in supported_flags
        )
        lab_commit, lab_source_sha256 = _lab_source_identity(lab_root)
        return HarveyLabCommandCapabilities(
            lab_root=lab_root.as_posix(),
            lab_commit=lab_commit,
            lab_source_sha256=lab_source_sha256,
            harness_run_help_sha256=_sha256_text(help_text),
            supported_flags=supported_flags,
            evaluation_command=self.lab_command,
            evaluation_command_sha256=_evaluation_command_sha256(
                self.lab_command,
                lab_root,
            ),
            sandbox_expectation=(
                "host adapter invokes LAB command; tool/container sandbox policy "
                "is recorded separately by the multi-harness runner"
            ),
            blockers=blockers,
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        self._validate_request(request)
        command_capabilities = self.command_capabilities(workspace)
        capabilities = self._record_capabilities(workspace, command_capabilities)
        if command_capabilities.blockers:
            formatted = "; ".join(command_capabilities.blockers)
            raise HarveyLabCliAdapterError(formatted)
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def _validate_request(self, request: RunRequest) -> None:
        if request.adapter.adapter_id != self.manifest.adapter_id:
            raise HarveyLabCliAdapterError(
                "run request adapter ID does not match manifest"
            )
        if request.adapter.adapter_version != self.manifest.adapter_version:
            raise HarveyLabCliAdapterError(
                "run request adapter version does not match manifest"
            )
        if request.task.family != "harvey_lab":
            raise HarveyLabCliAdapterError(
                "Harvey LAB adapter requires harvey_lab task"
            )
        if request.task.scoring_mode != "lab_native":
            raise HarveyLabCliAdapterError(
                "Harvey LAB adapter requires lab_native mode"
            )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self._validate_request(request)
        lab_root = self._resolved_lab_root()
        workspace.mkdir(parents=True, exist_ok=True)
        materialized_root = workspace / "lab-root"
        output_dir = workspace / "lab-output"
        private_logs = workspace / "private-logs"
        for directory in (materialized_root, output_dir, private_logs):
            _ensure_safe_workspace_directory(workspace, directory)
        _materialize_task(
            request,
            lab_root=lab_root,
            materialized_root=materialized_root,
        )
        write_json_object(workspace / "request.json", request.to_record())
        self.prepare(request, workspace)
        self._invoke_lab_command(
            lab_root=materialized_root,
            output_dir=output_dir,
            private_logs=private_logs,
        )
        scores_path = output_dir / "scores.json"
        scores = _read_json(scores_path, "LAB scores.json")
        normalized = normalize_lab_scores(scores, request)
        normalized_path = workspace / "lab-task-results.jsonl"
        write_jsonl_objects(normalized_path, normalized)
        artifacts = _result_artifacts(
            workspace,
            output_dir,
            scores_path,
            normalized_path,
        )
        public_summary = _public_summary(request, scores_path, normalized)
        result = RunResult(
            result_id=f"{request.request_id}:harvey-lab-result",
            request_id=request.request_id,
            status="succeeded",
            result_sha256=_record_sha256(
                {
                    "public_summary": public_summary,
                    "normalized": normalized,
                    "scores_sha256": _file_sha256(scores_path),
                }
            ),
            artifacts=artifacts,
            public_summary=public_summary,
        )
        write_json_object(workspace / "result.json", result.to_record())
        return result

    def _resolved_lab_root(self) -> Path:
        if self.lab_root is not None:
            return self.lab_root
        value = os.environ.get("HARVEY_LAB_ROOT")
        if value is None or not value.strip():
            raise HarveyLabCliAdapterError(
                "LAB root must be supplied with --lab-root or HARVEY_LAB_ROOT"
            )
        return Path(value)

    def _run_help_probe(self, workspace: Path) -> str:
        private_logs = workspace / "private-logs"
        _ensure_safe_workspace_directory(workspace, private_logs)
        completed = _run_subprocess(
            (*self.lab_command, "--help"),
            timeout_seconds=self.timeout_seconds,
            cwd=self._resolved_lab_root(),
        )
        (private_logs / "lab-help-stdout.log").write_text(
            completed.stdout,
            encoding="utf-8",
        )
        (private_logs / "lab-help-stderr.log").write_text(
            completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise HarveyLabCliAdapterError(
                f"LAB command --help failed with exit code {completed.returncode}"
            )
        return completed.stdout + "\n" + completed.stderr

    def _invoke_lab_command(
        self,
        *,
        lab_root: Path,
        output_dir: Path,
        private_logs: Path,
    ) -> None:
        completed = _run_subprocess(
            (
                *self.lab_command,
                "--lab-root",
                str(lab_root),
                "--output-dir",
                str(output_dir),
            ),
            timeout_seconds=self.timeout_seconds,
            cwd=self._resolved_lab_root(),
        )
        (private_logs / "lab-run-stdout.log").write_text(
            completed.stdout,
            encoding="utf-8",
        )
        (private_logs / "lab-run-stderr.log").write_text(
            completed.stderr,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise HarveyLabCliAdapterError(
                f"LAB command failed with exit code {completed.returncode}; "
                "see private logs"
            )


def normalize_lab_scores(
    scores: Mapping[str, Any],
    request: RunRequest,
) -> tuple[dict[str, Any], ...]:
    """Normalize a LAB scores.json payload into criterion summary rows."""

    rows = tuple(_score_rows(scores))
    normalized: list[dict[str, Any]] = []
    for row in rows:
        criterion_id = _required_str(row, "criterion_id")
        score = _required_number(row, "score")
        max_score = _optional_number(row, "max_score")
        normalized_score = score / max_score if max_score and max_score > 0 else score
        record = {
            "task_id": request.task.task_id,
            "lab_task_id": _lab_task_id(request),
            "adapter_id": request.adapter.adapter_id,
            "adapter_version": request.adapter.adapter_version,
            "model_key": request.model_key,
            "criterion_id": criterion_id,
            "score": score,
            "max_score": max_score,
            "normalized_score": normalized_score,
        }
        validate_public_record(record, "lab_score")
        normalized.append(record)
    if not normalized:
        raise HarveyLabCliAdapterError("LAB scores.json contains no criterion scores")
    return tuple(normalized)


def _materialize_task(
    request: RunRequest,
    *,
    lab_root: Path,
    materialized_root: Path,
) -> None:
    if not request.task.artifacts:
        raise HarveyLabCliAdapterError("Harvey LAB task has no source artifacts")
    resolved_lab_root = lab_root.resolve()
    resolved_materialized_root = materialized_root.resolve()
    for artifact in request.task.artifacts:
        source = lab_root / artifact.path
        if not source.is_file():
            raise HarveyLabCliAdapterError(
                f"LAB task artifact is missing: {artifact.path}"
            )
        try:
            source.resolve(strict=True).relative_to(resolved_lab_root)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HarveyLabCliAdapterError(
                f"LAB task artifact escapes the LAB root: {artifact.path}"
            ) from exc
        expected_sha256 = artifact.sha256.removeprefix("sha256:")
        destination = materialized_root / artifact.path
        _ensure_safe_destination_parent(materialized_root, Path(artifact.path).parent)
        try:
            destination.parent.resolve().relative_to(resolved_materialized_root)
        except (RuntimeError, ValueError) as exc:
            raise HarveyLabCliAdapterError(
                f"LAB task destination escapes the run workspace: {artifact.path}"
            ) from exc
        _copy_verified_artifact(
            source,
            destination,
            expected_sha256=expected_sha256,
            expected_size=artifact.size_bytes,
            artifact_path=artifact.path,
        )


def _ensure_safe_workspace_directory(workspace: Path, directory: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise HarveyLabCliAdapterError("LAB workspace directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        directory.resolve().relative_to(workspace.resolve())
    except (RuntimeError, ValueError) as exc:
        raise HarveyLabCliAdapterError(
            "LAB workspace directory escapes the run workspace"
        ) from exc


def _ensure_safe_destination_parent(root: Path, relative_parent: Path) -> None:
    current = root
    for part in relative_parent.parts:
        current /= part
        if current.is_symlink():
            raise HarveyLabCliAdapterError("LAB task destination contains a symlink")
        current.mkdir(exist_ok=True)
        if not current.is_dir():
            raise HarveyLabCliAdapterError(
                "LAB task destination parent is not a directory"
            )


def _copy_verified_artifact(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_size: int | None,
    artifact_path: str,
) -> None:
    if destination.is_symlink():
        raise HarveyLabCliAdapterError(
            f"LAB task destination must not be a symlink: {artifact_path}"
        )
    digest = hashlib.sha256()
    size_bytes = 0
    destination_created = False
    try:
        with (
            source.open("rb") as source_handle,
            destination.open("xb") as destination_handle,
        ):
            destination_created = True
            for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size_bytes += len(chunk)
                destination_handle.write(chunk)
    except OSError as exc:
        if destination_created:
            destination.unlink(missing_ok=True)
        raise HarveyLabCliAdapterError(
            f"could not materialize LAB task artifact: {artifact_path}"
        ) from exc
    if digest.hexdigest() != expected_sha256:
        destination.unlink(missing_ok=True)
        raise HarveyLabCliAdapterError(
            f"LAB task artifact hash mismatch: {artifact_path}"
        )
    if expected_size is not None and size_bytes != expected_size:
        destination.unlink(missing_ok=True)
        raise HarveyLabCliAdapterError(
            f"LAB task artifact size mismatch: {artifact_path}"
        )


def _result_artifacts(
    workspace: Path,
    output_dir: Path,
    scores_path: Path,
    normalized_path: Path,
) -> tuple[ArtifactRecord, ...]:
    artifacts = [
        _artifact_for(workspace, scores_path, artifact_id="lab-scores", public=True),
        _artifact_for(
            workspace,
            normalized_path,
            artifact_id="lab-task-results",
            media_type="application/jsonl",
            public=True,
        ),
    ]
    for private_path in sorted(output_dir.rglob("*")):
        if not private_path.is_file() or private_path == scores_path:
            continue
        artifacts.append(
            _artifact_for(
                workspace,
                private_path,
                artifact_id=f"private:{private_path.relative_to(output_dir).as_posix()}",
                public=False,
            )
        )
    return tuple(artifacts)


def _public_summary(
    request: RunRequest,
    scores_path: Path,
    normalized: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    score_sum = sum(_required_number(row, "normalized_score") for row in normalized)
    mean_score = score_sum / len(normalized)
    summary = {
        "task_id": request.task.task_id,
        "lab_task_id": _lab_task_id(request),
        "adapter_id": request.adapter.adapter_id,
        "model_key": request.model_key,
        "criterion_count": len(normalized),
        "mean_normalized_score": mean_score,
        "scores_sha256": _file_sha256(scores_path),
    }
    validate_public_record(summary, "lab_result.public_summary")
    return summary


def _score_rows(scores: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(scores.get("scores"), Sequence) and not isinstance(
        scores.get("scores"),
        str | bytes,
    ):
        return tuple(
            _require_mapping(item, "scores")
            for item in cast(Sequence[object], scores["scores"])
        )
    criteria = scores.get("criteria")
    if isinstance(criteria, Mapping):
        rows: list[Mapping[str, Any]] = []
        for key, value in cast(Mapping[object, object], criteria).items():
            row = dict(_require_mapping(value, "criteria"))
            row.setdefault("criterion_id", str(key))
            rows.append(row)
        return tuple(rows)
    raise HarveyLabCliAdapterError(
        "LAB scores.json must contain scores[] or criteria{}"
    )


def _artifact_for(
    root: Path,
    path: Path,
    *,
    artifact_id: str,
    public: bool,
    media_type: str = "application/json",
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=_file_sha256(path),
        media_type=media_type,
        public=public,
        size_bytes=path.stat().st_size,
    )


def _validate_lab_root(path: Path) -> None:
    if not path.is_dir():
        raise HarveyLabCliAdapterError(f"LAB root does not exist: {path}")
    if not (path / "tasks").is_dir():
        raise HarveyLabCliAdapterError(f"LAB root is missing tasks/: {path}")


def _lab_source_identity(path: Path) -> tuple[str, str]:
    lab_root = path.resolve(strict=True)
    git_root = Path(
        os.fsdecode(_git_output(lab_root, "rev-parse", "--show-toplevel")).strip()
    ).resolve(strict=True)
    try:
        lab_relative = lab_root.relative_to(git_root)
    except ValueError as exc:
        raise HarveyLabCliAdapterError(
            "LAB root is not contained by its Git worktree"
        ) from exc
    commit = os.fsdecode(_git_output(git_root, "rev-parse", "HEAD")).strip()
    tree_spec = (
        "HEAD^{tree}" if not lab_relative.parts else f"HEAD:{lab_relative.as_posix()}"
    )
    subtree_oid = os.fsdecode(_git_output(git_root, "rev-parse", tree_spec)).strip()
    scope = lab_relative.as_posix() if lab_relative.parts else "."
    unmerged = _git_paths(
        git_root,
        "diff",
        "--name-only",
        "-z",
        "--diff-filter=U",
        "--",
        scope,
    )
    if unmerged:
        raise HarveyLabCliAdapterError("LAB root contains unmerged Git paths")
    overlay_paths = set(
        _git_paths(
            git_root,
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            "HEAD",
            "--",
            scope,
        )
    )
    overlay_paths.update(
        _git_paths(
            git_root,
            "ls-files",
            "-z",
            "--others",
            "--exclude-standard",
            "--",
            scope,
        )
    )
    overlay_records = [
        _source_path_record(
            lab_root,
            _lab_scoped_path(git_root, lab_root, repo_relative),
        )
        for repo_relative in sorted(overlay_paths)
    ]
    special_records = _tracked_special_records(git_root, lab_root, scope)
    overlay_sha256 = _record_sha256({"files": overlay_records})
    source_sha256 = _record_sha256(
        {
            "identity_version": 1,
            "head_commit": commit,
            "head_subtree_oid": subtree_oid,
            "working_overlay_sha256": overlay_sha256,
            "tracked_symlinks": special_records,
        }
    )
    return commit, source_sha256


def _git_output(cwd: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(
            ("git", "-C", str(cwd), *args),
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise HarveyLabCliAdapterError(
            "could not inspect the LAB Git checkout"
        ) from exc
    if completed.returncode != 0:
        raise HarveyLabCliAdapterError(
            "LAB root must be a tracked path in a readable Git checkout"
        )
    return completed.stdout


def _git_paths(cwd: Path, *args: str) -> tuple[Path, ...]:
    return tuple(
        Path(os.fsdecode(value))
        for value in _git_output(cwd, *args).split(b"\0")
        if value
    )


def _lab_scoped_path(git_root: Path, lab_root: Path, repo_relative: Path) -> Path:
    candidate = git_root / repo_relative
    try:
        candidate.relative_to(lab_root)
    except ValueError as exc:
        raise HarveyLabCliAdapterError(
            "Git returned a path outside the LAB root"
        ) from exc
    return candidate


def _tracked_special_records(
    git_root: Path,
    lab_root: Path,
    scope: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in _git_output(
        git_root,
        "ls-files",
        "-s",
        "-z",
        "--",
        scope,
    ).split(b"\0"):
        if not entry:
            continue
        metadata, separator, raw_path = entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise HarveyLabCliAdapterError("Git returned malformed LAB index data")
        mode, _object_id, stage = fields
        if stage != b"0":
            raise HarveyLabCliAdapterError("LAB root contains unmerged Git paths")
        repo_relative = Path(os.fsdecode(raw_path))
        if mode == b"160000":
            raise HarveyLabCliAdapterError("LAB root must not contain Git submodules")
        if mode == b"120000":
            records.append(
                _source_path_record(
                    lab_root,
                    _lab_scoped_path(git_root, lab_root, repo_relative),
                )
            )
    return records


def _source_path_record(root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    if path.is_symlink():
        if Path(os.readlink(path)).is_absolute():
            raise HarveyLabCliAdapterError(
                f"LAB source symlinks must use relative targets: {relative}"
            )
        try:
            resolved = path.resolve(strict=True)
            target = resolved.relative_to(root)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HarveyLabCliAdapterError(
                f"LAB source symlink must resolve inside the LAB root: {relative}"
            ) from exc
        if resolved.is_dir():
            raise HarveyLabCliAdapterError(
                f"LAB source directory symlinks are not supported: {relative}"
            )
        if not resolved.is_file():
            raise HarveyLabCliAdapterError(
                f"LAB source symlinks must target regular files: {relative}"
            )
        return {
            "path": relative,
            "type": "symlink",
            "target": target.as_posix(),
            "target_sha256": _file_sha256(resolved),
            "target_executable": bool(resolved.stat().st_mode & 0o111),
        }
    if not path.exists():
        return {"path": relative, "type": "missing"}
    if not path.is_file():
        raise HarveyLabCliAdapterError(
            f"LAB source contains an unsupported non-file entry: {relative}"
        )
    return {
        "path": relative,
        "type": "file",
        "sha256": _file_sha256(path),
        "size_bytes": path.stat().st_size,
        "executable": bool(path.stat().st_mode & 0o111),
    }


def _evaluation_command_sha256(command: tuple[str, ...], lab_root: Path) -> str:
    arguments = [
        _command_argument_record(index, value, lab_root.resolve())
        for index, value in enumerate(command)
    ]
    return _record_sha256({"arguments": arguments})


def _command_argument_record(
    index: int,
    value: str,
    lab_root: Path,
) -> dict[str, Any]:
    candidate = _command_path(index, value, lab_root)
    if candidate is None:
        return {"index": index, "value": value}
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise HarveyLabCliAdapterError(
            f"LAB command path argument does not resolve: position {index}"
        ) from exc
    if resolved.is_dir():
        try:
            relative = resolved.relative_to(lab_root)
        except ValueError as exc:
            raise HarveyLabCliAdapterError(
                "LAB command directory arguments must resolve inside the LAB root"
            ) from exc
        return {
            "index": index,
            "type": "lab-directory",
            "path": relative.as_posix(),
        }
    if not resolved.is_file():
        raise HarveyLabCliAdapterError(
            f"LAB command argument is not a regular file: {candidate.name}"
        )
    try:
        relative = resolved.relative_to(lab_root)
    except ValueError:
        identity = {"name": candidate.name}
    else:
        identity = {"lab_path": relative.as_posix()}
    return {
        "index": index,
        "type": "file",
        **identity,
        "sha256": _file_sha256(resolved),
        "size_bytes": resolved.stat().st_size,
        "executable": bool(resolved.stat().st_mode & 0o111),
    }


def _command_path(index: int, value: str, lab_root: Path) -> Path | None:
    if index == 0:
        candidate = Path(value).expanduser()
        if "/" in value and not candidate.is_absolute():
            return lab_root / candidate
        resolved = shutil.which(value)
        return Path(resolved) if resolved is not None else candidate
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = lab_root / candidate
    if Path(value).is_absolute() or candidate.exists() or "/" in value:
        return candidate
    return None


def _supported_flags(help_text: str) -> tuple[str, ...]:
    return tuple(sorted(set(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", help_text))))


def _run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    if timeout_seconds <= 0:
        raise HarveyLabCliAdapterError("timeout_seconds must be positive")
    try:
        return subprocess.run(
            tuple(argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as exc:
        raise HarveyLabCliAdapterError(
            f"LAB command timed out after {timeout_seconds}s"
        ) from exc
    except OSError as exc:
        command = " ".join(str(part) for part in argv)
        raise HarveyLabCliAdapterError(
            f"LAB command could not start: {command}: {exc}"
        ) from exc


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
        path,
        error_factory=HarveyLabCliAdapterError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _lab_task_id(request: RunRequest) -> str:
    value = request.task.metadata.get("lab_task_id")
    if isinstance(value, str) and value.strip():
        return value
    return request.task.source_id


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HarveyLabCliAdapterError(f"{field_name} must be a non-empty string")
    return value


def _required_number(record: Mapping[str, Any], field_name: str) -> float:
    value = record.get(field_name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise HarveyLabCliAdapterError(f"{field_name} must be a number")
    return float(value)


def _optional_number(record: Mapping[str, Any], field_name: str) -> float | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise HarveyLabCliAdapterError(f"{field_name} must be a number")
    return float(value)


def _require_mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HarveyLabCliAdapterError(f"{field_name} entries must be objects")
    return cast(Mapping[str, Any], value)


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

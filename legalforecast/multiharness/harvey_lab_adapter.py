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
    harness_run_help_sha256: str
    supported_flags: tuple[str, ...]
    evaluation_command: tuple[str, ...]
    sandbox_expectation: str
    blockers: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "lab_root": self.lab_root,
            "lab_commit": self.lab_commit,
            "harness_run_help_sha256": self.harness_run_help_sha256,
            "supported_flags": list(self.supported_flags),
            "evaluation_command": list(self.evaluation_command),
            "sandbox_expectation": self.sandbox_expectation,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class HarveyLabCliAdapter:
    """Run selected Harvey LAB tasks through a LAB-compatible CLI command."""

    lab_command: tuple[str, ...]
    lab_root: Path | None = None
    manifest: AdapterManifest = field(default_factory=harvey_lab_manifest)
    timeout_seconds: float = 300

    def capabilities(self, workspace: Path) -> AdapterCapabilities:
        workspace.mkdir(parents=True, exist_ok=True)
        command_capabilities = self.command_capabilities(workspace)
        write_json_object(
            workspace / "lab-command-capabilities.json",
            command_capabilities.to_record(),
        )
        return AdapterCapabilities(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            supported_families=("harvey_lab",),
            supported_scoring_modes=("lab_native",),
            supports_sandbox_policy=True,
            capabilities_sha256=_record_sha256(command_capabilities.to_record()),
        )

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
        return HarveyLabCommandCapabilities(
            lab_root=lab_root.as_posix(),
            lab_commit=_lab_commit(lab_root),
            harness_run_help_sha256=_sha256_text(help_text),
            supported_flags=supported_flags,
            evaluation_command=self.lab_command,
            sandbox_expectation=(
                "host adapter invokes LAB command; tool/container sandbox policy "
                "is recorded separately by the multi-harness runner"
            ),
            blockers=blockers,
        )

    def prepare(self, request: RunRequest, workspace: Path) -> AdapterPreparation:
        capabilities = self.capabilities(workspace)
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
        command_capabilities = self.command_capabilities(workspace)
        if command_capabilities.blockers:
            formatted = "; ".join(command_capabilities.blockers)
            raise HarveyLabCliAdapterError(formatted)
        return AdapterPreparation(
            manifest=self.manifest,
            capabilities=capabilities,
            workspace=workspace,
        )

    def run(self, request: RunRequest, workspace: Path) -> RunResult:
        self.prepare(request, workspace)
        lab_root = self._resolved_lab_root()
        workspace.mkdir(parents=True, exist_ok=True)
        materialized_root = workspace / "lab-root"
        output_dir = workspace / "lab-output"
        private_logs = workspace / "private-logs"
        materialized_root.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        private_logs.mkdir(parents=True, exist_ok=True)
        _materialize_task(
            request,
            lab_root=lab_root,
            materialized_root=materialized_root,
        )
        write_json_object(workspace / "request.json", request.to_record())
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
        private_logs.mkdir(parents=True, exist_ok=True)
        completed = _run_subprocess(
            (*self.lab_command, "--help"),
            timeout_seconds=self.timeout_seconds,
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
    for artifact in request.task.artifacts:
        source = lab_root / artifact.path
        if not source.is_file():
            raise HarveyLabCliAdapterError(
                f"LAB task artifact is missing: {artifact.path}"
            )
        destination = materialized_root / artifact.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


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


def _lab_commit(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value:
        return "unknown"
    return value


def _supported_flags(help_text: str) -> tuple[str, ...]:
    return tuple(sorted(set(re.findall(r"--[A-Za-z][A-Za-z0-9-]*", help_text))))


def _run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
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
        )
    except subprocess.TimeoutExpired as exc:
        raise HarveyLabCliAdapterError(
            f"LAB command timed out after {timeout_seconds}s"
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
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _record_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

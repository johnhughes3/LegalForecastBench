"""Native LAB solving, separate evaluation, and public-safe score projection."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from legalforecast._canonical import canonical_json, sha256_file
from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.harvey_lab.core_runtime import (
    EVALUATE_MODULE,
    RUN_MODULE,
    LabCoreError,
    LabCoreRuntime,
    regular_files,
)
from legalforecast.multiharness.validation import (
    validate_no_secret_values,
    validate_public_record,
    validate_safe_relative_path,
)

_PROVIDER_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "MISTRAL_API_KEY",
        "FIREWORKS_API_KEY",
        "BASETEN_API_KEY",
    }
)


@dataclass(frozen=True)
class LabCoreRequest:
    """An explicit solver and single-judge measurement, never an implicit pair."""

    task_id: str
    model: str
    judge_model: str
    run_id: str
    max_turns: int
    sandbox_image: str
    provider_env: tuple[str, ...] = ()
    reasoning_effort: str | None = None
    timeout_seconds: float = 3600

    def __post_init__(self) -> None:
        validate_safe_relative_path(self.upstream_task_id, "LAB task ID")
        if len(Path(self.upstream_task_id).parts) < 2:
            raise LabCoreError("LAB task ID must include its category")
        for value in (self.model, self.judge_model, self.run_id, self.sandbox_image):
            if not value or value != value.strip() or any(ord(c) < 32 for c in value):
                raise LabCoreError("model, judge, run ID, and image must be explicit")
        if (
            type(self.max_turns) is not int
            or self.max_turns <= 0
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise LabCoreError("LAB turn and time limits must be positive")
        if not set(self.provider_env).issubset(_PROVIDER_NAMES):
            raise LabCoreError("only named model-provider variables may reach LAB")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.judge_model):
            raise LabCoreError("LAB judge must be one unqualified upstream model ID")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.sandbox_image):
            raise LabCoreError("LAB sandbox image must be an immutable local image ID")

    @property
    def upstream_task_id(self) -> str:
        """Return the upstream path behind the canonical family-prefixed ID."""
        return self.task_id.removeprefix("harvey_lab:")

    @property
    def upstream_run_id(self) -> str:
        """Map task/model/measurement identity to one safe, deterministic run ID."""
        payload = canonical_json([self.upstream_task_id, self.model, self.run_id])
        return "lfb-" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def run_lab_core(
    runtime: LabCoreRuntime, request: LabCoreRequest, output_dir: Path
) -> dict[str, object]:
    """Run the pinned native harness and judge, publishing only normalized scores.

    The caller owns spending approval. This function never retries or supplies
    credentials implicitly, and the upstream runtime owns its agent loop.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise LabCoreError("LAB output directory must be fresh")
    source = runtime.source_root.resolve(strict=True)
    output = output_dir.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise LabCoreError("LAB run output and source checkout must be disjoint")
    output.mkdir(parents=True, mode=0o700)
    private = output / "private"
    private.mkdir(mode=0o700)
    identity = runtime.probe(private)
    lab_root = private / "lab"
    task_record, input_hashes = _materialize_task(source, lab_root, request)
    criteria_ids = _criterion_ids(task_record)
    runtime.prepare_sandbox(private, request.sandbox_image)
    native_id = request.upstream_run_id
    run_root = lab_root / "results" / native_id
    argv = (
        "--task",
        request.upstream_task_id,
        "--model",
        request.model,
        "--run-id",
        native_id,
        "--max-turns",
        str(request.max_turns),
        "--sandbox-image",
        request.sandbox_image,
    )
    if request.reasoning_effort is not None:
        argv += ("--reasoning-effort", request.reasoning_effort)
    _verify_unchanged(runtime, private, identity, input_hashes)
    runtime.invoke(
        RUN_MODULE,
        argv,
        private_root=private,
        lab_root=lab_root,
        phase="solve",
        timeout=request.timeout_seconds,
        provider_env=request.provider_env,
    )
    _verify_unchanged(runtime, private, identity, input_hashes)
    if run_root.resolve(strict=True) != run_root:
        raise LabCoreError("LAB run root must not traverse symlinks")
    config = _read_result(run_root, "config.json")
    metrics = _read_result(run_root, "metrics.json")
    for record in (config, metrics):
        if any(
            record.get(key) != expected
            for key, expected in (
                ("task", request.upstream_task_id),
                ("model", request.model),
                ("run_id", native_id),
            )
        ):
            raise LabCoreError(
                "LAB run metadata does not match task/model/run identity"
            )
    if metrics.get("finished_cleanly") is not True:
        raise LabCoreError(
            "LAB solver did not finish cleanly; no evaluation was launched"
        )
    deliverables = _discover_outputs(run_root, task_record)
    runtime.invoke(
        EVALUATE_MODULE,
        (
            "--task",
            request.upstream_task_id,
            "--run-id",
            native_id,
            "--judges",
            request.judge_model,
            "--parallel",
            "1",
        ),
        private_root=private,
        lab_root=lab_root,
        phase="evaluate",
        timeout=request.timeout_seconds,
        provider_env=request.provider_env,
    )
    _verify_unchanged(runtime, private, identity, {**input_hashes, **deliverables})
    if _discover_outputs(run_root, task_record) != deliverables:
        raise LabCoreError("LAB output membership changed during evaluation")
    scores = _read_result(run_root, "scores.json")
    normalized = normalize_scores(scores, request, criteria_ids)
    normalized["source"] = identity
    normalized["settings"] = {
        "max_turns": request.max_turns,
        "sandbox_image": request.sandbox_image,
        "reasoning_effort": request.reasoning_effort,
    }
    normalized["artifacts"] = {
        path.relative_to(run_root / "output").as_posix(): digest
        for path, digest in sorted(deliverables.items())
    }
    values = runtime.environment(private, request.provider_env)
    validate_no_secret_values(
        normalized,
        tuple(values[name] for name in request.provider_env),
        "LAB public results",
    )
    validate_public_record(normalized, "LAB public results")
    public = output / "public"
    public.mkdir()
    write_json_object(public / "scores.json", normalized)
    (public / "NOTICE.txt").write_text(
        "Harvey LAB is a separate Harvey AI project. LegalForecastBench is not "
        "sponsored, partnered, or endorsed by Harvey AI. "
        "Upstream code is MIT licensed.\n\n"
        + (source / "LICENSE").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return normalized


def normalize_scores(
    scores: dict[str, object], request: LabCoreRequest, expected_ids: tuple[str, ...]
) -> dict[str, object]:
    """Validate the complete upstream result and drop rubric/reasoning text."""
    for key, expected in (
        ("run_id", request.upstream_run_id),
        ("task", request.upstream_task_id),
        ("judge_model", request.judge_model),
    ):
        if scores.get(key) != expected:
            raise LabCoreError(f"LAB scores have mismatched {key}")
    raw_rows = scores.get("criteria_results")
    if not isinstance(raw_rows, list):
        raise LabCoreError("LAB scores must contain criterion results")
    rows: dict[str, str] = {}
    for value in cast(list[object], raw_rows):
        if not isinstance(value, dict):
            raise LabCoreError("LAB criterion result must be an object")
        row = cast(dict[str, object], value)
        criterion_id, verdict = row.get("id"), row.get("verdict")
        if (
            not isinstance(criterion_id, str)
            or criterion_id in rows
            or verdict not in ("pass", "fail")
        ):
            raise LabCoreError(
                "LAB criterion IDs/verdicts are missing, duplicated, or invalid"
            )
        rows[criterion_id] = str(verdict)
    if set(rows) != set(expected_ids) or not rows:
        raise LabCoreError("LAB scores do not cover the exact task criteria")
    passed = sum(verdict == "pass" for verdict in rows.values())
    all_pass = passed == len(rows)
    for key, expected in (
        ("n_criteria", len(rows)),
        ("n_passed", passed),
        ("all_pass", all_pass),
    ):
        if type(scores.get(key)) is not type(expected) or scores[key] != expected:
            raise LabCoreError("LAB aggregate counts disagree with criterion verdicts")
    if (
        type(scores.get("score")) not in (int, float)
        or scores["score"] != int(all_pass)
        or type(scores.get("max_score")) not in (int, float)
        or scores.get("max_score") != 1
    ):
        raise LabCoreError("LAB all-pass score disagrees with criterion verdicts")
    return {
        "family": "harvey_lab",
        "task_id": "harvey_lab:" + request.upstream_task_id,
        "model": request.model,
        "judge_model": request.judge_model,
        "run_id": request.run_id,
        "upstream_run_id": request.upstream_run_id,
        "scoring": "lab-core-single-judge-all-pass",
        "score": int(all_pass),
        "n_criteria": len(rows),
        "n_passed": passed,
        "criterion_pass_rate": passed / len(rows),
        "criteria": [
            {"id": key, "passed": rows[key] == "pass"} for key in expected_ids
        ],
    }


def _materialize_task(
    source: Path, lab_root: Path, request: LabCoreRequest
) -> tuple[dict[str, object], dict[Path, str]]:
    task = source / "tasks" / request.upstream_task_id
    if task.is_symlink() or not task.resolve(strict=True).is_relative_to(
        source / "tasks"
    ):
        raise LabCoreError("LAB task escapes the source tasks root")
    record = _read_object(task / "task.json")
    docs_dir = record.get("docs_dir", "documents")
    if not isinstance(docs_dir, str):
        raise LabCoreError("LAB docs_dir must be a string")
    documents = (task / docs_dir).resolve(strict=True)
    if not documents.is_relative_to(source):
        raise LabCoreError("LAB document root escapes the pinned checkout")
    destination = lab_root / "tasks" / request.upstream_task_id
    destination.mkdir(parents=True)
    for name, path in regular_files(documents).items():
        target = destination / "documents" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    record["docs_dir"] = "documents"
    write_json_object(destination / "task.json", record)
    if (task / "instructions.md").exists():
        shutil.copyfile(task / "instructions.md", destination / "instructions.md")
    return record, {
        path: sha256_file(path) for path in regular_files(lab_root).values()
    }


def _criterion_ids(record: dict[str, object]) -> tuple[str, ...]:
    values = record.get("criteria")
    if not isinstance(values, list) or not values:
        raise LabCoreError("LAB task must have nonempty criteria")
    result: list[str] = []
    for value in cast(list[object], values):
        row = cast(dict[str, object], value) if isinstance(value, dict) else {}
        key = row.get("id")
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[\w.-]+", key)
            or key in result
        ):
            raise LabCoreError("LAB criterion IDs must be unique safe identifiers")
        result.append(key)
    return tuple(result)


def _discover_outputs(run_root: Path, task: dict[str, object]) -> dict[Path, str]:
    if run_root.resolve(strict=True) != run_root:
        raise LabCoreError("LAB run root must not traverse symlinks")
    output = run_root / "output"
    files = regular_files(output)
    if (
        not files
        or len(files) > 128
        or sum(path.stat().st_size for path in files.values()) > 512 * 1024 * 1024
    ):
        raise LabCoreError("LAB outputs are empty or exceed the supported bounds")
    declared = task.get("deliverables", {})
    if not isinstance(declared, dict):
        raise LabCoreError("LAB task deliverables must be a filename mapping")
    for name in cast(dict[str, object], declared).values():
        if not isinstance(name, str) or name not in files:
            raise LabCoreError("LAB solver omitted a declared output")
    return {path: sha256_file(path) for path in files.values()}


def _read_result(run_root: Path, name: str) -> dict[str, object]:
    path = run_root / name
    if (
        path.resolve() != path
        or not path.is_file()
        or path.stat().st_size > 16 * 1024 * 1024
    ):
        raise LabCoreError("LAB result must be a bounded regular file")
    return _read_object(path)


def _read_object(path: Path) -> dict[str, object]:
    return cast(
        dict[str, object],
        read_json_object(
            path,
            error_factory=LabCoreError,
            missing_message=lambda _path: "required LAB JSON file is missing",
            non_object_message=lambda _path: "LAB JSON must be an object",
        ),
    )


def _verify_unchanged(
    runtime: LabCoreRuntime,
    private: Path,
    identity: dict[str, str],
    files: dict[Path, str],
) -> None:
    if runtime.verify(private) != identity or any(
        path.is_symlink() or not path.is_file() or sha256_file(path) != digest
        for path, digest in files.items()
    ):
        raise LabCoreError("LAB source, launcher, task, or sealed output changed")

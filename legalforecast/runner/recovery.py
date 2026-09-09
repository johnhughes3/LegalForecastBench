"""Read-only planning and protected dispatch for official run recovery.

Recovery starts from artifacts produced by the source run. The source run's
frozen inputs and a cell ledger supply the original run identity; ``--ref``
only selects repaired orchestration code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Protocol, cast
from zipfile import BadZipFile, ZipFile

from legalforecast.runner.ledger import RunBinding, RunnerLedger, RunValidationError

SOURCE_WORKFLOW = ".github/workflows/run-benchmark.yaml"
RECOVERY_WORKFLOW = ".github/workflows/recover-benchmark.yaml"
RECOVERY_RUN_TITLE = "Recover benchmark {run_id} attempt {run_attempt}"
RECOVERY_CHILD_RUN_TITLE = "Run benchmark recovery {run_id} attempt {run_attempt}"
FORECAST_RUN_SCHEMA = "legalforecast.forecast-run.v1"
FORECAST_SUMMARY_SCHEMA = "legalforecast.forecast-run-summary.v1"
MAX_PARALLEL = 32


class RecoveryError(ValueError):
    """Raised when a source run cannot be safely recovered."""


class RecoveryClient(Protocol):
    """The GitHub API surface required by the read-only planner."""

    def get_run(self, repo: str, run_id: int) -> Mapping[str, object]: ...

    def list_artifacts(
        self, repo: str, run_id: int
    ) -> Sequence[Mapping[str, object]]: ...

    def download_artifact(self, repo: str, artifact_id: int) -> bytes: ...

    def list_active_recovery_runs(
        self, repo: str
    ) -> Sequence[Mapping[str, object]]: ...

    def dispatch(
        self,
        repo: str,
        workflow: str,
        ref: str,
        inputs: Mapping[str, str],
    ) -> None: ...


class GhRecoveryClient:
    """Use brokered ``gh`` access without opening AWS or provider access."""

    def _json_api(self, endpoint: str) -> object:
        result = self._run_gh(
            ("api", endpoint, "--header", "Accept: application/vnd.github+json"),
            endpoint=endpoint,
            text=True,
        )
        try:
            return json.loads(cast(str, result.stdout))
        except json.JSONDecodeError as exc:
            raise RecoveryError(
                f"GitHub API returned invalid JSON for {endpoint}"
            ) from exc

    def _json_pages(self, endpoint: str) -> tuple[Mapping[str, object], ...]:
        result = self._run_gh(
            (
                "api",
                "--paginate",
                "--slurp",
                endpoint,
                "--header",
                "Accept: application/vnd.github+json",
            ),
            endpoint=endpoint,
            text=True,
        )
        try:
            value: object = json.loads(cast(str, result.stdout))
        except json.JSONDecodeError as exc:
            raise RecoveryError(
                f"GitHub API returned invalid paginated JSON for {endpoint}"
            ) from exc
        if not isinstance(value, list):
            raise RecoveryError("GitHub paginated response must be an array")
        pages = cast(list[object], value)
        return tuple(_object(page, "GitHub API page") for page in pages)

    @staticmethod
    def _run_gh(
        arguments: Sequence[str],
        *,
        endpoint: str,
        text: bool,
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
                ["gh", *arguments],
                check=True,
                capture_output=True,
                text=text,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RecoveryError(f"GitHub request failed for {endpoint}") from exc

    def get_run(self, repo: str, run_id: int) -> Mapping[str, object]:
        return _object(
            self._json_api(f"repos/{repo}/actions/runs/{run_id}"),
            "workflow run",
        )

    def list_artifacts(self, repo: str, run_id: int) -> Sequence[Mapping[str, object]]:
        endpoint = f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
        artifacts: list[Mapping[str, object]] = []
        for page in self._json_pages(endpoint):
            raw_artifacts = page.get("artifacts")
            if not isinstance(raw_artifacts, list):
                raise RecoveryError("GitHub artifact response has no artifacts list")
            artifact_values = cast(list[object], raw_artifacts)
            artifacts.extend(
                _object(item, "workflow artifact") for item in artifact_values
            )
        return tuple(artifacts)

    def download_artifact(self, repo: str, artifact_id: int) -> bytes:
        endpoint = f"repos/{repo}/actions/artifacts/{artifact_id}/zip"
        result = self._run_gh(
            (
                "api",
                endpoint,
                "--header",
                "Accept: application/vnd.github+json",
                "--allow-escape-sequences",
            ),
            endpoint=endpoint,
            text=False,
        )
        return cast(bytes, result.stdout)

    def list_active_recovery_runs(self, repo: str) -> Sequence[Mapping[str, object]]:
        runs: list[Mapping[str, object]] = []
        for status in ("queued", "in_progress", "waiting", "pending", "requested"):
            value = _object(
                self._json_api(
                    f"repos/{repo}/actions/runs?event=workflow_dispatch&"
                    f"branch=main&status={status}&per_page=100"
                ),
                "workflow runs",
            )
            raw_runs = value.get("workflow_runs")
            if not isinstance(raw_runs, list):
                raise RecoveryError("GitHub workflow runs response has no runs list")
            run_values = cast(list[object], raw_runs)
            runs.extend(_object(item, "workflow run") for item in run_values)
        return tuple(runs)

    def dispatch(
        self,
        repo: str,
        workflow: str,
        ref: str,
        inputs: Mapping[str, str],
    ) -> None:
        command = ["gh", "workflow", "run", workflow, "--repo", repo, "--ref", ref]
        for key in sorted(inputs):
            command.extend(("--field", f"{key}={inputs[key]}"))
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RecoveryError("protected recovery workflow dispatch failed") from exc


@dataclass(frozen=True, slots=True)
class ArtifactLocator:
    """One immutable Actions artifact selected from the source run."""

    artifact_id: int
    name: str
    size_in_bytes: int
    expired: bool
    created_at: str | None
    expires_at: str | None

    def to_record(self) -> dict[str, object]:
        return {
            "id": self.artifact_id,
            "name": self.name,
            "size_in_bytes": self.size_in_bytes,
            "expired": self.expired,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True, slots=True)
class ArtifactCensus:
    """Counts from the source run's final artifact."""

    member_count: int
    document_member_count: int
    receipt_member_count: int
    transcript_member_count: int
    declared_state_count: int

    def to_record(self) -> dict[str, int]:
        return {
            "member_count": self.member_count,
            "document_member_count": self.document_member_count,
            "receipt_member_count": self.receipt_member_count,
            "transcript_member_count": self.transcript_member_count,
            "declared_state_count": self.declared_state_count,
        }


@dataclass(frozen=True, slots=True)
class FrozenRunIdentity:
    """Original inputs reconstructed from frozen artifacts and a cell ledger."""

    release_sha: str
    manifest_uri: str
    forecast_release_uri: str
    artifact_root_uri: str
    model_registry_uri: str
    model_key: str
    model_registry_sha256: str
    run_identity_sha256: str
    repeat_count: int
    account: str
    ceiling_microusd: int
    artifact_retention_days: int

    def to_record(self) -> dict[str, object]:
        return {
            "release_sha": self.release_sha,
            "manifest_uri": self.manifest_uri,
            "forecast_release_uri": self.forecast_release_uri,
            "artifact_root_uri": self.artifact_root_uri,
            "model_registry_uri": self.model_registry_uri,
            "model_key": self.model_key,
            "model_registry_sha256": self.model_registry_sha256,
            "run_identity_sha256": self.run_identity_sha256,
            "repeat_count": self.repeat_count,
            "account": self.account,
            "ceiling_microusd": self.ceiling_microusd,
            "artifact_retention_days": self.artifact_retention_days,
        }


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    """A read-only recovery plan and protected workflow request."""

    repo: str
    ref: str
    source_run_id: int
    source_run_attempt: int
    identity_source_attempt: int
    source_head_sha: str
    source_conclusion: str
    final_artifact: ArtifactLocator
    locked_inputs_artifact: ArtifactLocator
    state_artifacts: tuple[ArtifactLocator, ...]
    resume_sources: tuple[tuple[int, int], ...]
    frozen_identity: FrozenRunIdentity
    census: ArtifactCensus
    completed_cells: int
    incomplete_cells: int
    blocked_reasons: tuple[str, ...]
    dispatch_inputs: Mapping[str, str]

    @property
    def executable(self) -> bool:
        """Whether dispatching the protected workflow is safe."""

        return not self.blocked_reasons

    def to_record(self, *, execute_requested: bool = False) -> dict[str, object]:
        """Return the stable JSON record printed by the CLI."""

        if self.blocked_reasons:
            disposition = "blocked"
        elif execute_requested:
            disposition = "dispatch_requested"
        else:
            disposition = "ready"
        return {
            "schema_version": "legalforecast.benchmark-recovery-plan.v1",
            "command": "run resume",
            "disposition": disposition,
            "execute_requested": execute_requested,
            "repo": self.repo,
            "ref": self.ref,
            "source": {
                "run_id": self.source_run_id,
                "run_attempt": self.source_run_attempt,
                "identity_source_attempt": self.identity_source_attempt,
                "head_sha": self.source_head_sha,
                "conclusion": self.source_conclusion,
                "final_artifact": self.final_artifact.to_record(),
                "locked_inputs_artifact": self.locked_inputs_artifact.to_record(),
                "state_artifacts": [
                    artifact.to_record() for artifact in self.state_artifacts
                ],
                "census": self.census.to_record(),
            },
            "frozen_identity": self.frozen_identity.to_record(),
            "recovery": {
                "completed_cells": self.completed_cells,
                "incomplete_cells": self.incomplete_cells,
                "resume_sources": [
                    {"run_id": run_id, "run_attempt": attempt}
                    for run_id, attempt in self.resume_sources
                ],
                "billing_authority_checked": False,
                "blocked_reasons": list(self.blocked_reasons),
                "dispatch_inputs": dict(self.dispatch_inputs),
            },
        }


def build_recovery_plan(
    client: RecoveryClient,
    *,
    repo: str,
    run_id: int,
    ref: str,
    max_parallel: int,
) -> RecoveryPlan:
    """Inspect one terminal run and construct its protected recovery request."""

    _validate_request(repo=repo, run_id=run_id, ref=ref, max_parallel=max_parallel)
    run = client.get_run(repo, run_id)
    _validate_source_run(run, run_id=run_id)
    latest_attempt = _positive_int(run.get("run_attempt"), "workflow run attempt")
    source_head_sha = _digest(
        run.get("head_sha"), "workflow run head SHA", lengths=(40,)
    )
    source_conclusion = _text(run.get("conclusion"), "workflow run conclusion")

    artifacts = tuple(
        _artifact_locator(item) for item in client.list_artifacts(repo, run_id)
    )
    final_by_attempt = _attempt_artifacts(
        artifacts, rf"official-forecast-results-{run_id}-(?P<attempt>[1-9][0-9]*)"
    )
    inputs_by_attempt = _attempt_artifacts(
        artifacts,
        rf"locked-forecast-inputs-{run_id}-attempt-(?P<attempt>[1-9][0-9]*)",
    )
    state_by_attempt = _state_artifacts_by_attempt(artifacts)
    identity_attempts = sorted(
        set(final_by_attempt) & set(inputs_by_attempt) & set(state_by_attempt),
        reverse=True,
    )
    identity_attempts = [
        attempt for attempt in identity_attempts if attempt <= latest_attempt
    ]
    if not identity_attempts:
        raise RecoveryError("source run has no complete frozen identity artifact set")
    identity_attempt = identity_attempts[0]
    final_artifact = final_by_attempt[identity_attempt]
    locked_inputs = inputs_by_attempt[identity_attempt]

    census, export, summary, final_registry_bytes = _read_final_artifact(
        client.download_artifact(repo, final_artifact.artifact_id),
        run_id=run_id,
        run_attempt=identity_attempt,
    )
    locked_registry_bytes = _read_locked_inputs(
        client.download_artifact(repo, locked_inputs.artifact_id)
    )
    if locked_registry_bytes != final_registry_bytes:
        raise RecoveryError("final artifact changed the frozen model-registry bytes")
    expected_registry_sha = _digest(
        export.get("model_registry_sha256"),
        "model registry SHA-256",
        lengths=(64,),
    )
    if hashlib.sha256(locked_registry_bytes).hexdigest() != expected_registry_sha:
        raise RecoveryError("frozen model-registry bytes differ from source identity")

    binding, account, identity_repeat_count = _find_cell_binding(
        client,
        repo=repo,
        artifacts=state_by_attempt[identity_attempt],
    )
    model_key = _text(export.get("model_key"), "model_key")
    run_identity = _digest(
        export.get("run_identity_sha256"), "run identity SHA-256", lengths=(64,)
    )
    repeat_count = _positive_int(export.get("repeat_count"), "repeat_count")
    if binding.identity_sha256 != run_identity:
        raise RecoveryError("cell ledger run identity differs from fan-in export")
    if binding.model_key != model_key:
        raise RecoveryError("cell ledger model key differs from fan-in export")
    if binding.model_registry_sha256 != expected_registry_sha:
        raise RecoveryError("cell ledger model registry differs from frozen inputs")
    if identity_repeat_count != repeat_count:
        raise RecoveryError("cell ledger repeat count differs from fan-in export")

    frozen_identity = FrozenRunIdentity(
        release_sha=_digest(export.get("release_sha"), "release SHA", lengths=(40,)),
        manifest_uri=_text(export.get("manifest_uri"), "manifest_uri"),
        forecast_release_uri=_text(
            export.get("forecast_release_uri"), "forecast_release_uri"
        ),
        artifact_root_uri=_text(export.get("artifact_root_uri"), "artifact_root_uri"),
        model_registry_uri=_text(
            export.get("model_registry_uri"), "model_registry_uri"
        ),
        model_key=model_key,
        model_registry_sha256=expected_registry_sha,
        run_identity_sha256=run_identity,
        repeat_count=repeat_count,
        account=account,
        ceiling_microusd=binding.ceiling_microusd,
        artifact_retention_days=_artifact_retention_days(locked_inputs),
    )
    summary_completed = _nonnegative_int(
        summary.get("completed_cells"), "completed_cells"
    )
    if summary_completed not in {0, census.receipt_member_count}:
        raise RecoveryError("source summary completed count differs from receipts")
    completed_cells = census.receipt_member_count
    incomplete_cells = max(0, census.declared_state_count - completed_cells)

    resume_attempts = tuple(
        attempt
        for attempt in sorted(state_by_attempt, reverse=True)
        if attempt <= latest_attempt
    )
    resume_sources = tuple((run_id, attempt) for attempt in resume_attempts)
    state_artifacts = tuple(
        artifact
        for attempt in resume_attempts
        for artifact in state_by_attempt[attempt]
    )
    blocked: list[str] = []
    if final_artifact.expired or locked_inputs.expired:
        blocked.append("source run identity artifacts are expired")
    identity_states = state_by_attempt[identity_attempt]
    if any(artifact.expired for artifact in identity_states):
        blocked.append("one or more identity-attempt cell artifacts are expired")
    if len(identity_states) != census.declared_state_count:
        blocked.append(
            "identity-attempt cell artifact count differs from the source census"
        )
    if census.declared_state_count <= 0:
        blocked.append("source run does not declare a recoverable cell census")
    elif incomplete_cells == 0 and identity_attempt == latest_attempt:
        blocked.append("source run has no incomplete cells")
    expected_title = RECOVERY_RUN_TITLE.format(
        run_id=run_id, run_attempt=latest_attempt
    )
    current_workflow_run_id = _environment_run_id()
    if any(
        (current_workflow_run_id is None or active.get("id") != current_workflow_run_id)
        and (
            (
                active.get("path") == RECOVERY_WORKFLOW
                and active.get("display_title") == expected_title
            )
            or (
                active.get("path") == SOURCE_WORKFLOW
                and active.get("display_title")
                == RECOVERY_CHILD_RUN_TITLE.format(
                    run_id=run_id, run_attempt=latest_attempt
                )
            )
        )
        for active in client.list_active_recovery_runs(repo)
    ):
        blocked.append("an exact recovery workflow is already queued or running")

    dispatch_inputs = {
        "source_run_id": str(run_id),
        "source_run_attempt": str(latest_attempt),
        "ref": ref,
        "max_parallel": str(max_parallel),
        "execute": "true",
    }
    return RecoveryPlan(
        repo=repo,
        ref=ref,
        source_run_id=run_id,
        source_run_attempt=latest_attempt,
        identity_source_attempt=identity_attempt,
        source_head_sha=source_head_sha,
        source_conclusion=source_conclusion,
        final_artifact=final_artifact,
        locked_inputs_artifact=locked_inputs,
        state_artifacts=state_artifacts,
        resume_sources=resume_sources,
        frozen_identity=frozen_identity,
        census=census,
        completed_cells=completed_cells,
        incomplete_cells=incomplete_cells,
        blocked_reasons=tuple(blocked),
        dispatch_inputs=dispatch_inputs,
    )


def resolve_repository() -> str:
    """Resolve the GitHub repository without reading credentials or AWS state."""

    configured = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RecoveryError(
            "set GITHUB_REPOSITORY or run inside a Git checkout"
        ) from exc
    remote = result.stdout.strip()
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if remote.startswith(prefix):
            remote = remote.removeprefix(prefix)
            break
    if remote.endswith(".git"):
        remote = remote[:-4]
    if not _valid_repo(remote):
        raise RecoveryError("could not resolve repository in OWNER/NAME form")
    return remote


def _validate_request(*, repo: str, run_id: int, ref: str, max_parallel: int) -> None:
    if run_id <= 0:
        raise RecoveryError("--github-run must be a positive integer")
    if ref != "main":
        raise RecoveryError("recovery code must run from the main ref")
    if not 1 <= max_parallel <= MAX_PARALLEL:
        raise RecoveryError(f"--max-parallel must be between 1 and {MAX_PARALLEL}")
    if not _valid_repo(repo):
        raise RecoveryError("repository must be in OWNER/NAME form")


def _valid_repo(repo: str) -> bool:
    owner, separator, name = repo.partition("/")
    return bool(
        separator
        and owner
        and name
        and "/" not in name
        and not any(character.isspace() for character in repo)
    )


def _environment_run_id() -> int | None:
    value = os.environ.get("GITHUB_RUN_ID", "")
    return int(value) if value.isdecimal() and int(value) > 0 else None


def _validate_source_run(run: Mapping[str, object], *, run_id: int) -> None:
    if run.get("id") not in {None, run_id}:
        raise RecoveryError("workflow run ID differs from requested --github-run")
    if run.get("path") != SOURCE_WORKFLOW:
        raise RecoveryError("source run is not the benchmark workflow")
    if run.get("event") != "workflow_dispatch":
        raise RecoveryError("source run was not a manual benchmark dispatch")
    if run.get("head_branch") != "main":
        raise RecoveryError("source benchmark run was not dispatched from main")
    if run.get("status") != "completed":
        raise RecoveryError("source run has not reached a terminal state")
    _text(run.get("conclusion"), "workflow run conclusion")


def _artifact_locator(value: Mapping[str, object]) -> ArtifactLocator:
    size = value.get("size_in_bytes", 0)
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise RecoveryError("workflow artifact size is invalid")
    expired = value.get("expired", False)
    if not isinstance(expired, bool):
        raise RecoveryError("workflow artifact expired flag is invalid")
    return ArtifactLocator(
        artifact_id=_positive_int(value.get("id"), "workflow artifact id"),
        name=_text(value.get("name"), "workflow artifact name"),
        size_in_bytes=size,
        expired=expired,
        created_at=_optional_text(value.get("created_at")),
        expires_at=_optional_text(value.get("expires_at")),
    )


def _attempt_artifacts(
    artifacts: Sequence[ArtifactLocator], pattern: str
) -> dict[int, ArtifactLocator]:
    by_attempt: dict[int, ArtifactLocator] = {}
    compiled = re.compile(rf"^{pattern}$")
    for artifact in artifacts:
        match = compiled.fullmatch(artifact.name)
        if match is None:
            continue
        attempt = int(match.group("attempt"))
        if attempt in by_attempt:
            raise RecoveryError(f"duplicate source artifact for attempt {attempt}")
        by_attempt[attempt] = artifact
    return by_attempt


def _state_artifacts_by_attempt(
    artifacts: Sequence[ArtifactLocator],
) -> dict[int, tuple[ArtifactLocator, ...]]:
    grouped: dict[int, list[ArtifactLocator]] = {}
    pattern = re.compile(r"^locked-run-state-.+-attempt-(?P<attempt>[1-9][0-9]*)$")
    for artifact in artifacts:
        match = pattern.fullmatch(artifact.name)
        if match is not None:
            grouped.setdefault(int(match.group("attempt")), []).append(artifact)
    return {
        attempt: tuple(sorted(values, key=lambda artifact: artifact.name))
        for attempt, values in grouped.items()
    }


def _read_final_artifact(
    payload: bytes,
    *,
    run_id: int,
    run_attempt: int,
) -> tuple[ArtifactCensus, Mapping[str, object], Mapping[str, object], bytes]:
    with _open_zip(payload, "official results artifact") as archive:
        names = tuple(archive.namelist())
        _validate_member_names(names)
        export = _read_json_member(archive, "forecast-run.json")
        summary = _read_json_member(archive, "run-summary.json")
        try:
            registry_bytes = archive.read("model-registry.json")
        except KeyError as exc:
            raise RecoveryError(
                "official results artifact lacks model-registry.json"
            ) from exc
        if export.get("schema_version") != FORECAST_RUN_SCHEMA:
            raise RecoveryError("forecast-run.json has an unsupported schema")
        if summary.get("schema_version") != FORECAST_SUMMARY_SCHEMA:
            raise RecoveryError("run-summary.json has an unsupported schema")
        if export.get("workflow_run_id") != run_id:
            raise RecoveryError("forecast-run.json run ID differs from source run")
        if export.get("workflow_run_attempt") != run_attempt:
            raise RecoveryError("forecast-run.json attempt differs from source run")
        if summary.get("workflow_run_id") not in {None, run_id}:
            raise RecoveryError("run-summary.json run ID differs from source run")
        if summary.get("workflow_run_attempt") not in {None, run_attempt}:
            raise RecoveryError("run-summary.json attempt differs from source run")
        state_count = _nonnegative_int(
            summary.get("state_artifact_count"), "state_artifact_count"
        )
        return (
            ArtifactCensus(
                member_count=len(names),
                document_member_count=sum(
                    name.startswith("artifacts/documents/") for name in names
                ),
                receipt_member_count=sum(
                    name.startswith("receipts/") for name in names
                ),
                transcript_member_count=sum(
                    name.startswith("transcripts/") for name in names
                ),
                declared_state_count=state_count,
            ),
            export,
            summary,
            registry_bytes,
        )


def _read_locked_inputs(payload: bytes) -> bytes:
    with _open_zip(payload, "locked forecast inputs artifact") as archive:
        names = tuple(archive.namelist())
        _validate_member_names(names)
        for required in (
            "run-manifest.json",
            "forecast-release.json",
            "model-registry.json",
        ):
            if required not in names:
                raise RecoveryError(f"locked forecast inputs artifact lacks {required}")
        return archive.read("model-registry.json")


def _find_cell_binding(
    client: RecoveryClient,
    *,
    repo: str,
    artifacts: Sequence[ArtifactLocator],
) -> tuple[RunBinding, str, int]:
    failures = 0
    for artifact in artifacts:
        try:
            return _read_cell_ledger(
                client.download_artifact(repo, artifact.artifact_id)
            )
        except RecoveryError:
            failures += 1
    raise RecoveryError(
        f"none of {failures} identity-attempt cell artifacts has a valid run ledger"
    )


def _read_cell_ledger(payload: bytes) -> tuple[RunBinding, str, int]:
    with _open_zip(payload, "cell-state artifact") as archive:
        names = tuple(archive.namelist())
        _validate_member_names(names)
        ledger_names = [
            name for name in names if PurePosixPath(name).name == "ledger.sqlite3"
        ]
        if len(ledger_names) != 1:
            raise RecoveryError(
                "cell-state artifact must contain one ledger.sqlite3, found "
                f"{len(ledger_names)}"
            )
        ledger_bytes = archive.read(ledger_names[0])
    try:
        with TemporaryDirectory(prefix="lfb-recovery-ledger-") as directory:
            ledger_path = Path(directory) / "ledger.sqlite3"
            ledger_path.write_bytes(ledger_bytes)
            with RunnerLedger(ledger_path) as ledger:
                binding = ledger.read_run_binding()
    except (OSError, sqlite3.Error, RunValidationError) as exc:
        raise RecoveryError("cell-state artifact has an invalid run ledger") from exc
    identity = _object(json.loads(binding.identity_json), "cell ledger identity")
    account = _text(identity.get("account"), "cell ledger account")
    repeat_count = _positive_int(
        identity.get("repeat_count"), "cell ledger repeat count"
    )
    return binding, account, repeat_count


def _artifact_retention_days(artifact: ArtifactLocator) -> int:
    if artifact.created_at is None or artifact.expires_at is None:
        raise RecoveryError("locked inputs artifact lacks retention timestamps")
    try:
        created = datetime.fromisoformat(artifact.created_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(artifact.expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryError(
            "locked inputs artifact has invalid retention timestamps"
        ) from exc
    seconds = (expires - created).total_seconds()
    days = int((seconds + 86_399) // 86_400)
    if not 1 <= days <= 90:
        raise RecoveryError("locked inputs artifact has an invalid retention interval")
    return days


def _open_zip(payload: bytes, label: str) -> ZipFile:
    try:
        return ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise RecoveryError(f"{label} is not a valid ZIP") from exc


def _read_json_member(archive: ZipFile, name: str) -> Mapping[str, object]:
    try:
        payload = archive.read(name)
    except KeyError as exc:
        raise RecoveryError(f"official results artifact lacks {name}") from exc
    try:
        return _object(json.loads(payload), name)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"{name} is not valid JSON") from exc


def _validate_member_names(names: Sequence[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RecoveryError("workflow artifact contains an unsafe path")


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RecoveryError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RecoveryError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        parsed = value
    elif isinstance(value, str) and value.isdecimal():
        parsed = int(value)
    else:
        parsed = 0
    if parsed <= 0:
        raise RecoveryError(f"{label} must be a positive integer")
    return parsed


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RecoveryError(f"{label} must be a nonnegative integer")
    return value


def _digest(value: object, label: str, *, lengths: tuple[int, ...]) -> str:
    text = _text(value, label)
    if len(text) not in lengths or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise RecoveryError(f"{label} has an invalid lowercase hexadecimal digest")
    return text

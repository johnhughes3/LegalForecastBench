"""Brokered GitHub access for the read-only benchmark recovery planner."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from typing import cast


class RecoveryError(ValueError):
    """Raised when a source run cannot be safely recovered."""


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
        return tuple(recovery_object(page, "GitHub API page") for page in pages)

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
        return recovery_object(
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
                recovery_object(item, "workflow artifact") for item in artifact_values
            )
        return tuple(artifacts)

    def list_attempt_jobs(
        self, repo: str, run_id: int, run_attempt: int
    ) -> tuple[Mapping[str, object], ...]:
        endpoint = (
            f"repos/{repo}/actions/runs/{run_id}/attempts/{run_attempt}"
            "/jobs?per_page=100"
        )
        jobs: list[Mapping[str, object]] = []
        for page in self._json_pages(endpoint):
            values = page.get("jobs")
            if not isinstance(values, list):
                raise RecoveryError("GitHub attempt response has no jobs list")
            jobs.extend(
                recovery_object(item, "workflow job")
                for item in cast(list[object], values)
            )
        return tuple(jobs)

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
            value = recovery_object(
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
            runs.extend(recovery_object(item, "workflow run") for item in run_values)
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


def recovery_object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RecoveryError(f"{label} must be a JSON object")
    return cast(Mapping[str, object], value)

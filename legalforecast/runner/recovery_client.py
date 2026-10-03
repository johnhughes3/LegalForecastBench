"""Brokered GitHub access for the read-only benchmark recovery planner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast


class RecoveryError(ValueError):
    """Raised when a source run cannot be safely recovered."""


class GhRecoveryClient:
    """Use brokered ``gh`` access without opening AWS or provider access."""

    def __init__(self) -> None:
        # Only protected workflows opt into a pre-materialized, read-only cache.
        # Local planning never opens AWS or inherits operator credentials.
        value = os.environ.get("LFB_RECOVERY_ARCHIVE_DIR", "")
        self.archive_dir = (
            Path(value)
            if value and os.environ.get("GITHUB_ACTIONS") == "true"
            else None
        )
        self.archived: dict[int, Mapping[str, object]] = {}

    def _cached_artifacts(
        self, repo: str, run_id: int
    ) -> tuple[Mapping[str, object], ...]:
        if self.archive_dir is None:
            return ()
        index = recovery_object(
            json.loads((self.archive_dir / "index.json").read_text()), "archive cache"
        )
        if index.get("repository") != repo or index.get("run_id") != run_id:
            raise RecoveryError("archive cache does not match requested source run")
        values = index.get("artifacts")
        if not isinstance(values, list):
            raise RecoveryError("archive cache artifacts must be an array")
        records = tuple(
            recovery_object(item, "cached artifact")
            for item in cast(list[object], values)
        )
        seen: set[int] = set()
        for item in records:
            artifact_id = item.get("id")
            if type(artifact_id) is not int or artifact_id <= 0 or artifact_id in seen:
                raise RecoveryError(
                    "archive cache artifact ID is invalid or duplicated"
                )
            seen.add(artifact_id)
            self.archived[artifact_id] = item
        return records

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
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            # Preserve only fixed status categories. Raw stderr can contain
            # API response bodies or local configuration and stays private.
            status = re.search(r"\bHTTP ([1-5][0-9]{2})\b", stderr)
            detail = f"HTTP {status[1]}" if status else f"exit {exc.returncode}"
            if "rate limit" in stderr.lower():
                detail += "; rate_limit"
            elif "unknown flag:" in stderr.lower():
                detail += "; unsupported_cli_option"
            raise RecoveryError(
                f"GitHub request failed for {endpoint} ({detail})"
            ) from exc
        except OSError as exc:
            raise RecoveryError(
                f"GitHub request failed for {endpoint} (launch {type(exc).__name__})"
            ) from exc

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
        cached = self._cached_artifacts(repo, run_id)
        by_id = {item.get("id"): item for item in artifacts}
        for item in cached:
            original = by_id.get(item["id"])
            if original is not None and original.get("name") != item.get("name"):
                raise RecoveryError("archive cache artifact name differs from GitHub")
            by_id[item["id"]] = item
        return tuple(by_id.values())

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
        if self.archive_dir is not None:
            if not self.archived:
                index = recovery_object(
                    json.loads((self.archive_dir / "index.json").read_text()),
                    "archive cache",
                )
                if (
                    index.get("repository") != repo
                    or type(index.get("run_id")) is not int
                ):
                    raise RecoveryError("archive cache repository/run is invalid")
                self._cached_artifacts(repo, cast(int, index["run_id"]))
            cached = self.archived.get(artifact_id)
            if cached is not None:
                payload = (self.archive_dir / f"{artifact_id}.zip").read_bytes()
                if (
                    cached.get("digest")
                    != f"sha256:{hashlib.sha256(payload).hexdigest()}"
                ):
                    raise RecoveryError("archive cache ZIP digest mismatch")
                return payload
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

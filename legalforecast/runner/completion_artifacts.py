"""Exact artifact readers for native completion, using the shared ZIP extractor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile

from legalforecast.artifact_archive import extract_artifact
from legalforecast.runner.recovery import RecoveryClient
from legalforecast.runner.recovery_client import RecoveryError, recovery_object


def exact_artifact(client: RecoveryClient, repo: str, run_id: int, name: str) -> bytes:
    """Select exactly one unexpired named artifact belonging to this run."""
    matches = [
        item for item in client.list_artifacts(repo, run_id) if item.get("name") == name
    ]
    if len(matches) != 1 or matches[0].get("expired") is not False:
        raise RecoveryError(
            "exact completion artifact is missing, expired or ambiguous"
        )
    artifact_id = matches[0].get("id")
    if type(artifact_id) is not int or artifact_id <= 0:
        raise RecoveryError("completion artifact ID is invalid")
    return client.download_artifact(repo, artifact_id)


def artifact_record(payload: bytes, name: str) -> Mapping[str, object]:
    """Read a fixed metadata member without retaining private forecast inputs."""
    with TemporaryDirectory() as directory:
        root = Path(directory) / "artifact"
        unpack_artifact(payload, root)
        return read_record(root / name)


def read_record(path: Path) -> Mapping[str, object]:
    """Read JSON metadata with content-free failure messages."""
    try:
        return recovery_object(json.loads(path.read_bytes()), "completion metadata")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError("completion artifact lacks readable metadata") from exc


def dispatched_run_id(
    record: Mapping[str, object] | None, repo: str, workflow: str
) -> int | None:
    """Use only the exact validated CLI handoff; unresolved means stop."""
    if record is None or record.get("status") == "dispatched_unresolved":
        return None
    run_id = record.get("run_id")
    if (
        record.get("dispatched") is not True
        or record.get("repository") != repo
        or record.get("workflow")
        not in {workflow, workflow.removeprefix(".github/workflows/")}
        or record.get("ref") != "main"
        or type(run_id) is not int
        or run_id <= 0
        or record.get("run_url") != f"https://github.com/{repo}/actions/runs/{run_id}"
    ):
        raise RecoveryError("completion dispatch handoff identity is invalid")
    return run_id


def unpack_artifact(payload: bytes, destination: Path) -> None:
    """Reuse safe extraction while keeping failure output content-free."""
    try:
        extract_artifact(payload, destination)
    except (OSError, ValueError, BadZipFile) as exc:
        raise RecoveryError(
            "completion artifact could not be safely extracted"
        ) from exc

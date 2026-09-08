#!/usr/bin/env python3
"""Restore one completed forecast cell from the current or a source run."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

_ALLOWED_FILES = {
    "failure-summary.json",
    "ledger.sqlite3",
    "run-summary.json",
    "runner-failure.log",
    "state.json",
}
_STATE_ARTIFACT_PREFIX = "locked-run-state-"
_WORKFLOW_PATH = ".github/workflows/run-benchmark.yaml"


class IncompleteSourceState(Exception):
    """The source artifact is a known non-completed cell."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"durable state file is not JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"durable state file is not an object: {path.name}")
    return value


def _source_identity(source_run: dict[str, Any], run_id: str, attempt: int) -> None:
    if source_run.get("id") != int(run_id):
        raise ValueError("source workflow run identity does not match requested run")
    if source_run.get("run_attempt") != attempt:
        raise ValueError("source workflow run attempt does not match requested attempt")
    if source_run.get("path") != _WORKFLOW_PATH:
        raise ValueError("source workflow run is not the benchmark workflow")
    if source_run.get("event") != "workflow_dispatch":
        raise ValueError("source workflow run was not a manual benchmark dispatch")
    if source_run.get("head_branch") != "main":
        raise ValueError("source workflow run did not execute from main")
    if source_run.get("status") != "completed" or not isinstance(
        source_run.get("conclusion"), str
    ):
        raise ValueError("source workflow run is not terminal")


def _extract_artifacts(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list) and all(
        isinstance(item, dict) and "name" in item for item in value
    ):
        return value
    pages = value if isinstance(value, list) else [value]
    artifacts: list[Any] = []
    for page in pages:
        if isinstance(page, dict):
            page_artifacts = page.get("artifacts")
            if not isinstance(page_artifacts, list):
                raise ValueError("workflow artifact page lacks an artifacts list")
            artifacts.extend(page_artifacts)
        elif isinstance(page, list):
            artifacts.extend(page)
        else:
            raise ValueError("workflow artifact listing is not paginated JSON")
    if any(not isinstance(item, dict) for item in artifacts):
        raise ValueError("workflow artifact listing contains a non-object")
    return artifacts


def _unpack_state(archive: Path, destination: Path) -> None:
    allowed = _ALLOWED_FILES
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = Path(info.filename).parts
            if info.filename.endswith("/") and parts == ("receipts",):
                continue
            if (
                not info.filename
                or info.filename.startswith("/")
                or ".." in parts
                or len(parts) > 2
                or (len(parts) == 1 and parts[0] not in allowed)
                or (
                    len(parts) == 2
                    and (parts[0] != "receipts" or not parts[1].endswith(".json"))
                )
            ):
                raise ValueError("unexpected state archive path")
            if not info.filename.endswith("/"):
                output = destination / info.filename
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(bundle.read(info.filename))


def _validate_source_completed_state(
    root: Path, provider: str, cell_id: str, source_run_id: str, source_attempt: int
) -> None:
    state = _read_object(root / "state.json")
    if state.get("provider") != provider or state.get("cell_id") != cell_id:
        raise ValueError("source state identity does not match matrix cell")
    if (
        str(state.get("run_id")) != source_run_id
        or state.get("run_attempt") != source_attempt
    ):
        raise ValueError("source state run identity does not match requested attempt")
    if state.get("status") != "completed":
        raise IncompleteSourceState

    failure = _read_object(root / "failure-summary.json")
    summary = _read_object(root / "run-summary.json")
    if failure.get("status") != "completed" or summary.get("status") != "completed":
        raise ValueError("source state is marked completed but its summaries are not")
    ledger = root / "ledger.sqlite3"
    if ledger.is_symlink() or not ledger.is_file() or ledger.stat().st_size == 0:
        raise ValueError("completed source state has no durable ledger")
    # The runner validates this ledger and each receipt against the new run's
    # exact logical identity before it can issue or replay a provider call.
    receipts = root / "receipts"
    if not receipts.is_dir() or receipts.is_symlink():
        raise ValueError("completed source state has no receipt directory")
    receipt_paths = sorted(receipts.glob("*.json"))
    if not receipt_paths or any(
        path.is_symlink() or not path.is_file() for path in receipt_paths
    ):
        raise ValueError("completed source state has no durable receipts")
    for receipt_path in receipt_paths:
        _read_object(receipt_path)


def _download_artifact(artifact_id: int, archive: Path) -> None:
    try:
        subprocess.run(
            [
                "gh",
                "api",
                "--output",
                str(archive),
                f"/repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{artifact_id}/zip",
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "prior state download/API failure; refusing a fresh duplicate call"
        ) from exc


def _copy_state(
    source: Path, destination: Path, source_run_id: str, source_attempt: int
) -> None:
    for path in source.iterdir():
        if path.is_dir():
            shutil.copytree(path, destination / path.name, dirs_exist_ok=True)
        else:
            shutil.copyfile(path, destination / path.name)
    state_path = destination / "state.json"
    state = _read_object(state_path)
    state.update(
        {
            "restored_from_attempt": source_attempt,
            "restored_from_run_id": source_run_id,
            "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
            "run_id": os.environ["GITHUB_RUN_ID"],
            "status": "restored",
        }
    )
    state_path.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_artifacts(
    artifacts: list[dict[str, Any]],
    provider: str,
    slug: str,
    *,
    current_attempt: int | None = None,
    source_attempt: int | None = None,
) -> list[tuple[int, str, int]]:
    artifact_prefix = f"{_STATE_ARTIFACT_PREFIX}{provider}-{slug}-attempt-"
    pattern = re.compile(rf"^{re.escape(artifact_prefix)}([1-9][0-9]*)$")
    candidates: list[tuple[int, str, int]] = []
    for item in artifacts:
        name = item.get("name")
        artifact_id = item.get("id")
        created_at = item.get("created_at")
        match = pattern.fullmatch(name) if isinstance(name, str) else None
        if (
            item.get("expired") is not True
            and match is not None
            and isinstance(artifact_id, int)
            and isinstance(created_at, str)
        ):
            attempt = int(match.group(1))
            if (source_attempt is not None and attempt == source_attempt) or (
                source_attempt is None
                and current_attempt is not None
                and attempt < current_attempt
            ):
                candidates.append((attempt, created_at, artifact_id))
    return candidates


def _restore_candidates(
    candidates: list[tuple[int, str, int]],
    *,
    provider: str,
    cell_id: str,
    source_run_id: str | None,
    source_attempt: int | None,
) -> tuple[Path, int] | None:
    if not candidates:
        return None
    source_mode = source_run_id is not None
    if source_mode and len(candidates) != 1:
        raise ValueError("source run has duplicate state artifacts for this cell")

    candidates.sort(reverse=True)
    valid: tuple[Path, int] | None = None
    for attempt, _created, artifact_id in candidates:
        archive = Path(os.environ["RUNNER_TEMP"]) / f"forecast-state-{artifact_id}.zip"
        root = Path(os.environ["RUNNER_TEMP"]) / f"forecast-state-{artifact_id}"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir()
        _download_artifact(artifact_id, archive)
        try:
            _unpack_state(archive, root)
            state = _read_object(root / "state.json")
            _read_object(root / "failure-summary.json")
            if state.get("provider") != provider or state.get("cell_id") != cell_id:
                raise ValueError("state identity does not match artifact")
            if state.get("run_attempt") != attempt:
                raise ValueError("state attempt does not match artifact")
            if source_mode:
                if source_run_id is None or source_attempt is None:
                    raise ValueError("source workflow attempt is required")
                _validate_source_completed_state(
                    root, provider, cell_id, source_run_id, source_attempt
                )
            valid = (root, attempt)
            break
        except IncompleteSourceState:
            print("source state is not completed; allowing a fresh cell execution")
            return None
        except (
            OSError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
            zipfile.BadZipFile,
        ) as exc:
            if source_mode:
                raise ValueError(
                    "completed source state is corrupt; refusing a fresh duplicate call"
                ) from exc
            print(
                f"ignoring corrupt prior state attempt {attempt}: {exc}",
                file=sys.stderr,
            )
            continue

    if valid is None:
        raise ValueError(
            "all prior state artifacts were corrupt; refusing a fresh duplicate call"
        )
    return valid


def restore() -> None:
    provider = os.environ["PROVIDER"]
    cell_id = os.environ["CELL_ID"]
    slug = os.environ["CELL_ID_SLUG"]
    current_attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
    source_run_id = os.environ.get("RESUME_SOURCE_RUN_ID", "") or None
    source_attempt_raw = os.environ.get("RESUME_SOURCE_RUN_ATTEMPT", "")
    if source_run_id and not source_attempt_raw:
        raise ValueError("resume source run attempt is required with a source run ID")
    source_attempt = int(source_attempt_raw) if source_run_id else None
    if source_run_id and source_attempt is not None:
        source_run_metadata_path = os.environ.get("SOURCE_RUN_METADATA_PATH")
        if not source_run_metadata_path:
            raise ValueError(
                "source workflow metadata is required for cross-run restore"
            )
        _source_identity(
            _read_object(Path(source_run_metadata_path)), source_run_id, source_attempt
        )

    current_artifacts = _extract_artifacts(Path(os.environ["METADATA_PATH"]))
    current_candidates = _candidate_artifacts(
        current_artifacts, provider, slug, current_attempt=current_attempt
    )
    valid = _restore_candidates(
        current_candidates,
        provider=provider,
        cell_id=cell_id,
        source_run_id=None,
        source_attempt=None,
    )
    if valid is not None:
        root, attempt = valid
        run_root = Path(os.environ.get("LFB_RUN_ROOT", "/tmp/lfb-run"))
        _copy_state(root, run_root, os.environ["GITHUB_RUN_ID"], attempt)
        print(f"restore=attempt-{attempt}")
        return
    if current_candidates:
        # A current-run corrupt artifact must never be hidden by an external
        # source fallback. _restore_candidates raises in this case.
        raise ValueError(
            "all prior state artifacts were corrupt; refusing a fresh duplicate call"
        )
    if not source_run_id:
        print("restore=none")
        return
    source_artifacts_path = os.environ.get("SOURCE_METADATA_PATH")
    if not source_artifacts_path:
        raise ValueError("source workflow artifact metadata is required")
    source_artifacts = _extract_artifacts(Path(source_artifacts_path))
    source_candidates = _candidate_artifacts(
        source_artifacts, provider, slug, source_attempt=source_attempt
    )
    valid = _restore_candidates(
        source_candidates,
        provider=provider,
        cell_id=cell_id,
        source_run_id=source_run_id,
        source_attempt=source_attempt,
    )
    if valid is None:
        print("restore=none")
        return
    root, attempt = valid
    run_root = Path(os.environ.get("LFB_RUN_ROOT", "/tmp/lfb-run"))
    _copy_state(root, run_root, source_run_id, attempt)
    print(f"restore=run-{source_run_id}-attempt-{attempt}")


if __name__ == "__main__":
    try:
        restore()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from exc

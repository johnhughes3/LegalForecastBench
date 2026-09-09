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
    return _extract_artifact_value(json.loads(path.read_text(encoding="utf-8")))


def _extract_artifact_value(value: Any) -> list[dict[str, Any]]:
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


def _api_json(endpoint: str, *, paginate: bool = False) -> Any:
    command = ["gh", "api"]
    if paginate:
        command.extend(("--paginate", "--slurp"))
    command.append(endpoint)
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"workflow metadata API failure for {endpoint}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"workflow metadata API returned invalid JSON for {endpoint}"
        ) from exc


def _positive_decimal(value: Any, label: str) -> str:
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ValueError(f"{label} must be a positive integer")
    return text


def _resume_sources() -> list[tuple[str, int]]:
    raw_sources = os.environ.get("RESUME_SOURCES", "")
    legacy_id = os.environ.get("RESUME_SOURCE_RUN_ID", "")
    legacy_attempt = os.environ.get("RESUME_SOURCE_RUN_ATTEMPT", "")
    if raw_sources and (legacy_id or legacy_attempt):
        raise ValueError("resume_sources cannot be combined with legacy source inputs")
    if raw_sources:
        try:
            value = json.loads(raw_sources)
        except json.JSONDecodeError as exc:
            raise ValueError("resume_sources must be a JSON array") from exc
        if not isinstance(value, list) or not value or len(value) > 8:
            raise ValueError("resume_sources must contain between 1 and 8 sources")
        sources: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for entry in value:
            if not isinstance(entry, dict) or set(entry) != {"run_id", "run_attempt"}:
                raise ValueError(
                    "resume_sources entries require run_id and run_attempt"
                )
            run_id = _positive_decimal(entry["run_id"], "resume source run ID")
            attempt = int(
                _positive_decimal(entry["run_attempt"], "resume source run attempt")
            )
            source = (run_id, attempt)
            if source in seen:
                raise ValueError("resume_sources cannot contain duplicate sources")
            if run_id == os.environ.get("GITHUB_RUN_ID"):
                raise ValueError("resume source run must differ from the current run")
            seen.add(source)
            sources.append(source)
        return sources
    if legacy_id or legacy_attempt:
        if not legacy_id or not legacy_attempt:
            raise ValueError("legacy source run ID and attempt must both be set")
        run_id = _positive_decimal(legacy_id, "resume source run ID")
        if run_id == os.environ.get("GITHUB_RUN_ID"):
            raise ValueError("resume source run must differ from the current run")
        return [
            (
                run_id,
                int(_positive_decimal(legacy_attempt, "resume source run attempt")),
            )
        ]
    return []


def _unpack_state(archive: Path, destination: Path) -> None:
    allowed = _ALLOWED_FILES
    seen_paths: set[str] = set()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = Path(info.filename).parts
            if info.filename in seen_paths:
                raise ValueError("duplicate state archive path")
            seen_paths.add(info.filename)
            if info.filename.endswith("/") and parts in {
                ("receipts",),
                ("transcripts",),
            }:
                continue
            if (
                not info.filename
                or info.filename.startswith("/")
                or ".." in parts
                or len(parts) > 2
                or (len(parts) == 1 and parts[0] not in allowed)
                or (
                    len(parts) == 2
                    and (
                        parts[0] not in {"receipts", "transcripts"}
                        or not parts[1].endswith(".json")
                    )
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
    status = state.get("status")
    if status not in {"completed", "restored"}:
        if status == "failed" and _has_transcript_recovery(root, cell_id):
            _validate_source_transcript_recovery_state(root, cell_id)
            return
        raise IncompleteSourceState

    failure = _read_object(root / "failure-summary.json")
    summary = _read_object(root / "run-summary.json")
    if (
        status == "restored"
        and failure.get("status") == "failed"
        and summary.get("status") == "failed"
    ):
        if _has_transcript_recovery(root, cell_id):
            _validate_source_transcript_recovery_state(root, cell_id)
            return
        raise IncompleteSourceState
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
    _validate_transcript_files(root, cell_id)


def _has_transcript_recovery(root: Path, cell_id: str) -> bool:
    """Return whether a failed source has a terminal-result transcript candidate.

    This is only the archive-selection check.  The current run's recovery
    validator still parses the complete SDK history and verifies the prompt,
    tool pairing, forecast envelope, provider identity, and usage before it
    installs a replay payload.
    """

    transcripts = root / "transcripts"
    if not transcripts.is_dir() or transcripts.is_symlink():
        return False
    expected = transcripts / f"{cell_id}.json"
    if not expected.is_file() or expected.is_symlink():
        return False
    try:
        raw = expected.read_bytes()
    except OSError:
        return False
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        # A damaged artifact that still resembles a terminal transcript must
        # fail closed in the recovery validator instead of being treated as an
        # ordinary retry that could duplicate a provider call.
        return bool(
            re.search(rb'"agent_status"\s*:\s*"(?:succeeded|failed)"', raw)
            and re.search(rb'"messages"\s*:\s*\[\s*\{', raw)
            and re.search(rb'"tool_name"\s*:\s*"final_result"', raw)
        )
    return _has_terminal_result_candidate(value)


def _has_terminal_result_candidate(value: object) -> bool:
    """Recognize a nonempty SDK history containing a final-result tool call."""

    if not isinstance(value, dict) or value.get("agent_status") not in {
        "succeeded",
        "failed",
    }:
        return False
    messages = value.get("messages")
    if not isinstance(messages, list) or not messages:
        return False
    # Native structured output (for example Anthropic) has no final_result
    # tool call. Successful SDK histories still pass the strict recovery parser.
    if value.get("agent_status") == "succeeded":
        return True
    return any(
        isinstance(message, dict)
        and message.get("kind") == "response"
        and isinstance(parts := message.get("parts"), list)
        and any(
            isinstance(part, dict)
            and part.get("part_kind") == "tool-call"
            and part.get("tool_name") == "final_result"
            for part in parts
        )
        for message in messages
    )


def _validate_source_transcript_recovery_state(root: Path, cell_id: str) -> None:
    """Validate durable shape before the current run interprets a transcript.

    Transcript contents are validated only after the current run downloads its
    frozen registry and opens the copied ledger.  An invalid transcript then
    fails the provider job closed instead of allowing a duplicate call.
    """

    failure = _read_object(root / "failure-summary.json")
    summary = _read_object(root / "run-summary.json")
    if failure.get("status") != "failed" or summary.get("status") != "failed":
        raise ValueError("transcript recovery source is not consistently failed")
    ledger = root / "ledger.sqlite3"
    if ledger.is_symlink() or not ledger.is_file() or ledger.stat().st_size == 0:
        raise ValueError("transcript recovery source has no durable ledger")
    receipts = root / "receipts"
    if receipts.exists() and (receipts.is_symlink() or not receipts.is_dir()):
        raise ValueError("transcript recovery source has an unsafe receipt directory")
    if receipts.exists() and any(receipts.iterdir()):
        raise ValueError("transcript recovery source unexpectedly has a receipt")
    _validate_transcript_files(root, cell_id)
    transcript = root / "transcripts" / f"{cell_id}.json"
    if transcript.is_symlink() or not transcript.is_file():
        raise ValueError("transcript recovery source has no exact transcript")


def _download_artifact(artifact_id: int, archive: Path) -> None:
    try:
        with archive.open("wb") as output:
            subprocess.run(
                [
                    "gh",
                    "api",
                    "--allow-escape-sequences",
                    f"/repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{artifact_id}/zip",
                ],
                stdout=output,
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
        if path.name == "transcripts":
            continue
        if path.is_dir():
            shutil.copytree(path, destination / path.name, dirs_exist_ok=True)
        else:
            shutil.copyfile(path, destination / path.name)
    _copy_transcripts(source, destination)
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


def _validate_transcript_files(root: Path, cell_id: str) -> None:
    """Validate optional transcript paths without interpreting transcript bytes."""

    transcripts = root / "transcripts"
    if not transcripts.exists():
        return
    if transcripts.is_symlink() or not transcripts.is_dir():
        raise ValueError("durable transcript directory is unsafe")
    expected_name = f"{cell_id}.json"
    for path in transcripts.iterdir():
        if path.is_symlink() or not path.is_file() or path.name != expected_name:
            raise ValueError("durable transcript filename does not preserve cell ID")


def _copy_transcripts(source: Path, destination: Path) -> None:
    """Copy optional transcript bytes while refusing conflicting destinations."""

    source_transcripts = source / "transcripts"
    if not source_transcripts.exists():
        return
    if source_transcripts.is_symlink() or not source_transcripts.is_dir():
        raise ValueError("durable transcript directory is unsafe")
    destination_transcripts = destination / "transcripts"
    if destination_transcripts.exists() and (
        destination_transcripts.is_symlink() or not destination_transcripts.is_dir()
    ):
        raise ValueError("destination transcript directory is unsafe")
    destination_transcripts.mkdir(parents=True, exist_ok=True)
    for source_path in source_transcripts.iterdir():
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError("durable transcript is unsafe")
        destination_path = destination_transcripts / source_path.name
        source_bytes = source_path.read_bytes()
        if destination_path.exists() or destination_path.is_symlink():
            if (
                destination_path.is_symlink()
                or not destination_path.is_file()
                or destination_path.read_bytes() != source_bytes
            ):
                raise ValueError(
                    f"conflicting transcript destination: {destination_path.name}"
                )
            continue
        destination_path.write_bytes(source_bytes)


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
            _validate_transcript_files(root, cell_id)
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
    sources = _resume_sources()
    if not sources:
        print("restore=none")
        return
    repository = os.environ["GITHUB_REPOSITORY"]
    for source_run_id, source_attempt in sources:
        source_run = _api_json(
            f"/repos/{repository}/actions/runs/{source_run_id}/attempts/{source_attempt}"
        )
        if not isinstance(source_run, dict):
            raise ValueError("source workflow metadata is not an object")
        _source_identity(source_run, source_run_id, source_attempt)
        source_artifacts = _extract_artifact_value(
            _api_json(
                f"/repos/{repository}/actions/runs/{source_run_id}/artifacts?per_page=100",
                paginate=True,
            )
        )
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
            continue
        root, attempt = valid
        run_root = Path(os.environ.get("LFB_RUN_ROOT", "/tmp/lfb-run"))
        _copy_state(root, run_root, source_run_id, attempt)
        print(f"restore=run-{source_run_id}-attempt-{attempt}")
        return
    print("restore=none")


if __name__ == "__main__":
    try:
        restore()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise SystemExit(str(exc)) from exc

"""Preserve surviving GitHub artifact ZIPs through the protected S3 workflow."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from legalforecast.immutable_io import write_file_replace_safe

_HELPER = Path(__file__).resolve().parents[1] / ".github/scripts/reconcile-s3-object.sh"
_TIMEOUT = 900


def _validate(repository: str, bucket: str, archive_id: str, workers: int) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be OWNER/REPO")
    if any(part in {".", ".."} for part in repository.split("/")):
        raise ValueError("repository cannot contain path traversal")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("bucket must be an S3 bucket name")
    if not re.fullmatch(r"[1-9][0-9]*-[1-9][0-9]*", archive_id):
        raise ValueError("archive-id must be RUNID-ATTEMPT")
    if not 1 <= workers <= 8:
        raise ValueError("workers must be between 1 and 8")


def _snapshot(repository: str) -> list[dict[str, object]]:
    response = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/actions/artifacts?per_page=100",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )
    pages: object = json.loads(response.stdout)
    if not isinstance(pages, list):
        raise ValueError("GitHub artifact listing must contain pages")
    artifacts: list[dict[str, object]] = []
    seen: set[int] = set()
    total_count: int | None = None
    for page in cast(list[object], pages):
        if not isinstance(page, dict):
            raise ValueError("GitHub artifact page must be an object")
        page = cast(dict[str, object], page)
        count = page.get("total_count")
        if type(count) is not int or count < 0:
            raise ValueError("GitHub artifact page must declare total_count")
        if total_count is not None and count != total_count:
            raise ValueError("Artifact census changed during pagination; retry census")
        total_count = count
        if not isinstance(page.get("artifacts"), list):
            raise ValueError("GitHub artifact page is missing artifacts")
        for raw in cast(list[object], page["artifacts"]):
            if not isinstance(raw, dict):
                raise ValueError("GitHub artifact metadata must be an object")
            artifact = cast(dict[str, object], raw)
            artifact_id = artifact.get("id")
            if type(artifact_id) is not int or artifact_id <= 0:
                raise ValueError("GitHub artifact id must be a positive integer")
            if type(artifact.get("expired")) is not bool:
                raise ValueError("GitHub artifact must declare expiration state")
            if artifact_id in seen:
                raise ValueError(
                    "Duplicate artifact id in paginated listing; retry census"
                )
            seen.add(artifact_id)
            artifacts.append(artifact)
    if total_count is None or len(artifacts) != total_count:
        raise ValueError("Artifact census count does not match paginated results")
    return artifacts


def _upload(bucket: str, source: Path, key: str) -> None:
    subprocess.run(
        ["bash", str(_HELPER), bucket, str(source), key],
        check=True,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _error(exc: Exception) -> str:
    # Provider error output can include signed download URLs; never retain it.
    if isinstance(exc, subprocess.CalledProcessError):
        return f"command exited {exc.returncode}"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "command timed out"
    return type(exc).__name__


def _write(path: Path, value: dict[str, object]) -> None:
    write_file_replace_safe(path, (json.dumps(value, indent=2) + "\n").encode())


def _batch_size(deadline: float, reserve: int = 10) -> int:
    while True:
        response = subprocess.run(
            ["gh", "api", "rate_limit", "--jq", ".resources.core"],
            check=True,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
        quota = cast(dict[str, object], json.loads(response.stdout))
        remaining, reset = quota.get("remaining"), quota.get("reset")
        if type(remaining) is not int or remaining < 0 or type(reset) is not int:
            raise ValueError("Invalid GitHub core quota")
        if remaining > reserve:
            return min(200, remaining - reserve)
        delay = reset - time.time() + 1
        if not 0 < delay <= 3660 or time.monotonic() + delay > deadline:
            raise ValueError("GitHub quota reset exceeds bounded download wait")
        print(
            f"GitHub core quota reserve reached; waiting {delay:.0f}s for reset",
            flush=True,
        )
        time.sleep(delay)


def _download_phase(
    repository: str, bucket: str, archive_id: str, output_dir: Path, workers: int
) -> int:
    deadline = time.monotonic() + 7200
    _batch_size(deadline, reserve=50)
    artifacts = _snapshot(repository)
    available = [artifact for artifact in artifacts if not artifact["expired"]]
    expired = [artifact for artifact in artifacts if artifact["expired"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"reports/github-artifacts/multi-ablation/{repository}/"
    index: dict[str, object] = {
        "repository": repository,
        "archive_id": archive_id,
        "started_at": datetime.now(UTC).isoformat(),
        "bucket": bucket,
        "prefix": prefix,
        "scope": "Artifacts listed at start; artifacts created later are not included.",
        "listed_count": len(artifacts),
        "available_count": len(available),
        "skipped_expired_count": len(expired),
        "skipped_expired": expired,
        "status": "in_progress",
        "available": available,
    }
    _write(output_dir / "archive-snapshot.json", index)
    results: list[dict[str, object]] = [
        {
            "artifact": artifact,
            "key": f"{prefix}artifacts/{artifact['id']}.zip",
            "status": "failed",
            "error": "not downloaded",
        }
        for artifact in available
    ]
    index["results"] = results
    state_path = output_dir / "download-state.json"
    _write(state_path, index)

    def download(artifact: dict[str, object]) -> dict[str, object]:
        identifier = artifact["id"]
        result: dict[str, object] = {
            "artifact": artifact,
            "key": f"{prefix}artifacts/{identifier}.zip",
        }
        destination = output_dir / f"{identifier}.zip"
        try:
            # Opaque bytes only; never extract or execute artifact contents.
            with destination.open("wb") as stream:
                subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{repository}/actions/artifacts/{identifier}/zip",
                    ],
                    check=True,
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    timeout=_TIMEOUT,
                )
            if destination.stat().st_size == 0:
                raise ValueError("GitHub returned an empty artifact archive")
            result.update(status="downloaded", archive_bytes=destination.stat().st_size)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result.update(status="failed", error=_error(exc))
        return result

    cursor = 0
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while cursor < len(available):
                batch = available[cursor : cursor + _batch_size(deadline)]
                completed = list(executor.map(download, batch))
                results[cursor : cursor + len(batch)] = completed
                cursor += len(batch)
                _write(state_path, index)
                print(
                    f"Downloaded batch: processed {cursor}/{len(available)} artifacts",
                    flush=True,
                )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        index["download_error"] = _error(exc)
    index["status"] = (
        "downloaded" if all(r["status"] == "downloaded" for r in results) else "partial"
    )
    _write(state_path, index)
    return 0 if index["status"] == "downloaded" else 1


def _read_state(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Archive state must be an object")
    return cast(dict[str, object], value)


def _upload_phase(
    repository: str, bucket: str, archive_id: str, output_dir: Path, workers: int
) -> int:
    snapshot_path = output_dir / "archive-snapshot.json"
    snapshot = _read_state(snapshot_path)
    index = _read_state(output_dir / "download-state.json")
    prefix = f"reports/github-artifacts/multi-ablation/{repository}/"
    for state in (snapshot, index):
        for key, expected in (
            ("repository", repository),
            ("bucket", bucket),
            ("archive_id", archive_id),
            ("prefix", prefix),
        ):
            if state.get(key) != expected:
                raise ValueError(f"Archive phase identity mismatch: {key}")
    available = snapshot.get("available")
    raw_results = index.get("results")
    if (
        not isinstance(available, list)
        or not isinstance(raw_results, list)
        or len(cast(list[object], available)) != len(cast(list[object], raw_results))
    ):
        raise ValueError("Archive phase census mismatch")
    results = cast(list[dict[str, object]], raw_results)
    for artifact, result in zip(
        cast(list[dict[str, object]], available), results, strict=True
    ):
        identifier = artifact.get("id")
        if (
            type(identifier) is not int
            or identifier <= 0
            or result.get("artifact") != artifact
        ):
            raise ValueError("Archive phase artifact mismatch")
        if result.get("key") != f"{prefix}artifacts/{identifier}.zip" or result.get(
            "status"
        ) not in {"downloaded", "failed"}:
            raise ValueError("Archive phase result mismatch")
    _upload(bucket, snapshot_path, f"{prefix}runs/{archive_id}-snapshot.json")

    def copy(result: dict[str, object]) -> dict[str, object]:
        if result["status"] == "failed":
            return result
        artifact = cast(dict[str, object], result["artifact"])
        destination = output_dir / f"{artifact['id']}.zip"
        try:
            if destination.stat().st_size != result.get("archive_bytes"):
                raise ValueError("Downloaded artifact size mismatch")
            _upload(bucket, destination, str(result["key"]))
            result["status"] = "copied"
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result.update(status="failed", error=_error(exc))
        return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(copy, results))
    failures = sum(result["status"] == "failed" for result in results)
    index.update(
        results=results,
        copied_count=len(results) - failures,
        failed_count=failures,
        status="partial" if failures else "complete",
        finished_at=datetime.now(UTC).isoformat(),
    )
    index_path = output_dir / "archive-index.json"
    _write(index_path, index)
    _upload(bucket, index_path, f"{prefix}runs/{archive_id}.json")
    return 1 if failures else 0


def archive_artifacts(
    repository: str,
    bucket: str,
    archive_id: str,
    output_dir: Path,
    workers: int = 4,
    *,
    download_only: bool = False,
    upload_only: bool = False,
) -> int:
    """Download with quota-aware batches, then upload under fresh AWS credentials."""
    _validate(repository, bucket, archive_id, workers)
    if download_only and upload_only:
        raise ValueError("Choose only one archive phase")
    if not upload_only:
        result = _download_phase(repository, bucket, archive_id, output_dir, workers)
        if download_only:
            return result
    return _upload_phase(repository, bucket, archive_id, output_dir, workers)


def main() -> int:
    """Archive existing artifact ZIPs without publishing benchmark claims."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="Source GitHub OWNER/REPO")
    parser.add_argument("--bucket", required=True, help="Protected results S3 bucket")
    parser.add_argument(
        "--archive-id", required=True, help="Unique workflow RUNID-ATTEMPT"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Local ZIPs and archive-index.json",
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Concurrent copies (1-8; default 4)"
    )
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument(
        "--download-only",
        action="store_true",
        help="Save ZIPs and census locally; wait for GitHub quota resets",
    )
    phase.add_argument(
        "--upload-only",
        action="store_true",
        help="Upload local state without GitHub calls; requires fresh AWS credentials",
    )
    args = parser.parse_args()
    return archive_artifacts(
        args.repository,
        args.bucket,
        args.archive_id,
        args.output_dir,
        args.workers,
        download_only=args.download_only,
        upload_only=args.upload_only,
    )


if __name__ == "__main__":
    raise SystemExit(main())

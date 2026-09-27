"""Preserve surviving GitHub artifact ZIPs through the protected S3 workflow."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

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


def archive_artifacts(
    repository: str,
    bucket: str,
    archive_id: str,
    output_dir: Path,
    workers: int = 4,
) -> int:
    """Copy the initial census; retain a partial index and fail if any copy fails."""
    _validate(repository, bucket, archive_id, workers)
    started_at = datetime.now(UTC).isoformat()
    artifacts = _snapshot(repository)
    available = [artifact for artifact in artifacts if not artifact["expired"]]
    expired = [artifact for artifact in artifacts if artifact["expired"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"reports/github-artifacts/multi-ablation/{repository}/"
    index_path = output_dir / "archive-index.json"
    index: dict[str, object] = {
        "repository": repository,
        "archive_id": archive_id,
        "started_at": started_at,
        "bucket": bucket,
        "prefix": prefix,
        "scope": "Artifacts listed at start; artifacts created later are not included.",
        "listed_count": len(artifacts),
        "available_count": len(available),
        "skipped_expired_count": len(expired),
        "skipped_expired": expired,
        "status": "in_progress",
        "results": [],
        "available": available,
    }
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    _upload(bucket, index_path, f"{prefix}runs/{archive_id}-snapshot.json")

    def copy(artifact: dict[str, object]) -> dict[str, object]:
        artifact_id = artifact["id"]
        key = f"{prefix}artifacts/{artifact_id}.zip"
        result: dict[str, object] = {"artifact": artifact, "key": key}
        destination = output_dir / f"{artifact_id}.zip"
        try:
            # Store the opaque archive only: no extraction or execution of its contents.
            with destination.open("wb") as stream:
                subprocess.run(
                    [
                        "gh",
                        "api",
                        f"repos/{repository}/actions/artifacts/{artifact_id}/zip",
                    ],
                    check=True,
                    stdout=stream,
                    stderr=subprocess.PIPE,
                    timeout=_TIMEOUT,
                )
            if destination.stat().st_size == 0:
                raise ValueError("GitHub returned an empty artifact archive")
            _upload(bucket, destination, key)
            result["status"] = "copied"
            result["archive_bytes"] = destination.stat().st_size
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result["status"] = "failed"
            result["error"] = _error(exc)
        return result

    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(copy, available):
            results.append(result)
            print(
                f"{len(results)}/{len(available)}: {result['key']} {result['status']}",
                flush=True,
            )
    failures = sum(result["status"] == "failed" for result in results)
    index.update(
        {
            "results": results,
            "copied_count": len(results) - failures,
            "failed_count": failures,
            "status": "partial" if failures else "complete",
            "finished_at": datetime.now(UTC).isoformat(),
        }
    )
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    _upload(bucket, index_path, f"{prefix}runs/{archive_id}.json")
    return 1 if failures else 0


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
    args = parser.parse_args()
    return archive_artifacts(
        args.repository, args.bucket, args.archive_id, args.output_dir, args.workers
    )


if __name__ == "__main__":
    raise SystemExit(main())

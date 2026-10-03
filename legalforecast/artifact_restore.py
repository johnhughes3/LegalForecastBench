"""Read exact GitHub artifact ZIPs, falling back to protected S3 archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import cast

from legalforecast.artifact_archive import (
    extract_artifact,
    json_command,
    metadata_object,
    pointer_key,
)

_json_command = json_command
_object = metadata_object


def _get_s3(bucket: str, key: str) -> bytes:
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "object"
        subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                key,
                str(target),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        return target.read_bytes()


def archived_artifacts(
    repository: str,
    run_id: int,
    bucket: str,
    *,
    name: str | None = None,
    artifact_id: int | None = None,
) -> list[dict[str, object]]:
    """List validated pointers for one run; never infer identity from ZIP contents."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or any(
        segment in {".", ".."} for segment in repository.split("/")
    ):
        raise ValueError("repository must be OWNER/REPO")
    if type(run_id) is not int or run_id <= 0 or not bucket:
        raise ValueError("positive source run and archive bucket are required")
    prefix = pointer_key(repository, run_id, "", 1).split("by-run/", 1)[0]
    prefix += f"by-run/{run_id}/"
    if name is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", name):
            raise ValueError("artifact name must be a safe archive key segment")
        prefix += f"{name}/"
    listing = _object(
        _json_command(
            [
                "aws",
                "s3api",
                "list-objects-v2",
                "--bucket",
                bucket,
                "--prefix",
                prefix,
                "--output",
                "json",
            ]
        )
    )
    contents: object = listing.get("Contents") or []
    if not isinstance(contents, list):
        raise ValueError("archive listing contents must be an array")
    pointers: list[dict[str, object]] = []
    for entry in cast(list[object], contents):
        key = _object(entry).get("Key")
        if not isinstance(key, str):
            raise ValueError("archive pointer key is invalid")
        if artifact_id is not None and not key.endswith(f"/{artifact_id}.json"):
            continue
        pointer = _object(json.loads(_get_s3(bucket, key)))
        pointer_id, pointer_name, digest = (
            pointer.get("artifact_id"),
            pointer.get("name"),
            pointer.get("digest"),
        )
        if (
            pointer.get("repository") != repository
            or type(pointer.get("source_run_id")) is not int
            or pointer.get("source_run_id") != run_id
            or type(pointer_id) is not int
            or pointer_id <= 0
            or not isinstance(pointer_name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", pointer_name)
            or key != pointer_key(repository, run_id, pointer_name, pointer_id)
            or pointer.get("key")
            != f"{prefix.split('by-run/', 1)[0]}artifacts/{pointer_id}.zip"
            or not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        ):
            raise ValueError("archive pointer does not match source run identity")
        pointers.append(pointer)
    return pointers


def restore_artifact(
    repository: str,
    run_id: int,
    name: str | None,
    *,
    artifact_id: int | None = None,
    bucket: str = "",
) -> bytes:
    """Download an exact run/name/id, verifying SHA-256 for an archived ZIP.

    GitHub authorization/network failures remain visible and do not turn into an
    archive lookup. Only an absent/expired listing or HTTP 404/410 ZIP triggers
    fallback, allowing an artifact to expire between listing and downloading.
    """
    if name is None and artifact_id is None:
        raise ValueError("artifact name or exact ID is required")
    listing = _json_command(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
        ]
    )
    if not isinstance(listing, list):
        raise ValueError("GitHub artifact pages must be an array")
    matches: list[dict[str, object]] = []
    for page in cast(list[object], listing):
        values = _object(page).get("artifacts")
        if not isinstance(values, list):
            raise ValueError("GitHub artifact listing is invalid")
        for raw in cast(list[object], values):
            item = _object(raw)
            if (name is None or item.get("name") == name) and (
                artifact_id is None or item.get("id") == artifact_id
            ):
                matches.append(item)
    if len(matches) > 1:
        raise ValueError("artifact run/name/id is ambiguous")
    if matches and matches[0].get("expired") is not True:
        github_id = matches[0].get("id")
        if type(github_id) is not int or github_id <= 0:
            raise ValueError("GitHub artifact ID is invalid")
        result = subprocess.run(
            [
                "gh",
                "api",
                "--allow-escape-sequences",
                f"repos/{repository}/actions/artifacts/{github_id}/zip",
            ],
            capture_output=True,
        )
        if result.returncode == 0:
            payload = result.stdout
            digest = matches[0].get("digest")
            if isinstance(digest, str) and digest.startswith("sha256:"):
                _verify_digest(payload, digest)
            return payload
        import sys

        sys.stderr.buffer.write(result.stderr)
        if b"HTTP 404" not in result.stderr and b"HTTP 410" not in result.stderr:
            raise subprocess.CalledProcessError(result.returncode, result.args)
    if not bucket:
        raise ValueError(
            "GitHub artifact unavailable; protected archive bucket is required"
        )
    pointers = [
        item
        for item in archived_artifacts(
            repository, run_id, bucket, name=name, artifact_id=artifact_id
        )
        if (name is None or item["name"] == name)
        and (artifact_id is None or item["artifact_id"] == artifact_id)
    ]
    if not pointers and name is not None and artifact_id is None:
        # Owner-retained packages have no original GitHub artifact ID. Keep
        # their provenance separate, and never use them for an exact-ID lookup.
        from legalforecast.retained_package import (
            retained_pointer_key,
            validate_package,
        )

        match = re.fullmatch(
            r"official-forecast-results-([1-9][0-9]*)-([1-9][0-9]*)", name
        )
        if match is not None and int(match[1]) == run_id:
            pointer = _object(
                json.loads(
                    _get_s3(bucket, retained_pointer_key(repository, run_id, name))
                )
            )
            digest = pointer.get("digest")
            if (
                pointer.get("source_type") != "retained_draft_release_asset"
                or pointer.get("repository") != repository
                or pointer.get("source_run_id") != run_id
                or pointer.get("source_attempt") != int(match[2])
                or pointer.get("name") != name
                or type(pointer.get("release_asset_id")) is not int
                or cast(int, pointer["release_asset_id"]) <= 0
                or not isinstance(digest, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                or pointer.get("key")
                != (
                    f"reports/github-artifacts/multi-ablation/{repository}/"
                    f"retained-packages/{digest[7:]}.zip"
                )
            ):
                raise ValueError(
                    "retained pointer differs from original package identity"
                )
            payload = _get_s3(bucket, cast(str, pointer["key"]))
            _verify_digest(payload, digest)
            validate_package(payload, run_id, int(match[2]))
            return payload
    if len(pointers) != 1:
        raise ValueError(
            f"expected one archive pointer for {name}; found {len(pointers)}"
        )
    pointer = pointers[0]
    payload = _get_s3(bucket, cast(str, pointer["key"]))
    _verify_digest(payload, cast(str, pointer["digest"]))
    return payload


def _verify_digest(payload: bytes, digest: str) -> None:
    if f"sha256:{hashlib.sha256(payload).hexdigest()}" != digest:
        raise ValueError("artifact ZIP digest mismatch")


def materialize_recovery_cache(
    repository: str, run_id: int, bucket: str, destination: Path
) -> None:
    """Preserve archived identity/state bytes before assuming the authority role."""
    destination.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    for pointer in archived_artifacts(repository, run_id, bucket):
        name = cast(str, pointer["name"])
        if not name.startswith(
            (
                "official-forecast-results-",
                "locked-forecast-inputs-",
                "locked-run-state-",
                "restored-forecast-state-",
            )
        ):
            continue
        payload = _get_s3(bucket, cast(str, pointer["key"]))
        _verify_digest(payload, cast(str, pointer["digest"]))
        artifact_id = pointer["artifact_id"]
        (destination / f"{artifact_id}.zip").write_bytes(payload)
        records.append(
            {
                "id": artifact_id,
                "name": name,
                "expired": False,
                "archive_available": True,
                "digest": pointer["digest"],
                "size_in_bytes": len(payload),
            }
        )
    (destination / "index.json").write_text(
        json.dumps(
            {
                "repository": repository,
                "run_id": run_id,
                "artifacts": records,
            }
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--name")
    parser.add_argument("--artifact-id", type=int)
    parser.add_argument("--bucket", default="")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--recovery-cache",
        action="store_true",
        help="Materialize archived run identity/state ZIPs for protected recovery",
    )
    args = parser.parse_args()
    if args.recovery_cache:
        materialize_recovery_cache(
            args.repository, args.run_id, args.bucket, args.destination
        )
        return
    extract_artifact(
        restore_artifact(
            args.repository,
            args.run_id,
            args.name,
            artifact_id=args.artifact_id,
            bucket=args.bucket,
        ),
        args.destination,
    )


if __name__ == "__main__":
    main()

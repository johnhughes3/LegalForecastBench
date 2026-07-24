"""Publish a verified official shard fan-in through the canonical write path."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

from legalforecast.publication import cycle_closure
from legalforecast.publication.shard_fan_in import (
    FanInConfig,
    FanInError,
    FanInReport,
    build_parser,
    config_from_args,
    current_receipt_inventory_sha256,
    current_union_inventory_sha256,
    verify_fan_in,
)

_PUBLICATION_CLAIM = ".publication-claim.json"
_PUBLICATION_COMPLETE = ".publication-complete.json"
_PUBLICATION_CLAIM_SCHEMA = "legalforecast.canonical_publication_claim.v1"
_PUBLICATION_COMPLETE_SCHEMA = "legalforecast.canonical_publication_complete.v1"


def publish_fan_in(
    config: FanInConfig,
    *,
    publish_root: str,
    publication_cycle_id: str,
    drain_timeout_seconds: float = 1200.0,
    drain_poll_interval_seconds: float = 2.0,
) -> FanInReport:
    """Verify, race-check, and publish one official aggregate public directory."""

    if config.verify_only:
        raise FanInError("publication cannot use a verify-only fan-in config")
    _require_publication_source_identity(config)
    _require_committed_accepted_map(config.accepted_attempt_map_path)
    report = verify_fan_in(config)
    if report.cycle_id != publication_cycle_id:
        raise FanInError("publication cycle ID does not match the verified freeze")
    try:
        cycle_closure.seal_wait(
            config.receipt_root,
            cycle_id=publication_cycle_id,
            timeout_seconds=drain_timeout_seconds,
            poll_interval_seconds=drain_poll_interval_seconds,
        )
    except (cycle_closure.CycleClosureError, ValueError) as exc:
        raise FanInError(f"could not seal and drain publication cycle: {exc}") from exc
    source = report.aggregate_output_dir / "public"
    if not source.is_dir():
        raise FanInError(f"verified aggregate public directory is missing: {source}")
    with _protected_publication_snapshot(source) as snapshot:

        def stable() -> None:
            _require_stable_inventories(config, report)

        stable()
        _require_canonical_publish_root(publish_root, cycle_id=report.cycle_id)
        if publish_root.startswith("s3://"):
            _publish_s3_snapshot(
                snapshot,
                publish_root=publish_root,
                cycle_id=report.cycle_id,
                before_commit=stable,
            )
        else:
            _publish_local_snapshot(
                snapshot,
                destination=Path(publish_root),
                before_commit=stable,
            )
    return report


def _require_stable_inventories(config: FanInConfig, report: FanInReport) -> None:
    current_inventory = current_receipt_inventory_sha256(
        config.receipt_root, report.cycle_id
    )
    if current_inventory != report.receipt_inventory_sha256:
        raise FanInError(
            "receipt inventory changed after verification; rerun fan-in selection"
        )
    current_union_inventory = current_union_inventory_sha256(
        config.receipt_root, report.cycle_id
    )
    if current_union_inventory != report.union_inventory_sha256:
        raise FanInError(
            "union object versions changed after verification; rerun fan-in"
        )


@contextmanager
def _protected_publication_snapshot(source: Path) -> Generator[Path]:
    """Copy verified public bytes into a private read-only publication snapshot."""

    with tempfile.TemporaryDirectory(
        prefix="lfb-fan-in-publish-", ignore_cleanup_errors=True
    ) as directory:
        snapshot = Path(directory) / "public"
        shutil.copytree(source, snapshot)
        _set_snapshot_writable(snapshot, writable=False)
        try:
            yield snapshot
        finally:
            try:
                _set_snapshot_writable(snapshot, writable=True)
            except OSError:
                # Publication may already be atomically committed. Temporary
                # snapshot cleanup must not turn that into an ambiguous failure.
                pass


def _set_snapshot_writable(snapshot: Path, *, writable: bool) -> None:
    directory_mode = 0o700 if writable else 0o500
    file_mode = 0o600 if writable else 0o400
    snapshot.chmod(directory_mode)
    paths = tuple(snapshot.rglob("*"))
    for path in paths:
        if path.is_dir():
            path.chmod(directory_mode)
    for path in paths:
        if path.is_file():
            path.chmod(file_mode)


def _publish_local_snapshot(
    snapshot: Path,
    *,
    destination: Path,
    before_commit: Callable[[], None],
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FanInError(
            f"canonical publication destination already exists: {destination}"
        )
    staging_root = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}-publication-",
            dir=destination.parent,
        )
    )
    staging = staging_root / "payload"
    lock = destination.with_name(f".{destination.name}.publication.lock")
    lock_fd: int | None = None
    committed = False
    try:
        shutil.copytree(snapshot, staging)
        _set_snapshot_writable(staging, writable=True)
        try:
            lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise FanInError(
                f"canonical publication is already in progress: {destination}"
            ) from exc
        if destination.exists():
            raise FanInError(
                f"canonical publication destination already exists: {destination}"
            )
        _set_snapshot_writable(staging, writable=False)
        # Linux requires the directory entry itself to remain writable for the
        # atomic rename; all payload descendants are already read-only.
        staging.chmod(0o700)
        before_commit()
        staging.rename(destination)
        committed = True
        try:
            destination.chmod(0o500)
        except OSError:
            # The atomic rename is the commit boundary. Permission hardening is
            # best-effort after that point and must not turn success into an
            # ambiguous reported failure.
            pass
    except FanInError:
        raise
    except OSError as exc:
        raise FanInError(f"local publication failed: {exc}") from exc
    finally:
        try:
            if lock_fd is not None:
                os.close(lock_fd)
                lock.unlink(missing_ok=True)
        except OSError as exc:
            if not committed:
                raise FanInError(f"local publication cleanup failed: {exc}") from exc
        shutil.rmtree(staging_root, ignore_errors=True)


def _publish_s3_snapshot(
    snapshot: Path,
    *,
    publish_root: str,
    cycle_id: str,
    before_commit: Callable[[], None],
) -> None:
    manifest = _snapshot_manifest(snapshot)
    claim = {
        "schema_version": _PUBLICATION_CLAIM_SCHEMA,
        "cycle_id": cycle_id,
        "snapshot_sha256": _record_sha256({"files": manifest}),
        "files": manifest,
    }
    claim_payload = _json_bytes(claim)
    existing = set(_list_s3_publication_keys(publish_root))
    if existing and _PUBLICATION_CLAIM not in existing:
        raise FanInError("canonical publication prefix is not empty")
    _put_s3_bytes_once(
        publish_root,
        relative_key=_PUBLICATION_CLAIM,
        payload=claim_payload,
        content_type="application/json",
    )
    for item in manifest:
        relative_key = cast(str, item["path"])
        content_type = (
            mimetypes.guess_type(relative_key)[0] or "application/octet-stream"
        )
        _put_s3_file_once(
            publish_root,
            relative_key=relative_key,
            source=snapshot / relative_key,
            content_type=content_type,
        )
    expected = {_PUBLICATION_CLAIM, *(cast(str, item["path"]) for item in manifest)}
    observed = set(_list_s3_publication_keys(publish_root))
    if observed not in (expected, {*expected, _PUBLICATION_COMPLETE}):
        raise FanInError("canonical publication prefix contains conflicting objects")
    before_commit()
    complete_payload = _json_bytes(
        {
            "schema_version": _PUBLICATION_COMPLETE_SCHEMA,
            "cycle_id": cycle_id,
            "snapshot_sha256": claim["snapshot_sha256"],
            "claim_sha256": hashlib.sha256(claim_payload).hexdigest(),
        }
    )
    _put_s3_bytes_once(
        publish_root,
        relative_key=_PUBLICATION_COMPLETE,
        payload=complete_payload,
        content_type="application/json",
    )


def _snapshot_manifest(snapshot: Path) -> list[dict[str, object]]:
    manifest: list[dict[str, object]] = []
    for path in sorted(snapshot.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(snapshot).as_posix()
        if relative in {_PUBLICATION_CLAIM, _PUBLICATION_COMPLETE}:
            raise FanInError(f"verified snapshot uses reserved path: {relative}")
        payload = path.read_bytes()
        manifest.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
        )
    if not manifest:
        raise FanInError("verified publication snapshot is empty")
    return manifest


def _put_s3_bytes_once(
    root: str,
    *,
    relative_key: str,
    payload: bytes,
    content_type: str,
) -> None:
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(payload)
        handle.flush()
        _put_s3_file_once(
            root,
            relative_key=relative_key,
            source=Path(handle.name),
            content_type=content_type,
        )


def _put_s3_file_once(
    root: str,
    *,
    relative_key: str,
    source: Path,
    content_type: str,
) -> None:
    bucket, key = _s3_publication_location(root, relative_key=relative_key)
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "put-object",
            "--bucket",
            bucket,
            "--key",
            key,
            "--body",
            str(source),
            "--content-type",
            content_type,
            "--if-none-match",
            "*",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    message = result.stderr.strip()
    if "PreconditionFailed" not in message and "412" not in message:
        raise FanInError(f"conditional S3 publication failed: {message}")
    existing = _read_s3_publication_bytes(root, relative_key=relative_key)
    if (
        hashlib.sha256(existing).hexdigest()
        != hashlib.sha256(source.read_bytes()).hexdigest()
    ):
        raise FanInError(f"canonical publication object conflicts: {relative_key}")


def _read_s3_publication_bytes(root: str, *, relative_key: str) -> bytes:
    bucket, key = _s3_publication_location(root, relative_key=relative_key)
    with tempfile.NamedTemporaryFile() as handle:
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                key,
                handle.name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FanInError(
                "conflicting canonical object could not be verified: "
                f"{result.stderr.strip()}"
            )
        handle.seek(0)
        return handle.read()


def _list_s3_publication_keys(root: str) -> tuple[str, ...]:
    parsed = urlparse(root.rstrip("/") + "/")
    prefix = unquote(parsed.path.lstrip("/"))
    keys: list[str] = []
    token: str | None = None
    while True:
        command = [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            parsed.netloc,
            "--prefix",
            prefix,
            "--output",
            "json",
        ]
        if token is not None:
            command.extend(("--continuation-token", token))
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise FanInError(
                f"canonical publication prefix check failed: {result.stderr.strip()}"
            )
        try:
            payload: object = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise FanInError(
                "canonical publication prefix check returned invalid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise FanInError("canonical publication prefix check returned invalid JSON")
        record = cast(Mapping[str, object], payload)
        contents = record.get("Contents", [])
        if not isinstance(contents, list):
            raise FanInError("canonical publication prefix Contents must be an array")
        for raw in cast(list[object], contents):
            if not isinstance(raw, Mapping):
                raise FanInError("canonical publication prefix contains an invalid key")
            item = cast(Mapping[str, object], raw)
            key_value = item.get("Key")
            if not isinstance(key_value, str):
                raise FanInError("canonical publication prefix contains an invalid key")
            if not key_value.startswith(prefix):
                raise FanInError("canonical publication listing escaped its prefix")
            keys.append(key_value[len(prefix) :])
        truncated = record.get("IsTruncated", False)
        if truncated is False:
            break
        if truncated is not True:
            raise FanInError("canonical publication truncation flag must be Boolean")
        next_token = record.get("NextContinuationToken")
        if not isinstance(next_token, str) or not next_token:
            raise FanInError("canonical publication listing omitted continuation token")
        token = next_token
    return tuple(sorted(keys))


def _s3_publication_location(root: str, *, relative_key: str) -> tuple[str, str]:
    parsed = urlparse(root.rstrip("/") + "/")
    prefix = unquote(parsed.path.lstrip("/"))
    return parsed.netloc, prefix + relative_key


def _json_bytes(record: Mapping[str, object]) -> bytes:
    return (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _record_sha256(record: Mapping[str, object]) -> str:
    return hashlib.sha256(_json_bytes(record)).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Run official verification followed by the isolated publication step."""

    parser = build_parser()
    parser.description = "Verify and publish an official immutable shard fan-in."
    parser.add_argument("--publish-root", required=True)
    parser.add_argument("--publication-cycle-id", required=True)
    parser.add_argument("--cycle-drain-timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--cycle-drain-poll-interval-seconds", type=float, default=2.0)
    args = parser.parse_args(argv)
    if cast(bool, args.verify_only):
        raise FanInError("use shard_fan_in directly for --verify-only")
    config = config_from_args(args, verify_only=False)
    report = publish_fan_in(
        config,
        publish_root=cast(str, args.publish_root),
        publication_cycle_id=cast(str, args.publication_cycle_id),
        drain_timeout_seconds=cast(float, args.cycle_drain_timeout_seconds),
        drain_poll_interval_seconds=cast(float, args.cycle_drain_poll_interval_seconds),
    )
    print(json.dumps(report.to_record(), sort_keys=True))
    return 0


def _require_committed_accepted_map(path: Path | None) -> None:
    if path is None:
        return
    repository = Path.cwd().resolve()
    resolved = path.resolve()
    manifests = (repository / "manifests").resolve()
    if manifests not in resolved.parents:
        raise FanInError(
            "publishing accepted-attempt map must be under trusted manifests/"
        )
    relative = resolved.relative_to(repository)
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(relative)],
        check=False,
        capture_output=True,
        text=True,
    )
    unchanged = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", str(relative)],
        check=False,
    )
    if tracked.returncode != 0 or unchanged.returncode != 0:
        raise FanInError(
            "publishing accepted-attempt map must match a file committed in HEAD"
        )


def _require_publication_source_identity(config: FanInConfig) -> None:
    if (
        config.source_dispatch_run_id is None
        or config.source_dispatch_run_attempt is None
        or config.source_release_sha is None
    ):
        raise FanInError(
            "publication requires source dispatch run ID, run attempt, and release SHA"
        )


def _require_canonical_publish_root(root: str, *, cycle_id: str) -> None:
    expected_suffix = f"reports/{cycle_id}/multi-ablation"
    if not root.startswith("s3://"):
        key = Path(root).as_posix().rstrip("/")
        if key != expected_suffix and not key.endswith(f"/{expected_suffix}"):
            raise FanInError(
                "publication root must be the canonical cycle report destination: "
                f"PATH/{expected_suffix}"
            )
        return
    parsed = urlparse(root)
    if not parsed.netloc:
        raise FanInError("publication root must name an S3 bucket")
    key = unquote(parsed.path).strip("/")
    if key != expected_suffix:
        raise FanInError(
            "publication root must be the canonical cycle report prefix: "
            f"s3://BUCKET/{expected_suffix}/"
        )


if __name__ == "__main__":
    raise SystemExit(main())

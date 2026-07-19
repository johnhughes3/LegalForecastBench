"""Publish a verified official shard fan-in through the canonical write path."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

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


def publish_fan_in(config: FanInConfig, *, publish_root: str) -> FanInReport:
    """Verify, race-check, and publish one official aggregate public directory."""

    if config.verify_only:
        raise FanInError("publication cannot use a verify-only fan-in config")
    _require_committed_accepted_map(config.accepted_attempt_map_path)
    report = verify_fan_in(config)
    source = report.aggregate_output_dir / "public"
    if not source.is_dir():
        raise FanInError(f"verified aggregate public directory is missing: {source}")
    with _protected_publication_snapshot(source) as snapshot:
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
        _require_canonical_publish_root(publish_root, cycle_id=report.cycle_id)
        if publish_root.startswith("s3://"):
            _require_empty_s3_prefix(publish_root)
            result = subprocess.run(
                [
                    "aws",
                    "s3",
                    "sync",
                    str(snapshot),
                    publish_root,
                    "--only-show-errors",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise FanInError(
                    f"aggregate publication failed: {result.stderr.strip()}"
                )
        else:
            destination = Path(publish_root)
            if destination.exists():
                raise FanInError(
                    f"canonical publication destination already exists: {destination}"
                )
            shutil.copytree(snapshot, destination)
    return report


@contextmanager
def _protected_publication_snapshot(source: Path) -> Generator[Path]:
    """Copy verified public bytes into a private read-only publication snapshot."""

    with tempfile.TemporaryDirectory(prefix="lfb-fan-in-publish-") as directory:
        snapshot = Path(directory) / "public"
        shutil.copytree(source, snapshot)
        _set_snapshot_writable(snapshot, writable=False)
        try:
            yield snapshot
        finally:
            _set_snapshot_writable(snapshot, writable=True)


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


def main(argv: Sequence[str] | None = None) -> int:
    """Run official verification followed by the isolated publication step."""

    parser = build_parser()
    parser.description = "Verify and publish an official immutable shard fan-in."
    parser.add_argument("--publish-root", required=True)
    args = parser.parse_args(argv)
    if cast(bool, args.verify_only):
        raise FanInError("use shard_fan_in directly for --verify-only")
    config = config_from_args(args, verify_only=False)
    report = publish_fan_in(config, publish_root=cast(str, args.publish_root))
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


def _require_canonical_publish_root(root: str, *, cycle_id: str) -> None:
    if not root.startswith("s3://"):
        return
    parsed = urlparse(root)
    if not parsed.netloc:
        raise FanInError("publication root must name an S3 bucket")
    key = unquote(parsed.path).strip("/")
    expected_suffix = f"reports/{cycle_id}/multi-ablation"
    if key != expected_suffix:
        raise FanInError(
            "publication root must be the canonical cycle report prefix: "
            f"s3://BUCKET/{expected_suffix}/"
        )


def _require_empty_s3_prefix(root: str) -> None:
    parsed = urlparse(root)
    prefix = unquote(parsed.path).strip("/") + "/"
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "list-objects-v2",
            "--bucket",
            parsed.netloc,
            "--prefix",
            prefix,
            "--max-keys",
            "1",
            "--output",
            "json",
        ],
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
    key_count = cast(Mapping[str, object], payload).get("KeyCount")
    if isinstance(key_count, bool) or not isinstance(key_count, int) or key_count != 0:
        raise FanInError("canonical publication prefix is not empty")


if __name__ == "__main__":
    raise SystemExit(main())

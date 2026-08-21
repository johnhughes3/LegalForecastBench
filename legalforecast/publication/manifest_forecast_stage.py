"""Stage a manifest-mode forecast bundle into immutable S3 prefixes.

The manifest-mode builder intentionally writes only local, provider-free
inputs.  This module is the narrow hand-off from that local output to the
official OIDC workflow.  It authenticates every input before staging, creates
one digest-keyed prefix, and uses S3's create-only conditional write for every
object.  Existing objects are accepted only when their bytes still match the
same commitment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    FrozenArtifact,
    verify_freeze_bundle,
    write_hash_bundle,
)

MANIFEST_FORECAST_STAGE_SCHEMA_VERSION = "legalforecast-manifest-forecast-stage-v1"
MANIFEST_FORECAST_PREFIX = "cycle-1/manifest-runs"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_S3_KEY = re.compile(r"^[A-Za-z0-9._/-]+\Z")


class ManifestForecastStageError(ValueError):
    """Raised when a manifest forecast cannot be staged safely."""


@dataclass(frozen=True, slots=True)
class ManifestForecastStageConfig:
    """Inputs for one immutable manifest forecast staging operation."""

    output_dir: Path
    freeze_bundle: Path
    artifact_root: Path
    manifest_digest: str
    results_bucket: str
    packet_bucket: str
    dry_run: bool = False

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.manifest_digest) is None:
            raise ManifestForecastStageError(
                "manifest_digest must be a lowercase SHA-256 hex digest"
            )
        if not self.output_dir.is_dir():
            raise ManifestForecastStageError(
                f"output_dir is not a directory: {self.output_dir}"
            )
        if not self.freeze_bundle.is_file():
            raise ManifestForecastStageError(
                f"freeze bundle is missing: {self.freeze_bundle}"
            )
        if not self.artifact_root.is_dir():
            raise ManifestForecastStageError(
                f"artifact_root is not a directory: {self.artifact_root}"
            )
        for name, value in (
            ("results_bucket", self.results_bucket),
            ("packet_bucket", self.packet_bucket),
        ):
            if not value or "/" in value or value.startswith("."):
                raise ManifestForecastStageError(f"{name} must be an S3 bucket name")


@dataclass(frozen=True, slots=True)
class ManifestForecastStageResult:
    """Committed locations and hashes emitted by a staging operation."""

    prefix: str
    freeze_bundle_uri: str
    run_input_manifest_uri: str
    packet_count: int
    object_count: int
    stage_record: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class _LocalObject:
    bucket: str
    key: str
    path: Path
    sha256: str
    size_bytes: int
    content_type: str


def stage_manifest_forecast(
    config: ManifestForecastStageConfig,
) -> ManifestForecastStageResult:
    """Validate and stage manifest-mode output without contacting a provider."""

    output_dir = config.output_dir.resolve()
    artifact_root = config.artifact_root.resolve()
    try:
        bundle = verify_freeze_bundle(
            config.freeze_bundle,
            root_path=artifact_root,
        )
    except (FreezeProtocolError, OSError, ValueError) as exc:
        raise ManifestForecastStageError(f"freeze bundle is not valid: {exc}") from exc

    run_record = _load_object(
        output_dir / "manifest-mode-run-record.json", "run record"
    )
    if run_record.get("manifest_digest") != config.manifest_digest:
        raise ManifestForecastStageError(
            "run record manifest_digest does not match --manifest-digest"
        )
    run_inputs_path = output_dir / "run-inputs.json"
    run_inputs = _load_object(run_inputs_path, "run-inputs manifest")
    if run_inputs.get("cycle_id") != bundle.cycle_id:
        raise ManifestForecastStageError(
            "run-inputs cycle_id does not match the freeze bundle cycle_id"
        )
    packet_objects = _packet_objects(
        output_dir, run_inputs, bucket=config.packet_bucket
    )
    freeze_objects, staged_bundle_path = _freeze_objects(
        bundle,
        artifact_root=artifact_root,
        results_bucket=config.results_bucket,
        prefix=_prefix(config.manifest_digest),
    )

    try:
        return _build_stage_result(
            config=config,
            output_dir=output_dir,
            run_inputs_path=run_inputs_path,
            packet_objects=packet_objects,
            freeze_objects=freeze_objects,
            staged_bundle_path=staged_bundle_path,
        )
    finally:
        staged_bundle_path.unlink(missing_ok=True)


def _build_stage_result(
    *,
    config: ManifestForecastStageConfig,
    output_dir: Path,
    run_inputs_path: Path,
    packet_objects: Sequence[_LocalObject],
    freeze_objects: Sequence[_LocalObject],
    staged_bundle_path: Path,
) -> ManifestForecastStageResult:
    prefix = _prefix(config.manifest_digest)
    result_objects = [
        *freeze_objects,
        _local_object(
            config.results_bucket,
            f"{prefix}/freeze.json",
            staged_bundle_path,
            "application/json",
        ),
        _local_object(
            config.results_bucket,
            f"{prefix}/run-inputs.json",
            run_inputs_path,
            "application/json",
        ),
        _local_object(
            config.results_bucket,
            f"{prefix}/manifest-mode-run-record.json",
            output_dir / "manifest-mode-run-record.json",
            "application/json",
        ),
    ]
    # Keep a copy inside the digest prefix for audit/reconstruction while the
    # official runner continues to read the packet bucket's established
    # model-packets/<cycle>/... keys.
    packet_objects_for_results = [
        _local_object(
            config.results_bucket,
            f"{prefix}/model-packets/{obj.key[len('model-packets/') :]}",
            obj.path,
            obj.content_type,
        )
        for obj in packet_objects
    ]
    all_objects = [*result_objects, *packet_objects_for_results, *packet_objects]
    _verify_source_snapshots(all_objects)

    stage_record = {
        "schema_version": MANIFEST_FORECAST_STAGE_SCHEMA_VERSION,
        "manifest_digest": config.manifest_digest,
        "prefix": prefix,
        "freeze_bundle": f"s3://{config.results_bucket}/{prefix}/freeze.json",
        "run_input_manifest": f"s3://{config.results_bucket}/{prefix}/run-inputs.json",
        "packet_count": len(packet_objects),
        "objects": [
            {
                "bucket": obj.bucket,
                "key": obj.key,
                "sha256": obj.sha256,
                "size_bytes": obj.size_bytes,
            }
            for obj in all_objects
        ],
    }
    if not config.dry_run:
        for obj in all_objects:
            _put_immutable(obj)
        _verify_remote_objects(all_objects)

    return ManifestForecastStageResult(
        prefix=prefix,
        freeze_bundle_uri=f"s3://{config.results_bucket}/{prefix}/freeze.json",
        run_input_manifest_uri=(
            f"s3://{config.results_bucket}/{prefix}/run-inputs.json"
        ),
        packet_count=len(packet_objects),
        object_count=len(all_objects),
        stage_record=stage_record,
    )


def add_manifest_forecast_stage_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    """Register CLI arguments for the manifest forecast S3 bridge."""

    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze-bundle", type=Path, required=True)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        required=True,
        help="Common root used to preserve relative frozen-artifact paths.",
    )
    parser.add_argument("--manifest-digest", required=True)
    parser.add_argument("--results-bucket", required=True)
    parser.add_argument("--packet-bucket", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the upload plan without writing to S3.",
    )


def run_manifest_forecast_stage(args: argparse.Namespace) -> int:
    """CLI handler for ``acquisition stage-manifest-forecast``."""

    result = stage_manifest_forecast(
        ManifestForecastStageConfig(
            output_dir=cast(Path, args.output_dir),
            freeze_bundle=cast(Path, args.freeze_bundle),
            artifact_root=cast(Path, args.artifact_root),
            manifest_digest=cast(str, args.manifest_digest),
            results_bucket=cast(str, args.results_bucket),
            packet_bucket=cast(str, args.packet_bucket),
            dry_run=bool(args.dry_run),
        )
    )
    print(json.dumps(result.stage_record, indent=2, sort_keys=True))
    return 0


def _prefix(manifest_digest: str) -> str:
    return f"{MANIFEST_FORECAST_PREFIX}/{manifest_digest}"


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestForecastStageError(f"{label} is unreadable: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ManifestForecastStageError(f"{label} must be a JSON object: {path}")
    return dict(cast(Mapping[str, Any], raw))


def _packet_objects(
    output_dir: Path,
    run_inputs: Mapping[str, Any],
    *,
    bucket: str,
) -> list[_LocalObject]:
    packets = run_inputs.get("model_packets")
    if not isinstance(packets, list) or not packets:
        raise ManifestForecastStageError("run-inputs model_packets must be non-empty")
    objects: list[_LocalObject] = []
    seen: set[str] = set()
    packet_rows = cast(list[object], packets)
    for raw in packet_rows:
        if not isinstance(raw, Mapping):
            raise ManifestForecastStageError("run-inputs packet rows must be objects")
        packet = cast(Mapping[str, Any], raw)
        key = packet.get("packet_object_key")
        digest = packet.get("packet_sha256")
        if not isinstance(key, str) or not key.startswith("model-packets/"):
            raise ManifestForecastStageError(
                "packet key must start with model-packets/"
            )
        _validate_s3_key(key)
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ManifestForecastStageError(f"invalid packet_sha256 for {key}")
        if key in seen:
            raise ManifestForecastStageError(f"duplicate packet key: {key}")
        seen.add(key)
        path = (output_dir / key).resolve()
        try:
            path.relative_to(output_dir)
        except ValueError as exc:
            raise ManifestForecastStageError(
                f"packet path is outside output directory: {key}"
            ) from exc
        if not path.is_file():
            raise ManifestForecastStageError(f"packet file is missing: {path}")
        if _sha256_file(path) != digest:
            raise ManifestForecastStageError(
                f"packet bytes differ from run-inputs: {key}"
            )
        objects.append(
            _LocalObject(
                bucket=bucket,
                key=key,
                path=path,
                sha256=digest,
                size_bytes=path.stat().st_size,
                content_type="application/json",
            )
        )
    return objects


def _freeze_objects(
    bundle: FreezeBundle,
    *,
    artifact_root: Path,
    results_bucket: str,
    prefix: str,
) -> tuple[list[_LocalObject], Path]:
    staged_artifacts: list[FrozenArtifact] = []
    objects: list[_LocalObject] = []
    used_keys: set[str] = set()
    for artifact in bundle.artifacts:
        path = artifact.path.resolve()
        try:
            relative = path.relative_to(artifact_root)
        except ValueError as exc:
            raise ManifestForecastStageError(
                f"frozen artifact is outside --artifact-root: {path}"
            ) from exc
        if not relative.parts or ".." in relative.parts:
            raise ManifestForecastStageError(f"unsafe frozen artifact path: {relative}")
        staged_relative = Path("artifacts") / relative
        key = f"{prefix}/{staged_relative.as_posix()}"
        if key in used_keys:
            raise ManifestForecastStageError(f"duplicate staged artifact key: {key}")
        used_keys.add(key)
        staged_artifacts.append(
            FrozenArtifact(
                name=artifact.name,
                path=staged_relative,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
            )
        )
        objects.append(
            _local_object(
                results_bucket,
                key,
                path,
                _content_type(path),
            )
        )
    staged_bundle = FreezeBundle(
        cycle_id=bundle.cycle_id,
        freeze_timestamp=bundle.freeze_timestamp,
        artifacts=tuple(staged_artifacts),
        amends_bundle_sha256=bundle.amends_bundle_sha256,
    )
    with tempfile.TemporaryDirectory(prefix="lfb-manifest-stage-") as directory:
        path = Path(directory) / "freeze.json"
        write_hash_bundle(path, staged_bundle)
        descriptor, name = tempfile.mkstemp(prefix="lfb-staged-freeze-", suffix=".json")
        os.close(descriptor)
        persistent = Path(name)
        persistent.write_bytes(path.read_bytes())
    return objects, persistent


def _local_object(bucket: str, key: str, path: Path, content_type: str) -> _LocalObject:
    _validate_s3_key(key)
    return _LocalObject(
        bucket=bucket,
        key=key,
        path=path,
        sha256=_sha256_file(path),
        size_bytes=path.stat().st_size,
        content_type=content_type,
    )


def _validate_s3_key(key: str) -> None:
    if not _SAFE_S3_KEY.fullmatch(key) or any(
        part in {"", ".", ".."} for part in key.split("/")
    ):
        raise ManifestForecastStageError(f"unsafe S3 key: {key}")


def _verify_source_snapshots(objects: Sequence[_LocalObject]) -> None:
    for obj in objects:
        if (
            _sha256_file(obj.path) != obj.sha256
            or obj.path.stat().st_size != obj.size_bytes
        ):
            raise ManifestForecastStageError(
                f"source changed before staging: {obj.path}"
            )


def _put_immutable(obj: _LocalObject) -> None:
    # Recheck immediately before invoking the external uploader so a local
    # replacement after the initial inventory cannot be uploaded silently.
    _verify_source_snapshots((obj,))
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "put-object",
            "--bucket",
            obj.bucket,
            "--key",
            obj.key,
            "--body",
            str(obj.path),
            "--content-type",
            obj.content_type,
            "--metadata",
            f"sha256={obj.sha256}",
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
        raise ManifestForecastStageError(
            f"immutable S3 write failed for s3://{obj.bucket}/{obj.key}: {message}"
        )
    _verify_remote_object(obj)


def _verify_remote_objects(objects: Sequence[_LocalObject]) -> None:
    for obj in objects:
        _verify_remote_object(obj)


def _verify_remote_object(obj: _LocalObject) -> None:
    result = subprocess.run(
        [
            "aws",
            "s3api",
            "head-object",
            "--bucket",
            obj.bucket,
            "--key",
            obj.key,
            "--output",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ManifestForecastStageError(
            "cannot verify staged object "
            f"s3://{obj.bucket}/{obj.key}: {result.stderr.strip()}"
        )
    try:
        head = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManifestForecastStageError(
            f"S3 head-object returned invalid JSON for {obj.key}"
        ) from exc
    if not isinstance(head, Mapping):
        raise ManifestForecastStageError(
            f"S3 head-object returned a non-object for {obj.key}"
        )
    head_record = cast(Mapping[str, Any], head)
    if head_record.get("ContentLength") != obj.size_bytes:
        raise ManifestForecastStageError(f"staged object size mismatch: {obj.key}")
    metadata = head_record.get("Metadata")
    if not isinstance(metadata, Mapping):
        raise ManifestForecastStageError(
            f"staged object hash metadata mismatch: {obj.key}"
        )
    metadata_record = cast(Mapping[str, Any], metadata)
    if metadata_record.get("sha256") != obj.sha256:
        raise ManifestForecastStageError(
            f"staged object hash metadata mismatch: {obj.key}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise ManifestForecastStageError(f"cannot read staged source: {path}") from exc
    return digest.hexdigest()


def _content_type(path: Path) -> str:
    if path.suffix == ".jsonl":
        return "application/jsonl"
    if path.suffix == ".json":
        return "application/json"
    return "application/octet-stream"

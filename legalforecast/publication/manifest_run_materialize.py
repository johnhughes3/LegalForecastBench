"""Rebuild supplementary ``stage-manifest-forecast`` inputs from staged objects.

Staging reads a manifest-mode output directory and a frozen artifact tree that
exist only in the operator's gitignored ``artifacts/`` working tree.  Those
bytes are the un-run evaluation corpus, so they cannot be committed to this
public repository -- and they cannot be uploaded from a workstation either: the
buckets and their KMS key are governed by resource policies naming only the
OIDC roles, so even break-glass ``AdministratorAccess`` is denied.

Everything a supplementary sibling freeze shares with the official freeze is
already staged and immutable under ``cycle-1/manifest-runs/<manifest_digest>/``,
so this module rebuilds the tree inside the workflow instead of shipping it in.
Only the artifacts the sibling replaces -- its registry, caps, and execution
policy -- come from the checkout.

The rebuild is content-addressed, never path-inferred.  The candidate freeze
already records the exact SHA-256 of every artifact it commits, and the pinned
official freeze records where each of those digests is staged, so an artifact is
located by digest and every downloaded byte is verified against the candidate's
own commitment before it is written.  A digest present in neither the official
prefix nor the caller's explicit overrides fails closed rather than being
guessed at.  ``stage-manifest-forecast`` then re-verifies the whole bundle, so a
wrong reconstruction can only fail loudly; it can never be staged.

**Supplementary only, deliberately.**  There is no official re-verification mode
here, and adding one by pointing this module at the staged official freeze would
be a serious bug rather than a convenience.  A staged freeze's artifact paths
have already been rewritten to ``artifacts/<relative>`` by
``manifest_forecast_stage._freeze_objects``; restaging it applies that segment a
second time, yielding ``artifacts/artifacts/<relative>`` keys that do not exist,
so every create-only ``PutObject`` *succeeds* and creates junk in the immutable
official prefix that no role can delete, aborting only afterwards when
``freeze.json`` collides.  Official re-verification has to be a read-only
head-object check against the pinned freeze's own recorded keys -- a different
operation from staging, tracked separately.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    load_freeze_bundle_bytes,
    sha256_file,
)
from legalforecast.publication.manifest_forecast_stage_lane import (
    SHA256_PATTERN,
    iter_packet_rows,
    validate_s3_key,
)

MANIFEST_RUN_MATERIALIZE_SCHEMA_VERSION = (
    "legalforecast-manifest-run-materialize-plan-v1"
)
RUN_INPUTS_NAME = "run-inputs.json"
RUN_RECORD_NAME = "manifest-mode-run-record.json"
STAGED_FREEZE_NAME = "freeze.json"
# Long enough that a stalled transfer fails loudly instead of consuming the
# job budget, short enough that it cannot mask a hung endpoint. Every fetch
# happens before the first upload, so a fetch timeout strands nothing.
FETCH_TIMEOUT_SECONDS = 300


class ManifestRunMaterializeError(ValueError):
    """Raised when staging inputs cannot be rebuilt from authenticated bytes."""


# bucket, key, destination path.  Injected so the reconstruction logic is
# testable without AWS: the production fetcher is the only part that needs
# credentials, and it is the only part tests replace.
ObjectFetcher = Callable[[str, str, Path], None]


@dataclass(frozen=True, slots=True)
class ManifestRunMaterializeConfig:
    """Inputs for one reconstruction of a supplementary staging tree."""

    freeze_bundle: Path
    official_freeze_bundle_sha256: str
    official_prefix: str
    results_bucket: str
    packet_bucket: str
    artifact_root: Path
    output_dir: Path
    official_freeze_bundle_out: Path
    # Every packet digest the rebuild trusts is read out of run-inputs.json, so
    # that file has to be pinned too; without this it is the one input the
    # caller accepts on the staged prefix's word alone.
    run_inputs_sha256: str
    run_record_sha256: str
    local_artifacts: Mapping[str, Path] = field(
        default_factory=lambda: cast(Mapping[str, Path], {})
    )

    def __post_init__(self) -> None:
        for name, digest in (
            ("official_freeze_bundle_sha256", self.official_freeze_bundle_sha256),
            ("run_inputs_sha256", self.run_inputs_sha256),
            ("run_record_sha256", self.run_record_sha256),
        ):
            if SHA256_PATTERN.fullmatch(digest) is None:
                raise ManifestRunMaterializeError(
                    f"{name} must be a lowercase SHA-256 hex digest"
                )
        if not self.freeze_bundle.is_file():
            raise ManifestRunMaterializeError(
                f"candidate freeze bundle is missing: {self.freeze_bundle}"
            )
        for name, bucket in (
            ("results_bucket", self.results_bucket),
            ("packet_bucket", self.packet_bucket),
        ):
            if not bucket or "/" in bucket or bucket.startswith("."):
                raise ManifestRunMaterializeError(f"{name} must be an S3 bucket name")
        validate_s3_key(
            self.official_prefix.rstrip("/") or "/",
            error_type=ManifestRunMaterializeError,
        )
        for artifact_name, path in self.local_artifacts.items():
            if not path.is_file():
                raise ManifestRunMaterializeError(
                    f"local artifact {artifact_name} is missing: {path}"
                )


def materialize_manifest_run_inputs(
    config: ManifestRunMaterializeConfig,
    *,
    fetch: ObjectFetcher | None = None,
) -> dict[str, Any]:
    """Rebuild the artifact root and manifest-mode output directory."""

    fetcher = fetch if fetch is not None else fetch_s3_object
    prefix = config.official_prefix.rstrip("/")

    candidate = _load_bundle(config.freeze_bundle.read_bytes(), "candidate freeze")
    # Refuse an override that names nothing in the freeze before spending a
    # dozen downloads discovering it: a typo here means the operator believes
    # they replaced an artifact they did not.
    named = {str(artifact.name) for artifact in candidate.artifacts}
    unknown = sorted(set(config.local_artifacts) - named)
    if unknown:
        raise ManifestRunMaterializeError(
            "--local-artifact names no artifact in the candidate freeze: "
            + ", ".join(unknown)
        )

    official = _load_pinned_official_bundle(config, fetcher)
    staged_by_digest = _staged_paths_by_digest(official)

    artifact_records = _materialize_artifacts(
        config,
        candidate=candidate,
        staged_by_digest=staged_by_digest,
        prefix=prefix,
        fetch=fetcher,
    )
    output_records, packet_records = _materialize_output_dir(
        config, prefix=prefix, fetch=fetcher
    )

    return {
        "schema_version": MANIFEST_RUN_MATERIALIZE_SCHEMA_VERSION,
        "official_prefix": prefix,
        "official_freeze_bundle_sha256": config.official_freeze_bundle_sha256,
        "official_freeze_bundle": str(config.official_freeze_bundle_out),
        "candidate_freeze_bundle": str(config.freeze_bundle),
        "candidate_freeze_bundle_sha256": sha256_file(config.freeze_bundle),
        "artifact_root": str(config.artifact_root),
        "output_dir": str(config.output_dir),
        "artifacts": artifact_records,
        "output_objects": output_records,
        "packet_count": len(packet_records),
        "packets": packet_records,
    }


def _load_pinned_official_bundle(
    config: ManifestRunMaterializeConfig, fetch: ObjectFetcher
) -> FreezeBundle:
    """Download the official staged freeze and hold it to its caller-supplied pin.

    The pin is what makes the digest map trustworthy: without it a substituted
    object could name any staged location for any digest, and every artifact
    below would be fetched from wherever that substitution pointed.
    """

    destination = config.official_freeze_bundle_out
    destination.parent.mkdir(parents=True, exist_ok=True)
    key = f"{config.official_prefix.rstrip('/')}/{STAGED_FREEZE_NAME}"
    validate_s3_key(key, error_type=ManifestRunMaterializeError)
    fetch(config.results_bucket, key, destination)
    _require_exact_bytes(destination, sha256=config.official_freeze_bundle_sha256)
    return _load_bundle(destination.read_bytes(), "staged official freeze")


def _load_bundle(payload: bytes, label: str) -> FreezeBundle:
    # root_path=None keeps every artifact path exactly as recorded, which is what
    # the digest map and the rebuilt tree are both keyed on.
    try:
        return load_freeze_bundle_bytes(payload, root_path=None)
    except (FreezeProtocolError, ValueError) as exc:
        raise ManifestRunMaterializeError(f"{label} is not valid: {exc}") from exc


def _staged_paths_by_digest(official: FreezeBundle) -> dict[str, str]:
    """Map each officially staged artifact digest to its key below the prefix.

    Keyed by digest rather than by path on purpose.  The candidate freeze's own
    relative paths are the operator's local layout, which need not match the
    layout the official staging recorded; the digest is the only identity both
    bundles agree on.
    """

    staged: dict[str, str] = {}
    for artifact in official.artifacts:
        relative = _relative_posix(artifact.path, f"staged artifact {artifact.name}")
        # Deterministic when one digest is staged at several keys: identical
        # bytes, so any key serves, but the choice must not vary between runs.
        current = staged.get(artifact.sha256)
        if current is None or relative < current:
            staged[artifact.sha256] = relative
    return staged


def _materialize_artifacts(
    config: ManifestRunMaterializeConfig,
    *,
    candidate: FreezeBundle,
    staged_by_digest: Mapping[str, str],
    prefix: str,
    fetch: ObjectFetcher,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for artifact in candidate.artifacts:
        name = str(artifact.name)
        relative = _relative_posix(artifact.path, f"candidate artifact {name}")
        target = config.artifact_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        override = config.local_artifacts.get(name)
        if override is not None:
            if artifact.sha256 in staged_by_digest:
                # A shared artifact is the comparability claim; letting the
                # checkout supply bytes that are already staged would replace an
                # authenticated source with an unauthenticated one that merely
                # happens to agree today.
                raise ManifestRunMaterializeError(
                    f"local artifact {name} is already staged officially at "
                    f"{staged_by_digest[artifact.sha256]}; shared artifacts must "
                    "come from the pinned official prefix"
                )
            target.write_bytes(override.read_bytes())
            source = f"checkout:{override}"
        else:
            staged_relative = staged_by_digest.get(artifact.sha256)
            if staged_relative is None:
                raise ManifestRunMaterializeError(
                    f"candidate artifact {name} ({artifact.sha256}) is neither "
                    "staged under the pinned official prefix nor supplied by "
                    f"--local-artifact {name}=<path>"
                )
            key = f"{prefix}/{staged_relative}"
            validate_s3_key(key, error_type=ManifestRunMaterializeError)
            fetch(config.results_bucket, key, target)
            source = f"s3://{config.results_bucket}/{key}"
        _require_exact_bytes(target, sha256=artifact.sha256, size=artifact.size_bytes)
        records.append(
            {
                "name": name,
                "path": relative,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "source": source,
            }
        )
    return records


def _materialize_output_dir(
    config: ManifestRunMaterializeConfig,
    *,
    prefix: str,
    fetch: ObjectFetcher,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_records: list[dict[str, Any]] = []
    for name, expected in (
        (RUN_INPUTS_NAME, config.run_inputs_sha256),
        (RUN_RECORD_NAME, config.run_record_sha256),
    ):
        key = f"{prefix}/{name}"
        validate_s3_key(key, error_type=ManifestRunMaterializeError)
        destination = config.output_dir / name
        fetch(config.results_bucket, key, destination)
        _require_exact_bytes(destination, sha256=expected)
        output_records.append(
            {
                "name": name,
                "sha256": expected,
                "source": f"s3://{config.results_bucket}/{key}",
            }
        )

    run_inputs = _load_json_object(config.output_dir / RUN_INPUTS_NAME, "run-inputs")
    packet_records: list[dict[str, Any]] = []
    for key, digest in iter_packet_rows(
        run_inputs, error_type=ManifestRunMaterializeError
    ):
        destination = config.output_dir / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        fetch(config.packet_bucket, key, destination)
        _require_exact_bytes(destination, sha256=digest)
        packet_records.append(
            {
                "key": key,
                "sha256": digest,
                "source": f"s3://{config.packet_bucket}/{key}",
            }
        )
    return output_records, packet_records


def _require_exact_bytes(path: Path, *, sha256: str, size: int | None = None) -> None:
    actual = sha256_file(path)
    if actual != sha256:
        raise ManifestRunMaterializeError(
            f"materialized {path} hashes to {actual}, not the committed {sha256}"
        )
    if size is not None and path.stat().st_size != size:
        raise ManifestRunMaterializeError(
            f"materialized {path} is {path.stat().st_size} bytes, not {size}"
        )


def _relative_posix(path: Path, label: str) -> str:
    if path.is_absolute():
        raise ManifestRunMaterializeError(
            f"{label} must record a relative path: {path}"
        )
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ManifestRunMaterializeError(f"{label} has an unsafe path: {path}")
    relative = path.as_posix()
    validate_s3_key(relative, error_type=ManifestRunMaterializeError)
    return relative


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestRunMaterializeError(f"{label} is unreadable: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ManifestRunMaterializeError(f"{label} must be a JSON object: {path}")
    return dict(cast(Mapping[str, Any], raw))


def fetch_s3_object(bucket: str, key: str, destination: Path) -> None:
    """Download one object by exact key, never by listing."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                key,
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ManifestRunMaterializeError(
            f"timed out downloading s3://{bucket}/{key} after {FETCH_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode != 0:
        raise ManifestRunMaterializeError(
            f"cannot download s3://{bucket}/{key}: {result.stderr.strip()}"
        )


def _parse_local_artifacts(values: Sequence[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name.strip() or not path.strip():
            raise ManifestRunMaterializeError(
                "--local-artifact must be <artifact_name>=<path>"
            )
        key = name.strip()
        if key in overrides:
            # Silently taking the last one would let a copy-paste slip decide
            # which bytes an artifact is staged from.
            raise ManifestRunMaterializeError(
                f"--local-artifact {key} was supplied more than once"
            )
        overrides[key] = Path(path.strip())
    return overrides


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.publication.manifest_run_materialize",
        description=(
            "Rebuild supplementary stage-manifest-forecast inputs from the "
            "immutable objects an earlier official staging already wrote, so "
            "staging runs in GitHub Actions without shipping corpus bytes into "
            "a public repository."
        ),
    )
    parser.add_argument("--freeze-bundle", type=Path, required=True)
    parser.add_argument("--official-freeze-bundle-sha256", required=True)
    parser.add_argument(
        "--run-inputs-sha256",
        required=True,
        help=(
            "Raw-file SHA-256 of the staged run-inputs.json. Every packet digest "
            "trusted below is read out of it, so it is pinned rather than taken "
            "on the prefix's word."
        ),
    )
    parser.add_argument(
        "--run-record-sha256",
        required=True,
        help="Raw-file SHA-256 of the staged manifest-mode-run-record.json.",
    )
    parser.add_argument(
        "--official-prefix",
        required=True,
        help="Staged official manifest-run prefix, without a trailing slash.",
    )
    parser.add_argument("--results-bucket", required=True)
    parser.add_argument("--packet-bucket", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--official-freeze-bundle-out", type=Path, required=True)
    parser.add_argument(
        "--local-artifact",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help=(
            "Checked-out replacement artifact this sibling freeze does not share "
            "with the official one; repeat per artifact. Refused for any "
            "artifact already staged officially, and for a repeated name."
        ),
    )
    parser.add_argument("--plan-out", type=Path, required=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    plan = materialize_manifest_run_inputs(
        ManifestRunMaterializeConfig(
            freeze_bundle=cast(Path, args.freeze_bundle),
            official_freeze_bundle_sha256=cast(str, args.official_freeze_bundle_sha256),
            run_inputs_sha256=cast(str, args.run_inputs_sha256),
            run_record_sha256=cast(str, args.run_record_sha256),
            official_prefix=cast(str, args.official_prefix),
            results_bucket=cast(str, args.results_bucket),
            packet_bucket=cast(str, args.packet_bucket),
            artifact_root=cast(Path, args.artifact_root),
            output_dir=cast(Path, args.output_dir),
            official_freeze_bundle_out=cast(Path, args.official_freeze_bundle_out),
            local_artifacts=_parse_local_artifacts(
                cast(list[str], args.local_artifact)
            ),
        )
    )
    rendered = json.dumps(plan, indent=2, sort_keys=True)
    plan_out = cast(Path | None, args.plan_out)
    if plan_out is not None:
        plan_out.parent.mkdir(parents=True, exist_ok=True)
        plan_out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())

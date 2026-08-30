"""Carry a *first* official manifest run's private bytes to the OIDC runner.

Staging is Actions-only: the results and packet buckets and their KMS key are
governed by resource policies naming only the OIDC roles, so a developer machine
cannot write them at all.  For a *supplementary* sibling that is not a problem --
everything it shares with the official freeze is already staged and immutable, so
``manifest_run_materialize`` rebuilds the tree inside the workflow from those
objects.  A *first* official staging has no such source: its prefix is empty by
definition, which is exactly what makes it first.

The bytes therefore have to travel, and they cannot travel through this public
repository: the 13 frozen artifacts include the corpus manifest, the prediction
units, and the final labels, and the 200 model packets are un-run evaluation
inputs.  Publishing any of them before the run would destroy the contamination
control the benchmark rests on.

So they travel the way the paid-labeling chain already moves private source: as
one closed archive, age-encrypted to a recipient whose identity is a protected
environment secret, uploaded as an asset on a never-published **draft** GitHub
release, and pinned by exact release id, asset id, name, size, and digest at
dispatch.  The operator's upload is a GitHub write through the ordinary broker,
not an S3 write, so the manifest-staging OIDC role remains the only credential
that can create an object in the official prefix.

**The transport is not trusted, and does not need to be.**  Confidentiality is
the only property age and the draft release provide.  Integrity comes from the
commitments already in the chain: the dispatch pins the ciphertext digest, the
ciphertext decrypts to an archive holding a freeze bundle pinned by its own
dispatched digest, that bundle commits the SHA-256 of all 13 artifacts,
``run-inputs.json`` is pinned by a dispatched digest and commits the SHA-256 of
all 200 packets, and ``stage-manifest-forecast`` re-verifies every one of those
commitments before it writes.  A substituted archive can only fail loudly.

This module is deliberately *not* built on ``legalforecast.labeling
.official_paid_baton``'s sealed-package codec.  That codec's package manifest is
an authenticated byte contract in the live Cycle 1 chain and is frozen by
``docs/cycle-1-change-control.md``; refactoring a seam out of it to share here
would put a frozen contract at risk for no integrity gain, because -- unlike the
baton, which is its own chain of custody -- every byte in this package is already
committed by the freeze bundle and ``run-inputs.json``.  What is *not* redundant
is closed, safe archive handling, and that is what lives here.

Two operations, one on each side of the transport:

``build``
    Operator-side.  Collects the closed member set, normalizes the freeze
    bundle's artifact paths to the packaged layout, and writes a deterministic
    archive.  Prints the digests the dispatch has to pin.

``open``
    Runner-side.  Extracts an archive into an artifact root and a manifest-mode
    output directory, refusing anything that is not a plain, in-tree file, then
    holds the three pinned digests to their dispatched values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    sha256_file,
    verify_freeze_bundle_bytes,
    write_hash_bundle,
)
from legalforecast.publication.manifest_forecast_stage_lane import (
    SHA256_PATTERN,
    iter_packet_rows,
    load_json_object,
)

MANIFEST_RUN_SOURCE_PACKAGE_SCHEMA_VERSION = (
    "legalforecast-manifest-run-source-package-v1"
)

#: Archive member holding the path-normalized freeze bundle.
PACKAGE_FREEZE_NAME = "freeze.json"
#: Archive directory holding the frozen artifacts, one level, no nesting beyond
#: whatever the freeze bundle itself records relative to ``--artifact-root``.
PACKAGE_ARTIFACT_PREFIX = "artifact-root"
#: Archive directory holding the manifest-mode output tree.
PACKAGE_OUTPUT_PREFIX = "output-dir"

RUN_INPUTS_NAME = "run-inputs.json"
RUN_RECORD_NAME = "manifest-mode-run-record.json"

# The whole Cycle 1 corpus is ~15 MB across ~215 files. These caps are an order
# of magnitude above that: generous enough that a legitimate package never
# approaches them, tight enough that a decompression bomb cannot exhaust the
# runner before any commitment is checked.
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_MEMBER_COUNT = 4096

BUILD_SOURCE_PACKAGE_DESCRIPTION = (
    "Collect the closed input set for a FIRST official staging -- the frozen "
    "artifacts, the model packets run-inputs.json commits, and a freeze bundle "
    "rewritten to the packaged layout -- into one deterministic archive. "
    "Encrypt it with age and upload only the ciphertext to a never-published "
    "draft release; the archive itself is private corpus bytes and must never "
    "be committed or published. The digests printed here are what the staging "
    "dispatch pins."
)
OPEN_SOURCE_PACKAGE_DESCRIPTION = (
    "Runner-side counterpart to build-manifest-run-source-package. Extracts one "
    "archive into an artifact root and a manifest-mode output directory, "
    "refusing any member that is not a plain, in-tree file, then holds the "
    "freeze bundle, run-inputs, and run record to the digests the dispatch "
    "pinned. Every remaining byte is committed by one of those three, and "
    "stage-manifest-forecast re-verifies all of them."
)


class ManifestRunSourcePackageError(ValueError):
    """Raised when a first-stage source package cannot be built or opened."""


@dataclass(frozen=True, slots=True)
class BuildSourcePackageConfig:
    """Inputs for one operator-side source package build."""

    freeze_bundle: Path
    artifact_root: Path
    output_dir: Path
    package_out: Path

    def __post_init__(self) -> None:
        if not self.freeze_bundle.is_file():
            raise ManifestRunSourcePackageError(
                f"freeze bundle is missing: {self.freeze_bundle}"
            )
        if not self.artifact_root.is_dir():
            raise ManifestRunSourcePackageError(
                f"artifact_root is not a directory: {self.artifact_root}"
            )
        if not self.output_dir.is_dir():
            raise ManifestRunSourcePackageError(
                f"output_dir is not a directory: {self.output_dir}"
            )


@dataclass(frozen=True, slots=True)
class OpenSourcePackageConfig:
    """Inputs for one runner-side source package extraction."""

    package: Path
    artifact_root: Path
    output_dir: Path
    freeze_bundle_out: Path
    freeze_bundle_sha256: str
    run_inputs_sha256: str
    run_record_sha256: str

    def __post_init__(self) -> None:
        for name, digest in (
            ("freeze_bundle_sha256", self.freeze_bundle_sha256),
            ("run_inputs_sha256", self.run_inputs_sha256),
            ("run_record_sha256", self.run_record_sha256),
        ):
            if SHA256_PATTERN.fullmatch(digest) is None:
                raise ManifestRunSourcePackageError(
                    f"{name} must be a lowercase SHA-256 hex digest"
                )
        if not self.package.is_file():
            raise ManifestRunSourcePackageError(
                f"source package is missing: {self.package}"
            )


def build_manifest_run_source_package(
    config: BuildSourcePackageConfig,
) -> dict[str, Any]:
    """Seal one first-stage official corpus into a deterministic archive."""

    bundle = _verified_bundle(config.freeze_bundle, config.artifact_root)
    artifact_members = _artifact_members(bundle, config.artifact_root)
    output_members, packet_count = _output_members(config.output_dir)

    normalized_freeze = _normalized_freeze_bytes(bundle, config.artifact_root)
    members: dict[str, bytes] = {PACKAGE_FREEZE_NAME: normalized_freeze}
    members.update(artifact_members)
    members.update(output_members)
    _require_member_budget(members)

    _write_archive(config.package_out, members)
    package_sha256 = sha256_file(config.package_out)

    return {
        "schema_version": MANIFEST_RUN_SOURCE_PACKAGE_SCHEMA_VERSION,
        "package": str(config.package_out),
        "package_sha256": package_sha256,
        "package_size_bytes": config.package_out.stat().st_size,
        "member_count": len(members),
        "total_member_bytes": sum(len(payload) for payload in members.values()),
        # The three digests the dispatch pins. Every other byte in the package is
        # committed by one of them, transitively.
        "freeze_bundle_sha256": hashlib.sha256(normalized_freeze).hexdigest(),
        "run_inputs_sha256": hashlib.sha256(
            members[f"{PACKAGE_OUTPUT_PREFIX}/{RUN_INPUTS_NAME}"]
        ).hexdigest(),
        "run_record_sha256": hashlib.sha256(
            members[f"{PACKAGE_OUTPUT_PREFIX}/{RUN_RECORD_NAME}"]
        ).hexdigest(),
        "packet_count": packet_count,
        "artifact_count": len(artifact_members),
    }


def open_manifest_run_source_package(
    config: OpenSourcePackageConfig,
) -> dict[str, Any]:
    """Extract one source package and hold it to its dispatched commitments."""

    members = _read_archive(config.package)
    if PACKAGE_FREEZE_NAME not in members:
        raise ManifestRunSourcePackageError(
            f"source package has no {PACKAGE_FREEZE_NAME}"
        )

    freeze_payload = members[PACKAGE_FREEZE_NAME]
    _require_digest(freeze_payload, config.freeze_bundle_sha256, PACKAGE_FREEZE_NAME)
    for name, expected in (
        (f"{PACKAGE_OUTPUT_PREFIX}/{RUN_INPUTS_NAME}", config.run_inputs_sha256),
        (f"{PACKAGE_OUTPUT_PREFIX}/{RUN_RECORD_NAME}", config.run_record_sha256),
    ):
        if name not in members:
            raise ManifestRunSourcePackageError(f"source package has no {name}")
        _require_digest(members[name], expected, name)

    artifact_records = _extract_prefix(
        members, PACKAGE_ARTIFACT_PREFIX, config.artifact_root
    )
    output_records = _extract_prefix(members, PACKAGE_OUTPUT_PREFIX, config.output_dir)
    _write_new(config.freeze_bundle_out, freeze_payload)

    unclaimed = sorted(
        name
        for name in members
        if name != PACKAGE_FREEZE_NAME
        and not name.startswith(f"{PACKAGE_ARTIFACT_PREFIX}/")
        and not name.startswith(f"{PACKAGE_OUTPUT_PREFIX}/")
    )
    if unclaimed:
        # Not a security boundary -- the ciphertext digest already authenticates
        # the whole archive -- but an unplaced member means the package was built
        # by something other than ``build``, and guessing where it belongs is how
        # an unreviewed file reaches the staging inputs.
        raise ManifestRunSourcePackageError(
            "source package holds members outside "
            f"{PACKAGE_FREEZE_NAME}, {PACKAGE_ARTIFACT_PREFIX}/ and "
            f"{PACKAGE_OUTPUT_PREFIX}/: {', '.join(unclaimed)}"
        )

    return {
        "schema_version": MANIFEST_RUN_SOURCE_PACKAGE_SCHEMA_VERSION,
        "package": str(config.package),
        "package_sha256": sha256_file(config.package),
        "freeze_bundle": str(config.freeze_bundle_out),
        "freeze_bundle_sha256": config.freeze_bundle_sha256,
        "run_inputs_sha256": config.run_inputs_sha256,
        "run_record_sha256": config.run_record_sha256,
        "artifact_root": str(config.artifact_root),
        "output_dir": str(config.output_dir),
        "artifact_count": len(artifact_records),
        "output_object_count": len(output_records),
        "member_count": len(members),
    }


def _verified_bundle(freeze_bundle: Path, artifact_root: Path) -> FreezeBundle:
    try:
        return verify_freeze_bundle_bytes(
            freeze_bundle.read_bytes(), root_path=artifact_root
        )
    except (FreezeProtocolError, OSError, ValueError) as exc:
        raise ManifestRunSourcePackageError(
            f"freeze bundle is not valid against --artifact-root: {exc}"
        ) from exc


def _artifact_members(bundle: FreezeBundle, artifact_root: Path) -> dict[str, bytes]:
    """Collect the frozen artifacts under the layout staging will see.

    The relative-path check here is the *first* of two independent fences against
    ``legalforecastbench-bh6j``.  That defect fires when an artifact's path
    relative to ``--artifact-root`` already begins with ``artifacts/``, because
    ``manifest_forecast_stage._freeze_objects`` prepends that segment
    unconditionally and would then produce ``artifacts/artifacts/<name>`` keys.
    A staged bundle fed back through staging is the usual way in; pointing
    ``--artifact-root`` one directory too high is the other, and it is reachable
    on a *first* stage, where nothing else would catch it.  Refusing the shape at
    build time removes it from this lane permanently.
    """

    root = artifact_root.resolve()
    members: dict[str, bytes] = {}
    for artifact in bundle.artifacts:
        path = artifact.path.resolve()
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ManifestRunSourcePackageError(
                f"frozen artifact is outside --artifact-root: {path}"
            ) from exc
        if not relative.parts or ".." in relative.parts:
            raise ManifestRunSourcePackageError(
                f"unsafe frozen artifact path: {relative}"
            )
        if relative.parts[0] == "artifacts":
            raise ManifestRunSourcePackageError(
                "frozen artifact path relative to --artifact-root starts with "
                f"'artifacts/': {relative}. Staging prepends that segment itself, "
                "so this would stage artifacts/artifacts/... keys into an "
                "immutable prefix no role can delete. Pass the directory that "
                "directly contains the frozen artifacts"
            )
        member = f"{PACKAGE_ARTIFACT_PREFIX}/{relative.as_posix()}"
        if member in members:
            raise ManifestRunSourcePackageError(
                f"duplicate frozen artifact path: {relative}"
            )
        payload = _read_regular_file(path)
        if len(payload) != artifact.size_bytes:
            raise ManifestRunSourcePackageError(
                f"frozen artifact {artifact.name} is {len(payload)} bytes, not "
                f"the committed {artifact.size_bytes}"
            )
        _require_digest(payload, artifact.sha256, str(artifact.name))
        members[member] = payload
    return members


def _output_members(output_dir: Path) -> tuple[dict[str, bytes], int]:
    """Collect a closed member set from the manifest-mode output directory.

    Closed on purpose: the two named records plus exactly the packet keys
    ``run-inputs.json`` commits.  A whole-tree sweep would carry whatever else
    the operator's working directory happens to hold into an immutable prefix.
    """

    root = output_dir.resolve()
    members: dict[str, bytes] = {}
    for name in (RUN_INPUTS_NAME, RUN_RECORD_NAME):
        members[f"{PACKAGE_OUTPUT_PREFIX}/{name}"] = _read_regular_file(root / name)

    run_inputs = load_json_object(root / RUN_INPUTS_NAME, "run-inputs manifest")
    packet_count = 0
    for key, digest in iter_packet_rows(run_inputs):
        path = (root / key).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ManifestRunSourcePackageError(
                f"packet path is outside output directory: {key}"
            ) from exc
        member = f"{PACKAGE_OUTPUT_PREFIX}/{PurePosixPath(key).as_posix()}"
        if member in members:
            raise ManifestRunSourcePackageError(f"duplicate packet key: {key}")
        payload = _read_regular_file(path)
        _require_digest(payload, digest, key)
        members[member] = payload
        packet_count += 1
    return members, packet_count


def _normalized_freeze_bytes(bundle: FreezeBundle, artifact_root: Path) -> bytes:
    """Rewrite the bundle's artifact paths to the packaged artifact root.

    The operator's bundle records absolute machine paths, which are meaningless
    on the runner and are exactly the kind of local detail this public repository
    must not carry.  ``write_hash_bundle`` with ``root_path`` relativizes them and
    recomputes the bundle hash over the rewritten record, which is the same
    operation staging performs when it rewrites paths to ``artifacts/<name>``.
    """

    with tempfile.TemporaryDirectory(prefix="lfb-source-package-") as directory:
        path = Path(directory) / PACKAGE_FREEZE_NAME
        write_hash_bundle(path, bundle, root_path=artifact_root.resolve())
        return path.read_bytes()


def _write_archive(package_out: Path, members: Mapping[str, bytes]) -> None:
    """Write a deterministic, stored-only archive with no ambient metadata.

    ``ZIP_STORED`` and a fixed timestamp so the same inputs produce the same
    bytes: the operator pins the ciphertext digest at dispatch, and a package
    whose digest moved between two builds of identical inputs would make that pin
    unverifiable by anyone but the person who built it.
    """

    package_out.parent.mkdir(parents=True, exist_ok=True)
    if package_out.exists():
        raise ManifestRunSourcePackageError(
            f"refusing to replace an existing package: {package_out}"
        )
    with zipfile.ZipFile(package_out, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(members.items()):
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)


def _read_archive(package: Path) -> dict[str, bytes]:
    """Read every member of a closed archive, refusing anything unusual.

    Nothing here is extracted by path: members are read into memory under name,
    size, and count budgets, and only the caller's ``_extract_prefix`` writes
    them, under a root it re-checks.  A traversing or absolute member name, a
    symlink, a directory entry, or a device node is refused rather than
    sanitized, because a package that contains one was not built by ``build``.
    """

    members: dict[str, bytes] = {}
    total = 0
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBER_COUNT:
                raise ManifestRunSourcePackageError(
                    f"source package holds {len(infos)} members, over the "
                    f"{MAX_MEMBER_COUNT} limit"
                )
            for info in infos:
                name = _safe_member_name(info.filename)
                if info.is_dir():
                    raise ManifestRunSourcePackageError(
                        f"source package contains a directory entry: {name}"
                    )
                # Only the file-type bits decide. A zip entry may legitimately
                # carry no type bits at all (a plain writestr does that), so the
                # test is "declares a type, and it is not a regular file" --
                # which is what catches a symlink or a device node.
                file_type = (info.external_attr >> 16) & 0o170000
                if file_type and file_type != stat.S_IFREG:
                    raise ManifestRunSourcePackageError(
                        f"source package member is not a regular file: {name}"
                    )
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ManifestRunSourcePackageError(
                        f"source package member exceeds the size limit: {name}"
                    )
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ManifestRunSourcePackageError(
                        "source package exceeds the total size limit"
                    )
                if name in members:
                    raise ManifestRunSourcePackageError(
                        f"source package names {name} more than once"
                    )
                payload = archive.read(info)
                if len(payload) != info.file_size:
                    raise ManifestRunSourcePackageError(
                        f"source package member size differs on read: {name}"
                    )
                members[name] = payload
    except zipfile.BadZipFile as exc:
        raise ManifestRunSourcePackageError(
            f"source package is not a readable archive: {package}"
        ) from exc
    if not members:
        raise ManifestRunSourcePackageError("source package is empty")
    return members


def _extract_prefix(
    members: Mapping[str, bytes], prefix: str, destination: Path
) -> list[str]:
    root = destination.resolve()
    written: list[str] = []
    for name in sorted(members):
        if not name.startswith(f"{prefix}/"):
            continue
        relative = name[len(prefix) + 1 :]
        if not relative:
            raise ManifestRunSourcePackageError(f"empty member name under {prefix}/")
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:  # pragma: no cover - _safe_member_name precedes
            raise ManifestRunSourcePackageError(
                f"member escapes its destination root: {name}"
            ) from exc
        _write_new(target, members[name])
        written.append(relative)
    if not written:
        raise ManifestRunSourcePackageError(f"source package has no {prefix}/ members")
    return written


def _safe_member_name(raw: str) -> str:
    if not raw or raw != raw.strip() or "\\" in raw or "\x00" in raw:
        raise ManifestRunSourcePackageError(f"unsafe archive member name: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestRunSourcePackageError(f"unsafe archive member name: {raw!r}")
    return path.as_posix()


def _read_regular_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ManifestRunSourcePackageError(f"not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ManifestRunSourcePackageError(f"cannot read {path}") from exc


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ManifestRunSourcePackageError(
            f"refusing to replace an existing file: {path}"
        )
    path.write_bytes(payload)


def _require_digest(payload: bytes, expected: str, label: str) -> None:
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ManifestRunSourcePackageError(
            f"{label} hashes to {actual}, not the committed {expected}"
        )


def _require_member_budget(members: Mapping[str, bytes]) -> None:
    if len(members) > MAX_MEMBER_COUNT:
        raise ManifestRunSourcePackageError(
            f"source package would hold {len(members)} members, over the "
            f"{MAX_MEMBER_COUNT} limit"
        )
    total = 0
    for name, payload in members.items():
        if len(payload) > MAX_MEMBER_BYTES:
            raise ManifestRunSourcePackageError(
                f"source package member exceeds the size limit: {name}"
            )
        total += len(payload)
    if total > MAX_TOTAL_BYTES:
        raise ManifestRunSourcePackageError(
            "source package would exceed the total size limit"
        )


def add_build_source_package_arguments(parser: argparse.ArgumentParser) -> None:
    """Register CLI arguments for the operator-side package build."""

    parser.add_argument("--freeze-bundle", type=Path, required=True)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        required=True,
        help=(
            "Directory that DIRECTLY contains the frozen artifacts. Pointing it "
            "one level too high is refused: staging prepends its own artifacts/ "
            "segment, so a relative path already starting with artifacts/ would "
            "stage doubled keys into an immutable prefix."
        ),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--package-out",
        type=Path,
        required=True,
        help="Archive to create. An existing path is refused, never replaced.",
    )


def add_open_source_package_arguments(parser: argparse.ArgumentParser) -> None:
    """Register CLI arguments for the runner-side package extraction."""

    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze-bundle-out", type=Path, required=True)
    parser.add_argument(
        "--freeze-bundle-sha256",
        required=True,
        help=(
            "Raw-file SHA-256 of the packaged, path-normalized freeze bundle. "
            "This is the bundle build emitted, not the operator's local one, "
            "whose absolute artifact paths make different bytes."
        ),
    )
    parser.add_argument("--run-inputs-sha256", required=True)
    parser.add_argument("--run-record-sha256", required=True)


def run_build_source_package(args: argparse.Namespace) -> int:
    """CLI handler for ``acquisition build-manifest-run-source-package``."""

    record = build_manifest_run_source_package(
        BuildSourcePackageConfig(
            freeze_bundle=cast(Path, args.freeze_bundle),
            artifact_root=cast(Path, args.artifact_root),
            output_dir=cast(Path, args.output_dir),
            package_out=cast(Path, args.package_out),
        )
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def run_open_source_package(args: argparse.Namespace) -> int:
    """CLI handler for ``acquisition open-manifest-run-source-package``."""

    record = open_manifest_run_source_package(
        OpenSourcePackageConfig(
            package=cast(Path, args.package),
            artifact_root=cast(Path, args.artifact_root),
            output_dir=cast(Path, args.output_dir),
            freeze_bundle_out=cast(Path, args.freeze_bundle_out),
            freeze_bundle_sha256=cast(str, args.freeze_bundle_sha256),
            run_inputs_sha256=cast(str, args.run_inputs_sha256),
            run_record_sha256=cast(str, args.run_record_sha256),
        )
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - entry
    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.publication.manifest_run_source_package"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_build_source_package_arguments(subparsers.add_parser("build"))
    add_open_source_package_arguments(subparsers.add_parser("open"))
    args = parser.parse_args(argv)
    if args.command == "build":
        return run_build_source_package(args)
    return run_open_source_package(args)


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())

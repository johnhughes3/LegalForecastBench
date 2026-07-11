"""Freeze benchmark artifacts and detect post-freeze drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from legalforecast._datetime import format_utc_iso_z
from legalforecast._hashing import is_lowercase_sha256
from legalforecast.protocol.manifest import hash_payload

_CHUNK_SIZE = 1024 * 1024


class FreezeProtocolError(ValueError):
    """Base error for invalid or drifting freeze artifacts."""


class MissingFreezeArtifactError(FreezeProtocolError):
    """Raised when a required freeze artifact path is absent."""


class FrozenArtifactName(StrEnum):
    MANIFEST = "manifest"
    UNITS = "units"
    LABELS = "labels"
    PROMPT = "prompt"
    SCORER = "scorer"
    HARNESS = "harness"
    MODEL_REGISTRY = "model_registry"
    BASELINES = "baselines"
    EXCLUSION_LEDGER = "exclusion_ledger"


REQUIRED_FREEZE_ARTIFACTS: tuple[FrozenArtifactName, ...] = (
    FrozenArtifactName.MANIFEST,
    FrozenArtifactName.UNITS,
    FrozenArtifactName.LABELS,
    FrozenArtifactName.PROMPT,
    FrozenArtifactName.SCORER,
    FrozenArtifactName.HARNESS,
    FrozenArtifactName.MODEL_REGISTRY,
    FrozenArtifactName.BASELINES,
    FrozenArtifactName.EXCLUSION_LEDGER,
)
_FREEZE_HASH_FIELDS: Mapping[FrozenArtifactName, str] = {
    FrozenArtifactName.MANIFEST: "manifest_sha256",
    FrozenArtifactName.UNITS: "units_sha256",
    FrozenArtifactName.LABELS: "labels_sha256",
    FrozenArtifactName.PROMPT: "prompt_sha256",
    FrozenArtifactName.SCORER: "scorer_sha256",
    FrozenArtifactName.HARNESS: "harness_sha256",
    FrozenArtifactName.EXCLUSION_LEDGER: "exclusion_ledger_sha256",
}
ArtifactPathMap = (
    Mapping[FrozenArtifactName, str | Path]
    | Mapping[str, str | Path]
    | Mapping[FrozenArtifactName | str, str | Path]
)


@dataclass(frozen=True, slots=True)
class FrozenArtifact:
    """One immutable artifact included in a cycle freeze."""

    name: FrozenArtifactName
    path: Path
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        _require_sha256(self.sha256, f"{self.name.value}.sha256")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")

    def to_record(self, *, root_path: Path | None = None) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "path": _path_for_record(self.path, root_path=root_path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FreezeDrift:
    """A missing or modified artifact after a freeze."""

    name: FrozenArtifactName
    path: Path
    expected_sha256: str
    actual_sha256: str | None

    @property
    def is_missing(self) -> bool:
        return self.actual_sha256 is None

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "path": str(self.path),
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "is_missing": self.is_missing,
        }


@dataclass(frozen=True, slots=True)
class FreezeBundle:
    """Frozen hash bundle for one benchmark cycle."""

    cycle_id: str
    freeze_timestamp: datetime
    artifacts: tuple[FrozenArtifact, ...]
    amends_bundle_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.cycle_id, "cycle_id")
        _require_aware_datetime(self.freeze_timestamp, "freeze_timestamp")
        if not self.artifacts:
            raise ValueError("freeze bundle requires at least one artifact")
        seen: set[FrozenArtifactName] = set()
        duplicates: set[str] = set()
        for artifact in self.artifacts:
            if artifact.name in seen:
                duplicates.add(artifact.name.value)
            seen.add(artifact.name)
        if duplicates:
            raise ValueError(f"duplicate freeze artifacts: {sorted(duplicates)}")
        if self.amends_bundle_sha256 is not None:
            _require_sha256(self.amends_bundle_sha256, "amends_bundle_sha256")

    @property
    def bundle_sha256(self) -> str:
        return hash_payload(self.to_record(include_bundle_hash=False))

    def artifact(self, name: FrozenArtifactName) -> FrozenArtifact:
        for artifact in self.artifacts:
            if artifact.name is name:
                return artifact
        raise KeyError(name.value)

    def frozen_artifact_hashes(self) -> dict[str, str]:
        return {
            field_name: self.artifact(artifact_name).sha256
            for artifact_name, field_name in _FREEZE_HASH_FIELDS.items()
        }

    def to_record(
        self,
        *,
        root_path: Path | None = None,
        include_bundle_hash: bool = True,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "cycle_id": self.cycle_id,
            "freeze_timestamp": _iso_datetime(self.freeze_timestamp),
            "artifacts": [
                artifact.to_record(root_path=root_path)
                for artifact in sorted(self.artifacts, key=_artifact_sort_key)
            ],
            "frozen_artifacts": self.frozen_artifact_hashes(),
            "model_registry": {
                "path": _path_for_record(
                    self.artifact(FrozenArtifactName.MODEL_REGISTRY).path,
                    root_path=root_path,
                ),
                "sha256": self.artifact(FrozenArtifactName.MODEL_REGISTRY).sha256,
            },
            "baselines": {
                "path": _path_for_record(
                    self.artifact(FrozenArtifactName.BASELINES).path,
                    root_path=root_path,
                ),
                "sha256": self.artifact(FrozenArtifactName.BASELINES).sha256,
            },
            "exclusion_ledger": {
                "path": _path_for_record(
                    self.artifact(FrozenArtifactName.EXCLUSION_LEDGER).path,
                    root_path=root_path,
                ),
                "sha256": self.artifact(FrozenArtifactName.EXCLUSION_LEDGER).sha256,
            },
        }
        if self.amends_bundle_sha256 is not None:
            record["amends_bundle_sha256"] = self.amends_bundle_sha256
        if include_bundle_hash:
            record["hash_bundle_sha256"] = hash_payload(record)
        return record


def sha256_file(path: str | Path) -> str:
    """Compute a SHA-256 hash over raw file bytes."""

    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise MissingFreezeArtifactError(f"freeze artifact missing: {artifact_path}")
    digest = hashlib.sha256()
    with artifact_path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_cycle(
    cycle_id: str,
    artifact_paths: ArtifactPathMap,
    *,
    freeze_timestamp: datetime | None = None,
    required_artifacts: Sequence[FrozenArtifactName] = REQUIRED_FREEZE_ARTIFACTS,
    bundle_output_path: str | Path | None = None,
) -> FreezeBundle:
    """Hash all cycle artifacts and optionally write a bundle file."""

    bundle = FreezeBundle(
        cycle_id=cycle_id,
        freeze_timestamp=freeze_timestamp or datetime.now(UTC),
        artifacts=_collect_artifacts(artifact_paths, required_artifacts),
    )

    if bundle_output_path is not None:
        write_hash_bundle(bundle_output_path, bundle)
    return bundle


def amend_freeze_cycle(
    prior_bundle_path: str | Path,
    model_registry_path: str | Path,
    *,
    root_path: str | Path | None = None,
    prior_bundle_paths: Sequence[str | Path] = (),
    freeze_timestamp: datetime | None = None,
    bundle_output_path: str | Path | None = None,
) -> FreezeBundle:
    """Create a fail-closed registry-only amendment to an existing freeze."""

    root = Path(root_path) if root_path is not None else None
    prior = verify_freeze_bundle(
        prior_bundle_path,
        root_path=root,
        amendment_bundle_paths=prior_bundle_paths,
    )
    registry_path = Path(model_registry_path)
    registry_artifact = FrozenArtifact(
        name=FrozenArtifactName.MODEL_REGISTRY,
        path=registry_path,
        sha256=sha256_file(registry_path),
        size_bytes=registry_path.stat().st_size,
    )
    amended = FreezeBundle(
        cycle_id=prior.cycle_id,
        freeze_timestamp=freeze_timestamp or datetime.now(UTC),
        artifacts=tuple(
            registry_artifact
            if artifact.name is FrozenArtifactName.MODEL_REGISTRY
            else artifact
            for artifact in prior.artifacts
        ),
        amends_bundle_sha256=prior.bundle_sha256,
    )
    _verify_amendment(parent=prior, amended=amended)
    if bundle_output_path is not None:
        write_hash_bundle(bundle_output_path, amended, root_path=root)
    return amended


def write_hash_bundle(
    path: str | Path,
    bundle: FreezeBundle,
    *,
    root_path: str | Path | None = None,
) -> Mapping[str, Any]:
    """Write a machine-readable final hash bundle."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = Path(root_path) if root_path is not None else None
    record = bundle.to_record(root_path=root)
    output_path.write_text(
        f"{json.dumps(record, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return record


def load_freeze_bundle(
    path: str | Path,
    *,
    root_path: str | Path | None = None,
    artifact_path_overrides: ArtifactPathMap | None = None,
) -> FreezeBundle:
    """Load a freeze bundle and validate its own commitment hash."""

    bundle_path = Path(path)
    try:
        raw_record = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MissingFreezeArtifactError(
            f"pre-run freeze commitment is missing: {bundle_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise FreezeProtocolError(
            f"pre-run freeze commitment is invalid JSON: {bundle_path}"
        ) from exc
    if not isinstance(raw_record, Mapping):
        raise FreezeProtocolError("pre-run freeze commitment must be a JSON object")
    record = cast(Mapping[str, Any], raw_record)

    _verify_bundle_commitment_hash(record)
    cycle_id = _required_string(record, "cycle_id")
    freeze_timestamp = _required_timestamp(record, "freeze_timestamp")
    root = Path(root_path) if root_path is not None else None
    overrides = _coerce_artifact_path_overrides(artifact_path_overrides)
    artifacts = _load_record_artifacts(record, root_path=root, overrides=overrides)
    _require_all_freeze_artifacts(artifacts)
    return FreezeBundle(
        cycle_id=cycle_id,
        freeze_timestamp=freeze_timestamp,
        artifacts=artifacts,
        amends_bundle_sha256=_optional_sha256_string(record, "amends_bundle_sha256"),
    )


def verify_freeze_bundle(
    path: str | Path,
    *,
    cycle_id: str | None = None,
    root_path: str | Path | None = None,
    artifact_path_overrides: ArtifactPathMap | None = None,
    amendment_bundle_paths: Sequence[str | Path] = (),
) -> FreezeBundle:
    """Load a freeze bundle and raise if any required artifact has drifted."""

    bundle = load_freeze_bundle(
        path,
        root_path=root_path,
        artifact_path_overrides=artifact_path_overrides,
    )
    if cycle_id is not None and bundle.cycle_id != cycle_id:
        raise FreezeProtocolError(
            "pre-run freeze commitment cycle_id does not match dispatch input"
        )
    verify_no_freeze_drift(bundle)
    _verify_amendment_chain(
        bundle,
        amendment_bundle_paths=amendment_bundle_paths,
        root_path=Path(root_path) if root_path is not None else None,
    )
    return bundle


def detect_freeze_drift(bundle: FreezeBundle) -> tuple[FreezeDrift, ...]:
    """Return every frozen artifact that is now missing or modified."""

    drift: list[FreezeDrift] = []
    for artifact in bundle.artifacts:
        try:
            actual_sha256 = sha256_file(artifact.path)
        except MissingFreezeArtifactError:
            drift.append(
                FreezeDrift(
                    name=artifact.name,
                    path=artifact.path,
                    expected_sha256=artifact.sha256,
                    actual_sha256=None,
                )
            )
            continue
        if actual_sha256 != artifact.sha256:
            drift.append(
                FreezeDrift(
                    name=artifact.name,
                    path=artifact.path,
                    expected_sha256=artifact.sha256,
                    actual_sha256=actual_sha256,
                )
            )
    return tuple(drift)


def verify_no_freeze_drift(bundle: FreezeBundle) -> None:
    """Raise when any frozen artifact is missing or has changed."""

    drift = detect_freeze_drift(bundle)
    if not drift:
        return
    messages = [
        (
            f"{item.name.value} missing at {item.path}"
            if item.is_missing
            else f"{item.name.value} hash changed at {item.path}"
        )
        for item in drift
    ]
    raise FreezeProtocolError("; ".join(messages))


def _verify_amendment_chain(
    bundle: FreezeBundle,
    *,
    amendment_bundle_paths: Sequence[str | Path],
    root_path: Path | None,
) -> None:
    if bundle.amends_bundle_sha256 is None:
        return
    ancestors: dict[str, FreezeBundle] = {}
    for path in amendment_bundle_paths:
        ancestor = load_freeze_bundle(path, root_path=root_path)
        ancestors[ancestor.bundle_sha256] = ancestor

    current = bundle
    seen = {current.bundle_sha256}
    while current.amends_bundle_sha256 is not None:
        parent_hash = current.amends_bundle_sha256
        parent = ancestors.get(parent_hash)
        if parent is None:
            raise FreezeProtocolError(
                "amendment ancestor bundle is missing from the committed chain: "
                f"{parent_hash}"
            )
        if parent.bundle_sha256 in seen:
            raise FreezeProtocolError("freeze amendment chain contains a cycle")
        seen.add(parent.bundle_sha256)
        verify_no_freeze_drift(parent)
        _verify_amendment(parent=parent, amended=current)
        current = parent


def _verify_amendment(*, parent: FreezeBundle, amended: FreezeBundle) -> None:
    if amended.amends_bundle_sha256 != parent.bundle_sha256:
        raise FreezeProtocolError("amendment does not reference its parent bundle")
    if amended.cycle_id != parent.cycle_id:
        raise FreezeProtocolError("amendment cycle_id must match its parent bundle")
    for name in FrozenArtifactName:
        if name is FrozenArtifactName.MODEL_REGISTRY:
            continue
        if amended.artifact(name).sha256 != parent.artifact(name).sha256:
            raise FreezeProtocolError(
                f"amendment may change only model_registry; {name.value} hash changed"
            )

    parent_registry = _load_registry_for_amendment(parent)
    amended_registry = _load_registry_for_amendment(amended)
    parent_entries = {entry.registry_key: entry for entry in parent_registry.entries}
    amended_entries = {entry.registry_key: entry for entry in amended_registry.entries}
    missing = sorted(parent_entries.keys() - amended_entries.keys())
    if missing:
        raise FreezeProtocolError(
            f"amended model registry removed existing entries: {missing}"
        )
    changed = sorted(
        key
        for key, entry in parent_entries.items()
        if _registry_entry_hash(entry) != _registry_entry_hash(amended_entries[key])
    )
    if changed:
        raise FreezeProtocolError(
            f"amended model registry existing registry entry changed: {changed}"
        )
    added_keys = sorted(amended_entries.keys() - parent_entries.keys())
    if not added_keys:
        raise FreezeProtocolError("amended model registry must be a strict superset")

    try:
        from legalforecast.evals.model_registry import earliest_eligible_decision_date

        prior_anchor = earliest_eligible_decision_date(parent_registry.entries)
    except ValueError as exc:
        raise FreezeProtocolError(
            f"parent registry has no valid release anchor: {exc}"
        ) from exc
    late = sorted(
        key
        for key in added_keys
        if amended_entries[key].release_timestamp is None
        or amended_entries[key].release_timestamp.astimezone(UTC).date() > prior_anchor
    )
    if late:
        raise FreezeProtocolError(
            "added model raises release anchor beyond "
            f"{prior_anchor.isoformat()}: {late}"
        )


def _load_registry_for_amendment(bundle: FreezeBundle) -> Any:
    try:
        from legalforecast.evals.model_registry import load_model_registry

        return load_model_registry(
            bundle.artifact(FrozenArtifactName.MODEL_REGISTRY).path
        )
    except (OSError, ValueError) as exc:
        raise FreezeProtocolError(f"invalid amendment model registry: {exc}") from exc


def _registry_entry_hash(entry: Any) -> str:
    from legalforecast.evals.model_registry import model_registry_entry_sha256

    return model_registry_entry_sha256(entry)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast freeze",
        description="Freeze LegalForecast-MTD cycle artifacts and write hashes.",
    )
    parser.add_argument("cycle_id")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--units", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--scorer", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--model-registry", required=True)
    parser.add_argument("--baselines", required=True)
    parser.add_argument("--exclusion-ledger", required=True)
    parser.add_argument("--timestamp")
    parser.add_argument("--bundle-output")
    return parser


def build_verify_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast freeze verify",
        description="Verify a frozen LegalForecast-MTD cycle commitment.",
    )
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--cycle-id")
    parser.add_argument("--root")
    parser.add_argument(
        "--amendment-bundle",
        action="append",
        default=[],
        help="Committed ancestor freeze bundle; repeat for the full amendment chain.",
    )
    parser.add_argument(
        "--artifact-path",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help=(
            "Override an artifact path from the bundle, for artifacts downloaded "
            "to workflow-local paths."
        ),
    )
    return parser


def build_amend_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast freeze amend",
        description="Create a registry-only amendment to a frozen cycle.",
    )
    parser.add_argument("--prior-bundle", required=True)
    parser.add_argument("--model-registry", required=True)
    parser.add_argument("--root")
    parser.add_argument(
        "--amendment-bundle",
        action="append",
        default=[],
        help="Committed ancestor of the prior bundle; repeat for the full chain.",
    )
    parser.add_argument("--timestamp")
    parser.add_argument("--bundle-output", required=True)
    return parser


def cli_freeze(argv: Sequence[str]) -> int:
    if argv and argv[0] == "verify":
        return _cli_verify_freeze(argv[1:])
    if argv and argv[0] == "amend":
        return _cli_amend_freeze(argv[1:])

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    cycle_id = cast(str, args.cycle_id)
    bundle_output = (
        Path(cast(str, args.bundle_output))
        if args.bundle_output is not None
        else Path("manifests") / f"{cycle_id}.freeze.json"
    )

    bundle = freeze_cycle(
        cycle_id,
        {
            FrozenArtifactName.MANIFEST: Path(cast(str, args.manifest)),
            FrozenArtifactName.UNITS: Path(cast(str, args.units)),
            FrozenArtifactName.LABELS: Path(cast(str, args.labels)),
            FrozenArtifactName.PROMPT: Path(cast(str, args.prompt)),
            FrozenArtifactName.SCORER: Path(cast(str, args.scorer)),
            FrozenArtifactName.HARNESS: Path(cast(str, args.harness)),
            FrozenArtifactName.MODEL_REGISTRY: Path(cast(str, args.model_registry)),
            FrozenArtifactName.BASELINES: Path(cast(str, args.baselines)),
            FrozenArtifactName.EXCLUSION_LEDGER: Path(cast(str, args.exclusion_ledger)),
        },
        freeze_timestamp=(
            _parse_timestamp(cast(str, args.timestamp))
            if args.timestamp is not None
            else None
        ),
        bundle_output_path=bundle_output,
    )
    print(json.dumps(bundle.to_record(root_path=Path.cwd()), sort_keys=True))
    return 0


def _cli_amend_freeze(argv: Sequence[str]) -> int:
    parser = build_amend_arg_parser()
    args = parser.parse_args(argv)
    try:
        bundle = amend_freeze_cycle(
            cast(str, args.prior_bundle),
            cast(str, args.model_registry),
            root_path=cast(str | None, args.root),
            prior_bundle_paths=cast(Sequence[str], args.amendment_bundle),
            freeze_timestamp=(
                _parse_timestamp(cast(str, args.timestamp))
                if args.timestamp is not None
                else None
            ),
            bundle_output_path=cast(str, args.bundle_output),
        )
    except (FreezeProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(bundle.to_record(root_path=Path.cwd()), sort_keys=True))
    return 0


def _cli_verify_freeze(argv: Sequence[str]) -> int:
    parser = build_verify_arg_parser()
    args = parser.parse_args(argv)
    try:
        verify_freeze_bundle(
            cast(str, args.bundle),
            cycle_id=cast(str | None, args.cycle_id),
            root_path=cast(str | None, args.root),
            artifact_path_overrides=_parse_artifact_path_overrides(
                cast(Sequence[str], args.artifact_path)
            ),
            amendment_bundle_paths=cast(Sequence[str], args.amendment_bundle),
        )
    except (FreezeProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("pre-run freeze commitment verified for all frozen artifacts")
    return 0


def _collect_artifacts(
    artifact_paths: ArtifactPathMap,
    required_artifacts: Sequence[FrozenArtifactName],
) -> tuple[FrozenArtifact, ...]:
    paths_by_name: dict[FrozenArtifactName, Path] = {}
    for raw_name, raw_path in artifact_paths.items():
        name = (
            raw_name
            if isinstance(raw_name, FrozenArtifactName)
            else FrozenArtifactName(raw_name)
        )
        if name in paths_by_name:
            raise ValueError(f"duplicate freeze artifact path: {name.value}")
        paths_by_name[name] = Path(raw_path)

    missing_names = [
        artifact_name.value
        for artifact_name in required_artifacts
        if artifact_name not in paths_by_name
    ]
    if missing_names:
        raise MissingFreezeArtifactError(
            f"freeze artifacts are required: {', '.join(missing_names)}"
        )

    artifacts: list[FrozenArtifact] = []
    for name in REQUIRED_FREEZE_ARTIFACTS:
        path = paths_by_name.get(name)
        if path is None:
            continue
        artifacts.append(
            FrozenArtifact(
                name=name,
                path=path,
                sha256=sha256_file(path),
                size_bytes=path.stat().st_size,
            )
        )
    return tuple(artifacts)


def _verify_bundle_commitment_hash(record: Mapping[str, Any]) -> None:
    expected_bundle_sha256 = record.get("hash_bundle_sha256")
    if not isinstance(expected_bundle_sha256, str):
        raise FreezeProtocolError(
            "pre-run freeze commitment missing hash_bundle_sha256"
        )
    _require_sha256(expected_bundle_sha256, "hash_bundle_sha256")
    record_without_hash = dict(record)
    del record_without_hash["hash_bundle_sha256"]
    if hash_payload(record_without_hash) != expected_bundle_sha256:
        raise FreezeProtocolError(
            "pre-run freeze commitment hash_bundle_sha256 mismatch"
        )


def _load_record_artifacts(
    record: Mapping[str, Any],
    *,
    root_path: Path | None,
    overrides: Mapping[FrozenArtifactName, Path],
) -> tuple[FrozenArtifact, ...]:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        raise FreezeProtocolError("pre-run freeze commitment missing artifacts list")

    loaded: list[FrozenArtifact] = []
    for index, raw_artifact in enumerate(cast(list[Any], artifacts), start=1):
        if not isinstance(raw_artifact, Mapping):
            raise FreezeProtocolError(
                f"pre-run freeze commitment artifact {index} must be a JSON object"
            )
        artifact_record = cast(Mapping[str, Any], raw_artifact)
        name = _required_artifact_name(artifact_record, index)
        loaded.append(
            FrozenArtifact(
                name=name,
                path=_record_artifact_path(
                    artifact_record,
                    name=name,
                    root_path=root_path,
                    overrides=overrides,
                ),
                sha256=_required_sha256_string(artifact_record, name),
                size_bytes=_required_size_bytes(artifact_record, name),
            )
        )
    return tuple(loaded)


def _record_artifact_path(
    artifact_record: Mapping[str, Any],
    *,
    name: FrozenArtifactName,
    root_path: Path | None,
    overrides: Mapping[FrozenArtifactName, Path],
) -> Path:
    override = overrides.get(name)
    if override is not None:
        return override
    path = artifact_record.get("path")
    if not isinstance(path, str) or not path.strip():
        raise FreezeProtocolError(
            f"pre-run freeze commitment artifact {name.value} is missing path"
        )
    record_path = Path(path)
    if root_path is not None and not record_path.is_absolute():
        return root_path / record_path
    return record_path


def _require_all_freeze_artifacts(artifacts: Sequence[FrozenArtifact]) -> None:
    present = {artifact.name for artifact in artifacts}
    missing_names = [
        artifact_name.value
        for artifact_name in REQUIRED_FREEZE_ARTIFACTS
        if artifact_name not in present
    ]
    if missing_names:
        raise FreezeProtocolError(
            "pre-run freeze commitment missing required artifacts: "
            f"{', '.join(missing_names)}"
        )


def _coerce_artifact_path_overrides(
    artifact_path_overrides: ArtifactPathMap | None,
) -> dict[FrozenArtifactName, Path]:
    if artifact_path_overrides is None:
        return {}
    overrides: dict[FrozenArtifactName, Path] = {}
    for raw_name, raw_path in artifact_path_overrides.items():
        name = (
            raw_name
            if isinstance(raw_name, FrozenArtifactName)
            else FrozenArtifactName(raw_name)
        )
        if name in overrides:
            raise ValueError(f"duplicate freeze artifact override: {name.value}")
        overrides[name] = Path(raw_path)
    return overrides


def _parse_artifact_path_overrides(
    values: Sequence[str],
) -> dict[FrozenArtifactName, Path]:
    overrides: dict[FrozenArtifactName, Path] = {}
    for value in values:
        if "=" not in value:
            raise FreezeProtocolError(
                "artifact path overrides must use NAME=PATH syntax"
            )
        raw_name, raw_path = value.split("=", 1)
        if not raw_name.strip() or not raw_path.strip():
            raise FreezeProtocolError(
                "artifact path overrides must use NAME=PATH syntax"
            )
        try:
            name = FrozenArtifactName(raw_name)
        except ValueError as exc:
            raise FreezeProtocolError(
                f"unknown freeze artifact override: {raw_name}"
            ) from exc
        if name in overrides:
            raise FreezeProtocolError(
                f"duplicate freeze artifact override: {name.value}"
            )
        overrides[name] = Path(raw_path)
    return overrides


def _required_artifact_name(
    artifact_record: Mapping[str, Any],
    index: int,
) -> FrozenArtifactName:
    name = artifact_record.get("name")
    if not isinstance(name, str):
        raise FreezeProtocolError(
            f"pre-run freeze commitment artifact {index} is missing name"
        )
    try:
        return FrozenArtifactName(name)
    except ValueError as exc:
        raise FreezeProtocolError(
            f"pre-run freeze commitment artifact {index} has unknown name: {name}"
        ) from exc


def _required_sha256_string(
    artifact_record: Mapping[str, Any],
    name: FrozenArtifactName,
) -> str:
    sha256 = artifact_record.get("sha256")
    if not isinstance(sha256, str):
        raise FreezeProtocolError(
            f"pre-run freeze commitment artifact {name.value} is missing sha256"
        )
    _require_sha256(sha256, f"{name.value}.sha256")
    return sha256


def _required_size_bytes(
    artifact_record: Mapping[str, Any],
    name: FrozenArtifactName,
) -> int:
    size_bytes = artifact_record.get("size_bytes")
    if (
        isinstance(size_bytes, bool)
        or not isinstance(size_bytes, int)
        or size_bytes < 0
    ):
        raise FreezeProtocolError(
            f"pre-run freeze commitment artifact {name.value} has invalid size_bytes"
        )
    return size_bytes


def _required_string(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise FreezeProtocolError(f"pre-run freeze commitment missing {field_name}")
    return value


def _optional_sha256_string(record: Mapping[str, Any], field_name: str) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise FreezeProtocolError(f"pre-run freeze commitment has invalid {field_name}")
    try:
        _require_sha256(value, field_name)
    except ValueError as exc:
        raise FreezeProtocolError(
            f"pre-run freeze commitment has invalid {field_name}"
        ) from exc
    return value


def _required_timestamp(record: Mapping[str, Any], field_name: str) -> datetime:
    value = _required_string(record, field_name)
    try:
        return _parse_timestamp(value)
    except ValueError as exc:
        raise FreezeProtocolError(
            f"pre-run freeze commitment has invalid {field_name}"
        ) from exc


def _artifact_sort_key(artifact: FrozenArtifact) -> int:
    try:
        return REQUIRED_FREEZE_ARTIFACTS.index(artifact.name)
    except ValueError:
        return len(REQUIRED_FREEZE_ARTIFACTS)


def _path_for_record(path: Path, *, root_path: Path | None) -> str:
    if root_path is None:
        return str(path)
    try:
        return str(path.relative_to(root_path))
    except ValueError:
        return str(path)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require_aware_datetime(parsed, "timestamp")
    return parsed


def _iso_datetime(value: datetime) -> str:
    _require_aware_datetime(value, "datetime")
    return format_utc_iso_z(value)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_sha256(value: str, field_name: str) -> None:
    if not is_lowercase_sha256(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hash")


if __name__ == "__main__":
    raise SystemExit(cli_freeze(sys.argv[1:]))

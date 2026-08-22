"""Verifier-owned artifact snapshot boundary for manifest freeze inputs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

Snapshot = Callable[[Path, dict[Path, bytes], str], bytes]


def snapshot_verified_artifacts(
    root: Path,
    projection: Mapping[str, Any],
    snapshots: dict[Path, bytes],
    *,
    snapshot: Snapshot,
    error_type: type[ValueError],
) -> Mapping[str, Any]:
    """Hold every verifier-owned root byte stable through publication."""

    raw_verified = projection.get("verified_artifact_bytes")
    if not isinstance(raw_verified, Mapping):
        raise error_type("verified_artifact_bytes must be an object")
    verified: dict[str, Any] = {}
    root_absolute = root.absolute()
    for raw_path, payload in cast(Mapping[object, object], raw_verified).items():
        if (
            not isinstance(raw_path, str)
            or not raw_path
            or not isinstance(payload, bytes)
        ):
            raise error_type(
                f"authenticated successor artifact map is malformed: {root}"
            )
        path = Path(raw_path)
        if not path.is_absolute() or ".." in path.parts:
            raise error_type(
                f"authenticated successor artifact path is unsafe: {raw_path}"
            )
        try:
            path.relative_to(root_absolute)
        except ValueError as exc:
            raise error_type(
                f"authenticated successor artifact is outside its root: {raw_path}"
            ) from exc
        if snapshot(path, snapshots, "authenticated successor artifact") != payload:
            raise error_type(f"authenticated successor bytes changed: {root}")
        verified[raw_path] = payload
    return verified

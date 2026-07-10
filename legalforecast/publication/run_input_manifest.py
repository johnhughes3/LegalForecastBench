"""Freeze late-bound artifacts into an official run-input manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_lowercase_sha256

_CHUNK_SIZE = 1024 * 1024


class RunInputManifestError(ValueError):
    """Raised when a run-input manifest cannot be frozen safely."""


@dataclass(frozen=True, slots=True)
class FrozenRunInputManifest:
    """Result of recording a labels commitment in a run-input manifest."""

    output_path: Path
    labels_sha256: str


def freeze_run_input_labels(
    manifest_path: str | Path,
    *,
    labels_path: str | Path,
    output_path: str | Path,
) -> FrozenRunInputManifest:
    """Record the labels file hash without replacing an existing commitment."""

    source_path = Path(manifest_path)
    labels = Path(labels_path)
    output = Path(output_path)
    if source_path.resolve() == labels.resolve():
        raise RunInputManifestError(
            "run-input manifest and labels must be different files"
        )
    if output.resolve() == labels.resolve():
        raise RunInputManifestError("output path must not overwrite the labels file")
    manifest = _read_manifest(source_path)
    _validate_manifest_shape(manifest)
    labels_sha256 = _sha256_file(labels, label="labels file")

    existing = manifest.get("labels_sha256")
    if existing is not None and existing != "":
        if not isinstance(existing, str) or not is_lowercase_sha256(existing):
            raise RunInputManifestError(
                "existing labels_sha256 must be a lowercase SHA-256 hex digest"
            )
        if existing != labels_sha256:
            raise RunInputManifestError(
                "run-input manifest already commits to different labels; refusing "
                "to replace labels_sha256"
            )

    frozen_manifest = dict(manifest)
    frozen_manifest["labels_sha256"] = labels_sha256
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(frozen_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FrozenRunInputManifest(
        output_path=output,
        labels_sha256=labels_sha256,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit run-input manifest update CLI."""

    parser = argparse.ArgumentParser(
        description="Update late-bound commitments in an official run-input manifest."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_labels = subparsers.add_parser(
        "freeze-labels",
        help="Hash locked labels and emit a run-input manifest that records the hash.",
    )
    freeze_labels.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Existing packet-export run-input manifest to update.",
    )
    freeze_labels.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="Locked labels JSONL whose raw bytes form the commitment.",
    )
    freeze_labels.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination for the hash-bearing run-input manifest.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested manifest update and print its frozen commitment."""

    args = build_parser().parse_args(argv)
    if args.command != "freeze-labels":
        raise RunInputManifestError(f"unsupported manifest operation: {args.command}")
    result = freeze_run_input_labels(
        cast(Path, args.manifest),
        labels_path=cast(Path, args.labels),
        output_path=cast(Path, args.output),
    )
    print(
        json.dumps(
            {
                "labels_sha256": result.labels_sha256,
                "output": str(result.output_path),
            },
            sort_keys=True,
        )
    )
    return 0


def _read_manifest(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise RunInputManifestError(f"run-input manifest does not exist: {path}")
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RunInputManifestError(
            f"run-input manifest is not valid JSON: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise RunInputManifestError("run-input manifest must be a JSON object")
    return cast(Mapping[str, Any], payload)


def _validate_manifest_shape(manifest: Mapping[str, Any]) -> None:
    cycle_id = manifest.get("cycle_id")
    if not isinstance(cycle_id, str) or not cycle_id.strip():
        raise RunInputManifestError("run-input manifest requires cycle_id")
    model_packets = manifest.get("model_packets")
    if not isinstance(model_packets, list):
        raise RunInputManifestError("run-input manifest requires model_packets list")


def _sha256_file(path: Path, *, label: str) -> str:
    if not path.is_file():
        raise RunInputManifestError(f"{label} does not exist: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

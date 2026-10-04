"""Preserve an owner-retained experiment ZIP without treating it as a forecast run."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from zipfile import ZipFile

from legalforecast.artifact_archive import (
    upload_archive_object,
    validate_archive_request,
)
from legalforecast.retained_package import download_draft_asset, readback_archive_object


def validate_experiment_zip(target: Path, digest: str) -> None:
    """Check the selected transfer bytes are an intact ZIP, without extracting them."""
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("experiment ZIP differs from selected SHA256")
    with ZipFile(target) as archive:
        if not archive.infolist() or archive.testzip() is not None:
            raise ValueError("experiment ZIP is empty or corrupt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    parser.add_argument("--experiment", required=True, help="Stable experiment slug")
    parser.add_argument("--sha256", required=True, help="Exact lowercase ZIP SHA256")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--upload-only",
        action="store_true",
        help="Upload validated local bytes without GitHub access",
    )
    args = parser.parse_args()
    validate_archive_request(args.repository, args.bucket, "1-1", 1, 1)
    if (
        args.asset_id <= 0
        or not re.fullmatch(r"[0-9a-f]{64}", args.sha256)
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", args.experiment)
    ):
        raise ValueError(
            "positive asset ID, lowercase SHA256 and safe experiment slug required"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"{args.experiment}.zip"
    if not args.upload_only:
        download_draft_asset(args.repository, args.asset_id, target.name, target)
    validate_experiment_zip(target, args.sha256)
    key = (
        f"reports/retained-experiments/multi-ablation/{args.repository}/"
        f"{args.experiment}/{args.sha256}.zip"
    )
    if args.upload_only:
        upload_archive_object(args.bucket, target, key)
        readback_archive_object(args.bucket, key, target)
    print(f"Validated experiment ZIP: {key}")


if __name__ == "__main__":
    main()

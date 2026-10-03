"""Preserve a complete owner-retained forecast package from a private draft asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import cast

from legalforecast.artifact_archive import (
    extract_artifact,
    json_command,
    metadata_object,
    upload_archive_object,
    validate_archive_request,
    write_archive_index,
)


def package_name(run_id: int, attempt: int) -> str:
    if run_id <= 0 or attempt <= 0:
        raise ValueError("original run and attempt must be positive")
    return f"official-forecast-results-{run_id}-{attempt}"


def retained_pointer_key(repository: str, run_id: int, name: str) -> str:
    prefix = f"reports/github-artifacts/multi-ablation/{repository}/"
    return f"{prefix}retained-by-run/{run_id}/{name}.json"


def validate_package(payload: bytes, run_id: int, attempt: int) -> None:
    """Check original identity and complete, valid receipt membership before storage."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "package"
        extract_artifact(payload, root)
        identity = metadata_object(
            json.loads((root / "forecast-run.json").read_bytes())
        )
        summary = metadata_object(json.loads((root / "run-summary.json").read_bytes()))
        release = metadata_object(
            json.loads((root / "forecast-release.json").read_bytes())
        )
        registry_bytes = (root / "model-registry.json").read_bytes()
        if not isinstance(json.loads(registry_bytes), (list, dict)):
            raise ValueError("retained registry must be a supported JSON container")
        if hashlib.sha256(registry_bytes).hexdigest() != identity.get(
            "model_registry_sha256"
        ):
            raise ValueError("retained registry differs from frozen run identity")
        manifest = metadata_object(
            json.loads((root / "run-manifest.json").read_bytes())
        )
        selected = manifest.get("selected_cases")
        release_units = release.get("prediction_units")
        if not isinstance(selected, list) or not isinstance(release_units, list):
            raise ValueError("retained frozen membership is missing")
        expected_by_case: dict[str, set[str]] = {}
        for raw in cast(list[object], release_units):
            unit = metadata_object(raw)
            case_id, unit_id = unit.get("case_id"), unit.get("unit_id")
            if not isinstance(case_id, str) or not isinstance(unit_id, str):
                raise ValueError("release unit membership is invalid")
            expected_by_case.setdefault(case_id, set()).add(unit_id)
        if {
            metadata_object(row).get("case_id") for row in cast(list[object], selected)
        } != set(expected_by_case):
            raise ValueError("manifest membership differs from forecast release")
        for record in (identity, summary):
            if (
                record.get("workflow_run_id") != run_id
                or record.get("workflow_run_attempt") != attempt
            ):
                raise ValueError("retained package differs from original run/attempt")
        if summary.get("run_identity_sha256") != identity.get("run_identity_sha256"):
            raise ValueError("summary differs from forecast run identity")
        count = release.get("case_count")
        if release.get("release_digest") != identity.get("forecast_release_digest"):
            raise ValueError("forecast release differs from retained run identity")
        if (
            type(count) is not int
            or count <= 0
            or summary.get("status") != "completed"
            or summary.get("completed_cells") != count
            or summary.get("expected_cell_count") != count
        ):
            raise ValueError("retained package is not a complete forecast run")
        units: set[str] = set()
        cases: set[str] = set()
        receipts = list((root / "receipts").glob("*.json"))
        for path in receipts:
            receipt = metadata_object(json.loads(path.read_bytes()))
            case = receipt.get("case_id")
            if (
                not isinstance(case, str)
                or case in cases
                or receipt.get("model_key") != identity.get("model_key")
                or receipt.get("forecast_release_digest")
                != identity.get("forecast_release_digest")
                or receipt.get("run_identity_sha256")
                != identity.get("run_identity_sha256")
                or receipt.get("model_registry_sha256")
                != identity.get("model_registry_sha256")
            ):
                raise ValueError("receipt membership differs from retained run")
            cases.add(case)
            parser = metadata_object(receipt.get("parser_output"))
            required = parser.get("required_unit_ids")
            predictions = parser.get("predictions")
            if (
                parser.get("is_valid") is not True
                or parser.get("invalid_output") is not False
                or parser.get("defaulted_unit_ids") != []
                or not isinstance(required, list)
                or not isinstance(predictions, list)
            ):
                raise ValueError("retained prediction is invalid or incomplete")
            required = cast(list[str], required)
            if (
                set(required) != expected_by_case.get(case)
                or receipt.get("required_unit_ids") != required
            ):
                raise ValueError("receipt units differ from original case membership")
            predicted: list[str] = []
            for item in cast(list[object], predictions):
                prediction = metadata_object(item)
                if (
                    prediction.get("defaulted") is not False
                    or prediction.get("invalid_reason") is not None
                ):
                    raise ValueError("retained prediction is defaulted or invalid")
                probability = prediction.get("probability_fully_dismissed")
                if (
                    type(probability) not in (int, float)
                    or not math.isfinite(cast(float, probability))
                    or not 0 <= cast(float, probability) <= 1
                ):
                    raise ValueError("retained prediction probability is invalid")
                unit_id = prediction.get("unit_id")
                if not isinstance(unit_id, str):
                    raise ValueError("prediction unit ID must be a string")
                predicted.append(unit_id)
            if (
                len(predicted) != len(set(predicted))
                or set(predicted) != set(required)
                or units.intersection(required)
            ):
                raise ValueError("retained prediction unit membership is incomplete")
            units.update(required)
        if len(cases) != count or len(units) != release.get("unit_count"):
            raise ValueError("retained receipt census differs from forecast release")
        release_units = release.get("prediction_units")
        release_cases = release.get("cases")
        if not isinstance(release_units, list) or not isinstance(release_cases, list):
            raise ValueError("forecast release membership is missing")
        if units != {
            metadata_object(row).get("unit_id")
            for row in cast(list[object], release_units)
        } or cases != {
            metadata_object(row).get("case_id")
            for row in cast(list[object], release_cases)
        }:
            raise ValueError(
                "retained receipt membership differs from forecast release"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--asset-id", required=True, type=int)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--source-run-id", required=True, type=int)
    parser.add_argument("--source-attempt", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--upload-only", action="store_true")
    args = parser.parse_args()
    validate_archive_request(args.repository, args.bucket, "1-1", 1, args.source_run_id)
    name = package_name(args.source_run_id, args.source_attempt)
    if args.asset_id <= 0 or not re.fullmatch(r"[0-9a-f]{64}", args.sha256):
        raise ValueError("positive draft asset ID and SHA256 are required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / "retained-package.zip"
    if not args.upload_only:
        asset = metadata_object(
            json_command(
                [
                    "gh",
                    "api",
                    f"repos/{args.repository}/releases/assets/{args.asset_id}",
                ]
            )
        )
        releases = json_command(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{args.repository}/releases?per_page=100",
            ]
        )
        if not isinstance(releases, list):
            raise ValueError("release listing is invalid")
        drafts: list[dict[str, object]] = []
        for page in cast(list[object], releases):
            if not isinstance(page, list):
                raise ValueError("release page must be an array")
            for raw in cast(list[object], page):
                release = metadata_object(raw)
                assets = release.get("assets")
                if not isinstance(assets, list):
                    raise ValueError("release assets must be an array")
                if release.get("draft") is True and any(
                    metadata_object(item).get("id") == args.asset_id
                    for item in cast(list[object], assets)
                ):
                    drafts.append(release)
        if (
            len(drafts) != 1
            or asset.get("id") != args.asset_id
            or asset.get("name") != f"{name}.zip"
        ):
            raise ValueError("package must belong to one unpublished draft release")
        result = subprocess.run(
            [
                "gh",
                "api",
                "--allow-escape-sequences",
                "-H",
                "Accept: application/octet-stream",
                f"repos/{args.repository}/releases/assets/{args.asset_id}",
            ],
            check=True,
            capture_output=True,
        )
        target.write_bytes(result.stdout)
    payload = target.read_bytes()
    if hashlib.sha256(payload).hexdigest() != args.sha256:
        raise ValueError("retained package digest differs from selected asset")
    validate_package(payload, args.source_run_id, args.source_attempt)
    prefix = f"reports/github-artifacts/multi-ablation/{args.repository}/"
    key = f"{prefix}retained-packages/{args.sha256}.zip"
    pointer: dict[str, object] = {
        "source_type": "retained_draft_release_asset",
        "repository": args.repository,
        "source_run_id": args.source_run_id,
        "source_attempt": args.source_attempt,
        "name": name,
        "release_asset_id": args.asset_id,
        "digest": f"sha256:{args.sha256}",
        "key": key,
    }
    write_archive_index(args.output_dir / "retained-package-pointer.json", pointer)
    if args.upload_only:
        upload_archive_object(args.bucket, target, key)
        _readback(args.bucket, key, target)
        upload_archive_object(
            args.bucket,
            args.output_dir / "retained-package-pointer.json",
            retained_pointer_key(args.repository, args.source_run_id, name),
        )
        _readback(
            args.bucket,
            retained_pointer_key(args.repository, args.source_run_id, name),
            args.output_dir / "retained-package-pointer.json",
        )


def _readback(bucket: str, key: str, original: Path) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        downloaded = Path(scratch) / "readback"
        subprocess.run(
            [
                "aws",
                "s3api",
                "get-object",
                "--bucket",
                bucket,
                "--key",
                key,
                str(downloaded),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        if downloaded.read_bytes() != original.read_bytes():
            raise ValueError("retained archive readback differs from uploaded bytes")


if __name__ == "__main__":
    main()

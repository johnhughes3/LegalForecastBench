"""Prepare deterministic inputs for the source-tree release smoke."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from legalforecast.release import (
    BenchmarkRunManifest,
    DocumentRole,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    SelectedCase,
    serialize_run_manifest,
)


def fixture_manifest() -> BenchmarkRunManifest:
    """Return the manifest bound into the deterministic three-case fixture."""

    return BenchmarkRunManifest(
        run_id=UUID("12345678-1234-5678-1234-567812345678"),
        selected_cases=tuple(
            SelectedCase(
                case_id=case_id,
                provider_id="corpus-store",
                qc_status=QCStatus.ACCEPTED,
                role_locators=tuple(
                    RoleObjectLocator(
                        role=role,
                        locator=OpaqueObjectLocator(
                            provider_id="object-store",
                            object_locator=f"cases/{case_id}/{role.value}",
                            version_id=f"version-{case_id}-{role.value}",
                        ),
                    )
                    for role in (
                        DocumentRole.DECISION,
                        DocumentRole.MOTION,
                        DocumentRole.COMPLAINT,
                    )
                ),
                opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
            )
            for case_id in ("case-001", "case-002", "case-003")
        ),
        policy_version="federal-mtd-v1",
        code_revision="a" * 40,
        created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        locked_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    )


def write_fixture_manifest(path: Path) -> None:
    """Write the canonical fixture manifest to a new or identical path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_run_manifest(fixture_manifest())
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(
                f"fixture manifest already exists with different bytes: {path}"
            )
        return
    path.write_bytes(payload)


def collect_receipts(receipts_dir: Path, output_path: Path) -> None:
    """Combine public receipt JSON objects into the scorer's JSONL input."""

    receipt_paths = tuple(sorted(receipts_dir.glob("*.json")))
    if not receipt_paths:
        raise ValueError(f"no public run receipts found in {receipts_dir}")
    records: list[str] = []
    for receipt_path in receipt_paths:
        record = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"run receipt is not a JSON object: {receipt_path}")
        records.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(records) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one release-smoke input preparation operation."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    manifest = commands.add_parser("manifest", help="write the fixture run manifest")
    manifest.add_argument("--output", type=Path, required=True)
    receipts = commands.add_parser(
        "collect-receipts",
        help="combine a receipt directory into scorer JSONL input",
    )
    receipts.add_argument("--receipts-dir", type=Path, required=True)
    receipts.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "manifest":
        write_fixture_manifest(args.output)
    else:
        collect_receipts(args.receipts_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

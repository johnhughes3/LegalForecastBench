"""CLI for the one-document free support-memorandum augmentation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.free_document_downloader import UrlLibFreeDocumentSource
from legalforecast.ingestion.free_support_memorandum_executor import (
    FreeSupportMemorandumExecutorError,
    execute_free_support_memorandum_source_augmentation,
    verify_free_support_memorandum_source_augmentation,
)
from legalforecast.ingestion.free_support_memorandum_recovery import (
    FreeSupportMemorandumRecoveryError,
    verify_free_support_memorandum_recovery_plan,
)


class FreeSupportMemorandumExecutorCliError(ValueError):
    """Raised when the bounded CLI cannot safely publish its package."""


def add_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "recover-free-support-memorandum",
        help=(
            "Download only the authenticated ECF 14 public support memorandum and "
            "emit its additive source-augmentation package."
        ),
    )
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--bridge-descriptor", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Run only the fixed HTTPS public-document recovery."""

    return _run_with_dependencies(
        selection_path=cast(Path, args.selection),
        plan_path=cast(Path, args.plan),
        bridge_descriptor_path=cast(Path, args.bridge_descriptor),
        output_root=cast(Path, args.output_root),
        resume=bool(args.resume),
        source=None,
    )


def _run_with_test_dependencies(  # pyright: ignore[reportUnusedFunction]
    *,
    selection_path: Path,
    plan_path: Path,
    bridge_descriptor_path: Path,
    output_root: Path,
    source: UrlLibFreeDocumentSource | Any,
    resume: bool = True,
) -> int:
    """Exercise the private output seam with an offline source in tests."""

    return _run_with_dependencies(
        selection_path=selection_path,
        plan_path=plan_path,
        bridge_descriptor_path=bridge_descriptor_path,
        output_root=output_root,
        resume=resume,
        source=source,
    )


def _run_with_dependencies(
    *,
    selection_path: Path,
    plan_path: Path,
    bridge_descriptor_path: Path,
    output_root: Path,
    resume: bool,
    source: UrlLibFreeDocumentSource | Any | None,
) -> int:
    selection = _read(selection_path)
    plan_bytes = _read(plan_path)
    immutable_inputs = (selection_path, plan_path, bridge_descriptor_path)
    if any(_overlaps(output_root, path) for path in immutable_inputs):
        raise FreeSupportMemorandumExecutorCliError(
            "support memorandum output overlaps an immutable input"
        )
    if output_root.exists() and any(output_root.iterdir()):
        try:
            verify_free_support_memorandum_source_augmentation(
                persisted_plan_bytes=plan_bytes,
                bridge_descriptor_path=bridge_descriptor_path,
                corrected_selection_bytes=selection,
                output_root=output_root,
            )
        except FreeSupportMemorandumExecutorError as exc:
            raise FreeSupportMemorandumExecutorCliError(
                "support memorandum output is partial or invalid"
            ) from exc
        if not resume:
            raise FreeSupportMemorandumExecutorCliError(
                "support memorandum output already exists and resume is disabled"
            )
        _print_result(output_root, resumed=True)
        return 0
    try:
        verified_plan = verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_descriptor_path,
        )
    except FreeSupportMemorandumRecoveryError as exc:
        raise FreeSupportMemorandumExecutorCliError(
            "support memorandum plan is not authenticated"
        ) from exc
    document_source = source or UrlLibFreeDocumentSource(
        final_url_validator=lambda final_url: _require_exact_final_url(
            final_url, expected=str(verified_plan.record["source_url"])
        )
    )
    try:
        result = execute_free_support_memorandum_source_augmentation(
            persisted_plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_descriptor_path,
            corrected_selection_bytes=selection,
            output_root=output_root,
            source=document_source,
        )
    except FreeSupportMemorandumExecutorError as exc:
        raise FreeSupportMemorandumExecutorCliError(str(exc)) from exc
    _write(output_root / "free-document-request.json", result.request_bytes)
    _write(output_root / "free-document-download.json", result.download_bytes)
    _write(output_root / "disclosure-clearance.json", result.clearance_bytes)
    _write(output_root / "source-augmentation.json", result.projection_bytes)
    try:
        verify_free_support_memorandum_source_augmentation(
            persisted_plan_bytes=plan_bytes,
            bridge_descriptor_path=bridge_descriptor_path,
            corrected_selection_bytes=selection,
            output_root=output_root,
        )
    except FreeSupportMemorandumExecutorError as exc:
        raise FreeSupportMemorandumExecutorCliError(
            "saved support memorandum package did not replay"
        ) from exc
    _print_result(output_root, resumed=False)
    return 0


def _require_exact_final_url(url: str, *, expected: str) -> None:
    if url != expected:
        raise FreeSupportMemorandumExecutorCliError(
            "support memorandum redirect differs from the plan-derived URL"
        )


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise FreeSupportMemorandumExecutorCliError(f"missing regular file: {path}")
    return path.read_bytes()


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise FreeSupportMemorandumExecutorCliError(
            f"support memorandum artifact already exists: {path.name}"
        ) from exc
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        raise


def _overlaps(first: Path, second: Path) -> bool:
    first_absolute = first.absolute()
    second_absolute = second.absolute()
    return (
        first_absolute == second_absolute
        or first_absolute in second_absolute.parents
        or second_absolute in first_absolute.parents
    )


def _print_result(output_root: Path, *, resumed: bool) -> None:
    print(
        json.dumps(
            {
                "output_root": str(output_root),
                "resumed": resumed,
                "paid_activity_executed": False,
                "pacer_activity_executed": False,
                "recap_fetch_activity_executed": False,
                "provider_activity_executed": False,
                "evaluation_permitted": False,
                "freeze_permitted": False,
                "dispatch_permitted": False,
            },
            sort_keys=True,
        )
    )

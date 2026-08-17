"""Adapter for the attachment-menu (RECAP Fetch request type 3) command."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import write_json_object

# Loaded lazily, like the Stage A replay adapter, so the console layer keeps no
# static import edge into the ingestion package.
_EXECUTOR = importlib.metadata.EntryPoint(
    name="recap-attachment-page-fetch",
    value=(
        "legalforecast.ingestion.recap_attachment_page_fetch:"
        "execute_attachment_page_fetch_run"
    ),
    group="legalforecast.internal",
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],  # pyright: ignore[reportPrivateUsage]
) -> None:
    """Register the attachment-menu acquisition command."""

    parser = subparsers.add_parser(
        "fetch-recap-attachment-pages",
        help="Buy missing PACER attachment menus and resolve their selectors.",
        description=(
            "Fetch the PACER attachment menu for each named parent RECAP "
            "document exactly once through the direct CourtListener RECAP "
            "Fetch lane (request type 3), journal every dispatch, then read "
            "the free listing view to report the attachment-level selectors "
            "the menu created. Halts before any dispatch that would carry "
            "committed reservations past --max-total-usd, and skips menus "
            "CourtListener has already ingested."
        ),
    )
    parser.add_argument(
        "--recap-document",
        action="append",
        required=True,
        dest="recap_documents",
        metavar="ID",
        help=(
            "Parent RECAP document ID whose docket entry's attachment menu is "
            "missing. Repeat once per menu."
        ),
    )
    parser.add_argument(
        "--journal",
        type=Path,
        required=True,
        help="Crash-durable SQLite journal enforcing one POST per menu.",
    )
    parser.add_argument(
        "--cycle-id",
        required=True,
        help="Cycle identifier committed into every canonical submission body.",
    )
    parser.add_argument(
        "--authorization-sha256",
        required=True,
        help=(
            "SHA-256 of the owner authorization governing this spend; it is "
            "committed into each submission and into the receipt."
        ),
    )
    parser.add_argument(
        "--max-total-usd",
        required=True,
        help=(
            "Aggregate ceiling for this journal's reservations. The run halts "
            "before any dispatch that would exceed it."
        ),
    )
    parser.add_argument(
        "--reservation-usd",
        default="0.30",
        help="Worst-case reservation recorded per menu; default 0.30.",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="Optional path for the run receipt; the record also prints to stdout.",
    )
    parser.add_argument(
        "--poll-attempts",
        type=int,
        default=6,
        help="Queue-detail reads per menu before reporting it still queued.",
    )
    parser.add_argument(
        "--poll-backoff-seconds",
        type=float,
        default=5.0,
        help="Wait between queue-detail reads; default 5.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Required acknowledgment that this command dispatches paid POSTs.",
    )
    parser.add_argument(
        "--acknowledge-pacer-fees",
        action="store_true",
        help="Acknowledge that each fetched menu incurs PACER page fees.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Execute the attachment-menu lane behind an explicit fee acknowledgment."""

    if not args.live or not args.acknowledge_pacer_fees:
        raise SystemExit(
            "fetch-recap-attachment-pages requires --live and "
            "--acknowledge-pacer-fees: every menu is a PACER charge"
        )
    execute = cast(Callable[..., dict[str, Any]], _EXECUTOR.load())
    record = execute(
        recap_documents=cast(Sequence[str], args.recap_documents),
        journal_path=cast(Path, args.journal),
        cycle_id=cast(str, args.cycle_id),
        authorization_sha256=cast(str, args.authorization_sha256),
        max_total_usd=cast(str, args.max_total_usd),
        reservation_usd=cast(str, args.reservation_usd),
        poll_attempts=cast(int, args.poll_attempts),
        poll_backoff_seconds=cast(float, args.poll_backoff_seconds),
    )
    record["recorded_at_utc"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt_path = cast(Path | None, args.receipt)
    if receipt_path is not None:
        write_json_object(receipt_path, record)
    print(json.dumps(record, sort_keys=True))
    return 2 if record["halted"] else 0

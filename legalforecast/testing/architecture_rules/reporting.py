"""CLI reporting and ranked work-queue presentation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from legalforecast.testing.architecture_rules.baseline import (
    check_baseline,
    write_baseline,
)
from legalforecast.testing.architecture_rules.inventory import (
    BASELINE_PATH,
    WATCH_LINE_THRESHOLD,
    FileInventoryRecord,
    RepositoryInventory,
    scan_repository,
)


def ranked_queue(inventory: RepositoryInventory) -> tuple[FileInventoryRecord, ...]:
    """Rank inventoried files by size, symbol span, churn, degree, and risk."""

    return tuple(
        sorted(
            (
                record
                for record in inventory.files
                if record.line_count >= WATCH_LINE_THRESHOLD or record.flags
            ),
            key=lambda record: (
                -record.line_count,
                -record.largest_symbol_lines,
                -record.churn_90d,
                -(record.fan_in + record.fan_out),
                0 if record.cycle_id else 1,
                0 if "authenticated-path" in record.flags else 1,
                record.path,
            ),
        )
    )


def format_ranked_queue(inventory: RepositoryInventory) -> str:
    """Return a deterministic ranked-queue report."""

    lines = [
        "path\tlines\tsymbol_lines\tchurn_90d\tdegree\tlane\tkind\tflags",
    ]
    for record in ranked_queue(inventory):
        flags = ",".join(record.flags) if record.flags else "-"
        lines.append(
            "\t".join(
                (
                    record.path,
                    str(record.line_count),
                    str(record.largest_symbol_lines),
                    str(record.churn_90d),
                    str(record.fan_in + record.fan_out),
                    record.lane_owner,
                    record.disposition_kind,
                    flags,
                )
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the architecture ratchet from a shell or CI."""

    parser = argparse.ArgumentParser(
        description="Repository architecture and CLI-sprawl ratchets."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument(
        "--rank",
        action="store_true",
        help="Print the ranked oversized-file work queue and exit.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline
    if args.write_baseline:
        write_baseline(baseline, scan_repository(root))
        print(f"wrote architecture baseline to {baseline}")
        return 0
    if args.rank:
        sys.stdout.write(format_ranked_queue(scan_repository(root)))
        return 0
    violations = check_baseline(root, baseline)
    if violations:
        print("architecture ratchet found new violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    try:
        reported_baseline = baseline.relative_to(root)
    except ValueError:
        reported_baseline = baseline
    print(f"architecture ratchet passed: {reported_baseline}")
    return 0

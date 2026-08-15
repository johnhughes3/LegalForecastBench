"""CLI for generating the reviewed characterization corpus."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from legalforecast.testing.cli_corpus.command_manifest import build_command_manifest
from legalforecast.testing.cli_corpus.differential import write_differential_fixtures
from legalforecast.testing.cli_corpus.help_snapshots import write_help_snapshots
from legalforecast.testing.cli_corpus.path_identity import scan_path_identity
from legalforecast.testing.cli_corpus.paths import (
    IDENTITY_PATH,
    MANIFEST_PATH,
    TIMING_PATH,
    dump_json,
)
from legalforecast.testing.cli_corpus.xdist_timing import (
    parse_collect_only,
    parse_duration_lines,
    timing_payload,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Write selected corpus artifacts under the repository root."""

    parser = argparse.ArgumentParser(
        description="Generate CLI differential, path-identity, and timing corpora."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--write-help", action="store_true")
    parser.add_argument("--write-identity", action="store_true")
    parser.add_argument("--write-differential", action="store_true")
    parser.add_argument("--write-timing", action="store_true")
    parser.add_argument("--durations-file", type=Path)
    parser.add_argument("--collect-only-file", type=Path)
    parser.add_argument("--write-all", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    root = args.root.resolve()
    write_all = bool(args.write_all)
    if args.write_manifest or write_all:
        dump_json(root / MANIFEST_PATH, build_command_manifest())
    if args.write_help or write_all:
        write_help_snapshots(root)
    if args.write_identity or write_all:
        dump_json(root / IDENTITY_PATH, scan_path_identity(root))
    if args.write_differential or write_all:
        with TemporaryDirectory(prefix="legalforecast-cli-corpus-") as workspace:
            write_differential_fixtures(root, Path(workspace))
    if args.write_timing or write_all:
        dump_json(
            root / TIMING_PATH,
            _timing_from_suite(root, args.durations_file, args.collect_only_file),
        )
    return 0


def _timing_from_suite(
    root: Path,
    durations_file: Path | None,
    collect_only_file: Path | None,
) -> dict[str, object]:
    if collect_only_file is not None:
        collect_text = collect_only_file.read_text(encoding="utf-8")
    else:
        collected = subprocess.run(
            ["uv", "run", "pytest", "--collect-only", "-q", "--dist=no"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if collected.returncode != 0:
            raise RuntimeError(collected.stderr or collected.stdout)
        collect_text = collected.stdout
    durations = None
    if durations_file is not None:
        durations, _counts = parse_duration_lines(
            durations_file.read_text(encoding="utf-8")
        )
    return timing_payload(
        test_counts=parse_collect_only(collect_text),
        durations=durations,
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""Pinned-width CLI invocation used by help snapshots and differential cases."""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass

from legalforecast.testing.cli_corpus.paths import PINNED_COLUMNS


@dataclass(frozen=True, slots=True)
class CliCapture:
    """Captured process-shaped result of one in-process CLI invocation."""

    exit_status: int
    stdout: str
    stderr: str


def invoke_cli(
    argv: Sequence[str],
    *,
    columns: int = PINNED_COLUMNS,
) -> CliCapture:
    """Run ``legalforecast.cli.main`` with a pinned ``COLUMNS`` width.

    ``freeze`` and ``publish aggregate`` keep their pre-parser bypasses because
    this calls ``main`` rather than ``build_parser().parse_args``.
    """

    previous = os.environ.get("COLUMNS")
    previous_argv = list(sys.argv)
    main_module = sys.modules.get("__main__")
    previous_spec = getattr(main_module, "__spec__", None)
    os.environ["COLUMNS"] = str(columns)
    if sys.argv:
        sys.argv[0] = "legalforecast"
    else:
        sys.argv.append("legalforecast")
    if main_module is not None:
        main_module.__spec__ = None
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                from legalforecast.cli import main

                raw_status = main(list(argv))
            except SystemExit as exc:
                raw_status = exc.code
        return CliCapture(
            exit_status=_exit_status(raw_status),
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )
    finally:
        if main_module is not None:
            main_module.__spec__ = previous_spec
        sys.argv[:] = previous_argv
        if previous is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = previous


def _exit_status(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        return 1
    return value

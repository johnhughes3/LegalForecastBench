"""Pinned-width CLI invocation used by help snapshots and differential cases."""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
from collections.abc import Callable, Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass

from legalforecast.testing.cli_corpus.paths import PINNED_COLUMNS

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_CHOOSE_FROM = re.compile(r"\(choose from ([^)]*)\)")
_PINNED_ENV = ("COLUMNS", "LINES", "NO_COLOR", "PYTHON_COLORS")


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

    This calls ``main`` rather than ``build_parser().parse_args`` so the
    capture includes the same parser and error handling as the installed CLI.
    """

    previous_env = {name: os.environ.get(name) for name in _PINNED_ENV}
    previous_argv = list(sys.argv)
    previous_size = shutil.get_terminal_size
    main_module = sys.modules.get("__main__")
    previous_spec = getattr(main_module, "__spec__", None)
    os.environ["COLUMNS"] = str(columns)
    os.environ["LINES"] = "24"
    os.environ["NO_COLOR"] = "1"
    os.environ["PYTHON_COLORS"] = "0"
    shutil.get_terminal_size = _pinned_terminal_size(columns)
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
            stdout=_normalize_captured_text(stdout.getvalue()),
            stderr=_normalize_captured_text(stderr.getvalue()),
        )
    finally:
        shutil.get_terminal_size = previous_size
        if main_module is not None:
            main_module.__spec__ = previous_spec
        sys.argv[:] = previous_argv
        _restore_env(previous_env)


def _pinned_terminal_size(
    columns: int,
) -> Callable[..., os.terminal_size]:
    def get_terminal_size(fallback: tuple[int, int] = (80, 24)) -> os.terminal_size:
        del fallback
        return os.terminal_size((columns, 24))

    return get_terminal_size


def _restore_env(previous: dict[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _normalize_captured_text(text: str) -> str:
    return _normalize_argparse_choose_from(_strip_ansi(text))


def _normalize_argparse_choose_from(text: str) -> str:
    def _unquote(match: re.Match[str]) -> str:
        inner = match.group(1).replace("'", "")
        return f"(choose from {inner})"

    return _CHOOSE_FROM.sub(_unquote, text)


def _exit_status(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        return 1
    return value

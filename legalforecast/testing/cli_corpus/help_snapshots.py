"""Byte-stable help snapshots at a pinned terminal width."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from legalforecast.testing.cli_corpus.invoke import invoke_cli
from legalforecast.testing.cli_corpus.paths import HELP_DIR, PINNED_COLUMNS

HELP_SNAPSHOTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("root", ("--help",)),
    ("freeze", ("freeze", "--help")),
    ("publish-aggregate", ("publish", "aggregate", "--help")),
    ("acquisition", ("acquisition", "--help")),
    ("batch-002", ("batch-002", "--help")),
    ("discover", ("discover", "--help")),
    ("eval", ("eval", "--help")),
    ("multiharness", ("multiharness", "--help")),
)


def capture_help(
    argv: Sequence[str],
    *,
    columns: int = PINNED_COLUMNS,
) -> str:
    """Return stdout for a help invocation, requiring a successful exit."""

    captured = invoke_cli(argv, columns=columns)
    if captured.exit_status != 0:
        raise RuntimeError(
            f"help {list(argv)!r} exited {captured.exit_status}: {captured.stderr}"
        )
    return captured.stdout


def help_payload() -> dict[str, str]:
    """Capture every reviewed help family at the pinned width."""

    return {name: capture_help(argv) for name, argv in HELP_SNAPSHOTS}


def write_help_snapshots(root: Path, payload: dict[str, str] | None = None) -> None:
    """Write pinned-width help fixtures under ``HELP_DIR``."""

    snapshots = payload if payload is not None else help_payload()
    directory = root / HELP_DIR
    directory.mkdir(parents=True, exist_ok=True)
    expected = {f"{name}.txt" for name in snapshots}
    for name, text in snapshots.items():
        (directory / f"{name}.txt").write_text(text, encoding="utf-8")
    for stale in directory.glob("*.txt"):
        if stale.name not in expected:
            stale.unlink()


def load_help_snapshots(root: Path) -> dict[str, str]:
    """Load checked-in help fixtures."""

    directory = root / HELP_DIR
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(directory.glob("*.txt"))
    }

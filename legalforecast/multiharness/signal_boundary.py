"""Signal handling for interruptible multi-harness setup and execution."""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

from legalforecast.multiharness.command_adapter import CommandAdapterCancelled
from legalforecast.multiharness.run_progress import (
    RunProgressJournal,
    load_progress_journal,
    write_progress_journal,
)

JournalOwner = tuple[Path, RunProgressJournal]


@contextmanager
def signal_boundary(
    journal_owner: JournalOwner | None = None,
) -> Generator[Callable[[], bool]]:
    """Convert termination signals and finalize only an adopted journal."""

    requested = {"value": False}
    if threading.current_thread() is not threading.main_thread():
        yield lambda: requested["value"]
        return

    previous = {
        requested_signal: signal.getsignal(requested_signal)
        for requested_signal in (signal.SIGINT, signal.SIGTERM)
    }

    def mark_stop(requested_signal: int, frame: object) -> None:
        del requested_signal, frame
        requested["value"] = True
        raise KeyboardInterrupt

    for requested_signal in previous:
        signal.signal(requested_signal, mark_stop)
    try:
        yield lambda: requested["value"]
    except (CommandAdapterCancelled, KeyboardInterrupt):
        _mark_owned_journal_stopped(journal_owner)
        raise CommandAdapterCancelled("multi-harness startup was cancelled") from None
    finally:
        for requested_signal, previous_handler in previous.items():
            signal.signal(requested_signal, previous_handler)


def _mark_owned_journal_stopped(journal_owner: JournalOwner | None) -> None:
    if journal_owner is None:
        return
    output_dir, owned = journal_owner
    current = load_progress_journal(output_dir)
    if current is None:
        return
    if current.run_id == owned.run_id and current.identity == owned.identity:
        write_progress_journal(output_dir, current.mark_stopped())

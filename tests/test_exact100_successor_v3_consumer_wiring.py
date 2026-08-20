"""The production call site that reads a v3 cohort root downstream.

The verifier this wires to takes its authentication as an injected hook, and a
receipt-shaped return is something a stub can construct. So the guarantee that
a real replay happens cannot live in the verifier -- anything it checks locally
a stub computes locally too. It lives here, in what the call site binds.

These tests therefore spy on the real replay entry point itself. A wiring that
passed a stub, or that skipped authentication, would leave the spy uncalled.

Fixtures are synthetic; no corpus candidate, document or path appears here.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.ingestion.exact100_successor_v3.downstream import (
    AuthenticatedV3Root,
)
from tests.test_exact100_successor_v3_downstream import _v3_root


def _spy(seen: list[Path]) -> Any:
    """Stand in for the real replay while recording that IT was the one called."""

    def authenticate(target: Path, **_kwargs: object) -> AuthenticatedV3Root:
        seen.append(target)
        return AuthenticatedV3Root(root=target)

    return authenticate


def _operation() -> Any:
    return cli._VerifiedProjectionOperation(
        owner_thread_id=threading.get_ident(), cache={}, byte_closures={}
    )


def test_reading_a_v3_root_invokes_the_real_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The call site must bind the replay, not merely something receipt-shaped.

    Spying on the replay entry point is the only check a stub cannot satisfy:
    it asserts which callable ran, not what it returned.
    """

    root = _v3_root(tmp_path)
    replayed: list[Path] = []
    monkeypatch.setattr(
        cli,
        "authenticate_exact100_successor_v3_root",
        _spy(replayed),
    )

    result = cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=_operation()
    )

    assert replayed == [root]
    assert result["selection_path"] == root / "target-cohort-selection.jsonl"


def test_a_v3_root_is_recognised_before_the_missing_target_cohort_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A v3 root has no target-cohort run card at all.

    Without the probe the read of that card fails on the missing file, before
    any schema dispatch is reached -- so this is what makes a v3 root readable
    downstream rather than a dispatch arm.
    """

    root = _v3_root(tmp_path)
    monkeypatch.setattr(
        cli,
        "authenticate_exact100_successor_v3_root",
        lambda target, **_: AuthenticatedV3Root(root=target),
    )

    assert not (root / "run-cards/project-target-cohort.json").exists()
    assert cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=_operation()
    )


def test_a_failing_replay_stops_the_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Authentication failure must not be swallowed into a published result."""

    root = _v3_root(tmp_path)

    def refuse(_target: Path, **_kwargs: object) -> None:
        raise ValueError("v3 predecessor output differs from its replay")

    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", refuse)

    with pytest.raises(ValueError, match="differs from its replay"):
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=_operation()
        )


def test_the_verified_result_is_memoized_per_run_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replay is expensive enough that repeating it per read is not viable.

    Memoizing on the run-card digest keeps a re-minted root from ever being
    answered out of a stale entry.
    """

    root = _v3_root(tmp_path)
    replayed: list[Path] = []
    monkeypatch.setattr(
        cli,
        "authenticate_exact100_successor_v3_root",
        _spy(replayed),
    )
    operation = _operation()

    cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=operation
    )
    cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=operation
    )

    assert replayed == [root]


def test_a_rewritten_run_card_is_not_answered_from_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-minted root at the same path is a different root.

    Keying only on the path would hand back the previous root's verified result
    for bytes nothing replayed -- the memoization quietly becoming a bypass.

    The snapshot re-check would also catch it, so this is belt-and-braces; the
    observable property is that a changed card re-authenticates rather than
    resolving out of the cache at all.
    """

    root = _v3_root(tmp_path)
    replayed: list[Path] = []
    monkeypatch.setattr(
        cli,
        "authenticate_exact100_successor_v3_root",
        _spy(replayed),
    )
    operation = _operation()

    cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=operation
    )
    card = root / "run-cards/project-exact100-successor-replacement-v3.json"
    card.write_bytes(card.read_bytes().replace(b'"status"', b'"status" '))

    cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=operation
    )

    # Re-authenticated rather than answered from the previous root's entry.
    assert replayed == [root, root]

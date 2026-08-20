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


def test_a_cache_hit_still_covers_the_promoted_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hit path must not check less than the miss path.

    The miss path commitment-checks every promoted document. If the cached
    reread covers only the cohort surface files, a document swapped between two
    reads inside one operation is accepted on the second -- the narrow
    intra-operation window this reread exists to close.
    """

    root = _v3_root(tmp_path)
    replayed: list[Path] = []
    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", _spy(replayed))
    operation = _operation()
    cli._verify_completed_target_cohort_projection_in_operation(
        root, operation=operation
    )

    document = root / "owner-adjudicated-source/documents/case001/doc-1.pdf"
    document.write_bytes(b"%PDF-1.7 substituted\n")

    with pytest.raises(cli.CommandError, match="changed"):
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )


def test_the_read_joins_the_operation_byte_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every sibling branch feeds the operation-wide closure; so must this one.

    The closure is what makes two reads of the same path inside one operation
    have to agree. A branch that stays out of it is invisible to that check.
    """

    root = _v3_root(tmp_path)
    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", _spy([]))
    closure: dict[str, bytes] = {}
    token = cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.set(closure)
    try:
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=_operation()
        )
    finally:
        cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.reset(token)

    assert any(path.endswith("target-cohort-selection.jsonl") for path in closure)
    assert any(path.endswith("doc-1.pdf") for path in closure), (
        "promoted documents must join the closure, not only the surface files"
    )


def test_a_conflicting_byte_in_the_closure_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Joining the closure is only useful if a disagreement actually raises."""

    root = _v3_root(tmp_path)
    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", _spy([]))
    selection = root / "target-cohort-selection.jsonl"
    closure = {str(selection.absolute()): b"a different earlier reading\n"}
    token = cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.set(closure)
    try:
        with pytest.raises(cli.CommandError, match="closure conflicts"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=_operation()
            )
    finally:
        cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.reset(token)


def test_a_conflicting_document_byte_in_the_closure_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A disagreement on a promoted DOCUMENT must raise, not just on a surface file.

    Seeding a surface file proves the branch joins the closure at all, but it
    passes even with the documents left out of the snapshot set -- so it cannot
    tell whether the promoted evidence is subject to the coherence check. This
    seeds the document path instead, which is the assertion the surface-file
    version cannot make.
    """

    root = _v3_root(tmp_path)
    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", _spy([]))
    document = root / "owner-adjudicated-source/documents/case001/doc-1.pdf"
    closure = {str(document.absolute()): b"%PDF-1.7 a different reading\n"}
    token = cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.set(closure)
    try:
        with pytest.raises(cli.CommandError, match="closure conflicts"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=_operation()
            )
    finally:
        cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.reset(token)


def test_a_v3_root_declares_no_required_absences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing has to be missing for a v3 root, so the absence set is empty.

    An absence records a negative fact a projection depends on. A v3 root's
    contract is entirely positive -- every path its card commits must exist and
    match -- so an empty set here is the measured answer rather than a gap.
    """

    root = _v3_root(tmp_path)
    monkeypatch.setattr(cli, "authenticate_exact100_successor_v3_root", _spy([]))
    absences: set[str] = set()
    token = cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.set(absences)
    try:
        result = cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=_operation()
        )
    finally:
        cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.reset(token)

    assert absences == set()
    assert "verified_artifact_absences" not in result

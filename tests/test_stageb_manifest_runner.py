"""Focused authority checks for the additive Stage B manifest runner."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from types import SimpleNamespace

import pytest
from legalforecast.evals import stageb_manifest_runner as runner


def _comment(
    comment_id: str, text: str, *, author: str = "John Hughes"
) -> dict[str, str]:
    return {"id": comment_id, "author": author, "text": text}


def _beads_comments(
    spend_comments: Sequence[dict[str, str]],
    terminal_comments: Sequence[dict[str, str]],
) -> Callable[..., SimpleNamespace]:
    comments_by_bead = {
        runner.BEAD_ID: spend_comments,
        runner.TERMINAL_APPROVAL_BEAD_ID: terminal_comments,
    }

    def fake_run(args: Sequence[str], **_: object) -> SimpleNamespace:
        bead_id = args[2]
        return SimpleNamespace(stdout=json.dumps(comments_by_bead[bead_id]))

    return fake_run


def test_owner_approval_ids_require_exact_real_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spend = _comment("spend-id", runner.SPEND_APPROVAL)
    terminal = _comment("terminal-id", runner.TERMINAL_PACKET_APPROVAL)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend], [terminal]),
    )

    assert set(
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]
    ) == {"spend-id", "terminal-id"}


def test_owner_approval_ids_reject_near_match_terminal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spend = _comment("spend-id", runner.SPEND_APPROVAL)
    near_match = _comment(
        "near-match",
        "stage51-terminal-units: approved - packet "
        "8617ee835c3578042a1081f484d6520de187c5da8367e1e6a71228262266dcca",
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend], [near_match]),
    )

    with pytest.raises(
        runner.StageBManifestError, match="terminal-unit packet approval"
    ):
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]


def test_owner_approval_ids_reject_terminal_comment_on_spend_bead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spend = _comment("spend-id", runner.SPEND_APPROVAL)
    terminal = _comment("terminal-id", runner.TERMINAL_PACKET_APPROVAL)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        _beads_comments([spend, terminal], []),
    )

    with pytest.raises(
        runner.StageBManifestError, match="terminal-unit packet approval"
    ):
        runner._owner_approval_ids()  # pyright: ignore[reportPrivateUsage]

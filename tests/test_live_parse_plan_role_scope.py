# pyright: reportPrivateUsage=false
"""Where the live role requirement reads each document's authenticated role.

``tests/test_live_parse_plan_role_gate.py`` covers the relabelling attack the
role binding exists for.  This file covers the *source* of the authenticated
role, because one class of row does not state it in the manifest at all.

A materialization manifest merges free downloads with purchased RECAP-fetch
quarantine-recovery rows, and the recovery schema has no ``document_role``
field, so those rows arrive with none.  Requiring one of them refused every
executed non-fixture run over the whole root — including the pure reuse runs the
parse-quality regap executes inside — which is the outage this file exists to
keep fixed.

Their role is not missing, though: the authenticated target cohort selection
states it for the same ``(candidate_id, source_document_id)``, and the selection
travels in the same replay-verified lineage as the manifest.  So the live path
sources the role from the selection for exactly those rows, and every document
keeps the role-aware threshold it is entitled to.  Treating them as role-less
instead would hand 169 pleading and brief documents per root the permissive
unknown-role floor, and their Markdown reaches a Stage A LLM with no further
parse-quality gate.

A document with no role in *either* artifact still refuses, and a plan row that
asserts a role no artifact stated is still refused.
"""

from __future__ import annotations

from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
)
from pytest import CaptureFixture, MonkeyPatch
from tests.test_live_parse_plan_role_gate import (
    _QUARANTINE_SIGNATURE,
    _SELECTION_FILENAME,
    _CompanionDocument,
    _parse_documents_argv,
    _parse_plan_fixture,
    _ParserReached,
    _plan_record,
    _prior_live_mistral_run,
    _refused_live_parse_plan,
    _reuse_key,
)


def _quarantine_companion(**overrides: object) -> _CompanionDocument:
    """A purchased RECAP-fetch row: full signature, no manifest role."""

    fields: dict[str, object] = {
        "source_document_id": "recap-fetch-doc",
        "plan_role": None,
        "manifest_role": None,
        "parser_eligible": False,
        "quarantine_signature": True,
        "selection_role": "motion_to_dismiss_memorandum",
    }
    fields.update(overrides)
    return _CompanionDocument(**fields)  # pyright: ignore[reportArgumentType]


def test_quarantine_row_without_a_manifest_role_binds_the_selection_role(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The run proceeds, and the row keeps its real role — not ``None``.

    This is the whole fix in one assertion.  Before it, the role-less row
    refused the entire run.  A tempting cheaper repair — exempting the row from
    the requirement — would also let the run proceed, which is why the assertion
    is on the *role* the request carries and not merely on reaching the parser:
    ``None`` would silently drop this document from the 200-character pleading
    floor to the 1-character unknown-role floor.
    """

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch,
        tmp_path,
        document_role="complaint",
        companion=_quarantine_companion(),
    )
    parsed: list[tuple[MistralMarkdownConversionRequest, ...]] = []

    def _capture_parser_call(
        requests: tuple[MistralMarkdownConversionRequest, ...],
        *,
        config: object,
    ) -> tuple[object, ...]:
        del config
        parsed.append(tuple(requests))
        raise _ParserReached("captured live parser invocation")

    monkeypatch.setattr(cli, "convert_documents_to_markdown", _capture_parser_call)

    with pytest.raises(_ParserReached):
        cli.main(
            _parse_documents_argv(
                requests_path=requests_path,
                clearance_path=clearance_path,
                materialization_card=materialization_card,
                output_root=tmp_path / "acquisition",
                selection_path=tmp_path / _SELECTION_FILENAME,
            )
        )

    batch = [request for requests in parsed for request in requests]
    assert [request.source_document_id for request in batch] == [
        "complaint",
        "recap-fetch-doc",
    ]
    assert [request.document_role for request in batch] == [
        "complaint",
        "motion_to_dismiss_memorandum",
    ]


def test_quarantine_row_absent_from_the_selection_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """No role in the manifest and none in the selection is the genuine gap."""

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        companion=_quarantine_companion(selection_role=None),
    )

    assert (
        "authenticated materialization manifest record requires "
        "document_role: cand-1/recap-fetch-doc"
    ) in stderr


def test_partial_quarantine_signature_cannot_redirect_the_role_lookup(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """``parser_eligible: false`` alone does not license a selection lookup.

    Two of the three recovery lanes never constrain ``parser_eligible``, so a
    row carrying only that marker is not known to be a quarantine-recovery row.
    It must refuse rather than sourcing a role from a different artifact — even
    though the selection here does state one.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_role=None,
        authenticated_parser_eligible=False,
        authenticated_selection_role="order",
    )

    assert (
        "authenticated materialization manifest record requires "
        "document_role: cand-1/complaint"
    ) in stderr


def test_parser_eligible_manifest_row_without_a_role_is_still_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """A row the lineage says the parser *does* measure must state its role."""

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_role=None,
        authenticated_parser_eligible=True,
        authenticated_selection_role="order",
    )

    assert (
        "authenticated materialization manifest record requires "
        "document_role: cand-1/complaint"
    ) in stderr


def test_quarantine_row_manifest_role_still_wins_over_the_selection(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """The selection is consulted only where the manifest states nothing.

    Real roots contain documents whose manifest and selection roles differ
    (both within one threshold class), so preferring the manifest keeps the
    binding these runs already had rather than re-opening it to a second source.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        companion=_quarantine_companion(
            plan_role="order",
            manifest_role="complaint",
            selection_role="motion_to_dismiss_memorandum",
        ),
    )

    assert (
        "live parse plan document_role differs from the authenticated "
        "materialization manifest: cand-1/recap-fetch-doc: order != complaint"
    ) in stderr


def test_plan_role_contradicting_a_selection_sourced_role_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """A selection-sourced role binds the plan exactly like a manifest one.

    The parse plan states no role for these rows, so it is not required to carry
    one — but a plan that supplies a contradicting role is choosing its own
    threshold, which is the relabelling attack arriving through the one row
    class whose plan field is legitimately absent.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        companion=_quarantine_companion(plan_role="order"),
    )

    assert (
        "live parse plan document_role differs from the authenticated "
        "materialization manifest: cand-1/recap-fetch-doc: "
        "order != motion_to_dismiss_memorandum"
    ) in stderr


def test_mistral_markdown_request_prefers_the_authenticated_role() -> None:
    """A plan row with no role of its own still carries the lineage's role."""

    record = {
        key: value for key, value in _plan_record().items() if key != "document_role"
    }
    request = cli._mistral_markdown_request(
        record,
        output_root=Path("/tmp/output"),
        authenticated_document_role="motion_to_dismiss_memorandum",
    )

    assert request.document_role == "motion_to_dismiss_memorandum"


# Comfortably over the 1-character unknown-role floor and comfortably under the
# 200-character pleading floor.  This is the shape of a real production row
# (candidate 71194192, document 463345690: a purchased quarantine-recovery
# motion-to-dismiss memorandum with 67 substantive characters), and it is the
# case that separates "the selection role is bound" from "the row was let
# through".
_THIN_MEMORANDUM_MARKDOWN = (
    "# Memorandum\n\nDefendant moves to dismiss the amended complaint.\n"
)


def test_selection_sourced_role_still_regaps_thin_markdown(
    tmp_path: Path,
) -> None:
    """Binding the real role is what keeps the pleading floor doing its work.

    Under the unknown-role floor this Markdown is accepted and flows onward to
    Stage A.  Under the ``motion_to_dismiss_memorandum`` floor the selection
    authenticates, it is superseded and re-converted by the pinned parser, which
    is the outcome the corpus needs.
    """

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_THIN_MEMORANDUM_MARKDOWN
    )
    bound = cli._mistral_markdown_request(
        {
            "candidate_id": request.candidate_id,
            "source_document_id": request.source_document_id,
            "input_path": str(request.input_path),
            "expected_sha256": request.expected_sha256,
            "expected_byte_count": request.expected_byte_count,
            "markdown_output_path": str(request.markdown_output_path),
        },
        output_root=tmp_path / "successor",
        authenticated_document_role="motion_to_dismiss_memorandum",
    )

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=prior_card,
        prior_markdown_root=prior_root,
        requests=(bound,),
        output_root=tmp_path / "successor",
    )

    assert plan.superseded_keys == frozenset({_reuse_key(bound)})
    assert [gap.source_document_id for gap in plan.gaps] == ["complaint"]
    assert dict(plan.records_by_key) == {}
    # The frozen artifact is never mutated.
    assert (
        prior_root.joinpath("cand-1", "complaint.md").read_text(encoding="utf-8")
        == _THIN_MEMORANDUM_MARKDOWN
    )


def test_conflicting_manifest_roles_are_refused() -> None:
    """Two manifest rows for one document may not disagree about its role."""

    manifest = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "document_role": "complaint",
        },
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "document_role": "order",
        },
    ]

    with pytest.raises(
        cli.CommandError,
        match=(
            "authenticated materialization manifest has conflicting "
            "document_role: cand-1/complaint"
        ),
    ):
        cli._authenticated_live_parse_document_roles(manifest, selection_records=[])


def test_conflicting_selection_roles_are_refused() -> None:
    """The selection is a role source, so it fails closed on disagreement too."""

    selection = [
        {
            "candidate_id": "cand-1",
            "documents": [
                {"source_document_id": "doc-1", "document_role": "complaint"},
                {"source_document_id": "doc-1", "document_role": "order"},
            ],
        }
    ]
    manifest = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "doc-1",
            **_QUARANTINE_SIGNATURE,
        }
    ]

    with pytest.raises(
        cli.CommandError,
        match=(
            "authenticated target selection has conflicting document_role: cand-1/doc-1"
        ),
    ):
        cli._authenticated_live_parse_document_roles(
            manifest, selection_records=selection
        )

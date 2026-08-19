# pyright: reportPrivateUsage=false
"""The live role requirement is scoped to the rows the parser measures.

``tests/test_live_parse_plan_role_gate.py`` covers the relabelling attack the
role binding exists for.  This file covers the *scope* of the requirement: a
materialization manifest also carries rows it marks ``parser_eligible: false``
— the purchased RECAP-fetch quarantine-recovery documents, which are
``packet_eligible: false`` too — and those rows state no ``document_role``
anywhere upstream, because the recovery schema has no such field.

Requiring one of them refused every executed non-fixture run over the whole
materialization root, including the pure reuse runs the parse-quality regap
executes inside, so the requirement now follows what the authenticated manifest
actually says.  The exemption is not forgeable: the downstream lineage verifier
re-derives ``document-downloads-merged.jsonl`` from the upstream recovery
sources, and the recovery validators require ``parser_eligible: false`` on
quarantine rows and ``parser_eligible: true`` on resolved post-recovery rows.

The binding itself is untouched: an exempt row that does state a role still
binds to it, a role-less row that is *not* exempt is still refused, and a plan
that asserts a role the manifest never stated is refused as the same attack
arriving from the other direction.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
)
from pytest import CaptureFixture, MonkeyPatch
from tests.test_live_parse_plan_role_gate import (
    _WEAK_MARKDOWN,
    _CompanionDocument,
    _parse_documents_argv,
    _parse_plan_fixture,
    _ParserReached,
    _plan_record,
    _prior_live_mistral_run,
    _refused_live_parse_plan,
    _reuse_key,
)


def test_parser_ineligible_manifest_row_without_a_role_reaches_the_parser(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A manifest row marked ``parser_eligible: false`` states no role at all.

    The purchased RECAP-fetch quarantine-recovery rows carry no
    ``document_role`` anywhere upstream, so requiring one refused every executed
    run over the whole materialization root — including the pure reuse runs the
    parse-quality regap executes inside.  The requirement is therefore scoped to
    the rows the authenticated manifest says the parser measures; the
    role-bearing row beside it still binds.
    """

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch,
        tmp_path,
        document_role="complaint",
        companion=_CompanionDocument(
            source_document_id="recap-fetch-doc",
            plan_role=None,
            manifest_role=None,
            parser_eligible=False,
        ),
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
            )
        )

    batch = [request for requests in parsed for request in requests]
    assert [request.source_document_id for request in batch] == [
        "complaint",
        "recap-fetch-doc",
    ]
    assert [request.document_role for request in batch] == ["complaint", None]
    # The exemption is carried on the request itself so the reuse and
    # supersession gates can tell it apart from an unauthenticated role-less row.
    assert [request.parser_role_exempt for request in batch] == [False, True]


def test_parser_eligible_manifest_row_without_a_role_is_still_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Only ``parser_eligible: false`` exempts — never a truthy or absent flag.

    ``parser_eligible: true`` is what the resolved post-recovery validator
    requires of every row the parser *does* measure, so a role-less row carrying
    it is an unauthenticated role, not an exemption.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_role=None,
        authenticated_parser_eligible=True,
    )

    assert (
        "authenticated materialization manifest record requires "
        "document_role: cand-1/complaint"
    ) in stderr


def test_parser_ineligible_manifest_row_that_states_a_role_still_binds(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """The exemption scopes the role *requirement*, never the role *binding*."""

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        companion=_CompanionDocument(
            source_document_id="recap-fetch-doc",
            plan_role="order",
            manifest_role="complaint",
            parser_eligible=False,
        ),
    )

    assert (
        "live parse plan document_role differs from the authenticated "
        "materialization manifest: cand-1/recap-fetch-doc: order != complaint"
    ) in stderr


def test_plan_role_for_a_parser_ineligible_manifest_row_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Relabelling from the other direction: a role nothing authenticated.

    An exempt manifest row states no role, so a plan row that supplies one is
    choosing its own quality threshold exactly as a contradicting role does.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_role=None,
        authenticated_parser_eligible=False,
    )

    assert (
        "live parse plan asserts a document_role the authenticated "
        "materialization manifest does not state: cand-1/complaint: complaint"
    ) in stderr


def test_mistral_markdown_request_exempts_a_parser_ineligible_row() -> None:
    """The strict live default still yields for an authenticated exemption."""

    record = {
        key: value for key, value in _plan_record().items() if key != "document_role"
    }
    request = cli._mistral_markdown_request(
        record,
        output_root=Path("/tmp/output"),
        parser_role_exempt=True,
    )

    assert request.document_role is None
    assert request.parser_role_exempt is True


def test_reuse_gate_accepts_a_parser_exempt_request_without_a_role(
    tmp_path: Path,
) -> None:
    """An authenticated exemption reuses under the unknown-role floor.

    ``_WEAK_MARKDOWN`` fails the 200-character pleading threshold, so this also
    proves the exemption changes *which* floor applies rather than skipping the
    gate: the row still passes ``assess_parsed_text``, just under the same
    unknown-role floor the pinned parser converted it under.
    """

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_WEAK_MARKDOWN
    )
    exempt = replace(request, document_role=None, parser_role_exempt=True)

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=prior_card,
        prior_markdown_root=prior_root,
        requests=(exempt,),
        output_root=tmp_path / "successor",
    )

    assert plan.gaps == ()
    assert plan.superseded_keys == frozenset()
    assert list(plan.records_by_key) == [_reuse_key(exempt)]
    assert exempt.markdown_output_path.read_text(encoding="utf-8") == _WEAK_MARKDOWN


# Only ECF page stamps survived this conversion: `_CASE_PAGE_HEADER_RE` and
# `_PAGE_MARKER_RE` classify every line as boilerplate, leaving zero substantive
# characters.  It is the exact shape of the real defect this lane exists to
# reach (candidate 71942225, document 459533978: 1,922 bytes, 0 substantive
# characters), and it is rejected at *every* floor including the unknown-role
# one, whose minimum is 1 character and 1 line.
_ECF_STAMP_ONLY_MARKDOWN = (
    "##### Page 1\n\n"
    "Case 2:25-cv-02154-DCF Document 3 Filed 11/20/25 Page 1 of 21 PageID #: 154\n\n"
    "##### Page 2\n\n"
    "Case 2:25-cv-02154-DCF Document 3 Filed 11/20/25 Page 2 of 21 PageID #: 155\n"
)


def test_parser_exempt_reused_markdown_with_no_substantive_text_is_regapped(
    tmp_path: Path,
) -> None:
    """The exemption lowers the floor; it never removes the floor.

    Without this, an implementation that returned early for every exempt request
    — never calling ``assess_parsed_text`` at all — would satisfy every other
    test here, because the Markdown they reuse clears the unknown-role floor
    anyway.  A body-less conversion must still be superseded and re-parsed, or
    the scoping would quietly convert a real corpus-completeness finding into a
    silent acceptance for 174 rows per root.
    """

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_ECF_STAMP_ONLY_MARKDOWN
    )
    exempt = replace(request, document_role=None, parser_role_exempt=True)

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=prior_card,
        prior_markdown_root=prior_root,
        requests=(exempt,),
        output_root=tmp_path / "successor",
    )

    assert plan.superseded_keys == frozenset({_reuse_key(exempt)})
    assert [gap.source_document_id for gap in plan.gaps] == ["complaint"]
    assert dict(plan.records_by_key) == {}
    # The frozen artifact is never mutated, and nothing is published for it.
    assert not exempt.markdown_output_path.exists()
    assert (
        prior_root.joinpath("cand-1", "complaint.md").read_text(encoding="utf-8")
        == _ECF_STAMP_ONLY_MARKDOWN
    )


def test_conflicting_manifest_roles_are_refused_across_an_exemption(
    tmp_path: Path,
) -> None:
    """Two manifest rows for one document may not disagree about its role.

    The exempt arm maps a row to ``None``, so a duplicate key where one row is
    exempt and the other states a role must still refuse rather than letting
    whichever row is read last decide the threshold.
    """

    del tmp_path
    manifest = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "parser_eligible": False,
        },
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "document_role": "complaint",
        },
    ]

    with pytest.raises(
        cli.CommandError,
        match=(
            "authenticated materialization manifest has conflicting "
            "document_role: cand-1/complaint"
        ),
    ):
        cli._authenticated_live_parse_document_roles(manifest)

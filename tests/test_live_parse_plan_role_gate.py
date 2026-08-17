# pyright: reportPrivateUsage=false
"""Live parse plans must carry an *authenticated* ``document_role``.

``assess_parsed_text`` falls back to a permissive one-character/one-line floor
when the document role is unknown.  A legacy or hand-crafted parse-plan record
that omits ``document_role`` would therefore buy a weaker quality gate than
every authenticated row beside it, so the live parse path refuses the row at
the record-reading boundary instead of parsing it under the fallback.

Presence alone is not enough.  The parse plan is an ordinary file between
planning and parsing, so a materialized ``complaint`` can be relabelled as an
``order`` to trade the 200-character pleading floor for the 120-character
outcome floor.  The live path therefore binds every planned role to the role
the materialization manifest authenticated for that exact identity, and
reruns the same quality gate over reused Markdown so reuse cannot become a
cheaper route to a weaker threshold.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
)
from pytest import CaptureFixture, MonkeyPatch
from tests.test_acquisition_cli import (
    _materialized_cli_unit_fixture,
    _read_jsonl,
    _write_jsonl,
)

JsonRecord = dict[str, Any]
_GENERATED_AT = "2026-05-17T12:00:00Z"


class _ParserReached(Exception):
    """Sentinel that escapes ``main``'s CommandError/ValueError/OSError guards."""


def _parse_plan_fixture(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    *,
    document_role: str | None,
    authenticated_role: str | None = "complaint",
    authenticated_document_id: str = "complaint",
) -> tuple[Path, Path, Path]:
    """Build the smallest executable ``parse-documents`` invocation inputs.

    ``authenticated_role`` and ``authenticated_document_id`` describe the
    materialization manifest row the plan is measured against, so a test can
    contradict the plan (a relabelled role) or withhold the row entirely.
    """

    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fixture")
    digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    byte_count = source_pdf.stat().st_size

    request: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "input_path": str(source_pdf),
        "expected_sha256": digest,
        "expected_byte_count": byte_count,
    }
    if document_role is not None:
        request["document_role"] = document_role
    requests_path = tmp_path / "parse-requests.jsonl"
    _write_jsonl(requests_path, [request])

    clearance_path = tmp_path / "parse-clearance.jsonl"
    _write_jsonl(
        clearance_path,
        [
            {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "sha256": digest,
                "byte_count": byte_count,
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["controlled fixture review"],
                "reviewer_id": "fixture-reviewer",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": _GENERATED_AT,
            }
        ],
    )
    _, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path, skip_packet_planner_replay=True
    )
    # ``_materialized_cli_unit_fixture`` writes an empty placeholder manifest and
    # replays it as the verified lineage, so this is the authenticated statement
    # of each materialized document's role.
    manifest_record: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": authenticated_document_id,
        "sha256": digest,
        "byte_count": byte_count,
    }
    if authenticated_role is not None:
        manifest_record["document_role"] = authenticated_role
    _write_jsonl(tmp_path / "materialized-manifest.jsonl", [manifest_record])
    return requests_path, clearance_path, materialization_card


def _parse_documents_argv(
    *,
    requests_path: Path,
    clearance_path: Path,
    materialization_card: Path,
    output_root: Path,
    fixture_markdown_dir: Path | None = None,
) -> list[str]:
    argv = [
        "acquisition",
        "parse-documents",
        "--requests",
        str(requests_path),
        "--disclosure-clearance",
        str(clearance_path),
        "--materialization-run-card",
        str(materialization_card),
        "--output-root",
        str(output_root),
        "--execute",
    ]
    if fixture_markdown_dir is not None:
        argv.extend(["--fixture-markdown-dir", str(fixture_markdown_dir)])
    return argv


def test_live_parse_plan_without_document_role_never_reaches_the_parser(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """A role-less live plan row fails closed before any conversion happens."""

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch, tmp_path, document_role=None
    )
    parsed: list[tuple[MistralMarkdownConversionRequest, ...]] = []

    def _record_parser_call(
        requests: tuple[MistralMarkdownConversionRequest, ...],
        *,
        config: object,
    ) -> tuple[object, ...]:
        del config
        parsed.append(tuple(requests))
        raise _ParserReached("live parser must not run for a role-less plan")

    monkeypatch.setattr(cli, "convert_documents_to_markdown", _record_parser_call)
    output_root = tmp_path / "acquisition"

    assert (
        cli.main(
            _parse_documents_argv(
                requests_path=requests_path,
                clearance_path=clearance_path,
                materialization_card=materialization_card,
                output_root=output_root,
            )
        )
        == 2
    )

    # Exit code 2 alone is ambiguous, so pin the specific guard and prove the
    # parser was never invoked with an unassessable role.
    assert (
        "live parse plan record requires document_role: cand-1/complaint"
        in capsys.readouterr().err
    )
    assert parsed == []
    assert not (output_root / "mistral-markdown-conversions.jsonl").exists()


def test_live_parse_plan_with_document_role_reaches_the_parser(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The guard is scoped to the missing role, not to live parsing itself."""

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch, tmp_path, document_role="complaint"
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

    assert [request.document_role for batch in parsed for request in batch] == [
        "complaint"
    ]


def _refused_live_parse_plan(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    **fixture_kwargs: object,
) -> str:
    """Run one live plan expected to fail closed and return the stderr text."""

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch,
        tmp_path,
        **cast(Any, fixture_kwargs),
    )
    parsed: list[tuple[MistralMarkdownConversionRequest, ...]] = []

    def _record_parser_call(
        requests: tuple[MistralMarkdownConversionRequest, ...],
        *,
        config: object,
    ) -> tuple[object, ...]:
        del config
        parsed.append(tuple(requests))
        raise _ParserReached("live parser must not run for an unauthenticated role")

    monkeypatch.setattr(cli, "convert_documents_to_markdown", _record_parser_call)
    output_root = tmp_path / "acquisition"

    assert (
        cli.main(
            _parse_documents_argv(
                requests_path=requests_path,
                clearance_path=clearance_path,
                materialization_card=materialization_card,
                output_root=output_root,
            )
        )
        == 2
    )
    assert parsed == []
    assert not (output_root / "mistral-markdown-conversions.jsonl").exists()
    return capsys.readouterr().err


def test_hand_edited_plan_role_that_contradicts_the_manifest_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Relabelling a materialized complaint as an order buys no weaker gate.

    ``order`` carries the 120-character outcome floor instead of the
    200-character pleading floor, so accepting the edit would let the plan
    choose its own quality threshold.
    """

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="order",
        authenticated_role="complaint",
    )

    assert (
        "live parse plan document_role differs from the authenticated "
        "materialization manifest: cand-1/complaint: order != complaint"
    ) in stderr


def test_live_plan_row_absent_from_the_authenticated_manifest_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """A plan row with no manifest row has no authenticated role to match."""

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_document_id="some-other-document",
    )

    assert (
        "live parse plan record is absent from the authenticated "
        "materialization manifest: cand-1/complaint"
    ) in stderr


def test_manifest_row_without_a_document_role_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """An unauthenticated role cannot be laundered through a matching plan."""

    stderr = _refused_live_parse_plan(
        tmp_path,
        monkeypatch,
        capsys,
        document_role="complaint",
        authenticated_role=None,
    )

    assert (
        "authenticated materialization manifest record requires "
        "document_role: cand-1/complaint"
    ) in stderr


def test_fixture_markdown_parse_still_accepts_a_role_less_plan(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Fixture conversions never consult role thresholds, so they stay open."""

    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch, tmp_path, document_role=None
    )
    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "complaint.md").write_text(
        "Complaint markdown", encoding="utf-8"
    )
    output_root = tmp_path / "acquisition"

    assert (
        cli.main(
            _parse_documents_argv(
                requests_path=requests_path,
                clearance_path=clearance_path,
                materialization_card=materialization_card,
                output_root=output_root,
                fixture_markdown_dir=fixture_markdown,
            )
        )
        == 0
    )

    conversions = _read_jsonl(output_root / "mistral-markdown-conversions.jsonl")
    assert [conversion["status"] for conversion in conversions] == ["succeeded"]


def _plan_record(**overrides: object) -> JsonRecord:
    record: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "input_path": "/documents/complaint.pdf",
        "expected_sha256": "0" * 64,
        "expected_byte_count": 12,
        "document_role": "complaint",
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(
            {
                key: value
                for key, value in _plan_record().items()
                if key != "document_role"
            },
            id="absent",
        ),
        pytest.param(_plan_record(document_role=""), id="empty"),
        pytest.param(_plan_record(document_role="   "), id="blank"),
        pytest.param(_plan_record(document_role=None), id="null"),
    ],
)
def test_mistral_markdown_request_fails_closed_on_unusable_role(
    tmp_path: Path, record: JsonRecord
) -> None:
    """The strict default refuses every shape that assesses as ``role=None``."""

    with pytest.raises(cli.CommandError, match="requires document_role"):
        cli._mistral_markdown_request(record, output_root=tmp_path / "output")


def test_mistral_markdown_request_opt_out_preserves_the_optional_role() -> None:
    """Non-live callers keep the historical optional-role behaviour."""

    record = {
        key: value for key, value in _plan_record().items() if key != "document_role"
    }
    request = cli._mistral_markdown_request(
        record,
        output_root=Path("/tmp/output"),
        require_document_role=False,
    )

    assert request.document_role is None


def test_mistral_markdown_request_carries_a_present_role() -> None:
    request = cli._mistral_markdown_request(
        _plan_record(document_role="motion_to_dismiss_memorandum"),
        output_root=Path("/tmp/output"),
    )

    assert request.document_role == "motion_to_dismiss_memorandum"


_COMPLAINT_MARKDOWN = (
    "# Complaint\n\n"
    "Plaintiff alleges that the defendant breached the parties' written supply "
    "agreement by refusing to deliver the goods it had promised, and seeks "
    "damages, interest, and costs for the resulting losses.\n\n"
    "Plaintiff further alleges that the defendant acted in bad faith throughout "
    "the negotiations that followed the breach.\n"
)
_WEAK_MARKDOWN = "# Complaint\n\nExact historical Markdown.\n"


def _prior_live_mistral_run(
    tmp_path: Path, *, markdown: str
) -> tuple[Path, Path, MistralMarkdownConversionRequest]:
    """Author one authenticated prior live-Mistral parse plus its reuse request."""

    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fixture")
    digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    byte_count = source_pdf.stat().st_size

    prior_root = tmp_path / "prior-markdown"
    prior_markdown = prior_root / "cand-1" / "complaint.md"
    prior_markdown.parent.mkdir(parents=True)
    prior_markdown.write_text(markdown, encoding="utf-8")

    prior_requests_path = tmp_path / "prior-requests.jsonl"
    _write_jsonl(
        prior_requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "document_role": "complaint",
                "input_path": str(source_pdf),
                "expected_sha256": digest,
                "expected_byte_count": byte_count,
            }
        ],
    )
    conversion: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "status": "succeeded",
        "input_path": str(source_pdf),
        "markdown_path": "cand-1/complaint.md",
        "metadata_path": "cand-1/complaint.metadata.json",
        "parser_config": {
            "engine": "mistral",
            "parser_root": str(tmp_path / "parser"),
            "parser_revision": cli.EXPECTED_PARSER_REVISION,
            "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
            "timeout_seconds": 600,
            "debug": False,
            "command": [
                "uv",
                "run",
                "parser-pdf",
                "--file",
                str(source_pdf),
                "--mistral",
                "--no-ocr",
            ],
        },
        "quality_flags": [],
        "extracted_text": {
            "source_document_id": "complaint",
            "extracted_at": _GENERATED_AT,
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
            "quality_flags": [],
        },
        "source_sha256": digest,
        "source_byte_count": byte_count,
        "stdout": "",
        "stderr": "",
        "error_message": None,
    }
    prior_markdown.with_suffix(".metadata.json").write_text(
        json.dumps(conversion, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    prior_manifest_path = tmp_path / "prior-conversions.jsonl"
    _write_jsonl(prior_manifest_path, [conversion])
    prior_card_path = tmp_path / "prior-parse.json"
    prior_card_path.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "parse-documents",
                "status": "completed",
                "dry_run": False,
                "execute": True,
                "record_count": 1,
                "source_commitments": {
                    "requests": {
                        "path": str(prior_requests_path.resolve()),
                        "sha256": cli._bytes_sha256(prior_requests_path.read_bytes()),
                    }
                },
                "output_commitments": {
                    "parser_manifest": {
                        "path": str(prior_manifest_path.resolve()),
                        "sha256": cli._bytes_sha256(prior_manifest_path.read_bytes()),
                    }
                },
                "parser_execution": {
                    "mode": "live_mistral",
                    "engine": "mistral",
                    "parser_revision": cli.EXPECTED_PARSER_REVISION,
                    "parser_root": str(tmp_path / "parser"),
                    "fixture_markdown": False,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request = MistralMarkdownConversionRequest(
        candidate_id="cand-1",
        source_document_id="complaint",
        input_path=source_pdf,
        markdown_output_path=(
            tmp_path / "successor" / "markdown" / "cand-1" / "complaint.md"
        ),
        expected_sha256=digest,
        expected_byte_count=byte_count,
        document_role="complaint",
    )
    return prior_card_path, prior_root, request


def test_reused_markdown_below_the_current_role_threshold_is_refused(
    tmp_path: Path,
) -> None:
    """Reuse re-enters the quality gate under the authenticated current role.

    The prior run's byte, hash, and provenance commitments say nothing about
    which role measured the Markdown, so authenticated-but-thin Markdown must
    not become a cheaper route past the pleading threshold.
    """

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_WEAK_MARKDOWN
    )
    output_root = tmp_path / "successor"

    with pytest.raises(
        cli.CommandError,
        match=(
            "reused live-Mistral Markdown failed the current parse-quality "
            "gate: cand-1/complaint: insufficient_substantive_characters, "
            "insufficient_substantive_lines"
        ),
    ):
        cli._reuse_live_mistral_parse_outputs(
            prior_run_card_path=prior_card,
            prior_markdown_root=prior_root,
            requests=(request,),
            output_root=output_root,
        )

    assert not request.markdown_output_path.exists()


def test_reused_markdown_meeting_the_current_role_threshold_is_copied(
    tmp_path: Path,
) -> None:
    """The reuse gate is scoped to weak Markdown, not to reuse itself."""

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_COMPLAINT_MARKDOWN
    )
    output_root = tmp_path / "successor"

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=prior_card,
        prior_markdown_root=prior_root,
        requests=(request,),
        output_root=output_root,
    )

    assert plan.gaps == ()
    assert len(plan.records_by_key) == 1
    assert request.markdown_output_path.read_text(encoding="utf-8") == (
        _COMPLAINT_MARKDOWN
    )


def test_reuse_gate_refuses_a_request_without_an_authenticated_role(
    tmp_path: Path,
) -> None:
    """A role-less reuse request has no threshold, so it never reuses."""

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_COMPLAINT_MARKDOWN
    )
    role_less = replace(request, document_role=None)

    with pytest.raises(
        cli.CommandError,
        match="reused live-Mistral Markdown requires document_role: cand-1/complaint",
    ):
        cli._reuse_live_mistral_parse_outputs(
            prior_run_card_path=prior_card,
            prior_markdown_root=prior_root,
            requests=(role_less,),
            output_root=tmp_path / "successor",
        )

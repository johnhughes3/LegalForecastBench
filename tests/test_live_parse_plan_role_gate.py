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
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.mistral_markdown_parser import (
    MistralMarkdownConversionRequest,
)
from legalforecast.ingestion.parse_quality import PARSE_QUALITY_REJECTION_FLAG
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


@dataclass(frozen=True)
class _CompanionDocument:
    """A second plan document, described independently of the first.

    A real materialization root's manifest is *mixed*: role-bearing rows the
    parser will measure sit beside purchased RECAP-fetch rows the manifest marks
    ``parser_eligible: false``, which state no role anywhere upstream (bead
    ``legalforecastbench-d5ml`` records the measured distribution).  A one-row
    fixture cannot express that, so tests that care about the mixture add the
    second document here.
    """

    source_document_id: str
    plan_role: str | None
    manifest_role: str | None
    parser_eligible: bool | None = None


def _clearance_record(
    *, source_document_id: str, digest: str, byte_count: int
) -> JsonRecord:
    return {
        "schema_version": "legalforecast.disclosure_clearance.v1",
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "sha256": digest,
        "byte_count": byte_count,
        "status": "cleared",
        "restriction_status": "public",
        "restriction_evidence": ["controlled fixture review"],
        "reviewer_id": "fixture-reviewer",
        "controlled_store_provenance": "private-store://fixture/reviews",
        "reviewed_at": _GENERATED_AT,
    }


def _parse_plan_fixture(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    *,
    document_role: str | None,
    authenticated_role: str | None = "complaint",
    authenticated_document_id: str = "complaint",
    authenticated_parser_eligible: bool | None = None,
    companion: _CompanionDocument | None = None,
) -> tuple[Path, Path, Path]:
    """Build the smallest executable ``parse-documents`` invocation inputs.

    ``authenticated_role`` and ``authenticated_document_id`` describe the
    materialization manifest row the plan is measured against, so a test can
    contradict the plan (a relabelled role) or withhold the row entirely.
    ``authenticated_parser_eligible`` writes the manifest's own
    ``parser_eligible`` flag, which is what decides whether a role-less row is
    authenticated as outside the parser's reach or merely unauthenticated.
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
    manifest_record: JsonRecord = {
        "candidate_id": "cand-1",
        "source_document_id": authenticated_document_id,
        "sha256": digest,
        "byte_count": byte_count,
    }
    if authenticated_role is not None:
        manifest_record["document_role"] = authenticated_role
    if authenticated_parser_eligible is not None:
        manifest_record["parser_eligible"] = authenticated_parser_eligible
    request_records = [request]
    clearance_records = [
        _clearance_record(
            source_document_id="complaint", digest=digest, byte_count=byte_count
        )
    ]
    manifest_records = [manifest_record]

    if companion is not None:
        companion_pdf = tmp_path / f"{companion.source_document_id}.pdf"
        companion_pdf.write_bytes(b"%PDF companion fixture")
        companion_digest = hashlib.sha256(companion_pdf.read_bytes()).hexdigest()
        companion_bytes = companion_pdf.stat().st_size
        companion_request: JsonRecord = {
            "candidate_id": "cand-1",
            "source_document_id": companion.source_document_id,
            "input_path": str(companion_pdf),
            "expected_sha256": companion_digest,
            "expected_byte_count": companion_bytes,
        }
        if companion.plan_role is not None:
            companion_request["document_role"] = companion.plan_role
        companion_manifest: JsonRecord = {
            "candidate_id": "cand-1",
            "source_document_id": companion.source_document_id,
            "sha256": companion_digest,
            "byte_count": companion_bytes,
        }
        if companion.manifest_role is not None:
            companion_manifest["document_role"] = companion.manifest_role
        if companion.parser_eligible is not None:
            companion_manifest["parser_eligible"] = companion.parser_eligible
        request_records.append(companion_request)
        clearance_records.append(
            _clearance_record(
                source_document_id=companion.source_document_id,
                digest=companion_digest,
                byte_count=companion_bytes,
            )
        )
        manifest_records.append(companion_manifest)

    requests_path = tmp_path / "parse-requests.jsonl"
    _write_jsonl(requests_path, request_records)
    clearance_path = tmp_path / "parse-clearance.jsonl"
    _write_jsonl(clearance_path, clearance_records)
    _, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path, skip_packet_planner_replay=True
    )
    # ``_materialized_cli_unit_fixture`` writes an empty placeholder manifest and
    # replays it as the verified lineage, so this is the authenticated statement
    # of each materialized document's role.
    _write_jsonl(tmp_path / "materialized-manifest.jsonl", manifest_records)
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


def _reuse_key(
    request: MistralMarkdownConversionRequest,
) -> tuple[str, str, str, int]:
    return (
        request.candidate_id,
        request.source_document_id,
        cast(str, request.expected_sha256),
        cast(int, request.expected_byte_count),
    )


def test_reused_markdown_below_the_current_role_threshold_is_regapped(
    tmp_path: Path,
) -> None:
    """A gate-failing reused row is superseded by a fresh parse, not refused.

    The prior run's byte, hash, and provenance commitments say nothing about
    which role measured the Markdown, so authenticated-but-thin Markdown must
    not become a cheaper route past the pleading threshold.  It is also not a
    reason to abandon the whole plan: the authenticated source bytes are still
    present, so the row moves out of the reuse set and the pinned parser
    converts it again.  Nothing is relaxed — the frozen artifact is left
    exactly as it was, and the fresh conversion faces the identical gate.
    """

    prior_card, prior_root, request = _prior_live_mistral_run(
        tmp_path, markdown=_WEAK_MARKDOWN
    )
    output_root = tmp_path / "successor"

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=prior_card,
        prior_markdown_root=prior_root,
        requests=(request,),
        output_root=output_root,
    )

    assert plan.superseded_keys == frozenset({_reuse_key(request)})
    assert dict(plan.records_by_key) == {}
    assert [gap.source_document_id for gap in plan.gaps] == ["complaint"]
    assert plan.source["reused_record_count"] == 0
    assert plan.source["parsed_gap_count"] == 1
    # The failing conversion is superseded, never copied forward and never
    # mutated in place.
    assert not request.markdown_output_path.exists()
    assert (
        prior_root.joinpath("cand-1", "complaint.md").read_text(encoding="utf-8")
        == _WEAK_MARKDOWN
    )


def test_reused_markdown_meeting_the_current_role_threshold_is_copied(
    tmp_path: Path,
) -> None:
    """A gate-passing row still reuses, with no spurious re-parse."""

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
    assert plan.superseded_keys == frozenset()
    assert len(plan.records_by_key) == 1
    assert plan.source["reused_record_count"] == 1
    assert plan.source["parsed_gap_count"] == 0
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


def _superseding_parser(
    *,
    tmp_path: Path,
    markdown: str | None,
    calls: list[tuple[str, ...]],
) -> Any:
    """Return a stand-in pinned parser that publishes ``markdown`` for each gap.

    ``markdown=None`` reproduces the real parser's own parse-quality refusal:
    it publishes no Markdown and returns a failed record carrying the rejection
    flag, which is exactly the shape a second failed OCR of the same document
    would produce.
    """

    def convert(
        requests: tuple[MistralMarkdownConversionRequest, ...],
        **_kwargs: object,
    ) -> tuple[Any, ...]:
        calls.append(tuple(request.source_document_id for request in requests))
        records: list[Any] = []
        for request in requests:
            artifact_root = request.markdown_output_path.parent.parent
            metadata_path = request.markdown_output_path.with_suffix(".metadata.json")
            parser_config: JsonRecord = {
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
                    str(request.input_path),
                    "--mistral",
                    "--no-ocr",
                ],
            }
            shared = {
                "candidate_id": request.candidate_id,
                "source_document_id": request.source_document_id,
                "input_path": str(request.input_path),
                "markdown_path": request.markdown_output_path.relative_to(
                    artifact_root
                ).as_posix(),
                "metadata_path": metadata_path.relative_to(artifact_root).as_posix(),
                "parser_config": parser_config,
                "source_sha256": request.expected_sha256,
                "source_byte_count": request.expected_byte_count,
            }
            if markdown is None:
                records.append(
                    cli.MistralMarkdownConversionRecord(
                        status=cli.MistralMarkdownConversionStatus.FAILED,
                        quality_flags=(PARSE_QUALITY_REJECTION_FLAG,),
                        extracted_text=None,
                        error_message=(
                            "parser output failed parse-quality gate: "
                            "no_substantive_text"
                        ),
                        **cast(Any, shared),
                    )
                )
                continue
            request.markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
            request.markdown_output_path.write_text(markdown, encoding="utf-8")
            record = cli.MistralMarkdownConversionRecord(
                status=cli.MistralMarkdownConversionStatus.SUCCEEDED,
                quality_flags=(),
                extracted_text=cli.ExtractedTextArtifact(
                    source_document_id=request.source_document_id,
                    extracted_at=datetime.fromisoformat(_GENERATED_AT),
                    extraction_method="mistral_parser_markdown",
                    text_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
                ),
                **cast(Any, shared),
            )
            metadata_path.write_text(
                json.dumps(record.to_record(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            records.append(record)
        return tuple(records)

    return convert


def _superseding_reuse_argv(
    *,
    requests_path: Path,
    clearance_path: Path,
    materialization_card: Path,
    output_root: Path,
    prior_card: Path,
    prior_root: Path,
) -> list[str]:
    return [
        *_parse_documents_argv(
            requests_path=requests_path,
            clearance_path=clearance_path,
            materialization_card=materialization_card,
            output_root=output_root,
        ),
        "--resume",
        "--reuse-live-mistral-run-card",
        str(prior_card),
        "--reuse-markdown-root",
        str(prior_root),
    ]


def _superseding_reuse_fixture(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> tuple[list[str], Path]:
    """Build one ``parse-documents`` reuse invocation over a gate-failing row.

    ``_prior_live_mistral_run`` and ``_parse_plan_fixture`` describe the same
    ``cand-1/complaint`` identity over the same source bytes, so the prior run
    matches the current plan exactly and the only reason the row cannot be
    reused is the current parse-quality gate.
    """

    prior_card, prior_root, _request = _prior_live_mistral_run(
        tmp_path, markdown=_WEAK_MARKDOWN
    )
    requests_path, clearance_path, materialization_card = _parse_plan_fixture(
        monkeypatch, tmp_path, document_role="complaint"
    )
    output_root = tmp_path / "successor"
    return (
        _superseding_reuse_argv(
            requests_path=requests_path,
            clearance_path=clearance_path,
            materialization_card=materialization_card,
            output_root=output_root,
            prior_card=prior_card,
            prior_root=prior_root,
        ),
        output_root,
    )


def test_superseding_reparse_that_clears_the_gate_is_recorded(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The regapped row reaches the pinned parser and its fresh parse is kept."""

    argv, output_root = _superseding_reuse_fixture(tmp_path, monkeypatch)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        cli,
        "convert_documents_to_markdown",
        _superseding_parser(
            tmp_path=tmp_path, markdown=_COMPLAINT_MARKDOWN, calls=calls
        ),
    )

    assert cli.main(argv) == 0

    assert calls == [("complaint",)]
    assert (output_root / "markdown" / "cand-1" / "complaint.md").read_text(
        encoding="utf-8"
    ) == _COMPLAINT_MARKDOWN
    manifest = _read_jsonl(output_root / "mistral-markdown-conversions.jsonl")
    assert [record["status"] for record in manifest] == ["succeeded"]
    assert manifest[0]["extracted_text"]["text_sha256"] == (
        hashlib.sha256(_COMPLAINT_MARKDOWN.encode("utf-8")).hexdigest()
    )
    run_card_path = output_root / "run-cards" / "parse-documents.json"
    reused = json.loads(run_card_path.read_text(encoding="utf-8"))["parser_execution"][
        "reused_live_mistral"
    ]
    assert reused["reused_record_count"] == 0
    assert reused["parsed_gap_count"] == 1

    # Resuming the completed run must recognise its own supersession.  The
    # completed-run authenticator recomputes those two counts from the prior
    # artifacts, so it has to partition by the same gate; otherwise every
    # resume of a superseding run refuses as "reuse card differs" and pays for
    # the conversion again.
    manifest_path = output_root / "mistral-markdown-conversions.jsonl"
    manifest_bytes = manifest_path.read_bytes()
    run_card_bytes = run_card_path.read_bytes()

    def _reject_second_conversion(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("completed parse reuse must not call the provider")

    monkeypatch.setattr(cli, "convert_documents_to_markdown", _reject_second_conversion)

    assert cli.main(argv) == 0

    assert manifest_path.read_bytes() == manifest_bytes
    assert run_card_path.read_bytes() == run_card_bytes


def test_superseding_reparse_that_fails_the_gate_again_is_refused(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """Regapping is safening only while the replacement clears the same gate."""

    argv, output_root = _superseding_reuse_fixture(tmp_path, monkeypatch)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        cli,
        "convert_documents_to_markdown",
        _superseding_parser(tmp_path=tmp_path, markdown=None, calls=calls),
    )

    assert cli.main(argv) == 2

    assert calls == [("complaint",)]
    assert (
        "superseded live-Mistral conversion did not succeed: cand-1/complaint"
        in capsys.readouterr().err
    )
    # Fail closed end to end: no manifest, no run card, no published Markdown.
    assert not (output_root / "mistral-markdown-conversions.jsonl").exists()
    assert not (output_root / "run-cards" / "parse-documents.json").exists()
    assert not (output_root / "markdown" / "cand-1" / "complaint.md").exists()

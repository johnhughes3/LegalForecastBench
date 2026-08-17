# pyright: reportPrivateUsage=false
"""Live parse plans must carry ``document_role`` before the parser runs.

``assess_parsed_text`` falls back to a permissive one-character/one-line floor
when the document role is unknown.  A legacy or hand-crafted parse-plan record
that omits ``document_role`` would therefore buy a weaker quality gate than
every authenticated row beside it, so the live parse path refuses the row at
the record-reading boundary instead of parsing it under the fallback.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
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
) -> tuple[Path, Path, Path]:
    """Build the smallest executable ``parse-documents`` invocation inputs."""

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
        main(
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
        main(
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
        main(
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

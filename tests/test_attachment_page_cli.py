from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli_commands.attachment_pages import _requested_entries, register
from legalforecast.ingestion.attachment_page import (
    AttachmentPagePlanError,
    build_attachment_page_fetch_plan,
    record_attachment_page_authorization,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_NUMBER,
    client_for,
    docket_entries_response,
    main_document,
    recap_documents_response,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="legalforecast-acquisition")
    register(parser.add_subparsers(dest="command", required=True))
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    handler: Any = args.handler
    return int(handler(args))


def test_entry_arguments_parse_candidate_and_entry_number() -> None:
    assert _requested_entries(["70308595:8", "71280017:9"]) == [
        ("70308595", 8),
        ("71280017", 9),
    ]


@pytest.mark.parametrize("value", ["70308595", "70308595:", ":8", "70308595:eight", ""])
def test_a_malformed_entry_argument_is_refused(value: str) -> None:
    with pytest.raises(AttachmentPagePlanError, match="CANDIDATE:ENTRY"):
        _requested_entries([value])


def test_fetching_without_execute_spends_nothing_and_reports_usage(
    tmp_path: Path,
) -> None:
    exit_code = main(
        [
            "fetch-attachment-pages",
            "--plan",
            str(tmp_path / "plan.json"),
            "--authorization",
            str(tmp_path / "authorization.json"),
            "--output",
            str(tmp_path / "receipt.json"),
            "--request-ledger",
            str(tmp_path / "ledger.sqlite3"),
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "receipt.json").exists()
    assert not (tmp_path / "ledger.sqlite3").exists()


def test_fetching_with_a_mismatched_authorization_refuses_before_dispatch(
    tmp_path: Path,
) -> None:
    signed_client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    current_client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    signed_plan = build_attachment_page_fetch_plan(
        plan_id="menus-old",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=signed_client,
        per_menu_ceiling_usd="0.10",
    )
    current_plan = build_attachment_page_fetch_plan(
        plan_id="menus-new",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=current_client,
        per_menu_ceiling_usd="0.10",
    )
    authorization = record_attachment_page_authorization(
        plan=signed_plan,
        typed_confirmation=signed_plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc="2026-08-17T21:00:00Z",
    )
    plan_path = tmp_path / "plan.json"
    authorization_path = tmp_path / "authorization.json"
    plan_path.write_text(json.dumps(current_plan.to_record()), encoding="utf-8")
    authorization_path.write_text(
        json.dumps(authorization.to_record()), encoding="utf-8"
    )

    exit_code = main(
        [
            "fetch-attachment-pages",
            "--plan",
            str(plan_path),
            "--authorization",
            str(authorization_path),
            "--output",
            str(tmp_path / "receipt.json"),
            "--request-ledger",
            str(tmp_path / "ledger.sqlite3"),
            "--execute",
        ]
    )

    assert exit_code == 3
    assert not (tmp_path / "receipt.json").exists()
    # The refusal must land before any credential read or ledger creation.
    assert not (tmp_path / "ledger.sqlite3").exists()


def test_the_three_commands_are_registered_with_their_handlers() -> None:
    for command in (
        "plan-attachment-pages",
        "authorize-attachment-pages",
        "fetch-attachment-pages",
    ):
        with pytest.raises(SystemExit) as excinfo:
            main([command, "--help"])
        assert excinfo.value.code == 0

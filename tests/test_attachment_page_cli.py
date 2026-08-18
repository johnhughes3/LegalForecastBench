from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli_commands import attachment_pages as cli
from legalforecast.cli_commands.attachment_pages import _requested_entries, register
from legalforecast.ingestion.attachment_page import (
    AttachmentPageFetchPlan,
    AttachmentPagePlanError,
    build_attachment_page_fetch_plan,
    read_dispatch_records,
    record_attachment_page_authorization,
    write_authorization,
)
from legalforecast.ingestion.courtlistener_recap_fetch import RecapFetchHTTPResponse

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_NUMBER,
    attachment_document,
    client_for,
    docket_entries_response,
    main_document,
    recap_documents_response,
    recap_fetch_response,
)

QUEUE_ID = 5150
RECORDED_AT = "2026-08-17T21:00:00Z"


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
            "--dispatch-journal",
            str(tmp_path / "journal.sqlite3"),
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
            "--dispatch-journal",
            str(tmp_path / "journal.sqlite3"),
            "--execute",
        ]
    )

    assert exit_code == 3
    assert not (tmp_path / "receipt.json").exists()
    # The refusal must land before any credential read or ledger creation.
    assert not (tmp_path / "ledger.sqlite3").exists()
    assert not (tmp_path / "journal.sqlite3").exists()


def test_the_three_commands_are_registered_with_their_handlers() -> None:
    for command in (
        "plan-attachment-pages",
        "authorize-attachment-pages",
        "fetch-attachment-pages",
    ):
        with pytest.raises(SystemExit) as excinfo:
            main([command, "--help"])
        assert excinfo.value.code == 0


class _Posts:
    """Stand in for the RECAP Fetch transport and count charge-bearing POSTs."""

    def __init__(self, responses: list[RecapFetchHTTPResponse]) -> None:
        self._responses = list(responses)
        self.posts: list[dict[str, str]] = []

    def request(self, **kwargs: Any) -> RecapFetchHTTPResponse:
        self.posts.append(dict(kwargs["form"]))
        if not self._responses:
            raise AssertionError("transport received an unscripted POST")
        return self._responses.pop(0)


def _accepted(queue_id: int = QUEUE_ID) -> RecapFetchHTTPResponse:
    return RecapFetchHTTPResponse(
        status_code=201, payload={"id": queue_id, "status": 1, "message": ""}
    )


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[Any],
    posts: list[RecapFetchHTTPResponse],
) -> _Posts:
    """Point the fetch command at fixtures and away from every real endpoint."""

    client, _ = client_for(responses)
    transport = _Posts(posts)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "token")
    monkeypatch.setenv("PACER_USERNAME", "user")
    monkeypatch.setenv("PACER_PASSWORD", "secret")
    monkeypatch.setattr(cli, "CourtListenerClient", lambda **kwargs: client)
    monkeypatch.setattr(cli, "UrlLibRecapFetchTransport", lambda base_url: transport)
    return transport


def _plan_at(path: Path) -> AttachmentPageFetchPlan:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    plan = build_attachment_page_fetch_plan(
        plan_id="cycle-1-attachment-menus-test",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=client,
        per_menu_ceiling_usd="0.10",
    )
    path.write_text(json.dumps(plan.to_record()), encoding="utf-8")
    return plan


def _authorization_at(path: Path, plan: AttachmentPageFetchPlan) -> None:
    write_authorization(
        path,
        record_attachment_page_authorization(
            plan=plan,
            typed_confirmation=plan.required_confirmation(),
            reviewer_id="John Hughes",
            recorded_at_utc=RECORDED_AT,
        ),
    )


def _fetch(tmp_path: Path, *, output: str = "receipt.json") -> int:
    return main(
        [
            "fetch-attachment-pages",
            "--plan",
            str(tmp_path / "plan.json"),
            "--authorization",
            str(tmp_path / "authorization.json"),
            "--output",
            str(tmp_path / output),
            "--request-ledger",
            str(tmp_path / "ledger.sqlite3"),
            "--dispatch-journal",
            str(tmp_path / "journal.sqlite3"),
            "--execute",
        ]
    )


def _successful_run() -> list[Any]:
    return [
        recap_documents_response(documents=[main_document()]),
        recap_fetch_response(queue_id=QUEUE_ID, status=2, message="ok"),
        recap_documents_response(
            documents=[
                main_document(),
                attachment_document(document_id=9001, attachment_number=1),
            ]
        ),
    ]


def test_a_fetch_writes_its_receipt_and_consumes_the_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The receipt write path, end to end -- previously untested."""

    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    transport = _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])

    assert _fetch(tmp_path) == 0

    receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["plan_sha256"] == plan.plan_sha256
    assert receipt["charge_dispatched_count"] == 1
    assert receipt["ceiling_upper_bound_usd"] == "0.10"
    assert receipt["outcomes"][0]["disposition"] == "fetched"
    assert len(transport.posts) == 1
    authorization = json.loads(
        (tmp_path / "authorization.json").read_text(encoding="utf-8")
    )
    assert authorization["authorization"]["paid_activity_executed"] is True
    records = read_dispatch_records(tmp_path / "journal.sqlite3", plan.plan_sha256)
    assert [record.disposition for record in records] == ["fetched"]


def test_an_output_that_already_exists_refuses_before_any_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running after a partial failure is natural; charging for it is not."""

    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    (tmp_path / "receipt.json").write_text("{}", encoding="utf-8")
    transport = _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])

    assert _fetch(tmp_path) == 3

    assert transport.posts == []
    assert (tmp_path / "receipt.json").read_text(encoding="utf-8") == "{}"
    assert read_dispatch_records(tmp_path / "journal.sqlite3", plan.plan_sha256) == ()
    authorization = json.loads(
        (tmp_path / "authorization.json").read_text(encoding="utf-8")
    )
    assert authorization["authorization"]["paid_activity_executed"] is False


def test_reusing_a_consumed_authorization_refuses_without_charging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])
    assert _fetch(tmp_path) == 0

    second = _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])
    assert _fetch(tmp_path, output="receipt-2.json") == 3

    assert second.posts == []
    assert not (tmp_path / "receipt-2.json").exists()


def test_a_failed_menu_is_not_recharged_under_a_fresh_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fresh sign-off resumes a run; it does not re-buy what already dispatched."""

    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    first = _wire(
        monkeypatch,
        responses=[
            recap_documents_response(documents=[main_document()]),
            recap_fetch_response(queue_id=QUEUE_ID, status=3, message="PACER refused"),
        ],
        posts=[_accepted()],
    )
    # A terminal provider failure is a recorded outcome, not a halt.
    assert _fetch(tmp_path) == 0
    assert len(first.posts) == 1
    first_receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
    assert first_receipt["outcomes"][0]["disposition"] == "failed"

    (tmp_path / "authorization.json").unlink()
    _authorization_at(tmp_path / "authorization.json", plan)
    second = _wire(
        monkeypatch,
        responses=[recap_documents_response(documents=[main_document()])],
        posts=[_accepted()],
    )

    assert _fetch(tmp_path, output="receipt-2.json") == 0
    assert second.posts == []
    receipt = json.loads((tmp_path / "receipt-2.json").read_text(encoding="utf-8"))
    assert receipt["outcomes"][0]["disposition"] == "already_dispatched"
    assert receipt["charge_dispatched_count"] == 0


def test_a_failure_after_dispatch_reports_a_halt_and_never_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The old code printed "refused" over charges that had already gone out."""

    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    transport = _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(cli, "replace_artifact", _explode)

    exit_code = _fetch(tmp_path)

    assert exit_code == 1
    assert len(transport.posts) == 1
    stderr = capsys.readouterr().err
    assert "refused" not in stderr
    assert "halted after dispatch began" in stderr
    assert "1 charge(s) recorded as dispatched" in stderr
    # The receipt is gone, but the journal still carries the spend.
    records = read_dispatch_records(tmp_path / "journal.sqlite3", plan.plan_sha256)
    assert [record.disposition for record in records] == ["fetched"]


def test_a_malformed_plan_refuses_rather_than_tracebacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan_at(tmp_path / "plan.json")
    _authorization_at(tmp_path / "authorization.json", plan)
    (tmp_path / "plan.json").write_text("{not json", encoding="utf-8")
    transport = _wire(monkeypatch, responses=_successful_run(), posts=[_accepted()])

    assert _fetch(tmp_path) == 3

    assert transport.posts == []
    assert not (tmp_path / "receipt.json").exists()

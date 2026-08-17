from __future__ import annotations

import io
from typing import Any

import pytest
from legalforecast.ingestion.attachment_page import (
    AttachmentPageAuthorizationError,
    AttachmentPageFetchPlan,
    build_attachment_page_fetch_plan,
    load_attachment_page_authorization,
    prompt_for_attachment_page_authorization,
    record_attachment_page_authorization,
    render_authorization_prompt,
    verify_authorization_binds_plan,
    write_authorization,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_NUMBER,
    client_for,
    docket_entries_response,
    main_document,
    recap_documents_response,
)

RECORDED_AT = "2026-08-17T21:00:00Z"


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _plan(
    *,
    plan_id: str = "cycle-1-attachment-menus-test",
    entry_id: int = 429596666,
    ceiling: str = "0.10",
) -> AttachmentPageFetchPlan:
    client, _ = client_for(
        [
            docket_entries_response(entry_id=entry_id),
            recap_documents_response(
                documents=[main_document(entry_id=entry_id)], entry_id=entry_id
            ),
        ]
    )
    return build_attachment_page_fetch_plan(
        plan_id=plan_id,
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=client,
        per_menu_ceiling_usd=ceiling,
    )


def test_authorization_binds_the_exact_plan_digest() -> None:
    plan = _plan()

    authorization = record_attachment_page_authorization(
        plan=plan,
        typed_confirmation=plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc=RECORDED_AT,
    )

    assert authorization.plan_sha256 == plan.plan_sha256
    assert authorization.menu_count == 1
    assert authorization.content_record()["paid_activity_executed"] is False
    verify_authorization_binds_plan(authorization=authorization, plan=plan)


def test_a_confirmation_minted_from_another_plan_cannot_authorize() -> None:
    """The failure mode this whole design exists to prevent.

    A confirmation string copied out of an earlier projection binds a digest
    that has since moved. Accepting it would spend against a plan the owner
    never actually read.
    """

    signed_plan = _plan(plan_id="cycle-1-attachment-menus-old", ceiling="0.10")
    current_plan = _plan(plan_id="cycle-1-attachment-menus-new", ceiling="0.30")

    with pytest.raises(
        AttachmentPageAuthorizationError, match="does not match this exact plan"
    ):
        record_attachment_page_authorization(
            plan=current_plan,
            typed_confirmation=signed_plan.required_confirmation(),
            reviewer_id="John Hughes",
            recorded_at_utc=RECORDED_AT,
        )


def test_an_authorization_for_another_plan_is_refused_at_verification() -> None:
    signed_plan = _plan(plan_id="cycle-1-attachment-menus-old")
    current_plan = _plan(plan_id="cycle-1-attachment-menus-new")
    authorization = record_attachment_page_authorization(
        plan=signed_plan,
        typed_confirmation=signed_plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc=RECORDED_AT,
    )

    with pytest.raises(
        AttachmentPageAuthorizationError, match="different attachment-menu plan"
    ):
        verify_authorization_binds_plan(authorization=authorization, plan=current_plan)


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "APPROVE",
        "approve cycle-1-attachment-menus-test",
        "yes",
    ],
)
def test_a_confirmation_that_is_not_the_exact_line_is_refused(typed: str) -> None:
    plan = _plan()

    with pytest.raises(AttachmentPageAuthorizationError):
        record_attachment_page_authorization(
            plan=plan,
            typed_confirmation=typed,
            reviewer_id="John Hughes",
            recorded_at_utc=RECORDED_AT,
        )


def test_a_reviewer_who_is_not_the_owner_is_refused() -> None:
    plan = _plan()

    with pytest.raises(AttachmentPageAuthorizationError, match="reviewer must be"):
        record_attachment_page_authorization(
            plan=plan,
            typed_confirmation=plan.required_confirmation(),
            reviewer_id="An Agent",
            recorded_at_utc=RECORDED_AT,
        )


def test_the_prompt_reads_from_a_terminal_and_accepts_the_displayed_line() -> None:
    plan = _plan()
    stdin = _Tty(plan.required_confirmation() + "\n")
    stdout = io.StringIO()

    authorization = prompt_for_attachment_page_authorization(
        plan=plan,
        recorded_at_utc=RECORDED_AT,
        stdin=stdin,
        stdout=stdout,
    )

    displayed = stdout.getvalue()
    assert plan.required_confirmation() in displayed
    assert plan.plan_sha256 in displayed
    assert "no attachment document is purchased" in displayed.lower()
    assert authorization.plan_sha256 == plan.plan_sha256


def test_a_piped_confirmation_is_not_owner_authorization() -> None:
    plan = _plan()

    with pytest.raises(AttachmentPageAuthorizationError, match="interactive terminal"):
        prompt_for_attachment_page_authorization(
            plan=plan,
            recorded_at_utc=RECORDED_AT,
            stdin=io.StringIO(plan.required_confirmation() + "\n"),
            stdout=io.StringIO(),
        )


def test_the_prompt_shows_excluded_entries_so_the_count_is_explainable() -> None:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document(pacer_doc_id="")]),
            docket_entries_response(docket_id="71280017", entry_number=9, entry_id=555),
            recap_documents_response(documents=[main_document()], entry_id=555),
        ]
    )
    plan = build_attachment_page_fetch_plan(
        plan_id="cycle-1-attachment-menus-test",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER), ("71280017", 9)],
        client=client,
        per_menu_ceiling_usd="0.10",
    )

    rendered = render_authorization_prompt(plan)

    assert "Excluded, no charge:" in rendered
    assert "main_document_has_no_pacer_identity" in rendered
    assert "TARGET 1" in rendered


def test_loading_an_authorization_reverifies_its_digest(tmp_path: Any) -> None:
    plan = _plan()
    authorization = record_attachment_page_authorization(
        plan=plan,
        typed_confirmation=plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc=RECORDED_AT,
    )
    record = authorization.to_record()

    assert load_attachment_page_authorization(record).plan_sha256 == plan.plan_sha256

    record["authorization"]["menu_count"] = 7
    with pytest.raises(
        AttachmentPageAuthorizationError, match="digest does not verify"
    ):
        load_attachment_page_authorization(record)


def test_writing_an_authorization_refuses_to_clobber_an_existing_one(
    tmp_path: Any,
) -> None:
    plan = _plan()
    authorization = record_attachment_page_authorization(
        plan=plan,
        typed_confirmation=plan.required_confirmation(),
        reviewer_id="John Hughes",
        recorded_at_utc=RECORDED_AT,
    )
    path = tmp_path / "authorization.json"

    write_authorization(path, authorization)
    with pytest.raises(AttachmentPageAuthorizationError, match="already exists"):
        write_authorization(path, authorization)

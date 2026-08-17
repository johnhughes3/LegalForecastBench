from __future__ import annotations

import pytest
from legalforecast.ingestion.attachment_page import (
    ATTACHMENT_PAGE_REQUEST_TYPE,
    AttachmentPagePlanError,
    build_attachment_page_fetch_plan,
    load_attachment_page_fetch_plan,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_ID,
    ENTRY_NUMBER,
    MAIN_DOCUMENT_ID,
    MAIN_PACER_DOC_ID,
    attachment_document,
    client_for,
    docket_entries_response,
    main_document,
    recap_documents_response,
)


def test_plan_authenticates_a_missing_menu_and_commits_a_digest() -> None:
    client, transport = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )

    plan = build_attachment_page_fetch_plan(
        plan_id="cycle-1-attachment-menus-test",
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=client,
        per_menu_ceiling_usd="0.20",
    )

    assert len(plan.targets) == 1
    target = plan.targets[0]
    assert target.candidate_id == DOCKET_ID
    assert target.docket_entry_id == str(ENTRY_ID)
    assert target.main_source_document_id == str(MAIN_DOCUMENT_ID)
    assert target.main_pacer_doc_id == MAIN_PACER_DOC_ID
    assert plan.per_menu_ceiling_usd == "0.20"
    assert plan.total_ceiling_usd == "0.20"
    assert plan.plan_sha256
    assert plan.content_record()["request_type"] == ATTACHMENT_PAGE_REQUEST_TYPE
    assert transport.requests[0][1] == "/docket-entries/"
    assert transport.requests[1][1] == "/recap-documents/"


def test_plan_excludes_entries_whose_menu_courtlistener_already_holds() -> None:
    """An already-ingested menu resolves for free; charging for it is waste."""

    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(
                documents=[
                    main_document(),
                    attachment_document(document_id=9001, attachment_number=1),
                ]
            ),
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

    assert [target.candidate_id for target in plan.targets] == ["71280017"]
    assert [skip.candidate_id for skip in plan.skipped] == [DOCKET_ID]
    assert plan.skipped[0].reason == "already_ingested"
    assert plan.total_ceiling_usd == "0.10"


def test_plan_refuses_when_no_entry_needs_a_paid_menu() -> None:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(
                documents=[
                    main_document(),
                    attachment_document(document_id=9001, attachment_number=1),
                ]
            ),
        ]
    )

    with pytest.raises(AttachmentPagePlanError, match="nothing to authorize"):
        build_attachment_page_fetch_plan(
            plan_id="cycle-1-attachment-menus-test",
            requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
            client=client,
            per_menu_ceiling_usd="0.10",
        )


def test_plan_skips_an_entry_whose_main_document_has_no_pacer_identity() -> None:
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

    assert plan.skipped[0].reason == "main_document_has_no_pacer_identity"
    assert [target.candidate_id for target in plan.targets] == ["71280017"]


def test_plan_rejects_a_duplicate_requested_entry() -> None:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )

    with pytest.raises(AttachmentPagePlanError, match="duplicate requested entry"):
        build_attachment_page_fetch_plan(
            plan_id="cycle-1-attachment-menus-test",
            requested_entries=[(DOCKET_ID, ENTRY_NUMBER), (DOCKET_ID, ENTRY_NUMBER)],
            client=client,
            per_menu_ceiling_usd="0.10",
        )


def test_plan_rejects_a_nonexact_entry_resolution() -> None:
    client, _ = client_for(
        [
            docket_entries_response(entry_number=99),
        ]
    )

    with pytest.raises(AttachmentPagePlanError, match="entry resolution is not exact"):
        build_attachment_page_fetch_plan(
            plan_id="cycle-1-attachment-menus-test",
            requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
            client=client,
            per_menu_ceiling_usd="0.10",
        )


@pytest.mark.parametrize("ceiling", ["0", "-1.00", "0.001", "free"])
def test_plan_rejects_a_nonsensical_per_menu_ceiling(ceiling: str) -> None:
    client, _ = client_for([])

    with pytest.raises(AttachmentPagePlanError):
        build_attachment_page_fetch_plan(
            plan_id="cycle-1-attachment-menus-test",
            requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
            client=client,
            per_menu_ceiling_usd=ceiling,
        )


def test_loading_a_plan_reverifies_its_digest() -> None:
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
    record = plan.to_record()

    assert load_attachment_page_fetch_plan(record).plan_sha256 == plan.plan_sha256

    record["plan"]["targets"][0]["main_source_document_id"] = "999999999"
    with pytest.raises(AttachmentPagePlanError, match="digest does not verify"):
        load_attachment_page_fetch_plan(record)

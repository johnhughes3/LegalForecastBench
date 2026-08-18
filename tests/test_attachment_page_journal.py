"""The dispatch journal: what makes an attachment-menu charge durable."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.ingestion.attachment_page import (
    INTENDED,
    JOURNAL_SCHEMA_VERSION,
    AttachmentPageAlreadyDispatched,
    AttachmentPageDispatchJournal,
    AttachmentPageFetchPlan,
    AttachmentPageJournalError,
    build_attachment_page_fetch_plan,
    read_dispatch_records,
)

from attachment_page_fixtures import (
    DOCKET_ID,
    ENTRY_ID,
    ENTRY_NUMBER,
    MAIN_DOCUMENT_ID,
    client_for,
    docket_entries_response,
    journal_at,
    main_document,
    recap_documents_response,
)


def _plan(plan_id: str = "cycle-1-attachment-menus-test") -> AttachmentPageFetchPlan:
    client, _ = client_for(
        [
            docket_entries_response(),
            recap_documents_response(documents=[main_document()]),
        ]
    )
    return build_attachment_page_fetch_plan(
        plan_id=plan_id,
        requested_entries=[(DOCKET_ID, ENTRY_NUMBER)],
        client=client,
        per_menu_ceiling_usd="0.10",
    )


def test_an_intent_is_committed_with_the_target_identity(tmp_path: Path) -> None:
    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        record = journal.record_intent(plan=plan, target=plan.targets[0])

        assert record.disposition == INTENDED
        assert record.resolved is False
        assert record.plan_sha256 == plan.plan_sha256
        assert record.docket_entry_id == str(ENTRY_ID)
        assert record.main_source_document_id == str(MAIN_DOCUMENT_ID)
        assert record.intended_at_utc.endswith("Z")
        assert journal.dispatched_count(plan.plan_sha256) == 1


def test_an_intent_survives_the_process_that_wrote_it(tmp_path: Path) -> None:
    """The whole reason this is SQLite and not an in-memory list."""

    plan = _plan()
    journal = AttachmentPageDispatchJournal(tmp_path / "journal.sqlite3")
    journal.record_intent(plan=plan, target=plan.targets[0])
    journal.close()

    records = read_dispatch_records(tmp_path / "journal.sqlite3", plan.plan_sha256)
    assert [record.disposition for record in records] == [INTENDED]


def test_a_second_intent_for_the_same_entry_is_refused(tmp_path: Path) -> None:
    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])
        with pytest.raises(AttachmentPageAlreadyDispatched, match="already dispatched"):
            journal.record_intent(plan=plan, target=plan.targets[0])
        assert journal.dispatched_count(plan.plan_sha256) == 1


def test_a_resolved_charge_is_still_refused_a_second_intent(tmp_path: Path) -> None:
    """A failed menu is exactly the case a naive rerun would charge twice."""

    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])
        journal.record_disposition(
            plan_sha256=plan.plan_sha256,
            docket_entry_id=str(ENTRY_ID),
            disposition="failed",
            status=3,
            message="PACER refused",
        )
        with pytest.raises(AttachmentPageAlreadyDispatched):
            journal.record_intent(plan=plan, target=plan.targets[0])


def test_a_disposition_records_the_observed_outcome(tmp_path: Path) -> None:
    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])
        journal.record_disposition(
            plan_sha256=plan.plan_sha256,
            docket_entry_id=str(ENTRY_ID),
            disposition="fetched",
            queue_id="5150",
            status=2,
            message="ok",
        )
        record = journal.dispatched(plan.plan_sha256, str(ENTRY_ID))

    assert record is not None
    assert record.disposition == "fetched"
    assert record.resolved is True
    assert record.queue_id == "5150"
    assert record.status == 2
    assert record.resolved_at_utc is not None


def test_a_disposition_cannot_reset_a_row_to_merely_intended(tmp_path: Path) -> None:
    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])
        with pytest.raises(AttachmentPageJournalError, match="still intended"):
            journal.record_disposition(
                plan_sha256=plan.plan_sha256,
                docket_entry_id=str(ENTRY_ID),
                disposition=INTENDED,
            )


def test_a_disposition_without_a_pre_dispatch_row_is_refused(tmp_path: Path) -> None:
    """A disposition with no prior intent means the ordering rule was broken."""

    plan = _plan()
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        with pytest.raises(AttachmentPageJournalError, match="no pre-dispatch"):
            journal.record_disposition(
                plan_sha256=plan.plan_sha256,
                docket_entry_id=str(ENTRY_ID),
                disposition="fetched",
            )


def test_rows_are_scoped_to_the_plan_digest_that_authorized_them(
    tmp_path: Path,
) -> None:
    plan = _plan()
    other = replace(plan, plan_sha256="0" * 64)
    with journal_at(tmp_path / "journal.sqlite3") as journal:
        journal.record_intent(plan=plan, target=plan.targets[0])

        assert journal.dispatched_count(plan.plan_sha256) == 1
        assert journal.dispatched_count(other.plan_sha256) == 0
        assert journal.dispatched(other.plan_sha256, str(ENTRY_ID)) is None
        # A deliberate retry is a new plan and a new owner decision, so the
        # same entry under a different digest is a different row.
        journal.record_intent(plan=other, target=other.targets[0])
        assert len(journal.records_for(other.plan_sha256)) == 1


def test_a_journal_from_another_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE journal_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO journal_meta(key, value) VALUES ('schema', 'something.else')"
        )
        connection.commit()

    with pytest.raises(AttachmentPageJournalError, match="schema version"):
        AttachmentPageDispatchJournal(path)


def test_the_schema_version_is_stamped_on_a_fresh_journal(tmp_path: Path) -> None:
    with journal_at(tmp_path / "journal.sqlite3"):
        pass
    with sqlite3.connect(tmp_path / "journal.sqlite3") as connection:
        stored = connection.execute(
            "SELECT value FROM journal_meta WHERE key='schema'"
        ).fetchone()
    assert stored[0] == JOURNAL_SCHEMA_VERSION


def test_an_unopenable_journal_path_refuses_rather_than_tracebacks(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("", encoding="utf-8")

    with pytest.raises(AttachmentPageJournalError, match="dispatch journal"):
        AttachmentPageDispatchJournal(blocked / "journal.sqlite3")

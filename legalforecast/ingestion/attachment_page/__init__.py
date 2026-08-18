"""Attachment-menu acquisition: plan, authorize, then fetch fail-closed.

An attachment-level memorandum cannot be purchased while CourtListener holds
no RECAPDocument row for it, and that row appears only once the entry's PACER
attachment menu has been parsed. This package acquires those menus.

The modules are deliberately the halves of one contract, shipped together:
:mod:`plan` authenticates targets and commits them to a digest,
:mod:`authorization` turns that digest into an owner decision typed at a real
terminal, and :mod:`execute` spends only against a plan that decision binds.

:mod:`journal` is what makes those promises survive a crash. It records each
intended charge before the POST that incurs it, so no failure after the money
leaves can take the record with it, and its rows are the durable evidence that
refuses to charge one entry twice. :mod:`artifact_io` gives every artifact the
same crash-safe write.
"""

from __future__ import annotations

from legalforecast.ingestion.attachment_page.artifact_io import (
    canonical_artifact_bytes,
    replace_artifact,
    reserve_artifact_path,
    write_new_artifact,
)
from legalforecast.ingestion.attachment_page.authorization import (
    AUTHORIZATION_SCHEMA_VERSION,
    AttachmentPageAuthorization,
    AttachmentPageAuthorizationError,
    load_attachment_page_authorization,
    mark_authorization_executed,
    prompt_for_attachment_page_authorization,
    read_authorization_artifact,
    record_attachment_page_authorization,
    render_authorization_prompt,
    verify_authorization_binds_plan,
    write_authorization,
)
from legalforecast.ingestion.attachment_page.execute import (
    RECEIPT_SCHEMA_VERSION,
    AttachmentPageExecutionError,
    AttachmentPageFetchReceipt,
    AttachmentPageOutcome,
    AttachmentPageOutcomeUnknown,
    ResolvedAttachment,
    ceiling_upper_bound_usd,
    execute_attachment_page_fetches,
)
from legalforecast.ingestion.attachment_page.journal import (
    INTENDED,
    JOURNAL_SCHEMA_VERSION,
    AttachmentPageAlreadyDispatched,
    AttachmentPageDispatchJournal,
    AttachmentPageDispatchRecord,
    AttachmentPageJournalError,
    read_dispatch_records,
)
from legalforecast.ingestion.attachment_page.plan import (
    ATTACHMENT_PAGE_REQUEST_TYPE,
    CONFIRMATION_RULE,
    PLAN_SCHEMA_VERSION,
    AttachmentPageFetchPlan,
    AttachmentPagePlanError,
    AttachmentPageSkip,
    AttachmentPageTarget,
    build_attachment_page_fetch_plan,
    load_attachment_page_fetch_plan,
)

__all__ = [
    "ATTACHMENT_PAGE_REQUEST_TYPE",
    "AUTHORIZATION_SCHEMA_VERSION",
    "CONFIRMATION_RULE",
    "INTENDED",
    "JOURNAL_SCHEMA_VERSION",
    "PLAN_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_VERSION",
    "AttachmentPageAlreadyDispatched",
    "AttachmentPageAuthorization",
    "AttachmentPageAuthorizationError",
    "AttachmentPageDispatchJournal",
    "AttachmentPageDispatchRecord",
    "AttachmentPageExecutionError",
    "AttachmentPageFetchPlan",
    "AttachmentPageFetchReceipt",
    "AttachmentPageJournalError",
    "AttachmentPageOutcome",
    "AttachmentPageOutcomeUnknown",
    "AttachmentPagePlanError",
    "AttachmentPageSkip",
    "AttachmentPageTarget",
    "ResolvedAttachment",
    "build_attachment_page_fetch_plan",
    "canonical_artifact_bytes",
    "ceiling_upper_bound_usd",
    "execute_attachment_page_fetches",
    "load_attachment_page_authorization",
    "load_attachment_page_fetch_plan",
    "mark_authorization_executed",
    "prompt_for_attachment_page_authorization",
    "read_authorization_artifact",
    "read_dispatch_records",
    "record_attachment_page_authorization",
    "render_authorization_prompt",
    "replace_artifact",
    "reserve_artifact_path",
    "verify_authorization_binds_plan",
    "write_authorization",
    "write_new_artifact",
]

"""Attachment-menu acquisition: plan, authorize, then fetch fail-closed.

An attachment-level memorandum cannot be purchased while CourtListener holds
no RECAPDocument row for it, and that row appears only once the entry's PACER
attachment menu has been parsed. This package acquires those menus.

The three modules are deliberately the three halves of one contract, shipped
together: :mod:`plan` authenticates targets and commits them to a digest,
:mod:`authorization` turns that digest into an owner decision typed at a real
terminal, and :mod:`execute` spends only against a plan that decision binds.
"""

from __future__ import annotations

from legalforecast.ingestion.attachment_page.authorization import (
    AUTHORIZATION_SCHEMA_VERSION,
    AttachmentPageAuthorization,
    AttachmentPageAuthorizationError,
    load_attachment_page_authorization,
    prompt_for_attachment_page_authorization,
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
    "PLAN_SCHEMA_VERSION",
    "RECEIPT_SCHEMA_VERSION",
    "AttachmentPageAuthorization",
    "AttachmentPageAuthorizationError",
    "AttachmentPageExecutionError",
    "AttachmentPageFetchPlan",
    "AttachmentPageFetchReceipt",
    "AttachmentPageOutcome",
    "AttachmentPageOutcomeUnknown",
    "AttachmentPagePlanError",
    "AttachmentPageSkip",
    "AttachmentPageTarget",
    "ResolvedAttachment",
    "build_attachment_page_fetch_plan",
    "ceiling_upper_bound_usd",
    "execute_attachment_page_fetches",
    "load_attachment_page_authorization",
    "load_attachment_page_fetch_plan",
    "prompt_for_attachment_page_authorization",
    "record_attachment_page_authorization",
    "render_authorization_prompt",
    "verify_authorization_binds_plan",
    "write_authorization",
]

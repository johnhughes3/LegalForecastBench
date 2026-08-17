"""Authenticated plan for acquiring PACER attachment menu pages.

An attachment-level document cannot be purchased until CourtListener holds a
RECAPDocument row for it, and that row exists only once CourtListener has
parsed the entry's PACER attachment menu. Where the menu was never ingested,
no authenticated ``source_document_id`` exists anywhere, so a purchase
projection cannot be built at all.

This module produces the plan that fixes that: for each requested docket
entry it authenticates the entry's main document by GET, proves that no
attachment row currently exists, and commits the resulting target set to a
digest. Nothing here contacts PACER or spends money -- the plan is the
issuance artifact an owner signs against before any charge-bearing fetch is
authorized.

Entries that already carry attachment rows are recorded as ``already_ingested``
and excluded from the plan: their selectors resolve for free, and fetching
their menu would spend money for data CourtListener already has.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

from legalforecast.ingestion.attachment_page import _typed
from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerClientError,
    CourtListenerDocketEntry,
)

PLAN_SCHEMA_VERSION: Final = "legalforecast.attachment_page_fetch_plan.v1"
ATTACHMENT_PAGE_REQUEST_TYPE: Final = "3"
CONFIRMATION_RULE: Final = "fetch_exact_attachment_menus"


class AttachmentPagePlanError(ValueError):
    """Raised when an attachment-page plan cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class AttachmentPageTarget:
    """One docket entry whose attachment menu is missing from CourtListener."""

    candidate_id: str
    docket_entry_number: int
    docket_entry_id: str
    main_source_document_id: str
    main_pacer_doc_id: str
    entry_description: str

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "docket_entry_number": self.docket_entry_number,
            "docket_entry_id": self.docket_entry_id,
            "main_source_document_id": self.main_source_document_id,
            "main_pacer_doc_id": self.main_pacer_doc_id,
            "entry_description": self.entry_description,
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageSkip:
    """One requested entry excluded from the plan, with the reason."""

    candidate_id: str
    docket_entry_number: int
    reason: str
    detail: str

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "docket_entry_number": self.docket_entry_number,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class AttachmentPageFetchPlan:
    """The exact charge-bearing target set, committed to one digest."""

    plan_id: str
    targets: tuple[AttachmentPageTarget, ...]
    skipped: tuple[AttachmentPageSkip, ...]
    per_menu_ceiling_usd: str
    total_ceiling_usd: str
    plan_sha256: str

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "plan": self.content_record(),
            "plan_sha256": self.plan_sha256,
        }

    def content_record(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "request_type": ATTACHMENT_PAGE_REQUEST_TYPE,
            "menu_count": len(self.targets),
            "per_menu_ceiling_usd": self.per_menu_ceiling_usd,
            "total_ceiling_usd": self.total_ceiling_usd,
            "targets": [target.to_record() for target in self.targets],
            "skipped": [skip.to_record() for skip in self.skipped],
        }

    def required_confirmation(self) -> str:
        """Return the exact string an owner must type to authorize this plan.

        Callers must display this value from the plan they actually loaded and
        must never accept a confirmation supplied from anywhere else: a string
        copied from an earlier projection can bind a digest that no longer
        matches, which turns a fail-closed prompt into a burned authorization.
        """

        return (
            f"APPROVE {self.plan_id} {self.plan_sha256} "
            f"{self.total_ceiling_usd} RULE {CONFIRMATION_RULE} "
            f"TARGET {len(self.targets)} ONE_GLOBAL_SESSION"
        )


def commit_plan_digest(content: Mapping[str, object]) -> str:
    payload = canonical_json_value_bytes(
        content,
        error_type=AttachmentPagePlanError,
        error_message="attachment-page plan is not canonically serializable",
    )
    return hashlib.sha256(payload).hexdigest()


def _money(value: str | Decimal, label: str) -> str:
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AttachmentPagePlanError(f"{label} is not a decimal amount") from exc
    if not amount.is_finite() or amount <= 0 or int(amount.as_tuple().exponent) < -2:
        raise AttachmentPagePlanError(
            f"{label} must be a positive finite amount with at most two decimals"
        )
    return f"{amount:.2f}"


def _entry_for(
    client: CourtListenerClient,
    *,
    candidate_id: str,
    docket_entry_number: int,
) -> CourtListenerDocketEntry:
    matches = [
        entry
        for entry in client.iter_docket_entries(candidate_id, page_size=100)
        if str(entry.entry_number) == str(docket_entry_number)
    ]
    if len(matches) != 1:
        raise AttachmentPagePlanError(
            f"entry resolution is not exact for {candidate_id} "
            f"entry {docket_entry_number}: {len(matches)} matches"
        )
    return matches[0]


def build_attachment_page_fetch_plan(
    *,
    plan_id: str,
    requested_entries: Sequence[tuple[str, int]],
    client: CourtListenerClient,
    per_menu_ceiling_usd: str | Decimal,
) -> AttachmentPageFetchPlan:
    """Authenticate each requested entry and commit the exact target set.

    Identities are read live rather than copied from a prior artifact, so the
    plan's digest binds what CourtListener holds at plan time. Every requested
    entry lands in exactly one of ``targets`` or ``skipped``.
    """

    if not plan_id.strip() or "\n" in plan_id or " " in plan_id:
        raise AttachmentPagePlanError("plan id must be one nonempty bare token")
    if not requested_entries:
        raise AttachmentPagePlanError(
            "attachment-page plan requires at least one entry"
        )
    seen: set[tuple[str, int]] = set()
    per_menu = _money(per_menu_ceiling_usd, "per-menu ceiling")

    targets: list[AttachmentPageTarget] = []
    skipped: list[AttachmentPageSkip] = []
    for candidate_id, docket_entry_number in requested_entries:
        key = (candidate_id, int(docket_entry_number))
        if key in seen:
            raise AttachmentPagePlanError(
                f"duplicate requested entry {candidate_id} entry {docket_entry_number}"
            )
        seen.add(key)
        try:
            entry = _entry_for(
                client,
                candidate_id=candidate_id,
                docket_entry_number=docket_entry_number,
            )
            documents = tuple(
                client.iter_recap_documents(entry.docket_entry_id, page_size=100)
            )
        except CourtListenerClientError as exc:
            raise AttachmentPagePlanError(
                f"could not authenticate {candidate_id} entry "
                f"{docket_entry_number}: {exc}"
            ) from exc

        attachments = [
            document for document in documents if document.attachment_number is not None
        ]
        if attachments:
            skipped.append(
                AttachmentPageSkip(
                    candidate_id=candidate_id,
                    docket_entry_number=int(docket_entry_number),
                    reason="already_ingested",
                    detail=(
                        f"{len(attachments)} attachment row(s) already exist; "
                        "selectors resolve without spending"
                    ),
                )
            )
            continue

        mains = [
            document for document in documents if document.attachment_number is None
        ]
        if len(mains) != 1:
            skipped.append(
                AttachmentPageSkip(
                    candidate_id=candidate_id,
                    docket_entry_number=int(docket_entry_number),
                    reason="main_document_not_exact",
                    detail=(
                        f"{len(mains)} main document row(s) found; an attachment "
                        "menu fetch needs exactly one"
                    ),
                )
            )
            continue

        main = mains[0]
        pacer_doc_id = str(main.raw.get("pacer_doc_id") or "").strip()
        if not pacer_doc_id:
            skipped.append(
                AttachmentPageSkip(
                    candidate_id=candidate_id,
                    docket_entry_number=int(docket_entry_number),
                    reason="main_document_has_no_pacer_identity",
                    detail=(
                        "the main document carries no pacer_doc_id, so PACER "
                        "cannot be asked for its attachment menu"
                    ),
                )
            )
            continue

        targets.append(
            AttachmentPageTarget(
                candidate_id=candidate_id,
                docket_entry_number=int(docket_entry_number),
                docket_entry_id=str(entry.docket_entry_id),
                main_source_document_id=str(main.document_id),
                main_pacer_doc_id=pacer_doc_id,
                entry_description=str(entry.entry_text or ""),
            )
        )

    if not targets:
        raise AttachmentPagePlanError(
            "no requested entry needs a paid attachment menu; nothing to authorize"
        )
    total = _money(Decimal(per_menu) * len(targets), "total ceiling")
    plan = AttachmentPageFetchPlan(
        plan_id=plan_id,
        targets=tuple(targets),
        skipped=tuple(skipped),
        per_menu_ceiling_usd=per_menu,
        total_ceiling_usd=total,
        plan_sha256="",
    )
    return AttachmentPageFetchPlan(
        plan_id=plan.plan_id,
        targets=plan.targets,
        skipped=plan.skipped,
        per_menu_ceiling_usd=plan.per_menu_ceiling_usd,
        total_ceiling_usd=plan.total_ceiling_usd,
        plan_sha256=commit_plan_digest(plan.content_record()),
    )


def load_attachment_page_fetch_plan(record: object) -> AttachmentPageFetchPlan:
    """Rebuild a plan from its artifact and re-verify its committed digest."""

    error = AttachmentPagePlanError
    body = _typed.mapping(record, "attachment-page plan artifact", error=error)
    if body.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise error("unexpected attachment-page plan schema version")
    content = _typed.mapping(
        body.get("plan"), "attachment-page plan content", error=error
    )
    digest = body.get("plan_sha256")
    if not isinstance(digest, str) or digest != commit_plan_digest(content):
        raise error("attachment-page plan digest does not verify")
    if content.get("request_type") != ATTACHMENT_PAGE_REQUEST_TYPE:
        raise error("attachment-page plan request type must be 3")
    raw_targets = _typed.sequence(content.get("targets"), "plan targets", error=error)
    if not raw_targets:
        raise error("attachment-page plan requires at least one target")
    if content.get("menu_count") != len(raw_targets):
        raise error("attachment-page plan menu count does not match")

    targets: list[AttachmentPageTarget] = []
    for raw in raw_targets:
        target = _typed.mapping(raw, "plan target", error=error)
        targets.append(
            AttachmentPageTarget(
                candidate_id=_typed.text(
                    target.get("candidate_id"), "candidate id", error=error
                ),
                docket_entry_number=_typed.integer(
                    target.get("docket_entry_number"),
                    "docket entry number",
                    error=error,
                ),
                docket_entry_id=_typed.text(
                    target.get("docket_entry_id"), "docket entry id", error=error
                ),
                main_source_document_id=_typed.text(
                    target.get("main_source_document_id"),
                    "main source document id",
                    error=error,
                ),
                main_pacer_doc_id=_typed.text(
                    target.get("main_pacer_doc_id"), "main pacer doc id", error=error
                ),
                entry_description=_typed.optional_text(
                    target.get("entry_description"), "entry description", error=error
                ),
            )
        )

    skipped: list[AttachmentPageSkip] = []
    for raw in _typed.sequence(content.get("skipped", []), "plan skips", error=error):
        skip = _typed.mapping(raw, "plan skip", error=error)
        skipped.append(
            AttachmentPageSkip(
                candidate_id=_typed.text(
                    skip.get("candidate_id"), "candidate id", error=error
                ),
                docket_entry_number=_typed.integer(
                    skip.get("docket_entry_number"), "docket entry number", error=error
                ),
                reason=_typed.text(skip.get("reason"), "skip reason", error=error),
                detail=_typed.optional_text(
                    skip.get("detail"), "skip detail", error=error
                ),
            )
        )

    return AttachmentPageFetchPlan(
        plan_id=_typed.text(content.get("plan_id"), "plan id", error=error),
        targets=tuple(targets),
        skipped=tuple(skipped),
        per_menu_ceiling_usd=_money(
            _typed.text(
                content.get("per_menu_ceiling_usd"), "per-menu ceiling", error=error
            ),
            "per-menu ceiling",
        ),
        total_ceiling_usd=_money(
            _typed.text(content.get("total_ceiling_usd"), "total ceiling", error=error),
            "total ceiling",
        ),
        plan_sha256=digest,
    )

# pyright: reportPrivateUsage=false

"""Operator commands for acquiring PACER attachment menu pages.

Three commands, in the order they must run: plan (free, authenticated), then
authorize (a person types a line at a terminal), then fetch (charge-bearing,
bounded by what that person signed). The enforcement lives in
:mod:`legalforecast.ingestion.attachment_page`; this module is the supported
way to satisfy it, so the two ship together rather than leaving a fail-closed
gate with no key.

``fetch`` has one ordering rule that matters more than its argument list.
Everything that can refuse -- an unbound authorization, an unreadable journal,
a missing credential, an ``--output`` that already exists -- is settled before
the first charge. After that point the command may report a halt, but it may
never report a refusal: charges have gone out, and an operator who reads
"refused" will not go looking for spend.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from legalforecast._datetime import format_utc_iso_z
from legalforecast._json_io import read_json_object
from legalforecast.ingestion.attachment_page import (
    AttachmentPageAuthorizationError,
    AttachmentPageDispatchJournal,
    AttachmentPageExecutionError,
    AttachmentPageJournalError,
    AttachmentPagePlanError,
    build_attachment_page_fetch_plan,
    canonical_artifact_bytes,
    ceiling_upper_bound_usd,
    execute_attachment_page_fetches,
    load_attachment_page_authorization,
    load_attachment_page_fetch_plan,
    mark_authorization_executed,
    prompt_for_attachment_page_authorization,
    read_authorization_artifact,
    read_dispatch_records,
    replace_artifact,
    reserve_artifact_path,
    verify_authorization_binds_plan,
    write_authorization,
    write_new_artifact,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    DirectCourtListenerRecapFetchConfig,
    UrlLibRecapFetchTransport,
)
from legalforecast.ingestion.courtlistener_request_budget import (
    CourtListenerRequestBudget,
    CourtListenerRequestBudgetError,
    CourtListenerRequestLimits,
)

_EXIT_HALTED = 1
_EXIT_USAGE = 2
_EXIT_REFUSED = 3


class _ArtifactWriteError(ValueError):
    """Raised when a command refuses to write over an existing artifact."""


#: Everything a charge-bearing run can refuse with *before* it spends anything.
_PRE_DISPATCH_REFUSALS = (
    AttachmentPageAuthorizationError,
    AttachmentPageExecutionError,
    AttachmentPageJournalError,
    AttachmentPagePlanError,
    CourtListenerRequestBudgetError,
    _ArtifactWriteError,
    OSError,
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the plan/authorize/fetch attachment-menu commands."""

    plan = subparsers.add_parser(
        "plan-attachment-pages",
        help="Authenticate docket entries whose PACER attachment menu is missing.",
        description=(
            "Read each requested entry from CourtListener, prove no attachment "
            "row exists for it, and commit the resulting charge-bearing target "
            "set to one digest. Entries whose menu CourtListener already holds "
            "are excluded rather than charged. GET-only: this command contacts "
            "no PACER endpoint and spends nothing."
        ),
    )
    plan.add_argument("--plan-id", required=True, help="Bare token naming this plan.")
    plan.add_argument(
        "--entry",
        action="append",
        required=True,
        metavar="CANDIDATE:ENTRY",
        help=(
            "Docket entry to consider, as candidate id and entry number "
            "(repeatable, for example 70308595:8)."
        ),
    )
    plan.add_argument(
        "--per-menu-ceiling-usd",
        required=True,
        help=(
            "Per-menu ceiling. PACER bills attachment menus per page, so a long "
            "menu can exceed a single page's charge; set the ceiling accordingly."
        ),
    )
    plan.add_argument("--output", type=Path, required=True)
    plan.set_defaults(handler=run_plan)

    authorize = subparsers.add_parser(
        "authorize-attachment-pages",
        help="Record one owner authorization for an exact attachment-menu plan.",
        description=(
            "Display the loaded plan and read one typed confirmation from a "
            "terminal. The confirmation is derived from the plan this command "
            "loaded, so a line copied from an earlier projection cannot "
            "authorize a fetch. Contacts no provider and spends nothing. The "
            "authorization it writes is single-use: the first fetch that "
            "dispatches a charge consumes it."
        ),
    )
    authorize.add_argument("--plan", type=Path, required=True)
    authorize.add_argument("--output", type=Path, required=True)
    authorize.set_defaults(handler=run_authorize)

    fetch = subparsers.add_parser(
        "fetch-attachment-pages",
        help="Fetch exactly the authorized attachment menus, once each.",
        description=(
            "Charge-bearing. Fetches only menus the signed plan names, never "
            "twice, and never retries a dispatched charge. A menu ingested "
            "since signing is skipped without charge; a fetch that completes "
            "without creating attachment rows is recorded as a failure. Each "
            "intended charge is written to the dispatch journal before it is "
            "dispatched, so the durable record can never lag the spend, and "
            "the authorization is consumed at the first dispatch."
        ),
    )
    fetch.add_argument("--plan", type=Path, required=True)
    fetch.add_argument("--authorization", type=Path, required=True)
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument(
        "--request-ledger",
        type=Path,
        required=True,
        help="SQLite request-budget ledger recording every GET and POST.",
    )
    fetch.add_argument(
        "--dispatch-journal",
        type=Path,
        required=True,
        help=(
            "SQLite journal of every intended charge, written before dispatch. "
            "Pass the same path on every run of a plan: it is what stops an "
            "entry whose fetch failed from being charged a second time."
        ),
    )
    fetch.add_argument(
        "--execute",
        action="store_true",
        help="Required. Without it the command reports the plan and exits.",
    )
    fetch.set_defaults(handler=run_fetch)


def _requested_entries(values: list[str]) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for value in values:
        candidate, separator, entry = value.partition(":")
        if not separator or not candidate.strip() or not entry.strip().isdigit():
            raise AttachmentPagePlanError(
                f"--entry must be CANDIDATE:ENTRY, got {value!r}"
            )
        entries.append((candidate.strip(), int(entry)))
    return entries


def _read_plan_artifact(path: Path) -> object:
    """Read a plan artifact, refusing rather than tracebacking on bad bytes."""

    try:
        return read_json_object(
            path,
            error_factory=AttachmentPagePlanError,
            missing_message=lambda target: (
                f"no attachment-menu plan exists at {target}"
            ),
            non_object_message=lambda target: (
                f"attachment-menu plan at {target} is not a JSON object"
            ),
        )
    except json.JSONDecodeError as exc:
        raise AttachmentPagePlanError(
            f"attachment-menu plan at {path} is not valid JSON: {exc}"
        ) from exc
    except OSError as exc:
        raise AttachmentPagePlanError(
            f"attachment-menu plan at {path} could not be read: {exc}"
        ) from exc


def _budgeted_client(
    ledger: Path,
) -> tuple[CourtListenerClient, CourtListenerRequestBudget]:
    config = CourtListenerConfig.from_env()
    if config.api_token is None:
        raise AttachmentPageExecutionError("COURTLISTENER_API_TOKEN is required")
    budget = CourtListenerRequestBudget(
        ledger,
        limits=CourtListenerRequestLimits(per_minute=24, per_hour=290, per_day=1_350),
        max_wait_seconds=1_800.0,
    )
    return (
        CourtListenerClient(config=config, before_request=budget.before_request),
        budget,
    )


def run_plan(args: argparse.Namespace) -> int:
    try:
        entries = _requested_entries(args.entry)
        config = CourtListenerConfig.from_env()
        if config.api_token is None:
            raise AttachmentPagePlanError("COURTLISTENER_API_TOKEN is required")
        plan = build_attachment_page_fetch_plan(
            plan_id=args.plan_id,
            requested_entries=entries,
            client=CourtListenerClient(config=config),
            per_menu_ceiling_usd=args.per_menu_ceiling_usd,
        )
        write_new_artifact(args.output, plan.to_record(), error=AttachmentPagePlanError)
    except AttachmentPagePlanError as exc:
        print(f"attachment-menu planning refused: {exc}", file=sys.stderr)
        return _EXIT_REFUSED
    print(
        json.dumps(
            {
                "plan_id": plan.plan_id,
                "plan_sha256": plan.plan_sha256,
                "menu_count": len(plan.targets),
                "skipped_count": len(plan.skipped),
                "total_ceiling_usd": plan.total_ceiling_usd,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def run_authorize(args: argparse.Namespace) -> int:
    try:
        plan = load_attachment_page_fetch_plan(_read_plan_artifact(args.plan))
        authorization = prompt_for_attachment_page_authorization(
            plan=plan,
            recorded_at_utc=format_utc_iso_z(datetime.now(UTC)),
            stdin=sys.stdin,
            stdout=sys.stdout,
        )
        write_authorization(args.output, authorization)
    except (AttachmentPagePlanError, AttachmentPageAuthorizationError) as exc:
        print(f"attachment-menu authorization refused: {exc}", file=sys.stderr)
        return _EXIT_REFUSED
    print(
        json.dumps(
            {
                "plan_sha256": authorization.plan_sha256,
                "menu_count": authorization.menu_count,
                "reviewer_id": authorization.reviewer_id,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def run_fetch(args: argparse.Namespace) -> int:
    if not args.execute:
        print("fetch-attachment-pages requires --execute", file=sys.stderr)
        return _EXIT_USAGE
    try:
        plan = load_attachment_page_fetch_plan(_read_plan_artifact(args.plan))
        authorization = load_attachment_page_authorization(
            read_authorization_artifact(args.authorization)
        )
        # Refuse an unbound authorization before creating a ledger or reading a
        # credential, so a mismatch costs nothing and leaves nothing behind.
        verify_authorization_binds_plan(authorization=authorization, plan=plan)
        journal = AttachmentPageDispatchJournal(args.dispatch_journal)
        client, budget = _budgeted_client(args.request_ledger)
        fetch_config = DirectCourtListenerRecapFetchConfig.from_env()
        # Claim the receipt path last and before spending: an --output that
        # already exists is a natural state after a partial run, and finding
        # that out after N charges is how a run loses its whole record.
        reserve_artifact_path(args.output, error=_ArtifactWriteError)
    except _PRE_DISPATCH_REFUSALS as exc:
        print(f"attachment-menu fetch refused: {exc}", file=sys.stderr)
        return _EXIT_REFUSED

    # From here a charge can go out, so nothing below may claim a refusal.
    try:
        with journal:
            receipt = execute_attachment_page_fetches(
                plan=plan,
                authorization=authorization,
                config=fetch_config,
                transport=UrlLibRecapFetchTransport(fetch_config.base_url),
                client=client,
                journal=journal,
                before_request=budget.before_request,
                before_first_dispatch=lambda: mark_authorization_executed(
                    args.authorization
                ),
            )
            record = receipt.to_record()
            record["ceiling_upper_bound_usd"] = ceiling_upper_bound_usd(plan, receipt)
            replace_artifact(
                args.output,
                canonical_artifact_bytes(record, error=_ArtifactWriteError),
                error=_ArtifactWriteError,
            )
    except Exception as exc:  # broad on purpose: an honesty net over spent money
        print(
            _post_dispatch_failure(args.dispatch_journal, plan.plan_sha256, exc),
            file=sys.stderr,
        )
        return _EXIT_HALTED
    print(
        json.dumps(
            {
                "plan_sha256": receipt.plan_sha256,
                "recap_fetch_post_count": receipt.recap_fetch_post_count,
                "ceiling_upper_bound_usd": record["ceiling_upper_bound_usd"],
                "halted_reason": receipt.halted_reason,
            },
            sort_keys=True,
        )
    )
    return _EXIT_HALTED if receipt.halted_reason else 0


def _post_dispatch_failure(
    journal_path: Path, plan_sha256: str, exc: BaseException
) -> str:
    """Describe a failure that may sit on top of charges already dispatched."""

    try:
        dispatched = len(read_dispatch_records(journal_path, plan_sha256))
        counted = f"{dispatched} charge(s) recorded as dispatched"
    except (AttachmentPageJournalError, OSError) as journal_exc:
        counted = f"the dispatched-charge count could not be read ({journal_exc})"
    return (
        f"attachment-menu fetch halted after dispatch began: {exc}\n"
        f"This is not a refusal. The dispatch journal at {journal_path} holds "
        f"{counted} for this plan; reconcile spend from it, and use a fresh "
        "--output and a fresh authorization for any follow-up run."
    )

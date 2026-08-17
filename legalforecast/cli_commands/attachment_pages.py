# pyright: reportPrivateUsage=false

"""Operator commands for acquiring PACER attachment menu pages.

Three commands, in the order they must run: plan (free, authenticated), then
authorize (a person types a line at a terminal), then fetch (charge-bearing,
bounded by what that person signed). The enforcement lives in
:mod:`legalforecast.ingestion.attachment_page`; this module is the supported
way to satisfy it, so the two ship together rather than leaving a fail-closed
gate with no key.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from legalforecast._datetime import format_utc_iso_z
from legalforecast.ingestion.attachment_page import (
    AttachmentPageAuthorizationError,
    AttachmentPageExecutionError,
    AttachmentPagePlanError,
    build_attachment_page_fetch_plan,
    ceiling_upper_bound_usd,
    execute_attachment_page_fetches,
    load_attachment_page_authorization,
    load_attachment_page_fetch_plan,
    prompt_for_attachment_page_authorization,
    verify_authorization_binds_plan,
    write_authorization,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
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
    CourtListenerRequestLimits,
)

_EXIT_USAGE = 2
_EXIT_REFUSED = 3


class _ArtifactWriteError(ValueError):
    """Raised when a command refuses to write over an existing artifact."""


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
            "authorize a fetch. Contacts no provider and spends nothing."
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
            "without creating attachment rows is recorded as a failure."
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


def _write(path: Path, record: object, error: type[ValueError]) -> None:
    if path.exists():
        raise error(f"refusing to overwrite an existing artifact at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        canonical_json_bytes(
            record,
            error_type=error,
            error_message="artifact is not canonically serializable",
        )
    )


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
        _write(args.output, plan.to_record(), AttachmentPagePlanError)
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
        plan = load_attachment_page_fetch_plan(
            json.loads(args.plan.read_text(encoding="utf-8"))
        )
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
        plan = load_attachment_page_fetch_plan(
            json.loads(args.plan.read_text(encoding="utf-8"))
        )
        authorization = load_attachment_page_authorization(
            json.loads(args.authorization.read_text(encoding="utf-8"))
        )
        # Refuse an unbound authorization before creating a ledger or reading a
        # credential, so a mismatch costs nothing and leaves nothing behind.
        verify_authorization_binds_plan(authorization=authorization, plan=plan)
        client, budget = _budgeted_client(args.request_ledger)
        receipt = execute_attachment_page_fetches(
            plan=plan,
            authorization=authorization,
            config=DirectCourtListenerRecapFetchConfig.from_env(),
            transport=UrlLibRecapFetchTransport(
                DirectCourtListenerRecapFetchConfig.from_env().base_url
            ),
            client=client,
            before_request=budget.before_request,
        )
        record = receipt.to_record()
        record["ceiling_upper_bound_usd"] = ceiling_upper_bound_usd(plan, receipt)
        _write(args.output, record, _ArtifactWriteError)
    except (
        AttachmentPagePlanError,
        AttachmentPageAuthorizationError,
        AttachmentPageExecutionError,
        _ArtifactWriteError,
    ) as exc:
        print(f"attachment-menu fetch refused: {exc}", file=sys.stderr)
        return _EXIT_REFUSED
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
    return 1 if receipt.halted_reason else 0

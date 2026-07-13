"""Plan and journal fee-bearing Case.dev docket refreshes fail-closed."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from legalforecast.ingestion.case_dev_client import CaseDevClient
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_courtlistener_docket_for_mtd_decision,
)

DOCKET_LIVE_FETCH_PLAN_SCHEMA_VERSION = "legalforecast.docket_live_fetch_plan.v1"


class DocketLiveFetchError(RuntimeError):
    """Base error for docket-live-fetch planning and execution."""


class DocketLiveFetchReconciliationRequired(DocketLiveFetchError):
    """Raised when a prior submitted request has no safely replayable result."""


@dataclass(frozen=True, slots=True)
class DocketLiveFetchPlanItem:
    candidate_id: str
    docket_id: str
    decision_date: str
    decision_entry_ids: tuple[str, ...]
    existing_free_required_document_count: int | None
    existing_missing_required_document_count: int | None
    docket_entry_count: int | None
    reservation_usd: Decimal

    def to_record(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "docket_id": self.docket_id,
            "decision_date": self.decision_date,
            "decision_entry_ids": list(self.decision_entry_ids),
            "existing_free_required_document_count": (
                self.existing_free_required_document_count
            ),
            "existing_missing_required_document_count": (
                self.existing_missing_required_document_count
            ),
            "docket_entry_count": self.docket_entry_count,
            "reservation_usd": _money(self.reservation_usd),
        }


@dataclass(frozen=True, slots=True)
class DocketLiveFetchPlan:
    cycle_id: str
    policy_sha256: str
    eligibility_anchor: str
    cycle_budget_usd: Decimal
    max_per_case_usd: Decimal
    docket_fetch_reservation_usd: Decimal
    daily_budget_usd: Decimal
    daily_committed_spend_usd: Decimal
    spend_date_utc: str
    canonical_journal_path: str
    items: tuple[DocketLiveFetchPlanItem, ...]

    @property
    def total_projected_cost(self) -> Decimal:
        return sum((item.reservation_usd for item in self.items), Decimal("0"))

    @property
    def total_projected_cost_usd(self) -> str:
        return _money(self.total_projected_cost)

    @property
    def daily_remaining_headroom(self) -> Decimal:
        return self.daily_budget_usd - self.daily_committed_spend_usd

    @property
    def executable_items(self) -> tuple[DocketLiveFetchPlanItem, ...]:
        limit = int(self.daily_remaining_headroom // self.docket_fetch_reservation_usd)
        return self.items[:limit]

    @property
    def executable_projected_cost_usd(self) -> str:
        return _money(
            sum(
                (item.reservation_usd for item in self.executable_items),
                Decimal("0"),
            )
        )

    @property
    def plan_sha256(self) -> str:
        return _hash(self._content_record())

    @property
    def frontier_records(self) -> list[dict[str, object]]:
        cumulative = Decimal("0")
        frontier: list[dict[str, object]] = [
            {"selected_count": 0, "projected_spend_usd": "0.00"}
        ]
        for index, item in enumerate(self.items, start=1):
            cumulative += item.reservation_usd
            frontier.append(
                {
                    "selected_count": index,
                    "projected_spend_usd": _money(cumulative),
                }
            )
        return frontier

    def _content_record(self) -> dict[str, object]:
        return {
            "schema_version": DOCKET_LIVE_FETCH_PLAN_SCHEMA_VERSION,
            "cycle_id": self.cycle_id,
            "policy_sha256": self.policy_sha256,
            "eligibility_anchor": self.eligibility_anchor,
            "cycle_budget_usd": _money(self.cycle_budget_usd),
            "max_per_case_usd": _money(self.max_per_case_usd),
            "docket_fetch_reservation_usd": _money(self.docket_fetch_reservation_usd),
            "daily_budget_usd": _money(self.daily_budget_usd),
            "daily_committed_spend_usd": _money(self.daily_committed_spend_usd),
            "daily_remaining_headroom_usd": _money(self.daily_remaining_headroom),
            "spend_date_utc": self.spend_date_utc,
            "canonical_journal_path": self.canonical_journal_path,
            "total_projected_cost_usd": self.total_projected_cost_usd,
            "executable_item_count": len(self.executable_items),
            "executable_projected_cost_usd": self.executable_projected_cost_usd,
            "items": [item.to_record() for item in self.items],
            "frontier": self.frontier_records,
        }

    def to_record(self) -> dict[str, object]:
        return {**self._content_record(), "plan_sha256": self.plan_sha256}


@dataclass(frozen=True, slots=True)
class DocketLiveFetchExecutionResult:
    plan_sha256: str
    intended_count: int
    confirmed_count: int
    statuses: Mapping[str, str]
    confirmed_candidates: tuple[Mapping[str, str], ...] = ()

    def to_record(self) -> dict[str, object]:
        return {
            "plan_sha256": self.plan_sha256,
            "intended_count": self.intended_count,
            "confirmed_count": self.confirmed_count,
            "statuses": dict(self.statuses),
            "confirmed_candidates": [dict(item) for item in self.confirmed_candidates],
        }


def plan_docket_live_fetches(
    *,
    screening_records: Iterable[Mapping[str, object]],
    fetch_success_records: Iterable[Mapping[str, object]],
    ranking_records: Iterable[Mapping[str, object]],
    advisory_records: Iterable[Mapping[str, object]] = (),
    cohort_policy: Mapping[str, object],
    docket_fetch_reservation_usd: Decimal | str = "3.05",
    daily_budget_usd: Decimal | str = "25.00",
    daily_committed_spend_usd: Decimal | str,
    spend_date_utc: str,
    canonical_journal_path: str = "case-dev-docket-live-fetch.sqlite3",
) -> DocketLiveFetchPlan:
    """Build a deterministic, provider-free frontier from strict exclusions."""

    policy_sha256 = _required_text(cohort_policy, "policy_sha256")
    policy = _mapping(cohort_policy.get("policy"), "cohort policy")
    cycle_id = _required_text(policy, "cycle_id")
    eligibility_anchor = _required_text(policy, "eligibility_anchor")
    anchor = date.fromisoformat(eligibility_anchor)
    purchase = _mapping(policy.get("purchase_policy"), "purchase policy")
    cycle_budget = _decimal(purchase.get("cycle_budget_usd"), "cycle_budget_usd")
    max_per_case = _decimal(purchase.get("max_per_case_usd"), "max_per_case_usd")
    reservation = _decimal(docket_fetch_reservation_usd, "docket_fetch_reservation_usd")
    daily_budget = _decimal(daily_budget_usd, "daily_budget_usd")
    daily_committed = _decimal(daily_committed_spend_usd, "daily_committed_spend_usd")
    date.fromisoformat(spend_date_utc)
    if reservation <= 0 or reservation > max_per_case:
        raise ValueError(
            "docket fetch reservation must be positive and within max per case"
        )
    if daily_budget <= 0 or daily_budget > Decimal("25.00"):
        raise ValueError("daily budget must be positive and cannot exceed 25.00")
    if daily_committed < 0 or daily_committed > daily_budget:
        raise ValueError("daily committed spend must be within the daily budget")

    fetches = {
        _required_text(record, "candidate_id"): record
        for record in fetch_success_records
    }
    rankings: dict[str, Mapping[str, object]] = {}
    for record in ranking_records:
        identity = _mapping(record.get("identity"), "ranking identity")
        rankings[_required_text(identity, "courtlistener_docket_id")] = record
    advisories: dict[str, Mapping[str, object]] = {}
    advisory_input_present = False
    for record in advisory_records:
        advisory_input_present = True
        if record.get("recovery_class") != "high_confidence":
            continue
        candidate_id = _required_text(record, "candidate_id")
        if candidate_id in advisories:
            raise ValueError(f"duplicate high-confidence advisory {candidate_id}")
        advisories[candidate_id] = record

    eligible: list[DocketLiveFetchPlanItem] = []
    seen: set[str] = set()
    for record in screening_records:
        candidate_id = _required_text(record, "candidate_id")
        if candidate_id in seen or record.get("state") != "excluded":
            continue
        advisory = advisories.get(candidate_id)
        if advisory_input_present and advisory is None:
            continue
        evidence = _mapping(record.get("evidence"), "screening evidence")
        if evidence.get("reason") != "no_target_motion":
            continue
        decision_date = date.fromisoformat(_required_text(evidence, "decision_date"))
        if decision_date < anchor:
            continue
        entry_ids = _string_tuple(evidence.get("source_entry_ids"), "source_entry_ids")
        if not entry_ids:
            continue
        fetch = fetches.get(candidate_id)
        if fetch is None:
            continue
        if advisory is not None:
            if _required_text(advisory, "decision_date") != decision_date.isoformat():
                raise ValueError(f"advisory decision date disagrees for {candidate_id}")
            if (
                _string_tuple(advisory.get("decision_entry_ids"), "decision_entry_ids")
                != entry_ids
            ):
                raise ValueError(
                    f"advisory decision entries disagree for {candidate_id}"
                )
        docket_id = _required_text(fetch, "docket_id")
        raw_path = Path(_required_text(fetch, "raw_html_path"))
        page = parse_courtlistener_docket_html(
            raw_path.read_text(encoding="utf-8"),
            source_url=_required_text(fetch, "source_url"),
            docket_id=docket_id,
        )
        cited = tuple(entry for entry in page.entries if entry.row_id in entry_ids)
        if len(cited) != len(set(entry_ids)):
            continue
        docket_screen = screen_courtlistener_docket_for_mtd_decision(
            page, decision_filed_on_or_after=anchor
        )
        anchored_decision_ids = {
            entry.row_id for entry in docket_screen.decision_entries
        }
        if not anchored_decision_ids.intersection(entry_ids):
            continue
        ranking = rankings.get(docket_id, advisory or {})
        eligible.append(
            DocketLiveFetchPlanItem(
                candidate_id=candidate_id,
                docket_id=docket_id,
                decision_date=decision_date.isoformat(),
                decision_entry_ids=entry_ids,
                existing_free_required_document_count=_optional_int(
                    ranking, "actual_free_required_document_count"
                ),
                existing_missing_required_document_count=_optional_int(
                    ranking, "missing_required_document_count"
                ),
                docket_entry_count=_optional_int(ranking, "docket_entry_count"),
                reservation_usd=reservation,
            )
        )
        seen.add(candidate_id)

    eligible.sort(key=_frontier_key)
    limit = int(cycle_budget // reservation)
    items = tuple(eligible[:limit])
    return DocketLiveFetchPlan(
        cycle_id=cycle_id,
        policy_sha256=policy_sha256,
        eligibility_anchor=eligibility_anchor,
        cycle_budget_usd=cycle_budget,
        max_per_case_usd=max_per_case,
        docket_fetch_reservation_usd=reservation,
        daily_budget_usd=daily_budget,
        daily_committed_spend_usd=daily_committed,
        spend_date_utc=spend_date_utc,
        canonical_journal_path=canonical_journal_path,
        items=items,
    )


def load_docket_live_fetch_plan(record: Mapping[str, object]) -> DocketLiveFetchPlan:
    """Load and verify a serialized immutable docket-live-fetch plan."""

    if record.get("schema_version") != DOCKET_LIVE_FETCH_PLAN_SCHEMA_VERSION:
        raise ValueError("unsupported docket live fetch plan schema")
    items_value = record.get("items")
    if not isinstance(items_value, list):
        raise ValueError("docket live fetch plan items must be an array")
    raw_items = cast(list[object], items_value)
    items = tuple(_plan_item(_mapping(item, "plan item")) for item in raw_items)
    plan = DocketLiveFetchPlan(
        cycle_id=_required_text(record, "cycle_id"),
        policy_sha256=_required_text(record, "policy_sha256"),
        eligibility_anchor=_required_text(record, "eligibility_anchor"),
        cycle_budget_usd=_decimal(record.get("cycle_budget_usd"), "cycle_budget_usd"),
        max_per_case_usd=_decimal(record.get("max_per_case_usd"), "max_per_case_usd"),
        docket_fetch_reservation_usd=_decimal(
            record.get("docket_fetch_reservation_usd"),
            "docket_fetch_reservation_usd",
        ),
        daily_budget_usd=_decimal(record.get("daily_budget_usd"), "daily_budget_usd"),
        daily_committed_spend_usd=_decimal(
            record.get("daily_committed_spend_usd"), "daily_committed_spend_usd"
        ),
        spend_date_utc=_required_text(record, "spend_date_utc"),
        canonical_journal_path=_required_text(record, "canonical_journal_path"),
        items=items,
    )
    if record.get("plan_sha256") != plan.plan_sha256:
        raise ValueError("docket live fetch plan hash mismatch")
    if record.get("total_projected_cost_usd") != plan.total_projected_cost_usd:
        raise ValueError("docket live fetch projected cost mismatch")
    if record.get("frontier") != plan.frontier_records:
        raise ValueError("docket live fetch cumulative frontier mismatch")
    if plan.total_projected_cost > plan.cycle_budget_usd:
        raise ValueError("docket live fetch plan exceeds cycle budget")
    if plan.daily_budget_usd > Decimal("25.00"):
        raise ValueError("docket live fetch daily budget exceeds provider cap")
    if plan.daily_remaining_headroom < 0:
        raise ValueError("docket live fetch daily committed spend exceeds cap")
    if record.get("executable_item_count") != len(plan.executable_items):
        raise ValueError("docket live fetch executable prefix mismatch")
    if (
        record.get("executable_projected_cost_usd")
        != plan.executable_projected_cost_usd
    ):
        raise ValueError("docket live fetch executable projected cost mismatch")
    if not Path(plan.canonical_journal_path).is_absolute():
        raise ValueError("docket live fetch canonical journal path must be absolute")
    return plan


class DocketLiveFetchJournal:
    """Durable one-shot journal for non-idempotent fee-bearing docket POSTs."""

    def __init__(self, path: str | Path, *, plan: DocketLiveFetchPlan) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.plan = plan
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._create_schema()
        self._bind_plan()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def statuses(self) -> dict[str, str]:
        rows = self._connection.execute(
            "SELECT docket_id, status FROM docket_fetch_operations ORDER BY docket_id"
        ).fetchall()
        return {str(row["docket_id"]): str(row["status"]) for row in rows}

    @property
    def committed_reservation_usd(self) -> str:
        row = self._connection.execute(
            """SELECT COALESCE(SUM(reservation_usd), 0) AS total
            FROM docket_fetch_operations WHERE status != 'planned'"""
        ).fetchone()
        assert row is not None
        return _money(self.plan.daily_committed_spend_usd + Decimal(str(row["total"])))

    def submit(self, item: DocketLiveFetchPlanItem) -> bool:
        """Commit submitted state immediately before the single HTTP attempt."""

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            row = self._operation(item.docket_id)
            assert row is not None
            status = str(row["status"])
            if status == "confirmed":
                self._connection.commit()
                return False
            if status in {"submitted", "unknown"}:
                raise DocketLiveFetchReconciliationRequired(
                    f"docket {item.docket_id} has {status} paid outcome; "
                    "provider evidence is required before any reissue"
                )
            committed = Decimal(self.committed_reservation_usd)
            if committed + item.reservation_usd > self.plan.cycle_budget_usd:
                raise DocketLiveFetchError("docket fetch reservation exceeds cycle cap")
            if committed + item.reservation_usd > self.plan.daily_budget_usd:
                raise DocketLiveFetchError("docket fetch reservation exceeds daily cap")
            cursor = self._connection.execute(
                """UPDATE docket_fetch_operations SET status='submitted'
                WHERE docket_id=? AND status='planned'""",
                (item.docket_id,),
            )
            if cursor.rowcount != 1:
                raise DocketLiveFetchError("docket fetch journal transition failed")
        except BaseException:
            self._connection.rollback()
            raise
        self._connection.commit()
        return True

    def confirm(self, docket_id: str, response: Mapping[str, object]) -> None:
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE docket_fetch_operations
                SET status='confirmed', response_json=?, error=NULL
                WHERE docket_id=? AND status='submitted'""",
                (_canonical(response), docket_id),
            )
            if cursor.rowcount != 1:
                raise DocketLiveFetchError("cannot confirm unsubmitted docket fetch")

    def mark_unknown(self, docket_id: str, error: BaseException) -> None:
        with self._connection:
            self._connection.execute(
                """UPDATE docket_fetch_operations SET status='unknown', error=?
                WHERE docket_id=? AND status='submitted'""",
                (f"{type(error).__name__}: {error}", docket_id),
            )

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS docket_fetch_ledger (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                cycle_id TEXT NOT NULL,
                policy_sha256 TEXT NOT NULL,
                plan_sha256 TEXT NOT NULL,
                cycle_budget_usd TEXT NOT NULL,
                daily_budget_usd TEXT NOT NULL,
                daily_committed_spend_usd TEXT NOT NULL,
                spend_date_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS docket_fetch_operations (
                docket_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                reservation_usd TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('planned','submitted','confirmed','unknown')),
                response_json TEXT,
                error TEXT
            );
            """
        )

    def _bind_plan(self) -> None:
        with self._connection:
            self._connection.execute(
                """INSERT OR IGNORE INTO docket_fetch_ledger(
                    singleton, cycle_id, policy_sha256, plan_sha256, cycle_budget_usd,
                    daily_budget_usd, daily_committed_spend_usd, spend_date_utc
                ) VALUES(1, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.plan.cycle_id,
                    self.plan.policy_sha256,
                    self.plan.plan_sha256,
                    _money(self.plan.cycle_budget_usd),
                    _money(self.plan.daily_budget_usd),
                    _money(self.plan.daily_committed_spend_usd),
                    self.plan.spend_date_utc,
                ),
            )
            row = self._connection.execute(
                "SELECT * FROM docket_fetch_ledger WHERE singleton=1"
            ).fetchone()
            assert row is not None
            actual = (
                str(row["cycle_id"]),
                str(row["policy_sha256"]),
                str(row["plan_sha256"]),
                str(row["cycle_budget_usd"]),
                str(row["daily_budget_usd"]),
                str(row["daily_committed_spend_usd"]),
                str(row["spend_date_utc"]),
            )
            expected = (
                self.plan.cycle_id,
                self.plan.policy_sha256,
                self.plan.plan_sha256,
                _money(self.plan.cycle_budget_usd),
                _money(self.plan.daily_budget_usd),
                _money(self.plan.daily_committed_spend_usd),
                self.plan.spend_date_utc,
            )
            if actual != expected:
                raise DocketLiveFetchError(
                    "docket fetch journal is bound to a different frozen plan"
                )
            for item in self.plan.executable_items:
                self._connection.execute(
                    """INSERT OR IGNORE INTO docket_fetch_operations(
                        docket_id, candidate_id, reservation_usd, status
                    ) VALUES(?, ?, ?, 'planned')""",
                    (item.docket_id, item.candidate_id, _money(item.reservation_usd)),
                )

    def _operation(self, docket_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM docket_fetch_operations WHERE docket_id=?", (docket_id,)
        ).fetchone()


def execute_docket_live_fetch_plan(
    plan: DocketLiveFetchPlan,
    *,
    client: CaseDevClient,
    journal_path: str | Path,
    live: bool,
    acknowledge_pacer_fees: bool,
) -> DocketLiveFetchExecutionResult:
    """Execute each planned fee-bearing lookup at most once."""

    if not live or not acknowledge_pacer_fees:
        raise ValueError("live docket fetch and fee acknowledgment are both required")
    if datetime.now(UTC).date().isoformat() != plan.spend_date_utc:
        raise DocketLiveFetchError(
            "frozen docket live-fetch plan is not authorized for the current UTC day"
        )
    if Path(journal_path).resolve() != Path(plan.canonical_journal_path).resolve():
        raise DocketLiveFetchError(
            "journal path differs from the canonical path frozen in the plan"
        )
    with DocketLiveFetchJournal(journal_path, plan=plan) as journal:
        for item in plan.executable_items:
            if not journal.submit(item):
                continue
            try:
                response = client.live_fetch_docket(
                    item.docket_id, acknowledge_pacer_fees=True
                )
                _validate_live_fetch_response(response, item=item)
                docket = _mapping(response.get("docket", response), "live docket")
                response_id = _required_text(docket, "id")
                if response_id != item.docket_id:
                    raise DocketLiveFetchError(
                        "live docket response identity does not match planned docket"
                    )
                journal.confirm(item.docket_id, cast(Mapping[str, object], response))
            except BaseException as exc:
                journal.mark_unknown(item.docket_id, exc)
                raise
        statuses = journal.statuses()
    return DocketLiveFetchExecutionResult(
        plan_sha256=plan.plan_sha256,
        intended_count=len(plan.executable_items),
        confirmed_count=sum(status == "confirmed" for status in statuses.values()),
        statuses=statuses,
        confirmed_candidates=tuple(
            {"candidate_id": item.candidate_id, "docket_id": item.docket_id}
            for item in plan.executable_items
            if statuses[item.docket_id] == "confirmed"
        ),
    )


def _frontier_key(item: DocketLiveFetchPlanItem) -> tuple[object, ...]:
    return (
        item.reservation_usd,
        -(item.existing_free_required_document_count or 0),
        item.existing_missing_required_document_count
        if item.existing_missing_required_document_count is not None
        else 10**9,
        item.docket_entry_count if item.docket_entry_count is not None else 10**9,
        item.docket_id,
    )


def _validate_live_fetch_response(
    response: Mapping[str, object], *, item: DocketLiveFetchPlanItem
) -> None:
    if response.get("type") != "lookup" or response.get("live") is not True:
        raise DocketLiveFetchError(
            "live docket response must prove a completed live lookup"
        )
    fees = _mapping(response.get("pacerFees"), "live docket pacerFees")
    service_fee = _decimal(fees.get("serviceFee"), "pacerFees.serviceFee")
    max_pacer_cost = _decimal(fees.get("maxPacerCost"), "pacerFees.maxPacerCost")
    if service_fee + max_pacer_cost > item.reservation_usd:
        raise DocketLiveFetchError(
            "live docket response fees exceed the frozen reservation"
        )


def _plan_item(record: Mapping[str, object]) -> DocketLiveFetchPlanItem:
    return DocketLiveFetchPlanItem(
        candidate_id=_required_text(record, "candidate_id"),
        docket_id=_required_text(record, "docket_id"),
        decision_date=_required_text(record, "decision_date"),
        decision_entry_ids=_string_tuple(
            record.get("decision_entry_ids"), "decision_entry_ids"
        ),
        existing_free_required_document_count=_optional_int(
            record, "existing_free_required_document_count"
        ),
        existing_missing_required_document_count=_optional_int(
            record, "existing_missing_required_document_count"
        ),
        docket_entry_count=_optional_int(record, "docket_entry_count"),
        reservation_usd=_decimal(record.get("reservation_usd"), "reservation_usd"),
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _decimal(value: object, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a decimal dollar amount") from exc
    if amount < 0:
        raise ValueError(f"{label} cannot be negative")
    return amount.quantize(Decimal("0.01"))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_int(record: Mapping[str, object], field: str) -> int | None:
    value = record.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer or null")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array of non-empty strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) and item for item in items):
        raise ValueError(f"{label} must be an array of non-empty strings")
    return tuple(cast(list[str], items))

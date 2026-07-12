"""Fail-closed completeness proofs for paginated CourtListener RECAP searches.

CourtListener groups matching documents into docket-level result articles.  Its
title count and pagination contract therefore reconcile against result groups,
not the number of document links emitted by the parser.  This module captures
that distinction explicitly and never treats a fetched sweep as saturated until
the page-one contract, every page, cross-page identities, and a fresh page-one
verification all agree.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from legalforecast.ingestion.firecrawl_recap_discovery import RecapSearchPage

RECAP_RESULT_WINDOW_PAGE_LIMIT = 100


class RecapSweepPreflightState(StrEnum):
    """Whether a page-one observation authorizes the declared sweep."""

    READY = "ready"
    PARTITION_REQUIRED = "partition_required"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    GROUPING_UNRECONCILED = "grouping_unreconciled"


class RecapProofState(StrEnum):
    """Terminal proof state for one term and one date partition."""

    PROVEN_COMPLETE = "proven_complete"
    PREFLIGHT_BLOCKED = "preflight_blocked"
    INCOMPLETE_PAGE_SET = "incomplete_page_set"
    UNSTABLE_TOTALS = "unstable_totals"
    RESULT_SHIFT_DETECTED = "result_shift_detected"
    FRESH_VERIFICATION_REQUIRED = "fresh_verification_required"
    COUNT_UNRECONCILED = "count_unreconciled"


class RecapCountBasis(StrEnum):
    """The only supported CourtListener result-count reconciliation basis."""

    GROUPS = "docket_result_groups"
    UNRECONCILED = "unreconciled"


@dataclass(frozen=True, slots=True)
class RecapSweepPreflight:
    """Frozen page-one contract and budget decision for one search partition."""

    state: RecapSweepPreflightState
    reason: str
    observation_id: str
    search_identity: tuple[str, str, str]
    page_one_fingerprint: str
    declared_total_results: int
    declared_total_pages: int
    groups_per_full_page: int
    expected_final_page_groups: int
    configured_page_limit: int
    accessible_page_limit: int
    remaining_credit_budget: int
    required_remaining_fetches: int
    required_remaining_credit_reservation: int

    @property
    def can_sweep(self) -> bool:
        return self.state is RecapSweepPreflightState.READY

    @property
    def partition_required(self) -> bool:
        return self.state is RecapSweepPreflightState.PARTITION_REQUIRED


@dataclass(frozen=True, slots=True)
class RecapSearchCompletenessProof:
    """Auditable terminal result that defaults to no saturation proof."""

    state: RecapProofState
    reason: str
    saturation_proven: bool
    count_basis: RecapCountBasis
    search_identity: tuple[str, str, str]
    declared_total_results: int
    declared_total_pages: int
    observed_page_count: int
    observed_entry_count: int
    observed_group_count: int

    @property
    def complete(self) -> bool:
        return self.saturation_proven


@dataclass(frozen=True, slots=True)
class _PageEvidence:
    page_number: int
    search_identity: tuple[str, str, str]
    total_results: int
    total_pages: int
    entry_keys: tuple[str, ...]
    group_keys: tuple[str, ...]
    fingerprint: str
    has_next: bool


def preflight_recap_search_sweep(
    page_one: RecapSearchPage,
    *,
    observation_id: str,
    configured_page_limit: int,
    remaining_credit_budget: int,
    credits_per_attempt: int,
    max_attempts_per_page: int,
) -> RecapSweepPreflight:
    """Evaluate page one before authorizing any remaining page requests.

    The remaining reservation includes pages two through the declared terminal
    page plus one fresh page-one verification after the sweep.  Attempt ceilings
    are included so the authorization remains valid under worst-case retries.
    """

    if page_one.target.page != 1:
        raise ValueError("preflight requires an actual RECAP page one")
    normalized_observation_id = _nonempty_id(observation_id, "observation_id")
    _positive_int(configured_page_limit, "configured_page_limit")
    _nonnegative_int(remaining_credit_budget, "remaining_credit_budget")
    _positive_int(credits_per_attempt, "credits_per_attempt")
    _positive_int(max_attempts_per_page, "max_attempts_per_page")

    evidence = _page_evidence(page_one)
    group_count = len(evidence.group_keys)
    grouping_reason = _page_one_grouping_contract_error(
        total_results=evidence.total_results,
        total_pages=evidence.total_pages,
        page_one_groups=group_count,
        page_one_has_next=evidence.has_next,
    )
    accessible_page_limit = min(configured_page_limit, RECAP_RESULT_WINDOW_PAGE_LIMIT)
    required_remaining_fetches = evidence.total_pages
    required_credit_reservation = (
        required_remaining_fetches * credits_per_attempt * max_attempts_per_page
    )
    expected_final_groups = (
        0
        if grouping_reason is not None
        else _expected_final_page_groups(
            total_results=evidence.total_results,
            total_pages=evidence.total_pages,
            groups_per_full_page=group_count,
        )
    )

    if grouping_reason is not None:
        state = RecapSweepPreflightState.GROUPING_UNRECONCILED
        reason = grouping_reason
    elif evidence.total_pages > accessible_page_limit:
        state = RecapSweepPreflightState.PARTITION_REQUIRED
        reason = (
            "declared RECAP sweep exceeds the effective 100-page result window; "
            "partition the entry-date window before fetching page two"
            if evidence.total_pages > RECAP_RESULT_WINDOW_PAGE_LIMIT
            else "declared RECAP sweep exceeds the configured page limit; "
            "partition the entry-date window before fetching page two"
        )
    elif required_credit_reservation > remaining_credit_budget:
        state = RecapSweepPreflightState.INSUFFICIENT_CREDITS
        reason = (
            "remaining Firecrawl credits cannot reserve the declared sweep and "
            "fresh page-one verification"
        )
    else:
        state = RecapSweepPreflightState.READY
        reason = "page-one grouping, page, and credit contracts are satisfied"

    return RecapSweepPreflight(
        state=state,
        reason=reason,
        observation_id=normalized_observation_id,
        search_identity=evidence.search_identity,
        page_one_fingerprint=evidence.fingerprint,
        declared_total_results=evidence.total_results,
        declared_total_pages=evidence.total_pages,
        groups_per_full_page=group_count,
        expected_final_page_groups=expected_final_groups,
        configured_page_limit=configured_page_limit,
        accessible_page_limit=accessible_page_limit,
        remaining_credit_budget=remaining_credit_budget,
        required_remaining_fetches=required_remaining_fetches,
        required_remaining_credit_reservation=required_credit_reservation,
    )


def prove_recap_search_sweep(
    *,
    preflight: RecapSweepPreflight,
    pages: Sequence[RecapSearchPage],
    final_page_one: RecapSearchPage | None,
    final_page_one_observation_id: str | None,
) -> RecapSearchCompletenessProof:
    """Return a proof result without ever overclaiming an incomplete sweep."""

    evidence_pages = tuple(_page_evidence(page) for page in pages)
    observed_entries = sum(len(page.entry_keys) for page in evidence_pages)
    observed_groups = sum(len(page.group_keys) for page in evidence_pages)

    def result(
        state: RecapProofState,
        reason: str,
        *,
        proven: bool = False,
        count_basis: RecapCountBasis = RecapCountBasis.UNRECONCILED,
    ) -> RecapSearchCompletenessProof:
        return RecapSearchCompletenessProof(
            state=state,
            reason=reason,
            saturation_proven=proven,
            count_basis=count_basis,
            search_identity=preflight.search_identity,
            declared_total_results=preflight.declared_total_results,
            declared_total_pages=preflight.declared_total_pages,
            observed_page_count=len(evidence_pages),
            observed_entry_count=observed_entries,
            observed_group_count=observed_groups,
        )

    if not preflight.can_sweep:
        return result(
            RecapProofState.PREFLIGHT_BLOCKED,
            f"preflight did not authorize the sweep: {preflight.reason}",
        )

    expected_page_numbers = tuple(range(1, preflight.declared_total_pages + 1))
    observed_page_numbers = tuple(page.page_number for page in evidence_pages)
    if observed_page_numbers != expected_page_numbers:
        return result(
            RecapProofState.INCOMPLETE_PAGE_SET,
            "observed RECAP pages do not exactly match the declared page sequence",
        )
    if evidence_pages[0].fingerprint != preflight.page_one_fingerprint:
        return result(
            RecapProofState.RESULT_SHIFT_DETECTED,
            "sweep page one no longer matches the frozen preflight fingerprint",
        )

    for page in evidence_pages:
        if page.search_identity != preflight.search_identity:
            return result(
                RecapProofState.INCOMPLETE_PAGE_SET,
                "observed page belongs to a different term or date partition",
            )
        if (
            page.total_results != preflight.declared_total_results
            or page.total_pages != preflight.declared_total_pages
        ):
            return result(
                RecapProofState.UNSTABLE_TOTALS,
                "CourtListener totals changed after the page-one preflight",
            )
        should_have_next = page.page_number < preflight.declared_total_pages
        if page.has_next is not should_have_next:
            return result(
                RecapProofState.INCOMPLETE_PAGE_SET,
                "page continuation state disagrees with the declared terminal page",
            )
        expected_groups = (
            preflight.expected_final_page_groups
            if page.page_number == preflight.declared_total_pages
            else preflight.groups_per_full_page
        )
        if len(page.group_keys) != expected_groups:
            return result(
                RecapProofState.COUNT_UNRECONCILED,
                "result-group count violates the page-one grouping contract",
            )

    seen_entries: set[str] = set()
    seen_groups: set[str] = set()
    for page in evidence_pages:
        entry_overlap = seen_entries.intersection(page.entry_keys)
        if entry_overlap:
            return result(
                RecapProofState.RESULT_SHIFT_DETECTED,
                "entry overlap across pages indicates a shifted result window",
            )
        group_overlap = seen_groups.intersection(page.group_keys)
        if group_overlap:
            return result(
                RecapProofState.RESULT_SHIFT_DETECTED,
                "docket result-group overlap across pages indicates a shifted window",
            )
        if len(page.entry_keys) != len(set(page.entry_keys)):
            return result(
                RecapProofState.RESULT_SHIFT_DETECTED,
                "duplicate entry identity within a page prevents completeness proof",
            )
        if len(page.group_keys) != len(set(page.group_keys)):
            return result(
                RecapProofState.RESULT_SHIFT_DETECTED,
                "duplicate docket result group within a page prevents proof",
            )
        seen_entries.update(page.entry_keys)
        seen_groups.update(page.group_keys)

    normalized_final_observation_id = (
        final_page_one_observation_id.strip()
        if final_page_one_observation_id is not None
        else None
    )
    if (
        final_page_one is None
        or not normalized_final_observation_id
        or normalized_final_observation_id == preflight.observation_id
    ):
        return result(
            RecapProofState.FRESH_VERIFICATION_REQUIRED,
            "a distinct, uncached page-one observation is required after the sweep",
        )
    final_evidence = _page_evidence(final_page_one)
    if final_evidence.page_number != 1:
        return result(
            RecapProofState.FRESH_VERIFICATION_REQUIRED,
            "final verification observation is not page one",
        )
    if (
        final_evidence.search_identity != preflight.search_identity
        or final_evidence.total_results != preflight.declared_total_results
        or final_evidence.total_pages != preflight.declared_total_pages
    ):
        return result(
            RecapProofState.UNSTABLE_TOTALS,
            "fresh page-one verification changed the search identity or totals",
        )
    if final_evidence.fingerprint != preflight.page_one_fingerprint:
        return result(
            RecapProofState.RESULT_SHIFT_DETECTED,
            "fresh page-one fingerprint changed after the sweep",
        )

    if observed_groups != preflight.declared_total_results:
        return result(
            RecapProofState.COUNT_UNRECONCILED,
            "observed docket result groups do not reconcile to the declared total",
        )
    return result(
        RecapProofState.PROVEN_COMPLETE,
        "stable totals, exact group counts, disjoint pages, and fresh page one agree",
        proven=True,
        count_basis=RecapCountBasis.GROUPS,
    )


def _page_evidence(page: RecapSearchPage) -> _PageEvidence:
    search_identity = (
        page.target.term,
        page.target.entry_date_filed_after.isoformat(),
        page.target.entry_date_filed_before.isoformat(),
    )
    grouped_dockets: dict[int, str] = {}
    ordered_entries: list[tuple[int, int, str, str, str]] = []
    for hit in page.hits:
        provenance = hit.provenance
        if provenance.page != page.target.page:
            raise ValueError("RECAP hit provenance page disagrees with its page")
        existing_docket = grouped_dockets.setdefault(
            provenance.result_ordinal, hit.docket_id
        )
        if existing_docket != hit.docket_id:
            raise ValueError("one RECAP result group contains multiple dockets")
        ordered_entries.append(
            (
                provenance.result_ordinal,
                provenance.entry_ordinal,
                hit.entry_key,
                hit.docket_id,
                hit.entry_date_filed.isoformat(),
            )
        )
    group_ordinals = tuple(sorted(grouped_dockets))
    if group_ordinals and group_ordinals != tuple(range(1, len(group_ordinals) + 1)):
        raise ValueError("RECAP result-group ordinals are not contiguous")
    ordered_entries.sort(key=lambda item: (item[0], item[1]))
    group_keys = tuple(grouped_dockets[ordinal] for ordinal in group_ordinals)
    entry_keys = tuple(item[2] for item in ordered_entries)
    fingerprint_payload = {
        "page": page.target.page,
        "total_results": page.total_results,
        "total_pages": page.total_pages,
        "groups": group_keys,
        "entries": ordered_entries,
        "has_next": page.next_url is not None,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return _PageEvidence(
        page_number=page.target.page,
        search_identity=search_identity,
        total_results=page.total_results,
        total_pages=page.total_pages,
        entry_keys=entry_keys,
        group_keys=group_keys,
        fingerprint=fingerprint,
        has_next=page.next_url is not None,
    )


def _page_one_grouping_contract_error(
    *,
    total_results: int,
    total_pages: int,
    page_one_groups: int,
    page_one_has_next: bool,
) -> str | None:
    if total_results == 0:
        if total_pages != 1 or page_one_groups != 0 or page_one_has_next:
            return "zero-result page one has inconsistent pages or result groups"
        return None
    if total_pages <= 0 or page_one_groups <= 0:
        return "nonzero page one lacks a positive page or result-group contract"
    if page_one_has_next is not (total_pages > 1):
        return "page-one continuation disagrees with the declared page count"
    expected_pages = (total_results + page_one_groups - 1) // page_one_groups
    if expected_pages != total_pages:
        return (
            "declared total pages cannot be reconciled to the page-one "
            "docket-result-group capacity"
        )
    return None


def _expected_final_page_groups(
    *, total_results: int, total_pages: int, groups_per_full_page: int
) -> int:
    if total_results == 0:
        return 0
    return total_results - groups_per_full_page * (total_pages - 1)


def _nonempty_id(value: str, name: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def _positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonnegative_int(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")

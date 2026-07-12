from __future__ import annotations

from datetime import date

import pytest
from legalforecast.ingestion.firecrawl_recap_discovery import (
    RecapSearchHit,
    RecapSearchPage,
    RecapSearchProvenance,
    RecapSearchTarget,
    build_recap_search_url,
)
from legalforecast.ingestion.recap_search_completeness import (
    RECAP_RESULT_WINDOW_PAGE_LIMIT,
    RecapCountBasis,
    RecapProofState,
    RecapSweepPreflight,
    RecapSweepPreflightState,
    preflight_recap_search_sweep,
    prove_recap_search_sweep,
)

ANCHOR = date(2026, 6, 30)
WINDOW_END = date(2026, 7, 12)
TERM = "motion to dismiss"


def _hit(
    *,
    page: int,
    entry_number: int,
    docket_id: str | None = None,
    result_ordinal: int = 1,
    entry_ordinal: int = 1,
) -> RecapSearchHit:
    normalized_docket_id = docket_id or str(10_000 + entry_number)
    document_number = str(entry_number)
    source_url = build_recap_search_url(
        term=TERM,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=page,
    )
    return RecapSearchHit(
        entry_key=f"{normalized_docket_id}:document:{document_number}",
        docket_id=normalized_docket_id,
        docket_entry_id=None,
        document_number=document_number,
        attachment_number=None,
        docket_url=(
            f"https://www.courtlistener.com/docket/{normalized_docket_id}/case/"
        ),
        document_url=(
            "https://www.courtlistener.com/docket/"
            f"{normalized_docket_id}/{document_number}/case/"
        ),
        entry_date_filed=date(2026, 7, 2),
        case_name=f"Case {normalized_docket_id}",
        description="Order on motion to dismiss",
        is_available=True,
        provenance=RecapSearchProvenance(
            query_term=TERM,
            search_url=source_url,
            page=page,
            result_ordinal=result_ordinal,
            entry_ordinal=entry_ordinal,
            raw_html_sha256=f"{page:064x}",
        ),
    )


def _page(
    page_number: int,
    *,
    total_results: int,
    total_pages: int,
    hits: tuple[RecapSearchHit, ...],
) -> RecapSearchPage:
    target = RecapSearchTarget(
        term=TERM,
        entry_date_filed_after=ANCHOR,
        entry_date_filed_before=WINDOW_END,
        page=page_number,
        url=build_recap_search_url(
            term=TERM,
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            page=page_number,
        ),
    )
    next_url = (
        build_recap_search_url(
            term=TERM,
            entry_date_filed_after=ANCHOR,
            entry_date_filed_before=WINDOW_END,
            page=page_number + 1,
        )
        if page_number < total_pages
        else None
    )
    return RecapSearchPage(
        target=target,
        hits=hits,
        total_results=total_results,
        total_pages=total_pages,
        next_url=next_url,
    )


def test_page_one_preflight_proves_sweep_fits_page_and_credit_ceilings() -> None:
    page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=1),),
    )

    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=1_000,
        remaining_credit_budget=30,
        credits_per_attempt=5,
        max_attempts_per_page=3,
    )

    assert preflight.state is RecapSweepPreflightState.READY
    assert preflight.can_sweep is True
    assert preflight.declared_total_pages == 2
    assert preflight.accessible_page_limit == RECAP_RESULT_WINDOW_PAGE_LIMIT
    # Page two plus a fresh page-one verification, each with up to 3 attempts.
    assert preflight.required_remaining_fetches == 2
    assert preflight.required_remaining_credit_reservation == 30


def test_preflight_requires_partition_before_page_101_result_window() -> None:
    page_one_hits = tuple(
        _hit(
            page=1,
            entry_number=entry_number,
            docket_id=str(10_000 + (entry_number + 1) // 2),
            result_ordinal=(entry_number + 1) // 2,
            entry_ordinal=1 if entry_number % 2 else 2,
        )
        for entry_number in range(1, 21)
    )
    page_one = _page(
        1,
        total_results=12_000,
        total_pages=1_200,
        hits=page_one_hits,
    )

    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=1_000,
        remaining_credit_budget=45_000,
        credits_per_attempt=5,
        max_attempts_per_page=3,
    )

    assert RECAP_RESULT_WINDOW_PAGE_LIMIT == 100
    assert preflight.state is RecapSweepPreflightState.PARTITION_REQUIRED
    assert preflight.can_sweep is False
    assert preflight.partition_required is True
    assert preflight.groups_per_full_page == 10
    assert "100-page" in preflight.reason


def test_preflight_fails_closed_when_remaining_credits_cannot_cover_sweep() -> None:
    page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=1),),
    )

    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=29,
        credits_per_attempt=5,
        max_attempts_per_page=3,
    )

    assert preflight.state is RecapSweepPreflightState.INSUFFICIENT_CREDITS
    assert preflight.can_sweep is False
    assert preflight.required_remaining_credit_reservation == 30


def test_preflight_requires_an_actual_page_one_observation() -> None:
    page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )

    with pytest.raises(ValueError, match="page one"):
        preflight_recap_search_sweep(
            page_two,
            observation_id="attempt-page-2",
            configured_page_limit=100,
            remaining_credit_budget=100,
            credits_per_attempt=5,
            max_attempts_per_page=1,
        )


def _ready_two_page_preflight() -> tuple[RecapSearchPage, RecapSweepPreflight]:
    page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=1),),
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=20,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )
    return page_one, preflight


def test_complete_stable_sweep_proves_saturation() -> None:
    page_one, preflight = _ready_two_page_preflight()
    page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )
    final_page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=1),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, page_two),
        final_page_one=final_page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.PROVEN_COMPLETE
    assert proof.saturation_proven is True
    assert proof.complete is True
    assert proof.count_basis is RecapCountBasis.GROUPS
    assert proof.observed_entry_count == 2
    assert proof.observed_group_count == 2


def test_stable_totals_are_required_across_every_page() -> None:
    page_one, preflight = _ready_two_page_preflight()
    shifted_total_page_two = _page(
        2,
        total_results=3,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, shifted_total_page_two),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.UNSTABLE_TOTALS
    assert proof.saturation_proven is False


def test_entry_overlap_across_pages_is_detected_as_result_shift() -> None:
    page_one, preflight = _ready_two_page_preflight()
    overlapping_page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=1),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, overlapping_page_two),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.RESULT_SHIFT_DETECTED
    assert "entry overlap" in proof.reason
    assert proof.saturation_proven is False


def test_group_overlap_is_detected_even_when_entry_keys_differ() -> None:
    page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=1, docket_id="12345"),),
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=20,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )
    same_group_page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2, docket_id="12345"),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, same_group_page_two),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.RESULT_SHIFT_DETECTED
    assert "group overlap" in proof.reason


def test_missing_page_cannot_claim_complete() -> None:
    page_one, preflight = _ready_two_page_preflight()

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one,),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.INCOMPLETE_PAGE_SET
    assert proof.complete is False


@pytest.mark.parametrize(
    "verification_id",
    [None, "attempt-page-1-initial"],
)
def test_fresh_page_one_verification_is_required(
    verification_id: str | None,
) -> None:
    page_one, preflight = _ready_two_page_preflight()
    page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, page_two),
        final_page_one=page_one if verification_id is not None else None,
        final_page_one_observation_id=verification_id,
    )

    assert proof.state is RecapProofState.FRESH_VERIFICATION_REQUIRED
    assert proof.saturation_proven is False


def test_changed_page_one_fingerprint_detects_result_shift() -> None:
    page_one, preflight = _ready_two_page_preflight()
    page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )
    shifted_page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=99),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, page_two),
        final_page_one=shifted_page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.RESULT_SHIFT_DETECTED
    assert "page-one fingerprint" in proof.reason


def test_sweep_page_one_must_match_the_frozen_preflight_observation() -> None:
    _page_one, preflight = _ready_two_page_preflight()
    shifted_page_one = _page(
        1,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=1, entry_number=99),),
    )
    page_two = _page(
        2,
        total_results=2,
        total_pages=2,
        hits=(_hit(page=2, entry_number=2),),
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(shifted_page_one, page_two),
        final_page_one=shifted_page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.RESULT_SHIFT_DETECTED
    assert "preflight fingerprint" in proof.reason


def test_unreconciled_page_one_grouping_is_exposed_instead_of_overclaimed() -> None:
    page_one = _page(
        1,
        total_results=3,
        total_pages=1,
        hits=(_hit(page=1, entry_number=1),),
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=5,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one,),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert preflight.state is RecapSweepPreflightState.GROUPING_UNRECONCILED
    assert proof.state is RecapProofState.PREFLIGHT_BLOCKED
    assert proof.count_basis is RecapCountBasis.UNRECONCILED
    assert proof.saturation_proven is False
    assert proof.declared_total_results == 3
    assert proof.observed_entry_count == 1
    assert proof.observed_group_count == 1


def test_grouped_count_can_reconcile_when_one_group_contains_multiple_hits() -> None:
    grouped_hits = (
        _hit(
            page=1,
            entry_number=1,
            docket_id="12345",
            result_ordinal=1,
            entry_ordinal=1,
        ),
        _hit(
            page=1,
            entry_number=2,
            docket_id="12345",
            result_ordinal=1,
            entry_ordinal=2,
        ),
        _hit(
            page=1,
            entry_number=3,
            docket_id="67890",
            result_ordinal=2,
            entry_ordinal=1,
        ),
    )
    page_one = _page(
        1,
        total_results=2,
        total_pages=1,
        hits=grouped_hits,
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=5,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one,),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert proof.state is RecapProofState.PROVEN_COMPLETE
    assert proof.count_basis is RecapCountBasis.GROUPS
    assert proof.observed_entry_count == 3
    assert proof.observed_group_count == 2
    assert proof.saturation_proven is True


def test_terminal_page_may_have_fewer_groups_than_page_one_capacity() -> None:
    page_one_hits = tuple(
        _hit(
            page=1,
            entry_number=entry_number,
            result_ordinal=entry_number,
        )
        for entry_number in range(1, 11)
    )
    page_one = _page(
        1,
        total_results=12,
        total_pages=2,
        hits=page_one_hits,
    )
    page_two = _page(
        2,
        total_results=12,
        total_pages=2,
        hits=(
            _hit(page=2, entry_number=11, result_ordinal=1),
            _hit(page=2, entry_number=12, result_ordinal=2),
        ),
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=10,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one, page_two),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert preflight.expected_final_page_groups == 2
    assert proof.state is RecapProofState.PROVEN_COMPLETE
    assert proof.observed_group_count == 12


def test_zero_result_partition_requires_fresh_verification_then_proves_complete() -> (
    None
):
    page_one = _page(
        1,
        total_results=0,
        total_pages=1,
        hits=(),
    )
    preflight = preflight_recap_search_sweep(
        page_one,
        observation_id="attempt-page-1-initial",
        configured_page_limit=100,
        remaining_credit_budget=5,
        credits_per_attempt=5,
        max_attempts_per_page=1,
    )

    proof = prove_recap_search_sweep(
        preflight=preflight,
        pages=(page_one,),
        final_page_one=page_one,
        final_page_one_observation_id="attempt-page-1-verification",
    )

    assert preflight.state is RecapSweepPreflightState.READY
    assert preflight.groups_per_full_page == 0
    assert proof.state is RecapProofState.PROVEN_COMPLETE
    assert proof.count_basis is RecapCountBasis.GROUPS
    assert proof.saturation_proven is True

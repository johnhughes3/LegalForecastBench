"""Cost math, cheapest-first admission, replay, and purchase-ceiling."""

from __future__ import annotations

from decimal import Decimal

import pytest
from legalforecast.config import SpendCeiling, StratificationPolicy, usd
from legalforecast.document_need.artifact import (
    DocumentNeedArtifactError,
    build_selection_artifact,
    project_purchase_ceiling,
    replay_selection_artifact,
)
from legalforecast.document_need.costs import price_case, price_document
from legalforecast.document_need.cycle_config import (
    DocumentNeedConfigError,
    document_need_view_from_cycle_config,
)
from legalforecast.document_need.protocol import MergedCaseBuckets
from legalforecast.document_need.ranking import rank_cases
from legalforecast.document_need.types import (
    Chronology,
    ChronologyEntry,
    DocketDocument,
    EntryVerdict,
    NeedBucket,
)
from tests.document_need_fixtures import (
    activated_haiku_config,
    inert_cycle_2,
    luna_on_cycle1_registry,
)


def _doc(
    *,
    paid: bool,
    pages: int | None,
    selector: str = "main_document",
    description: str = "doc",
    restricted: bool = False,
) -> DocketDocument:
    return DocketDocument(
        selector=selector,
        description=description,
        freely_available=not paid,
        pacer_only=paid,
        page_count=pages,
        restricted=restricted,
    )


def _case(
    candidate_id: str,
    *,
    required_pages: int,
    conditional_pages: int | None = None,
    notice_pages: int = 1,
    restricted_motion: bool = False,
) -> tuple[Chronology, MergedCaseBuckets]:
    entries = (
        ChronologyEntry(
            entry=1,
            filed="2026-01-01",
            text="Complaint.",
            documents=(_doc(paid=False, pages=5, description="complaint"),),
        ),
        ChronologyEntry(
            entry=10,
            filed="2026-02-01",
            text="Motion.",
            documents=(
                _doc(
                    paid=True,
                    pages=required_pages,
                    description="mtd",
                    restricted=restricted_motion,
                ),
            ),
        ),
        ChronologyEntry(
            entry=12,
            filed="2026-02-10",
            text="Response.",
            documents=(
                _doc(
                    paid=True,
                    pages=5 if conditional_pages is None else conditional_pages,
                    description="opp",
                ),
            ),
        ),
        ChronologyEntry(
            entry=15,
            filed="2026-02-11",
            text="Notice.",
            documents=(_doc(paid=True, pages=notice_pages, description="notice"),),
        ),
    )
    chronology = Chronology(
        candidate_id=candidate_id,
        case_name=candidate_id,
        court="nysd",
        docket_number=f"1:26-cv-{candidate_id}",
        target_motion_entries=(10,),
        decision_cut_entry=20,
        entries=entries,
    )
    merged = MergedCaseBuckets(
        candidate_id=candidate_id,
        pass1_model_id="fixture:document-need-v1",
        pass2_model_id="fixture:document-need-v1",
        entries=(
            EntryVerdict(1, NeedBucket.CLEARLY_REQUIRED, "complaint", "pleading"),
            EntryVerdict(10, NeedBucket.CLEARLY_REQUIRED, "mtd_memorandum", "motion"),
            EntryVerdict(12, NeedBucket.CONDITIONAL, "opposition", "maybe"),
            EntryVerdict(15, NeedBucket.CLEARLY_NOT_REQUIRED, None, "notice"),
        ),
        promotions=(),
    )
    return chronology, merged


def test_free_first_zeroes_freely_available_document() -> None:
    view = document_need_view_from_cycle_config(activated_haiku_config())
    free = _doc(paid=False, pages=40)
    paid = _doc(paid=True, pages=40)
    assert price_document(
        free,
        free_first=view.free_first,
        per_page=view.pacer_per_page_usd,
        cap=view.per_document_price_cap_usd,
    ) == Decimal("0.00")
    assert price_document(
        paid,
        free_first=view.free_first,
        per_page=view.pacer_per_page_usd,
        cap=view.per_document_price_cap_usd,
    ) == Decimal("3.00")


def test_unknown_page_count_uses_per_document_cap() -> None:
    view = document_need_view_from_cycle_config(activated_haiku_config())
    assert price_document(
        _doc(paid=True, pages=None),
        free_first=True,
        per_page=view.pacer_per_page_usd,
        cap=view.per_document_price_cap_usd,
    ) == Decimal("3.00")


def test_min_max_from_required_and_conditional() -> None:
    view = document_need_view_from_cycle_config(activated_haiku_config())
    chronology, merged = _case("case-a", required_pages=10, conditional_pages=8)
    costs = price_case(chronology, {row.entry: row for row in merged.entries}, view)
    # required paid 10 pages * 0.10 = 1.00; complaint is free
    assert costs.min_cost == Decimal("1.00")
    # conditional 8 pages * 0.10 = 0.80
    assert costs.max_cost == Decimal("1.80")


def test_price_perturbation_changes_min_max_and_rank() -> None:
    config = activated_haiku_config()
    cheap_c, cheap_m = _case("aaa", required_pages=5, conditional_pages=5)
    dear_c, dear_m = _case("bbb", required_pages=6, conditional_pages=5)
    artifact = build_selection_artifact(
        config=config,
        chronologies=(cheap_c, dear_c),
        merged=(cheap_m, dear_m),
        cohort_target_n=2,
    )
    assert [row.ranked.candidate_id for row in artifact.cases] == ["aaa", "bbb"]
    replay_selection_artifact(
        artifact,
        config=config,
        chronologies=(cheap_c, dear_c),
        merged=(cheap_m, dear_m),
        cohort_target_n=2,
    )
    bumped = Chronology(
        candidate_id="aaa",
        case_name="aaa",
        court="nysd",
        docket_number="1:26-cv-aaa",
        target_motion_entries=(10,),
        decision_cut_entry=20,
        entries=(
            cheap_c.entries[0],
            ChronologyEntry(
                entry=10,
                filed="2026-02-01",
                text="Motion.",
                documents=(_doc(paid=True, pages=20, description="mtd"),),
            ),
            cheap_c.entries[2],
            cheap_c.entries[3],
        ),
    )
    rebuilt = build_selection_artifact(
        config=config,
        chronologies=(bumped, dear_c),
        merged=(cheap_m, dear_m),
        cohort_target_n=2,
    )
    original_aaa = next(
        row for row in artifact.cases if row.ranked.candidate_id == "aaa"
    )
    rebuilt_aaa = next(row for row in rebuilt.cases if row.ranked.candidate_id == "aaa")
    assert rebuilt_aaa.ranked.min_cost != original_aaa.ranked.min_cost
    assert rebuilt_aaa.ranked.max_cost != original_aaa.ranked.max_cost
    assert rebuilt.cases[0].ranked.candidate_id == "bbb"
    assert rebuilt.sha256 != artifact.sha256
    with pytest.raises(DocumentNeedArtifactError, match="drifted"):
        replay_selection_artifact(
            artifact,
            config=config,
            chronologies=(bumped, dear_c),
            merged=(cheap_m, dear_m),
            cohort_target_n=2,
        )


def test_registry_selector_refused_end_to_end() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    with pytest.raises(DocumentNeedConfigError, match=r"gpt-5\.6-luna"):
        build_selection_artifact(
            config=luna_on_cycle1_registry(),
            chronologies=(chronology,),
            merged=(merged,),
            cohort_target_n=1,
        )


def test_stratification_cap_changes_admission_set() -> None:
    view_off_config = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=None)
    )
    pairs = [
        _case(f"c{index:02d}", required_pages=5 + index, conditional_pages=5)
        for index in range(10)
    ]
    chronologies = tuple(pair[0] for pair in pairs)
    merged = tuple(pair[1] for pair in pairs)
    off = build_selection_artifact(
        config=view_off_config,
        chronologies=chronologies,
        merged=merged,
        cohort_target_n=5,
    )
    off_admitted = [row.ranked.candidate_id for row in off.cases if row.admitted]
    view_on = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=None),
        stratification=StratificationPolicy(
            enabled=True, bottom_decile_share_cap=usd("0.00")
        ),
    )
    on = build_selection_artifact(
        config=view_on,
        chronologies=chronologies,
        merged=merged,
        cohort_target_n=5,
    )
    on_admitted = [row.ranked.candidate_id for row in on.cases if row.admitted]
    assert off_admitted != on_admitted
    cheapest = rank_cases(
        [
            price_case(
                chrono,
                {row.entry: row for row in verdict.entries},
                document_need_view_from_cycle_config(view_off_config),
            )
            for chrono, verdict in pairs
        ]
    )[0]
    assert cheapest.bottom_decile is True
    assert cheapest.candidate_id in off_admitted
    assert cheapest.candidate_id not in on_admitted
    assert len(on_admitted) == 5


def test_default_stratification_cap_admits_one_bottom_decile_in_ten() -> None:
    config = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=None),
        stratification=StratificationPolicy(
            enabled=True, bottom_decile_share_cap=usd("0.10")
        ),
    )
    pairs = [
        _case(f"c{index:02d}", required_pages=5 + index, conditional_pages=5)
        for index in range(10)
    ]
    artifact = build_selection_artifact(
        config=config,
        chronologies=tuple(pair[0] for pair in pairs),
        merged=tuple(pair[1] for pair in pairs),
        cohort_target_n=10,
    )
    admitted = [row.ranked.candidate_id for row in artifact.cases if row.admitted]
    cheapest = next(row for row in artifact.cases if row.ranked.cost_rank == 1)
    assert cheapest.ranked.bottom_decile is True
    assert cheapest.ranked.candidate_id in admitted
    assert cheapest.admitted is True
    assert len(admitted) == 10


def test_max_per_case_ceiling_rejects_over_limit_case() -> None:
    config = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("500.00"), max_per_case_usd=usd("1.20"))
    )
    cheap_c, cheap_m = _case("aaa", required_pages=5, conditional_pages=5)
    dear_c, dear_m = _case("bbb", required_pages=20, conditional_pages=20)
    artifact = build_selection_artifact(
        config=config,
        chronologies=(cheap_c, dear_c),
        merged=(cheap_m, dear_m),
        cohort_target_n=2,
    )
    by_id = {row.ranked.candidate_id: row for row in artifact.cases}
    assert by_id["aaa"].admitted is True
    assert by_id["bbb"].admitted is False
    assert by_id["bbb"].reject_reason == "max_per_case"


def test_restricted_required_document_is_not_admitted() -> None:
    sealed_c, sealed_m = _case("seal", required_pages=1, restricted_motion=True)
    open_c, open_m = _case("open", required_pages=20, conditional_pages=20)
    artifact = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(sealed_c, open_c),
        merged=(sealed_m, open_m),
        cohort_target_n=1,
    )
    by_id = {row.ranked.candidate_id: row for row in artifact.cases}
    assert by_id["seal"].ranked.restricted_required is True
    assert by_id["seal"].admitted is False
    assert by_id["seal"].reject_reason == "restricted_required_document"
    assert by_id["open"].admitted is True


def test_purchase_ceiling_is_sum_of_admitted_max_cost() -> None:
    config = activated_haiku_config()
    cheap_c, cheap_m = _case("aaa", required_pages=5, conditional_pages=5)
    dear_c, dear_m = _case("bbb", required_pages=20, conditional_pages=20)
    artifact = build_selection_artifact(
        config=config,
        chronologies=(cheap_c, dear_c),
        merged=(cheap_m, dear_m),
        cohort_target_n=1,
    )
    ceiling = project_purchase_ceiling(artifact)
    admitted = next(row for row in artifact.cases if row.admitted)
    assert ceiling.admitted_candidate_ids == ("aaa",)
    assert ceiling.ceiling_usd == admitted.ranked.max_cost
    assert "APPROVE cycle-2" in ceiling.confirmation_phrase
    assert ceiling.selection_sha256 == artifact.sha256


def test_inert_cycle_never_emits_artifact() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    with pytest.raises(DocumentNeedConfigError, match="not activated"):
        build_selection_artifact(
            config=inert_cycle_2(),
            chronologies=(chronology,),
            merged=(merged,),
            cohort_target_n=1,
        )

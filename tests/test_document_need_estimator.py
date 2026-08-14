"""Cost math, cheapest-first admission, replay, and purchase-ceiling."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from legalforecast.config import (
    EvaluationRegistryPin,
    SpendCeiling,
    StratificationPolicy,
    usd,
)
from legalforecast.document_need.artifact import (
    DocumentNeedArtifactError,
    build_selection_artifact,
    project_purchase_ceiling,
    replay_selection_artifact,
)
from legalforecast.document_need.costs import CaseCosts, price_case, price_document
from legalforecast.document_need.cycle_config import (
    CaseMixStratification,
    DocumentNeedConfigError,
    document_need_view_from_cycle_config,
    format_usd,
)
from legalforecast.document_need.protocol import MergedCaseBuckets
from legalforecast.document_need.ranking import RankedCase, admit_cheapest, rank_cases
from legalforecast.document_need.types import (
    Chronology,
    ChronologyEntry,
    DocketDocument,
    EntryVerdict,
    NeedBucket,
    Pass2Promotion,
)
from tests.document_need_fixtures import (
    HAIKU,
    ROOT,
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
    unavailable: bool = False,
) -> DocketDocument:
    return DocketDocument(
        selector=selector,
        description=description,
        freely_available=False if unavailable else not paid,
        pacer_only=False if unavailable else paid,
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
    restricted_conditional: bool = False,
    unavailable_motion: bool = False,
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
                    unavailable=unavailable_motion,
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
                    restricted=restricted_conditional,
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
        pass1_model_id=HAIKU.model_id,
        pass1_provider=HAIKU.provider,
        pass1_version=HAIKU.model_version_or_snapshot,
        pass2_model_id=HAIKU.model_id,
        pass2_provider=HAIKU.provider,
        pass2_version=HAIKU.model_version_or_snapshot,
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
        reservation=view.reservation_usd,
    ) == Decimal("0.00")
    assert price_document(
        paid,
        free_first=view.free_first,
        per_page=view.pacer_per_page_usd,
        cap=view.per_document_price_cap_usd,
        reservation=view.reservation_usd,
    ) == Decimal("3.05")


def test_unknown_page_count_uses_reservation() -> None:
    view = document_need_view_from_cycle_config(activated_haiku_config())
    assert price_document(
        _doc(paid=True, pages=None),
        free_first=True,
        per_page=view.pacer_per_page_usd,
        cap=view.per_document_price_cap_usd,
        reservation=view.reservation_usd,
    ) == Decimal("3.05")


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
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=usd("999.00"))
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
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=usd("999.00")),
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
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=usd("999.00")),
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


def test_stratification_quota_is_frozen_against_pass1_admitted_size() -> None:
    """Drop extras in one shot. Do not recompute quota as n shrinks (10→9→0)."""

    config = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("999.00"), max_per_case_usd=usd("999.00")),
        stratification=StratificationPolicy(
            enabled=True, bottom_decile_share_cap=usd("0.10")
        ),
    )
    pairs = [
        _case(f"c{index:02d}", required_pages=5 + index, conditional_pages=5)
        for index in range(20)
    ]
    artifact = build_selection_artifact(
        config=config,
        chronologies=tuple(pair[0] for pair in pairs),
        merged=tuple(pair[1] for pair in pairs),
        cohort_target_n=10,
    )
    admitted = [row for row in artifact.cases if row.admitted]
    bottoms = [row for row in admitted if row.ranked.bottom_decile]
    ranked = [row for row in artifact.cases if row.ranked.bottom_decile]
    assert len(ranked) == 2
    assert len(admitted) == 10
    assert len(bottoms) == 1
    assert ranked[0].admitted is True
    assert ranked[1].admitted is False
    assert ranked[1].reject_reason == "stratification_bottom_decile_cap"


def test_bottom_decile_share_is_revalidated_when_backfill_cannot_restore_n() -> None:
    """When extras drop 10→9 and backfill misses, final share must still be <= cap.

    Pass-1 quota stays frozen so a successful backfill can keep one bottom in
    ten. After backfill, revalidate against the final admitted size without
    repeating that 10→9→0 cascade during the first drop.
    """

    pairs = [
        _case(f"c{index:02d}", required_pages=5 + index, conditional_pages=5)
        for index in range(20)
    ]
    chronologies = tuple(pair[0] for pair in pairs)
    merged = tuple(pair[1] for pair in pairs)
    measured = build_selection_artifact(
        config=activated_haiku_config(
            spend=SpendCeiling(
                hard_cap_usd=usd("999.00"), max_per_case_usd=usd("999.00")
            )
        ),
        chronologies=chronologies,
        merged=merged,
        cohort_target_n=10,
    )
    first_ten = [row for row in measured.cases if row.admitted]
    assert len(first_ten) == 10
    ceiling = sum((row.ranked.max_cost for row in first_ten), Decimal("0.00"))
    ceiling_text = format_usd(ceiling)
    artifact = build_selection_artifact(
        config=activated_haiku_config(
            spend=SpendCeiling(
                hard_cap_usd=usd(ceiling_text), max_per_case_usd=usd(ceiling_text)
            ),
            stratification=StratificationPolicy(
                enabled=True, bottom_decile_share_cap=usd("0.10")
            ),
        ),
        chronologies=chronologies,
        merged=merged,
        cohort_target_n=10,
    )
    admitted = [row for row in artifact.cases if row.admitted]
    ranked_bottoms = [row for row in artifact.cases if row.ranked.bottom_decile]
    eleventh = next(row for row in measured.cases if row.ranked.cost_rank == 11)
    expected = {
        row.ranked.candidate_id for row in first_ten if not row.ranked.bottom_decile
    }
    expected.add(eleventh.ranked.candidate_id)
    assert {row.ranked.candidate_id for row in admitted} == expected
    assert len(ranked_bottoms) == 2
    assert all(row.admitted is False for row in ranked_bottoms)
    assert all(
        row.reject_reason == "stratification_bottom_decile_cap"
        for row in ranked_bottoms
    )
    share = Decimal(sum(1 for row in admitted if row.ranked.bottom_decile)) / Decimal(
        len(admitted)
    )
    assert share <= Decimal("0.10")


def test_bottom_decile_share_is_revalidated_until_stable() -> None:
    """A second failed backfill must not leave 1/9 over a 10% cap.

    Codex P1 on PR 741: 191 candidates costing 1..191, target 20, cap 0.10,
    spend 210. One revalidation pass still left rank 1 among nine admissions.
    """

    ranked = tuple(
        RankedCase(
            costs=CaseCosts(
                candidate_id=f"r{rank:03d}",
                min_cost=Decimal(rank),
                max_cost=Decimal(rank),
                entries=(),
                restricted_required=False,
            ),
            cost_rank=rank,
            bottom_decile=rank <= 20,
        )
        for rank in range(1, 192)
    )
    decisions = admit_cheapest(
        ranked,
        target_n=20,
        spend_ceiling=Decimal("210"),
        max_per_case=Decimal("210"),
        stratification=CaseMixStratification(
            enabled=True, bottom_decile_share_cap=Decimal("0.10")
        ),
    )
    admitted = [row for row in decisions if row.admitted]
    assert admitted
    share = Decimal(sum(1 for row in admitted if row.ranked.bottom_decile)) / Decimal(
        len(admitted)
    )
    assert share <= Decimal("0.10")
    assert all(not row.ranked.bottom_decile for row in admitted)


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


def test_restricted_conditional_document_is_not_admitted() -> None:
    sealed_c, sealed_m = _case("seal", required_pages=5, restricted_conditional=True)
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


def test_unavailable_required_document_is_not_admitted() -> None:
    ghost_c, ghost_m = _case("ghost", required_pages=5, unavailable_motion=True)
    open_c, open_m = _case("open", required_pages=20, conditional_pages=20)
    artifact = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(ghost_c, open_c),
        merged=(ghost_m, open_m),
        cohort_target_n=1,
    )
    by_id = {row.ranked.candidate_id: row for row in artifact.cases}
    assert by_id["ghost"].ranked.restricted_required is True
    assert by_id["ghost"].admitted is False
    assert by_id["ghost"].reject_reason == "restricted_required_document"
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


def test_verdict_model_must_match_selector_policy() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    tainted = replace(merged, pass1_model_id="gpt-5.6-luna")
    with pytest.raises(DocumentNeedArtifactError, match="pass1 selector"):
        build_selection_artifact(
            config=activated_haiku_config(),
            chronologies=(chronology,),
            merged=(tainted,),
            cohort_target_n=1,
        )


def test_verdict_must_bind_provider_not_just_model_id() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    tainted = replace(merged, pass1_provider="openai")
    with pytest.raises(DocumentNeedArtifactError, match="pass1 selector"):
        build_selection_artifact(
            config=activated_haiku_config(),
            chronologies=(chronology,),
            merged=(tainted,),
            cohort_target_n=1,
        )


def test_required_entry_with_no_documents_is_not_admitted() -> None:
    ghost_c, ghost_m = _case("ghost", required_pages=5)
    empty_motion = replace(ghost_c.entries[1], documents=())
    ghost_c = replace(
        ghost_c,
        entries=(
            ghost_c.entries[0],
            empty_motion,
            ghost_c.entries[2],
            ghost_c.entries[3],
        ),
    )
    open_c, open_m = _case("open", required_pages=20, conditional_pages=20)
    artifact = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(ghost_c, open_c),
        merged=(ghost_m, open_m),
        cohort_target_n=1,
    )
    by_id = {row.ranked.candidate_id: row for row in artifact.cases}
    assert by_id["ghost"].ranked.restricted_required is True
    assert by_id["ghost"].admitted is False
    assert by_id["ghost"].reject_reason == "restricted_required_document"
    assert by_id["open"].admitted is True


def test_stratification_cap_uses_final_admitted_size() -> None:
    config = activated_haiku_config(
        spend=SpendCeiling(hard_cap_usd=usd("6.00"), max_per_case_usd=usd("6.00")),
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
    admitted = [row for row in artifact.cases if row.admitted]
    cheapest = next(row for row in artifact.cases if row.ranked.cost_rank == 1)
    assert cheapest.ranked.bottom_decile is True
    assert cheapest.admitted is False
    assert cheapest.reject_reason == "stratification_bottom_decile_cap"
    assert all(not row.ranked.bottom_decile for row in admitted)
    share = Decimal(sum(1 for row in admitted if row.ranked.bottom_decile)) / Decimal(
        len(admitted)
    )
    assert share <= Decimal("0.10")


def test_failed_completeness_is_refused_at_artifact_boundary() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    tainted = replace(merged, completeness_ok=False)
    with pytest.raises(DocumentNeedArtifactError, match="completeness"):
        build_selection_artifact(
            config=activated_haiku_config(),
            chronologies=(chronology,),
            merged=(tainted,),
            cohort_target_n=1,
        )


def test_duplicate_merged_entry_verdicts_are_refused() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    tainted = replace(merged, entries=(*merged.entries, merged.entries[0]))
    with pytest.raises(DocumentNeedArtifactError, match="duplicate entry"):
        build_selection_artifact(
            config=activated_haiku_config(),
            chronologies=(chronology,),
            merged=(tainted,),
            cohort_target_n=1,
        )


def test_selection_digest_binds_evaluation_registry_bytes(tmp_path: Path) -> None:
    chronology, merged = _case("case-a", required_pages=5)
    registry = tmp_path / "eval.json"
    pin = EvaluationRegistryPin(path=str(registry))
    _write_disjoint_registry(registry, "other-a")
    first = build_selection_artifact(
        config=activated_haiku_config(evaluation_registry=pin),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    _write_disjoint_registry(registry, "other-b")
    second = build_selection_artifact(
        config=activated_haiku_config(evaluation_registry=pin),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    assert first.sha256 != second.sha256


def _write_disjoint_registry(path: Path, model_id: str) -> Path:
    source = json.loads(
        (ROOT / "model_registries" / "cycle-1-2026-06-30.json").read_text(
            encoding="utf-8"
        )
    )
    record = dict(source[0])
    record["provider"] = "openai"
    record["model_id"] = model_id
    record["model_version_or_snapshot"] = model_id
    record["display_name"] = model_id
    path.write_text(json.dumps([record]), encoding="utf-8")
    return path


def test_selection_digest_binds_approval_policy() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    baseline = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    config = activated_haiku_config()
    phrase_changed = replace(
        config,
        typed_confirmation=replace(
            config.typed_confirmation,
            phrase_template=config.typed_confirmation.phrase_template + " PIN",
        ),
    )
    rule_changed = replace(
        config,
        ranking=replace(config.ranking, purchase_rule="cheapest_first_manual_review"),
    )
    phrase_artifact = build_selection_artifact(
        config=phrase_changed,
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    rule_artifact = build_selection_artifact(
        config=rule_changed,
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    assert phrase_artifact.sha256 != baseline.sha256
    assert rule_artifact.sha256 != baseline.sha256
    assert "PIN" in phrase_artifact.purchase_ceiling.confirmation_phrase


def test_selection_digest_binds_admission_limits() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    baseline = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    tighter = build_selection_artifact(
        config=activated_haiku_config(
            spend=SpendCeiling(
                hard_cap_usd=usd("400.00"), max_per_case_usd=usd("400.00")
            )
        ),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    assert tighter.sha256 != baseline.sha256
    assert tighter.cases[0].admitted is True


def test_promotions_must_match_final_entry_verdicts() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    mismatched = replace(
        merged,
        promotions=(
            Pass2Promotion(
                entry=12,
                from_bucket=NeedBucket.CONDITIONAL,
                to_bucket=NeedBucket.CLEARLY_REQUIRED,
                rationale="stale reconstructed promotion",
                predecision_entry_cited=12,
            ),
        ),
    )
    with pytest.raises(DocumentNeedArtifactError, match="does not match entry"):
        build_selection_artifact(
            config=activated_haiku_config(),
            chronologies=(chronology,),
            merged=(mismatched,),
            cohort_target_n=1,
        )


def test_sealed_case_records_cannot_be_mutated_after_digest() -> None:
    chronology, merged = _case("case-a", required_pages=5)
    artifact = build_selection_artifact(
        config=activated_haiku_config(),
        chronologies=(chronology,),
        merged=(merged,),
        cohort_target_n=1,
    )
    record = artifact.case_records[0]
    with pytest.raises(TypeError):
        record["admitted"] = False
    exported = artifact.to_record()
    json.dumps(exported)
    case = exported["cases"]
    assert type(case) is list
    first = case[0]
    assert type(first) is dict
    assert type(first["promotions"]) is list
    assert type(exported["provenance"]) is dict
    first["admitted"] = False
    assert artifact.case_records[0]["admitted"] is True
    assert artifact.to_record()["sha256"] == artifact.sha256

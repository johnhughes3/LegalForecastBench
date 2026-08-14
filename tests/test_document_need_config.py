"""Document-need cycle-config view and registry preflight."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.config import (
    CYCLE_2_ID,
    CycleConfigNotActivatedError,
    EvaluationRegistryPin,
    load_activated_cycle,
    load_cycle,
)
from legalforecast.config.types import RankingSortKey, SortDirection
from legalforecast.document_need.cycle_config import (
    DocumentNeedConfigError,
    document_need_view_from_cycle_config,
    preflight_selector_models,
    require_activated_cycle,
)
from tests.document_need_fixtures import (
    ROOT,
    activated_haiku_config,
    cycle_1,
    inert_cycle_2,
    luna_on_cycle1_registry,
)


def test_view_loads_from_d1_cycle_2_public_record() -> None:
    view = document_need_view_from_cycle_config(load_cycle(CYCLE_2_ID))
    assert view.cycle_id == "cycle-2"
    assert view.activated is False
    assert view.selector_model_policy.primary == "gpt-5.6-luna"
    assert view.ranking_policy.primary == "max_cost"
    assert view.ranking_policy.tiebreak == ("min_cost", "candidate_id")
    assert view.case_mix_stratification.enabled is False
    assert view.spend_ceiling_usd is None
    assert view.max_per_case_usd is None


def test_cycle_1_ranking_is_not_a_document_need_view() -> None:
    with pytest.raises(DocumentNeedConfigError, match=r"ranking\.keys must be"):
        document_need_view_from_cycle_config(cycle_1())


def test_inert_cycle_is_refused() -> None:
    with pytest.raises(DocumentNeedConfigError, match="not activated"):
        require_activated_cycle(inert_cycle_2())
    with pytest.raises(DocumentNeedConfigError, match=r"dn9\.2"):
        require_activated_cycle(load_cycle(CYCLE_2_ID))


def test_load_activated_cycle_refuses_draft_cycle_2() -> None:
    with pytest.raises(CycleConfigNotActivatedError, match=r"dn9\.2"):
        load_activated_cycle(CYCLE_2_ID)


def test_preflight_accepts_cleared_haiku_against_cycle1_registry() -> None:
    preflight_selector_models(activated_haiku_config(), repository_root_path=ROOT)


def test_preflight_refuses_registry_selector() -> None:
    with pytest.raises(DocumentNeedConfigError, match=r"gpt-5\.6-luna"):
        preflight_selector_models(luna_on_cycle1_registry(), repository_root_path=ROOT)


def test_preflight_refuses_side_channel_registry_path(tmp_path: Path) -> None:
    config = replace(
        activated_haiku_config(),
        evaluation_registry=EvaluationRegistryPin(
            path=str(tmp_path / "does-not-exist.json")
        ),
    )
    with pytest.raises(DocumentNeedConfigError, match="does-not-exist"):
        preflight_selector_models(config, repository_root_path=ROOT)


def test_descending_ranking_direction_is_refused() -> None:
    config = activated_haiku_config()
    keys = tuple(
        RankingSortKey(key.attribute, SortDirection.DESCENDING) if index == 0 else key
        for index, key in enumerate(config.ranking.keys)
    )
    bad = replace(config, ranking=replace(config.ranking, keys=keys))
    with pytest.raises(DocumentNeedConfigError, match="ascending"):
        document_need_view_from_cycle_config(bad)

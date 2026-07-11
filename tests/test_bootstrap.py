from __future__ import annotations

import json

import pytest
from legalforecast.evals.bootstrap import (
    BootstrapConfig,
    ModelScoreInput,
    draw_cluster_samples,
    paired_clustered_bootstrap,
)
from legalforecast.evals.output_parser import ParserStatus
from legalforecast.evals.scorers import UnitScore


def test_draw_cluster_samples_is_seeded_and_samples_case_clusters() -> None:
    case_ids = ("case-1", "case-2", "case-3")

    first = draw_cluster_samples(case_ids, replicates=4, seed=123)
    second = draw_cluster_samples(case_ids, replicates=4, seed=123)

    assert first == second
    assert len(first) == 4
    assert all(len(sample) == len(case_ids) for sample in first)
    assert all(case_id in case_ids for sample in first for case_id in sample)


def test_bootstrap_replicates_include_all_units_from_sampled_cases() -> None:
    model_a = ModelScoreInput(
        model_id="model-a",
        unit_scores=(
            _score("case-1", "u1", "model-a", 0.1),
            _score("case-1", "u2", "model-a", 0.3),
            _score("case-2", "u3", "model-a", 0.9),
        ),
    )
    model_b = ModelScoreInput(
        model_id="model-b",
        unit_scores=(
            _score("case-1", "u1", "model-b", 0.2),
            _score("case-1", "u2", "model-b", 0.4),
            _score("case-2", "u3", "model-b", 0.8),
        ),
    )

    result = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=5, seed=44),
    )

    first_replicate = result.replicates[0]
    expected_a = _manual_resampled_micro_brier(
        model_a,
        first_replicate.sampled_case_ids,
    )
    expected_b = _manual_resampled_micro_brier(
        model_b,
        first_replicate.sampled_case_ids,
    )

    assert first_replicate.micro_briers["model-a"] == pytest.approx(expected_a)
    assert first_replicate.micro_briers["model-b"] == pytest.approx(expected_b)
    assert result.observed_micro_briers["model-a"] == pytest.approx(1.3 / 3)
    assert result.pairwise_deltas[0].observed_delta == pytest.approx(-0.1 / 3)
    record = result.to_record()
    assert record["rank_tier_method"] == (
        "bonferroni_pairwise_bootstrap_confidence_intervals"
    )
    assert "not a full simultaneous ranking model" in record["rank_tier_caveat"]
    json.dumps(record)


def test_bootstrap_resamples_related_family_as_one_independence_unit() -> None:
    model_a = ModelScoreInput(
        model_id="model-a",
        unit_scores=(
            _score("case-1", "u1", "model-a", 0.1, related_family_id="family-a"),
            _score("case-2", "u2", "model-a", 0.3, related_family_id="family-a"),
            _score("case-3", "u3", "model-a", 0.9),
        ),
    )
    model_b = ModelScoreInput(
        model_id="model-b",
        unit_scores=(
            _score("case-1", "u1", "model-b", 0.2, related_family_id="family-a"),
            _score("case-2", "u2", "model-b", 0.4, related_family_id="family-a"),
            _score("case-3", "u3", "model-b", 0.8),
        ),
    )

    result = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=8, seed=44),
    )

    assert result.case_ids == ("case-1", "case-2", "case-3")
    assert result.cluster_ids == ("case:case-3", "related_family:family-a")
    assert any(
        "related_family:family-a" in replicate.sampled_cluster_ids
        for replicate in result.replicates
    )
    for replicate in result.replicates:
        family_draws = replicate.sampled_cluster_ids.count("related_family:family-a")
        assert replicate.sampled_case_ids.count("case-1") == family_draws
        assert replicate.sampled_case_ids.count("case-2") == family_draws
        assert replicate.micro_briers["model-a"] == pytest.approx(
            _manual_resampled_micro_brier_by_cluster(model_a, replicate)
        )


def test_bootstrap_prefers_mdl_family_over_related_family_cluster() -> None:
    model_a = ModelScoreInput(
        model_id="model-a",
        unit_scores=(
            _score(
                "case-1",
                "u1",
                "model-a",
                0.1,
                related_family_id="related-a",
                mdl_family_id="mdl-a",
            ),
            _score(
                "case-2",
                "u2",
                "model-a",
                0.3,
                related_family_id="related-b",
                mdl_family_id="mdl-a",
            ),
        ),
    )
    model_b = ModelScoreInput(
        model_id="model-b",
        unit_scores=(
            _score(
                "case-1",
                "u1",
                "model-b",
                0.2,
                related_family_id="related-a",
                mdl_family_id="mdl-a",
            ),
            _score(
                "case-2",
                "u2",
                "model-b",
                0.4,
                related_family_id="related-b",
                mdl_family_id="mdl-a",
            ),
        ),
    )

    result = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=4, seed=3),
    )

    assert result.cluster_ids == ("mdl_family:mdl-a",)
    assert {replicate.sampled_cluster_ids for replicate in result.replicates} == {
        ("mdl_family:mdl-a",)
    }
    assert all(
        replicate.sampled_case_ids == ("case-1", "case-2")
        for replicate in result.replicates
    )


def test_bootstrap_is_reproducible_and_pairwise_by_same_sampled_cases() -> None:
    model_a = _model("model-a", {"case-1": (0.1, 0.2), "case-2": (0.3,)})
    model_b = _model("model-b", {"case-1": (0.4, 0.5), "case-2": (0.6,)})

    first = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=20, seed=9),
    )
    second = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=20, seed=9),
    )

    assert first.to_record() == second.to_record()
    for replicate in first.replicates:
        assert set(replicate.micro_briers) == {"model-a", "model-b"}
        assert len(replicate.sampled_case_ids) == 2


def test_bootstrap_pairwise_probability_counts_ties_as_half_credit() -> None:
    model_a = _model("model-a", {"case-1": (0.1,), "case-2": (0.2,)})
    model_b = _model("model-b", {"case-1": (0.1,), "case-2": (0.2,)})

    result = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=20, seed=9),
    )

    delta = result.pairwise_deltas[0]
    assert delta.observed_delta == 0.0
    assert delta.probability_a_better == 0.5


def test_small_cluster_warning_suppresses_uncertainty_tiers() -> None:
    model_a = _model("model-a", {"case-1": (0.01,)})
    model_b = _model("model-b", {"case-1": (0.20,)})

    result = paired_clustered_bootstrap(
        (model_a, model_b),
        config=BootstrapConfig(replicates=10, seed=11, small_cluster_threshold=2),
    )

    assert result.small_cluster_warning is not None
    assert result.cluster_dimension == "case"
    assert [rank.rank for rank in result.ranks] == [1, 2]
    assert [rank.tier for rank in result.ranks] == [None, None]


def test_rank_tiers_separate_statistically_distinguishable_models() -> None:
    model_a = _model("model-a", {"case-1": (0.01,), "case-2": (0.01,)})
    model_b = _model("model-b", {"case-1": (0.20,), "case-2": (0.20,)})
    model_c = _model("model-c", {"case-1": (0.20,), "case-2": (0.20,)})

    result = paired_clustered_bootstrap(
        (model_b, model_c, model_a),
        config=BootstrapConfig(replicates=50, seed=11, small_cluster_threshold=1),
    )
    ranks = {rank.model_id: rank for rank in result.ranks}

    assert [rank.model_id for rank in result.ranks] == [
        "model-a",
        "model-b",
        "model-c",
    ]
    assert ranks["model-a"].rank == 1
    assert ranks["model-a"].tier == 1
    assert ranks["model-b"].tier == 2
    assert ranks["model-c"].tier == 2


def test_rank_tiers_record_familywise_multiple_comparison_adjustment() -> None:
    model_a = _model("model-a", {"case-1": (0.01,), "case-2": (0.01,)})
    model_b = _model("model-b", {"case-1": (0.20,), "case-2": (0.20,)})
    model_c = _model("model-c", {"case-1": (0.21,), "case-2": (0.21,)})

    result = paired_clustered_bootstrap(
        (model_a, model_b, model_c),
        config=BootstrapConfig(
            replicates=50,
            seed=11,
            ci_level=0.95,
            small_cluster_threshold=1,
        ),
    )
    record = result.to_record()

    assert result.rank_tier_ci_level == pytest.approx(1 - (0.05 / 3))
    assert record["config"]["rank_tier_correction"] == "bonferroni"
    assert record["rank_tier_ci_level"] == pytest.approx(1 - (0.05 / 3))


def test_bootstrap_rejects_unpaired_case_unit_keys() -> None:
    model_a = _model("model-a", {"case-1": (0.1,)})
    model_b = _model("model-b", {"case-2": (0.2,)})

    with pytest.raises(ValueError, match="matching case/unit keys"):
        paired_clustered_bootstrap(
            (model_a, model_b),
            config=BootstrapConfig(replicates=5),
        )


def test_bootstrap_rejects_mismatched_cluster_metadata() -> None:
    model_a = ModelScoreInput(
        model_id="model-a",
        unit_scores=(
            _score("case-1", "u1", "model-a", 0.1, related_family_id="family-a"),
        ),
    )
    model_b = ModelScoreInput(
        model_id="model-b",
        unit_scores=(
            _score("case-1", "u1", "model-b", 0.2, related_family_id="family-b"),
        ),
    )

    with pytest.raises(ValueError, match="matching bootstrap cluster metadata"):
        paired_clustered_bootstrap(
            (model_a, model_b),
            config=BootstrapConfig(replicates=5),
        )


def _model(model_id: str, cases: dict[str, tuple[float, ...]]) -> ModelScoreInput:
    scores: list[UnitScore] = []
    for case_id, briers in cases.items():
        for index, brier in enumerate(briers, start=1):
            scores.append(_score(case_id, f"u{index}", model_id, brier))
    return ModelScoreInput(model_id=model_id, unit_scores=tuple(scores))


def _score(
    case_id: str,
    unit_id: str,
    model_id: str,
    brier: float,
    *,
    related_family_id: str | None = None,
    mdl_family_id: str | None = None,
) -> UnitScore:
    return UnitScore(
        case_id=case_id,
        model_id=model_id,
        unit_id=unit_id,
        probability_fully_dismissed=0.5,
        outcome=0,
        brier=brier,
        log_loss=0.7,
        parser_status=ParserStatus.VALID,
        raw_output_sha256="sha256:" + ("0" * 64),
        related_family_id=related_family_id,
        mdl_family_id=mdl_family_id,
    )


def _manual_resampled_micro_brier(
    model: ModelScoreInput,
    sampled_case_ids: tuple[str, ...],
) -> float:
    by_case: dict[str, list[UnitScore]] = {}
    for score in model.unit_scores:
        by_case.setdefault(score.case_id, []).append(score)
    values = [
        unit_score.brier
        for case_id in sampled_case_ids
        for unit_score in by_case[case_id]
    ]
    return sum(values) / len(values)


def _manual_resampled_micro_brier_by_cluster(
    model: ModelScoreInput,
    replicate,
) -> float:
    by_cluster: dict[str, list[UnitScore]] = {}
    for score in model.unit_scores:
        cluster_id = (
            f"mdl_family:{score.mdl_family_id}"
            if score.mdl_family_id is not None
            else (
                f"related_family:{score.related_family_id}"
                if score.related_family_id is not None
                else f"case:{score.case_id}"
            )
        )
        by_cluster.setdefault(cluster_id, []).append(score)
    values = [
        unit_score.brier
        for cluster_id in replicate.sampled_cluster_ids
        for unit_score in by_cluster[cluster_id]
    ]
    return sum(values) / len(values)

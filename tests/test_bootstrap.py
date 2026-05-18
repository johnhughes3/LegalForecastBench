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
    json.dumps(result.to_record())


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


def test_rank_tiers_separate_statistically_distinguishable_models() -> None:
    model_a = _model("model-a", {"case-1": (0.01,), "case-2": (0.01,)})
    model_b = _model("model-b", {"case-1": (0.20,), "case-2": (0.20,)})
    model_c = _model("model-c", {"case-1": (0.20,), "case-2": (0.20,)})

    result = paired_clustered_bootstrap(
        (model_b, model_c, model_a),
        config=BootstrapConfig(replicates=50, seed=11),
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


def test_bootstrap_rejects_unpaired_case_unit_keys() -> None:
    model_a = _model("model-a", {"case-1": (0.1,)})
    model_b = _model("model-b", {"case-2": (0.2,)})

    with pytest.raises(ValueError, match="matching case/unit keys"):
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


def _score(case_id: str, unit_id: str, model_id: str, brier: float) -> UnitScore:
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

from __future__ import annotations

import json
import re
from argparse import Namespace
from datetime import date
from pathlib import Path

import pytest
from legalforecast.cli_commands import report as report_command
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    dump_model_registry,
)
from legalforecast.evals.scorers import CalibrationBin, ScoreSummary
from legalforecast.multiharness.reporting import (
    CommunityComparisonRow,
    render_community_comparison_csv,
    render_community_comparison_html,
    render_community_comparison_json,
    render_community_comparison_markdown,
)
from legalforecast.publication.static_sites import render_official_results_site
from legalforecast.reporting.contamination_tiers import (
    PRELIMINARY_CAVEAT,
    PRELIMINARY_MARKER,
    ContaminationDriftError,
    ContaminationTier,
    ContaminationTierReason,
    ContaminationTierRow,
    ContaminationTierSidecar,
    ModelCohortScore,
    build_contamination_tier_sidecar,
    classify_contamination_tier,
    classify_leaderboard_models,
    classify_registry_entry,
    compute_contamination_drift,
    frozen_result_digest,
    load_contamination_tier_sidecar,
    preliminary_caveat_if_needed,
    reported_model_label,
    sidecar_rows_from_registry,
    write_contamination_tier_sidecar,
)
from legalforecast.reporting.leaderboard import build_benchmark_leaderboard_report
from legalforecast.selection import TrainingCutoffStatus
from tests.test_static_result_sites import write_official_report_fixture

BOUNDARY = date(2026, 6, 30)
PRELIMINARY_MODEL = "new-model"
RESISTANT_MODEL = "old-model"
_DIGEST_A = "sha256:" + "a" * 64
_DIGEST_B = "sha256:" + "b" * 64


def test_known_cutoff_before_boundary_is_contamination_resistant() -> None:
    decision = classify_contamination_tier(
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=date(2026, 2, 16),
        contamination_boundary=BOUNDARY,
    )

    assert decision.tier is ContaminationTier.RESISTANT
    assert decision.reason is ContaminationTierReason.KNOWN_CUTOFF_PREDATES_BOUNDARY


def test_flipping_cutoff_to_or_past_the_boundary_makes_the_row_preliminary() -> None:
    resistant = classify_contamination_tier(
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=date(2026, 6, 29),
        contamination_boundary=BOUNDARY,
    )
    on_boundary = classify_contamination_tier(
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=BOUNDARY,
        contamination_boundary=BOUNDARY,
    )
    after_boundary = classify_contamination_tier(
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=date(2026, 8, 1),
        contamination_boundary=BOUNDARY,
    )

    assert resistant.tier is ContaminationTier.RESISTANT
    assert on_boundary.tier is ContaminationTier.PRELIMINARY
    assert after_boundary.tier is ContaminationTier.PRELIMINARY
    assert (
        on_boundary.reason
        is ContaminationTierReason.KNOWN_CUTOFF_DOES_NOT_PREDATE_BOUNDARY
    )


@pytest.mark.parametrize(
    "status",
    (TrainingCutoffStatus.UNKNOWN, TrainingCutoffStatus.NOT_DISCLOSED),
)
def test_unknown_cutoff_cannot_claim_contamination_resistant(
    status: TrainingCutoffStatus,
) -> None:
    decision = classify_contamination_tier(
        provider_training_cutoff_status=status,
        provider_training_cutoff=None,
        contamination_boundary=BOUNDARY,
    )

    assert decision.tier is ContaminationTier.PRELIMINARY
    assert decision.reason is ContaminationTierReason.CUTOFF_NOT_KNOWN


def test_registry_entry_classifier_reuses_cutoff_fields() -> None:
    resistant = _entry(
        model_id=RESISTANT_MODEL,
        cutoff="2026-02-16",
        status="known",
    )
    preliminary = _entry(
        model_id=PRELIMINARY_MODEL,
        cutoff="2026-08-01",
        status="known",
        release_timestamp="2026-08-10T00:00:00Z",
    )

    assert (
        classify_registry_entry(resistant, contamination_boundary=BOUNDARY).tier
        is ContaminationTier.RESISTANT
    )
    assert (
        classify_registry_entry(preliminary, contamination_boundary=BOUNDARY).tier
        is ContaminationTier.PRELIMINARY
    )


def test_sidecar_is_keyed_by_frozen_result_digest_and_is_not_a_schema_family(
    tmp_path: Path,
) -> None:
    result_bytes = b'{"schema_version":"legalforecast-official-aggregate-v1"}\n'
    digest = frozen_result_digest(result_bytes)
    registry = ModelRegistry.from_records(
        [
            _registry_record(RESISTANT_MODEL, cutoff="2026-02-16", status="known"),
            _registry_record(PRELIMINARY_MODEL, cutoff="2026-08-01", status="known"),
        ]
    )
    sidecar = build_contamination_tier_sidecar(
        result_digest=digest,
        cohort_id="cycle-1",
        contamination_boundary=BOUNDARY,
        rows=sidecar_rows_from_registry(
            (RESISTANT_MODEL, PRELIMINARY_MODEL),
            registry=registry,
            contamination_boundary=BOUNDARY,
        ),
    )
    path = tmp_path / "contamination-tier-sidecar.json"
    write_contamination_tier_sidecar(path, sidecar)

    loaded = load_contamination_tier_sidecar(path, expected_digest=digest)
    record = json.loads(path.read_text(encoding="utf-8"))

    assert sidecar.authoritative is False
    assert record["authoritative"] is False
    assert record["kind"] == "contamination_tier_sidecar"
    assert "schema_version" not in record
    assert loaded.tier_by_model_id()[PRELIMINARY_MODEL] is (
        ContaminationTier.PRELIMINARY
    )
    assert loaded.tier_by_model_id()[RESISTANT_MODEL] is ContaminationTier.RESISTANT
    with pytest.raises(ValueError, match="result_digest does not match"):
        load_contamination_tier_sidecar(path, expected_digest=_DIGEST_A)
    with pytest.raises(ValueError, match="must not declare a schema_version"):
        sidecar_payload = dict(record)
        sidecar_payload["schema_version"] = "legalforecast.contamination_tiers.v1"
        ContaminationTierSidecar.from_record(sidecar_payload)


def test_reported_label_marks_only_preliminary_rows() -> None:
    tiers = {
        PRELIMINARY_MODEL: ContaminationTier.PRELIMINARY,
        RESISTANT_MODEL: ContaminationTier.RESISTANT,
    }

    assert reported_model_label(PRELIMINARY_MODEL, tiers) == (
        f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}"
    )
    assert reported_model_label(RESISTANT_MODEL, tiers) == RESISTANT_MODEL
    assert reported_model_label(PRELIMINARY_MODEL, None) == PRELIMINARY_MODEL
    assert preliminary_caveat_if_needed(tiers) == PRELIMINARY_CAVEAT
    assert (
        preliminary_caveat_if_needed({RESISTANT_MODEL: ContaminationTier.RESISTANT})
        is None
    )


def test_human_report_surfaces_never_emit_unmarked_preliminary_rows() -> None:
    tiers = {
        PRELIMINARY_MODEL: ContaminationTier.PRELIMINARY,
        RESISTANT_MODEL: ContaminationTier.RESISTANT,
    }
    outputs = _human_report_outputs(tiers)

    assert set(outputs) == {
        "leaderboard.md",
        "leaderboard.html",
        "community.md",
        "community.html",
    }
    for name, rendered in outputs.items():
        assert f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}" in rendered, name
        assert PRELIMINARY_CAVEAT in rendered, name
        assert _unmarked_model_mentions(rendered, PRELIMINARY_MODEL) == [], name
        assert RESISTANT_MODEL in rendered, name
        assert f"{RESISTANT_MODEL}{PRELIMINARY_MARKER}" not in rendered, name


def test_cutoff_past_boundary_classifies_and_renders_as_preliminary() -> None:
    registry = ModelRegistry.from_records(
        [
            _registry_record(PRELIMINARY_MODEL, cutoff="2026-08-01", status="known"),
            _registry_record(RESISTANT_MODEL, cutoff="2026-02-16", status="known"),
        ]
    )
    tiers = classify_leaderboard_models(
        (PRELIMINARY_MODEL, RESISTANT_MODEL),
        registry=registry,
        contamination_boundary=BOUNDARY,
    )
    markdown = build_benchmark_leaderboard_report(
        (
            _summary(PRELIMINARY_MODEL, micro_brier=0.10, ece=0.03),
            _summary(RESISTANT_MODEL, micro_brier=0.12, ece=0.04),
        )
    ).to_markdown(contamination_tiers=tiers)

    assert tiers[PRELIMINARY_MODEL] is ContaminationTier.PRELIMINARY
    assert f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}" in markdown
    assert PRELIMINARY_CAVEAT in markdown
    assert f"{RESISTANT_MODEL}{PRELIMINARY_MARKER}" not in markdown


def test_removing_the_caveat_from_a_preliminary_render_fails_the_contract() -> None:
    rendered = build_benchmark_leaderboard_report(
        (_summary(PRELIMINARY_MODEL, micro_brier=0.10, ece=0.03),)
    ).to_markdown(
        contamination_tiers={PRELIMINARY_MODEL: ContaminationTier.PRELIMINARY}
    )
    stripped = rendered.replace(PRELIMINARY_CAVEAT, "")

    assert PRELIMINARY_CAVEAT in rendered
    assert PRELIMINARY_CAVEAT not in stripped
    assert f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}" in stripped


def test_leaderboard_json_envelope_does_not_absorb_the_tier_flag() -> None:
    report = build_benchmark_leaderboard_report(
        (
            _summary(PRELIMINARY_MODEL, micro_brier=0.10, ece=0.03),
            _summary(RESISTANT_MODEL, micro_brier=0.12, ece=0.04),
        )
    )
    record = report.to_record()
    csv_text = report.to_csv()

    assert [row["model_id"] for row in record["rows"]] == [
        PRELIMINARY_MODEL,
        RESISTANT_MODEL,
    ]
    assert "contamination_tier" not in record
    assert PRELIMINARY_MARKER not in csv_text
    assert PRELIMINARY_CAVEAT not in json.dumps(record)


def test_community_json_envelope_stays_unmarked_when_human_renders_are_marked() -> None:
    row = _community_row(PRELIMINARY_MODEL)
    tiers = {PRELIMINARY_MODEL: ContaminationTier.PRELIMINARY}
    json_text = render_community_comparison_json((row,))
    markdown = render_community_comparison_markdown((row,), contamination_tiers=tiers)

    payload = json.loads(json_text)
    assert payload["schema_version"] == (
        "legalforecast.multiharness.community_report.v1"
    )
    assert payload["rows"][0]["model_key"] == PRELIMINARY_MODEL
    assert PRELIMINARY_MARKER not in payload["rows"][0]["model_key"]
    assert f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}" in markdown
    assert PRELIMINARY_CAVEAT in markdown
    csv_text = render_community_comparison_csv((row,))
    assert PRELIMINARY_MODEL in csv_text
    assert PRELIMINARY_MARKER not in csv_text


def test_official_site_auto_loads_sidecar_and_marks_preliminary_models(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    leaderboard = official_dir / "report" / "leaderboard.json"
    sidecar = build_contamination_tier_sidecar(
        result_digest=frozen_result_digest(leaderboard.read_bytes()),
        cohort_id="fixture-cycle",
        contamination_boundary=BOUNDARY,
        rows=(
            _row("model-a", ContaminationTier.RESISTANT, date(2026, 2, 16)),
            _row("model-b", ContaminationTier.PRELIMINARY, date(2026, 8, 1)),
        ),
    )
    write_contamination_tier_sidecar(
        official_dir / "contamination-tier-sidecar.json",
        sidecar,
    )

    site = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "official-site",
    )
    rendered = site.index_path.read_text(encoding="utf-8")

    assert f"model-b{PRELIMINARY_MARKER}" in rendered
    assert PRELIMINARY_CAVEAT in rendered
    assert _unmarked_model_mentions(rendered, "model-b") == []
    assert "model-a*" not in rendered


def test_drift_emits_paired_delta_with_both_cohort_identities() -> None:
    drift = compute_contamination_drift(
        ModelCohortScore(
            model_id=PRELIMINARY_MODEL,
            cohort_id="cycle-1",
            contamination_tier=ContaminationTier.PRELIMINARY,
            micro_brier=0.10,
            result_digest=_DIGEST_A,
        ),
        ModelCohortScore(
            model_id=PRELIMINARY_MODEL,
            cohort_id="cycle-2",
            contamination_tier=ContaminationTier.RESISTANT,
            micro_brier=0.13,
            result_digest=_DIGEST_B,
        ),
    )

    assert drift.preliminary_cohort_id == "cycle-1"
    assert drift.resistant_cohort_id == "cycle-2"
    assert drift.resistant_minus_preliminary_micro_brier == pytest.approx(0.03)
    record = drift.to_record()
    assert record["preliminary_result_digest"] == _DIGEST_A
    assert record["resistant_result_digest"] == _DIGEST_B


def test_drift_refuses_a_model_with_only_one_tier() -> None:
    preliminary = ModelCohortScore(
        model_id=PRELIMINARY_MODEL,
        cohort_id="cycle-1",
        contamination_tier=ContaminationTier.PRELIMINARY,
        micro_brier=0.10,
        result_digest=_DIGEST_A,
    )
    also_preliminary = ModelCohortScore(
        model_id=PRELIMINARY_MODEL,
        cohort_id="cycle-2",
        contamination_tier=ContaminationTier.PRELIMINARY,
        micro_brier=0.11,
        result_digest=_DIGEST_B,
    )

    with pytest.raises(ContaminationDriftError, match="one preliminary score"):
        compute_contamination_drift(preliminary, also_preliminary)


def test_drift_refuses_the_same_cohort_identity() -> None:
    with pytest.raises(ContaminationDriftError, match="two different cohort"):
        compute_contamination_drift(
            ModelCohortScore(
                model_id=PRELIMINARY_MODEL,
                cohort_id="cycle-1",
                contamination_tier=ContaminationTier.PRELIMINARY,
                micro_brier=0.10,
                result_digest=_DIGEST_A,
            ),
            ModelCohortScore(
                model_id=PRELIMINARY_MODEL,
                cohort_id="cycle-1",
                contamination_tier=ContaminationTier.RESISTANT,
                micro_brier=0.13,
                result_digest=_DIGEST_B,
            ),
        )


def test_report_cli_writes_sidecar_and_marks_human_outputs(
    tmp_path: Path,
) -> None:
    scores_path = tmp_path / "scores.json"
    scores_path.write_text(
        json.dumps(
            {
                "summaries": [
                    _summary(PRELIMINARY_MODEL, micro_brier=0.10, ece=0.03).to_record(),
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    registry_path = tmp_path / "registry.json"
    dump_model_registry(
        ModelRegistry.from_records(
            [
                _registry_record(
                    PRELIMINARY_MODEL, cutoff="2026-08-01", status="known"
                ),
            ]
        ),
        registry_path,
    )
    output_dir = tmp_path / "report"

    assert (
        report_command.run(
            _report_args(
                scores=scores_path,
                output_dir=output_dir,
                model_registry=registry_path,
                contamination_boundary=BOUNDARY.isoformat(),
                cohort_id="cycle-1",
            )
        )
        == 0
    )

    sidecar_path = output_dir / "contamination-tier-sidecar.json"
    markdown = (output_dir / "leaderboard.md").read_text(encoding="utf-8")
    html_text = (output_dir / "leaderboard.html").read_text(encoding="utf-8")
    json_text = (output_dir / "leaderboard.json").read_text(encoding="utf-8")
    csv_text = (output_dir / "leaderboard.csv").read_text(encoding="utf-8")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert sidecar["authoritative"] is False
    assert sidecar["kind"] == "contamination_tier_sidecar"
    assert sidecar["result_digest"] == frozen_result_digest(
        (output_dir / "leaderboard.json").read_bytes()
    )
    assert "schema_version" not in sidecar
    assert f"{PRELIMINARY_MODEL}{PRELIMINARY_MARKER}" in markdown
    assert PRELIMINARY_CAVEAT in markdown
    assert PRELIMINARY_CAVEAT in html_text
    assert _unmarked_model_mentions(markdown, PRELIMINARY_MODEL) == []
    assert _unmarked_model_mentions(html_text, PRELIMINARY_MODEL) == []
    assert PRELIMINARY_MARKER not in json.dumps(json.loads(json_text)["rows"])
    assert PRELIMINARY_MARKER not in csv_text
    assert PRELIMINARY_CAVEAT not in json_text


def test_report_cli_requires_registry_boundary_and_cohort_together() -> None:
    with pytest.raises(ValueError, match="must be passed together"):
        report_command._contamination_inputs(
            Namespace(
                model_registry=Path("registry.json"),
                contamination_boundary=None,
                cohort_id=None,
            )
        )


def test_classify_leaderboard_models_matches_registry_ids() -> None:
    registry = ModelRegistry.from_records(
        [
            _registry_record(RESISTANT_MODEL, cutoff="2026-02-16", status="known"),
            _registry_record(PRELIMINARY_MODEL, cutoff="2026-08-01", status="known"),
        ]
    )

    tiers = classify_leaderboard_models(
        (RESISTANT_MODEL, PRELIMINARY_MODEL),
        registry=registry,
        contamination_boundary=BOUNDARY,
    )

    assert tiers == {
        RESISTANT_MODEL: ContaminationTier.RESISTANT,
        PRELIMINARY_MODEL: ContaminationTier.PRELIMINARY,
    }


def _report_args(
    *,
    scores: Path,
    output_dir: Path,
    model_registry: Path | None = None,
    contamination_boundary: str | None = None,
    cohort_id: str | None = None,
) -> Namespace:
    return Namespace(
        scores=scores,
        output_dir=output_dir,
        accounting=None,
        title="LegalForecast-MTD Leaderboard",
        bootstrap_replicates=1,
        bootstrap_seed=20260514,
        dry_run=False,
        model_registry=model_registry,
        contamination_boundary=contamination_boundary,
        cohort_id=cohort_id,
    )


def _human_report_outputs(
    tiers: dict[str, ContaminationTier],
) -> dict[str, str]:
    report = build_benchmark_leaderboard_report(
        (
            _summary(PRELIMINARY_MODEL, micro_brier=0.10, ece=0.03),
            _summary(RESISTANT_MODEL, micro_brier=0.12, ece=0.04),
        )
    )
    community_rows = (
        _community_row(PRELIMINARY_MODEL),
        _community_row(RESISTANT_MODEL, row_id="resistant-row"),
    )
    return {
        "leaderboard.md": report.to_markdown(contamination_tiers=tiers),
        "leaderboard.html": report.to_html(contamination_tiers=tiers),
        "community.md": render_community_comparison_markdown(
            community_rows, contamination_tiers=tiers
        ),
        "community.html": render_community_comparison_html(
            community_rows, contamination_tiers=tiers
        ),
    }


def _unmarked_model_mentions(rendered: str, model_id: str) -> list[str]:
    pattern = re.compile(
        rf"(?<![\w-]){re.escape(model_id)}(?!{re.escape(PRELIMINARY_MARKER)})"
    )
    return pattern.findall(rendered)


def _row(
    model_id: str,
    tier: ContaminationTier,
    cutoff: date,
) -> ContaminationTierRow:
    reason = (
        ContaminationTierReason.KNOWN_CUTOFF_PREDATES_BOUNDARY
        if tier is ContaminationTier.RESISTANT
        else ContaminationTierReason.KNOWN_CUTOFF_DOES_NOT_PREDATE_BOUNDARY
    )
    return ContaminationTierRow(
        model_id=model_id,
        contamination_tier=tier,
        classification_reason=reason,
        provider_training_cutoff_status=TrainingCutoffStatus.KNOWN,
        provider_training_cutoff=cutoff,
    )


def _entry(
    *,
    model_id: str,
    cutoff: str | None,
    status: str,
    release_timestamp: str = "2026-05-14T09:00:00Z",
) -> ModelRegistryEntry:
    return ModelRegistryEntry.from_record(
        _registry_record(
            model_id,
            cutoff=cutoff,
            status=status,
            release_timestamp=release_timestamp,
        )
    )


def _registry_record(
    model_id: str,
    *,
    cutoff: str | None,
    status: str,
    release_timestamp: str = "2026-05-14T09:00:00Z",
) -> dict[str, object]:
    return {
        "provider": "example-provider",
        "model_id": model_id,
        "display_name": model_id,
        "model_version_or_snapshot": "2026-05-14",
        "release_timestamp": release_timestamp,
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": status,
        "provider_training_cutoff": cutoff,
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "provider-price-sheet-2026-05-14",
        "input_token_price": 0.25,
        "output_token_price": 1.0,
        "known_cutoff_publicity_caveats": [],
    }


def _community_row(model_key: str, *, row_id: str = "row-1") -> CommunityComparisonRow:
    return CommunityComparisonRow(
        row_id=row_id,
        row_type="single-shard",
        submission_ids=("submission-1",),
        shard_ids=("shard-1",),
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        selection_sha256="sha256:" + "1" * 64,
        selection_label="fixture-selection",
        suite_version="fixture",
        adapter_id="fixture-adapter",
        adapter_version="0.1.0",
        model_key=model_key,
        conformance_status="passed",
        task_count=2,
        coverage_percentage=100.0,
        status_counts={"passed": 2},
        contributor_credit=(),
        artifact_ids=("artifact-1",),
    )


def _summary(model_id: str, *, micro_brier: float, ece: float) -> ScoreSummary:
    return ScoreSummary(
        model_id=model_id,
        case_count=2,
        unit_count=5,
        micro_brier=micro_brier,
        macro_brier=micro_brier + 0.01,
        brier_skill_score=1 - (micro_brier / 0.25),
        log_loss=0.50 + micro_brier,
        ece=ece,
        capped_case_micro_brier=micro_brier + 0.01,
        related_family_capped_micro_brier=micro_brier + 0.02,
        mdl_family_capped_micro_brier=micro_brier + 0.03,
        case_unit_cap=10,
        family_unit_cap=10,
        dominance_threshold=0.40,
        dominance_sensitivity_reports=(),
        invalid_output_rate=0.0,
        refusal_rate=0.0,
        defaulted_prediction_rate=0.0,
        base_rate=0.5,
        base_rate_brier=0.25,
        ece_bins=(
            CalibrationBin(
                bin_index=0,
                lower=0.0,
                upper=0.5,
                unit_count=3,
                mean_probability=0.2,
                observed_rate=0.25,
                absolute_calibration_error=0.05,
            ),
        ),
        unit_scores=(),
    )

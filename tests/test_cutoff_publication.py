from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

from legalforecast.evals.model_registry import TrainingCutoffStatus
from legalforecast.publication.static_sites import render_official_results_site
from legalforecast.reporting.contamination_tiers import (
    PRELIMINARY_CAVEAT,
    PRELIMINARY_MARKER,
    ContaminationTier,
    ContaminationTierReason,
    ContaminationTierRow,
    ContaminationTierSidecar,
    frozen_result_digest,
    write_contamination_tier_sidecar,
)
from legalforecast.reporting.result_class import (
    SUPPLEMENTARY_CAVEAT,
    SUPPLEMENTARY_MARKER,
    ResultClass,
)
from tests.test_static_result_sites import (
    SUPPLEMENTARY_MODEL_ID,
    write_official_report_fixture,
    write_result_class_sidecar_for,
    write_supplementary_report_fixture,
)


def table_row_html(rendered: str, label: str) -> str:
    start = rendered.index(f"<th scope='row'>{label}</th>")
    return rendered[start : rendered.index("</tr>", start)]


def section_html(rendered: str, heading: str) -> str:
    start = rendered.index(heading)
    return rendered[start : rendered.index("</section>", start)]


def write_contamination_sidecar_for(
    artifacts_dir: Path,
    tiers: Mapping[str, ContaminationTier],
) -> None:
    """Bind cutoff eligibility evidence to one bundle's frozen leaderboard."""

    digest = frozen_result_digest(
        (artifacts_dir / "report" / "leaderboard.json").read_bytes()
    )
    write_contamination_tier_sidecar(
        artifacts_dir / "contamination-tier-sidecar.json",
        ContaminationTierSidecar(
            result_digest=digest,
            cohort_id="fixture-cycle",
            contamination_boundary=date(2026, 6, 30),
            rows=tuple(
                ContaminationTierRow(
                    model_id=model_id,
                    contamination_tier=tier,
                    classification_reason=(
                        ContaminationTierReason.KNOWN_CUTOFF_PREDATES_BOUNDARY
                        if tier is ContaminationTier.RESISTANT
                        else ContaminationTierReason.CUTOFF_NOT_KNOWN
                    ),
                    provider_training_cutoff_status=(
                        TrainingCutoffStatus.KNOWN
                        if tier is ContaminationTier.RESISTANT
                        else TrainingCutoffStatus.UNKNOWN
                    ),
                    provider_training_cutoff=(
                        date(2026, 2, 16)
                        if tier is ContaminationTier.RESISTANT
                        else None
                    ),
                )
                for model_id, tier in sorted(tiers.items())
            ),
        ),
    )


def test_training_cutoff_eligible_post_anchor_row_joins_headline_comparison(
    tmp_path: Path,
) -> None:
    """A later release remains visibly post-anchor while ranking by cutoff tier."""

    official_dir = write_official_report_fixture(tmp_path)
    supplementary_dir = write_supplementary_report_fixture(tmp_path)
    write_result_class_sidecar_for(
        official_dir,
        {
            "model-a": ResultClass.PRE_ANCHOR,
            "model-b": ResultClass.PRE_ANCHOR,
            "global_base_rate": ResultClass.PRE_ANCHOR,
        },
    )
    write_result_class_sidecar_for(
        supplementary_dir,
        {SUPPLEMENTARY_MODEL_ID: ResultClass.POST_ANCHOR},
    )
    write_contamination_sidecar_for(
        official_dir,
        {
            "model-a": ContaminationTier.RESISTANT,
            "model-b": ContaminationTier.PRELIMINARY,
        },
    )
    write_contamination_sidecar_for(
        supplementary_dir,
        {SUPPLEMENTARY_MODEL_ID: ContaminationTier.RESISTANT},
    )

    rendered = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "official-site",
        supplementary_artifacts_dir=supplementary_dir,
    ).index_path.read_text(encoding="utf-8")

    headline = section_html(rendered, "<h2 id='headline-title'>")
    assert f"{SUPPLEMENTARY_MODEL_ID}{SUPPLEMENTARY_MARKER}" in headline
    assert "<p class='metric'>0.0100</p>" in headline
    assert rendered.index(
        f"<th scope='row'>{SUPPLEMENTARY_MODEL_ID}{SUPPLEMENTARY_MARKER}</th>"
    ) < rendered.index("<th scope='row'>model-a</th>")
    assert "Eligible comparison" in table_row_html(
        rendered, f"{SUPPLEMENTARY_MODEL_ID}{SUPPLEMENTARY_MARKER}"
    )
    assert "Unavailable across separately aggregated result bundles" in rendered
    assert "Historical post-anchor marker" in rendered
    assert SUPPLEMENTARY_CAVEAT not in rendered


def test_unknown_cutoff_post_anchor_row_stays_qualified_and_out_of_headline(
    tmp_path: Path,
) -> None:
    official_dir = write_official_report_fixture(tmp_path)
    supplementary_dir = write_supplementary_report_fixture(tmp_path)
    write_result_class_sidecar_for(
        official_dir,
        {
            "model-a": ResultClass.PRE_ANCHOR,
            "model-b": ResultClass.PRE_ANCHOR,
            "global_base_rate": ResultClass.PRE_ANCHOR,
        },
    )
    write_result_class_sidecar_for(
        supplementary_dir,
        {SUPPLEMENTARY_MODEL_ID: ResultClass.POST_ANCHOR},
    )
    write_contamination_sidecar_for(
        official_dir,
        {"model-a": ContaminationTier.RESISTANT},
    )
    write_contamination_sidecar_for(
        supplementary_dir,
        {SUPPLEMENTARY_MODEL_ID: ContaminationTier.PRELIMINARY},
    )

    rendered = render_official_results_site(
        official_artifacts_dir=official_dir,
        output_dir=tmp_path / "official-site",
        supplementary_artifacts_dir=supplementary_dir,
    ).index_path.read_text(encoding="utf-8")

    headline = section_html(rendered, "<h2 id='headline-title'>")
    assert SUPPLEMENTARY_MODEL_ID not in headline
    assert "<p class='metric'>0.0880</p>" in headline
    qualified_label = (
        f"{SUPPLEMENTARY_MODEL_ID}{PRELIMINARY_MARKER}{SUPPLEMENTARY_MARKER}"
    )
    assert f"<th scope='row'>{qualified_label}</th>" in rendered
    assert "Qualified comparison" in table_row_html(rendered, qualified_label)
    assert rendered.index("<th scope='row'>model-a</th>") < rendered.index(
        f"<th scope='row'>{qualified_label}</th>"
    )
    assert PRELIMINARY_CAVEAT in rendered
    assert SUPPLEMENTARY_CAVEAT in rendered

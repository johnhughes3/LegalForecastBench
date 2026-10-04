from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import model_registry_sha256
from legalforecast.evals.output_parser import (
    ParserStatus,
    parse_model_output,
    public_parser_record,
)
from legalforecast.evals.run_record_scoring import (
    ReleaseOutcomeLabel,
    score_run_records,
)
from legalforecast.release import issue_synthetic_release, serialize_run_manifest
from tests.test_locked_run_manifest_consumer import (
    _manifest,
    _strict_receipts,
    _write_registry,
)
from tests.test_locked_run_manifest_consumer import (
    main as cli_main,
)


def test_score_run_records_groups_models_and_preserves_identity_precedence() -> None:
    labels = (_label("unit-a", True), _label("unit-b", False))
    summaries = score_run_records(
        (
            _run_record(
                model_id="model-z",
                metadata_model_id="ignored-metadata",
                solver_id="offline:ignored-solver",
                case_id="case-z",
            ),
            _run_record(
                metadata_model_id="model-a",
                solver_id="offline:ignored-solver",
                case_id="case-a",
            ),
            _run_record(solver_id="offline:model-a", case_id="case-b"),
        ),
        labels,
        base_rate=0.25,
    )

    assert tuple(summary.model_id for summary in summaries) == ("model-a", "model-z")
    assert tuple(summary.case_count for summary in summaries) == (2, 1)
    assert all(summary.base_rate == 0.25 for summary in summaries)


def test_score_run_records_computes_base_rate_from_scored_labels() -> None:
    summaries = score_run_records(
        (_run_record(model_id="model-a"),),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=None,
    )

    assert summaries[0].base_rate == 0.5


def test_score_run_records_excludes_ambiguous_units_and_all_ambiguous_cases() -> None:
    summaries = score_run_records(
        (
            _run_record(case_id="all-ambiguous", required_unit_ids=("unit-a",)),
            _run_record(case_id="mixed"),
        ),
        (_ambiguous_label("unit-a"), _label("unit-b", False)),
        base_rate=0.0,
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.case_count == 1
    assert summary.unit_count == 1
    assert tuple(score.unit_id for score in summary.unit_scores) == ("unit-b",)


def test_score_run_records_preserves_parser_accounting_for_ambiguous_units() -> None:
    raw_output = json.dumps(
        {
            "case_assessment": "Partial prediction.",
            "predictions": [
                {
                    "unit_id": "unit-a",
                    "probability_fully_dismissed": 0.8,
                }
            ],
        }
    )
    summaries = score_run_records(
        (_run_record(raw_output=raw_output),),
        (_label("unit-a", True), _ambiguous_label("unit-b")),
        base_rate=1.0,
    )

    summary = summaries[0]
    assert summary.unit_count == 1
    assert summary.invalid_output_rate == 1.0
    assert summary.defaulted_prediction_rate == 0.5
    assert summary.unit_scores[0].parser_status is ParserStatus.MISSING_UNIT


def test_score_run_records_quality_rates_include_all_ambiguous_cases_and_units() -> (
    None
):
    summaries = score_run_records(
        (
            _run_record(
                case_id="refused-ambiguous",
                required_unit_ids=("unit-a",),
                raw_output="I cannot provide a prediction.",
            ),
            _run_record(
                case_id="valid-scored",
                required_unit_ids=("unit-b",),
            ),
        ),
        (_ambiguous_label("unit-a"), _label("unit-b", False)),
        base_rate=0.0,
    )

    summary = summaries[0]
    assert summary.case_count == 1
    assert summary.unit_count == 1
    assert summary.invalid_output_rate == 0.5
    assert summary.refusal_rate == 0.5
    assert summary.defaulted_prediction_rate == 0.5


def test_score_run_records_accepts_public_prose_free_parser_projection() -> None:
    record = _run_record()
    raw_output = str(record.pop("raw_output"))
    record["parser_output"] = public_parser_record(
        parse_model_output(raw_output, required_unit_ids=("unit-a", "unit-b"))
    )

    summaries = score_run_records(
        (record,),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=0.5,
    )

    assert summaries[0].unit_count == 2
    assert summaries[0].invalid_output_rate == 0.0


def test_score_run_records_rejects_duplicate_outcome_label_unit_ids() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate outcome labels for units: \\['unit-a'\\]",
    ):
        score_run_records(
            (_run_record(),),
            (
                _label("unit-a", True),
                _label("unit-a", False),
                _label("unit-b", False),
            ),
            base_rate=None,
        )


def test_score_run_records_rejects_empty_solver_model_suffix() -> None:
    with pytest.raises(
        ValueError,
        match="solver_id must include a non-empty model ID",
    ):
        score_run_records(
            (_run_record(solver_id="offline:"),),
            (_label("unit-a", True), _label("unit-b", False)),
            base_rate=0.5,
        )


def test_score_run_records_can_include_ablation_in_model_identity() -> None:
    summaries = score_run_records(
        (
            _run_record(
                model_id="model-a",
                case_id="case-full",
                ablation="full_packet",
            ),
            _run_record(
                model_id="model-a",
                case_id="case-metadata",
                ablation="metadata_only",
            ),
        ),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=0.5,
        include_ablation_in_model_id=True,
    )

    assert tuple(summary.model_id for summary in summaries) == (
        "model-a::full_packet",
        "model-a::metadata_only",
    )


def test_score_run_records_ignores_legacy_ablation_when_not_opted_in() -> None:
    record = _run_record()
    record["ablation"] = ""

    summaries = score_run_records(
        (record,),
        (_label("unit-a", True), _label("unit-b", False)),
        base_rate=0.5,
    )

    assert summaries[0].model_id == "model-fallback"


def test_score_run_records_rejects_computed_base_rate_without_scored_labels() -> None:
    with pytest.raises(
        ValueError,
        match="cannot compute base rate without scored labels",
    ):
        score_run_records(
            (_run_record(),),
            (_ambiguous_label("unit-a"), _ambiguous_label("unit-b")),
            base_rate=None,
        )


@pytest.mark.parametrize(
    ("scenario", "message"),
    [
        ("empty-runs", "at least one run record is required"),
        ("empty-labels", "at least one outcome label is required"),
        (
            "missing-label",
            "labels missing for required units: \\['unit-b'\\]",
        ),
    ],
)
def test_score_run_records_preserves_boundary_errors(
    scenario: str,
    message: str,
) -> None:
    run_records = () if scenario == "empty-runs" else (_run_record(),)
    labels = () if scenario == "empty-labels" else (_label("unit-a", True),)
    with pytest.raises(ValueError, match=message):
        score_run_records(run_records, labels, base_rate=0.5)


def _run_record(
    *,
    model_id: str | None = None,
    metadata_model_id: str | None = None,
    solver_id: str = "offline:model-fallback",
    case_id: str = "case-1",
    required_unit_ids: tuple[str, ...] = ("unit-a", "unit-b"),
    raw_output: str | None = None,
    ablation: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "case_id": case_id,
        "solver_id": solver_id,
        "required_unit_ids": list(required_unit_ids),
        "raw_output": raw_output
        if raw_output is not None
        else json.dumps(
            {
                "case_assessment": "Mixed outcome.",
                "predictions": [
                    {
                        "unit_id": unit_id,
                        "probability_fully_dismissed": (0.8 if index == 0 else 0.2),
                    }
                    for index, unit_id in enumerate(required_unit_ids)
                ],
            }
        ),
    }
    if model_id is not None:
        record["model_id"] = model_id
    if metadata_model_id is not None:
        record["metadata"] = {"model_id": metadata_model_id}
    if ablation is not None:
        record["ablation"] = ablation
    return record


def _label(unit_id: str, dismissed: bool) -> ReleaseOutcomeLabel:
    return ReleaseOutcomeLabel(
        unit_id=unit_id,
        primary_outcome=int(dismissed),
        label_confidence=0.97,
    )


def _ambiguous_label(unit_id: str) -> ReleaseOutcomeLabel:
    return ReleaseOutcomeLabel(
        unit_id=unit_id,
        primary_outcome=None,
        label_confidence=0.4,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "original",
        "canonical",
        "provider",
        "missing",
        "non-jev",
        "condition",
        "invalid-count",
    ],
)
def test_gateway_jev_unreported_route_scores_and_reports(
    tmp_path: Path, mutation: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    release_dir = tmp_path / "release"
    issued = issue_synthetic_release(release_dir)
    registry_path = _write_registry(tmp_path)
    entry = json.loads(registry_path.read_text())[0]
    if mutation != "non-jev":
        entry.update(
            provider="vercel_ai_gateway",
            model_id="typesafe-ai/jev",
            model_version_or_snapshot="typesafe-ai/jev",
            max_output_tokens=1,
            jev_input_mode="grok_summaries",
            jev_summaries_sha256="a" * 64,
        )
    registry_path.write_text(json.dumps([entry]))
    records = _strict_receipts(issued, registry_path)
    routing = {
        "originalModelId": "typesafe-ai/jev",
        "canonicalSlug": "typesafe-ai/jev",
        "resolvedProvider": "typesafe-ai",
        "finalProvider": "typesafe-ai",
        "modelAttemptCount": 1,
        "totalProviderAttemptCount": 1,
    }
    if mutation == "original":
        routing["originalModelId"] = "other/model"
    elif mutation == "canonical":
        routing["canonicalSlug"] = "other/model"
    elif mutation == "provider":
        routing["finalProvider"] = "other"
    if mutation == "invalid-count":
        routing["modelAttemptCount"] = 0
    for record in records:
        record["served_model_version"] = "unreported"
        record["execution_condition"] = (
            "jev_full_text" if mutation == "condition" else "jev_grok_summaries"
        )
        if mutation != "missing":
            record["jev_provider_metadata"] = {
                "gateway": {
                    "routing": routing,
                    "generationId": "generation",
                    "gatewayCost": "0.001",
                    "marketCost": "0.001",
                }
            }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(
        serialize_run_manifest(_manifest("case-001", "case-002", "case-003"))
    )
    runs_path = tmp_path / "runs.jsonl"
    runs_path.write_text("".join(json.dumps(record) + "\n" for record in records))
    scores_path = tmp_path / "scores.json"
    command = [
        "score",
        "--runs",
        str(runs_path),
        "--labels-release",
        str(release_dir / "labels-release.json"),
        "--forecast-release",
        str(release_dir / "forecast-release.json"),
        "--artifact-root",
        str(release_dir),
        "--manifest",
        str(manifest_path),
        "--expected-run-identity-sha256",
        "c" * 64,
        "--model-registry",
        str(registry_path),
        "--expected-model-registry-sha256",
        model_registry_sha256(registry_path.read_bytes()),
        "--output",
        str(scores_path),
    ]
    if mutation is not None:
        assert cli_main(command) == 2
        error = capsys.readouterr().err
        assert any(
            message in error for message in ("Gateway", "served model", "Jev receipt")
        )
        assert not scores_path.exists()
        return
    assert cli_main(command) == 0
    scores = json.loads(scores_path.read_text())
    assert scores["identity"]["models"][0]["served_model_version"] == "unreported"
    report_dir = tmp_path / "report"
    assert (
        cli_main(
            [
                "report",
                "--scores",
                str(scores_path),
                "--output-dir",
                str(report_dir),
                "--manifest",
                str(manifest_path),
                "--forecast-release",
                str(release_dir / "forecast-release.json"),
                "--labels-release",
                str(release_dir / "labels-release.json"),
                "--artifact-root",
                str(release_dir),
                "--frozen-model-registry",
                str(registry_path),
            ]
        )
        == 0
    )
    report = json.loads((report_dir / "leaderboard.json").read_text())
    assert report["provenance"]["models"][0]["served_model_version"] == "unreported"

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast._json_io import write_json_object
from legalforecast.multiharness.community import (
    CommunityRunSummary,
    CommunitySubmissionManifest,
    CommunitySubmissionShard,
    validate_submission_file,
)
from legalforecast.multiharness.reporting import (
    CommunityComparisonRow,
    render_community_comparison_csv,
    render_community_comparison_html,
    render_community_comparison_json,
    render_community_comparison_markdown,
)
from legalforecast.multiharness.spec import (
    CanonicalTask,
    CommunityAggregate,
    CommunitySubmission,
)
from legalforecast.multiharness.validation import MultiHarnessValidationError
from legalforecast.publication.static_sites import render_community_results_site

JsonRecord = dict[str, Any]
FIXTURE_ROOT = Path(__file__).parent / "fixtures/multiharness-artifact-characterization"
VERSIONED_READERS = {
    "legalforecast.multiharness.spec.CanonicalTask.from_record": (
        "canonical-task.v1.json"
    ),
    "legalforecast.multiharness.community.CommunityRunSummary.from_record": (
        "community-run-summary.v1.json"
    ),
    "legalforecast.multiharness.community.CommunitySubmissionShard.from_record": (
        "community-submission-shard.v1.json"
    ),
    "legalforecast.multiharness.community.CommunitySubmissionManifest.from_record": (
        "community-submission-manifest.v1.json"
    ),
    "legalforecast.multiharness.spec.CommunitySubmission.from_record": (
        "legacy-community-submission.v1.json"
    ),
    "legalforecast.multiharness.spec.CommunityAggregate.from_record": (
        "legacy-community-aggregate.v1.json"
    ),
}


def test_manifest_identifies_every_characterized_legacy_reader() -> None:
    manifest = _read_json(FIXTURE_ROOT / "manifest.json")
    readers = cast(list[JsonRecord], manifest["versioned_readers"])

    assert {
        cast(str, item["reader"]): cast(str, item["fixture"]) for item in readers
    } == (VERSIONED_READERS)
    for item in readers:
        assert (FIXTURE_ROOT / cast(str, item["fixture"])).is_file()


@pytest.mark.parametrize(
    ("reader_name", "fixture_name"),
    VERSIONED_READERS.items(),
)
def test_versioned_artifacts_read_and_rewrite_equivalently(
    reader_name: str,
    fixture_name: str,
) -> None:
    record = _read_json(FIXTURE_ROOT / fixture_name)

    assert _read_and_rewrite(reader_name, record) == record


@pytest.mark.parametrize(
    ("reader_name", "fixture_name"),
    VERSIONED_READERS.items(),
)
def test_versioned_artifact_readers_refuse_unknown_versions(
    reader_name: str,
    fixture_name: str,
) -> None:
    record = _read_json(FIXTURE_ROOT / fixture_name)
    record["schema_version"] = "legalforecast.multiharness.unknown.v999"

    with pytest.raises(MultiHarnessValidationError, match="schema_version"):
        _read_and_rewrite(reader_name, record)


def test_current_submission_package_passes_file_and_hash_validation() -> None:
    submission_path = FIXTURE_ROOT / "community-submission-manifest.v1.json"

    manifest = validate_submission_file(submission_path)

    assert manifest.to_record() == _read_json(submission_path)


def test_current_aggregate_row_and_static_reports_match_goldens() -> None:
    row_record = _read_json(FIXTURE_ROOT / "community-comparison-row.v1.json")
    row = _comparison_row(row_record)

    assert row.to_record() == row_record
    actual_reports = {
        "community-comparison.json": render_community_comparison_json((row,)),
        "community-comparison.csv": render_community_comparison_csv((row,)),
        "community-comparison.md": render_community_comparison_markdown((row,)),
        "community-comparison.html": render_community_comparison_html((row,)),
    }
    for filename, actual in actual_reports.items():
        expected = (FIXTURE_ROOT / "reports" / filename).read_text(encoding="utf-8")
        portable_actual = actual.replace("\r\n", "\n")
        assert portable_actual.rstrip("\n") == expected.rstrip("\n")
    csv_report = actual_reports["community-comparison.csv"]
    assert csv_report.count("\r\n") == 2
    assert "\n" not in csv_report.replace("\r\n", "")
    assert actual_reports["community-comparison.md"].endswith("\n")


def test_current_site_summary_renders_and_refuses_unknown_versions(
    tmp_path: Path,
) -> None:
    summary = _read_json(FIXTURE_ROOT / "site-summary.v1.json")
    aggregate_dir = tmp_path / "aggregate"
    summary_path = aggregate_dir / "registry" / "site-summary.json"
    write_json_object(summary_path, summary)

    result = render_community_results_site(
        community_aggregate_dir=aggregate_dir,
        output_dir=tmp_path / "site",
    )

    rendered = result.index_path.read_text(encoding="utf-8")
    assert "fixture-submission:fixture-shard" in rendered
    assert "Harvey LAB (lab_native)" in rendered

    unknown = deepcopy(summary)
    unknown["schema_version"] = "legalforecast.multiharness.unknown.v999"
    write_json_object(summary_path, unknown)
    with pytest.raises(MultiHarnessValidationError, match="schema_version"):
        render_community_results_site(
            community_aggregate_dir=aggregate_dir,
            output_dir=tmp_path / "unknown-site",
        )


def _read_and_rewrite(reader_name: str, record: Mapping[str, Any]) -> JsonRecord:
    if reader_name.endswith("CanonicalTask.from_record"):
        return CanonicalTask.from_record(record).to_record()
    if reader_name.endswith("CommunityRunSummary.from_record"):
        return CommunityRunSummary.from_record(record).to_record()
    if reader_name.endswith("CommunitySubmissionShard.from_record"):
        return CommunitySubmissionShard.from_record(record).to_record()
    if reader_name.endswith("CommunitySubmissionManifest.from_record"):
        return CommunitySubmissionManifest.from_record(record).to_record()
    if reader_name.endswith("CommunitySubmission.from_record"):
        return CommunitySubmission.from_record(record).to_record()
    if reader_name.endswith("CommunityAggregate.from_record"):
        return CommunityAggregate.from_record(record).to_record()
    raise AssertionError(f"uncharacterized reader: {reader_name}")


def _comparison_row(record: Mapping[str, Any]) -> CommunityComparisonRow:
    return CommunityComparisonRow(
        row_id=cast(str, record["row_id"]),
        row_type=cast(str, record["row_type"]),
        submission_ids=tuple(cast(list[str], record["submission_ids"])),
        shard_ids=tuple(cast(list[str], record["shard_ids"])),
        family=cast(str, record["family"]),
        scoring_mode=cast(str, record["scoring_mode"]),
        selection_sha256=cast(str, record["selection_sha256"]),
        selection_label=cast(str, record["selection_label"]),
        suite_version=cast(str, record["suite_version"]),
        adapter_id=cast(str, record["adapter_id"]),
        adapter_version=cast(str, record["adapter_version"]),
        model_key=cast(str, record["model_key"]),
        conformance_status=cast(str, record["conformance_status"]),
        task_count=cast(int, record["task_count"]),
        coverage_percentage=cast(float, record["coverage_percentage"]),
        status_counts=cast(Mapping[str, int], record["status_counts"]),
        contributor_credit=tuple(
            cast(list[Mapping[str, Any]], record["contributor_credit"])
        ),
        artifact_ids=tuple(cast(list[str], record["artifact_ids"])),
    )


def _read_json(path: Path) -> JsonRecord:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(JsonRecord, value)

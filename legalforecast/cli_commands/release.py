# pyright: reportPrivateUsage=false

"""The ``legalforecast release`` public contract commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from legalforecast.immutable_io import ImmutableIOError
from legalforecast.release import (
    ForecastDraft,
    ForecastRelease,
    issue_release,
    issue_synthetic_release,
    load_forecast_draft,
    load_forecast_execution,
    load_labels_draft,
    publish_release,
    validate_release,
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register release issuance and validation on the root parser."""

    release = subparsers.add_parser(
        "release", help="Issue and validate public forecast and labels releases."
    )
    commands = release.add_subparsers(dest="release_command", metavar="COMMAND")

    issue = commands.add_parser(
        "issue", help="Issue a release pair from strict drafts and artifact bytes."
    )
    issue.add_argument("--forecast-draft", type=Path, required=True)
    issue.add_argument("--labels-draft", type=Path, required=True)
    issue.add_argument("--artifact-root", type=Path, required=True)
    issue.add_argument("--output-dir", type=Path, required=True)
    issue.set_defaults(handler=run_issue)

    synthetic = commands.add_parser(
        "issue-synthetic", help="Issue the deterministic three-case fixture."
    )
    synthetic.add_argument("--output-dir", type=Path, required=True)
    synthetic.set_defaults(handler=run_issue_synthetic)

    validate = commands.add_parser(
        "validate", help="Validate a paired release and every referenced artifact."
    )
    validate.add_argument("--forecast", type=Path, required=True)
    validate.add_argument("--labels", type=Path, required=True)
    validate.add_argument("--artifact-root", type=Path, required=True)
    validate.set_defaults(handler=run_validate)


def run_issue(args: argparse.Namespace) -> int:
    """Issue and create-only publish a generic release pair."""

    artifact_root = cast(Path, args.artifact_root)
    forecast_draft = load_forecast_draft(cast(Path, args.forecast_draft))
    forecast_draft = _preserve_compatible_manifest_binding(
        forecast_draft,
        artifact_root=artifact_root,
    )
    issued = issue_release(
        forecast_draft,
        load_labels_draft(cast(Path, args.labels_draft)),
        artifact_root=artifact_root,
    )
    output_dir = cast(Path, args.output_dir)
    try:
        publish_release(output_dir, issued, artifact_root=artifact_root)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc
    _print_issue_status(output_dir, issued.forecast.release_digest)
    return 0


def _preserve_compatible_manifest_binding(
    forecast_draft: ForecastDraft,
    *,
    artifact_root: Path,
) -> ForecastDraft:
    """Carry a binding through a draft round-trip when its source is exact.

    Older draft callers omit the optional binding field.  If the artifact root
    also contains the release from which that draft was derived, preserving
    the binding keeps re-issuance byte-compatible without guessing a manifest
    for a genuinely new release.
    """

    if forecast_draft.run_manifest_binding is not None:
        return forecast_draft
    source_path = artifact_root / "forecast-release.json"
    if not source_path.is_file():
        return forecast_draft
    try:
        source = load_forecast_execution(
            source_path,
            artifact_root=artifact_root,
        ).release
    except (FileNotFoundError, ValueError, OSError):
        return forecast_draft
    if not source.run_manifest_binding or not _draft_matches_release(
        forecast_draft,
        source,
    ):
        return forecast_draft
    return forecast_draft.model_copy(
        update={"run_manifest_binding": source.run_manifest_binding}
    )


def _draft_matches_release(
    forecast_draft: ForecastDraft,
    source: ForecastRelease,
) -> bool:
    draft_cases = {
        case.case_id: tuple(
            (document.document_id, document.role, document.path)
            for document in case.documents
        )
        for case in forecast_draft.cases
    }
    source_cases = {
        case.case_id: tuple(
            (document.document_id, document.role, document.path)
            for document in case.documents
        )
        for case in source.cases
    }
    if draft_cases != source_cases:
        return False
    documents_by_case = {case.case_id: case.documents for case in source.cases}
    draft_units = {
        unit.unit_id: (
            unit.case_id,
            unit.claim_name,
            unit.defendant_group,
            unit.count,
            unit.should_score,
            tuple(unit.model_visible_document_ids),
            unit.packet_path,
            unit.prompt_path,
        )
        for unit in forecast_draft.prediction_units
    }
    source_units = {
        unit.unit_id: (
            unit.case_id,
            unit.claim_name,
            unit.defendant_group,
            unit.count,
            unit.should_score,
            tuple(
                documents_by_case[unit.case_id][index].document_id
                for index in unit.model_visible_document_indexes
            ),
            unit.packet_path,
            unit.prompt_path,
        )
        for unit in source.prediction_units
    }
    return (
        forecast_draft.release_id == source.release_id
        and forecast_draft.policy_digest == source.policy_digest
        and forecast_draft.code_version == source.code_version
        and forecast_draft.packet_builder_version == source.packet_builder_version
        and draft_units == source_units
    )


def run_issue_synthetic(args: argparse.Namespace) -> int:
    """Issue and create-only publish the deterministic fixture."""

    output_dir = cast(Path, args.output_dir)
    try:
        issued = issue_synthetic_release(output_dir)
    except ImmutableIOError as exc:
        raise ValueError(str(exc)) from exc
    _print_issue_status(output_dir, issued.forecast.release_digest)
    return 0


def run_validate(args: argparse.Namespace) -> int:
    """Validate a paired public release."""

    forecast, labels = validate_release(
        cast(Path, args.forecast),
        cast(Path, args.labels),
        artifact_root=cast(Path, args.artifact_root),
    )
    print(
        json.dumps(
            {
                "case_count": forecast.case_count,
                "forecast_release_digest": forecast.release_digest,
                "labels_release_digest": labels.release_digest,
                "release_id": forecast.release_id,
                "unit_count": forecast.unit_count,
                "valid": True,
            },
            sort_keys=True,
        )
    )
    return 0


def _print_issue_status(output_dir: Path, forecast_digest: str) -> None:
    print(
        json.dumps(
            {
                "forecast_release": str(output_dir / "forecast-release.json"),
                "forecast_release_digest": forecast_digest,
                "labels_release": str(output_dir / "labels-release.json"),
            },
            sort_keys=True,
        )
    )

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import legalforecast.ingestion.resolved_post_recovery as resolved_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.disclosure_review_authority import (
    disclosure_authority_identity_from_cohort_policy,
)
from legalforecast.ingestion.disclosure_review_bundle import prepare_review_worksheet
from legalforecast.ingestion.target_100_acquisition import (
    Target100PreparationConfig,
    TargetCohortPreparationConfig,
    TargetCohortPreparationError,
    build_target_100_stage_commands,
    build_target_cohort_stage_commands,
)
from pytest import CaptureFixture
from tests.disclosure_review_fixtures import (
    service_disclosure_authority_from_policy_bytes,
    service_review_signer,
    signed_service_review_lineage,
)
from tests.purchase_approval_fixtures import build_approved_purchase_fixture
from tests.test_acquisition_cli import (
    _finalized_prediction_unit_record,
    _write_model_registry,
)


@pytest.fixture(autouse=True)
def _allow_cryptographic_service_identity_in_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli_validate = cli.validate_review_receipt
    resolved_validate = resolved_module.validate_review_receipt
    monkeypatch.setattr(
        cli,
        "validate_review_receipt",
        lambda *positional, **keywords: cli_validate(
            *positional, **{**keywords, "allow_test_service_identity": True}
        ),
    )
    monkeypatch.setattr(
        resolved_module,
        "validate_review_receipt",
        lambda *positional, **keywords: resolved_validate(
            *positional, **{**keywords, "allow_test_service_identity": True}
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_main_disclosure_review_authority",
        lambda cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(
                reviewer_policy_bytes,
                identity=disclosure_authority_identity_from_cohort_policy(cohort),
            )
        ),
    )


@dataclass(frozen=True, slots=True)
class _AuthenticatedReviewFiles:
    reviews: Path
    receipt: Path
    requests: Path
    worksheet: Path
    policy: Path
    policy_pin: str
    cohort_policy: Path


def _snapshot_manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def test_preparation_clearance_inputs_ignore_unrecovered_paid_gaps(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "prepared"
    (output_root / "03-gap-bridge").mkdir(parents=True)
    (output_root / "03c-merged-downloads").mkdir(parents=True)
    free_document = {
        "source_document_id": "free-decision",
        "redaction_or_seal_status": "public",
        "restriction_evidence": ["courtlistener_public_download"],
        "is_sealed": False,
        "is_private": False,
        "requires_paid_recovery": False,
    }
    unknown_paid_gap = {
        "source_document_id": "paid-motion",
        "redaction_or_seal_status": "unknown",
        "restriction_evidence": ["no_positive_restriction_marker"],
        "is_sealed": None,
        "is_private": None,
        "requires_paid_recovery": True,
    }
    _write_jsonl(
        output_root / "03-gap-bridge/case-relevance.jsonl",
        [
            {
                "candidate_id": "case-1",
                "documents": [free_document, unknown_paid_gap],
            }
        ],
    )
    _write_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        [
            {
                "candidate_id": "case-1",
                "source_document_id": "free-decision",
                "sha256": "a" * 64,
                "byte_count": 10,
                "free_or_purchased": "free",
            }
        ],
    )

    cli._prepare_target_100_clearance_inputs(output_root, resume=False)

    restrictions = _read_jsonl(
        output_root / "06-clearance-inputs/restriction-evidence.jsonl"
    )
    requests = _read_jsonl(
        output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
    )
    assert [
        (row["candidate_id"], row["source_document_id"]) for row in restrictions
    ] == [("case-1", "free-decision")]
    assert [(row["candidate_id"], row["source_document_id"]) for row in requests] == [
        ("case-1", "free-decision")
    ]
    restriction_path = output_root / "06-clearance-inputs/restriction-evidence.jsonl"
    request_path = output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
    restriction_bytes = restriction_path.read_bytes()
    request_bytes = request_path.read_bytes()
    cli._prepare_target_100_clearance_inputs(output_root, resume=True)
    assert restriction_path.read_bytes() == restriction_bytes
    assert request_path.read_bytes() == request_bytes
    request_path.write_bytes(request_bytes + b"\n")
    with pytest.raises(cli.CommandError, match="resume artifact mismatch"):
        cli._prepare_target_100_clearance_inputs(output_root, resume=True)
    assert restriction_path.read_bytes() == restriction_bytes


def test_preparation_clearance_inputs_route_acquired_unknown_to_review(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "prepared"
    (output_root / "03-gap-bridge").mkdir(parents=True)
    (output_root / "03c-merged-downloads").mkdir(parents=True)
    _write_jsonl(
        output_root / "03-gap-bridge/case-relevance.jsonl",
        [
            {
                "candidate_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "unknown-document",
                        "redaction_or_seal_status": "unknown",
                        "restriction_evidence": ["no_positive_restriction_marker"],
                        "is_sealed": None,
                        "is_private": None,
                        "requires_paid_recovery": True,
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        [
            {
                "candidate_id": "case-1",
                "source_document_id": "unknown-document",
                "sha256": "a" * 64,
                "byte_count": 10,
                "free_or_purchased": "purchased",
            }
        ],
    )

    cli._prepare_target_100_clearance_inputs(output_root, resume=False)

    [restriction] = _read_jsonl(
        output_root / "06-clearance-inputs/restriction-evidence.jsonl"
    )
    [review_request] = _read_jsonl(
        output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
    )
    assert restriction["restriction_status"] == "unknown"
    assert review_request["restriction_status"] == "unknown"


def test_preparation_clearance_inputs_reject_acquired_restricted_document(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "prepared"
    (output_root / "03-gap-bridge").mkdir(parents=True)
    (output_root / "03c-merged-downloads").mkdir(parents=True)
    _write_jsonl(
        output_root / "03-gap-bridge/case-relevance.jsonl",
        [
            {
                "candidate_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "sealed-document",
                        "redaction_or_seal_status": "sealed",
                        "restriction_evidence": ["courtlistener_sealed"],
                        "is_sealed": True,
                        "is_private": False,
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        [
            {
                "candidate_id": "case-1",
                "source_document_id": "sealed-document",
                "sha256": "a" * 64,
                "byte_count": 10,
                "free_or_purchased": "free",
            }
        ],
    )

    with pytest.raises(
        cli.TargetCohortProjectionError,
        match="sealed/private/restricted",
    ):
        cli._prepare_target_100_clearance_inputs(output_root, resume=False)
    assert not (output_root / "06-clearance-inputs").exists()


def test_merge_download_manifests_filters_to_reconciled_selection(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "downloads.jsonl"
    selection_path = tmp_path / "selection.jsonl"
    output_root = tmp_path / "merged"
    _write_jsonl(
        manifest_path,
        [
            {
                "candidate_id": candidate_id,
                "source_document_id": f"{candidate_id}-decision",
                "local_path": f"{candidate_id}/decision.pdf",
                "sha256": "a" * 64,
            }
            for candidate_id in ("selected-case", "excluded-case")
        ],
    )
    _write_jsonl(
        selection_path,
        [{"candidate_id": "selected-case", "selected": True}],
    )

    assert (
        main(
            [
                "acquisition",
                "merge-download-manifests",
                "--download-manifest",
                str(manifest_path),
                "--candidate-selection",
                str(selection_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "document-downloads-merged.jsonl") == [
        {
            "candidate_id": "selected-case",
            "local_path": "selected-case/decision.pdf",
            "sha256": "a" * 64,
            "source_document_id": "selected-case-decision",
        }
    ]
    run_card = json.loads(
        (output_root / "run-cards/merge-download-manifests.json").read_text()
    )
    assert run_card["candidate_selection_applied"] is True
    assert run_card["candidate_selection_sha256"] == (
        "sha256:" + hashlib.sha256(selection_path.read_bytes()).hexdigest()
    )
    assert run_card["selected_candidate_count"] == 1
    assert run_card["selected_candidate_ids_sha256"] == cli._canonical_json_sha256(
        ["selected-case"]
    )
    assert run_card["excluded_manifest_record_count"] == 1


@pytest.mark.parametrize("alias_kind", ["file_symlink", "parent_symlink", "hardlink"])
def test_merge_candidate_selection_rejects_filesystem_aliases(
    tmp_path: Path,
    alias_kind: str,
    capsys: CaptureFixture[str],
) -> None:
    preparation_root = tmp_path / alias_kind / "prepared"
    selection_path = (
        preparation_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
    )
    external_selection = tmp_path / alias_kind / "external-selection.jsonl"
    manifest_path = tmp_path / alias_kind / "downloads.jsonl"
    external_selection.parent.mkdir(parents=True)
    _write_jsonl(
        external_selection,
        [{"candidate_id": "selected-case", "selected": True}],
    )
    _write_jsonl(
        manifest_path,
        [
            {
                "candidate_id": "selected-case",
                "source_document_id": "selected-case-decision",
                "local_path": "selected-case/decision.pdf",
                "sha256": "a" * 64,
            }
        ],
    )
    if alias_kind == "parent_symlink":
        external_parent = tmp_path / alias_kind / "external-gap"
        external_parent.mkdir()
        (external_parent / selection_path.name).write_bytes(
            external_selection.read_bytes()
        )
        selection_path.parent.parent.mkdir(parents=True)
        selection_path.parent.symlink_to(external_parent, target_is_directory=True)
    else:
        selection_path.parent.mkdir(parents=True)
        if alias_kind == "file_symlink":
            selection_path.symlink_to(external_selection)
        else:
            selection_path.hardlink_to(external_selection)

    frozen_config = {
        "stage_commands": [
            {
                "stage": "merge-free-downloads",
                "argv": [
                    "acquisition",
                    "merge-download-manifests",
                    "--candidate-selection",
                    str(selection_path),
                ],
            }
        ]
    }
    with pytest.raises(cli.CommandError, match=r"symlink|singly linked"):
        cli._frozen_merge_candidate_selection_path(
            preparation_root=preparation_root,
            config=frozen_config,
        )
    output_root = tmp_path / alias_kind / "merged"
    assert (
        main(
            [
                "acquisition",
                "merge-download-manifests",
                "--download-manifest",
                str(manifest_path),
                "--candidate-selection",
                str(selection_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "symlink" in error or "singly linked" in error
    assert not (output_root / "document-downloads-merged.jsonl").exists()
    assert not (output_root / "run-cards/merge-download-manifests.json").exists()


def test_preparation_clearance_inputs_reject_duplicate_manifest_key(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "prepared"
    (output_root / "03-gap-bridge").mkdir(parents=True)
    (output_root / "03c-merged-downloads").mkdir(parents=True)
    _write_jsonl(
        output_root / "03-gap-bridge/case-relevance.jsonl",
        [
            {
                "candidate_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "free-decision",
                        "redaction_or_seal_status": "public",
                        "restriction_evidence": ["courtlistener_public_download"],
                        "is_sealed": False,
                        "is_private": False,
                    }
                ],
            }
        ],
    )
    manifest_record = {
        "candidate_id": "case-1",
        "source_document_id": "free-decision",
        "sha256": "a" * 64,
        "byte_count": 10,
        "free_or_purchased": "free",
    }
    _write_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        [manifest_record, dict(manifest_record)],
    )

    with pytest.raises(cli.CommandError, match="duplicate free document manifest"):
        cli._prepare_target_100_clearance_inputs(output_root, resume=False)
    assert not (output_root / "06-clearance-inputs").exists()


def test_preparation_clearance_inputs_reject_manifest_key_missing_from_relevance(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "prepared"
    (output_root / "03-gap-bridge").mkdir(parents=True)
    (output_root / "03c-merged-downloads").mkdir(parents=True)
    _write_jsonl(
        output_root / "03-gap-bridge/case-relevance.jsonl",
        [
            {
                "candidate_id": "case-1",
                "documents": [
                    {
                        "source_document_id": "different-document",
                        "redaction_or_seal_status": "public",
                        "restriction_evidence": ["courtlistener_public_download"],
                        "is_sealed": False,
                        "is_private": False,
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl",
        [
            {
                "candidate_id": "case-1",
                "source_document_id": "free-decision",
                "sha256": "a" * 64,
                "byte_count": 10,
                "free_or_purchased": "free",
            }
        ],
    )

    with pytest.raises(
        cli.TargetCohortProjectionError,
        match="requested document is absent from case relevance",
    ):
        cli._prepare_target_100_clearance_inputs(output_root, resume=False)
    assert not (output_root / "06-clearance-inputs").exists()


def test_target_100_commands_are_resumable_noncharging_and_exactly_capped(
    tmp_path: Path,
) -> None:
    config = Target100PreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=200,
        authenticated_screened_cases=tmp_path / "authenticated-screened.jsonl",
        screened_cases_sha256="c" * 64,
        target_case_count=100,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
        use_embedded_entries=True,
        resume=True,
    )

    commands = build_target_100_stage_commands(config)

    assert [command.stage for command in commands] == [
        "plan-public-downloads",
        "download-free",
        "bridge-pacer-gaps",
        "download-bridge-free",
        "merge-free-downloads",
        "filter-core-documents",
        "plan",
    ]
    flattened = [argument for command in commands for argument in command.argv]
    assert "purchase-missing" not in flattened
    assert "purchase-missing-recap-fetch" not in flattened
    assert "--acknowledge-pacer-fees" not in flattened
    assert "--live-purchase" not in flattened
    assert "--resume" in flattened
    assert commands[-1].argv[-2:] == ("--target-case-count", "100")
    assert "--live-courtlistener" in commands[2].argv
    assert "--request-ledger" in commands[2].argv
    assert "--live-public-download" in commands[1].argv
    assert "--candidate-selection" in commands[4].argv
    assert commands[0].argv[
        commands[0].argv.index("--expected-snapshot-manifest-sha256") + 1
    ] == ("b" * 64)


def test_target_command_builder_defensively_rejects_missing_narrowed_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Target100PreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=100,
        authenticated_screened_cases=tmp_path / "authenticated-screened.jsonl",
        screened_cases_sha256="c" * 64,
        raw_html_dir=tmp_path / "raw",
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )
    monkeypatch.setattr(Target100PreparationConfig, "validate", lambda self: None)

    with pytest.raises(
        TargetCohortPreparationError,
        match="authenticated raw-HTML manifest is required",
    ):
        build_target_100_stage_commands(config)


def test_target_cohort_commands_are_noncharging_and_bind_explicit_target(
    tmp_path: Path,
) -> None:
    config = TargetCohortPreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=220,
        target_case_count=150,
        authenticated_screened_cases=tmp_path / "authenticated-screened.jsonl",
        screened_cases_sha256="c" * 64,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
        use_embedded_entries=True,
        resume=True,
    )

    commands = build_target_cohort_stage_commands(config)

    flattened = [argument for command in commands for argument in command.argv]
    assert commands[-1].argv[-2:] == ("--target-case-count", "150")
    assert "purchase-missing" not in flattened
    assert "purchase-missing-recap-fetch" not in flattened
    assert "--acknowledge-pacer-fees" not in flattened
    assert "--live-purchase" not in flattened
    assert "--live-courtlistener" in commands[2].argv
    assert "firecrawl" not in " ".join(flattened).lower()
    assert "case.dev" not in " ".join(flattened).lower()


def test_retarget_config_is_semantic_and_keeps_all_stages_in_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "new-target-100"
    source = tmp_path / "prior-target-preparation"
    base = TargetCohortPreparationConfig(
        output_root=destination,
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=103,
        target_case_count=100,
        authenticated_screened_cases=tmp_path / "authenticated-screened.jsonl",
        screened_cases_sha256="c" * 64,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )
    retarget = replace(base, retarget_source_preparation_root=source)

    assert retarget != base
    commands = build_target_cohort_stage_commands(retarget)
    assert commands == build_target_cohort_stage_commands(base)
    assert len(commands) == 7
    destination_path_flags = {
        "--candidate-selection",
        "--case-relevance",
        "--core-filter-results",
        "--document-output-root",
        "--download-manifest",
        "--free-download-manifest",
        "--output-root",
        "--paid-gaps",
        "--public-selection",
        "--requests",
    }
    for command in commands:
        for index, argument in enumerate(command.argv[:-1]):
            if argument in destination_path_flags:
                assert Path(command.argv[index + 1]).is_relative_to(destination)
    flattened = tuple(argument for command in commands for argument in command.argv)
    assert str(source) not in flattened
    assert "--retarget-source-preparation-root" not in flattened


@pytest.mark.parametrize("target_case_count", [1, 99, 101, 150])
def test_retarget_config_requires_exactly_100_cases(
    tmp_path: Path,
    target_case_count: int,
) -> None:
    config = TargetCohortPreparationConfig(
        output_root=tmp_path / "new-target",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=200,
        target_case_count=target_case_count,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
        retarget_source_preparation_root=tmp_path / "source-target",
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )

    with pytest.raises(
        TargetCohortPreparationError,
        match="retarget target case count must be exactly 100",
    ):
        build_target_cohort_stage_commands(config)


@pytest.mark.parametrize("relationship", ["same", "source-parent", "output-parent"])
def test_retarget_config_requires_disjoint_source_and_destination_roots(
    tmp_path: Path,
    relationship: str,
) -> None:
    shared = tmp_path / "preparation"
    if relationship == "same":
        source, destination = shared, shared
    elif relationship == "source-parent":
        source, destination = shared, shared / "new-target"
    else:
        source, destination = shared / "old-target", shared
    config = TargetCohortPreparationConfig(
        output_root=destination,
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=103,
        target_case_count=100,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
        retarget_source_preparation_root=source,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )

    with pytest.raises(
        TargetCohortPreparationError,
        match="source and destination preparation roots must be disjoint",
    ):
        build_target_cohort_stage_commands(config)


@pytest.mark.parametrize("symlinked_root", ["source", "destination"])
def test_retarget_config_rejects_symlink_traversal(
    tmp_path: Path,
    symlinked_root: str,
) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    source = (
        linked_parent / "source" if symlinked_root == "source" else tmp_path / "source"
    )
    destination = (
        linked_parent / "destination"
        if symlinked_root == "destination"
        else tmp_path / "destination"
    )
    config = TargetCohortPreparationConfig(
        output_root=destination,
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=103,
        target_case_count=100,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
        retarget_source_preparation_root=source,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )

    with pytest.raises(
        TargetCohortPreparationError,
        match=f"retarget {symlinked_root} preparation root must not traverse a symlink",
    ):
        build_target_cohort_stage_commands(config)


def test_target_command_builders_reject_candidate_pool_below_target(
    tmp_path: Path,
) -> None:
    cohort = TargetCohortPreparationConfig(
        output_root=tmp_path / "cohort",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=149,
        target_case_count=150,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
        use_embedded_entries=True,
    )
    exact_100 = Target100PreparationConfig(
        output_root=tmp_path / "exact-100",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256="b" * 64,
        candidate_pool_size=99,
        authenticated_screened_cases=tmp_path / "screened.jsonl",
        screened_cases_sha256="c" * 64,
        use_embedded_entries=True,
    )

    with pytest.raises(ValueError, match="at least target case count"):
        build_target_cohort_stage_commands(cohort)
    with pytest.raises(ValueError, match="at least target case count"):
        build_target_100_stage_commands(exact_100)


@pytest.mark.parametrize(
    "manifest_sha256",
    (
        "B" * 64,
        "b" * 63,
        ("b" * 63) + "g",
    ),
)
def test_target_config_rejects_non_lowercase_snapshot_manifest_sha256(
    tmp_path: Path,
    manifest_sha256: str,
) -> None:
    config = TargetCohortPreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        expected_snapshot_manifest_sha256=manifest_sha256,
        candidate_pool_size=220,
        target_case_count=150,
        authenticated_screened_cases=tmp_path / "authenticated-screened.jsonl",
        screened_cases_sha256="c" * 64,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
    )

    with pytest.raises(
        ValueError,
        match="snapshot manifest SHA-256 must be 64 lowercase hex digits",
    ):
        build_target_cohort_stage_commands(config)


def test_target_cohort_cli_help_requires_target_and_explains_sources(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "prepare-target-cohort", "--help"])
    output = capsys.readouterr().out
    assert "--target-case-count" in output
    assert "required" in output
    assert "CourtListener" in output
    assert "Case.dev" in output
    assert "decision-search" in output
    assert "never purchases" in output


def test_target_cohort_execute_retains_full_frontier_and_replays_byte_identically(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=3)
    )
    output_root = tmp_path / "run"
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "2",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]

    assert main(command) == 0
    summary_path = output_root / "target-cohort-preparation-summary.json"
    config_path = output_root / "target-cohort-config.json"
    frontier_path = output_root / "05-budget/full-candidate-frontier.json"
    budget_path = output_root / "05-budget/missing-core-budget-plan.json"
    summary = json.loads(summary_path.read_text())
    config = json.loads(config_path.read_text())
    frontier_artifact = json.loads(frontier_path.read_text())
    frontier = frontier_artifact["policy"]["candidates"]
    budget = json.loads(budget_path.read_text())

    current_inputs, _ = cli._expected_preparation_input_commitments(
        preparation_root=output_root,
        config=config,
    )
    reconciled_selection = (
        output_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
    )
    assert str(reconciled_selection.resolve()) in current_inputs["03c-merged-downloads"]
    assert (
        cli._frozen_merge_candidate_selection_path(
            preparation_root=output_root,
            config=config,
        )
        == reconciled_selection.resolve()
    )
    legacy_config = json.loads(json.dumps(config))
    merge_command = next(
        command
        for command in legacy_config["stage_commands"]
        if command["stage"] == "merge-free-downloads"
    )
    selection_index = merge_command["argv"].index("--candidate-selection")
    del merge_command["argv"][selection_index : selection_index + 2]
    legacy_inputs, _ = cli._expected_preparation_input_commitments(
        preparation_root=output_root,
        config=legacy_config,
    )
    assert (
        str(reconciled_selection.resolve()) not in legacy_inputs["03c-merged-downloads"]
    )
    assert (
        cli._frozen_merge_candidate_selection_path(
            preparation_root=output_root,
            config=legacy_config,
        )
        is None
    )

    assert summary["schema_version"] == ("legalforecast.target_cohort_preparation.v1")
    assert config["schema_version"] == "legalforecast.target_cohort_config.v1"
    assert summary["target_case_count"] == config["target_case_count"] == 2
    assert summary["selected_case_count"] == 2
    assert len(budget["case_plans"]) == 2
    assert len(frontier) == summary["full_candidate_frontier_count"] == 3
    assert frontier_artifact["policy"]["frontier_truncated"] is False
    assert set(frontier_artifact["policy"]["source_commitments"]) == {
        "snapshot_manifest_sha256",
        "preparation_config_sha256",
        "reconciled_selection_sha256",
        "case_relevance_sha256",
        "download_manifest_sha256",
        "core_filter_results_sha256",
        "provisional_budget_plan_sha256",
        "restriction_evidence_sha256",
        "disclosure_review_requests_sha256",
    }
    clearance_contract = frontier_artifact["policy"]["clearance_contract"]
    assert clearance_contract["stage"] == "clear-disclosures"
    assert clearance_contract["required_source_commitments"] == [
        "download_manifest",
        "restriction_evidence",
        "reviews",
        "review_receipt",
    ]
    assert clearance_contract["required_output_commitments"] == ["disclosure_clearance"]
    assert clearance_contract["orphan_clearance_rows_allowed"] is False
    assert [row["rank"] for row in frontier] == [1, 2, 3]
    assert [row["selection_status"] for row in frontier] == [
        "selected",
        "selected",
        "eligible_omitted",
    ]
    assert {row["court"] for row in frontier} == {"nysd"}
    assert {row["nos_macro_category"] for row in frontier} == {"civil_rights"}
    assert all(row["related_family_id"] is None for row in frontier)
    assert all(row["mdl_family_id"] is None for row in frontier)
    assert summary["full_candidate_frontier_sha256"] == (
        "sha256:" + hashlib.sha256(frontier_path.read_bytes()).hexdigest()
    )
    assert config["config_sha256"].startswith("sha256:")
    normalized_frontier = cli._replacement_frontier_rows(
        frontier_path.read_bytes(),
        source=frontier_path,
    )
    assert len(normalized_frontier) == 3
    assert all("selection_status" not in row for row in normalized_frontier)
    reconciled_selection_bytes = reconciled_selection.read_bytes()
    selected_candidate_ids = tuple(
        str(row["candidate_id"])
        for row in frontier
        if row["selection_status"] == "selected"
    )
    assert (
        cli._verify_replacement_initial_selection_lineage(
            initial_candidate_ids=selected_candidate_ids,
            target_frontier_artifact=frontier_artifact,
            reconciled_selection_bytes=reconciled_selection_bytes,
            reconciled_selection_path=reconciled_selection,
        )
        == normalized_frontier
    )
    with pytest.raises(
        cli.ClearanceReplacementError,
        match="initial selection differs from the verified target-frontier",
    ):
        cli._verify_replacement_initial_selection_lineage(
            initial_candidate_ids=(
                *selected_candidate_ids[:-1],
                str(frontier[-1]["candidate_id"]),
            ),
            target_frontier_artifact=frontier_artifact,
            reconciled_selection_bytes=reconciled_selection_bytes,
            reconciled_selection_path=reconciled_selection,
        )
    missing_lineage = json.loads(json.dumps(frontier_artifact))
    missing_lineage["policy"]["source_commitments"].pop("snapshot_manifest_sha256")
    missing_lineage["policy_sha256"] = cli._canonical_json_sha256(
        missing_lineage["policy"]
    )
    with pytest.raises(ValueError, match="source commitments differ"):
        cli._verified_target_cohort_frontier_rows(missing_lineage)
    extra_lineage = json.loads(json.dumps(frontier_artifact))
    extra_lineage["policy"]["source_commitments"]["untrusted_sha256"] = (
        "sha256:" + "a" * 64
    )
    extra_lineage["policy_sha256"] = cli._canonical_json_sha256(extra_lineage["policy"])
    with pytest.raises(ValueError, match="source commitments differ"):
        cli._verified_target_cohort_frontier_rows(extra_lineage)
    partial_posthoc_lineage = json.loads(json.dumps(frontier_artifact))
    partial_posthoc_lineage["policy"]["source_commitments"][
        "preparation_summary_sha256"
    ] = "sha256:" + "b" * 64
    partial_posthoc_lineage["policy_sha256"] = cli._canonical_json_sha256(
        partial_posthoc_lineage["policy"]
    )
    with pytest.raises(ValueError, match="source commitments differ"):
        cli._verified_target_cohort_frontier_rows(partial_posthoc_lineage)
    null_contract_hash = json.loads(json.dumps(frontier_artifact))
    null_contract_hash["policy"]["clearance_contract"]["download_manifest_sha256"] = (
        None
    )
    null_contract_hash["policy_sha256"] = cli._canonical_json_sha256(
        null_contract_hash["policy"]
    )
    with pytest.raises(ValueError, match="clearance contract differs"):
        cli._verified_target_cohort_frontier_rows(null_contract_hash)
    tampered_frontier = tmp_path / "tampered-frontier.json"
    frontier_artifact["policy"]["candidate_count"] = 2
    tampered_frontier.write_text(json.dumps(frontier_artifact, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="policy hash mismatch"):
        cli._replacement_frontier_rows(
            tampered_frontier.read_bytes(),
            source=tampered_frontier,
        )

    committed = {
        path: path.read_bytes()
        for path in (summary_path, config_path, frontier_path, budget_path)
    }
    assert main(command) == 0
    assert {path: path.read_bytes() for path in committed} == committed

    def unexpected_resume_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("completed-summary guard must run before a provider")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_resume_provider)
    for field, value in (
        ("full_candidate_frontier_sha256", "sha256:" + "0" * 64),
        ("full_candidate_frontier_count", 2),
    ):
        tampered_summary = json.loads(committed[summary_path])
        tampered_summary[field] = value
        summary_path.write_text(json.dumps(tampered_summary, sort_keys=True) + "\n")
        assert main(command) == 2
        assert "full frontier summary mismatch" in capsys.readouterr().err
        summary_path.write_bytes(committed[summary_path])
    frontier_path.unlink()
    assert main(command) == 2
    assert "stage output commitment mismatch" in capsys.readouterr().err
    assert not frontier_path.exists()
    frontier_path.write_bytes(committed[frontier_path])

    def unexpected_bridge(*args: object, **kwargs: object) -> object:
        raise AssertionError("changed target must fail before a provider client")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_bridge)
    changed = list(command)
    changed[changed.index("2")] = "3"
    assert main(changed) == 2
    assert "changed-config resume" in capsys.readouterr().err
    assert {path: path.read_bytes() for path in committed} == committed


@pytest.mark.parametrize(
    ("profile", "config_count", "summary_count", "expected"),
    [
        (cli._TARGET_100_PREPARATION, 100, 100, 100),
        (cli._TARGET_COHORT_PREPARATION, 150, 150, 150),
    ],
)
def test_materializer_resolves_only_unambiguous_target_counts(
    profile: cli._TargetPreparationProfile,
    config_count: int | None,
    summary_count: int,
    expected: int,
) -> None:
    config = {} if config_count is None else {"target_case_count": config_count}
    summary = {"target_case_count": summary_count}

    assert (
        cli._target_case_count_for_materialized_frontier(
            profile=profile,
            config=config,
            summary=summary,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("profile", "config_count", "summary_count"),
    [
        (cli._TARGET_100_PREPARATION, None, None),
        (cli._TARGET_100_PREPARATION, None, 100),
        (cli._TARGET_100_PREPARATION, None, 99),
        (cli._TARGET_100_PREPARATION, 99, 99),
        (cli._TARGET_100_PREPARATION, 100, 99),
        (cli._TARGET_COHORT_PREPARATION, None, 150),
        (cli._TARGET_COHORT_PREPARATION, 150, 149),
    ],
)
def test_materializer_rejects_ambiguous_or_mismatched_target_counts(
    profile: cli._TargetPreparationProfile,
    config_count: int | None,
    summary_count: int | None,
) -> None:
    config = {} if config_count is None else {"target_case_count": config_count}
    summary = {} if summary_count is None else {"target_case_count": summary_count}

    with pytest.raises(cli.CommandError, match="target case count"):
        cli._target_case_count_for_materialized_frontier(
            profile=profile,
            config=config,
            summary=summary,
        )


def test_target_cohort_rejects_nonpositive_and_underfilled_targets_without_stages(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=3)
    )

    def command(target: int, output_root: Path) -> list[str]:
        return [
            "acquisition",
            "prepare-target-cohort",
            "--output-root",
            str(output_root),
            "--snapshot",
            str(snapshot),
            "--expected-cycle-hash",
            cycle_hash,
            "--expected-snapshot-manifest-sha256",
            _snapshot_manifest_sha256(snapshot),
            "--target-case-count",
            str(target),
            "--fixture-documents",
            str(fixture_documents),
            "--courtlistener-fixture",
            str(courtlistener_fixture),
            "--use-embedded-entries",
            "--execute",
        ]

    invalid_root = tmp_path / "invalid"
    assert main(command(0, invalid_root)) == 2
    assert "target case count must be positive" in capsys.readouterr().err
    [invalid_attempt] = invalid_root.glob(
        "attempts/prepare-target-cohort/*/run-card.json"
    )
    assert json.loads(invalid_attempt.read_text())["paid_activity_executed"] is False
    assert not (invalid_root / "01-public-plan").exists()

    underfilled_root = tmp_path / "underfilled"
    assert main(command(4, underfilled_root)) == 2
    assert (
        "candidate pool size must be at least target case count"
        in capsys.readouterr().err
    )
    [underfilled_attempt] = underfilled_root.glob(
        "attempts/prepare-target-cohort/*/run-card.json"
    )
    attempt = json.loads(underfilled_attempt.read_text())
    assert attempt["stage"] == "prepare-target-cohort"
    assert attempt["paid_activity_requested"] is False
    assert attempt["paid_activity_executed"] is False
    assert not (underfilled_root / "01-public-plan").exists()


def test_target_cohort_resume_rejects_mutated_full_frontier_before_provider(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=3)
    )
    output_root = tmp_path / "run"
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "2",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    assert main(command) == 0
    summary_path = output_root / "target-cohort-preparation-summary.json"
    success_card = output_root / "run-cards/prepare-target-cohort.json"
    summary_before = summary_path.read_bytes()
    card_before = success_card.read_bytes()
    frontier_path = output_root / "05-budget/full-candidate-frontier.json"
    frontier = json.loads(frontier_path.read_text())
    frontier["policy"]["candidates"][0]["estimated_cost_usd"] = "0.00"
    frontier_path.write_text(json.dumps(frontier, sort_keys=True) + "\n")

    def unexpected_bridge(*args: object, **kwargs: object) -> object:
        raise AssertionError("resume verification must precede provider setup")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_bridge)
    assert main(command) == 2
    assert "stage output commitment mismatch" in capsys.readouterr().err
    assert summary_path.read_bytes() == summary_before
    assert success_card.read_bytes() == card_before


def test_target_cohort_resume_requires_resolved_success_run_card(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run"
    custom_run_card = tmp_path / "committed-run-card.json"
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "2",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--run-card-output",
        str(custom_run_card),
        "--execute",
    ]
    assert main(command) == 0
    summary = output_root / "target-cohort-preparation-summary.json"
    summary_before = summary.read_bytes()
    custom_run_card.unlink()

    def unexpected_bridge(*args: object, **kwargs: object) -> object:
        raise AssertionError("run-card verification must precede provider setup")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_bridge)
    assert main(command) == 2
    assert "committed success run card is missing" in capsys.readouterr().err
    assert summary.read_bytes() == summary_before


def test_target_cohort_frontier_rejects_orphan_manifest_rows(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    manifest_path = output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
    manifest = _read_jsonl(manifest_path)
    orphan = dict(manifest[0])
    orphan["candidate_id"] = "orphan-candidate"
    _write_jsonl(manifest_path, [*manifest, orphan])
    budget_plan = cli._missing_core_budget_plan(
        json.loads(
            (output_root / "05-budget/missing-core-budget-plan.json").read_text()
        )
    )
    config = TargetCohortPreparationConfig(
        output_root=output_root,
        snapshot=snapshot,
        expected_cycle_hash=cycle_hash,
        expected_snapshot_manifest_sha256=_snapshot_manifest_sha256(snapshot),
        candidate_pool_size=2,
        target_case_count=2,
        authenticated_screened_cases=(
            output_root / "00-authenticated-snapshot/screened-cases.jsonl"
        ),
        screened_cases_sha256=hashlib.sha256(
            (
                output_root / "00-authenticated-snapshot/screened-cases.jsonl"
            ).read_bytes()
        ).hexdigest(),
        fixture_documents=fixture_documents,
        courtlistener_fixture=courtlistener_fixture,
        use_embedded_entries=True,
    )

    with pytest.raises(cli.CommandError, match="orphan download-manifest"):
        cli._prepare_full_candidate_frontier(
            output_root,
            budget_plan=budget_plan,
            target_case_count=config.target_case_count,
            cost_per_document_usd=config.cost_per_document_usd,
            max_missing_core_documents_per_case=(
                config.max_missing_core_documents_per_case
            ),
            snapshot_manifest_path=snapshot / "manifest.json",
            preparation_config_path=output_root / "target-cohort-config.json",
            frontier_path=output_root / "05-budget/full-candidate-frontier.json",
            resume=True,
        )


def test_target_cohort_custom_common_outputs_cannot_alias_inputs(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    fixture_before = courtlistener_fixture.read_bytes()
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(tmp_path / "run"),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--run-card-output",
                str(courtlistener_fixture),
            ]
        )
        == 2
    )
    assert "overlap" in capsys.readouterr().err
    assert courtlistener_fixture.read_bytes() == fixture_before


def test_generic_preparation_is_accepted_by_post_clearance_projection(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=3)
    )
    prepared = tmp_path / "prepared"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(prepared),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    clearance_root = tmp_path / "clearance"
    restriction_path = prepared / "06-clearance-inputs/restriction-evidence.jsonl"
    download_manifest = (
        prepared / "03c-merged-downloads/document-downloads-merged.jsonl"
    )
    review = _write_authenticated_reviews(
        tmp_path / "review",
        manifest_path=download_manifest,
        document_root=prepared / "documents/free",
        review_requests_path=(
            prepared / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=restriction_path,
        store_uri="private-store://fixture/generic",
    )
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(download_manifest),
                "--review-requests",
                str(review.requests),
                "--document-root",
                str(prepared / "documents/free"),
                "--review-worksheet",
                str(review.worksheet),
                "--reviews",
                str(review.reviews),
                "--review-receipt",
                str(review.receipt),
                "--reviewer-policy",
                str(review.policy),
                "--cohort-policy",
                str(review.cohort_policy),
                "--restriction-evidence",
                str(restriction_path),
                "--output-root",
                str(clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    projected = tmp_path / "projected"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projected),
                "--selection",
                str(
                    prepared / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(prepared / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(download_manifest),
                "--disclosure-clearance",
                str(clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(restriction_path),
                "--preparation-summary",
                str(prepared / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(prepared / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-case-count",
                "2",
                "--execute",
            ]
        )
        == 0
    )
    projection = json.loads((projected / "target-cohort-projection.json").read_text())
    assert projection["selected_case_count"] == 2


def test_target_100_cli_help_explains_provider_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "prepare-target-100", "--help"])
    output = capsys.readouterr().out
    assert "Complete saturated snapshot" in output
    assert "never purchases" in output
    assert "CourtListener" in output
    assert "Case.dev" in output

    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "--help"])
    top_help = capsys.readouterr().out
    assert "CourtListener REST is the only production final authority" in top_help
    assert "DISABLED for live use: legacy Case.dev/PACER" in top_help
    assert "DISABLED for live use: legacy Case.dev docket-refresh" in top_help


def test_target_100_candidate_pool_size_has_no_stale_default(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="candidate_pool_size"):
        Target100PreparationConfig(  # type: ignore[call-arg]
            output_root=tmp_path / "run",
            snapshot=tmp_path / "snapshot",
            expected_cycle_hash="a" * 64,
            expected_snapshot_manifest_sha256="b" * 64,
        )


def test_target_100_dry_run_writes_a_nonpurchase_stage_plan(tmp_path: Path) -> None:
    output_root = tmp_path / "run"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["dry_run"] is True
    assert summary["target_case_count"] == 100
    assert summary["paid_activity_requested"] is False
    assert summary["paid_activity_executed"] is False
    assert all(
        row["stage"] != "purchase-missing-recap-fetch"
        for row in summary["stage_commands"]
    )


def test_target_preparation_uses_buffered_screened_view_after_source_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run"
    load_verified = cli.load_verified_screening_snapshot

    def load_then_swap(*args: Any, **kwargs: Any) -> Any:
        verified = load_verified(*args, **kwargs)
        (snapshot / "screened-cases.jsonl").write_bytes(b"")
        return verified

    monkeypatch.setattr(cli, "load_verified_screening_snapshot", load_then_swap)
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
            ]
        )
        == 0
    )

    authenticated = output_root / "00-authenticated-snapshot/screened-cases.jsonl"
    assert len(_read_jsonl(authenticated)) == 2
    config = json.loads((output_root / "target-cohort-config.json").read_text())
    summary = json.loads(
        (output_root / "target-cohort-preparation-summary.json").read_text()
    )
    assert config["candidate_pool_size"] == 2
    assert summary["candidate_pool_size"] == 2
    assert config["authenticated_screened_cases"] == str(authenticated.resolve())
    bridge = next(
        command
        for command in summary["stage_commands"]
        if command["stage"] == "bridge-pacer-gaps"
    )
    assert bridge["argv"][bridge["argv"].index("--screened-cases") + 1] == str(
        authenticated
    )


def test_target_preparation_fails_if_manifest_swaps_before_child_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run"
    expected_manifest_sha256 = _snapshot_manifest_sha256(snapshot)
    build_commands = cli.build_target_cohort_stage_commands

    def build_then_swap(config: TargetCohortPreparationConfig) -> Any:
        commands = build_commands(config)
        manifest = snapshot / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b" ")
        return commands

    monkeypatch.setattr(
        cli,
        "build_target_cohort_stage_commands",
        build_then_swap,
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                expected_manifest_sha256,
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 2
    )
    assert not (output_root / "03-gap-bridge").exists()


def test_target_preparation_uses_owned_raw_bytes_after_source_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run"
    raw_records = _read_jsonl(snapshot / "raw-artifacts.jsonl")
    source_raw_dir = Path(str(raw_records[0]["path"])).parent
    source_raw_path = source_raw_dir / "1000.html"
    admitted_payload = source_raw_path.read_bytes()
    real_main = cli.main

    def mutate_source_before_plan(argv: list[str] | tuple[str, ...]) -> int:
        if tuple(argv[:2]) == ("acquisition", "plan-public-downloads"):
            source_raw_path.write_bytes(b"<html>attacker replacement</html>")
        return real_main(argv)

    monkeypatch.setattr(cli, "main", mutate_source_before_plan)
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--raw-html-dir",
                str(source_raw_dir),
                "--execute",
            ]
        )
        == 0
    )

    owned_raw_dir = output_root / "00-authenticated-snapshot/raw-html"
    owned_manifest = output_root / "00-authenticated-snapshot/raw-html-manifest.jsonl"
    assert source_raw_path.read_bytes() != admitted_payload
    assert (owned_raw_dir / "1000.html").read_bytes() == admitted_payload
    config = json.loads((output_root / "target-cohort-config.json").read_text())
    assert config["requested_raw_html_dir"] == str(source_raw_dir.resolve())
    assert config["raw_html_dir"] == str(owned_raw_dir.resolve())
    assert config["authenticated_raw_html_manifest"] == str(owned_manifest.resolve())
    assert config["authenticated_raw_html_manifest_sha256"] == (
        "sha256:" + hashlib.sha256(owned_manifest.read_bytes()).hexdigest()
    )
    bridge = next(
        command
        for command in config["stage_commands"]
        if command["stage"] == "bridge-pacer-gaps"
    )
    public_plan = next(
        command
        for command in config["stage_commands"]
        if command["stage"] == "plan-public-downloads"
    )
    assert public_plan["argv"][
        public_plan["argv"].index("--screened-cases") + 1
    ] == str(output_root / "00-authenticated-snapshot/screened-cases.jsonl")
    assert public_plan["argv"][public_plan["argv"].index("--raw-html-dir") + 1] == str(
        owned_raw_dir
    )
    assert public_plan["argv"][
        public_plan["argv"].index("--authenticated-raw-html-manifest") + 1
    ] == str(owned_manifest)
    assert str(source_raw_dir) not in public_plan["argv"]
    assert bridge["argv"][bridge["argv"].index("--raw-html-dir") + 1] == str(
        owned_raw_dir
    )
    assert str(source_raw_dir) not in bridge["argv"]
    summary = json.loads(
        (output_root / "target-cohort-preparation-summary.json").read_text()
    )
    gap_inputs = summary["stage_input_commitments"]["03-gap-bridge"]
    assert str(owned_manifest.resolve()) in gap_inputs
    assert str((owned_raw_dir / "1000.html").resolve()) in gap_inputs
    assert str(source_raw_path.resolve()) not in gap_inputs


def test_target_preparation_uses_owned_screened_bytes_before_public_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run-owned-screened"
    source_screened = snapshot / "screened-cases.jsonl"
    real_main = cli.main

    def delete_source_before_plan(argv: list[str] | tuple[str, ...]) -> int:
        if tuple(argv[:2]) == ("acquisition", "plan-public-downloads"):
            source_screened.unlink()
        return real_main(argv)

    monkeypatch.setattr(cli, "main", delete_source_before_plan)
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    summary = json.loads(
        (output_root / "01-public-plan/public-packet-plan-summary.json").read_text()
    )
    owned_screened = output_root / "00-authenticated-snapshot/screened-cases.jsonl"
    assert summary["authenticated_screened_cases_sha256"] == (
        "sha256:" + hashlib.sha256(owned_screened.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("owned_input", ("screened", "raw"))
def test_target_preparation_fails_if_owned_input_mutates_after_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owned_input: str,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / f"run-{owned_input}"
    source_raw_dir = Path(
        str(_read_jsonl(snapshot / "raw-artifacts.jsonl")[0]["path"])
    ).parent
    real_main = cli.main

    def mutate_owned_after_plan(argv: list[str] | tuple[str, ...]) -> int:
        result = real_main(argv)
        if tuple(argv[:2]) == ("acquisition", "plan-public-downloads"):
            target = (
                output_root / "00-authenticated-snapshot/screened-cases.jsonl"
                if owned_input == "screened"
                else output_root / "00-authenticated-snapshot/raw-html/1000.html"
            )
            target.write_bytes(target.read_bytes() + b"\nattacker")
        return result

    monkeypatch.setattr(cli, "main", mutate_owned_after_plan)
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--raw-html-dir",
                str(source_raw_dir),
                "--execute",
            ]
        )
        == 2
    )
    assert not (output_root / "target-cohort-preparation-summary.json").exists()


def test_target_preparation_rejects_route_mutation_after_bridge_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run-route-mutation"
    admit_routes = cli._read_authenticated_public_first_bridge_inputs

    def admit_then_mutate_routes(**kwargs: Any) -> Any:
        admitted = admit_routes(**kwargs)
        public_selection = cast(Path, kwargs["public_selection_path"])
        public_selection.write_bytes(public_selection.read_bytes() + b"\n")
        return admitted

    monkeypatch.setattr(
        cli,
        "_read_authenticated_public_first_bridge_inputs",
        admit_then_mutate_routes,
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 2
    )
    assert (output_root / "03-gap-bridge/pacer-gap-bridge-summary.json").is_file()
    assert not (output_root / "target-cohort-preparation-summary.json").exists()


def test_target_preparation_resume_rejects_route_mutation(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run-route-resume"
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "2",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    assert main(command) == 0
    public_selection = output_root / "01-public-plan/public-packet-selection.jsonl"
    public_selection.write_bytes(public_selection.read_bytes() + b"\n")

    assert main(command) == 2


def test_target_preparation_resumes_after_interruption_with_bridge_checkpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=2)
    )
    output_root = tmp_path / "run-bridge-interruption"
    command = [
        "acquisition",
        "prepare-target-cohort",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--target-case-count",
        "2",
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    child_main = cli.main
    interrupt_bridge = True

    def interrupt_after_bridge(
        argv: list[str] | tuple[str, ...],
    ) -> int:
        nonlocal interrupt_bridge
        result = child_main(argv)
        if interrupt_bridge and tuple(argv[:2]) == ("acquisition", "bridge-pacer-gaps"):
            interrupt_bridge = False
            return 2
        return result

    monkeypatch.setattr(cli, "main", interrupt_after_bridge)
    assert main(command) == 2
    manifest_path = output_root / "02-free-download/free-document-downloads.jsonl"
    manifest_before = manifest_path.read_bytes()
    bridge_checkpoints = tuple(
        (output_root / "03-gap-bridge/checkpoints/pacer-gap-bridge").glob("*.json")
    )
    assert len(bridge_checkpoints) == 2
    assert not (output_root / "target-cohort-preparation-summary.json").exists()

    monkeypatch.setattr(cli, "main", child_main)
    assert main(command) == 0

    assert manifest_path.read_bytes() == manifest_before
    bridge_card = json.loads(
        (output_root / "03-gap-bridge/run-cards/bridge-pacer-gaps.json").read_text()
    )
    assert bridge_card["resumed_terminal_candidate_count"] == 2
    assert bridge_card["checkpoint_terminal_candidate_count"] == 2
    assert bridge_card["reconciled"] is True


def test_target_100_real_five_stage_courtlistener_fixture_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "run"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=101)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["selected_case_count"] == 100
    assert summary["candidate_pool_size"] == 101
    assert summary["next_stage"] == "clear-disclosures"
    assert summary["budget_status"] == "provisional_pre_clearance"
    assert summary["paid_activity_executed"] is False
    assert summary["total_missing_core_documents"] == 100
    assert summary["total_estimated_cost_usd"] == "305.00"
    assert summary["config_sha256"].startswith("sha256:")
    assert summary["selected_candidate_ids_sha256"].startswith("sha256:")
    assert summary["frontier_sha256"].startswith("sha256:")
    assert not (output_root / "05-budget/full-candidate-frontier.json").exists()
    assert set(summary["stage_commitments"]) == {
        "01-public-plan",
        "02-free-download",
        "03-gap-bridge",
        "03b-bridge-free-download",
        "03c-merged-downloads",
        "04-core-filter",
        "05-budget",
        "06-clearance-inputs",
        "documents",
    }
    bridge_card = json.loads(
        (output_root / "03-gap-bridge/run-cards/bridge-pacer-gaps.json").read_text()
    )
    assert bridge_card["bridge_provider"] == "courtlistener_rest"
    assert bridge_card["paid_activity_executed"] is False

    config_path = output_root / "target-100-config.json"
    budget_path = output_root / "05-budget/missing-core-budget-plan.json"
    success_card_path = output_root / "run-cards/prepare-target-100.json"

    missing_output_root = output_root / "forbidden-materializer-output"
    overlapping_command = [
        "acquisition",
        "materialize-target-cohort-frontier",
        "--output-root",
        str(missing_output_root),
        "--preparation-root",
        str(output_root),
        "--preparation-summary",
        str(output_root / "target-100-preparation-summary.json"),
        "--preparation-config",
        str(config_path),
        "--snapshot-manifest",
        str(snapshot / "manifest.json"),
        "--execute",
    ]
    assert main(overlapping_command) == 2
    assert not missing_output_root.exists()

    summary_path = output_root / "target-100-preparation-summary.json"
    summary_before = summary_path.read_bytes()
    incomplete_summary = json.loads(summary_before)
    incomplete_summary["stage_input_commitments"].pop("01-public-plan")
    summary_path.write_text(
        json.dumps(incomplete_summary, indent=2, sort_keys=True) + "\n"
    )
    rejected_root = tmp_path / "rejected-incomplete-commitments"
    rejected_command = [
        "acquisition",
        "materialize-target-cohort-frontier",
        "--output-root",
        str(rejected_root),
        "--preparation-root",
        str(output_root),
        "--preparation-summary",
        str(summary_path),
        "--preparation-config",
        str(config_path),
        "--snapshot-manifest",
        str(snapshot / "manifest.json"),
        "--execute",
    ]
    assert main(rejected_command) == 2
    assert not rejected_root.exists()
    summary_path.write_bytes(summary_before)

    budget_before = budget_path.read_bytes()
    for missing_fields in (
        ("target_case_count",),
        ("target_case_count_met",),
        ("target_case_count", "target_case_count_met"),
    ):
        incomplete_budget = json.loads(budget_before)
        for missing_field in missing_fields:
            incomplete_budget.pop(missing_field)
        budget_path.write_text(
            json.dumps(incomplete_budget, indent=2, sort_keys=True) + "\n"
        )
        budget_tamper_summary = json.loads(summary_before)
        budget_tamper_summary["stage_commitments"] = cli._target_100_stage_commitments(
            output_root
        )
        summary_path.write_text(
            json.dumps(budget_tamper_summary, indent=2, sort_keys=True) + "\n"
        )
        rejected_budget_root = tmp_path / (
            "rejected-budget-" + "-".join(missing_fields)
        )
        assert (
            main(
                [
                    *rejected_command[:3],
                    str(rejected_budget_root),
                    *rejected_command[4:],
                ]
            )
            == 2
        )
        assert not rejected_budget_root.exists()
        budget_path.write_bytes(budget_before)
        summary_path.write_bytes(summary_before)

    fixture_documents_before = fixture_documents.read_bytes()
    fixture_documents.write_bytes(fixture_documents_before + b"\n")
    rejected_fixture_root = tmp_path / "rejected-mutated-fixture"
    assert (
        main(
            [
                *rejected_command[:3],
                str(rejected_fixture_root),
                *rejected_command[4:],
            ]
        )
        == 2
    )
    assert not rejected_fixture_root.exists()
    fixture_documents.write_bytes(fixture_documents_before)

    success_card_before = success_card_path.read_bytes()
    external_alias_root = tmp_path / "rejected-success-card-alias"
    assert (
        main(
            [
                *rejected_command[:3],
                str(external_alias_root),
                *rejected_command[4:],
                "--run-card-output",
                str(success_card_path),
            ]
        )
        == 2
    )
    assert success_card_path.read_bytes() == success_card_before
    assert not external_alias_root.exists()
    success_log_path = output_root / "logs/prepare-target-100.jsonl"
    success_log_before = success_log_path.read_bytes()
    external_log_alias_root = tmp_path / "rejected-success-log-alias"
    assert (
        main(
            [
                *rejected_command[:3],
                str(external_log_alias_root),
                *rejected_command[4:],
                "--log-output",
                str(success_log_path),
            ]
        )
        == 2
    )
    assert success_log_path.read_bytes() == success_log_before
    assert not external_log_alias_root.exists()
    hardlinked_log = tmp_path / "hardlinked-success-log.jsonl"
    hardlinked_log.hardlink_to(success_log_path)
    hardlink_output_root = tmp_path / "rejected-success-log-hardlink"
    assert (
        main(
            [
                *rejected_command[:3],
                str(hardlink_output_root),
                *rejected_command[4:],
                "--log-output",
                str(hardlinked_log),
            ]
        )
        == 2
    )
    assert success_log_path.read_bytes() == success_log_before
    assert not hardlink_output_root.exists()
    hardlinked_log.unlink()

    legacy_before = {
        path.relative_to(output_root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output_root.rglob("*")
        if path.is_file()
    }

    def unexpected_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("post-hoc frontier must not construct a provider")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_provider)
    materialized_root = tmp_path / "materialized-frontier"
    materialize_command = [
        "acquisition",
        "materialize-target-cohort-frontier",
        "--output-root",
        str(materialized_root),
        "--preparation-root",
        str(output_root),
        "--preparation-summary",
        str(output_root / "target-100-preparation-summary.json"),
        "--preparation-config",
        str(output_root / "target-100-config.json"),
        "--snapshot-manifest",
        str(snapshot / "manifest.json"),
        "--execute",
    ]
    assert main(materialize_command) == 0
    frontier_path = materialized_root / "full-candidate-frontier.json"
    materializer_card = (
        materialized_root / "run-cards/materialize-target-cohort-frontier.json"
    )
    frontier = json.loads(frontier_path.read_text())
    completed_materializer = json.loads(materializer_card.read_text())
    commitments = frontier["policy"]["source_commitments"]
    assert frontier["policy"]["candidate_count"] == 101
    assert frontier["policy"]["selected_candidate_count"] == 100
    assert completed_materializer["record_count"] == 101
    assert completed_materializer["target_case_count"] == 100
    assert commitments["preparation_summary_sha256"] == (
        "sha256:"
        + hashlib.sha256(
            (output_root / "target-100-preparation-summary.json").read_bytes()
        ).hexdigest()
    )
    assert commitments["preparation_success_run_card_sha256"] == (
        "sha256:"
        + hashlib.sha256(
            (output_root / "run-cards/prepare-target-100.json").read_bytes()
        ).hexdigest()
    )
    frontier_before = frontier_path.read_bytes()
    card_before = materializer_card.read_bytes()
    assert main(materialize_command) == 0
    assert frontier_path.read_bytes() == frontier_before
    assert materializer_card.read_bytes() == card_before
    frontier_path.unlink()
    assert main(materialize_command) == 2
    assert not frontier_path.exists()
    frontier_path.write_bytes(frontier_before)
    legacy_after = {
        path.relative_to(output_root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    assert legacy_after == legacy_before

    free_manifest = _read_jsonl(
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
    )
    assert (
        _read_jsonl(
            output_root / "03b-bridge-free-download/free-document-downloads.jsonl"
        )
        == []
    )
    assert len(
        _read_jsonl(
            output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
        )
    ) == len(free_manifest)
    clearance_root = tmp_path / "free-clearance"
    restriction_path = output_root / "06-clearance-inputs/restriction-evidence.jsonl"
    download_manifest_path = (
        output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
    )
    review = _write_authenticated_reviews(
        tmp_path / "free-review",
        manifest_path=download_manifest_path,
        document_root=output_root / "documents/free",
        review_requests_path=(
            output_root / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=restriction_path,
        store_uri="private-store://fixture/target-100",
    )
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(download_manifest_path),
                "--review-requests",
                str(review.requests),
                "--document-root",
                str(output_root / "documents/free"),
                "--review-worksheet",
                str(review.worksheet),
                "--reviews",
                str(review.reviews),
                "--review-receipt",
                str(review.receipt),
                "--reviewer-policy",
                str(review.policy),
                "--cohort-policy",
                str(review.cohort_policy),
                "--restriction-evidence",
                str(restriction_path),
                "--output-root",
                str(clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    clearance = clearance_root / "disclosure-clearance.jsonl"
    clearance_run_card = clearance_root / "run-cards/clear-disclosures.json"
    assert not _read_jsonl(clearance_root / "disclosure-quarantine.jsonl")
    projected = tmp_path / "projected"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projected),
                "--selection",
                str(
                    output_root
                    / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(output_root / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(
                    output_root / "03c-merged-downloads/document-downloads-merged.jsonl"
                ),
                "--disclosure-clearance",
                str(clearance),
                "--clearance-run-card",
                str(clearance_run_card),
                "--restriction-evidence",
                str(restriction_path),
                "--preparation-summary",
                str(output_root / "target-100-preparation-summary.json"),
                "--preparation-config",
                str(output_root / "target-100-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--execute",
            ]
        )
        == 0
    )
    budget_plan = projected / "missing-core-budget-plan.json"
    selection = projected / "target-cohort-selection.jsonl"
    approval = build_approved_purchase_fixture(
        tmp_path / "purchase-v2-authority",
        target_cohort_root=projected,
    )
    purchase_policy = approval.policy
    cohort_policy = approval.cohort_policy
    purchase_ledger = approval.ledger
    broker_policy = tmp_path / "recap-fetch-broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--output",
                str(broker_policy),
            ]
        )
        == 0
    )
    broker = json.loads(broker_policy.read_text())
    allowed_document_ids = [
        record["recap_document"] for record in broker["allowed_documents"]
    ]
    assert len(allowed_document_ids) == 100
    assert all(str(document_id).isdigit() for document_id in allowed_document_ids)

    purchase_cl_fixture, purchase_broker_fixture = _purchase_fixtures(
        tmp_path, allowed_document_ids
    )
    purchase_output = tmp_path / "offline-purchase"
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--initialization-receipt-output",
                str(approval.initialization_receipt),
                "--output-root",
                str(tmp_path / "purchase-ledger-initialization"),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--output-root",
                str(purchase_output),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--purchase-ledger-initialization-receipt",
                str(approval.initialization_receipt),
                "--courtlistener-fixture",
                str(purchase_cl_fixture),
                "--purchase-broker-fixture",
                str(purchase_broker_fixture),
                "--execute",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )
    purchase_card = json.loads(
        (purchase_output / "run-cards/purchase-missing-recap-fetch.json").read_text()
    )
    assert purchase_card["paid_activity_requested"] is False
    assert purchase_card["paid_activity_executed"] is False


def test_immutable_materializer_two_source_cli_is_parse_ready_and_resumable(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation = tmp_path / "preparation"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "fixture", case_count=1)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(preparation),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--target-case-count",
                "1",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    free_manifest = preparation / "03c-merged-downloads/document-downloads-merged.jsonl"
    free_restrictions = preparation / "06-clearance-inputs/restriction-evidence.jsonl"
    free_clearance_root = tmp_path / "free-clearance"
    free_review = _write_authenticated_reviews(
        tmp_path / "free-review",
        manifest_path=free_manifest,
        document_root=preparation / "documents/free",
        review_requests_path=(
            preparation / "06-clearance-inputs/disclosure-review-requests.jsonl"
        ),
        restriction_evidence_path=free_restrictions,
        store_uri="private-store://fixture/materializer-free",
    )
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(free_manifest),
                "--review-requests",
                str(free_review.requests),
                "--document-root",
                str(preparation / "documents/free"),
                "--review-worksheet",
                str(free_review.worksheet),
                "--reviews",
                str(free_review.reviews),
                "--review-receipt",
                str(free_review.receipt),
                "--reviewer-policy",
                str(free_review.policy),
                "--cohort-policy",
                str(free_review.cohort_policy),
                "--restriction-evidence",
                str(free_restrictions),
                "--output-root",
                str(free_clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    projection = tmp_path / "projection"
    assert (
        main(
            [
                "acquisition",
                "project-target-cohort",
                "--output-root",
                str(projection),
                "--selection",
                str(
                    preparation
                    / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
                ),
                "--case-relevance",
                str(preparation / "03-gap-bridge/case-relevance.jsonl"),
                "--download-manifest",
                str(free_manifest),
                "--disclosure-clearance",
                str(free_clearance_root / "disclosure-clearance.jsonl"),
                "--clearance-run-card",
                str(free_clearance_root / "run-cards/clear-disclosures.json"),
                "--restriction-evidence",
                str(free_restrictions),
                "--preparation-summary",
                str(preparation / "target-cohort-preparation-summary.json"),
                "--preparation-config",
                str(preparation / "target-cohort-config.json"),
                "--snapshot-manifest",
                str(snapshot / "manifest.json"),
                "--target-case-count",
                "1",
                "--execute",
            ]
        )
        == 0
    )
    selection = projection / "target-cohort-selection.jsonl"
    budget_plan = projection / "missing-core-budget-plan.json"
    approval = build_approved_purchase_fixture(
        tmp_path / "purchase-v2-authority",
        target_cohort_root=projection,
    )
    purchase_policy = approval.policy
    cohort_policy = approval.cohort_policy
    purchase_ledger = approval.ledger
    broker_policy = tmp_path / "broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--output",
                str(broker_policy),
            ]
        )
        == 0
    )
    [allowed] = json.loads(broker_policy.read_text())["allowed_documents"]
    purchase_cl_fixture, purchase_broker_fixture = _purchase_fixtures(
        tmp_path, [str(allowed["recap_document"])]
    )
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--initialization-receipt-output",
                str(approval.initialization_receipt),
                "--output-root",
                str(tmp_path / "ledger-init"),
                "--execute",
            ]
        )
        == 0
    )
    purchase_root = tmp_path / "purchase"
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--output-root",
                str(purchase_root),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--purchase-ledger-initialization-receipt",
                str(approval.initialization_receipt),
                "--courtlistener-fixture",
                str(purchase_cl_fixture),
                "--purchase-broker-fixture",
                str(purchase_broker_fixture),
                "--execute",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )
    purchase_result = purchase_root / "courtlistener-recap-fetch-purchases.json"
    purchase_attempt = json.loads(purchase_result.read_text())["attempts"][0]
    purchased_fixture = tmp_path / "purchased-pdfs.json"
    purchased_fixture.write_text(
        json.dumps(
            {purchase_attempt["download_url"]: _fixture_pdf_text("Purchased motion")}
        )
    )
    recovery = tmp_path / "recovery"
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(purchase_result),
                "--selection",
                str(selection),
                "--output-root",
                str(recovery),
                "--fixture-documents",
                str(purchased_fixture),
                "--execute",
            ]
        )
        == 0
    )
    purchased_manifest = recovery / "purchased-document-downloads.jsonl"
    [purchased_row] = _read_jsonl(purchased_manifest)
    purchased_restrictions = tmp_path / "purchased-restrictions.jsonl"
    _write_jsonl(
        purchased_restrictions,
        [
            {
                "candidate_id": purchased_row["candidate_id"],
                "source_document_id": purchased_row["source_document_id"],
                "restriction_status": "public",
                "restriction_evidence": ["courtlistener_recap_fetch_public"],
                "is_sealed": False,
                "is_private": False,
            }
        ],
    )
    purchased_review = _write_authenticated_reviews(
        tmp_path / "purchased-review",
        manifest_path=purchased_manifest,
        document_root=recovery / "documents/purchased",
        restriction_evidence_path=purchased_restrictions,
        store_uri="private-store://fixture/materializer-purchased",
    )
    purchased_clearance_root = tmp_path / "purchased-clearance"
    assert (
        main(
            [
                "acquisition",
                "clear-disclosures",
                "--download-manifest",
                str(purchased_manifest),
                "--review-requests",
                str(purchased_review.requests),
                "--document-root",
                str(recovery / "documents/purchased"),
                "--review-worksheet",
                str(purchased_review.worksheet),
                "--reviews",
                str(purchased_review.reviews),
                "--review-receipt",
                str(purchased_review.receipt),
                "--reviewer-policy",
                str(purchased_review.policy),
                "--cohort-policy",
                str(purchased_review.cohort_policy),
                "--restriction-evidence",
                str(purchased_restrictions),
                "--output-root",
                str(purchased_clearance_root),
                "--execute",
            ]
        )
        == 0
    )
    ledger_paths = tuple(
        path
        for path in (
            purchase_ledger,
            Path(f"{purchase_ledger}.lock"),
            Path(f"{purchase_ledger}-wal"),
            Path(f"{purchase_ledger}-shm"),
            Path(f"{purchase_ledger}-journal"),
        )
        if path.exists()
    )
    ledger_before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in ledger_paths
    }
    purchase_runtime_args = [
        "--purchase-policy",
        str(purchase_policy),
        "--purchase-ledger",
        str(purchase_ledger),
        "--controlled-private-root",
        str(approval.controlled_private_root),
        "--purchase-ledger-initialization-receipt",
        str(approval.initialization_receipt),
    ]
    private_purchase_runtime_args = [
        "--controlled-private-root",
        str(approval.controlled_private_root),
        "--purchase-ledger-initialization-receipt",
        str(approval.initialization_receipt),
    ]
    materialized = tmp_path / "materialized"
    command = [
        "acquisition",
        "materialize-cohort-documents",
        "--output-root",
        str(materialized),
        "--preparation-root",
        str(preparation),
        "--preparation-summary",
        str(preparation / "target-cohort-preparation-summary.json"),
        "--preparation-config",
        str(preparation / "target-cohort-config.json"),
        "--snapshot-manifest",
        str(snapshot / "manifest.json"),
        "--target-cohort-root",
        str(projection),
        "--free-disclosure-clearance",
        str(projection / "disclosure-clearance.jsonl"),
        "--purchased-recovery-root",
        str(recovery),
        "--purchased-disclosure-clearance",
        str(purchased_clearance_root / "disclosure-clearance.jsonl"),
        "--purchased-clearance-run-card",
        str(purchased_clearance_root / "run-cards/clear-disclosures.json"),
        "--purchase-policy",
        str(purchase_policy),
        "--cohort-policy",
        str(cohort_policy),
        "--purchase-ledger",
        str(purchase_ledger),
        "--controlled-private-root",
        str(approval.controlled_private_root),
        "--purchase-ledger-initialization-receipt",
        str(approval.initialization_receipt),
        "--execute",
    ]
    symlink_target = tmp_path / "external-materializer-target"
    free_row = next(
        row
        for row in _read_jsonl(free_manifest)
        if row["source_document_id"] != purchased_row["source_document_id"]
    )
    free_digest = str(free_row["sha256"])
    external_parent = symlink_target / "sha256" / free_digest[:2]
    external_parent.mkdir(parents=True)
    external_temporary = external_parent / (f".{free_digest}.pdf.4321.{('a' * 32)}.tmp")
    external_payload = b"must remain outside the materializer"
    external_temporary.write_bytes(external_payload)
    materialized.mkdir()
    (materialized / "documents").symlink_to(
        symlink_target,
        target_is_directory=True,
    )
    assert main(command) == 2
    assert external_temporary.read_bytes() == external_payload
    assert (materialized / "documents").is_symlink()
    (materialized / "documents").unlink()
    forbidden_source_output = preparation / "forbidden-materializer-output"
    assert main([*command[:3], str(forbidden_source_output), *command[4:]]) == 2
    assert not forbidden_source_output.exists()
    free_manifest_before = free_manifest.read_bytes()
    assert main([*command, "--run-card-output", str(free_manifest)]) == 2
    assert free_manifest.read_bytes() == free_manifest_before
    assert main(command) == 0
    run_card = materialized / "run-cards/materialize-cohort-documents.json"
    card_before = run_card.read_bytes()
    assert main(command) == 0
    assert run_card.read_bytes() == card_before
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in ledger_paths
    } == ledger_before
    combined = _read_jsonl(materialized / "document-downloads-merged.jsonl")
    assert {row["free_or_purchased"] for row in combined} == {"free", "purchased"}
    crash_destination = materialized / "documents" / str(combined[0]["local_path"])
    linked_temporary = crash_destination.with_name(
        f".{crash_destination.name}.4321.post-link.tmp"
    )
    os.link(crash_destination, linked_temporary)
    assert main(command) == 0
    assert crash_destination.stat().st_nlink == 1
    assert not linked_temporary.exists()
    run_card.unlink()
    crash_destination.unlink()
    partial_temporary = crash_destination.with_name(
        f".{crash_destination.name}.4321.pre-link.tmp"
    )
    partial_temporary.write_bytes(b"partial")
    assert main(command) == 0
    assert crash_destination.is_file()
    assert not partial_temporary.exists()
    unexpected_fifo = materialized / "unexpected.fifo"
    os.mkfifo(unexpected_fifo)
    assert main(command) == 2
    unexpected_fifo.unlink()
    substituted_selection = tmp_path / "substituted-selection.jsonl"
    substituted_rows = _read_jsonl(selection)
    substituted_rows[0]["case_name"] = "Substituted v. Cohort"
    _write_jsonl(substituted_selection, substituted_rows)
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--selection",
                str(substituted_selection),
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--document-root",
                str(materialized / "documents"),
                "--materialization-run-card",
                str(run_card),
                *purchase_runtime_args,
                "--output-root",
                str(tmp_path / "substituted-selection-attack"),
                "--execute",
            ]
        )
        == 2
    )
    parse_root = tmp_path / "parse-plan"
    plan_parse_command = [
        "acquisition",
        "plan-parse-documents",
        "--selection",
        str(selection),
        "--download-manifest",
        str(materialized / "document-downloads-merged.jsonl"),
        "--disclosure-clearance",
        str(materialized / "disclosure-clearance.jsonl"),
        "--document-root",
        str(materialized / "documents"),
        "--materialization-run-card",
        str(run_card),
        *purchase_runtime_args,
        "--output-root",
        str(parse_root),
        "--execute",
    ]
    assert main(plan_parse_command) == 0
    canonical_card_bytes = run_card.read_bytes()
    tampered_card = json.loads(canonical_card_bytes)
    del tampered_card["source_commitments"]["target_selection"]
    run_card.write_text(json.dumps(tampered_card), encoding="utf-8")
    assert main(plan_parse_command) == 2
    run_card.write_bytes(canonical_card_bytes)
    tampered_card = json.loads(canonical_card_bytes)
    tampered_card["source_commitments"]["target_selection"]["sha256"] = (
        "sha256:" + "0" * 64
    )
    run_card.write_text(json.dumps(tampered_card), encoding="utf-8")
    assert main(plan_parse_command) == 2
    run_card.write_bytes(canonical_card_bytes)
    summary_path = materialized / "cohort-document-materialization.json"
    canonical_summary_bytes = summary_path.read_bytes()
    tampered_summary = json.loads(canonical_summary_bytes)
    tampered_summary["next_stage"] = "attacker-controlled"
    summary_path.write_text(json.dumps(tampered_summary), encoding="utf-8")
    tampered_card = json.loads(canonical_card_bytes)
    tampered_card["output_commitments"]["materialization_summary"]["sha256"] = (
        "sha256:" + hashlib.sha256(summary_path.read_bytes()).hexdigest()
    )
    run_card.write_text(json.dumps(tampered_card), encoding="utf-8")
    assert main(plan_parse_command) == 2
    summary_path.write_bytes(canonical_summary_bytes)
    run_card.write_bytes(canonical_card_bytes)
    assert main(plan_parse_command) == 0
    parse_requests = _read_jsonl(parse_root / "parse-document-requests.jsonl")
    assert len(parse_requests) == 3
    injected_document_fifo = materialized / "documents/injected.fifo"
    os.mkfifo(injected_document_fifo)
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--document-root",
                str(materialized / "documents"),
                "--materialization-run-card",
                str(run_card),
                *purchase_runtime_args,
                "--output-root",
                str(tmp_path / "fifo-attack"),
                "--execute",
            ]
        )
        == 2
    )
    injected_document_fifo.unlink()
    markdown_fixtures = tmp_path / "markdown-fixtures"
    markdown_fixtures.mkdir()
    for request in parse_requests:
        (markdown_fixtures / f"{request['source_document_id']}.md").write_text(
            (
                f"Public filing {request['source_document_id']}\n"
                "This synthetic fixture contains enough substantive filing text "
                "to exercise the authenticated parser and downstream lineage gate.\n"
                "It is provider-free test content and is not a source document.\n"
                "The fixture keeps the replay test deterministic and self-contained."
            ),
            encoding="utf-8",
        )

    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--selection",
                str(selection),
                "--requests",
                str(parse_root / "parse-document-requests.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--materialization-run-card",
                str(run_card),
                *purchase_runtime_args,
                "--fixture-markdown-dir",
                str(markdown_fixtures),
                "--output-root",
                str(parse_root),
                "--execute",
            ]
        )
        == 0
    )
    assert len(_read_jsonl(parse_root / "mistral-markdown-conversions.jsonl")) == 3
    assert (
        main(
            [
                "acquisition",
                "build-decision-texts",
                "--selection",
                str(selection),
                "--selection-run-card",
                str(projection / "run-cards/project-target-cohort.json"),
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--restriction-evidence",
                str(materialized / "restriction-evidence.jsonl"),
                "--parser-manifest",
                str(parse_root / "mistral-markdown-conversions.jsonl"),
                "--parser-run-card",
                str(parse_root / "run-cards/parse-documents.json"),
                "--markdown-root",
                str(parse_root / "markdown"),
                "--output-root",
                str(tmp_path / "decision-texts-missing-card"),
                "--execute",
            ]
        )
        == 2
    )
    assert (
        "executed decision-text construction requires canonical materialization"
        in capsys.readouterr().err
    )
    assert not (tmp_path / "decision-texts-missing-card").exists()
    decision_text_root = tmp_path / "decision-texts"
    monkeypatch.setattr(
        cli,
        "_validate_parser_run_card_commitments",
        lambda *args, **kwargs: None,
    )
    parser_manifest_path = parse_root / "mistral-markdown-conversions.jsonl"
    live_shaped_parser_rows = _read_jsonl(parser_manifest_path)
    for row in live_shaped_parser_rows:
        row["parser_config"] = {
            "engine": "mistral",
            "parser_revision": cli.EXPECTED_PARSER_REVISION,
            "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
            "fixture_markdown": False,
        }
        row["extraction_method"] = "mistral_parser_markdown"
        row["extracted_text"]["extraction_method"] = "mistral_parser_markdown"
    _write_jsonl(parser_manifest_path, live_shaped_parser_rows)
    assert (
        main(
            [
                "acquisition",
                "build-decision-texts",
                "--selection",
                str(selection),
                "--selection-run-card",
                str(projection / "run-cards/project-target-cohort.json"),
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--restriction-evidence",
                str(materialized / "restriction-evidence.jsonl"),
                "--parser-manifest",
                str(parse_root / "mistral-markdown-conversions.jsonl"),
                "--parser-run-card",
                str(parse_root / "run-cards/parse-documents.json"),
                "--markdown-root",
                str(parse_root / "markdown"),
                "--materialization-run-card",
                str(run_card),
                *private_purchase_runtime_args,
                "--output-root",
                str(decision_text_root),
                "--execute",
            ]
        )
        == 0
    )
    assert _read_jsonl(decision_text_root / "decision-texts.jsonl")
    dummy_jsonl = tmp_path / "downstream-placeholder.jsonl"
    dummy_jsonl.write_text("{}\n", encoding="utf-8")
    dummy_registry = tmp_path / "downstream-registry.json"
    dummy_registry.write_text("{}\n", encoding="utf-8")
    snapshot_raw_artifacts = _read_jsonl(snapshot / "raw-artifacts.jsonl")
    raw_html_root = Path(str(snapshot_raw_artifacts[0]["path"])).parent
    [selected_case] = _read_jsonl(selection)
    candidate_id = str(selected_case["candidate_id"])
    prediction_units = tmp_path / "packet-prediction-units.jsonl"
    finalized_units = _finalized_prediction_unit_record(candidate_id)
    finalized_units["case_id"] = str(selected_case["case_id"])
    _write_jsonl(prediction_units, [finalized_units])
    packet_registry = _write_model_registry(tmp_path)
    raw_artifacts = tmp_path / "canonical-raw-artifacts.jsonl"
    _write_jsonl(
        raw_artifacts,
        [
            {
                key: record[key]
                for key in (
                    "candidate_id",
                    "path",
                    "sha256",
                    "byte_count",
                    "retrieved_at",
                )
            }
            for record in snapshot_raw_artifacts
        ],
    )
    packet_root = tmp_path / "packet-plan"
    packet_command = [
        "acquisition",
        "plan-packet-inputs",
        "--selection",
        str(selection),
        "--download-manifest",
        str(materialized / "document-downloads-merged.jsonl"),
        "--parser-manifest",
        str(parse_root / "mistral-markdown-conversions.jsonl"),
        "--disclosure-clearance",
        str(materialized / "disclosure-clearance.jsonl"),
        "--prediction-units",
        str(prediction_units),
        "--model-registry",
        str(packet_registry),
        "--raw-html-dir",
        str(raw_html_root),
        "--raw-artifacts-manifest",
        str(raw_artifacts),
        "--document-root",
        str(materialized / "documents"),
        "--markdown-root",
        str(parse_root / "markdown"),
        "--output-root",
        str(packet_root),
        "--generated-at",
        "2026-07-15T12:00:00Z",
        "--execute",
    ]
    assert main(packet_command) == 2
    assert (
        main(
            [
                *packet_command,
                "--materialization-run-card",
                str(run_card),
                *private_purchase_runtime_args,
            ]
        )
        == 0
    )
    packet_build_authority_args = [
        "--parser-run-card",
        str(parse_root / "run-cards/parse-documents.json"),
        "--parse-plan-run-card",
        str(parse_root / "run-cards/plan-parse-documents.json"),
        "--raw-prediction-units",
        str(prediction_units),
        "--llm-unitization-audit",
        str(dummy_jsonl),
        "--llm-unitize-run-card",
        str(dummy_jsonl),
        "--llm-unitize-provider-journal",
        str(dummy_jsonl),
        "--original-unitization-review-queue",
        str(dummy_jsonl),
        "--stage-a-structural-flags",
        str(dummy_jsonl),
        "--stage-a-structural-review-audit",
        str(dummy_jsonl),
        "--stage-a-review-run-card",
        str(dummy_jsonl),
        "--stage-a-review-provider-journal",
        str(dummy_jsonl),
        "--stage-a-review-model-registry",
        str(packet_registry),
        "--stage-a-review-model-key",
        "fixture-reviewer",
        "--unitization-review-queue",
        str(dummy_jsonl),
        "--unitization-review-adjudications",
        str(dummy_jsonl),
        "--apply-unitization-review-run-card",
        str(dummy_jsonl),
        "--expected-model-registry-sha256",
        hashlib.sha256(packet_registry.read_bytes()).hexdigest(),
    ]
    monkeypatch.setattr(
        cli,
        "_verify_parser_packet_authority",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_packet_authority",
        lambda **kwargs: cli._StageAReplay(
            raw_prediction_unit_records=tuple(_read_jsonl(prediction_units)),
            unitization_audit_records=tuple(_read_jsonl(dummy_jsonl)),
            original_review_records=tuple(_read_jsonl(dummy_jsonl)),
            structural_flag_records=tuple(_read_jsonl(dummy_jsonl)),
            structural_review_audit_records=tuple(_read_jsonl(dummy_jsonl)),
            merged_review_records=tuple(_read_jsonl(dummy_jsonl)),
            adjudication_records=tuple(_read_jsonl(dummy_jsonl)),
        ),
    )
    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_root / "packet-build-input.jsonl"),
                "--packet-input-run-card",
                str(packet_root / "run-cards/plan-packet-inputs.json"),
                "--selection",
                str(selection),
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--parser-manifest",
                str(parse_root / "mistral-markdown-conversions.jsonl"),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--prediction-units",
                str(prediction_units),
                "--model-registry",
                str(packet_registry),
                "--raw-html-dir",
                str(raw_html_root),
                "--raw-artifacts-manifest",
                str(raw_artifacts),
                "--document-root",
                str(materialized / "documents"),
                "--markdown-root",
                str(parse_root / "markdown"),
                "--materialization-run-card",
                str(run_card),
                *private_purchase_runtime_args,
                *packet_build_authority_args,
                "--output-root",
                str(packet_root),
                "--execute",
            ]
        )
        == 0
    )
    finalized_packet_input = _read_jsonl(packet_root / "packet-build-input.jsonl")
    finalized_candidate_id = str(finalized_packet_input[0]["candidate_id"])

    class _DecisionArtifact:
        records = (
            {
                "candidate_id": finalized_candidate_id,
                "document_id": "fixture-decision",
                "text": "The motion to dismiss is granted.",
            },
        )

        def verify_stage_b_audit_commitments(self, records: object) -> None:
            del records

    monkeypatch.setattr(
        cli,
        "verify_stage_a_readiness_provenance",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(cli, "verify_labeling_policy", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli,
        "verify_stage_b_readiness_provenance",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_decision_text_artifact_with_materialization",
        lambda **kwargs: _DecisionArtifact(),
    )
    monkeypatch.setattr(
        cli,
        "build_clean_corpus_readiness",
        lambda **kwargs: cli.CorpusReadinessReport(
            required_clean_count=1,
            clean_candidate_ids=(finalized_candidate_id,),
            excluded_candidate_ids=(),
            exclusion_reasons={},
            funnel={"clean": 1},
            case_mix={},
        ),
    )
    monkeypatch.setattr(
        cli,
        "_verified_shared_provider_chain",
        lambda *args, **kwargs: (object(), dummy_jsonl),
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_review_run_card",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_unitization_review_run_card",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_llm_label_run_card",
        lambda *args, **kwargs: None,
    )
    finalize_command = [
        "acquisition",
        "finalize-corpus",
        "--selection",
        str(selection),
        "--parser-manifest",
        str(parse_root / "mistral-markdown-conversions.jsonl"),
        "--parser-run-card",
        str(parse_root / "run-cards/parse-documents.json"),
        "--decision-texts",
        str(dummy_jsonl),
        "--decision-texts-manifest",
        str(dummy_registry),
        "--decision-texts-run-card",
        str(dummy_registry),
        "--disclosure-clearance",
        str(materialized / "disclosure-clearance.jsonl"),
        "--markdown-root",
        str(parse_root / "markdown"),
        "--raw-html-dir",
        str(raw_html_root),
        "--raw-artifacts-manifest",
        str(raw_artifacts),
        "--raw-prediction-units",
        str(prediction_units),
        "--llm-unitization-run-card",
        str(dummy_jsonl),
        "--llm-review-stage-a-run-card",
        str(dummy_jsonl),
        "--prediction-units",
        str(prediction_units),
        "--llm-unitization-audit",
        str(dummy_jsonl),
        "--llm-unitize-run-card",
        str(dummy_jsonl),
        "--llm-unitize-provider-journal",
        str(dummy_jsonl),
        "--original-unitization-review-queue",
        str(dummy_jsonl),
        "--stage-a-structural-flags",
        str(dummy_jsonl),
        "--stage-a-structural-review-audit",
        str(dummy_jsonl),
        "--stage-a-review-run-card",
        str(dummy_jsonl),
        "--stage-a-review-provider-journal",
        str(dummy_jsonl),
        "--stage-a-review-model-registry",
        str(packet_registry),
        "--stage-a-review-model-key",
        "fixture-reviewer",
        "--unitization-review-queue",
        str(dummy_jsonl),
        "--unitization-review-adjudications",
        str(dummy_jsonl),
        "--apply-unitization-review-run-card",
        str(dummy_jsonl),
        "--provider-cycle-caps",
        str(dummy_registry),
        "--provider-journal",
        str(dummy_jsonl),
        "--parse-plan-run-card",
        str(parse_root / "run-cards/plan-parse-documents.json"),
        "--labels",
        str(dummy_jsonl),
        "--llm-label-audit",
        str(dummy_jsonl),
        "--original-llm-label-labels",
        str(dummy_jsonl),
        "--original-llm-label-audit",
        str(dummy_jsonl),
        "--llm-label-run-card",
        str(dummy_jsonl),
        "--stage-b-judge-registry",
        str(packet_registry),
        "--labeling-policy",
        str(dummy_registry),
        "--lawyer-review-queue",
        str(dummy_jsonl),
        "--lawyer-review-audit",
        str(dummy_jsonl),
        "--packet-build-input",
        str(packet_root / "packet-build-input.jsonl"),
        "--packet-input-run-card",
        str(packet_root / "run-cards/plan-packet-inputs.json"),
        "--packets",
        str(packet_root / "packets.jsonl"),
        "--packet-build-run-card",
        str(packet_root / "run-cards/build-packets.json"),
        "--model-registry",
        str(packet_registry),
        "--expected-model-registry-sha256",
        hashlib.sha256(packet_registry.read_bytes()).hexdigest(),
        "--screened-cases",
        str(snapshot / "screened-cases.jsonl"),
        "--discovery-summary",
        str(snapshot / "summary.json"),
        "--discovery-exclusions",
        str(snapshot / "exclusions.jsonl"),
        "--screening-snapshot-manifest",
        str(snapshot / "manifest.json"),
        "--screening-cycle-store",
        str(snapshot.parent.parent / "cycle-1.sqlite3"),
        "--target-cohort-preparation-root",
        str(preparation),
        "--target-clean-cases",
        "1",
        "--output-root",
        str(tmp_path / "finalize"),
    ]
    assert main(finalize_command) == 2
    assert (
        main(
            [
                *finalize_command,
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--materialization-run-card",
                str(run_card),
                "--document-root",
                str(materialized / "documents"),
                *private_purchase_runtime_args,
                "--execute",
            ]
        )
        == 0
    )

    def _replace_cli_value(command: list[str], flag: str, value: Path) -> list[str]:
        replaced = list(command)
        replaced[replaced.index(flag) + 1] = str(value)
        return replaced

    captured_packet_records: list[dict[str, object]] = []

    def capture_readiness(**kwargs: object) -> cli.CorpusReadinessReport:
        captured_packet_records.extend(
            cast(list[dict[str, object]], kwargs["packet_records"])
        )
        return cli.CorpusReadinessReport(
            required_clean_count=1,
            clean_candidate_ids=(finalized_candidate_id,),
            excluded_candidate_ids=(),
            exclusion_reasons={},
            funnel={"clean": 1},
            case_mix={},
        )

    original_build_validator = cli._validate_packet_build_run_card
    canonical_packets_path = packet_root / "packets.jsonl"
    canonical_packets_bytes = canonical_packets_path.read_bytes()

    def validate_then_swap_packets(*args: Any, **kwargs: Any) -> cli._PacketBuildReplay:
        replay = original_build_validator(*args, **kwargs)
        swapped = _read_jsonl(canonical_packets_path)
        swapped[0]["candidate_id"] = "attacker-packet-path-swap"
        _write_jsonl(canonical_packets_path, swapped)
        return replay

    monkeypatch.setattr(cli, "build_clean_corpus_readiness", capture_readiness)
    monkeypatch.setattr(
        cli,
        "_validate_packet_build_run_card",
        validate_then_swap_packets,
    )
    race_finalize_command = _replace_cli_value(
        finalize_command,
        "--output-root",
        tmp_path / "race-finalize",
    )
    assert (
        main(
            [
                *race_finalize_command,
                "--download-manifest",
                str(materialized / "document-downloads-merged.jsonl"),
                "--materialization-run-card",
                str(run_card),
                "--document-root",
                str(materialized / "documents"),
                *private_purchase_runtime_args,
                "--execute",
            ]
        )
        == 0
    )
    assert captured_packet_records[0]["candidate_id"] == finalized_candidate_id
    canonical_packets_path.write_bytes(canonical_packets_bytes)
    monkeypatch.setattr(
        cli,
        "_validate_packet_build_run_card",
        original_build_validator,
    )

    attacker_raw_root = tmp_path / "attacker-raw-html"
    attacker_raw_root.mkdir()
    canonical_raw_path = Path(str(snapshot_raw_artifacts[0]["path"]))
    attacker_raw_path = attacker_raw_root / canonical_raw_path.name
    attacker_payload = canonical_raw_path.read_bytes() + b"\n<!-- substituted -->\n"
    attacker_raw_path.write_bytes(attacker_payload)
    attacker_raw_manifest = tmp_path / "attacker-raw-artifacts.jsonl"
    _write_jsonl(
        attacker_raw_manifest,
        [
            {
                "candidate_id": f"courtlistener-docket-{candidate_id}",
                "path": str(attacker_raw_path),
                "sha256": hashlib.sha256(attacker_payload).hexdigest(),
                "byte_count": len(attacker_payload),
                "retrieved_at": "2026-07-15T12:00:00Z",
            }
        ],
    )
    attacker_packet_root = tmp_path / "attacker-packet-plan"
    attacker_plan_command = [
        *packet_command,
        "--materialization-run-card",
        str(run_card),
        *private_purchase_runtime_args,
    ]
    for flag, value in (
        ("--raw-html-dir", attacker_raw_root),
        ("--raw-artifacts-manifest", attacker_raw_manifest),
        ("--output-root", attacker_packet_root),
    ):
        attacker_plan_command = _replace_cli_value(
            attacker_plan_command,
            flag,
            value,
        )
    assert main(attacker_plan_command) == 2
    assert (
        "packet raw-artifact manifest differs from authenticated snapshot"
        in capsys.readouterr().err
    )
    combined_path = materialized / "document-downloads-merged.jsonl"
    combined_before = combined_path.read_bytes()
    tampered = _read_jsonl(combined_path)
    tampered[0].pop("materialization_schema_version")
    _write_jsonl(combined_path, tampered)
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(combined_path),
                "--disclosure-clearance",
                str(materialized / "disclosure-clearance.jsonl"),
                "--document-root",
                str(materialized / "documents"),
                "--output-root",
                str(tmp_path / "rejected-marker"),
                "--execute",
            ]
        )
        == 2
    )
    combined_path.write_bytes(combined_before)


def test_target_100_resume_rejects_changed_cost_provider_fixture_and_snapshot(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "base", case_count=100)
    )

    def command(output_root: Path) -> list[str]:
        return [
            "acquisition",
            "prepare-target-100",
            "--output-root",
            str(output_root),
            "--snapshot",
            str(snapshot),
            "--expected-cycle-hash",
            cycle_hash,
            "--expected-snapshot-manifest-sha256",
            _snapshot_manifest_sha256(snapshot),
            "--fixture-documents",
            str(fixture_documents),
            "--courtlistener-fixture",
            str(courtlistener_fixture),
            "--use-embedded-entries",
        ]

    mutations = (
        ("cost", ["--cost-per-document-usd", "4.00"]),
        (
            "provider",
            [
                "--live-courtlistener",
                "--request-ledger",
                str(tmp_path / "requests.sqlite3"),
            ],
        ),
    )
    for name, extra in mutations:
        output_root = tmp_path / f"run-{name}"
        assert main(command(output_root)) == 0
        changed = command(output_root)
        if name == "provider":
            fixture_index = changed.index("--courtlistener-fixture")
            del changed[fixture_index : fixture_index + 2]
        changed.extend(extra)
        assert main(changed) == 2
        assert "changed-config resume" in capsys.readouterr().err

    fixture_output = tmp_path / "run-fixture"
    assert main(command(fixture_output)) == 0
    courtlistener_fixture.write_text(
        courtlistener_fixture.read_text() + "\n", encoding="utf-8"
    )
    assert main(command(fixture_output)) == 2
    assert "changed-config resume" in capsys.readouterr().err

    other_snapshot, other_hash, other_documents, other_courtlistener = (
        _target_100_fixture(tmp_path / "other", case_count=100)
    )
    snapshot_output = tmp_path / "run-snapshot"
    assert main(command(snapshot_output)) == 0
    changed_snapshot = command(snapshot_output)
    replacements = {
        str(snapshot): str(other_snapshot),
        cycle_hash: other_hash,
        _snapshot_manifest_sha256(snapshot): _snapshot_manifest_sha256(other_snapshot),
        str(fixture_documents): str(other_documents),
        str(courtlistener_fixture): str(other_courtlistener),
    }
    changed_snapshot = [replacements.get(value, value) for value in changed_snapshot]
    assert main(changed_snapshot) == 2
    assert "changed-config resume" in capsys.readouterr().err


def test_target_100_underfilled_snapshot_writes_durable_failure_only(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=99)
    )
    output_root = tmp_path / "run"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 2
    )
    [attempt_path] = output_root.glob("attempts/prepare-target-100/*/run-card.json")
    run_card = json.loads(attempt_path.read_text())
    assert run_card["status"] == "failed"
    assert run_card["paid_activity_executed"] is False
    assert not (output_root / "run-cards/prepare-target-100.json").exists()
    assert not (output_root / "target-100-preparation-summary.json").exists()
    assert not (output_root / "01-public-plan").exists()


@pytest.mark.parametrize(
    "collision",
    (
        "output_snapshot",
        "output_snapshot_symlink",
        "summary_manifest",
        "summary_manifest_hardlink",
        "run_card_fixture",
        "log_request_ledger",
        "request_ledger_under_output",
    ),
)
def test_target_100_preflight_rejects_protected_output_overlap_before_writes(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    collision: str,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    manifest = snapshot / "manifest.json"
    manifest_before = manifest.read_bytes()
    output_root = snapshot if collision == "output_snapshot" else tmp_path / "run"
    if collision == "output_snapshot_symlink":
        output_root.symlink_to(snapshot, target_is_directory=True)
    command = [
        "acquisition",
        "prepare-target-100",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
    ]
    request_ledger = tmp_path / "requests.sqlite3"
    if collision == "summary_manifest":
        command.extend(("--summary-output", str(manifest)))
    elif collision == "summary_manifest_hardlink":
        summary_alias = tmp_path / "summary-hardlink.json"
        summary_alias.hardlink_to(manifest)
        command.extend(("--summary-output", str(summary_alias)))
    elif collision == "run_card_fixture":
        command.extend(("--run-card-output", str(courtlistener_fixture)))
    elif collision in {"log_request_ledger", "request_ledger_under_output"}:
        fixture_index = command.index("--courtlistener-fixture")
        del command[fixture_index : fixture_index + 2]
        if collision == "request_ledger_under_output":
            request_ledger = output_root / "requests.sqlite3"
        command.extend(
            (
                "--live-courtlistener",
                "--request-ledger",
                str(request_ledger),
            )
        )
        if collision == "log_request_ledger":
            command.extend(("--log-output", str(request_ledger)))

    assert main(command) == 2
    stderr = capsys.readouterr().err
    assert "overlap" in stderr or "hard-link alias" in stderr
    attempt_events = [
        json.loads(line)
        for line in stderr.splitlines()
        if line.startswith("{") and '"event": "attempt_failed"' in line
    ]
    [event] = attempt_events
    attempt_card = json.loads(Path(event["artifact_path"]).read_text())
    assert attempt_card["paid_activity_requested"] is False
    assert attempt_card["paid_activity_executed"] is False
    assert manifest.read_bytes() == manifest_before
    assert not (snapshot / "target-100-config.json").exists()
    if collision == "request_ledger_under_output":
        assert not output_root.exists()


def test_target_100_resume_rejects_mutated_and_injected_stage_artifacts(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    output_root = tmp_path / "run"
    command = [
        "acquisition",
        "prepare-target-100",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    assert main(command) == 0
    summary_path = output_root / "target-100-preparation-summary.json"
    success_card_path = output_root / "run-cards/prepare-target-100.json"
    summary_before = summary_path.read_bytes()
    success_card_before = success_card_path.read_bytes()
    stage_artifact = output_root / "04-core-filter/core-filter-results.jsonl"
    stage_before = stage_artifact.read_bytes()

    def unexpected_bridge(*args: object, **kwargs: object) -> object:
        raise AssertionError("resume guard must run before any child provider")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_bridge)
    stage_artifact.write_bytes(stage_before + b"\n")
    assert main(command) == 2
    assert "stage input commitment mismatch" in capsys.readouterr().err
    assert summary_path.read_bytes() == summary_before
    assert success_card_path.read_bytes() == success_card_before

    stage_artifact.write_bytes(stage_before)
    selection_artifact = (
        output_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
    )
    selection_before = selection_artifact.read_bytes()
    selection_artifact.write_bytes(selection_before + b"\n")
    assert main(command) == 2
    assert "stage" in capsys.readouterr().err
    assert summary_path.read_bytes() == summary_before
    assert success_card_path.read_bytes() == success_card_before

    selection_artifact.write_bytes(selection_before)
    injected = output_root / "03-gap-bridge/unexpected.json"
    injected.write_text("{}\n")
    assert main(command) == 2
    assert "unexpected stage artifact" in capsys.readouterr().err
    assert summary_path.read_bytes() == summary_before
    assert success_card_path.read_bytes() == success_card_before
    config_path = output_root / "target-100-config.json"
    config_path.unlink()
    assert main(command) == 2
    assert "committed config is missing" in capsys.readouterr().err
    assert not config_path.exists()
    assert summary_path.read_bytes() == summary_before
    assert success_card_path.read_bytes() == success_card_before
    assert (
        len(list(output_root.glob("attempts/prepare-target-100/*/run-card.json"))) == 4
    )


def test_target_100_changed_config_failure_preserves_prior_success(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    output_root = tmp_path / "run"
    command = [
        "acquisition",
        "prepare-target-100",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
    ]
    assert main(command) == 0
    success_card = output_root / "run-cards/prepare-target-100.json"
    success_before = success_card.read_bytes()

    assert main([*command, "--cost-per-document-usd", "4.00"]) == 2
    assert "changed-config resume" in capsys.readouterr().err
    assert success_card.read_bytes() == success_before
    [attempt] = output_root.glob("attempts/prepare-target-100/*/run-card.json")
    failure = json.loads(attempt.read_text())
    assert failure["status"] == "failed"
    assert failure["paid_activity_executed"] is False


def test_target_100_snapshot_failure_is_attempt_scoped_and_nonpaid(
    tmp_path: Path,
) -> None:
    snapshot, _, fixture_documents, courtlistener_fixture = _target_100_fixture(
        tmp_path, case_count=100
    )
    output_root = tmp_path / "run"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                "f" * 64,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 2
    )
    [attempt] = output_root.glob("attempts/prepare-target-100/*/run-card.json")
    record = json.loads(attempt.read_text())
    assert record["status"] == "failed"
    assert record["paid_activity_requested"] is False
    assert record["paid_activity_executed"] is False
    assert not (output_root / "run-cards/prepare-target-100.json").exists()
    assert not (output_root / "target-100-config.json").exists()


def test_target_100_custom_summary_path_is_frozen_and_required_after_success(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    output_root = tmp_path / "run"
    custom_summary = tmp_path / "committed-summary.json"
    base = [
        "acquisition",
        "prepare-target-100",
        "--output-root",
        str(output_root),
        "--snapshot",
        str(snapshot),
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-snapshot-manifest-sha256",
        _snapshot_manifest_sha256(snapshot),
        "--fixture-documents",
        str(fixture_documents),
        "--courtlistener-fixture",
        str(courtlistener_fixture),
        "--use-embedded-entries",
        "--execute",
    ]
    command = [*base, "--summary-output", str(custom_summary)]
    assert main(command) == 0
    success_card = output_root / "run-cards/prepare-target-100.json"
    success_before = success_card.read_bytes()

    def unexpected_bridge(*args: object, **kwargs: object) -> object:
        raise AssertionError("summary commitment must fail before child reuse")

    monkeypatch.setattr(cli, "_courtlistener_bridge_client", unexpected_bridge)
    assert main([*base, "--summary-output", str(tmp_path / "changed.json")]) == 2
    assert "committed success summary is missing" in capsys.readouterr().err
    assert main(base) == 2
    assert "committed success summary is missing" in capsys.readouterr().err

    custom_summary.unlink()
    assert main(command) == 2
    assert "committed success summary is missing" in capsys.readouterr().err
    assert success_card.read_bytes() == success_before
    assert (
        len(list(output_root.glob("attempts/prepare-target-100/*/run-card.json"))) == 3
    )


def test_target_100_attempt_symlink_cannot_redirect_failure_into_snapshot(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    output_root = tmp_path / "run"
    output_root.mkdir()
    (output_root / "attempts").symlink_to(snapshot, target_is_directory=True)
    manifest = snapshot / "manifest.json"
    manifest_before = manifest.read_bytes()

    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--expected-snapshot-manifest-sha256",
                _snapshot_manifest_sha256(snapshot),
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
            ]
        )
        == 2
    )
    stderr = capsys.readouterr().err
    assert "attempt tree" in stderr
    [event] = [
        json.loads(line)
        for line in stderr.splitlines()
        if line.startswith("{") and '"event": "attempt_failed"' in line
    ]
    attempt_path = Path(event["artifact_path"]).resolve()
    assert not attempt_path.is_relative_to(snapshot.resolve())
    assert json.loads(attempt_path.read_text())["paid_activity_executed"] is False
    assert manifest.read_bytes() == manifest_before
    assert not list(snapshot.glob("prepare-target-100/*/run-card.json"))


def _target_100_fixture(
    tmp_path: Path,
    *,
    case_count: int,
) -> tuple[Path, str, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store_path = tmp_path / f"cycle-{case_count}.sqlite3"
    snapshot_root = tmp_path / f"snapshots-{case_count}"
    records = [_screened_case(index) for index in range(case_count)]
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch("batch-002", {"provider": "courtlistener-recap-rest-v4"})
        store.ensure_terms("batch-002", ("motion to dismiss",))
        store.commit_search_page(
            "batch-002",
            "motion to dismiss",
            None,
            [
                {
                    "provider_hit_id": f"hit-{index}",
                    "candidate_id": f"courtlistener-docket-{1000 + index}",
                    "payload": {"docket_id": str(1000 + index)},
                }
                for index in range(case_count)
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        for index, record in enumerate(records):
            store.record_observation(
                f"courtlistener-docket-{1000 + index}",
                batch_id="batch-002",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=record,
            )
        raw_html_root = tmp_path / "raw-html"
        raw_html_root.mkdir()
        for index in range(case_count):
            docket_id = 1000 + index
            raw_html = _target_fixture_docket_html(docket_id).encode("utf-8")
            store.write_raw_artifact(
                f"courtlistener-docket-{docket_id}",
                raw_html_root / f"{docket_id}.html",
                raw_html,
                retrieved_at="2026-07-15T12:00:00Z",
            )
        snapshot = store.export_snapshot(
            snapshot_root,
            snapshot_id=f"target-100-{case_count}",
            batch_id="batch-002",
            complete=True,
            stage_commitments={
                "courtlistener_rest_screen_inputs": {
                    "schema_version": (
                        "legalforecast.courtlistener_rest_screen_inputs.v1"
                    )
                }
            },
        )
        cycle_hash = store.cycle_hash

    fixture_documents = tmp_path / f"free-documents-{case_count}.json"
    fixture_documents.write_text(
        json.dumps(
            {
                url: _fixture_pdf_text("Benign public court filing")
                for index in range(case_count)
                for url in (
                    f"https://storage.courtlistener.com/{1000 + index}-complaint.pdf",
                    f"https://storage.courtlistener.com/{1000 + index}-decision.pdf",
                )
            }
        )
    )
    courtlistener_fixture = tmp_path / f"courtlistener-{case_count}.jsonl"
    responses: list[dict[str, object]] = []
    for index in range(case_count):
        docket_id = 1000 + index
        entry_id = 7000 + index
        document_id = 9000 + index
        responses.extend(
            (
                {
                    "method": "GET",
                    "path": f"/dockets/{docket_id}/",
                    "params": {},
                    "status_code": 200,
                    "payload": {
                        "id": docket_id,
                        "court": "nysd",
                        "docket_number": f"1:26-cv-{index + 1:05d}",
                        "case_name": f"Fixture {index} v. Example",
                    },
                },
                {
                    "method": "GET",
                    "path": "/docket-entries/",
                    "params": {"docket": str(docket_id), "page_size": 100},
                    "status_code": 200,
                    "payload": {
                        "results": [
                            {
                                "id": entry_id,
                                "docket": docket_id,
                                "entry_number": 5,
                                "description": "MOTION to Dismiss filed by Defendant.",
                                "date_filed": "2026-01-01",
                                "recap_documents": [{"id": document_id}],
                            }
                        ],
                        "next": None,
                    },
                },
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "params": {},
                    "status_code": 200,
                    "payload": {
                        "id": document_id,
                        "docket_entry": entry_id,
                        "document_number": "5",
                        "attachment_number": None,
                        "description": "Motion to Dismiss",
                        "is_available": False,
                        "is_sealed": False,
                        "is_private": False,
                    },
                },
            )
        )
    courtlistener_fixture.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in responses)
    )
    return snapshot, cycle_hash, fixture_documents, courtlistener_fixture


def _fixture_pdf_text(text: str) -> str:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    body = stream.encode("utf-8")
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Count 1 /Kids [] >> endobj",
        "3 0 obj << /Type /Page /Contents 23 0 R >> endobj",
        f"23 0 obj << /Length {len(body)} >> stream\n{stream}\nendstream endobj",
    ]
    return "%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF"


def _target_fixture_docket_html(docket_id: int) -> str:
    return f"""
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1"><p>1</p></div>
            <div class="col-xs-3"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8">
              <p>COMPLAINT filed by Plaintiff.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Complaint</p></div>
                <a href="https://storage.courtlistener.com/{docket_id}-complaint.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-5">
            <div class="col-xs-1"><p>5</p></div>
            <div class="col-xs-3"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Motion to Dismiss</p></div>
                <a class="open_buy_pacer_modal" href="https://ecf.nysd.uscourts.gov/doc1/{docket_id}">
                  Buy on PACER
                </a>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-16">
            <div class="col-xs-1"><p>16</p></div>
            <div class="col-xs-3"><p>Jun 30, 2026</p></div>
            <div class="col-xs-8">
              <p>ORDER granting Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/{docket_id}-decision.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _write_authenticated_reviews(
    root: Path,
    *,
    manifest_path: Path,
    document_root: Path,
    review_requests_path: Path | None = None,
    restriction_evidence_path: Path,
    store_uri: str,
) -> _AuthenticatedReviewFiles:
    root.mkdir(parents=True)
    authenticated_at = "2026-07-15T12:00:00Z"
    manifest = _read_jsonl(manifest_path)
    requests = root / "review-requests.jsonl"
    if review_requests_path is None:
        _write_jsonl(
            requests,
            [
                {
                    "schema_version": "legalforecast.disclosure_review_request.v1",
                    "candidate_id": row["candidate_id"],
                    "source_document_id": row["source_document_id"],
                    "sha256": row["sha256"],
                    "byte_count": row["byte_count"],
                    "free_or_purchased": row["free_or_purchased"],
                    "required_human_decision": "cleared_or_quarantined",
                }
                for row in manifest
            ],
        )
    else:
        requests.write_bytes(review_requests_path.read_bytes())
    request_bytes = requests.read_bytes()
    restriction_bytes = restriction_evidence_path.read_bytes()
    cohort_decisions = cli._fixture_cohort_policy_decisions()
    cohort_decisions["eligibility_anchor"] = "2026-06-30"
    stop_rule = cohort_decisions["stop_rule"]
    assert isinstance(stop_rule, dict)
    stop_rule["search_window_end"] = "2026-07-15"
    cohort_artifact = cli.generate_cohort_policy(cohort_decisions)
    cohort_policy = root / "cohort-policy.json"
    cohort_policy.write_text(
        json.dumps(cohort_artifact, sort_keys=True) + "\n", encoding="utf-8"
    )
    signer = service_review_signer(
        reviewer_id="reviewer:fixture",
        controlled_store_uri=store_uri,
        identity=disclosure_authority_identity_from_cohort_policy(cohort_artifact),
    )
    worksheet_record = prepare_review_worksheet(
        _read_jsonl(requests),
        manifest,
        _read_jsonl(restriction_evidence_path),
        document_root=document_root,
        review_requests_bytes=request_bytes,
        download_manifest_bytes=manifest_path.read_bytes(),
        restriction_evidence_bytes=restriction_bytes,
        disclosure_authority=signer["disclosure_authority"],
    )
    signed = signed_service_review_lineage(
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "byte_count": row["byte_count"],
                "free_or_purchased": row["free_or_purchased"],
                "status": "cleared",
                "reviewer_id": "reviewer:fixture",
                "controlled_store_provenance": store_uri,
                "reviewed_at": authenticated_at,
            }
            for row in manifest
        ],
        restriction_evidence_bytes=restriction_bytes,
        download_manifest_bytes=manifest_path.read_bytes(),
        review_requests_bytes=request_bytes,
        worksheet=worksheet_record,
        signer=signer,
        authenticated_at=authenticated_at,
    )
    reviews = root / "reviews.jsonl"
    reviews.write_bytes(signed["reviews_bytes"])
    receipt = root / "receipt.json"
    receipt.write_bytes(signed["review_receipt_bytes"])
    worksheet = root / "worksheet.json"
    worksheet.write_bytes(signed["review_worksheet_bytes"])
    policy = root / "reviewer-policy.json"
    policy.write_bytes(signed["reviewer_policy_bytes"])
    return _AuthenticatedReviewFiles(
        reviews=reviews,
        receipt=receipt,
        requests=requests,
        worksheet=worksheet,
        policy=policy,
        policy_pin=signed["reviewer_policy_sha256"],
        cohort_policy=cohort_policy,
    )


def _purchase_fixtures(
    tmp_path: Path,
    document_ids: list[str],
) -> tuple[Path, Path]:
    courtlistener = tmp_path / "purchase-courtlistener.jsonl"
    broker = tmp_path / "purchase-broker.json"
    courtlistener_records: list[dict[str, object]] = []
    broker_records: list[dict[str, object]] = []
    for index, document_id in enumerate(document_ids):
        queue_id = str(50000 + index)
        courtlistener_records.extend(
            (
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "status_code": 200,
                    "payload": {"id": int(document_id)},
                },
                {
                    "method": "GET",
                    "path": f"/recap-fetch/{queue_id}/",
                    "status_code": 200,
                    "payload": {"status": 2},
                },
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "status_code": 200,
                    "payload": {
                        "id": int(document_id),
                        "is_available": True,
                        "filepath_local": (
                            f"https://storage.courtlistener.com/{document_id}.pdf"
                        ),
                    },
                },
            )
        )
        broker_records.append(
            {"reservation_id": f"reservation-{index}", "id": queue_id}
        )
    courtlistener.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in courtlistener_records
        )
    )
    broker.write_text(json.dumps(broker_records, sort_keys=True))
    return courtlistener, broker


def _screened_case(index: int) -> dict[str, object]:
    docket_id = 1000 + index
    return {
        "candidate_id": f"courtlistener-docket-{docket_id}",
        "provider": "courtlistener-recap-rest-v4",
        "canonical_rest_screen_complete": True,
        "nature_of_suit": "440 Civil Rights",
        "nos_macro_category": "civil_rights",
        "candidate": {
            "docket_id": str(docket_id),
            "candidate_key": str(docket_id),
            "metadata": {
                "case_id": str(docket_id),
                "case_name": f"Fixture {index} v. Example",
                "court": "nysd",
                "docket_number": f"1:26-cv-{index + 1:05d}",
            },
            "url": f"https://www.courtlistener.com/docket/{docket_id}/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _entry(
                docket_id,
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                f"https://storage.courtlistener.com/{docket_id}-complaint.pdf",
                pacer_only=False,
            ),
            _entry(
                docket_id,
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                f"https://ecf.nysd.uscourts.gov/doc1/{docket_id}",
                pacer_only=True,
            ),
            _entry(
                docket_id,
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                f"https://storage.courtlistener.com/{docket_id}-decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _entry(
    docket_id: int,
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{docket_id}-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "source_document_id": f"{docket_id}{number}",
                "kind": "main_document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]

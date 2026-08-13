from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_manifest_template import render_cycle_config
from legalforecast.ingestion.cycle_orchestrator import load_cycle_config
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes

ROOT = Path(__file__).parents[1]
INITIAL_RECOVERY_TEMPLATE = (
    ROOT / "manifests" / "cycle-1-target-100.exact100-initial-recovery.template.json"
)
REVIEW_TEMPLATE = (
    ROOT / "manifests" / "cycle-1-target-100.initial-recovery-disclosure.template.json"
)
NO_REVIEW_TEMPLATE = (
    ROOT
    / "manifests"
    / "cycle-1-target-100.initial-recovery-disclosure-no-review.template.json"
)
REPLACEMENT_PLAN_TEMPLATE = (
    ROOT
    / "manifests"
    / "cycle-1-target-100.replacement-recovery-disclosure-plan.template.json"
)
REPLACEMENT_MODEL_TEMPLATE = (
    ROOT
    / "manifests"
    / "cycle-1-target-100.replacement-disclosure-model-continuation.template.json"
)
REPLACEMENT_EMPTY_TEMPLATE = (
    ROOT
    / "manifests"
    / "cycle-1-target-100.replacement-disclosure-empty-continuation.template.json"
)


def _assignments(tmp_path: Path) -> dict[str, Path]:
    return {
        "REPO_ROOT": tmp_path / "repo",
        "RECOVERY_ROOT": tmp_path / "recovery",
        "TARGET_COHORT_ROOT": tmp_path / "target-cohort",
        "PURCHASE_ROOT": tmp_path / "purchase-authority",
        "PURCHASE_PRIVATE_ROOT": tmp_path / "purchase-private",
        "DISCLOSURE_ARTIFACT_ROOT": tmp_path / "disclosure-artifacts",
        "DISCLOSURE_PRIVATE_ROOT": tmp_path / "disclosure-private",
        "TERMINAL_DISPOSITION_SELECTION": tmp_path / "terminal" / "selection.jsonl",
        "TERMINAL_DISPOSITION_SNAPSHOT_MANIFEST": tmp_path
        / "terminal"
        / "snapshot"
        / "manifest.json",
        "TERMINAL_PURCHASE_RESULT": tmp_path / "terminal" / "purchase-result.json",
        "TERMINAL_PURCHASE_RUN_CARD": tmp_path / "terminal" / "purchase-run-card.json",
    }


def _render(tmp_path: Path, template: Path):
    assignments = _assignments(tmp_path)
    output = tmp_path / f"{template.stem}.rendered.json"
    render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
        argument_validator=cli_module._validate_rendered_cycle_arguments,  # pyright: ignore[reportPrivateUsage]
    )
    return load_cycle_config(output), assignments


def _render_initial_recovery(tmp_path: Path):
    assignments = {
        "CYCLE_ROOT": tmp_path / "recovery-cycle",
        "INITIAL_APPROVED_ROOT": tmp_path / "target-cohort",
        "PURCHASE_AUTHORITY_ROOT": tmp_path / "purchase-authority",
        "PURCHASE_PRIVATE_ROOT": tmp_path / "purchase-private",
        "RECOVERY_ROOT": tmp_path / "recovery",
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
    }
    output = tmp_path / "exact100-initial-recovery.rendered.json"
    render_cycle_config(
        template_path=INITIAL_RECOVERY_TEMPLATE,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
        argument_validator=cli_module._validate_rendered_cycle_arguments,  # pyright: ignore[reportPrivateUsage]
    )
    return load_cycle_config(output), assignments


def _replacement_assignments(tmp_path: Path) -> dict[str, Path]:
    return {
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
        "ARTIFACT_ROOT": tmp_path / "artifacts",
        "INITIAL_PRIVATE_ROOT": tmp_path / "private-initial",
        "PRIOR_CLEARANCE": tmp_path / "prior" / "disclosure-clearance.jsonl",
        "PRIOR_CLEARANCE_RUN_CARD": (
            tmp_path / "prior" / "run-cards" / "finalize-provenance-quarantine.json"
        ),
        "PLAN_ROOT": tmp_path / "replacement" / "04-disclosure-plan",
        "REPLACEMENT_ROOT": tmp_path / "replacement",
        "SUCCESSOR_PRIVATE_ROOT": tmp_path / "private-successor",
    }


def _render_replacement(tmp_path: Path, template: Path):
    assignments = _replacement_assignments(tmp_path)
    template_record = cast(dict[str, object], json.loads(template.read_bytes()))
    variables = cast(list[str], template_record["variables"])
    output = tmp_path / f"{template.stem}.rendered.json"
    render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"{name}={assignments[name]}" for name in variables],
        argument_validator=cli_module._validate_rendered_cycle_arguments,  # pyright: ignore[reportPrivateUsage]
    )
    return load_cycle_config(output), assignments


def _flag_value(arguments: tuple[str, ...], flag: str) -> str:
    return arguments[arguments.index(flag) + 1]


def _assert_canonical_initial_recovery_inputs(
    *,
    stage_arguments: tuple[tuple[str, ...], ...],
    recovery_root: Path,
) -> None:
    expected = {
        "--download-manifest": recovery_root / "recap-fetch-quarantine-downloads.jsonl",
        "--case-relevance": recovery_root / "purchased-case-relevance.jsonl",
        "--document-root": recovery_root / "documents" / "recap-fetch-quarantine",
        "--restriction-evidence": recovery_root
        / "post-recovery-restriction-evidence.jsonl",
    }
    for arguments in stage_arguments:
        for flag, expected_path in expected.items():
            if flag in arguments:
                assert _flag_value(arguments, flag) == str(expected_path)

    legacy_paths = (
        recovery_root / "purchased-document-downloads-quarantine.jsonl",
        recovery_root / "case-relevance.jsonl",
        recovery_root / "documents" / "quarantine",
        recovery_root / "restriction-evidence.jsonl",
    )
    for legacy_path in legacy_paths:
        assert all(
            argument != str(legacy_path)
            for arguments in stage_arguments
            for argument in arguments
        )


@pytest.mark.parametrize("disclosure_template", [REVIEW_TEMPLATE, NO_REVIEW_TEMPLATE])
def test_provider_free_render_connects_recovery_v2_to_disclosure_and_resolution(
    tmp_path: Path,
    disclosure_template: Path,
) -> None:
    recovery_config, recovery_assignments = _render_initial_recovery(tmp_path)
    disclosure_config, disclosure_assignments = _render(tmp_path, disclosure_template)

    assert (
        recovery_assignments["RECOVERY_ROOT"] == disclosure_assignments["RECOVERY_ROOT"]
    )
    recovery = recovery_config.stages[-1]
    plan = next(
        stage
        for stage in disclosure_config.stages
        if stage.command == "plan-disclosure-provenance"
    )
    finalizer = next(
        stage
        for stage in disclosure_config.stages
        if stage.command == "finalize-provenance-quarantine"
    )
    resolver = next(
        stage
        for stage in disclosure_config.stages
        if stage.command == "resolve-post-recovery-documents"
    )
    terminal_bindings = {
        "--terminal-disposition-selection": "TERMINAL_DISPOSITION_SELECTION",
        "--terminal-disposition-snapshot-manifest": (
            "TERMINAL_DISPOSITION_SNAPSHOT_MANIFEST"
        ),
        "--terminal-purchase-result": "TERMINAL_PURCHASE_RESULT",
        "--terminal-purchase-run-card": "TERMINAL_PURCHASE_RUN_CARD",
    }
    for flag, assignment in terminal_bindings.items():
        assert _flag_value(resolver.arguments, flag) == str(
            disclosure_assignments[assignment]
        )
    review = next(
        (
            stage
            for stage in disclosure_config.stages
            if stage.command == "review-disclosure-exceptions"
        ),
        None,
    )

    producer_to_consumers = {
        "--manifest-output": (
            (plan, "--download-manifest"),
            (finalizer, "--download-manifest"),
            (resolver, "--download-manifest"),
        ),
        "--case-relevance-output": (
            (plan, "--case-relevance"),
            (finalizer, "--case-relevance"),
        ),
        "--restriction-evidence-output": (
            (plan, "--restriction-evidence"),
            (finalizer, "--restriction-evidence"),
            (resolver, "--restriction-evidence"),
        ),
        "--document-output-root": tuple(
            (stage, "--document-root")
            for stage in (plan, review, finalizer)
            if stage is not None
        ),
        "--review-requests-output": (
            (plan, "--review-requests"),
            (finalizer, "--review-requests"),
        ),
    }
    for producer_flag, consumers in producer_to_consumers.items():
        produced_path = _flag_value(recovery.arguments, producer_flag)
        assert produced_path.startswith(str(recovery_assignments["RECOVERY_ROOT"]))
        for consumer, consumer_flag in consumers:
            assert _flag_value(consumer.arguments, consumer_flag) == produced_path

    assert _flag_value(plan.arguments, "--recovery-run-card") == str(recovery.run_card)
    assert _flag_value(finalizer.arguments, "--recovery-run-card") == str(
        recovery.run_card
    )
    _assert_canonical_initial_recovery_inputs(
        stage_arguments=tuple(
            stage.arguments
            for stage in disclosure_config.stages
            if stage.command != "init-cycle"
        ),
        recovery_root=recovery_assignments["RECOVERY_ROOT"],
    )


@pytest.mark.parametrize(
    ("run_card_variant", "expected_result", "expected_provider_calls"),
    [
        ("missing", 2, 0),
        ("wrong-stage", 2, 0),
        ("incomplete", 2, 0),
        ("tampered-plan", 2, 0),
        ("completed", 0, 1),
    ],
)
def test_model_review_requires_completed_plan_before_provider_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_card_variant: str,
    expected_result: int,
    expected_provider_calls: int,
) -> None:
    plan_path = tmp_path / "plan" / "disclosure-provenance-plan.json"
    worksheet_path = tmp_path / "plan" / "disclosure-exception-worksheet.json"
    plan_run_card_path = (
        tmp_path / "plan" / "run-cards" / "plan-disclosure-provenance.json"
    )
    document_root = tmp_path / "documents"
    output_root = tmp_path / "review"
    frozen_root = tmp_path / "frozen"
    private_root = tmp_path / "private"
    plan_path.parent.mkdir(parents=True)
    plan_run_card_path.parent.mkdir(parents=True)
    document_root.mkdir()
    frozen_root.mkdir()
    auto_payload = b"auto-clear document"
    exception_payload = b"exception document"
    auto_document = {
        "candidate_id": "case-a",
        "source_document_id": "auto",
        "local_path": "case-a/auto.pdf",
    }
    exception_document = {
        "candidate_id": "case-a",
        "source_document_id": "exception",
        "local_path": "case-a/exception.pdf",
    }
    (document_root / "case-a").mkdir()
    (document_root / auto_document["local_path"]).write_bytes(auto_payload)
    (document_root / exception_document["local_path"]).write_bytes(exception_payload)
    plan_bytes = canonical_json_bytes(
        {"documents": [auto_document, exception_document]}
    )
    worksheet_bytes = canonical_json_bytes({"documents": [exception_document]})
    plan_path.write_bytes(plan_bytes)
    worksheet_path.write_bytes(worksheet_bytes)
    plan_run_card = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "plan-disclosure-provenance",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "output_paths": [str(plan_path.resolve()), str(worksheet_path.resolve())],
        "source_commitments": {
            "document_root": {
                "path": str(document_root.resolve()),
                "tree_sha256": cli_module._canonical_json_sha256(  # pyright: ignore[reportPrivateUsage]
                    {
                        "case-a/auto.pdf": "sha256:"
                        + hashlib.sha256(auto_payload).hexdigest(),
                        "case-a/exception.pdf": "sha256:"
                        + hashlib.sha256(exception_payload).hexdigest(),
                    }
                ),
                "document_count": 2,
            }
        },
        "output_commitments": {
            "routing_plan": {
                "path": str(plan_path.resolve()),
                "sha256": cli_module._bytes_sha256(plan_bytes),  # pyright: ignore[reportPrivateUsage]
            },
            "exception_worksheet": {
                "path": str(worksheet_path.resolve()),
                "sha256": cli_module._bytes_sha256(worksheet_bytes),  # pyright: ignore[reportPrivateUsage]
            },
        },
    }
    if run_card_variant == "wrong-stage":
        plan_run_card["stage"] = "prepare-disclosure-review"
    elif run_card_variant == "incomplete":
        plan_run_card["status"] = "failed"
    if run_card_variant != "missing":
        plan_run_card_path.write_bytes(
            (
                json.dumps(plan_run_card, indent=2, sort_keys=True, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        )
    if run_card_variant == "tampered-plan":
        # Keep both worksheet documents so rejection is the run-card hash bind,
        # not a later plan/worksheet document-set mismatch.
        plan_path.write_bytes(plan_bytes + b" ")

    provider_calls = 0
    capability = object()

    def authenticate(**kwargs: object) -> object:
        nonlocal provider_calls
        assert kwargs["document_bytes_by_key"] == {
            ("case-a", "exception"): exception_payload
        }
        provider_calls += 1
        return capability

    def private_records_for_capability(value: object) -> tuple[()]:
        assert value is capability
        return ()

    def validate_fixture_worksheet(
        *_args: object, **_kwargs: object
    ) -> tuple[dict[str, str]]:
        return (exception_document,)

    def public_record_for_capability(value: object) -> dict[str, int]:
        return {"decision_count": 1} if value is capability else {}

    def provider_call_executed(value: object) -> bool:
        return value is capability

    monkeypatch.setattr(
        cli_module,
        "validate_exception_review_worksheet_v3",
        validate_fixture_worksheet,
    )
    monkeypatch.setattr(
        cli_module, "authenticate_disclosure_model_review", authenticate
    )
    monkeypatch.setattr(
        cli_module,
        "public_disclosure_model_review_record",
        public_record_for_capability,
    )
    monkeypatch.setattr(
        cli_module,
        "private_disclosure_model_review_records",
        private_records_for_capability,
    )
    monkeypatch.setattr(
        cli_module,
        "disclosure_model_review_provider_call_executed",
        provider_call_executed,
    )
    command = [
        "acquisition",
        "review-disclosure-exceptions",
        "--output-root",
        str(output_root),
        "--routing-plan",
        str(plan_path),
        "--exception-worksheet",
        str(worksheet_path),
        "--document-root",
        str(document_root),
        "--frozen-authority-root",
        str(frozen_root),
        "--provider-journal",
        str(private_root / "provider-journal.sqlite3"),
        "--provider-spend-authority",
        str(private_root / "provider-spend-authority.sqlite3"),
        "--controlled-private-store-root",
        str(private_root),
        "--execute",
        "--resume",
    ]
    if run_card_variant != "missing":
        command.extend(("--plan-run-card", str(plan_run_card_path)))

    if run_card_variant == "missing":
        with pytest.raises(SystemExit) as exc_info:
            main(command)
        result = exc_info.value.code
    else:
        result = main(command)
    assert result == expected_result
    assert provider_calls == expected_provider_calls


def test_initial_recovery_disclosure_review_template_pins_authenticated_model_path(
    tmp_path: Path,
) -> None:
    config, assignments = _render(tmp_path, REVIEW_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "plan-disclosure-provenance",
        "review-disclosure-exceptions",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
    ]
    assert [stage.boundary.value for stage in config.stages] == [
        "provider_free",
        "provider_free",
        "model_provider",
        "provider_free",
        "provider_free",
    ]
    assert not {
        "record-disclosure-review-decisions",
        "clear-provenance-disclosures",
        "evaluate",
        "freeze",
        "dispatch",
    } & {stage.command for stage in config.stages}

    _init, plan, review, finalizer, resolver = config.stages
    _assert_canonical_initial_recovery_inputs(
        stage_arguments=tuple(
            stage.arguments for stage in (plan, review, finalizer, resolver)
        ),
        recovery_root=assignments["RECOVERY_ROOT"],
    )
    assert _flag_value(plan.arguments, "--schema-version") == "v3"
    assert _flag_value(plan.arguments, "--recovery-run-card") == str(
        assignments["RECOVERY_ROOT"]
        / "run-cards"
        / "recover-recap-fetch-quarantine.json"
    )
    for flag in (
        "--selection",
        "--purchase-policy",
        "--purchase-ledger",
        "--purchase-ledger-initialization-receipt",
        "--controlled-private-root",
        "--recovery-cohort-policy",
    ):
        assert flag in plan.arguments
        assert _flag_value(finalizer.arguments, flag) == _flag_value(
            plan.arguments, flag
        )

    assert _flag_value(review.arguments, "--frozen-authority-root") == str(
        assignments["REPO_ROOT"]
    )
    assert _flag_value(review.arguments, "--provider-journal") == str(
        assignments["DISCLOSURE_PRIVATE_ROOT"] / "provider-attempts.sqlite3"
    )
    assert _flag_value(review.arguments, "--provider-spend-authority") == str(
        assignments["DISCLOSURE_PRIVATE_ROOT"] / "provider-spend-authority.sqlite3"
    )
    assert _flag_value(finalizer.arguments, "--model-review-authority") == (
        _flag_value(review.arguments, "--authority-output")
    )
    assert _flag_value(
        finalizer.arguments, "--model-review-private-records"
    ) == _flag_value(review.arguments, "--private-records-output")
    assert _flag_value(finalizer.arguments, "--model-review-run-card") == str(
        review.run_card
    )
    for flag in (
        "--frozen-authority-root",
        "--provider-journal",
        "--provider-spend-authority",
    ):
        assert _flag_value(finalizer.arguments, flag) == _flag_value(
            review.arguments, flag
        )
    assert "--model-registry" not in review.arguments
    assert "--model-key" not in review.arguments
    assert "--evaluated-model-registry" not in review.arguments
    assert "--require-no-model-review-eligible-exceptions" not in (finalizer.arguments)
    assert _flag_value(resolver.arguments, "--clearance-run-card") == str(
        finalizer.run_card
    )


def test_initial_recovery_no_review_template_is_closed_provider_free_branch(
    tmp_path: Path,
) -> None:
    config, assignments = _render(tmp_path, NO_REVIEW_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "plan-disclosure-provenance",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
    ]
    assert all(stage.boundary.value == "provider_free" for stage in config.stages)
    _init, plan, finalizer, resolver = config.stages
    _assert_canonical_initial_recovery_inputs(
        stage_arguments=tuple(stage.arguments for stage in (plan, finalizer, resolver)),
        recovery_root=assignments["RECOVERY_ROOT"],
    )
    assert _flag_value(plan.arguments, "--schema-version") == "v3"
    assert "--require-no-model-review-eligible-exceptions" not in finalizer.arguments
    assert _flag_value(finalizer.arguments, "--public-marker-clearance-policy") == str(
        assignments["REPO_ROOT"]
        / "docs"
        / "disclosure-public-marker-policy-cycle-1-2026-08-06.json"
    )
    assert _flag_value(finalizer.arguments, "--plan-run-card") == str(plan.run_card)
    for forbidden in (
        "--model-review-authority",
        "--model-review-private-records",
        "--model-review-run-card",
        "--frozen-authority-root",
        "--provider-journal",
        "--provider-spend-authority",
    ):
        assert forbidden not in finalizer.arguments
    assert _flag_value(resolver.arguments, "--clearance-run-card") == str(
        finalizer.run_card
    )


def test_replacement_recovery_disclosure_plan_stops_after_authenticated_plan(
    tmp_path: Path,
) -> None:
    config, assignments = _render_replacement(tmp_path, REPLACEMENT_PLAN_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "record-replacement-purchase-approval",
        "purchase-missing-recap-fetch",
        "recover-recap-fetch-quarantine",
        "plan-disclosure-provenance",
    ]
    assert [stage.boundary.value for stage in config.stages] == [
        "provider_free",
        "human",
        "paid",
        "network",
        "provider_free",
    ]
    purchase, recovery, plan = config.stages[2:]
    assert _flag_value(plan.arguments, "--schema-version") == "v3"
    assert _flag_value(plan.arguments, "--output-root") == str(assignments["PLAN_ROOT"])
    assert str(plan.run_card).startswith(str(assignments["PLAN_ROOT"]))
    assert not {
        "review-disclosure-exceptions",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
        "accumulate-replacement-clearance",
    } & {stage.command for stage in config.stages}
    for stage in (purchase, recovery):
        assert _flag_value(stage.arguments, "--replacement-purchase-authority") == str(
            assignments["REPLACEMENT_ROOT"]
            / "01-plan"
            / "replacement-purchase-authority.json"
        )
        assert _flag_value(
            stage.arguments, "--replacement-controlled-private-root"
        ) == str(assignments["SUCCESSOR_PRIVATE_ROOT"])


def test_replacement_model_continuation_starts_after_plan_and_cannot_rewrite_it(
    tmp_path: Path,
) -> None:
    config, assignments = _render_replacement(tmp_path, REPLACEMENT_MODEL_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "review-disclosure-exceptions",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
        "accumulate-replacement-clearance",
    ]
    _init, review, finalizer, resolver, accumulator = config.stages
    assert review.boundary.value == "model_provider"
    assert not {
        "record-replacement-purchase-approval",
        "purchase-missing-recap-fetch",
        "recover-recap-fetch-quarantine",
        "plan-disclosure-provenance",
    } & {stage.command for stage in config.stages}
    assert _flag_value(review.arguments, "--routing-plan") == str(
        assignments["PLAN_ROOT"] / "disclosure-provenance-plan.json"
    )
    assert _flag_value(review.arguments, "--exception-worksheet") == str(
        assignments["PLAN_ROOT"] / "disclosure-exception-worksheet.json"
    )
    assert _flag_value(review.arguments, "--plan-run-card") == str(
        assignments["PLAN_ROOT"] / "run-cards" / "plan-disclosure-provenance.json"
    )
    assert _flag_value(finalizer.arguments, "--model-review-authority") == (
        _flag_value(review.arguments, "--authority-output")
    )
    assert _flag_value(finalizer.arguments, "--model-review-private-records") == (
        _flag_value(review.arguments, "--private-records-output")
    )
    assert _flag_value(finalizer.arguments, "--model-review-run-card") == str(
        review.run_card
    )
    assert "--require-no-model-review-eligible-exceptions" not in finalizer.arguments
    assert _flag_value(resolver.arguments, "--replacement-purchase-authority") == str(
        assignments["REPLACEMENT_ROOT"]
        / "01-plan"
        / "replacement-purchase-authority.json"
    )
    assert _flag_value(resolver.arguments, "--clearance-run-card") == str(
        finalizer.run_card
    )
    assert _flag_value(accumulator.arguments, "--current-clearance-run-card") == str(
        finalizer.run_card
    )


def test_replacement_continuation_uses_provider_free_public_marker_policy(
    tmp_path: Path,
) -> None:
    config, assignments = _render_replacement(tmp_path, REPLACEMENT_EMPTY_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
        "accumulate-replacement-clearance",
    ]
    assert all(stage.boundary.value == "provider_free" for stage in config.stages)
    _init, finalizer, resolver, accumulator = config.stages
    assert "review-disclosure-exceptions" not in {
        stage.command for stage in config.stages
    }
    assert "--require-no-model-review-eligible-exceptions" not in finalizer.arguments
    assert _flag_value(finalizer.arguments, "--public-marker-clearance-policy") == str(
        assignments["REPO_ROOT"]
        / "docs"
        / "disclosure-public-marker-policy-cycle-1-2026-08-06.json"
    )
    assert _flag_value(finalizer.arguments, "--plan-run-card") == str(
        assignments["PLAN_ROOT"] / "run-cards" / "plan-disclosure-provenance.json"
    )
    assert _flag_value(finalizer.arguments, "--routing-plan") == str(
        assignments["PLAN_ROOT"] / "disclosure-provenance-plan.json"
    )
    for forbidden in (
        "--model-review-authority",
        "--model-review-private-records",
        "--model-review-run-card",
        "--frozen-authority-root",
        "--provider-journal",
        "--provider-spend-authority",
    ):
        assert forbidden not in finalizer.arguments
    assert _flag_value(resolver.arguments, "--replacement-purchase-authority") == str(
        assignments["REPLACEMENT_ROOT"]
        / "01-plan"
        / "replacement-purchase-authority.json"
    )
    assert _flag_value(
        resolver.arguments, "--replacement-controlled-private-root"
    ) == str(assignments["SUCCESSOR_PRIVATE_ROOT"])
    assert _flag_value(resolver.arguments, "--clearance-run-card") == str(
        finalizer.run_card
    )
    assert _flag_value(accumulator.arguments, "--current-clearance-run-card") == str(
        finalizer.run_card
    )

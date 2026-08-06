from __future__ import annotations

from pathlib import Path

import legalforecast.cli as cli_module
from legalforecast.ingestion.cycle_manifest_template import render_cycle_config
from legalforecast.ingestion.cycle_orchestrator import load_cycle_config

ROOT = Path(__file__).parents[1]
REVIEW_TEMPLATE = (
    ROOT / "manifests" / "cycle-1-target-100.initial-recovery-disclosure.template.json"
)
NO_REVIEW_TEMPLATE = (
    ROOT
    / "manifests"
    / "cycle-1-target-100.initial-recovery-disclosure-no-review.template.json"
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


def _flag_value(arguments: tuple[str, ...], flag: str) -> str:
    return arguments[arguments.index(flag) + 1]


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
    config, _assignments_by_name = _render(tmp_path, NO_REVIEW_TEMPLATE)

    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "plan-disclosure-provenance",
        "finalize-provenance-quarantine",
        "resolve-post-recovery-documents",
    ]
    assert all(stage.boundary.value == "provider_free" for stage in config.stages)
    _init, plan, finalizer, resolver = config.stages
    assert _flag_value(plan.arguments, "--schema-version") == "v3"
    assert "--require-no-model-review-eligible-exceptions" in finalizer.arguments
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

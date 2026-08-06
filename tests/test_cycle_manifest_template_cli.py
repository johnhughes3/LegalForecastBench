from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import legalforecast.ingestion.cycle_manifest_template as cycle_manifest_template
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_manifest_template import (
    CycleManifestTemplateError,
    render_cycle_config,
)
from legalforecast.ingestion.cycle_orchestrator import load_cycle_config
from legalforecast.ingestion.disclosure_review_bundle import canonical_json_bytes
from legalforecast.labeling.provider_cycle_caps_materializer import (
    load_provider_cycle_caps_successor_policy,
)
from legalforecast.labeling.provider_journal import load_provider_cycle_caps
from legalforecast.protocol.policy_artifacts import (
    generate_labeling_policy,
    verify_labeling_policy,
)


def _template(root: str = "${ROOT}") -> dict[str, object]:
    run_card = f"{root}/run-cards/init-cycle.json"
    return {
        "schema_version": "legalforecast.acquisition_cycle_template.v1",
        "completion_mode": "partial",
        "variables": ["ROOT"],
        "config": {
            "schema_version": "legalforecast.acquisition_cycle_config.v1",
            "cycle_id": "cycle-next",
            "eligibility_anchor": "2026-06-30",
            "target_case_count": 100,
            "stages": [
                {
                    "id": "initialize",
                    "command": "init-cycle",
                    "boundary": "provider_free",
                    "arguments": [
                        "--output-root",
                        root,
                        "--eligibility-anchor",
                        "2026-06-30",
                        "--run-card-output",
                        run_card,
                        "--execute",
                        "--resume",
                    ],
                    "run_card": run_card,
                    "run_card_stage": "init-cycle",
                }
            ],
        },
    }


def _write_template(path: Path, payload: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(payload))


def test_render_cycle_config_cli_publishes_valid_canonical_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "published" / "cycle.json"
    output.parent.mkdir()
    cycle_root = tmp_path / "cycle"
    _write_template(template, _template())

    status = main(
        [
            "acquisition",
            "render-cycle-config",
            "--template",
            str(template),
            "--variable",
            f"ROOT={cycle_root}",
            "--output",
            str(output),
        ]
    )

    assert status == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["cycle_id"] == "cycle-next"
    assert receipt["stage_count"] == 1
    assert receipt["completion_mode"] == "partial"
    assert receipt["corpus_finalization_planned"] is False
    assert receipt["provider_activity_executed"] is False
    assert receipt["paid_activity_executed"] is False
    config = load_cycle_config(output)
    assert config.stages[0].run_card == (cycle_root / "run-cards" / "init-cycle.json")
    assert output.read_bytes() == canonical_json_bytes(json.loads(output.read_bytes()))


@pytest.mark.parametrize("argument_to_remove", ["--output-root"])
def test_render_cycle_config_cli_rejects_missing_required_stage_argument(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    argument_to_remove: str,
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    payload = _template()
    config = payload["config"]
    assert isinstance(config, dict)
    stages = config["stages"]
    assert isinstance(stages, list)
    stage = stages[0]
    assert isinstance(stage, dict)
    arguments = stage["arguments"]
    assert isinstance(arguments, list)
    index = arguments.index(argument_to_remove)
    del arguments[index : index + 2]
    _write_template(template, payload)

    assert (
        main(
            [
                "acquisition",
                "render-cycle-config",
                "--template",
                str(template),
                "--variable",
                f"ROOT={tmp_path / 'root'}",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert "arguments are invalid" in capsys.readouterr().err


def test_render_cycle_config_cli_rejects_unknown_stage_argument(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    payload = _template()
    config = payload["config"]
    assert isinstance(config, dict)
    stages = config["stages"]
    assert isinstance(stages, list)
    stage = stages[0]
    assert isinstance(stage, dict)
    arguments = stage["arguments"]
    assert isinstance(arguments, list)
    arguments.append("--not-a-real-flag")
    _write_template(template, payload)

    assert (
        main(
            [
                "acquisition",
                "render-cycle-config",
                "--template",
                str(template),
                "--variable",
                f"ROOT={tmp_path / 'root'}",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert "arguments are invalid" in capsys.readouterr().err


@pytest.mark.parametrize(
    "assignments,match",
    [
        ([], "missing variables: ROOT"),
        (["ROOT=relative"], "must be an absolute path"),
        (["ROOT=/one", "ROOT=/two"], "unique NAME=/absolute/path"),
        (["ROOT=/one", "EXTRA=/two"], "unexpected variables: EXTRA"),
    ],
)
def test_render_cycle_config_rejects_invalid_variable_assignments(
    tmp_path: Path,
    assignments: list[str],
    match: str,
) -> None:
    template = tmp_path / "template.json"
    _write_template(template, _template())

    with pytest.raises(CycleManifestTemplateError, match=match):
        render_cycle_config(
            template_path=template,
            output_path=tmp_path / "cycle.json",
            variable_assignments=assignments,
        )


def test_render_cycle_config_rejects_unused_declared_variable(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    payload = _template("/fixed")
    _write_template(template, payload)

    with pytest.raises(CycleManifestTemplateError, match="unused variables: ROOT"):
        render_cycle_config(
            template_path=template,
            output_path=tmp_path / "cycle.json",
            variable_assignments=["ROOT=/cycle"],
        )


def test_render_cycle_config_rejects_malformed_placeholder(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    payload = _template()
    config = payload["config"]
    assert isinstance(config, dict)
    config["cycle_id"] = "${root}"
    _write_template(template, payload)

    with pytest.raises(
        CycleManifestTemplateError,
        match="malformed or unresolved placeholder",
    ):
        render_cycle_config(
            template_path=template,
            output_path=tmp_path / "cycle.json",
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )


def test_corpus_template_requires_terminal_finalization(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    payload = _template()
    payload["completion_mode"] = "corpus"
    _write_template(template, payload)

    with pytest.raises(
        CycleManifestTemplateError,
        match="corpus template must end with finalize-corpus",
    ):
        render_cycle_config(
            template_path=template,
            output_path=tmp_path / "cycle.json",
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )


def test_render_cycle_config_never_replaces_existing_output(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    _write_template(template, _template())
    output.write_text("keep", encoding="utf-8")

    with pytest.raises(CycleManifestTemplateError, match="output already exists"):
        render_cycle_config(
            template_path=template,
            output_path=output,
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )

    assert output.read_text(encoding="utf-8") == "keep"


def test_render_cycle_config_rejects_symlinked_output_parent(tmp_path: Path) -> None:
    template = tmp_path / "template.json"
    _write_template(template, _template())
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(
        CycleManifestTemplateError,
        match="output directory must not contain symlinks",
    ):
        render_cycle_config(
            template_path=template,
            output_path=linked / "cycle.json",
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )


def test_render_cycle_config_does_not_create_through_symlinked_ancestor(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.json"
    _write_template(template, _template())
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        CycleManifestTemplateError,
        match="output directory must already exist",
    ):
        render_cycle_config(
            template_path=template,
            output_path=linked / "missing" / "cycle.json",
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )

    assert not (outside / "missing").exists()


def test_render_cycle_config_removes_output_after_parent_rebinding_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    _write_template(template, _template())
    original = cycle_manifest_template._require_directory_identity
    calls = 0

    def fail_after_creation(
        descriptor: int,
        path: Path,
        *,
        expected_identity: tuple[int, int],
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise CycleManifestTemplateError("simulated directory rebinding")
        original(descriptor, path, expected_identity=expected_identity)

    monkeypatch.setattr(
        cycle_manifest_template,
        "_require_directory_identity",
        fail_after_creation,
    )

    with pytest.raises(
        CycleManifestTemplateError,
        match="simulated directory rebinding",
    ):
        render_cycle_config(
            template_path=template,
            output_path=output,
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )

    assert not output.exists()


def test_render_cycle_config_rejects_parent_rebound_between_stat_and_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "template.json"
    output_parent = tmp_path / "published"
    output_parent.mkdir()
    output = output_parent / "cycle.json"
    displaced_parent = tmp_path / "displaced"
    _write_template(template, _template())
    original_open = os.open
    rebound = False

    def rebind_before_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal rebound
        if not rebound and dir_fd is None and Path(path) == output_parent:
            rebound = True
            output_parent.rename(displaced_parent)
            output_parent.mkdir()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(cycle_manifest_template.os, "open", rebind_before_open)

    with pytest.raises(
        CycleManifestTemplateError,
        match="output directory identity changed during publication",
    ):
        render_cycle_config(
            template_path=template,
            output_path=output,
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )

    assert not output.exists()
    assert not (displaced_parent / output.name).exists()


def test_render_cycle_config_never_exposes_partial_output_to_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    _write_template(template, _template())
    original_write = cycle_manifest_template._write_staging_payload
    staging_is_partial = threading.Event()
    finish_write = threading.Event()

    def pause_with_partial_staging(descriptor: int, payload: bytes) -> None:
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, payload[: len(payload) // 2])
        staging_is_partial.set()
        assert finish_write.wait(timeout=5)
        original_write(descriptor, payload)

    monkeypatch.setattr(
        cycle_manifest_template,
        "_write_staging_payload",
        pause_with_partial_staging,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            render_cycle_config,
            template_path=template,
            output_path=output,
            variable_assignments=[f"ROOT={tmp_path / 'root'}"],
        )
        assert staging_is_partial.wait(timeout=5)
        assert not output.exists()
        finish_write.set()
        receipt = future.result(timeout=5)

    assert output.read_bytes()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == receipt["output_sha256"]


def test_render_cycle_config_recovers_incomplete_crash_residue(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    root = tmp_path / "root"
    template_record = _template()
    _write_template(template, template_record)
    rendered = cycle_manifest_template._substitute(
        template_record["config"],
        {"ROOT": str(root)},
    )
    payload = canonical_json_bytes(rendered)
    staging = tmp_path / cycle_manifest_template._staging_name(output.name, payload)
    staging.write_bytes(payload[: len(payload) // 2])
    staging.chmod(0o600)

    render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"ROOT={root}"],
    )

    assert output.read_bytes() == payload
    assert not staging.exists()


def test_render_cycle_config_finishes_post_link_crash_residue_idempotently(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template.json"
    output = tmp_path / "cycle.json"
    root = tmp_path / "root"
    template_record = _template()
    _write_template(template, template_record)
    rendered = cycle_manifest_template._substitute(
        template_record["config"],
        {"ROOT": str(root)},
    )
    payload = canonical_json_bytes(rendered)
    staging = tmp_path / cycle_manifest_template._staging_name(output.name, payload)
    staging.write_bytes(payload)
    staging.chmod(0o600)
    output.hardlink_to(staging)
    assert output.stat().st_nlink == 2

    receipt = render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"ROOT={root}"],
    )

    assert output.read_bytes() == payload
    assert output.stat().st_nlink == 1
    assert not staging.exists()
    assert hashlib.sha256(payload).hexdigest() == receipt["output_sha256"]


def test_checked_in_template_example_renders(tmp_path: Path) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "acquisition-cycle.template.example.json"
    )

    receipt = render_cycle_config(
        template_path=template,
        output_path=tmp_path / "cycle.json",
        variable_assignments=[f"ARTIFACT_ROOT={tmp_path / 'artifacts'}"],
    )

    assert receipt["target_case_count"] == 100
    assert receipt["stage_count"] == 1


def test_checked_in_target_100_template_is_a_complete_acquisition_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.acquisition-cycle.template.json"
    )
    output = tmp_path / "cycle.json"
    assignments = {
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
        "ARTIFACT_ROOT": tmp_path / "artifacts",
        "PRIVATE_ROOT": tmp_path / "private",
        "PARSER_ROOT": tmp_path / "parser",
    }

    status = main(
        [
            "acquisition",
            "render-cycle-config",
            "--template",
            str(template),
            *[
                argument
                for name, path in assignments.items()
                for argument in ("--variable", f"{name}={path}")
            ],
            "--output",
            str(output),
        ]
    )

    assert status == 0
    receipt = json.loads(capsys.readouterr().out)
    config = load_cycle_config(output)
    commands = tuple(stage.command for stage in config.stages)
    assert receipt["completion_mode"] == "corpus"
    assert receipt["corpus_finalization_planned"] is True
    assert receipt["stage_count"] == 27
    assert config.target_case_count == 100
    assert commands[0] == "init-cycle"
    assert commands[-1] == "finalize-corpus"
    assert "purchase-missing-recap-fetch" in commands
    assert "parse-documents" in commands
    assert "llm-unitize" in commands
    assert "llm-review-stage-a" in commands
    assert "llm-label" in commands
    assert "plan-packet-inputs" in commands
    assert "build-packets" in commands
    assert not {"evaluate", "freeze", "dispatch"} & set(commands)
    assert all("--execute" in stage.arguments for stage in config.stages)
    assert all("--resume" in stage.arguments for stage in config.stages)
    clear_stages = [
        stage
        for stage in config.stages
        if stage.command == "clear-provenance-disclosures"
    ]
    assert len(clear_stages) == 2
    assert all(stage.run_card_stage == "clear-disclosures" for stage in clear_stages)
    assert all(
        stage.arguments[stage.arguments.index("--schema-version") + 1] == "v2"
        for stage in config.stages
        if stage.command == "plan-disclosure-provenance"
    )
    provider_caps_path = (
        assignments["ARTIFACT_ROOT"]
        / "01-provider-authority"
        / "provider-cycle-caps.json"
    )
    provider_caps_consumers = [
        stage for stage in config.stages if "--provider-cycle-caps" in stage.arguments
    ]
    assert provider_caps_consumers
    assert all(
        stage.arguments[stage.arguments.index("--provider-cycle-caps") + 1]
        == str(provider_caps_path)
        for stage in provider_caps_consumers
    )
    assert "--target-clean-cases" in config.stages[-1].arguments
    target_index = config.stages[-1].arguments.index("--target-clean-cases")
    assert config.stages[-1].arguments[target_index + 1] == "100"
    assert "--original-llm-label-labels" in config.stages[-1].arguments
    assert "--original-llm-label-audit" in config.stages[-1].arguments
    assert "/tmp" not in template.read_text(encoding="utf-8")


def test_checked_in_replacement_tranche_template_requires_successor_authority(
    tmp_path: Path,
) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.replacement-purchase-tranche.template.json"
    )
    output = tmp_path / "replacement-cycle.json"
    assignments = {
        "REPO_ROOT": tmp_path / "repo",
        "SOURCE_ROOT": tmp_path / "source",
        "ARTIFACT_ROOT": tmp_path / "artifacts",
        "INITIAL_PRIVATE_ROOT": tmp_path / "private-initial",
        "PRIOR_CLEARANCE": tmp_path / "prior" / "disclosure-clearance.jsonl",
        "PRIOR_CLEARANCE_RUN_CARD": (
            tmp_path / "prior" / "run-cards" / "clear-provenance-disclosures.json"
        ),
        "REPLACEMENT_ROOT": tmp_path / "replacement",
        "SUCCESSOR_PRIVATE_ROOT": tmp_path / "private-successor",
    }

    receipt = render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    config = load_cycle_config(output)

    assert receipt["completion_mode"] == "partial"
    assert receipt["stage_count"] == 9
    assert receipt["provider_activity_requested"] is False
    assert receipt["provider_activity_executed"] is False
    assert receipt["paid_activity_requested"] is False
    assert receipt["paid_activity_executed"] is False
    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "record-replacement-purchase-approval",
        "purchase-missing-recap-fetch",
        "recover-recap-fetch-quarantine",
        "plan-disclosure-provenance",
        "record-disclosure-review-decisions",
        "clear-provenance-disclosures",
        "resolve-post-recovery-documents",
        "accumulate-replacement-clearance",
    ]
    approval_stage = config.stages[1]
    assert "--authority-output" in approval_stage.arguments
    assert "--attempt-policy-output" in approval_stage.arguments
    assert "--frontier" not in approval_stage.arguments
    assert (
        approval_stage.arguments[
            approval_stage.arguments.index("--ranked-reserve-projection-sha256") + 1
        ]
        == "sha256:1dab63dd17c69fd0222b58d6e30af67ad56550ca6578262f1089222a68257e56"
    )
    paid_stage = next(
        stage
        for stage in config.stages
        if stage.command == "purchase-missing-recap-fetch"
    )
    assert paid_stage.boundary.value == "paid"
    assert "--replacement-purchase-authority" in paid_stage.arguments
    assert "--replacement-controlled-private-root" in paid_stage.arguments
    assert "--purchase-ledger-initialization-receipt" in paid_stage.arguments
    assert "--broker-policy" not in paid_stage.arguments
    assert "--direct-courtlistener-purchase" in paid_stage.arguments
    assert paid_stage.arguments[paid_stage.arguments.index("--budget-plan") + 1] == str(
        assignments["REPLACEMENT_ROOT"] / "01-plan" / "replacement-budget-plan.json"
    )
    assert (
        paid_stage.arguments[
            paid_stage.arguments.index("--request-budget-max-wait-seconds") + 1
        ]
        == "3700"
    )
    assert "--acknowledge-pacer-fees" in paid_stage.arguments
    assert not any(
        stage.command == "generate-recap-fetch-broker-policy" for stage in config.stages
    )
    recovery = next(
        stage
        for stage in config.stages
        if stage.command == "recover-recap-fetch-quarantine"
    )
    assert "--replacement-purchase-authority" in recovery.arguments
    assert "--target-projection-run-card" not in recovery.arguments
    resolver = next(
        stage
        for stage in config.stages
        if stage.command == "resolve-post-recovery-documents"
    )
    assert "--replacement-purchase-authority" in resolver.arguments
    assert "--replacement-controlled-private-root" in resolver.arguments
    accumulation = config.stages[-1]
    assert accumulation.command == "accumulate-replacement-clearance"
    assert accumulation.arguments[
        accumulation.arguments.index("--prior-purchased-clearance") + 1
    ] == str(assignments["PRIOR_CLEARANCE"])
    rendered = output.read_text(encoding="utf-8")
    assert "replacement-frontier.json" not in rendered
    assert "recap-fetch-broker" not in rendered


def test_checked_in_replacement_reprojection_consumes_active_exact_100_selection(
    tmp_path: Path,
) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.replacement-reprojection.template.json"
    )
    output = tmp_path / "replacement-reprojection.json"
    assignments = {
        "REPO_ROOT": tmp_path / "repo",
        "ARTIFACT_ROOT": tmp_path / "artifacts",
        "INITIAL_PRIVATE_ROOT": tmp_path / "private-initial",
        "REPLACEMENT_ROOT": tmp_path / "replacement",
        "SOURCE_ROOT": tmp_path / "source",
    }

    receipt = render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    config = load_cycle_config(output)

    assert receipt["completion_mode"] == "partial"
    assert receipt["stage_count"] == 2
    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "project-target-cohort",
    ]
    projection = config.stages[-1]
    assert projection.arguments[projection.arguments.index("--selection") + 1] == str(
        assignments["REPLACEMENT_ROOT"] / "01-plan" / "active-selection.jsonl"
    )
    assert projection.arguments[
        projection.arguments.index("--replacement-result") + 1
    ] == str(assignments["REPLACEMENT_ROOT"] / "01-plan" / "replacement-result.json")
    assert "--replacement-replay-frontier" in projection.arguments
    assert "--replacement-replay-purchase-ledger" in projection.arguments
    assert "--replacement-replay-purchased-clearance" in projection.arguments
    assert "--replacement-replay-tranche-selection" in projection.arguments
    assert projection.arguments[projection.arguments.index("--output-root") + 1] == str(
        assignments["REPLACEMENT_ROOT"] / "01-projection"
    )
    assert (
        projection.arguments[projection.arguments.index("--target-case-count") + 1]
        == "100"
    )
    assert projection.run_card == (
        assignments["REPLACEMENT_ROOT"]
        / "01-projection"
        / "run-cards"
        / "project-target-cohort.json"
    )
    assert projection.arguments[
        projection.arguments.index("--replacement-replay-purchased-clearance") + 1
    ] == str(
        assignments["REPLACEMENT_ROOT"]
        / "07-cumulative-clearance"
        / "disclosure-clearance.jsonl"
    )


def test_replacement_corpus_consolidates_promoted_purchases_and_exclusions(
    tmp_path: Path,
) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.replacement-corpus.template.json"
    )
    output = tmp_path / "replacement-corpus.json"
    assignments = {
        "INITIAL_RECOVERY_SOURCE": tmp_path / "initial-recovery-source.json",
        "PREPARATION_ROOT": tmp_path / "preparation",
        "PURCHASE_PRIVATE_ROOT": tmp_path / "purchase-private",
        "PURCHASE_ROOT": tmp_path / "purchase",
        "EXACT100_ROOT": tmp_path / "exact-100",
        "PARSER_ROOT": tmp_path / "parser",
        "SUCCESSOR_ARTIFACT_ROOT": tmp_path / "successor",
        "SUCCESSOR_PRIVATE_ROOT": tmp_path / "successor-private",
        "SUCCESSOR_RECOVERY_SOURCE_DIR": tmp_path / "successor-recovery-sources",
        "REPO_ROOT": Path(__file__).parents[1],
        "SOURCE_ROOT": tmp_path / "source",
    }

    receipt = render_cycle_config(
        template_path=template,
        output_path=output,
        variable_assignments=[f"{name}={path}" for name, path in assignments.items()],
    )
    config = load_cycle_config(output)

    assert receipt["completion_mode"] == "corpus"
    assert [stage.command for stage in config.stages] == [
        "init-cycle",
        "build-replacement-recovery-index",
        "build-replacement-exclusions",
        "consolidate-replacement-recovery",
        "materialize-cohort-documents",
        "plan-parse-documents",
        "parse-documents",
        "llm-unitize",
        "llm-review-stage-a",
        "apply-unitization-review",
        "build-decision-texts",
        "llm-label",
        "llm-label",
        "llm-label",
        "plan-label-audit",
        "apply-lawyer-review",
        "plan-packet-inputs",
        "build-packets",
        "finalize-corpus",
    ]
    exact_selection = assignments["EXACT100_ROOT"] / "target-cohort-selection.jsonl"
    recovery_index, exclusions, consolidation = config.stages[1:4]
    consolidated_root = (
        assignments["SUCCESSOR_ARTIFACT_ROOT"] / "11-consolidated-recovery"
    )
    assert recovery_index.boundary.value == "provider_free"
    assert consolidation.boundary.value == "provider_free"
    assert consolidation.arguments[
        consolidation.arguments.index("--target-purchased-manifest") + 1
    ] == str(assignments["EXACT100_ROOT"] / "purchased-document-downloads.jsonl")
    assert consolidation.arguments[
        consolidation.arguments.index("--controlled-private-root") + 1
    ] == str(assignments["PURCHASE_PRIVATE_ROOT"] / "purchase-approval")
    assert exclusions.arguments[
        exclusions.arguments.index("--target-cohort-root") + 1
    ] == str(assignments["EXACT100_ROOT"])
    materialize = config.stages[4]
    assert materialize.arguments[
        materialize.arguments.index("--preparation-root") + 1
    ] == str(assignments["PREPARATION_ROOT"])
    assert materialize.arguments[
        materialize.arguments.index("--target-cohort-root") + 1
    ] == str(assignments["EXACT100_ROOT"])
    assert materialize.arguments[
        materialize.arguments.index("--purchased-recovery-root") + 1
    ] == str(consolidated_root)
    assert materialize.arguments[
        materialize.arguments.index("--purchased-disclosure-clearance") + 1
    ] == str(consolidated_root / "disclosure-clearance.jsonl")
    assert materialize.arguments[
        materialize.arguments.index("--purchased-clearance-run-card") + 1
    ] == str(consolidation.run_card)
    assert materialize.arguments[
        materialize.arguments.index("--purchase-result") + 1
    ] == str(
        assignments["PURCHASE_ROOT"]
        / "07-purchase"
        / "purchased-document-downloads.jsonl"
    )
    assert materialize.arguments[
        materialize.arguments.index("--purchase-run-card") + 1
    ] == str(
        assignments["PURCHASE_ROOT"]
        / "07-purchase"
        / "run-cards"
        / "purchase-missing-recap-fetch.json"
    )
    selection_consumers = [
        stage for stage in config.stages if "--selection" in stage.arguments
    ]
    assert selection_consumers
    assert all(
        stage.arguments[stage.arguments.index("--selection") + 1]
        == str(exact_selection)
        for stage in selection_consumers
    )
    assert (
        config.stages[-1].arguments[
            config.stages[-1].arguments.index("--target-clean-cases") + 1
        ]
        == "100"
    )
    resolved_consumers = [
        stage
        for stage in config.stages
        if "--resolved-post-recovery-documents" in stage.arguments
    ]
    assert resolved_consumers
    assert all(
        stage.arguments[stage.arguments.index("--resolved-post-recovery-documents") + 1]
        == str(consolidated_root / "resolved-post-recovery-documents.jsonl")
        for stage in resolved_consumers
    )
    finalization = config.stages[-1]
    successor_exclusions = (
        assignments["SUCCESSOR_ARTIFACT_ROOT"]
        / "10-successor-exclusions"
        / "successor-target-exclusions.jsonl"
    )
    exclusion_sources = [
        finalization.arguments[index + 1]
        for index, argument in enumerate(finalization.arguments)
        if argument == "--exclusion-source"
    ]
    assert exclusion_sources == [
        str(
            assignments["SUCCESSOR_ARTIFACT_ROOT"]
            / "23-packet-plan"
            / "exclusion-ledger.jsonl"
        ),
        str(successor_exclusions),
    ]
    assert finalization.arguments[
        finalization.arguments.index("--replacement-exclusion-run-card") + 1
    ] == str(
        assignments["SUCCESSOR_ARTIFACT_ROOT"]
        / "10-successor-exclusions"
        / "run-cards"
        / "build-replacement-exclusions.json"
    )
    assert (
        str(assignments["EXACT100_ROOT"] / "target-cohort-exclusions.jsonl")
        not in exclusion_sources
    )
    successor_private_paths = [
        Path(argument)
        for stage in config.stages
        for argument in (*stage.arguments, str(stage.run_card))
        if Path(argument).is_relative_to(assignments["SUCCESSOR_PRIVATE_ROOT"])
    ]
    assert successor_private_paths
    caps = str(
        assignments["REPO_ROOT"]
        / "model_registries"
        / "cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )
    provider_stages = [
        stage
        for stage in config.stages
        if stage.command in {"llm-unitize", "llm-review-stage-a"}
        or "--execution-provider" in stage.arguments
    ]
    assert len(provider_stages) == 4
    assert all(
        "--local-provider-journal-only" in stage.arguments for stage in provider_stages
    )
    assert all(
        stage.arguments[stage.arguments.index("--provider-cycle-caps") + 1] == caps
        for stage in provider_stages
    )
    for stage in config.stages:
        for argument in (*stage.arguments, str(stage.run_card)):
            if argument.startswith(str(assignments["SUCCESSOR_ARTIFACT_ROOT"])):
                continue
            assert not argument.startswith(str(tmp_path / "replacement"))
    rendered = output.read_text(encoding="utf-8")
    assert "courtlistener-recap-fetch-purchases.json" not in rendered
    assert "provider-authority-table" not in rendered
    assert "provider-authority-region" not in rendered

    runbook = (
        Path(__file__).parents[1] / "docs" / "official-run-runbook.md"
    ).read_text(encoding="utf-8")
    assert "EXACT100_ROOT/purchased-document-downloads.jsonl" in runbook
    assert "EXACT100_ROOT/document-downloads-merged.jsonl" in runbook
    assert "EXACT100_ROOT/document-downloads.jsonl" not in runbook
    schema = (
        Path(__file__).parents[1] / "docs" / "schemas" / "clearance-replacement-v1.md"
    ).read_text(encoding="utf-8")
    assert "`run-cards/project-target-cohort.json` under `EXACT100_ROOT`" in schema
    assert "`01-projection/run-cards/project-target-cohort.json`" not in schema


def test_replacement_corpus_template_rejects_stale_single_root_variables(
    tmp_path: Path,
) -> None:
    template = (
        Path(__file__).parents[1]
        / "manifests"
        / "cycle-1-target-100.replacement-corpus.template.json"
    )

    with pytest.raises(
        CycleManifestTemplateError,
        match=(
            r"missing variables: .*EXACT100_ROOT"
            r".*unexpected variables: ARTIFACT_ROOT"
        ),
    ):
        render_cycle_config(
            template_path=template,
            output_path=tmp_path / "stale.json",
            variable_assignments=[
                f"ARTIFACT_ROOT={tmp_path / 'artifacts'}",
                f"PARSER_ROOT={tmp_path / 'parser'}",
                f"PRIVATE_ROOT={tmp_path / 'private'}",
                f"REPLACEMENT_ROOT={tmp_path / 'replacement'}",
                f"REPO_ROOT={Path(__file__).parents[1]}",
                f"SOURCE_ROOT={tmp_path / 'source'}",
            ],
        )


def test_checked_in_target_100_provider_caps_inputs_share_cycle_identity() -> None:
    root = Path(__file__).parents[1] / "model_registries"
    base_path = root / "cycle-1-target-100-provider-caps-base-2026-07-28.json"
    policy_path = (
        root / "cycle-1-target-100-provider-caps-successor-policy-2026-07-28.json"
    )
    policy_bytes = policy_path.read_bytes()

    base = load_provider_cycle_caps(base_path)
    policy = load_provider_cycle_caps_successor_policy(
        policy_bytes,
        expected_sha256=hashlib.sha256(policy_bytes).hexdigest(),
    )

    assert base.cycle_id == "cycle-1-target-100-2026-07-25"
    assert policy.cycle_id == base.cycle_id
    assert set(policy.provider_accounts) == set(base.providers)


def test_checked_in_target_100_labeling_policy_shares_cycle_identity() -> None:
    root = Path(__file__).parents[1]
    cycle_id = "cycle-1-target-100-2026-07-25"
    policy_path = root / "docs" / "labeling-policy.json"
    registry_path = root / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
    provider_caps_path = (
        root
        / "model_registries"
        / "cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )

    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    verify_labeling_policy(
        policy,
        judge_registry_path=registry_path,
        expected_cycle_id=cycle_id,
    )
    expected = generate_labeling_policy(
        cycle_id=cycle_id,
        judge_registry_path=registry_path,
        published_at=datetime(2026, 7, 28, 22, 58, 15, tzinfo=UTC),
        threshold_source=(
            "docs/schemas/evaluation-policy-artifacts-v1.md: "
            "legalforecast.labeling_policy.v1 Cycle 1 audit thresholds "
            "approved in docs/labeling-protocol.md"
        ),
    )
    assert policy == expected
    legacy = generate_labeling_policy(
        cycle_id="cycle-1",
        judge_registry_path=registry_path,
        published_at=datetime(2026, 7, 15, 9, 41, 10, tzinfo=UTC),
        threshold_source=(
            "docs/schemas/evaluation-policy-artifacts-v1.md: "
            "legalforecast.labeling_policy.v1 Cycle 1 audit thresholds "
            "approved in docs/labeling-protocol.md"
        ),
    )
    assert {
        key: value
        for key, value in policy["policy"].items()
        if key not in {"cycle_id", "published_at"}
    } == {
        key: value
        for key, value in legacy["policy"].items()
        if key not in {"cycle_id", "published_at"}
    }
    policy_file_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    assert policy_file_sha256 == (
        "0dd6f10a4d8354334e4f0b5f14534573ebbe7e807e52497db5d424de30f4e2d0"
    )
    assert load_provider_cycle_caps(provider_caps_path).cycle_id == cycle_id
    prerequisites = (
        root / "docs" / "cycle-1-target-100-direct-prerequisites.md"
    ).read_text(encoding="utf-8")
    assert (
        "| Labeling policy | `$REPO_ROOT/docs/labeling-policy.json` | "
        f"`{policy_file_sha256}` |"
    ) in prerequisites
    assert f"--cycle-id {cycle_id}" in prerequisites

    expected_argument = "${REPO_ROOT}/docs/labeling-policy.json"
    expected_cycle_ids = {
        "cycle-1-target-100.acquisition-cycle.template.json": cycle_id,
        "cycle-1-target-100.replacement-corpus.template.json": (
            f"{cycle_id}-replacement-corpus"
        ),
    }
    for template_name, expected_cycle_id in expected_cycle_ids.items():
        template = json.loads(
            (root / "manifests" / template_name).read_text(encoding="utf-8")
        )
        assert template["config"]["cycle_id"] == expected_cycle_id
        consumers = [
            stage
            for stage in template["config"]["stages"]
            if "--labeling-policy" in stage["arguments"]
        ]
        assert consumers
        assert all(
            stage["arguments"][stage["arguments"].index("--labeling-policy") + 1]
            == expected_argument
            for stage in consumers
        )

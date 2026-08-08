from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import cast

import pytest
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.labeling import official_paid_job
from legalforecast.labeling.official_paid_job import (
    OfficialPaidLabelingJobError,
    _within_root,
    run_official_paid_labeling_job,
)
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = "a" * 40


def test_main_has_explicit_error_return_when_parser_exit_returns(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    def reject_job(**kwargs: object) -> int:
        raise OfficialPaidLabelingJobError("invalid sealed job")

    exit_calls: list[tuple[int, str | None]] = []

    def record_exit(
        parser: object,
        status: int = 0,
        message: str | None = None,
    ) -> None:
        exit_calls.append((status, message))

    monkeypatch.setattr(
        official_paid_job,
        "run_official_paid_labeling_job",
        reject_job,
    )
    monkeypatch.setattr("argparse.ArgumentParser.exit", record_exit)

    status = official_paid_job.main(
        [
            "--job-manifest",
            str(tmp_path / "manifest.json"),
            "--job-root",
            str(tmp_path),
            "--release-sha",
            RELEASE_SHA,
            "--stage",
            "llm-unitize",
            "--provider",
            "anthropic",
            "--expected-provider-account-alias",
            "anthropic-primary",
        ]
    )

    assert status == 2
    assert len(exit_calls) == 1
    exit_status, message = exit_calls[0]
    assert exit_status == 2
    assert message is not None
    assert message.endswith(": error: invalid sealed job\n")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _job_root(tmp_path: Path) -> tuple[Path, list[str]]:
    root = tmp_path / "job"
    root.mkdir()
    registry_path = root / "judge-registry.json"
    shutil.copyfile(
        ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json",
        registry_path,
    )
    model_keys = [
        entry.registry_key for entry in load_model_registry(registry_path).entries
    ]
    _write_json(
        root / "provider-caps.json",
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": "cycle-1",
            "spend_authority": {
                "backend": "dynamodb",
                "resource_identity_sha256": "b" * 64,
                "ledger_scope_fields": ["cycle_id", "provider", "account"],
                "max_billable_attempts": 3,
                "failure_threshold": 3,
                "failure_window_seconds": 300,
            },
            "providers": [
                {
                    "provider": provider,
                    "account": f"{provider}-primary",
                    "cycle_reservation_cap_usd": "10.00",
                    "external_spend_limit_usd": "20.00",
                    "external_limit_scope": "test fixture",
                    "external_limit_source": "test fixture",
                    "verified_at": "2026-07-12T16:00:00Z",
                }
                for provider in ("anthropic", "google", "openai")
            ],
        },
    )
    return root, model_keys


def _write_label_job(root: Path, model_keys: list[str], *, provider: str) -> Path:
    required_inputs = {
        "decision-texts": "inputs/decision-texts.jsonl",
        "decision-texts-manifest": "inputs/decision-texts-manifest.json",
        "decision-texts-run-card": "inputs/decision-texts-card.json",
        "evaluated-model-registry": "inputs/evaluated-registry.json",
        "llm-review-stage-a-run-card": "inputs/review-card.json",
        "llm-unitization-run-card": "inputs/unitization-card.json",
        "parser-manifest": "inputs/parser-manifest.jsonl",
        "prediction-units": "inputs/finalized-units.jsonl",
        "selection": "inputs/selection.jsonl",
        "unitization-review-run-card": "inputs/apply-card.json",
    }
    for relative in required_inputs.values():
        _write_json(root / relative, {})
    markdown_root = root / "inputs/markdown"
    markdown_root.mkdir(parents=True)
    (markdown_root / "fixture.md").write_text("fixture\n", encoding="utf-8")
    path = root / "official-paid-labeling-job.json"
    _write_json(
        path,
        {
            "schema_version": "legalforecast.official_paid_labeling_job.v1",
            "release_sha": RELEASE_SHA,
            "stage": "llm-label-provider-shard",
            "provider": provider,
            "arguments": {
                **required_inputs,
                "markdown-root": "inputs/markdown",
                "model-key": model_keys,
                "model-registry": "judge-registry.json",
                "output-root": "output",
                "provider-cycle-caps": "provider-caps.json",
                "provider-journal": "output/provider-attempts.sqlite3",
            },
        },
    )
    return path


def test_label_job_binds_complete_panel_to_one_provider_and_authority(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")
    captured: dict[str, object] = {}

    def record_child(*, provider: str, command: tuple[str, ...]) -> int:
        captured["provider"] = provider
        captured["command"] = command
        return 0

    monkeypatch.setattr(
        official_paid_job, "run_provider_isolated_command", record_child
    )

    result = run_official_paid_labeling_job(
        job_manifest_path=manifest,
        job_root=root,
        release_sha=RELEASE_SHA,
        stage="llm-label-provider-shard",
        provider="openai",
        provider_authority_table="exact-provider-authority",
        provider_authority_region="us-east-1",
        expected_provider_account_alias="openai-primary",
    )

    assert result == 0
    assert captured["provider"] == "openai"
    command = list(cast(tuple[str, ...], captured["command"]))
    assert Path(command[0]).name == "legalforecast"
    assert command[1:3] == ["acquisition", "llm-label"]
    assert "-m" not in command
    assert "legalforecast.cli" not in command
    assert command[-7:] == [
        "--execution-provider",
        "openai",
        "--provider-authority-table",
        "exact-provider-authority",
        "--provider-authority-region",
        "us-east-1",
        "--execute",
    ]
    assert command.count("--model-key") == len(model_keys)
    assert "--provider-shard-audit" not in command
    assert "--provider-shard-run-card" not in command


def test_job_fails_closed_when_legalforecast_entry_point_is_unavailable(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")

    monkeypatch.setattr(
        official_paid_job,
        "sys",
        type("StubSys", (), {"executable": "/tmp/reviewed/python"})(),
    )
    monkeypatch.setattr(official_paid_job.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="legalforecast entry point is unavailable",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="openai",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="openai-primary",
        )


def test_validate_only_checks_all_inputs_without_authority_or_provider_cli(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="google")
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    assert (
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="google",
            provider_authority_table="",
            provider_authority_region="",
            expected_provider_account_alias="google-primary",
            validate_only=True,
        )
        == 0
    )

    (root / "inputs/selection.jsonl").unlink()
    with pytest.raises(OfficialPaidLabelingJobError, match="required input is absent"):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="google",
            provider_authority_table="",
            provider_authority_region="",
            expected_provider_account_alias="google-primary",
            validate_only=True,
        )


def test_job_rejects_cross_stage_provider_before_cli(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="outside the reviewed allowlist",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-unitize",
            provider="openai",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="openai-primary",
        )


def test_job_rejects_path_escape_and_authority_argument_substitution(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="google")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["arguments"]["model-registry"] = "../outside.json"
    payload["arguments"]["provider-authority-table"] = "substitute-table"
    _write_json(manifest, payload)
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="not allowlisted",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="google",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="google-primary",
        )

    del payload["arguments"]["provider-authority-table"]
    _write_json(manifest, payload)
    with pytest.raises(OfficialPaidLabelingJobError, match="path is unsafe"):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="google",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="google-primary",
        )


@pytest.mark.parametrize("path_name", ["provider-journal", "labels-output"])
def test_job_rejects_output_paths_outside_output_root(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    path_name: str,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["arguments"][path_name] = f"outside-output/{path_name}"
    _write_json(manifest, payload)
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match=rf"{path_name} must remain under output-root",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="openai",
            provider_authority_table="",
            provider_authority_region="",
            expected_provider_account_alias="openai-primary",
            validate_only=True,
        )


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_job_rejects_non_finite_numeric_arguments(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    non_finite: float,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["arguments"]["high-confidence-threshold"] = non_finite
    _write_json(manifest, payload)
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="high-confidence-threshold has an invalid value",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="openai",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="openai-primary",
        )


@pytest.mark.parametrize("missing_component", ["root", "path"])
def test_within_root_wraps_missing_strict_resolution(
    tmp_path: Path,
    missing_component: str,
) -> None:
    root = tmp_path / "job"
    path = root / "official-paid-labeling-job.json"
    if missing_component == "path":
        root.mkdir()

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="sealed path is unavailable",
    ) as exc_info:
        _within_root(path, root, must_exist=True)

    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


@pytest.mark.parametrize("unreadable_component", ["root", "path"])
def test_within_root_wraps_unreadable_strict_resolution(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    unreadable_component: str,
) -> None:
    root = tmp_path / "job"
    root.mkdir()
    path = root / "official-paid-labeling-job.json"
    path.touch()
    unreadable = root if unreadable_component == "root" else path
    original_resolve = Path.resolve

    def resolve_with_unreadable_path(
        candidate: Path,
        *,
        strict: bool = False,
    ) -> Path:
        if strict and candidate == unreadable:
            raise PermissionError("permission denied")
        return original_resolve(candidate, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_with_unreadable_path)

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="sealed path is unavailable",
    ) as exc_info:
        _within_root(path, root, must_exist=True)

    assert isinstance(exc_info.value.__cause__, PermissionError)


def test_job_rejects_account_alias_drift(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="google")
    monkeypatch.setattr(
        official_paid_job,
        "run_provider_isolated_command",
        lambda **kwargs: pytest.fail(f"provider child must not run: {kwargs}"),
    )

    with pytest.raises(
        OfficialPaidLabelingJobError,
        match="account alias differs",
    ):
        run_official_paid_labeling_job(
            job_manifest_path=manifest,
            job_root=root,
            release_sha=RELEASE_SHA,
            stage="llm-label-provider-shard",
            provider="google",
            provider_authority_table="exact-provider-authority",
            provider_authority_region="us-east-1",
            expected_provider_account_alias="google-other",
        )

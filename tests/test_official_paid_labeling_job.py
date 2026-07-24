from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from legalforecast import cli
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.labeling.official_paid_job import (
    OfficialPaidLabelingJobError,
    run_official_paid_labeling_job,
)
from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[1]
RELEASE_SHA = "a" * 40


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
    path = root / "official-paid-labeling-job.json"
    _write_json(
        path,
        {
            "schema_version": "legalforecast.official_paid_labeling_job.v1",
            "release_sha": RELEASE_SHA,
            "stage": "llm-label-provider-shard",
            "provider": provider,
            "arguments": {
                "model-key": model_keys,
                "model-registry": "judge-registry.json",
                "output-root": "output",
                "provider-cycle-caps": "provider-caps.json",
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
    captured: list[str] = []
    monkeypatch.setattr(cli, "main", lambda args: captured.extend(args) or 0)

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
    assert captured[:2] == ["acquisition", "llm-label"]
    assert captured[-7:] == [
        "--execution-provider",
        "openai",
        "--provider-authority-table",
        "exact-provider-authority",
        "--provider-authority-region",
        "us-east-1",
        "--execute",
    ]
    assert captured.count("--model-key") == len(model_keys)
    assert "--provider-shard-audit" not in captured
    assert "--provider-shard-run-card" not in captured


def test_job_rejects_cross_stage_provider_before_cli(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="openai")
    monkeypatch.setattr(
        cli,
        "main",
        lambda args: pytest.fail(f"CLI must not run: {args}"),
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
        cli,
        "main",
        lambda args: pytest.fail(f"CLI must not run: {args}"),
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
    with pytest.raises(
        OfficialPaidLabelingJobError, match="escapes the sealed job root"
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


def test_job_rejects_account_alias_drift(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root, model_keys = _job_root(tmp_path)
    manifest = _write_label_job(root, model_keys, provider="google")
    monkeypatch.setattr(
        cli,
        "main",
        lambda args: pytest.fail(f"CLI must not run: {args}"),
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

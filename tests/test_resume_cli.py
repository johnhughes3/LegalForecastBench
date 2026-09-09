from __future__ import annotations

import argparse
import io
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import pytest
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
)
from legalforecast.runner.ledger import RunnerLedger
from legalforecast.runner.recovery import (
    RECOVERY_RUN_TITLE,
    RECOVERY_WORKFLOW,
    SOURCE_WORKFLOW,
    GhRecoveryClient,
    RecoveryError,
    build_recovery_plan,
)

RUN_ID = 123456789
SOURCE_HEAD_SHA = "b" * 40
RELEASE_SHA = "a" * 40
REGISTRY_BYTES = b'{"models":[]}\n'
REGISTRY_SHA = __import__("hashlib").sha256(REGISTRY_BYTES).hexdigest()


def _zip(members: Mapping[str, bytes | str]) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return output.getvalue()


def _ledger_bytes() -> tuple[bytes, str]:
    identity = {
        "schema_version": "legalforecast.public-run-identity.v1",
        "forecast_release_digest": "d" * 64,
        "model_key": "openai:gpt-6-astra",
        "model_registry_sha256": REGISTRY_SHA,
        "model_registry_entry_sha256": "e" * 64,
        "served_model_version": "gpt-6-astra",
        "repeat_count": 1,
        "account": "official-account",
    }
    identity_json = ARTIFACT_CANONICAL_JSON_V1.encode(identity).decode()
    identity_sha = str(
        ARTIFACT_RAW_SHA256_V1.commit(identity, domain=PUBLIC_RUN_IDENTITY_V1).digest
    )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "ledger.sqlite3"
        with RunnerLedger(path) as ledger:
            ledger.ensure_run(
                identity_sha256=identity_sha,
                identity_json=identity_json,
                release_digest="d" * 64,
                harness="native",
                model_key="openai:gpt-6-astra",
                ceiling_microusd=250_000_000,
                approval_reference="",
            )
        return path.read_bytes(), identity_sha


class FakeRecoveryClient:
    def __init__(self, *, latest_attempt: int = 1) -> None:
        self.latest_attempt = latest_attempt
        self.dispatched: list[tuple[str, str, str, Mapping[str, str]]] = []
        self.active_runs: tuple[Mapping[str, object], ...] = ()
        ledger, run_identity_sha = _ledger_bytes()
        export = {
            "schema_version": "legalforecast.forecast-run.v1",
            "workflow_run_id": RUN_ID,
            "workflow_run_attempt": 1,
            "release_sha": RELEASE_SHA,
            "manifest_uri": "s3://bucket/run-manifest.json",
            "forecast_release_uri": "s3://bucket/forecast-release.json",
            "artifact_root_uri": "s3://bucket/artifacts/",
            "model_registry_uri": "model_registries/frozen.json",
            "model_key": "openai:gpt-6-astra",
            "model_registry_sha256": REGISTRY_SHA,
            "run_identity_sha256": run_identity_sha,
            "repeat_count": 1,
        }
        summary = {
            "schema_version": "legalforecast.forecast-run-summary.v1",
            "workflow_run_id": RUN_ID,
            "workflow_run_attempt": 1,
            "state_artifact_count": 3,
            "completed_cells": 0,
            "status": "failed",
        }
        self.payloads = {
            10: _zip(
                {
                    "forecast-run.json": json.dumps(export),
                    "run-summary.json": json.dumps(summary),
                    "model-registry.json": REGISTRY_BYTES,
                    "receipts/cell-a.json": "{}",
                    "receipts/cell-b.json": "{}",
                    "transcripts/cell-a.json": "{}",
                    "artifacts/documents/private.txt": "not inspected",
                }
            ),
            11: _zip(
                {
                    "run-manifest.json": "{}",
                    "forecast-release.json": "{}",
                    "model-registry.json": REGISTRY_BYTES,
                    "artifacts/documents/private.txt": "not inspected",
                }
            ),
            12: _zip({"ledger.sqlite3": ledger, "state.json": "{}"}),
            13: _zip({"ledger.sqlite3": ledger, "state.json": "{}"}),
            14: _zip({"ledger.sqlite3": ledger, "state.json": "{}"}),
            20: _zip({"state.json": "{}"}),
        }

    def get_run(self, repo: str, run_id: int) -> Mapping[str, object]:
        return {
            "id": run_id,
            "path": SOURCE_WORKFLOW,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "head_sha": SOURCE_HEAD_SHA,
            "status": "completed",
            "conclusion": "failure",
            "run_attempt": self.latest_attempt,
            "inputs": None,
        }

    def list_artifacts(self, repo: str, run_id: int) -> Sequence[Mapping[str, object]]:
        values: list[Mapping[str, object]] = [
            self._artifact(10, f"official-forecast-results-{run_id}-1"),
            self._artifact(11, f"locked-forecast-inputs-{run_id}-attempt-1"),
            self._artifact(12, "locked-run-state-openai-cell-a-attempt-1"),
            self._artifact(13, "locked-run-state-openai-cell-b-attempt-1"),
            self._artifact(14, "locked-run-state-openai-cell-c-attempt-1"),
        ]
        if self.latest_attempt == 2:
            values.append(
                self._artifact(20, "locked-run-state-openai-cell-c-attempt-2")
            )
        return values

    @staticmethod
    def _artifact(artifact_id: int, name: str) -> Mapping[str, object]:
        return {
            "id": artifact_id,
            "name": name,
            "size_in_bytes": 100,
            "expired": False,
            "created_at": "2026-09-08T00:00:00Z",
            "expires_at": "2026-09-22T00:00:00Z",
        }

    def download_artifact(self, repo: str, artifact_id: int) -> bytes:
        return self.payloads[artifact_id]

    def list_active_recovery_runs(self, repo: str) -> Sequence[Mapping[str, object]]:
        return self.active_runs

    def dispatch(
        self,
        repo: str,
        workflow: str,
        ref: str,
        inputs: Mapping[str, str],
    ) -> None:
        self.dispatched.append((repo, workflow, ref, inputs))


def test_recovery_plan_reconstructs_frozen_identity_from_artifacts() -> None:
    plan = build_recovery_plan(
        FakeRecoveryClient(),
        repo="owner/bench",
        run_id=RUN_ID,
        ref="main",
        max_parallel=8,
    )

    assert plan.executable
    assert plan.source_head_sha == SOURCE_HEAD_SHA
    assert plan.frozen_identity.release_sha == RELEASE_SHA
    assert plan.frozen_identity.release_sha != plan.source_head_sha
    assert plan.frozen_identity.account == "official-account"
    assert plan.frozen_identity.ceiling_microusd == 250_000_000
    assert plan.frozen_identity.model_registry_sha256 == REGISTRY_SHA
    assert plan.completed_cells == 2
    assert plan.incomplete_cells == 1
    assert len(plan.state_artifacts) == 3
    assert plan.dispatch_inputs == {
        "source_run_id": str(RUN_ID),
        "source_run_attempt": "1",
        "ref": "main",
        "max_parallel": "8",
        "execute": "true",
    }


def test_recovery_plan_falls_back_to_prior_identity_and_keeps_latest_state() -> None:
    plan = build_recovery_plan(
        FakeRecoveryClient(latest_attempt=2),
        repo="owner/bench",
        run_id=RUN_ID,
        ref="main",
        max_parallel=8,
    )

    assert plan.source_run_attempt == 2
    assert plan.identity_source_attempt == 1
    assert plan.resume_sources == ((RUN_ID, 2), (RUN_ID, 1))
    assert plan.state_artifacts[0].name.endswith("attempt-2")
    assert plan.dispatch_inputs["source_run_attempt"] == "2"


def test_recovery_plan_blocks_an_active_exact_dispatch() -> None:
    client = FakeRecoveryClient()
    client.active_runs = (
        {
            "path": RECOVERY_WORKFLOW,
            "display_title": RECOVERY_RUN_TITLE.format(run_id=RUN_ID, run_attempt=1),
        },
    )
    plan = build_recovery_plan(
        client,
        repo="owner/bench",
        run_id=RUN_ID,
        ref="main",
        max_parallel=8,
    )

    assert not plan.executable
    assert "already queued or running" in plan.blocked_reasons[0]


def test_recovery_plan_does_not_block_the_current_planning_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeRecoveryClient()
    client.active_runs = (
        {
            "id": 987,
            "path": RECOVERY_WORKFLOW,
            "display_title": RECOVERY_RUN_TITLE.format(run_id=RUN_ID, run_attempt=1),
        },
    )
    monkeypatch.setenv("GITHUB_RUN_ID", "987")

    plan = build_recovery_plan(
        client,
        repo="owner/bench",
        run_id=RUN_ID,
        ref="main",
        max_parallel=8,
    )

    assert plan.executable


def test_recovery_plan_rejects_changed_registry_bytes() -> None:
    client = FakeRecoveryClient()
    client.payloads[11] = _zip(
        {
            "run-manifest.json": "{}",
            "forecast-release.json": "{}",
            "model-registry.json": "changed",
        }
    )
    with pytest.raises(RecoveryError, match="model-registry bytes"):
        build_recovery_plan(
            client,
            repo="owner/bench",
            run_id=RUN_ID,
            ref="main",
            max_parallel=8,
        )


def test_resume_command_is_read_only_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from legalforecast.cli_commands import run as run_commands

    client = FakeRecoveryClient()
    monkeypatch.setattr(run_commands, "GhRecoveryClient", lambda: client)
    assert (
        run_commands.run_resume(
            argparse.Namespace(
                repo="owner/bench",
                github_run=RUN_ID,
                ref="main",
                max_parallel=8,
                execute=False,
            )
        )
        == 0
    )

    record = json.loads(capsys.readouterr().out)
    assert record["disposition"] == "ready"
    assert record["execute_requested"] is False
    assert record["recovery"]["billing_authority_checked"] is False
    assert client.dispatched == []


def test_resume_execute_dispatches_only_the_protected_workflow(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from legalforecast.cli_commands import run as run_commands

    client = FakeRecoveryClient()
    monkeypatch.setattr(run_commands, "GhRecoveryClient", lambda: client)
    assert (
        run_commands.run_resume(
            argparse.Namespace(
                repo="owner/bench",
                github_run=RUN_ID,
                ref="main",
                max_parallel=8,
                execute=True,
            )
        )
        == 0
    )

    record = json.loads(capsys.readouterr().out)
    assert record["disposition"] == "dispatch_requested"
    assert client.dispatched == [
        (
            "owner/bench",
            RECOVERY_WORKFLOW,
            "main",
            record["recovery"]["dispatch_inputs"],
        )
    ]


def test_resume_execute_reports_blocked_without_dispatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from legalforecast.cli_commands import run as run_commands

    client = FakeRecoveryClient()
    client.active_runs = (
        {
            "path": RECOVERY_WORKFLOW,
            "display_title": RECOVERY_RUN_TITLE.format(run_id=RUN_ID, run_attempt=1),
        },
    )
    monkeypatch.setattr(run_commands, "GhRecoveryClient", lambda: client)
    status = run_commands.run_resume(
        argparse.Namespace(
            repo="owner/bench",
            github_run=RUN_ID,
            ref="main",
            max_parallel=8,
            execute=True,
        )
    )
    assert status == 2
    assert json.loads(capsys.readouterr().out)["disposition"] == "blocked"
    assert client.dispatched == []


def test_gh_client_paginates_artifact_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        payload = json.dumps(
            [
                {"artifacts": [{"id": 1, "name": "one"}]},
                {"artifacts": [{"id": 2, "name": "two"}]},
            ]
        )
        return subprocess.CompletedProcess(command, 0, stdout=payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    artifacts = GhRecoveryClient().list_artifacts("owner/repo", RUN_ID)

    assert [artifact["id"] for artifact in artifacts] == [1, 2]
    assert "--paginate" in calls[0]
    assert "--slurp" in calls[0]


def test_active_scan_includes_runs_waiting_for_environment_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runs = (
            [{"id": 17, "status": "waiting"}] if "status=waiting&" in command[2] else []
        )
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"workflow_runs": runs}), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert list(GhRecoveryClient().list_active_recovery_runs("owner/repo")) == [
        {"id": 17, "status": "waiting"}
    ]


def test_resume_command_help_exposes_the_operator_interface() -> None:
    result = subprocess.run(
        ["legalforecast", "run", "resume", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--github-run" in result.stdout
    assert "--ref" in result.stdout
    assert "--max-parallel" in result.stdout
    assert "--execute" in result.stdout


def test_recovery_counts_bundled_cells_and_missing_worker() -> None:
    client = FakeRecoveryClient()
    original_list = client.list_artifacts
    first, second = "a" * 64, "b" * 64
    client.payloads[12] = _zip(
        {f"{first}.zip": client.payloads[12], f"{second}.zip": client.payloads[13]}
    )

    def artifacts(repo: str, run_id: int) -> Sequence[Mapping[str, object]]:
        return [
            *original_list(repo, run_id)[:2],
            client._artifact(12, f"restored-forecast-state-{run_id}-attempt-1"),
        ]

    client.list_artifacts = artifacts  # type: ignore[method-assign]
    with ZipFile(io.BytesIO(client.payloads[10])) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    summary = json.loads(members["run-summary.json"])
    summary.update(expected_cell_count=3, state_artifact_count=2)
    members["run-summary.json"] = json.dumps(summary).encode()
    client.payloads[10] = _zip(members)
    plan = build_recovery_plan(
        client,
        repo="johnhughes3/LegalForecastBench",
        run_id=RUN_ID,
        ref="main",
        max_parallel=8,
    )
    assert plan.incomplete_cells == 1
    assert plan.blocked_reasons == ()

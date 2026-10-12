"""Provider-free exact workflow handoff tests for native completion."""

from __future__ import annotations

import io
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest
from legalforecast.runner import completion
from legalforecast.runner.recovery import (
    ArtifactCensus,
    ArtifactLocator,
    FrozenRunIdentity,
    RecoveryPlan,
)
from legalforecast.runner.recovery_client import dispatched_workflow_record

REPO = "owner/bench"
LABELS = "s3://bucket/labels-release.json"


def zipped(records: Mapping[str, object]) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, value in records.items():
            archive.writestr(name, json.dumps(value))
    return stream.getvalue()


def plan(run_id: int, incomplete: int = 0) -> RecoveryPlan:
    artifact = ArtifactLocator(1, "fixture", 10, False, None, None)
    frozen = FrozenRunIdentity(
        "a" * 40,
        "s3://bucket/manifest",
        "s3://bucket/forecast",
        "s3://bucket/artifacts",
        "model_registries/frozen.json",
        "openai:model",
        "b" * 64,
        "c" * 64,
        1,
        "account",
        100_000_000,
        90,
    )
    return RecoveryPlan(
        REPO,
        "main",
        run_id,
        1,
        1,
        "a" * 40,
        "success",
        artifact,
        artifact,
        (),
        ((run_id, 1),),
        frozen,
        ArtifactCensus(0, 0, 2 - incomplete, 0, 2),
        2 - incomplete,
        incomplete,
        () if incomplete else ("source run has no incomplete cells",),
        {"source_run_id": str(run_id), "source_run_attempt": "1", "execute": "true"},
    )


class Client:
    def __init__(self, *, recovery: bool = False) -> None:
        self.recovery = recovery
        self.plans = {10: plan(10, 1 if recovery else 0), 30: plan(30)}
        self.dispatches: list[tuple[str, Mapping[str, str]]] = []
        self.watches: list[int] = []
        self.unknown = False
        self.unsafe = False
        self.cross_source = False
        self.active = False
        self.payloads = {
            1: zipped(
                {
                    "lfb-protected-recovery-result.json": {
                        "source_run_id": 10,
                        "source_run_attempt": 1,
                        "dispatch_safe": True,
                        "cap_microusd": 100_000_000,
                        "projected_committed_microusd": 50_000_000,
                        "blocked_reasons": [],
                    }
                }
            ),
            2: zipped(
                {
                    "lfb-child-dispatch.json": {
                        **dispatched_workflow_record(
                            REPO,
                            "run-benchmark.yaml",
                            "main",
                            f"https://github.com/{REPO}/actions/runs/30",
                        ),
                        "source_run_id": 10,
                        "source_run_attempt": 1,
                        "recovery_run_id": 20,
                        "recovery_run_attempt": 1,
                    }
                }
            ),
        }

    def watch_run(self, repo: str, run_id: int) -> Mapping[str, object]:
        self.watches.append(run_id)
        return self.get_run(repo, run_id)

    def get_run(self, repo: str, run_id: int) -> Mapping[str, object]:
        workflow = (
            completion.RECOVERY_WORKFLOW
            if run_id == 20
            else completion.SCORE_WORKFLOW
            if run_id == 40
            else completion.SOURCE_WORKFLOW
        )
        return {
            "id": run_id,
            "run_attempt": 1,
            "path": workflow,
            "event": "workflow_dispatch",
            "head_branch": "main",
            "status": "waiting" if self.active else "completed",
            "conclusion": "success",
        }

    def list_active_recovery_runs(self, repo: str) -> Sequence[Mapping[str, object]]:
        return []

    def list_artifacts(self, repo: str, run_id: int) -> Sequence[Mapping[str, object]]:
        if run_id == 20:
            return [
                {"id": 1, "name": "protected-recovery-result-20-1", "expired": False},
                {"id": 2, "name": "recovery-child-dispatch-20-1", "expired": False},
            ]
        return [
            {"id": 3, "name": "protected-labels-fan-in-cycle-1-40", "expired": False}
        ]

    def download_artifact(self, repo: str, artifact_id: int) -> bytes:
        if artifact_id == 1 and self.unsafe:
            return zipped(
                {
                    "lfb-protected-recovery-result.json": {
                        "source_run_id": 10,
                        "source_run_attempt": 1,
                        "dispatch_safe": False,
                        "cap_microusd": 100_000_000,
                        "projected_committed_microusd": 50_000_000,
                        "blocked_reasons": ["uncertain charge"],
                    }
                }
            )
        if artifact_id == 2 and self.cross_source:
            return zipped({"lfb-child-dispatch.json": {"source_run_id": 999}})
        if artifact_id in self.payloads:
            return self.payloads[artifact_id]
        forecast_id = 30 if self.recovery else 10
        return zipped(
            {
                "lfb-site-export.json": {
                    "source": {
                        "run_identity_sha256": "c" * 64,
                        "model_registry_sha256": "b" * 64,
                    },
                    "results": [
                        {"model_id": "openai:model", "case_count": 2, "unit_count": 3}
                    ],
                },
                "lfb-report/scoring-runtime.json": {
                    "forecast_run_id": str(forecast_id),
                    "forecast_run_attempt": "1",
                    "forecast_revision": "a" * 40,
                },
            }
        )

    def dispatch(
        self, repo: str, workflow: str, ref: str, inputs: Mapping[str, str]
    ) -> Mapping[str, object]:
        self.dispatches.append((workflow, dict(inputs)))
        run_id = 20 if workflow == completion.RECOVERY_WORKFLOW else 40
        return dispatched_workflow_record(
            repo,
            workflow,
            ref,
            "" if self.unknown else f"https://github.com/{repo}/actions/runs/{run_id}",
        )


def execute(
    client: Client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    max_recoveries: int = 1,
) -> Mapping[str, object]:
    monkeypatch.setattr(
        completion,
        "build_recovery_plan",
        lambda _client, **kwargs: client.plans[kwargs["run_id"]],
    )
    return completion.complete_native_run(
        client,
        repo=REPO,
        run_id=10,
        cycle_id="cycle-1",
        labels_release_uri=LABELS,
        output_dir=tmp_path / "scores",
        publish=True,
        max_recoveries=max_recoveries,
    )


def test_complete_forecast_dispatches_only_scoring_and_downloads_exact_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Client()
    result = execute(client, tmp_path, monkeypatch)
    assert result["status"] == "scored" and result["case_count"] == 2
    assert result["website_integrated"] is False and result["paper_integrated"] is False
    assert client.watches == [10, 40]
    assert len(client.dispatches) == 1
    inputs = client.dispatches[0][1]
    assert inputs["labels_release_uri"] == LABELS and inputs["forecast_run_id"] == "10"
    assert inputs["release_sha"] == "a" * 40 and inputs["publish"] == "true"
    assert (tmp_path / "scores/lfb-site-export.json").is_file()


def test_recovery_follows_exact_safe_child_and_keeps_labels_out_of_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Client(recovery=True)
    result = execute(client, tmp_path, monkeypatch)
    assert result["status"] == "scored" and result["forecast_run_id"] == 30
    assert client.watches == [10, 20, 30, 40]
    assert LABELS not in json.dumps(client.dispatches[0])
    assert "labels_release_uri" not in client.dispatches[0][1]
    assert client.dispatches[1][1]["forecast_run_id"] == "30"


@pytest.mark.parametrize(
    "kind",
    [
        "unknown",
        "unsafe",
        "cross_source",
        "limit",
        "summary",
        "active",
        "identity_drift",
    ],
)
def test_completion_stops_without_guessing_or_unbounded_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    client = Client(recovery=True)
    if kind in {"unknown", "unsafe", "cross_source", "active"}:
        setattr(client, kind, True)
    if kind == "summary":
        client.plans[10] = replace(
            client.plans[10],
            frozen_identity=replace(
                client.plans[10].frozen_identity,
                jev_summaries_uri="s3://bucket/summaries",
            ),
        )
    if kind == "identity_drift":
        client.plans[30] = replace(
            client.plans[30],
            frozen_identity=replace(
                client.plans[30].frozen_identity, ceiling_microusd=200_000_000
            ),
        )
    result = execute(
        client, tmp_path, monkeypatch, max_recoveries=0 if kind == "limit" else 1
    )
    assert result["status"] in {"blocked", "dispatched_unresolved"}
    assert not (tmp_path / "scores").exists()
    assert all(
        workflow != completion.SCORE_WORKFLOW for workflow, _ in client.dispatches
    )
    assert len(client.dispatches) <= 1


@pytest.mark.parametrize("terminal", [True, False])
def test_native_watcher_reads_actual_run_after_watch_auth_failure(
    monkeypatch: pytest.MonkeyPatch, terminal: bool
) -> None:
    import subprocess

    from legalforecast.runner.completion_client import GhCompletionClient

    reads = 0

    class WatchClient(GhCompletionClient):
        def get_run(self, repo: str, run_id: int) -> Mapping[str, object]:
            nonlocal reads
            reads += 1
            return {"status": "completed" if terminal and reads > 1 else "waiting"}

    calls: list[list[str]] = []

    def fail_watch(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(subprocess, "run", fail_watch)
    actual = WatchClient().watch_run(REPO, 10)
    assert actual["status"] == ("completed" if terminal else "waiting")
    expected = ["gh", "run", "watch", "10", "--repo", REPO, "--exit-status"]
    assert calls == [expected] * (1 if terminal else 3)


def test_existing_output_is_refused_before_workflow_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "scores").mkdir()
    client = Client()
    with pytest.raises(completion.RecoveryError, match="new output directory"):
        execute(client, tmp_path, monkeypatch)
    assert client.watches == [] and client.dispatches == []


def test_complete_cli_has_required_scoring_and_bounded_recovery_help() -> None:
    import argparse

    from legalforecast.cli_commands.run import register

    parser = argparse.ArgumentParser()
    register(parser.add_subparsers())
    args = parser.parse_args(
        [
            "run",
            "complete",
            "--github-run",
            "10",
            "--cycle-id",
            "cycle-1",
            "--labels-release-uri",
            LABELS,
            "--output-dir",
            "out",
        ]
    )
    assert args.max_recoveries == 1 and args.max_parallel == 8
    assert args.publish is False


def test_unknown_scoring_identity_preserves_dispatch_without_redispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Client()
    client.unknown = True
    result = execute(client, tmp_path, monkeypatch)
    assert result["status"] == "dispatched_unresolved"
    assert len(client.dispatches) == 1
    assert result["scoring_dispatch"] == {
        **dispatched_workflow_record(REPO, completion.SCORE_WORKFLOW, "main", "")
    }
    assert not (tmp_path / "scores").exists()


def test_native_watcher_restarts_after_expiry_but_never_widens_denied_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from legalforecast.runner.completion_client import GhCompletionClient

    reads = 0
    watches = 0

    class WatchClient(GhCompletionClient):
        def get_run(self, repo: str, run_id: int) -> Mapping[str, object]:
            nonlocal reads
            reads += 1
            if reads == 3:
                raise completion.RecoveryError("GitHub read denied (403)")
            return {"status": "in_progress"}

    def expired_watch(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        nonlocal watches
        watches += 1
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(subprocess, "run", expired_watch)
    with pytest.raises(completion.RecoveryError, match="403"):
        WatchClient().watch_run(REPO, 10)
    assert watches == 2
    assert reads == 3


@pytest.mark.parametrize("member", ["source", "results"])
def test_malformed_scored_metadata_stops_without_creating_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    client = Client()
    source: object = (
        []
        if member == "source"
        else {
            "run_identity_sha256": "c" * 64,
            "model_registry_sha256": "b" * 64,
        }
    )
    results: object = (
        [None]
        if member == "results"
        else [{"model_id": "openai:model", "case_count": 2, "unit_count": 3}]
    )
    client.payloads[3] = zipped(
        {
            "lfb-site-export.json": {
                "source": source,
                "results": results,
            }
        }
    )
    result = execute(client, tmp_path, monkeypatch)
    assert result["status"] == "blocked"
    assert not (tmp_path / "scores").exists()


def test_three_no_progress_recoveries_stop_before_fourth_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Client(recovery=True)
    child_id = 29

    def incomplete_plan(*args: object, **kwargs: object) -> RecoveryPlan:
        return plan(int(str(kwargs["run_id"])), 1)

    def exact_child(*args: object, **kwargs: object) -> int:
        nonlocal child_id
        child_id += 1
        return child_id

    monkeypatch.setattr(completion, "build_recovery_plan", incomplete_plan)
    monkeypatch.setattr(completion, "_protected_child", exact_child)
    result = completion.complete_native_run(
        client,
        repo=REPO,
        run_id=10,
        cycle_id="cycle-1",
        labels_release_uri=LABELS,
        output_dir=tmp_path / "scores",
        max_recoveries=8,
    )
    assert result["status"] == "blocked"
    assert "three recoveries made no progress" in str(result["reason"])
    assert len(client.dispatches) == 3
    assert all(
        workflow == completion.RECOVERY_WORKFLOW for workflow, _ in client.dispatches
    )

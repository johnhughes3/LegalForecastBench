"""End-to-end wiring of the containerized tools-on lane into ``multiharness run``.

These runs are *harness-vs-API* measurements, not official benchmark numbers.
They score the same corpus through a different treatment -- an agentic CLI with
its own tools live -- and the lane keeps its own identity all the way into the
score row: ``solver_id`` and the scored ``model_id`` both carry the
``-container-tools-on`` adapter id, and every receipt's ``treatment_id`` names
the adapter and version beside the model key.

No provider is contacted.  ``run_container_harness`` is replaced with a fake
that writes the envelope the manifest says to read, so what is proven here is
the wiring -- selection, prompt authentication, release evidence, projection,
scoring -- rather than any model's behavior.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast._json_io import write_jsonl_objects
from legalforecast.cli import main as legalforecast_main
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.harness_lane.adapter import ContainerCliAdapter
from legalforecast.multiharness.harness_lane.harnesses import (
    identity_for_registry_name,
)
from legalforecast.multiharness.harness_lane.results_package import (
    HarnessLaneResultsError,
    build_harness_lane_results_package,
)
from legalforecast.multiharness.harness_lane.sentinel import (
    SENTINEL_RELATIVE_PATH,
    SentinelError,
    SentinelVerdict,
    check_workspace_sentinel,
    materialize_workspace_sentinel,
    mint_workspace_sentinel,
    probe_workspace_tool_use,
)
from legalforecast.multiharness.harness_lane.tool_accounting import (
    ToolAccountingError,
    harness_tool_use,
)
from legalforecast.multiharness.local_cli_manifest import (
    LocalCliAdapterManifest,
)
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.multiharness.validation import validate_public_record
from legalforecast.release.synthetic import issue_synthetic_release
from tests.test_multiharness_scoped_runs import projected_lab_layout
from tests.test_multiharness_task_loaders import (
    _model_packet,  # pyright: ignore[reportPrivateUsage]
)

CONTAINER_MANIFEST = Path("examples/adapters/claude-code-native")
LAB_MANIFEST = Path("examples/adapters/claude-code-lab-native")
LFB_ADAPTER = "claude-code-container-tools-on"
PROVIDER_HOST = "api.anthropic.com"


def _run_multiharness(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="legalforecast")
    add_multiharness_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(argv)
    return int(args.handler(args))


def run_legalforecast(argv: list[str]) -> int:
    """Drive the top-level CLI, so the scoring module reaches it through here.

    Keeping the ``legalforecast.cli`` entry point in one test module is not
    style: the architecture baseline tracks which test files reach the CLI
    facade and ratchets that set downward, so a second importer is a
    regression even when the call is identical.
    """

    return int(legalforecast_main(argv))


def _lane_manifest_record() -> dict[str, Any]:
    return json.loads(
        (CONTAINER_MANIFEST / "local-cli-adapter-manifest.json").read_text(
            encoding="utf-8"
        )
    )


def _stream_json(answer: str, tools: tuple[str, ...]) -> str:
    events: list[dict[str, Any]] = [
        {"type": "system", "subtype": "init", "tools": list(tools)}
    ]
    events.extend(
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": t}]}}
        for t in tools
    )
    events.append(
        {"type": "result", "subtype": "success", "is_error": False, "result": answer}
    )
    return "\n".join(json.dumps(event) for event in events) + "\n"


@pytest.fixture
def fake_container(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Replace the container runtime with a recorder that writes real stdout."""

    state: dict[str, Any] = {
        "answer": "",
        "tools": ("Bash", "Read"),
        "specs": [],
        # Relative path -> bytes the "harness" leaves in its workspace. A LAB
        # row is scored from a file the harness wrote, not from its transcript.
        "workspace_files": {},
    }

    def runner(
        spec: ContainerHarnessSpec, *, backend: str = "docker"
    ) -> ContainerHarnessResult:
        state["specs"].append(spec)
        for relative, payload in cast(
            dict[str, bytes], state["workspace_files"]
        ).items():
            target = spec.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout = spec.log_root / "stdout.jsonl"
        stdout.write_text(
            _stream_json(str(state["answer"]), tuple(state["tools"])),
            encoding="utf-8",
        )
        stderr = spec.log_root / "stderr.log"
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=1.25,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=(PROVIDER_HOST,),
            refused=(),
            allowlist={"hosts": [PROVIDER_HOST], "ports": [443]},
        )

    monkeypatch.setattr(
        "legalforecast.multiharness.harness_lane.adapter.run_container_harness",
        runner,
    )
    yield state


def _release_task_index(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    release_root = tmp_path / "release"
    issue_synthetic_release(release_root)
    solver_root = tmp_path / "solver-inputs"
    index = ReleaseLfbTaskLoader().load_forecast_release(
        release_root / "forecast-release.json",
        artifact_root=release_root,
        solver_input_root=solver_root,
    )
    index_path = tmp_path / "task-index.json"
    index_path.write_text(
        json.dumps(index.to_record(), sort_keys=True), encoding="utf-8"
    )
    scored = next(task for task in index.tasks if task.metadata["should_score"])
    metadata = dict(scored.metadata) | {"task_id": scored.task_id}
    metadata["release_prompt"] = (
        release_root / "prompts" / f"{scored.metadata['unit_id']}.txt"
    ).read_text(encoding="utf-8")
    return index_path, solver_root, metadata


def _label_record(unit_id: str, *, dismissed: bool) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "unit_resolution": (
            "fully_dismissed" if dismissed else "survives_in_material_respect"
        ),
        "fully_dismissed": dismissed,
        "amendment_class": (
            "dismissed_without_express_amendment_opportunity"
            if dismissed
            else "not_fully_dismissed"
        ),
        "ambiguous": False,
        "label_confidence": 1.0,
        "supporting_citations": [{"document_id": "doc-001"}],
        "first_written_disposition_id": "doc-001",
        "first_written_disposition_date": "2024-01-02",
    }


def test_container_lane_lfb_run_produces_scoreable_artifacts(
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    index_path, solver_root, task = _release_task_index(tmp_path)
    unit_id = str(task["unit_id"])
    fake_container["answer"] = json.dumps(
        {
            "case_assessment": "Container-lane fixture answer.",
            "predictions": [{"unit_id": unit_id, "probability_fully_dismissed": 0.25}],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    output_dir = tmp_path / "run"

    assert (
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-index",
                str(index_path),
                "--solver-input-root",
                str(solver_root),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(CONTAINER_MANIFEST / "local-cli-adapter-manifest.json"),
                "--auth-profile",
                "fixture-none",
                "--allow-host",
                PROVIDER_HOST,
                "--model-key",
                "claude:fixture",
                "--task-id",
                str(task["task_id"]),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    # The container was handed the exact private prompt bytes, not task
    # metadata, and could reach nothing but the provider host.
    spec = fake_container["specs"][0]
    assert spec.allow_hosts == (PROVIDER_HOST,)
    assert str(task["release_prompt"]) in spec.harness_argv
    assert (
        spec.image
        == json.loads(
            (CONTAINER_MANIFEST / "local-cli-adapter-manifest.json").read_text(
                encoding="utf-8"
            )
        )["executable"]["container_image_digest"]
    )
    # ...and the prompt itself stays out of every published run artifact.
    for name in ("row-results.jsonl", "canonical-runs.jsonl"):
        assert str(task["release_prompt"]) not in (output_dir / name).read_text(
            encoding="utf-8"
        )

    lfb_runs = output_dir / "lfb" / "runs.jsonl"
    records = [
        json.loads(line) for line in lfb_runs.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    record = records[0]
    assert record["solver_id"] == f"{LFB_ADAPTER}:claude:fixture"
    assert record["model_id"] == f"{LFB_ADAPTER}:claude:fixture"
    assert record["execution_backend"] == "container_cli_tools_on"
    assert "raw_output" not in record
    assert len(record["tool_call_logs"]) == 2
    # Official scoring stays fail-closed against this lane without a new gate:
    # the locked path in run_record_scoring authenticates a public run receipt
    # (schema_version, run_identity_sha256, model_registry_sha256) bound to a
    # frozen official model registry, and a harness-lane row mints none of it.
    assert not {
        "schema_version",
        "run_identity_sha256",
        "model_registry_sha256",
    } & set(record)

    receipts = [
        json.loads(line)
        for line in (output_dir / "release-harness-receipts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert receipts[0]["tools"]["allowed"] == ["Bash", "Read"]
    assert receipts[0]["tools"]["policy"] == "native_cli_builtins:distinct_tool_names"
    assert receipts[0]["treatment_id"].startswith(f"native:{LFB_ADAPTER}:")

    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        "\n".join(
            json.dumps(_label_record(name, dismissed=name != unit_id))
            for name in ("unit-001", "unit-002")
        )
        + "\n",
        encoding="utf-8",
    )
    scores = tmp_path / "scores.json"
    assert (
        legalforecast_main(
            [
                "score",
                "--runs",
                str(lfb_runs),
                "--labels",
                str(labels),
                "--output",
                str(scores),
            ]
        )
        == 0
    )
    summaries = json.loads(scores.read_text(encoding="utf-8"))["summaries"]
    assert len(summaries) == 1
    assert summaries[0]["model_id"] == f"{LFB_ADAPTER}:claude:fixture"


def test_container_lane_runs_a_projected_harvey_lab_selection(
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    result, index = projected_lab_layout(tmp_path)
    task = index.tasks[0]
    fake_container["answer"] = "A drafted deliverable for the projected LAB task."
    output_dir = tmp_path / "run"

    assert (
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-source",
                "harvey-lab",
                "--projected-root",
                str(result.solver_root),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(LAB_MANIFEST / "local-cli-adapter-manifest.json"),
                "--auth-profile",
                "fixture-none",
                "--allow-host",
                PROVIDER_HOST,
                "--model-key",
                "claude:fixture",
                "--task-id",
                task.task_id,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    rows = [
        json.loads(line)
        for line in (output_dir / "lab" / "task-results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["task_id"] == task.task_id
    assert rows[0]["result"]["status"] == "succeeded"
    summary = rows[0]["result"]["public_summary"]
    assert summary["allowed_tools"] == ["Bash", "Read"]
    assert summary["native_tools_enabled"] is True
    assert summary["server_side_web_tools_disabled"] is True
    # LAB tasks score through lab_native, never through the LFB Brier scorer.
    assert not (output_dir / "lfb" / "runs.jsonl").exists()

    # The harness saw the task's own documents, verified against the projection.
    staged = sorted(
        path.name for path in fake_container["specs"][0].workspace.iterdir()
    )
    assert "instructions.txt" in staged


def test_lfb_packet_task_source_runs_but_yields_no_score_rows(
    tmp_path: Path,
    fake_container: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The packet source runs, says so, and cannot score -- structurally.

    ``LfbTaskLoader`` packets carry no ``release_schema_version``, so
    ``release_harness`` projects no LFB record for them -- exactly as for every
    other command adapter today.  This is not a wiring gap to close: a packet
    row has no release identity and no per-unit packet/prompt commitment, so
    the only ways to make it score would be to fabricate that identity or to
    open a second, unauthenticated door into ``lfb/runs.jsonl``.  The scoring
    route is ``--forecast-release``/``--artifact-root`` on the same task
    source, pinned by ``test_lfb_release_task_source_scores_end_to_end`` in
    ``test_multiharness_harness_lane_scoring``, and the run says so on stderr
    before it starts rather than leaving the absence to be discovered.
    """

    packets = tmp_path / "packets.jsonl"
    write_jsonl_objects(packets, (_model_packet().to_record(),))
    fake_container["answer"] = json.dumps({"predictions": []}, separators=(",", ":"))
    output_dir = tmp_path / "run"

    assert (
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-source",
                "lfb",
                "--packets",
                str(packets),
                "--solver-input-root",
                str(tmp_path / "solver-inputs"),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(CONTAINER_MANIFEST / "local-cli-adapter-manifest.json"),
                "--auth-profile",
                "fixture-none",
                "--allow-host",
                PROVIDER_HOST,
                "--model-key",
                "claude:fixture",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert (output_dir / "row-results.jsonl").is_file()
    assert not (output_dir / "lfb" / "runs.jsonl").exists()
    # ...and the operator was told that before the run, not left to infer it
    # from the file that is missing afterwards.
    warning = capsys.readouterr().err
    assert "--packets is a plumbing input" in warning
    assert "no lfb/runs.jsonl" in warning
    assert "--forecast-release" in warning


def test_registry_adapter_without_a_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="needs --local-cli-manifest"):
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-index",
                str(tmp_path / "missing.json"),
                "--adapter",
                LFB_ADAPTER,
                "--model-key",
                "claude:fixture",
                "--output-dir",
                str(tmp_path / "run"),
            ]
        )


def test_run_refuses_both_a_task_index_and_a_task_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one of --task-index"):
        _run_multiharness(
            [
                "multiharness",
                "run",
                "--task-index",
                str(tmp_path / "index.json"),
                "--task-source",
                "lfb",
                "--packets",
                str(tmp_path / "packets.jsonl"),
                "--adapter",
                LFB_ADAPTER,
                "--local-cli-manifest",
                str(CONTAINER_MANIFEST / "local-cli-adapter-manifest.json"),
                "--model-key",
                "claude:fixture",
                "--output-dir",
                str(tmp_path / "run"),
            ]
        )


def _lines(*events: dict[str, Any]) -> str:
    return "\n".join(json.dumps(event) for event in events) + "\n"


# One minimal but *complete* transcript per harness, in that harness's own
# envelope. Each parser refuses a stream with no terminal event, so a truncated
# fixture would prove only that the fallback path returns "unreported".
_TOOL_TRANSCRIPTS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "claude": (
        _lines(
            {"type": "system", "subtype": "init", "tools": ["Read"]},
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "Read"}]},
            },
            {"type": "result", "subtype": "success", "is_error": False, "result": "A"},
        ),
        ("Read",),
        "distinct_tool_names",
    ),
    "codex": (
        _lines(
            {"type": "thread.started", "thread_id": "t"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"id": "i1", "type": "file_change"}},
            {
                "type": "item.completed",
                "item": {"id": "i2", "type": "agent_message", "text": "A"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        ),
        ("file_change",),
        "distinct_tool_names",
    ),
    "grok": (
        _lines(
            {
                "type": "system",
                "subtype": "init",
                "tools": ["read_file"],
                "model": "grok-4.6",
            },
            {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "read_file"}]},
            },
            {"type": "result", "subtype": "success", "is_error": False, "result": "A"},
        ),
        ("read_file",),
        "distinct_tool_names",
    ),
    "kimi": (
        _lines(
            {"role": "meta", "type": "system.version", "version": "0.36.0"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "Read"}}]},
            {"role": "assistant", "content": "A"},
        ),
        ("Read",),
        "distinct_tool_names",
    ),
    # Antigravity's JSON envelope names no tools at all, so the lane reports
    # "unreported" rather than claiming the harness used none.
    "agy": (json.dumps({"status": "SUCCESS", "response": "A"}), (), "unreported"),
}


@pytest.mark.parametrize("basename", sorted(_TOOL_TRANSCRIPTS))
def test_every_harness_tool_reader_is_wired_to_its_own_envelope(
    basename: str,
) -> None:
    stdout, expected, reporting = _TOOL_TRANSCRIPTS[basename]
    observed = harness_tool_use(basename, stdout + "\n")

    assert observed.tools == expected
    assert observed.reporting == reporting
    assert observed.call_count == len(expected)
    assert observed.policy == f"native_cli_builtins:{reporting}"


def test_an_unknown_harness_basename_is_refused_rather_than_counted_zero() -> None:
    with pytest.raises(ToolAccountingError, match="no tool-use reader"):
        harness_tool_use("unknown-cli", "{}\n")


# --- Uploading the full results ------------------------------------------------
#
# The lane's evidence is the harness's own transcripts, and they are exactly what
# cannot be published: they carry the operator's container environment and, on a
# LAB row, the staged case documents.  So the run splits -- private archive to
# S3, constructed summary to this public repository -- and these tests hold the
# split to the only thing that matters about it: nothing from a host reaches the
# public side.  The markers below are synthetic, never taken from a real
# environment.

_HOST_HOME = "/home/example-operator"
_HOST_TOKEN = "sk-ant-oat01-EXAMPLEEXAMPLEEXAMPLE"
_HOST_SESSION = "session-id-0123456789abcdef"
_HOST_SOCKET = "/run/user/4242/docker.sock"
_PLANTED_MARKERS = (_HOST_HOME, _HOST_TOKEN, _HOST_SESSION, _HOST_SOCKET)


def _lane_public_summary(*, exit_code: int, duration: float) -> dict[str, Any]:
    """A public_summary shaped exactly as ContainerCliAdapter emits one."""

    return {
        "adapter_id": LFB_ADAPTER,
        "adapter_version": "1.0.0",
        "allowed_tools": ["Bash", "Read"],
        "auth_mode": "contributor-subscription",
        "container_image_digest": (
            "lfb/claude-code@sha256:"
            "1111111111111111111111111111111111111111111111111111111111111111"
        ),
        "container_image_id": (
            "sha256:2222222222222222222222222222222222222222222222222222222222222222"
        ),
        "duration_seconds": duration,
        "egress_allowed_hosts": [PROVIDER_HOST],
        "egress_allowlist": {
            "hosts": [PROVIDER_HOST],
            "ports": [443],
            "subdomains": [],
        },
        "egress_refused": [
            {"host": "example.com", "port": 443, "reason": "host_not_allowed"}
        ],
        "executable": "claude",
        "execution_backend": "container_cli_tools_on",
        "exit_code": exit_code,
        "failure_class": None if exit_code == 0 else "crash",
        "harness": "claude-code",
        "harness_track": "native",
        "model_key": "claude-opus-4-6",
        "native_tools_enabled": True,
        "server_side_web_tools_disabled": True,
        "timed_out": False,
        "tool_call_count": 2,
        "tool_policy": "native_cli_builtins:distinct_tool_names",
        "tool_use_reporting": "distinct_tool_names",
    }


def _fixture_run_directory(root: Path) -> Path:
    """Write a run directory carrying host markers everywhere they really land."""

    run_dir = root / "run-output"
    (run_dir / "lfb").mkdir(parents=True)
    (run_dir / "rows" / "row-0" / "container-logs").mkdir(parents=True)
    (run_dir / "rows" / "row-0" / "private-logs").mkdir(parents=True)

    (run_dir / "run-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.run_manifest.v1",
                "run_id": "harness-lane-fixture",
                "selection_sha256": "aa" * 32,
                "run_config_sha256": "bb" * 32,
                "request_ids": ["request-0", "request-1"],
                "result_ids": ["result-0", "result-1"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_jsonl_objects(
        run_dir / "canonical-runs.jsonl",
        [
            {
                "schema_version": "legalforecast.multiharness.run_result.v1",
                "result_id": f"result-{index}",
                "request_id": f"request-{index}",
                "status": "succeeded" if index == 0 else "failed",
                "result_sha256": f"{index}" * 64,
                "artifacts": [],
                "public_summary": _lane_public_summary(
                    exit_code=0 if index == 0 else 1, duration=1.5
                ),
            }
            for index in (0, 1)
        ],
    )
    write_jsonl_objects(
        run_dir / "release-harness-receipts.jsonl", [{"receipt": "one"}]
    )
    write_jsonl_objects(run_dir / "lfb" / "runs.jsonl", [{"run": 0}, {"run": 1}])
    # The real leak vector: MultiHarnessRunRow.to_record() writes the workspace
    # as an absolute host path. It belongs in the archive and nowhere else.
    write_jsonl_objects(
        run_dir / "row-results.jsonl",
        [{"row_id": "row-0", "workspace": f"{_HOST_HOME}/lfb/run/rows/row-0"}],
    )
    (run_dir / "rows" / "row-0" / "container-logs" / "stdout.log").write_text(
        f"HOME={_HOST_HOME}\nDOCKER_HOST=unix://{_HOST_SOCKET}\n"
        f"token={_HOST_TOKEN}\nsession={_HOST_SESSION}\n",
        encoding="utf-8",
    )
    (
        run_dir / "rows" / "row-0" / "private-logs" / "harness-lane-transcript.json"
    ).write_text(json.dumps({"response_sha256": "cc" * 32}) + "\n", encoding="utf-8")
    return run_dir


def test_the_public_summary_carries_the_fence_evidence_and_no_host_bytes(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run_directory(tmp_path)

    package = build_harness_lane_results_package(
        run_dir=run_dir, output_dir=tmp_path / "package"
    )

    summary_bytes = package.summary_path.read_bytes()
    for marker in _PLANTED_MARKERS:
        assert marker.encode("utf-8") not in summary_bytes, marker
    summary = json.loads(summary_bytes)
    assert summary["schema_version"] == "legalforecast-harness-lane-results-v1"
    assert summary["run_id"] == "harness-lane-fixture"
    assert summary["result_count"] == 2
    assert summary["status_counts"] == {"failed": 1, "succeeded": 1}
    assert summary["release_receipt_count"] == 1
    assert summary["lfb_row_count"] == 2
    assert summary["package_sha256"] == package.package_sha256

    (harness,) = summary["harnesses"]
    # What makes the run believable: which image, tools on, provider web tools
    # off, what it reached, and what the fence refused.
    assert harness["container_image_digest"].endswith(":" + "11" * 32)
    assert harness["native_tools_enabled"] is True
    assert harness["server_side_web_tools_disabled"] is True
    assert harness["egress_allowed_hosts"] == [PROVIDER_HOST]
    assert harness["egress_refused"] == [
        {"host": "example.com", "port": 443, "reason": "host_not_allowed"}
    ]
    assert harness["tools_observed"] == ["Bash", "Read"]
    assert harness["row_count"] == 2
    assert harness["nonzero_exit_count"] == 1
    assert harness["failure_class_counts"] == {"crash": 1, "none": 1}


def test_the_private_archive_keeps_the_bytes_the_summary_must_not_publish(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run_directory(tmp_path)

    package = build_harness_lane_results_package(
        run_dir=run_dir, output_dir=tmp_path / "package"
    )

    with zipfile.ZipFile(package.package_path) as archive:
        names = set(archive.namelist())
        transcript = archive.read("run/rows/row-0/container-logs/stdout.log")
        rows = archive.read("run/row-results.jsonl")
    assert "run/run-manifest.json" in names
    assert "run/lfb/runs.jsonl" in names
    # "Full results" means full: the transcripts and the absolute workspace path
    # travel to the private bucket rather than being dropped.
    for marker in (_HOST_HOME, _HOST_TOKEN, _HOST_SESSION, _HOST_SOCKET):
        assert marker.encode("utf-8") in transcript
    assert _HOST_HOME.encode("utf-8") in rows

    assert package.prefix == f"cycle-1/harness-lane/{package.package_sha256}"
    assert package.asset_name == (
        f"harness-lane-results-{package.package_sha256}.zip.age"
    )
    assert package.package_size_bytes == package.package_path.stat().st_size


def test_two_builds_of_one_run_directory_agree_on_the_pinned_digest(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run_directory(tmp_path)

    first = build_harness_lane_results_package(
        run_dir=run_dir, output_dir=tmp_path / "first"
    )
    second = build_harness_lane_results_package(
        run_dir=run_dir, output_dir=tmp_path / "second"
    )

    # The dispatch pins this digest; a build that moved it would make the pin
    # verifiable only by whoever built it.
    assert first.package_sha256 == second.package_sha256
    assert first.summary_sha256 == second.summary_sha256


def test_a_host_path_reaching_a_public_summary_field_is_refused(
    tmp_path: Path,
) -> None:
    run_dir = _fixture_run_directory(tmp_path)
    rows = [
        json.loads(line)
        for line in (run_dir / "canonical-runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    # Both rows, so the identity-agreement check passes and the host-path
    # guard is the thing under test.
    for row in rows:
        row["public_summary"]["executable"] = f"{_HOST_HOME}/.local/bin/claude"
    (run_dir / "canonical-runs.jsonl").unlink()
    write_jsonl_objects(run_dir / "canonical-runs.jsonl", rows)

    with pytest.raises(HarnessLaneResultsError, match="host filesystem path"):
        build_harness_lane_results_package(
            run_dir=run_dir, output_dir=tmp_path / "package"
        )


# --- Workspace sentinel: behavioural proof that a tool was used -------------
#
# Every assertion below is about *evidence*, never about a score.  The sentinel
# runs as its own probe container precisely so a scored row's prompt bytes and
# projected answer stay untouched, and nothing here reaches a number.

_SENTINEL_TOKEN = "0f" * 16
_SentinelRunner = Callable[[ContainerHarnessSpec], ContainerHarnessResult]


def _lane_adapter(runner: _SentinelRunner) -> ContainerCliAdapter:
    return ContainerCliAdapter(
        identity=identity_for_registry_name(LFB_ADAPTER),
        local_manifest=LocalCliAdapterManifest.from_record(_lane_manifest_record()),
        auth_profile=FIXTURE_NONE,
        allow_hosts=(PROVIDER_HOST,),
        parent_env={},
        runner=runner,
    )


def _sentinel_runner(
    specs: list[ContainerHarnessSpec], *, echo: bool, exit_code: int = 0
) -> _SentinelRunner:
    """A container stand-in that can only answer by reading the staged file.

    The token is never handed to this fake: ``echo=True`` has to read it back
    out of the mounted workspace, so the probe test proves staging and checking
    actually meet rather than that the test told itself the answer.
    """

    def runner(spec: ContainerHarnessSpec) -> ContainerHarnessResult:
        specs.append(spec)
        spec.log_root.mkdir(parents=True, exist_ok=True)
        staged = spec.workspace.joinpath(*SENTINEL_RELATIVE_PATH.split("/"))
        answer = (
            f"SENTINEL={staged.read_text(encoding='utf-8').strip()}"
            if echo
            else "SENTINEL=guessed-without-reading-anything"
        )
        stdout = spec.log_root / "stdout.jsonl"
        stdout.write_text(_stream_json(answer, ()), encoding="utf-8")
        stderr = spec.log_root / "stderr.log"
        stderr.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=exit_code,
            timed_out=False,
            duration_seconds=0.5,
            stdout_path=stdout,
            stderr_path=stderr,
            image_id=spec.image,
            proxy_image_id=spec.image,
            allowed_hosts=(PROVIDER_HOST,),
            refused=(),
            allowlist={"hosts": [PROVIDER_HOST], "ports": [443]},
        )

    return runner


def test_the_probe_prompt_names_the_file_but_never_the_token() -> None:
    sentinel = mint_workspace_sentinel()

    assert len(sentinel.token) == 32
    assert sentinel.container_path in sentinel.prompt()
    # The whole mechanism rests on this: a prompt carrying the token would let
    # a model that touched no file answer correctly.
    assert sentinel.token not in sentinel.prompt()


def test_a_token_in_the_answer_proves_a_local_tool_read() -> None:
    sentinel = mint_workspace_sentinel(token=_SENTINEL_TOKEN)

    check = check_workspace_sentinel(
        sentinel,
        prompt=sentinel.prompt(),
        answer=f"SENTINEL={_SENTINEL_TOKEN}",
        transcript=f'{{"type":"result","result":"SENTINEL={_SENTINEL_TOKEN}"}}',
    )

    assert check.verdict is SentinelVerdict.PROVEN
    # Both channels carry it, so this also pins the precedence: the answer is
    # named as the source rather than the raw envelope around it.
    assert check.found_in == "answer"
    assert check.proven


def test_a_run_that_never_surfaced_the_token_is_absent() -> None:
    sentinel = mint_workspace_sentinel(token=_SENTINEL_TOKEN)

    check = check_workspace_sentinel(
        sentinel,
        prompt=sentinel.prompt(),
        answer="SENTINEL=0f0f0f",
        transcript="tools_used: []",
    )

    assert check.verdict is SentinelVerdict.ABSENT
    assert check.found_in is None
    assert check.token == _SENTINEL_TOKEN


def test_a_run_with_no_sentinel_is_not_attempted_rather_than_absent() -> None:
    # "Nobody staged a sentinel" and "the agent declined to read one" are
    # different claims, and only the second is evidence about the harness.
    check = check_workspace_sentinel(
        None, prompt="forecast this motion", answer="denied"
    )

    assert check.verdict is SentinelVerdict.NOT_ATTEMPTED
    assert check.token is None


def test_a_token_the_prompt_discloses_is_refused_rather_than_proven() -> None:
    sentinel = mint_workspace_sentinel(token=_SENTINEL_TOKEN)

    with pytest.raises(SentinelError, match="appears in the prompt"):
        check_workspace_sentinel(
            sentinel,
            prompt=f"{sentinel.prompt()} For reference the value is {_SENTINEL_TOKEN}.",
            answer=f"SENTINEL={_SENTINEL_TOKEN}",
        )


def test_a_guessable_token_is_refused_at_mint_time() -> None:
    with pytest.raises(SentinelError, match="at least"):
        mint_workspace_sentinel(token="abc")


def test_staging_a_sentinel_over_an_earlier_one_is_refused(tmp_path: Path) -> None:
    sentinel = mint_workspace_sentinel(token=_SENTINEL_TOKEN)

    staged = materialize_workspace_sentinel(sentinel, tmp_path)

    assert staged.read_text(encoding="utf-8").strip() == _SENTINEL_TOKEN
    with pytest.raises(SentinelError, match="already exists"):
        materialize_workspace_sentinel(mint_workspace_sentinel(), tmp_path)


def test_the_probe_proves_tool_use_by_round_tripping_the_mounted_workspace(
    tmp_path: Path,
) -> None:
    specs: list[ContainerHarnessSpec] = []
    adapter = _lane_adapter(_sentinel_runner(specs, echo=True))

    probe = probe_workspace_tool_use(
        adapter, workspace=tmp_path, model_key="claude-opus-5"
    )

    assert probe.check.verdict is SentinelVerdict.PROVEN
    assert probe.check.found_in == "transcript"
    assert probe.exit_code == 0
    assert probe.timed_out is False
    # The only channel the token travelled through is the mounted file: it is
    # in neither the rendered argv nor the prompt the agent was handed.
    assert probe.sentinel.token not in " ".join(specs[0].harness_argv)
    assert specs[0].workspace.joinpath(*SENTINEL_RELATIVE_PATH.split("/")).is_file()


def test_a_probe_that_answered_without_reading_is_absent_beside_its_exit(
    tmp_path: Path,
) -> None:
    adapter = _lane_adapter(_sentinel_runner([], echo=False, exit_code=1))

    probe = probe_workspace_tool_use(
        adapter, workspace=tmp_path, model_key="claude-opus-5"
    )
    record = probe.to_public_record()

    assert probe.check.verdict is SentinelVerdict.ABSENT
    # Without the exit code beside it, a crashed probe and a harness that used
    # no tools would publish the same verdict.
    assert record["sentinel_verdict"] == "absent"
    assert record["sentinel_probe_exit_code"] == 1
    assert record["sentinel_token"] == probe.sentinel.token
    validate_public_record(record, "sentinel.public_record")

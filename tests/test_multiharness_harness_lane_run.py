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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from legalforecast._json_io import write_jsonl_objects
from legalforecast.cli import main as legalforecast_main
from legalforecast.multiharness.cli import add_multiharness_parser
from legalforecast.multiharness.container_harness import (
    ContainerHarnessResult,
    ContainerHarnessSpec,
)
from legalforecast.multiharness.harness_lane.tool_accounting import (
    ToolAccountingError,
    harness_tool_use,
)
from legalforecast.multiharness.local_cli_manifest import capability_digest_for
from legalforecast.multiharness.task_loaders import ReleaseLfbTaskLoader
from legalforecast.release.synthetic import issue_synthetic_release
from tests.test_multiharness_scoped_runs import projected_lab_layout
from tests.test_multiharness_task_loaders import (
    _model_packet,  # pyright: ignore[reportPrivateUsage]
)

CONTAINER_MANIFEST = Path("examples/adapters/claude-code-native")
LFB_ADAPTER = "claude-code-container-tools-on"
PROVIDER_HOST = "api.anthropic.com"


def _run_multiharness(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="legalforecast")
    add_multiharness_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(argv)
    return int(args.handler(args))


def _lane_manifest_record() -> dict[str, Any]:
    return json.loads(
        (CONTAINER_MANIFEST / "local-cli-adapter-manifest.json").read_text(
            encoding="utf-8"
        )
    )


def _lab_manifest(destination: Path) -> Path:
    """Write a LAB-capable sibling of the committed container manifest.

    The committed manifests declare ``legalforecast_mtd``/``lfb_brier`` only,
    so a LAB row would be refused by ``prepare``.  Everything else -- image
    digest, argv template, tool posture -- is reused verbatim, and the
    capability digest is recomputed over the changed payload rather than
    copied, so the manifest is as self-consistent as a committed one.
    """

    record = _lane_manifest_record()
    binding = dict(record["harness_binding"])
    binding["adapter_id"] = f"{LFB_ADAPTER}-harvey-lab"
    binding["supported_families"] = ["harvey_lab"]
    binding["supported_scoring_modes"] = ["lab_native"]
    record["harness_binding"] = binding
    record["manifest_id"] = binding["adapter_id"]
    record["capability_digest"] = capability_digest_for(record)
    destination.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    return destination


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

    state: dict[str, Any] = {"answer": "", "tools": ("Bash", "Read"), "specs": []}

    def runner(
        spec: ContainerHarnessSpec, *, backend: str = "docker"
    ) -> ContainerHarnessResult:
        state["specs"].append(spec)
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
                str(_lab_manifest(tmp_path / "lab-manifest.json")),
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
    tmp_path: Path, fake_container: dict[str, Any]
) -> None:
    """The packet source runs; it cannot score, and that is structural.

    ``LfbTaskLoader`` packets carry no ``release_schema_version``, so
    ``release_harness`` projects no LFB record for them -- exactly as for every
    other command adapter today.  Scoring this lane needs a release-backed
    index.  This test pins that boundary so it is a known limit rather than a
    surprise.
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

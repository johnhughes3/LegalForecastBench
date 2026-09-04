from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest
from legalforecast.evals.output_parser import (
    DEFAULT_MISSING_PROBABILITY,
    ParserIssueCode,
)
from legalforecast.multiharness.adapter_registry import builtin_adapter_registry
from legalforecast.multiharness.harness_lane import (
    CONTAINER_WORKSPACE_ROOT,
    GRADED_DIRECTORY_MODE,
    GRADED_FILE_MODE,
    GRADED_PACKET_RELATIVE_PATH,
    HarnessLaneForecastError,
    HarnessLaneStagingError,
    classify_harness_forecast,
    default_invoke_prompt,
    read_container_workspace_file,
    require_honest_canonical_row,
    require_packet_staged,
    stage_graded_container_workspace,
    workspace_relative_files,
)
from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SolverInputPayload,
    SolverInputStore,
    write_solver_input_store,
)
from legalforecast.multiharness.spec import CanonicalTask
from legalforecast.testing.mock_model_outputs import get_mock_model_output

SHA256 = "sha256:" + "a" * 64
ROOT = Path(__file__).resolve().parents[1]
MULTIHARNESS_ROOT = ROOT / "legalforecast" / "multiharness"


def test_prompt_only_workspace_is_refused_before_invoke(tmp_path: Path) -> None:
    workspace = tmp_path / "container-workspace"
    workspace.mkdir()
    invoke_prompt = default_invoke_prompt(GRADED_PACKET_RELATIVE_PATH)
    (workspace / SOLVER_INPUT_ENTRY_PATH).write_text(invoke_prompt, encoding="utf-8")

    with pytest.raises(HarnessLaneStagingError, match=r"only prompt\.txt"):
        require_packet_staged(workspace, invoke_prompt=invoke_prompt)


def test_solver_visible_materialize_is_not_a_graded_workspace(tmp_path: Path) -> None:
    task = _task()
    store = _store(tmp_path, task=task)
    visible = tmp_path / "solver-visible"
    store.materialize(task, destination_root=visible)

    assert workspace_relative_files(visible) == (SOLVER_INPUT_ENTRY_PATH,)
    with pytest.raises(HarnessLaneStagingError, match=r"only prompt\.txt"):
        require_packet_staged(
            visible,
            invoke_prompt=default_invoke_prompt(GRADED_PACKET_RELATIVE_PATH),
        )


def test_correct_staging_puts_packet_on_the_planned_container_read(
    tmp_path: Path,
) -> None:
    packet_bytes = b'{"private":"packet"}\n'
    task = _task(packet_bytes=packet_bytes)
    store = _store(tmp_path, task=task, packet_bytes=packet_bytes)

    staged = stage_graded_container_workspace(
        store,
        task,
        destination_root=tmp_path / "container-workspace",
    )

    files = workspace_relative_files(staged.host_root)
    assert SOLVER_INPUT_ENTRY_PATH in files
    assert files != (SOLVER_INPUT_ENTRY_PATH,)
    assert GRADED_PACKET_RELATIVE_PATH in files
    assert staged.packet_relative_path == GRADED_PACKET_RELATIVE_PATH
    assert GRADED_PACKET_RELATIVE_PATH in staged.invoke_prompt
    assert staged.planned_read_path == (
        f"{CONTAINER_WORKSPACE_ROOT}/{GRADED_PACKET_RELATIVE_PATH}"
    )
    assert staged.planned_read_path in staged.planned_command

    observed = read_container_workspace_file(staged, staged.planned_read_path)
    assert observed == packet_bytes
    assert _bytes_sha256(observed) == task.task_sha256


def test_staged_workspace_is_traversable_by_other_uid(tmp_path: Path) -> None:
    """A 0700 host-owned root is opaque to sandbox UID 65532 on a bind mount."""

    task = _task()
    store = _store(tmp_path, task=task)
    staged = stage_graded_container_workspace(
        store,
        task,
        destination_root=tmp_path / "container-workspace",
    )
    packet = staged.host_root / GRADED_PACKET_RELATIVE_PATH
    assert packet.is_file()

    directory = packet.parent
    while True:
        mode = stat.S_IMODE(directory.stat().st_mode)
        assert mode == GRADED_DIRECTORY_MODE
        assert mode & stat.S_IXOTH
        if directory == staged.host_root:
            break
        directory = directory.parent

    file_mode = stat.S_IMODE(packet.stat().st_mode)
    assert file_mode == GRADED_FILE_MODE
    assert file_mode & stat.S_IROTH


def test_json_decode_error_is_a_failed_row_not_a_scored_success() -> None:
    fixture = get_mock_model_output("mock_invalid_json_truncated")

    row = classify_harness_forecast(
        fixture.raw_output,
        required_unit_ids=fixture.required_unit_ids,
    )
    record = row.to_canonical_record()
    parser = record["parser_output"]
    assert isinstance(parser, dict)

    require_honest_canonical_row(record)
    assert record["status"] != "succeeded"
    assert record["public_summary"]["failure_class"] != "none"
    assert record["public_summary"]["failure_class"] is not None
    assert record["status"] == "failed"
    assert (
        record["public_summary"]["failure_class"]
        == LocalCliFailureClass.SCHEMA_VIOLATION.value
    )
    assert record["scored"] is False
    assert parser["is_valid"] is False
    assert parser["invalid_output"] is True
    assert parser["status"] == "invalid_json"
    assert any(
        issue["code"] == ParserIssueCode.JSON_DECODE_ERROR.value
        for issue in parser["issues"]
    )
    assert parser["predictions"][0]["defaulted"] is True
    assert parser["predictions"][0]["probability_fully_dismissed"] == (
        DEFAULT_MISSING_PROBABILITY
    )


def test_stack_invalid_success_shape_is_refused() -> None:
    record = {
        "status": "succeeded",
        "public_summary": {"failure_class": None},
        "parser_output": {
            "is_valid": False,
            "invalid_output": True,
            "status": "invalid_json",
            "issues": [{"code": "json_decode_error", "unit_id": None}],
            "predictions": [
                {
                    "unit_id": "unit-001",
                    "probability_fully_dismissed": 0.5,
                    "defaulted": True,
                    "invalid_reason": "json_decode_error",
                }
            ],
            "defaulted_unit_ids": ["unit-001"],
        },
        "scored": True,
    }

    with pytest.raises(HarnessLaneForecastError, match="succeeded"):
        require_honest_canonical_row(record)


def test_valid_forecast_is_scored_without_defaulted_probability() -> None:
    fixture = get_mock_model_output("mock_calibrated_predictions")

    row = classify_harness_forecast(
        fixture.raw_output,
        required_unit_ids=fixture.required_unit_ids,
    )
    record = row.to_canonical_record()
    parser = record["parser_output"]
    assert isinstance(parser, dict)

    require_honest_canonical_row(record)
    assert record["status"] == "succeeded"
    assert record["public_summary"]["failure_class"] == "none"
    assert record["scored"] is True
    assert parser["is_valid"] is True
    assert parser["defaulted_unit_ids"] == []
    assert [item["probability_fully_dismissed"] for item in parser["predictions"]] == [
        prediction.probability_fully_dismissed
        for prediction in fixture.expected_predictions
    ]


def test_multiharness_has_no_kimi_harness_entry() -> None:
    hits = [
        path.relative_to(ROOT).as_posix()
        for path in MULTIHARNESS_ROOT.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".json", ".md", ".toml"}
        and "kimi" in path.read_text(encoding="utf-8", errors="replace").casefold()
    ]
    assert hits == []
    assert not any(
        "kimi" in name.casefold() for name in builtin_adapter_registry().known_names()
    )


def _store(
    tmp_path: Path,
    *,
    task: CanonicalTask,
    packet_bytes: bytes | None = None,
) -> SolverInputStore:
    encoded = packet_bytes if packet_bytes is not None else _packet_bytes()
    return write_solver_input_store(
        destination_root=tmp_path / "solver-inputs",
        task_index_sha256=SHA256,
        payloads=(
            SolverInputPayload(
                task=task,
                prompt="private prompt",
                source_packet_bytes=encoded,
            ),
        ),
    )


def _task(packet_bytes: bytes | None = None) -> CanonicalTask:
    encoded = packet_bytes if packet_bytes is not None else _packet_bytes()
    return CanonicalTask(
        task_id="lfb:fixture:full_packet",
        family="legalforecast_mtd",
        scoring_mode="lfb_brier",
        suite_version="fixture-suite",
        source_id="fixture",
        task_sha256=_bytes_sha256(encoded),
        metadata={"prompt_sha256": hashlib.sha256(b"private prompt").hexdigest()},
    )


def _packet_bytes() -> bytes:
    return json.dumps(
        {"private": "packet"}, sort_keys=True, separators=(",", ":")
    ).encode()


def _bytes_sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()

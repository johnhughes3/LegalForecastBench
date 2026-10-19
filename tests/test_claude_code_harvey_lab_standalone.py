from __future__ import annotations

import io
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import legalforecast.multiharness.claude_code_container_runtime as container_runtime
import legalforecast.multiharness.claude_code_harvey_lab as lab_join
import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.claude_code import ClaudeCodeCliAdapter
from legalforecast.multiharness.claude_code_container_inputs import (
    CLAUDE_CODE_STAGED_PROMPT_INSTRUCTION,
)
from legalforecast.multiharness.claude_code_container_runtime import (
    OUTER_CONTAINER_ONLY_MODE,
    ClaudeCodeContainerExecutionService,
)
from legalforecast.multiharness.claude_code_harvey_lab import (
    ClaudeCodeHarveyLabMeasurementResult,
    run_claude_code_clean_native_harvey_lab,
)
from legalforecast.multiharness.container_harness import ContainerHarnessResult
from legalforecast.multiharness.container_harness.fence import (
    ParserFenceFields,
    fence_from_parser_fields,
)
from legalforecast.multiharness.harvey_lab_observed_score import (
    HarveyLabObservedScoreError,
    observed_harvey_lab_score,
)
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.scoring import LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION

from test_harvey_lab_projection import FIXTURE_PIN
from test_multiharness_claude_clean_native_lab_e2e import (
    _hosts,
    _install_binaries,
    _make_writable,
)

IMAGE = "sha256:" + "a" * 64


def test_container_workspace_uses_real_plan_and_stream_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _install_binaries(tmp_path)
    hosts = _hosts(tmp_path)
    captured: dict[str, object] = {}

    def container_double(
        spec: container_runtime.ContainerHarnessSpec,
        *,
        publication_directory: Path,
        backend: str,
    ) -> ContainerHarnessResult:
        del publication_directory, backend
        captured["spec"] = spec
        captured["prompt_mode"] = (spec.workspace / "prompt.txt").stat().st_mode
        output = spec.workspace / "output"
        output.mkdir(exist_ok=True)
        (output / "issue-identification-memo.docx").write_bytes(_docx_bytes())
        spec.log_root.mkdir(parents=True, exist_ok=True)
        stdout_path = spec.log_root / "stdout"
        stderr_path = spec.log_root / "stderr"
        events = (
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-sonnet-4-6",
                "tools": ["Bash", "Read", "Glob"],
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read-prompt",
                            "name": "Bash",
                            "input": {"command": "cat /workspace/prompt.txt"},
                        }
                    ]
                },
            },
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "read-prompt",
                            "content": "authenticated prompt",
                        }
                    ]
                },
            },
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "model": "claude-sonnet-4-6",
                "result": {"deliverable": "memo", "status": "complete"},
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "server_tool_use": {
                        "web_search_requests": 0,
                        "web_fetch_requests": 0,
                    },
                },
                "total_cost_usd": 0.001,
            },
        )
        stdout_path.write_text(
            "\n".join(json.dumps(event, separators=(",", ":")) for event in events),
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
        return ContainerHarnessResult(
            run_id=spec.run_id,
            exit_code=0,
            timed_out=False,
            duration_seconds=1,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            image_id=IMAGE,
            proxy_image_id=IMAGE,
            allowed_hosts=spec.allow_hosts,
            refused=(),
            allowlist={},
            fence=fence_from_parser_fields(
                ParserFenceFields(
                    parse_ok=True,
                    reports_fence=True,
                    tools_available=("Bash", "Read", "Glob"),
                    server_side_web_tools_available=(),
                    server_side_web_request_count=0,
                )
            ),
        )

    monkeypatch.setattr(container_runtime, "run_container_harness", container_double)
    monkeypatch.setattr(lab_join, "harvey_lab_v1_1_pin", lambda: FIXTURE_PIN)
    service = ClaudeCodeContainerExecutionService(
        image_digest=IMAGE,
        auth_profile=FIXTURE_NONE,
        model_key="anthropic:claude-sonnet-4-6",
        output_root=tmp_path / "container-results",
        gateway_base_url="http://lfb-model-gateway:8080",
        gateway_upstream_base_url="http://fixture-upstream:8081/v1",
        execution_mode=OUTER_CONTAINER_ONLY_MODE,
        fixture_egress_network="fixture-network",
    )
    try:
        result = run_claude_code_clean_native_harvey_lab(
            adapter=ClaudeCodeCliAdapter(
                execution_service=service,  # type: ignore[arg-type]
                output_format="stream-json",
                verbose=True,
            ),
            evaluator_execution_service=LocalCliExecutionService(
                auth_profile=FIXTURE_NONE,
                parent_env=env,
            ),
            container_workspace=True,
            **hosts,
        )
        assert isinstance(result, ClaudeCodeHarveyLabMeasurementResult)
    finally:
        _make_writable(tmp_path)

    planned = captured["spec"]
    assert isinstance(planned, container_runtime.ContainerHarnessSpec)
    assert planned.read_only_workspace_paths == ("prompt.txt", "task")
    assert result.solver_spec.output_format == "stream-json"
    assert result.solver_spec.argv[result.solver_spec.argv.index("-p") + 1] == (
        CLAUDE_CODE_STAGED_PROMPT_INSTRUCTION
    )
    assert result.solver_spec.argv[
        result.solver_spec.argv.index("--output-format") + 1
    ] == ("stream-json")
    assert "--verbose" in result.solver_spec.argv
    assert int(captured["prompt_mode"]) & 0o222 == 0
    assert result.solver_execution.status == "succeeded"
    assert result.execution_mode == "fixture"
    assert result.baseline_score_value is None
    assert result.score.score_value == 1
    assert result.projection.manifest.pin == FIXTURE_PIN

    inconsistent = {
        "schema_version": LAB_VERDICT_DERIVATIVE_SCHEMA_VERSION,
        "score": 1,
        "n_passed": result.score.n_criteria,
        "n_criteria": result.score.n_criteria,
        "verdicts": [
            {"ordinal": ordinal, "verdict": "fail" if ordinal == 1 else "pass"}
            for ordinal in range(1, result.score.n_criteria + 1)
        ],
    }
    raw = json.dumps(inconsistent, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(HarveyLabObservedScoreError, match="inconsistent"):
        observed_harvey_lab_score(replace(result.evaluation, raw_result=raw))

    duplicate = raw.replace(b'{"n_criteria":', b'{"score":1,"n_criteria":', 1)
    with pytest.raises(HarveyLabObservedScoreError, match="duplicate"):
        observed_harvey_lab_score(replace(result.evaluation, raw_result=duplicate))


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()

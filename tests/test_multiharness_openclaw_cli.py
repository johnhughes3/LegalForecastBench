from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from legalforecast.multiharness.openclaw_cli import StdioTransport, main
from legalforecast.multiharness.spec import AdapterCapabilities, RunResult
from legalforecast.multiharness.tool_protocol import (
    ToolRequest,
    ToolResponse,
    decode_tool_request,
    encode_tool_message,
)
from tests.test_multiharness_openclaw import request


def test_cli_capabilities_and_offline_result_are_valid_records(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    assert main(["capabilities", "--output", str(output)]) == 0
    capabilities = AdapterCapabilities.from_record(json.loads(output.read_text()))
    assert capabilities.adapter_id == "openclaw-pinned-bridge"
    assert capabilities.supported_families == ("legalforecast_mtd",)

    live = request()
    offline = replace(
        live,
        task=replace(live.task, metadata={"fixture": "adapter-conformance"}),
        sandbox_policy=replace(live.sandbox_policy, allowed_provider_env_vars=()),
    )
    input_path = tmp_path / "request.json"
    input_path.write_text(json.dumps(offline.to_record()))
    assert (
        main(
            [
                "run",
                "--request",
                str(input_path),
                "--output",
                str(output),
                "--workspace",
                str(tmp_path),
            ]
        )
        == 0
    )
    result = RunResult.from_record(json.loads(output.read_text()))
    assert result.request_id == offline.request_id
    assert result.status == "succeeded"
    assert result.public_summary["offline_protocol_fixture"] is True
    assert result.public_summary["provider_request_count"] == 0


@pytest.mark.parametrize("phase", ["run", "run-with-tools"])
def test_cli_rejects_invalid_requests_without_output_or_input_disclosure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], phase: str
) -> None:
    input_path = tmp_path / "request.json"
    input_path.write_text("private-request-marker: not JSON")
    output = tmp_path / "result.json"
    assert (
        main(
            [
                phase,
                "--request",
                str(input_path),
                "--output",
                str(output),
                "--workspace",
                str(tmp_path),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "failed closed" in captured.err
    assert "private-request-marker" not in captured.err
    assert not output.exists()


def test_cli_live_dispatch_refuses_missing_provider_grant_before_runtime(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    live = request()
    denied = replace(
        live, sandbox_policy=replace(live.sandbox_policy, allowed_provider_env_vars=())
    )
    input_path = tmp_path / "request.json"
    input_path.write_text(json.dumps(denied.to_record()))
    output = tmp_path / "result.json"
    assert (
        main(
            [
                "run-with-tools",
                "--request",
                str(input_path),
                "--output",
                str(output),
                "--workspace",
                str(tmp_path),
            ]
        )
        == 1
    )
    assert "failed closed" in capsys.readouterr().err
    assert not output.exists()
    assert not (tmp_path / "private-logs").exists()


def test_stdio_transport_exchanges_canonical_jsonl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_record = ToolRequest(
        request_id="cli-read",
        operation="read",
        arguments={"file_path": "prompt.txt"},
        input_paths=("prompt.txt",),
    )
    response = ToolResponse(
        request_id=request_record.request_id,
        status="succeeded",
        output={"content": "staged prompt"},
    )
    input_stream = io.TextIOWrapper(io.BytesIO(encode_tool_message(response)))
    output_stream = io.TextIOWrapper(io.BytesIO())
    monkeypatch.setattr("sys.stdin", input_stream)
    monkeypatch.setattr("sys.stdout", output_stream)
    actual = StdioTransport().execute(request_record)
    assert actual == response
    output_stream.buffer.seek(0)
    assert decode_tool_request(output_stream.buffer.read()) == request_record


def test_stdio_transport_rejects_non_protocol_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"{}\n")))
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(io.BytesIO()))
    with pytest.raises(ValueError, match="schema_version"):
        StdioTransport().execute(ToolRequest(request_id="cli-read", operation="read"))

"""Hermes Python 3.13 child: one managed conversation and one host-owned tool.

This file deliberately uses only the standard library before importing Hermes;
the benchmark package requires Python 3.14 and cannot share Hermes' environment.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, TextIO, cast

TOOL_NAME = "read_canonical_task"
MAX_MESSAGE_BYTES = 1_048_576


class Agent(Protocol):
    """Public Hermes library members used by this pinned bridge."""

    model: str
    tools: list[dict[str, object]]

    def run_conversation(self, user_message: str) -> dict[str, object]: ...

    def close(self) -> None: ...


class Registry(Protocol):
    """Supported Hermes tool registration surface."""

    def register(self, **kwargs: object) -> None: ...


def execute(
    config: Mapping[str, object],
    factory: Callable[..., Agent],
    registry: Registry,
    incoming: TextIO,
    outgoing: TextIO,
) -> dict[str, object]:
    """Let Hermes own its conversation loop; forward its sole tool to the host."""

    calls = [0]
    successful_reads = [0]
    task_text = [""]
    offset = [0]

    def read_task(arguments: Mapping[str, object], **_kwargs: object) -> str:
        calls[0] += 1
        requested_offset = arguments.get("offset", 0)
        if (
            set(arguments) - {"offset"}
            or type(requested_offset) is not int
            or requested_offset != offset[0]
        ):
            raise ValueError("read canonical task chunks in order")
        if successful_reads[0]:
            return next_chunk()
        request_id = f"{config['request_id']}:hermes-tool:1"
        outgoing.write(
            json.dumps(
                {
                    "schema_version": "legalforecast.multiharness.tool_request.v1",
                    "request_id": request_id,
                    "operation": "read_text",
                    "arguments": {"encoding": "utf-8"},
                    "input_paths": [config["solver_input_path"]],
                }
            )
            + "\n"
        )
        outgoing.flush()
        line = incoming.readline(MAX_MESSAGE_BYTES + 1)
        if not line.endswith("\n") or len(line.encode()) > MAX_MESSAGE_BYTES:
            raise ValueError("invalid host tool response size")
        response = cast(dict[str, object], json.loads(line))
        if (
            response.get("schema_version")
            != "legalforecast.multiharness.tool_response.v1"
            or response.get("request_id") != request_id
            or response.get("status") != "succeeded"
        ):
            raise ValueError("host tool response did not match")
        output = response.get("output")
        if not isinstance(output, dict):
            raise ValueError("host tool response has no output")
        text = cast(dict[str, object], output).get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("host tool response has no text")
        successful_reads[0] += 1
        task_text[0] = text
        return next_chunk()

    def next_chunk() -> str:
        if offset[0] >= len(task_text[0]):
            raise ValueError("canonical task already read completely")
        # Hermes' smallest supported per-tool budget is 8,000 characters.
        # Keep each chunk below it, including JSON framing, so its spill-to-file
        # mechanism never hides task text behind an unavailable filesystem tool.
        end = min(offset[0] + 6000, len(task_text[0]))
        while True:
            encoded = json.dumps(
                {
                    "text": task_text[0][offset[0] : end],
                    "next_offset": end,
                    "complete": end == len(task_text[0]),
                },
                ensure_ascii=False,
            )
            if len(encoded) <= 7500:
                offset[0] = end
                return encoded
            end = offset[0] + (end - offset[0]) // 2

    registry.register(
        name=TOOL_NAME,
        toolset="legalforecast",
        schema={
            "name": TOOL_NAME,
            "description": "Read the next host-authenticated forecast prompt chunk.",
            "parameters": {
                "type": "object",
                "properties": {"offset": {"type": "integer", "minimum": 0}},
                "additionalProperties": False,
            },
        },
        handler=read_task,
    )
    agent = factory(
        model=config["model"],
        provider="openrouter",
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
        enabled_toolsets=["legalforecast"],
        max_iterations=200,
        run_budget_seconds=180,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        load_soul_identity=False,
        save_trajectories=False,
        quiet_mode=True,
        fallback_model=None,
        session_id=config["session_id"],
        cwd=config["working_directory"],
    )
    try:
        names = [
            cast(dict[str, object], tool["function"])["name"] for tool in agent.tools
        ]
        if names != [TOOL_NAME]:
            raise ValueError("Hermes exposed unexpected tools")
        result = agent.run_conversation(
            "Call read_canonical_task with offset 0, then each returned next_offset "
            "until complete is true. Read every chunk before forecasting using only "
            "that complete prompt. Return JSON with case_assessment and predictions; "
            "each prediction has unit_id, probability_fully_dismissed and rationale. "
            f"Required units: {json.dumps(config['required_unit_ids'])}."
        )
        if successful_reads[0] != 1 or offset[0] != len(task_text[0]):
            raise ValueError("Hermes did not read the complete canonical task")
        return {
            "result": result,
            "model": agent.model,
            "tool_call_count": successful_reads[0],
            "task_chunk_count": calls[0],
            "session_id": config["session_id"],
        }
    finally:
        agent.close()


def main() -> int:
    """Execute in the pinned Hermes environment, keeping diagnostics private."""

    config = cast(dict[str, object], json.loads(Path(sys.argv[1]).read_text()))
    # The parent validates this checkout before it launches this child.
    sys.path.insert(0, str(config["checkout"]))
    if importlib.metadata.version("hermes-agent") != "0.21.5":
        raise ValueError("installed Hermes version does not match the pin")
    protocol_out = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        factory = cast(
            Callable[..., Agent], importlib.import_module("run_agent").AIAgent
        )
        registry = cast(Registry, importlib.import_module("tools.registry").registry)
        result = execute(config, factory, registry, sys.stdin, protocol_out)
        result["python_version"] = platform.python_version()
        result["hermes_version"] = importlib.metadata.version("hermes-agent")
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

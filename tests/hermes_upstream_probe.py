"""Opt-in pinned Hermes conformance with SDK fixtures, never live inference."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import socket
import sys
from pathlib import Path


def main() -> None:
    checkout, runtime_path, private_home = map(Path, sys.argv[1:])
    os.environ.clear()
    os.environ.update(
        {
            "HERMES_HOME": str(private_home),
            "HERMES_SAFE_MODE": "1",
            "HERMES_IGNORE_RULES": "1",
            "OPENROUTER_API_KEY": "offline-test",
        }
    )
    (private_home / "config.yaml").write_text(
        json.dumps(
            {
                "tools": {"tool_search": {"enabled": "off"}},
                "memory": {"memory_enabled": False, "user_profile_enabled": False},
            }
        )
    )

    def denied(*_args, **_kwargs):
        raise OSError("offline conformance forbids network requests")

    socket.socket.connect = denied
    # SDK clients may be recreated during a turn. Block network on the class,
    # rather than only stubbing the first client instance.
    importlib.import_module("httpx").Client.send = denied
    importlib.import_module("requests").Session.request = denied
    sys.path.insert(0, str(checkout))
    agent_class = importlib.import_module("run_agent").AIAgent
    registry = importlib.import_module("tools.registry").registry
    completion_class = importlib.import_module("openai.types.chat").ChatCompletion
    completions = importlib.import_module(
        "openai.resources.chat.completions"
    ).Completions
    spec = importlib.util.spec_from_file_location("bridge", runtime_path)
    assert spec is not None and spec.loader is not None
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    calls = []
    canonical_task = "Forecast the public test motion " + "x" * 12000 + " END-OF-TASK"

    def complete(_self, **kwargs):
        # Hermes puts bulk fields in extra_body; the SDK merges these before
        # sending the wire request (agent/sdk_transform_bypass.py).
        wire = {**kwargs, **kwargs.get("extra_body", {})}
        calls.append(kwargs)
        tool_messages = [
            message for message in wire["messages"] if message.get("role") == "tool"
        ]
        previous = json.loads(tool_messages[-1]["content"]) if tool_messages else None
        if previous is None or not previous["complete"]:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{len(calls)}",
                        "type": "function",
                        "function": {
                            "name": "read_canonical_task",
                            "arguments": json.dumps(
                                {"offset": previous["next_offset"] if previous else 0}
                            ),
                        },
                    }
                ],
            }
            finish = "tool_calls"
        else:
            assert (
                "".join(
                    json.loads(message["content"])["text"] for message in tool_messages
                )
                == canonical_task
            )
            assert all(len(message["content"]) <= 7500 for message in tool_messages)
            message = {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "case_assessment": "Offline fixture",
                        "predictions": [
                            {
                                "unit_id": "count_i",
                                "probability_fully_dismissed": 0.7,
                            }
                        ],
                    }
                ),
            }
            finish = "stop"
        return completion_class(
            id="offline",
            created=1,
            model="openai/gpt-4o-mini",
            object="chat.completion",
            choices=[{"index": 0, "message": message, "finish_reason": finish}],
            usage={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        )

    completions.create = complete
    incoming = io.StringIO(
        json.dumps(
            {
                "schema_version": "legalforecast.multiharness.tool_response.v1",
                "request_id": "case:hermes-tool:1",
                "status": "succeeded",
                "output": {"text": canonical_task},
            }
        )
        + "\n"
    )
    outgoing = io.StringIO()
    result = bridge.execute(
        {
            "request_id": "case",
            "model": "openai/gpt-4o-mini",
            "session_id": "offline-conformance",
            "required_unit_ids": ["count_i"],
            "working_directory": str(private_home),
            "solver_input_path": "prompt.txt",
        },
        agent_class,
        registry,
        incoming,
        outgoing,
    )
    assert result["result"]["completed"] is True
    assert result["tool_call_count"] == 1
    assert len(calls) == 4
    assert result["task_chunk_count"] == 3
    assert json.loads(outgoing.getvalue())["operation"] == "read_text"
    print("Pinned Hermes conversation and host tool passed (SDK fixtures)")


if __name__ == "__main__":
    main()

"""Regressions derived from the September 26 terminal smoke's event shapes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.claude_code_stream import normalize_claude_stream, usage


@pytest.mark.parametrize("denied", [False, True])
def test_compound_prompt_read_and_optional_docket_material(
    tmp_path: Path, denied: bool
) -> None:
    (tmp_path / "prompt.txt").write_text("forecast the staged case")
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "docket-history.json").write_text("{}")
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "read",
                        "name": "Bash",
                        "input": {
                            "command": "cat /workspace/prompt.txt; ls /workspace"
                        },
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
                        "tool_use_id": "read",
                        "is_error": denied,
                        "content": "forecast the staged case",
                    }
                ]
            },
        },
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": {"predictions": []},
        },
    ]
    _, envelope, accepted = normalize_claude_stream(
        "\n".join(json.dumps(e) for e in events), tmp_path
    )
    assert accepted is not denied
    assert envelope is not None
    trace = envelope["_lfb_tool_trace"]
    assert trace == {
        "bash_tool_count": 0 if denied else 1,
        "read_tool_count": 0 if denied else 1,
        "referenced_paths": [] if denied else ["/workspace/prompt.txt"],
    }


def test_terminal_usage_counts_cache_buckets_once() -> None:
    # Native terminal totals observed in the saved paid smoke, with no case text.
    envelope: dict[str, object] = {
        "usage": {
            "input_tokens": 10,
            "cache_creation_input_tokens": 15562,
            "cache_read_input_tokens": 24983,
            "output_tokens": 1860,
        }
    }
    normalized = usage(envelope)
    assert normalized["input_tokens"] == 40555
    assert normalized["cache_creation_input_tokens"] == 15562
    assert normalized["cache_read_input_tokens"] == 24983
    assert usage(envelope) == normalized
    assert envelope["usage"] == {
        "input_tokens": 10,
        "cache_creation_input_tokens": 15562,
        "cache_read_input_tokens": 24983,
        "output_tokens": 1860,
    }

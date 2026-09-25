"""Claude Code stream normalization and authenticated tool-use evidence."""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import cast


def normalize_claude_stream(
    raw_stdout: str,
    workspace: Path,
) -> tuple[str, dict[str, object] | None, bool]:
    """Extract Claude's terminal result while retaining tool evidence privately."""

    events: list[dict[str, object]] = []
    for line in raw_stdout.splitlines():
        if not line.strip():
            continue
        try:
            decoded: object = json.loads(line)
        except json.JSONDecodeError:
            return raw_stdout, _json_object(raw_stdout), False
        if not isinstance(decoded, dict):
            return raw_stdout, None, False
        events.append(cast(dict[str, object], decoded))
    terminal = next(
        (event for event in reversed(events) if event.get("type") == "result"),
        None,
    )
    if terminal is None:
        return raw_stdout, None, False
    envelope = dict(terminal)
    init = next(
        (
            event
            for event in events
            if event.get("type") == "system" and event.get("subtype") == "init"
        ),
        None,
    )
    if "model" not in envelope and init is not None:
        model = init.get("model")
        if isinstance(model, str) and model.strip():
            envelope["model"] = model
    observations = _stream_bash_observations(events)
    staged_paths = staged_workspace_paths(workspace)
    read_paths: set[str] = set()
    for _tool_use_id, command in observations:
        read_paths.update(_read_paths_from_cat(command, staged_paths))
    referenced = tuple(path for path in staged_paths if path in read_paths)
    envelope["_lfb_tool_trace"] = {
        "bash_tool_count": len(observations),
        "read_tool_count": sum(
            1
            for _tool_use_id, command in observations
            if _read_paths_from_cat(command, staged_paths)
        ),
        "referenced_paths": list(referenced),
    }
    prompt_referenced = "/workspace/prompt.txt" in referenced
    staged_documents = tuple(
        path for path in staged_paths if path.startswith("/workspace/documents/")
    )
    documents_referenced = all(path in referenced for path in staged_documents)
    trace_ok = bool(observations) and prompt_referenced and documents_referenced
    return (
        json.dumps(envelope, sort_keys=True, separators=(",", ":")),
        envelope,
        trace_ok,
    )


def _stream_bash_observations(
    events: list[dict[str, object]],
) -> tuple[tuple[str, str], ...]:
    """Return Bash tool uses whose matching result is not marked as an error.

    Stream events are untrusted until a ``tool_result`` with the same ID says
    that the command completed without an error. The Anthropic stream omits
    ``is_error`` for successful results, so only an explicit true value fails.
    Keeping the command only in this private in-memory observation also lets
    the public trace expose counts and staged paths without copying case text
    or shell arguments into output.
    """

    successful_tool_use_ids: set[str] = set()
    for event in events:
        if event.get("type") != "user":
            continue
        message_value = event.get("message")
        if not isinstance(message_value, dict):
            continue
        message = cast(dict[str, object], message_value)
        content_value = message.get("content")
        if not isinstance(content_value, list):
            continue
        content = cast(list[object], content_value)
        for block_value in content:
            if not isinstance(block_value, dict):
                continue
            block = cast(dict[str, object], block_value)
            if block.get("type") == "tool_result" and block.get("is_error") is not True:
                tool_use_id = block.get("tool_use_id")
                if isinstance(tool_use_id, str) and tool_use_id:
                    successful_tool_use_ids.add(tool_use_id)

    observations: list[tuple[str, str]] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        message_value = event.get("message")
        if not isinstance(message_value, dict):
            continue
        message = cast(dict[str, object], message_value)
        content_value = message.get("content")
        if not isinstance(content_value, list):
            continue
        content = cast(list[object], content_value)
        for block_value in content:
            if not isinstance(block_value, dict):
                continue
            block = cast(dict[str, object], block_value)
            if block.get("type") != "tool_use" or block.get("name") != "Bash":
                continue
            tool_use_id = block.get("id")
            if (
                not isinstance(tool_use_id, str)
                or not tool_use_id
                or tool_use_id not in successful_tool_use_ids
            ):
                continue
            tool_input_value = block.get("input")
            if isinstance(tool_input_value, dict):
                tool_input = cast(dict[str, object], tool_input_value)
                command = tool_input.get("command")
                if isinstance(command, str) and command.strip():
                    observations.append((tool_use_id, command))
    return tuple(observations)


def _read_paths_from_cat(
    command: str,
    staged_paths: tuple[str, ...],
) -> tuple[str, ...]:
    """Identify staged paths in the controlled read instruction."""

    # A newline is a shell command separator, even though ``shlex.split``
    # treats it as ordinary whitespace. The staged paths are ordinary names,
    # so rejecting it cannot turn a valid controlled read into a false success.
    if "\n" in command or "\r" in command:
        return ()
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ()
    if not tokens or tokens[0] != "cat" or not tokens[1:]:
        return ()
    staged = set(staged_paths)
    if any(token not in staged for token in tokens[1:]):
        return ()
    return tuple(path for path in staged_paths if path in tokens[1:])


def staged_workspace_paths(workspace: Path) -> tuple[str, ...]:
    """Return the container paths of the staged prompt and visible documents."""

    paths = ["/workspace/prompt.txt"]
    documents = workspace / "documents"
    if documents.is_dir():
        for path in sorted(documents.rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(workspace).as_posix()
                paths.append(f"/workspace/{relative}")
    return tuple(paths)


def served_model(envelope: dict[str, object] | None) -> str | None:
    if envelope is None:
        return None
    model = envelope.get("model")
    if isinstance(model, str) and model.strip():
        return model
    model_usage = envelope.get("modelUsage")
    if isinstance(model_usage, dict):
        typed_model_usage = cast(dict[str, object], model_usage)
        if len(typed_model_usage) == 1:
            value = next(iter(typed_model_usage))
            return value if value.strip() else None
    return None


def terminal_success(envelope: dict[str, object] | None) -> bool:
    return bool(
        envelope is not None
        and envelope.get("type") == "result"
        and envelope.get("subtype") == "success"
        and envelope.get("is_error") is False
    )


def usage(envelope: dict[str, object] | None) -> dict[str, int]:
    if envelope is None or not isinstance(envelope.get("usage"), dict):
        return {}
    raw_usage = cast(dict[object, object], envelope["usage"])
    return {
        key: value
        for key, value in raw_usage.items()
        if isinstance(key, str) and type(value) is int and value >= 0
    }


def cost(envelope: dict[str, object] | None) -> float | None:
    if envelope is None:
        return None
    value = envelope.get("total_cost_usd")
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def tool_call_count_from_stdout(stdout: str) -> int:
    """Read the private stream trace's count without publishing its transcript."""

    try:
        decoded: object = json.loads(stdout)
    except json.JSONDecodeError:
        return 0
    if not isinstance(decoded, dict):
        return 0
    envelope = cast(dict[str, object], decoded)
    trace_value = envelope.get("_lfb_tool_trace")
    if not isinstance(trace_value, dict):
        return 0
    trace = cast(dict[str, object], trace_value)
    count = trace.get("bash_tool_count")
    return count if type(count) is int and count >= 0 else 0


def _json_object(stdout: str) -> dict[str, object] | None:
    try:
        value: object = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], value) if isinstance(value, dict) else None


__all__ = [
    "cost",
    "normalize_claude_stream",
    "served_model",
    "staged_workspace_paths",
    "terminal_success",
    "tool_call_count_from_stdout",
    "usage",
]

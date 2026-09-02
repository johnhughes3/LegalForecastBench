"""Parse Claude Code's ``stream-json`` envelope into a typed run result.

The generic manifest projection in
:func:`legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
already pulls the answer text out of the final ``result`` event, and that is
all the canonical :class:`~legalforecast.multiharness.spec.RunResult` needs.
This module exists for the question the projection cannot answer: *did the
harness actually behave like a harness?*

That question has two halves, and both are evidence rather than assertion:

* **Did it use its tools?**  A tools-on lane whose runs invoke no tool has
  measured the bare API through an expensive wrapper.  ``tools_used`` is read
  off the ``tool_use`` blocks the transcript actually contains.
* **Could it have searched the web?**  ``server_side_web_tools_available``
  reads the ``system``/``init`` event's own ``tools`` array, so a run proves
  the provider-executed web tools were absent instead of citing the argv flag
  that was supposed to remove them.  No container egress rule reaches a
  server-executed ``WebSearch``, and these forecasts are about real federal
  cases whose outcomes are one search away.

The stream is deliberately parsed permissively.  The 2.1.251 envelope already
carries event kinds beyond ``system``/``assistant``/``user``/``result`` -- a
``rate_limit_event`` shows up in an ordinary run -- and the CLI is free to add
more.  Unknown kinds are collected in ``unknown_event_types`` and ignored; the
only structural requirement is that exactly one terminal ``result`` event is
present.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass

CLAUDE_CODE_RESULT_EVENT: Final[str] = "result"
CLAUDE_CODE_SYSTEM_EVENT: Final[str] = "system"
CLAUDE_CODE_ASSISTANT_EVENT: Final[str] = "assistant"
CLAUDE_CODE_INIT_SUBTYPE: Final[str] = "init"
CLAUDE_CODE_SUCCESS_SUBTYPE: Final[str] = "success"
SERVER_SIDE_WEB_TOOLS: Final[frozenset[str]] = frozenset({"WebFetch", "WebSearch"})
_KNOWN_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        CLAUDE_CODE_ASSISTANT_EVENT,
        CLAUDE_CODE_RESULT_EVENT,
        CLAUDE_CODE_SYSTEM_EVENT,
        "user",
    }
)
# The CLI reports "none" when it authenticated from a subscription login rather
# than from ANTHROPIC_API_KEY, so this is how a run shows which credential it
# actually spent.
API_KEY_SOURCE_NONE: Final[str] = "none"


class ClaudeCodeStreamError(ValueError):
    """Raised when stdout is not a Claude Code ``stream-json`` transcript."""


@dataclass(frozen=True, slots=True)
class ClaudeCodeUsage:
    """Token and cost accounting for one run, as the CLI reported it."""

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    total_cost_usd: float | None
    num_turns: int | None
    duration_ms: int | None
    web_search_requests: int
    web_fetch_requests: int

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record of this run's usage."""

        return {
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "num_turns": self.num_turns,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "web_fetch_requests": self.web_fetch_requests,
            "web_search_requests": self.web_search_requests,
        }


@dataclass(frozen=True, slots=True)
class ClaudeCodeStreamResult:
    """One parsed Claude Code run: the answer, the posture, and the usage."""

    answer: str
    is_error: bool
    subtype: str
    stop_reason: str | None
    terminal_reason: str | None
    api_error_status: str | None
    model: str | None
    permission_mode: str | None
    api_key_source: str | None
    tools_available: tuple[str, ...]
    tools_used: tuple[str, ...]
    usage: ClaudeCodeUsage
    unknown_event_types: tuple[str, ...]

    @property
    def server_side_web_tools_available(self) -> tuple[str, ...]:
        """Return the provider-executed web tools the run could have called.

        Non-empty means the contamination fence was not actually closed for
        this run, whatever the manifest's ``server_side_web_tools_disabled``
        capability claims.
        """

        return tuple(sorted(SERVER_SIDE_WEB_TOOLS.intersection(self.tools_available)))

    @property
    def server_side_web_requests(self) -> int:
        """Return how many provider-executed web retrievals the run actually made.

        ``tools_available`` shows what was on the menu when the run started, and
        this CLI can surface further tool schemas mid-run, so the count the
        provider itself reports back is the stronger evidence: zero means no
        outcome ever came back over a channel the egress fence cannot see.
        """

        return self.usage.web_search_requests + self.usage.web_fetch_requests

    @property
    def used_any_tool(self) -> bool:
        """Return whether the harness invoked at least one of its own tools."""

        return bool(self.tools_used)

    @property
    def failure_class(self) -> LocalCliFailureClass | None:
        """Classify the run from the terminal event, not from the exit code.

        Claude Code exits 0 on a refusal and on a budget stop, so the exit code
        alone would publish a failed row as a success.
        """

        if not self.is_error and self.subtype == CLAUDE_CODE_SUCCESS_SUBTYPE:
            return (
                None if self.answer.strip() else LocalCliFailureClass.SCHEMA_VIOLATION
            )
        if self.subtype.startswith("error_max_turns") or self.subtype.endswith(
            "_timeout"
        ):
            return LocalCliFailureClass.TIMEOUT
        if self.api_error_status is not None:
            return LocalCliFailureClass.CRASH
        if self.stop_reason == "refusal" or self.subtype == "error_refusal":
            return LocalCliFailureClass.REFUSAL
        return LocalCliFailureClass.CRASH

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record carrying no transcript and no session id."""

        failure = self.failure_class
        return {
            "api_key_source": self.api_key_source,
            "answer_characters": len(self.answer),
            "api_error_status": self.api_error_status,
            "failure_class": None if failure is None else failure.value,
            "is_error": self.is_error,
            "model": self.model,
            "permission_mode": self.permission_mode,
            "server_side_web_requests": self.server_side_web_requests,
            "server_side_web_tools_available": list(
                self.server_side_web_tools_available
            ),
            "stop_reason": self.stop_reason,
            "subtype": self.subtype,
            "terminal_reason": self.terminal_reason,
            "tools_available": list(self.tools_available),
            "tools_used": list(self.tools_used),
            "unknown_event_types": list(self.unknown_event_types),
            "usage": self.usage.to_record(),
        }


def parse_claude_code_stream(stdout: str) -> ClaudeCodeStreamResult:
    """Parse ``--output-format stream-json`` stdout into a typed result.

    Lines that are not JSON objects are skipped rather than fatal: the CLI
    writes its diagnostics to stderr, and a lone stray line should not lose an
    otherwise complete run.  A missing terminal ``result`` event is fatal,
    because without it there is no answer and no usage to report.
    """

    events = tuple(_iter_events(stdout))
    result_event = _terminal_result_event(events)
    init_event = _init_event(events)
    return ClaudeCodeStreamResult(
        answer=_string_or_empty(result_event.get(CLAUDE_CODE_RESULT_EVENT)),
        is_error=bool(result_event.get("is_error", True)),
        subtype=_string_or_empty(result_event.get("subtype")),
        stop_reason=_optional_string(result_event.get("stop_reason")),
        terminal_reason=_optional_string(result_event.get("terminal_reason")),
        api_error_status=_optional_string(result_event.get("api_error_status")),
        model=_optional_string(init_event.get("model")),
        permission_mode=_optional_string(init_event.get("permissionMode")),
        api_key_source=_optional_string(init_event.get("apiKeySource")),
        tools_available=_string_tuple(init_event.get("tools")),
        tools_used=_tools_used(events),
        usage=_usage(result_event),
        unknown_event_types=_unknown_event_types(events),
    )


def _iter_events(stdout: str) -> Iterator[Mapping[str, Any]]:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            decoded: object = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(decoded, dict):
            yield cast(Mapping[str, Any], decoded)


def _terminal_result_event(
    events: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for event in reversed(events):
        if event.get("type") == CLAUDE_CODE_RESULT_EVENT:
            return event
    raise ClaudeCodeStreamError(
        "Claude Code stream-json stdout has no terminal result event; the run "
        "produced no answer and no usage to report"
    )


def _init_event(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    for event in events:
        if (
            event.get("type") == CLAUDE_CODE_SYSTEM_EVENT
            and event.get("subtype") == CLAUDE_CODE_INIT_SUBTYPE
        ):
            return event
    return {}


def _tools_used(events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    ordered: list[str] = []
    for event in events:
        if event.get("type") != CLAUDE_CODE_ASSISTANT_EVENT:
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = cast(Mapping[str, Any], message).get("content")
        if not isinstance(content, list):
            continue
        for item in cast(list[Any], content):
            if not isinstance(item, dict):
                continue
            block = cast(Mapping[str, Any], item)
            if block.get("type") != "tool_use":
                continue
            name = _optional_string(block.get("name"))
            if name is not None and name not in ordered:
                ordered.append(name)
    return tuple(ordered)


def _unknown_event_types(events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    seen: set[str] = set()
    for event in events:
        kind = _optional_string(event.get("type"))
        if kind is not None and kind not in _KNOWN_EVENT_TYPES:
            seen.add(kind)
    return tuple(sorted(seen))


def _usage(result_event: Mapping[str, Any]) -> ClaudeCodeUsage:
    usage = result_event.get("usage")
    record: Mapping[str, Any] = (
        cast(Mapping[str, Any], usage) if isinstance(usage, dict) else {}
    )
    reported = record.get("server_tool_use")
    server_tools: Mapping[str, Any] = (
        cast(Mapping[str, Any], reported) if isinstance(reported, dict) else {}
    )
    return ClaudeCodeUsage(
        input_tokens=_int_or_zero(record.get("input_tokens")),
        output_tokens=_int_or_zero(record.get("output_tokens")),
        cache_read_input_tokens=_int_or_zero(record.get("cache_read_input_tokens")),
        cache_creation_input_tokens=_int_or_zero(
            record.get("cache_creation_input_tokens")
        ),
        total_cost_usd=_optional_float(result_event.get("total_cost_usd")),
        num_turns=_optional_int(result_event.get("num_turns")),
        duration_ms=_optional_int(result_event.get("duration_ms")),
        web_search_requests=_int_or_zero(server_tools.get("web_search_requests")),
        web_fetch_requests=_int_or_zero(server_tools.get("web_fetch_requests")),
    )


def _string_or_empty(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast(list[Any], value) if isinstance(item, str))


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None

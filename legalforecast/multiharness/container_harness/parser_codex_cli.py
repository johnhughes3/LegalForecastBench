"""Parse Codex CLI's ``codex exec --json`` envelope into a typed run result.

The generic manifest projection in
:func:`legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
already pulls the answer out of the last ``item.completed`` / ``agent_message``
event, and that is all the canonical
:class:`~legalforecast.multiharness.spec.RunResult` needs.  This module exists
for the question the projection cannot answer: *did the harness actually behave
like a harness?*

Two halves, both evidence rather than assertion:

* **Did it use its tools?**  A tools-on lane whose runs invoke no tool has
  measured the bare API through an expensive wrapper.  ``tools_used`` is read
  off the ``item.completed`` events the transcript actually contains --
  ``command_execution``, ``file_change``, ``mcp_tool_call``, ``todo_list``.
* **Did anything reach the web?**  Codex's provider-executed retrieval surfaces
  as a ``web_search`` item, and that call runs on the provider's own
  infrastructure, downstream of every container egress rule.  These forecasts
  are about real federal cases whose outcomes are one search away, so
  ``server_side_web_calls`` counts them rather than citing the
  ``web_search="disabled"`` flag that was supposed to prevent them.

Where this differs from the Claude Code stream, and why the two parsers are
separate files rather than one polymorphic reader:

* Codex emits **no opening session event**.  There is no equivalent of Claude's
  ``system``/``init``, so the effective model, sandbox posture and approval
  policy are simply not recoverable from a transcript -- which is why the
  manifest pins ``--model`` explicitly and why nothing here reports a model.
  A tool inventory is likewise unavailable: the only proof about web tools is
  that no ``web_search`` item was produced.
* The terminal event is ``turn.completed`` (with ``usage``) on success and
  ``turn.failed`` (with ``error.message``) on failure -- two different events,
  not one event with an ``is_error`` flag.
* Codex reconnects internally on transport errors, emitting a top-level
  ``{"type": "error"}`` per attempt before it gives up.  Those are counted, not
  fatal: the adapter's own ``max_attempts`` is 1, and the count is how an
  operator sees that a "slow" run was actually a retry storm.

Unknown event and item kinds are collected and ignored rather than fatal.  The
0.151.0 stream already carries kinds this lane never exercises (``item.started``
and ``item.updated`` deltas, ``reasoning`` items), and the CLI is free to add
more; the only structural requirement is one terminal ``turn.completed`` or
``turn.failed``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass

CODEX_THREAD_STARTED_EVENT: Final[str] = "thread.started"
CODEX_TURN_STARTED_EVENT: Final[str] = "turn.started"
CODEX_TURN_COMPLETED_EVENT: Final[str] = "turn.completed"
CODEX_TURN_FAILED_EVENT: Final[str] = "turn.failed"
CODEX_ITEM_COMPLETED_EVENT: Final[str] = "item.completed"
CODEX_ERROR_EVENT: Final[str] = "error"
CODEX_AGENT_MESSAGE_ITEM: Final[str] = "agent_message"
CODEX_ERROR_ITEM: Final[str] = "error"
# The provider-executed retrieval tool.  Everything else in the item vocabulary
# runs inside the container; this one does not, so it is the only item kind the
# egress fence cannot see and the only one that can carry a case outcome back.
CODEX_SERVER_SIDE_WEB_ITEM: Final[str] = "web_search"
# The harness's own local tools, in the item vocabulary Codex 0.151.0 emits.
# ``reasoning`` and ``agent_message`` are the model talking, not a tool call.
CODEX_LOCAL_TOOL_ITEMS: Final[frozenset[str]] = frozenset(
    {"command_execution", "file_change", "mcp_tool_call", "todo_list"}
)
_KNOWN_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        CODEX_ERROR_EVENT,
        CODEX_ITEM_COMPLETED_EVENT,
        CODEX_THREAD_STARTED_EVENT,
        CODEX_TURN_COMPLETED_EVENT,
        CODEX_TURN_FAILED_EVENT,
        CODEX_TURN_STARTED_EVENT,
        "item.started",
        "item.updated",
    }
)
_KNOWN_ITEM_TYPES: Final[frozenset[str]] = (
    frozenset(
        {
            CODEX_AGENT_MESSAGE_ITEM,
            CODEX_ERROR_ITEM,
            CODEX_SERVER_SIDE_WEB_ITEM,
            "reasoning",
        }
    )
    | CODEX_LOCAL_TOOL_ITEMS
)


class CodexCliStreamError(ValueError):
    """Raised when stdout is not a ``codex exec --json`` transcript."""


@dataclass(frozen=True, slots=True)
class CodexCliUsage:
    """Token accounting for one run, as the CLI reported it.

    There is no cost field anywhere in this envelope, which is why the
    manifest's ``cost_usd_field`` is null and its ``cost_basis`` is
    ``subscription_unallocable``: a ChatGPT-subscription run has no per-run USD
    to report, and inventing one would be a number nobody measured.
    """

    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    reasoning_output_tokens: int

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record of this run's usage."""

        return {
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
        }


@dataclass(frozen=True, slots=True)
class CodexCliStreamResult:
    """One parsed Codex run: the answer, the tool evidence, and the usage."""

    answer: str
    turn_completed: bool
    terminal_error_message: str | None
    error_event_count: int
    tools_used: tuple[str, ...]
    server_side_web_calls: int
    usage: CodexCliUsage
    unknown_event_types: tuple[str, ...]
    unknown_item_types: tuple[str, ...]

    @property
    def used_any_tool(self) -> bool:
        """Return whether the harness invoked at least one of its own tools."""

        return bool(self.tools_used)

    @property
    def failure_class(self) -> LocalCliFailureClass | None:
        """Classify the run from the terminal event, not from the exit code.

        A ``turn.failed`` is the CLI's own typed failure and is reported as a
        crash: its ``error.message`` is a transport or provider string, and
        guessing a refusal or a timeout out of free text would mislabel rows.
        A completed turn that produced no agent message is a schema violation
        rather than a success, because the run has no deliverable.
        """

        if not self.turn_completed:
            return LocalCliFailureClass.CRASH
        return None if self.answer.strip() else LocalCliFailureClass.SCHEMA_VIOLATION

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record carrying no transcript and no thread id.

        ``terminal_error_message`` is deliberately absent: the observed
        messages embed provider URLs and request ids, and this record reaches a
        published summary.  Its presence is reported as a boolean instead.
        """

        failure = self.failure_class
        return {
            "error_event_count": self.error_event_count,
            "answer_characters": len(self.answer),
            "failure_class": None if failure is None else failure.value,
            "server_side_web_calls": self.server_side_web_calls,
            "terminal_error": self.terminal_error_message is not None,
            "tools_used": list(self.tools_used),
            "turn_completed": self.turn_completed,
            "unknown_event_types": list(self.unknown_event_types),
            "unknown_item_types": list(self.unknown_item_types),
            "usage": self.usage.to_record(),
        }


def parse_codex_cli_stream(stdout: str) -> CodexCliStreamResult:
    """Parse ``codex exec --json`` stdout into a typed result.

    Lines that are not JSON objects are skipped rather than fatal: the CLI
    writes ``Reading additional input from stdin...`` and its tracing lines to
    the console, and a lone stray line should not lose an otherwise complete
    run.  A stream with neither ``turn.completed`` nor ``turn.failed`` is
    fatal, because it ended without a terminal event and there is nothing
    truthful to report about it.
    """

    events = tuple(_iter_events(stdout))
    completed = _last_event(events, CODEX_TURN_COMPLETED_EVENT)
    failed = _last_event(events, CODEX_TURN_FAILED_EVENT)
    if completed is None and failed is None:
        raise CodexCliStreamError(
            "codex exec --json stdout has no terminal turn.completed or "
            "turn.failed event; the run ended without reporting an outcome"
        )
    items = tuple(_iter_completed_items(events))
    return CodexCliStreamResult(
        answer=_answer(items),
        turn_completed=completed is not None,
        terminal_error_message=_terminal_error_message(failed, items),
        error_event_count=sum(
            1 for event in events if event.get("type") == CODEX_ERROR_EVENT
        ),
        tools_used=_tools_used(items),
        server_side_web_calls=sum(
            1 for item in items if item.get("type") == CODEX_SERVER_SIDE_WEB_ITEM
        ),
        usage=_usage(completed),
        unknown_event_types=_unknown(
            (_optional_string(event.get("type")) for event in events),
            _KNOWN_EVENT_TYPES,
        ),
        unknown_item_types=_unknown(
            (_optional_string(item.get("type")) for item in items), _KNOWN_ITEM_TYPES
        ),
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


def _last_event(
    events: Sequence[Mapping[str, Any]], event_type: str
) -> Mapping[str, Any] | None:
    for event in reversed(events):
        if event.get("type") == event_type:
            return event
    return None


def _iter_completed_items(
    events: Sequence[Mapping[str, Any]],
) -> Iterator[Mapping[str, Any]]:
    for event in events:
        if event.get("type") != CODEX_ITEM_COMPLETED_EVENT:
            continue
        item = event.get("item")
        if isinstance(item, dict):
            yield cast(Mapping[str, Any], item)


def _answer(items: Sequence[Mapping[str, Any]]) -> str:
    """Return the last agent message, matching the manifest's own projection.

    Under ``--output-schema`` this text is itself a JSON document rather than
    prose, so a caller that adds schema enforcement parses it a second time.
    This lane renders argv without a schema, so it is returned verbatim.
    """

    for item in reversed(items):
        if item.get("type") == CODEX_AGENT_MESSAGE_ITEM:
            return _string_or_empty(item.get("text"))
    return ""


def _terminal_error_message(
    failed: Mapping[str, Any] | None, items: Sequence[Mapping[str, Any]]
) -> str | None:
    if failed is not None:
        error = failed.get("error")
        if isinstance(error, dict):
            message = _optional_string(cast(Mapping[str, Any], error).get("message"))
            if message is not None:
                return message
        return "codex reported turn.failed without an error message"
    for item in reversed(items):
        if item.get("type") == CODEX_ERROR_ITEM:
            return _optional_string(item.get("message"))
    return None


def _tools_used(items: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    ordered: list[str] = []
    for item in items:
        kind = _optional_string(item.get("type"))
        if kind in CODEX_LOCAL_TOOL_ITEMS and kind not in ordered:
            ordered.append(kind)
    return tuple(ordered)


def _unknown(kinds: Iterator[str | None], known: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted({kind for kind in kinds if kind is not None} - known))


def _usage(completed: Mapping[str, Any] | None) -> CodexCliUsage:
    reported = None if completed is None else completed.get("usage")
    record: Mapping[str, Any] = (
        cast(Mapping[str, Any], reported) if isinstance(reported, dict) else {}
    )
    return CodexCliUsage(
        input_tokens=_int_or_zero(record.get("input_tokens")),
        output_tokens=_int_or_zero(record.get("output_tokens")),
        cached_input_tokens=_int_or_zero(record.get("cached_input_tokens")),
        cache_write_input_tokens=_int_or_zero(record.get("cache_write_input_tokens")),
        reasoning_output_tokens=_int_or_zero(record.get("reasoning_output_tokens")),
    )


def _string_or_empty(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0

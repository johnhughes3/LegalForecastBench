"""Parse the Grok CLI's headless envelope into a typed run result.

The generic manifest projection in
:func:`legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
already pulls the answer out of the terminal ``result`` line, so this module
exists for the two things that projection cannot answer.

**Why there was no answer.**  ``grok`` exits 1 for authentication failure,
network error, quota exhaustion and ordinary runtime error alike, so the exit
code cannot tell an out-of-credit account from a logged-out one -- and on this
lane's own machine the only live evidence that exists is exactly that case:
the single permitted 2026-08-31 probe returned ``HTTP 402 Grok Build usage
balance exhausted`` and was not retried.  :class:`GrokFailureKind` gives that
failure a name of its own, so an operator reads "top up the account" rather
than "the harness crashed".  The shared
:class:`~legalforecast.multiharness.local_cli_contracts.LocalCliFailureClass`
has no billing member, so the kind rides alongside it instead of replacing it.

**Whether it behaved like a harness.**  A tools-on lane whose runs invoke no
tool has measured the bare API through an expensive wrapper, so ``tools_used``
is read off the ``tool_use`` blocks the transcript actually contains.
``server_side_web_tools_used`` names xAI's provider-executed ``web_search`` /
``web_fetch`` separately: those run downstream of every container egress rule.

One reader handles both envelopes the CLI writes to stdout -- the NDJSON of
``--output-format streaming-messages-json`` and the single ``{"type":
"error"}`` object a run that never reached the model prints -- because that
error object is itself a legal one-line NDJSON stream.  Unknown event kinds
are collected in ``unknown_event_types`` and ignored.

PENDING LIVE VERIFICATION: only the error path was ever observed.  The success
path is transcribed from the CLI's bundled documentation, so a first
successful run is the confirmation, not this module.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, cast

from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass

GROK_RESULT_EVENT: Final[str] = "result"
GROK_ERROR_EVENT: Final[str] = "error"
GROK_SYSTEM_EVENT: Final[str] = "system"
GROK_ASSISTANT_EVENT: Final[str] = "assistant"
GROK_INIT_SUBTYPE: Final[str] = "init"
GROK_SUCCESS_SUBTYPE: Final[str] = "success"
# xAI's own ids for provider-executed retrieval, as the 1.0.13 binary spells
# them; ``--disable-web-search`` turns off both, and this is the evidence.
SERVER_SIDE_WEB_TOOLS: Final[frozenset[str]] = frozenset({"web_fetch", "web_search"})
_KNOWN_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        GROK_ASSISTANT_EVENT,
        GROK_ERROR_EVENT,
        GROK_RESULT_EVENT,
        GROK_SYSTEM_EVENT,
        "user",
    }
)


class GrokStreamError(ValueError):
    """Raised when stdout is not a Grok headless transcript at all."""


class GrokFailureKind(StrEnum):
    """Why a Grok run produced no answer, at the granularity an operator acts on.

    ``QUOTA_EXHAUSTED`` is an account state rather than a defect, and it is
    the state this machine is in.  The rest come from the error vocabulary
    carried in the 1.0.13 binary.
    """

    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    AUTH = "auth"
    PROVIDER_ERROR = "provider_error"
    MAX_TURNS = "max_turns"
    REFUSAL = "refusal"
    EMPTY_ANSWER = "empty_answer"
    UNKNOWN_ERROR = "unknown_error"


# An HTTP status decides on its own; substrings are the fallback path for a
# message that carried no status.
_STATUS_KINDS: Final[Mapping[int, GrokFailureKind]] = {
    401: GrokFailureKind.AUTH,
    402: GrokFailureKind.QUOTA_EXHAUSTED,
    403: GrokFailureKind.AUTH,
    429: GrokFailureKind.RATE_LIMITED,
    500: GrokFailureKind.PROVIDER_ERROR,
    502: GrokFailureKind.PROVIDER_ERROR,
    503: GrokFailureKind.PROVIDER_ERROR,
}
_MESSAGE_KINDS: Final[tuple[tuple[GrokFailureKind, tuple[str, ...]], ...]] = (
    (
        GrokFailureKind.QUOTA_EXHAUSTED,
        (
            "usage balance exhausted",
            "run out of credits",
            "out of credits",
            "spending limit",
            "usage limit reached",
            "you hit your weekly limit",
            "you hit your free usage limit",
        ),
    ),
    (
        GrokFailureKind.RATE_LIMITED,
        ("too many requests", "rate limit"),
    ),
    (
        GrokFailureKind.AUTH,
        ("not signed in", "not logged in", "unauthorized", "authentication"),
    ),
    (
        GrokFailureKind.PROVIDER_ERROR,
        ("internal server error", "the service is busy"),
    ),
)


@dataclass(frozen=True, slots=True)
class GrokUsage:
    """Token and cost accounting for one run, as the CLI reported it.

    When ``cost_is_partial`` is set the CLI omits every cost float, so a zero
    means "not reported" rather than "free" -- which is why the lane's cost
    basis is ``subscription_unallocable``.
    """

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    reasoning_tokens: int
    total_cost_usd: float | None
    num_turns: int | None
    duration_ms: int | None
    cost_is_partial: bool
    usage_is_incomplete: bool

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record of this run's usage."""

        return {
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cost_is_partial": self.cost_is_partial,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "num_turns": self.num_turns,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_cost_usd": self.total_cost_usd,
            "usage_is_incomplete": self.usage_is_incomplete,
        }


@dataclass(frozen=True, slots=True)
class GrokRunResult:
    """One parsed Grok run: the answer, the posture, the usage, the failure."""

    answer: str
    is_error: bool
    subtype: str
    stop_reason: str | None
    error_kind: GrokFailureKind | None
    http_status: int | None
    error_message: str | None
    model: str | None
    tools_available: tuple[str, ...]
    tools_used: tuple[str, ...]
    usage: GrokUsage
    unknown_event_types: tuple[str, ...]

    @property
    def server_side_web_tools_available(self) -> tuple[str, ...]:
        """Return the provider-executed web tools the run could have called."""

        return tuple(sorted(SERVER_SIDE_WEB_TOOLS.intersection(self.tools_available)))

    @property
    def server_side_web_tools_used(self) -> tuple[str, ...]:
        """Return the provider-executed web tools the run actually called.

        Non-empty means an outcome could have come back over a channel the
        egress fence never sees, whatever ``--disable-web-search`` intended.
        """

        return tuple(sorted(SERVER_SIDE_WEB_TOOLS.intersection(self.tools_used)))

    @property
    def used_any_tool(self) -> bool:
        """Return whether the harness invoked at least one of its own tools."""

        return bool(self.tools_used)

    @property
    def failure_kind(self) -> GrokFailureKind | None:
        """Return the run's typed failure, or None when it produced an answer."""

        if self.error_kind is not None:
            return self.error_kind
        if not self.is_error and self.subtype == GROK_SUCCESS_SUBTYPE:
            return None if self.answer.strip() else GrokFailureKind.EMPTY_ANSWER
        if self.subtype.startswith("error_max_turns") or self.stop_reason in {
            "max_turn_requests",
            "max_tokens",
        }:
            return GrokFailureKind.MAX_TURNS
        if self.stop_reason == "refusal" or self.subtype == "error_refusal":
            return GrokFailureKind.REFUSAL
        return GrokFailureKind.UNKNOWN_ERROR

    @property
    def failure_class(self) -> LocalCliFailureClass | None:
        """Map the typed kind onto the shared closed taxonomy.

        Quota, rate limiting and authentication all land on ``crash``: the
        shared enum has no billing member.  That is lossy on purpose --
        ``failure_kind`` carries the distinction, and widening a schema the
        official lane also uses is not this lane's call.
        """

        kind = self.failure_kind
        if kind is None:
            return None
        if kind is GrokFailureKind.MAX_TURNS:
            return LocalCliFailureClass.TIMEOUT
        if kind is GrokFailureKind.REFUSAL:
            return LocalCliFailureClass.REFUSAL
        if kind is GrokFailureKind.EMPTY_ANSWER:
            return LocalCliFailureClass.SCHEMA_VIOLATION
        return LocalCliFailureClass.CRASH

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record carrying no transcript and no session id."""

        failure = self.failure_class
        kind = self.failure_kind
        return {
            "answer_characters": len(self.answer),
            "error_kind": None if kind is None else kind.value,
            "failure_class": None if failure is None else failure.value,
            "http_status": self.http_status,
            "is_error": self.is_error,
            "model": self.model,
            "server_side_web_tools_available": list(
                self.server_side_web_tools_available
            ),
            "server_side_web_tools_used": list(self.server_side_web_tools_used),
            "stop_reason": self.stop_reason,
            "subtype": self.subtype,
            "tools_available": list(self.tools_available),
            "tools_used": list(self.tools_used),
            "unknown_event_types": list(self.unknown_event_types),
            "usage": self.usage.to_record(),
        }


def parse_grok_stream(stdout: str) -> GrokRunResult:
    """Parse Grok headless stdout into a typed result.

    Lines that are not JSON objects are skipped rather than fatal: diagnostics
    go to stderr, and one stray line should not lose an otherwise complete
    run.  A stream with neither an error object nor a terminal ``result``
    event is fatal, because there is then no answer and no failure to report.
    """

    events = tuple(_iter_events(stdout))
    for event in events:
        if event.get("type") == GROK_ERROR_EVENT:
            return _error_result(event, events)
    result_event = _terminal_result_event(events)
    init_event = _init_event(events)
    return GrokRunResult(
        answer=_string_or_empty(result_event.get(GROK_RESULT_EVENT)),
        is_error=bool(result_event.get("is_error", True)),
        subtype=_string_or_empty(result_event.get("subtype")),
        stop_reason=_stop_reason(result_event),
        error_kind=None,
        http_status=None,
        error_message=None,
        model=_model(init_event, result_event),
        tools_available=_string_tuple(init_event.get("tools")),
        tools_used=_tools_used(events),
        usage=_usage(result_event),
        unknown_event_types=_unknown_event_types(events),
    )


def classify_grok_error(message: str, http_status: int | None) -> GrokFailureKind:
    """Classify one Grok error message, preferring the HTTP status it carries."""

    if http_status is not None:
        kind = _STATUS_KINDS.get(http_status)
        if kind is not None:
            return kind
    lowered = message.casefold()
    for kind, markers in _MESSAGE_KINDS:
        if any(marker in lowered for marker in markers):
            return kind
    return GrokFailureKind.UNKNOWN_ERROR


def _error_result(
    event: Mapping[str, Any], events: Sequence[Mapping[str, Any]]
) -> GrokRunResult:
    outer = _string_or_empty(event.get("message"))
    message, status = _embedded_error(outer)
    return GrokRunResult(
        answer="",
        is_error=True,
        subtype=GROK_ERROR_EVENT,
        stop_reason=None,
        error_kind=classify_grok_error(message, status),
        http_status=status,
        error_message=message,
        model=None,
        tools_available=(),
        tools_used=_tools_used(events),
        usage=_usage({}),
        unknown_event_types=_unknown_event_types(events),
    )


def _embedded_error(message: str) -> tuple[str, int | None]:
    """Return the inner message and HTTP status from Grok's nested error blob.

    The CLI reports ``Internal error: `` followed by a pretty-printed JSON
    object.  It is decoded from the first ``{`` rather than matched with a
    greedy ``{.*}``, which breaks the moment a message carries trailing prose.
    """

    start = message.find("{")
    if start < 0:
        return message, None
    try:
        decoded, _end = json.JSONDecoder().raw_decode(message, start)
    except ValueError:
        return message, None
    if not isinstance(decoded, dict):
        return message, None
    blob = cast(Mapping[str, Any], decoded)
    inner = _optional_string(blob.get("message"))
    return inner if inner is not None else message, _optional_int(
        blob.get("http_status")
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
        if event.get("type") == GROK_RESULT_EVENT:
            return event
    raise GrokStreamError(
        "Grok stdout carries neither an error object nor a terminal result "
        "event; the run produced no answer and no failure to report"
    )


def _init_event(events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    for event in events:
        if (
            event.get("type") == GROK_SYSTEM_EVENT
            and event.get("subtype") == GROK_INIT_SUBTYPE
        ):
            return event
    return {}


def _model(
    init_event: Mapping[str, Any], result_event: Mapping[str, Any]
) -> str | None:
    declared = _optional_string(init_event.get("model"))
    if declared is not None:
        return declared
    # modelUsage is keyed by the model actually billed -- the stronger identity
    # when the init line is absent.
    usage = result_event.get("modelUsage")
    if isinstance(usage, dict):
        names = sorted(cast(Mapping[str, Any], usage))
        if names:
            return names[0]
    return None


def _stop_reason(result_event: Mapping[str, Any]) -> str | None:
    # snake_case is the streaming-messages-json spelling, camelCase the
    # single-object json one; reading both keeps one parser for both.
    return _optional_string(result_event.get("stop_reason")) or _optional_string(
        result_event.get("stopReason")
    )


def _tools_used(events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    ordered: list[str] = []
    for event in events:
        if event.get("type") != GROK_ASSISTANT_EVENT:
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


def _usage(result_event: Mapping[str, Any]) -> GrokUsage:
    usage = result_event.get("usage")
    record: Mapping[str, Any] = (
        cast(Mapping[str, Any], usage) if isinstance(usage, dict) else {}
    )
    return GrokUsage(
        input_tokens=_int_or_zero(record.get("input_tokens")),
        output_tokens=_int_or_zero(record.get("output_tokens")),
        cache_read_input_tokens=_int_or_zero(record.get("cache_read_input_tokens")),
        cache_creation_input_tokens=_int_or_zero(
            record.get("cache_creation_input_tokens")
        ),
        reasoning_tokens=_int_or_zero(record.get("reasoning_tokens")),
        total_cost_usd=_optional_float(result_event.get("total_cost_usd")),
        num_turns=_optional_int(result_event.get("num_turns")),
        duration_ms=_optional_int(result_event.get("duration_ms")),
        cost_is_partial=bool(result_event.get("cost_is_partial", False)),
        usage_is_incomplete=bool(result_event.get("usage_is_incomplete", False)),
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

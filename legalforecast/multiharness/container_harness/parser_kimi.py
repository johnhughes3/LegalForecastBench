"""Parse Kimi Code's ``stream-json`` envelope into a typed run result.

Kimi is the outlier of the containerized tools-on family, and every deviation
here is forced by the CLI rather than chosen:

* **There is no terminal event.**  Claude Code closes every run with one
  ``result`` event carrying the answer, the usage and an ``is_error`` flag, so
  its parser can classify from a single record.  Kimi's writer emits
  OpenAI-chat-shaped lines keyed on ``role`` and simply stops.  Success here is
  "a final assistant line carried text", and everything else is a failure this
  module has to name.
* **The lines are keyed on ``role``, not ``type``.**  Only ``meta`` lines carry
  a ``type``, and ``goal.summary`` lines carry no ``role`` at all.  That is why
  :func:`legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
  -- which matches ``event["type"]`` -- cannot project this harness today, and
  why the answer accessor lives here.  See ``parse_kimi_stream``.
* **Nothing reports usage.**  The writer has no usage code path at all, so a
  run's token and cost accounting is simply absent rather than zero; the
  manifest declares ``unreported.*`` field paths and this module reports no
  numbers rather than inventing them.

EVIDENCE CLASS, STATED UP FRONT.  The meta-line shapes below are live-verified
bytes from the 2026-08-31 characterization.  The *assistant* line shape and the
final-text accessor are derived from the CLI's bundled writer source and have
never been observed live, because the provider returned HTTP 500 to every
attempt during characterization.  Treat ``answer`` as pending live
verification until a successful run has been seen.

Two failure modes get explicit names because both otherwise publish a wrong
number as a right one:

* **The empty successful run.**  Kimi's update preflight runs in print mode and
  on one branch calls ``process.exit(0)`` with no output whatsoever.  Exit 0
  plus empty stdout is not an empty answer; it is a crash, and
  :attr:`KimiStreamResult.failure_class` says so.
* **The retry ladder.**  A failing turn is retried internally up to ten times
  with exponential backoff and no flag caps it, so one invocation can spend
  minutes on a sick provider and then produce nothing.  Those
  ``turn.step.retrying`` lines are counted and surfaced instead of discarded:
  they are the only in-band evidence that the run met a provider fault rather
  than a model refusal.

Parsing is permissive by design.  Unknown ``meta`` types and lines with no
``role`` are collected and ignored rather than raising, because this envelope
is a young one and a lane that dies on an unrecognised line loses runs it
already paid for.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass

KIMI_ASSISTANT_ROLE: Final[str] = "assistant"
KIMI_META_ROLE: Final[str] = "meta"
KIMI_TOOL_ROLE: Final[str] = "tool"
KIMI_VERSION_EVENT: Final[str] = "system.version"
KIMI_RETRY_EVENT: Final[str] = "turn.step.retrying"
KIMI_SESSION_RESUME_EVENT: Final[str] = "session.resume_hint"
_KNOWN_META_TYPES: Final[frozenset[str]] = frozenset(
    {KIMI_VERSION_EVENT, KIMI_RETRY_EVENT, KIMI_SESSION_RESUME_EVENT}
)
# Kimi's two retrieval tools.  They are executed by the CLI, but their service
# base URLs default to the SAME host as the completion API, so the container's
# host-level egress allowlist cannot fence them and the image redirects them at
# a non-allowlisted .invalid host instead.  A run that names either of these in
# a tool call is evidence the redirect did not hold, whatever the manifest's
# server_side_web_tools_disabled capability claims.
KIMI_WEB_TOOLS: Final[frozenset[str]] = frozenset({"FetchURL", "WebSearch"})


class KimiStreamError(ValueError):
    """Raised when stdout is not a Kimi Code ``stream-json`` transcript."""


@dataclass(frozen=True, slots=True)
class KimiRetryLadder:
    """What the CLI's internal retry ladder did during one invocation.

    ``max_attempts`` is the ceiling the CLI reported, not one this lane chose:
    the manifest's ``max_attempts`` of 1 governs how many times *we* invoke the
    CLI, and nothing caps how many times the CLI re-calls the provider inside a
    single invocation.  The only guard is the run timeout.
    """

    attempts_observed: int
    max_attempts: int | None
    last_error_name: str | None
    last_status_code: int | None
    total_backoff_ms: float

    @property
    def retried(self) -> bool:
        """Return whether the CLI re-called the provider inside this run."""

        return self.attempts_observed > 0

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record with no provider message text.

        The error *name* and status code classify the fault; the provider's
        prose message is dropped because this record reaches a public summary.
        """

        return {
            "attempts_observed": self.attempts_observed,
            "last_error_name": self.last_error_name,
            "last_status_code": self.last_status_code,
            "max_attempts": self.max_attempts,
            "total_backoff_ms": self.total_backoff_ms,
        }


@dataclass(frozen=True, slots=True)
class KimiStreamResult:
    """One parsed Kimi Code run: the answer, the tool posture, the faults."""

    answer: str
    version: str | None
    tools_used: tuple[str, ...]
    web_tools_invoked: tuple[str, ...]
    retry: KimiRetryLadder
    assistant_lines: int
    tool_result_lines: int
    unknown_meta_types: tuple[str, ...]
    roleless_lines: int

    @property
    def used_any_tool(self) -> bool:
        """Return whether the harness invoked at least one of its own tools."""

        return bool(self.tools_used)

    @property
    def web_retrieval_requests(self) -> int:
        """Return how many retrieval calls the run actually made.

        Zero is the evidence that the image's base-URL redirect held.  A
        non-zero count means a run could have read the case outcome, whatever
        the manifest declared.
        """

        return len(self.web_tools_invoked)

    @property
    def reports_usage(self) -> bool:
        """Return whether this envelope carries token or cost accounting.

        Always ``False``.  It is a property rather than a comment so a caller
        that needs usage fails against a stated fact instead of reading zeros
        as a measurement.
        """

        return False

    @property
    def failure_class(self) -> LocalCliFailureClass | None:
        """Classify the run from the stream shape; there is no result event.

        Order matters.  Empty stdout is checked first because it is the
        auto-update ``process.exit(0)`` envelope, which exits *successfully*
        and would otherwise be read as an empty answer.  A retry ladder with no
        answer is a provider fault (``crash``), not a refusal: the CLI only
        retries errors it classified as retryable.
        """

        if self.answer.strip():
            return None
        if self.assistant_lines == 0 and self.version is None:
            return LocalCliFailureClass.CRASH
        if self.retry.retried:
            return LocalCliFailureClass.CRASH
        return LocalCliFailureClass.SCHEMA_VIOLATION

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record carrying no transcript and no session id."""

        failure = self.failure_class
        return {
            "answer_characters": len(self.answer),
            "assistant_lines": self.assistant_lines,
            "failure_class": None if failure is None else failure.value,
            "reports_usage": self.reports_usage,
            "retry": self.retry.to_record(),
            "roleless_lines": self.roleless_lines,
            "tool_result_lines": self.tool_result_lines,
            "tools_used": list(self.tools_used),
            "unknown_meta_types": list(self.unknown_meta_types),
            "version": self.version,
            "web_retrieval_requests": self.web_retrieval_requests,
            "web_tools_invoked": list(self.web_tools_invoked),
        }


def parse_kimi_stream(stdout: str) -> KimiStreamResult:
    """Parse ``--output-format stream-json`` stdout into a typed result.

    Completely empty stdout is fatal, because that is the shape of a run that
    never started -- the CLI writes its version line before anything else.
    Anything else is parsed for what it holds: a run that hit the provider's
    retry ladder and died has no answer but does have evidence, and losing it
    to an exception would leave the operator guessing.
    """

    events = tuple(_iter_events(stdout))
    if not events:
        raise KimiStreamError(
            "Kimi Code stream-json stdout carried no JSON lines; the CLI writes "
            "a system.version line before anything else, so the process "
            "produced no transcript at all"
        )
    tools, web_tools = _tools_used(events)
    return KimiStreamResult(
        answer=_final_answer(events),
        version=_version(events),
        tools_used=tools,
        web_tools_invoked=web_tools,
        retry=_retry_ladder(events),
        assistant_lines=sum(
            1 for event in events if event.get("role") == KIMI_ASSISTANT_ROLE
        ),
        tool_result_lines=sum(
            1 for event in events if event.get("role") == KIMI_TOOL_ROLE
        ),
        unknown_meta_types=_unknown_meta_types(events),
        roleless_lines=sum(1 for event in events if "role" not in event),
    )


def kimi_deliverable_text(stdout: str) -> str:
    """Return the run's final answer, or refuse a transcript that has none.

    This is the accessor the generic manifest projection cannot express: it
    matches on ``role``, where
    :func:`~legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
    matches on ``type``.  Until that helper can be told which key discriminates
    an event, a caller wanting Kimi's deliverable must come through here.
    """

    answer = parse_kimi_stream(stdout).answer
    if not answer.strip():
        raise KimiStreamError(
            "Kimi Code stream-json stdout has no assistant line carrying text; "
            "the run produced no answer"
        )
    return answer


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


def _final_answer(events: Sequence[Mapping[str, Any]]) -> str:
    """Return the last assistant line's text.

    ``content`` is omitted entirely on a tool-call-only flush, and hook output
    is emitted as an assistant line too, so the rule is the *last* assistant
    line that actually carried text -- not the last assistant line, and not the
    first.
    """

    for event in reversed(events):
        if event.get("role") != KIMI_ASSISTANT_ROLE:
            continue
        content = event.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return ""


def _version(events: Sequence[Mapping[str, Any]]) -> str | None:
    for event in events:
        if _meta_type(event) == KIMI_VERSION_EVENT:
            return _optional_string(event.get("version"))
    return None


def _tools_used(
    events: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ordered: list[str] = []
    for event in events:
        if event.get("role") != KIMI_ASSISTANT_ROLE:
            continue
        calls = event.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for item in cast(list[Any], calls):
            if not isinstance(item, dict):
                continue
            function = cast(Mapping[str, Any], item).get("function")
            if not isinstance(function, dict):
                continue
            name = _optional_string(cast(Mapping[str, Any], function).get("name"))
            if name is not None and name not in ordered:
                ordered.append(name)
    web = tuple(sorted(KIMI_WEB_TOOLS.intersection(ordered)))
    return tuple(ordered), web


def _retry_ladder(events: Sequence[Mapping[str, Any]]) -> KimiRetryLadder:
    attempts = 0
    max_attempts: int | None = None
    error_name: str | None = None
    status_code: int | None = None
    backoff = 0.0
    for event in events:
        if _meta_type(event) != KIMI_RETRY_EVENT:
            continue
        attempts += 1
        max_attempts = _optional_int(event.get("max_attempts")) or max_attempts
        error_name = _optional_string(event.get("error_name")) or error_name
        status_code = _optional_int(event.get("status_code")) or status_code
        delay = event.get("delay_ms")
        if isinstance(delay, (int, float)) and not isinstance(delay, bool):
            backoff += float(delay)
    return KimiRetryLadder(
        attempts_observed=attempts,
        max_attempts=max_attempts,
        last_error_name=error_name,
        last_status_code=status_code,
        total_backoff_ms=backoff,
    )


def _unknown_meta_types(events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    seen: set[str] = set()
    for event in events:
        kind = _meta_type(event)
        if kind is not None and kind not in _KNOWN_META_TYPES:
            seen.add(kind)
    return tuple(sorted(seen))


def _meta_type(event: Mapping[str, Any]) -> str | None:
    """Return a ``meta`` line's type, ignoring lines that are not meta.

    ``goal.summary`` lines carry a ``type`` and no ``role`` at all, so keying
    on ``type`` alone would misread one as a meta event.
    """

    if event.get("role") != KIMI_META_ROLE:
        return None
    return _optional_string(event.get("type"))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

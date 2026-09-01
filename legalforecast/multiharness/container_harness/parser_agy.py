"""Parse the Antigravity CLI (``agy``) ``--output-format json`` envelope.

The generic manifest projection in
:func:`legalforecast.multiharness.local_cli_manifest.project_structured_stdout_deliverable`
already lifts ``.response`` out of this envelope, and that is all the canonical
:class:`~legalforecast.multiharness.spec.RunResult` needs.  This module exists
for the run-quality questions the projection cannot answer -- and, just as
importantly, to say plainly which of those questions ``agy`` cannot answer at
all.

What the envelope does give, characterised live on 2026-08-31 from agy 1.1.22:
a single-line JSON object with eight keys -- ``conversation_id``, ``status``,
``response``, ``duration_seconds``, ``num_turns``, ``structured_output``,
``json_schema`` and ``usage`` -- where ``usage`` carries ``input_tokens``,
``output_tokens``, ``thinking_tokens``, ``cache_read_tokens`` and
``total_tokens``.  A ninth key, ``error``, appears on the failure path; it was
found by the first containerized run rather than by that census, which is
precisely what the unknown-key tolerance below is for.

What it does not give, and what therefore cannot be evidenced per run:

* **Which model served the run.**  There is no ``model`` key anywhere in the
  envelope, so model provenance is *request-side only*: the manifest pins
  ``--model`` and the result records what was asked for.  This matters because
  agy's own default model is read from mutable per-user state rather than
  compiled in.
* **Whether the harness used its tools.**  Unlike Claude Code's stream-json
  transcript, this envelope contains no tool inventory and no tool-call
  records, so :attr:`AntigravityResult.tools_used` is empty for every run and
  is not evidence that no tool ran.  ``num_turns`` above one is the only hint,
  and it is a hint, not a count.
* **Whether web retrieval was available.**  The fence itself is no longer
  open -- the harness image seeds a ``PreToolUse`` lifecycle hook that hard-
  blocks ``search_web``, ``read_url_content`` and the browser tools, which
  matters because ``search_web`` is dispatched by the CLI but executed
  upstream and so runs downstream of every container egress rule.  What this
  envelope cannot do is *evidence* that fence: it carries no tool inventory
  and no server-tool counters, so a run proves the block from the denial
  journal the hook writes into the workspace and from the gap the blocked call
  leaves in agy's own transcript, never from anything read here.

Parsing is deliberately permissive about shape and strict about outcome.
Unknown top-level keys are collected by name in ``unknown_fields`` and ignored,
so an upstream addition does not fail a run; an unknown ``status``, by
contrast, classifies as a crash rather than passing through as a success.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

from legalforecast.multiharness.local_cli_contracts import LocalCliFailureClass

AGY_SUCCESS_STATUS: Final[str] = "SUCCESS"
# Every literal the 1.1.22 binary carries.  Only SUCCESS has been observed
# live, which is why the mapping below is explicit per literal and fails closed
# on anything else rather than guessing from a substring.
AGY_STATUSES: Final[frozenset[str]] = frozenset(
    {"SUCCESS", "FAILURE", "ERROR", "TIMEOUT", "CANCELLED", "DENIED"}
)
_STATUS_FAILURES: Final[Mapping[str, LocalCliFailureClass]] = {
    # A print-mode timeout is agy's own --print-timeout firing, which is the
    # only turn budget it has: there is no --max-turns.
    "TIMEOUT": LocalCliFailureClass.TIMEOUT,
    "CANCELLED": LocalCliFailureClass.CANCELLED,
    # DENIED is a tool-permission denial (agy's headless soft-denial path), not
    # a model refusal.  agy publishes no refusal status at all, so a model that
    # declines the task still comes back as SUCCESS carrying refusal prose --
    # that is a scoring question, not one this parser can answer.
    "DENIED": LocalCliFailureClass.SANDBOX_DENIAL,
    "FAILURE": LocalCliFailureClass.CRASH,
    "ERROR": LocalCliFailureClass.CRASH,
}
_KNOWN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "conversation_id",
        "duration_seconds",
        "error",
        "json_schema",
        "num_turns",
        "response",
        "status",
        "structured_output",
        "usage",
    }
)
# agy's model provenance is what the manifest asked for, never what the
# envelope reported, because the envelope reports nothing.
MODEL_PROVENANCE_REQUEST_SIDE: Final[str] = "request_side_only"


class AntigravityJsonError(ValueError):
    """Raised when stdout is not an ``agy --output-format json`` envelope."""


@dataclass(frozen=True, slots=True)
class AntigravityUsage:
    """Token and turn accounting for one run, as the CLI reported it.

    There is no cost field and no cache-write field in this envelope; the
    manifest's ``cost_basis`` is ``subscription_unallocable`` for that reason.
    """

    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cache_read_tokens: int
    total_tokens: int
    num_turns: int | None
    duration_seconds: float | None

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record of this run's usage."""

        return {
            "cache_read_tokens": self.cache_read_tokens,
            "duration_seconds": self.duration_seconds,
            "input_tokens": self.input_tokens,
            "num_turns": self.num_turns,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class AntigravityResult:
    """One parsed ``agy`` run: the answer, the outcome, and the usage."""

    answer: str
    status: str
    error_detail: str | None
    structured_output: Mapping[str, Any] | None
    usage: AntigravityUsage
    unknown_fields: tuple[str, ...]

    @property
    def model(self) -> None:
        """Return ``None``: the envelope names no model.  Always.

        Kept as an explicit property rather than omitted so a caller that reads
        ``model`` off a harness result gets a documented absence instead of an
        ``AttributeError`` that invites someone to fill it in from the request.
        """

        return None

    @property
    def model_provenance(self) -> str:
        """Return how a caller may attribute this run's model."""

        return MODEL_PROVENANCE_REQUEST_SIDE

    @property
    def tools_used(self) -> tuple[str, ...]:
        """Return ``()``: this envelope records no tool calls at all.

        Empty here means *unreported*, not *unused*.  A tools-on lane needs
        behavioural proof instead -- a workspace file only a tool could have
        read -- which is what the live smoke prompt is for.
        """

        return ()

    @property
    def reports_tool_use(self) -> bool:
        """Return whether this harness reports tool use per run.  It does not."""

        return False

    @property
    def failure_class(self) -> LocalCliFailureClass | None:
        """Classify the run from ``status``, not from the exit code.

        Fails closed: a status literal this parser has never seen classifies as
        a crash rather than being waved through as a success.
        """

        if self.status == AGY_SUCCESS_STATUS:
            return (
                None if self.answer.strip() else LocalCliFailureClass.SCHEMA_VIOLATION
            )
        return _STATUS_FAILURES.get(self.status, LocalCliFailureClass.CRASH)

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready record carrying no transcript and no session id.

        ``conversation_id`` is deliberately absent: it is a session identifier,
        it keys agy's on-disk conversation and transcript tree, and this record
        is published.  So is the ``error`` text, for a sharper reason: the
        first containerized run's error string embedded a Google user-content
        URL carrying an account-scoped identifier for the logged-in operator.
        Whether an error was reported is publishable; what it said is not.
        """

        failure = self.failure_class
        return {
            "answer_characters": len(self.answer),
            "error_reported": self.error_detail is not None,
            "failure_class": None if failure is None else failure.value,
            "model": self.model,
            "model_provenance": self.model_provenance,
            "reports_tool_use": self.reports_tool_use,
            "status": self.status,
            "status_is_declared": self.status in AGY_STATUSES,
            "structured_output_present": self.structured_output is not None,
            "tools_used": list(self.tools_used),
            "unknown_fields": list(self.unknown_fields),
            "usage": self.usage.to_record(),
        }


def parse_antigravity_json(stdout: str) -> AntigravityResult:
    """Parse ``--output-format json`` stdout into a typed result.

    The whole envelope is one line, but the CLI is free to print a diagnostic
    line beside it, so the last decodable JSON object carrying a ``status`` key
    wins.  Stdout with no such object is fatal: without it there is no outcome
    and no usage to report.
    """

    envelope = _envelope(stdout)
    return AntigravityResult(
        answer=_string_or_empty(envelope.get("response")),
        status=_string_or_empty(envelope.get("status")),
        error_detail=_optional_string(envelope.get("error")),
        structured_output=_optional_mapping(envelope.get("structured_output")),
        usage=_usage(envelope),
        unknown_fields=tuple(sorted(set(envelope).difference(_KNOWN_FIELDS))),
    )


def _envelope(stdout: str) -> Mapping[str, Any]:
    found: Mapping[str, Any] | None = None
    for candidate in (stdout, *stdout.splitlines()):
        stripped = candidate.strip()
        if not stripped:
            continue
        try:
            decoded: object = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(decoded, dict) and "status" in decoded:
            found = cast(Mapping[str, Any], decoded)
    if found is None:
        raise AntigravityJsonError(
            "agy json stdout has no result envelope; the run produced no status "
            "and no usage to report"
        )
    return found


def _usage(envelope: Mapping[str, Any]) -> AntigravityUsage:
    reported = envelope.get("usage")
    record: Mapping[str, Any] = (
        cast(Mapping[str, Any], reported) if isinstance(reported, dict) else {}
    )
    return AntigravityUsage(
        input_tokens=_int_or_zero(record.get("input_tokens")),
        output_tokens=_int_or_zero(record.get("output_tokens")),
        thinking_tokens=_int_or_zero(record.get("thinking_tokens")),
        cache_read_tokens=_int_or_zero(record.get("cache_read_tokens")),
        total_tokens=_int_or_zero(record.get("total_tokens")),
        num_turns=_optional_int(envelope.get("num_turns")),
        duration_seconds=_optional_float(envelope.get("duration_seconds")),
    )


def _string_or_empty(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_mapping(value: object) -> Mapping[str, Any] | None:
    return cast(Mapping[str, Any], value) if isinstance(value, dict) else None


def _int_or_zero(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None

"""Read each harness's own transcript for the tools it actually invoked.

The lane's whole claim is that a harness beats the bare API *because it used
its tools*, so the tool evidence has to come from the harness's own machine
output rather than from an assumption.  Each containerized harness already has
a committed parser for its envelope; this module is the one place that maps an
executable basename to its parser and normalizes the answer.

Two properties matter more than convenience:

* **No blanket zero.**  Antigravity's JSON envelope names no tools at all, so
  its accounting is reported as ``unreported`` rather than as "zero tools were
  used".  A zero that means "the harness does not say" and a zero that means
  "the harness used nothing" are different claims, and only one of them is
  true here.
* **Distinct names, said out loud.**  Every parser deduplicates tool names, so
  what is available is the set of distinct tools invoked, not a call count.
  The release receipt's ``tools.call_count`` is that number and its
  ``tools.policy`` string says so, because a receipt field named "call_count"
  carrying a distinct-name count is otherwise a quiet overstatement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

TOOL_USE_REPORTED: Final = "distinct_tool_names"
TOOL_USE_UNREPORTED: Final = "unreported"
TOOL_POLICY_PREFIX: Final = "native_cli_builtins"


class ToolAccountingError(ValueError):
    """Raised when a harness has no declared way to report its tool use."""


@dataclass(frozen=True, slots=True)
class HarnessFenceObservation:
    """Whether this run's own transcript shows native tools on and web tools off.

    Both booleans are observations, not capability claims.  ``observable`` is
    false when the envelope cannot answer (Antigravity names no tools) or when
    the transcript does not parse; callers must not publish ``True`` for a
    field they could not read.
    """

    native_tools_enabled: bool
    server_side_web_tools_disabled: bool
    web_tools_available: tuple[str, ...]
    web_request_count: int
    observable: bool

    @property
    def web_open(self) -> bool:
        """Return whether provider-executed web retrieval was available or used."""

        return bool(self.web_tools_available) or self.web_request_count > 0


@dataclass(frozen=True, slots=True)
class HarnessToolUse:
    """Distinct native tools one harness reported invoking, if it reports any."""

    tools: tuple[str, ...]
    reporting: str

    @property
    def reported(self) -> bool:
        """Return whether the harness's envelope carries tool evidence at all."""

        return self.reporting == TOOL_USE_REPORTED

    @property
    def policy(self) -> str:
        """Return the receipt tool-policy string that names this evidence class."""

        return f"{TOOL_POLICY_PREFIX}:{self.reporting}"

    @property
    def call_count(self) -> int:
        """Return the receipt's ``tools.call_count`` for this evidence class."""

        return len(self.tools)


def _claude(stdout: str) -> tuple[str, ...]:
    from legalforecast.multiharness.container_harness.parsers import (
        parse_claude_code_stream,
    )

    return parse_claude_code_stream(stdout).tools_used


def _codex(stdout: str) -> tuple[str, ...]:
    from legalforecast.multiharness.container_harness.parser_codex_cli import (
        parse_codex_cli_stream,
    )

    return parse_codex_cli_stream(stdout).tools_used


def _grok(stdout: str) -> tuple[str, ...]:
    from legalforecast.multiharness.container_harness.parser_grok import (
        parse_grok_stream,
    )

    return parse_grok_stream(stdout).tools_used


def _kimi(stdout: str) -> tuple[str, ...]:
    from legalforecast.multiharness.container_harness.parser_kimi import (
        parse_kimi_stream,
    )

    return parse_kimi_stream(stdout).tools_used


# Imports stay inside the readers so a plain ``multiharness adapters list``
# does not pull five provider parsers in behind the registry.
_READERS: Final[dict[str, Callable[[str], tuple[str, ...]]]] = {
    "claude": _claude,
    "codex": _codex,
    "grok": _grok,
    "kimi": _kimi,
}
# Antigravity's ``--output-format json`` envelope has no tool field at all; the
# parser's ``reports_tool_use`` is False by construction rather than by chance.
_UNREPORTING: Final[frozenset[str]] = frozenset({"agy"})


def harness_tool_use(executable_basename: str, stdout: str) -> HarnessToolUse:
    """Return the distinct native tools this harness's own transcript names."""

    if executable_basename in _UNREPORTING:
        return HarnessToolUse(tools=(), reporting=TOOL_USE_UNREPORTED)
    reader = _READERS.get(executable_basename)
    if reader is None:
        declared = ", ".join(sorted((*_READERS, *_UNREPORTING)))
        raise ToolAccountingError(
            f"no tool-use reader for harness {executable_basename!r}; "
            f"declared harnesses: {declared}"
        )
    try:
        tools = reader(stdout)
    except ValueError:
        # from-None is deliberate: parser messages can embed transcript text,
        # and this feeds a published summary.  An unparseable transcript is an
        # absence of tool evidence, not evidence of no tools.
        return HarnessToolUse(tools=(), reporting=TOOL_USE_UNREPORTED)
    return HarnessToolUse(tools=tools, reporting=TOOL_USE_REPORTED)


def _unobservable_fence() -> HarnessFenceObservation:
    return HarnessFenceObservation(
        native_tools_enabled=False,
        server_side_web_tools_disabled=True,
        web_tools_available=(),
        web_request_count=0,
        observable=False,
    )


def _claude_fence(stdout: str) -> HarnessFenceObservation:
    from legalforecast.multiharness.container_harness.parsers import (
        parse_claude_code_stream,
    )

    parsed = parse_claude_code_stream(stdout)
    available = parsed.server_side_web_tools_available
    requests = parsed.server_side_web_requests
    return HarnessFenceObservation(
        native_tools_enabled=bool(parsed.tools_available),
        server_side_web_tools_disabled=not available and requests == 0,
        web_tools_available=available,
        web_request_count=requests,
        observable=True,
    )


def _codex_fence(stdout: str) -> HarnessFenceObservation:
    from legalforecast.multiharness.container_harness.parser_codex_cli import (
        parse_codex_cli_stream,
    )

    parsed = parse_codex_cli_stream(stdout)
    return HarnessFenceObservation(
        native_tools_enabled=bool(parsed.tools_used),
        server_side_web_tools_disabled=parsed.server_side_web_calls == 0,
        web_tools_available=(),
        web_request_count=parsed.server_side_web_calls,
        observable=True,
    )


def _grok_fence(stdout: str) -> HarnessFenceObservation:
    from legalforecast.multiharness.container_harness.parser_grok import (
        parse_grok_stream,
    )

    parsed = parse_grok_stream(stdout)
    available = parsed.server_side_web_tools_available
    used = parsed.server_side_web_tools_used
    return HarnessFenceObservation(
        native_tools_enabled=bool(parsed.tools_available),
        server_side_web_tools_disabled=not available and not used,
        web_tools_available=available,
        web_request_count=len(used),
        observable=True,
    )


def _kimi_fence(stdout: str) -> HarnessFenceObservation:
    from legalforecast.multiharness.container_harness.parser_kimi import (
        parse_kimi_stream,
    )

    parsed = parse_kimi_stream(stdout)
    invoked = parsed.web_tools_invoked
    return HarnessFenceObservation(
        native_tools_enabled=bool(parsed.tools_used),
        server_side_web_tools_disabled=not invoked,
        web_tools_available=(),
        web_request_count=len(invoked),
        observable=True,
    )


_FENCE_READERS: Final[dict[str, Callable[[str], HarnessFenceObservation]]] = {
    "claude": _claude_fence,
    "codex": _codex_fence,
    "grok": _grok_fence,
    "kimi": _kimi_fence,
}


def harness_fence_observation(
    executable_basename: str, stdout: str
) -> HarnessFenceObservation:
    """Return the web-fence and native-tool observations from this transcript."""

    if executable_basename in _UNREPORTING:
        return _unobservable_fence()
    reader = _FENCE_READERS.get(executable_basename)
    if reader is None:
        declared = ", ".join(sorted((*_FENCE_READERS, *_UNREPORTING)))
        raise ToolAccountingError(
            f"no fence reader for harness {executable_basename!r}; "
            f"declared harnesses: {declared}"
        )
    try:
        return reader(stdout)
    except ValueError:
        # from-None: parser messages can embed transcript text.  An unparseable
        # envelope is an absence of fence evidence, not evidence the fence held.
        return _unobservable_fence()

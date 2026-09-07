"""Derive fence flags from parser observations of the actual invocation.

The halted stack published ``server_side_web_tools_disabled=True`` from a
stub that also set ``observable=False``, then discarded the observable bit.
AGY rows and parser failures therefore claimed the fence held.  Both
booleans are observations: when the envelope cannot answer, they are null,
never True.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

_SOURCES: Final[frozenset[str]] = frozenset(
    {"parser", "unobservable", "parser_failure"}
)


class FenceEvidenceError(ValueError):
    """Raised when a fence claim is not derived from a parser observation."""


@dataclass(frozen=True, slots=True)
class ParserFenceFields:
    """The subset of a harness parser result that can answer the web-fence question."""

    parse_ok: bool
    reports_fence: bool
    tools_available: tuple[str, ...] = ()
    server_side_web_tools_available: tuple[str, ...] = ()
    server_side_web_request_count: int = 0

    def __post_init__(self) -> None:
        if self.server_side_web_request_count < 0:
            raise FenceEvidenceError(
                "fence parser web request count must be non-negative"
            )

    def to_record(self) -> dict[str, object]:
        """Return the exact parser inputs from which fence claims are derived."""

        return {
            "parse_ok": self.parse_ok,
            "reports_fence": self.reports_fence,
            "tools_available": list(self.tools_available),
            "server_side_web_tools_available": list(
                self.server_side_web_tools_available
            ),
            "server_side_web_request_count": self.server_side_web_request_count,
        }

    @classmethod
    def from_record(cls, value: object) -> ParserFenceFields:
        """Parse the closed parser-field schema or fail closed."""

        if not isinstance(value, Mapping):
            raise FenceEvidenceError("fence parser fields must be an object")
        record = cast(Mapping[str, object], value)
        expected = {
            "parse_ok",
            "reports_fence",
            "tools_available",
            "server_side_web_tools_available",
            "server_side_web_request_count",
        }
        if set(record) != expected:
            raise FenceEvidenceError("fence parser fields have the wrong schema")
        parse_ok = record["parse_ok"]
        reports_fence = record["reports_fence"]
        count = record["server_side_web_request_count"]
        if not isinstance(parse_ok, bool) or not isinstance(reports_fence, bool):
            raise FenceEvidenceError("fence parser flags must be booleans")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise FenceEvidenceError(
                "fence parser web request count must be non-negative"
            )
        return cls(
            parse_ok=parse_ok,
            reports_fence=reports_fence,
            tools_available=_string_tuple(record["tools_available"], "tools_available"),
            server_side_web_tools_available=_string_tuple(
                record["server_side_web_tools_available"],
                "server_side_web_tools_available",
            ),
            server_side_web_request_count=count,
        )


@dataclass(frozen=True, slots=True)
class FenceObservation:
    """Whether this run's own transcript shows native tools on and web tools off.

    ``observable`` is false when the envelope cannot answer or the transcript
    does not parse.  Callers must not publish ``True`` for a field they could
    not read.
    """

    observable: bool
    native_tools_enabled: bool | None
    server_side_web_tools_disabled: bool | None
    web_tools_available: tuple[str, ...]
    web_request_count: int | None
    source: str
    parser_fields: ParserFenceFields | None = None

    def __post_init__(self) -> None:
        if self.source not in _SOURCES:
            raise FenceEvidenceError(f"unknown fence source: {self.source!r}")
        if self.observable:
            if self.source != "parser":
                raise FenceEvidenceError("observable fence must come from a parser")
            if (
                self.native_tools_enabled is None
                or self.server_side_web_tools_disabled is None
                or self.web_request_count is None
            ):
                raise FenceEvidenceError(
                    "observable fence flags must be booleans derived from the parser"
                )
            if self.parser_fields is None:
                raise FenceEvidenceError(
                    "observable fence claims require their parser fields"
                )
            expected = _derived_fence_values(self.parser_fields)
            actual = (
                self.observable,
                self.native_tools_enabled,
                self.server_side_web_tools_disabled,
                self.web_tools_available,
                self.web_request_count,
                self.source,
            )
            if actual != expected:
                raise FenceEvidenceError(
                    "fence record does not match its parser fields"
                )
            return
        if self.server_side_web_tools_disabled is True:
            raise FenceEvidenceError(
                "unobservable or parser-failure row cannot claim the fence held"
            )
        if self.native_tools_enabled is True:
            raise FenceEvidenceError(
                "unobservable or parser-failure row cannot claim native tools "
                "were enabled"
            )
        if (
            self.native_tools_enabled is not None
            or self.server_side_web_tools_disabled is not None
            or self.web_request_count is not None
        ):
            raise FenceEvidenceError(
                "unobservable fence flags must be null, not a boolean claim"
            )
        if self.source == "parser":
            raise FenceEvidenceError("unobservable fence cannot use source=parser")
        if self.parser_fields is not None:
            expected = _derived_fence_values(self.parser_fields)
            actual = (
                self.observable,
                self.native_tools_enabled,
                self.server_side_web_tools_disabled,
                self.web_tools_available,
                self.web_request_count,
                self.source,
            )
            if actual != expected:
                raise FenceEvidenceError(
                    "fence record does not match its parser fields"
                )

    def to_record(self) -> dict[str, Any]:
        """Return the published fence record, with nulls when unobservable."""

        return {
            "observable": self.observable,
            "native_tools_enabled": self.native_tools_enabled,
            "server_side_web_tools_disabled": self.server_side_web_tools_disabled,
            "web_tools_available": list(self.web_tools_available),
            "web_request_count": self.web_request_count,
            "source": self.source,
            "parser_fields": (
                None if self.parser_fields is None else self.parser_fields.to_record()
            ),
        }


def unobservable_fence(
    *, source: str, parser_fields: ParserFenceFields | None = None
) -> FenceObservation:
    """Return a fence record that cannot claim the fence held."""

    return FenceObservation(
        observable=False,
        native_tools_enabled=None,
        server_side_web_tools_disabled=None,
        web_tools_available=(),
        web_request_count=None,
        source=source,
        parser_fields=parser_fields,
    )


def fence_from_parser_fields(fields: ParserFenceFields) -> FenceObservation:
    """Derive fence booleans from parser fields, or mark the row unobservable."""

    if not fields.parse_ok:
        return unobservable_fence(source="parser_failure", parser_fields=fields)
    if not fields.reports_fence:
        return unobservable_fence(source="unobservable", parser_fields=fields)
    if fields.server_side_web_request_count < 0:
        raise FenceEvidenceError("web request count must not be negative")
    disabled = (
        not fields.server_side_web_tools_available
        and fields.server_side_web_request_count == 0
    )
    return FenceObservation(
        observable=True,
        native_tools_enabled=bool(fields.tools_available),
        server_side_web_tools_disabled=disabled,
        web_tools_available=tuple(fields.server_side_web_tools_available),
        web_request_count=fields.server_side_web_request_count,
        source="parser",
        parser_fields=fields,
    )


def fence_from_cli_output(cli_name: str, stdout: bytes) -> FenceObservation:
    """Derive fence evidence from the completed invocation's own stdout bytes.

    Claude's stream-json envelope reports both its offered tools and provider-side
    web request counts. Other currently fenced CLIs do not expose both facts in a
    stable envelope, so they remain explicitly unobservable instead of inheriting
    a positive claim from their argv.
    """

    if cli_name != "claude":
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=True, reports_fence=False)
        )
    try:
        text = stdout.decode("utf-8")
    except UnicodeDecodeError:
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=False, reports_fence=True)
        )
    events: list[Mapping[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            decoded: object = json.loads(line)
        except ValueError:
            continue
        if isinstance(decoded, Mapping):
            events.append(cast(Mapping[str, object], decoded))
    init = next(
        (
            event
            for event in events
            if event.get("type") == "system" and event.get("subtype") == "init"
        ),
        None,
    )
    terminal = next(
        (event for event in reversed(events) if event.get("type") == "result"),
        None,
    )
    if init is None or terminal is None:
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=False, reports_fence=True)
        )
    try:
        tools = _string_tuple(init.get("tools"), "tools")
    except FenceEvidenceError:
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=False, reports_fence=True)
        )
    usage = terminal.get("usage")
    if not isinstance(usage, Mapping):
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=True, reports_fence=False)
        )
    server_tool_use = cast(Mapping[str, object], usage).get("server_tool_use")
    if not isinstance(server_tool_use, Mapping):
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=True, reports_fence=False)
        )
    reported = cast(Mapping[str, object], server_tool_use)
    counts = (
        reported.get("web_search_requests"),
        reported.get("web_fetch_requests"),
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in counts):
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=False, reports_fence=True)
        )
    web_count = sum(cast(tuple[int, int], counts))
    if web_count < 0:
        return fence_from_parser_fields(
            ParserFenceFields(parse_ok=False, reports_fence=True)
        )
    web_tools = tuple(tool for tool in tools if tool in {"WebFetch", "WebSearch"})
    return fence_from_parser_fields(
        ParserFenceFields(
            parse_ok=True,
            reports_fence=True,
            tools_available=tools,
            server_side_web_tools_available=web_tools,
            server_side_web_request_count=web_count,
        )
    )


def require_honest_fence_record(record: Mapping[str, object]) -> None:
    """Refuse a published fence record that cannot be rederived exactly."""

    expected = {
        "observable",
        "native_tools_enabled",
        "server_side_web_tools_disabled",
        "web_tools_available",
        "web_request_count",
        "source",
        "parser_fields",
    }
    if set(record) != expected:
        raise FenceEvidenceError(
            "fence record must include the exact parser observations and fields "
            "used for derivation"
        )
    parser_fields = ParserFenceFields.from_record(record["parser_fields"])
    derived = fence_from_parser_fields(parser_fields).to_record()
    if dict(record) != derived:
        raise FenceEvidenceError(
            "fence record does not match its parser fields; an unobservable row "
            "cannot claim the fence held"
        )


def _derived_fence_values(
    fields: ParserFenceFields,
) -> tuple[bool, bool | None, bool | None, tuple[str, ...], int | None, str]:
    if not fields.parse_ok:
        return False, None, None, (), None, "parser_failure"
    if not fields.reports_fence:
        return False, None, None, (), None, "unobservable"
    disabled = (
        not fields.server_side_web_tools_available
        and fields.server_side_web_request_count == 0
    )
    return (
        True,
        bool(fields.tools_available),
        disabled,
        tuple(fields.server_side_web_tools_available),
        fields.server_side_web_request_count,
        "parser",
    )


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise FenceEvidenceError(f"fence parser {field_name} must be a list of strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise FenceEvidenceError(f"fence parser {field_name} must be a list of strings")
    return tuple(cast(list[str], items))

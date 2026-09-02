"""Read each harness's own transcript for the tokens it actually spent.

Sibling of :mod:`legalforecast.multiharness.harness_lane.tool_accounting` and
deliberately built to the same shape: one table from an executable basename to
the parser that already extracts that harness's usage, and one typed answer
that a published summary can carry.

The defect this closes is specific.  Every containerized manifest declares
``usage_reporting`` accessors and every parser extracts them into a typed
result, but the adapter never carried those numbers into its public summary --
so the release projection's defaults stood, and every LFB row published
``input_tokens: 0``, ``output_tokens: 0``.  Nobody measured zero.

Three properties matter more than convenience:

* **Unreported is not zero.**  Kimi's envelope has no usage code path at all
  (``KimiStreamResult.reports_usage`` is ``False`` by construction), so its
  rows carry ``usage_reporting: "unreported"`` and no token fields, never a 0.
  :class:`HarnessUsage` enforces that in ``__post_init__``: a reported result
  must carry counts and an unreported one must carry ``None`` everywhere, so
  there is no constructible object that says "reported: 0 tokens".
* **An empty accounting block is unreported too.**  Every parser reads its
  token fields with an ``_int_or_zero``, so a missing ``usage`` object yields
  zeros that look exactly like a measurement.  A completed turn cannot spend
  zero input tokens, so a zero input/output pair is downgraded to unreported
  with an ``empty_usage_block`` caveat rather than published as a count.
* **Imputed cost is not spend.**  Every harness in this lane runs on a
  subscription -- ``cost_basis`` is ``subscription_unallocable`` in all five
  committed manifests -- so no per-run dollar figure is money that left an
  account.  Claude Code and Grok report a ``total_cost_usd``; it is a
  list-price imputation of what the same tokens would have cost on the API.
  It is published as ``usage.imputed_cost_usd`` beside
  ``usage.cost_metering: "imputed_list_price"``, and it is deliberately *not*
  projected into the summary's ``estimated_cost``, which the release
  projection copies into the LFB row as an unlabelled float.

Known gap, stated rather than hidden: for an unreporting harness this module
omits the summary's ``input_tokens``/``output_tokens`` keys, and
``release_harness._optional_non_negative_summary_int`` then defaults the LFB
inspect row to 0.  Closing that needs the release projection to distinguish
"absent because unreported" from "absent because nobody set it", which is out
of this module's reach.  Until it lands, ``usage_reporting`` on the adapter's
public summary is the truth marker for those rows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Self

USAGE_REPORTED: Final = "cli_reported_usage"
USAGE_UNREPORTED: Final = "unreported"
#: A dollar figure the CLI computed from list prices for tokens billed to a
#: subscription.  Real accounting, wrong denominator: nothing was metered.
COST_IMPUTED_LIST_PRICE: Final = "imputed_list_price"
COST_UNREPORTED: Final = "unreported"
#: The harness reported an all-zero token block, which is an absent
#: measurement rather than a run that spent nothing.
CAVEAT_EMPTY_USAGE_BLOCK: Final = "empty_usage_block"
#: Grok drops every cost float when its own accounting is partial.
CAVEAT_PARTIAL_COST: Final = "cost_is_partial"
CAVEAT_INCOMPLETE_USAGE: Final = "usage_is_incomplete"


class UsageAccountingError(ValueError):
    """Raised when a harness has no declared way to report its token usage."""


@dataclass(frozen=True, slots=True)
class HarnessUsage:
    """Tokens one harness reported spending, if it reports any at all.

    ``reporting`` is the field that must be read first: on
    :data:`USAGE_UNREPORTED` every count is ``None`` and the absence is the
    measurement.  ``caveats`` carries per-run qualifications the harness itself
    declared -- they qualify a reported number, they do not soften an absent
    one.
    """

    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    reasoning_tokens: int | None
    imputed_cost_usd: float | None
    reporting: str
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reporting not in {USAGE_REPORTED, USAGE_UNREPORTED}:
            raise UsageAccountingError(
                f"usage reporting class {self.reporting!r} is not one of "
                f"{USAGE_REPORTED!r}, {USAGE_UNREPORTED!r}"
            )
        if self.reporting == USAGE_UNREPORTED:
            if any(
                value is not None
                for value in (
                    self.input_tokens,
                    self.output_tokens,
                    self.cache_read_tokens,
                    self.cache_write_tokens,
                    self.reasoning_tokens,
                    self.imputed_cost_usd,
                )
            ):
                raise UsageAccountingError(
                    "an unreported usage result must carry no counts; a number "
                    "beside 'unreported' is a measurement claiming not to be one"
                )
            return
        if self.input_tokens is None or self.output_tokens is None:
            raise UsageAccountingError(
                "a reported usage result must carry input and output token "
                "counts; use HarnessUsage.unreported() when the harness's "
                "envelope carries no accounting"
            )

    @classmethod
    def unreported(cls, *caveats: str) -> Self:
        """Return the result for a harness whose envelope carries no usage."""

        return cls(
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_write_tokens=None,
            reasoning_tokens=None,
            imputed_cost_usd=None,
            reporting=USAGE_UNREPORTED,
            caveats=tuple(sorted(caveats)),
        )

    @property
    def reported(self) -> bool:
        """Return whether this run's envelope carried token accounting."""

        return self.reporting == USAGE_REPORTED

    @property
    def cost_metering(self) -> str:
        """Return what the run's dollar figure is, or that there is none.

        Never ``"metered"``: this lane has no metered cost to report, so the
        only two answers are an imputation and an absence.
        """

        if self.imputed_cost_usd is None:
            return COST_UNREPORTED
        return COST_IMPUTED_LIST_PRICE

    def to_record(self, *, cost_basis: str) -> dict[str, Any]:
        """Return the JSON-ready nested usage record for a published summary."""

        return {
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "caveats": list(self.caveats),
            "cost_basis": cost_basis,
            "cost_metering": self.cost_metering,
            "imputed_cost_usd": self.imputed_cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "reporting": self.reporting,
        }

    def summary_fields(self, *, cost_basis: str) -> dict[str, Any]:
        """Return the fields this result contributes to the public summary.

        The flat ``input_tokens``/``output_tokens`` keys are what the release
        projection reads, so they appear only when the harness actually
        reported counts.  ``usage_reporting`` is always present and says which
        case this row is, exactly as ``tool_use_reporting`` does for tools.
        ``estimated_cost`` is deliberately never set: see the module docstring.
        """

        fields: dict[str, Any] = {
            "usage": self.to_record(cost_basis=cost_basis),
            "usage_reporting": self.reporting,
        }
        if self.reported:
            fields["input_tokens"] = self.input_tokens
            fields["output_tokens"] = self.output_tokens
        return fields


def _reported(
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int | None,
    cache_write_tokens: int | None,
    reasoning_tokens: int | None,
    imputed_cost_usd: float | None,
    caveats: tuple[str, ...] = (),
) -> HarnessUsage:
    """Return a reported result, or an unreported one for an empty block.

    Every parser fills its token fields with an ``_int_or_zero``, so an
    envelope that carried no ``usage`` object at all arrives here as zeros.  A
    turn that reached the model cannot have spent zero input *and* zero output
    tokens, so that pair is the absence of an accounting block rather than a
    measurement of nothing, and it is reported as such.
    """

    if input_tokens == 0 and output_tokens == 0:
        return HarnessUsage.unreported(CAVEAT_EMPTY_USAGE_BLOCK, *caveats)
    return HarnessUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
        imputed_cost_usd=imputed_cost_usd,
        reporting=USAGE_REPORTED,
        caveats=tuple(sorted(caveats)),
    )


def _claude(stdout: str) -> HarnessUsage:
    from legalforecast.multiharness.container_harness.parsers import (
        parse_claude_code_stream,
    )

    usage = parse_claude_code_stream(stdout).usage
    return _reported(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
        reasoning_tokens=None,
        imputed_cost_usd=usage.total_cost_usd,
    )


def _codex(stdout: str) -> HarnessUsage:
    from legalforecast.multiharness.container_harness.parser_codex_cli import (
        parse_codex_cli_stream,
    )

    usage = parse_codex_cli_stream(stdout).usage
    # No cost field exists anywhere in this envelope, which is why the
    # manifest's ``cost_usd_field`` is null; there is nothing to impute from.
    return _reported(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cached_input_tokens,
        cache_write_tokens=usage.cache_write_input_tokens,
        reasoning_tokens=usage.reasoning_output_tokens,
        imputed_cost_usd=None,
    )


def _grok(stdout: str) -> HarnessUsage:
    from legalforecast.multiharness.container_harness.parser_grok import (
        parse_grok_stream,
    )

    usage = parse_grok_stream(stdout).usage
    caveats: list[str] = []
    if usage.cost_is_partial:
        caveats.append(CAVEAT_PARTIAL_COST)
    if usage.usage_is_incomplete:
        caveats.append(CAVEAT_INCOMPLETE_USAGE)
    return _reported(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        imputed_cost_usd=usage.total_cost_usd,
        caveats=tuple(caveats),
    )


def _agy(stdout: str) -> HarnessUsage:
    from legalforecast.multiharness.container_harness.parser_agy import (
        parse_antigravity_json,
    )

    usage = parse_antigravity_json(stdout).usage
    # This envelope has no cache-write field and no cost field at all; both are
    # null in the manifest for the same reason.
    return _reported(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=None,
        reasoning_tokens=usage.thinking_tokens,
        imputed_cost_usd=None,
    )


# Imports stay inside the readers so a plain ``multiharness adapters list``
# does not pull five provider parsers in behind the registry.
_READERS: Final[dict[str, Callable[[str], HarnessUsage]]] = {
    "agy": _agy,
    "claude": _claude,
    "codex": _codex,
    "grok": _grok,
}
# Kimi Code's writer has no usage code path: ``KimiStreamResult.reports_usage``
# is False by construction, and its manifest's token accessors are the
# ``unreported.*`` sentinel rather than a real dotted path.
_UNREPORTING: Final[frozenset[str]] = frozenset({"kimi"})


def harness_usage(executable_basename: str, stdout: str) -> HarnessUsage:
    """Return the token accounting this harness's own transcript carries."""

    if executable_basename in _UNREPORTING:
        return HarnessUsage.unreported()
    reader = _READERS.get(executable_basename)
    if reader is None:
        declared = ", ".join(sorted((*_READERS, *_UNREPORTING)))
        raise UsageAccountingError(
            f"no usage reader for harness {executable_basename!r}; "
            f"declared harnesses: {declared}"
        )
    try:
        return reader(stdout)
    except ValueError:
        # from-None is deliberate: parser messages can embed transcript text,
        # and this feeds a published summary.  An unparseable transcript is an
        # absence of usage evidence, not evidence that nothing was spent.
        return HarnessUsage.unreported()

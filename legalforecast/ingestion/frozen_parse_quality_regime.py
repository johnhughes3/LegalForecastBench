"""Which parse-quality regime authenticates one frozen predecessor parse lineage.

``legalforecast.ingestion.parse_quality`` was added by PR #764 on 2026-08-16 and
is applied by ``verify_stage_a_parse_records`` to every parser record it
replays.  The exact-100 predecessor Stage A cohort was parsed on 2026-08-07, and
its ``llm-unitize`` run card commits that parse manifest *by digest*.  Replaying
it today therefore measures evidence against a gate that did not exist when the
evidence was produced, and the card's committed inputs cannot be redirected at a
corrected parse stage: ``verify_stage_a_unitization_run_card`` requires the
committed inputs to be reproduced exactly, which is the point of the commitment.

This module names the assessment regime in force when one authenticated parse
manifest was produced, keyed by the digest the caller has already
authenticated.  It is the same shape as
``legalforecast.ingestion.frozen_parser_model.registry``: a closed,
content-addressed mapping, so nothing an artifact carries in its own payload can
select its own verifier.

**Nothing about byte identity is relaxed.**  Whichever regime is selected, every
parser record must still resolve to a Markdown path inside the trusted root,
reproduce its committed ``text_sha256`` over the captured bytes, and carry live
Mistral extraction provenance.  The regime decides one question only: whether a
gate written after the evidence is applied to it retroactively.

Two conditions gate the selection, and they are **not** equally strong.  Be
precise about which one actually enforces this feature:

1. ``frozen_predecessor_replay`` — an *unchecked caller assertion* that the
   replay reached us from a run card whose parse inputs are pinned by an
   earlier paid run and therefore cannot name a corrected parse stage.  Nothing
   verifies that claim; it is a routing fact the caller states about itself.
2. The parse manifest digest must appear in the closed mapping below.  **This
   is the enforcing boundary.**  It is content-addressed over bytes the
   verifier itself read and authenticated, so obtaining a preserved regime for
   anything not audited here would require a SHA-256 preimage.

A caller that satisfies condition 1 by accident therefore still gets the current
gate for every manifest except the two audited below.  Do not extend more trust
to condition 1 than it earns: a new *live* caller that needs this path should
verify its context explicitly rather than inheriting the flag by default.

The **successor** half of a replay — the bytes that will drive fresh provider
calls — never sets condition 1 for its own top-level manifest and is always
assessed under the current gate.  A corrected parse for a superseded row
therefore has to clear today's gate on the way in; see
``_reuse_live_mistral_parse_outputs`` in the CLI.  Frozen *ancestor*
projections replayed for provenance run under their producing regime in both
halves.  The finding this regime declines to apply retroactively is not
suppressed: it is repaired in the successor lineage, and the systemic parser
defect behind it is tracked separately.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

PARSE_QUALITY_REGIME_CURRENT: Final = "current"
"""Today's production gate, and the default for every lineage and caller."""

PARSE_QUALITY_REGIME_PRE_764: Final = "pre-parse-quality-gate"
"""No parse-quality assessment: the regime in force before PR #764."""


class ParseQualityRegimeError(ValueError):
    """Raised when a parse-quality regime name is not pinned."""


@dataclass(frozen=True, slots=True)
class ParseQualityRegime:
    """One named assessment regime for replayed parser records."""

    name: str
    enforces_parse_quality: bool


_REGIMES: Final[Mapping[str, ParseQualityRegime]] = MappingProxyType(
    {
        PARSE_QUALITY_REGIME_CURRENT: ParseQualityRegime(
            name=PARSE_QUALITY_REGIME_CURRENT, enforces_parse_quality=True
        ),
        PARSE_QUALITY_REGIME_PRE_764: ParseQualityRegime(
            name=PARSE_QUALITY_REGIME_PRE_764, enforces_parse_quality=False
        ),
    }
)

FROZEN_PREDECESSOR_PARSE_QUALITY_REGIME: Final[Mapping[str, str]] = MappingProxyType(
    {
        # 47-final-exact100-downstream-v6-main-2ce1fd8-v1/03-parse/
        # mistral-markdown-conversions.jsonl, parsed 2026-08-07 and committed by
        # digest in the exact-100 predecessor llm-unitize run card.
        "53c9e7245b56b0f21e5cac715a6010156ba4d3f4d322911d54beb27279de8357": (
            PARSE_QUALITY_REGIME_PRE_764
        ),
        # The stage 31 and stage 32 parse manifests are byte-identical to each
        # other (and distinct from 47's above), so one entry covers both.
        #
        # Reached while authenticating 47, not instead of it: the materialization
        # projection walks _verify_supporting_document_downstream_projection ->
        # verify_exact100_successor_replacement_v2_projection ->
        # _replay_exact100_successor_replacement_v2_inputs ->
        # _replay_exact100_stipulated_eligibility_unchecked, which replays this
        # ancestor from the persisted eligibility-audit run card's own committed
        # input_paths.  Same frozen chain, same 2026-08-07 rows.
        "f0059a6c19afec540331337a4f8e5ba89a7802f886180943b318bde7bf35bcc6": (
            PARSE_QUALITY_REGIME_PRE_764
        ),
    }
)


def frozen_predecessor_parse_quality_regime(parser_manifest_sha256: str) -> str:
    """Return the regime name for one authenticated predecessor parse manifest.

    An unlisted manifest replays under the current gate, which is the behaviour
    every manifest has today.  Callers that are not replaying a frozen
    predecessor run card must not call this at all.
    """

    return FROZEN_PREDECESSOR_PARSE_QUALITY_REGIME.get(
        parser_manifest_sha256.removeprefix("sha256:"),
        PARSE_QUALITY_REGIME_CURRENT,
    )


def replay_parse_quality_regime(
    *, parser_manifest_sha256: str, frozen_predecessor_replay: bool
) -> str:
    """Apply both selection conditions in one place.

    Keeping the conjunction here rather than inline at the call site gives the
    rule — *a preserved regime needs a frozen-predecessor caller* **and** *a
    pinned digest* — exactly one implementation and one truth table to test.
    """

    if not frozen_predecessor_replay:
        return PARSE_QUALITY_REGIME_CURRENT
    return frozen_predecessor_parse_quality_regime(parser_manifest_sha256)


def resolve_parse_quality_regime(name: str) -> ParseQualityRegime:
    """Return one named regime, or fail closed on an unrecognized name."""

    regime = _REGIMES.get(name)
    if regime is None:
        raise ParseQualityRegimeError(f"parse-quality regime is not pinned: {name!r}")
    return regime


def parse_quality_regime_names() -> tuple[str, ...]:
    """Return every pinned regime name, in sorted order."""

    return tuple(sorted(_REGIMES))


__all__ = [
    "FROZEN_PREDECESSOR_PARSE_QUALITY_REGIME",
    "PARSE_QUALITY_REGIME_CURRENT",
    "PARSE_QUALITY_REGIME_PRE_764",
    "ParseQualityRegime",
    "ParseQualityRegimeError",
    "frozen_predecessor_parse_quality_regime",
    "parse_quality_regime_names",
    "replay_parse_quality_regime",
    "resolve_parse_quality_regime",
]

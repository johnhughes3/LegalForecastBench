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

Two independent conditions gate the selection, so neither alone weakens a check:

1. the caller must be replaying a **frozen predecessor** run card — the only
   path whose parse inputs are pinned by an earlier paid run and so cannot name
   a corrected parse stage — and
2. the parse manifest digest must appear in the closed mapping below.

The **successor** half of a replay — the bytes that will drive fresh provider
calls — never satisfies condition 1 and is always assessed under the current
gate.  A corrected parse for a superseded row therefore has to clear today's
gate on the way in; see ``_reuse_live_mistral_parse_outputs`` in the CLI.  The
finding this regime declines to apply retroactively is not suppressed: it is
repaired in the successor lineage, and the systemic parser defect behind it is
tracked separately.
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
        # 31-final-exact100-downstream-v1 and 32-final-exact100-downstream-v2
        # share these exact bytes.  The materialization projection replays this
        # ancestor for provenance while authenticating 47, so it is reached from
        # inside the same frozen chain and carries the same 2026-08-07 rows.
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
    "resolve_parse_quality_regime",
]

"""Which derivation model authenticates one frozen exact-100 replay surface.

Two verifiers on the exact-100 predecessor Stage A lineage replay *derived*
values rather than observed bytes, and in both cases the deriving code was
deliberately broadened after the evidence under replay was minted:

1. **The stipulated-eligibility audit.**  ``verify_target_document_eligibility_
   audit`` re-derives every target document's verdict through
   ``legalforecast.ingestion.target_document_eligibility``.  PR #767
   (``a73dde0d``, 2026-08-16) broadened that detector to catch settlement-driven
   dismissals captioned as ordinary motions.  The audit under replay was minted
   2026-08-07 and is committed by digest in a paid run card.
2. **The exact-100 v2 wider public plan.**  The v2 successor projection
   re-derives the plan through ``plan_public_packet_downloads``, whose
   operative-complaint classifier gained ``_non_complaint_claim_kind`` in PR
   #667 (``253bad6d``, 2026-08-13).  The v2 root committed its
   ``wider_public_plan`` digest before that hunk existed.

   **Be precise about #667's scope, because this module versions only part of
   it.**  #667 touched eight production files.  Besides adding
   ``_non_complaint_claim_kind`` it also broadened three functions in
   ``courtlistener_web.py`` that the planner consults live -
   ``classify_courtlistener_entry_role`` (reached on every
   ``CourtListenerWebDocketEntry.role`` access, which is a property, not a
   frozen field), ``brief_targets_motion``, and
   ``is_substantive_mtd_opposition_entry``.  Those are deliberately **not**
   versioned here, on measurement rather than assumption:

   * restoring ``courtlistener_web.py`` *and* ``public_packet_planner.py`` to
     their pre-#667 ``2ce1fd80`` content reproduces the **current** digest
     ``6bacc47b…`` unchanged, so neither module moves this cohort's plan; and
   * restoring ``_non_complaint_claim_kind`` alone, with ``courtlistener_web``
     left at HEAD, reproduces the minted ``a499faec…`` **byte-for-byte** - which
     it could not do if the other hunks perturbed this cohort at all.

   So the seam is scoped to the one hunk that actually moves the digest.  This
   is safe in the fail-loud direction regardless: the recomputed plan is still
   byte-compared against the persisted plan, so a cohort where those other
   functions *did* matter would refuse here rather than pass quietly.  A future
   frozen plan root that refuses despite this regime should suspect exactly
   those three functions first.

Replaying either through today's model compares one model's output against a
different model's output, so a deliberate later broadening reads as evidence
corruption.  This is the same class of drift that
``frozen_parser_model.registry`` (PR #866) and ``frozen_parse_quality_regime``
(PR #869) already resolve, and it is resolved the same way.

**One selector mechanism, two seams.**  The sweep that enumerated these two
instances described them as riding "one selector".  That is true of the
*mechanism* and false of the *key*: the two seams authenticate different
artifacts, so each carries its own pin.  What they share -- and what lives here
exactly once -- is the selection rule: a closed, content-addressed map from a
digest the caller has **already authenticated** to the name of the model in
force when that evidence was produced, plus a resolution step that fails closed
on any name not pinned.  Nothing an artifact carries in its own payload can
select its own verifier, because the keys are digests the verifier itself
computed over bytes it independently authenticated.

**Nothing about byte identity is relaxed.**  Under either regime the replay must
still reproduce the frozen bytes exactly; a preserved model that produced a
different result would refuse just as loudly.  The regime decides one question
only: which derivation is replayed, not whether the comparison happens.

**Bytes a stage will consume stay current-strict.**  The live Stage A
consumption path calls ``require_eligible_target_document`` directly
(``labeling/llm_pipeline.py``) and never consults this module, so a document
entering Stage A today faces today's detector.  Likewise the successor half of a
replay -- the bytes that will drive fresh provider calls -- has no pinned digest
here and is always assessed under the current model.

The two findings this module declines to apply retroactively are **not
suppressed**: candidates 73209444 and 73325674 are tracked for owner
adjudication as corpus-completeness findings, and 68941639 is already excluded.
Tracking a finding while refusing to rewrite frozen history is the charter's
pattern, not an exception to it.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

TARGET_ELIGIBILITY_REGIME_CURRENT: Final = "current"
"""Today's production detector, and the default for every lineage and caller."""

TARGET_ELIGIBILITY_REGIME_PRE_767: Final = "pre-settlement-dismissal-detector"
"""The stipulation/voluntary-dismissal detector in force before PR #767."""

OPERATIVE_COMPLAINT_REGIME_CURRENT: Final = "current"
"""Today's production complaint classifier, and the default everywhere."""

OPERATIVE_COMPLAINT_REGIME_PRE_667: Final = "pre-non-complaint-claim-kinds"
"""The operative-complaint classifier in force before PR #667."""


class FrozenReplayRegimeError(ValueError):
    """Raised when a replay model regime name is not pinned."""


@dataclass(frozen=True, slots=True)
class TargetEligibilityRegime:
    """One named detector generation for replayed target-document verdicts."""

    name: str
    detects_settlement_driven_dismissals: bool


@dataclass(frozen=True, slots=True)
class OperativeComplaintRegime:
    """One named classifier generation for replayed complaint selection."""

    name: str
    classifies_non_complaint_claim_kinds: bool


_TARGET_ELIGIBILITY_REGIMES: Final[Mapping[str, TargetEligibilityRegime]] = (
    MappingProxyType(
        {
            TARGET_ELIGIBILITY_REGIME_CURRENT: TargetEligibilityRegime(
                name=TARGET_ELIGIBILITY_REGIME_CURRENT,
                detects_settlement_driven_dismissals=True,
            ),
            TARGET_ELIGIBILITY_REGIME_PRE_767: TargetEligibilityRegime(
                name=TARGET_ELIGIBILITY_REGIME_PRE_767,
                detects_settlement_driven_dismissals=False,
            ),
        }
    )
)

_OPERATIVE_COMPLAINT_REGIMES: Final[Mapping[str, OperativeComplaintRegime]] = (
    MappingProxyType(
        {
            OPERATIVE_COMPLAINT_REGIME_CURRENT: OperativeComplaintRegime(
                name=OPERATIVE_COMPLAINT_REGIME_CURRENT,
                classifies_non_complaint_claim_kinds=True,
            ),
            OPERATIVE_COMPLAINT_REGIME_PRE_667: OperativeComplaintRegime(
                name=OPERATIVE_COMPLAINT_REGIME_PRE_667,
                classifies_non_complaint_claim_kinds=False,
            ),
        }
    )
)

FROZEN_PREDECESSOR_TARGET_ELIGIBILITY_REGIME: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            # 32-final-exact100-downstream-v2/03-parse/
            # mistral-markdown-conversions.jsonl, parsed 2026-08-07 and committed
            # by digest in the stipulated-eligibility audit run card at
            # 33-target-eligibility-audit-main-a166c74-v1, whose own bytes are
            # pinned as the sealed ``stipulated_audit_run_card`` authority.  That
            # persisted audit carries 101 rows and exactly one ineligible target
            # (69736298/485714828); the pre-#767 detector reproduces all 101 rows
            # with zero disagreements, the current detector disagrees on three.
            #
            # This is the same manifest digest ``frozen_parse_quality_regime``
            # pins for the ancestor projection, and for the same reason: it is
            # the parse manifest this frozen chain replays.
            "f0059a6c19afec540331337a4f8e5ba89a7802f886180943b318bde7bf35bcc6": (
                TARGET_ELIGIBILITY_REGIME_PRE_767
            )
        }
    )
)

FROZEN_V2_OPERATIVE_COMPLAINT_REGIME: Final[Mapping[str, str]] = MappingProxyType(
    {
        # 16-target153-preparation-main-911371f-v1/01-public-plan/run-cards/
        # plan-public-downloads.json -- the wider public plan's own completed run
        # card, whose bytes this verifier authenticates against the sealed
        # ``wider_plan_run_card`` authority *before* consulting this map.
        #
        # Keyed on the run card rather than on the final153 snapshot manifest:
        # the snapshot digest already means "911371f parser model" in
        # ``frozen_parser_model.registry``, and it is shared by plan roots whose
        # recomputation does not drift.  The run card is unique to the one frozen
        # plan root whose committed ``wider_public_plan`` digest (a499faec…) was
        # minted before #667; the historical plan root keeps the current model
        # and reproduces its own commitment unchanged.
        "47199b60715c838efbb7adc21d5677049ca70ceb5a06e21597432d90abdbfc38": (
            OPERATIVE_COMPLAINT_REGIME_PRE_667
        )
    }
)


def _select(mapping: Mapping[str, str], digest: str, *, default: str) -> str:
    """Look one authenticated digest up in a closed regime map.

    The single selection rule shared by both seams.  An unlisted digest returns
    the current model, which is the behaviour every artifact has today.
    """

    return mapping.get(digest.removeprefix("sha256:"), default)


def frozen_predecessor_target_eligibility_regime(parser_manifest_sha256: str) -> str:
    """Return the detector generation for one authenticated parse manifest."""

    return _select(
        FROZEN_PREDECESSOR_TARGET_ELIGIBILITY_REGIME,
        parser_manifest_sha256,
        default=TARGET_ELIGIBILITY_REGIME_CURRENT,
    )


def replay_target_eligibility_regime(
    *, parser_manifest_sha256: str, frozen_predecessor_replay: bool
) -> str:
    """Apply both selection conditions for the eligibility seam in one place.

    Two conditions gate this selection and they are **not** equally strong, the
    same asymmetry ``frozen_parse_quality_regime`` documents:

    1. ``frozen_predecessor_replay`` is an *unchecked caller assertion* that the
       replay reached us from a paid run card whose parse inputs are pinned and
       therefore cannot name a corrected audit.  Nothing verifies that claim.
    2. The parse manifest digest must appear in the closed map above.  **This is
       the enforcing boundary** -- it is content-addressed over bytes the
       verifier itself read and authenticated, so obtaining a preserved detector
       for anything not audited here would require a SHA-256 preimage.

    A caller that satisfies condition 1 by accident therefore still gets the
    current detector for every manifest except the one pinned above.  Do not
    extend more trust to condition 1 than it earns.
    """

    if not frozen_predecessor_replay:
        return TARGET_ELIGIBILITY_REGIME_CURRENT
    return frozen_predecessor_target_eligibility_regime(parser_manifest_sha256)


def replay_operative_complaint_regime(*, public_plan_run_card_sha256: str) -> str:
    """Return the classifier generation for one authenticated public-plan card.

    Single-condition, following ``frozen_parser_model.registry`` rather than
    ``frozen_parse_quality_regime``: there is no separate caller assertion to
    make here because the key *is* the caller's context.  The run card bytes are
    checked against the sealed ``wider_plan_run_card`` authority before this
    lookup, so reaching a preserved classifier already required presenting the
    one frozen plan root this regime describes.
    """

    return _select(
        FROZEN_V2_OPERATIVE_COMPLAINT_REGIME,
        public_plan_run_card_sha256,
        default=OPERATIVE_COMPLAINT_REGIME_CURRENT,
    )


def resolve_target_eligibility_regime(name: str) -> TargetEligibilityRegime:
    """Return one named detector generation, or fail closed on a stray name."""

    regime = _TARGET_ELIGIBILITY_REGIMES.get(name)
    if regime is None:
        raise FrozenReplayRegimeError(
            f"target-document eligibility regime is not pinned: {name!r}"
        )
    return regime


def resolve_operative_complaint_regime(name: str) -> OperativeComplaintRegime:
    """Return one named classifier generation, or fail closed on a stray name."""

    regime = _OPERATIVE_COMPLAINT_REGIMES.get(name)
    if regime is None:
        raise FrozenReplayRegimeError(
            f"operative-complaint regime is not pinned: {name!r}"
        )
    return regime


_ACTIVE_OPERATIVE_COMPLAINT_REGIME: Final[ContextVar[str]] = ContextVar(
    "active_operative_complaint_regime",
    default=OPERATIVE_COMPLAINT_REGIME_CURRENT,
)


def active_operative_complaint_regime() -> str:
    """Return the classifier generation in force for the calling context."""

    return _ACTIVE_OPERATIVE_COMPLAINT_REGIME.get()


@contextmanager
def operative_complaint_regime_scope(name: str) -> Generator[str]:
    """Bind one classifier generation for the duration of a synchronous call.

    Why a scoped context and not a threaded parameter.  The classifier is
    consulted from ``public_packet_planner`` through ``_best_free_document``,
    which is reached from ten distinct functions and their transitive callers:
    threading a parameter to every one of them is a twenty-plus signature change
    across a hot production module, and *any* path missed would silently derive
    a different plan digest rather than refuse.  A regime is a property of the
    whole recomputation, not of an individual call, so binding it once around
    the recomputation is both smaller and safer -- it is exactly the shape the
    root-cause probe validated, where the pre-#667 classifier applied uniformly
    across the recomputation and reproduced the minted digest byte-for-byte.
    What the scope covers -- and which parts of #667 it deliberately does not,
    with the measurements behind that choice -- is set out in the module
    docstring above.

    This mirrors ``_VERIFIED_PROJECTION_BYTE_COLLECTOR`` in the CLI, which
    already carries verifier-owned state across one nested projection the same
    way.  PR #866's "forward kwargs rather than introduce ambient state" applies
    to kwargs that already existed end to end; none exist here.

    Fails closed on entry: an unpinned name raises before any planning runs, so
    a stray regime can never read as "no classifier".  The token is always
    reset, including on an exception inside the block.

    **Synchronous callers only.**  A ``ContextVar`` does not propagate into
    threads a callee may spawn; if the planner ever becomes concurrent this
    binding must be revisited.
    """

    resolve_operative_complaint_regime(name)
    token = _ACTIVE_OPERATIVE_COMPLAINT_REGIME.set(name)
    try:
        yield name
    finally:
        _ACTIVE_OPERATIVE_COMPLAINT_REGIME.reset(token)


def target_eligibility_regime_names() -> tuple[str, ...]:
    """Return every pinned detector generation name, in sorted order."""

    return tuple(sorted(_TARGET_ELIGIBILITY_REGIMES))


def operative_complaint_regime_names() -> tuple[str, ...]:
    """Return every pinned classifier generation name, in sorted order."""

    return tuple(sorted(_OPERATIVE_COMPLAINT_REGIMES))


__all__ = [
    "FROZEN_PREDECESSOR_TARGET_ELIGIBILITY_REGIME",
    "FROZEN_V2_OPERATIVE_COMPLAINT_REGIME",
    "OPERATIVE_COMPLAINT_REGIME_CURRENT",
    "OPERATIVE_COMPLAINT_REGIME_PRE_667",
    "TARGET_ELIGIBILITY_REGIME_CURRENT",
    "TARGET_ELIGIBILITY_REGIME_PRE_767",
    "FrozenReplayRegimeError",
    "OperativeComplaintRegime",
    "TargetEligibilityRegime",
    "active_operative_complaint_regime",
    "frozen_predecessor_target_eligibility_regime",
    "operative_complaint_regime_names",
    "operative_complaint_regime_scope",
    "replay_operative_complaint_regime",
    "replay_target_eligibility_regime",
    "resolve_operative_complaint_regime",
    "resolve_target_eligibility_regime",
    "target_eligibility_regime_names",
]

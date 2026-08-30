"""Fences for the provider-lane contract shared by dispatch and the cost receipt.

``provider_lane`` looks like the natural extension point for a new provider: it
is a small mapping from a registry key to a workflow lane, and adding a branch
to it is a one-line change.  Doing only that is a **silent** failure, which is
why these fences exist.

The cost-projection receipt is built by iterating ``PROVIDER_LANES`` and
bucketing matrix rows with ``provider_lane`` (``cost_projector`` ~:368-429).  A
provider that ``provider_lane`` resolves to a lane *outside* ``PROVIDER_LANES``
therefore lands in the receipt's aggregate ``matrix`` but in **no** provider
matrix -- and receipt verification still passes, because it only checks that the
lane rows equal ``matrix_rows`` for the selected lane and ``[]`` for the others
(~:788-805).  Every known lane legitimately gets ``[]``.  The result is a
dispatch that quietly runs zero cells while every gate reports success.

Extending ``PROVIDER_LANES`` is likewise not a free change: it alters the
receipt card's field set, which Cycle 1 change control freezes.  See
``docs/schemas/manifest-cost-projection-receipt-v1.md`` ("a **separate card, not
this one with an added field**") and bead ``legalforecastbench-s9b9``, which
carries the correct fix -- a new receipt card version with its own schema id and
its own field set.

So the lane set is all-or-nothing, and these tests make each half fail loudly.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from legalforecast.evals.corpus_manifest import cost_projector
from legalforecast.evals.corpus_manifest.cost_projector import (
    PROVIDER_LANES,
    ManifestCostProjectionError,
    provider_lane,
)


def _provider_strings_named_in_provider_lane() -> frozenset[str]:
    """Return every string literal appearing in ``provider_lane``'s body.

    Parsed from the source rather than hard-coded so that a future branch such
    as ``if provider == "xai": return "xai"`` is picked up automatically.  A
    fence nobody has to remember to update is the only kind that holds.
    """

    tree = ast.parse(inspect.getsource(provider_lane).strip())
    return frozenset(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def test_every_lane_provider_lane_resolves_is_a_dispatchable_lane() -> None:
    """A resolvable provider must map into ``PROVIDER_LANES``.

    Guards the silent half-measure: extending ``provider_lane`` alone yields
    rows that reach the receipt matrix but no provider matrix, and verification
    still passes. This turns that into a red test.
    """

    resolvable: dict[str, str] = {}
    for candidate in _provider_strings_named_in_provider_lane():
        try:
            resolvable[candidate] = provider_lane(f"{candidate}:some-model")
        except ManifestCostProjectionError:
            continue

    assert resolvable, "provider_lane resolved no providers; the fence went vacuous"

    orphaned = {
        provider: lane
        for provider, lane in resolvable.items()
        if lane not in PROVIDER_LANES
    }
    assert not orphaned, (
        "provider_lane resolves providers to lanes absent from PROVIDER_LANES: "
        f"{sorted(orphaned.items())}. Rows for these providers would land in the "
        "receipt matrix but in no provider matrix, and verification would still "
        "pass -- a silent zero-cell dispatch. Adding a lane is not a free change "
        "either: it alters the frozen receipt card's field set. See bead "
        "legalforecastbench-s9b9 for the supported fix."
    )


def test_unsupported_provider_fails_closed_rather_than_defaulting() -> None:
    """An unmapped provider must raise, never fall through to a default lane."""

    with pytest.raises(ManifestCostProjectionError, match="unsupported model provider"):
        provider_lane("xai:grok-4.6")
    with pytest.raises(ManifestCostProjectionError, match="unsupported model provider"):
        provider_lane("together:moonshotai/Kimi-K3")


def test_receipt_field_allowlist_covers_every_dispatchable_lane() -> None:
    """Every lane needs its receipt fields, or issuance emits an unverifiable card.

    ``_cost_exact_keys`` is strict in both directions, so a lane added to
    ``PROVIDER_LANES`` without matching entries in the receipt field allowlist
    produces a receipt that fails its own verifier with
    ``unknown=['<lane>_count', '<lane>_matrix']``. Catching that here makes the
    frozen-card breach a test failure instead of a dispatch-time refusal.
    """

    allowlist = cost_projector._COST_RECEIPT_FIELDS
    missing = sorted(
        field
        for lane in PROVIDER_LANES
        for field in (f"{lane}_count", f"{lane}_matrix")
        if field not in allowlist
    )
    assert not missing, (
        f"PROVIDER_LANES declares lanes whose receipt fields are not in the "
        f"card's allowlist: {missing}. Issuance would emit a receipt that fails "
        "its own verifier. The receipt card is frozen under Cycle 1 change "
        "control -- mint a new card version (bead legalforecastbench-s9b9) "
        "rather than widening this allowlist."
    )

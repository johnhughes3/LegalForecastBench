"""The owner-judgment terminal exclusion grounds and their record versioning.

A ground is either something the eligibility detector can reach on its own or
something only an owner can rule on, and the two are recorded differently: a
detector ground must bind the exact selection it was derived from, an owner
ground must not claim detector evidence at all, and the ``evidence_class`` the
record carries says which regime cleared it.  Getting that split wrong records
an owner's ruling as an authenticated detector replay, which is a false claim
about how the exclusion was established.

Fixtures are synthetic throughout; no corpus candidate or document appears here.
"""

from __future__ import annotations

import json

import pytest
from legalforecast.ingestion.exact100_successor_v3.projector import (
    EXCLUSION_SCHEMA_VERSION,
    EXCLUSION_SCHEMA_VERSION_V3,
    Exact100SuccessorReplacementV3Error,
    TerminalExclusionGroundV2,
    is_owner_judgment_ground,
    mint_verified_exact100_v3_terminal_exclusions,
)
from tests.exact100_successor_v3_fixtures import _base, _exclusion

_ONE_SIDED = TerminalExclusionGroundV2.OWNER_ADJUDICATED_ONE_SIDED_RECORD
_RULE_41 = TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL


def _minted_record(ground: TerminalExclusionGroundV2) -> dict[str, object]:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes, ground=ground)
        ],
    )
    line = exclusions.records_bytes.decode().splitlines()[0]
    return json.loads(line)


def test_the_one_sided_record_ground_is_an_owner_judgment() -> None:
    """An owner's reading of a one-sided record is not a detector result.

    No retrieval failed and no eligibility replay established it, so recording
    it as an authenticated detector replay would misstate its provenance.
    """

    record = _minted_record(_ONE_SIDED)

    assert record["ground"] == "owner_adjudicated_one_sided_record"
    assert record["evidence_class"] == "recorded_owner_adjudication"
    assert record["evidence_commitments"] == {}


def test_an_owner_ground_claiming_detector_evidence_refuses() -> None:
    base = _base()
    entry = _exclusion(
        "case000", selection_bytes=base.selection_bytes, ground=_ONE_SIDED
    )
    entry["evidence_commitments"] = {"selection": "sha256:" + "0" * 64}

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="must not claim detector evidence"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


def test_a_ground_added_after_v2_records_shipped_carries_its_own_version() -> None:
    """Records already in the chain must keep meaning what they meant.

    The earlier grounds keep stamping the version their minted records carry, so
    those roots still replay; only the later ground moves, which is what stops a
    single version identifier from denoting two different vocabularies.
    """

    assert _minted_record(_ONE_SIDED)["schema_version"] == EXCLUSION_SCHEMA_VERSION_V3
    assert _minted_record(_RULE_41)["schema_version"] == EXCLUSION_SCHEMA_VERSION
    assert (
        _minted_record(TerminalExclusionGroundV2.STIPULATED_INELIGIBLE)[
            "schema_version"
        ]
        == EXCLUSION_SCHEMA_VERSION
    )
    assert EXCLUSION_SCHEMA_VERSION_V3 != EXCLUSION_SCHEMA_VERSION


def test_every_ground_is_classified_as_detector_or_owner_judgment() -> None:
    """Vocabulary growth must force the classification, not inherit a default.

    The split is what decides whether a record has to bind the selection and
    what regime it claims cleared it, so a ground nobody classified would be
    recorded as an authenticated detector replay purely by falling through.
    """

    owner = {
        ground
        for ground in TerminalExclusionGroundV2
        if is_owner_judgment_ground(ground)
    }
    detector = {
        ground
        for ground in TerminalExclusionGroundV2
        if not is_owner_judgment_ground(ground)
    }

    assert owner == {_RULE_41, _ONE_SIDED}
    assert detector == {
        TerminalExclusionGroundV2.STIPULATED_INELIGIBLE,
        TerminalExclusionGroundV2.TERMINAL_MISSING_CORE_DOCUMENT,
    }
    assert owner | detector == set(TerminalExclusionGroundV2)
    assert not owner & detector

"""How a promotion records where its replacement came from.

The Cycle 1 methods disclosure is generated from these records rather than
written by hand, so whatever a promotion says about its own sourcing is what
the published report asserts.  Two sourcing stories exist and they must not be
conflated: a replacement the owner adjudicated after the sealed reserve horizon
was exhausted, and one derived by a deterministic walk of the ranked reserve --
a different artifact, with a different rank, that was not exhausted.

Fixtures are synthetic throughout; no corpus candidate, document or digest
appears here.
"""

from __future__ import annotations

from typing import Any

import pytest
from legalforecast.ingestion.exact100_successor_v3.projector import (
    PromotionProvenanceClass,
    methods_disclosure_text,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    OwnerAdjudicatedReplacementError,
    mint_verified_owner_adjudicated_replacement,
)
from tests.exact100_successor_v3_fixtures import _replacement_inputs

_RESERVE_DIGEST = "sha256:" + "d" * 64


def _claim(**overrides: Any) -> dict[str, Any]:
    claim = {
        "artifact_sha256": _RESERVE_DIGEST,
        "reserve_rank": 3,
        "selection_basis": (
            "Deterministic: walk the ranked reserve in ascending reserve_rank "
            "and take the first row not already in the frozen cohort."
        ),
    }
    claim.update(overrides)
    return claim


def _minted(claim: dict[str, Any] | None) -> Any:
    inputs = _replacement_inputs("new1", "case000")
    if claim is not None:
        inputs["owner_disposition"]["reserve_derivation"] = claim
    return mint_verified_owner_adjudicated_replacement(**inputs)


def test_a_replacement_without_a_claim_stays_owner_adjudicated() -> None:
    """Absence is the reading every already-minted root depends on.

    Those roots are replayed under whatever code is landed, and their promotion
    records were written before any reserve claim existed, so a promotion that
    makes no claim has to serialize exactly as it always did.
    """

    assert _minted(None).reserve_derivation is None


def test_a_claim_is_carried_onto_the_sealed_replacement() -> None:
    replacement = _minted(_claim())

    assert replacement.reserve_derivation is not None
    assert replacement.reserve_derivation["reserve_rank"] == 3
    assert replacement.reserve_derivation["artifact_sha256"] == _RESERVE_DIGEST


def test_a_claim_does_not_move_the_replacement_commitment() -> None:
    """The claim describes sourcing, not evidence, so it must not re-seal it.

    If it did, adding the field would change every already-minted root's
    commitment and break the chain the projector replays.
    """

    assert _minted(None).commitment_sha256 == _minted(_claim()).commitment_sha256


@pytest.mark.parametrize(
    "override",
    [
        {"artifact_sha256": "not-a-digest"},
        {"reserve_rank": 0},
        {"reserve_rank": "3"},
        {"reserve_rank": -1},
        {"selection_basis": ""},
    ],
    ids=["digest", "rank-zero", "rank-string", "rank-negative", "basis-empty"],
)
def test_an_incomplete_claim_refuses(override: dict[str, Any]) -> None:
    """A sourcing claim is what the published report will repeat."""

    with pytest.raises(OwnerAdjudicatedReplacementError, match="reserve derivation"):
        _minted(_claim(**override))


def test_an_unknown_claim_field_refuses() -> None:
    with pytest.raises(OwnerAdjudicatedReplacementError, match="reserve derivation"):
        _minted(_claim(exhausted=True))


def test_the_provenance_classes_are_distinct_and_complete() -> None:
    """The ranked reserve and the sealed wider-rank horizon are two systems.

    A candidate can sit in both at different ranks, so labelling a
    reserve-derived promotion as wider-rank-derived would not be a rounding
    error -- it would publish a rank the candidate does not hold there.
    """

    assert {member.value for member in PromotionProvenanceClass} == {
        "wider_rank_derived",
        "ranked_reserve_derived",
        "owner_adjudicated",
    }


def test_the_disclosure_names_owner_adjudication_only_for_owner_promotions() -> None:
    text = methods_disclosure_text(
        _result(
            [
                _promotion_record(PromotionProvenanceClass.OWNER_ADJUDICATED, None),
            ]
        )
    )

    assert "owner adjudication" in text
    assert "the reserve having been exhausted" in text
    assert "ranked reserve" not in text


def test_the_disclosure_states_reserve_derivation_without_claiming_exhaustion() -> None:
    """Both halves of the owner-adjudication sentence are false here.

    The candidate was not owner-selected, and the reserve it came from was not
    exhausted -- rank three of five was available.
    """

    text = methods_disclosure_text(
        _result(
            [
                _promotion_record(
                    PromotionProvenanceClass.RANKED_RESERVE_DERIVED, _claim()
                ),
            ]
        )
    )

    assert "ranked reserve" in text
    assert "rank 3" in text
    assert "exhausted" not in text
    assert "owner adjudication" not in text
    assert "wider-rank" not in text


def test_the_disclosure_separates_both_families_when_both_are_present() -> None:
    text = methods_disclosure_text(
        _result(
            [
                _promotion_record(PromotionProvenanceClass.OWNER_ADJUDICATED, None),
                _promotion_record(
                    PromotionProvenanceClass.RANKED_RESERVE_DERIVED, _claim()
                ),
            ]
        )
    )

    assert "owner adjudication" in text
    assert "ranked reserve" in text
    assert text.count("exhausted") == 1


def _promotion_record(
    provenance: PromotionProvenanceClass, claim: dict[str, Any] | None
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "candidate_id": "new1",
        "replaces_candidate_id": "case000",
        "provenance_class": provenance.value,
        "wider_rank": None,
    }
    if claim is not None:
        record["reserve_derivation"] = claim
    return record


def _result(promotions: list[dict[str, Any]]) -> Any:
    class _Stub:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self.promotions = tuple(rows)

    return _Stub(promotions)


def _projected_with(claim: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Project one swap through the real projector and return its promotions."""

    import json

    from legalforecast.ingestion.exact100_successor_v3.projector import (
        mint_verified_exact100_v3_terminal_exclusions,
        project_exact100_successor_replacement_v3,
    )
    from tests.exact100_successor_v3_fixtures import _base, _exclusion

    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )
    result = project_exact100_successor_replacement_v3(
        base=base, terminal_exclusions=exclusions, replacements=[_minted(claim)]
    )
    return [
        json.loads(line)
        for line in result.promotions_bytes.decode().splitlines()
        if line.strip()
    ]


def test_a_promotion_without_a_claim_carries_no_reserve_key() -> None:
    """The key must be absent, not null.

    Every already-minted root is replayed byte-for-byte against its stored
    promotions, and those were written before this field existed -- so emitting
    it unconditionally, even as null, invalidates them at chain time.
    """

    record = _projected_with(None)[0]

    assert "reserve_derivation" not in record
    assert record["provenance_class"] == "owner_adjudicated"
    assert record["wider_rank"] is None


def test_a_promotion_with_a_claim_is_labelled_reserve_derived() -> None:
    """Not wider-rank-derived: that is a different ranking system.

    The same candidate can hold a rank in both, so publishing the reserve rank
    under the wider-rank label would state a rank it does not hold there.
    """

    record = _projected_with(_claim())[0]

    assert record["provenance_class"] == "ranked_reserve_derived"
    assert record["reserve_derivation"]["reserve_rank"] == 3
    assert record["reserve_derivation"]["artifact_sha256"] == _RESERVE_DIGEST
    assert record["wider_rank"] is None


def test_the_projected_disclosure_states_the_true_provenance() -> None:
    """End to end: the published sentence comes from the projected records."""

    from legalforecast.ingestion.exact100_successor_v3.projector import (
        mint_verified_exact100_v3_terminal_exclusions,
        project_exact100_successor_replacement_v3,
    )
    from tests.exact100_successor_v3_fixtures import _base, _exclusion

    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )
    result = project_exact100_successor_replacement_v3(
        base=base, terminal_exclusions=exclusions, replacements=[_minted(_claim())]
    )

    text = methods_disclosure_text(result)

    assert "ranked reserve" in text
    assert "rank 3" in text
    assert "exhausted" not in text
    assert "wider-rank" not in text

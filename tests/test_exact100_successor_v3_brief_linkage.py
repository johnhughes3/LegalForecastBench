"""Linkage-gated classification of an ambiguous supporting-brief spelling.

One receipt spelling means different things in different tranches: in one, the
document spelled ``opening_memorandum`` is the case's only motion; in another it
is the brief filed in support of a separate ``target_motion`` entry.  The
spelling alone cannot decide, and getting it wrong in either direction damages
already-minted evidence -- classifying it a brief empties the first case's
target list, and classifying it a motion gives the second case two motions.

The authenticated validation record decides instead: a record that names the
entries its document supports is a brief; a record that names none is the
motion.  These tests pin both directions and the guards around them.

Fixtures are synthetic throughout (``tests.exact100_successor_v3_fixtures``);
no corpus candidate, document, digest or path appears here.
"""

from __future__ import annotations

import pytest
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    OwnerAdjudicatedReplacementError,
    mint_verified_owner_adjudicated_replacement,
)
from tests.exact100_successor_v3_fixtures import _ROLES, _replacement_inputs

# The motion sits on entry 2 in the shared fixture; the brief is added on 6.
_MOTION_ENTRY = 2
_BRIEF_ENTRY = 6


def _inputs_with_brief(receipt_role: str) -> dict[str, object]:
    """A packet whose motion is joined by a separately docketed brief."""

    roles = (*_ROLES[:2], ("", receipt_role, _BRIEF_ENTRY), *_ROLES[2:])
    return _replacement_inputs("new1", "case000", roles=roles)


def _brief_validation(inputs: dict[str, object]) -> dict[str, object]:
    validations = inputs["byte_role_validation_by_id"]
    assert isinstance(validations, dict)
    record = validations[f"new1-doc-{_BRIEF_ENTRY}"]
    assert isinstance(record, dict)
    return record


def test_an_ambiguous_spelling_without_linkage_is_the_target_motion() -> None:
    """Absence of linkage has to preserve the reading already on disk.

    A minted root whose only motion carries this spelling records that entry as
    its target motion, and it is replayed under whatever code is landed, so the
    unlinked reading is not a default -- it is a compatibility requirement.
    """

    inputs = _inputs_with_brief("opening_memorandum")

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="more than one target motion"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_an_ambiguous_spelling_with_linkage_is_a_supporting_brief() -> None:
    """Declared linkage is what makes the document briefing rather than a motion."""

    inputs = _inputs_with_brief("opening_memorandum")
    _brief_validation(inputs)["linked_motion_entries"] = [_MOTION_ENTRY]

    replacement = mint_verified_owner_adjudicated_replacement(**inputs)

    row = replacement.selection_row
    assert row["target_motion_entry_numbers"] == [_MOTION_ENTRY]
    brief = next(
        document
        for document in row["documents"]
        if document["docket_entry_number"] == _BRIEF_ENTRY
    )
    assert brief["document_role"] == "motion_to_dismiss_memorandum"
    assert brief["model_visible"] is True


def test_linkage_naming_another_entry_refuses() -> None:
    """A brief that supports some other motion is not this packet's briefing."""

    inputs = _inputs_with_brief("opening_memorandum")
    _brief_validation(inputs)["linked_motion_entries"] = [_MOTION_ENTRY + 40]

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="does not name the target motion"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_linkage_naming_the_motion_and_another_entry_refuses() -> None:
    """Naming the target motion is necessary but not sufficient: it must be exact."""

    inputs = _inputs_with_brief("opening_memorandum")
    _brief_validation(inputs)["linked_motion_entries"] = [
        _MOTION_ENTRY,
        _MOTION_ENTRY + 40,
    ]

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="does not name the target motion"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


@pytest.mark.parametrize(
    "value",
    [[], "2", [None], [2.5], {"entry": 2}, [-1]],
    ids=["empty", "string", "null-member", "float", "mapping", "negative"],
)
def test_malformed_linkage_refuses(value: object) -> None:
    """Linkage is an authenticated claim, so an unreadable one fails closed.

    Silently ignoring it would resolve to the unlinked reading and count the
    brief as a second target motion, which is the shape the mint exists to catch.
    """

    inputs = _inputs_with_brief("opening_memorandum")
    _brief_validation(inputs)["linked_motion_entries"] = value

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="linkage is not a list of docket"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_an_unconditional_brief_without_linkage_still_mints() -> None:
    """The unconditional spelling must not acquire a linkage requirement.

    An already-minted root carries this spelling with no linkage recorded, and a
    guard that demanded it would make that root unusable at the first projection
    that included it -- the defect that sank an earlier attempt at this fix.
    """

    inputs = _inputs_with_brief("motion_memorandum")

    replacement = mint_verified_owner_adjudicated_replacement(**inputs)

    assert replacement.selection_row["target_motion_entry_numbers"] == [_MOTION_ENTRY]


def test_an_unconditional_brief_with_linkage_is_still_checked() -> None:
    """Recording linkage on the unconditional spelling still has to be honest."""

    inputs = _inputs_with_brief("motion_memorandum")
    _brief_validation(inputs)["linked_motion_entries"] = [_MOTION_ENTRY + 40]

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="does not name the target motion"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)

"""Behaviour of the v3 exact-100 successor projector and its evidence capability.

Fixtures live in :mod:`tests.exact100_successor_v3_fixtures`; the console-script
surface is covered by :mod:`tests.test_exact100_successor_v3_cli`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import pytest
from legalforecast.ingestion.exact100_successor_v3.projector import (
    Exact100SuccessorReplacementV3Error,
    PromotionProvenanceClass,
    TerminalExclusionGroundV2,
    methods_disclosure_text,
    mint_verified_exact100_v3_terminal_exclusions,
    project_exact100_successor_replacement_v3,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    _AMBIGUOUS_BRIEF_RECEIPT_ROLES,
    _RECEIPT_ROLE_TO_DOCUMENT_ROLE,
    _SUPPORTING_BRIEF_RECEIPT_ROLES,
    OwnerAdjudicatedReplacementError,
    VerifiedOwnerAdjudicatedReplacement,
    mint_verified_owner_adjudicated_replacement,
    require_verified_owner_adjudicated_replacement,
)
from legalforecast.unitization.construct_units import StageADocumentRole
from tests.exact100_successor_v3_fixtures import (
    _ROLES,
    _base,
    _cohort,
    _exclusion,
    _projected,
    _replacement,
    _replacement_inputs,
    _sha,
)

# Receipt spellings that name the target motion itself. Held here rather than in
# the module because the point is to pin the map's motion family against silent
# growth: a new spelling has to be classified in one set or the other, and this
# copy is what makes an unclassified addition fail a test instead of defaulting
# to "target motion".
_TARGET_MOTION_SPELLINGS = {
    "target_motion",
    "target_motion_opening_brief",
    "motion_to_dismiss_memorandum",
    "motion_to_dismiss_notice",
}
#: The three classifications together must cover the map's motion family, and
#: must not overlap: the count assertion below is what makes that a partition
#: rather than merely a cover.
_CLASSIFIED_MOTION_SPELLINGS = (
    _TARGET_MOTION_SPELLINGS
    | _AMBIGUOUS_BRIEF_RECEIPT_ROLES
    | _SUPPORTING_BRIEF_RECEIPT_ROLES
)

# --------------------------------------------------------------------------
# Replacement evidence
# --------------------------------------------------------------------------


def test_replacement_evidence_seals_a_complete_owner_adjudicated_packet() -> None:
    replacement = _replacement("new1", "case000")

    assert replacement.candidate_id == "new1"
    assert replacement.replaces_candidate_id == "case000"
    assert len(replacement.download_manifest) == len(_ROLES)
    assert set(replacement.field_provenance) >= {"case_name", "court", "docket_number"}


def test_replacement_evidence_withholds_the_disposition_from_the_model() -> None:
    """Outcome leakage: the disposition is the one document the model must not see."""

    replacement = _replacement("new1", "case000")
    documents = {
        str(document["document_role"]): document
        for document in replacement.selection_row["documents"]
    }

    assert documents["decision"]["model_visible"] is False
    assert documents["decision"]["contains_target_outcome"] is True
    assert all(
        document["model_visible"] is True
        for role, document in documents.items()
        if role != "decision"
    )


def test_replacement_evidence_refuses_bytes_that_differ_from_the_receipt() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["document_bytes_by_id"]))
    inputs["document_bytes_by_id"][key] = b"%PDF-1.7 tampered\n"

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="differ from the receipt"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_document_without_byte_role_validation() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["byte_role_validation_by_id"].pop(
        next(iter(inputs["byte_role_validation_by_id"]))
    )

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="no byte-role validation"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_role_verdict_that_is_not_a_match() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key]["role_verdict"] = "mismatch"

    with pytest.raises(OwnerAdjudicatedReplacementError, match="not an exact match"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_an_unrecorded_validation_regime() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key].pop("validation_class")

    with pytest.raises(OwnerAdjudicatedReplacementError, match="validation regime"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_an_incomplete_packet() -> None:
    roles = tuple(item for item in _ROLES if item[0] != "decision")
    inputs = _replacement_inputs("new1", "case000", roles=roles)

    with pytest.raises(OwnerAdjudicatedReplacementError, match="packet is incomplete"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_role_outside_the_closed_map() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["documents"][0]["document_role"] = "some_new_tranche_label"

    with pytest.raises(OwnerAdjudicatedReplacementError, match="closed map"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_disposition_naming_another_slot() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["owner_disposition"]["excluded_candidate_id"] = "case099"

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="does not name the excluded slot"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_document_absent_from_the_docket() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["docket_entries_by_number"].pop(1)

    with pytest.raises(OwnerAdjudicatedReplacementError, match="docket snapshot lacks"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_missing_identity_provenance() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["field_provenance"].pop("case_name")

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="lack recorded provenance"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


# --------------------------------------------------------------------------
# Terminal exclusions
# --------------------------------------------------------------------------


def test_terminal_exclusions_admit_more_than_one_candidate() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
            _exclusion("case002", selection_bytes=base.selection_bytes),
        ],
    )

    assert exclusions.candidate_ids == ("case000", "case001", "case002")


def test_terminal_exclusions_admit_the_owner_judgment_ground() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion(
                "case000",
                selection_bytes=base.selection_bytes,
                ground=(
                    TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
                ),
            )
        ],
    )

    record = exclusions.records[0]
    assert record["evidence_class"] == "recorded_owner_adjudication"
    assert record["evidence_commitments"] == {}


def test_terminal_exclusion_requires_an_owner_authorization_citation() -> None:
    base = _base()
    entry = _exclusion("case000", selection_bytes=base.selection_bytes)
    entry["owner_authorization_commitments"] = {}

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="owner authorization citation"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


def test_detector_exclusion_must_bind_the_predecessor_selection() -> None:
    base = _base()
    entry = _exclusion("case000", selection_bytes=base.selection_bytes)
    entry["evidence_commitments"]["selection"] = _sha(b"another selection")

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="different exact selection"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


def test_owner_judgment_exclusion_may_not_claim_detector_evidence() -> None:
    base = _base()
    entry = _exclusion(
        "case000",
        selection_bytes=base.selection_bytes,
        ground=(
            TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
        ),
    )
    entry["evidence_commitments"] = {"selection": _sha(base.selection_bytes)}

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="must not claim detector evidence"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


def test_three_paired_swaps_keep_the_cohort_at_exactly_100_unique_cases() -> None:
    result = _projected()
    ids = [row["candidate_id"] for row in result.selection]

    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert {"case000", "case001", "case002"}.isdisjoint(ids)
    assert {"new0", "new1", "new2"} <= set(ids)
    assert result.state["selected_case_count"] == 100
    assert result.state["terminal_exclusion_count"] == 3
    assert result.state["promotion_count"] == 3


def test_every_promotion_records_its_provenance_class_explicitly() -> None:
    result = _projected()

    assert all(
        record["provenance_class"] == PromotionProvenanceClass.OWNER_ADJUDICATED.value
        for record in result.promotions
    )
    assert all(record["wider_rank"] is None for record in result.promotions)
    assert {record["replaces_candidate_id"] for record in result.promotions} == {
        "case000",
        "case001",
        "case002",
    }


def test_an_exclusion_without_its_paired_replacement_refuses() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
        ],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="exactly one paired replacement"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("new0", "case000")],
        )


def test_one_replacement_cannot_fill_two_slots() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
        ],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="promoted into two slots"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[
                _replacement("new0", "case000"),
                _replacement("new0", "case001"),
            ],
        )


def test_a_replacement_already_in_the_cohort_refuses() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="already inside the predecessor"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("case099", "case000")],
        )


def test_exclusions_bound_to_another_selection_refuse() -> None:
    base = _base()
    other = _base(_cohort(100))
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=other.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=other.selection_bytes)],
    )
    object.__setattr__(exclusions, "selection_sha256", _sha(b"forged"))

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="different predecessor selection"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("new0", "case000")],
        )


def test_a_caller_constructed_replacement_is_rejected() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )
    forged = object.__new__(VerifiedOwnerAdjudicatedReplacement)

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="not produced by verified minting"
    ):
        project_exact100_successor_replacement_v3(
            base=base, terminal_exclusions=exclusions, replacements=[forged]
        )


def test_methods_disclosure_names_the_owner_adjudicated_count_and_pairs() -> None:
    text = methods_disclosure_text(_projected())

    assert text.startswith("3 exact-100 replacements entered the cohort")
    assert "owner adjudication" in text
    assert "new0 for case000" in text


# --------------------------------------------------------------------------
# Defects found in review round 1
# --------------------------------------------------------------------------


def test_manifest_local_path_resolves_against_the_successor_document_tree() -> None:
    """The path a consumer resolves must be the path the bytes are written to."""

    replacement = _replacement("new1", "case000")

    for row in replacement.download_manifest:
        local_path = str(row["local_path"])
        assert local_path == f"new1/{row['source_document_id']}.pdf"
        # The projector writes document_bytes under
        # owner-adjudicated-source/<key minus "documents/">, so this equality is
        # what makes local_path resolve there.
        assert f"documents/{local_path}" in replacement.document_bytes


def test_mutating_a_minted_replacement_is_detected() -> None:
    """The seal alone cannot see a reached-into record; the commitment can."""

    replacement = _replacement("new1", "case000")
    decision = next(
        document
        for document in replacement.selection_row["documents"]
        if document["document_role"] == "decision"
    )
    decision["model_visible"] = True

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="changed after verified minting"
    ):
        require_verified_owner_adjudicated_replacement(replacement)


def test_a_verdict_about_another_role_refuses() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key]["requested_role"] = "decision"

    with pytest.raises(OwnerAdjudicatedReplacementError, match="for a different role"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_a_verdict_labelled_differently_but_meaning_the_same_role_is_accepted() -> None:
    """Tranches label the same document differently; the corpus role decides."""

    inputs = _replacement_inputs("new1", "case000")
    target = "new1-doc-2"
    inputs["byte_role_validation_by_id"][target]["requested_role"] = (
        "target_motion_opening_brief"
    )

    replacement = mint_verified_owner_adjudicated_replacement(**inputs)

    assert replacement.candidate_id == "new1"


def test_a_separately_docketed_brief_in_support_mints_as_briefing() -> None:
    """A brief in support on its own entry is briefing, not an unmapped label.

    Both halves of the split carry the corpus memorandum role, so the packet
    holds two.  The mapped role is asserted rather than mere acceptance: Stage A
    refuses every other spelling and the model packet mounts only the complaint
    family, the notice and the brief roles, so a mapping that satisfied this
    module alone would drop the document out of the prompt.
    """

    roles = (*_ROLES[:2], ("", "motion_memorandum", 6), *_ROLES[2:])
    inputs = _replacement_inputs("new1", "case000", roles=roles)
    memorandum = StageADocumentRole.MTD_MEMORANDUM.value

    documents = mint_verified_owner_adjudicated_replacement(**inputs).selection_row[
        "documents"
    ]

    supporting = next(
        item for item in documents if item["source_document_id"].endswith("6")
    )
    assert supporting["document_role"] == memorandum
    assert supporting["model_visible"] is True
    assert supporting["contains_target_outcome"] is False
    assert [document["document_role"] for document in documents].count(memorandum) == 2
    assert _RECEIPT_ROLE_TO_DOCUMENT_ROLE["motion_memorandum"] == memorandum


def test_a_brief_in_support_is_not_counted_as_the_target_motion() -> None:
    """The corpus records the motion's own entry, never the brief's as well.

    Selecting on the receipt spelling is what makes this possible: both halves
    of the split share one corpus role, so the mapped role cannot tell them
    apart, and a second entry here would strand the promotion at the readiness
    gate, which counts exactly one target motion per case.
    """

    roles = (*_ROLES[:2], ("", "motion_memorandum", 6), *_ROLES[2:])
    inputs = _replacement_inputs("new1", "case000", roles=roles)

    replacement = mint_verified_owner_adjudicated_replacement(**inputs)

    assert replacement.selection_row["target_motion_entry_numbers"] == [2]


def test_a_packet_holding_only_a_brief_in_support_refuses() -> None:
    """The brief satisfies the required roles, so the motion check must refuse."""

    motion, *rest = _ROLES[1:]
    roles = (_ROLES[0], ("", "motion_memorandum", motion[2]), *rest)
    inputs = _replacement_inputs("new1", "case000", roles=roles)

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="needs a target motion document"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_a_packet_naming_two_target_motions_refuses() -> None:
    """Two motions is a packet-construction error, not a shape to emit."""

    roles = (*_ROLES[:2], ("", "motion_to_dismiss_notice", 6), *_ROLES[2:])
    inputs = _replacement_inputs("new1", "case000", roles=roles)

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="more than one target motion"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def _unclassified_motion_spellings(mapping: Mapping[str, str]) -> set[str]:
    """Receipt spellings that map to a motion role without being classified.

    An unclassified spelling counts as the target motion by default, so this
    returning anything is the silent hazard, not a style complaint.
    """

    motion_roles = {
        StageADocumentRole.MTD_MEMORANDUM.value,
        StageADocumentRole.MTD_NOTICE.value,
    }
    return {
        receipt
        for receipt, role in mapping.items()
        if role in motion_roles and receipt not in _CLASSIFIED_MOTION_SPELLINGS
    }


def test_every_motion_family_receipt_spelling_is_classified() -> None:
    """Map growth must force a decision among the three classifications.

    A spelling is the motion, or briefing in support of it, or ambiguous between
    the two and resolved by declared linkage.  Leaving a new one unclassified
    silently makes it the motion, which is how a packet acquires a second one.
    """

    motion_roles = {
        StageADocumentRole.MTD_MEMORANDUM.value,
        StageADocumentRole.MTD_NOTICE.value,
    }
    mtd_spellings = {
        receipt
        for receipt, role in _RECEIPT_ROLE_TO_DOCUMENT_ROLE.items()
        if role in motion_roles
    }

    assert mtd_spellings == _CLASSIFIED_MOTION_SPELLINGS
    assert len(_TARGET_MOTION_SPELLINGS) + len(_AMBIGUOUS_BRIEF_RECEIPT_ROLES) + len(
        _SUPPORTING_BRIEF_RECEIPT_ROLES
    ) == len(_CLASSIFIED_MOTION_SPELLINGS)
    assert _unclassified_motion_spellings(_RECEIPT_ROLE_TO_DOCUMENT_ROLE) == set()


def test_the_classification_fence_trips_on_an_unclassified_motion_spelling() -> None:
    """The fence has to fail on map growth, or it is not a fence.

    Simulates a later tranche adding a motion-family spelling and leaving it
    unclassified, which is the shape that would otherwise mint a brief-only
    packet with the brief silently named as the target motion.
    """

    grown = {
        **_RECEIPT_ROLE_TO_DOCUMENT_ROLE,
        "brief_in_support": StageADocumentRole.MTD_MEMORANDUM.value,
    }

    assert _unclassified_motion_spellings(grown) == {"brief_in_support"}


def test_two_documents_on_one_entry_name_one_target_motion() -> None:
    """One docket entry can carry a main document and its attachments.

    Those are separate documents naming a single motion, so the packet is
    counted by distinct entry rather than by document -- and the emitted row
    carries that entry once, because a repeated entry reads downstream as two
    target motions.
    """

    roles = (*_ROLES[:2], ("", "target_motion_opening_brief", 2), *_ROLES[2:])
    inputs = _replacement_inputs("new1", "case000", roles=roles)
    inputs["documents"][2]["source_document_id"] = "new1-doc-2b"
    inputs["document_bytes_by_id"]["new1-doc-2b"] = b"%PDF-1.7 synthetic attachment\n"
    payload = inputs["document_bytes_by_id"]["new1-doc-2b"]
    digest = hashlib.sha256(payload).hexdigest()
    inputs["documents"][2]["sha256"] = digest
    inputs["documents"][2]["byte_count"] = len(payload)
    inputs["byte_role_validation_by_id"]["new1-doc-2b"] = {
        "encrypted": False,
        "pdf_byte_count": len(payload),
        "pdf_sha256": digest,
        "requested_role": "target_motion_opening_brief",
        "role_verdict": "match",
        "source_document_id": "new1-doc-2b",
        "strict_parse": "pass",
        "structural_defects": [],
        "validation_class": "document_repair_byte_role_verdict",
    }
    inputs["docket_entries_by_number"][2]["recap_documents"].append(
        {"id": "new1-doc-2b"}
    )

    replacement = mint_verified_owner_adjudicated_replacement(**inputs)

    assert replacement.selection_row["target_motion_entry_numbers"] == [2]


def test_purchased_documents_are_not_counted_as_free() -> None:
    replacement = _replacement("new1", "case000")
    purchased = sum(
        1
        for row in replacement.download_manifest
        if row["free_or_purchased"] == "purchased"
    )

    assert purchased == 2
    assert replacement.selection_row["free_required_document_count"] == (
        len(replacement.download_manifest) - purchased
    )


def test_an_unknown_restriction_row_without_the_full_evidence_set_refuses() -> None:
    """v2's public-use property, held on the surface where new rows enter."""

    cohort = _cohort()
    row = cohort["restriction_evidence"][0]
    row["restriction_status"] = "unknown"
    row["restriction_evidence"] = ["courtlistener_rest_docket_exact_match"]

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="not cleared and public"
    ):
        _base(cohort)


def test_an_unknown_restriction_row_with_the_full_evidence_set_is_accepted() -> None:
    cohort = _cohort()
    row = cohort["restriction_evidence"][0]
    row["restriction_status"] = "unknown"
    row["restriction_evidence"] = [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_true",
        "courtlistener_rest_recap_document_is_sealed_unknown",
        "courtlistener_rest_public_download_url_allowlisted",
    ]

    assert _base(cohort).selection_bytes

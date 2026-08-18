"""One selector, two seams: which derivation model replays frozen evidence.

Both seams here answer the same question the parser-model registry (#866) and
the parse-quality regime (#869) already answer for their own surfaces: a frozen
artifact serializes *derived* values, the deriving code was deliberately
broadened afterwards, and replaying old evidence through new code compares two
models instead of checking byte identity.

These tests pin the properties that make the selection safe rather than
convenient:

* the closed maps hold exactly the audited digests and nothing else;
* an unpinned digest keeps the current model, so nothing outside the audit can
  reach a preserved one;
* an unrecognized regime name refuses instead of reading as "no model";
* the preserved models reproduce the frozen verdicts, and the current models
  reproduce today's;
* the bytes a stage will consume stay on the current model.

Document excerpts below are verbatim title and body fragments of the four
frozen exact-100 target documents, quoted through the collect-all sweep's
evidence.  They stand in for the frozen corpus so the suite stays hermetic; the
whole-corpus proof is separate and is recorded on bead ``legalforecastbench-0jyz``
(all 101 persisted audit rows recomputed from the frozen Markdown: the pre-#767
detector disagrees with the persisted audit on zero rows, the current detector
on exactly three).
"""

from __future__ import annotations

import pytest
from legalforecast.ingestion.frozen_replay_model_regime import (
    FROZEN_PREDECESSOR_TARGET_ELIGIBILITY_REGIME,
    FROZEN_V2_OPERATIVE_COMPLAINT_REGIME,
    OPERATIVE_COMPLAINT_REGIME_CURRENT,
    OPERATIVE_COMPLAINT_REGIME_PRE_667,
    TARGET_ELIGIBILITY_REGIME_CURRENT,
    TARGET_ELIGIBILITY_REGIME_PRE_767,
    FrozenReplayRegimeError,
    active_operative_complaint_regime,
    frozen_predecessor_target_eligibility_regime,
    operative_complaint_regime_names,
    operative_complaint_regime_scope,
    replay_operative_complaint_regime,
    replay_target_eligibility_regime,
    resolve_operative_complaint_regime,
    resolve_target_eligibility_regime,
    target_eligibility_regime_names,
)
from legalforecast.ingestion.courtlistener_web import CourtListenerWebDocketEntry
from legalforecast.ingestion.operative_complaint import (
    OperativeComplaintKind,
    select_operative_complaint_entry,
)
from legalforecast.ingestion.target_document_eligibility import (
    is_stipulated_or_voluntary_target_document,
)

# The stages 31/32 parse manifest the stipulated-eligibility audit replays.
_PINNED_PARSE_MANIFEST_SHA256 = (
    "f0059a6c19afec540331337a4f8e5ba89a7802f886180943b318bde7bf35bcc6"
)
# The wider public plan's own completed run card, already the sealed
# ``wider_plan_run_card`` authority in the CLI.
_PINNED_PLAN_RUN_CARD_SHA256 = (
    "47199b60715c838efbb7adc21d5677049ca70ceb5a06e21597432d90abdbfc38"
)
_UNPINNED_SHA256 = "0" * 64

# --- the three rows #767 flips, and the one row it does not ----------------
# All four are in the frozen exact-100 cohort.  The first three are true
# positives the current detector catches and the frozen audit records as
# eligible; the fourth is the single ineligible target the frozen audit does
# record, and both generations must agree on it.

_STIPULATION_TITLE = (
    "# STIPULATION TO DISMISS\n\nThe parties, by counsel, hereby stipulate that "
    "this action be voluntarily dismissed with prejudice.\n"
)
_PLAINTIFF_SETTLEMENT_MOTION = (
    "# PLAINTIFF'S MOTION TO DISMISS WITH PREJUDICE\n\n"
    "The parties have reached a full and final settlement resolving all claims "
    "in this action. The parties executed a written Settlement Agreement and "
    "Mutual Release, and Plaintiff agreed to file a Motion to Dismiss with "
    "Prejudice.\n"
)
_PRO_SE_SETTLEMENT_MOTION = (
    "# MOTION TO DISMISS\n\nNOEW COMES Plaintiff, Derrance Harris move to "
    "dismiss, states that the parties have resolve this matter, and have "
    "entered confidential release.\n"
)
_RULE_41_STIPULATION = (
    "# JOINT STIPULATION OF DISMISSAL\n\nPursuant to Rule 41(a)(1)(A)(ii), the "
    "parties stipulate to the dismissal of this action with prejudice.\n"
)
_NOTICE_OF_VOLUNTARY_DISMISSAL = (
    "# NOTICE OF VOLUNTARY DISMISSAL\n\nPlaintiff hereby gives notice of the "
    "voluntary dismissal of this action.\n"
)
_ADVERSARIAL_DEFENDANT_MTD = (
    "# DEFENDANT'S MOTION TO DISMISS\n\nDefendant moves to dismiss the complaint "
    "under Rule 12(b)(6) for failure to state a claim upon which relief may be "
    "granted.\n"
)

_FLIPPED_BY_767 = (
    pytest.param(_STIPULATION_TITLE, id="68941639-stipulation-to-dismiss"),
    pytest.param(_PLAINTIFF_SETTLEMENT_MOTION, id="73209444-settlement-mutual-release"),
    pytest.param(_PRO_SE_SETTLEMENT_MOTION, id="73325674-pro-se-confidential-release"),
)


def _stipulated(markdown: str, *, regime: str) -> bool:
    return is_stipulated_or_voluntary_target_document(
        candidate_id="candidate",
        source_document_id="document",
        document_role="motion_to_dismiss_notice",
        markdown=markdown,
        regime=regime,
    )


# ---------------------------------------------------------------------------
# The closed maps
# ---------------------------------------------------------------------------


def test_the_pinned_maps_hold_exactly_the_audited_digests() -> None:
    """A closed mapping is the whole security argument; keep it visible."""

    assert dict(FROZEN_PREDECESSOR_TARGET_ELIGIBILITY_REGIME) == {
        _PINNED_PARSE_MANIFEST_SHA256: TARGET_ELIGIBILITY_REGIME_PRE_767
    }
    assert dict(FROZEN_V2_OPERATIVE_COMPLAINT_REGIME) == {
        _PINNED_PLAN_RUN_CARD_SHA256: OPERATIVE_COMPLAINT_REGIME_PRE_667
    }


def test_regime_names_are_closed() -> None:
    assert target_eligibility_regime_names() == (
        TARGET_ELIGIBILITY_REGIME_CURRENT,
        TARGET_ELIGIBILITY_REGIME_PRE_767,
    )
    assert operative_complaint_regime_names() == (
        OPERATIVE_COMPLAINT_REGIME_CURRENT,
        OPERATIVE_COMPLAINT_REGIME_PRE_667,
    )


@pytest.mark.parametrize("prefix", ["", "sha256:"])
def test_the_pinned_parse_manifest_selects_the_preserved_detector(
    prefix: str,
) -> None:
    assert (
        frozen_predecessor_target_eligibility_regime(
            f"{prefix}{_PINNED_PARSE_MANIFEST_SHA256}"
        )
        == TARGET_ELIGIBILITY_REGIME_PRE_767
    )


def test_an_unpinned_parse_manifest_keeps_the_current_detector() -> None:
    assert (
        frozen_predecessor_target_eligibility_regime(_UNPINNED_SHA256)
        == TARGET_ELIGIBILITY_REGIME_CURRENT
    )


@pytest.mark.parametrize("prefix", ["", "sha256:"])
def test_the_pinned_run_card_selects_the_preserved_classifier(prefix: str) -> None:
    assert (
        replay_operative_complaint_regime(
            public_plan_run_card_sha256=f"{prefix}{_PINNED_PLAN_RUN_CARD_SHA256}"
        )
        == OPERATIVE_COMPLAINT_REGIME_PRE_667
    )


def test_an_unpinned_run_card_keeps_the_current_classifier() -> None:
    """The historical packet's plan root, and every live planning caller."""

    assert (
        replay_operative_complaint_regime(public_plan_run_card_sha256=_UNPINNED_SHA256)
        == OPERATIVE_COMPLAINT_REGIME_CURRENT
    )


# ---------------------------------------------------------------------------
# Seam 7: the two-condition rule, in full
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("frozen_predecessor_replay", "digest", "expected"),
    [
        (True, _PINNED_PARSE_MANIFEST_SHA256, TARGET_ELIGIBILITY_REGIME_PRE_767),
        (True, _UNPINNED_SHA256, TARGET_ELIGIBILITY_REGIME_CURRENT),
        (False, _PINNED_PARSE_MANIFEST_SHA256, TARGET_ELIGIBILITY_REGIME_CURRENT),
        (False, _UNPINNED_SHA256, TARGET_ELIGIBILITY_REGIME_CURRENT),
    ],
)
def test_a_preserved_detector_needs_both_conditions(
    frozen_predecessor_replay: bool, digest: str, expected: str
) -> None:
    """Both conditions, and the case that matters most: flagged but unpinned.

    A caller that asserts the frozen-predecessor routing fact by accident still
    gets today's detector for every manifest except the audited one, because
    the closed digest map -- not the caller's assertion -- is the enforcing
    boundary.
    """

    assert (
        replay_target_eligibility_regime(
            parser_manifest_sha256=digest,
            frozen_predecessor_replay=frozen_predecessor_replay,
        )
        == expected
    )


# ---------------------------------------------------------------------------
# Fail closed on an unrecognized name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["", "none", "pre-767", "current "])
def test_an_unpinned_detector_name_refuses(name: str) -> None:
    with pytest.raises(FrozenReplayRegimeError, match="not pinned"):
        resolve_target_eligibility_regime(name)


@pytest.mark.parametrize("name", ["", "none", "pre-667", "disabled"])
def test_an_unpinned_classifier_name_refuses(name: str) -> None:
    with pytest.raises(FrozenReplayRegimeError, match="not pinned"):
        resolve_operative_complaint_regime(name)


def test_an_unpinned_name_refuses_before_any_planning_runs() -> None:
    """The scope resolves on entry, so a stray name never reaches the planner."""

    with pytest.raises(FrozenReplayRegimeError, match="not pinned"):
        with operative_complaint_regime_scope("pre-667"):  # pragma: no cover
            raise AssertionError("scope body must not run")
    assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_CURRENT


def test_an_unrecognized_regime_refuses_the_eligibility_call() -> None:
    with pytest.raises(FrozenReplayRegimeError, match="not pinned"):
        _stipulated(_ADVERSARIAL_DEFENDANT_MTD, regime="pre-767")


# ---------------------------------------------------------------------------
# Seam 7: the preserved detector reproduces the frozen verdicts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("markdown", _FLIPPED_BY_767)
def test_the_current_detector_catches_the_three_settlement_dismissals(
    markdown: str,
) -> None:
    """#767 is right on the merits; these are true positives, not noise."""

    assert _stipulated(markdown, regime=TARGET_ELIGIBILITY_REGIME_CURRENT) is True


@pytest.mark.parametrize("markdown", _FLIPPED_BY_767)
def test_the_preserved_detector_reproduces_the_frozen_eligible_verdict(
    markdown: str,
) -> None:
    """The frozen 2026-08-07 audit recorded all three as eligible.

    Replaying it under the detector contemporaneous with its mint reproduces
    that verdict, which is what byte equality with the persisted audit needs.
    The finding is not suppressed -- it is tracked for owner adjudication.
    """

    assert _stipulated(markdown, regime=TARGET_ELIGIBILITY_REGIME_PRE_767) is False


@pytest.mark.parametrize(
    "markdown",
    [
        pytest.param(_RULE_41_STIPULATION, id="rule-41-a-1-A-ii"),
        pytest.param(_NOTICE_OF_VOLUNTARY_DISMISSAL, id="notice-of-voluntary"),
    ],
)
def test_both_generations_agree_on_the_one_frozen_ineligible_target(
    markdown: str,
) -> None:
    """The audit's single ineligible row must survive the preserved detector.

    ``_replay_exact100_stipulated_eligibility_unchecked`` requires exactly one
    ineligible target.  A preserved detector that lost this row would refuse
    the replay just as loudly as one that added rows.
    """

    assert _stipulated(markdown, regime=TARGET_ELIGIBILITY_REGIME_CURRENT) is True
    assert _stipulated(markdown, regime=TARGET_ELIGIBILITY_REGIME_PRE_767) is True


def test_an_adversarial_defendant_motion_is_eligible_under_both() -> None:
    """The seam must not make a contested Rule 12(b)(6) motion ineligible."""

    assert _stipulated(_ADVERSARIAL_DEFENDANT_MTD, regime="current") is False
    assert (
        _stipulated(
            _ADVERSARIAL_DEFENDANT_MTD, regime=TARGET_ELIGIBILITY_REGIME_PRE_767
        )
        is False
    )


def test_the_eligibility_default_is_the_current_detector() -> None:
    """Bytes a stage will consume face today's detector, never a preserved one.

    ``require_eligible_target_document`` is what the live Stage A path calls;
    its default must stay current so a document entering Stage A today is
    judged by today's model.
    """

    assert (
        is_stipulated_or_voluntary_target_document(
            candidate_id="candidate",
            source_document_id="document",
            document_role="motion_to_dismiss_notice",
            markdown=_PLAINTIFF_SETTLEMENT_MOTION,
        )
        is True
    )


# ---------------------------------------------------------------------------
# Seam 12: the scoped classifier generation
# ---------------------------------------------------------------------------


def _counterclaim_entry(entry_number: int = 4) -> CourtListenerWebDocketEntry:
    return CourtListenerWebDocketEntry(
        row_id=f"entry-{entry_number}",
        entry_number=str(entry_number),
        filed_at="Jul 2, 2026",
        text=(
            f"{entry_number} Jul 2, 2026 COUNTERCLAIM against Plaintiff filed by "
            "Defendant."
        ),
        documents=(),
    )


def test_the_current_classifier_names_a_counterclaim() -> None:
    selection = select_operative_complaint_entry(
        (_counterclaim_entry(),), before_entry=10
    )
    assert selection is not None
    assert selection.kind is OperativeComplaintKind.COUNTERCLAIM


def test_the_preserved_classifier_predates_the_counterclaim_kind() -> None:
    """#667 added ``_non_complaint_claim_kind``; before it, the label fell through.

    Returning ``None`` from that function *is* the pre-#667 model rather than an
    approximation of it, because the function did not exist.
    """

    selection = select_operative_complaint_entry(
        (_counterclaim_entry(),),
        before_entry=10,
        regime=OPERATIVE_COMPLAINT_REGIME_PRE_667,
    )
    assert (
        selection is None or selection.kind is not OperativeComplaintKind.COUNTERCLAIM
    )


def test_the_scope_binds_the_classifier_without_a_parameter() -> None:
    """The planner is never threaded; the scope is what reaches it."""

    entries = (_counterclaim_entry(),)
    assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_CURRENT
    with operative_complaint_regime_scope(OPERATIVE_COMPLAINT_REGIME_PRE_667):
        assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_PRE_667
        scoped = select_operative_complaint_entry(entries, before_entry=10)
    unscoped = select_operative_complaint_entry(entries, before_entry=10)

    assert unscoped is not None
    assert unscoped.kind is OperativeComplaintKind.COUNTERCLAIM
    assert scoped is None or scoped.kind is not OperativeComplaintKind.COUNTERCLAIM


def test_an_explicit_regime_overrides_the_active_scope() -> None:
    with operative_complaint_regime_scope(OPERATIVE_COMPLAINT_REGIME_PRE_667):
        selection = select_operative_complaint_entry(
            (_counterclaim_entry(),),
            before_entry=10,
            regime=OPERATIVE_COMPLAINT_REGIME_CURRENT,
        )
    assert selection is not None
    assert selection.kind is OperativeComplaintKind.COUNTERCLAIM


def test_the_scope_resets_even_when_the_body_raises() -> None:
    """A leaked binding would silently version unrelated live planning."""

    with pytest.raises(RuntimeError, match="boom"):
        with operative_complaint_regime_scope(OPERATIVE_COMPLAINT_REGIME_PRE_667):
            raise RuntimeError("boom")
    assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_CURRENT


def test_nested_scopes_restore_the_outer_binding() -> None:
    with operative_complaint_regime_scope(OPERATIVE_COMPLAINT_REGIME_PRE_667):
        with operative_complaint_regime_scope(OPERATIVE_COMPLAINT_REGIME_CURRENT):
            assert (
                active_operative_complaint_regime()
                == OPERATIVE_COMPLAINT_REGIME_CURRENT
            )
        assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_PRE_667
    assert active_operative_complaint_regime() == OPERATIVE_COMPLAINT_REGIME_CURRENT

"""Deterministic semantic eligibility for Stage A target documents."""

from __future__ import annotations

import re

from legalforecast.ingestion.frozen_replay_model_regime import (
    TARGET_ELIGIBILITY_REGIME_CURRENT,
    resolve_target_eligibility_regime,
)
from legalforecast.ingestion.provenance import DocumentRole

# The title pattern exactly as it stood before PR #767 (``a73dde0d``,
# 2026-08-16), preserved so a frozen audit minted under it replays under it.
# See ``frozen_replay_model_regime``; never applied to bytes entering Stage A.
_PRE_767_STIPULATED_TITLE = (
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\[?proposed\]?\s+)?"
    r"(?:(?:joint\s+)?stipulation\s+(?:for\s+(?:and\s+)?order\s+of|of)\s+"
    r"dismissal|stipulated\s+motion\s+to\s+dismiss|notice\s+of\s+voluntary\s+"
    r"dismissal)\s*$"
)

# Today's production title pattern.  #767 additionally catches "stipulation to
# dismiss", a bare "…order of dismiss", and joint motions to dismiss.
_CURRENT_STIPULATED_TITLE = (
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\[?proposed\]?\s+)?"
    r"(?:(?:joint\s+)?stipulation\s+(?:for\s+(?:and\s+)?order\s+of|of|to)\s+"
    r"dismiss(?:al)?|(?:joint|stipulated)\s+motion\s+to\s+dismiss|"
    r"notice\s+of\s+voluntary\s+dismissal)\s*$"
)


class TargetDocumentEligibilityError(ValueError):
    """Raised when a target-role document is semantically ineligible."""


def require_eligible_target_document(
    *,
    candidate_id: str,
    source_document_id: str,
    document_role: DocumentRole | str,
    markdown: str,
    regime: str = TARGET_ELIGIBILITY_REGIME_CURRENT,
) -> None:
    """Reject strong parsed-body evidence that a target MTD role is false.

    ``regime`` names the detector generation to apply.  Every caller gets
    today's production detector by default; only a replay of frozen evidence
    whose authenticated parse manifest is pinned in
    ``frozen_replay_model_regime`` may pass anything else, and an unrecognized
    name fails closed rather than reading as "no detector".
    """

    model = resolve_target_eligibility_regime(regime)
    try:
        role = DocumentRole(document_role)
    except ValueError as exc:
        raise TargetDocumentEligibilityError(
            f"unsupported target document role: {document_role}"
        ) from exc
    if role not in {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}:
        return
    opening = "\n".join(markdown.splitlines()[:120])
    stipulated_or_voluntary_title = re.search(
        (
            _CURRENT_STIPULATED_TITLE
            if model.detects_settlement_driven_dismissals
            else _PRE_767_STIPULATED_TITLE
        ),
        opening,
    )
    party_motion_title = re.search(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:plaintiffs?|petitioners?)"
        r"(?:['\u2019]s?)?\s+motion\s+to\s+dismiss\b",
        opening,
    )
    party_mover = re.search(
        r"(?is)\b(?:plaintiffs?|petitioners?)\b.{0,240}"
        r"\bmove[s]?\s+to\s+dismiss\b",
        opening,
    )
    defendant_mover = re.search(
        r"(?im)^\s*(?:#{1,6}\s*)?defendants?(?:['\u2019]s?)?"
        r".{0,80}\bmotion\s+to\s+dismiss\b",
        opening,
    ) or re.search(
        r"(?is)\bdefendants?\b.{0,160}\bmove[s]?\s+to\s+dismiss\b",
        opening,
    )
    settlement_signal = re.search(
        r"(?is)\b(?:settlement|settled|mutual\s+release|confidential\s+release|"
        r"resolv(?:e|ed)\s+(?:this|the)\s+(?:matter|action|case)|"
        r"agreed\s+to\s+(?:voluntarily\s+)?dismiss|"
        r"voluntar(?:y|ily)\s+dismiss(?:al|ed)?)\b",
        opening,
    )
    # Settlement-driven dismissals can be captioned as ordinary MTDs.  Bind the
    # signal to a plaintiff/petitioner movant and reject an explicit defendant
    # movant, which preserves contested motions enforcing a prior release.
    party_settlement_dismissal = bool(
        (party_motion_title or party_mover)
        and not defendant_mover
        and settlement_signal
    )
    joint_dismissal_agreement = re.search(
        r"(?is)\b(?:the\s+)?parties\b.{0,160}\b(?:hereby\s+)?"
        r"(?:jointly\s+move|agree(?:d)?|stipulate(?:d)?)\s+to\s+"
        r"(?:voluntarily\s+)?dismiss\b",
        opening,
    )
    rule_41_stipulation = re.search(
        r"(?is)\brule\s+41\s*\(a\)\s*\(1\)\s*\(a\)\s*\(ii\).{0,800}"
        r"\b(?:parties\s+(?:stipulate|agree)|parties['\u2019]?\s+stipulation)\b",
        opening,
    ) or re.search(
        r"(?is)\b(?:parties\s+(?:stipulate|agree)|parties['\u2019]?\s+stipulation)"
        r"\b.{0,800}\brule\s+41\s*\(a\)\s*\(1\)\s*\(a\)\s*\(ii\)",
        opening,
    )
    # The settlement-driven clauses are #767's addition and exist only under the
    # current detector.  Under the preserved generation the title and Rule 41
    # tests stand alone, which is exactly the pre-#767 disjunction.
    settlement_driven = model.detects_settlement_driven_dismissals and (
        party_settlement_dismissal
        or bool(joint_dismissal_agreement and not defendant_mover)
    )
    if stipulated_or_voluntary_title or rule_41_stipulation or settlement_driven:
        raise TargetDocumentEligibilityError(
            "target motion document is a stipulated or voluntary dismissal filing: "
            f"{candidate_id}/{source_document_id}"
        )


def is_stipulated_or_voluntary_target_document(
    *,
    candidate_id: str,
    source_document_id: str,
    document_role: DocumentRole | str,
    markdown: str,
    regime: str = TARGET_ELIGIBILITY_REGIME_CURRENT,
) -> bool:
    """Return whether the shared target gate rejects the parsed document."""

    try:
        role = DocumentRole(document_role)
    except ValueError as exc:
        raise TargetDocumentEligibilityError(
            f"unsupported target document role: {document_role}"
        ) from exc
    try:
        require_eligible_target_document(
            candidate_id=candidate_id,
            source_document_id=source_document_id,
            document_role=role,
            markdown=markdown,
            regime=regime,
        )
    except TargetDocumentEligibilityError:
        return True
    return False

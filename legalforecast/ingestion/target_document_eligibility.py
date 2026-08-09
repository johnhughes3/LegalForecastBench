"""Deterministic semantic eligibility for Stage A target documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from legalforecast.ingestion.provenance import DocumentRole


class TargetDocumentIneligibilityReason(StrEnum):
    """Strong parsed-body grounds that disqualify a purported target document."""

    STIPULATED_OR_VOLUNTARY_DISMISSAL_TITLE = "stipulated_or_voluntary_dismissal_title"
    RULE_41_A_1_A_II_STIPULATION = "rule_41_a_1_a_ii_stipulation"


@dataclass(frozen=True, slots=True)
class TargetDocumentEligibility:
    """Provider-free semantic result for one authenticated target document."""

    reason: TargetDocumentIneligibilityReason | None

    @property
    def is_eligible(self) -> bool:
        """Return whether the supplied target document passes this narrow gate."""

        return self.reason is None


def evaluate_target_document_eligibility(
    *,
    document_role: DocumentRole | str,
    markdown: str,
) -> TargetDocumentEligibility:
    """Evaluate the v4 target-document predicate from supplied document text only."""

    role = DocumentRole(document_role)
    if role not in {DocumentRole.MTD_NOTICE, DocumentRole.MTD_MEMORANDUM}:
        return TargetDocumentEligibility(reason=None)

    opening = "\n".join(markdown.splitlines()[:120])
    stipulated_or_voluntary_title = re.search(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\[?proposed\]?\s+)?"
        r"(?:(?:joint\s+)?stipulation\s+(?:for\s+(?:and\s+)?order\s+of|of)\s+"
        r"dismissal|stipulated\s+motion\s+to\s+dismiss|notice\s+of\s+voluntary\s+"
        r"dismissal)\s*$",
        opening,
    )
    if stipulated_or_voluntary_title:
        return TargetDocumentEligibility(
            reason=TargetDocumentIneligibilityReason.STIPULATED_OR_VOLUNTARY_DISMISSAL_TITLE
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
    if rule_41_stipulation:
        return TargetDocumentEligibility(
            reason=TargetDocumentIneligibilityReason.RULE_41_A_1_A_II_STIPULATION
        )
    return TargetDocumentEligibility(reason=None)

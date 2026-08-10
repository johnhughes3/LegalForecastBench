"""Deterministic semantic eligibility for Stage A target documents."""

from __future__ import annotations

import re

from legalforecast.ingestion.provenance import DocumentRole


class TargetDocumentEligibilityError(ValueError):
    """Raised when a target-role document is semantically ineligible."""


def require_eligible_target_document(
    *,
    candidate_id: str,
    source_document_id: str,
    document_role: DocumentRole | str,
    markdown: str,
) -> None:
    """Reject strong parsed-body evidence that a target MTD role is false."""

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
        r"(?im)^\s*(?:#{1,6}\s*)?(?:\[?proposed\]?\s+)?"
        r"(?:(?:joint\s+)?stipulation\s+(?:for\s+(?:and\s+)?order\s+of|of)\s+"
        r"dismissal|stipulated\s+motion\s+to\s+dismiss|notice\s+of\s+voluntary\s+"
        r"dismissal)\s*$",
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
    if stipulated_or_voluntary_title or rule_41_stipulation:
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
        )
    except TargetDocumentEligibilityError:
        return True
    return False

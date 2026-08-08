"""Versioned schema identifiers used by commitment-bearing code."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SCHEMA_IDENTIFIER = re.compile(
    r"legalforecast(?:\.[a-z0-9][a-z0-9_-]*)+\.v[1-9][0-9]*"
)


@dataclass(frozen=True, slots=True)
class SchemaIdentifier:
    """A closed, versioned LegalForecastBench schema domain."""

    value: str

    def __post_init__(self) -> None:
        if _SCHEMA_IDENTIFIER.fullmatch(self.value) is None:
            raise ValueError(
                "schema identifier must be a versioned legalforecast schema"
            )

    def __str__(self) -> str:
        return self.value


ACQUISITION_RUN_CARD_V1 = SchemaIdentifier("legalforecast.acquisition_run_card.v1")
CLEARANCE_REPLACEMENT_PLAN_V1 = SchemaIdentifier(
    "legalforecast.clearance_replacement_plan.v1"
)
DISCLOSURE_CLEARANCE_V1 = SchemaIdentifier("legalforecast.disclosure_clearance.v1")
POST_RECOVERY_RESTRICTION_EVIDENCE_V1 = SchemaIdentifier(
    "legalforecast.post_recovery_restriction_evidence.v1"
)
RECAP_FETCH_QUARANTINE_RECOVERY_V1 = SchemaIdentifier(
    "legalforecast.recap_fetch_quarantine_recovery.v1"
)
RECAP_FETCH_QUARANTINE_RECOVERY_RUN_CARD_V2 = SchemaIdentifier(
    "legalforecast.recap_fetch_quarantine_recovery_run_card.v2"
)
REPLACEMENT_PURCHASE_APPROVAL_V2 = SchemaIdentifier(
    "legalforecast.replacement_purchase_approval.v2"
)
REPLACEMENT_RECOVERY_SOURCE_RUN_CARD_V2 = SchemaIdentifier(
    "legalforecast.replacement_recovery_source_run_card.v2"
)
RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4 = SchemaIdentifier(
    "legalforecast.resolved_post_recovery_public_document.v4"
)
TARGET_RAW_DOCKET_RECOVERY_PLAN_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_plan.v1"
)
TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_provenance.v1"
)
TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_receipt.v1"
)
TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_summary.v1"
)

# This registry names the current recovery vertical slice without changing any
# producer's local constant.  Migration to these imports is post-Cycle 1 work.
RECOVERY_VERTICAL_SLICE_SCHEMAS = (
    ACQUISITION_RUN_CARD_V1,
    CLEARANCE_REPLACEMENT_PLAN_V1,
    DISCLOSURE_CLEARANCE_V1,
    POST_RECOVERY_RESTRICTION_EVIDENCE_V1,
    RECAP_FETCH_QUARANTINE_RECOVERY_V1,
    RECAP_FETCH_QUARANTINE_RECOVERY_RUN_CARD_V2,
    REPLACEMENT_PURCHASE_APPROVAL_V2,
    REPLACEMENT_RECOVERY_SOURCE_RUN_CARD_V2,
    RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
)

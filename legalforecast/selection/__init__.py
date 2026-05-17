"""Selection, eligibility, and contamination controls."""

from legalforecast.selection.eligibility import (
    ContaminationMetadata,
    ContaminationRisk,
    EligibilityStatus,
    ModelRunMetadata,
    PressPublicityTag,
    SeriesCaseTiming,
    TrainingCutoffStatus,
)
from legalforecast.selection.exclusion_ledger import (
    ExclusionLedger,
    ExclusionLedgerEntry,
    ExclusionReason,
    ExclusionStage,
)
from legalforecast.selection.fallback_rules import (
    FallbackDecision,
    FallbackDecisionStatus,
    FallbackGap,
    TargetedFallbackRule,
    decide_targeted_fallback,
    targeted_fallback_rules,
)
from legalforecast.selection.motion_linkage import (
    MotionDispositionLink,
    MotionLinkageExclusionReason,
    MotionLinkageResult,
    link_mtd_dispositions,
    link_retrieved_candidate,
)

__all__ = [
    "ContaminationMetadata",
    "ContaminationRisk",
    "EligibilityStatus",
    "ExclusionLedger",
    "ExclusionLedgerEntry",
    "ExclusionReason",
    "ExclusionStage",
    "FallbackDecision",
    "FallbackDecisionStatus",
    "FallbackGap",
    "ModelRunMetadata",
    "MotionDispositionLink",
    "MotionLinkageExclusionReason",
    "MotionLinkageResult",
    "PressPublicityTag",
    "SeriesCaseTiming",
    "TargetedFallbackRule",
    "TrainingCutoffStatus",
    "decide_targeted_fallback",
    "link_mtd_dispositions",
    "link_retrieved_candidate",
    "targeted_fallback_rules",
]

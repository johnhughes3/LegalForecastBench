"""Post-Cycle-1 document-need triage and cheapest-first selection.

This package is inert relative to live Cycle 1 acquisition: nothing here is
imported by ``legalforecast.cli`` or the v2 purchase-approval recorder. Cycle
knobs come from D1's per-cycle config view (see ``cycle_config``).
"""

from legalforecast.document_need.artifact import (
    PURCHASE_CEILING_SCHEMA,
    SELECTION_SCHEMA,
    PurchaseCeiling,
    SelectionArtifact,
    build_selection_artifact,
    project_purchase_ceiling,
    replay_selection_artifact,
)
from legalforecast.document_need.blindness import (
    BlindnessError,
    Pass1Process,
    assert_pass1_cannot_read_decision,
)
from legalforecast.document_need.costs import (
    CaseCosts,
    PricedEntry,
    price_case,
    price_document,
    price_entry,
)
from legalforecast.document_need.cycle_config import (
    BUCKET_IDS,
    RANKING_PRIMARY,
    CaseMixStratification,
    DocumentNeedConfigError,
    DocumentNeedCycleView,
    NeedSelectorIds,
    RankingPolicy,
    TypedConfirmationParameters,
    document_need_view_from_cycle_config,
    document_need_view_from_cycle_record,
    preflight_selector_models,
    require_activated_cycle,
)
from legalforecast.document_need.prep import (
    AuditBundles,
    DocumentNeedPrepError,
    prepare_audit_bundles,
)
from legalforecast.document_need.protocol import (
    DocumentNeedProtocolError,
    MergedCaseBuckets,
    apply_pass2_promotions,
    run_two_pass,
)
from legalforecast.document_need.ranking import (
    AdmissionDecision,
    admit_cheapest,
    rank_cases,
)
from legalforecast.document_need.types import (
    BlindBundle,
    Chronology,
    ChronologyEntry,
    DecisionText,
    DocketDocument,
    EyesBundle,
    NeedBucket,
    Pass1Verdict,
    Pass2Promotion,
    Pass2Verdict,
)

__all__ = [
    "BUCKET_IDS",
    "PURCHASE_CEILING_SCHEMA",
    "RANKING_PRIMARY",
    "SELECTION_SCHEMA",
    "AdmissionDecision",
    "AuditBundles",
    "BlindBundle",
    "BlindnessError",
    "CaseCosts",
    "CaseMixStratification",
    "Chronology",
    "ChronologyEntry",
    "DecisionText",
    "DocketDocument",
    "DocumentNeedConfigError",
    "DocumentNeedCycleView",
    "DocumentNeedPrepError",
    "DocumentNeedProtocolError",
    "EyesBundle",
    "MergedCaseBuckets",
    "NeedBucket",
    "NeedSelectorIds",
    "Pass1Process",
    "Pass1Verdict",
    "Pass2Promotion",
    "Pass2Verdict",
    "PricedEntry",
    "PurchaseCeiling",
    "RankingPolicy",
    "SelectionArtifact",
    "TypedConfirmationParameters",
    "admit_cheapest",
    "apply_pass2_promotions",
    "assert_pass1_cannot_read_decision",
    "build_selection_artifact",
    "document_need_view_from_cycle_config",
    "document_need_view_from_cycle_record",
    "preflight_selector_models",
    "prepare_audit_bundles",
    "price_case",
    "price_document",
    "price_entry",
    "project_purchase_ceiling",
    "rank_cases",
    "replay_selection_artifact",
    "require_activated_cycle",
    "run_two_pass",
]

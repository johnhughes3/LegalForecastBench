"""Cycle 1 entry: legacy-pinned, read-only, not activated.

This documents current Cycle 1 values and points at the modules that remain
authoritative for frozen paths. Importing this module does not change any
Cycle 1 constant, validator, or preflight gate.
"""

from __future__ import annotations

from legalforecast.config.types import (
    CYCLE_1_ID,
    CohortPolicyPin,
    CycleConfig,
    DocumentNeedBucketDefinitions,
    EvaluationRegistryPin,
    FreeFirstPolicy,
    LegacyPointer,
    PerDocumentPriceCap,
    RankingSortKey,
    RankingTiebreakPolicy,
    RetryQueueLagTolerances,
    SelectorModel,
    SelectorModelPolicy,
    SortDirection,
    SpendCeiling,
    StratificationPolicy,
    TypedConfirmationParams,
    usd,
)
from legalforecast.contracts.schemas import COHORT_POLICY_V3

# Frozen evaluated-model registry bytes; live disclosure authority still pins
# this digest in legalforecast.ingestion.disclosure_model_review_authority.
_CYCLE_1_EVALUATED_REGISTRY_SHA256 = (
    "960c4783826e365d01229fd0199b1c767144ad2275de1c4cfe981f25f4159f2e"
)

# Committed exact-100 cohort-policy v3 artifact digest (documentary).
_CYCLE_1_COHORT_POLICY_SHA256 = (
    "d9bb6b40bf4914ed94e17b66b5ba2cfd2a0051dbb8dc1947269fe65886806216"
)

_DOCUMENT_NEED_BUCKETS = DocumentNeedBucketDefinitions(
    clearly_required=(
        "Required for case completeness under the pinned cohort policy: the "
        "target motion, its memorandum, the operative pleading it attacks, and "
        "filed oppositions/replies (and other required briefing roles) when "
        "those entries exist."
    ),
    conditional=(
        "Might or might not be required depending on what the clearly-required "
        "documents contain (a brief that may incorporate by reference, an "
        "exhibit a memorandum may rely on, an amended pleading whose "
        "operativeness is ambiguous from labels alone)."
    ),
    clearly_not_required=(
        "Not required for packet completeness: purely procedural docket "
        "material, non-target motions, and other entries outside the cohort "
        "policy's required roles."
    ),
)

_TYPED_CONFIRMATION = TypedConfirmationParams(
    decisions=("approve", "reject", "free_only"),
    phrase_template=(
        "{DECISION} {cycle_id} {request_sha256} {projected_cost_usd} "
        "RULE {rule} TARGET {target_case_count} {session_scope_token}"
    ),
    session_scope_token="ONE_GLOBAL_SESSION FREE_ONLY",
)

_RETRY = RetryQueueLagTolerances(
    recap_fetch_poll_attempts=3,
    recap_fetch_poll_backoff_seconds=0.0,
    courtlistener_request_budget_max_wait_seconds=120.0,
    disclosure_review_max_attempts=2,
    disclosure_review_failure_window_seconds=3600,
    live_model_retry_backoff_seconds=2.0,
)

_PRICE_CAP = PerDocumentPriceCap(
    pacer_page_usd=usd("0.10"),
    pacer_document_cap_usd=usd("3.00"),
    reservation_usd=usd("3.05"),
    includes_pacer_fees=True,
    includes_service_fees=True,
    includes_rounding=True,
)

CYCLE_1 = CycleConfig(
    cycle_id=CYCLE_1_ID,
    activated=False,
    legacy_pinned=True,
    activation_blocker=(
        "legacy-pinned: Cycle 1 acquisition paths keep reading existing "
        "constants; this entry is documentary only"
    ),
    eligibility_anchor="2026-06-30",
    acquisition_cycle_id="cycle-1-target-100-2026-07-25",
    evaluation_registry=EvaluationRegistryPin(
        path="model_registries/cycle-1-2026-06-30.json",
        sha256=_CYCLE_1_EVALUATED_REGISTRY_SHA256,
    ),
    selector_model_policy=SelectorModelPolicy(
        # Historical cleared (non-evaluation) selectors. Not an activation of
        # a new Cycle 1 selector, and not a substitute for the live disclosure
        # reviewer registry pin.
        primary=SelectorModel(
            provider="google",
            model_id="gemini-3.5-flash",
            model_version_or_snapshot="gemini-3.5-flash",
        ),
        alternates=(
            SelectorModel(
                provider="anthropic",
                model_id="claude-sonnet-4-6",
                model_version_or_snapshot="claude-sonnet-4-6",
            ),
            SelectorModel(
                provider="openai",
                model_id="gpt-5.4-mini-2026-03-17",
                model_version_or_snapshot="gpt-5.4-mini-2026-03-17",
            ),
            SelectorModel(
                provider="anthropic",
                model_id="claude-haiku-4-5-20251001",
                model_version_or_snapshot="claude-haiku-4-5-20251001",
            ),
            SelectorModel(
                provider="anthropic",
                model_id="claude-fable-5",
                model_version_or_snapshot="claude-fable-5",
            ),
        ),
    ),
    per_document_price_cap=_PRICE_CAP,
    free_first=FreeFirstPolicy(required=True, paid_only_after_free_exhausted=True),
    cohort_policy=CohortPolicyPin(
        schema_version=str(COHORT_POLICY_V3),
        provenance_path="docs/cohort-policy-cycle-1-target-100-2026-08-13.json",
        policy_sha256=_CYCLE_1_COHORT_POLICY_SHA256,
    ),
    document_need_buckets=_DOCUMENT_NEED_BUCKETS,
    ranking=RankingTiebreakPolicy(
        keys=(
            RankingSortKey("missing_core_document_count", SortDirection.ASCENDING),
            RankingSortKey("estimated_cost_usd", SortDirection.ASCENDING),
            RankingSortKey("candidate_id", SortDirection.ASCENDING),
        ),
        purchase_rule="buy_cheapest_complete",
        ranking_policy_version="legacy-cost-only-v1",
        record_cost_rank_in_provenance=True,
    ),
    stratification=StratificationPolicy(
        enabled=False,
        bottom_decile_share_cap=usd("0.10"),
    ),
    spend=SpendCeiling(hard_cap_usd=usd("567.30"), max_per_case_usd=usd("73.20")),
    typed_confirmation=_TYPED_CONFIRMATION,
    retry_queue_lag=_RETRY,
    pointers=(
        LegacyPointer(
            knob="evaluation_registry",
            location="model_registries/cycle-1-2026-06-30.json",
            note="Live disclosure authority also pins this path and SHA-256.",
        ),
        LegacyPointer(
            knob="selector_model_policy",
            location=(
                "legalforecast.ingestion.disclosure_model_review_authority "
                "(_REVIEWER_KEY) and the Cycle 1 labeling registries"
            ),
            note="Documentary cleared-set only; not a live selector switch.",
        ),
        LegacyPointer(
            knob="per_document_price_cap",
            location="legalforecast.ingestion.missing_core_budget.DEFAULT_PURCHASE_COST_USD",
            note="Reservation $3.05; repair execution still requires $3.00 PACER cap.",
        ),
        LegacyPointer(
            knob="free_first",
            location=(
                "legalforecast.ingestion.missing_document_successor (free-first plan)"
            ),
            note="Live repair and purchase paths remain free-first.",
        ),
        LegacyPointer(
            knob="cohort_policy",
            location="legalforecast.ingestion.cohort_policy and the v3 provenance JSON",
            note="Freeze authenticates the committed artifact, not this pin.",
        ),
        LegacyPointer(
            knob="ranking",
            location="legalforecast.ingestion.target_cohort_projection._RANKING_POLICY",
            note=(
                "Live cost ranking is missing_core then estimated_cost then "
                "candidate_id."
            ),
        ),
        LegacyPointer(
            knob="spend",
            location=(
                "docs/cohort-policy-cycle-1-target-100-2026-08-13.json purchase_policy"
            ),
            note="Live exact-100 hard cap $567.30 / max per case $73.20.",
        ),
        LegacyPointer(
            knob="typed_confirmation",
            location=(
                "legalforecast.ingestion.purchase_approval."
                "PurchaseApprovalRequest.required_confirmation"
            ),
            note="Live phrase construction stays in purchase_approval.",
        ),
        LegacyPointer(
            knob="retry_queue_lag",
            location=(
                "legalforecast.ingestion.courtlistener_recap_fetch poll defaults; "
                "courtlistener_request_budget.max_wait_seconds"
            ),
            note=(
                "Queue-lag wait-out is the #706 behavior; defaults are documented here."
            ),
        ),
    ),
)

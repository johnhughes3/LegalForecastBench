"""Draft Cycle 2 entry: named, inert, unreachable from live acquisition.

This may name Luna / Sonnet 5 / Gemini 3.5 Flash as the post-Cycle-1 selector
policy (dn9.2), but ``activated`` is false until ``LegalForecastBench-dm0g.7.3``
closes. The loader refuses live use. Do not close dn9.2 from this plumbing.
"""

from __future__ import annotations

from legalforecast.config.types import (
    CYCLE_2_ID,
    CohortPolicyPin,
    CycleConfig,
    DocumentNeedBucketDefinitions,
    EvaluationRegistryPin,
    FreeFirstPolicy,
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

CYCLE_2 = CycleConfig(
    cycle_id=CYCLE_2_ID,
    activated=False,
    legacy_pinned=False,
    activation_blocker=(
        "legalforecastbench-dn9.2 is blocked on LegalForecastBench-dm0g.7.3 "
        "(publish the Cycle 1 public report); this draft must stay inert"
    ),
    eligibility_anchor=None,
    acquisition_cycle_id=None,
    evaluation_registry=EvaluationRegistryPin(
        # Sentinel path: Cycle 2 has no evaluation registry yet. Preflight
        # against this pin fails closed until a real registry is committed.
        path="model_registries/cycle-2-evaluation-registry-NOT-YET-PINNED.json",
        sha256=None,
    ),
    selector_model_policy=SelectorModelPolicy(
        # Exact callable IDs. dn9.2 named "claude-sonnet-5.0"; the frozen
        # callable ID in this repo is claude-sonnet-5. Latest stable Gemini
        # Flash with a pinned ID here is gemini-3.5-flash (the preview Flash
        # ID is mutable and ineligible).
        primary=SelectorModel(
            provider="openai",
            model_id="gpt-5.6-luna",
            model_version_or_snapshot="gpt-5.6-luna",
        ),
        alternates=(
            SelectorModel(
                provider="anthropic",
                model_id="claude-sonnet-5",
                model_version_or_snapshot="claude-sonnet-5",
            ),
            SelectorModel(
                provider="google",
                model_id="gemini-3.5-flash",
                model_version_or_snapshot="gemini-3.5-flash",
            ),
        ),
    ),
    per_document_price_cap=PerDocumentPriceCap(
        pacer_page_usd=usd("0.10"),
        pacer_document_cap_usd=usd("3.00"),
        reservation_usd=usd("3.05"),
        includes_pacer_fees=True,
        includes_service_fees=True,
        includes_rounding=True,
    ),
    free_first=FreeFirstPolicy(required=True, paid_only_after_free_exhausted=True),
    cohort_policy=CohortPolicyPin(
        schema_version=str(COHORT_POLICY_V3),
        provenance_path=None,
        policy_sha256=None,
    ),
    document_need_buckets=_DOCUMENT_NEED_BUCKETS,
    ranking=RankingTiebreakPolicy(
        keys=(
            RankingSortKey("max_cost", SortDirection.ASCENDING),
            RankingSortKey("min_cost", SortDirection.ASCENDING),
            RankingSortKey("candidate_id", SortDirection.ASCENDING),
        ),
        purchase_rule="cheapest_first_auto_admit",
        ranking_policy_version="document-need-max-cost-v1",
        record_cost_rank_in_provenance=True,
    ),
    stratification=StratificationPolicy(
        enabled=False,
        bottom_decile_share_cap=usd("0.10"),
    ),
    spend=SpendCeiling(hard_cap_usd=None, max_per_case_usd=None),
    typed_confirmation=TypedConfirmationParams(
        decisions=("approve", "reject", "free_only"),
        phrase_template=(
            "{DECISION} {cycle_id} {request_sha256} {projected_cost_usd} "
            "RULE {rule} TARGET {target_case_count} {session_scope_token}"
        ),
        session_scope_token="ONE_GLOBAL_SESSION FREE_ONLY",
    ),
    retry_queue_lag=RetryQueueLagTolerances(
        recap_fetch_poll_attempts=3,
        recap_fetch_poll_backoff_seconds=0.0,
        courtlistener_request_budget_max_wait_seconds=120.0,
        disclosure_review_max_attempts=2,
        disclosure_review_failure_window_seconds=3600,
        live_model_retry_backoff_seconds=2.0,
    ),
)

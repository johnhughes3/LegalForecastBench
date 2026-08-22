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
ATTACHMENT_PAGE_AUTHORIZATION_V1 = SchemaIdentifier(
    "legalforecast.attachment_page_authorization.v1"
)
ATTACHMENT_PAGE_DISPATCH_JOURNAL_V1 = SchemaIdentifier(
    "legalforecast.attachment_page_dispatch_journal.v1"
)
ATTACHMENT_PAGE_FETCH_PLAN_V1 = SchemaIdentifier(
    "legalforecast.attachment_page_fetch_plan.v1"
)
ATTACHMENT_PAGE_FETCH_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.attachment_page_fetch_receipt.v1"
)
CANDIDATE_SCOPED_STAGE_A_REPLAY_V1 = SchemaIdentifier(
    "legalforecast.candidate_scoped_stage_a_replay.v1"
)
CANDIDATE_SCOPED_STAGE_A_REPLAY_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.candidate_scoped_stage_a_replay_receipt.v1"
)
COHORT_POLICY_V1 = SchemaIdentifier("legalforecast.cohort_policy.v1")
COHORT_POLICY_V2 = SchemaIdentifier("legalforecast.cohort_policy.v2")
COHORT_POLICY_V3 = SchemaIdentifier("legalforecast.cohort_policy.v3")
CORPUS_COMPLETION_SUMMARY_V1 = SchemaIdentifier(
    "legalforecast.corpus_completion_summary.v1"
)
CORPUS_COMPLETION_SUMMARY_V2 = SchemaIdentifier(
    "legalforecast.corpus_completion_summary.v2"
)
CORPUS_COMPLETION_SUMMARY_RUN_CARD_V1 = SchemaIdentifier(
    "legalforecast.corpus_completion_summary_run_card.v1"
)
CORPUS_COMPLETION_SUMMARY_RUN_CARD_V2 = SchemaIdentifier(
    "legalforecast.corpus_completion_summary_run_card.v2"
)
CYCLE_PREFLIGHT_MANIFEST_SIDECAR_V1 = SchemaIdentifier(
    "legalforecast.cycle_preflight_manifest_sidecar.v1"
)
CYCLE_GROUPED_LABEL_AUDIT_PACKET_V1 = SchemaIdentifier(
    "legalforecast.case_grouped_label_audit_packet.v1"
)
CYCLE_PREFLIGHT_REPORT_V2 = SchemaIdentifier("legalforecast.cycle_preflight_report.v2")
CYCLE1_MANIFEST_UNITIZER_SPEND_AUTHORITY_V1 = SchemaIdentifier(
    "legalforecast.cycle1.manifest_unitizer_spend_authority.v1"
)
CYCLE1_MANIFEST_UNITIZER_R2_AUTHORITY_V1 = SchemaIdentifier(
    "legalforecast.cycle1.manifest_unitizer_r2_authority.v1"
)
CYCLE1_STAGE51_FINALIZED_UNITS_INTEGRATION_V1 = SchemaIdentifier(
    "legalforecast.cycle1.stage51_finalized_units_integration.v1"
)
CLEARANCE_REPLACEMENT_PLAN_V1 = SchemaIdentifier(
    "legalforecast.clearance_replacement_plan.v1"
)
DIRECT_COURTLISTENER_QUEUE_DELIVERY_AUTHORITY_V1 = SchemaIdentifier(
    "legalforecast.direct_courtlistener_queue_delivery_authority.v1"
)
DISCLOSURE_CLEARANCE_V1 = SchemaIdentifier("legalforecast.disclosure_clearance.v1")
SUPPORTING_DOCUMENT_RESTRICTION_EVIDENCE_V1 = SchemaIdentifier(
    "legalforecast.supporting_document_restriction_evidence.v1"
)
EXACT100_SUCCESSOR_PROMOTION_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_promotion.v1"
)
EXACT100_SUCCESSOR_PROMOTION_V2 = SchemaIdentifier(
    "legalforecast.exact100_successor_promotion.v2"
)
EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_config.v1"
)
EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V2 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_config.v2"
)
EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_state.v1"
)
EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_state.v2"
)
EXACT100_SUCCESSOR_SEMANTIC_REPAIR_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_semantic_repair.v1"
)
EXACT100_SUCCESSOR_WIDER_RANK_LEDGER_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_wider_rank_ledger.v1"
)
EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_terminal_exclusion.v1"
)
EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V2 = SchemaIdentifier(
    "legalforecast.exact100_successor_terminal_exclusion.v2"
)
EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V3 = SchemaIdentifier(
    "legalforecast.exact100_successor_terminal_exclusion.v3"
)
EXACT100_SUCCESSOR_PROMOTION_V3 = SchemaIdentifier(
    "legalforecast.exact100_successor_promotion.v3"
)
EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V3 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_config.v3"
)
EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3 = SchemaIdentifier(
    "legalforecast.exact100_successor_replacement_state.v3"
)
EXACT100_SUCCESSOR_PREDECESSOR_COVERAGE_V1 = SchemaIdentifier(
    "legalforecast.exact100_successor_predecessor_coverage.v1"
)
EXACT100_SUCCESSOR_PREDECESSOR_COVERAGE_V2 = SchemaIdentifier(
    "legalforecast.exact100_successor_predecessor_coverage.v2"
)
OWNER_ADJUDICATED_REPLACEMENT_EVIDENCE_V1 = SchemaIdentifier(
    "legalforecast.owner_adjudicated_replacement_evidence.v1"
)
OWNER_ADJUDICATED_REPLACEMENT_PLAN_V1 = SchemaIdentifier(
    "legalforecast.owner_adjudicated_replacement_plan.v1"
)
OWNER_SIGNED_CORPUS_MANIFEST_V1 = SchemaIdentifier(
    "legalforecast.owner_signed_corpus_manifest.v1"
)
MANIFEST_MODE_FORECAST_RUN_RECORD_V1 = SchemaIdentifier(
    "legalforecast.manifest_mode_forecast_run_record.v1"
)
EXACT100_METHODS_DISCLOSURE_V1 = SchemaIdentifier(
    "legalforecast.exact100_methods_disclosure.v1"
)
DOCUMENT_BODY_ROLE_VALIDATOR_V1 = SchemaIdentifier(
    "legalforecast.document_body_role_validator.v1"
)
DOCUMENT_BODY_ROLE_VALIDATOR_V2 = SchemaIdentifier(
    "legalforecast.document_body_role_validator.v2"
)
MISSING_DOCUMENT_EXCLUSION_V1 = SchemaIdentifier(
    "legalforecast.missing_document_exclusion.v1"
)
MISSING_DOCUMENT_INCLUSION_V1 = SchemaIdentifier(
    "legalforecast.missing_document_inclusion.v1"
)
MISSING_DOCUMENT_SUCCESSOR_STATE_V1 = SchemaIdentifier(
    "legalforecast.missing_document_successor_state.v1"
)
REPAIR_MANIFEST_APPROVAL_V1 = SchemaIdentifier(
    "legalforecast.repair_manifest_approval.v1"
)
REPAIR_MANIFEST_APPROVAL_V2 = SchemaIdentifier(
    "legalforecast.repair_manifest_approval.v2"
)
EXACT100_ZERO_COST_RECOVERY_PLAN_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_plan.v1"
)
EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_public_document.v1"
)
EXACT100_ZERO_COST_RECOVERY_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_receipt.v1"
)
EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_receipt.v2"
)
EXACT100_ZERO_COST_RECOVERY_REQUEST_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_request.v1"
)
EXACT100_ZERO_COST_RECOVERY_REQUEST_V2 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_request.v2"
)
EXACT100_ZERO_COST_RECOVERY_RUN_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_run.v1"
)
EXACT100_ZERO_COST_RECOVERY_RUN_V2 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_run.v2"
)
EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_terminal_authority.v3"
)
EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_rest_observation.v1"
)
EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1 = SchemaIdentifier(
    "legalforecast.exact100_zero_cost_recovery_rest_observation_transcript.v1"
)
FIRECRAWL_SCRAPE_REQUEST_CONTRACT_V1 = SchemaIdentifier(
    "legalforecast.firecrawl_scrape_request_contract.v1"
)
FREE_SUPPORT_MEMORANDUM_RECOVERY_PLAN_V1 = SchemaIdentifier(
    "legalforecast.free_support_memorandum_recovery_plan.v1"
)
EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1 = SchemaIdentifier(
    "legalforecast.exact100_supporting_document_successor.v1"
)
EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V1 = SchemaIdentifier(
    "legalforecast.exact100_missing_document_acquisition_plan.v1"
)
EXACT100_MISSING_DOCUMENT_SUCCESSOR_V1 = SchemaIdentifier(
    "legalforecast.exact100_missing_document_successor.v1"
)
EXACT100_MISSING_DOCUMENT_ACQUISITION_PLAN_V2 = SchemaIdentifier(
    "legalforecast.exact100_missing_document_acquisition_plan.v2"
)
EXACT100_MISSING_DOCUMENT_SUCCESSOR_V2 = SchemaIdentifier(
    "legalforecast.exact100_missing_document_successor.v2"
)
EXACT100_DOCUMENT_REPAIR_PILOT_V1 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_pilot.v1"
)
EXACT100_DOCUMENT_REPAIR_PILOT_V2 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_pilot.v2"
)
EXACT100_DOCUMENT_REPAIR_EXECUTION_V1 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_execution.v1"
)
EXACT100_DOCUMENT_REPAIR_EXECUTION_V2 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_execution.v2"
)
EXACT100_DOCUMENT_REPAIR_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_receipt.v1"
)
EXACT100_DOCUMENT_REPAIR_PURCHASE_AUTHORITY_V1 = SchemaIdentifier(
    "legalforecast.exact100_document_repair_purchase_authority.v1"
)
FIRECRAWL_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION_V1 = SchemaIdentifier(
    "legalforecast.firecrawl_provider_contract_defect_authorization.v1"
)
FINALIZED_PREDICTION_UNITS_V2 = SchemaIdentifier(
    "legalforecast.finalized_prediction_units.v2"
)
FINALIZED_PREDICTION_UNITS_V3 = SchemaIdentifier(
    "legalforecast.finalized_prediction_units.v3"
)
FINALIZED_PREDICTION_UNITS_V4 = SchemaIdentifier(
    "legalforecast.finalized_prediction_units.v4"
)
UNITIZATION_ADJUDICATION_V1 = SchemaIdentifier(
    "legalforecast.unitization_adjudication.v1"
)
UNITIZATION_ADJUDICATION_V2 = SchemaIdentifier(
    "legalforecast.unitization_adjudication.v2"
)
UNITIZATION_ADJUDICATION_V3 = SchemaIdentifier(
    "legalforecast.unitization_adjudication.v3"
)
UNITIZATION_ADJUDICATION_PREFLIGHT_REPORT_V1 = SchemaIdentifier(
    "legalforecast.unitization_adjudication_preflight_report.v1"
)
LLM_UNITIZATION_RECONSTRUCTION_RECOVERY_V1 = SchemaIdentifier(
    "legalforecast.llm_unitization_reconstruction_recovery.v1"
)
LLM_STAGE_A_UNITIZER_TERMINAL_ESCALATION_V1 = SchemaIdentifier(
    "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1"
)
LLM_STAGE_A_STRUCTURAL_REVIEW_RECONSTRUCTION_RECOVERY_V1 = SchemaIdentifier(
    "legalforecast.llm_stage_a_structural_review_reconstruction_recovery.v1"
)
LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1 = SchemaIdentifier(
    "legalforecast.llm_stage_a_structural_review_terminal_escalation.v1"
)
LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2 = SchemaIdentifier(
    "legalforecast.llm_stage_a_structural_review_terminal_escalation.v2"
)
STAGE_A_STRUCTURAL_FLAG_V2 = SchemaIdentifier(
    "legalforecast.stage_a_structural_flag.v2"
)
UNITIZATION_REVIEW_BUNDLE_V1 = SchemaIdentifier(
    "legalforecast.unitization_review_bundle.v1"
)
UNITIZATION_REVIEW_BUNDLE_MANIFEST_V1 = SchemaIdentifier(
    "legalforecast.unitization_review_bundle_manifest.v1"
)
UNITIZATION_REVIEW_QUEUE_V1 = SchemaIdentifier(
    "legalforecast.unitization_review_queue.v1"
)
UNITIZATION_REVIEW_QUEUE_V2 = SchemaIdentifier(
    "legalforecast.unitization_review_queue.v2"
)
UNITIZATION_REVIEW_QUEUE_GENERATION_V1 = SchemaIdentifier(
    "legalforecast.unitization_review_queue_generation.v1"
)
UNITIZER_TERMINAL_REVIEW_QUEUE_V1 = SchemaIdentifier(
    "legalforecast.unitizer_terminal_review_queue.v1"
)
UNITIZER_TERMINAL_REVIEW_BUNDLE_V1 = SchemaIdentifier(
    "legalforecast.unitizer_terminal_review_bundle.v1"
)
SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V1 = SchemaIdentifier(
    "legalforecast.successor_attorney_packet_manifest.v1"
)
SUCCESSOR_ATTORNEY_PACKET_MANIFEST_V2 = SchemaIdentifier(
    "legalforecast.successor_attorney_packet_manifest.v2"
)
SUCCESSOR_ATTORNEY_PACKET_VIEW_V1 = SchemaIdentifier(
    "legalforecast.successor_attorney_packet_view.v1"
)
SUCCESSOR_ATTORNEY_PACKET_VIEW_V2 = SchemaIdentifier(
    "legalforecast.successor_attorney_packet_view.v2"
)
SUCCESSOR_RERUN_IMPACT_V1 = SchemaIdentifier("legalforecast.successor_rerun_impact.v1")
SUCCESSOR_RERUN_PROPOSAL_V1 = SchemaIdentifier(
    "legalforecast.successor_rerun_proposal.v1"
)
POST_RECOVERY_RESTRICTION_EVIDENCE_V1 = SchemaIdentifier(
    "legalforecast.post_recovery_restriction_evidence.v1"
)
PROVIDER_AUTHORITY_INFRA_APPLY_RECOVERY_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.provider_authority_infra_apply_recovery_receipt.v1"
)
PROVIDER_AUTHORITY_INFRA_IMPORT_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.provider_authority_infra_import_receipt.v1"
)
PROVIDER_AUTHORITY_INFRA_IMPORT_RECOVERY_RECEIPT_V1 = SchemaIdentifier(
    "legalforecast.provider_authority_infra_import_recovery_receipt.v1"
)
PROVIDER_AUTHORITY_INFRA_IMPORT_REQUEST_V1 = SchemaIdentifier(
    "legalforecast.provider_authority_infra_import_request.v1"
)
PURCHASE_SPEND_SUMMARY_V1 = SchemaIdentifier("legalforecast.purchase_spend_summary.v1")
RECAP_FETCH_QUARANTINE_RECOVERY_V1 = SchemaIdentifier(
    "legalforecast.recap_fetch_quarantine_recovery.v1"
)
RAW_BYTES_CODEC_V1 = SchemaIdentifier("legalforecast.codec.raw-bytes.v1")
RAW_BYTES_RAW_SHA256_COMMITMENT_V1 = SchemaIdentifier(
    "legalforecast.commitment.raw-bytes.raw-sha256.v1"
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
REPLACEMENT_RECOVERY_CONSOLIDATION_RUN_CARD_V2 = SchemaIdentifier(
    "legalforecast.replacement_recovery_consolidation_run_card.v2"
)
REPLACEMENT_RECOVERY_CONSOLIDATION_RUN_CARD_V3 = SchemaIdentifier(
    "legalforecast.replacement_recovery_consolidation_run_card.v3"
)
RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4 = SchemaIdentifier(
    "legalforecast.resolved_post_recovery_public_document.v4"
)
SELECTED_ACQUISITION_SLICE_V1 = SchemaIdentifier(
    "legalforecast.selected_acquisition_slice.v1"
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
TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_successor_plan.v1"
)
TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_recovery_provider_contract_retry_plan.v1"
)
TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_auxiliary_provenance_bridge.v1"
)
TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_V1 = SchemaIdentifier(
    "legalforecast.target_raw_docket_auxiliary_provenance_bridge_run_card.v1"
)
TARGET_DOCUMENT_ELIGIBILITY_AUDIT_V1 = SchemaIdentifier(
    "legalforecast.target_document_eligibility_audit.v1"
)
ZERO_COST_SUCCESSOR_CONFIG_V1 = SchemaIdentifier(
    "legalforecast.zero_cost_successor_config.v1"
)
MULTIHARNESS_TASK_IDENTITY_V1 = SchemaIdentifier(
    "legalforecast.multiharness.task_identity.v1"
)
MULTIHARNESS_SOLVER_IDENTITY_V1 = SchemaIdentifier(
    "legalforecast.multiharness.solver_identity.v1"
)
MULTIHARNESS_RUN_IDENTITY_V1 = SchemaIdentifier(
    "legalforecast.multiharness.run_identity.v1"
)
MULTIHARNESS_MATCHED_HARNESS_IDENTITY_V1 = SchemaIdentifier(
    "legalforecast.multiharness.matched_harness_identity.v1"
)
MULTIHARNESS_SYSTEM_BUNDLE_LABEL_V1 = SchemaIdentifier(
    "legalforecast.multiharness.system_bundle_label.v1"
)

# This registry names the current recovery vertical slice without changing any
# producer's local constant.  Migration to these imports is post-Cycle 1 work.
RECOVERY_VERTICAL_SLICE_SCHEMAS = (
    ACQUISITION_RUN_CARD_V1,
    ATTACHMENT_PAGE_AUTHORIZATION_V1,
    ATTACHMENT_PAGE_DISPATCH_JOURNAL_V1,
    ATTACHMENT_PAGE_FETCH_PLAN_V1,
    ATTACHMENT_PAGE_FETCH_RECEIPT_V1,
    CLEARANCE_REPLACEMENT_PLAN_V1,
    DIRECT_COURTLISTENER_QUEUE_DELIVERY_AUTHORITY_V1,
    DISCLOSURE_CLEARANCE_V1,
    SUPPORTING_DOCUMENT_RESTRICTION_EVIDENCE_V1,
    EXACT100_SUCCESSOR_PROMOTION_V1,
    EXACT100_SUCCESSOR_PROMOTION_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V2,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2,
    EXACT100_SUCCESSOR_SEMANTIC_REPAIR_V1,
    EXACT100_SUCCESSOR_WIDER_RANK_LEDGER_V1,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V2,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V3,
    EXACT100_SUCCESSOR_PROMOTION_V3,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V3,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3,
    EXACT100_SUCCESSOR_PREDECESSOR_COVERAGE_V1,
    EXACT100_SUCCESSOR_PREDECESSOR_COVERAGE_V2,
    OWNER_ADJUDICATED_REPLACEMENT_EVIDENCE_V1,
    OWNER_ADJUDICATED_REPLACEMENT_PLAN_V1,
    EXACT100_METHODS_DISCLOSURE_V1,
    EXACT100_ZERO_COST_RECOVERY_PLAN_V1,
    EXACT100_ZERO_COST_RECOVERY_PUBLIC_DOCUMENT_V1,
    EXACT100_ZERO_COST_RECOVERY_RECEIPT_V1,
    EXACT100_ZERO_COST_RECOVERY_RECEIPT_V2,
    EXACT100_ZERO_COST_RECOVERY_REQUEST_V1,
    EXACT100_ZERO_COST_RECOVERY_REQUEST_V2,
    EXACT100_ZERO_COST_RECOVERY_RUN_V1,
    EXACT100_ZERO_COST_RECOVERY_RUN_V2,
    EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_V1,
    EXACT100_ZERO_COST_RECOVERY_REST_OBSERVATION_TRANSCRIPT_V1,
    FIRECRAWL_PROVIDER_CONTRACT_DEFECT_AUTHORIZATION_V1,
    FIRECRAWL_SCRAPE_REQUEST_CONTRACT_V1,
    FREE_SUPPORT_MEMORANDUM_RECOVERY_PLAN_V1,
    EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1,
    FINALIZED_PREDICTION_UNITS_V2,
    FINALIZED_PREDICTION_UNITS_V3,
    LLM_STAGE_A_STRUCTURAL_REVIEW_RECONSTRUCTION_RECOVERY_V1,
    LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V1,
    LLM_STAGE_A_STRUCTURAL_REVIEW_TERMINAL_ESCALATION_V2,
    STAGE_A_STRUCTURAL_FLAG_V2,
    UNITIZATION_REVIEW_BUNDLE_V1,
    UNITIZATION_REVIEW_BUNDLE_MANIFEST_V1,
    UNITIZATION_REVIEW_QUEUE_V1,
    UNITIZATION_ADJUDICATION_V1,
    UNITIZATION_ADJUDICATION_V2,
    UNITIZATION_ADJUDICATION_PREFLIGHT_REPORT_V1,
    POST_RECOVERY_RESTRICTION_EVIDENCE_V1,
    PURCHASE_SPEND_SUMMARY_V1,
    RECAP_FETCH_QUARANTINE_RECOVERY_V1,
    RECAP_FETCH_QUARANTINE_RECOVERY_RUN_CARD_V2,
    REPLACEMENT_PURCHASE_APPROVAL_V2,
    REPLACEMENT_RECOVERY_CONSOLIDATION_RUN_CARD_V2,
    REPLACEMENT_RECOVERY_CONSOLIDATION_RUN_CARD_V3,
    REPLACEMENT_RECOVERY_SOURCE_RUN_CARD_V2,
    RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    SELECTED_ACQUISITION_SLICE_V1,
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVIDER_CONTRACT_RETRY_PLAN_V1,
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_V1,
    TARGET_RAW_DOCKET_AUXILIARY_PROVENANCE_BRIDGE_RUN_CARD_V1,
    TARGET_DOCUMENT_ELIGIBILITY_AUDIT_V1,
    ZERO_COST_SUCCESSOR_CONFIG_V1,
)

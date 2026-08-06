# Ingestion Module Map

`legalforecast.ingestion` intentionally still has a mostly flat, shallow structure. Moving its modules while acquisition work is active would create broad import churn, so this map supplies the internal structure: each Python module belongs to exactly one concern below, and each concern names its ownership boundary and useful entry points.

Use this page to find code, not as a second API specification. Module docstrings and typed public interfaces remain authoritative. The consistency test in `tests/test_ingestion_module_map.py` requires every ingestion Python file to appear exactly once, so new modules must be placed deliberately.

## 1. Package surface and shared contracts

**Owns:** Package exports, canonical serialization, common acquisition vocabulary, HTTP validation, provenance records, and shared restriction/URI rules.

**Start with:** `__init__.py` for the compatibility surface, `acquisition_contract.py` for packet roles, and `provenance.py` for source-document records.

| Module | Responsibility |
| --- | --- |
| [`__init__.py`](../legalforecast/ingestion/__init__.py) | Compatibility exports for ingestion clients and workflows. |
| [`acquisition_contract.py`](../legalforecast/ingestion/acquisition_contract.py) | Production acquisition constants and packet-role normalization. |
| [`canonical_json.py`](../legalforecast/ingestion/canonical_json.py) | Canonical JSON bytes shared by trust boundaries. |
| [`decision_first_terms.py`](../legalforecast/ingestion/decision_first_terms.py) | Frozen decision-first RECAP search vocabulary. |
| [`disclosure_uri.py`](../legalforecast/ingestion/disclosure_uri.py) | URI validation shared by disclosure boundaries. |
| [`http_config.py`](../legalforecast/ingestion/http_config.py) | HTTPS endpoint validation for live clients. |
| [`provenance.py`](../legalforecast/ingestion/provenance.py) | Source-document and extracted-text provenance schemas. |
| [`restricted_material.py`](../legalforecast/ingestion/restricted_material.py) | Fail-closed restricted-material classification. |

## 2. Cycle orchestration, storage, and readiness

**Owns:** Immutable cycle configuration, durable execution state, path materialization, batch assembly, readiness gates, and operational reporting.

**Start with:** `cycle_orchestrator.py` for stage execution, `cycle_acquisition_store.py` for durable state, and `cycle_acquisition_assembler.py` for final roots.

| Module | Responsibility |
| --- | --- |
| [`corpus_readiness.py`](../legalforecast/ingestion/corpus_readiness.py) | Clean-corpus readiness checks. |
| [`cycle_acquisition_assembler.py`](../legalforecast/ingestion/cycle_acquisition_assembler.py) | Content-addressed immutable batch assembly. |
| [`cycle_acquisition_store.py`](../legalforecast/ingestion/cycle_acquisition_store.py) | Resumable state for one acquisition cycle. |
| [`cycle_manifest_template.py`](../legalforecast/ingestion/cycle_manifest_template.py) | Canonical configs from path-parameterized templates. |
| [`cycle_orchestrator.py`](../legalforecast/ingestion/cycle_orchestrator.py) | Receipt-backed acquisition-stage orchestration. |
| [`cycle_path_metadata.py`](../legalforecast/ingestion/cycle_path_metadata.py) | Private machine-local path metadata for a frozen cycle. |
| [`downstream_rehearsal.py`](../legalforecast/ingestion/downstream_rehearsal.py) | Provider-free downstream model-response fixtures. |
| [`funnel_report.py`](../legalforecast/ingestion/funnel_report.py) | Reproducible funnel reports from terminal artifacts. |
| [`infisical_systemd_launcher.py`](../legalforecast/ingestion/infisical_systemd_launcher.py) | Child exit-status propagation for Infisical-wrapped services. |
| [`readiness_provenance.py`](../legalforecast/ingestion/readiness_provenance.py) | Stage A/B provenance gates for readiness. |

## 3. CourtListener and RECAP discovery

**Owns:** CourtListener transports, REST and HTML discovery, request budgets, search completeness, pagination, opinion leads, and provider-neutral scheduling.

**Start with:** `recap_api_discovery.py` for REST discovery, `courtlistener_acquisition.py` for screened candidates, and `discovery_scheduler.py` for ordering semantics.

| Module | Responsibility |
| --- | --- |
| [`courtlistener_acquisition.py`](../legalforecast/ingestion/courtlistener_acquisition.py) | Live discovery and MTD candidate screening. |
| [`courtlistener_client.py`](../legalforecast/ingestion/courtlistener_client.py) | Typed CourtListener client and fixture transport. |
| [`courtlistener_dates.py`](../legalforecast/ingestion/courtlistener_dates.py) | Fail-closed docket-entry date parsing. |
| [`courtlistener_live_html_source.py`](../legalforecast/ingestion/courtlistener_live_html_source.py) | Run-level bot-challenge handling for HTML retrieval. |
| [`courtlistener_opinion_discovery.py`](../legalforecast/ingestion/courtlistener_opinion_discovery.py) | Opinion-cluster discovery for MTD leads. |
| [`courtlistener_request_budget.py`](../legalforecast/ingestion/courtlistener_request_budget.py) | Crash-durable rolling REST request budgets. |
| [`courtlistener_snapshot_materialization.py`](../legalforecast/ingestion/courtlistener_snapshot_materialization.py) | Provider-free verification of direct discovery inputs. |
| [`courtlistener_unrestricted_recap_discovery.py`](../legalforecast/ingestion/courtlistener_unrestricted_recap_discovery.py) | Durable discovery including unavailable RECAP documents. |
| [`courtlistener_web.py`](../legalforecast/ingestion/courtlistener_web.py) | Public docket-page parsing and candidate ranking. |
| [`discovery_scheduler.py`](../legalforecast/ingestion/discovery_scheduler.py) | Provider-neutral, order-neutral discovery scheduling. |
| [`firecrawl_docket_pagination.py`](../legalforecast/ingestion/firecrawl_docket_pagination.py) | CourtListener docket pagination over injected transport. |
| [`firecrawl_recap_decision_discovery.py`](../legalforecast/ingestion/firecrawl_recap_decision_discovery.py) | Decision-first RECAP search through scraped HTML. |
| [`firecrawl_recap_discovery.py`](../legalforecast/ingestion/firecrawl_recap_discovery.py) | Anchored RECAP entry discovery and completeness checks. |
| [`recap_api_batch_driver.py`](../legalforecast/ingestion/recap_api_batch_driver.py) | Cycle batch drivers for the RECAP REST pipeline. |
| [`recap_api_discovery.py`](../legalforecast/ingestion/recap_api_discovery.py) | REST v4 discovery and docket reconstruction. |
| [`recap_client.py`](../legalforecast/ingestion/recap_client.py) | Typed RECAP fallback client and fixture transport. |
| [`recap_partial_checkpoint.py`](../legalforecast/ingestion/recap_partial_checkpoint.py) | Recovery projection from durably acquired search pages. |
| [`recap_search_completeness.py`](../legalforecast/ingestion/recap_search_completeness.py) | Completeness proofs for paginated RECAP searches. |

## 4. Firecrawl acquisition and recovery

**Owns:** Budgeted Firecrawl scheduling, source identity, exact-batch observation, public HTML recovery, and sealed exhaustion outcomes.

**Start with:** `budgeted_firecrawl.py` for the durable scheduler, `firecrawl_source.py` for transport, and `firecrawl_docket_recovery.py` for terminal recovery.

| Module | Responsibility |
| --- | --- |
| [`budgeted_courtlistener_html_source.py`](../legalforecast/ingestion/budgeted_courtlistener_html_source.py) | Durable budgeted CourtListener HTML source. |
| [`budgeted_docket_acquisition.py`](../legalforecast/ingestion/budgeted_docket_acquisition.py) | Ranked docket acquisition through the canonical ledger. |
| [`budgeted_firecrawl.py`](../legalforecast/ingestion/budgeted_firecrawl.py) | Budget-authorized resumable page scheduling. |
| [`firecrawl_docket_recovery.py`](../legalforecast/ingestion/firecrawl_docket_recovery.py) | Sealing a budget-exhausted ranked docket run. |
| [`firecrawl_screening_identity.py`](../legalforecast/ingestion/firecrawl_screening_identity.py) | Authenticated identity for provider-free screens. |
| [`firecrawl_source.py`](../legalforecast/ingestion/firecrawl_source.py) | Strict source for allowlisted public HTML. |
| [`frozen_batch_firecrawl_observation.py`](../legalforecast/ingestion/frozen_batch_firecrawl_observation.py) | Exact frozen-priority-batch observation. |
| [`opinion_recap_firecrawl.py`](../legalforecast/ingestion/opinion_recap_firecrawl.py) | Budgeted opinion-to-RECAP identity fallback. |

## 5. Case.dev enrichment, bridging, and purchase

**Owns:** Case.dev configuration and transport, enrichment/ranking, CourtListener bridging, smoke runs, live docket refresh, and guarded PACER purchase journals.

**Start with:** `case_dev_client.py` for transport, `case_dev_recap_enrichment.py` for free enrichment, and `case_dev_purchase.py` for fee-bearing execution.

| Module | Responsibility |
| --- | --- |
| [`case_dev_client.py`](../legalforecast/ingestion/case_dev_client.py) | Typed client and offline fixture transport. |
| [`case_dev_config.py`](../legalforecast/ingestion/case_dev_config.py) | Runtime configuration and usage estimates. |
| [`case_dev_discovery.py`](../legalforecast/ingestion/case_dev_discovery.py) | Durable order-neutral discovery adapter. |
| [`case_dev_firecrawl.py`](../legalforecast/ingestion/case_dev_firecrawl.py) | Bounded Case.dev-to-Firecrawl public HTML acquisition. |
| [`case_dev_provisional_frontier.py`](../legalforecast/ingestion/case_dev_provisional_frontier.py) | Authenticated frontier from partial Case.dev progress. |
| [`case_dev_purchase.py`](../legalforecast/ingestion/case_dev_purchase.py) | Guarded PACER purchase orchestration and journal. |
| [`case_dev_ranked_selection.py`](../legalforecast/ingestion/case_dev_ranked_selection.py) | Source-bound ranking and REST-batch selection. |
| [`case_dev_recap_batch.py`](../legalforecast/ingestion/case_dev_recap_batch.py) | Pure reconciliation for free enrichment batches. |
| [`case_dev_recap_enrichment.py`](../legalforecast/ingestion/case_dev_recap_enrichment.py) | Free enrichment and conservative cost ranking. |
| [`case_dev_scheduling.py`](../legalforecast/ingestion/case_dev_scheduling.py) | Identity-preserving enrichment scheduling. |
| [`case_dev_smoke.py`](../legalforecast/ingestion/case_dev_smoke.py) | Phase-zero smoke runner and report helpers. |
| [`courtlistener_case_dev_bridge.py`](../legalforecast/ingestion/courtlistener_case_dev_bridge.py) | Public candidate to authoritative document-ID bridge. |
| [`docket_live_fetch.py`](../legalforecast/ingestion/docket_live_fetch.py) | Planning and journaling fee-bearing docket refreshes. |

## 6. Screening, snapshots, and cohort selection

**Owns:** MTD screening, immutable cohort policy, snapshot union/replay/reconciliation, exact case-mix optimization, target projection, reserve replacement, and provider-free retargeting.

**Start with:** `mtd_acquisition_screen.py` for screening, `cohort_policy.py` for precommitments, and `target_cohort_projection.py` for exact cohort construction.

| Module | Responsibility |
| --- | --- |
| [`case_mix_optimizer.py`](../legalforecast/ingestion/case_mix_optimizer.py) | Exact cost selection under intersecting caps. |
| [`cohort_policy.py`](../legalforecast/ingestion/cohort_policy.py) | Immutable precommitments and append-only observations. |
| [`exact310_rest_rebind.py`](../legalforecast/ingestion/exact310_rest_rebind.py) | Policy layer for the exact terminal REST rebind. |
| [`mtd_acquisition_screen.py`](../legalforecast/ingestion/mtd_acquisition_screen.py) | Public-record MTD decision screening. |
| [`pacer_gap_append_rebase.py`](../legalforecast/ingestion/pacer_gap_append_rebase.py) | Append-only snapshot growth authentication. |
| [`ranked_reserve_replacement.py`](../legalforecast/ingestion/ranked_reserve_replacement.py) | Continuation through a frozen ranked reserve. |
| [`rest_observation_policy_rebind.py`](../legalforecast/ingestion/rest_observation_policy_rebind.py) | Rebind of authenticated terminal REST observations. |
| [`rest_priority_subset_promotion.py`](../legalforecast/ingestion/rest_priority_subset_promotion.py) | Promotion of a terminal REST priority tranche. |
| [`retained_cohort_extension.py`](../legalforecast/ingestion/retained_cohort_extension.py) | Provider-free extension of a frozen cohort. |
| [`screening_snapshot_union.py`](../legalforecast/ingestion/screening_snapshot_union.py) | Union of complete saturated screening snapshots. |
| [`screening_union_policy_rebind.py`](../legalforecast/ingestion/screening_union_policy_rebind.py) | Exact policy rebind for an authenticated union. |
| [`snapshot_quarantine.py`](../legalforecast/ingestion/snapshot_quarantine.py) | Quarantine of unregistered snapshot directories. |
| [`snapshot_reconciliation.py`](../legalforecast/ingestion/snapshot_reconciliation.py) | Complete screening-snapshot reconciliation. |
| [`snapshot_replay.py`](../legalforecast/ingestion/snapshot_replay.py) | Source-bound superseding-cycle rescreening inputs. |
| [`strict_screen_evidence.py`](../legalforecast/ingestion/strict_screen_evidence.py) | Canonical accepted strict-screen evidence validation. |
| [`target_100_acquisition.py`](../legalforecast/ingestion/target_100_acquisition.py) | Noncharging target-cohort preparation commands. |
| [`target_cohort_projection.py`](../legalforecast/ingestion/target_cohort_projection.py) | Exact post-clearance cohort projection. |
| [`target_preparation_retarget.py`](../legalforecast/ingestion/target_preparation_retarget.py) | Authenticated provider-free retarget import boundary. |
| [`target_public_gap_refresh.py`](../legalforecast/ingestion/target_public_gap_refresh.py) | Exact-target public-gap refresh. |
| [`terminal_subset_promotion.py`](../legalforecast/ingestion/terminal_subset_promotion.py) | Authenticated promotion of an exact terminal subset. |
| [`zero_cost_successor.py`](../legalforecast/ingestion/zero_cost_successor.py) | Exact-cohort successor after terminal recovery. |

## 7. Document planning, retrieval, and text preparation

**Owns:** Public and purchased document retrieval, core-document selection, source normalization, packet-input planning, parsing, role adjudication, and final packet assembly.

**Start with:** `public_packet_planner.py` for public inputs, `packet_input_planner.py` for authenticated inputs, and `model_packet_assembly.py` for final packets.

| Module | Responsibility |
| --- | --- |
| [`cohort_document_materializer.py`](../legalforecast/ingestion/cohort_document_materializer.py) | Immutable cleared cohort-document materialization. |
| [`core_document_filter.py`](../legalforecast/ingestion/core_document_filter.py) | Core-document filtering from relevance output. |
| [`decision_text_artifact.py`](../legalforecast/ingestion/decision_text_artifact.py) | Hash-bound first-disposition text artifacts. |
| [`docket_decision_text_source.py`](../legalforecast/ingestion/docket_decision_text_source.py) | Authenticated audit-only decision-text lineage. |
| [`docket_markdown.py`](../legalforecast/ingestion/docket_markdown.py) | Controlled docket packet and audit Markdown. |
| [`docket_sync.py`](../legalforecast/ingestion/docket_sync.py) | Docket and filing retrieval normalization. |
| [`fallback_retrieval.py`](../legalforecast/ingestion/fallback_retrieval.py) | Supplemental public-source retrieval diagnostics. |
| [`free_document_downloader.py`](../legalforecast/ingestion/free_document_downloader.py) | Fixture-safe free CourtListener/RECAP downloads. |
| [`mistral_markdown_parser.py`](../legalforecast/ingestion/mistral_markdown_parser.py) | Local conversion of acquired documents to Markdown. |
| [`model_packet_assembly.py`](../legalforecast/ingestion/model_packet_assembly.py) | Final model packets from docket and parsed artifacts. |
| [`operative_complaint.py`](../legalforecast/ingestion/operative_complaint.py) | Strict operative-complaint selection. |
| [`packet_input_planner.py`](../legalforecast/ingestion/packet_input_planner.py) | Authenticated packet-build and private-store inputs. |
| [`packet_role_adjudication.py`](../legalforecast/ingestion/packet_role_adjudication.py) | Human role adjudication against parser evidence. |
| [`public_packet_planner.py`](../legalforecast/ingestion/public_packet_planner.py) | Free public document download plans. |
| [`purchased_document_recovery.py`](../legalforecast/ingestion/purchased_document_recovery.py) | Fee-acknowledged purchased-document recovery. |

## 8. Opinion-backed resolution and gap recovery

**Owns:** Opinion-to-docket identity resolution, disposition evidence, docket-history gap planning, free-only routes, and post-recovery public lineage.

**Start with:** `opinion_recap_resolver.py` for identity, `opinion_backed_disposition.py` for evidence, and `opinion_docket_gap_planner.py` for refresh planning.

| Module | Responsibility |
| --- | --- |
| [`free_only_materialization.py`](../legalforecast/ingestion/free_only_materialization.py) | Authority for an entirely free target cohort. |
| [`opinion_backed_disposition.py`](../legalforecast/ingestion/opinion_backed_disposition.py) | Public opinions bound to resolved docket entries. |
| [`opinion_docket_gap_planner.py`](../legalforecast/ingestion/opinion_docket_gap_planner.py) | Refresh plans for opinion-backed docket gaps. |
| [`opinion_recap_resolver.py`](../legalforecast/ingestion/opinion_recap_resolver.py) | Strict opinion-lead to RECAP identity resolution. |
| [`resolved_post_recovery.py`](../legalforecast/ingestion/resolved_post_recovery.py) | Public lineage after unknown-status recovery. |

## 9. Disclosure review and provenance clearance

**Owns:** Hash-bound disclosure scanning, human and model review authority, signed review bundles, provenance-first routing, quarantine recovery, and clearance-driven replacement.

**Start with:** `disclosure_clearance.py` for scanning, `provenance_clearance.py` for routing, and `disclosure_review_bundle.py` for signed review evidence.

| Module | Responsibility |
| --- | --- |
| [`clearance_replacement.py`](../legalforecast/ingestion/clearance_replacement.py) | Frozen replacement planning after clearance. |
| [`disclosure_clearance.py`](../legalforecast/ingestion/disclosure_clearance.py) | Hash-bound acquired-document clearance. |
| [`disclosure_model_review.py`](../legalforecast/ingestion/disclosure_model_review.py) | Pure review of disclosure-marker exception pages. |
| [`disclosure_model_review_authority.py`](../legalforecast/ingestion/disclosure_model_review_authority.py) | Authenticated execution authority for model review. |
| [`disclosure_review_authorities/__init__.py`](../legalforecast/ingestion/disclosure_review_authorities/__init__.py) | Namespace for disclosure-review authority providers. |
| [`disclosure_review_authority.py`](../legalforecast/ingestion/disclosure_review_authority.py) | Main-pinned hardware-authenticated review authority. |
| [`disclosure_review_bundle.py`](../legalforecast/ingestion/disclosure_review_bundle.py) | Deterministic externally signed review bundles. |
| [`provenance_clearance.py`](../legalforecast/ingestion/provenance_clearance.py) | Provenance-first routing with human exceptions. |
| [`recap_fetch_quarantine_recovery.py`](../legalforecast/ingestion/recap_fetch_quarantine_recovery.py) | Controlled recovery of unknown-status documents. |
| [`replacement_recovery_source.py`](../legalforecast/ingestion/replacement_recovery_source.py) | Authenticated recovery-source descriptors for replacement consolidation. |

## 10. Spend authority, RECAP Fetch, and terminal outcomes

**Owns:** Purchase approvals, immutable attempt/broker policy, isolated RECAP Fetch submission, missing-document budgets, reconciliation, and terminal failure evidence.

**Start with:** `purchase_approval.py` for human authority, `recap_fetch_broker.py` for isolated submission, and `recap_fetch_attempt_policy.py` for bounded retry authority.

| Module | Responsibility |
| --- | --- |
| [`courtlistener_recap_fetch.py`](../legalforecast/ingestion/courtlistener_recap_fetch.py) | Guarded individual-document RECAP Fetch purchases. |
| [`missing_core_budget.py`](../legalforecast/ingestion/missing_core_budget.py) | Cost guardrails for missing core documents. |
| [`purchase_approval.py`](../legalforecast/ingestion/purchase_approval.py) | Human approval for an exact purchase plan. |
| [`recap_fetch_attempt_policy.py`](../legalforecast/ingestion/recap_fetch_attempt_policy.py) | Immutable bounded unknown-status attempt authority. |
| [`recap_fetch_broker.py`](../legalforecast/ingestion/recap_fetch_broker.py) | Signed isolated budget-enforcing broker client. |
| [`recap_fetch_broker_policy.py`](../legalforecast/ingestion/recap_fetch_broker_policy.py) | Broker allowlist derived from executable artifacts. |
| [`replacement_purchase_approval.py`](../legalforecast/ingestion/replacement_purchase_approval.py) | Approval for a clearance-replacement tranche. |
| [`terminal_purchase_failure.py`](../legalforecast/ingestion/terminal_purchase_failure.py) | Verifier for cap-counted terminal purchase failures. |

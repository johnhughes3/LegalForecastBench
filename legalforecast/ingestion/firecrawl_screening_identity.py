"""Fail-closed source identity for the provider-free Firecrawl screen.

The global cycle identity intentionally covers only the source-neutral strict
screen.  Firecrawl replay and promotion execute additional parsing,
orchestration, and storage code.  This module commits that closed transitive
set without changing the identity of independent CourtListener REST snapshots.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.ingestion.strict_screen_evidence import (
    StrictScreenEvidenceError,
    validate_strict_screen_evidence,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA: Final = (
    "legalforecast.firecrawl_screening_implementation.v1"
)
SCREENING_SNAPSHOT_UNION_INPUTS_SCHEMA: Final = (
    "legalforecast.screening_snapshot_union_inputs.v2"
)
FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY: Final = (
    "firecrawl_screening_implementation"
)
FIRECRAWL_SCREENING_DIRECT_STAGE_KEYS: Final = frozenset(
    {
        "firecrawl_screen_inputs",
        "source_bound_replay",
        "terminal_subset_promotion",
    }
)
SCREENING_SNAPSHOT_UNION_STAGE_KEY: Final = "screening_snapshot_union_inputs"
SCREENING_UNION_POLICY_REBIND_STAGE_KEY: Final = "screening_union_policy_rebind"
SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA: Final = (
    "legalforecast.screening_union_policy_rebind_implementation.v1"
)
REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY: Final = "rest_terminal_subset_promotion"
REST_TERMINAL_SUBSET_PROMOTION_SCHEMA: Final = (
    "legalforecast.rest_terminal_subset_promotion.v1"
)
REST_PRIORITY_SELECTION_POLICY_SCHEMA: Final = (
    "legalforecast.rest_priority_subset_selection_policy.v1"
)
REST_PRIORITY_DEFERRED_OMISSION_SCHEMA: Final = (
    "legalforecast.rest_priority_deferred_omission_inventory.v1"
)
SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS: Final = (
    "legalforecast/cli.py",
    "legalforecast/ingestion/cycle_acquisition_store.py",
    "legalforecast/ingestion/firecrawl_screening_identity.py",
    "legalforecast/ingestion/restricted_material.py",
    "legalforecast/ingestion/screening_snapshot_union.py",
    "legalforecast/ingestion/screening_union_policy_rebind.py",
    "legalforecast/ingestion/strict_screen_evidence.py",
)
SOURCE_NEUTRAL_DIRECT_STAGE_KEYS: Final = frozenset(
    {
        "courtlistener_discovery_inputs",
        "courtlistener_rest_screen_inputs",
        REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY,
    }
)
SOURCE_NEUTRAL_NAMED_STAGES: Final = frozenset(
    {
        "exact310-terminal-rest-policy-rebind",
        "rebind-terminal-rest-observations",
    }
)

# Ordered exactly as the audited 18-file compatibility set.  The strict-proof
# validator and recursive union loader are load-bearing admission code, and the
# identity module itself closes the resulting 21-file set.
FIRECRAWL_SCREENING_SOURCE_PATHS: Final = (
    "legalforecast/cli.py",
    "legalforecast/ingestion/budgeted_docket_acquisition.py",
    "legalforecast/ingestion/case_dev_firecrawl.py",
    "legalforecast/ingestion/courtlistener_acquisition.py",
    "legalforecast/ingestion/courtlistener_client.py",
    "legalforecast/ingestion/courtlistener_dates.py",
    "legalforecast/ingestion/courtlistener_web.py",
    "legalforecast/ingestion/cycle_acquisition_store.py",
    "legalforecast/ingestion/docket_sync.py",
    "legalforecast/ingestion/mtd_acquisition_screen.py",
    "legalforecast/ingestion/operative_complaint.py",
    "legalforecast/ingestion/provenance.py",
    "legalforecast/ingestion/recap_api_discovery.py",
    "legalforecast/ingestion/restricted_material.py",
    "legalforecast/ingestion/snapshot_replay.py",
    "legalforecast/ingestion/strict_screen_evidence.py",
    "legalforecast/ingestion/screening_snapshot_union.py",
    "legalforecast/selection/contamination_filters.py",
    "legalforecast/selection/exclusion_ledger.py",
    "legalforecast/selection/motion_linkage.py",
    "legalforecast/ingestion/firecrawl_screening_identity.py",
)

LEGACY_32057DE_SOURCE_MANIFEST_SHA256: Final = (
    "3e1628b1bbeb3d2af682baaa12815a4c631a64a0ca95eadf2d70e9fa9da419c9"
)
LEGACY_32057DE_SOURCE_SHA256: Final[Mapping[str, str]] = {
    "legalforecast/cli.py": (
        "f8084d8e8dea277366131b0ba899e6034ebc3fc000621ddaca798825b855e18c"
    ),
    "legalforecast/ingestion/budgeted_docket_acquisition.py": (
        "a11b91e5b9cef810ab88d6dde16bfe0dc4d77dbce798bf3e354261d34f8c10a9"
    ),
    "legalforecast/ingestion/case_dev_firecrawl.py": (
        "4e3d1bf19c975264c185d1ef6e1c3132a43b72e91d2031b7e98ca93b028180b1"
    ),
    "legalforecast/ingestion/courtlistener_acquisition.py": (
        "261ab270306634cdaf18520ed7bc5e39282ce4dac923c8bb2e307ebda8445394"
    ),
    "legalforecast/ingestion/courtlistener_client.py": (
        "5afbee992368bd790db9eb118a08b895bfe01599f51d8f37885f3d0fcc31640c"
    ),
    "legalforecast/ingestion/courtlistener_dates.py": (
        "c414deb237d62fe6fbdd43863cdd4acf0387a5de54ecb21f0cd7c0ec88417f3d"
    ),
    "legalforecast/ingestion/courtlistener_web.py": (
        "35f4b0a3c88a55cc00de1a61782b8c5a8f1ba64db23c2fe55a1f950ff12c869b"
    ),
    "legalforecast/ingestion/cycle_acquisition_store.py": (
        "94ef6986c054250f75ee93d4f5d99a5192b51fdb03ee4627eea694325b1f0973"
    ),
    "legalforecast/ingestion/docket_sync.py": (
        "0731149bd3d84bf6d87d6e59fbe2631555b4b345b3d0824ad01bb567bc80d33f"
    ),
    "legalforecast/ingestion/mtd_acquisition_screen.py": (
        "72084326faa7f76afc6075556fd8ba6738df83189ce178100cb1a0eb50630e7e"
    ),
    "legalforecast/ingestion/operative_complaint.py": (
        "aff85d1a327d3a7dc44f884d9bd833010ffe3fb32136d48153d4ccb48851a5eb"
    ),
    "legalforecast/ingestion/provenance.py": (
        "fb67f7db133dd3382c12c37010485d321f9b0fab93d7fc9a2f617628d254ae14"
    ),
    "legalforecast/ingestion/recap_api_discovery.py": (
        "ca6ed64c73939778dd1a30e3e018cb72e1866d7ba854c3e061807c9dcd9f8623"
    ),
    "legalforecast/ingestion/restricted_material.py": (
        "f36a0cf5b5db5e3d6d997d46095cccfde89be9a9213db6b26576a116ed16758d"
    ),
    "legalforecast/ingestion/snapshot_replay.py": (
        "b019d01e2a1fef7546d7c12a50dafa60bf6f4c6862493633e60a986a3e410ac1"
    ),
    "legalforecast/selection/contamination_filters.py": (
        "e1437bf64633071c06fa28bee618e8cc17e2a41ca929e9e3a1e8164e4048bde9"
    ),
    "legalforecast/selection/exclusion_ledger.py": (
        "092dc50db5bd27ea924c61472841522a2bce03f9ae81115ed2aceb5d5a6a2915"
    ),
    "legalforecast/selection/motion_linkage.py": (
        "a44d1bb198801cc99d3057d148527e31d6cd5ef6dbdfc0c13271f2cc97f8cfe2"
    ),
}

COMPATIBLE_4D3BA85_SOURCE_MANIFEST_SHA256: Final = (
    "913e76a76c3d0cd69640e1034bec8c13557cdb03dc5d77f35c5ab82c7e8448c5"
)
COMPATIBLE_4D3BA85_SOURCE_SHA256: Final[Mapping[str, str]] = {
    "legalforecast/cli.py": (
        "dfebc9187b35f2c2d36eff94314907de837c03c4b1dca5abd09a1353d9f2ae4b"
    ),
    "legalforecast/ingestion/budgeted_docket_acquisition.py": (
        "a11b91e5b9cef810ab88d6dde16bfe0dc4d77dbce798bf3e354261d34f8c10a9"
    ),
    "legalforecast/ingestion/case_dev_firecrawl.py": (
        "4e3d1bf19c975264c185d1ef6e1c3132a43b72e91d2031b7e98ca93b028180b1"
    ),
    "legalforecast/ingestion/courtlistener_acquisition.py": (
        "261ab270306634cdaf18520ed7bc5e39282ce4dac923c8bb2e307ebda8445394"
    ),
    "legalforecast/ingestion/courtlistener_client.py": (
        "5afbee992368bd790db9eb118a08b895bfe01599f51d8f37885f3d0fcc31640c"
    ),
    "legalforecast/ingestion/courtlistener_dates.py": (
        "c414deb237d62fe6fbdd43863cdd4acf0387a5de54ecb21f0cd7c0ec88417f3d"
    ),
    "legalforecast/ingestion/courtlistener_web.py": (
        "35f4b0a3c88a55cc00de1a61782b8c5a8f1ba64db23c2fe55a1f950ff12c869b"
    ),
    "legalforecast/ingestion/cycle_acquisition_store.py": (
        "8056af7bb6ca810fe945153f0e79ded8d4879abf0305a7bda98e99805739807a"
    ),
    "legalforecast/ingestion/docket_sync.py": (
        "0731149bd3d84bf6d87d6e59fbe2631555b4b345b3d0824ad01bb567bc80d33f"
    ),
    "legalforecast/ingestion/firecrawl_screening_identity.py": (
        "41da191a51cd8ade7decce5c3c3c5bf4fad0dd88af64da39d1b8f94f5370d626"
    ),
    "legalforecast/ingestion/mtd_acquisition_screen.py": (
        "72084326faa7f76afc6075556fd8ba6738df83189ce178100cb1a0eb50630e7e"
    ),
    "legalforecast/ingestion/operative_complaint.py": (
        "aff85d1a327d3a7dc44f884d9bd833010ffe3fb32136d48153d4ccb48851a5eb"
    ),
    "legalforecast/ingestion/provenance.py": (
        "fb67f7db133dd3382c12c37010485d321f9b0fab93d7fc9a2f617628d254ae14"
    ),
    "legalforecast/ingestion/recap_api_discovery.py": (
        "ca6ed64c73939778dd1a30e3e018cb72e1866d7ba854c3e061807c9dcd9f8623"
    ),
    "legalforecast/ingestion/restricted_material.py": (
        "f36a0cf5b5db5e3d6d997d46095cccfde89be9a9213db6b26576a116ed16758d"
    ),
    "legalforecast/ingestion/screening_snapshot_union.py": (
        "ed8e10077ea0d86a25dc34a443b22f595e28d598730ff0ec342c97c974d2d8fc"
    ),
    "legalforecast/ingestion/snapshot_replay.py": (
        "eb0c03115d606630d15bccad3cf29332313be41a854ea90e9c385bee549c088b"
    ),
    "legalforecast/ingestion/strict_screen_evidence.py": (
        "135663c6a0e666e440d3b269b7a608062799ae5830f06dfc810c99bdda4026f3"
    ),
    "legalforecast/selection/contamination_filters.py": (
        "e1437bf64633071c06fa28bee618e8cc17e2a41ca929e9e3a1e8164e4048bde9"
    ),
    "legalforecast/selection/exclusion_ledger.py": (
        "092dc50db5bd27ea924c61472841522a2bce03f9ae81115ed2aceb5d5a6a2915"
    ),
    "legalforecast/selection/motion_linkage.py": (
        "a44d1bb198801cc99d3057d148527e31d6cd5ef6dbdfc0c13271f2cc97f8cfe2"
    ),
}

COMPATIBLE_FINAL_V3_SOURCE_MANIFEST_SHA256: Final = (
    "9e076e7f488f60e7f8308af4f27db7f38b9418383c53ccd1e9d652c6236a955c"
)
COMPATIBLE_FINAL_V3_SOURCE_SHA256: Final[Mapping[str, str]] = {
    "legalforecast/cli.py": (
        "08cde002a79e9c2f6ece0dc25a977e7c2c4b3bd010d9502d87ca5e30e76795d3"
    ),
    "legalforecast/ingestion/budgeted_docket_acquisition.py": (
        "a11b91e5b9cef810ab88d6dde16bfe0dc4d77dbce798bf3e354261d34f8c10a9"
    ),
    "legalforecast/ingestion/case_dev_firecrawl.py": (
        "4e3d1bf19c975264c185d1ef6e1c3132a43b72e91d2031b7e98ca93b028180b1"
    ),
    "legalforecast/ingestion/courtlistener_acquisition.py": (
        "261ab270306634cdaf18520ed7bc5e39282ce4dac923c8bb2e307ebda8445394"
    ),
    "legalforecast/ingestion/courtlistener_client.py": (
        "5afbee992368bd790db9eb118a08b895bfe01599f51d8f37885f3d0fcc31640c"
    ),
    "legalforecast/ingestion/courtlistener_dates.py": (
        "c414deb237d62fe6fbdd43863cdd4acf0387a5de54ecb21f0cd7c0ec88417f3d"
    ),
    "legalforecast/ingestion/courtlistener_web.py": (
        "9a3afae7ba91ac07e1f1b99ff5cfa0afc82207dcc93e4f80723d9ec85cb66905"
    ),
    "legalforecast/ingestion/cycle_acquisition_store.py": (
        "8056af7bb6ca810fe945153f0e79ded8d4879abf0305a7bda98e99805739807a"
    ),
    "legalforecast/ingestion/docket_sync.py": (
        "0731149bd3d84bf6d87d6e59fbe2631555b4b345b3d0824ad01bb567bc80d33f"
    ),
    "legalforecast/ingestion/firecrawl_screening_identity.py": (
        "dc3b00b2cbb22df0d8067dac2522d1a371d43ffa9c70d2da5b1d7b490fad8b4d"
    ),
    "legalforecast/ingestion/mtd_acquisition_screen.py": (
        "72084326faa7f76afc6075556fd8ba6738df83189ce178100cb1a0eb50630e7e"
    ),
    "legalforecast/ingestion/operative_complaint.py": (
        "aff85d1a327d3a7dc44f884d9bd833010ffe3fb32136d48153d4ccb48851a5eb"
    ),
    "legalforecast/ingestion/provenance.py": (
        "fb67f7db133dd3382c12c37010485d321f9b0fab93d7fc9a2f617628d254ae14"
    ),
    "legalforecast/ingestion/recap_api_discovery.py": (
        "ca6ed64c73939778dd1a30e3e018cb72e1866d7ba854c3e061807c9dcd9f8623"
    ),
    "legalforecast/ingestion/restricted_material.py": (
        "f36a0cf5b5db5e3d6d997d46095cccfde89be9a9213db6b26576a116ed16758d"
    ),
    "legalforecast/ingestion/screening_snapshot_union.py": (
        "c95f22b456dda41dc7575ad50da638fb59adb27276aebe571ba3d036a9f23bc3"
    ),
    "legalforecast/ingestion/snapshot_replay.py": (
        "eb0c03115d606630d15bccad3cf29332313be41a854ea90e9c385bee549c088b"
    ),
    "legalforecast/ingestion/strict_screen_evidence.py": (
        "135663c6a0e666e440d3b269b7a608062799ae5830f06dfc810c99bdda4026f3"
    ),
    "legalforecast/selection/contamination_filters.py": (
        "e1437bf64633071c06fa28bee618e8cc17e2a41ca929e9e3a1e8164e4048bde9"
    ),
    "legalforecast/selection/exclusion_ledger.py": (
        "092dc50db5bd27ea924c61472841522a2bce03f9ae81115ed2aceb5d5a6a2915"
    ),
    "legalforecast/selection/motion_linkage.py": (
        "a44d1bb198801cc99d3057d148527e31d6cd5ef6dbdfc0c13271f2cc97f8cfe2"
    ),
}


class FirecrawlScreeningIdentityError(ValueError):
    """Raised when a Firecrawl screening source commitment is not exact."""


_REST_PROMOTION_FIELDS: Final = frozenset(
    {
        "schema_version",
        "selection_semantics",
        "eligibility_anchor_date",
        "cycle_hash",
        "priority_batch_id",
        "priority_batch_digest",
        "priority_snapshot_manifest_sha256",
        "priority_screened_cases_sha256",
        "priority_exclusions_sha256",
        "priority_frontier_file_sha256",
        "priority_frontier_sha256",
        "source_batch_id",
        "source_batch_digest",
        "source_candidate_count",
        "source_candidate_set_sha256",
        "source_candidate_id_set_sha256",
        "source_lineage_commitment_sha256",
        "ranking_policy_sha256",
        "selection_policy_sha256",
        "selection_policy",
        "tranche_ordinal",
        "selected_candidate_count",
        "selected_candidate_ids",
        "selected_candidate_id_set_sha256",
        "selected_candidate_set_sha256",
        "selected_terminal_observations_sha256",
        "accepted_candidate_count",
        "accepted_candidate_ids",
        "accepted_candidate_id_set_sha256",
        "excluded_candidate_count",
        "excluded_candidate_ids",
        "excluded_candidate_id_set_sha256",
        "deferred_omission_inventory",
        "strict_screen_is_sole_eligibility_and_exclusion_authority",
        "ranking_metadata_visibility",
        "cohort_sampling_claim",
        "parent_source_fully_screened",
        "terminality_scope",
        "final_cohort_eligible",
        "full_source_terminal",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
        "evaluation_activity_executed",
        "freeze_activity_executed",
        "dispatch_activity_executed",
    }
)
_REST_SELECTION_POLICY_FIELDS: Final = frozenset(
    {
        "schema_version",
        "approval_reference",
        "approved_by",
        "approved",
        "cohort_shape",
        "benchmark_claim_scope",
        "selection_purpose",
        "representative_sample_claimed",
        "acquisition_only",
        "model_visible",
        "outcome_polarity_blind",
        "outcome_polarity_used",
        "stage_b_labels_used",
        "model_outputs_used",
        "strict_screen_is_sole_eligibility_and_exclusion_authority",
        "ranking_metadata_visibility",
        "eligibility_anchor_date",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
    }
)
_REST_DEFERRED_OMISSION_FIELDS: Final = frozenset(
    {
        "schema_version",
        "disposition",
        "candidate_count",
        "candidate_ids",
        "candidate_id_set_sha256",
        "jsonl_sha256",
        "parent_source_candidate_count",
        "selected_plus_deferred_partition_sha256",
    }
)


def canonical_rest_commitment_json_bytes(value: object) -> bytes:
    """Serialize REST promotion commitments with one stable UTF-8 encoding."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise FirecrawlScreeningIdentityError(
            "REST commitment input is not canonical JSON"
        ) from exc


def rest_priority_candidate_id_set_sha256(candidate_ids: Sequence[str]) -> str:
    """Hash one unique candidate-ID set as sorted canonical JSON."""

    normalized = list(candidate_ids)
    if len(normalized) != len(set(normalized)):
        raise FirecrawlScreeningIdentityError(
            "REST priority candidate IDs must be unique"
        )
    return hashlib.sha256(
        canonical_rest_commitment_json_bytes(sorted(normalized))
    ).hexdigest()


def rest_priority_partition_sha256(
    *,
    selected_candidate_ids: Sequence[str],
    deferred_candidate_ids: Sequence[str],
) -> str:
    """Hash the exact selected/deferred parent partition."""

    selected = _rest_candidate_ids(
        selected_candidate_ids, "REST priority selected candidate IDs"
    )
    deferred = _rest_candidate_ids(
        deferred_candidate_ids, "REST priority deferred candidate IDs"
    )
    payload = canonical_rest_commitment_json_bytes(
        {
            "deferred_candidate_ids": deferred,
            "selected_candidate_ids": selected,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def rest_priority_deferred_omission_jsonl_bytes(
    candidate_ids: Sequence[str],
) -> bytes:
    """Serialize the committed omission inventory with canonical JSONL bytes."""

    normalized = _rest_candidate_ids(
        candidate_ids, "REST priority deferred candidate IDs"
    )
    return b"".join(
        canonical_rest_commitment_json_bytes(
            {
                "candidate_id": candidate_id,
                "disposition": "unscreened_not_excluded",
                "schema_version": ("legalforecast.rest_priority_deferred_omission.v1"),
            }
        )
        + b"\n"
        for candidate_id in normalized
    )


def validate_rest_terminal_subset_promotion_commitment(
    commitment: object,
    *,
    snapshot_candidate_ids: Sequence[str],
    snapshot_accepted_ids: Sequence[str],
    snapshot_excluded_ids: Sequence[str],
) -> dict[str, object]:
    """Validate the source-neutral, acquisition-shaped REST promotion form."""

    if not isinstance(commitment, Mapping):
        raise FirecrawlScreeningIdentityError(
            "REST terminal subset promotion commitment must be an object"
        )
    typed = cast(Mapping[str, object], commitment)
    if set(typed) != set(_REST_PROMOTION_FIELDS):
        raise FirecrawlScreeningIdentityError(
            "REST terminal subset promotion commitment has unexpected fields"
        )
    if (
        typed.get("schema_version") != REST_TERMINAL_SUBSET_PROMOTION_SCHEMA
        or typed.get("selection_semantics") != "exact_frozen_priority_tranche"
        or typed.get("terminality_scope") != "promoted_exact_selected_source"
        or typed.get("cohort_sampling_claim")
        != (
            "convenience_acquisition_shaped_nonrepresentative_"
            "relative_model_comparison_only"
        )
        or typed.get("ranking_metadata_visibility")
        != "acquisition_only_never_packet_visible"
        or typed.get("tranche_ordinal") != 1
    ):
        raise FirecrawlScreeningIdentityError(
            "REST terminal subset promotion semantics are invalid"
        )
    _rest_required_text(typed, "eligibility_anchor_date")
    for field in (
        "cycle_hash",
        "priority_batch_digest",
        "priority_snapshot_manifest_sha256",
        "priority_screened_cases_sha256",
        "priority_exclusions_sha256",
        "priority_frontier_file_sha256",
        "priority_frontier_sha256",
        "source_batch_digest",
        "source_candidate_set_sha256",
        "source_candidate_id_set_sha256",
        "source_lineage_commitment_sha256",
        "ranking_policy_sha256",
        "selection_policy_sha256",
        "selected_candidate_id_set_sha256",
        "selected_candidate_set_sha256",
        "selected_terminal_observations_sha256",
        "accepted_candidate_id_set_sha256",
        "excluded_candidate_id_set_sha256",
    ):
        _rest_sha256(typed, field)
    for field in ("priority_batch_id", "source_batch_id"):
        _rest_required_text(typed, field)

    selected = _rest_candidate_ids(
        typed.get("selected_candidate_ids"), "REST promotion selected candidate IDs"
    )
    accepted = _rest_candidate_ids(
        typed.get("accepted_candidate_ids"), "REST promotion accepted candidate IDs"
    )
    excluded = _rest_candidate_ids(
        typed.get("excluded_candidate_ids"), "REST promotion excluded candidate IDs"
    )
    actual_candidates = _rest_candidate_ids(
        snapshot_candidate_ids, "REST promotion snapshot candidate IDs"
    )
    actual_accepted = _rest_candidate_ids(
        snapshot_accepted_ids, "REST promotion snapshot accepted IDs"
    )
    actual_excluded = _rest_candidate_ids(
        snapshot_excluded_ids, "REST promotion snapshot excluded IDs"
    )
    if set(accepted).intersection(excluded) or set(accepted).union(excluded) != set(
        selected
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion accepted and excluded IDs do not partition selection"
        )
    if (
        set(selected) != set(actual_candidates)
        or set(accepted) != set(actual_accepted)
        or set(excluded) != set(actual_excluded)
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion snapshot IDs differ from committed terminal IDs"
        )
    for count_field, values in (
        ("selected_candidate_count", selected),
        ("accepted_candidate_count", accepted),
        ("excluded_candidate_count", excluded),
    ):
        if typed.get(count_field) != len(values):
            raise FirecrawlScreeningIdentityError(
                f"REST promotion {count_field} does not reconcile"
            )
    for digest_field, values in (
        ("selected_candidate_id_set_sha256", selected),
        ("accepted_candidate_id_set_sha256", accepted),
        ("excluded_candidate_id_set_sha256", excluded),
    ):
        if typed.get(digest_field) != rest_priority_candidate_id_set_sha256(values):
            raise FirecrawlScreeningIdentityError(
                f"REST promotion {digest_field} does not reconcile"
            )

    deferred_value = typed.get("deferred_omission_inventory")
    if not isinstance(deferred_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "REST promotion deferred omission inventory must be an object"
        )
    deferred = cast(Mapping[str, object], deferred_value)
    if (
        set(deferred) != set(_REST_DEFERRED_OMISSION_FIELDS)
        or deferred.get("schema_version") != REST_PRIORITY_DEFERRED_OMISSION_SCHEMA
        or deferred.get("disposition") != "unscreened_not_excluded"
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion deferred omission inventory is invalid"
        )
    deferred_ids = _rest_candidate_ids(
        deferred.get("candidate_ids"), "REST promotion deferred candidate IDs"
    )
    if set(selected).intersection(deferred_ids):
        raise FirecrawlScreeningIdentityError(
            "REST promotion selected and deferred candidate IDs overlap"
        )
    parent_count = typed.get("source_candidate_count")
    if (
        isinstance(parent_count, bool)
        or not isinstance(parent_count, int)
        or parent_count < 1
        or deferred.get("candidate_count") != len(deferred_ids)
        or deferred.get("parent_source_candidate_count") != parent_count
        or len(selected) + len(deferred_ids) != parent_count
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion selected/deferred parent partition does not reconcile"
        )
    if deferred.get("candidate_id_set_sha256") != rest_priority_candidate_id_set_sha256(
        deferred_ids
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion deferred candidate ID commitment mismatch"
        )
    omission_jsonl = rest_priority_deferred_omission_jsonl_bytes(deferred_ids)
    if deferred.get("jsonl_sha256") != hashlib.sha256(omission_jsonl).hexdigest():
        raise FirecrawlScreeningIdentityError(
            "REST promotion deferred omission JSONL commitment mismatch"
        )
    if typed.get("source_candidate_id_set_sha256") != (
        rest_priority_candidate_id_set_sha256((*selected, *deferred_ids))
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion parent candidate ID commitment mismatch"
        )
    if deferred.get("selected_plus_deferred_partition_sha256") != (
        rest_priority_partition_sha256(
            selected_candidate_ids=selected,
            deferred_candidate_ids=deferred_ids,
        )
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion selected/deferred partition commitment mismatch"
        )

    policy_value = typed.get("selection_policy")
    policy = _validate_rest_priority_selection_policy(
        policy_value,
        eligibility_anchor_date=cast(str, typed["eligibility_anchor_date"]),
    )
    policy_sha256 = hashlib.sha256(
        canonical_rest_commitment_json_bytes(policy)
    ).hexdigest()
    if typed.get("selection_policy_sha256") != policy_sha256:
        raise FirecrawlScreeningIdentityError(
            "REST promotion selection-policy commitment mismatch"
        )
    required_true = (
        "strict_screen_is_sole_eligibility_and_exclusion_authority",
        "final_cohort_eligible",
        "full_source_terminal",
    )
    required_false = (
        "parent_source_fully_screened",
        "provider_activity_requested",
        "provider_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
        "evaluation_activity_executed",
        "freeze_activity_executed",
        "dispatch_activity_executed",
    )
    if any(typed.get(field) is not True for field in required_true) or any(
        typed.get(field) is not False for field in required_false
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion authority or activity flags are invalid"
        )
    return {field: typed[field] for field in sorted(_REST_PROMOTION_FIELDS)}


def validate_rest_terminal_subset_promotion_snapshot_evidence(
    commitment: Mapping[str, object],
    *,
    snapshot_candidates: Sequence[Mapping[str, Any]],
    snapshot_screened: Sequence[Mapping[str, Any]],
    snapshot_exclusions: Sequence[Mapping[str, Any]],
) -> None:
    """Reconcile a promoted snapshot's terminal records to its frozen evidence.

    Manifest repinning authenticates bytes, but it must not let an operator change
    a promoted terminal and then bless the changed bytes with a new manifest.
    The promotion commitment therefore binds the complete terminal projection,
    while the accepted/excluded ledgers must remain exact projections of that
    same evidence.
    """

    selected = _rest_candidate_ids(
        commitment.get("selected_candidate_ids"),
        "REST promotion selected candidate IDs",
    )
    anchor = _rest_required_text(commitment, "eligibility_anchor_date")
    candidates_by_id = _rest_rows_by_candidate_id(
        snapshot_candidates, "REST promotion candidates"
    )
    if set(candidates_by_id) != set(selected):
        raise FirecrawlScreeningIdentityError(
            "REST promotion candidate records differ from committed selection"
        )

    terminal_projections: list[dict[str, object]] = []
    accepted_ids: list[str] = []
    excluded_ids: list[str] = []
    expected_screened: dict[str, dict[str, object]] = {}
    expected_exclusions: dict[str, dict[str, object]] = {}
    for candidate_id in selected:
        row = candidates_by_id[candidate_id]
        state = row.get("state")
        reason_code = row.get("reason_code")
        observed_at = row.get("observed_at")
        evidence = row.get("evidence")
        if (
            state not in {"accepted", "excluded"}
            or not isinstance(reason_code, str)
            or not reason_code.strip()
            or not isinstance(observed_at, str)
            or not observed_at.strip()
            or not isinstance(evidence, Mapping)
        ):
            raise FirecrawlScreeningIdentityError(
                f"REST promotion terminal record is invalid: {candidate_id}"
            )
        typed_evidence = cast(Mapping[str, Any], evidence)
        if typed_evidence.get("candidate_id") != candidate_id:
            raise FirecrawlScreeningIdentityError(
                f"REST promotion evidence identity mismatch: {candidate_id}"
            )
        if state == "accepted":
            if reason_code != "strict_clean_screen_passed":
                raise FirecrawlScreeningIdentityError(
                    f"REST promotion acceptance reason is invalid: {candidate_id}"
                )
            try:
                validate_strict_screen_evidence(
                    typed_evidence,
                    expected_candidate_id=candidate_id,
                )
            except StrictScreenEvidenceError as exc:
                raise FirecrawlScreeningIdentityError(str(exc)) from exc
            if typed_evidence.get("eligibility_anchor_date") != anchor:
                raise FirecrawlScreeningIdentityError(
                    "REST promotion acceptance does not use the committed "
                    f"eligibility anchor: {candidate_id}"
                )
            accepted_ids.append(candidate_id)
        else:
            excluded_ids.append(candidate_id)

        outcome = dict(typed_evidence)
        outcome["candidate_id"] = candidate_id
        if state == "excluded":
            outcome.setdefault("reason", reason_code)
            outcome.setdefault("primary_exclusion_reason", reason_code)
            expected_exclusions[candidate_id] = outcome
        else:
            expected_screened[candidate_id] = outcome
        terminal_projections.append(
            {
                "candidate_id": candidate_id,
                "state": state,
                "reason_code": reason_code,
                "evidence": dict(typed_evidence),
                "observed_at": observed_at,
            }
        )

    actual_terminal_sha256 = hashlib.sha256(
        json.dumps(
            terminal_projections,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    if (
        commitment.get("selected_terminal_observations_sha256")
        != actual_terminal_sha256
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion terminal observations differ from commitment"
        )
    committed_accepted = _rest_candidate_ids(
        commitment.get("accepted_candidate_ids"),
        "REST promotion accepted candidate IDs",
    )
    committed_excluded = _rest_candidate_ids(
        commitment.get("excluded_candidate_ids"),
        "REST promotion excluded candidate IDs",
    )
    if accepted_ids != committed_accepted:
        raise FirecrawlScreeningIdentityError(
            "REST promotion accepted terminal ordering differs from commitment"
        )
    if excluded_ids != committed_excluded:
        raise FirecrawlScreeningIdentityError(
            "REST promotion excluded terminal ordering differs from commitment"
        )
    if (
        _rest_rows_by_candidate_id(snapshot_screened, "REST promotion screened cases")
        != expected_screened
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion screened evidence differs from terminal evidence"
        )
    if (
        _rest_rows_by_candidate_id(snapshot_exclusions, "REST promotion exclusions")
        != expected_exclusions
    ):
        raise FirecrawlScreeningIdentityError(
            "REST promotion exclusion evidence differs from terminal evidence"
        )


def validate_rest_terminal_subset_promotions_in_snapshot(
    stage_commitments: Mapping[str, object],
    *,
    snapshot_candidates: Sequence[Mapping[str, Any]],
    snapshot_screened: Sequence[Mapping[str, Any]],
    snapshot_exclusions: Sequence[Mapping[str, Any]],
) -> int:
    """Validate every direct or nested REST-promotion leaf against outer rows.

    A union carries its source commitments transitively.  Consequently, an
    outer repinned snapshot must reprove each embedded promotion against the
    outer snapshot's actual terminal records rather than merely validating the
    embedded commitment in isolation.
    """

    promotion_leaves: list[Mapping[str, object]] = []
    _collect_rest_terminal_subset_promotion_leaves(
        stage_commitments,
        label="snapshot",
        promotion_leaves=promotion_leaves,
    )
    seen_ids: set[str] = set()
    candidates_by_id = _rest_rows_by_candidate_id(
        snapshot_candidates, "REST promotion outer candidates"
    )
    screened_by_id = _rest_rows_by_candidate_id(
        snapshot_screened, "REST promotion outer screened cases"
    )
    exclusions_by_id = _rest_rows_by_candidate_id(
        snapshot_exclusions, "REST promotion outer exclusions"
    )
    for index, promotion in enumerate(promotion_leaves, start=1):
        selected = _rest_candidate_ids(
            promotion.get("selected_candidate_ids"),
            f"REST promotion leaf {index} selected candidate IDs",
        )
        overlap = seen_ids.intersection(selected)
        if overlap:
            raise FirecrawlScreeningIdentityError(
                "REST promotion leaves overlap or repeat candidates: "
                + ", ".join(sorted(overlap))
            )
        seen_ids.update(selected)
        selected_set = set(selected)
        leaf_candidates = [
            candidates_by_id[candidate_id]
            for candidate_id in selected
            if candidate_id in candidates_by_id
        ]
        leaf_screened = [
            screened_by_id[candidate_id]
            for candidate_id in selected
            if candidate_id in screened_by_id
        ]
        leaf_exclusions = [
            exclusions_by_id[candidate_id]
            for candidate_id in selected
            if candidate_id in exclusions_by_id
        ]
        actual_accepted_ids = [
            cast(str, row["candidate_id"])
            for row in leaf_candidates
            if row.get("state") in {"accepted", "newly_free"}
        ]
        actual_excluded_ids = [
            cast(str, row["candidate_id"])
            for row in leaf_candidates
            if row.get("state") == "excluded"
        ]
        validate_rest_terminal_subset_promotion_commitment(
            promotion,
            snapshot_candidate_ids=tuple(
                cast(str, row["candidate_id"]) for row in leaf_candidates
            ),
            snapshot_accepted_ids=actual_accepted_ids,
            snapshot_excluded_ids=actual_excluded_ids,
        )
        validate_rest_terminal_subset_promotion_snapshot_evidence(
            promotion,
            snapshot_candidates=leaf_candidates,
            snapshot_screened=leaf_screened,
            snapshot_exclusions=leaf_exclusions,
        )
        if set(actual_accepted_ids).union(actual_excluded_ids) != selected_set:
            raise FirecrawlScreeningIdentityError(
                f"REST promotion leaf {index} lacks exact outer terminal rows"
            )
    return len(promotion_leaves)


def validate_verified_snapshot_rest_terminal_subset_promotions(
    snapshot: Path,
    manifest: Mapping[str, object],
) -> int:
    """Validate promotion leaves against hash-bound rows from a verified snapshot.

    Direct downstream consumers do not have the union loader's buffered row
    objects.  This boundary rereads only the three terminal-authority files,
    checks their bytes against the already verified manifest, and applies the
    same recursive promotion validator before any acquisition planning begins.
    """

    stage_commitments_value = manifest.get("stage_commitments")
    if not isinstance(stage_commitments_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "snapshot stage commitments must be an object"
        )
    stage_commitments = cast(Mapping[str, object], stage_commitments_value)
    promotion_leaves: list[Mapping[str, object]] = []
    _collect_rest_terminal_subset_promotion_leaves(
        stage_commitments,
        label="verified snapshot",
        promotion_leaves=promotion_leaves,
    )
    if not promotion_leaves:
        return 0
    files_value = manifest.get("files")
    if not isinstance(files_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "verified snapshot lacks file commitments"
        )
    files = cast(Mapping[str, object], files_value)
    rows = {
        filename: _verified_rest_promotion_snapshot_rows(
            snapshot,
            filename=filename,
            commitment=files.get(filename),
        )
        for filename in (
            "candidates.jsonl",
            "screened-cases.jsonl",
            "exclusions.jsonl",
        )
    }
    return validate_rest_terminal_subset_promotions_in_snapshot(
        stage_commitments,
        snapshot_candidates=rows["candidates.jsonl"],
        snapshot_screened=rows["screened-cases.jsonl"],
        snapshot_exclusions=rows["exclusions.jsonl"],
    )


def _verified_rest_promotion_snapshot_rows(
    snapshot: Path,
    *,
    filename: str,
    commitment: object,
) -> tuple[dict[str, object], ...]:
    if not isinstance(commitment, Mapping):
        raise FirecrawlScreeningIdentityError(
            f"verified snapshot lacks {filename} commitment"
        )
    typed_commitment = cast(Mapping[str, object], commitment)
    expected_sha256 = typed_commitment.get("sha256")
    expected_byte_count = typed_commitment.get("byte_count")
    expected_row_count = typed_commitment.get("row_count")
    if (
        not isinstance(expected_sha256, str)
        or _SHA256.fullmatch(expected_sha256) is None
        or isinstance(expected_byte_count, bool)
        or not isinstance(expected_byte_count, int)
        or expected_byte_count < 0
        or isinstance(expected_row_count, bool)
        or not isinstance(expected_row_count, int)
        or expected_row_count < 0
    ):
        raise FirecrawlScreeningIdentityError(
            f"verified snapshot has invalid {filename} commitment"
        )
    path = snapshot / filename
    try:
        if path.is_symlink() or not path.is_file():
            raise FirecrawlScreeningIdentityError(
                f"verified snapshot {filename} is not a regular file"
            )
        payload = path.read_bytes()
    except OSError as exc:
        raise FirecrawlScreeningIdentityError(
            f"cannot read verified snapshot {filename}: {exc}"
        ) from exc
    if (
        hashlib.sha256(payload).hexdigest() != expected_sha256
        or len(payload) != expected_byte_count
        or payload.count(b"\n") != expected_row_count
    ):
        raise FirecrawlScreeningIdentityError(
            f"verified snapshot {filename} differs from its manifest"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise FirecrawlScreeningIdentityError(
            f"verified snapshot {filename} is not UTF-8"
        ) from exc
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise FirecrawlScreeningIdentityError(
                f"verified snapshot {filename} contains a blank row"
            )
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FirecrawlScreeningIdentityError(
                f"verified snapshot {filename} has invalid JSON at line {line_number}"
            ) from exc
        if not isinstance(value, dict) or not all(
            isinstance(key, str) for key in cast(dict[object, object], value)
        ):
            raise FirecrawlScreeningIdentityError(
                f"verified snapshot {filename} line {line_number} is not an object"
            )
        records.append(cast(dict[str, object], value))
    if len(records) != expected_row_count:
        raise FirecrawlScreeningIdentityError(
            f"verified snapshot {filename} row count differs from its manifest"
        )
    return tuple(records)


def _collect_rest_terminal_subset_promotion_leaves(
    stage_commitments: Mapping[str, object],
    *,
    label: str,
    promotion_leaves: list[Mapping[str, object]],
) -> None:
    promotion_value = stage_commitments.get(REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY)
    union_value = stage_commitments.get(SCREENING_SNAPSHOT_UNION_STAGE_KEY)
    if promotion_value is not None and union_value is not None:
        raise FirecrawlScreeningIdentityError(
            f"{label} mixes REST promotion and union stage commitments"
        )
    if promotion_value is not None:
        if not isinstance(promotion_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} REST promotion commitment must be an object"
            )
        promotion_leaves.append(cast(Mapping[str, object], promotion_value))
        return
    if union_value is None:
        return
    if not isinstance(union_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            f"{label} screening snapshot union commitment must be an object"
        )
    union = cast(Mapping[str, object], union_value)
    if union.get("schema_version") != SCREENING_SNAPSHOT_UNION_INPUTS_SCHEMA:
        raise FirecrawlScreeningIdentityError(
            f"{label} screening snapshot union schema is not identity-aware v2"
        )
    sources = union.get("sources")
    if not isinstance(sources, list):
        raise FirecrawlScreeningIdentityError(
            f"{label} screening snapshot union sources must be an array"
        )
    for index, source_value in enumerate(cast(list[object], sources), start=1):
        if not isinstance(source_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} union source {index} must be an object"
            )
        nested = cast(Mapping[str, object], source_value).get("stage_commitments")
        if not isinstance(nested, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} union source {index} lacks stage commitments"
            )
        _collect_rest_terminal_subset_promotion_leaves(
            cast(Mapping[str, object], nested),
            label=f"{label} union source {index}",
            promotion_leaves=promotion_leaves,
        )


def _rest_rows_by_candidate_id(
    rows: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise FirecrawlScreeningIdentityError(
                f"{label} contains a missing candidate ID"
            )
        if candidate_id in by_id:
            raise FirecrawlScreeningIdentityError(
                f"{label} contains duplicate candidate ID: {candidate_id}"
            )
        by_id[candidate_id] = dict(row)
    return by_id


def _validate_rest_priority_selection_policy(
    value: object, *, eligibility_anchor_date: str
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "REST priority selection policy must be an object"
        )
    policy = cast(Mapping[str, object], value)
    if set(policy) != set(_REST_SELECTION_POLICY_FIELDS):
        raise FirecrawlScreeningIdentityError(
            "REST priority selection policy has unexpected fields"
        )
    exact_values: Mapping[str, object] = {
        "schema_version": REST_PRIORITY_SELECTION_POLICY_SCHEMA,
        "approved": True,
        "cohort_shape": "convenience_acquisition_shaped_nonrepresentative",
        "benchmark_claim_scope": "relative_model_performance_only",
        "selection_purpose": "cheapest_clean_cases_for_timely_cycle",
        "representative_sample_claimed": False,
        "acquisition_only": True,
        "model_visible": False,
        "outcome_polarity_blind": True,
        "outcome_polarity_used": False,
        "stage_b_labels_used": False,
        "model_outputs_used": False,
        "strict_screen_is_sole_eligibility_and_exclusion_authority": True,
        "ranking_metadata_visibility": "acquisition_only_never_packet_visible",
        "eligibility_anchor_date": eligibility_anchor_date,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "model_activity_requested": False,
        "model_activity_executed": False,
    }
    if any(policy.get(field) != expected for field, expected in exact_values.items()):
        raise FirecrawlScreeningIdentityError(
            "REST priority selection policy semantics are invalid"
        )
    for field in ("approval_reference", "approved_by"):
        _rest_required_text(policy, field)
    return {field: policy[field] for field in sorted(_REST_SELECTION_POLICY_FIELDS)}


def _rest_candidate_ids(value: object, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FirecrawlScreeningIdentityError(f"{label} must be an array")
    normalized = list(cast(Sequence[object], value))
    if not all(isinstance(item, str) and item.strip() for item in normalized) or len(
        normalized
    ) != len(set(cast(list[str], normalized))):
        raise FirecrawlScreeningIdentityError(
            f"{label} must contain unique nonempty strings"
        )
    return [cast(str, item) for item in normalized]


def _rest_required_text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FirecrawlScreeningIdentityError(
            f"REST promotion {field} must be nonempty text"
        )
    return value


def _rest_sha256(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise FirecrawlScreeningIdentityError(
            f"REST promotion {field} must be a lowercase SHA-256"
        )
    return value


def firecrawl_screening_implementation(
    *, source_root: Path | None = None
) -> dict[str, object]:
    """Return the current exact 21-file implementation commitment."""

    root = (
        Path(__file__).resolve().parents[2]
        if source_root is None
        else source_root.resolve()
    )
    source_sha256: dict[str, str] = {}
    for relative_path in FIRECRAWL_SCREENING_SOURCE_PATHS:
        path = root / relative_path
        if path.is_symlink() or not path.is_file():
            raise FirecrawlScreeningIdentityError(
                f"Firecrawl screening source is missing or unsafe: {relative_path}"
            )
        source_sha256[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": source_sha256,
        "manifest_sha256": source_manifest_sha256(source_sha256),
    }


def screening_union_policy_rebind_implementation(
    *, source_root: Path | None = None
) -> dict[str, object]:
    """Return the exact implementation commitment for the policy rebind."""

    root = (
        Path(__file__).resolve().parents[2]
        if source_root is None
        else source_root.resolve()
    )
    source_sha256: dict[str, str] = {}
    for relative_path in SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS:
        path = root / relative_path
        if path.is_symlink() or not path.is_file():
            raise FirecrawlScreeningIdentityError(
                "screening-union policy-rebind source is missing or unsafe: "
                f"{relative_path}"
            )
        source_sha256[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA,
        "source_sha256": source_sha256,
        "manifest_sha256": _ordered_source_manifest_sha256(
            source_sha256,
            ordered_paths=SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS,
        ),
    }


def validate_screening_union_policy_rebind_implementation(
    commitment: object,
    *,
    require_current: bool,
) -> dict[str, object]:
    """Validate the closed policy-rebind implementation commitment."""

    if not isinstance(commitment, Mapping):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind implementation must be an object"
        )
    typed = cast(Mapping[str, object], commitment)
    if set(typed) != {"schema_version", "source_sha256", "manifest_sha256"}:
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind implementation has unexpected fields"
        )
    if (
        typed.get("schema_version")
        != SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA
    ):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind implementation schema mismatch"
        )
    source_value = typed.get("source_sha256")
    if not isinstance(source_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind source commitment must be an object"
        )
    source_mapping = cast(Mapping[object, object], source_value)
    if set(source_mapping) != set(SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind source key set changed"
        )
    normalized_sources: dict[str, str] = {}
    for path in SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS:
        digest = source_mapping.get(path)
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise FirecrawlScreeningIdentityError(
                f"screening-union policy-rebind source SHA-256 is malformed: {path}"
            )
        normalized_sources[path] = digest
    manifest_sha256 = typed.get("manifest_sha256")
    if (
        not isinstance(manifest_sha256, str)
        or _SHA256.fullmatch(manifest_sha256) is None
        or _ordered_source_manifest_sha256(
            normalized_sources,
            ordered_paths=SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS,
        )
        != manifest_sha256
    ):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind source manifest commitment mismatch"
        )
    normalized: dict[str, object] = {
        "schema_version": SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA,
        "source_sha256": normalized_sources,
        "manifest_sha256": manifest_sha256,
    }
    if require_current and _canonical_commitment(normalized) != _canonical_commitment(
        screening_union_policy_rebind_implementation()
    ):
        raise FirecrawlScreeningIdentityError(
            "screening-union policy-rebind sources do not match current code"
        )
    return normalized


def _ordered_source_manifest_sha256(
    source_sha256: Mapping[str, str], *, ordered_paths: tuple[str, ...]
) -> str:
    payload = b"".join(
        f"{path}\0{source_sha256[path]}\n".encode() for path in ordered_paths
    )
    return hashlib.sha256(payload).hexdigest()


def source_manifest_sha256(source_sha256: Mapping[str, str]) -> str:
    """Hash an exact ordered ``path\0sha256\n`` source manifest."""

    if set(source_sha256) == set(FIRECRAWL_SCREENING_SOURCE_PATHS):
        ordered_paths = FIRECRAWL_SCREENING_SOURCE_PATHS
    elif set(source_sha256) == set(LEGACY_32057DE_SOURCE_SHA256):
        ordered_paths = tuple(
            path
            for path in FIRECRAWL_SCREENING_SOURCE_PATHS
            if path in LEGACY_32057DE_SOURCE_SHA256
        )
    else:
        ordered_paths = tuple(source_sha256)
    payload = b"".join(
        f"{path}\0{source_sha256[path]}\n".encode() for path in ordered_paths
    )
    return hashlib.sha256(payload).hexdigest()


def validate_firecrawl_screening_implementation(
    commitment: object,
    *,
    require_current: bool,
) -> dict[str, object]:
    """Validate exact shape/digest and optionally current source equality."""

    if not isinstance(commitment, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation commitment must be an object"
        )
    typed = cast(Mapping[str, object], commitment)
    if set(typed) != {"schema_version", "source_sha256", "manifest_sha256"}:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation commitment has unexpected fields"
        )
    if typed.get("schema_version") != FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation schema mismatch"
        )
    source_value = typed.get("source_sha256")
    if not isinstance(source_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source commitment must be an object"
        )
    source_mapping = cast(Mapping[object, object], source_value)
    if set(source_mapping) != set(FIRECRAWL_SCREENING_SOURCE_PATHS):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source key set changed"
        )
    normalized_sources: dict[str, str] = {}
    for path, digest in source_mapping.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise FirecrawlScreeningIdentityError(
                "Firecrawl screening source commitment is malformed"
            )
        if _SHA256.fullmatch(digest) is None:
            raise FirecrawlScreeningIdentityError(
                f"Firecrawl screening source SHA-256 is malformed: {path}"
            )
        normalized_sources[path] = digest
    manifest_sha256 = typed.get("manifest_sha256")
    if (
        not isinstance(manifest_sha256, str)
        or _SHA256.fullmatch(manifest_sha256) is None
    ):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source manifest SHA-256 is malformed"
        )
    if source_manifest_sha256(normalized_sources) != manifest_sha256:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source manifest commitment mismatch"
        )
    normalized: dict[str, object] = {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": {
            path: normalized_sources[path] for path in FIRECRAWL_SCREENING_SOURCE_PATHS
        },
        "manifest_sha256": manifest_sha256,
    }
    compatible_previous = tuple(
        {
            "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
            "source_sha256": {
                path: source_sha256[path] for path in FIRECRAWL_SCREENING_SOURCE_PATHS
            },
            "manifest_sha256": manifest_sha256,
        }
        for source_sha256, manifest_sha256 in (
            (
                COMPATIBLE_4D3BA85_SOURCE_SHA256,
                COMPATIBLE_4D3BA85_SOURCE_MANIFEST_SHA256,
            ),
            (
                COMPATIBLE_FINAL_V3_SOURCE_SHA256,
                COMPATIBLE_FINAL_V3_SOURCE_MANIFEST_SHA256,
            ),
        )
    )
    if require_current and _canonical_commitment(normalized) not in {
        # Use canonical JSON because nested dictionaries are not hashable.
        _canonical_commitment(firecrawl_screening_implementation()),
        *(_canonical_commitment(item) for item in compatible_previous),
    }:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening sources do not match the committed implementation"
        )
    return normalized


def _canonical_commitment(commitment: Mapping[str, object]) -> str:
    return json.dumps(commitment, sort_keys=True, separators=(",", ":"))


def require_snapshot_firecrawl_screening_implementation(
    manifest: Mapping[str, object], *, require_current: bool
) -> dict[str, object]:
    """Extract and validate the required stage commitment from a snapshot."""

    stage_commitments = manifest.get("stage_commitments")
    if not isinstance(stage_commitments, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl snapshot lacks stage commitments"
        )
    commitment = cast(Mapping[str, object], stage_commitments).get(
        FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY
    )
    if commitment is None:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl snapshot lacks firecrawl_screening_implementation"
        )
    return validate_firecrawl_screening_implementation(
        commitment, require_current=require_current
    )


def snapshot_firecrawl_screening_source_count(
    manifest: Mapping[str, object], *, require_current: bool
) -> int:
    """Return authenticated Firecrawl source leaves contributing to a snapshot."""

    stage_commitments = manifest.get("stage_commitments")
    if stage_commitments is None:
        raise FirecrawlScreeningIdentityError(
            "snapshot lacks affirmative stage commitments"
        )
    if not isinstance(stage_commitments, Mapping):
        raise FirecrawlScreeningIdentityError(
            "snapshot stage commitments must be an object"
        )
    if not stage_commitments:
        raise FirecrawlScreeningIdentityError(
            "snapshot lacks affirmative stage commitments"
        )
    return _stage_firecrawl_screening_source_count(
        cast(Mapping[str, object], stage_commitments),
        require_current=require_current,
        label="snapshot",
    )


def _stage_firecrawl_screening_source_count(
    stage_commitments: Mapping[str, object],
    *,
    require_current: bool,
    label: str,
) -> int:
    rebind_value = stage_commitments.get(SCREENING_UNION_POLICY_REBIND_STAGE_KEY)
    if rebind_value is not None:
        if not isinstance(rebind_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening-union policy rebind must be an object"
            )
        rebind = cast(Mapping[str, object], rebind_value)
        validate_screening_union_policy_rebind_implementation(
            rebind.get("implementation"),
            require_current=require_current,
        )
    direct_keys = FIRECRAWL_SCREENING_DIRECT_STAGE_KEYS.intersection(stage_commitments)
    union_present = SCREENING_SNAPSHOT_UNION_STAGE_KEY in stage_commitments
    union_value = stage_commitments.get(SCREENING_SNAPSHOT_UNION_STAGE_KEY)
    implementation = stage_commitments.get(FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY)
    if union_present:
        if direct_keys:
            raise FirecrawlScreeningIdentityError(
                f"{label} mixes direct Firecrawl and union stage commitments"
            )
        if not isinstance(union_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union commitment must be an object"
            )
        union = cast(Mapping[str, object], union_value)
        if union.get("schema_version") != SCREENING_SNAPSHOT_UNION_INPUTS_SCHEMA:
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union schema is not identity-aware v2"
            )
        source_count = union.get("source_count")
        sources = union.get("sources")
        firecrawl_source_count = union.get("firecrawl_screening_source_count")
        if not isinstance(sources, list):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union lacks an exact Firecrawl count"
            )
        typed_sources = cast(list[object], sources)
        if (
            not isinstance(source_count, int)
            or isinstance(source_count, bool)
            or source_count < 2
            or len(typed_sources) != source_count
            or not isinstance(firecrawl_source_count, int)
            or isinstance(firecrawl_source_count, bool)
            or firecrawl_source_count < 0
        ):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union lacks an exact Firecrawl count"
            )
        computed_count = 0
        for index, source_value in enumerate(typed_sources, start=1):
            if not isinstance(source_value, Mapping):
                raise FirecrawlScreeningIdentityError(
                    f"{label} union source {index} must be an object"
                )
            source = cast(Mapping[str, object], source_value)
            nested_stage_commitments = source.get("stage_commitments")
            if not isinstance(nested_stage_commitments, Mapping):
                raise FirecrawlScreeningIdentityError(
                    f"{label} union source {index} lacks stage commitments"
                )
            computed_count += _stage_firecrawl_screening_source_count(
                cast(Mapping[str, object], nested_stage_commitments),
                require_current=require_current,
                label=f"{label} union source {index}",
            )
        if computed_count != firecrawl_source_count:
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union Firecrawl count mismatch"
            )
        if firecrawl_source_count:
            if implementation is None:
                raise FirecrawlScreeningIdentityError(
                    f"{label} lacks firecrawl_screening_implementation"
                )
            validate_firecrawl_screening_implementation(
                implementation,
                require_current=require_current,
            )
        elif implementation is not None:
            raise FirecrawlScreeningIdentityError(
                f"{label} REST-only union has a Firecrawl implementation commitment"
            )
        return firecrawl_source_count
    if direct_keys:
        if len(direct_keys) != 1:
            raise FirecrawlScreeningIdentityError(
                f"{label} has ambiguous direct Firecrawl stage commitments"
            )
        if implementation is None:
            raise FirecrawlScreeningIdentityError(
                f"{label} lacks firecrawl_screening_implementation"
            )
        validate_firecrawl_screening_implementation(
            implementation,
            require_current=require_current,
        )
        return 1
    if implementation is not None:
        raise FirecrawlScreeningIdentityError(
            f"{label} has an orphan Firecrawl implementation commitment"
        )
    source_neutral_keys = SOURCE_NEUTRAL_DIRECT_STAGE_KEYS.intersection(
        stage_commitments
    )
    for source_neutral_key in source_neutral_keys:
        source_neutral_value = stage_commitments[source_neutral_key]
        if not isinstance(source_neutral_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} source-neutral commitment must be an object: "
                f"{source_neutral_key}"
            )
        if source_neutral_key == REST_TERMINAL_SUBSET_PROMOTION_STAGE_KEY:
            promotion = cast(Mapping[str, object], source_neutral_value)
            validate_rest_terminal_subset_promotion_commitment(
                promotion,
                snapshot_candidate_ids=_rest_candidate_ids(
                    promotion.get("selected_candidate_ids"),
                    f"{label} REST promotion selected candidate IDs",
                ),
                snapshot_accepted_ids=_rest_candidate_ids(
                    promotion.get("accepted_candidate_ids"),
                    f"{label} REST promotion accepted candidate IDs",
                ),
                snapshot_excluded_ids=_rest_candidate_ids(
                    promotion.get("excluded_candidate_ids"),
                    f"{label} REST promotion excluded candidate IDs",
                ),
            )
    named_stage = stage_commitments.get("stage")
    recognized_named_stage = (
        isinstance(named_stage, str) and named_stage in SOURCE_NEUTRAL_NAMED_STAGES
    )
    source_neutral_form_count = len(source_neutral_keys) + int(recognized_named_stage)
    if source_neutral_form_count == 0:
        raise FirecrawlScreeningIdentityError(
            f"{label} lacks recognized source-neutral lineage"
        )
    if source_neutral_form_count != 1:
        raise FirecrawlScreeningIdentityError(
            f"{label} has ambiguous source-neutral lineage"
        )
    return 0

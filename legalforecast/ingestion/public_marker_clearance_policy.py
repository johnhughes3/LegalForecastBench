"""Closed owner policy for provider-free public-marker clearance."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.cohort_policy import (
    CohortPolicyError,
    verify_cohort_policy,
)

SCHEMA_VERSION = "legalforecast.disclosure_public_marker_policy.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_POLICY_FIELDS = {
    "cycle_id",
    "cohort_policy_sha256",
    "source_scope",
    "eligible_route_reasons",
    "required_scan_coverage",
    "require_zero_unscanned_pages",
    "require_valid_visibility",
    "markers_are_diagnostic_only",
    "model_review_required",
    "positive_restriction_action",
    "unproven_public_action",
    "incomplete_scan_action",
    "visibility_contradiction_action",
}
_FIXED_POLICY = {
    "source_scope": "verifier_issued_recovered_courtlistener_public",
    "eligible_route_reasons": ["automated_marker_present"],
    "required_scan_coverage": "complete",
    "require_zero_unscanned_pages": True,
    "require_valid_visibility": True,
    "markers_are_diagnostic_only": True,
    "model_review_required": False,
    "positive_restriction_action": "quarantine",
    "unproven_public_action": "quarantine",
    "incomplete_scan_action": "quarantine",
    "visibility_contradiction_action": "quarantine",
}


class PublicMarkerClearancePolicyError(ValueError):
    """Raised when public-marker clearance policy is malformed or unbound."""


@dataclass(frozen=True, slots=True)
class PublicMarkerClearancePolicy:
    """Verified immutable owner policy bound to one cohort policy."""

    cycle_id: str
    cohort_policy_sha256: str
    policy_sha256: str
    eligible_route_reasons: tuple[str, ...]
    markers_are_diagnostic_only: bool


def generate_public_marker_clearance_policy(
    *, cycle_id: str, cohort_policy_sha256: str
) -> dict[str, object]:
    """Generate the closed policy artifact for one exact cohort."""

    normalized_cycle = _text(cycle_id, "cycle_id")
    normalized_cohort = _digest(cohort_policy_sha256, "cohort_policy_sha256")
    policy: dict[str, object] = {
        "cycle_id": normalized_cycle,
        "cohort_policy_sha256": normalized_cohort,
        **_FIXED_POLICY,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "policy": policy,
        "policy_sha256": _sha256(policy),
    }


def verify_public_marker_clearance_policy(
    artifact: Mapping[str, object],
    *,
    cohort_policy_artifact: Mapping[str, Any],
) -> PublicMarkerClearancePolicy:
    """Verify exact semantics and bind them to the supplied cohort policy."""

    if set(artifact) != {"schema_version", "policy", "policy_sha256"}:
        raise PublicMarkerClearancePolicyError(
            "public-marker policy artifact fields are invalid"
        )
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise PublicMarkerClearancePolicyError(
            "unsupported public-marker policy schema"
        )
    raw_policy = artifact.get("policy")
    if not isinstance(raw_policy, Mapping):
        raise PublicMarkerClearancePolicyError("public-marker policy must be an object")
    policy = cast(Mapping[str, object], raw_policy)
    if set(policy) != _POLICY_FIELDS:
        raise PublicMarkerClearancePolicyError(
            "public-marker policy fields are invalid"
        )
    for field, expected in _FIXED_POLICY.items():
        if policy.get(field) != expected:
            raise PublicMarkerClearancePolicyError(
                "public-marker policy fields are invalid"
            )
    cycle_id = _text(policy.get("cycle_id"), "cycle_id")
    cohort_sha256 = _digest(policy.get("cohort_policy_sha256"), "cohort_policy_sha256")
    committed = _digest(artifact.get("policy_sha256"), "policy_sha256")
    actual = _sha256(policy)
    if committed != actual:
        raise PublicMarkerClearancePolicyError(
            "public-marker policy hash does not match its content"
        )
    try:
        verified_cohort_sha256 = verify_cohort_policy(cohort_policy_artifact)
    except CohortPolicyError as exc:
        raise PublicMarkerClearancePolicyError(str(exc)) from exc
    raw_cohort_policy = cohort_policy_artifact.get("policy")
    cohort_cycle_id = (
        cast(Mapping[str, object], raw_cohort_policy).get("cycle_id")
        if isinstance(raw_cohort_policy, Mapping)
        else None
    )
    if cycle_id != cohort_cycle_id:
        raise PublicMarkerClearancePolicyError(
            "public-marker policy cycle differs from cohort policy"
        )
    if cohort_sha256 != verified_cohort_sha256:
        raise PublicMarkerClearancePolicyError(
            "public-marker policy cohort hash differs from cohort policy"
        )
    return PublicMarkerClearancePolicy(
        cycle_id=cycle_id,
        cohort_policy_sha256=cohort_sha256,
        policy_sha256=actual,
        eligible_route_reasons=("automated_marker_present",),
        markers_are_diagnostic_only=True,
    )


def _canonical_json_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=PublicMarkerClearancePolicyError,
        error_message="public-marker policy is not canonical JSON",
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PublicMarkerClearancePolicyError(f"{label} must be non-empty text")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PublicMarkerClearancePolicyError(f"{label} must be a SHA-256 digest")
    return value


__all__ = [
    "SCHEMA_VERSION",
    "PublicMarkerClearancePolicy",
    "PublicMarkerClearancePolicyError",
    "generate_public_marker_clearance_policy",
    "verify_public_marker_clearance_policy",
]

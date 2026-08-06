from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from legalforecast.ingestion.public_marker_clearance_policy import (
    PublicMarkerClearancePolicyError,
    generate_public_marker_clearance_policy,
    verify_public_marker_clearance_policy,
)


def _cohort_policy() -> dict[str, object]:
    return {
        "schema_version": "legalforecast.cohort_policy.v1",
        "policy": {
            "cycle_id": "cycle-1-target-100-2026-07-25",
        },
        "policy_sha256": "7" * 64,
    }


def test_public_marker_policy_is_closed_and_cohort_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "legalforecast.ingestion.public_marker_clearance_policy.verify_cohort_policy",
        lambda _artifact: "7" * 64,
    )
    artifact = generate_public_marker_clearance_policy(
        cycle_id="cycle-1-target-100-2026-07-25",
        cohort_policy_sha256="7" * 64,
    )

    policy = verify_public_marker_clearance_policy(
        artifact,
        cohort_policy_artifact=_cohort_policy(),
    )

    assert policy.cycle_id == "cycle-1-target-100-2026-07-25"
    assert policy.cohort_policy_sha256 == "7" * 64
    assert policy.markers_are_diagnostic_only is True
    assert policy.eligible_route_reasons == ("automated_marker_present",)

    changed = deepcopy(artifact)
    changed["policy"]["positive_restriction_action"] = "clear"  # type: ignore[index]
    with pytest.raises(PublicMarkerClearancePolicyError, match="policy fields"):
        verify_public_marker_clearance_policy(
            changed,
            cohort_policy_artifact=_cohort_policy(),
        )


def test_generated_policy_cannot_mutate_closed_baseline() -> None:
    first = generate_public_marker_clearance_policy(
        cycle_id="cycle-1-target-100-2026-07-25",
        cohort_policy_sha256="7" * 64,
    )
    first_policy = first["policy"]
    assert isinstance(first_policy, dict)
    reasons = first_policy["eligible_route_reasons"]
    assert isinstance(reasons, list)
    reasons.append("changed-by-caller")

    later = generate_public_marker_clearance_policy(
        cycle_id="cycle-1-target-100-2026-07-25",
        cohort_policy_sha256="7" * 64,
    )
    later_policy = later["policy"]
    assert isinstance(later_policy, dict)
    assert later_policy["eligible_route_reasons"] == ["automated_marker_present"]


def test_public_marker_policy_rejects_hash_and_cohort_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "legalforecast.ingestion.public_marker_clearance_policy.verify_cohort_policy",
        lambda _artifact: "7" * 64,
    )
    artifact = generate_public_marker_clearance_policy(
        cycle_id="cycle-1-target-100-2026-07-25",
        cohort_policy_sha256="7" * 64,
    )
    changed_hash = deepcopy(artifact)
    changed_hash["policy_sha256"] = "8" * 64
    with pytest.raises(PublicMarkerClearancePolicyError, match="hash"):
        verify_public_marker_clearance_policy(
            changed_hash,
            cohort_policy_artifact=_cohort_policy(),
        )

    changed_cycle = generate_public_marker_clearance_policy(
        cycle_id="other-cycle",
        cohort_policy_sha256="7" * 64,
    )
    with pytest.raises(PublicMarkerClearancePolicyError, match="cycle"):
        verify_public_marker_clearance_policy(
            changed_cycle,
            cohort_policy_artifact=_cohort_policy(),
        )


def test_cycle_1_public_marker_policy_is_bound_to_checked_in_cohort() -> None:
    root = Path(__file__).resolve().parents[1]
    policy_artifact = json.loads(
        (
            root / "docs/disclosure-public-marker-policy-cycle-1-2026-08-06.json"
        ).read_bytes()
    )
    cohort_artifact = json.loads(
        (root / "docs/cohort-policy-cycle-1-target-100-2026-07-25.json").read_bytes()
    )

    policy = verify_public_marker_clearance_policy(
        policy_artifact,
        cohort_policy_artifact=cohort_artifact,
    )

    assert policy.policy_sha256 == (
        "a8847909788cdaea64a30c5a7e8e7da41f655568049be1e09cb2703611425f41"
    )

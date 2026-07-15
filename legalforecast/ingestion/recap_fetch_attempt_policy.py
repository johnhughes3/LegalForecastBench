"""Immutable authority for bounded unknown-status RECAP Fetch attempts.

The artifact created here authorizes spend only. It never establishes that a
document is public, and every authorized document must remain quarantined until
post-recovery lineage and disclosure clearance are independently verified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicyError,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.missing_core_budget import MissingCoreBudgetPlan
from legalforecast.ingestion.recap_fetch_broker_policy import (
    COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE,
    RecapFetchBrokerPolicyError,
    validate_recap_fetch_budget_plan_artifact,
)

RECAP_FETCH_ATTEMPT_POLICY_VERSION = "legalforecast.recap_fetch_attempt_policy.v1"
BOUNDED_FETCH_ATTEMPT_AUTHORITY = "bounded_fetch_attempt_only"
UNKNOWN_STATUS_EVIDENCE = [
    "courtlistener_rest_docket_exact_match",
    "courtlistener_rest_docket_entry_exact_match",
    "courtlistener_rest_recap_document_exact_match",
    "courtlistener_rest_recap_document_is_available_false",
    "courtlistener_rest_recap_document_seal_status_unknown",
    "courtlistener_rest_no_positive_restriction_marker",
]

_DOCUMENT_ID = re.compile(r"[1-9][0-9]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class RecapFetchAttemptPolicyError(ValueError):
    """Raised when unknown-status evidence cannot grant attempt authority."""


def generate_recap_fetch_attempt_policy(
    *,
    purchase_policy_artifact: Mapping[str, object],
    cohort_policy_artifact: Mapping[str, Any],
    budget_plan: MissingCoreBudgetPlan,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Bind the unknown subset of one executable plan to exact source rows."""

    try:
        purchase_policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy, cohort_policy_artifact
        )
        validate_recap_fetch_budget_plan_artifact(
            budget_plan_artifact,
            budget_plan=budget_plan,
            reservation_usd=purchase_policy.per_document_reservation_usd,
            hard_cap_usd=purchase_policy.hard_cap_usd,
            opening_committed_spend_usd=purchase_policy.opening_committed_spend_usd,
            opening_case_committed_spend_usd=(
                purchase_policy.opening_case_committed_spend_usd
            ),
            per_case_cap_usd=purchase_policy.max_per_case_usd,
            broad_frontier_allowlist=False,
        )
    except (CaseDevPurchasePolicyError, RecapFetchBrokerPolicyError) as exc:
        raise RecapFetchAttemptPolicyError(str(exc)) from exc
    if budget_plan.dry_run:
        raise RecapFetchAttemptPolicyError(
            "attempt policy requires an executable non-dry-run budget plan"
        )

    selection = _selection_index(selection_records)
    allowed: list[dict[str, str]] = []
    seen_documents: set[str] = set()
    for case_plan in budget_plan.case_plans:
        candidate_id = _canonical_text(case_plan.candidate_id, "candidate_id")
        documents = selection.get(candidate_id)
        if documents is None:
            raise RecapFetchAttemptPolicyError(
                f"missing selection metadata for candidate {candidate_id}"
            )
        for raw_document_id in case_plan.purchase_document_ids:
            document_id = _canonical_document_id(raw_document_id)
            if document_id in seen_documents:
                raise RecapFetchAttemptPolicyError(
                    "planned RECAP document IDs must be globally unique"
                )
            seen_documents.add(document_id)
            document = documents.get(document_id)
            if document is None:
                raise RecapFetchAttemptPolicyError(
                    f"missing selected document {candidate_id}/{document_id}"
                )
            if _is_explicit_unknown_attempt_candidate(document):
                allowed.append(
                    {
                        "case_id": candidate_id,
                        "recap_document": document_id,
                        "evidence_class": "unknown_status_quarantine",
                        "selection_document_sha256": _sha256(document),
                    }
                )

    if not allowed:
        raise RecapFetchAttemptPolicyError(
            "attempt policy requires at least one exact unknown-status document"
        )
    allowed.sort(key=lambda row: (row["case_id"], int(row["recap_document"])))
    policy: dict[str, object] = {
        "authority": BOUNDED_FETCH_ATTEMPT_AUTHORITY,
        "cycle_id": purchase_policy.cycle_id,
        "purchase_policy_sha256": purchase_policy.policy_sha256,
        "cohort_policy_sha256": purchase_policy.cohort_policy_sha256,
        "budget_plan_sha256": _sha256(budget_plan_artifact),
        "selection_sha256": _sha256(_canonical_records(selection_records)),
        "cycle_cap_usd": f"{purchase_policy.hard_cap_usd:.2f}",
        "per_case_cap_usd": f"{purchase_policy.max_per_case_usd:.2f}",
        "reservation_usd": f"{purchase_policy.per_document_reservation_usd:.2f}",
        "opening_committed_spend_usd": (
            f"{purchase_policy.opening_committed_spend_usd:.2f}"
        ),
        "planned_reserved_usd": f"{budget_plan.total_estimated_cost:.2f}",
        "allowed_documents": allowed,
    }
    return {
        "schema_version": RECAP_FETCH_ATTEMPT_POLICY_VERSION,
        "policy": policy,
        "policy_sha256": _sha256(policy),
    }


def verify_recap_fetch_attempt_policy(
    artifact: Mapping[str, object],
    *,
    purchase_policy_artifact: Mapping[str, object],
    cohort_policy_artifact: Mapping[str, Any],
    budget_plan: MissingCoreBudgetPlan,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, str]]:
    """Recompute an attempt policy and return document-to-case authority."""

    expected = generate_recap_fetch_attempt_policy(
        purchase_policy_artifact=purchase_policy_artifact,
        cohort_policy_artifact=cohort_policy_artifact,
        budget_plan=budget_plan,
        budget_plan_artifact=budget_plan_artifact,
        selection_records=selection_records,
    )
    if dict(artifact) != expected:
        raise RecapFetchAttemptPolicyError(
            "attempt policy does not match its immutable source inputs"
        )
    policy = cast(Mapping[str, object], expected["policy"])
    documents = cast(Sequence[Mapping[str, str]], policy["allowed_documents"])
    return {
        row["recap_document"]: {
            "case_id": row["case_id"],
            "selection_document_sha256": row["selection_document_sha256"],
        }
        for row in documents
    }


def write_recap_fetch_attempt_policy(
    path: str | Path, artifact: Mapping[str, object]
) -> Path:
    """Atomically publish a verified-shape artifact without replacing bytes."""

    _verify_shape(artifact)
    target = Path(path)
    payload = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise RecapFetchAttemptPolicyError("attempt policy output is a symlink")
    if target.exists():
        metadata = target.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RecapFetchAttemptPolicyError(
                "attempt policy output must be a singly linked regular file"
            )
        if target.read_bytes() != payload:
            raise RecapFetchAttemptPolicyError(
                "refusing to overwrite a different attempt policy"
            )
        return target
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise RecapFetchAttemptPolicyError(
                "attempt policy was concurrently created with different content"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _selection_index(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    output: dict[str, dict[str, Mapping[str, Any]]] = {}
    for record in records:
        candidate_id = _canonical_text(record.get("candidate_id"), "candidate_id")
        if candidate_id in output:
            raise RecapFetchAttemptPolicyError("selection candidates must be unique")
        if record.get("selected") is not True or record.get("exclusion_reasons") != []:
            raise RecapFetchAttemptPolicyError(
                f"selection for {candidate_id} is not included"
            )
        raw_documents = record.get("documents")
        if isinstance(raw_documents, (str, bytes)) or not isinstance(
            raw_documents, Sequence
        ):
            raise RecapFetchAttemptPolicyError("selection documents must be a list")
        documents: dict[str, Mapping[str, Any]] = {}
        for item in cast(Sequence[object], raw_documents):
            if not isinstance(item, Mapping):
                raise RecapFetchAttemptPolicyError(
                    "selected document must be an object"
                )
            document = cast(Mapping[str, Any], item)
            document_id = _canonical_document_id(document.get("source_document_id"))
            if document_id in documents:
                raise RecapFetchAttemptPolicyError(
                    "selected document IDs must be unique"
                )
            documents[document_id] = document
        output[candidate_id] = documents
    return output


def _is_explicit_unknown_attempt_candidate(document: Mapping[str, Any]) -> bool:
    if document.get("is_sealed") is True or document.get("is_private") is True:
        raise RecapFetchAttemptPolicyError(
            "restricted documents cannot receive attempt authority"
        )
    exact_unknown = (
        document.get("redaction_or_seal_status") == "unknown"
        and document.get("is_sealed") is None
        and document.get("is_private") is None
        and document.get("is_available") is False
        and document.get("availability_status") == "unavailable"
        and document.get("requires_paid_recovery") is True
        and document.get("restriction_evidence") == UNKNOWN_STATUS_EVIDENCE
    )
    incomplete_private_status = (
        document.get("redaction_or_seal_status") == "public"
        and document.get("is_sealed") is False
        and document.get("is_private") is None
        and document.get("availability_status") == "unavailable"
        and document.get("requires_paid_recovery") is True
        and document.get("restriction_evidence")
        == COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE
    )
    return exact_unknown or incomplete_private_status


def _verify_shape(artifact: Mapping[str, object]) -> None:
    if set(artifact) != {"schema_version", "policy", "policy_sha256"}:
        raise RecapFetchAttemptPolicyError("attempt policy fields are invalid")
    if artifact.get("schema_version") != RECAP_FETCH_ATTEMPT_POLICY_VERSION:
        raise RecapFetchAttemptPolicyError("attempt policy schema is invalid")
    policy = artifact.get("policy")
    if not isinstance(policy, Mapping) or artifact.get("policy_sha256") != _sha256(
        cast(Mapping[str, object], policy)
    ):
        raise RecapFetchAttemptPolicyError("attempt policy hash is invalid")


def _canonical_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(record) for record in records]


def _canonical_document_id(value: object) -> str:
    if not isinstance(value, str) or _DOCUMENT_ID.fullmatch(value) is None:
        raise RecapFetchAttemptPolicyError(
            "RECAP document IDs must be canonical positive integers"
        )
    return value


def _canonical_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RecapFetchAttemptPolicyError(f"{field} must be a canonical string")
    return value


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

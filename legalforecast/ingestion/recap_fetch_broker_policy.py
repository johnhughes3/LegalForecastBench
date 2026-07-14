"""Derive an immutable RECAP Fetch broker allowlist from executable artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicyError,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.missing_core_budget import MissingCoreBudgetPlan

RECAP_FETCH_BROKER_POLICY_VERSION = "courtlistener-recap-fetch-policy-v1"

_CANONICAL_RECAP_DOCUMENT_ID = re.compile(r"[1-9][0-9]*")
_CANONICAL_USD = re.compile(r"(0|[1-9][0-9]*)\.[0-9]{2}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_JAVASCRIPT_MAX_SAFE_CENTS = 9_007_199_254_740_991
CASE_DEV_PAID_RESTRICTION_EVIDENCE = [
    "courtlistener_docket_entry_checked",
    "case_dev_entry_and_document_checked",
]
COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE = [
    "courtlistener_rest_docket_exact_match",
    "courtlistener_rest_docket_entry_exact_match",
    "courtlistener_rest_recap_document_exact_match",
    "courtlistener_rest_recap_document_is_sealed_false",
]


class RecapFetchBrokerPolicyError(ValueError):
    """Raised when broker-policy inputs cannot prove a safe allowlist."""


def generate_recap_fetch_broker_policy(
    *,
    purchase_policy_artifact: Mapping[str, object],
    cohort_policy_artifact: Mapping[str, Any],
    budget_plan: MissingCoreBudgetPlan,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Build the exact broker policy accepted by secure-gate.

    The budget plan is the sole authority for which documents may be charged.
    Selection metadata can only prove that those planned documents are public;
    extra selection documents never expand the allowlist.
    """

    try:
        purchase_policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        verify_case_dev_purchase_policy_cohort_binding(
            purchase_policy,
            cohort_policy_artifact,
        )
    except CaseDevPurchasePolicyError as exc:
        raise RecapFetchBrokerPolicyError(str(exc)) from exc

    if budget_plan.dry_run:
        raise RecapFetchBrokerPolicyError(
            "broker policy requires an executable non-dry-run budget plan"
        )
    _validate_budget_plan_artifact(
        budget_plan_artifact,
        budget_plan=budget_plan,
        reservation_usd=purchase_policy.per_document_reservation_usd,
        hard_cap_usd=purchase_policy.hard_cap_usd,
        opening_committed_spend_usd=purchase_policy.opening_committed_spend_usd,
        opening_case_committed_spend_usd=(
            purchase_policy.opening_case_committed_spend_usd
        ),
        per_case_cap_usd=purchase_policy.max_per_case_usd,
    )
    if len(purchase_policy.cycle_id) > 128:
        raise RecapFetchBrokerPolicyError(
            "cycle_id exceeds the secure-gate 128-character limit"
        )
    for field, amount in (
        ("cycle_cap_usd", purchase_policy.hard_cap_usd),
        ("per_case_cap_usd", purchase_policy.max_per_case_usd),
        ("reservation_usd", purchase_policy.per_document_reservation_usd),
        (
            "opening_committed_spend_usd",
            purchase_policy.opening_committed_spend_usd,
        ),
    ):
        _require_javascript_safe_money(amount, field)

    selection = _index_selection(selection_records)
    allowed_documents: list[dict[str, str]] = []
    seen_candidates: set[str] = set()
    seen_documents: set[str] = set()
    derived_cases: set[str] = set()
    for case_plan in budget_plan.case_plans:
        candidate_id = _canonical_case_id(case_plan.candidate_id, "candidate_id")
        if candidate_id in seen_candidates:
            raise RecapFetchBrokerPolicyError(
                "executable case plan candidate IDs must be unique"
            )
        seen_candidates.add(candidate_id)
        if case_plan.dry_run:
            raise RecapFetchBrokerPolicyError(
                f"case plan {candidate_id} is marked dry-run"
            )
        if case_plan.exclusion_reasons:
            raise RecapFetchBrokerPolicyError(
                f"case plan {candidate_id} is excluded and cannot be allowlisted"
            )
        if case_plan.missing_core_document_count != len(
            case_plan.purchase_document_ids
        ):
            raise RecapFetchBrokerPolicyError(
                f"case plan {candidate_id} purchase count is inconsistent"
            )
        selected_documents = selection.get(candidate_id)
        if selected_documents is None:
            raise RecapFetchBrokerPolicyError(
                f"missing selection metadata for candidate {candidate_id}"
            )
        for document_id in case_plan.purchase_document_ids:
            canonical_document_id = _canonical_document_id(document_id)
            if canonical_document_id in seen_documents:
                raise RecapFetchBrokerPolicyError(
                    "planned RECAP document IDs must be unique across cases"
                )
            seen_documents.add(canonical_document_id)
            metadata = selected_documents.get(canonical_document_id)
            if metadata is None:
                raise RecapFetchBrokerPolicyError(
                    "missing public restriction metadata for planned RECAP "
                    f"document {canonical_document_id} in {candidate_id}"
                )
            _require_not_restricted(metadata, canonical_document_id)
            allowed_documents.append(
                {
                    "recap_document": canonical_document_id,
                    "case_id": candidate_id,
                }
            )
            derived_cases.add(candidate_id)

    if not allowed_documents:
        raise RecapFetchBrokerPolicyError("broker document allowlist must not be empty")

    opening_commitments = {
        case_id: f"{amount:.2f}"
        for case_id, amount in sorted(
            purchase_policy.opening_case_committed_spend_usd.items()
        )
    }
    absent_opening_cases = sorted(set(opening_commitments) - derived_cases)
    if absent_opening_cases:
        raise RecapFetchBrokerPolicyError(
            "opening commitment cases are absent from the derived allowlist: "
            + ", ".join(absent_opening_cases)
        )

    allowed_documents.sort(
        key=lambda document: (
            document["case_id"],
            int(document["recap_document"]),
        )
    )
    return {
        "version": RECAP_FETCH_BROKER_POLICY_VERSION,
        "cycle_id": purchase_policy.cycle_id,
        "purchase_policy_sha256": purchase_policy.policy_sha256,
        "cycle_cap_usd": f"{purchase_policy.hard_cap_usd:.2f}",
        "per_case_cap_usd": f"{purchase_policy.max_per_case_usd:.2f}",
        "reservation_usd": f"{purchase_policy.per_document_reservation_usd:.2f}",
        "opening_committed_spend_usd": (
            f"{purchase_policy.opening_committed_spend_usd:.2f}"
        ),
        "opening_case_committed_spend_usd": opening_commitments,
        "allowed_documents": allowed_documents,
    }


def broker_policy_sha256(policy: Mapping[str, object]) -> str:
    """Return secure-gate's canonical content digest for a broker policy."""

    return hashlib.sha256(_canonical_json(dict(policy)).encode("utf-8")).hexdigest()


def write_recap_fetch_broker_policy(
    path: str | Path,
    policy: Mapping[str, object],
) -> Path:
    """Atomically publish a deterministic policy and refuse byte changes."""

    _verify_generated_policy_shape(policy)
    target = Path(path)
    payload = (
        json.dumps(policy, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise RecapFetchBrokerPolicyError(
            "refusing a symlink RECAP Fetch broker policy output"
        )
    if target.exists():
        if not stat.S_ISREG(target.stat(follow_symlinks=False).st_mode):
            raise RecapFetchBrokerPolicyError(
                "existing RECAP Fetch broker policy output must be a regular file"
            )
        if target.read_bytes() != payload:
            raise RecapFetchBrokerPolicyError(
                "refusing to overwrite a different RECAP Fetch broker policy"
            )
        return target

    fd, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError:
        if target.is_symlink() or not stat.S_ISREG(
            target.stat(follow_symlinks=False).st_mode
        ):
            raise RecapFetchBrokerPolicyError(
                "concurrent RECAP Fetch broker policy output is not a regular file"
            ) from None
        if target.read_bytes() != payload:
            raise RecapFetchBrokerPolicyError(
                "RECAP Fetch broker policy was concurrently created with "
                "different content"
            ) from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _index_selection(
    selection_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    indexed: dict[str, dict[str, Mapping[str, Any]]] = {}
    for selection in selection_records:
        candidate_id = _canonical_case_id(
            selection.get("candidate_id"), "selection candidate_id"
        )
        if candidate_id in indexed:
            raise RecapFetchBrokerPolicyError("selection candidate IDs must be unique")
        if (
            selection.get("selected") is not True
            or selection.get("exclusion_reasons") != []
        ):
            raise RecapFetchBrokerPolicyError(
                f"selection for {candidate_id} is not a final included selection"
            )
        raw_documents = selection.get("documents")
        if not isinstance(raw_documents, Sequence) or isinstance(
            raw_documents, (str, bytes)
        ):
            raise RecapFetchBrokerPolicyError(
                f"selection documents for {candidate_id} must be a list"
            )
        documents: dict[str, Mapping[str, Any]] = {}
        for raw_document in cast(Sequence[object], raw_documents):
            if not isinstance(raw_document, Mapping):
                raise RecapFetchBrokerPolicyError(
                    f"selected document for {candidate_id} must be an object"
                )
            document = cast(Mapping[str, Any], raw_document)
            raw_document_id = document.get("source_document_id")
            if not isinstance(raw_document_id, str) or not raw_document_id.strip():
                raise RecapFetchBrokerPolicyError(
                    f"selected document for {candidate_id} lacks an ID"
                )
            document_id = raw_document_id.strip()
            if document_id != raw_document_id or document_id in documents:
                raise RecapFetchBrokerPolicyError(
                    f"selected document IDs for {candidate_id} must be canonical "
                    "and unique"
                )
            documents[document_id] = document
        indexed[candidate_id] = documents
    return indexed


def _require_not_restricted(metadata: Mapping[str, Any], document_id: str) -> None:
    status = metadata.get("redaction_or_seal_status")
    is_sealed = metadata.get("is_sealed")
    is_private = metadata.get("is_private")
    public = status == "public" and is_sealed is False and is_private is False
    screened_paid_unknown = (
        status == "unknown"
        and is_sealed is None
        and is_private is None
        and metadata.get("requires_paid_recovery") is True
        and metadata.get("availability_status") == "unavailable"
        and metadata.get("restriction_evidence") == CASE_DEV_PAID_RESTRICTION_EVIDENCE
    )
    courtlistener_rest_public = (
        status == "public"
        and is_sealed is False
        and is_private is None
        and metadata.get("requires_paid_recovery") is True
        and metadata.get("availability_status") == "unavailable"
        and metadata.get("restriction_evidence")
        == COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE
    )
    if not public and not screened_paid_unknown and not courtlistener_rest_public:
        raise RecapFetchBrokerPolicyError(
            f"document {document_id} is sealed/private/restricted or lacks "
            "the bridge's explicit restriction-screening metadata"
        )


def _canonical_document_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or _CANONICAL_RECAP_DOCUMENT_ID.fullmatch(value) is None
    ):
        raise RecapFetchBrokerPolicyError(
            "planned RECAP document IDs must be canonical positive integers"
        )
    return value


def _canonical_case_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise RecapFetchBrokerPolicyError(
            f"{field} must be a non-empty canonical string"
        )
    return value


def _canonical_json(value: object) -> str:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return (
            "{"
            + ",".join(
                f"{json.dumps(key, ensure_ascii=False)}:{_canonical_json(mapping[key])}"
                for key in sorted(mapping)
            )
            + "}"
        )
    if isinstance(value, list):
        items = cast(list[object], value)
        return "[" + ",".join(_canonical_json(item) for item in items) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _verify_generated_policy_shape(policy: Mapping[str, object]) -> None:
    expected = {
        "version",
        "cycle_id",
        "purchase_policy_sha256",
        "cycle_cap_usd",
        "per_case_cap_usd",
        "reservation_usd",
        "opening_committed_spend_usd",
        "opening_case_committed_spend_usd",
        "allowed_documents",
    }
    if (
        set(policy) != expected
        or policy.get("version") != RECAP_FETCH_BROKER_POLICY_VERSION
    ):
        raise RecapFetchBrokerPolicyError(
            "RECAP Fetch broker policy has an unexpected schema"
        )
    cycle_id = policy.get("cycle_id")
    if not isinstance(cycle_id, str) or not cycle_id or len(cycle_id) > 128:
        raise RecapFetchBrokerPolicyError(
            "RECAP Fetch broker policy identity is invalid"
        )
    digest = policy.get("purchase_policy_sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise RecapFetchBrokerPolicyError("purchase policy digest is invalid")
    cycle_cap = _canonical_money(policy.get("cycle_cap_usd"), "cycle_cap_usd")
    per_case_cap = _canonical_money(policy.get("per_case_cap_usd"), "per_case_cap_usd")
    reservation = _canonical_money(policy.get("reservation_usd"), "reservation_usd")
    opening = _canonical_money(
        policy.get("opening_committed_spend_usd"),
        "opening_committed_spend_usd",
    )
    if (
        reservation <= 0
        or per_case_cap <= 0
        or reservation > per_case_cap
        or per_case_cap > cycle_cap
        or opening > cycle_cap
    ):
        raise RecapFetchBrokerPolicyError(
            "broker policy caps, reservation, or opening spend are inconsistent"
        )
    raw_documents = policy.get("allowed_documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise RecapFetchBrokerPolicyError("broker document allowlist must not be empty")
    documents = cast(list[object], raw_documents)
    seen_documents: set[str] = set()
    allowed_cases: set[str] = set()
    for raw_document in documents:
        if not isinstance(raw_document, Mapping):
            raise RecapFetchBrokerPolicyError("allowed document schema is invalid")
        document = cast(Mapping[str, object], raw_document)
        if set(document) != {
            "recap_document",
            "case_id",
        }:
            raise RecapFetchBrokerPolicyError("allowed document schema is invalid")
        document_id = _canonical_document_id(document.get("recap_document"))
        case_id = _canonical_case_id(document.get("case_id"), "case_id")
        if document_id in seen_documents:
            raise RecapFetchBrokerPolicyError("allowed document IDs must be unique")
        seen_documents.add(document_id)
        allowed_cases.add(case_id)
    raw_opening_cases = policy.get("opening_case_committed_spend_usd")
    if not isinstance(raw_opening_cases, Mapping):
        raise RecapFetchBrokerPolicyError("opening case commitments must be an object")
    opening_cases = cast(Mapping[object, object], raw_opening_cases)
    attributed = Decimal("0.00")
    for raw_case_id, raw_amount in opening_cases.items():
        case_id = _canonical_case_id(raw_case_id, "opening commitment case ID")
        amount = _canonical_money(raw_amount, "opening case commitment")
        if case_id not in allowed_cases or amount > per_case_cap:
            raise RecapFetchBrokerPolicyError(
                "opening commitment case or amount is inconsistent"
            )
        attributed += amount
    if attributed != opening:
        raise RecapFetchBrokerPolicyError(
            "opening case commitments must exactly equal opening committed spend"
        )


def _validate_budget_plan_artifact(
    artifact: Mapping[str, object],
    *,
    budget_plan: MissingCoreBudgetPlan,
    reservation_usd: Decimal,
    hard_cap_usd: Decimal,
    opening_committed_spend_usd: Decimal,
    opening_case_committed_spend_usd: Mapping[str, Decimal],
    per_case_cap_usd: Decimal,
) -> None:
    if artifact.get("dry_run") is not False:
        raise RecapFetchBrokerPolicyError(
            "budget plan artifact must explicitly be non-dry-run"
        )
    raw_cost = _canonical_money(
        artifact.get("cost_per_document_usd"), "cost_per_document_usd"
    )
    if raw_cost != reservation_usd or budget_plan.cost_per_document != reservation_usd:
        raise RecapFetchBrokerPolicyError(
            "budget plan document cost must equal the verified reservation"
        )
    raw_budget = _canonical_money(
        artifact.get("max_projected_budget_usd"), "max_projected_budget_usd"
    )
    if raw_budget != budget_plan.max_projected_budget:
        raise RecapFetchBrokerPolicyError(
            "budget plan projected cap is internally inconsistent"
        )
    if raw_budget <= 0 or raw_budget > hard_cap_usd:
        raise RecapFetchBrokerPolicyError(
            "budget plan projected cap exceeds the verified purchase-policy cap"
        )

    raw_case_plans = artifact.get("case_plans")
    if not isinstance(raw_case_plans, list):
        raise RecapFetchBrokerPolicyError(
            "budget plan case_plans do not match the executable plan"
        )
    case_records = cast(list[object], raw_case_plans)
    if len(case_records) != len(budget_plan.case_plans):
        raise RecapFetchBrokerPolicyError(
            "budget plan case_plans do not match the executable plan"
        )
    total_document_count = 0
    total_cost = Decimal("0.00")
    for raw_case, case_plan in zip(case_records, budget_plan.case_plans, strict=True):
        if not isinstance(raw_case, Mapping):
            raise RecapFetchBrokerPolicyError("budget case plan must be an object")
        typed_case = cast(Mapping[str, object], raw_case)
        document_ids = typed_case.get("purchase_document_ids")
        if not isinstance(document_ids, list) or document_ids != list(
            case_plan.purchase_document_ids
        ):
            raise RecapFetchBrokerPolicyError(
                "budget case purchase_document_ids are internally inconsistent"
            )
        count = len(cast(list[object], document_ids))
        expected_cost = reservation_usd * count
        if (
            budget_plan.max_missing_core_documents_per_case <= 0
            or count > budget_plan.max_missing_core_documents_per_case
        ):
            raise RecapFetchBrokerPolicyError(
                f"budget case plan {case_plan.candidate_id} exceeds its document cap"
            )
        if typed_case.get("dry_run") is not False or case_plan.dry_run:
            raise RecapFetchBrokerPolicyError(
                f"budget case plan {case_plan.candidate_id} is marked dry-run"
            )
        if typed_case.get("exclusion_reasons") != [] or case_plan.exclusion_reasons:
            raise RecapFetchBrokerPolicyError(
                f"budget case plan {case_plan.candidate_id} is excluded"
            )
        if (
            typed_case.get("candidate_id") != case_plan.candidate_id
            or typed_case.get("missing_core_document_count") != count
            or typed_case.get("estimated_purchase_count") != count
            or _canonical_money(
                typed_case.get("estimated_cost_usd"), "estimated_cost_usd"
            )
            != expected_cost
            or case_plan.estimated_cost != expected_cost
        ):
            raise RecapFetchBrokerPolicyError(
                f"budget case plan {case_plan.candidate_id} is internally inconsistent"
            )
        opening_case = opening_case_committed_spend_usd.get(
            case_plan.candidate_id, Decimal("0.00")
        )
        if opening_case + expected_cost > per_case_cap_usd:
            raise RecapFetchBrokerPolicyError(
                f"budget case plan {case_plan.candidate_id} exceeds the verified "
                "per-case cap"
            )
        total_document_count += count
        total_cost += expected_cost

    if artifact.get("total_missing_core_documents") != total_document_count:
        raise RecapFetchBrokerPolicyError(
            "budget plan total document count is internally inconsistent"
        )
    if (
        _canonical_money(
            artifact.get("total_estimated_cost_usd"), "total_estimated_cost_usd"
        )
        != total_cost
        or budget_plan.total_estimated_cost != total_cost
    ):
        raise RecapFetchBrokerPolicyError(
            "budget plan total estimated cost is internally inconsistent"
        )
    if (
        total_cost > raw_budget
        or opening_committed_spend_usd + total_cost > hard_cap_usd
    ):
        raise RecapFetchBrokerPolicyError(
            "budget plan reservations exceed the verified purchase-policy envelope"
        )


def _canonical_money(value: object, field: str) -> Decimal:
    if not isinstance(value, str) or _CANONICAL_USD.fullmatch(value) is None:
        raise RecapFetchBrokerPolicyError(
            f"{field} must be canonical nonnegative two-decimal USD"
        )
    amount = Decimal(value)
    _require_javascript_safe_money(amount, field)
    return amount


def _require_javascript_safe_money(amount: Decimal, field: str) -> None:
    cents = amount * 100
    if cents != cents.to_integral_value() or cents > _JAVASCRIPT_MAX_SAFE_CENTS:
        raise RecapFetchBrokerPolicyError(
            f"{field} exceeds secure-gate's safe integer-cent domain"
        )

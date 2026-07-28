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
    require_approved_case_dev_purchase_policy,
    verify_approved_purchase_input_bytes,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
)
from legalforecast.ingestion.missing_core_budget import MissingCoreBudgetPlan
from legalforecast.ingestion.recap_fetch_broker_policy import (
    COURTLISTENER_REST_PAID_RESTRICTION_EVIDENCE,
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


class RecapFetchAttemptPolicyError(ValueError):
    """Raised when unknown-status evidence cannot grant attempt authority."""


def generate_recap_fetch_attempt_policy(
    *,
    purchase_policy_artifact: Mapping[str, object],
    cohort_policy_artifact: Mapping[str, Any],
    budget_plan: MissingCoreBudgetPlan,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
    budget_plan_bytes: bytes | None = None,
    selection_bytes: bytes | None = None,
    controlled_private_root: Path | None = None,
    replacement_purchase_authority_artifact: Mapping[str, object] | None = None,
    replacement_controlled_private_root: Path | None = None,
    purchase_ledger_initialization_receipt_path: Path | None = None,
) -> dict[str, object]:
    """Bind the unknown subset of one executable plan to exact source rows."""

    return _build_recap_fetch_attempt_policy(
        purchase_policy_artifact=purchase_policy_artifact,
        cohort_policy_artifact=cohort_policy_artifact,
        budget_plan=budget_plan,
        budget_plan_artifact=budget_plan_artifact,
        selection_records=selection_records,
        budget_plan_bytes=budget_plan_bytes,
        selection_bytes=selection_bytes,
        controlled_private_root=controlled_private_root,
        require_fresh_ledger_namespace=True,
        replacement_purchase_authority_artifact=(
            replacement_purchase_authority_artifact
        ),
        replacement_controlled_private_root=replacement_controlled_private_root,
        purchase_ledger_initialization_receipt_path=(
            purchase_ledger_initialization_receipt_path
        ),
    )


def _build_recap_fetch_attempt_policy(
    *,
    purchase_policy_artifact: Mapping[str, object],
    cohort_policy_artifact: Mapping[str, Any],
    budget_plan: MissingCoreBudgetPlan,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
    budget_plan_bytes: bytes | None,
    selection_bytes: bytes | None,
    controlled_private_root: Path | None,
    require_fresh_ledger_namespace: bool,
    replacement_purchase_authority_artifact: Mapping[str, object] | None,
    replacement_controlled_private_root: Path | None,
    purchase_ledger_initialization_receipt_path: Path | None,
) -> dict[str, object]:
    """Build minting or replay evidence under an explicit private mode."""

    try:
        # Lazy to avoid the ingestion package's disclosure/projection import cycle.
        from legalforecast.ingestion.purchase_approval import (
            require_fresh_purchase_ledger_namespace,
        )

        purchase_policy = verify_case_dev_purchase_policy(purchase_policy_artifact)
        require_approved_case_dev_purchase_policy(
            purchase_policy, controlled_private_root=controlled_private_root
        )
        replacement_inputs_supplied = sum(
            value is not None
            for value in (
                replacement_purchase_authority_artifact,
                replacement_controlled_private_root,
                purchase_ledger_initialization_receipt_path,
            )
        )
        if replacement_inputs_supplied not in {0, 3}:
            raise ValueError(
                "replacement authority, controlled private root, and purchase-ledger "
                "initialization receipt must be supplied together"
            )
        replacement_mode = replacement_inputs_supplied == 3
        if (
            purchase_policy.has_verified_approval
            and require_fresh_ledger_namespace
            and not replacement_mode
        ):
            require_fresh_purchase_ledger_namespace(
                purchase_policy.canonical_ledger_path
            )
        if replacement_purchase_authority_artifact is None:
            verify_approved_purchase_input_bytes(
                purchase_policy,
                controlled_private_root=cast(Path, controlled_private_root),
                budget_plan_bytes=budget_plan_bytes,
                selection_bytes=selection_bytes,
            )
        else:
            from legalforecast.ingestion.replacement_purchase_approval import (
                verify_replacement_purchase_authority,
            )

            verify_replacement_purchase_authority(
                authority_artifact=replacement_purchase_authority_artifact,
                controlled_private_root=cast(Path, replacement_controlled_private_root),
                initial_purchase_policy_artifact=purchase_policy_artifact,
                initial_controlled_private_root=cast(Path, controlled_private_root),
                cohort_policy_artifact=cohort_policy_artifact,
                budget_plan_bytes=cast(bytes, budget_plan_bytes),
                selection_bytes=cast(bytes, selection_bytes),
                purchase_ledger_path=purchase_policy.canonical_ledger_path,
                purchase_ledger_initialization_receipt_path=cast(
                    Path, purchase_ledger_initialization_receipt_path
                ),
            )
        if purchase_policy.has_verified_approval:
            _require_structured_inputs_match_authenticated_bytes(
                budget_plan_artifact=budget_plan_artifact,
                selection_records=selection_records,
                budget_plan_bytes=cast(bytes, budget_plan_bytes),
                selection_bytes=cast(bytes, selection_bytes),
            )
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
    except (OSError, ValueError) as exc:
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
    budget_plan_bytes: bytes,
    selection_bytes: bytes,
    controlled_private_root: Path,
    replacement_purchase_authority_artifact: Mapping[str, object] | None = None,
    replacement_controlled_private_root: Path | None = None,
    purchase_ledger_initialization_receipt_path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Replay existing attempt authority without minting after initialization."""

    expected = _build_recap_fetch_attempt_policy(
        purchase_policy_artifact=purchase_policy_artifact,
        cohort_policy_artifact=cohort_policy_artifact,
        budget_plan=budget_plan,
        budget_plan_artifact=budget_plan_artifact,
        selection_records=selection_records,
        budget_plan_bytes=budget_plan_bytes,
        selection_bytes=selection_bytes,
        controlled_private_root=controlled_private_root,
        require_fresh_ledger_namespace=False,
        replacement_purchase_authority_artifact=(
            replacement_purchase_authority_artifact
        ),
        replacement_controlled_private_root=replacement_controlled_private_root,
        purchase_ledger_initialization_receipt_path=(
            purchase_ledger_initialization_receipt_path
        ),
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

    target = Path(path)
    payload = _attempt_policy_payload(artifact)
    preflight_recap_fetch_attempt_policy(target, artifact)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
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


def preflight_recap_fetch_attempt_policy(
    path: str | Path, artifact: Mapping[str, object]
) -> Path:
    """Validate write-once attempt-policy state without changing the output."""

    target = Path(path)
    payload = _attempt_policy_payload(artifact)
    if target.is_symlink():
        raise RecapFetchAttemptPolicyError("attempt policy output is a symlink")
    if not target.exists():
        return target
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


def _attempt_policy_payload(artifact: Mapping[str, object]) -> bytes:
    _verify_shape(artifact)
    return (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode()


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
            # A selected case can include ordinary free documents whose stable
            # source identifiers are provider-qualified strings. Only IDs in
            # the executable paid plan are RECAP Fetch identifiers and must be
            # canonical positive integers; that validation happens during
            # executable-plan matching.
            document_id = _canonical_text(
                document.get("source_document_id"), "source_document_id"
            )
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


def _require_structured_inputs_match_authenticated_bytes(
    *,
    budget_plan_artifact: Mapping[str, object],
    selection_records: Sequence[Mapping[str, Any]],
    budget_plan_bytes: bytes,
    selection_bytes: bytes,
) -> None:
    """Prevent callers from detaching structured authority from approved bytes."""

    try:
        parsed_budget = json.loads(budget_plan_bytes)
        parsed_selection = [
            json.loads(line) for line in selection_bytes.splitlines() if line.strip()
        ]
    except (UnicodeError, ValueError) as exc:
        raise RecapFetchAttemptPolicyError(
            "authenticated purchase inputs are not canonical JSON"
        ) from exc
    if not isinstance(parsed_budget, Mapping):
        raise RecapFetchAttemptPolicyError(
            "budget plan structure differs from authenticated bytes"
        )
    typed_budget = cast(Mapping[str, object], parsed_budget)
    if dict(typed_budget) != dict(budget_plan_artifact):
        raise RecapFetchAttemptPolicyError(
            "budget plan structure differs from authenticated bytes"
        )
    if parsed_selection != _canonical_records(selection_records):
        raise RecapFetchAttemptPolicyError(
            "selection structure differs from authenticated bytes"
        )


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

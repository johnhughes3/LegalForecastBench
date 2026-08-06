"""Deterministic, provider-free Cycle 1 corpus completion summaries."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.ingestion.canonical_json import canonical_json_value_bytes
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchasePolicy,
    CaseDevPurchaseSnapshot,
    read_case_dev_purchase_snapshot,
    summarize_case_dev_purchase_snapshot,
    verify_case_dev_purchase_policy,
    verify_case_dev_purchase_policy_cohort_binding,
    verify_purchase_ledger_initialization_lineage,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)

SUMMARY_SCHEMA_VERSION = "legalforecast.corpus_completion_summary.v1"
RUN_CARD_SCHEMA_VERSION = "legalforecast.corpus_completion_summary_run_card.v1"

_FINAL_READINESS_FIELDS = frozenset(
    {
        "required_clean_count",
        "clean_count",
        "meets_target",
        "clean_candidate_ids",
        "excluded_candidate_ids",
        "exclusion_reasons",
        "funnel",
        "case_mix",
        "screening_snapshot_reconciliation",
        "target_cohort_preparation",
    }
)
_FUNNEL_FIELDS = frozenset(
    {
        "selected",
        "parsed_complete",
        "unitized_complete",
        "labeled_complete",
        "packet_inputs",
        "packets_built",
        "excluded",
        "clean",
    }
)
_CASE_MIX_DIMENSIONS = frozenset(
    {
        "court",
        "nature_of_suit",
        "nos_macro_category",
        "related_family_id",
        "mdl_family_id",
        "case_type_stratum",
    }
)
_RESOLVED_REVIEW_STATUSES = frozenset(
    {"adjudicated", "resolved", "complete", "succeeded"}
)


class CorpusCompletionSummaryError(ValueError):
    """Raised when terminal corpus evidence cannot support a closed summary."""


@dataclass(frozen=True, slots=True)
class CorpusCompletionSummaryInputs:
    """Exact terminal artifacts consumed by the provider-free summary."""

    finalize_run_card: Path
    corpus_readiness: Path
    complete_exclusion_ledger: Path
    materialization_summary: Path
    materialization_run_card: Path
    purchase_policy: Path
    cohort_policy: Path
    purchase_ledger: Path
    purchase_ledger_initialization_receipt: Path
    model_registry: Path
    unitization_review_queue: Path
    unitization_adjudications: Path
    lawyer_review_queue: Path
    lawyer_review_audit: Path
    adjudication_beads: tuple[str, ...] = ()

    def file_paths(self) -> tuple[tuple[str, Path], ...]:
        """Return regular-file inputs in deterministic semantic order."""

        return (
            ("finalize_run_card", self.finalize_run_card),
            ("corpus_readiness", self.corpus_readiness),
            ("complete_exclusion_ledger", self.complete_exclusion_ledger),
            ("materialization_summary", self.materialization_summary),
            ("materialization_run_card", self.materialization_run_card),
            ("purchase_policy", self.purchase_policy),
            ("cohort_policy", self.cohort_policy),
            (
                "purchase_ledger_initialization_receipt",
                self.purchase_ledger_initialization_receipt,
            ),
            ("model_registry", self.model_registry),
            ("unitization_review_queue", self.unitization_review_queue),
            ("unitization_adjudications", self.unitization_adjudications),
            ("lawyer_review_queue", self.lawyer_review_queue),
            ("lawyer_review_audit", self.lawyer_review_audit),
        )


def build_corpus_completion_summary(
    inputs: CorpusCompletionSummaryInputs,
) -> dict[str, object]:
    """Authenticate terminal artifacts and return one deterministic summary."""

    payloads = _read_input_payloads(inputs)
    finalize_card = _json_object(payloads["finalize_run_card"], "finalize run card")
    readiness = _json_object(payloads["corpus_readiness"], "corpus readiness")
    exclusion_records = _jsonl_records(
        payloads["complete_exclusion_ledger"], "complete exclusion ledger"
    )
    materialization = _json_object(
        payloads["materialization_summary"], "materialization summary"
    )
    materialization_card = _json_object(
        payloads["materialization_run_card"], "materialization run card"
    )
    stage_a_queue = _jsonl_records(
        payloads["unitization_review_queue"], "unitization review queue"
    )
    stage_a_adjudications = _jsonl_records(
        payloads["unitization_adjudications"], "unitization adjudications"
    )
    stage_b_queue = _jsonl_records(
        payloads["lawyer_review_queue"], "lawyer review queue"
    )
    stage_b_audit = _jsonl_records(
        payloads["lawyer_review_audit"], "lawyer review audit"
    )

    _validate_readiness(readiness)
    _validate_finalize_card(finalize_card, readiness=readiness, inputs=inputs)
    exclusion_summary = _summarize_exclusions(exclusion_records, readiness=readiness)
    acquisition_summary = _validate_materialization(
        materialization,
        run_card=materialization_card,
        summary_payload=payloads["materialization_summary"],
        readiness=readiness,
        inputs=inputs,
    )

    policy, purchase_snapshot = _read_authenticated_purchase_snapshot(
        inputs,
        payloads=payloads,
    )
    expected_purchase_state = _required_str(
        _required_mapping(
            materialization_card,
            "source_commitments",
            "materialization run card",
        ),
        "purchase_state_sha256",
        "materialization source commitments",
    )
    if purchase_snapshot.purchase_state_sha256 != expected_purchase_state:
        raise CorpusCompletionSummaryError(
            "purchase ledger state differs from materialization commitment"
        )
    if (
        _required_str(
            _required_mapping(
                materialization,
                "source_commitments",
                "materialization summary",
            ),
            "purchase_state_sha256",
            "materialization source commitments",
        )
        != expected_purchase_state
    ):
        raise CorpusCompletionSummaryError(
            "materialization summary purchase state differs from its run card"
        )
    canonical_spend = summarize_case_dev_purchase_snapshot(
        policy=policy,
        snapshot=purchase_snapshot,
    )
    spend_summary = {
        "currency": "USD",
        "cycle_id": policy.cycle_id,
        "purchase_policy_sha256": policy.policy_sha256,
        "purchase_state_sha256": purchase_snapshot.purchase_state_sha256,
        "hard_cap_usd": f"{policy.hard_cap_usd:.2f}",
        "opening_committed_spend_usd": (f"{policy.opening_committed_spend_usd:.2f}"),
        **canonical_spend.to_record(),
    }

    registry_payload = payloads["model_registry"]
    try:
        registry = load_model_registry_bytes(registry_payload)
        official_entries = require_official_registry_entries(registry.entries)
        eligibility_anchor = earliest_eligible_decision_date(
            official_entries
        ).isoformat()
    except ValueError as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc

    adjudication_summary = _summarize_adjudications(
        stage_a_queue=stage_a_queue,
        stage_a_adjudications=stage_a_adjudications,
        stage_b_queue=stage_b_queue,
        stage_b_audit=stage_b_audit,
        bead_references=inputs.adjudication_beads,
    )
    input_commitments = _input_commitments(
        inputs,
        payloads=payloads,
        purchase_snapshot=purchase_snapshot,
    )
    discovery = cast(
        Mapping[str, object], readiness["screening_snapshot_reconciliation"]
    )
    body: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "target": {
            "required_clean_count": readiness["required_clean_count"],
            "clean_count": readiness["clean_count"],
            "meets_target": True,
            "eligibility_anchor": eligibility_anchor,
        },
        "discovery": {
            "accepted_count": discovery["accepted_count"],
            "excluded_count": discovery["excluded_count"],
            "processed_count": discovery["processed_count"],
        },
        "exclusions": exclusion_summary,
        "acquisition": acquisition_summary,
        "funnel": dict(cast(Mapping[str, int], readiness["funnel"])),
        "case_mix": {
            dimension: dict(sorted(buckets.items()))
            for dimension, buckets in sorted(
                cast(Mapping[str, Mapping[str, int]], readiness["case_mix"]).items()
            )
        },
        "adjudication": adjudication_summary,
        "spend": spend_summary,
        "input_commitments": input_commitments,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    body["summary_sha256"] = _canonical_sha256(body)
    _require_inputs_unchanged(inputs, payloads=payloads)
    return body


def summary_json_bytes(summary: Mapping[str, object]) -> bytes:
    """Serialize a completion summary in its deterministic artifact form."""

    _validate_summary_self_hash(summary)
    try:
        return (
            json.dumps(
                dict(summary),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise CorpusCompletionSummaryError(
            "corpus completion summary is not canonical JSON"
        ) from exc


def completion_summary_run_card(
    *,
    inputs: CorpusCompletionSummaryInputs,
    summary_path: Path,
    summary_payload: bytes,
    input_commitments: Mapping[str, object],
    execute: bool,
) -> dict[str, object]:
    """Return the deterministic closed run card for summary publication."""

    input_paths = [str(path.resolve()) for _, path in inputs.file_paths()] + [
        str(inputs.purchase_ledger.resolve())
    ]
    summary_commitment = _byte_commitment(summary_path, summary_payload)
    return {
        "schema_version": RUN_CARD_SCHEMA_VERSION,
        "stage": "summarize-corpus",
        "status": "completed" if execute else "validated",
        "dry_run": not execute,
        "execute": execute,
        "input_paths": input_paths,
        "output_paths": [str(summary_path.resolve())],
        "input_commitments": dict(input_commitments),
        "output_commitments": {"corpus_completion_summary": summary_commitment},
        "activity": {
            "provider_requested": False,
            "provider_executed": False,
            "paid_requested": False,
            "paid_executed": False,
            "aws_requested": False,
            "aws_executed": False,
            "evaluation_authorized": False,
            "freeze_authorized": False,
            "dispatch_authorized": False,
        },
        "zero_provider_activity_evidence": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "aws_activity_requested": False,
        "aws_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }


def require_completion_inputs_unchanged(
    inputs: CorpusCompletionSummaryInputs,
    *,
    summary: Mapping[str, object],
) -> None:
    """Re-read every source and reject static or SQLite state drift."""

    commitments = _required_mapping(summary, "input_commitments", "summary")
    payloads = _read_input_payloads(inputs)
    for name, path in inputs.file_paths():
        expected = _required_mapping(commitments, name, "summary commitments")
        if (
            Path(_required_str(expected, "path", f"{name} commitment")).resolve()
            != path.resolve()
            or _normalize_sha256(
                _required_str(expected, "sha256", f"{name} commitment")
            )
            != hashlib.sha256(payloads[name]).hexdigest()
            or _required_nonnegative_int(expected, "byte_count", f"{name} commitment")
            != len(payloads[name])
        ):
            raise CorpusCompletionSummaryError(
                f"completion-summary source changed after verification: {path}"
            )
    _, snapshot = _read_authenticated_purchase_snapshot(inputs, payloads=payloads)
    expected_ledger = _required_mapping(
        commitments, "purchase_ledger", "summary commitments"
    )
    expected_identity = (
        _normalize_sha256(
            _required_str(
                expected_ledger,
                "purchase_state_sha256",
                "purchase ledger commitment",
            )
        ),
        _normalize_sha256(
            _required_str(
                expected_ledger,
                "operations_sha256",
                "purchase ledger commitment",
            )
        ),
        _required_str(
            expected_ledger,
            "committed_amount_usd",
            "purchase ledger commitment",
        ),
        _required_nonnegative_int(
            expected_ledger,
            "operation_count",
            "purchase ledger commitment",
        ),
    )
    if _purchase_snapshot_identity(snapshot) != expected_identity:
        raise CorpusCompletionSummaryError(
            "purchase ledger changed after completion-summary verification"
        )


def _validate_readiness(readiness: Mapping[str, Any]) -> None:
    if set(readiness) != set(_FINAL_READINESS_FIELDS):
        raise CorpusCompletionSummaryError("corpus readiness field set differs")
    required = _required_positive_int(readiness, "required_clean_count", "readiness")
    clean_count = _required_nonnegative_int(readiness, "clean_count", "readiness")
    if readiness.get("meets_target") is not True or clean_count < required:
        raise CorpusCompletionSummaryError("corpus readiness does not meet its target")
    clean_ids = _required_unique_strings(readiness, "clean_candidate_ids", "readiness")
    excluded_ids = _required_unique_strings(
        readiness, "excluded_candidate_ids", "readiness"
    )
    if len(clean_ids) != clean_count or set(clean_ids) & set(excluded_ids):
        raise CorpusCompletionSummaryError("readiness candidate partition differs")
    funnel = _required_mapping(readiness, "funnel", "readiness")
    if set(funnel) != set(_FUNNEL_FIELDS):
        raise CorpusCompletionSummaryError("readiness funnel field set differs")
    counts = {
        field: _required_nonnegative_int(funnel, field, "readiness funnel")
        for field in _FUNNEL_FIELDS
    }
    if (
        counts["selected"] != clean_count + len(excluded_ids)
        or counts["clean"] != clean_count
        or counts["excluded"] != len(excluded_ids)
        or any(count > counts["selected"] for count in counts.values())
        or any(
            counts[field] < clean_count
            for field in (
                "parsed_complete",
                "unitized_complete",
                "labeled_complete",
                "packet_inputs",
                "packets_built",
            )
        )
    ):
        raise CorpusCompletionSummaryError("readiness funnel counts do not reconcile")
    raw_reasons = _required_mapping(readiness, "exclusion_reasons", "readiness")
    if set(raw_reasons) != set(excluded_ids):
        raise CorpusCompletionSummaryError("readiness exclusion reasons differ")
    for candidate_id, reasons in raw_reasons.items():
        _string_sequence(reasons, f"readiness reasons for {candidate_id}")
    case_mix = _required_mapping(readiness, "case_mix", "readiness")
    if set(case_mix) != set(_CASE_MIX_DIMENSIONS):
        raise CorpusCompletionSummaryError("readiness case-mix dimensions differ")
    for dimension, raw_buckets in case_mix.items():
        if not isinstance(raw_buckets, Mapping) or not raw_buckets:
            raise CorpusCompletionSummaryError(
                f"readiness case-mix {dimension} is invalid"
            )
        buckets = cast(Mapping[object, object], raw_buckets)
        if (
            any(
                not isinstance(name, str)
                or not name
                or type(value) is not int
                or value < 0
                for name, value in buckets.items()
            )
            or sum(value for value in buckets.values() if isinstance(value, int))
            != clean_count
        ):
            raise CorpusCompletionSummaryError(
                f"readiness case-mix {dimension} does not reconcile"
            )
    discovery = _required_mapping(
        readiness,
        "screening_snapshot_reconciliation",
        "readiness",
    )
    accepted = _required_nonnegative_int(discovery, "accepted_count", "discovery")
    excluded = _required_nonnegative_int(discovery, "excluded_count", "discovery")
    processed = _required_nonnegative_int(discovery, "processed_count", "discovery")
    if processed != accepted + excluded:
        raise CorpusCompletionSummaryError("discovery counts do not reconcile")
    if counts["selected"] > accepted:
        raise CorpusCompletionSummaryError(
            "selected count exceeds discovery acceptance"
        )
    _required_mapping(readiness, "target_cohort_preparation", "readiness")


def _validate_finalize_card(
    card: Mapping[str, Any],
    *,
    readiness: Mapping[str, Any],
    inputs: CorpusCompletionSummaryInputs,
) -> None:
    if (
        card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or card.get("stage") != "finalize-corpus"
        or card.get("status") != "completed"
        or card.get("dry_run") is not False
        or card.get("execute") is not True
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
        or card.get("record_count") != readiness["clean_count"]
        or card.get("target_clean_cases") != readiness["required_clean_count"]
        or card.get("clean_count") != readiness["clean_count"]
        or card.get("meets_target") is not True
    ):
        raise CorpusCompletionSummaryError("finalize-corpus run card is inconsistent")
    raw_inputs = card.get("input_paths")
    raw_outputs = card.get("output_paths")
    if not isinstance(raw_inputs, list) or not isinstance(raw_outputs, list):
        raise CorpusCompletionSummaryError("finalize-corpus paths are malformed")
    input_values = cast(list[object], raw_inputs)
    output_values = cast(list[object], raw_outputs)
    if not all(isinstance(path, str) for path in (*input_values, *output_values)):
        raise CorpusCompletionSummaryError("finalize-corpus paths are malformed")
    committed_inputs = {Path(cast(str, path)).resolve() for path in input_values}
    required_inputs = {
        inputs.materialization_run_card.resolve(),
        inputs.model_registry.resolve(),
        inputs.unitization_review_queue.resolve(),
        inputs.unitization_adjudications.resolve(),
        inputs.lawyer_review_queue.resolve(),
        inputs.lawyer_review_audit.resolve(),
    }
    if not required_inputs.issubset(committed_inputs):
        raise CorpusCompletionSummaryError(
            "summary inputs are not all owned by finalize-corpus"
        )
    committed_outputs = [Path(cast(str, path)).resolve() for path in output_values]
    expected_outputs = {
        inputs.corpus_readiness.resolve(),
        inputs.complete_exclusion_ledger.resolve(),
    }
    if len(committed_outputs) != 2 or set(committed_outputs) != expected_outputs:
        raise CorpusCompletionSummaryError("finalize-corpus outputs differ")


def _summarize_exclusions(
    records: Sequence[Mapping[str, Any]],
    *,
    readiness: Mapping[str, Any],
) -> dict[str, object]:
    by_id: dict[str, Mapping[str, Any]] = {}
    primary_counts: Counter[str] = Counter()
    secondary_counts: Counter[str] = Counter()
    for record in records:
        candidate_id = _required_str(record, "candidate_id", "exclusion record")
        if candidate_id in by_id:
            raise CorpusCompletionSummaryError(
                f"duplicate complete-ledger candidate: {candidate_id}"
            )
        by_id[candidate_id] = record
        primary = _required_str(record, "primary_exclusion_reason", "exclusion record")
        secondary = _string_sequence(
            record.get("secondary_exclusion_reasons", ()),
            "secondary exclusion reasons",
        )
        if primary in secondary:
            raise CorpusCompletionSummaryError(
                f"primary exclusion reason repeated for {candidate_id}"
            )
        primary_counts[primary] += 1
        secondary_counts.update(secondary)
    clean_ids = set(cast(Sequence[str], readiness["clean_candidate_ids"]))
    if clean_ids & set(by_id):
        raise CorpusCompletionSummaryError(
            "clean candidate appears in complete exclusion ledger"
        )
    processed = _required_nonnegative_int(
        cast(Mapping[str, object], readiness["screening_snapshot_reconciliation"]),
        "processed_count",
        "discovery",
    )
    if len(clean_ids) + len(by_id) != processed:
        raise CorpusCompletionSummaryError(
            "clean candidates and complete ledger do not reconcile to discovery"
        )
    raw_reasons = cast(Mapping[str, Sequence[str]], readiness["exclusion_reasons"])
    for candidate_id, reasons in raw_reasons.items():
        ledger_record = by_id.get(candidate_id)
        if ledger_record is None:
            raise CorpusCompletionSummaryError(
                f"readiness exclusion absent from complete ledger: {candidate_id}"
            )
        ledger_reasons = {
            _required_str(
                ledger_record,
                "primary_exclusion_reason",
                "exclusion record",
            ),
            *_string_sequence(
                ledger_record.get("secondary_exclusion_reasons", ()),
                "secondary exclusion reasons",
            ),
        }
        if not set(reasons).issubset(ledger_reasons):
            raise CorpusCompletionSummaryError(
                f"readiness reasons differ from complete ledger: {candidate_id}"
            )
    return {
        "complete_exclusion_count": len(records),
        "primary_reason_counts": dict(sorted(primary_counts.items())),
        "secondary_reason_counts": dict(sorted(secondary_counts.items())),
    }


def _validate_materialization(
    summary: Mapping[str, Any],
    *,
    run_card: Mapping[str, Any],
    summary_payload: bytes,
    readiness: Mapping[str, Any],
    inputs: CorpusCompletionSummaryInputs,
) -> dict[str, object]:
    target_count = _required_positive_int(
        summary, "target_case_count", "materialization summary"
    )
    document_count = _required_nonnegative_int(
        summary, "document_count", "materialization summary"
    )
    free_count = _required_nonnegative_int(
        summary, "free_document_count", "materialization summary"
    )
    purchased_count = _required_nonnegative_int(
        summary, "purchased_document_count", "materialization summary"
    )
    if (
        target_count != cast(Mapping[str, int], readiness["funnel"])["selected"]
        or document_count != free_count + purchased_count
        or summary.get("content_addressed") is not True
        or summary.get("source_roots_mutated") is not False
    ):
        raise CorpusCompletionSummaryError("materialization summary is inconsistent")
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "materialize-cohort-documents"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
        or run_card.get("zero_provider_activity_evidence") is not True
        or run_card.get("target_case_count") != target_count
        or run_card.get("record_count") != document_count
        or run_card.get("free_document_count") != free_count
        or run_card.get("purchased_document_count") != purchased_count
        or run_card.get("source_roots_mutated") is not False
    ):
        raise CorpusCompletionSummaryError("materialization run card is inconsistent")
    output_commitments = _required_mapping(
        run_card, "output_commitments", "materialization run card"
    )
    committed_summary = _required_mapping(
        output_commitments,
        "materialization_summary",
        "materialization output commitments",
    )
    if (
        Path(
            _required_str(
                committed_summary,
                "path",
                "materialization summary commitment",
            )
        ).resolve()
        != inputs.materialization_summary.resolve()
        or _normalize_sha256(
            _required_str(
                committed_summary,
                "sha256",
                "materialization summary commitment",
            )
        )
        != hashlib.sha256(summary_payload).hexdigest()
    ):
        raise CorpusCompletionSummaryError(
            "materialization summary differs from its output commitment"
        )
    return {
        "materialized_case_count": target_count,
        "document_count": document_count,
        "free_document_count": free_count,
        "purchased_document_count": purchased_count,
    }


def _summarize_adjudications(
    *,
    stage_a_queue: Sequence[Mapping[str, Any]],
    stage_a_adjudications: Sequence[Mapping[str, Any]],
    stage_b_queue: Sequence[Mapping[str, Any]],
    stage_b_audit: Sequence[Mapping[str, Any]],
    bead_references: Sequence[str],
) -> dict[str, object]:
    stage_a_ids = _review_ids(stage_a_queue, "Stage A queue")
    covered_stage_a: set[str] = set()
    adjudication_ids: set[str] = set()
    for record in stage_a_adjudications:
        adjudication_id = _required_str(
            record, "adjudication_id", "Stage A adjudication"
        )
        if adjudication_id in adjudication_ids:
            raise CorpusCompletionSummaryError(
                f"duplicate Stage A adjudication: {adjudication_id}"
            )
        adjudication_ids.add(adjudication_id)
        review_ids = _required_unique_strings(
            record, "review_ids", "Stage A adjudication"
        )
        overlap = covered_stage_a & set(review_ids)
        if overlap:
            raise CorpusCompletionSummaryError(
                f"Stage A review adjudicated more than once: {sorted(overlap)}"
            )
        covered_stage_a.update(review_ids)
    if not covered_stage_a.issubset(stage_a_ids):
        raise CorpusCompletionSummaryError(
            "Stage A adjudication references an unknown queue row"
        )
    stage_b_ids = _review_ids(stage_b_queue, "Stage B queue")
    resolved_stage_b: set[str] = set()
    for record in stage_b_audit:
        review_id = record.get("review_id")
        if review_id is None or record.get("status") not in _RESOLVED_REVIEW_STATUSES:
            continue
        if not isinstance(review_id, str) or not review_id:
            raise CorpusCompletionSummaryError("Stage B audit review_id is invalid")
        resolved_stage_b.add(review_id)
    if not resolved_stage_b.issubset(stage_b_ids):
        raise CorpusCompletionSummaryError(
            "Stage B audit resolves an unknown queue row"
        )
    pending_stage_a = sorted(stage_a_ids - covered_stage_a)
    pending_stage_b = sorted(stage_b_ids - resolved_stage_b)
    pending_ids = sorted({*pending_stage_a, *pending_stage_b})
    bead_map = _adjudication_bead_map(bead_references)
    if set(bead_map) != set(pending_ids):
        raise CorpusCompletionSummaryError(
            "adjudication bead mappings must exactly cover pending review IDs"
        )
    return {
        "stage_a_queue_count": len(stage_a_ids),
        "stage_a_adjudication_count": len(stage_a_adjudications),
        "stage_a_pending_count": len(pending_stage_a),
        "stage_a_pending_review_ids": pending_stage_a,
        "stage_b_queue_count": len(stage_b_ids),
        "stage_b_resolved_count": len(resolved_stage_b),
        "stage_b_pending_count": len(pending_stage_b),
        "stage_b_pending_review_ids": pending_stage_b,
        "pending_count": len(pending_ids),
        "pending_bead_references": bead_map,
        "queue_empty_or_fully_adjudicated": not pending_stage_a and not pending_stage_b,
    }


def _review_ids(records: Sequence[Mapping[str, Any]], label: str) -> set[str]:
    review_ids: set[str] = set()
    for record in records:
        review_id = _required_str(record, "review_id", label)
        if review_id in review_ids:
            raise CorpusCompletionSummaryError(
                f"duplicate {label} review_id: {review_id}"
            )
        review_ids.add(review_id)
    return review_ids


def _adjudication_bead_map(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in _string_sequence(values, "adjudication beads"):
        review_id, separator, bead_id = value.partition("=")
        if (
            separator != "="
            or not review_id.strip()
            or not bead_id.strip()
            or review_id in result
        ):
            raise CorpusCompletionSummaryError(
                "adjudication bead must be a unique REVIEW_ID=BEAD_ID mapping"
            )
        result[review_id] = bead_id
    return dict(sorted(result.items()))


def _read_input_payloads(
    inputs: CorpusCompletionSummaryInputs,
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    try:
        for name, path in inputs.file_paths():
            payloads[name] = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc
    return payloads


def _require_inputs_unchanged(
    inputs: CorpusCompletionSummaryInputs,
    *,
    payloads: Mapping[str, bytes],
) -> None:
    try:
        for name, path in inputs.file_paths():
            if read_unique_regular_file(path) != payloads[name]:
                raise CorpusCompletionSummaryError(
                    f"summary input changed while being verified: {path}"
                )
    except (OSError, ReviewBundleError) as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc


def _input_commitments(
    inputs: CorpusCompletionSummaryInputs,
    *,
    payloads: Mapping[str, bytes],
    purchase_snapshot: CaseDevPurchaseSnapshot,
) -> dict[str, object]:
    commitments: dict[str, object] = {
        name: _byte_commitment(path, payloads[name])
        for name, path in inputs.file_paths()
    }
    commitments["purchase_ledger"] = {
        "path": str(inputs.purchase_ledger.resolve()),
        "purchase_state_sha256": purchase_snapshot.purchase_state_sha256,
        "operations_sha256": _operations_sha256(purchase_snapshot.operations),
        "committed_amount_usd": purchase_snapshot.committed_amount_usd,
        "operation_count": len(purchase_snapshot.operations),
    }
    return commitments


def _read_authenticated_purchase_snapshot(
    inputs: CorpusCompletionSummaryInputs,
    *,
    payloads: Mapping[str, bytes],
) -> tuple[CaseDevPurchasePolicy, CaseDevPurchaseSnapshot]:
    policy_artifact = _json_object(payloads["purchase_policy"], "purchase policy")
    cohort_artifact = _json_object(payloads["cohort_policy"], "cohort policy")
    try:
        policy = verify_case_dev_purchase_policy(policy_artifact)
        verify_case_dev_purchase_policy_cohort_binding(policy, cohort_artifact)
        verify_purchase_ledger_initialization_lineage(
            inputs.purchase_ledger_initialization_receipt,
            policy=policy,
        )
    except (OSError, ValueError) as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc
    _validate_initialization_receipt_file_hashes(
        payloads["purchase_ledger_initialization_receipt"],
        purchase_policy_payload=payloads["purchase_policy"],
        cohort_policy_payload=payloads["cohort_policy"],
    )
    try:
        snapshot = read_case_dev_purchase_snapshot(
            inputs.purchase_ledger,
            policy=policy,
            initialization_receipt_path=(inputs.purchase_ledger_initialization_receipt),
        )
    except (OSError, ValueError) as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc
    return policy, snapshot


def _operations_sha256(operations: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        canonical_json_value_bytes(
            [dict(operation) for operation in operations],
            error_type=CorpusCompletionSummaryError,
            error_message="purchase operations are not canonical JSON",
        )
    ).hexdigest()


def _purchase_snapshot_identity(
    snapshot: CaseDevPurchaseSnapshot,
) -> tuple[str, str, str, int]:
    return (
        snapshot.purchase_state_sha256,
        _operations_sha256(snapshot.operations),
        snapshot.committed_amount_usd,
        len(snapshot.operations),
    )


def _validate_initialization_receipt_file_hashes(
    payload: bytes,
    *,
    purchase_policy_payload: bytes,
    cohort_policy_payload: bytes,
) -> None:
    receipt = _json_object(payload, "purchase ledger initialization receipt")
    for field, source_payload in (
        ("purchase_policy_file_sha256", purchase_policy_payload),
        ("cohort_policy_file_sha256", cohort_policy_payload),
    ):
        if (
            _normalize_sha256(
                _required_str(receipt, field, "purchase ledger initialization receipt")
            )
            != hashlib.sha256(source_payload).hexdigest()
        ):
            raise CorpusCompletionSummaryError(
                f"initialization receipt {field} differs from current bytes"
            )


def _validate_summary_self_hash(summary: Mapping[str, object]) -> None:
    expected = summary.get("summary_sha256")
    if not isinstance(expected, str):
        raise CorpusCompletionSummaryError("summary_sha256 is missing")
    body = {key: value for key, value in summary.items() if key != "summary_sha256"}
    if _canonical_sha256(body) != expected:
        raise CorpusCompletionSummaryError("summary_sha256 does not match content")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        canonical_json_value_bytes(
            value,
            error_type=CorpusCompletionSummaryError,
            error_message="completion summary is not canonical JSON",
        )
    ).hexdigest()


def _byte_commitment(path: Path, payload: bytes) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusCompletionSummaryError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise CorpusCompletionSummaryError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _jsonl_records(payload: bytes, label: str) -> tuple[dict[str, Any], ...]:
    try:
        lines = payload.decode("utf-8").splitlines()
        values = [json.loads(line) for line in lines if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusCompletionSummaryError(f"{label} is not valid JSONL") from exc
    if not all(isinstance(value, dict) for value in values):
        raise CorpusCompletionSummaryError(f"{label} rows must be JSON objects")
    return tuple(cast(dict[str, Any], value) for value in values)


def _required_mapping(
    record: Mapping[str, Any], field: str, label: str
) -> Mapping[str, Any]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise CorpusCompletionSummaryError(f"{label} {field} must be an object")
    return cast(Mapping[str, Any], value)


def _required_str(record: Mapping[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CorpusCompletionSummaryError(f"{label} {field} must be nonempty")
    return value


def _required_nonnegative_int(record: Mapping[str, Any], field: str, label: str) -> int:
    value = record.get(field)
    if type(value) is not int or value < 0:
        raise CorpusCompletionSummaryError(
            f"{label} {field} must be a nonnegative integer"
        )
    return value


def _required_positive_int(record: Mapping[str, Any], field: str, label: str) -> int:
    value = _required_nonnegative_int(record, field, label)
    if value < 1:
        raise CorpusCompletionSummaryError(f"{label} {field} must be positive")
    return value


def _required_unique_strings(
    record: Mapping[str, Any], field: str, label: str
) -> tuple[str, ...]:
    values = _string_sequence(record.get(field), f"{label} {field}")
    if len(values) != len(set(values)):
        raise CorpusCompletionSummaryError(f"{label} {field} contains duplicates")
    return values


def _string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CorpusCompletionSummaryError(f"{label} must contain nonempty strings")
    items = cast(Sequence[object], value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise CorpusCompletionSummaryError(f"{label} must contain nonempty strings")
    return tuple(cast(str, item) for item in items)


def _normalize_sha256(value: str) -> str:
    normalized = value.removeprefix("sha256:")
    if (
        len(normalized) != 64
        or normalized.lower() != normalized
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise CorpusCompletionSummaryError("SHA-256 commitment is invalid")
    return normalized


__all__ = [
    "RUN_CARD_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "CorpusCompletionSummaryError",
    "CorpusCompletionSummaryInputs",
    "build_corpus_completion_summary",
    "completion_summary_run_card",
    "require_completion_inputs_unchanged",
    "summary_json_bytes",
]

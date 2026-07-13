"""Immutable cohort precommitments and append-only snapshot observations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    PublishedSnapshot,
    cohort_reason_policy_taxonomy,
    verify_snapshot,
)

COHORT_POLICY_SCHEMA_VERSION = "legalforecast.cohort_policy.v1"
OBSERVATION_SCHEMA_VERSION = "legalforecast.cohort_observation_manifest.v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CLAIM_CLASS_RANK = {
    "provisional_feasibility": 0,
    "official_descriptive": 1,
    "target": 2,
}
_TERMINAL_REDUCED_N_ACTIONS = frozenset({"pilot_only_no_official_cycle", "abort_cycle"})
_POLICY_KEYS = frozenset(
    {
        "cycle_id",
        "cycle_acquisition_hash",
        "eligibility_anchor",
        "stop_rule",
        "window_policy",
        "refresh_policy",
        "packet_completeness",
        "target_motion",
        "purchase_policy",
        "disclosure_clearance",
        "reduced_n",
    }
)


class CohortPolicyError(ValueError):
    """Raised when a cohort artifact is incomplete, mutable, or inconsistent."""


def generate_cohort_policy(decisions: Mapping[str, Any]) -> dict[str, Any]:
    """Validate supplied decisions and bind them into a canonical policy artifact."""

    normalized = cast(dict[str, Any], json.loads(_canonical(decisions)))
    refresh_value = normalized.get("refresh_policy")
    if isinstance(refresh_value, dict):
        refresh = cast(dict[str, Any], refresh_value)
        for field, reason_codes in cohort_reason_policy_taxonomy().items():
            refresh.setdefault(field, list(reason_codes))
    policy = _validated_policy(normalized)
    return {
        "schema_version": COHORT_POLICY_SCHEMA_VERSION,
        "policy": policy,
        "policy_sha256": _hash(policy),
    }


def verify_cohort_policy(
    artifact: Mapping[str, Any], *, expected_sha256: str | None = None
) -> str:
    """Verify schema, semantic constraints, and the immutable content commitment."""

    _exact_keys(
        artifact,
        {"schema_version", "policy", "policy_sha256"},
        "cohort policy artifact",
    )
    if artifact.get("schema_version") != COHORT_POLICY_SCHEMA_VERSION:
        raise CohortPolicyError("unsupported cohort policy schema version")
    policy_value = artifact.get("policy")
    if not isinstance(policy_value, Mapping):
        raise CohortPolicyError("cohort policy must be an object")
    policy = _validated_policy(cast(Mapping[str, Any], policy_value))
    actual = _hash(policy)
    committed = _sha(artifact.get("policy_sha256"), "policy_sha256")
    if actual != committed:
        raise CohortPolicyError("cohort policy hash does not match its content")
    if expected_sha256 is not None and actual != _sha(
        expected_sha256, "expected_sha256"
    ):
        raise CohortPolicyError("cohort policy hash does not match expected hash")
    return actual


def write_cohort_policy(path: str | Path, artifact: Mapping[str, Any]) -> None:
    """Verify and atomically publish a canonical policy file."""

    verify_cohort_policy(artifact)
    target = Path(path)
    payload = f"{_canonical(artifact)}\n".encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(f"{target}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if target.exists():
            if target.read_bytes() != payload:
                raise CohortPolicyError(
                    "cohort policy already exists with different immutable content"
                )
            return
        _atomic_write(target, payload)
    finally:
        os.close(lock_fd)


def export_observation_manifest(
    *,
    store: CycleAcquisitionStore,
    policy_artifact: Mapping[str, Any],
    destination: str | Path,
) -> tuple[dict[str, Any], ...]:
    """Append newly published store snapshots without rewriting prior records."""

    policy_sha256 = verify_cohort_policy(policy_artifact)
    policy = cast(Mapping[str, Any], policy_artifact["policy"])
    cycle_hash = _sha(policy.get("cycle_acquisition_hash"), "cycle_acquisition_hash")
    if store.cycle_hash != cycle_hash:
        raise CohortPolicyError("cohort policy and cycle store hashes do not match")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(f"{path}.lock")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        existing = _read_manifest(path) if path.exists() else ()
        if existing:
            verify_observation_manifest(existing, policy_artifact=policy_artifact)
        else:
            header_payload: dict[str, Any] = {
                "schema_version": OBSERVATION_SCHEMA_VERSION,
                "record_type": "header",
                "sequence": 0,
                "cycle_id": policy["cycle_id"],
                "cycle_acquisition_hash": cycle_hash,
                "cohort_policy_sha256": policy_sha256,
                "previous_record_sha256": None,
            }
            existing = (_commit_record(header_payload),)
            _append_records(path, existing)

        snapshots = store.published_snapshots()
        _verify_existing_snapshot_prefix(store, existing, snapshots)
        recorded_ids = {
            cast(str, record["snapshot_id"])
            for record in existing
            if record.get("record_type") == "snapshot"
        }
        additions: list[dict[str, Any]] = []
        previous = cast(str, existing[-1]["record_sha256"])
        for snapshot in snapshots:
            if snapshot.snapshot_id in recorded_ids:
                continue
            manifest_sha256 = _verified_snapshot_manifest_hash(store, snapshot)
            payload = {
                "schema_version": OBSERVATION_SCHEMA_VERSION,
                "record_type": "snapshot",
                "sequence": len(existing) + len(additions),
                "cycle_id": policy["cycle_id"],
                "cycle_acquisition_hash": cycle_hash,
                "cohort_policy_sha256": policy_sha256,
                "snapshot_id": snapshot.snapshot_id,
                "batch_id": snapshot.batch_id,
                "batch_digest": _sha(
                    snapshot.manifest.get("batch_digest"), "batch_digest"
                ),
                "snapshot_manifest_sha256": manifest_sha256,
                "snapshot_created_at": snapshot.created_at,
                "previous_record_sha256": previous,
            }
            committed = _commit_record(payload)
            additions.append(committed)
            previous = cast(str, committed["record_sha256"])
        if additions:
            _append_records(path, additions)
        result = (*existing, *additions)
        verify_observation_manifest(result, policy_artifact=policy_artifact)
        return result
    finally:
        os.close(lock_fd)


def verify_observation_manifest(
    records: Sequence[Mapping[str, Any]],
    *,
    policy_artifact: Mapping[str, Any],
) -> str:
    """Verify an append-only manifest hash chain against the cohort policy."""

    if not records:
        raise CohortPolicyError("observation manifest is empty")
    policy_sha256 = verify_cohort_policy(policy_artifact)
    policy = cast(Mapping[str, Any], policy_artifact["policy"])
    cycle_id = _text(policy.get("cycle_id"), "cycle_id")
    cycle_hash = _sha(policy.get("cycle_acquisition_hash"), "cycle_acquisition_hash")
    seen_snapshots: set[str] = set()
    previous: str | None = None
    for expected_sequence, raw in enumerate(records):
        record = dict(raw)
        if record.get("schema_version") != OBSERVATION_SCHEMA_VERSION:
            raise CohortPolicyError("unsupported observation manifest schema")
        if record.get("sequence") != expected_sequence:
            raise CohortPolicyError("observation manifest sequence is not contiguous")
        expected_type = "header" if expected_sequence == 0 else "snapshot"
        if record.get("record_type") != expected_type:
            raise CohortPolicyError("observation manifest record type is invalid")
        common_keys = {
            "schema_version",
            "record_type",
            "sequence",
            "cycle_id",
            "cycle_acquisition_hash",
            "cohort_policy_sha256",
            "previous_record_sha256",
            "record_sha256",
        }
        snapshot_keys = {
            "snapshot_id",
            "batch_id",
            "batch_digest",
            "snapshot_manifest_sha256",
            "snapshot_created_at",
        }
        _exact_keys(
            record,
            common_keys if expected_type == "header" else common_keys | snapshot_keys,
            f"observation {expected_sequence}",
        )
        if record.get("cycle_id") != cycle_id:
            raise CohortPolicyError("observation manifest cycle_id mismatch")
        if record.get("cycle_acquisition_hash") != cycle_hash:
            raise CohortPolicyError("observation manifest cycle hash mismatch")
        if record.get("cohort_policy_sha256") != policy_sha256:
            raise CohortPolicyError("observation manifest policy hash mismatch")
        if record.get("previous_record_sha256") != previous:
            raise CohortPolicyError("observation manifest hash chain is broken")
        committed = _sha(record.get("record_sha256"), "record_sha256")
        payload = {
            key: value for key, value in record.items() if key != "record_sha256"
        }
        if _hash(payload) != committed:
            raise CohortPolicyError(
                "observation record hash does not match its content"
            )
        if expected_type == "snapshot":
            snapshot_id = _text(record.get("snapshot_id"), "snapshot_id")
            if snapshot_id in seen_snapshots:
                raise CohortPolicyError("observation manifest repeats a snapshot_id")
            seen_snapshots.add(snapshot_id)
            _text(record.get("batch_id"), "batch_id")
            _sha(record.get("batch_digest"), "batch_digest")
            _sha(record.get("snapshot_manifest_sha256"), "snapshot_manifest_sha256")
            _text(record.get("snapshot_created_at"), "snapshot_created_at")
        previous = committed
    assert previous is not None
    return previous


def read_observation_manifest(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read JSONL records without repairing or ignoring malformed tails."""

    return _read_manifest(Path(path))


def _validated_policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(raw, _POLICY_KEYS, "cohort policy")
    policy = dict(raw)
    _text(policy.get("cycle_id"), "cycle_id")
    _sha(policy.get("cycle_acquisition_hash"), "cycle_acquisition_hash")
    anchor = _date(policy.get("eligibility_anchor"), "eligibility_anchor")

    stop = _object(policy.get("stop_rule"), "stop_rule")
    _exact_keys(
        stop,
        {
            "mode",
            "target_clean_cases",
            "search_window_end",
            "stop_on_frontier_exhaustion",
            "stop_on_budget_headroom_exhaustion",
        },
        "stop_rule",
    )
    if stop.get("mode") not in {"deadline_only", "target_or_deadline"}:
        raise CohortPolicyError("stop_rule.mode is unsupported")
    target = _positive_int(stop.get("target_clean_cases"), "target_clean_cases")
    if _date(stop.get("search_window_end"), "search_window_end") < anchor:
        raise CohortPolicyError("search_window_end precedes eligibility_anchor")
    _true(stop.get("stop_on_frontier_exhaustion"), "stop_on_frontier_exhaustion")
    _true(
        stop.get("stop_on_budget_headroom_exhaustion"),
        "stop_on_budget_headroom_exhaustion",
    )

    window = _object(policy.get("window_policy"), "window_policy")
    _exact_keys(
        window,
        {"overlap_days", "backfill_late_indexed", "refresh_before_purchase"},
        "window_policy",
    )
    overlap = _nonnegative_int(window.get("overlap_days"), "overlap_days")
    if overlap > 31:
        raise CohortPolicyError("overlap_days cannot exceed 31")
    _true(window.get("backfill_late_indexed"), "backfill_late_indexed")
    _true(window.get("refresh_before_purchase"), "refresh_before_purchase")

    refresh = _object(policy.get("refresh_policy"), "refresh_policy")
    _exact_keys(
        refresh,
        {
            "immutable_reason_codes",
            "refreshable_reason_codes",
            "accepted_reason_codes",
            "newly_free_reason_codes",
            "transient_reason_codes",
            "evidence_precedence",
            "transition_semantics",
        },
        "refresh_policy",
    )
    taxonomy = cohort_reason_policy_taxonomy()
    groups: list[set[str]] = []
    for key, expected in taxonomy.items():
        supplied = _string_list(refresh.get(key), key)
        if supplied != expected:
            raise CohortPolicyError(
                f"{key} must exactly match the cycle-store reason taxonomy"
            )
        groups.append(set(supplied))
    if any(
        left & right
        for index, left in enumerate(groups)
        for right in groups[index + 1 :]
    ):
        raise CohortPolicyError("refresh reason-code classes must be disjoint")
    precedence = _object(refresh.get("evidence_precedence"), "evidence_precedence")
    precedence_order = (
        "transient",
        "excluded_refreshable",
        "accepted",
        "newly_free",
        "excluded_immutable",
    )
    _exact_keys(precedence, set(precedence_order), "evidence_precedence")
    priorities = [
        _nonnegative_int(precedence[key], f"evidence_precedence.{key}")
        for key in precedence_order
    ]
    if len(set(priorities)) != len(priorities):
        raise CohortPolicyError("evidence_precedence priorities must be unique")
    if priorities != sorted(priorities):
        raise CohortPolicyError(
            "evidence_precedence must increase from transient through "
            "excluded_immutable"
        )
    semantics = _object(refresh.get("transition_semantics"), "transition_semantics")
    _exact_keys(
        semantics,
        {
            "immutable_reconsideration",
            "transient_supersedes_evidenced",
            "higher_rank_supersedes_lower_rank",
            "latest_wins_equal_rank",
        },
        "transition_semantics",
    )
    if semantics.get("immutable_reconsideration") != "never":
        raise CohortPolicyError("immutable_reconsideration must be never")
    if semantics.get("transient_supersedes_evidenced") is not False:
        raise CohortPolicyError(
            "transient observations must not supersede evidenced state"
        )
    _true(
        semantics.get("higher_rank_supersedes_lower_rank"),
        "higher_rank_supersedes_lower_rank",
    )
    _true(semantics.get("latest_wins_equal_rank"), "latest_wins_equal_rank")

    packet = _object(policy.get("packet_completeness"), "packet_completeness")
    _exact_keys(
        packet,
        {
            "motion_or_combined_memorandum_required",
            "opposition_required_if_docketed",
            "reply_required",
        },
        "packet_completeness",
    )
    _true(
        packet.get("motion_or_combined_memorandum_required"),
        "motion_or_combined_memorandum_required",
    )
    _true(
        packet.get("opposition_required_if_docketed"), "opposition_required_if_docketed"
    )
    if packet.get("reply_required") is not False:
        raise CohortPolicyError("reply_required must be false")

    motion = _object(policy.get("target_motion"), "target_motion")
    _exact_keys(motion, {"selector", "exactly_one_per_candidate"}, "target_motion")
    if motion.get("selector") != "earliest_eligible_mtd_then_lowest_entry_number":
        raise CohortPolicyError("target_motion.selector is unsupported")
    _true(motion.get("exactly_one_per_candidate"), "exactly_one_per_candidate")

    purchase = _object(policy.get("purchase_policy"), "purchase_policy")
    _exact_keys(
        purchase,
        {
            "rule",
            "cycle_budget_usd",
            "max_per_case_usd",
            "reservation_headroom_required",
        },
        "purchase_policy",
    )
    if purchase.get("rule") != "buy_cheapest_complete":
        raise CohortPolicyError("purchase_policy.rule is unsupported")
    budget = _money(purchase.get("cycle_budget_usd"), "cycle_budget_usd")
    per_case = _money(purchase.get("max_per_case_usd"), "max_per_case_usd")
    if per_case > budget:
        raise CohortPolicyError("max_per_case_usd exceeds cycle_budget_usd")
    _true(
        purchase.get("reservation_headroom_required"), "reservation_headroom_required"
    )

    clearance = _object(policy.get("disclosure_clearance"), "disclosure_clearance")
    _exact_keys(
        clearance,
        {
            "all_documents_require_clearance",
            "unknown_or_unscannable",
            "replacement_rule",
        },
        "disclosure_clearance",
    )
    _true(
        clearance.get("all_documents_require_clearance"),
        "all_documents_require_clearance",
    )
    if clearance.get("unknown_or_unscannable") != "quarantine":
        raise CohortPolicyError("unknown_or_unscannable must be quarantine")
    if clearance.get("replacement_rule") != "next_cheapest_eligible_under_same_cap":
        raise CohortPolicyError("disclosure clearance replacement_rule is unsupported")

    reduced = _object(policy.get("reduced_n"), "reduced_n")
    _exact_keys(
        reduced,
        {"target_clean_cases", "claim_tiers", "below_minimum_action"},
        "reduced_n",
    )
    if _positive_int(reduced.get("target_clean_cases"), "target_clean_cases") != target:
        raise CohortPolicyError("reduced_n target must match stop_rule target")
    _validate_claim_tiers(reduced.get("claim_tiers"), target=target)
    if reduced.get("below_minimum_action") not in _TERMINAL_REDUCED_N_ACTIONS:
        raise CohortPolicyError("reduced_n.below_minimum_action is unsupported")
    return cast(dict[str, Any], json.loads(_canonical(policy)))


def _validate_claim_tiers(value: object, *, target: int) -> None:
    if not isinstance(value, list) or not value:
        raise CohortPolicyError("reduced_n.claim_tiers must be a non-empty list")
    tiers = cast(list[object], value)
    previous_maximum: int | None = None
    for index, tier_value in enumerate(tiers):
        tier = _object(tier_value, f"claim_tiers[{index}]")
        _exact_keys(
            tier,
            {
                "minimum_clean_cases",
                "maximum_clean_cases",
                "claim_class",
                "minimum_prediction_units",
                "insufficient_units_action",
            },
            f"claim_tiers[{index}]",
        )
        minimum = _positive_int(
            tier.get("minimum_clean_cases"),
            f"claim_tiers[{index}].minimum_clean_cases",
        )
        maximum = _positive_int(
            tier.get("maximum_clean_cases"),
            f"claim_tiers[{index}].maximum_clean_cases",
        )
        if maximum < minimum:
            raise CohortPolicyError(f"claim_tiers[{index}] has an inverted range")
        if previous_maximum is not None and minimum != previous_maximum + 1:
            raise CohortPolicyError(
                "reduced_n.claim_tiers must be ordered, contiguous, and non-overlapping"
            )
        claim_class = tier.get("claim_class")
        if claim_class not in _CLAIM_CLASS_RANK:
            raise CohortPolicyError(f"claim_tiers[{index}].claim_class is unsupported")
        threshold = tier.get("minimum_prediction_units")
        action = tier.get("insufficient_units_action")
        if threshold is None:
            if action is not None:
                raise CohortPolicyError(
                    "insufficient_units_action requires minimum_prediction_units"
                )
        else:
            _positive_int(threshold, f"claim_tiers[{index}].minimum_prediction_units")
            if action not in ({*_CLAIM_CLASS_RANK, *_TERMINAL_REDUCED_N_ACTIONS}):
                raise CohortPolicyError(
                    f"claim_tiers[{index}].insufficient_units_action is unsupported"
                )
            claim_rank = _CLAIM_CLASS_RANK[cast(str, claim_class)]
            action_rank = _CLAIM_CLASS_RANK.get(cast(str, action), -1)
            if action_rank >= claim_rank:
                raise CohortPolicyError(
                    "insufficient_units_action must be a lower claim class or "
                    "terminal action"
                )
        previous_maximum = maximum
    if previous_maximum != target:
        raise CohortPolicyError(
            "reduced_n.claim_tiers must terminate exactly at target_clean_cases"
        )


def _verified_snapshot_manifest_hash(
    store: CycleAcquisitionStore, snapshot: PublishedSnapshot
) -> str:
    verify_snapshot(
        snapshot.path,
        expected_cycle_hash=store.cycle_hash,
        expected_batch_digest=store.batch_digest(snapshot.batch_id),
    )
    path = snapshot.path / "manifest.json"
    payload = path.read_bytes()
    parsed = json.loads(payload)
    if parsed != snapshot.manifest:
        raise CohortPolicyError(
            f"snapshot manifest differs from cycle store: {snapshot.snapshot_id}"
        )
    return hashlib.sha256(payload).hexdigest()


def _verify_existing_snapshot_prefix(
    store: CycleAcquisitionStore,
    records: Sequence[Mapping[str, Any]],
    snapshots: Sequence[PublishedSnapshot],
) -> None:
    existing = [record for record in records if record.get("record_type") == "snapshot"]
    if [record.get("snapshot_id") for record in existing] != [
        snapshot.snapshot_id for snapshot in snapshots[: len(existing)]
    ]:
        raise CohortPolicyError(
            "existing observation snapshots are not a prefix of the cycle store"
        )
    for record, snapshot in zip(existing, snapshots, strict=False):
        manifest_sha256 = _verified_snapshot_manifest_hash(store, snapshot)
        expected = {
            "batch_id": snapshot.batch_id,
            "batch_digest": _sha(snapshot.manifest.get("batch_digest"), "batch_digest"),
            "snapshot_created_at": snapshot.created_at,
            "snapshot_manifest_sha256": manifest_sha256,
        }
        for field, value in expected.items():
            if record.get(field) != value:
                raise CohortPolicyError(
                    "existing observation no longer matches cycle store/disk "
                    f"commitment: {snapshot.snapshot_id} {field}"
                )


def _commit_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(payload)
    record["record_sha256"] = _hash(record)
    return record


def _append_records(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        for record in records:
            _write_all(fd, f"{_canonical(record)}\n".encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_manifest(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise CohortPolicyError(
                f"invalid observation JSON at line {line_number}: {error.msg}"
            ) from error
        if not isinstance(value, dict):
            raise CohortPolicyError(f"observation line {line_number} is not an object")
        records.append(cast(dict[str, Any], value))
    return tuple(records)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _exact_keys(
    record: Mapping[str, Any], expected: set[str] | frozenset[str], label: str
) -> None:
    actual = set(record)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        raise CohortPolicyError(
            f"{label} fields mismatch; missing={missing}, extra={extra}"
        )


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CohortPolicyError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CohortPolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if _SHA256.fullmatch(text) is None:
        raise CohortPolicyError(f"{label} must be a lowercase SHA-256")
    return text


def _date(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise CohortPolicyError(f"{label} must be an ISO date") from error
    if parsed.isoformat() != text:
        raise CohortPolicyError(f"{label} must use YYYY-MM-DD format")
    return parsed


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write while appending observation manifest")
        view = view[written:]


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise CohortPolicyError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: object, label: str) -> int:
    result = _nonnegative_int(value, label)
    if result == 0:
        raise CohortPolicyError(f"{label} must be positive")
    return result


def _true(value: object, label: str) -> None:
    if value is not True:
        raise CohortPolicyError(f"{label} must be true")


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CohortPolicyError(f"{label} must be a non-empty list")
    values: list[str] = []
    for item in cast(list[object], value):
        values.append(_text(item, label))
    if len(set(values)) != len(values):
        raise CohortPolicyError(f"{label} contains duplicates")
    return tuple(values)


def _money(value: object, label: str) -> Decimal:
    text = _text(value, label)
    try:
        amount = Decimal(text)
    except InvalidOperation as error:
        raise CohortPolicyError(f"{label} must be a decimal string") from error
    exponent = amount.as_tuple().exponent
    if (
        not amount.is_finite()
        or amount < 0
        or not isinstance(exponent, int)
        or exponent < -2
    ):
        raise CohortPolicyError(
            f"{label} must be non-negative with at most two decimals"
        )
    return amount

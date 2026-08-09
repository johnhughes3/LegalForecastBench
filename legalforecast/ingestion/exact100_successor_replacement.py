"""Pure exact-100 successor replacement projection.

This module deliberately stops at a provider-free projection.  Its public
projector accepts raw artifact bytes only when an opaque terminal authority has
already bound those exact bytes.  The authority is the integration seam for a
future authenticated terminal verifier; SHA-256 strings supplied by a caller
are evidence in the emitted result, never authority to promote a case.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes

JsonRecord = dict[str, Any]

RESULT_SCHEMA_VERSION = "legalforecast.exact100_successor_replacement.v1"
_TARGET_CASE_COUNT = 100
_AUTHORITY_SEAL = object()


class Exact100SuccessorReplacementError(ValueError):
    """Raised when a replacement projection is not exactly authenticated."""


class VerifiedExact100TerminalAuthority:
    """Opaque authority binding exact terminal, source, selection, and reserve bytes.

    A production verifier must mint this capability only after it has validated
    terminal provenance.  The projector checks the private seal and all four
    byte commitments before deriving any successor.  The explicitly named test
    issuer below validates shape only; it is not provenance verification and
    must not be used by an integration path.
    """

    __slots__ = (
        "_ranked_reserve_rows_sha256",
        "_seal",
        "_selected_rows_sha256",
        "_source_rows_sha256",
        "_terminal_exclusions_bytes",
    )

    def __init__(self) -> None:
        raise TypeError(
            "verified terminal authority is issued only by an authenticated verifier"
        )


@dataclass(frozen=True, slots=True)
class Exact100SuccessorReplacement:
    """Closed artifacts from one deterministic exact-100 replacement projection."""

    successor_selection: tuple[JsonRecord, ...]
    terminal_exclusions: tuple[JsonRecord, ...]
    promoted_reserves: tuple[JsonRecord, ...]
    result: JsonRecord

    @property
    def successor_selection_bytes(self) -> bytes:
        """Return the canonical JSONL successor selection."""

        return _jsonl_bytes(self.successor_selection)

    @property
    def terminal_exclusions_bytes(self) -> bytes:
        """Return the verifier-owned canonical terminal exclusion JSONL."""

        return _jsonl_bytes(self.terminal_exclusions)

    @property
    def promoted_reserves_bytes(self) -> bytes:
        """Return the canonical JSONL promoted source rows."""

        return _jsonl_bytes(self.promoted_reserves)

    @property
    def result_bytes(self) -> bytes:
        """Return the canonical result contract."""

        return _canonical_bytes(self.result)


def project_exact100_successor_replacement(
    *,
    terminal_authority: VerifiedExact100TerminalAuthority,
    source_rows_bytes: bytes,
    selected_rows_bytes: bytes,
    ranked_reserve_rows_bytes: bytes,
) -> Exact100SuccessorReplacement:
    """Replace selected terminal cases with the first ranked eligible reserves.

    The selection contains exactly 100 source rows.  Every terminal exclusion
    must name one selected candidate, and every reserve must name an unselected
    source candidate with consecutive ``reserve_rank`` values.  The authority
    binds the exact bytes before this function runs; the function has no file,
    provider, purchase, evaluation, freeze, or dispatch capability.
    """

    authority = _require_authority(terminal_authority)
    _require_bound_bytes(
        source_rows_bytes,
        authority._source_rows_sha256,  # pyright: ignore[reportPrivateUsage]
        "source rows",
    )
    _require_bound_bytes(
        selected_rows_bytes,
        authority._selected_rows_sha256,  # pyright: ignore[reportPrivateUsage]
        "selected rows",
    )
    _require_bound_bytes(
        ranked_reserve_rows_bytes,
        authority._ranked_reserve_rows_sha256,  # pyright: ignore[reportPrivateUsage]
        "ranked reserve rows",
    )

    source_rows = _jsonl_records(source_rows_bytes, "source rows")
    selected_rows = _jsonl_records(selected_rows_bytes, "selected rows")
    reserve_rows = _jsonl_records(ranked_reserve_rows_bytes, "ranked reserve rows")
    terminal_rows = _jsonl_records(
        authority._terminal_exclusions_bytes,  # pyright: ignore[reportPrivateUsage]
        "terminal exclusions",
        allow_empty=True,
    )

    source_by_id = _candidate_index(source_rows, "source rows")
    selected_ids = _verify_selected_rows(selected_rows, source_by_id)
    terminal_ids = _verify_terminal_rows(terminal_rows, selected_ids)
    ranked_reserves = _verify_ranked_reserves(
        reserve_rows, source_by_id=source_by_id, selected_ids=selected_ids
    )

    terminal_count = len(terminal_ids)
    if terminal_count > len(ranked_reserves):
        raise Exact100SuccessorReplacementError(
            "terminal exclusion count exceeds ranked reserve capacity"
        )
    promoted_ids = tuple(
        candidate_id for _rank, candidate_id in ranked_reserves[:terminal_count]
    )
    promoted_rows = tuple(
        dict(source_by_id[candidate_id]) for candidate_id in promoted_ids
    )
    terminal_id_set = set(terminal_ids)
    successor_rows = tuple(
        [
            row
            for row in selected_rows
            if _candidate_id(row, "selected row") not in terminal_id_set
        ]
        + list(promoted_rows)
    )
    successor_ids = _candidate_ids(successor_rows, "successor selection")
    if len(successor_ids) != _TARGET_CASE_COUNT:
        raise Exact100SuccessorReplacementError(
            "successor selection does not contain exactly 100 cases"
        )
    if len(set(successor_ids)) != len(successor_ids):
        raise Exact100SuccessorReplacementError(
            "successor selection contains duplicate candidates"
        )

    successor_bytes = _jsonl_bytes(successor_rows)
    terminal_bytes = authority._terminal_exclusions_bytes  # pyright: ignore[reportPrivateUsage]
    promoted_bytes = _jsonl_bytes(promoted_rows)
    result: JsonRecord = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "source_commitments": {
            "source_rows": _sha256(source_rows_bytes),
            "selected_rows": _sha256(selected_rows_bytes),
            "ranked_reserve_rows": _sha256(ranked_reserve_rows_bytes),
            "terminal_exclusions": _sha256(terminal_bytes),
        },
        "output_commitments": {
            "successor_selection": _sha256(successor_bytes),
            "promoted_reserves": _sha256(promoted_bytes),
        },
        "selected_case_count": _TARGET_CASE_COUNT,
        "terminal_exclusion_count": terminal_count,
        "promoted_reserve_count": len(promoted_rows),
        "promoted_candidate_ids": list(promoted_ids),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "provider_activity_permitted": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    result["result_sha256"] = replacement_result_digest(result)
    return Exact100SuccessorReplacement(
        successor_selection=successor_rows,
        terminal_exclusions=tuple(dict(row) for row in terminal_rows),
        promoted_reserves=promoted_rows,
        result=result,
    )


def replacement_result_digest(result: Mapping[str, object]) -> str:
    """Return the self-excluded digest for an emitted replacement result."""

    return _sha256(
        _canonical_bytes(
            {key: value for key, value in result.items() if key != "result_sha256"}
        )
    )


def verify_exact100_successor_replacement_result(result: Mapping[str, object]) -> None:
    """Raise unless *result* is a complete, self-consistent v1 contract."""

    expected_fields = {
        "schema_version",
        "source_commitments",
        "output_commitments",
        "selected_case_count",
        "terminal_exclusion_count",
        "promoted_reserve_count",
        "promoted_candidate_ids",
        "provider_activity_requested",
        "provider_activity_executed",
        "provider_activity_permitted",
        "paid_activity_requested",
        "paid_activity_executed",
        "paid_activity_permitted",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
        "result_sha256",
    }
    if (
        set(result) != expected_fields
        or result.get("schema_version") != RESULT_SCHEMA_VERSION
    ):
        raise Exact100SuccessorReplacementError(
            "replacement result has unsupported fields or schema"
        )
    if result.get("selected_case_count") != _TARGET_CASE_COUNT:
        raise Exact100SuccessorReplacementError(
            "replacement result selected case count is invalid"
        )
    terminal_count = _nonnegative_int(
        result.get("terminal_exclusion_count"), "terminal exclusion count"
    )
    promoted_count = _nonnegative_int(
        result.get("promoted_reserve_count"), "promoted reserve count"
    )
    promoted_ids = _string_list(
        result.get("promoted_candidate_ids"), "promoted candidate IDs"
    )
    if promoted_count != terminal_count or len(promoted_ids) != promoted_count:
        raise Exact100SuccessorReplacementError(
            "replacement result promotion counts do not reconcile"
        )
    if len(set(promoted_ids)) != len(promoted_ids):
        raise Exact100SuccessorReplacementError(
            "replacement result promoted candidate IDs are duplicated"
        )
    for commitment_name in ("source_commitments", "output_commitments"):
        commitments = result.get(commitment_name)
        if not isinstance(commitments, Mapping) or not commitments:
            raise Exact100SuccessorReplacementError(
                f"replacement result {commitment_name} are malformed"
            )
        typed_commitments = cast(Mapping[str, object], commitments)
        if any(not _is_sha256(value) for value in typed_commitments.values()):
            raise Exact100SuccessorReplacementError(
                f"replacement result {commitment_name} contain malformed digests"
            )
    flags = (
        "provider_activity_requested",
        "provider_activity_executed",
        "provider_activity_permitted",
        "paid_activity_requested",
        "paid_activity_executed",
        "paid_activity_permitted",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    )
    if any(result.get(flag) is not False for flag in flags):
        raise Exact100SuccessorReplacementError(
            "replacement result grants unavailable authority"
        )
    if result.get("result_sha256") != replacement_result_digest(result):
        raise Exact100SuccessorReplacementError(
            "replacement result digest does not match its self-excluded preimage"
        )


def issue_verified_terminal_authority_for_testing(
    *,
    source_rows_bytes: bytes,
    selected_rows_bytes: bytes,
    ranked_reserve_rows_bytes: bytes,
    terminal_exclusions_bytes: bytes,
) -> VerifiedExact100TerminalAuthority:
    """Issue a shape-validated authority for unit tests only.

    This helper deliberately provides no provenance verification.  Its name is
    part of the proof boundary: it may create fixtures, never production
    authority.  A real verifier must authenticate terminal evidence before
    minting the same sealed capability through its own internal integration seam.
    """

    source_rows = _jsonl_records(source_rows_bytes, "source rows")
    selected_rows = _jsonl_records(selected_rows_bytes, "selected rows")
    reserve_rows = _jsonl_records(ranked_reserve_rows_bytes, "ranked reserve rows")
    terminal_rows = _jsonl_records(
        terminal_exclusions_bytes, "terminal exclusions", allow_empty=True
    )
    source_by_id = _candidate_index(source_rows, "source rows")
    selected_ids = _verify_selected_rows(selected_rows, source_by_id)
    _verify_terminal_rows(terminal_rows, selected_ids)
    _verify_ranked_reserves(
        reserve_rows, source_by_id=source_by_id, selected_ids=selected_ids
    )

    authority = object.__new__(VerifiedExact100TerminalAuthority)
    authority._source_rows_sha256 = _sha256(source_rows_bytes)  # pyright: ignore[reportPrivateUsage]
    authority._selected_rows_sha256 = _sha256(selected_rows_bytes)  # pyright: ignore[reportPrivateUsage]
    authority._ranked_reserve_rows_sha256 = _sha256(  # pyright: ignore[reportPrivateUsage]
        ranked_reserve_rows_bytes
    )
    authority._terminal_exclusions_bytes = terminal_exclusions_bytes  # pyright: ignore[reportPrivateUsage]
    authority._seal = _AUTHORITY_SEAL  # pyright: ignore[reportPrivateUsage]
    return authority


def _require_authority(
    value: VerifiedExact100TerminalAuthority,
) -> VerifiedExact100TerminalAuthority:
    if (
        type(value) is not VerifiedExact100TerminalAuthority
        or getattr(value, "_seal", None) is not _AUTHORITY_SEAL
    ):
        raise Exact100SuccessorReplacementError(
            "terminal authority was not issued by an authenticated verifier"
        )
    return value


def _require_bound_bytes(payload: bytes, expected: str, label: str) -> None:
    if not hmac.compare_digest(_sha256(payload), expected):
        raise Exact100SuccessorReplacementError(
            f"{label} differ from verified terminal authority"
        )


def _verify_selected_rows(
    selected_rows: Sequence[Mapping[str, Any]], source_by_id: Mapping[str, JsonRecord]
) -> tuple[str, ...]:
    selected_ids = _candidate_ids(selected_rows, "selected rows")
    if len(selected_ids) != _TARGET_CASE_COUNT:
        raise Exact100SuccessorReplacementError(
            "selected rows do not contain exactly 100 cases"
        )
    if len(set(selected_ids)) != len(selected_ids):
        raise Exact100SuccessorReplacementError(
            "selected rows contain duplicate candidates"
        )
    for row, candidate_id in zip(selected_rows, selected_ids, strict=True):
        source_row = source_by_id.get(candidate_id)
        if source_row is None:
            raise Exact100SuccessorReplacementError(
                f"selected candidate is absent from source rows: {candidate_id}"
            )
        if dict(row) != source_row:
            raise Exact100SuccessorReplacementError(
                f"selected row differs from authenticated source row: {candidate_id}"
            )
    return selected_ids


def _verify_terminal_rows(
    terminal_rows: Sequence[Mapping[str, Any]], selected_ids: Sequence[str]
) -> tuple[str, ...]:
    terminal_ids = _candidate_ids(terminal_rows, "terminal exclusions")
    if len(set(terminal_ids)) != len(terminal_ids):
        raise Exact100SuccessorReplacementError(
            "terminal exclusions contain duplicate candidates"
        )
    unselected = sorted(set(terminal_ids) - set(selected_ids))
    if unselected:
        raise Exact100SuccessorReplacementError(
            "terminal exclusion is not selected: " + ", ".join(unselected)
        )
    return terminal_ids


def _verify_ranked_reserves(
    reserve_rows: Sequence[Mapping[str, Any]],
    *,
    source_by_id: Mapping[str, JsonRecord],
    selected_ids: Sequence[str],
) -> tuple[tuple[int, str], ...]:
    ranked: list[tuple[int, str]] = []
    reserve_ids: set[str] = set()
    selected_id_set = set(selected_ids)
    for row in reserve_rows:
        candidate_id = _candidate_id(row, "ranked reserve row")
        if candidate_id in reserve_ids:
            raise Exact100SuccessorReplacementError(
                "ranked reserve rows contain duplicate candidates"
            )
        if candidate_id in selected_id_set:
            raise Exact100SuccessorReplacementError(
                "ranked reserve candidate is already selected"
            )
        if candidate_id not in source_by_id:
            raise Exact100SuccessorReplacementError(
                f"ranked reserve candidate is absent from source rows: {candidate_id}"
            )
        rank = _positive_int(row.get("reserve_rank"), "reserve rank")
        ranked.append((rank, candidate_id))
        reserve_ids.add(candidate_id)
    ranked.sort()
    if [rank for rank, _candidate_id in ranked] != list(range(1, len(ranked) + 1)):
        raise Exact100SuccessorReplacementError(
            "ranked reserve rows have skipped or duplicate reserve ranks"
        )
    return tuple(ranked)


def _jsonl_records(
    payload: bytes, label: str, *, allow_empty: bool = False
) -> list[JsonRecord]:
    if not payload and not allow_empty:
        raise Exact100SuccessorReplacementError(f"{label} are empty or not bytes")
    records: list[JsonRecord] = []
    for line_number, line in enumerate(payload.splitlines(keepends=True), start=1):
        if not line.endswith(b"\n") or not line[:-1]:
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is not canonical JSONL"
            )
        try:
            decoded = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is invalid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is not an object"
            )
        record = cast(JsonRecord, decoded)
        if _canonical_bytes(record) != line:
            raise Exact100SuccessorReplacementError(
                f"{label} line {line_number} is not canonical JSONL"
            )
        records.append(record)
    return records


def _candidate_index(
    records: Sequence[Mapping[str, Any]], label: str
) -> dict[str, JsonRecord]:
    output: dict[str, JsonRecord] = {}
    for record in records:
        candidate_id = _candidate_id(record, label)
        if candidate_id in output:
            raise Exact100SuccessorReplacementError(
                f"{label} contain duplicate candidates"
            )
        output[candidate_id] = dict(record)
    return output


def _candidate_ids(records: Sequence[Mapping[str, Any]], label: str) -> tuple[str, ...]:
    return tuple(_candidate_id(record, label) for record in records)


def _candidate_id(record: Mapping[str, Any], label: str) -> str:
    value = record.get("candidate_id")
    if not isinstance(value, str) or not value:
        raise Exact100SuccessorReplacementError(f"{label} lack candidate_id")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Exact100SuccessorReplacementError(f"{label} is invalid")
    return value


def _positive_int(value: object, label: str) -> int:
    parsed = _nonnegative_int(value, label)
    if parsed == 0:
        raise Exact100SuccessorReplacementError(f"{label} is invalid")
    return parsed


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise Exact100SuccessorReplacementError(f"{label} are malformed")
    values = cast(list[object], value)
    if any(not isinstance(item, str) or not item for item in values):
        raise Exact100SuccessorReplacementError(f"{label} are malformed")
    return tuple(cast(str, item) for item in values)


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _canonical_bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementError,
        error_message="replacement artifact is not canonicalizable",
    )


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical_bytes(record) for record in records)

"""Account for sidecar egress evidence; empty or missing is not clean.

The sidecar writes a JSON object with ``allowed_hosts``, ``refused``, and
``decision_count``.  Defaulting any of those to an empty list made a missing
file look like a successful fenced run.  An accounted record with
``decision_count == 0`` is still not clean: that is the absence of
observations, not proof the fence held.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast


class EgressEvidenceError(ValueError):
    """Raised when egress evidence is missing, empty-keyed, or malformed."""


@dataclass(frozen=True, slots=True)
class AccountedEgress:
    """One sidecar evidence record after the required fields are present."""

    allowed_hosts: tuple[str, ...]
    refused: tuple[Mapping[str, Any], ...]
    decision_count: int

    @property
    def empty(self) -> bool:
        """Return whether the proxy recorded no decisions at all."""

        return self.decision_count == 0


def is_clean_egress(accounted: AccountedEgress | None) -> bool:
    """Return whether egress evidence can be treated as a clean observation.

    Missing evidence is not clean.  An accounted record with no decisions is
    not clean either.
    """

    if accounted is None or accounted.empty:
        return False
    return True


def parse_egress_evidence(payload: object) -> AccountedEgress:
    """Return accounted evidence, or refuse to treat a hole as a clean fence."""

    if not isinstance(payload, Mapping):
        raise EgressEvidenceError(
            "egress evidence must be a JSON object; empty or missing egress "
            "evidence is not treated as clean"
        )
    record = cast(Mapping[str, object], payload)
    required = ("allowed_hosts", "refused", "decision_count")
    if any(field not in record for field in required):
        raise EgressEvidenceError(
            "egress evidence is missing required fields; empty or missing "
            "egress evidence is not treated as clean"
        )
    decision_count_raw = record["decision_count"]
    if isinstance(decision_count_raw, bool) or not isinstance(decision_count_raw, int):
        raise EgressEvidenceError("decision_count must be an integer")
    decision_count = decision_count_raw
    if decision_count < 0:
        raise EgressEvidenceError("decision_count must not be negative")
    accounted = AccountedEgress(
        allowed_hosts=_string_tuple(record["allowed_hosts"], "allowed_hosts"),
        refused=_refused_tuple(record["refused"]),
        decision_count=decision_count,
    )
    if accounted.empty and (accounted.allowed_hosts or accounted.refused):
        raise EgressEvidenceError(
            "decision_count is 0 but decisions are recorded; empty or missing "
            "egress evidence is not treated as clean"
        )
    minimum_decisions = len(accounted.allowed_hosts) + len(accounted.refused)
    if decision_count < minimum_decisions:
        raise EgressEvidenceError(
            "decision_count is smaller than the recorded allowed and refused decisions"
        )
    return accounted


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise EgressEvidenceError(f"{field_name} must be a list")
    hosts: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise EgressEvidenceError(f"{field_name} must be a list of strings")
        if not item:
            raise EgressEvidenceError(f"{field_name} must not contain empty hosts")
        hosts.append(item)
    return tuple(hosts)


def _refused_tuple(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise EgressEvidenceError("refused must be a list")
    records: list[Mapping[str, Any]] = []
    for item in cast(list[object], value):
        if not isinstance(item, Mapping):
            raise EgressEvidenceError("refused entries must be objects")
        record = dict(cast(Mapping[str, Any], item))
        required = {"host", "port", "reason"}
        allowed = required | {"host_redacted"}
        if not required.issubset(record):
            raise EgressEvidenceError("refused entries require host, port, and reason")
        if set(record) - allowed:
            raise EgressEvidenceError("refused entries contain unknown fields")
        host = record["host"]
        port = record["port"]
        reason = record["reason"]
        if not isinstance(host, str):
            raise EgressEvidenceError("refused host must be a string")
        if isinstance(port, bool) or not isinstance(port, int):
            raise EgressEvidenceError("refused port must be an integer")
        if not isinstance(reason, str) or not reason:
            raise EgressEvidenceError("refused reason must be a non-empty string")
        redacted = record.get("host_redacted")
        if redacted is not None and redacted is not True:
            raise EgressEvidenceError("refused host_redacted must be true when present")
        if redacted is True:
            if not host or not 0 <= port <= 65535:
                raise EgressEvidenceError(
                    "refused redacted host must be non-empty with a valid port"
                )
        elif host:
            if not 1 <= port <= 65535:
                raise EgressEvidenceError("refused host has an invalid port")
        elif port != 0:
            raise EgressEvidenceError(
                "refused empty host is valid only for a malformed request at port 0"
            )
        records.append(record)
    return tuple(records)

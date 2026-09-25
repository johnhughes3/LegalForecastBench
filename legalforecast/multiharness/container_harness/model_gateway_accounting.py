"""Concurrent request accounting and durable per-run usage evidence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .model_gateway_types import (
    GatewayBudgetExceeded,
    GatewayEvidenceError,
    GatewayUsageSnapshot,
    ObservedUsage,
    Reservation,
)

if TYPE_CHECKING:
    from .model_gateway_protocol import ModelGatewayPolicy


@dataclass(slots=True)
class GatewayUsage:
    """Account reservations and observed usage across concurrent requests."""

    evidence_path: Path | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _request_count: int = 0
    _input_tokens: int = 0
    _output_tokens: int = 0
    _reserved_input_tokens: int = 0
    _reserved_output_tokens: int = 0
    _rejected_count: int = 0
    _observed_input_tokens: int = 0
    _observed_output_tokens: int = 0
    _observed_input_known: bool = True
    _observed_output_known: bool = True
    _observed_input_seen: bool = False
    _observed_output_seen: bool = False

    def __post_init__(self) -> None:
        if self.evidence_path is not None:
            _validate_evidence_path(self.evidence_path)
            with self._lock:
                self._write_evidence_locked()

    def reserve(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        policy: ModelGatewayPolicy,
    ) -> Reservation:
        """Reserve worst-case input/output usage before contacting upstream."""

        with self._lock:
            if self._request_count >= policy.max_requests:
                self._rejected_count += 1
                self._write_evidence_locked()
                raise GatewayBudgetExceeded("request budget exhausted")
            if (
                self._input_tokens + self._reserved_input_tokens + input_tokens
                > policy.max_total_input_tokens
            ):
                self._rejected_count += 1
                self._write_evidence_locked()
                raise GatewayBudgetExceeded("input-token budget exhausted")
            if (
                self._output_tokens + self._reserved_output_tokens + output_tokens
                > policy.max_total_output_tokens
            ):
                self._rejected_count += 1
                self._write_evidence_locked()
                raise GatewayBudgetExceeded("output-token budget exhausted")
            self._request_count += 1
            self._reserved_input_tokens += input_tokens
            self._reserved_output_tokens += output_tokens
            self._write_evidence_locked()
            return Reservation(input_tokens, output_tokens)

    def settle(
        self,
        reservation: Reservation,
        observed: ObservedUsage | None,
    ) -> None:
        """Replace a reservation, conservatively if upstream usage is absent."""

        input_tokens = (
            observed.input_tokens
            if observed is not None and observed.input_tokens is not None
            else reservation.input_tokens
        )
        output_tokens = (
            observed.output_tokens
            if observed is not None and observed.output_tokens is not None
            else reservation.output_tokens
        )
        with self._lock:
            self._reserved_input_tokens -= reservation.input_tokens
            self._reserved_output_tokens -= reservation.output_tokens
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            if observed is None:
                self._observed_input_seen = True
                self._observed_output_seen = True
                self._observed_input_known = False
                self._observed_output_known = False
            else:
                if observed.input_tokens is None:
                    self._observed_input_seen = True
                    self._observed_input_known = False
                elif self._observed_input_known:
                    self._observed_input_seen = True
                    self._observed_input_tokens += observed.input_tokens
                if observed.output_tokens is None:
                    self._observed_output_seen = True
                    self._observed_output_known = False
                elif self._observed_output_known:
                    self._observed_output_seen = True
                    self._observed_output_tokens += observed.output_tokens
            self._write_evidence_locked()

    def snapshot(self) -> GatewayUsageSnapshot:
        """Return a consistent usage snapshot."""

        with self._lock:
            return self._snapshot_locked()

    def _write_evidence_locked(self) -> None:
        if self.evidence_path is None:
            return
        snapshot = self._snapshot_locked()
        payload = {
            "schema_version": 1,
            "request_count": snapshot.request_count,
            "rejected_count": snapshot.rejected_count,
            "accounted_input_tokens": snapshot.input_tokens,
            "accounted_output_tokens": snapshot.output_tokens,
            "reserved_input_tokens": snapshot.reserved_input_tokens,
            "reserved_output_tokens": snapshot.reserved_output_tokens,
            "observed_input_tokens": snapshot.observed_input_tokens,
            "observed_output_tokens": snapshot.observed_output_tokens,
        }
        temporary_path: str | None = None
        try:
            file_descriptor, temporary_path = tempfile.mkstemp(
                prefix=f".{self.evidence_path.name}.",
                dir=self.evidence_path.parent,
            )
            os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as evidence:
                evidence.write(
                    json.dumps(payload, sort_keys=True, separators=(",", ":"))
                )
                evidence.write("\n")
                evidence.flush()
                os.fsync(evidence.fileno())
            os.replace(temporary_path, self.evidence_path)
            temporary_path = None
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            raise GatewayEvidenceError("usage evidence is unavailable") from exc
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

    def _snapshot_locked(self) -> GatewayUsageSnapshot:
        return GatewayUsageSnapshot(
            request_count=self._request_count,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            reserved_input_tokens=self._reserved_input_tokens,
            reserved_output_tokens=self._reserved_output_tokens,
            rejected_count=self._rejected_count,
            observed_input_tokens=(
                self._observed_input_tokens
                if self._observed_input_seen and self._observed_input_known
                else None
            ),
            observed_output_tokens=(
                self._observed_output_tokens
                if self._observed_output_seen and self._observed_output_known
                else None
            ),
        )


def _validate_evidence_path(path: Path) -> None:
    if not path.is_absolute():
        raise GatewayEvidenceError("usage evidence path must be absolute")
    if path.is_symlink():
        raise GatewayEvidenceError("usage evidence path must not be a symlink")
    if path.exists():
        try:
            mode = path.stat().st_mode & 0o777
        except OSError as exc:
            raise GatewayEvidenceError(
                "usage evidence path cannot be inspected"
            ) from exc
        if not path.is_file():
            raise GatewayEvidenceError("usage evidence path is not a regular file")
        if mode & 0o077:
            raise GatewayEvidenceError("usage evidence file must be owner-only")
    if not path.parent.is_dir():
        raise GatewayEvidenceError("usage evidence parent directory is unavailable")


__all__ = ["GatewayUsage"]

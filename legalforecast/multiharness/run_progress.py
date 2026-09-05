"""Durable progress journal for community harness interrupt and resume.

This sidecar is not a frozen Cycle 1 authenticated contract. It exists so a
contributor can stop a run and continue it later without re-spending completed
tasks or silently swapping solver, config, or policy identity.
"""

from __future__ import annotations

import hashlib
import json
import signal
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from legalforecast._json_io import read_json_object_safe, write_json_object_safe
from legalforecast.multiharness.command_adapter import CommandAdapterCancelled
from legalforecast.multiharness.identity import derive_solver_identity
from legalforecast.multiharness.validation import (
    require_mapping,
    require_schema_version,
    require_sequence,
    require_str,
    validate_sha256,
)

PROGRESS_JOURNAL_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative progress-journal sidecar
    "legalforecast.multiharness.run_progress_journal.v1"
)
JOURNAL_FILENAME = "run-progress.json"
COVERAGE_FULL = "full"
COVERAGE_SCOPED = "scoped"
CLAIM_FULL = "full"
CLAIM_SCOPED = "scoped"
CLAIM_PARTIAL = "partial"
JOURNAL_IN_PROGRESS = "in_progress"
JOURNAL_INTERRUPTED = "interrupted"
JOURNAL_COMPLETED = "completed"
SCOPED_LABEL_PREFIX = "scoped:"


class ResumeRefusedError(ValueError):
    """Resume would corrupt identity, re-spend, or trust a damaged journal."""


@dataclass(frozen=True, slots=True)
class IdentityBinding:
    """Run-level solver, config, policy, and selection identity for resume."""

    solver_identity_key: str
    config_sha256: str
    runtime_policy_sha256: str
    selection_sha256: str

    def to_record(self) -> dict[str, str]:
        return {
            "solver_identity_key": self.solver_identity_key,
            "config_sha256": self.config_sha256,
            "runtime_policy_sha256": self.runtime_policy_sha256,
            "selection_sha256": self.selection_sha256,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        return cls(
            solver_identity_key=require_str(record, "solver_identity_key"),
            config_sha256=require_str(record, "config_sha256"),
            runtime_policy_sha256=require_str(record, "runtime_policy_sha256"),
            selection_sha256=require_str(record, "selection_sha256"),
        )


@dataclass(frozen=True, slots=True)
class RunProgressJournal:
    """Incremental durable state written after every completed or interrupted row."""

    run_id: str
    identity: IdentityBinding
    coverage_kind: str
    selection_label: str
    completed_row_ids: tuple[str, ...]
    status: str
    interrupted_row_id: str | None = None
    journal_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ResumeRefusedError("progress journal run_id is empty")
        if self.coverage_kind not in {COVERAGE_FULL, COVERAGE_SCOPED}:
            raise ResumeRefusedError("progress journal coverage_kind is invalid")
        if self.status not in {
            JOURNAL_IN_PROGRESS,
            JOURNAL_INTERRUPTED,
            JOURNAL_COMPLETED,
        }:
            raise ResumeRefusedError("progress journal status is invalid")
        if not self.selection_label.strip():
            raise ResumeRefusedError("progress journal selection_label is empty")
        expected = _journal_sha256(self._hash_payload())
        if self.journal_sha256 and self.journal_sha256 != expected:
            raise ResumeRefusedError("progress journal digest does not match contents")
        object.__setattr__(self, "journal_sha256", expected)

    def _hash_payload(self) -> dict[str, Any]:
        return {
            "completed_row_ids": list(self.completed_row_ids),
            "coverage_kind": self.coverage_kind,
            "identity": self.identity.to_record(),
            "interrupted_row_id": self.interrupted_row_id,
            "run_id": self.run_id,
            "schema_version": PROGRESS_JOURNAL_SCHEMA_VERSION,
            "selection_label": self.selection_label,
            "status": self.status,
        }

    def to_record(self) -> dict[str, Any]:
        return {**self._hash_payload(), "journal_sha256": self.journal_sha256}

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Self:
        try:
            require_schema_version(record, PROGRESS_JOURNAL_SCHEMA_VERSION)
            identity = IdentityBinding.from_record(require_mapping(record, "identity"))
            completed = tuple(
                _require_token(item, "completed_row_ids")
                for item in require_sequence(record, "completed_row_ids")
            )
            interrupted = record.get("interrupted_row_id")
            if interrupted is not None:
                interrupted = _require_token(interrupted, "interrupted_row_id")
            return cls(
                run_id=require_str(record, "run_id"),
                identity=identity,
                coverage_kind=require_str(record, "coverage_kind"),
                selection_label=require_str(record, "selection_label"),
                completed_row_ids=completed,
                status=require_str(record, "status"),
                interrupted_row_id=interrupted,
                journal_sha256=require_str(record, "journal_sha256"),
            )
        except (TypeError, ValueError) as exc:
            raise ResumeRefusedError(
                "progress journal is corrupt or unreadable; resume refused"
            ) from exc

    def with_completed_row(self, row_id: str) -> Self:
        completed = tuple(dict.fromkeys((*self.completed_row_ids, row_id)))
        status = (
            JOURNAL_COMPLETED
            if self.status == JOURNAL_COMPLETED
            else JOURNAL_IN_PROGRESS
        )
        interrupted_row_id = (
            None if self.interrupted_row_id == row_id else self.interrupted_row_id
        )
        return type(self)(
            run_id=self.run_id,
            identity=self.identity,
            coverage_kind=self.coverage_kind,
            selection_label=self.selection_label,
            completed_row_ids=completed,
            status=status,
            interrupted_row_id=interrupted_row_id,
        )

    def with_interrupted_row(self, row_id: str) -> Self:
        return type(self)(
            run_id=self.run_id,
            identity=self.identity,
            coverage_kind=self.coverage_kind,
            selection_label=self.selection_label,
            completed_row_ids=self.completed_row_ids,
            status=JOURNAL_INTERRUPTED,
            interrupted_row_id=row_id,
        )

    def mark_completed(self) -> Self:
        return type(self)(
            run_id=self.run_id,
            identity=self.identity,
            coverage_kind=self.coverage_kind,
            selection_label=self.selection_label,
            completed_row_ids=self.completed_row_ids,
            status=JOURNAL_COMPLETED,
            interrupted_row_id=None,
        )

    def mark_stopped(self) -> Self:
        return type(self)(
            run_id=self.run_id,
            identity=self.identity,
            coverage_kind=self.coverage_kind,
            selection_label=self.selection_label,
            completed_row_ids=self.completed_row_ids,
            status=JOURNAL_INTERRUPTED,
            interrupted_row_id=self.interrupted_row_id,
        )

    def claim_kind(self) -> str:
        if self.status == JOURNAL_INTERRUPTED:
            return CLAIM_PARTIAL
        if self.coverage_kind == COVERAGE_SCOPED:
            return CLAIM_SCOPED
        return CLAIM_FULL


def bind_run_identity(
    *,
    adapter_ids: tuple[str, ...],
    adapter_versions: tuple[str, ...],
    model_keys: tuple[str, ...],
    config_record: Mapping[str, Any],
    policy_record: Mapping[str, Any],
    policy_sha256: str | None,
    selection_sha256: str,
) -> IdentityBinding:
    """Derive the run-level identity used as the resume refusal predicate."""

    settings_payload = {
        "adapter_ids": list(adapter_ids),
        "adapter_versions": list(adapter_versions),
        "model_keys": list(model_keys),
    }
    primary_adapter = adapter_ids[0] if adapter_ids else "multiharness"
    primary_model = model_keys[0] if model_keys else "unspecified"
    solver = derive_solver_identity(
        provider=primary_adapter,
        requested_model=primary_model,
        settings_sha256=_prefixed_sha256(settings_payload),
        served_model=None,
    )
    config_without_policy = {
        key: value for key, value in config_record.items() if key != "sandbox_policy"
    }
    runtime_policy = policy_sha256 or _prefixed_sha256(dict(policy_record))
    return IdentityBinding(
        solver_identity_key=solver.key,
        config_sha256=_prefixed_sha256(config_without_policy),
        runtime_policy_sha256=runtime_policy
        if runtime_policy.startswith("sha256:")
        else f"sha256:{runtime_policy}",
        selection_sha256=_prefixed_if_needed(selection_sha256),
    )


def refuse_resume_identity_drift(
    *,
    prior: IdentityBinding,
    requested: IdentityBinding,
) -> None:
    """Refuse resume when solver, config, policy, or selection identity drifted.

    Task, solver, config, and policy crossing uses the same predicate as
    ``validate_resume_binding`` in ``identity.py``. This run-level check also
    names selection drift, which that per-row helper does not see.
    """

    if requested.selection_sha256 != prior.selection_sha256:
        raise ResumeRefusedError(
            "resume refused: selection identity drifted "
            f"(prior {prior.selection_sha256} vs requested "
            f"{requested.selection_sha256})"
        )
    if requested.solver_identity_key != prior.solver_identity_key:
        raise ResumeRefusedError(
            "resume refused: solver identity drifted "
            f"(prior {prior.solver_identity_key} vs requested "
            f"{requested.solver_identity_key})"
        )
    if requested.config_sha256 != prior.config_sha256:
        raise ResumeRefusedError(
            "resume refused: config identity drifted "
            f"(prior {prior.config_sha256} vs requested {requested.config_sha256})"
        )
    if requested.runtime_policy_sha256 != prior.runtime_policy_sha256:
        raise ResumeRefusedError(
            "resume refused: runtime policy identity drifted "
            f"(prior {prior.runtime_policy_sha256} vs requested "
            f"{requested.runtime_policy_sha256})"
        )


def load_progress_journal(output_dir: Path) -> RunProgressJournal | None:
    """Load a journal if present. Corrupt bytes refuse resume rather than skip."""

    path = output_dir / JOURNAL_FILENAME
    if not path.is_file():
        return None
    try:
        record = read_json_object_safe(
            path,
            error_factory=ResumeRefusedError,
            missing_message=lambda item: f"progress journal does not exist: {item}",
            non_object_message=lambda item: (
                f"progress journal must be a JSON object: {item}"
            ),
        )
        return RunProgressJournal.from_record(record)
    except ResumeRefusedError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ResumeRefusedError(
            "progress journal is corrupt or unreadable; resume refused"
        ) from exc


def write_progress_journal(output_dir: Path, journal: RunProgressJournal) -> None:
    """Atomically replace the progress journal after a durable row event."""

    path = output_dir / JOURNAL_FILENAME
    temporary = path.with_name(f".{path.name}.tmp")
    write_json_object_safe(temporary, journal.to_record())
    temporary.replace(path)


JournalOwner = tuple[Path, RunProgressJournal]


@dataclass(slots=True)
class RunSignalBoundary:
    """One continuous signal boundary with late-bound journal ownership."""

    requested: bool = False
    journal_owner: JournalOwner | None = None

    def __call__(self) -> bool:
        return self.requested

    def adopt(self, output_dir: Path, journal: RunProgressJournal) -> None:
        self.journal_owner = (output_dir, journal)


@contextmanager
def signal_boundary() -> Generator[RunSignalBoundary]:
    """Convert termination signals across one optionally adopted journal."""

    boundary = RunSignalBoundary()
    if threading.current_thread() is not threading.main_thread():
        yield boundary
        return

    previous = {
        requested_signal: signal.getsignal(requested_signal)
        for requested_signal in (signal.SIGINT, signal.SIGTERM)
    }

    def mark_stop(requested_signal: int, frame: object) -> None:
        del requested_signal, frame
        boundary.requested = True
        raise KeyboardInterrupt

    for requested_signal in previous:
        signal.signal(requested_signal, mark_stop)
    try:
        yield boundary
    except (CommandAdapterCancelled, KeyboardInterrupt):
        _mark_owned_journal_stopped(boundary.journal_owner)
        raise CommandAdapterCancelled("multi-harness startup was cancelled") from None
    finally:
        for requested_signal, previous_handler in previous.items():
            signal.signal(requested_signal, previous_handler)


def _mark_owned_journal_stopped(journal_owner: JournalOwner | None) -> None:
    if journal_owner is None:
        return
    output_dir, owned = journal_owner
    current = load_progress_journal(output_dir)
    if current is None:
        return
    if current.run_id == owned.run_id and current.identity == owned.identity:
        write_progress_journal(output_dir, current.mark_stopped())


def scoped_selection_label(label: str) -> str:
    """Prefix a non-full selection so claims cannot look like a full suite."""

    trimmed = label.strip()
    if not trimmed:
        return "scoped"
    if trimmed == COVERAGE_FULL:
        return COVERAGE_SCOPED
    if trimmed == COVERAGE_SCOPED or trimmed.startswith(SCOPED_LABEL_PREFIX):
        return trimmed
    return f"{SCOPED_LABEL_PREFIX}{trimmed}"


def is_scoped_label(label: str) -> bool:
    return any(
        part == COVERAGE_SCOPED or part.startswith(SCOPED_LABEL_PREFIX)
        for part in label.strip().split("+")
    )


def is_partial_label(label: str) -> bool:
    return any(
        part == CLAIM_PARTIAL or part.startswith(f"{CLAIM_PARTIAL}:")
        for part in label.strip().split("+")
    )


def require_coverage_kind(value: object) -> str:
    if not isinstance(value, str) or value not in {COVERAGE_FULL, COVERAGE_SCOPED}:
        raise ValueError("coverage_kind must be 'full' or 'scoped'")
    return value


def require_honest_coverage_claim(
    *,
    selection_label: str,
    coverage_kind: str,
    interrupted: bool,
) -> None:
    """Fail closed when a scoped or interrupted run is labeled as a full suite."""

    require_coverage_kind(coverage_kind)
    if interrupted and not is_partial_label(selection_label):
        raise ValueError(
            "interrupted run must be labeled partial; it is not a full-suite claim"
        )
    if coverage_kind == COVERAGE_SCOPED and not is_scoped_label(selection_label):
        raise ValueError(
            "scoped run is missing its scoped selection_label; "
            "this cannot be claimed as a full-suite result"
        )


def _journal_sha256(payload: Mapping[str, Any]) -> str:
    return _prefixed_sha256(dict(payload))


# contract-ratchet: allow non-persisted sidecar journal digest
def _prefixed_sha256(record: Mapping[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _prefixed_if_needed(value: str) -> str:
    validate_sha256(value, "selection_sha256", allow_prefix=True)
    if value.startswith("sha256:"):
        return value
    return f"sha256:{value}"


def _require_token(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResumeRefusedError(f"progress journal {field_name} is invalid")
    return value
